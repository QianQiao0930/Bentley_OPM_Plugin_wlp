# -*- coding: utf-8 -*-
"""H 型钢门型架纯几何 / 数据逻辑单测（不依赖 Bentley 运行时）。

覆盖：竖直线解析、立柱与横担的布置不变量、截面朝向与右手系、表 1 荷载查询、
管架编号。门架几何的核心约定是「所选竖直线为整组中心线、L 为横担全长」——
两立柱轴线关于该线对称、横担以其为中点，横担两端各超立柱外缘 50
（图上 50 TYP.），两立柱净距 ``B = L - 100 - 2×立柱截面高``；立柱顶面顶焊在
横担下翼缘下表面、两者腹板共面。
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
_GEOM_DIR = os.path.join(_MODULE_DIR, '门型架H型钢')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 门型架_H型钢_几何 as geom  # noqa: E402
from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-9


def _plane_dirs(heading_deg):
    heading = math.radians(heading_deg)
    return ((math.cos(heading), math.sin(heading), 0.0),
            (-math.sin(heading), math.cos(heading), 0.0))


def _member_axes_world(variant_key, member_kind, heading_deg=0.0):
    run_dir, v_dir = _plane_dirs(heading_deg)
    world = []
    for ux, vx, wx in geom.member_axes(variant_key, member_kind):
        world.append((ux * run_dir[0] + vx * v_dir[0],
                      ux * run_dir[1] + vx * v_dir[1],
                      wx))
    return tuple(world)


def _post(base=(0.0, 0.0, 0.0), height_mm=3000.0):
    return geom.VerticalPost(
        base=tuple(float(v) for v in base),
        top=(base[0], base[1], base[2] + float(height_mm)),
        height_mm=float(height_mm),
    )


def _member_world(variant_key, member_kind, post, arm_length_mm,
                  heading_deg=0.0, post_axis_u=0.0):
    """返回 ``(origin, axis_z, length_mm, world_points)``。

    ``world_points`` 是截面轮廓（未扫掠）映射到世界的点列，与
    ``门型架（H型钢）.py`` 中 ``_build_member_element`` 的做法一致。
    """
    run_dir, v_dir = _plane_dirs(heading_deg)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, post.height_mm, arm_length_mm, post_axis_u)
    origin = (
        post.base[0] + origin_uvw[0] * run_dir[0] + origin_uvw[1] * v_dir[0],
        post.base[1] + origin_uvw[0] * run_dir[1] + origin_uvw[1] * v_dir[1],
        post.base[2] + origin_uvw[2],
    )
    axis_x, axis_y, axis_z = _member_axes_world(
        variant_key, member_kind, heading_deg)
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
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, 3000.0)]])
        self.assertAlmostEqual(post.height_mm, 3000.0, places=6)
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 3000.0))

    def test_downward_segment_is_normalised(self):
        post = geom.parse_vertical_post([[(0.0, 0.0, 2500.0), (0.0, 0.0, 0.0)]])
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(post.height_mm, 2500.0, places=6)

    def test_slight_tilt_within_tolerance_is_accepted(self):
        tilt_deg = geom.VERTICAL_TOLERANCE_DEG - 2.0
        self.assertGreater(tilt_deg, 0.0)
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
        short = geom.MIN_POST_HEIGHT_MM - 1.0
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, short)]])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([])


class LayoutTests(unittest.TestCase):
    """L 为横担全长时的一整套布置不变量。"""

    ARM_LENGTH = 2000.0

    def _members(self, variant_key, arm_length=None, height_mm=3000.0,
                 heading_deg=0.0):
        arm_length = self.ARM_LENGTH if arm_length is None else arm_length
        post = _post(height_mm=height_mm)
        left = _member_world(variant_key, 'post', post, arm_length, heading_deg,
                             geom.post_axis_offset(variant_key, arm_length,
                                                   'left'))
        right = _member_world(variant_key, 'post', post, arm_length, heading_deg,
                              geom.post_axis_offset(variant_key, arm_length,
                                                    'right'))
        arm = _member_world(variant_key, 'arm', post, arm_length, heading_deg)
        return post, left, right, arm

    def test_net_span_is_derived_from_the_arm_length(self):
        leg_depth = geom.member_depth('A', 'post')
        self.assertAlmostEqual(
            geom.net_span('A', self.ARM_LENGTH),
            self.ARM_LENGTH - 2.0 * geom.ARM_END_OVERHANG_MM - 2.0 * leg_depth,
            places=9)
        for variant_key in sorted(geom.VARIANTS):
            leg_depth = geom.member_depth(variant_key, 'post')
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            span = right_box[0] - left_box[1]
            self.assertAlmostEqual(
                span, self.ARM_LENGTH - 2.0 * geom.ARM_END_OVERHANG_MM
                - 2.0 * leg_depth, places=6,
                msg='%s 净距' % variant_key)
            self.assertAlmostEqual(span, geom.net_span(variant_key,
                                                       self.ARM_LENGTH),
                                   places=6)

    def test_selected_line_is_the_assembly_centreline(self):
        """所选竖直线是整组中心线：两立柱轴对称，横担亦以它为中点。"""
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            self.assertAlmostEqual(
                geom.post_axis_offset(variant_key, self.ARM_LENGTH, 'left'),
                -geom.post_axis_offset(variant_key, self.ARM_LENGTH, 'right'),
                places=9)
            self.assertAlmostEqual(left_box[0], -right_box[1], places=6)
            self.assertAlmostEqual(
                left_box[0],
                -(self.ARM_LENGTH - 2.0 * geom.ARM_END_OVERHANG_MM) / 2.0,
                places=6)
            # 横担两端同样对称于中心线。
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            self.assertAlmostEqual(u_start, -length / 2.0, places=9)
            self.assertAlmostEqual(u_start, -(u_start + length), places=9)

    def test_post_section_is_centred_on_its_own_axis(self):
        """立柱截面高 h 沿 u，外接矩形中心落在轴线上 -> 内缘在轴线 ±h/2。"""
        for variant_key in sorted(geom.VARIANTS):
            depth = geom.member_depth(variant_key, 'post')
            post, left, right, arm = self._members(variant_key)
            left_axis = geom.post_axis_offset(variant_key, self.ARM_LENGTH,
                                              'left')
            left_box = _bbox(left[3])
            self.assertAlmostEqual(left_box[0], left_axis - depth / 2.0,
                                   places=6)
            self.assertAlmostEqual(left_box[1], left_axis + depth / 2.0,
                                   places=6)

    def test_post_axes_are_symmetric_about_the_selected_line(self):
        """两立柱轴线间距为 L - 100 - 截面高，且关于所选中心线对称。"""
        for variant_key in sorted(geom.VARIANTS):
            depth = geom.member_depth(variant_key, 'post')
            pitch = (self.ARM_LENGTH - 2.0 * geom.ARM_END_OVERHANG_MM
                     - depth)
            left_axis = geom.post_axis_offset(variant_key, self.ARM_LENGTH,
                                              'left')
            right_axis = geom.post_axis_offset(variant_key, self.ARM_LENGTH,
                                               'right')
            self.assertAlmostEqual(left_axis, -pitch / 2.0, places=9)
            self.assertAlmostEqual(right_axis, pitch / 2.0, places=9)
            self.assertAlmostEqual(right_axis - left_axis, pitch, places=9)

    def test_arm_length_is_the_rail_full_length(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            self.assertAlmostEqual(length, self.ARM_LENGTH, places=9)
            # 横担截面轮廓在扫掠起点上，故 u 恒为 u_start。
            for point in arm[3]:
                self.assertAlmostEqual(point[0], u_start, places=6)

    def test_both_rail_ends_overhang_the_post_outer_face_by_50(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            self.assertAlmostEqual(
                left_box[0] - u_start, geom.ARM_END_OVERHANG_MM, places=6)
            self.assertAlmostEqual(
                (u_start + length) - right_box[1], geom.ARM_END_OVERHANG_MM,
                places=6)

    def test_rail_spans_over_both_posts(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            u_start, length = geom.beam_span(variant_key, self.ARM_LENGTH)
            self.assertLessEqual(u_start, left_box[0])
            self.assertGreaterEqual(u_start + length, right_box[1])

    def test_rail_top_face_lies_at_the_height_of_the_selected_line(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], post.height_mm, places=6)

    def test_post_top_meets_the_rail_underside(self):
        for variant_key in sorted(geom.VARIANTS):
            arm_depth = geom.member_depth(variant_key, 'arm')
            post, left, right, arm = self._members(variant_key)
            arm_box = _bbox(arm[3])
            leg_top = left[0][2] + left[2] * left[1][2]
            self.assertAlmostEqual(leg_top, arm_box[4], places=6)
            self.assertAlmostEqual(left[2], post.height_mm - arm_depth,
                                   places=9)

    def test_post_length_deducts_the_arm_depth(self):
        for variant_key in sorted(geom.VARIANTS):
            arm_depth = geom.member_depth(variant_key, 'arm')
            _, post_length = geom.member_origin_length(
                variant_key, 'post', 3000.0, self.ARM_LENGTH, 0.0)
            self.assertAlmostEqual(post_length, 3000.0 - arm_depth, places=9)

    def test_flange_width_is_along_v_for_both_members(self):
        """立柱与横担的翼缘宽 B 都朝向 v，故截面 v 范围为 ±B/2。"""
        for variant_key in sorted(geom.VARIANTS):
            flange = geom.member_flange_width(variant_key, 'post')
            post, left, right, arm = self._members(variant_key)
            for member in (left, right, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2], -flange / 2.0, places=6)
                self.assertAlmostEqual(box[3], flange / 2.0, places=6)

    def test_webs_are_coplanar_in_the_frame_plane(self):
        """腹板中心平面都在 v = 0（门架平面内）：截面 v 范围关于 0 对称。"""
        for variant_key in sorted(geom.VARIANTS):
            post, left, right, arm = self._members(variant_key)
            for member in (left, right, arm):
                box = _bbox(member[3])
                self.assertAlmostEqual(box[2] + box[3], 0.0, places=6)
            # 腹板厚度方向为 v：截面在 v 上存在 ±t1/2 两条长边。
            half_web = float(geom.section_dimensions(variant_key)['t1']) / 2.0
            box = _bbox(arm[3])
            self.assertLess(half_web, (box[3] - box[2]) / 2.0)

    def test_heading_rotates_the_frame_plane(self):
        post = _post()
        # 横担左端在左立柱外缘之外 50，即 u = -L/2（以整组中心线为中点）。
        start = geom.beam_span('A', self.ARM_LENGTH)[0]
        for heading in (0.0, 90.0, 180.0, 270.0):
            run_dir, _v_dir = _plane_dirs(heading)
            origin, axis_z, length, points = _member_world(
                'A', 'arm', post, self.ARM_LENGTH, heading)
            self.assertAlmostEqual(axis_z[0], run_dir[0], places=9)
            self.assertAlmostEqual(axis_z[1], run_dir[1], places=9)
            self.assertAlmostEqual(origin[0], run_dir[0] * start, places=6)
            self.assertAlmostEqual(origin[1], run_dir[1] * start, places=6)
            for point in points:
                projected = ((point[0] - origin[0]) * run_dir[0]
                             + (point[1] - origin[1]) * run_dir[1])
                self.assertAlmostEqual(projected, 0.0, places=6)
            self.assertAlmostEqual(_bbox(points)[5], post.height_mm, places=6)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm'):
                axis_x, axis_y, axis_z = geom.member_axes(variant_key, member_kind)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)

    def test_too_short_arm_length_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.net_span('D', 100.0)


class VariantTests(unittest.TestCase):
    def test_specifications_match_table_one(self):
        expected = {'A': 'H100×100×6×8', 'B': 'H150×150×7×10',
                    'C': 'H200×200×8×12', 'D': 'H250×250×9×14'}
        self.assertEqual(
            dict((key, geom.specification(key)) for key in geom.VARIANTS),
            expected)

    def test_section_dimensions_resolve(self):
        for variant_key, height, width, web, flange in (
                ('A', 100.0, 100.0, 6.0, 8.0),
                ('B', 150.0, 150.0, 7.0, 10.0),
                ('C', 200.0, 200.0, 8.0, 12.0),
                ('D', 250.0, 250.0, 9.0, 14.0)):
            section = geom.section_dimensions(variant_key)
            self.assertAlmostEqual(section['H'], height, places=9)
            self.assertAlmostEqual(section['B'], width, places=9)
            self.assertAlmostEqual(section['t1'], web, places=9)
            self.assertAlmostEqual(section['t2'], flange, places=9)
            self.assertAlmostEqual(
                geom.member_depth(variant_key, 'post'), height, places=9)
            self.assertAlmostEqual(
                geom.member_depth(variant_key, 'arm'), height, places=9)
            self.assertAlmostEqual(
                geom.member_flange_width(variant_key, 'arm'), width, places=9)

    def test_variant_choices_are_sorted(self):
        self.assertEqual([key for key, _label in geom.variant_choices()],
                         ['A', 'B', 'C', 'D'])

    def test_only_type_one_is_supported(self):
        for key in sorted(geom.VARIANTS):
            self.assertTrue(geom.variant_supports_type(key, 1))
            self.assertFalse(geom.variant_supports_type(key, 3))
            self.assertFalse(geom.variant_supports_type(key, 'x'))
        self.assertFalse(geom.hanger_type(1))
        self.assertFalse(geom.hanger_type(3))

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.specification('Z')


class LoadTableTests(unittest.TestCase):
    """表 1 逐格核对：列 L≤1000 / 2000 / 3000，行 H=1000 / 2000 / 3000 / 4000。"""

    def test_table_one_values(self):
        expected = {
            ('A', 1000): (20.0, None, None),
            ('A', 2000): (10.0, None, None),
            ('A', 3000): (None, None, None),
            ('A', 4000): (None, None, None),
            ('B', 1000): (80.0, 60.0, None),
            ('B', 2000): (40.0, 40.0, None),
            ('B', 3000): (20.0, 20.0, None),
            ('B', 4000): (None, None, None),
            ('C', 1000): (140.0, 80.0, 60.0),
            ('C', 2000): (80.0, 80.0, 60.0),
            ('C', 3000): (40.0, 40.0, 40.0),
            ('C', 4000): (20.0, 20.0, 20.0),
            ('D', 1000): (200.0, 120.0, 100.0),
            ('D', 2000): (100.0, 100.0, 100.0),
            ('D', 3000): (70.0, 70.0, 70.0),
            ('D', 4000): (40.0, 40.0, 40.0),
        }
        self.assertEqual(len(expected), 16)
        for variant_key in sorted(geom.VARIANTS):
            for height in (1000, 2000, 3000, 4000):
                for column, want in zip((1000, 2000, 3000),
                                        expected[(variant_key, height)]):
                    got = geom.allowable_load(variant_key, float(height),
                                              float(column)).value
                    if want is None:
                        self.assertIsNone(
                            got, '%s H=%d L=%d' % (variant_key, height, column))
                    else:
                        self.assertAlmostEqual(
                            got, want, places=9,
                            msg='%s H=%d L=%d' % (variant_key, height, column))

    def test_height_is_rounded_down_conservatively(self):
        """H=2900 按表中 2000 取用（偏安全），而不是 3000。"""
        result = geom.allowable_load('D', 2900.0, 1000.0)
        self.assertEqual(result.used_height_mm, 2000)
        self.assertAlmostEqual(result.value, 100.0, places=9)

    def test_arm_length_rounds_up_to_the_next_column(self):
        self.assertAlmostEqual(
            geom.allowable_load('D', 1000.0, 1500.0).value, 120.0, places=9)

    def test_blank_cells_report_no_value(self):
        self.assertIsNone(geom.allowable_load('A', 1000.0, 2000.0).value)
        self.assertIsNone(geom.allowable_load('B', 2000.0, 3000.0).value)
        self.assertIsNone(geom.allowable_load('A', 3000.0, 1000.0).value)

    def test_out_of_range_is_reported(self):
        below = geom.allowable_load('A', 400.0, 1000.0)
        self.assertIsNone(below.value)
        self.assertIn('小于表中最小值', below.message)
        above = geom.allowable_load('D', 1000.0, 3500.0)
        self.assertIsNone(above.value)
        self.assertIn('超出表中上限', above.message)

    def test_used_columns_are_reported(self):
        result = geom.allowable_load('D', 1000.0, 1000.0)
        self.assertEqual(result.used_height_mm, 1000)
        self.assertEqual(result.used_arm_mm, 1000)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_pipe_rack_number('D13', 1, 'c', 3000.0, 2000.0),
            'D13-1-C-3000-2000')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(
            geom.build_pipe_rack_number('', 1, 'A', 3000, 2000), '')
        self.assertEqual(
            geom.build_pipe_rack_number('   ', 1, 'A', 3000, 2000), '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(1999.5), 2000)
        self.assertEqual(geom.round_half_up(-0.5), 0)


if __name__ == '__main__':
    unittest.main()
