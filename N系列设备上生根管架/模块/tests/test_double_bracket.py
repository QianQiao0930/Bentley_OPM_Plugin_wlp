# -*- coding: utf-8 -*-
"""N 系列 —— 双三角架（N4）纯数据 / 逻辑单测（不依赖 Bentley 运行时）。"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_DOUBLE_DIR = os.path.join(_MODULE_DIR, '双三角架')
_SINGLE_DIR = os.path.join(_MODULE_DIR, '单三角架')
for _path in (_DOUBLE_DIR, _SINGLE_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 双三角架_数据 as data  # noqa: E402


# 表 3 原值：(构件A, 构件B, 构件C, 连接板类型, MIN.H, MIN.L2)
TABLE_THREE = {
    'A': ('[14a', '[10', '[14a', 2, 390.0, 390.0),
    'B': ('[20a', '[12.6', '[20a', 3, 480.0, 480.0),
    'C': ('H148x100x6x9', 'H100x100x6x8', 'H125x125x6.5x9', 2, 390.0, 390.0),
    'D': ('H194x150x6x9', 'H125x125x6.5x9', 'H175x175x7.5x11', 3, 480.0, 480.0),
    'E': ('H244x175x7x11', 'H150x150x7x10', 'H200x200x8x12', 4, 500.0, 500.0),
    'F': ('H294x200x8x12', 'H200x200x8x12', 'H250x250x9x14', 5, 590.0, 590.0),
}


class TableTests(unittest.TestCase):
    def test_table_three_values(self):
        for key, expected in TABLE_THREE.items():
            info = data.SUBTYPES[key]
            actual = (info['comp_a'], info['comp_b'], info['comp_c'],
                      info['plate_type'], info['min_h'], info['min_l2'])
            self.assertEqual(actual, expected, msg='子项 %s' % key)

    def test_sections_present(self):
        for info in data.SUBTYPES.values():
            for spec in (info['comp_a'], info['comp_b'], info['comp_c']):
                self.assertIn(spec, data.SECTIONS)

    def test_new_h_sections(self):
        self.assertEqual(data.section_dims('H175x175x7.5x11')['height'], 175.0)
        self.assertEqual(data.section_dims('H250x250x9x14')['height'], 250.0)


class ResolveTests(unittest.TestCase):
    def test_defaults_and_radial_chain(self):
        # 横担长 = L1 + L3 + 50 + 构件C宽；横担自中心线 r=0 起算。
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'l3_mm': 300.0, 'l4_mm': 200.0},
            1500.0)
        self.assertAlmostEqual(resolved['L1'], 1500.0)
        c_width = data.section_dims('[14a')['width']
        self.assertAlmostEqual(
            resolved['beam_length'], 1500.0 + 300.0 + 50.0 + c_width)
        self.assertAlmostEqual(resolved['beam_start_r'], 0.0)
        self.assertAlmostEqual(resolved['outer_end'],
                               resolved['beam_length'])

    def test_beam_offset_is_half_l2(self):
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'l2_mm': 600.0}, 500.0)
        self.assertAlmostEqual(resolved['beam_offset'], 300.0)

    def test_h_below_min_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options(
                {'subtype': 'A', 'type': 1, 'height_mm': 300.0}, 500.0)

    def test_l2_below_min_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options(
                {'subtype': 'A', 'type': 1, 'l2_mm': 300.0}, 500.0)

    def test_l4_may_equal_or_exceed_l3(self):
        # 内侧构件C 由 L4 控制，可与 L3 相同甚至更大。
        equal = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'l3_mm': 900.0, 'l4_mm': 900.0}, 500.0)
        self.assertAlmostEqual(equal['L4'], 900.0)
        bigger = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'l3_mm': 900.0, 'l4_mm': 1200.0}, 500.0)
        self.assertAlmostEqual(bigger['L4'], 1200.0)

    def test_unknown_subtype_is_rejected(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'Z'}, 500.0)

    def test_plate_type_from_table(self):
        for key, expected in TABLE_THREE.items():
            resolved = data.resolve_options({'subtype': key, 'type': 1}, 500.0)
            self.assertEqual(resolved['plate_type'], expected[3])

    def test_connector_span_channel_back_to_back(self):
        # 槽钢横担背靠背：构件C 跨距 = L2 − 构件A宽（焊在两腹板外表面）。
        channel = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'l2_mm': 600.0}, 1500.0)
        self.assertAlmostEqual(
            channel['connector_span'],
            600.0 - data.section_dims('[14a')['width'])
        # 工字钢横担：构件C 只焊到两腹板侧面，跨距 = L2 − 腹板厚。
        hbeam = data.resolve_options(
            {'subtype': 'C', 'type': 1, 'l2_mm': 600.0}, 1500.0)
        self.assertAlmostEqual(
            hbeam['connector_span'],
            600.0 - data.section_dims('H148x100x6x9')['tw'])

    def test_type_one_brace_run(self):
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 1, 'height_mm': 500.0}, 500.0)
        self.assertAlmostEqual(resolved['brace_run'], 500.0 - 140.0)

    def test_type_two_brace_run(self):
        resolved = data.resolve_options(
            {'subtype': 'A', 'type': 2, 'height_mm': 500.0}, 500.0)
        self.assertAlmostEqual(resolved['brace_run'], 500.0)


class LoadTests(unittest.TestCase):
    def test_vertical_load_values(self):
        expected = {
            ('A', 500): 76.0, ('A', 1000): 36.0,
            ('C', 1500): 100.0, ('D', 2000): 120.0,
            ('E', 2500): 200.0, ('F', 1000): 500.0,
        }
        for (key, span), value in expected.items():
            load, used, _ = data.vertical_load(key, span)
            self.assertAlmostEqual(load, value, places=6,
                                   msg='%s a=%d' % (key, span))
            self.assertEqual(used, span)

    def test_horizontal_load_values(self):
        expected = {
            ('A', 500): 6.0, ('B', 1000): 4.0, ('C', 1250): 4.0,
            ('D', 1500): 5.0, ('E', 750): 40.0, ('F', 500): 90.0,
        }
        for (key, span), value in expected.items():
            load, used, _ = data.horizontal_load(key, span)
            self.assertAlmostEqual(load, value, places=6,
                                   msg='%s b=%d' % (key, span))
            self.assertEqual(used, span)

    def test_span_rounds_up(self):
        load, used, _ = data.vertical_load('A', 600.0)
        self.assertEqual(used, 750)
        self.assertAlmostEqual(load, 56.0)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            data.build_number('N4', 1, 'A', 390.0, 500.0, 400.0, 900.0, 300.0),
            'N4-1-A-390-500-400-900-300')

    def test_empty_series_produces_no_number(self):
        self.assertEqual(
            data.build_number('', 1, 'A', 390.0, 500.0, 400.0, 900.0, 300.0),
            '')


if __name__ == '__main__':
    unittest.main()
