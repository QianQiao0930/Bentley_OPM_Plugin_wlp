# -*- coding: utf-8 -*-
"""立管的耳轴（F6/F7）纯数据 / 尺寸推导单测（不依赖 Bentley 运行时）。

覆盖：DN→OD（ASME）表、耳轴选取（表 1）、补强板 W、端板厚度（表 2）、材料
（表 3）、壁厚 STD、尺寸推导、方位角与编号、构件清单、输入校验。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '立管的耳轴')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 立管的耳轴_几何 as geom  # noqa: E402


class TableTests(unittest.TestCase):
    def test_dn_range(self):
        self.assertEqual(min(geom.DN_OD_TABLE), 50)
        self.assertEqual(max(geom.DN_OD_TABLE), 1200)

    def test_outer_diameters_spot(self):
        expected = {50: 60.3, 100: 114.3, 200: 219.1, 600: 609.6,
                    1000: 1016.0, 1200: 1219.2}
        for dn, od in expected.items():
            self.assertAlmostEqual(geom.od_mm(dn), od, places=6, msg='DN%d' % dn)

    def test_nps_text(self):
        self.assertEqual(geom.nps_text(100), '4"')
        self.assertEqual(geom.nps_text(250), '10"')
        self.assertEqual(geom.nps_text(1200), '48"')

    def test_trunnion_candidates(self):
        self.assertEqual(geom.trunnion_candidates(50), (50,))
        self.assertEqual(geom.trunnion_candidates(100), (50, 80, 100))
        self.assertEqual(geom.trunnion_candidates(1200), (600,))
        self.assertEqual(geom.default_trunnion_dn(100), 100)
        self.assertEqual(geom.default_trunnion_dn(300), 250)

    def test_pad_width(self):
        self.assertEqual(geom.pad_w_mm(50), 50.0)
        self.assertEqual(geom.pad_w_mm(150), 50.0)
        self.assertEqual(geom.pad_w_mm(200), 75.0)
        self.assertEqual(geom.pad_w_mm(400), 75.0)
        self.assertEqual(geom.pad_w_mm(500), 100.0)
        self.assertEqual(geom.pad_w_mm(1000), 150.0)
        self.assertEqual(geom.pad_w_mm(1100), 200.0)
        self.assertEqual(geom.pad_w_mm(1200), 200.0)

    def test_end_plate_thickness(self):
        self.assertEqual(geom.end_plate_thickness_mm(50), 10.0)
        self.assertEqual(geom.end_plate_thickness_mm(80), 10.0)
        self.assertEqual(geom.end_plate_thickness_mm(100), 12.0)
        self.assertEqual(geom.end_plate_thickness_mm(250), 16.0)
        self.assertEqual(geom.end_plate_thickness_mm(400), 20.0)
        self.assertEqual(geom.end_plate_thickness_mm(600), 25.0)

    def test_end_plate_by_type(self):
        self.assertEqual(geom.end_plate_thickness_for_type('A', 200), 6.0)
        self.assertEqual(geom.end_plate_thickness_for_type('B', 200), 12.0)
        self.assertEqual(geom.end_plate_thickness_for_type('C', 200), 0.0)
        self.assertRaises(ValueError,
                          lambda: geom.end_plate_thickness_for_type('Z', 200))

    def test_material_codes(self):
        self.assertIn('Q235B', geom.material_for_code('C1')['trunnion_material'])
        self.assertIn('15CrMoG', geom.material_for_code('A1')['trunnion_material'])
        self.assertEqual(geom.material_for_code('S1')['trunnion_material'],
                         'Q235B 或相近材料（注 12）')

    def test_pad_required(self):
        self.assertTrue(geom.pad_required('S1'))
        self.assertFalse(geom.pad_required('C1'))

    def test_wall_std(self):
        self.assertAlmostEqual(geom.trunnion_wall_std_mm(50), 3.91, places=6)
        self.assertAlmostEqual(geom.trunnion_wall_std_mm(100), 6.02, places=6)


class MatchDnTests(unittest.TestCase):
    def test_match(self):
        for dn in (50, 100, 300, 1200):
            self.assertEqual(geom.match_dn(dn), dn)

    def test_out_of_range(self):
        self.assertIsNone(geom.match_dn(5000))
        self.assertIsNone(geom.match_dn(None))


class LayoutTests(unittest.TestCase):
    def test_end_plate_dia(self):
        layout = geom.build_layout(pipe_dn=250, trunnion_dn=200, end_type='A')
        self.assertAlmostEqual(layout.end_plate_dia_mm,
                               layout.trunnion_od + 12.0, places=6)

    def test_pad_od(self):
        layout = geom.build_layout(pipe_dn=100, trunnion_dn=100,
                                   pad_thickness_mm=5.0)
        self.assertAlmostEqual(layout.pad_w_mm, 50.0, places=6)
        # 补强板外径 = 耳轴外径 + 2W（按用户口径）。
        self.assertAlmostEqual(layout.pad_od_mm,
                               layout.trunnion_od + 100.0, places=6)
        self.assertTrue(layout.has_pad)

    def test_no_pad(self):
        layout = geom.build_layout(pad_thickness_mm=0.0)
        self.assertFalse(layout.has_pad)

    def test_trunnion_inner_radius(self):
        layout = geom.build_layout(trunnion_dn=100)
        self.assertAlmostEqual(
            geom.trunnion_inner_radius(layout),
            layout.trunnion_od / 2.0 - layout.trunnion_wall_mm, places=6)

    def test_type_and_count(self):
        self.assertEqual(geom.trunnion_count(geom.build_layout(type_code='F6')), 1)
        self.assertEqual(geom.trunnion_count(geom.build_layout(type_code='F7')), 2)
        self.assertEqual(geom.trunnion_azimuths(geom.build_layout(type_code='F7',
                                                                  azimuth_deg=0)),
                         (0.0, 180.0))

    def test_invalid_inputs(self):
        self.assertRaises(ValueError,
                          lambda: geom.build_layout(type_code='F9'))
        self.assertRaises(ValueError, lambda: geom.build_layout(length_mm=0))
        self.assertRaises(ValueError,
                          lambda: geom.build_layout(trunnion_wall_override_mm=999))


class NumberTests(unittest.TestCase):
    def test_default_number(self):
        layout = geom.build_layout(type_code='F6', pipe_dn=250, trunnion_dn=200,
                                   material_code='C1', length_mm=500,
                                   end_type='A', azimuth_deg=90.0,
                                   pad_thickness_mm=0.0)
        self.assertEqual(layout.number, 'F6-10"-8"-C1-500-A-90')

    def test_wall_override_number(self):
        layout = geom.build_layout(type_code='F6', pipe_dn=250, trunnion_dn=200,
                                   material_code='C1', length_mm=500,
                                   end_type='A', azimuth_deg=90.0,
                                   pad_thickness_mm=0.0,
                                   trunnion_wall_override_mm=22.23)
        self.assertEqual(layout.number, 'F6-10"-8"(22.23)-C1-500-A-90')

    def test_pad_suffix_number(self):
        layout = geom.build_layout(type_code='F6', pipe_dn=250, trunnion_dn=200,
                                   material_code='C1', length_mm=500,
                                   end_type='A', azimuth_deg=90.0,
                                   pad_thickness_mm=5.0)
        self.assertEqual(layout.number, 'F6-10"-8"-C1-500-A-90-5')

    def test_f7_smaller_azimuth(self):
        layout = geom.build_layout(type_code='F7', pipe_dn=250, trunnion_dn=200,
                                   azimuth_deg=200.0, pad_thickness_mm=0.0)
        self.assertEqual(layout.azimuth_label, '20')
        self.assertTrue(layout.number.endswith('-A-20'))

    def test_format_angle(self):
        self.assertEqual(geom.format_angle(0.0), '0')
        self.assertEqual(geom.format_angle(90.0), '90')
        self.assertEqual(geom.format_angle(22.5), '22.5')


class ComponentTests(unittest.TestCase):
    def test_components_with_pad(self):
        layout = geom.build_layout(pipe_dn=100, trunnion_dn=100, end_type='A',
                                   pad_thickness_mm=5.0)
        codes = [item['code'] for item in geom.component_items(layout)]
        self.assertEqual(codes, ['Trunnion', 'EndPlate', 'Pad'])

    def test_components_no_pad_type_c(self):
        layout = geom.build_layout(pipe_dn=100, trunnion_dn=100, end_type='C',
                                   pad_thickness_mm=0.0)
        codes = [item['code'] for item in geom.component_items(layout)]
        self.assertEqual(codes, ['Trunnion'])

    def test_quantities(self):
        layout = geom.build_layout(type_code='F7', pipe_dn=100, trunnion_dn=100,
                                   end_type='A', pad_thickness_mm=5.0)
        for item in geom.component_items(layout):
            self.assertEqual(item['quantity'], 2, item['code'])


if __name__ == '__main__':
    unittest.main()
