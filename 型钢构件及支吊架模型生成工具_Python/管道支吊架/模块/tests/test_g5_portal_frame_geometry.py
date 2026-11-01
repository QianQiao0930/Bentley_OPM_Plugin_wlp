# -*- coding: utf-8 -*-
"""G5 地面上生根的门型架：纯几何 / 数据逻辑单测（不依赖 Bentley 运行时）。

覆盖：竖直线解析（地面 → 横担顶面）、立柱与横担的布置不变量（净距
``B = L − 2×25 − 2W``、横担以整组中心线为中点、两端各超立柱外缘 25）、
角钢背靠背 / H 型钢腹板共面与端面焊接、表 1 允许荷载（MAX.H × L）、
表 2 锚板 / 锚栓与抬升量、管架编号 ``名称-子项-H-L``。
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
_GEOM_DIR = os.path.join(_MODULE_DIR, 'G5门型架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import G5门型架_几何 as geom  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-9


def _plane_dirs(heading_deg):
    heading = math.radians(heading_deg)
    return ((math.cos(heading), math.sin(heading), 0.0),
            (-math.sin(heading), math.cos(heading), 0.0))


def _member_axes_world(variant_key, member_kind, heading_deg=0.0,
                       mirror_u=False):
    run_dir, v_dir = _plane_dirs(heading_deg)
    world = []
    for ux, vx, wx in geom.member_axes(variant_key, member_kind, mirror_u):
        world.append((ux * run_dir[0] + vx * v_dir[0],
                      ux * run_dir[1] + vx * v_dir[1],
                      wx))
    return tuple(world)


def _post(base=(0.0, 0.0, 0.0), height_mm=1000.0):
    """``base`` 取锚板顶面中心（局部 w = 0）；``height_mm`` 为构架高度。"""
    return geom.VerticalPost(
        base=tuple(float(v) for v in base),
        top=(base[0], base[1], base[2] + float(height_mm)),
        height_mm=float(height_mm),
    )


def _member_world(variant_key, member_kind, post, arm_length_mm,
                  heading_deg=0.0, post_axis_u=0.0, mirror_u=False):
    """返回 ``(origin, axis_z, length_mm, world_points)``。"""
    run_dir, v_dir = _plane_dirs(heading_deg)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, post.height_mm, arm_length_mm, post_axis_u)
    origin = (
        post.base[0] + origin_uvw[0] * run_dir[0] + origin_uvw[1] * v_dir[0],
        post.base[1] + origin_uvw[0] * run_dir[1] + origin_uvw[1] * v_dir[1],
        post.base[2] + origin_uvw[2],
    )
    axis_x, axis_y, axis_z = _member_axes_world(
        variant_key, member_kind, heading_deg, mirror_u)
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


class ParseVerticalPostTests(unittest.TestCase):
    def test_single_vertical_segment(self):
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, 800.0)]])
        self.assertAlmostEqual(post.height_mm, 800.0, places=6)
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 800.0))

    def test_downward_segment_is_normalised(self):
        """端点顺序颠倒时，低端始终是地面（梯台底面）。"""
        post = geom.parse_vertical_post([[(0.0, 0.0, 900.0), (0.0, 0.0, 0.0)]])
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 900.0))
        self.assertAlmostEqual(post.height_mm, 900.0, places=6)

    def test_slight_tilt_within_tolerance_is_accepted(self):
        tilt_deg = geom.VERTICAL_TOLERANCE_DEG - 2.0
        tilt = math.radians(tilt_deg)
        top = (1000.0 * math.sin(tilt), 0.0, 1000.0 * math.cos(tilt))
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), top]])
        self.assertAlmostEqual(post.height_mm, 1000.0 * math.cos(tilt),
                               places=6)

    def test_horizontal_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (500.0, 0.0, 0.0)]])

    def test_two_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post(
                [[(0.0, 0.0, 0.0), (0.0, 0.0, 500.0), (0.0, 500.0, 500.0)]])

    def test_too_short_is_rejected(self):
        short = geom.MIN_FRAME_HEIGHT_MM - 1.0
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, short)]])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([])


class LayoutTests(unittest.TestCase):
    """横担全长 L 给定时的一整套布置不变量。"""

    ARM_LENGTH = 1500.0
    FRAME_HEIGHT = 1000.0

    def _members(self, variant_key, arm_length=None, height_mm=None,
                 heading_deg=0.0):
        arm_length = self.ARM_LENGTH if arm_length is None else arm_length
        height_mm = self.FRAME_HEIGHT if height_mm is None else height_mm
        post = _post(height_mm=height_mm)
        left = _member_world(
            variant_key, 'post', post, arm_length, heading_deg,
            geom.post_axis_offset(variant_key, arm_length, 'left'))
        right = _member_world(
            variant_key, 'post', post, arm_length, heading_deg,
            geom.post_axis_offset(variant_key, arm_length, 'right'),
            mirror_u=True)
        arm = _member_world(variant_key, 'arm', post, arm_length, heading_deg)
        return post, left, right, arm

    def test_net_span_between_inner_faces_equals_b(self):
        for variant_key in sorted(geom.VARIANTS):
            # G 子项截面宽 250，L 必须大于 50 + 2×250 才成立。
            for arm_length in (1000.0, 1500.0, 2000.0):
                post, left, right, arm = self._members(variant_key, arm_length)
                left_box = _bbox(left[3])
                right_box = _bbox(right[3])
                self.assertAlmostEqual(
                    right_box[0] - left_box[1],
                    geom.net_span(variant_key, arm_length), places=6,
                    msg='%s L=%.0f' % (variant_key, arm_length))

    def test_net_span_formula(self):
        """B = L − 2×25 − 2W（图上横担两端各超立柱外缘 25）。"""
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            self.assertAlmostEqual(
                geom.net_span(variant_key, self.ARM_LENGTH),
                self.ARM_LENGTH - 2.0 * geom.ARM_END_OVERHANG_MM - 2.0 * width,
                places=9)
            self.assertAlmostEqual(
                geom.post_axis_pitch(variant_key, self.ARM_LENGTH),
                geom.net_span(variant_key, self.ARM_LENGTH) + width, places=9)

    def test_selected_line_is_the_assembly_centreline(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            self.assertAlmostEqual(
                geom.post_axis_offset(variant_key, self.ARM_LENGTH, 'left'),
                -geom.post_axis_offset(variant_key, self.ARM_LENGTH, 'right'),
                places=9)
            self.assertAlmostEqual(left_box[0], -right_box[1], places=6)
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertAlmostEqual(u_start, -length / 2.0, places=9)
            self.assertAlmostEqual(arm[0][0], -beam_end, places=6)

    def test_post_section_is_centred_on_its_own_axis(self):
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            post, left, right, arm = self._members(variant_key)
            left_axis = geom.post_axis_offset(variant_key, self.ARM_LENGTH,
                                              'left')
            left_box = _bbox(left[3])
            self.assertAlmostEqual(left_box[0], left_axis - width / 2.0,
                                   places=6)
            self.assertAlmostEqual(left_box[1], left_axis + width / 2.0,
                                   places=6)

    def test_beam_ends_overhang_post_outer_faces_by_25(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertAlmostEqual(left_box[0] - u_start,
                                   geom.ARM_END_OVERHANG_MM, places=6)
            self.assertAlmostEqual(beam_end - right_box[1],
                                   geom.ARM_END_OVERHANG_MM, places=6)
            self.assertAlmostEqual(length, self.ARM_LENGTH, places=9)

    def test_beam_spans_over_both_posts(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            u_start = geom.beam_span(variant_key, self.ARM_LENGTH)[0]
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertLessEqual(u_start, _bbox(left[3])[0])
            self.assertGreaterEqual(beam_end, _bbox(right[3])[1])

    def test_beam_top_face_lies_at_the_frame_height(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], post.height_mm, places=6)

    def test_posts_stand_on_the_plate_top_face(self):
        """立柱底面在锚板顶面（局部 w = 0），构架高度由地面抬升量另算。"""
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            for leg in (left, right):
                self.assertAlmostEqual(leg[0][2], 0.0, places=9)

    def test_beam_section_is_centred_on_the_frame_plane(self):
        for variant_key in sorted(geom.VARIANTS):
            x_extent = geom.section_box(variant_key)[0]
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[2], -x_extent / 2.0, places=6)
            self.assertAlmostEqual(arm_box[3], x_extent / 2.0, places=6)

    def test_angle_posts_are_back_to_back_with_the_arm_leg(self):
        """角钢：立柱镜像到横担竖直肢外侧，背面的 v = W/2 相贴。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            self.assertAlmostEqual(geom.post_v_offset(variant_key), width,
                                   places=9)
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[3], width / 2.0, places=6)
            for leg in (left, right):
                leg_box = _bbox(leg[3])
                self.assertAlmostEqual(leg_box[2], arm_box[3], places=6)
                self.assertGreaterEqual(leg_box[2], width / 2.0 - TOL)

    def test_angle_post_stops_10mm_below_the_arm_horizontal_leg(self):
        for variant_key in ('A', 'B', 'C'):
            thickness = geom.section_dimensions(variant_key)['t']
            post, left, right, arm = self._members(variant_key)
            height = post.height_mm
            expected = height - thickness - geom.WELD_GAP_MM
            self.assertAlmostEqual(
                geom.post_length(variant_key, height), expected, places=9)
            leg_top = left[0][2] + left[2] * left[1][2]
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

    def test_angle_legs_are_mirror_symmetric_with_openings_outward(self):
        for variant_key in ('A', 'B', 'C'):
            left = geom.post_opening_direction(variant_key, mirror_u=False)
            right = geom.post_opening_direction(variant_key, mirror_u=True)
            self.assertAlmostEqual(left[0], -1.0, places=9)
            self.assertAlmostEqual(right[0], 1.0, places=9)
            self.assertAlmostEqual(left[1], right[1], places=9)

    def test_both_posts_keep_the_same_v_range(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            self.assertAlmostEqual(left_box[2], right_box[2], places=6)
            self.assertAlmostEqual(left_box[3], right_box[3], places=6)

    def test_hbeam_webs_are_coplanar_with_the_arm_web(self):
        """H 型钢：立柱与横担腹板同在 v = 0，截面关于 0 对称、无需镜像。"""
        for variant_key in ('D', 'E', 'F', 'G'):
            self.assertAlmostEqual(geom.post_v_offset(variant_key), 0.0,
                                   places=9)
            self.assertAlmostEqual(geom.weld_contact_length(variant_key), 0.0,
                                   places=9)
            post, left, right, arm = self._members(variant_key)
            for member in (left, right, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2] + box[3], 0.0, places=6)

    def test_hbeam_post_top_butts_the_arm_bottom_flange(self):
        for variant_key in ('D', 'E', 'F', 'G'):
            depth = geom.beam_depth(variant_key)
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            for leg in (left, right):
                leg_top = leg[0][2] + leg[2] * leg[1][2]
                self.assertAlmostEqual(leg_top, arm_box[4], places=6)
                self.assertAlmostEqual(leg[2], post.height_mm - depth,
                                       places=9)

    def test_post_length_per_family(self):
        """角钢 H − 肢厚 − 10；H 型钢 H − 横担截面高。"""
        for variant_key in ('A', 'B', 'C'):
            thickness = geom.section_dimensions(variant_key)['t']
            self.assertAlmostEqual(
                geom.post_length(variant_key, self.FRAME_HEIGHT),
                self.FRAME_HEIGHT - thickness - geom.WELD_GAP_MM, places=9)
        for variant_key in ('D', 'E', 'F', 'G'):
            self.assertAlmostEqual(
                geom.post_length(variant_key, self.FRAME_HEIGHT),
                self.FRAME_HEIGHT - geom.beam_depth(variant_key), places=9)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm'):
                for mirror_u in (False, True):
                    axis_x, axis_y, axis_z = geom.member_axes(
                        variant_key, member_kind, mirror_u)
                    product = _cross(axis_x, axis_y)
                    for index in range(3):
                        self.assertAlmostEqual(product[index], axis_z[index],
                                               places=12)

    def test_heading_rotates_the_frame_plane(self):
        post = _post(height_mm=self.FRAME_HEIGHT)
        start = geom.beam_span('C', self.ARM_LENGTH)[0]
        for heading in (0.0, 90.0, 180.0, 270.0):
            run_dir, _v_dir = _plane_dirs(heading)
            origin, axis_z, length, points = _member_world(
                'C', 'arm', post, self.ARM_LENGTH, heading)
            self.assertAlmostEqual(axis_z[0], run_dir[0], places=9)
            self.assertAlmostEqual(origin[0], run_dir[0] * start, places=6)
            self.assertAlmostEqual(origin[1], run_dir[1] * start, places=6)
            self.assertAlmostEqual(_bbox(points)[5], post.height_mm, places=6)
            self.assertAlmostEqual(length, self.ARM_LENGTH, places=9)

    def test_too_short_arm_length_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.net_span('G', 100.0)


