# -*- coding: utf-8 -*-
"""弯头耳轴（F2 / F4 / F5）HVAC 圆风管分支的纯逻辑单测。

覆盖 ``elbow_selection_logic`` 新增的风管解析、表 1 档位匹配与 ``D450`` 编号，
并锁住管道弯头的老行为（含报错文案）不被改坏。
"""

import os
import sys
import unittest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_GEOM_DIR = os.path.join(os.path.dirname(_TEST_DIR), '竖直弯头的竖直耳轴')
if os.path.isdir(_GEOM_DIR) and _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

from elbow_selection_logic import (  # noqa: E402
    duct_size_label,
    duct_table_dn,
    f2_number,
    f4_number,
    f5_number,
    is_hvac_class,
    is_rect_hvac_class,
    main_size_token,
    resolve_elbow_dimensions,
)


# 与 F2/F4/F5 脚本里同一份表（子集足够覆盖测试用到的档位）。
PIPE_DATA = {
    50: (60.3, 3.91), 100: (114.3, 6.02), 150: (168.3, 7.11),
    200: (219.1, 8.18), 250: (273.0, 9.27), 300: (323.9, 9.53),
    350: (355.6, 9.53), 400: (406.4, 9.53), 450: (457.2, 9.53),
    500: (508.0, 9.53), 600: (610.0, 9.53), 700: (711.0, 19.05),
    800: (813.0, 19.05),
}
SUPPORTED_MAIN_DNS = tuple(sorted(PIPE_DATA))

# 资料/hvac_弯头属性.txt（元素 77462）里的 HVAC 数值属性。
HVAC_450_PROPERTIES = {
    'ANGLE': 90.0,
    'MAIN_DIAMETER': 450.0,
    'RUN_DIAMETER': 450.0,
    'RADIUS': 450.0,
    'RADIUS_TO_DIAMETER': 1.0,
    'WALL_THICKNESS': 0.0,
    'HVAC_THICKNESS': 0.0,
    'CONNECTION_LENGTH': 0.0,
    'MAIN_CONNECTION_LENGTH': 50.0,
    'RUN_CONNECTION_LENGTH': 50.0,
}


def resolve_duct(numbers, class_name='HVAC_ROUND_ELBOW', texts=None):
    return resolve_elbow_dimensions(
        numbers, texts or {}, class_name, PIPE_DATA, SUPPORTED_MAIN_DNS)


def resolve_pipe(numbers, texts=None, class_name='PIPE_ELBOW'):
    return resolve_elbow_dimensions(
        numbers, texts or {}, class_name, PIPE_DATA, SUPPORTED_MAIN_DNS)


class HvacClassificationTests(unittest.TestCase):
    def test_hvac_class_detection(self):
        self.assertTrue(is_hvac_class('HVAC_ROUND_ELBOW'))
        self.assertTrue(is_hvac_class('OpenPlant_3D.HVAC_ROUND_DUCT'))
        self.assertFalse(is_hvac_class('LONG_RADIUS_90_DEGREE_PIPE_ELBOW'))
        self.assertFalse(is_hvac_class(None))

    def test_rect_hvac_detection(self):
        self.assertTrue(is_rect_hvac_class('HVAC_RECT_ELBOW'))
        self.assertFalse(is_rect_hvac_class('HVAC_ROUND_ELBOW'))

    def test_rect_hvac_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '矩形风管'):
            resolve_duct(HVAC_450_PROPERTIES, 'HVAC_RECT_ELBOW')

    def test_duct_size_label_uses_actual_diameter(self):
        self.assertEqual('D450', duct_size_label(450.0))
        self.assertEqual('D315', duct_size_label(315.4))
        self.assertEqual('D1200', duct_size_label(1200.0))
        with self.assertRaises(ValueError):
            duct_size_label(0.0)

    def test_main_size_token(self):
        self.assertEqual('D450', main_size_token('D450', '18"'))
        self.assertEqual('18"', main_size_token(None, '18"'))
        self.assertEqual('DN450', main_size_token('  ', 'DN450'))


