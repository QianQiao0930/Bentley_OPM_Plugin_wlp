# -*- coding: utf-8 -*-
"""N 系列 —— 单三角架（N3）纯数据 / 逻辑单测（不依赖 Bentley 运行时）。

覆盖：表 2 子项、截面尺寸、H / 端部余量校验、类型 1/2 的斜撑几何、表 1 荷载
查值、管架编号 ``N3-名称-类型-子项-H-L``。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '单三角架')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 单三角架_数据 as data  # noqa: E402


# 表 2 原值：(构件A, 构件B, 连接板类型, MIN.H)
TABLE_TWO = {
    'A': ('[14a', '[10', 2, 390.0),
    'B': ('[20a', '[12.6', 3, 480.0),
    'C': ('H148x100x6x9', 'H100x100x6x8', 2, 390.0),
    'D': ('H194x150x6x9', 'H125x125x6.5x9', 3, 480.0),
    'E': ('H244x175x7x11', 'H150x150x7x10', 4, 500.0),
    'F': ('H294x200x8x12', 'H200x200x8x12', 5, 590.0),
}


class TableTests(unittest.TestCase):
    def test_table_two_values(self):
        for key, expected in TABLE_TWO.items():
            info = data.SUBTYPES[key]
            actual = (info['comp_a'], info['comp_b'], info['plate_type'],
                      info['min_h'])
            self.assertEqual(actual, expected, msg='子项 %s' % key)

    def test_six_subtypes(self):
        self.assertEqual(data.SUBTYPE_KEYS, ('A', 'B', 'C', 'D', 'E', 'F'))

    def test_sections_present(self):
        for info in data.SUBTYPES.values():
            self.assertIn(info['comp_a'], data.SECTIONS)
            self.assertIn(info['comp_b'], data.SECTIONS)

    def test_channel_and_h_dims(self):
        self.assertEqual(data.section_dims('[14a')['height'], 140.0)
        self.assertEqual(data.section_dims('[20a')['height'], 200.0)
        self.assertEqual(data.section_dims('H148x100x6x9')['height'], 148.0)
        self.assertEqual(data.section_dims('H148x100x6x9')['width'], 100.0)
        self.assertEqual(data.section_dims('H148x100x6x9')['kind'], 'H')
        self.assertEqual(data.section_dims('[14a')['kind'], 'C')


class ResolveTests(unittest.TestCase):
    def test_type_one_brace_run(self):
        # 类型 1：斜撑投影 = H - 横担截面高。
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'height_mm': 500.0}, 1500.0)
        self.assertAlmostEqual(resolved['brace_run'], 500.0 - 140.0)
        self.assertAlmostEqual(resolved['attach_x'], 360.0)
        self.assertAlmostEqual(resolved['end_overhang'], 1500.0 - 360.0)

    def test_type_two_brace_run(self):
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 2, 'height_mm': 500.0}, 1500.0)
        self.assertAlmostEqual(resolved['brace_run'], 500.0)
        self.assertAlmostEqual(resolved['end_overhang'], 1000.0)

    def test_brace_is_forty_five_degrees(self):
        resolved = data.resolve_options(
            {'subtype': 'B', 'type': 1, 'height_mm': 800.0}, 2000.0)
        self.assertAlmostEqual(resolved['brace_length'],
                               resolved['brace_run'] * (2.0 ** 0.5), places=6)

    def test_default_height_is_min_h(self):
        resolved = data.resolve_options({'subtype': 'C', 'type': 1}, 2000.0)
        self.assertAlmostEqual(resolved['H'], 390.0)

    def test_height_below_min_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options(
                {'subtype': 'A', 'type': 1, 'height_mm': 300.0}, 1500.0)

    def test_end_overhang_below_150_is_rejected(self):
        # 类型 1：run = H - 140；L=800、H=700 → run=560 → 余量 240 OK。
        data.resolve_options({'subtype': 'A', 'type': 1, 'height_mm': 700.0},
                             800.0)
        # H=900 → run=760 → 余量 40 < 150。
        with self.assertRaises(ValueError):
            data.resolve_options(
                {'subtype': 'A', 'type': 1, 'height_mm': 900.0}, 800.0)

    def test_unknown_subtype_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'Z'}, 1500.0)

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'A', 'type': 3}, 1500.0)

    def test_plate_type_from_table(self):
        for key, expected in TABLE_TWO.items():
            resolved = data.resolve_options(
                {'subtype': key, 'type': 1}, 3000.0)
            self.assertEqual(resolved['plate_type'], expected[2])


class LoadTests(unittest.TestCase):
    def test_table_one_values(self):
        expected = {
            ('A', 500): 38.0, ('A', 1000): 18.0,
            ('B', 1000): 35.0, ('B', 1250): 30.0,
            ('C', 1500): 50.0, ('C', 1750): 40.0,
            ('D', 2000): 60.0,
            ('E', 2500): 100.0,
            ('F', 2000): 200.0,
        }
        for (key, span), value in expected.items():
            load, used, _ = data.allowable_load(key, span)
            self.assertAlmostEqual(load, value, places=6,
                                   msg='%s a=%d' % (key, span))
            self.assertEqual(used, span)

    def test_span_rounds_up_to_the_next_column(self):
        load, used, _ = data.allowable_load('A', 600.0)
        self.assertEqual(used, 750)
        self.assertAlmostEqual(load, 28.0)

    def test_out_of_range_is_reported(self):
        load, _used, note = data.allowable_load('A', 3000.0)
        self.assertIsNone(load)
        self.assertIn('超出表中上限', note)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            data.build_number('N3', 1, 'A', 390.0, 1200.0),
            'N3-1-A-390-1200')

    def test_number_rounds_h_and_l(self):
        self.assertEqual(
            data.build_number('N3', 2, 'C', 499.6, 1000.4),
            'N3-2-C-500-1000')

    def test_empty_series_produces_no_number(self):
        self.assertEqual(data.build_number('', 1, 'A', 390.0, 1200.0), '')
        self.assertEqual(data.build_number('  ', 1, 'A', 390.0, 1200.0), '')


if __name__ == '__main__':
    unittest.main()