class GroundBaseTests(unittest.TestCase):
    """表 2：锚板 / 膨胀锚栓 / 地坪最小厚度，以及钢构架抬升量。"""

    def test_table_two_values(self):
        expected = {
            'A': (150.0, 100.0, 10.0, 10.0, 8.0, 120.0, 55.0, 100.0),
            'B': (210.0, 150.0, 14.0, 10.0, 12.0, 160.0, 90.0, 150.0),
            'C': (260.0, 200.0, 18.0, 12.0, 16.0, 180.0, 100.0, 150.0),
            'D': (260.0, 200.0, 18.0, 12.0, 16.0, 180.0, 100.0, 150.0),
            'E': (350.0, 250.0, 22.0, 16.0, 20.0, 220.0, 125.0, 150.0),
            'F': (400.0, 300.0, 22.0, 20.0, 20.0, 220.0, 125.0, 150.0),
            'G': (500.0, 400.0, 22.0, 20.0, 20.0, 220.0, 125.0, 150.0),
        }
        for variant_key, values in expected.items():
            spec = geom.ground_anchor_spec(variant_key)
            actual = (spec['plate_e'], spec['hole_spacing_f'],
                      spec['hole_dia_g'], spec['plate_t'], spec['bolt_dia'],
                      spec['bolt_len'], spec['embed'], spec['min_h'])
            self.assertEqual(actual, values, msg=variant_key)

    def test_ground_lift_is_grout_plus_plate(self):
        for variant_key in sorted(geom.VARIANTS):
            plate_t = geom.ground_anchor_spec(variant_key)['plate_t']
            self.assertAlmostEqual(
                geom.ground_lift(variant_key),
                geom.GROUND_GROUT_THICKNESS_MM + plate_t, places=9)
        self.assertAlmostEqual(geom.ground_lift('A'), 35.0, places=9)
        self.assertAlmostEqual(geom.ground_lift('G'), 45.0, places=9)

    def test_min_pavement_thickness(self):
        self.assertAlmostEqual(geom.min_pavement_thickness('A'), 100.0,
                               places=9)
        self.assertAlmostEqual(geom.min_pavement_thickness('G'), 150.0,
                               places=9)

    def test_spec_is_a_copy(self):
        spec = geom.ground_anchor_spec('A')
        spec['plate_e'] = 999.0
        self.assertAlmostEqual(
            geom.ground_anchor_spec('A')['plate_e'], 150.0, places=9)


