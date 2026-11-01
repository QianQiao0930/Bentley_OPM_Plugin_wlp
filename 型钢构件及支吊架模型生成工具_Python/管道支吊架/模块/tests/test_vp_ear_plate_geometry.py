# -*- coding: utf-8 -*-
"""小管径立管耳板（DN15~DN50）纯数据 / 尺寸推导单测（不依赖 Bentley 运行时）。

覆盖：DN→OD（ASME）表、长度 / 高度 / 材料代码表、尺寸推导（耳板径向、底板
径向/切向、孔心）、方位角与编号、构件清单、输入校验。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '小管径立管耳板')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import 小管径立管耳板_几何 as geom  # noqa: E402


class TableTests(unittest.TestCase):
    def test_dn_range(self):
        self.assertEqual(sorted(geom.DN_OD_TABLE), [15, 20, 25, 32, 40, 50])

    def test_pipe_outer_diameters_asme(self):
        expected = {15: 21.3, 20: 26.7, 25: 33.4, 32: 42.2, 40: 48.3, 50: 60.3}
        for dn, od in expected.items():
            self.assertAlmostEqual(geom.od_mm(dn), od, places=6, msg='DN%d' % dn)

    def test_length_codes(self):
        self.assertEqual(geom.length_for_code('1'), 100.0)
        self.assertEqual(geom.length_for_code('2'), 150.0)
        self.assertEqual(geom.length_for_code('3'), 200.0)

    def test_height_codes(self):
        self.assertEqual(geom.height_for_code('A'), (50.0, 10.0))
        self.assertEqual(geom.height_for_code('B'), (100.0, 20.0))
        self.assertEqual(geom.height_for_code('C'), (150.0, 40.0))
        self.assertEqual(geom.height_for_code('D'), (200.0, 60.0))
        self.assertEqual(geom.allowable_vertical_pipe_m('d'), 60.0)

    def test_material_codes(self):
        expected = {
            'L': ('Q345R', 'Q235B'),
            'C1': ('Q235B', 'Q235B'),
            'C2': ('Q345R', 'Q235B'),
            'A1': ('15CrMoR', 'Q235B'),
            'A2': ('12Cr1MoVR', 'Q235B'),
            'S': ('06Cr19Ni10', 'Q235B'),
        }
        for code, (ear, base) in expected.items():
            row = geom.material_for_code(code)
            self.assertEqual(row['ear_material'], ear, code)
            self.assertEqual(row['base_material'], base, code)

    def test_unknown_codes_raise(self):
        for call in (lambda: geom.length_for_code('9'),
                     lambda: geom.height_for_code('Z'),
                     lambda: geom.material_for_code('X'),
                     lambda: geom.od_mm(100)):
            self.assertRaises(ValueError, call)


class MatchDnTests(unittest.TestCase):
    def test_exact_and_near(self):
        for dn in (15, 20, 25, 32, 40, 50):
            self.assertEqual(geom.match_dn(dn), dn)
        # 公称直径略有偏差时取最近档（25.4 → DN25）。
        self.assertEqual(geom.match_dn(25.4), 25)

    def test_out_of_range_returns_none(self):
        self.assertIsNone(geom.match_dn(100))
        self.assertIsNone(geom.match_dn(None))
        self.assertIsNone(geom.match_dn(0))


class LayoutTests(unittest.TestCase):
    def test_ear_radial_span_touches_pipe(self):
        layout = geom.build_layout(dn=25, length_code='1', height_code='A')
        inner, outer = geom.ear_radial_span(layout)
        self.assertAlmostEqual(inner, 33.4 / 2.0, places=6)
        self.assertAlmostEqual(outer, 33.4 / 2.0 + 100.0, places=6)

    def test_base_radial_outer_flush_with_ear(self):
        layout = geom.build_layout(dn=25, length_code='2', height_code='C')
        ear_outer = geom.ear_radial_span(layout)[1]
        base_inner, base_outer = geom.base_radial_span(layout)
        self.assertAlmostEqual(base_outer, ear_outer, places=6)
        self.assertAlmostEqual(base_outer - base_inner, 70.0, places=6)
        self.assertLess(base_inner, ear_outer)

    def test_base_tangential_span(self):
        layout = geom.build_layout()
        self.assertEqual(geom.base_tangential_span(layout), (-60.0, 60.0))

    def test_ear_z_span_is_clean_rectangle(self):
        layout = geom.build_layout(height_code='B')
        bottom, top = geom.ear_z_span(layout)
        self.assertAlmostEqual(top, 100.0, places=6)
        # 耳板是干净的 H×L×10 矩形体，底端坐在底板顶面（z=0）。
        self.assertAlmostEqual(bottom, 0.0, places=6)
        self.assertAlmostEqual(top - bottom, layout.ear_height_mm, places=6)

    def test_hole_centers_fixed(self):
        layout = geom.build_layout(fixed=True)
        centers = geom.hole_centers(layout)
        self.assertEqual(len(centers), 2)
        base_inner, base_outer = geom.base_radial_span(layout)
        expected_r = (base_inner + base_outer) / 2.0
        for r, t in centers:
            self.assertAlmostEqual(r, expected_r, places=6)
        self.assertEqual(sorted(t for _, t in centers), [-40.0, 40.0])

    def test_hole_centers_not_fixed(self):
        layout = geom.build_layout(fixed=False)
        self.assertEqual(geom.hole_centers(layout), ())

    def test_invalid_code_raises(self):
        self.assertRaises(ValueError, lambda: geom.build_layout(length_code='9'))
        self.assertRaises(ValueError, lambda: geom.build_layout(height_code='Z'))
        self.assertRaises(ValueError, lambda: geom.build_layout(material_code='X'))


class NumberTests(unittest.TestCase):
    def test_number_format_fixed(self):
        number = geom.build_pipe_rack_number('2', 'B', 'C1', 0.0, True)
        self.assertEqual(number, 'F10-2-B-C1-0-Y')

    def test_number_not_fixed(self):
        number = geom.build_pipe_rack_number('1', 'A', 'S', 90.0, False)
        self.assertEqual(number, 'F10-1-A-S-90-N')

    def test_label_azimuth_uses_smaller(self):
        # 200° 与 20° 两块耳板，编号取较小的 20。
        self.assertAlmostEqual(geom.label_azimuth_deg(200.0), 20.0, places=6)
        self.assertAlmostEqual(geom.label_azimuth_deg(30.0), 30.0, places=6)

    def test_format_angle(self):
        self.assertEqual(geom.format_angle(0.0), '0')
        self.assertEqual(geom.format_angle(45.0), '45')
        self.assertEqual(geom.format_angle(22.5), '22.5')

    def test_layout_number_and_spec(self):
        layout = geom.build_layout(dn=40, length_code='3', height_code='D',
                                   material_code='A1', azimuth_deg=200.0,
                                   fixed=True)
        self.assertEqual(layout.number, 'F10-3-D-A1-20-Y')
        self.assertIn('DN40', geom.specification(layout))
        self.assertIn('15CrMoR', geom.specification(layout))


class ComponentTests(unittest.TestCase):
    def test_fixed_has_bolt_component(self):
        layout = geom.build_layout(fixed=True)
        items = geom.component_items(layout)
        codes = [item['code'] for item in items]
        self.assertEqual(codes, ['EarPlate', 'BasePlate', 'Bolt'])
        bolt = next(item for item in items if item['code'] == 'Bolt')
        self.assertEqual(bolt['quantity'], 4)
        self.assertIn('M12', bolt['specification'])

    def test_not_fixed_has_no_bolt(self):
        layout = geom.build_layout(fixed=False)
        codes = [item['code'] for item in geom.component_items(layout)]
        self.assertNotIn('Bolt', codes)

    def test_describe_mentions_fixed(self):
        self.assertIn('固定', geom.describe(geom.build_layout(fixed=True)))
        self.assertIn('不固定', geom.describe(geom.build_layout(fixed=False)))


if __name__ == '__main__':
    unittest.main()
