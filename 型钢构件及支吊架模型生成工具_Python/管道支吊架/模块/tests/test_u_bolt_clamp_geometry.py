# -*- coding: utf-8 -*-
"""A1 U 型管卡（U 形螺栓管夹）纯数据 / 几何推导单测（不依赖 Bentley 运行时）。

覆盖：表 1 全表尺寸与自洽性（``C = B + d``）、表 2 / 表 3、DN 匹配、弯弧与直腿
的相切几何、每腿两颗螺母的位置、扫掠路径与角度档位、摆放坐标架（水平管 /
竖直管 / 斜管）、编号与清单文字。
"""

from __future__ import division

import math
import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, 'U型管卡')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

import U型管卡_几何 as geom  # noqa: E402


class TableTests(unittest.TestCase):
    def test_dn_range(self):
        self.assertEqual(geom.table_dns(),
                         [15, 20, 25, 32, 40, 50, 65, 80, 90, 100, 125, 150,
                          200, 250, 300, 350, 400, 450, 500, 550, 600, 650,
                          700, 750, 800, 850, 900])

    def test_table_is_self_consistent(self):
        self.assertEqual(geom.check_table(), [])

    def test_dn100_row(self):
        """DN100 表值：B=120、C=132、D=115、E=80、螺栓 M12。"""
        row = geom.get_row(100)
        self.assertEqual(row['nps'], '4"')
        self.assertEqual(row['bolt'], 'M12')
        self.assertEqual((row['B'], row['C'], row['D'], row['E']),
                         (120, 132, 115, 80))

    def test_bolt_diameter(self):
        self.assertAlmostEqual(geom.bolt_diameter('M12'), 12.0)
        self.assertAlmostEqual(geom.bolt_diameter('M6'), 6.0)
        self.assertAlmostEqual(geom.bolt_diameter('M24'), 24.0)

    def test_bolt_by_dn_groups(self):
        expected = {15: 'M6', 25: 'M6', 32: 'M10', 50: 'M10', 65: 'M12',
                    125: 'M12', 150: 'M16', 200: 'M16', 250: 'M20',
                    400: 'M20', 450: 'M24', 900: 'M24'}
        for dn, bolt in expected.items():
            self.assertEqual(geom.get_row(dn)['bolt'], bolt, 'DN%d' % dn)

    def test_loads(self):
        row = geom.get_row(100)
        self.assertAlmostEqual(row['load_axial'], 12.0)
        self.assertAlmostEqual(row['load_lateral'], 3.0)
        # 450 以上原表横向为「—」。
        self.assertIsNone(geom.get_row(450)['load_lateral'])

    def test_unknown_dn_rejected(self):
        with self.assertRaises(ValueError):
            geom.get_row(123)

    def test_dn_choices(self):
        choices = geom.dn_choices()
        self.assertEqual(len(choices), len(geom.TABLE))
        self.assertEqual(choices[0][0], 15)
        self.assertIn('4"', dict(choices)[100])

    def test_materials(self):
        self.assertEqual(geom.MATERIALS['C1']['bolt_material'], 'Q235B或20')
        self.assertEqual(geom.MATERIALS['S']['bolt_material'], '06Cr19Ni10')
        self.assertEqual(geom.MATERIALS['S1']['temperature'], '≤120')

    def test_correction_factors(self):
        self.assertAlmostEqual(geom.CORRECTION_FACTORS['200']['C1'], 0.94)
        self.assertAlmostEqual(geom.CORRECTION_FACTORS['300']['S'], 0.85)
        self.assertAlmostEqual(geom.CORRECTION_FACTORS['≤150']['S'], 1.03)


class MatchTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(geom.match_table_dn(100), 100)
        self.assertEqual(geom.match_table_dn(100.0), 100)

    def test_near_match(self):
        self.assertEqual(geom.match_table_dn(98.0), 100)
        self.assertEqual(geom.match_table_dn(102.5), 100)

    def test_far_value_returns_none(self):
        """超出「就近匹配 + max(5, 15%)」容差的公称直径返回 None。"""
        self.assertIsNone(geom.match_table_dn(3000.0))
        self.assertIsNone(geom.match_table_dn(None))
        self.assertIsNone(geom.match_table_dn('abc'))
        self.assertIsNone(geom.match_table_dn(0))
        # 1000 距 900 只有 100（< 15%×900=135），仍算命中 900。
        self.assertEqual(geom.match_table_dn(1000.0), 900)


