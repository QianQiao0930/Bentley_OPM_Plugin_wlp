# -*- coding: utf-8 -*-
from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)
for _path in (_PLUGIN_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import L型管架_几何 as geom  # noqa: E402
import steel_sweep_geometry as ssg  # noqa: E402


RUN_DIR = (1.0, 0.0, 0.0)
UP = (0.0, 0.0, 1.0)


def _polygon_points(geometry, per_arc=48):
    points = []
    for segment in geometry.segments:
        if not hasattr(segment, 'center'):
            points.append((segment.start.x, segment.start.y))
            points.append((segment.end.x, segment.end.y))
            continue
        for index in range(per_arc + 1):
            angle = segment.start_angle + segment.sweep * index / per_arc
            points.append((
                segment.center.x + segment.radius * math.cos(angle),
                segment.center.y + segment.radius * math.sin(angle),
            ))
    return points


def _centroid(points):
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for index in range(len(points)):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (3.0 * area2), cy / (3.0 * area2)


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


class ParseLShapeTests(unittest.TestCase):
    def test_forward_polyline(self):
        line = geom.parse_l_shape([[
            (0.0, 0.0, 0.0), (0.0, 0.0, 1500.0), (800.0, 0.0, 1500.0)]])
        self.assertEqual((0.0, 0.0, 0.0), line.post_end)
        self.assertEqual((0.0, 0.0, 1500.0), line.corner)
        self.assertEqual((800.0, 0.0, 1500.0), line.arm_end)
        self.assertAlmostEqual(1500.0, line.post_height_mm)
        self.assertAlmostEqual(800.0, line.arm_length_mm)
        self.assertAlmostEqual(0.0, line.heading_deg)
        self.assertFalse(line.is_hanger)

    def test_reversed_polyline_is_normalised(self):
        line = geom.parse_l_shape([[
            (800.0, 0.0, 1500.0), (0.0, 0.0, 1500.0), (0.0, 0.0, 0.0)]])
        self.assertEqual((0.0, 0.0, 0.0), line.post_end)
        self.assertEqual((800.0, 0.0, 1500.0), line.arm_end)

    def test_hanger_polyline_has_post_above(self):
        # 拐点 (0,0,0)，竖直段向上到 (0,0,1200)，水平段到 (700,0,0)。
        line = geom.parse_l_shape([
            [(0.0, 0.0, 1200.0), (0.0, 0.0, 0.0), (700.0, 0.0, 0.0)]],
            hanger=True)
        self.assertTrue(line.is_hanger)
        self.assertEqual((0.0, 0.0, 1200.0), line.post_end)
        self.assertEqual((0.0, 0.0, 0.0), line.corner)
        self.assertAlmostEqual(1200.0, line.post_height_mm)

    def test_hanger_rejects_post_below(self):
        # 非吊架折线（立杆在下），hanger=True 应拒绝。
        with self.assertRaises(ValueError):
            geom.parse_l_shape([
                [(0.0, 0.0, 0.0), (0.0, 0.0, 1200.0), (700.0, 0.0, 1200.0)]],
                hanger=True)

    def test_non_hanger_rejects_post_above(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([
                [(0.0, 0.0, 1200.0), (0.0, 0.0, 0.0), (700.0, 0.0, 0.0)]],
                hanger=False)

    def test_two_separate_pieces_sharing_corner(self):
        line = geom.parse_l_shape([
            [(0.0, 0.0, 0.0), (0.0, 0.0, 1200.0)],
            [(0.0, 0.0, 1200.0), (0.0, -900.0, 1200.0)],
        ])
        self.assertAlmostEqual(-90.0, line.heading_deg)
        self.assertAlmostEqual(900.0, line.arm_length_mm)

    def test_corner_gap_within_tolerance_is_accepted(self):
        line = geom.parse_l_shape([
            [(0.0, 0.0, 0.0), (0.0, 0.0, 1000.0)],
            [(0.0, 0.0, 1000.4), (500.0, 0.0, 1000.4)],
        ])
        self.assertAlmostEqual(1000.2, line.corner[2])

    def test_single_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([[(0.0, 0.0, 0.0), (0.0, 0.0, 1000.0)]])

    def test_three_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([[
                (0.0, 0.0, 0.0), (0.0, 0.0, 1000.0),
                (500.0, 0.0, 1000.0), (500.0, 0.0, 1500.0)]])

    def test_detached_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([
                [(0.0, 0.0, 0.0), (0.0, 0.0, 1000.0)],
                [(900.0, 0.0, 1000.0), (1500.0, 0.0, 1000.0)],
            ])

    def test_post_above_corner_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([[
                (0.0, 0.0, 1500.0), (0.0, 0.0, 3000.0), (800.0, 0.0, 1500.0)]])

    def test_too_short_members_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_l_shape([[
                (0.0, 0.0, 0.0), (0.0, 0.0, 100.0), (800.0, 0.0, 100.0)]])
        with self.assertRaises(ValueError):
            geom.parse_l_shape([[
                (0.0, 0.0, 0.0), (0.0, 0.0, 1000.0), (100.0, 0.0, 1000.0)]])


def _uvw_range(variant, kind, post_height=1000.0, arm_length=800.0, hanger=False):
    """把构件截面（含扫掠端点）投影到支架局部基 (u, v, w) 的包络。"""
    geometry = geom.member_geometry(variant, kind, 1.0, hanger)
    points = _polygon_points(geometry)
    axis_x, axis_y, axis_z = geom.member_axes(variant, kind, hanger)
    origin, length = geom.member_origin_length(
        variant, kind, post_height, arm_length, hanger)
    ranges = [[], [], []]
    for (x, y) in points:
        for index in range(3):
            ranges[index].append(
                origin[index] + x * axis_x[index] + y * axis_y[index])
    for index in range(3):
        ranges[index].append(origin[index] + axis_z[index] * length)
    return tuple((min(values), max(values)) for values in ranges)


def _length(vector):
    return math.sqrt(sum(component * component for component in vector))


def _uvw_centroid(variant, kind, post_height=1000.0, arm_length=800.0):
    """构件截面重心在支架局部基 (u, v, w) 下的坐标。"""
    geometry = geom.member_geometry(variant, kind)
    cx, cy = _centroid(_polygon_points(geometry))
    axis_x, axis_y, _ = geom.member_axes(variant, kind)
    origin, _ = geom.member_origin_length(
        variant, kind, post_height, arm_length)
    return tuple(
        origin[index] + cx * axis_x[index] + cy * axis_y[index]
        for index in range(3))


class MemberPlacementTests(unittest.TestCase):
    def test_post_centroid_is_centred_in_run(self):
        # 容差放宽到 0.5 mm：型钢截面生成器 数据表的截面重心公式与其实际
        # 绘制的圆角轮廓存在亚毫米级差异（角钢用表列 Z0、槽钢用简化重心）。
        for variant in geom.VARIANTS:
            u, _, _ = _uvw_centroid(variant, 'post')
            self.assertAlmostEqual(0.0, u, delta=0.5, msg=variant)

    def test_post_centroid_on_web_back_plane(self):
        # 角钢 / H 型钢重心落在竖直线 = 腹板背平面；
        # 槽钢背靠背时重心必然偏离腹板背 Z0（沿 -v）。
        for variant in ('A', 'B', 'C', 'E', 'F'):
            _, v, _ = _uvw_centroid(variant, 'post')
            self.assertAlmostEqual(0.0, v, delta=0.5, msg=variant)
        z0 = geom.section_dimensions('D')['Z0']
        _, v, _ = _uvw_centroid('D', 'post')
        self.assertAlmostEqual(-z0, v, delta=0.5)

    def test_arm_top_face_lies_on_a_local_axis_plane(self):
        for variant in geom.VARIANTS:
            geometry = geom.member_geometry(variant, 'arm')
            points = _polygon_points(geometry)
            ys = [point[1] for point in points]
            if geom.arm_axis_y_is_up(variant):
                # 型钢正立：local +y 向上，顶面在 y=0，截面在其下方。
                self.assertAlmostEqual(0.0, max(ys), places=6, msg=variant)
                self.assertLess(min(ys), -1.0, msg=variant)
            else:
                # 角钢倒扣：local +y 向下，顶面在 y=0，截面在其上方（+y）。
                self.assertAlmostEqual(0.0, min(ys), places=6, msg=variant)
                self.assertGreater(max(ys), 1.0, msg=variant)

    def test_member_bases_are_orthonormal(self):
        for variant in geom.VARIANTS:
            for kind in ('post', 'arm'):
                axis_x, axis_y, axis_z = geom.member_axes(variant, kind)
                for axis in (axis_x, axis_y, axis_z):
                    self.assertAlmostEqual(1.0, _length(axis), places=9)
                self.assertAlmostEqual(0.0, _dot(axis_x, axis_y), places=9)
                self.assertAlmostEqual(0.0, _dot(axis_x, axis_z), places=9)
                self.assertAlmostEqual(0.0, _dot(axis_y, axis_z), places=9)

    def test_post_is_vertical(self):
        for variant in geom.VARIANTS:
            axis_x, axis_y, axis_z = geom.member_axes(variant, 'post')
            self.assertAlmostEqual(1.0, axis_z[2], places=9, msg=variant)
            self.assertAlmostEqual(0.0, axis_x[2], places=9, msg=variant)
            self.assertAlmostEqual(0.0, axis_y[2], places=9, msg=variant)

    def test_arm_top_face_sits_on_the_selected_line(self):
        for variant in geom.VARIANTS:
            _, _, w_range = _uvw_range(variant, 'arm')
            self.assertAlmostEqual(0.0, w_range[1], places=6, msg=variant)

    def test_arm_back_end_overhangs_post_by_15(self):
        for variant in geom.VARIANTS:
            post_u = _uvw_range(variant, 'post')[0]
            arm_u = _uvw_range(variant, 'arm')[0]
            overhang = post_u[0] - arm_u[0]
            self.assertAlmostEqual(
                geom.ARM_BACK_OVERHANG_MM, overhang, places=6, msg=variant)

    def test_hanger_h_beam_post_stands_on_crossarm_top_flange(self):
        for variant in ('E', 'F'):
            post_w = _uvw_range(variant, 'post', hanger=True)[2]
            self.assertAlmostEqual(0.0, post_w[0], places=6, msg=variant)
            self.assertAlmostEqual(
                1000.0, post_w[1], places=6, msg=variant)

    def test_hanger_channel_post_extends_into_crossarm_web(self):
        height = geom.section_dimensions('D')['H']
        post_w = _uvw_range('D', 'post', hanger=True)[2]
        arm_w = _uvw_range('D', 'arm')[2]
        self.assertAlmostEqual(0.0, arm_w[1], places=6)
        self.assertAlmostEqual(-height, post_w[0], places=6)
        self.assertAlmostEqual(1000.0, post_w[1], places=6)
        # 腹板背相贴在同一平面 v=0。
        post_v = _uvw_range('D', 'post', hanger=True)[1]
        arm_v = _uvw_range('D', 'arm')[1]
        self.assertAlmostEqual(post_v[1], arm_v[0], places=6)

    def test_hanger_angle_post_is_back_to_back_with_crossarm_leg(self):
        for variant in ('A', 'B', 'C'):
            post_v = _uvw_range(variant, 'post', hanger=True)[1]
            arm_v = _uvw_range(variant, 'arm')[1]
            # 立杆贴合肢的背面（v 最大）与横担竖直肢外皮（v 最小）重合。
            self.assertAlmostEqual(post_v[1], arm_v[0], places=6, msg=variant)

    def test_only_types_one_and_three_allow_h_sections(self):
        self.assertTrue(geom.variant_supports_type('E', 1))
        self.assertFalse(geom.variant_supports_type('E', 2))
        self.assertTrue(geom.variant_supports_type('E', 3))
        self.assertFalse(geom.variant_supports_type('E', 4))
        self.assertTrue(geom.variant_supports_type('A', 4))
        self.assertTrue(geom.hanger_type(3))
        self.assertTrue(geom.hanger_type(4))
        self.assertFalse(geom.hanger_type(1))
        self.assertFalse(geom.hanger_type(2))

    def test_h_beam_post_butts_crossarm_bottom_flange(self):
        for variant in ('E', 'F'):
            height = geom.section_dimensions(variant)['H']
            post_w = _uvw_range(variant, 'post')[2]
            arm_w = _uvw_range(variant, 'arm')[2]
            self.assertAlmostEqual(0.0, arm_w[1], places=6, msg=variant)
            self.assertAlmostEqual(-height, post_w[1], places=6, msg=variant)
            self.assertAlmostEqual(post_w[1], arm_w[0], places=6, msg=variant)

    def test_angle_post_leg_touches_crossarm_opening_side(self):
        for variant in ('A', 'B', 'C'):
            thickness = geom.section_dimensions(variant)['t']
            post_v_min = _uvw_range(variant, 'post')[1][0]
            arm_v_min = _uvw_range(variant, 'arm')[1][0]
            # 立杆贴合肢的 -v 面与横担竖直肢的 +v 面重合。
            self.assertAlmostEqual(
                post_v_min, arm_v_min + thickness, places=6, msg=variant)

    def test_channel_webs_are_back_to_back(self):
        # 立杆腹板背（v 最大）与横担腹板背（v 最小）在同一平面 v=0。
        post_v = _uvw_range('D', 'post')[1]
        arm_v = _uvw_range('D', 'arm')[1]
        self.assertAlmostEqual(0.0, post_v[1], places=6)
        self.assertAlmostEqual(0.0, arm_v[0], places=6)
        self.assertAlmostEqual(post_v[1], arm_v[0], places=6)
        # 开口方向相反：立杆在 -v 侧，横担在 +v 侧。
        self.assertLess(post_v[0], -1.0)
        self.assertGreater(arm_v[1], 1.0)

    def test_h_beam_post_is_centred(self):
        geometry = geom.member_geometry('E', 'post')
        points = _polygon_points(geometry)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        self.assertAlmostEqual(125.0, max(xs) - min(xs), places=6)
        self.assertAlmostEqual(125.0, max(ys) - min(ys), places=6)


class VariantTests(unittest.TestCase):
    def test_specifications_match_table_three(self):
        expected = {
            'A': '∠50×6', 'B': '∠75×7', 'C': '∠100×10',
            'D': '[16a', 'E': 'H125×125×6.5×9', 'F': 'H150×150×7×10',
        }
        for key, spec in expected.items():
            self.assertEqual(spec, geom.specification(key))

    def test_section_dimensions_resolve(self):
        self.assertEqual(50.0, geom.section_dimensions('A')['B'])
        self.assertEqual(160.0, geom.section_dimensions('D')['H'])
        self.assertEqual(125.0, geom.section_dimensions('E')['H'])
        self.assertEqual(150.0, geom.section_dimensions('F')['B'])

    def test_only_types_one_and_three_allow_e_and_f(self):
        self.assertTrue(geom.variant_supports_type('E', 1))
        self.assertFalse(geom.variant_supports_type('E', 2))
        self.assertTrue(geom.variant_supports_type('F', 3))
        self.assertTrue(geom.variant_supports_type('A', 2))


class LoadTableTests(unittest.TestCase):
    def test_table_one_values(self):
        self.assertEqual(0.3, geom.allowable_load('A', 500, 250).value)
        self.assertEqual(3.0, geom.allowable_load('C', 500, 250).value)
        self.assertEqual(2.0, geom.allowable_load('C', 500, 500).value)
        self.assertEqual(0.5, geom.allowable_load('D', 3000, 500).value)
        self.assertIsNone(geom.allowable_load('A', 500, 500).value)

    def test_table_two_values(self):
        self.assertEqual(8.0, geom.allowable_load('E', 500, 500).value)
        self.assertEqual(5.0, geom.allowable_load('E', 500, 750).value)
        self.assertEqual(25.0, geom.allowable_load('F', 500, 250).value)
        self.assertEqual(1.0, geom.allowable_load('F', 3000, 750).value)

    def test_height_is_rounded_down_conservatively(self):
        result = geom.allowable_load('D', 1400, 250)
        self.assertEqual(1000, result.used_height_mm)
        self.assertEqual(5.0, result.value)

    def test_out_of_range_is_reported(self):
        self.assertIsNone(geom.allowable_load('A', 300, 250).value)
        self.assertIsNone(geom.allowable_load('E', 2000, 800).value)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            'D5-1-A-1500-801',
            geom.build_pipe_rack_number('D5', 1, 'A', 1500.4, 800.6))

    def test_empty_name_produces_no_number(self):
        self.assertEqual('', geom.build_pipe_rack_number('  ', 1, 'A', 1000, 500))

    def test_round_half_up(self):
        self.assertEqual(3, geom.round_half_up(2.5))
        self.assertEqual(2, geom.round_half_up(2.49))


if __name__ == '__main__':
    unittest.main()
