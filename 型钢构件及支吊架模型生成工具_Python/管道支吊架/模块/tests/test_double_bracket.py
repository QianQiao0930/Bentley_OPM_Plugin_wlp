# -*- coding: utf-8 -*-
"""N 系列 —— 双三角架（N4）纯数据 / 逻辑单测（不依赖 Bentley 运行时）。"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_DOUBLE_DIR = os.path.join(_MODULE_DIR, '双三角架')
_SINGLE_DIR = os.path.join(_MODULE_DIR, '单三角架')
_PLATE_DIR = os.path.join(_MODULE_DIR, '连接板')
for _path in (_DOUBLE_DIR, _SINGLE_DIR, _PLATE_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 双三角架_数据 as data  # noqa: E402
import 连接板_数据 as plate_data  # noqa: E402


# 辅助线总长 L = 设备中心 → 管道中心；2R = 设备外径；D = 设备预焊件长度。
# 默认取 L1 = 900 mm（子项 A 的 L1 上限为 1000 mm）。
DEFAULT_L1 = 900.0
DEFAULT_EQUIPMENT_OD = 2000.0
DEFAULT_PREWELD = 100.0
DEFAULT_L2 = 390.0          # 子项 A 的 MIN.L2


def total_for(l1=DEFAULT_L1, l2=DEFAULT_L2, od=DEFAULT_EQUIPMENT_OD,
              preweld=DEFAULT_PREWELD):
    """按 L1（端板外表面 → 管道中心）反算辅助线总长 L。"""
    return (float(l1)
            + data.equipment_face_r(float(od) / 2.0, float(l2))
            + float(preweld))


DEFAULT_TOTAL_LENGTH = total_for()


def resolve(overrides=None, total_length=DEFAULT_TOTAL_LENGTH):
    """按测试默认的设备外径 / 预焊件长度解析选项。"""
    options = {'equipment_od_mm': DEFAULT_EQUIPMENT_OD,
               'preweld_mm': DEFAULT_PREWELD}
    options.update(overrides or {})
    return data.resolve_options(options, total_length)


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
        # L1 = L − √(R² − L2²/4) − D；横担长 = L1 + L3 + 50 + 构件C宽。
        total = total_for()
        resolved = resolve({'l3_mm': 300.0, 'l4_mm': 200.0}, total)
        face = math.sqrt(1000.0 ** 2 - (resolved['L2'] / 2.0) ** 2)
        l1 = total - face - 100.0
        self.assertAlmostEqual(resolved['L'], total)
        self.assertAlmostEqual(resolved['OD'], 2000.0)
        self.assertAlmostEqual(resolved['R'], 1000.0)
        self.assertAlmostEqual(resolved['D'], 100.0)
        self.assertAlmostEqual(resolved['face_r'], face)
        self.assertAlmostEqual(resolved['L1'], l1)
        self.assertAlmostEqual(resolved['L1'], DEFAULT_L1)
        # 表 1 的 a ＝ L1；max_l1 ＝ 该子项最大 a 列。
        self.assertAlmostEqual(resolved['a'], resolved['L1'])
        self.assertAlmostEqual(resolved['max_l1'], 1000.0)
        c_width = data.section_dims('[14a')['width']
        self.assertAlmostEqual(resolved['beam_length'],
                               l1 + 300.0 + 50.0 + c_width)
        self.assertAlmostEqual(resolved['beam_start_r'], 0.0)
        self.assertAlmostEqual(resolved['outer_end'],
                               resolved['beam_length'])

    def test_beam_offset_is_half_l2(self):
        resolved = resolve({'l2_mm': 600.0})
        self.assertAlmostEqual(resolved['beam_offset'], 300.0)

    def test_h_below_min_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve({'subtype': 'A', 'type': 1, 'height_mm': 300.0})

    def test_l2_below_min_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve({'subtype': 'A', 'type': 1, 'l2_mm': 300.0})

    def test_l4_may_equal_or_exceed_l3(self):
        # 内侧构件C 由 L4 控制，可与 L3 相同甚至更大（仍须留在端板外侧）。
        total = total_for(1500.0, l2=590.0)      # 子项 F：MIN.L2 = 590
        equal = resolve({'subtype': 'F', 'l3_mm': 900.0, 'l4_mm': 900.0},
                        total)
        self.assertAlmostEqual(equal['L4'], 900.0)
        bigger = resolve({'subtype': 'F', 'l3_mm': 900.0, 'l4_mm': 1200.0},
                         total)
        self.assertAlmostEqual(bigger['L4'], 1200.0)

    def test_unknown_subtype_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve({'subtype': 'Z'})

    def test_plate_type_from_table(self):
        for key, expected in TABLE_THREE.items():
            resolved = resolve({'subtype': key, 'type': 1})
            self.assertEqual(resolved['plate_type'], expected[3])

    def test_connector_span_channel_back_to_back(self):
        # 槽钢横担背靠背：构件C 跨距 = L2 − 构件A宽（焊在两腹板外表面）。
        channel = resolve({'subtype': 'A', 'type': 1, 'l2_mm': 600.0})
        self.assertAlmostEqual(
            channel['connector_span'],
            600.0 - data.section_dims('[14a')['width'])
        # 工字钢横担：构件C 只焊到两腹板侧面，跨距 = L2 − 腹板厚。
        hbeam = resolve({'subtype': 'C', 'type': 1, 'l2_mm': 600.0})
        self.assertAlmostEqual(
            hbeam['connector_span'],
            600.0 - data.section_dims('H148x100x6x9')['tw'])

    def test_type_one_brace_run(self):
        resolved = resolve({'subtype': 'A', 'type': 1, 'height_mm': 500.0})
        self.assertAlmostEqual(resolved['brace_run'], 500.0 - 140.0)

    def test_type_two_brace_run(self):
        resolved = resolve({'subtype': 'A', 'type': 2, 'height_mm': 500.0})
        self.assertAlmostEqual(resolved['brace_run'], 500.0)


class EquipmentChainTests(unittest.TestCase):
    """L1 = L − √(R² − L2²/4) − D、表 1 的 L1 上限与输入校验。"""

    def test_l1_formula(self):
        face = math.sqrt(1000.0 ** 2 - 500.0 ** 2)
        total = total_for(900.0, l2=1000.0)
        resolved = resolve({'l2_mm': 1000.0}, total)
        self.assertAlmostEqual(resolved['face_r'], face)
        self.assertAlmostEqual(resolved['L1'], total - face - 100.0)
        self.assertAlmostEqual(resolved['L1'], 900.0)

    def test_max_l1_matches_table_one(self):
        # 表 1 每行最大的 a 列＝该子项允许的最大 L1。
        self.assertEqual(data.MAX_L1,
                         {'A': 1000.0, 'B': 1250.0, 'C': 1750.0,
                          'D': 2000.0, 'E': 2500.0, 'F': 2500.0})

    def test_l1_over_max_is_rejected(self):
        # 子项 A 的 L1 上限为 1000 mm。
        accepted = resolve({}, total_for(1000.0))
        self.assertAlmostEqual(accepted['L1'], 1000.0)
        with self.assertRaises(ValueError):
            resolve({}, total_for(1000.0 + 1.0))

    def test_bigger_subtype_allows_longer_l1(self):
        total = total_for(2000.0, l2=590.0)
        resolved = resolve({'subtype': 'F'}, total)     # F 上限 2500
        self.assertAlmostEqual(resolved['L1'], 2000.0)
        with self.assertRaises(ValueError):
            resolve({'subtype': 'A'}, total)            # A 上限 1000

    def test_vertical_load_is_looked_up_by_l1(self):
        # a ＝ L1：A 子项 L1=900 → 查 a≤1000 列（旧口径按斜撑投影 250 查 a≤500）。
        resolved = resolve({})
        self.assertAlmostEqual(resolved['L1'], 900.0)
        self.assertEqual(resolved['vertical_load_span'], 1000)
        self.assertAlmostEqual(resolved['vertical_load'], 36.0)

    def test_equipment_face_r(self):
        self.assertAlmostEqual(data.equipment_face_r(1000.0, 1200.0),
                               math.sqrt(1000.0 ** 2 - 600.0 ** 2))
        with self.assertRaises(ValueError):
            data.equipment_face_r(1000.0, 2000.0)   # L2/2 = R，超出设备外圆

    def test_compute_l1_matches_formula(self):
        self.assertAlmostEqual(
            data.compute_l1(3000.0, 800.0, 600.0, 50.0),
            3000.0 - math.sqrt(800.0 ** 2 - 300.0 ** 2) - 50.0)

    def test_preweld_defaults_to_zero(self):
        total = total_for(850.0)
        resolved = data.resolve_options(
            {'subtype': 'A', 'equipment_od_mm': 2000.0}, total)
        self.assertAlmostEqual(resolved['D'], 0.0)
        self.assertAlmostEqual(
            resolved['L1'],
            total - math.sqrt(1000.0 ** 2 - (resolved['L2'] / 2.0) ** 2))

    def test_equipment_od_is_required(self):
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'A'}, DEFAULT_TOTAL_LENGTH)
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'A', 'equipment_od_mm': ''},
                                 DEFAULT_TOTAL_LENGTH)
        with self.assertRaises(ValueError):
            data.resolve_options({'subtype': 'A', 'equipment_od_mm': 0.0},
                                 DEFAULT_TOTAL_LENGTH)

    def test_l1_must_be_positive(self):
        # 2R=2000、L2=390、D=100 时，L 必须大于 ≈1081 mm。
        with self.assertRaises(ValueError):
            resolve({}, 1000.0)

    def test_l4_must_stay_outboard_of_end_plate(self):
        # L1 = 900 时 L4=1000 会把内侧构件C 推进设备里。
        with self.assertRaises(ValueError):
            resolve({'l4_mm': 1000.0})

    def test_negative_preweld_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve({'preweld_mm': -10.0})


class AuxiliaryLineTests(unittest.TestCase):
    """辅助线口径：设备中心 → 管道中心，内缩 L1 得到端板基准线。"""

    LINE = {
        'start_mm': (0.0, 0.0, 100.0),
        'end_mm': (4000.0, 0.0, 100.0),
        'length_mm': 4000.0,
        'heading_deg': 0.0,
        'z_mm': 100.0,
    }

    def test_plate_line_shrinks_to_end_plate(self):
        plate = data.plate_line(self.LINE, 2919.198)
        self.assertAlmostEqual(plate['start_mm'][0], 4000.0 - 2919.198)
        self.assertAlmostEqual(plate['start_mm'][1], 0.0)
        self.assertAlmostEqual(plate['start_mm'][2], 100.0)
        self.assertAlmostEqual(plate['end_mm'][0], 4000.0)
        self.assertAlmostEqual(plate['length_mm'], 2919.198)
        self.assertAlmostEqual(plate['heading_deg'], 0.0)
        # 原始字典不被修改。
        self.assertAlmostEqual(self.LINE['start_mm'][0], 0.0)
        self.assertAlmostEqual(self.LINE['length_mm'], 4000.0)

    def test_plate_line_with_rotated_heading(self):
        line = dict(self.LINE, start_mm=(0.0, 0.0, 0.0),
                    end_mm=(0.0, 3000.0, 0.0), heading_deg=90.0)
        plate = data.plate_line(line, 500.0)
        self.assertAlmostEqual(plate['start_mm'][0], 0.0)
        self.assertAlmostEqual(plate['start_mm'][1], 2500.0)

    def test_plate_line_needs_end_point(self):
        with self.assertRaises(ValueError):
            data.plate_line({'start_mm': (0.0, 0.0, 0.0),
                             'heading_deg': 0.0}, 100.0)

    def test_orient_line_reverse_swaps_ends(self):
        oriented = data.orient_line(self.LINE, True)
        self.assertAlmostEqual(oriented['start_mm'][0], 4000.0)
        self.assertAlmostEqual(oriented['end_mm'][0], 0.0)
        self.assertAlmostEqual(abs(oriented['heading_deg']), 180.0)
        self.assertAlmostEqual(oriented['length_mm'], 4000.0)

    def test_orient_line_keeps_line_by_default(self):
        oriented = data.orient_line(self.LINE)
        self.assertEqual(oriented['start_mm'], self.LINE['start_mm'])
        self.assertAlmostEqual(oriented['heading_deg'], 0.0)

    def test_reverse_option_reaches_result(self):
        self.assertTrue(resolve({'reverse': True})['reverse'])
        self.assertFalse(resolve({})['reverse'])


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


class PreweldOptionTests(unittest.TestCase):
    """设备预焊件显示开关（几何生成在 Bentley 里，这里校验开关与前置尺寸）。"""

    def test_show_preweld_default_off(self):
        self.assertFalse(resolve({})['show_preweld'])
        self.assertTrue(resolve({'show_preweld': True})['show_preweld'])

    def test_preweld_constants_are_sane(self):
        self.assertGreater(data.PREWELD_PIPE_OD, 0.0)
        self.assertGreater(data.PREWELD_PIPE_WALL, 0.0)
        self.assertLess(data.PREWELD_PIPE_WALL, data.PREWELD_PIPE_OD / 2.0)
        self.assertGreaterEqual(data.PREWELD_PIPE_SEGMENTS, 8)
        # 透明度 75%：0.0＝不透明、1.0＝全透明。
        self.assertAlmostEqual(data.PREWELD_TRANSPARENCY, 0.75)

    def test_two_plates_leave_room_for_the_pipe(self):
        # 预焊件板占 x∈[T,2T]、φ100 管占 x∈[2T,D]：D 必须大于 2T 才画得出管。
        for key in data.SUBTYPE_KEYS:
            plate = plate_data.resolve_options({
                'type': data.SUBTYPES[key]['plate_type'], 'mode': 'H',
                'heading_deg': 0.0, 'mount': 'wall'})
            self.assertGreater(plate['T'], 0.0)
            # 各板型 2T ≤ 50 mm，故 D=100 mm 时仍留有 50 mm 管长。
            self.assertLessEqual(2.0 * plate['T'], 50.0, msg='子项 %s' % key)


class LabelTests(unittest.TestCase):
    """面板下拉框文本（固定 360 px 宽，标签必须够短）。"""

    def test_subtype_label_is_compact(self):
        for key in data.SUBTYPE_KEYS:
            label = data.subtype_label(key)
            self.assertTrue(label.startswith(key + ' | '))
            self.assertLessEqual(len(label), 56, msg=label)
            for spec in (data.SUBTYPES[key]['comp_a'],
                         data.SUBTYPES[key]['comp_b'],
                         data.SUBTYPES[key]['comp_c']):
                self.assertIn(spec, label)

    def test_subtype_detail_carries_plate_and_minimums(self):
        for key in data.SUBTYPE_KEYS:
            info = data.SUBTYPES[key]
            detail = data.subtype_detail(key)
            self.assertIn('板%d' % info['plate_type'], detail)
            self.assertIn('MIN.H %.0f' % info['min_h'], detail)
            self.assertIn('MIN.L2 %.0f' % info['min_l2'], detail)


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