class GeometryTests(unittest.TestCase):
    def test_dn100_geometry(self):
        g = geom.build_geometry(100)
        self.assertAlmostEqual(g.r_leg, 66.0)          # C/2 = 132/2
        self.assertAlmostEqual(g.leg_tip_y, 115.0)     # D
        # 弯弧圆心固定在管轴上 → 相切点 = 弯弧起点 = 0。
        self.assertAlmostEqual(g.arc_center_y, 0.0)
        self.assertAlmostEqual(g.bend_start_y, 0.0)
        self.assertAlmostEqual(g.arc_bottom_y, -66.0)  # 0 − C/2
        self.assertAlmostEqual(g.d, 12.0)
        # 直腿段 = 腿端 → 弯弧起点 = D。
        self.assertAlmostEqual(g.straight_mm, 115.0)
        # 表 1 的 E 列只作参考。
        self.assertAlmostEqual(g.table_straight_mm, 80.0)
        self.assertAlmostEqual(g.leg_center_offset, 35.0)   # D − E

    def test_arc_center_always_on_pipe_axis(self):
        """弧心必须落在管轴上（否则弯弧会吃进管子里）。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            self.assertAlmostEqual(g.arc_center_y,
                                   geom.ARC_CENTER_ON_AXIS_MM, places=9,
                                   msg='DN%d' % dn)
            self.assertAlmostEqual(g.bend_start_y, g.arc_center_y, places=9)
            self.assertAlmostEqual(g.arc_bottom_y, g.arc_center_y - g.r_leg,
                                   places=9)

    def test_straight_leg_equals_d(self):
        """弧心在管轴上时，直腿段长 = 腿端 = D（逐行）。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            self.assertAlmostEqual(g.leg_tip_y - g.bend_start_y, g.straight_mm,
                                   places=9, msg='DN%d' % dn)
            self.assertAlmostEqual(g.straight_mm, g.tip_mm, places=9,
                                   msg='DN%d' % dn)

    def test_arc_hugs_pipe_for_every_diameter(self):
        """**回归测试**：全表弯弧都必须包在管子外面（早期口径 21/27 档穿管）。

        判据：弯弧处螺栓**内表面**半径（= C/2 − d/2 = B/2）必须大于管外半径。
        修正前 DN100 内表面只到 37.0 而管外半径 57.15 → 侵入 20.1 mm。
        """
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            clearance = g.pipe_clearance_mm()
            self.assertIsNotNone(clearance, 'DN%d 缺管外径' % dn)
            self.assertGreater(clearance, 0.0,
                               'DN%d 弯弧侵入管道 %.1f mm'
                               % (dn, -clearance))
            self.assertTrue(g.arc_hugs_pipe(), 'DN%d' % dn)
            # 内表面半径必须正好等于 B/2，净空落在 1.5~4 mm 这个量级。
            self.assertAlmostEqual(g.inner_face_radius, g.inner_mm / 2.0,
                                   places=9, msg='DN%d' % dn)
            self.assertGreater(clearance, 1.5, 'DN%d 净空偏小' % dn)
            self.assertLess(clearance, 4.0, 'DN%d 净空偏大' % dn)

    def test_pipe_clearance_unknown_dn(self):
        """表里没有该 DN 的管外径时净空返回 None（不报假数）。"""
        table = dict(geom.PIPE_OUTSIDE_DIAMETERS)
        try:
            del geom.PIPE_OUTSIDE_DIAMETERS[100]
            g = geom.build_geometry(100)
            self.assertIsNone(g.pipe_clearance_mm())
            self.assertIsNone(g.arc_hugs_pipe())
        finally:
            geom.PIPE_OUTSIDE_DIAMETERS.clear()
            geom.PIPE_OUTSIDE_DIAMETERS.update(table)

    def test_no_warnings_for_whole_table(self):
        """全表都不该出现净空 / 螺母相关的告警。"""
        for dn in geom.table_dns():
            self.assertEqual(geom.build_geometry(dn).warnings(), [],
                             'DN%d' % dn)

    def test_arc_tangent_to_legs(self):
        """弯弧半径 = C/2，圆心在管轴上，起末两点为 ±C/2 处的切点。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            path = g.sweep_path()
            (center_y, center_z), radius, start_angle, sweep_angle = path['arc']
            self.assertAlmostEqual(radius, g.r_leg, places=9, msg='DN%d' % dn)
            self.assertAlmostEqual(center_y, g.arc_center_y, places=9)
            self.assertAlmostEqual(center_z, 0.0, places=9)
            self.assertAlmostEqual(start_angle % 360.0, 90.0, places=9)
            self.assertAlmostEqual(sweep_angle, 180.0, places=9)
            # 路径首末点：两条腿的腿端。
            self.assertAlmostEqual(path['start'][1], g.r_leg, places=9)
            self.assertAlmostEqual(path['start'][0], g.leg_tip_y, places=9)
            self.assertAlmostEqual(path['end'][1], -g.r_leg, places=9)
            self.assertAlmostEqual(path['end'][0], g.leg_tip_y, places=9)
            # 相切点必须在直腿段上（在腿端与弯弧起点之间或恰在起点）。
            self.assertAlmostEqual(path['leg_end'][0], g.bend_start_y, places=9)
            self.assertGreaterEqual(path['leg_end'][0], g.arc_center_y - 1e-9)

    def test_two_nuts_per_leg(self):
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            self.assertEqual(len(g.nuts), 2, 'DN%d' % dn)
            self.assertEqual(len(g.nut_positions()), 4, 'DN%d' % dn)
            first, second = g.nuts[0], g.nuts[1]
            self.assertAlmostEqual(first[2] - first[1], g.nut_height, places=9)
            self.assertAlmostEqual(second[2] - second[1], g.nut_height, places=9)
            # 第二颗紧贴第一颗之上。
            self.assertAlmostEqual(second[1] - first[2], geom.NUT_GAP_MM, places=9)

    def test_nut_center_offset_from_leg_tip(self):
        """**甲方口径**：螺母中心距腿端 = ``(D − 管道半径) / 2``（逐行）。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            expected = (g.tip_mm - g.pipe_od_mm / 2.0) / 2.0
            self.assertAlmostEqual(g.nut_end_offset_mm(), expected, places=9,
                                   msg='DN%d' % dn)
            self.assertAlmostEqual(g.leg_tip_y - g.nut_center_y, expected,
                                   places=9, msg='DN%d' % dn)
            # 两颗螺母以该中心对称、相贴。
            first, second = g.nuts[0], g.nuts[1]
            self.assertAlmostEqual(
                (first[1] + second[2]) / 2.0, g.nut_center_y, places=9,
                msg='DN%d' % dn)
            self.assertAlmostEqual(g.nut_center_y - first[1],
                                   second[2] - g.nut_center_y, places=9)

    def test_nut_offset_fallback_without_pipe_od(self):
        """管外径查不到时，螺母中心到腿端退回兜底值（不报假数、仍能建模）。"""
        table = dict(geom.PIPE_OUTSIDE_DIAMETERS)
        try:
            del geom.PIPE_OUTSIDE_DIAMETERS[100]
            g = geom.build_geometry(100)
            self.assertAlmostEqual(g.nut_end_offset_mm(),
                                   geom.BOLT_TIP_EXTRA_MM, places=9)
        finally:
            geom.PIPE_OUTSIDE_DIAMETERS.clear()
            geom.PIPE_OUTSIDE_DIAMETERS.update(table)

    def test_nut_inside_straight_leg_for_all_diameters(self):
        """表 1 全表：两颗螺母都必须落在直腿段内（不压进弯弧、不超出腿端）。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            self.assertGreater(g.nut_clearance_mm(), 0.0, 'DN%d' % dn)
            self.assertGreater(g.nuts[0][1], g.bend_start_y, 'DN%d' % dn)
            self.assertLessEqual(g.nuts[1][2], g.leg_tip_y, 'DN%d' % dn)
            # 腿端还要留出至少一颗螺母高的丝头。
            self.assertGreaterEqual(g.leg_tip_y - g.nuts[1][2], 1.0,
                                    'DN%d 腿端余量不足' % dn)
            self.assertNotIn('过短', ''.join(g.warnings()), 'DN%d' % dn)

    def test_nut_across_flats_and_hole(self):
        g = geom.build_geometry(100)
        self.assertAlmostEqual(g.nut_across_flats, 18.0)
        self.assertAlmostEqual(g.nut_height, 9.6)
        # 螺母中心孔半径 = (d + 2×单边间隙) / 2 = (12 + 2) / 2 = 7。
        self.assertAlmostEqual(g.hole_radius, 7.0)

    def test_height_covers_whole_group(self):
        g = geom.build_geometry(100)
        self.assertAlmostEqual(g.height_mm, g.nut_top_y - g.arc_bottom_y)
        # 螺母组现在落在腿端以下（甲方口径），总高仍覆盖"螺母顶 → 弯弧最低点"。
        self.assertLess(g.nut_top_y, g.leg_tip_y)
        self.assertGreater(g.nut_top_y, g.arc_bottom_y)

    def test_outer_span_matches_table(self):
        """两腿外缘 = C + d；由 ``C = B + d`` 得 ``= B + 2d``（DN15 见下）。"""
        for dn in geom.table_dns():
            g = geom.build_geometry(dn)
            self.assertGreater(g.outer_span_mm, g.span_mm, 'DN%d' % dn)
            self.assertAlmostEqual(g.outer_span_mm, g.center_mm + g.d,
                                   msg='DN%d' % dn)
            self.assertAlmostEqual(g.outer_span_mm, g.inner_mm + 2.0 * g.d,
                                   msg='DN%d' % dn)

    def test_dn15_center_distance_corrected(self):
        """DN15：原图 C=27 与 B=25 / M6 不自洽，本表按 B + d 修正为 31。"""
        g = geom.build_geometry(15)
        self.assertEqual(g.inner_mm, 25.0)
        self.assertEqual(g.center_mm, 31.0)
        self.assertAlmostEqual(g.center_mm, g.inner_mm + g.d)
        self.assertIn(15, geom.KNOWN_TABLE_ISSUES)

    def test_angle_choices(self):
        angles = [angle for angle, _label in geom.angle_choices()]
        self.assertEqual(angles, list(geom.ANGLE_STEPS_DEG))
        self.assertIn(0.0, angles)
        labels = dict(geom.angle_choices())
        self.assertIn('开口朝上', labels[0.0])

    def test_normalize_angle(self):
        self.assertAlmostEqual(geom.normalize_angle(0), 0.0)
        self.assertAlmostEqual(geom.normalize_angle(360), 0.0)
        self.assertAlmostEqual(geom.normalize_angle(-90), 270.0)
        self.assertAlmostEqual(geom.normalize_angle(450), 90.0)
        with self.assertRaises(ValueError):
            geom.normalize_angle('abc')
        with self.assertRaises(ValueError):
            geom.normalize_angle(float('nan'))


class FrameTests(unittest.TestCase):
    def _dot(self, a, b):
        return sum(x * y for x, y in zip(a, b))

    def test_horizontal_pipe_default_opens_up(self):
        """水平管（+X）默认开口朝上：ey = 世界 +Z。"""
        frame = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        ex, ey, ez = frame
        self.assertAlmostEqual(ex[0], 1.0)
        self.assertAlmostEqual(ey[2], 1.0)
        self.assertAlmostEqual(self._dot(ex, ey), 0.0, places=9)

    def test_horizontal_pipe_along_y(self):
        frame = geom.placement_frame((0.0, 1.0, 0.0), 0.0)
        ex, ey, ez = frame
        self.assertAlmostEqual(ey[2], 1.0)
        self.assertAlmostEqual(self._dot(ex, ey), 0.0, places=9)
        self.assertAlmostEqual(self._dot(ex, ez), 0.0, places=9)

    def test_angle_rotates_about_pipe_axis(self):
        """90° 时开口方向 = 绕管轴右手旋转 90° 后的方向，且仍垂直于管轴。"""
        frame0 = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame90 = geom.placement_frame((1.0, 0.0, 0.0), 90.0)
        ex0, ey0, ez0 = frame0
        ex90, ey90, ez90 = frame90
        self.assertAlmostEqual(ex90[0], 1.0)
        # 绕 +X 右手旋转 90°：(0,0,1) -> (0,-1,0)。
        self.assertAlmostEqual(ey90[1], -1.0, places=9)
        self.assertAlmostEqual(self._dot(ex90, ey90), 0.0, places=9)
        self.assertAlmostEqual(self._dot(ey90, ez90), 0.0, places=9)
        self.assertAlmostEqual(self._dot(ex90, ez90), 0.0, places=9)

    def test_vertical_pipe_falls_back_to_world_x(self):
        """竖直管：世界 +Z 无法作基准，开口基准退回世界 +X，且角度可调。"""
        frame = geom.placement_frame((0.0, 0.0, 1.0), 0.0)
        ex, ey, ez = frame
        self.assertAlmostEqual(abs(ex[2]), 1.0)
        self.assertAlmostEqual(abs(ey[0]), 1.0)
        self.assertAlmostEqual(self._dot(ex, ey), 0.0, places=9)
        frame90 = geom.placement_frame((0.0, 0.0, 1.0), 90.0)
        self.assertAlmostEqual(self._dot(frame90[1], frame90[0]), 0.0, places=9)

    def test_sloped_pipe_frame_is_orthonormal(self):
        frame = geom.placement_frame((0.5, 0.5, 0.7071067811865476), 30.0)
        ex, ey, ez = frame
        for vector in (ex, ey, ez):
            self.assertAlmostEqual(math.sqrt(sum(c * c for c in vector)), 1.0,
                                   places=9)
        self.assertAlmostEqual(self._dot(ex, ey), 0.0, places=9)
        self.assertAlmostEqual(self._dot(ex, ez), 0.0, places=9)
        self.assertAlmostEqual(self._dot(ey, ez), 0.0, places=9)

    def test_zero_axis_rejected(self):
        self.assertIsNone(geom.placement_frame((0.0, 0.0, 0.0), 0.0))

    def test_local_to_world(self):
        frame = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        world = geom.local_to_world((10.0, 20.0, 30.0), frame, 0.0, 5.0, 0.0)
        # ey = +Z：世界 z 增加 5。
        self.assertAlmostEqual(world[0], 10.0)
        self.assertAlmostEqual(world[1], 20.0)
        self.assertAlmostEqual(world[2], 35.0)


class TextTests(unittest.TestCase):
    def test_assembly_tag(self):
        self.assertEqual(geom.assembly_tag(100, 'M12', 0), 'A1-DN100-M12-0°')
        self.assertEqual(geom.assembly_tag(150, 'M16', 90), 'A1-DN150-M16-90°')

    def test_bom_items(self):
        g = geom.build_geometry(100)
        items = geom.bom_items(g)
        codes = [item['code'] for item in items]
        self.assertEqual(codes, ['U_BOLT', 'NUT'])
        self.assertEqual(items[0]['quantity'], 1)
        self.assertEqual(items[1]['quantity'], 4)
        self.assertIn('M12', items[0]['specification'])

    def test_describe_text(self):
        g = geom.build_geometry(100)
        text = geom.describe(g, 0.0)
        for fragment in ('DN100', 'M12', '两腿中心距', '开口朝上', '螺母'):
            self.assertIn(fragment, text)

    def test_corrected_load(self):
        g = geom.build_geometry(100)
        axial, lateral, factor = geom.corrected_load(g, 'C1', '200')
        self.assertAlmostEqual(factor, 0.94)
        self.assertAlmostEqual(axial, 12.0 * 0.94)
        self.assertAlmostEqual(lateral, 3.0 * 0.94)
        with self.assertRaises(ValueError):
            geom.corrected_load(g, 'C1', '999')
        with self.assertRaises(ValueError):
            geom.corrected_load(g, 'S1', '200')


if __name__ == '__main__':
    unittest.main(verbosity=2)
