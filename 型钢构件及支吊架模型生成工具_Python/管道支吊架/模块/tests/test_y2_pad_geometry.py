# -*- coding: utf-8 -*-
"""弧形垫板（Y2）纯几何 / 数据逻辑单测。

截面 = 两段同心圆弧（内弧 R = 管外径/2，外弧 R + 板厚 T）+ 两条径向直线，
居中于管底竖直向下（−Z）方向，张角 α；沿管轴拉伸 L；最低点中央开气孔 Ø6。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '弧形垫板')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 弧形垫板_几何 as geom  # noqa: E402


class TestPipeTable(unittest.TestCase):
    def test_od_mm_known_values(self):
        self.assertAlmostEqual(geom.od_mm(15), 21.3)
        self.assertAlmostEqual(geom.od_mm(100), 114.3)
        self.assertAlmostEqual(geom.od_mm(500), 508.0)
        self.assertAlmostEqual(geom.od_mm(900), 914.4)

    def test_od_mm_unknown_raises(self):
        with self.assertRaises(ValueError):
            geom.od_mm(123)

    def test_nps_and_label(self):
        self.assertEqual(geom.nps_text(100), '4"')
        self.assertIn('4"', geom.dn_label(100))
        self.assertEqual(geom.dn_choices()[0], 15)
        self.assertEqual(geom.dn_choices()[-1], 900)


class TestMatchDn(unittest.TestCase):
    def test_nominal_value(self):
        self.assertEqual(geom.match_dn(100), 100)
        self.assertEqual(geom.match_dn(250), 250)

    def test_outside_diameter(self):
        self.assertEqual(geom.match_dn(114.3), 100)
        self.assertEqual(geom.match_dn(219.1), 200)
        self.assertEqual(geom.match_dn(273.0), 250)

    def test_out_of_range(self):
        self.assertIsNone(geom.match_dn(None))
        self.assertIsNone(geom.match_dn('x'))
        self.assertIsNone(geom.match_dn(0))
        self.assertIsNone(geom.match_dn(9999))


class TestPlateThickness(unittest.TestCase):
    def test_table_1_boundaries(self):
        # 表 1：DN15~200 → 6；DN250~450 → 8；DN500~900 → 10。
        for dn in (15, 50, 100, 200):
            self.assertAlmostEqual(geom.plate_thickness_mm(dn), 6.0)
        for dn in (250, 300, 400, 450):
            self.assertAlmostEqual(geom.plate_thickness_mm(dn), 8.0)
        for dn in (500, 600, 900):
            self.assertAlmostEqual(geom.plate_thickness_mm(dn), 10.0)

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            geom.plate_thickness_mm(10)
        with self.assertRaises(ValueError):
            geom.plate_thickness_mm(1000)


class TestMaterialCodes(unittest.TestCase):
    def test_table_2(self):
        self.assertEqual(geom.material_for_code('C1')['pad_material'], 'Q235B')
        self.assertEqual(geom.material_for_code('l')['pad_material'], 'Q345R')
        self.assertEqual(geom.material_for_code('C2')['pad_material'], 'Q345R')
        self.assertEqual(geom.material_for_code('A1')['pad_material'], '15CrMoR')
        self.assertEqual(geom.material_for_code('A2')['pad_material'],
                         '12Cr1MoVR')
        self.assertEqual(geom.material_for_code('S')['pad_material'],
                         '06Cr19Ni10')

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            geom.material_for_code('X')

    def test_default_present(self):
        self.assertIn(geom.DEFAULT_MATERIAL_CODE, geom.MATERIAL_CODES)


class TestNumber(unittest.TestCase):
    def test_format(self):
        self.assertEqual(geom.build_number(100, 500, 'c1', 120),
                         'Y2-100-500-C1-120')
        self.assertEqual(geom.build_number(50, 300.0, 'S', 180.0),
                         'Y2-50-300-S-180')

    def test_fractional(self):
        self.assertEqual(geom.build_number(100, 500.5, 'C1', 120.5),
                         'Y2-100-500.5-C1-120.5')

    def test_k1_note(self):
        self.assertTrue(geom.k1_alpha_note(100))
        self.assertTrue(geom.k1_alpha_note(125))
        self.assertEqual(geom.k1_alpha_note(150), '')


class TestLayout(unittest.TestCase):
    def test_basic(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        self.assertEqual(layout.dn, 100)
        self.assertAlmostEqual(layout.od_mm, 114.3)
        self.assertAlmostEqual(layout.thickness, 6.0)
        self.assertAlmostEqual(layout.inner_radius, 57.15)
        self.assertAlmostEqual(layout.outer_radius, 63.15)
        self.assertAlmostEqual(layout.length_mm, 500.0)
        self.assertAlmostEqual(layout.half_length_mm, 250.0)
        self.assertAlmostEqual(layout.alpha_deg, 120.0)
        self.assertEqual(layout.material_code, 'C1')
        self.assertEqual(layout.pad_material, 'Q235B')
        self.assertEqual(layout.number, 'Y2-100-500-C1-120')

    def test_outer_equals_inner_plus_thickness(self):
        for dn in (15, 100, 300, 500, 900):
            layout = geom.build_layout(dn, 400, 'C1', 120)
            self.assertAlmostEqual(
                layout.outer_radius - layout.inner_radius, layout.thickness)

    def test_alpha_default(self):
        self.assertAlmostEqual(geom.build_layout(100, 500).alpha_deg, 120.0)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            geom.build_layout(100, 0)          # L 过小
        with self.assertRaises(ValueError):
            geom.build_layout(100, 500, 'C1', 0)     # α 过小
        with self.assertRaises(ValueError):
            geom.build_layout(100, 500, 'C1', 400)   # α 过大
        with self.assertRaises(ValueError):
            geom.build_layout(10, 500)         # 管径超范围
        with self.assertRaises(ValueError):
            geom.build_layout(100, 500, 'X')   # 材料代码非法


class TestSectionPoints(unittest.TestCase):
    def _steps(self, layout):
        return geom.arc_step_count(layout.alpha_deg) + 1

    def test_structure_and_radii(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        points = geom.section_points(layout)
        steps = self._steps(layout)
        self.assertEqual(len(points), 2 * steps)

        inner = points[:steps]
        outer = points[steps:]
        for y, z in inner:
            self.assertAlmostEqual(math.hypot(y, z), layout.inner_radius, places=6)
        for y, z in outer:
            self.assertAlmostEqual(math.hypot(y, z), layout.outer_radius, places=6)

    def test_lowest_point_on_bottom(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        points = geom.section_points(layout)
        steps = self._steps(layout)
        middle = points[steps // 2]
        self.assertAlmostEqual(middle[0], 0.0, places=6)
        self.assertAlmostEqual(middle[1], -layout.inner_radius, places=6)

    def test_entirely_below_axis(self):
        for alpha in (60, 120, 180):
            layout = geom.build_layout(200, 400, 'C2', alpha)
            for _y, z in geom.section_points(layout):
                self.assertLessEqual(z, 1.0e-9)

    def test_closed_by_radial_line(self):
        layout = geom.build_layout(300, 400, 'C1', 120)
        points = geom.section_points(layout)
        first, last = points[0], points[-1]
        gap = math.hypot(first[0] - last[0], first[1] - last[1])
        # 首尾由一条径向直线相连，长度 = 板厚。
        self.assertAlmostEqual(gap, layout.thickness, places=6)

    def test_symmetry_about_bottom(self):
        layout = geom.build_layout(300, 400, 'C1', 120)
        points = geom.section_points(layout)
        steps = self._steps(layout)
        inner = points[:steps]
        # 内弧关于 y = 0 对称。
        for index in range(steps):
            left = inner[index]
            right = inner[steps - 1 - index]
            self.assertAlmostEqual(left[0], -right[0], places=6)
            self.assertAlmostEqual(left[1], right[1], places=6)

    def test_alpha_180_endpoints_at_sides(self):
        layout = geom.build_layout(100, 500, 'C1', 180)
        points = geom.section_points(layout)
        steps = self._steps(layout)
        # α=180°：内弧端点落在 y = ±R、z = 0。
        self.assertAlmostEqual(points[0][1], 0.0, places=6)
        self.assertAlmostEqual(abs(points[0][0]), layout.inner_radius, places=6)
        self.assertAlmostEqual(points[steps - 1][1], 0.0, places=6)


class TestSectionSegments(unittest.TestCase):
    """截面轮廓段：直线 + 真圆弧（三点定弧），供无棱面的拉伸建模。"""

    @staticmethod
    def _circumradius(first, second, third):
        ax, ay = first
        bx, by = second
        cx, cy = third
        denominator = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        side_a = math.hypot(bx - cx, by - cy)
        side_b = math.hypot(cx - ax, cy - ay)
        side_c = math.hypot(ax - bx, ay - by)
        return side_a * side_b * side_c / abs(denominator)

    def test_structure(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        segments = geom.section_segments(layout)
        self.assertEqual([kind for kind, _points in segments],
                         ['arc', 'line', 'arc', 'line'])
        self.assertEqual(len(segments[0][1]), 3)   # 圆弧：起点 / 中点 / 终点
        self.assertEqual(len(segments[1][1]), 2)   # 直线：起点 / 终点

    def test_arcs_lie_on_expected_radii(self):
        """圆弧三点的外接圆半径 = 内弧 / 外弧半径，证明是精确圆弧而非折线。"""
        layout = geom.build_layout(300, 500, 'C1', 120)
        segments = geom.section_segments(layout)
        self.assertAlmostEqual(self._circumradius(*segments[0][1]),
                               layout.inner_radius, places=6)
        self.assertAlmostEqual(self._circumradius(*segments[2][1]),
                               layout.outer_radius, places=6)

    def test_arc_midpoint_is_lowest_point(self):
        layout = geom.build_layout(200, 500, 'C1', 120)
        inner_arc = geom.section_segments(layout)[0][1]
        self.assertAlmostEqual(inner_arc[1][0], 0.0, places=6)
        self.assertAlmostEqual(inner_arc[1][1], -layout.inner_radius, places=6)

    def test_chain_is_closed(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        segments = geom.section_segments(layout)
        for index, (_kind, points) in enumerate(segments):
            following = segments[(index + 1) % len(segments)][1]
            for left, right in zip(points[-1], following[0]):
                self.assertAlmostEqual(left, right, places=9)

    def test_radial_lines_span_the_thickness(self):
        layout = geom.build_layout(450, 500, 'C1', 120)
        lines = [points for kind, points in geom.section_segments(layout)
                 if kind == 'line']
        self.assertEqual(len(lines), 2)
        for points in lines:
            length = math.hypot(points[1][0] - points[0][0],
                                points[1][1] - points[0][1])
            self.assertAlmostEqual(length, layout.thickness, places=6)

    def test_matches_polyline_key_points(self):
        """真圆弧端点 / 中点与折线近似的关键点重合（同一轮廓）。"""
        layout = geom.build_layout(500, 800, 'A1', 180)
        inner_arc = geom.section_segments(layout)[0][1]
        points = geom.section_points(layout)
        steps = geom.arc_step_count(layout.alpha_deg) + 1
        pairs = ((inner_arc[0], points[0]),
                 (inner_arc[1], points[steps // 2]),
                 (inner_arc[2], points[steps - 1]))
        for expected, actual in pairs:
            self.assertAlmostEqual(expected[0], actual[0], places=6)
            self.assertAlmostEqual(expected[1], actual[1], places=6)


class TestAreaAndMass(unittest.TestCase):
    def test_area_formula(self):
        layout = geom.build_layout(100, 500, 'C1', 120)
        expected = (0.5 * math.radians(120)
                    * (layout.outer_radius ** 2 - layout.inner_radius ** 2)
                    - math.pi * (geom.VENT_HOLE_DIA_MM / 2.0) ** 2)
        self.assertAlmostEqual(geom.section_area_mm2(layout), expected, places=6)

    def test_vent_hole_toggle(self):
        with_hole = geom.build_layout(100, 500, 'C1', 120, has_vent_hole=True)
        without = geom.build_layout(100, 500, 'C1', 120, has_vent_hole=False)
        difference = (geom.section_area_mm2(without)
                      - geom.section_area_mm2(with_hole))
        self.assertAlmostEqual(difference,
                               math.pi * (geom.VENT_HOLE_DIA_MM / 2.0) ** 2,
                               places=6)

    def test_mass(self):
        layout = geom.build_layout(500, 1000, 'C1', 120)
        expected = (geom.section_area_mm2(layout) * 1000.0
                    * geom.STEEL_DENSITY_KG_MM3)
        self.assertAlmostEqual(geom.plate_mass_kg(layout), expected, places=6)
        self.assertGreater(geom.plate_mass_kg(layout), 0.0)


if __name__ == '__main__':
    unittest.main()