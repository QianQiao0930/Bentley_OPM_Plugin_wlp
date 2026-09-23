# -*- coding: utf-8 -*-
"""T 形架纯几何 / 数据逻辑单测（不依赖 Bentley 运行时）。

覆盖：所选**竖直线**的解析（允许 ±5° 微倾）、坐标架（立柱竖直、横担世界水平）、
类型 1（正 T 形架，立柱在下）与类型 2（吊架，立柱在上）的布置不变量、两类连接
（角钢背靠背 / H 型钢端面焊）、截面朝向与右手系、表 1 / 表 2 荷载查询与最大允许
H / L、管架编号。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_PLUGIN_DIR = os.path.dirname(_MODULE_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, 'T形架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import T形架_几何 as geom  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-9


def _line(base=(0.0, 0.0, 0.0), top=(0.0, 0.0, 1000.0)):
    base = tuple(float(v) for v in base)
    top = tuple(float(v) for v in top)
    length = math.sqrt(sum((top[i] - base[i]) ** 2 for i in range(3)))
    return geom.SelectedLine(base=base, top=top, length_mm=length)


def _member_world(variant_key, member_kind, line, arm_length_mm,
                  heading_deg=0.0, rack_type=1):
    """返回 ``(origin, axis_z, length_mm, points)``（世界坐标）。

    与 ``D12_G4-[T形_倒T形架].py`` 中 ``_build_member_element`` 的做法一致。
    """
    u_dir, v_dir, w_dir = geom.frame_axes(heading_deg)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, line.length_mm, arm_length_mm, rack_type)
    origin = tuple(
        line.base[i] + origin_uvw[0] * u_dir[i] + origin_uvw[1] * v_dir[i]
        + origin_uvw[2] * w_dir[i] for i in range(3))
    axis_x, axis_y, axis_z = (
        geom.world_direction(u_dir, v_dir, w_dir, axis)
        for axis in geom.member_axes(variant_key, member_kind, rack_type))
    frame = ssg.Frame(origin, axis_x, axis_y, axis_z)
    points = [point
              for segment in geom.sample_member(variant_key, member_kind, frame)
              for point in segment]
    return origin, axis_z, length_mm, points


def _bbox(points):
    return (
        min(point[0] for point in points), max(point[0] for point in points),
        min(point[1] for point in points), max(point[1] for point in points),
        min(point[2] for point in points), max(point[2] for point in points),
    )


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


class ParseLineTests(unittest.TestCase):
    def test_single_upward_segment(self):
        line = geom.parse_selected_line([[(0, 0, 0), (0, 0, 1200)]])
        self.assertAlmostEqual(line.length_mm, 1200.0, places=6)
        self.assertEqual(line.base, (0.0, 0.0, 0.0))
        self.assertEqual(line.top, (0.0, 0.0, 1200.0))

    def test_downward_segment_puts_base_at_the_lower_z(self):
        line = geom.parse_selected_line([[(0, 0, 900), (0, 0, 0)]])
        self.assertEqual(line.base, (0.0, 0.0, 0.0))
        self.assertEqual(line.top, (0.0, 0.0, 900.0))

    def test_slight_tilt_within_tolerance_is_accepted(self):
        """允许 ±5° 以内的轻微倾斜（与门型架一致）；H 取两端 Z 差。"""
        tilt_deg = geom.VERTICAL_TOLERANCE_DEG - 2.0
        tilt = math.radians(tilt_deg)
        top = (1000.0 * math.sin(tilt), 0.0, 1000.0 * math.cos(tilt))
        line = geom.parse_selected_line([[(0.0, 0.0, 0.0), top]])
        self.assertAlmostEqual(line.length_mm, 1000.0 * math.cos(tilt),
                               places=6)

    def test_horizontal_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_selected_line([[(0, 0, 0), (500, 0, 0)]])

    def test_forty_five_degree_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_selected_line([[(0, 0, 0), (500, 0, 500)]])

    def test_two_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_selected_line([[(0, 0, 0), (0, 0, 500), (0, 500, 500)]])

    def test_too_short_is_rejected(self):
        short = geom.MIN_LINE_LENGTH_MM - 1.0
        with self.assertRaises(ValueError):
            geom.parse_selected_line([[(0, 0, 0), (0, 0, short)]])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_selected_line([])


class AxisDirectionTests(unittest.TestCase):
    def test_heading_sets_the_crossbar_direction(self):
        for heading in (0.0, 90.0, 180.0, 270.0):
            u_dir, v_dir, w_dir = geom.frame_axes(heading)
            angle = math.radians(heading)
            self.assertAlmostEqual(u_dir[0], math.cos(angle), places=9)
            self.assertAlmostEqual(u_dir[1], math.sin(angle), places=9)
            self.assertAlmostEqual(u_dir[2], 0.0, places=9)
            # 立柱始终竖直向上。
            self.assertEqual(w_dir, (0.0, 0.0, 1.0))

    def test_axes_are_orthonormal_and_right_handed(self):
        for heading in (0.0, 30.0, 120.0, 250.0):
            u_dir, v_dir, w_dir = geom.frame_axes(heading)
            for vector in (u_dir, v_dir, w_dir):
                self.assertAlmostEqual(_dot(vector, vector), 1.0, places=9)
            self.assertAlmostEqual(_dot(u_dir, v_dir), 0.0, places=9)
            self.assertAlmostEqual(_dot(u_dir, w_dir), 0.0, places=9)
            self.assertAlmostEqual(_dot(v_dir, w_dir), 0.0, places=9)
            product = _cross(u_dir, v_dir)
            for index in range(3):
                self.assertAlmostEqual(product[index], w_dir[index], places=12)


class LayoutTests(unittest.TestCase):
    """立柱竖直、朝向 0 时的一整套布置不变量（此时局部 = 世界）。"""

    ARM_LENGTH = 400.0

    def _members(self, variant_key, arm_length=None, height_mm=1000.0,
                 heading_deg=0.0, top=None):
        arm_length = self.ARM_LENGTH if arm_length is None else arm_length
        line = _line(top=top or (0.0, 0.0, height_mm))
        post = _member_world(variant_key, 'post', line, arm_length, heading_deg)
        arm = _member_world(variant_key, 'arm', line, arm_length, heading_deg)
        return line, post, arm

    def test_post_section_is_centred_on_the_line(self):
        """立柱截面外接矩形中心落在所选直线上（u = 0），两侧各 ∓W/2。"""
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            _line_obj, post, arm = self._members(variant_key)
            post_box = _bbox(post[3])
            self.assertAlmostEqual(post_box[0], -width / 2.0, places=6)
            self.assertAlmostEqual(post_box[1], width / 2.0, places=6)

    def test_arm_is_centred_on_the_line(self):
        """横担以 u = 0 为中点：两端各 ∓L/2。"""
        for variant_key in sorted(geom.VARIANTS):
            _line_obj, post, arm = self._members(variant_key)
            origin, axis_z, length, _points = arm
            self.assertAlmostEqual(origin[0], -self.ARM_LENGTH / 2.0, places=6)
            self.assertAlmostEqual(length, self.ARM_LENGTH, places=9)
            beam_end = origin[0] + length * axis_z[0]
            self.assertAlmostEqual(origin[0], -beam_end, places=6)

    def test_arm_length_is_the_full_length_l(self):
        for variant_key in sorted(geom.VARIANTS):
            for arm_length in (250.0, 1000.0, 2000.0):
                _line_obj, post, arm = self._members(variant_key, arm_length)
                self.assertAlmostEqual(arm[2], arm_length, places=9)

    def test_arm_top_face_lies_at_the_top_of_the_line(self):
        for variant_key in sorted(geom.VARIANTS):
            _line_obj, post, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], 1000.0, places=6)

    def test_arm_section_is_centred_on_the_frame_plane(self):
        for variant_key in sorted(geom.VARIANTS):
            x_extent = geom.section_box(variant_key)[0]
            _line_obj, post, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[2], -x_extent / 2.0, places=6)
            self.assertAlmostEqual(arm_box[3], x_extent / 2.0, places=6)

    # -- 角钢：背靠背、非通长 ----------------------------------------------

    def test_angle_post_is_back_to_back_with_arm_vertical_leg(self):
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            self.assertAlmostEqual(geom.post_v_offset(variant_key), width,
                                   places=9)
            _line_obj, post, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[3], width / 2.0, places=6)
            post_box = _bbox(post[3])
            self.assertAlmostEqual(post_box[2], arm_box[3], places=6)
            self.assertGreaterEqual(post_box[2], arm_box[3] - TOL)

    def test_angle_post_is_not_full_length(self):
        """角钢立柱非通长：顶端比横担水平肢下表面低 10 mm 留作施焊。"""
        for variant_key in ('A', 'B', 'C'):
            thickness = geom.section_dimensions(variant_key)['t']
            _line_obj, post, arm = self._members(variant_key)
            expected = 1000.0 - thickness - geom.WELD_GAP_MM
            self.assertAlmostEqual(
                geom.post_length(variant_key, 1000.0), expected, places=9)
            leg_top = post[0][2] + post[2] * post[1][2]
            self.assertAlmostEqual(leg_top, expected, places=6)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5] - thickness - leg_top,
                                   geom.WELD_GAP_MM, places=6)

    def test_angle_weld_contact_length(self):
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            thickness = geom.section_dimensions(variant_key)['t']
            self.assertAlmostEqual(
                geom.weld_contact_length(variant_key),
                width - thickness - geom.WELD_GAP_MM, places=9)
            self.assertGreater(geom.weld_contact_length(variant_key), 0.0)

    def test_angle_arm_puts_the_horizontal_leg_on_top(self):
        line = _line()
        origin, axis_z, length, points = _member_world('A', 'arm', line, 400.0)
        side = geom.section_dimensions('A')['B']
        top = [point for point in points
               if abs(point[2] - 1000.0) < 1.0e-6]
        self.assertTrue(top)
        self.assertGreaterEqual(max(p[1] for p in top) - min(p[1] for p in top),
                                side - geom.section_dimensions('A')['t'])
        self.assertAlmostEqual(max(point[1] for point in points), side / 2.0,
                               places=6)

    # -- H 型钢：端面焊接、腹板共面 ----------------------------------------

    def test_hbeam_post_meets_the_arm_underside(self):
        """H 型钢立柱顶面顶焊在横担下翼缘下表面（端面焊接，无间隙）。"""
        for variant_key in ('D', 'E', 'F', 'G'):
            depth = geom.beam_depth(variant_key)
            _line_obj, post, arm = self._members(variant_key)
            self.assertAlmostEqual(
                geom.post_length(variant_key, 1000.0), 1000.0 - depth,
                places=9)
            leg_top = post[0][2] + post[2] * post[1][2]
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(leg_top, arm_box[4], places=6)
            self.assertAlmostEqual(geom.weld_contact_length(variant_key), 0.0,
                                   places=9)

    def test_hbeam_webs_are_coplanar(self):
        """立柱与横担腹板都在 v = 0（截面 v 范围关于 0 对称）。"""
        for variant_key in ('D', 'E', 'F', 'G'):
            self.assertAlmostEqual(geom.post_v_offset(variant_key), 0.0,
                                   places=9)
            _line_obj, post, arm = self._members(variant_key)
            for member in (post, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2] + box[3], 0.0, places=6)

    def test_hbeam_post_and_arm_flanges_symmetric(self):
        for variant_key in ('D', 'E', 'F', 'G'):
            flange = geom.section_dimensions(variant_key)['B']
            _line_obj, post, arm = self._members(variant_key)
            for member in (post, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2], -flange / 2.0, places=6)
                self.assertAlmostEqual(box[3], flange / 2.0, places=6)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm'):
                axis_x, axis_y, axis_z = geom.member_axes(variant_key,
                                                          member_kind)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)


class HangerLayoutTests(unittest.TestCase):
    """类型 2（吊架，立柱在上）：横担在下端、管位朝上，立柱自横担上表面向上。"""

    ARM_LENGTH = 400.0
    HEIGHT = 1000.0

    def _members(self, variant_key, arm_length=None, height_mm=None):
        arm_length = self.ARM_LENGTH if arm_length is None else arm_length
        height_mm = self.HEIGHT if height_mm is None else height_mm
        line = _line(top=(0.0, 0.0, height_mm))
        post = _member_world(variant_key, 'post', line, arm_length,
                             rack_type=2)
        arm = _member_world(variant_key, 'arm', line, arm_length, rack_type=2)
        return line, post, arm

    def test_arm_is_centred_on_the_line(self):
        for variant_key in sorted(geom.VARIANTS):
            _line_obj, post, arm = self._members(variant_key)
            origin, axis_z, length, _points = arm
            self.assertAlmostEqual(length, self.ARM_LENGTH, places=9)
            start = origin[0]
            end = start + length * axis_z[0]
            self.assertAlmostEqual(start, -end, places=6)
            self.assertAlmostEqual(abs(start), self.ARM_LENGTH / 2.0, places=6)

    def test_post_spans_from_the_crossbar_to_the_structure(self):
        for variant_key in sorted(geom.VARIANTS):
            _line_obj, post, arm = self._members(variant_key)
            post_box = _bbox(post[3])
            leg_top = post[0][2] + post[2] * post[1][2]
            self.assertAlmostEqual(leg_top, self.HEIGHT, places=6)
            bottom = (0.0 if geom.variant_is_hbeam(variant_key)
                      else -geom.weld_contact_length(variant_key))
            self.assertAlmostEqual(post_box[4], bottom, places=6)

    def test_hbeam_crossbar_top_face_is_the_pipe_seat(self):
        """H 型钢横担上翼缘上表面位于竖直线下端（w = 0），立柱端面焊在其上。"""
        for variant_key in ('D', 'E', 'F', 'G'):
            _line_obj, post, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], 0.0, places=6)
            self.assertAlmostEqual(arm_box[4], -geom.beam_depth(variant_key),
                                   places=6)
            self.assertAlmostEqual(post[0][2], 0.0, places=6)

    def test_angle_crossbar_horizontal_leg_top_is_the_pipe_seat(self):
        """角钢横担水平肢在顶部、其上表面（管位面）在 w = 0，竖直肢向下。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            _line_obj, post, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], 0.0, places=6)
            self.assertAlmostEqual(arm_box[4], -width, places=6)
            seat = [point for point in arm[3] if abs(point[2]) < 1.0e-6]
            self.assertTrue(seat)
            seat_span = (max(point[1] for point in seat)
                         - min(point[1] for point in seat))
            # 管位面跨度接近肢宽（扣除两端圆角），明显宽于半个肢宽。
            self.assertGreater(seat_span, width / 2.0)

    def test_angle_post_is_back_to_back_in_hanger(self):
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            _line_obj, post, arm = self._members(variant_key)
            post_box = _bbox(post[3])
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(post_box[2], width / 2.0, places=6)
            self.assertAlmostEqual(arm_box[3], width / 2.0, places=6)

    def test_hbeam_webs_are_coplanar_in_hanger(self):
        for variant_key in ('D', 'E', 'F', 'G'):
            _line_obj, post, arm = self._members(variant_key)
            for member in (post, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2] + box[3], 0.0, places=6)

    def test_hanger_post_length(self):
        for variant_key in ('A', 'B', 'C'):
            self.assertAlmostEqual(
                geom.post_length(variant_key, 1000.0, 2),
                1000.0 + geom.weld_contact_length(variant_key), places=9)
        for variant_key in ('D', 'E', 'F', 'G'):
            self.assertAlmostEqual(
                geom.post_length(variant_key, 1000.0, 2), 1000.0, places=9)

    def test_angle_hanger_weld_contact(self):
        """角钢立柱下探段与横担竖直肢的搭接长度 = W − 肢厚 − 10（同类型 1）。"""
        for variant_key in ('A', 'B', 'C'):
            _line_obj, post, arm = self._members(variant_key)
            post_bottom = post[0][2]
            post_top = post_bottom + post[2] * post[1][2]
            arm_box = _bbox(arm[3])
            overlap = (min(post_top, arm_box[5])
                       - max(post_bottom, arm_box[4]))
            self.assertAlmostEqual(overlap,
                                   geom.weld_contact_length(variant_key),
                                   places=6)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm'):
                axis_x, axis_y, axis_z = geom.member_axes(variant_key,
                                                          member_kind, 2)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)