class DuctTableLookupTests(unittest.TestCase):
    def test_exact_diameter_matches_dn_without_note(self):
        dn, note = duct_table_dn(450.0, PIPE_DATA, SUPPORTED_MAIN_DNS)
        self.assertEqual(450, dn)
        self.assertEqual('', note)

    def test_metric_duct_size_matches_nearest_pipe_od_with_note(self):
        dn, note = duct_table_dn(315.0, PIPE_DATA, SUPPORTED_MAIN_DNS)
        self.assertEqual(300, dn)
        self.assertIn('就近匹配', note)

    def test_unmatched_size_is_reported(self):
        dn, note = duct_table_dn(90.0, PIPE_DATA, SUPPORTED_MAIN_DNS)
        self.assertIsNone(dn)
        self.assertIn('未匹配到表 1', note)


class DuctDimensionTests(unittest.TestCase):
    def test_sample_duct_elbow_77462(self):
        dims = resolve_duct(HVAC_450_PROPERTIES)
        self.assertTrue(dims['is_duct'])
        self.assertEqual(450, dims['main_dn'])
        self.assertEqual('D450', dims['main_label'])
        self.assertEqual('D450', dims['main_size_text'])
        self.assertEqual('', dims['main_dn_note'])
        self.assertAlmostEqual(450.0, dims['outside_diameter_mm'])
        self.assertAlmostEqual(450.0, dims['nominal_diameter_mm'])
        # HVAC 弯头端口在弯曲半径端面上：中心至端面 = RADIUS = 450。
        self.assertAlmostEqual(450.0, dims['run_length_mm'])
        self.assertAlmostEqual(450.0, dims['outlet_length_mm'])
        self.assertAlmostEqual(450.0, dims['center_to_end_mm'])
        self.assertAlmostEqual(0.0, dims['wall_thickness_mm'])

    def test_run_diameter_fallback_and_equivalent_diameter(self):
        dims = resolve_duct({'RUN_DIAMETER': 400.0, 'RADIUS': 600.0})
        self.assertEqual('D400', dims['main_label'])
        self.assertEqual(400, dims['main_dn'])
        self.assertAlmostEqual(600.0, dims['center_to_end_mm'])

    def test_length_half_fallback(self):
        dims = resolve_duct({'MAIN_DIAMETER': 450.0, 'LENGTH': 900.0})
        self.assertAlmostEqual(450.0, dims['center_to_end_mm'])
        self.assertEqual('D450', dims['main_label'])

    def test_design_length_wins_over_radius(self):
        dims = resolve_duct({'MAIN_DIAMETER': 450.0, 'RADIUS': 450.0,
                             'DESIGN_LENGTH_CENTER_TO_RUN_END': 500.0,
                             'DESIGN_LENGTH_CENTER_TO_OUTLET_END': 500.0})
        self.assertAlmostEqual(500.0, dims['center_to_end_mm'])

    def test_missing_diameter_is_reported(self):
        with self.assertRaisesRegex(ValueError, '缺少直径属性'):
            resolve_duct({'RADIUS': 450.0})

    def test_missing_radius_is_reported(self):
        with self.assertRaisesRegex(ValueError, '缺少 RADIUS'):
            resolve_duct({'MAIN_DIAMETER': 450.0})

    def test_unmatched_duct_size_is_reported(self):
        with self.assertRaisesRegex(ValueError, '未匹配到表 1'):
            resolve_duct({'MAIN_DIAMETER': 90.0, 'RADIUS': 90.0})

    def test_meter_unit_is_scaled(self):
        dims = resolve_duct({'MAIN_DIAMETER': 0.45, 'RADIUS': 0.45},
                            texts={'UNIT_OF_MEASURE': 'M'})
        self.assertAlmostEqual(450.0, dims['outside_diameter_mm'])
        self.assertEqual('D450', dims['main_label'])