class LoadTableTests(unittest.TestCase):
    """表 1 逐格核对（kN）；「—」为 None。"""

    def test_table_one_values(self):
        expected = {
            ('A', 500, 500): 2.0,
            ('B', 500, 500): 4.0,
            ('B', 500, 1000): 2.0,
            ('B', 1000, 500): 2.0,
            ('B', 1000, 1000): 1.0,
            ('C', 500, 500): 8.0,
            ('C', 1000, 1000): 2.0,
            ('D', 1000, 500): 20.0,
            ('D', 1500, 1000): 8.0,
            ('E', 1000, 1000): 40.0,
            ('E', 2000, 2000): 20.0,
            ('F', 1000, 1500): 40.0,
            ('F', 2000, 2000): 30.0,
            ('F', 3000, 1000): 20.0,
            ('G', 1000, 2000): 80.0,
            ('G', 2000, 1500): 60.0,
            ('G', 3000, 2000): 40.0,
        }
        for (key, height, arm), value in expected.items():
            result = geom.allowable_load(key, height, arm)
            self.assertAlmostEqual(result.value, value, places=9,
                                   msg='%s H=%d L=%d' % (key, height, arm))

    def test_blank_cells_report_no_value(self):
        self.assertIsNone(geom.allowable_load('A', 500, 1000).value)
        self.assertIsNone(geom.allowable_load('B', 500, 1500).value)
        self.assertIn('为空', geom.allowable_load('A', 500, 1000).message)

    def test_height_uses_the_covering_max_height_row(self):
        """H 取「覆盖输入的最小 MAX.H 行」：H=1500 落 MAX.H=2000 行（60 kN）。"""
        result = geom.allowable_load('G', 1500.0, 1000.0)
        self.assertAlmostEqual(result.value, 60.0, places=9)
        self.assertEqual(result.used_height_mm, 2000)
        # H 小于全部 MAX.H 时落在第一行。
        low = geom.allowable_load('G', 800.0, 1000.0)
        self.assertAlmostEqual(low.value, 100.0, places=9)
        self.assertEqual(low.used_height_mm, 1000)
        # 同一 MAX.H 行内，L 越大荷载越小；H=2500 覆盖到 MAX.H=3000 行。
        self.assertAlmostEqual(
            geom.allowable_load('G', 2500.0, 1000.0).value, 40.0, places=9)
        self.assertEqual(
            geom.allowable_load('G', 2500.0, 1500.0).used_height_mm, 3000)
        self.assertAlmostEqual(
            geom.allowable_load('G', 2500.0, 1500.0).value, 40.0, places=9)

    def test_arm_length_rounds_up_to_the_next_column(self):
        self.assertAlmostEqual(
            geom.allowable_load('G', 1000.0, 501.0).value, 100.0, places=9)
        self.assertAlmostEqual(
            geom.allowable_load('E', 1000.0, 1200.0).value, 20.0, places=9)

    def test_out_of_range_is_reported(self):
        above_height = geom.allowable_load('A', 600.0, 500.0)
        self.assertIsNone(above_height.value)
        self.assertIn('超出表中最大 MAX.H', above_height.message)
        above = geom.allowable_load('A', 500.0, 2500.0)
        self.assertIsNone(above.value)
        self.assertIn('超出表中上限', above.message)

    def test_max_height_and_max_arm_length(self):
        expected = {'A': (500.0, 1000.0), 'B': (1000.0, 1000.0),
                    'C': (1000.0, 1000.0), 'D': (1500.0, 1000.0),
                    'E': (2000.0, 2000.0), 'F': (3000.0, 2000.0),
                    'G': (3000.0, 2000.0)}
        for variant_key, (height, arm) in expected.items():
            self.assertAlmostEqual(geom.max_height(variant_key), height,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.max_arm_length(variant_key), arm,
                                   places=9, msg=variant_key)


