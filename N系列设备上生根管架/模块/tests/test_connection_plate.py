# -*- coding: utf-8 -*-
"""N 系列设备上生根管架 —— 连接板纯数据 / 逻辑单测（不依赖 Bentley 运行时）。

覆盖：表 1 尺寸、保温 H / 保冷 C 工况取值、图 1 / 图 2 孔位、参数校验与
管架编号 ``系列-名称-类型-H/C``。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '连接板')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 连接板_数据 as data  # noqa: E402


# 表 1 原值：(E, F, G保温, G保冷, T, D, L保温, L保冷, 数量)
TABLE_ONE = {
    0: (180.0, 100.0, 18.0, 24.0, 10.0, 16.0, 40.0, 120.0, 4),
    1: (290.0, 200.0, 22.0, 28.0, 12.0, 20.0, 50.0, 120.0, 4),
    2: (370.0, 270.0, 27.0, 33.0, 16.0, 24.0, 60.0, 140.0, 4),
    3: (460.0, 340.0, 33.0, 39.0, 20.0, 30.0, 80.0, 160.0, 4),
    4: (480.0, 380.0, 27.0, 33.0, 20.0, 24.0, 70.0, 150.0, 8),
    5: (570.0, 450.0, 33.0, 39.0, 25.0, 30.0, 90.0, 170.0, 8),
}


class TableTests(unittest.TestCase):
    def test_table_one_values(self):
        for key, expected in TABLE_ONE.items():
            table = data.PLATE_TABLE[key]
            actual = (table['E'], table['F'], table['G_ins'], table['G_cold'],
                      table['T'], table['D'], table['L_ins'], table['L_cold'],
                      table['bolt_count'])
            self.assertEqual(actual, expected, msg='类型 %d' % key)

    def test_six_types(self):
        self.assertEqual(data.TYPE_KEYS, (0, 1, 2, 3, 4, 5))


class ResolveTests(unittest.TestCase):
    def test_defaults(self):
        resolved = data.resolve_options()
        self.assertEqual(resolved['type'], 0)
        self.assertEqual(resolved['mode'], 'H')
        self.assertEqual(resolved['mount'], 'wall')
        self.assertAlmostEqual(resolved['G'], 18.0)
        self.assertAlmostEqual(resolved['bolt_length'], 40.0)
        self.assertEqual(resolved['bolt_count'], 4)

    def test_hot_mode_uses_insulated_columns(self):
        for key, row in TABLE_ONE.items():
            resolved = data.resolve_options({'type': key, 'mode': 'H'})
            self.assertAlmostEqual(resolved['G'], row[2])
            self.assertAlmostEqual(resolved['bolt_length'], row[6])

    def test_cold_mode_uses_cold_columns(self):
        for key, row in TABLE_ONE.items():
            resolved = data.resolve_options({'type': key, 'mode': 'C'})
            self.assertAlmostEqual(resolved['G'], row[3])
            self.assertAlmostEqual(resolved['bolt_length'], row[7])

    def test_no_insulation_mode_matches_hot_data(self):
        for key, row in TABLE_ONE.items():
            no_ins = data.resolve_options({'type': key, 'mode': 'N'})
            hot = data.resolve_options({'type': key, 'mode': 'H'})
            self.assertAlmostEqual(no_ins['G'], row[2])
            self.assertAlmostEqual(no_ins['bolt_length'], row[6])
            self.assertEqual(no_ins['holes'], hot['holes'])
            self.assertEqual(no_ins['bolt_count'], hot['bolt_count'])

    def test_mode_is_case_insensitive(self):
        self.assertEqual(data.resolve_options({'mode': 'c'})['mode'], 'C')
        self.assertEqual(data.resolve_options({'mode': 'n'})['mode'], 'N')

    def test_bolt_fastener_dimensions_present(self):
        resolved = data.resolve_options({'type': 3})
        for name in ('head_af', 'head_h', 'nut_af', 'nut_h',
                     'washer_od', 'washer_t'):
            self.assertGreater(resolved[name], 0.0, msg=name)
        self.assertGreater(resolved['nut_af'], resolved['bolt_dia'])

    def test_invalid_type_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'type': 9})
        with self.assertRaises(ValueError):
            data.resolve_options({'type': 'x'})

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'mode': 'Z'})

    def test_invalid_mount_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'mount': 'roof'})

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'size': 10})

    def test_non_finite_heading_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'heading_deg': float('nan')})


class HoleTests(unittest.TestCase):
    def test_four_holes_for_types_zero_to_three(self):
        for key in (0, 1, 2, 3):
            positions = data.hole_positions(key)
            self.assertEqual(len(positions), 4, msg='类型 %d' % key)

    def test_eight_holes_for_types_four_and_five(self):
        for key in (4, 5):
            positions = data.hole_positions(key)
            self.assertEqual(len(positions), 8, msg='类型 %d' % key)

    def test_four_hole_positions_are_the_corners_of_the_f_square(self):
        for key in (0, 1, 2, 3):
            half = data.PLATE_TABLE[key]['F'] / 2.0
            expected = {(-half, -half), (half, -half), (half, half),
                        (-half, half)}
            self.assertEqual(set(data.hole_positions(key)), expected)

    def test_eight_hole_positions_add_the_edge_midpoints(self):
        for key in (4, 5):
            half = data.PLATE_TABLE[key]['F'] / 2.0
            expected = {
                (-half, -half), (0.0, -half), (half, -half),
                (half, 0.0), (half, half), (0.0, half),
                (-half, half), (-half, 0.0),
            }
            self.assertEqual(set(data.hole_positions(key)), expected)

    def test_no_hole_at_the_plate_centre(self):
        for key in data.TYPE_KEYS:
            self.assertNotIn((0.0, 0.0), data.hole_positions(key))

    def test_holes_fit_inside_the_plate(self):
        for key in data.TYPE_KEYS:
            table = data.PLATE_TABLE[key]
            half = table['F'] / 2.0
            hole_r = max(table['G_ins'], table['G_cold']) / 2.0
            for (y, z) in data.hole_positions(key):
                self.assertLessEqual(abs(y) + hole_r, table['E'] / 2.0)
                self.assertLessEqual(abs(z) + hole_r, table['E'] / 2.0)
                self.assertLessEqual(max(abs(y), abs(z)), half)

    def test_bolt_count_matches_hole_count(self):
        for key in data.TYPE_KEYS:
            resolved = data.resolve_options({'type': key})
            self.assertEqual(resolved['bolt_count'], len(resolved['holes']))


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(data.build_plate_number('N8', 0, 'H'), 'N8-0-H')
        self.assertEqual(data.build_plate_number('N8', 5, 'C'), 'N8-5-C')

    def test_no_insulation_omits_the_mode_suffix(self):
        self.assertEqual(data.build_plate_number('N8', 1, 'N'), 'N8-1')
        self.assertEqual(data.build_plate_number('N8', 4, 'n'), 'N8-4')

    def test_empty_series_produces_no_number(self):
        self.assertEqual(data.build_plate_number('', 0, 'H'), '')
        self.assertEqual(data.build_plate_number('  ', 0, 'H'), '')


class DescriptionTests(unittest.TestCase):
    def test_type_label_mentions_dimensions(self):
        label = data.type_label(0)
        self.assertIn('类型 0', label)
        self.assertIn('180×180×10', label)
        self.assertIn('M16', label)

    def test_describe_spec_mentions_hole_and_bolt(self):
        text = data.describe_spec(data.resolve_options({'type': 4, 'mode': 'C'}))
        self.assertIn('480×480×20', text)
        self.assertIn('8-φ33', text)
        self.assertIn('M24×150', text)
        self.assertIn('保冷', text)


if __name__ == '__main__':
    unittest.main()
