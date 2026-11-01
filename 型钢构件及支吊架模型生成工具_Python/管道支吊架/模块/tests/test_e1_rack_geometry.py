# -*- coding: utf-8 -*-
"""E1 管架（不保温管导向架）纯几何 / 数据逻辑单测（不依赖 Bentley 运行时）。

覆盖：DN↔OD、子项匹配、H 计算（注 2）、编号（注 3）、朝管面距离与不锈钢薄板
间隙、构件A 截面朝向（朝管面宽 = 50/50/100/100/150、右手系、竖直拉伸）、
薄板包围盒、构件清单。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_PLUGIN_DIR = os.path.dirname(_MODULE_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, 'E1管架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import E1管架_几何 as geom  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-6


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


class PipeTableTest(unittest.TestCase):
    def test_od_values(self):
        self.assertAlmostEqual(geom.od_mm(15), 21.3)
        self.assertAlmostEqual(geom.od_mm(65), 73.0)
        self.assertAlmostEqual(geom.od_mm(80), 88.9)
        self.assertAlmostEqual(geom.od_mm(900), 914.4)

    def test_match_dn(self):
        self.assertEqual(geom.match_dn(250.0), 250)   # 读取库给的是公称直径
        self.assertEqual(geom.match_dn(80.0), 80)
        self.assertEqual(geom.match_dn(88.9), 80)     # 也兼容外径
        self.assertEqual(geom.match_dn(219.1), 200)
        self.assertIsNone(geom.match_dn(1000.0))


class SubitemTest(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(geom.subitem_for_dn(15), 'A')
        self.assertEqual(geom.subitem_for_dn(65), 'A')
        self.assertEqual(geom.subitem_for_dn(80), 'B')
        self.assertEqual(geom.subitem_for_dn(150), 'B')
        self.assertEqual(geom.subitem_for_dn(200), 'C')
        self.assertEqual(geom.subitem_for_dn(300), 'C')
        self.assertEqual(geom.subitem_for_dn(350), 'D')
        self.assertEqual(geom.subitem_for_dn(600), 'D')
        self.assertEqual(geom.subitem_for_dn(650), 'E')
        self.assertEqual(geom.subitem_for_dn(900), 'E')

    def test_gap_uses_nearest(self):
        # 65~80 之间的空档取较近的一档。
        self.assertEqual(geom.subitem_for_dn(70), 'A')
        self.assertEqual(geom.subitem_for_dn(78), 'B')

    def test_face_widths(self):
        expected = {'A': 50.0, 'B': 50.0, 'C': 100.0, 'D': 100.0, 'E': 150.0}
        for key, width in expected.items():
            self.assertAlmostEqual(geom.get_subitem(key)['face_width'], width)


class HeightAndNumberTest(unittest.TestCase):
    def test_small_pipe_fixed_height(self):
        self.assertAlmostEqual(geom.height_mm('A', 21.3), 50.0)
        self.assertAlmostEqual(geom.height_mm('A', 73.0), 50.0)

    def test_large_pipe_height(self):
        # ≥3″：OD/2 + 50 圆整到 mm。
        self.assertEqual(geom.height_mm('B', 88.9), 94)   # 94.45 -> 94
        self.assertEqual(geom.height_mm('C', 323.8), 212)  # 211.9 -> 212
        self.assertEqual(geom.height_mm('E', 914.4), 507)  # 507.2 -> 507

    def test_number(self):
        self.assertEqual(geom.build_number('A', 50), 'E1-A-50')
        self.assertEqual(geom.build_number('D', 355.6), 'E1-D-356')
        self.assertEqual(geom.build_number('B', 94, stainless=True), 'E1-B-94-S')
        self.assertTrue(geom.is_stainless_marked('E1-B-94-S'))
        self.assertFalse(geom.is_stainless_marked('E1-B-94'))


class FaceDistanceTest(unittest.TestCase):
    def test_carbon_steel(self):
        self.assertAlmostEqual(geom.face_distance_mm(88.9), 88.9 / 2.0 + 3.0)

    def test_stainless_adds_liner(self):
        thickness = geom.get_subitem('C')['liner'][2]
        self.assertAlmostEqual(
            geom.face_distance_mm(323.8, True, 'C'),
            323.8 / 2.0 + 3.0 + thickness)


class LayoutTest(unittest.TestCase):
    def test_carbon_layout(self):
        layout = geom.build_layout(200)
        self.assertEqual(layout.subitem, 'C')
        self.assertAlmostEqual(layout.height_mm, 160.0)
        self.assertEqual(layout.number, 'E1-C-160')
        self.assertIsNone(layout.liner)
        self.assertAlmostEqual(layout.allowable_load_kn, 6.0)

    def test_stainless_layout(self):
        layout = geom.build_layout(80, stainless=True)
        self.assertEqual(layout.subitem, 'B')
        self.assertEqual(layout.number, 'E1-B-94-S')
        self.assertEqual(layout.liner['thickness_mm'], 2.0)


class MemberOrientationTest(unittest.TestCase):
    """构件A 截面朝向：朝管面宽沿管轴、其余背离管道、右手系竖直拉伸。"""

    def _world_points(self, subitem, side):
        center = (1000.0, 0.0, 500.0)
        face = 123.0
        base_z = 300.0
        samples = geom.sample_member(subitem, side, center, face, base_z, 100.0)
        points = [point for segment in samples for point in segment]
        return points

    def test_face_width_and_min_y(self):
        for subitem in geom.subitem_choices():
            width = geom.get_subitem(subitem)['face_width']
            for side in (1, -1):
                points = self._world_points(subitem, side)
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                self.assertAlmostEqual(max(xs) - min(xs), width, delta=1.0e-3,
                                       msg='%s/%+d 朝管面宽' % (subitem, side))
                if side > 0:
                    self.assertAlmostEqual(min(ys), 123.0, delta=1.0e-3,
                                           msg='%s 内侧距管轴' % subitem)
                    self.assertGreaterEqual(max(ys), 123.0 - 1.0e-6)
                else:
                    self.assertAlmostEqual(max(ys), -123.0, delta=1.0e-3,
                                           msg='%s 内侧距管轴' % subitem)
                    self.assertLessEqual(min(ys), -123.0 + 1.0e-6)

    def test_frame_right_handed_and_vertical(self):
        for subitem in geom.subitem_choices():
            for side in (1, -1):
                origin, ax, ay, az = geom.member_frame(
                    subitem, side, (0.0, 0.0, 0.0), 100.0, 0.0, 150.0)
                self.assertAlmostEqual(abs(az[2]), 1.0)
                cross = _cross(ax, ay)
                self.assertAlmostEqual(cross[0], az[0], delta=TOL)
                self.assertAlmostEqual(cross[1], az[1], delta=TOL)
                self.assertAlmostEqual(cross[2], az[2], delta=TOL)

    def test_members_are_mirror_not_rotation(self):
        # 角钢两侧构件应镜像：沿管轴特征同向（axis_x 相同），背离方向相反。
        center = (0.0, 0.0, 0.0)
        _o1, ax1, ay1, _z1 = geom.member_frame(
            'B', 1, center, 100.0, 0.0, 150.0)
        _o2, ax2, ay2, _z2 = geom.member_frame(
            'B', -1, center, 100.0, 0.0, 150.0)
        for index in range(3):
            self.assertAlmostEqual(ax1[index], ax2[index], delta=TOL)
            self.assertAlmostEqual(ay1[index], -ay2[index], delta=TOL)

    def test_profile_closed(self):
        for subitem in geom.subitem_choices():
            geometry = geom.member_geometry(subitem)
            self.assertTrue(geometry.is_closed_and_continuous())

    def test_rotated_pipe_direction(self):
        # 管轴沿世界 +Y 时，背离方向 = Z×Y = -X。
        pipe_dir = (0.0, 1.0, 0.0)
        away_dir = (-1.0, 0.0, 0.0)
        center = (500.0, 800.0, 400.0)
        face = 90.0
        for subitem in geom.subitem_choices():
            width = geom.get_subitem(subitem)['face_width']
            samples = geom.sample_member(
                subitem, 1, center, face, 300.0, 150.0, 1.0, pipe_dir, away_dir)
            points = [p for segment in samples for p in segment]
            us = [p[1] - center[1] for p in points]      # 沿 +Y
            vs = [center[0] - p[0] for p in points]      # 沿 -X（away_dir）
            self.assertAlmostEqual(max(us) - min(us), width, delta=1.0e-3)
            self.assertAlmostEqual(min(vs), face, delta=1.0e-3)


class LinerTest(unittest.TestCase):
    def test_liner_between_pipe_and_member(self):
        subitem = 'D'
        od = 406.4
        face = geom.face_distance_mm(od, True, subitem)
        base_z = 100.0
        height = geom.height_mm(subitem, od)
        axis_z = base_z + od / 2.0
        box = geom.liner_box(subitem, 1, od, axis_z, base_z, height)
        thickness = geom.get_subitem(subitem)['liner'][2]
        self.assertAlmostEqual(box.v0, od / 2.0 + 3.0)
        self.assertAlmostEqual(box.v1, face)
        self.assertAlmostEqual(box.v1 - box.v0, thickness)
        self.assertGreaterEqual(box.z0, base_z - 1.0e-9)
        self.assertLessEqual(box.z1, base_z + height + 1.0e-9)

    def test_liner_mirrored(self):
        box = geom.liner_box('B', -1, 88.9, 60.0, 10.0,
                             geom.height_mm('B', 88.9))
        self.assertLessEqual(box.v1, 0.0)
        self.assertAlmostEqual(box.v1, -(88.9 / 2.0 + 3.0))


class ComponentItemsTest(unittest.TestCase):
    def test_carbon(self):
        items = geom.component_items(geom.build_layout(100))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['quantity'], 2)
        self.assertEqual(items[0]['name'], '构件A')

    def test_stainless(self):
        items = geom.component_items(geom.build_layout(100, stainless=True))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]['name'], '不锈钢薄板')
        self.assertEqual(items[1]['quantity'], 2)


if __name__ == '__main__':
    unittest.main()