class VariantTests(unittest.TestCase):
    def test_specifications_match_table_one(self):
        expected = {'A': '∠50×6', 'B': '∠75×7', 'C': '∠100×10',
                    'D': 'H100×100×6×8', 'E': 'H150×150×7×10',
                    'F': 'H200×200×8×12', 'G': 'H250×250×9×14'}
        self.assertEqual(
            dict((key, geom.specification(key)) for key in geom.VARIANTS),
            expected)

    def test_section_dimensions_resolve(self):
        """按图的子项表：立柱沿 u 的截面宽 = 横担截面高 = 型钢高度/肢宽。"""
        expected = {'A': (50.0, 50.0), 'B': (75.0, 75.0), 'C': (100.0, 100.0),
                    'D': (100.0, 100.0), 'E': (150.0, 150.0),
                    'F': (200.0, 200.0), 'G': (250.0, 250.0)}
        for variant_key, (width, flange) in expected.items():
            self.assertAlmostEqual(geom.inplane_width(variant_key), width,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.beam_depth(variant_key), width,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.section_box(variant_key)[0], flange,
                                   places=9, msg=variant_key)

    def test_raw_section_tables_resolve(self):
        for variant_key in ('A', 'B', 'C'):
            section = geom.section_dimensions(variant_key)
            self.assertIn('B', section)
            self.assertIn('t', section)
        for variant_key in ('D', 'E', 'F', 'G'):
            section = geom.section_dimensions(variant_key)
            self.assertIn('H', section)
            self.assertIn('t2', section)

    def test_width_and_depth_per_family(self):
        for variant_key in ('A', 'B', 'C'):
            self.assertFalse(geom.variant_is_hbeam(variant_key))
            self.assertAlmostEqual(geom.inplane_width(variant_key),
                                   geom.section_dimensions(variant_key)['B'],
                                   places=9)
        for variant_key in ('D', 'E', 'F', 'G'):
            self.assertTrue(geom.variant_is_hbeam(variant_key))
            self.assertAlmostEqual(geom.inplane_width(variant_key),
                                   geom.section_dimensions(variant_key)['H'],
                                   places=9)
            self.assertAlmostEqual(geom.beam_depth(variant_key),
                                   geom.section_dimensions(variant_key)['H'],
                                   places=9)
            self.assertAlmostEqual(
                geom.beam_flange_thickness(variant_key),
                geom.section_dimensions(variant_key)['t2'], places=9)

    def test_variant_choices_are_sorted(self):
        self.assertEqual([key for key, _label in geom.variant_choices()],
                         ['A', 'B', 'C', 'D', 'E', 'F', 'G'])

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.specification('Z')
        with self.assertRaises(ValueError):
            geom.ground_anchor_spec('Z')


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_pipe_rack_number('G5', 'a', 500.0, 1000.0),
            'G5-A-500-1000')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(geom.build_pipe_rack_number('', 'A', 500, 1000), '')
        self.assertEqual(geom.build_pipe_rack_number('   ', 'A', 500, 1000), '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(1.5), 2)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(499.5), 500)

    def test_number_uses_the_given_sizes(self):
        self.assertEqual(
            geom.build_pipe_rack_number('G5', 'G', 3000.0, 2000.0),
            'G5-G-3000-2000')


if __name__ == '__main__':
    unittest.main()