class LoadTableTests(unittest.TestCase):
    def test_table_one_values(self):
        expected = {
            ('A', 500, 250): 1.0,
            ('A', 1000, 250): 0.5,
            ('B', 500, 500): 1.8,
            ('B', 1000, 250): 1.8,
            ('C', 500, 1000): 2.4,
            ('C', 1000, 750): 1.2,
            ('C', 1500, 1000): 0.6,
        }
        for (key, height, arm), value in expected.items():
            self.assertAlmostEqual(
                geom.allowable_load(key, height, arm).value, value, places=9,
                msg='%s H=%d L=%d' % (key, height, arm))

    def test_table_two_values(self):
        expected = {
            ('D', 1000, 500): 20.0,
            ('D', 2000, 1000): 5.0,
            ('E', 1000, 2000): 15.0,
            ('E', 3000, 2000): 10.0,
            ('F', 4000, 2000): 10.0,
            ('G', 1000, 2000): 40.0,
            ('G', 4000, 500): 20.0,
        }
        for (key, height, arm), value in expected.items():
            self.assertAlmostEqual(
                geom.allowable_load(key, height, arm).value, value, places=9,
                msg='%s H=%d L=%d' % (key, height, arm))

    def test_blank_cells_report_no_value(self):
        self.assertIsNone(geom.allowable_load('A', 500, 500).value)
        self.assertIsNone(geom.allowable_load('B', 1000, 750).value)
        self.assertIsNone(geom.allowable_load('D', 2000, 1500).value)
        self.assertIsNone(geom.allowable_load('E', 4000, 500).value)

    def test_max_allowed_height_and_arm_length(self):
        expected = {
            'A': (1000, 250),
            'B': (1000, 500),
            'C': (1500, 1000),
            'D': (2000, 1000),
            'E': (3000, 2000),
            'F': (4000, 2000),
            'G': (4000, 2000),
        }
        for key, (height, arm) in expected.items():
            self.assertEqual(geom.max_allowed_height(key), height,
                             msg='%s Hmax' % key)
            self.assertEqual(geom.max_allowed_arm_length(key), arm,
                             msg='%s Lmax' % key)

    def test_ground_anchor_lift_is_grout_plus_plate(self):
        """地面固定时钢构架相对线端的抬升 = 灌浆梯台厚 + 锚板厚。"""
        for key in sorted(geom.VARIANTS):
            spec = geom.ground_anchor_spec(key)
            self.assertAlmostEqual(
                geom.ground_anchor_lift(key),
                geom.GROUND_GROUT_THICKNESS_MM + spec['plate_t'], places=9)
        # E 子项：25 + 16 = 41，正好解释 H=1600 时地面到横担顶的 1641。
        self.assertAlmostEqual(geom.ground_anchor_lift('E'), 41.0, places=9)

    def test_height_rounds_down_conservatively(self):
        """H=1900 按表中 1000 取用（偏安全），而不是 2000。"""
        result = geom.allowable_load('G', 1900.0, 500.0)
        self.assertEqual(result.used_height_mm, 1000)
        self.assertAlmostEqual(result.value, 100.0, places=9)

    def test_out_of_range_is_reported(self):
        below = geom.allowable_load('A', 400.0, 250.0)
        self.assertIsNone(below.value)
        self.assertIn('小于表中最小值', below.message)
        above = geom.allowable_load('A', 1000.0, 2500.0)
        self.assertIsNone(above.value)
        self.assertIn('超出表中上限', above.message)