class PipeBehaviourUnchangedTests(unittest.TestCase):
    def test_pipe_dimensions_and_labels(self):
        dims = resolve_pipe(
            {'NOMINAL_DIAMETER': 250.0, 'OUTSIDE_DIAMETER': 273.0,
             'WALL_THICKNESS': 9.27,
             'DESIGN_LENGTH_CENTER_TO_RUN_END': 381.0,
             'DESIGN_LENGTH_CENTER_TO_OUTLET_END': 381.0},
            texts={'UNIT_OF_MEASURE': 'MM'})
        self.assertFalse(dims['is_duct'])
        self.assertIsNone(dims['main_label'])
        self.assertEqual('DN250', dims['main_size_text'])
        self.assertEqual(250, dims['main_dn'])
        self.assertAlmostEqual(273.0, dims['outside_diameter_mm'])
        self.assertAlmostEqual(381.0, dims['run_length_mm'])
        self.assertAlmostEqual(9.27, dims['wall_thickness_mm'])

    def test_pipe_length_half_fallback(self):
        dims = resolve_pipe({'NOMINAL_DIAMETER': 400.0,
                             'OUTSIDE_DIAMETER': 406.4, 'LENGTH': 762.0})
        self.assertAlmostEqual(381.0, dims['center_to_end_mm'])

    def test_pipe_error_messages_unchanged(self):
        cases = (
            ({}, '弯头缺少 NOMINAL_DIAMETER。'),
            ({'NOMINAL_DIAMETER': 250.0},
             '弯头缺少有效的 OUTSIDE_DIAMETER。'),
            ({'NOMINAL_DIAMETER': 250.0, 'OUTSIDE_DIAMETER': 273.0},
             '弯头缺少中心至端面长度，无法确定两个端口坐标。'),
            ({'NOMINAL_DIAMETER': 260.0, 'OUTSIDE_DIAMETER': 273.0,
              'LENGTH': 762.0},
             '弯头公称直径 260.0 mm 不在当前参考表支持范围内。'),
        )
        for numbers, message in cases:
            with self.assertRaises(ValueError) as context:
                resolve_pipe(numbers)
            self.assertEqual(message, str(context.exception))


class DuctNumberFormatTests(unittest.TestCase):
    """编号里的主管尺寸按风管实际外径写（D450），不再写管道 NPS。"""

    def test_f2_duct_number(self):
        self.assertEqual(
            'F2-D450-10"-C1-500-A',
            f2_number(450, 250, 9.27, 9.27, 'C1', 500, 'A', main_label='D450'))

    def test_f2_duct_number_keeps_suffixes(self):
        self.assertEqual(
            'F2-D450-10"(12)-C1-500-B-F-UP-HE',
            f2_number(450, 250, 12.0, 9.27, 'C1', 500, 'B', ptfe=True,
                      upward=True, horizontal_elbow=True, main_label='D450'))

    def test_f2_pipe_number_unchanged(self):
        self.assertEqual(
            'F2-16"-8"-C1-500-A-HE',
            f2_number(400, 200, 8.18, 8.18, 'C1', 500, 'A',
                      horizontal_elbow=True))

    def test_f4_duct_number(self):
        self.assertEqual(
            'F4-D450-10"-C1-800-A',
            f4_number(450, 250, 9.27, 9.27, 'C1', 800, 'A',
                      main_label='D450'))
        self.assertEqual(
            'F4-D450-10"-C1-800-B-FB2',
            f4_number(450, 250, 9.27, 9.27, 'C1', 800, 'B', 'FB2',
                      main_label='D450'))

    def test_f4_pipe_number_unchanged(self):
        self.assertEqual('F4-16"-8"-C1-800-A-FB1',
                         f4_number(400, 200, 8.18, 8.18, 'C1', 800, 'A', 'FB1'))

    def test_f5_duct_number(self):
        self.assertEqual(
            'F5-D450-DN250-C1-800-A-45',
            f5_number(450, 250, 9.27, 9.27, 'C1', 800, 'A', 45,
                      main_label='D450'))
        self.assertEqual(
            'F5-D450-DN250-C1-800-A-45-FB',
            f5_number(450, 250, 9.27, 9.27, 'C1', 800, 'A', 45, True,
                      main_label='D450'))

    def test_f5_pipe_number_unchanged(self):
        self.assertEqual('F5-DN400-DN200-C1-800-A-45',
                         f5_number(400, 200, 8.18, 8.18, 'C1', 800, 'A', 45))

    def test_number_round_trip_with_resolver(self):
        dims = resolve_duct(HVAC_450_PROPERTIES)
        number = f2_number(dims['main_dn'], 250, 9.27, 9.27, 'C1', 500, 'A',
                           horizontal_elbow=True, main_label=dims['main_label'])
        self.assertEqual('F2-D450-10"-C1-500-A-HE', number)


if __name__ == '__main__':
    unittest.main()
