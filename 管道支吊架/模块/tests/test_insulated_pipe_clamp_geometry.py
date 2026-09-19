# -*- coding: utf-8 -*-
"""保温管夹（高温隔热限位管托）纯数据 / 尺寸推导单测（不依赖 Bentley 运行时）。

覆盖：DN80~600 表格与管外径、螺栓规格、T1/T2/T3、尺寸推导（H / L / 保温层 /
管夹外径 / 底板）、输入校验、允许荷载、管架编号。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '保温管夹')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 保温管夹_几何 as geom  # noqa: E402


class TableTests(unittest.TestCase):
    def test_dn_range(self):
        self.assertEqual(sorted(geom.DN_TABLE),
                         [80, 100, 125, 150, 200, 250, 300, 350, 400, 450,
                          500, 550, 600])

    def test_pipe_outer_diameters(self):
        expected = {
            80: 88.9, 100: 114.3, 125: 141.3, 150: 168.3, 200: 219.1,
            250: 273.0, 300: 323.9, 350: 355.6, 400: 406.4, 450: 457.2,
            500: 508.0, 550: 558.8, 600: 609.6,
        }
        for dn, od in expected.items():
            self.assertAlmostEqual(geom.od_mm(dn), od, places=6, msg='DN%d' % dn)

    def test_bolt_specs(self):
        """DN80~600 均为 4 个螺栓；直径随 DN 分级。"""
        expected = {80: 'M12', 100: 'M12', 125: 'M16', 150: 'M16',
                    200: 'M20', 250: 'M20', 300: 'M20', 350: 'M20',
                    400: 'M20', 450: 'M24', 500: 'M24', 550: 'M24',
                    600: 'M24'}
        for dn, dia in expected.items():
            row = geom.get_row(dn)
            self.assertEqual(row['bolt_count'], 4, 'DN%d' % dn)
            self.assertEqual(row['bolt_dia'], dia, 'DN%d' % dn)
            self.assertGreater(geom.bolt_dia_mm(dn), 0.0)

    def test_saddle_and_bearing_thicknesses(self):
        """表 1 的 T1 / T2 / T3 逐行核对。"""
        expected = {
            80: (10.0, 8.0, 6.0), 100: (10.0, 8.0, 6.0),
            125: (10.0, 8.0, 10.0), 150: (10.0, 8.0, 10.0),
            200: (12.0, 12.0, 12.0), 250: (12.0, 12.0, 12.0),
            300: (12.0, 12.0, 12.0), 350: (12.0, 12.0, 12.0),
            400: (12.0, 12.0, 12.0), 450: (14.0, 12.0, 14.0),
            500: (14.0, 12.0, 14.0), 550: (14.0, 12.0, 14.0),
            600: (14.0, 12.0, 14.0),
        }
        for dn, (t1, t2, t3) in expected.items():
            row = geom.get_row(dn)
            self.assertAlmostEqual(row['T1'], t1, places=6, msg='DN%d T1' % dn)
            self.assertAlmostEqual(row['T2'], t2, places=6, msg='DN%d T2' % dn)
            self.assertAlmostEqual(row['T3'], t3, places=6, msg='DN%d T3' % dn)

    def test_dn_choices_are_sorted(self):
        self.assertEqual([dn for dn, _label in geom.dn_choices()],
                         sorted(geom.DN_TABLE))

    def test_out_of_range_dn_is_rejected(self):
        for dn in (15, 50, 700, None, 'x'):
            with self.assertRaises(ValueError):
                geom.get_row(dn)


class LayoutTests(unittest.TestCase):
    def _layout(self, dn=200, insulation=50.0, height=400.0, length=500.0):
        return geom.build_layout(dn, insulation, height, length)

    def test_clamp_grips_the_insulation_outer_diameter(self):
        for dn in sorted(geom.DN_TABLE):
            layout = self._layout(dn=dn)
            self.assertAlmostEqual(layout.pipe_radius, geom.od_mm(dn) / 2.0,
                                   places=6)
            self.assertAlmostEqual(layout.insulation_radius,
                                   layout.pipe_radius + 50.0, places=6)
            self.assertAlmostEqual(layout.clamp_outer_radius,
                                   layout.insulation_radius + layout.t3,
                                   places=6)
            self.assertAlmostEqual(layout.insulation_od,
                                   layout.insulation_radius * 2.0, places=6)

    def test_height_is_pipe_bottom_to_shoe_bottom(self):
        """H = 管道（不含保温层）底部 → 管托底面。"""
        for dn in sorted(geom.DN_TABLE):
            for height in (200.0, 400.0, 1000.0):
                layout = self._layout(dn=dn, height=height)
                pipe_bottom_z = -layout.pipe_radius
                self.assertAlmostEqual(pipe_bottom_z - layout.shoe_bottom_z,
                                       height, places=6)

    def test_shoe_length_and_minimum(self):
        layout = self._layout(length=300.0)
        self.assertAlmostEqual(layout.shoe_length_mm, 300.0, places=9)
        with self.assertRaises(ValueError):
            geom.build_layout(200, 50.0, 400.0, 299.9)

    def test_base_width_comes_from_table_two(self):
        """底板宽度 W 由保温层外径 D 查表 2。"""
        for dn in sorted(geom.DN_TABLE):
            for insulation in (20.0, 50.0, 150.0):
                layout = self._layout(dn=dn, insulation=insulation)
                self.assertAlmostEqual(
                    layout.base_width,
                    geom.base_width_for_insulation_od(layout.insulation_od),
                    places=6, msg='DN%d B=%.0f' % (dn, insulation))

    def test_base_plate_and_height1(self):
        layout = self._layout()
        self.assertAlmostEqual(layout.base_top_z,
                               layout.shoe_bottom_z + layout.t1, places=6)
        self.assertAlmostEqual(layout.height1_mm,
                               layout.height_mm - layout.t1, places=6)

    def test_ear_and_gap_from_table_one(self):
        layout = self._layout(dn=200)
        self.assertEqual((layout.ear_width, layout.ear_height,
                          layout.ear_thickness), (60.0, 60.0, 20.0))
        self.assertAlmostEqual(layout.bolt_center_c, 35.0, places=6)
        self.assertAlmostEqual(layout.weld_leg_k, 8.0, places=6)
        self.assertAlmostEqual(layout.plate_gap_j, 30.0, places=6)

    def test_bolt_length(self):
        layout = self._layout()
        self.assertAlmostEqual(
            layout.bolt_length_mm,
            2.0 * layout.ear_thickness + geom.BOLT_EXTRA_MM, places=6)
        self.assertEqual(layout.bolt_count, 4)

    def test_middle_rib_threshold(self):
        self.assertFalse(self._layout(length=600.0).has_middle_rib)
        self.assertTrue(self._layout(length=601.0).has_middle_rib)

    def test_clamp_half_points_lie_between_the_radii(self):
        layout = self._layout(dn=300)
        r_in = layout.insulation_radius
        r_out = r_in + layout.t3
        for upper in (True, False):
            points = geom.clamp_half_points(layout, upper)
            self.assertGreater(len(points), 4)
            for y, z in points:
                radius = math.hypot(y, z)
                self.assertGreaterEqual(radius + 1.0e-6, r_in)
                self.assertLessEqual(radius - 1.0e-6, r_out)

    def test_shoe_section_points(self):
        layout = self._layout(dn=200)
        points = geom.shoe_section_points(layout)
        ys = [y for y, _z in points]
        zs = [z for _y, z in points]
        self.assertAlmostEqual(min(ys), -layout.base_width / 2.0, places=6)
        self.assertAlmostEqual(max(ys), layout.base_width / 2.0, places=6)
        self.assertAlmostEqual(min(zs), layout.shoe_bottom_z, places=6)
        self.assertAlmostEqual(max(zs), layout.top_plate_top_z, places=6)

    def test_table_values_reach_the_layout(self):
        layout = self._layout(dn=450)
        self.assertAlmostEqual(layout.t1, 14.0, places=6)
        self.assertAlmostEqual(layout.t2, 12.0, places=6)
        self.assertAlmostEqual(layout.t3, 14.0, places=6)
        self.assertEqual(layout.bolt_dia, 'M24')

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.build_layout(200, 0.5, 400.0, 500.0)
        with self.assertRaises(ValueError):
            geom.build_layout(200, 50.0, 0.5, 500.0)
        with self.assertRaises(ValueError):
            geom.build_layout(200, 50.0, 400.0, 100.0)


class LoadTableTests(unittest.TestCase):
    def test_allowable_loads(self):
        expected = {
            80: (40.0, 8.0, 30.0),
            150: (70.0, 15.0, 60.0),
            200: (150.0, 30.0, 80.0),
            400: (200.0, 40.0, 100.0),
            600: (300.0, 50.0, 120.0),
        }
        for dn, loads in expected.items():
            self.assertEqual(geom.allowable_loads(dn), loads, 'DN%d' % dn)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_clamp_number('T4', 200, '350', 400.0, 500.0, '20', '1'),
            'T4-200-350-400-500-20-1')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(
            geom.build_clamp_number('', 200, '350', 400, 500, '20', '1'), '')
        self.assertEqual(
            geom.build_clamp_number('   ', 200, '350', 400, 500, '20', '1'),
            '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(-0.5), 0)


if __name__ == '__main__':
    unittest.main()
