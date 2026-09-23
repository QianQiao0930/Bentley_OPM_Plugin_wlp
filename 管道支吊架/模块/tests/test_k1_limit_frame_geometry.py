# -*- coding: utf-8 -*-
"""K1 限位架（不保温管的限位架）纯几何 / 数据逻辑单测。

子项 A = 竖直半片 T；子项 B/C = 水平工字钢、长度沿管轴（腹板水平、两翼缘竖直，
管道骑在两翼缘端面），底板焊在朝已有钢构那一端的截面上。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_PLUGIN_DIR = os.path.dirname(_MODULE_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, 'K1限位架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import K1限位架_几何 as geom  # noqa: E402


class SubitemTest(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(geom.subitem_for_dn(15), 'A')
        self.assertEqual(geom.subitem_for_dn(80), 'A')
        self.assertEqual(geom.subitem_for_dn(100), 'B')
        self.assertEqual(geom.subitem_for_dn(250), 'B')
        self.assertEqual(geom.subitem_for_dn(300), 'C')
        self.assertEqual(geom.subitem_for_dn(900), 'C')

    def test_sizes(self):
        self.assertEqual(geom.main_size_mm(geom.get_subitem('A')), 100.0)
        self.assertEqual(geom.main_size_mm(geom.get_subitem('B')), 150.0)
        self.assertEqual(geom.main_size_mm(geom.get_subitem('C')), 200.0)

    def test_build_layout_auto_subitem(self):
        # build_layout 不传 subitem 时按 DN 自动选子项。
        for dn, expected in ((25, 'A'), (50, 'A'), (80, 'A'), (100, 'B'),
                             (150, 'B'), (250, 'B'), (300, 'C'), (900, 'C')):
            self.assertEqual(geom.build_layout(dn).subitem, expected,
                             msg='DN%d' % dn)

    def test_od_table_complete(self):
        # 管径表含 3 1/2"(90) 与 34"(850)。
        self.assertEqual(geom.od_mm(90), 101.6)
        self.assertEqual(geom.od_mm(850), 863.6)

    def test_match_dn(self):
        self.assertEqual(geom.match_dn(80.0), 80)
        self.assertEqual(geom.match_dn(114.3), 100)
        self.assertEqual(geom.match_dn(150.0), 150)
        self.assertIsNone(geom.match_dn(1000.0))


class NumberTest(unittest.TestCase):
    def test_number(self):
        self.assertEqual(geom.build_number('A', 50), 'K1-A')       # A 省管径
        self.assertEqual(geom.build_number('B', 150), 'K1-B-150')
        self.assertEqual(geom.build_number('C', 300), 'K1-C-300')


class TProfileTest(unittest.TestCase):
    def test_t_half(self):
        geometry = geom.member_geometry('A')
        self.assertTrue(geometry.is_closed_and_continuous())
        self.assertAlmostEqual(geometry.section['flange_width'], 100.0)
        self.assertAlmostEqual(geometry.section['depth'], 50.0)   # 8 + 42


class FrameTest(unittest.TestCase):
    def setUp(self):
        self.center = (1000.0, 2000.0, 500.0)
        self.width = 100.0
        # 各子项取一个合法管径（两翼缘净距 < 管外径）。
        self.od_by_subitem = {'A': 88.9, 'B': 219.1, 'C': 355.6}

    def _points(self, subitem, side, pipe_dir=(1.0, 0.0, 0.0)):
        samples = geom.sample_member(
            subitem, side, self.center, self.width,
            self.od_by_subitem[subitem], 1.0, pipe_dir)
        return [p for segment in samples for p in segment]

    def test_a_is_vertical_column(self):
        od = self.od_by_subitem['A']
        origin, _ax, _ay, az, length = geom.member_frame(
            'A', 1, self.center, self.width, od)
        self.assertAlmostEqual(az[2], 1.0)
        self.assertAlmostEqual(length, 100.0)
        self.assertAlmostEqual(origin[2] + length, self.center[2] - od / 2.0)
        for point in self._points('A', 1):
            self.assertAlmostEqual(point[2], origin[2], delta=1.0e-6)

    def test_bc_horizontal_beam_flange_top_at_contact(self):
        # 子项 B/C：水平梁，两翼缘端面（顶）= 管轴下方 contact；截面在 v-z 平面。
        for subitem in ('B', 'C'):
            od = self.od_by_subitem[subitem]
            item = geom.get_subitem(subitem)
            contact, _gap = geom.flange_seat(subitem, od)
            flange_top = self.center[2] - contact
            origin, ax, ay, az, length = geom.member_frame(
                subitem, 1, self.center, self.width, od)
            self.assertAlmostEqual(az[2], 0.0)                 # 沿管轴拉伸
            self.assertAlmostEqual(length, item['length_mm'])
            points = self._points(subitem, 1)
            zs = [p[2] for p in points]
            vs = [p[1] - self.center[1] for p in points]
            self.assertAlmostEqual(max(zs), flange_top, delta=1.0e-3)
            self.assertAlmostEqual(max(zs) - min(zs), item['cross_b_mm'],
                                   delta=1.0e-3)
            self.assertAlmostEqual(max(vs) - min(vs), item['cross_h_mm'],
                                   delta=1.0e-3)
            # 截面位于型钢内端（沿管轴 u = origin 处）。
            us = [p[0] - self.center[0] for p in points]
            self.assertAlmostEqual(max(us) - min(us), 0.0, delta=1.0e-6)
            self.assertAlmostEqual(min(us), origin[0] - self.center[0],
                                   delta=1.0e-6)
            # 管底在翼缘端面之下（管子骑在两翼缘之间）。
            self.assertLess(self.center[2] - od / 2.0, flange_top)

    def test_right_handed_frame(self):
        for subitem in geom.subitem_choices():
            od = self.od_by_subitem[subitem]
            for side in (1, -1):
                _o, ax, ay, az, _h = geom.member_frame(
                    subitem, side, self.center, self.width, od)
                cross = (ax[1] * ay[2] - ax[2] * ay[1],
                         ax[2] * ay[0] - ax[0] * ay[2],
                         ax[0] * ay[1] - ax[1] * ay[0])
                self.assertAlmostEqual(cross[0], az[0], delta=1.0e-9)
                self.assertAlmostEqual(cross[1], az[1], delta=1.0e-9)
                self.assertAlmostEqual(cross[2], az[2], delta=1.0e-9)

    def test_two_blocks_straddle_existing_steel(self):
        # B/C：底板内侧面在 u = ±W/2，型钢内端再外移一个板厚。
        for subitem in ('B', 'C'):
            od = self.od_by_subitem[subitem]
            thickness = geom.get_subitem(subitem)['plate'][2]
            plus = geom.plate_box(subitem, 1, self.center, self.width, od)
            minus = geom.plate_box(subitem, -1, self.center, self.width, od)
            self.assertAlmostEqual(plus.u0, self.width / 2.0)
            self.assertAlmostEqual(minus.u1, -self.width / 2.0)
            _o, _ax, _ay, _az, _l = geom.member_frame(
                subitem, 1, self.center, self.width, od)
            self.assertAlmostEqual(_o[0] - self.center[0],
                                   self.width / 2.0 + thickness)

    def test_plate_is_vertical_at_inner_end(self):
        od = self.od_by_subitem['C']
        box = geom.plate_box('C', 1, self.center, self.width, od)
        self.assertIsNotNone(box)
        self.assertAlmostEqual(box.u1 - box.u0, 10.0)      # 厚度沿管轴
        self.assertAlmostEqual(box.v1 - box.v0, 200.0)     # 竖直板
        self.assertAlmostEqual(box.z1 - box.z0, 200.0)
        contact, gap = geom.flange_seat('C', od)
        flange_top = self.center[2] - contact
        # 钢板顶面低于翼缘端面一个 gap。
        self.assertAlmostEqual(box.z1, flange_top - gap, delta=1.0e-6)

    def test_flange_seat_gap_formula(self):
        # gap = 2 × (OD − sqrt(OD² − (b/2)²))，b = 型钢宽度 − 2×翼缘厚。
        import math
        for subitem, width, t2 in (('B', 100.0, 8.0), ('C', 150.0, 10.0)):
            od = self.od_by_subitem[subitem]
            base = width - 2.0 * t2
            contact, gap = geom.flange_seat(subitem, od)
            self.assertAlmostEqual(
                contact, math.sqrt((od / 2.0) ** 2 - (base / 2.0) ** 2))
            self.assertAlmostEqual(gap, 2.0 * (
                od - math.sqrt(od ** 2 - (base / 2.0) ** 2)))
            # gap 应 ≈ 管底到翼缘端面的高度（钢板顶面 ≈ 管底，不扎进管子）。
            sagitta = od / 2.0 - math.sqrt(
                (od / 2.0) ** 2 - (base / 2.0) ** 2)
            self.assertLessEqual(gap, sagitta + 1.0e-6)

    def test_a_has_no_gap(self):
        contact, gap = geom.flange_seat('A', self.od_by_subitem['A'])
        self.assertAlmostEqual(contact, self.od_by_subitem['A'] / 2.0)
        self.assertAlmostEqual(gap, 0.0)

    def test_no_plate_for_a(self):
        self.assertIsNone(geom.plate_box('A', 1, self.center, self.width,
                                         self.od_by_subitem['A']))


class LayoutTest(unittest.TestCase):
    def test_layout(self):
        layout = geom.build_layout(150)
        self.assertEqual(layout.subitem, 'B')
        self.assertEqual(layout.number, 'K1-B-150')
        self.assertEqual(layout.size_mm, 150.0)
        self.assertEqual(layout.plate, (150.0, 150.0, 10.0))
        items = geom.component_items(layout)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['quantity'], 2)

    def test_a_has_no_plate(self):
        layout = geom.build_layout(50)
        self.assertEqual(layout.subitem, 'A')
        self.assertIsNone(layout.plate)
        self.assertEqual(len(geom.component_items(layout)), 1)


if __name__ == '__main__':
    unittest.main()
