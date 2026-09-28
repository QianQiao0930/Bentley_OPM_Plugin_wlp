# -*- coding: utf-8 -*-
"""弯头弧形垫板纯几何 / 数据逻辑单测。

截面 = Y2 同款（内弧 R = 管外径/2、外弧 R + T、张角 α = 120°，居中于背弧），
沿弯头中心线圆弧扫掠、覆盖 75° 且居中于 45° 中点；气孔 Ø6 在覆盖中点背弧冠线。
编号 ``弯头垫板-管径-弯头倍率``。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_ELBOW_DIR = os.path.join(_MODULE_DIR, '弯头垫板')
if _ELBOW_DIR not in sys.path:
    sys.path.insert(0, _ELBOW_DIR)

import 弯头垫板_几何 as geom  # noqa: E402


def _frame(dn=100, multiplier=1.5, origin=(0.0, 0.0, 0.0),
           axis_x=(1.0, 0.0, 0.0), axis_z=(0.0, 0.0, 1.0)):
    """端口 0 在原点、入口切线 +X、指向弯曲中心 +Z 的弯头（在 X-Z 平面内弯曲）。"""
    return geom.build_frame(origin, axis_x, axis_z, dn, multiplier)


class TestNominalAndMultiplier(unittest.TestCase):
    def test_nominal_is_inch_based(self):
        # DN100 = 4″ → 101.6 mm，不是公制名义值 100。
        self.assertAlmostEqual(geom.nominal_mm(100), 101.6)
        self.assertAlmostEqual(geom.nominal_mm(50), 50.8)
        self.assertAlmostEqual(geom.nominal_mm(500), 508.0)

    def test_nominal_covers_every_dn(self):
        for dn in geom.dn_choices():
            self.assertGreater(geom.nominal_mm(dn), 0.0)

    def test_bend_radius(self):
        # 1.5D 长半径：DN100 → 1.5 × 101.6 = 152.4（ASME B16.9 中心至端面）。
        self.assertAlmostEqual(geom.bend_radius_mm(100, 1.5), 152.4)
        # 1.0D 短半径。
        self.assertAlmostEqual(geom.bend_radius_mm(100, 1.0), 101.6)
        self.assertAlmostEqual(geom.bend_radius_mm(200, 2.0),
                               2.0 * geom.nominal_mm(200))

    def test_snap_multiplier(self):
        self.assertAlmostEqual(geom.snap_multiplier(1.52), 1.5)
        self.assertAlmostEqual(geom.snap_multiplier(1.02), 1.0)
        self.assertAlmostEqual(geom.snap_multiplier(1.9), 2.0)
        self.assertAlmostEqual(geom.snap_multiplier(2.9), 3.0)

    def test_multiplier_from_center_to_end(self):
        # 标准 1.5D 弯头实测中心至端面 = 152.4 → 倍率 1.5 且吻合。
        multiplier, matched = geom.multiplier_from_center_to_end(100, 152.4)
        self.assertAlmostEqual(multiplier, 1.5)
        self.assertTrue(matched)
        # 公制名义值 150（≈1.476D）也应吸附到 1.5 并判定吻合。
        multiplier, matched = geom.multiplier_from_center_to_end(100, 150.0)
        self.assertAlmostEqual(multiplier, 1.5)
        self.assertTrue(matched)
        # 明显非标准的比值不吻合（220/101.6 = 2.17，离 2.0D 超过 5%）。
        _multiplier, matched = geom.multiplier_from_center_to_end(100, 220.0)
        self.assertFalse(matched)

    def test_multiplier_from_center_to_end_rejects_bad_value(self):
        with self.assertRaises(ValueError):
            geom.multiplier_from_center_to_end(100, 0.0)
        with self.assertRaises(ValueError):
            geom.multiplier_from_center_to_end(100, None)

    def test_multiplier_label(self):
        self.assertEqual(geom.multiplier_label(1.5), '1.5D')
        self.assertEqual(geom.multiplier_label(1.0), '1.0D')


class TestNumber(unittest.TestCase):
    def test_build_number(self):
        self.assertEqual(geom.build_number(100, 1.5), '弯头垫板-100-1.5')
        self.assertEqual(geom.build_number(200, 1.0), '弯头垫板-200-1.0')
        self.assertEqual(geom.build_number(50, 2.0), '弯头垫板-50-2.0')

    def test_layout_number_matches(self):
        layout = geom.build_layout(300, 1.5)
        self.assertEqual(layout.number, '弯头垫板-300-1.5')


class TestLayout(unittest.TestCase):
    def test_coverage_centred_on_bend_middle(self):
        layout = geom.build_layout(100, 1.5)
        self.assertAlmostEqual(layout.coverage_deg, 75.0)
        self.assertAlmostEqual(layout.coverage_start_deg, 7.5)
        self.assertAlmostEqual(layout.coverage_end_deg, 82.5)
        self.assertAlmostEqual(
            (layout.coverage_start_deg + layout.coverage_end_deg) / 2.0,
            geom.COVERAGE_CENTER_DEG)

    def test_section_matches_y2_convention(self):
        layout = geom.build_layout(100, 1.5)
        self.assertAlmostEqual(layout.alpha_deg, 120.0)
        self.assertAlmostEqual(layout.inner_radius, geom.od_mm(100) / 2.0)
        self.assertAlmostEqual(layout.outer_radius,
                               layout.inner_radius + layout.thickness)
        self.assertAlmostEqual(layout.thickness, 6.0)   # DN100 → 表 1 取 6

    def test_arc_length(self):
        layout = geom.build_layout(100, 1.5)
        self.assertAlmostEqual(layout.arc_length_mm,
                               152.4 * math.radians(75.0), places=6)

    def test_elbow_angle_is_90(self):
        self.assertAlmostEqual(geom.build_layout(100, 1.5).elbow_angle_deg, 90.0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            geom.build_layout(100, 9.0)          # 倍率过大
        with self.assertRaises(ValueError):
            geom.build_layout(10, 1.5)           # 管径超范围
        with self.assertRaises(ValueError):
            geom.build_layout(100, 1.5, 'X')     # 材料代码非法
        with self.assertRaises(ValueError):
            geom.build_layout(100, 1.5, coverage_deg=120.0)  # 覆盖超过 90°
        with self.assertRaises(ValueError):
            geom.build_layout(100, 1.5, coverage_deg=0.0)


class TestSectionReuse(unittest.TestCase):
    """截面必须与 Y2 完全同源（同一套「直线 + 真圆弧」）。"""

    def test_segments_structure(self):
        layout = geom.build_layout(200, 1.5)
        segments = geom.section_segments(layout)
        self.assertEqual([kind for kind, _points in segments],
                         ['arc', 'line', 'arc', 'line'])

    def test_arcs_on_expected_radii(self):
        layout = geom.build_layout(300, 1.5)
        segments = geom.section_segments(layout)

        def circumradius(first, second, third):
            ax, ay = first
            bx, by = second
            cx, cy = third
            denominator = 2.0 * (ax * (by - cy) + bx * (cy - ay)
                                 + cx * (ay - by))
            side_a = math.hypot(bx - cx, by - cy)
            side_b = math.hypot(cx - ax, cy - ay)
            side_c = math.hypot(ax - bx, ay - by)
            return side_a * side_b * side_c / abs(denominator)

        self.assertAlmostEqual(circumradius(*segments[0][1]),
                               layout.inner_radius, places=6)
        self.assertAlmostEqual(circumradius(*segments[2][1]),
                               layout.outer_radius, places=6)

    def test_pad_centred_on_extrados(self):
        """截面 φ = 0（最低点）必须落在 −z，即本地方位系的背弧方向。"""
        layout = geom.build_layout(100, 1.5)
        inner_arc = geom.section_segments(layout)[0][1]
        self.assertAlmostEqual(inner_arc[1][0], 0.0, places=6)
        self.assertAlmostEqual(inner_arc[1][1], -layout.inner_radius, places=6)


class TestElbowArc(unittest.TestCase):
    """中心线圆弧：P(t)、T(t)、背弧方向。"""

    def test_radius_and_ports(self):
        frame = _frame(dn=100, multiplier=1.5)
        radius = frame.radius_mm
        self.assertAlmostEqual(radius, 152.4)

        # t = 0 落在端口 0（原点）；t = 90° 落在端口 1 = 原点 + R·X + R·Z。
        start = geom.path_point(frame, 0.0)
        end = geom.path_point(frame, 90.0)
        self.assertAlmostEqual(start[0], 0.0, places=9)
        self.assertAlmostEqual(start[1], 0.0, places=9)
        self.assertAlmostEqual(start[2], 0.0, places=9)
        self.assertAlmostEqual(end[0], radius, places=9)
        self.assertAlmostEqual(end[1], 0.0, places=9)
        self.assertAlmostEqual(end[2], radius, places=9)

    def test_every_point_is_radius_from_center(self):
        frame = _frame()
        for t_deg in (0.0, 7.5, 45.0, 82.5, 90.0):
            point = geom.path_point(frame, t_deg)
            distance = math.sqrt(sum(
                (point[index] - frame.arc_center[index]) ** 2
                for index in range(3)))
            self.assertAlmostEqual(distance, frame.radius_mm, places=9)

    def test_extrados_and_tangent_are_perpendicular(self):
        frame = _frame()
        for t_deg in (0.0, 7.5, 45.0, 82.5, 90.0):
            outward = geom.extrados_dir(frame, t_deg)
            tangent = geom.path_tangent(frame, t_deg)
            dot = sum(outward[index] * tangent[index] for index in range(3))
            self.assertAlmostEqual(dot, 0.0, places=9)
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in outward)),
                                   1.0, places=9)
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in tangent)),
                                   1.0, places=9)

    def test_extrados_points_away_from_center(self):
        frame = _frame()
        for t_deg in (7.5, 45.0, 82.5):
            point = geom.path_point(frame, t_deg)
            outward = geom.extrados_dir(frame, t_deg)
            # 沿背弧方向离开中心线点，离弯曲中心更远。
            probe = tuple(point[index] + outward[index] for index in range(3))
            before = math.sqrt(sum((point[index] - frame.arc_center[index]) ** 2
                                   for index in range(3)))
            after = math.sqrt(sum((probe[index] - frame.arc_center[index]) ** 2
                                  for index in range(3)))
            self.assertGreater(after, before)

    def test_tangent_at_ports(self):
        frame = _frame()
        start = geom.path_tangent(frame, 0.0)
        end = geom.path_tangent(frame, 90.0)
        # t = 0 切线 = 入口切线 axis_x；t = 90° 切线 = axis_z。
        self.assertAlmostEqual(start[0], 1.0, places=9)
        self.assertAlmostEqual(start[2], 0.0, places=9)
        self.assertAlmostEqual(end[0], 0.0, places=9)
        self.assertAlmostEqual(end[2], 1.0, places=9)

    def test_bend_plane_normal(self):
        frame = _frame()
        normal = geom.bend_plane_normal(frame)
        # X = +X、Z = +Z 时，法向 = X × Z = −Y。
        self.assertAlmostEqual(normal[1], -1.0, places=9)
        self.assertAlmostEqual(normal[0], 0.0, places=9)

    def test_path_points_three_point_arc(self):
        layout = geom.build_layout(100, 1.5)
        frame = _frame()
        start, middle, end = geom.path_points(frame, layout)
        # 三点同圆（弯曲半径），中点落在 45°。
        for point in (start, middle, end):
            distance = math.sqrt(sum(
                (point[index] - frame.arc_center[index]) ** 2
                for index in range(3)))
            self.assertAlmostEqual(distance, frame.radius_mm, places=9)
        expected_middle = geom.path_point(frame, 45.0)
        for index in range(3):
            self.assertAlmostEqual(middle[index], expected_middle[index],
                                   places=9)

    def test_rejects_non_orthogonal_axes(self):
        with self.assertRaises(ValueError):
            geom.build_frame((0, 0, 0), (1, 0, 0), (1, 0, 0), 100, 1.5)


class TestSweepFrame(unittest.TestCase):
    def test_orthonormal_and_at_path_start(self):
        layout = geom.build_layout(100, 1.5)
        frame = _frame()
        ex, ey, ez, origin = geom.sweep_frame(frame, layout)
        for vector in (ex, ey, ez):
            self.assertAlmostEqual(math.sqrt(sum(v * v for v in vector)),
                                   1.0, places=9)
        for first, second in ((ex, ey), (ey, ez), (ex, ez)):
            dot = sum(first[index] * second[index] for index in range(3))
            self.assertAlmostEqual(dot, 0.0, places=9)
        expected = geom.path_point(frame, layout.coverage_start_deg)
        for index in range(3):
            self.assertAlmostEqual(origin[index], expected[index], places=9)

    def test_local_z_points_inward_and_centres_pad_on_extrados(self):
        """截面局部 −z 必须指向背弧：−z 方向（= ez 的反向）与 extrados 同向。"""
        layout = geom.build_layout(100, 1.5)
        frame = _frame()
        _ex, _ey, ez, _origin = geom.sweep_frame(frame, layout)
        outward = geom.extrados_dir(frame, layout.coverage_start_deg)
        for index in range(3):
            self.assertAlmostEqual(-ez[index], outward[index], places=9)

    def test_section_maps_outward_by_radius(self):
        """截面最低点 (0, −R) 映射到世界后，距弯曲中心 = R_bend + R_pipe。"""
        layout = geom.build_layout(100, 1.5)
        frame = _frame()
        ex, ey, ez, origin = geom.sweep_frame(frame, layout)
        x, y, z = 0.0, 0.0, -layout.inner_radius
        world = tuple(origin[index] + x * ex[index] + y * ey[index]
                      + z * ez[index] for index in range(3))
        distance = math.sqrt(sum(
            (world[index] - frame.arc_center[index]) ** 2 for index in range(3)))
        self.assertAlmostEqual(distance,
                               frame.radius_mm + layout.inner_radius, places=6)


class TestVentHole(unittest.TestCase):
    def test_axis_runs_through_thickness_at_coverage_middle(self):
        layout = geom.build_layout(100, 1.5)
        frame = _frame()
        outer_end, inner_end = geom.vent_hole_axis(frame, layout, 5.0)
        center = geom.path_point(frame, geom.COVERAGE_CENTER_DEG)
        outer_distance = math.sqrt(sum(
            (outer_end[index] - frame.arc_center[index]) ** 2
            for index in range(3)))
        inner_distance = math.sqrt(sum(
            (inner_end[index] - frame.arc_center[index]) ** 2
            for index in range(3)))
        # 外端比内端离弯曲中心更远（沿背弧向外钻穿板厚）。
        self.assertGreater(outer_distance, inner_distance)
        self.assertAlmostEqual(outer_distance,
                               frame.radius_mm + layout.outer_radius + 5.0,
                               places=6)
        # 轴线沿覆盖中点的背弧径向，故外端沿 +outward 离开中心线点。
        outward = geom.extrados_dir(frame, geom.COVERAGE_CENTER_DEG)
        for index in range(3):
            self.assertAlmostEqual(
                outer_end[index] - center[index],
                outward[index] * (layout.outer_radius + 5.0), places=6)


class TestMass(unittest.TestCase):
    def test_centroid_offset_between_radii_for_thin_arc(self):
        """张角趋近 0 时，形心距中心线 = 环形扇形的平均半径。"""
        layout = geom.build_layout(100, 1.5, alpha_deg=1.0)
        expected = (layout.inner_radius + layout.outer_radius) / 2.0
        self.assertAlmostEqual(geom.section_centroid_offset_mm(layout),
                               expected, delta=0.2)

    def test_centroid_offset_pulled_inward_for_wide_arc(self):
        """120° 宽扇形形心比内弧半径还靠近管轴（扇形的固有性质）。"""
        layout = geom.build_layout(100, 1.5)
        self.assertLess(geom.section_centroid_offset_mm(layout),
                        layout.inner_radius)

    def test_volume_uses_pappus(self):
        layout = geom.build_layout(100, 1.5)
        expected = (geom.section_area_mm2(layout)
                    * (layout.bend_radius_mm
                       + geom.section_centroid_offset_mm(layout))
                    * math.radians(layout.coverage_deg))
        self.assertAlmostEqual(geom.plate_volume_mm3(layout), expected,
                               places=6)

    def test_mass_positive_and_scales_with_coverage(self):
        small = geom.build_layout(100, 1.5, coverage_deg=30.0)
        large = geom.build_layout(100, 1.5, coverage_deg=75.0)
        self.assertGreater(geom.plate_mass_kg(large), geom.plate_mass_kg(small))
        self.assertGreater(geom.plate_mass_kg(large), 0.0)

    def test_vent_hole_reduces_volume(self):
        with_hole = geom.build_layout(100, 1.5, has_vent_hole=True)
        without = geom.build_layout(100, 1.5, has_vent_hole=False)
        self.assertLess(geom.plate_volume_mm3(with_hole),
                        geom.plate_volume_mm3(without))

    def test_summary_mentions_number_and_multiplier(self):
        layout = geom.build_layout(100, 1.5)
        summary = geom.layout_summary(layout)
        self.assertIn('弯头垫板-100-1.5', summary)
        self.assertIn('1.5D', summary)


if __name__ == '__main__':
    unittest.main()