class VariantTests(unittest.TestCase):
    def test_specifications_match_table_three(self):
        expected = {'A': '∠50×6', 'B': '∠75×7', 'C': '∠100×10',
                    'D': 'H100×100×6×8', 'E': 'H150×150×7×10',
                    'F': 'H200×200×8×12', 'G': 'H250×250×9×14'}
        self.assertEqual(
            dict((key, geom.specification(key)) for key in geom.VARIANTS),
            expected)

    def test_families(self):
        for key in ('A', 'B', 'C'):
            self.assertFalse(geom.variant_is_hbeam(key))
        for key in ('D', 'E', 'F', 'G'):
            self.assertTrue(geom.variant_is_hbeam(key))

    def test_section_dimensions_resolve(self):
        self.assertAlmostEqual(geom.section_dimensions('A')['B'], 50.0)
        self.assertAlmostEqual(geom.section_dimensions('C')['B'], 100.0)
        self.assertAlmostEqual(geom.section_dimensions('D')['H'], 100.0)
        self.assertAlmostEqual(geom.section_dimensions('G')['H'], 250.0)

    def test_supported_rack_types(self):
        for key in sorted(geom.VARIANTS):
            self.assertTrue(geom.variant_supports_type(key, 1))
            self.assertTrue(geom.variant_supports_type(key, 2))
            self.assertFalse(geom.variant_supports_type(key, 3))
            self.assertFalse(geom.variant_supports_type(key, 'x'))
        self.assertFalse(geom.hanger_type(1))
        self.assertTrue(geom.hanger_type(2))
        self.assertFalse(geom.hanger_type(3))

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.specification('Z')


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_pipe_rack_number('D12', 1, 'a', 1000.0, 400.0),
            'D12-1-A-1000-400')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(geom.build_pipe_rack_number('', 1, 'A', 1000, 400), '')
        self.assertEqual(geom.build_pipe_rack_number('   ', 1, 'A', 1000, 400),
                         '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(-0.5), 0)


if __name__ == '__main__':
    unittest.main()
