# -*- coding: utf-8 -*-
"""``水平T形架_几何`` 的纯计算单测（不依赖 Bentley 运行时）。

覆盖五个路径点、两个类型的偏心算法、构件选型、编号、允许荷载与上限、
以及扫掠坐标架必须保持右手系。

运行：
    python -m unittest test_horizontal_t_frame_geometry
"""

from __future__ import division

import os
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_PLUGIN_DIR = os.path.dirname(_MODULE_DIR)
_REPO_ROOT = os.path.dirname(_PLUGIN_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, '水平T形架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 水平T形架_几何 as geom  # noqa: E402


def make_line(length=1000.0, base=(0.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0)):
    top = tuple(base[index] + direction[index] * length for index in range(3))
    return geom.parse_selected_line([[base, top]])


class ParseLineTests(unittest.TestCase):
    def test_accepts_horizontal_line(self):
        line = make_line(1000.0)
        self.assertAlmostEqual(line.length_mm, 1000.0, places=9)
        self.assertEqual(line.base, (0.0, 0.0, 0.0))

    def test_rejects_vertical_line(self):
        with self.assertRaises(ValueError):
            make_line(1000.0, direction=(0.0, 0.0, 1.0))

    def test_rejects_sloped_line(self):
        with self.assertRaises(ValueError):
            make_line(1000.0, direction=(1.0, 0.0, 0.5))

    def test_accepts_slight_tilt_within_tolerance(self):
        line = make_line(1000.0, direction=(1.0, 0.0, 0.05))
        self.assertGreater(line.length_mm, 1000.0)

    def test_rejects_short_line(self):
        with self.assertRaises(ValueError):
            make_line(100.0)

    def test_rejects_multi_segment(self):
        with self.assertRaises(ValueError):
            geom.parse_selected_line(
                [[(0.0, 0.0, 0.0), (500.0, 0.0, 0.0)],
                 [(500.0, 0.0, 0.0), (1000.0, 0.0, 0.0)]])


class PathPointTests(unittest.TestCase):
    """工况：辅助线 (0,0,0) -> (1000,0,0)。"""

    def setUp(self):
        self.line = make_line(1000.0)

    def test_variant_a_known_coordinates(self):
        """子项A：tb=6、wA/2=25 —— 与图纸口径核对过的基准值。"""
        points = geom.path_points(self.line, 'A', 1, 250.0)
        self.assertAlmostEqual(points['tb_mm'], 6.0, places=9)
        self.assertAlmostEqual(points['l1_mm'], 994.0, places=9)
        self.assertEqual(points['p0'], (0.0, 0.0, 0.0))
        self.assertEqual(points['p1'], (1000.0, 0.0, 0.0))
        self.assertEqual(points['p2'], (994.0, 0.0, 0.0))

    def test_type_one_is_symmetric_about_a_centroid(self):
        points = geom.path_points(self.line, 'A', 1, 250.0)
        self.assertEqual(points['p3'], (994.0, -125.0, 0.0))
        self.assertEqual(points['p4'], (994.0, 125.0, 0.0))
        self.assertAlmostEqual(points['offset_mm'], 0.0, places=9)

    def test_type_two_known_coordinates(self):
        """类型2：P3 = P2 − (wA/2 + 15)·v，P4 = P3 + L2·v。

        子项A：25 + 15 = 40 -> P3.y = -40、P4.y = -40 + 250 = 210。
        """
        points = geom.path_points(self.line, 'A', 2, 250.0)
        self.assertEqual(points['p3'], (994.0, -40.0, 0.0))
        self.assertEqual(points['p4'], (994.0, 210.0, 0.0))
        self.assertAlmostEqual(points['offset_mm'], 40.0, places=9)

    def test_arm_span_always_equals_l2(self):
        """两种类型的 |P3P4| 都必须等于 L2。"""
        for rack_type in geom.ALL_RACK_TYPES:
            for key in sorted(geom.VARIANTS):
                for l2 in (50.0, 250.0, 500.0):
                    points = geom.path_points(self.line, key, rack_type, l2)
                    span = _distance(points['p3'], points['p4'])
                    self.assertAlmostEqual(span, l2, places=6,
                                           msg='%s type=%d L2=%g'
                                           % (key, rack_type, l2))

    def test_type_two_bottom_offset_is_half_width_plus_15(self):
        for key in sorted(geom.VARIANTS):
            points = geom.path_points(self.line, key, 2, 250.0)
            expected = geom.member_half_width(key, 'post') + 15.0
            self.assertAlmostEqual(points['offset_mm'], expected, places=9,
                                   msg='%s' % key)

    def test_b_path_is_perpendicular_to_the_auxiliary_line(self):
        for rack_type in geom.ALL_RACK_TYPES:
            points = geom.path_points(self.line, 'C', rack_type, 250.0)
            delta = _sub(points['p4'], points['p3'])
            self.assertAlmostEqual(_dot(delta, points['u_dir']), 0.0, places=6)

    def test_l2_below_minimum_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.path_points(self.line, 'A', 1, 10.0)

    def test_line_shorter_than_tb_is_rejected(self):
        """辅助线短到扣掉 tb 后构件A 长度为负时必须拒绝。

        ``parse_selected_line`` 的最小线长是 150 mm，所以用直接构造的
        ``SelectedLine`` 覆盖这个边界。
        """
        line = geom.SelectedLine(base=(0.0, 0.0, 0.0), top=(5.0, 0.0, 0.0),
                                 length_mm=5.0, direction=(1.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            geom.path_points(line, 'E', 1, 250.0)


    def test_fit_offset_values(self):
        """构件B 的贴合偏移 ``(u, v, w)``。

        角钢：u = −(翼缘/2 − 10)、w = +肢厚；
        槽钢：u = −翼缘/2 + 腹板厚 ``tw``（从半宽里扣掉腹板厚）；两者 v 均为 0。
        """
        expected = {
            'A': (-15.0, 0.0, 6.0),
            'B': (-27.5, 0.0, 7.0),
            'C': (-23.0, 0.0, 0.0),   # -58/2 + tw 6.0
            'D': (-23.0, 0.0, 0.0),   # -58/2 + tw 6.0
            'E': (-29.5, 0.0, 0.0),   # -73/2 + tw 7.0
        }
        for key, value in expected.items():
            got = geom.member_fit_offset(key, 'arm')
            self.assertEqual(len(got), 3, msg=key)
            for index, part in enumerate(value):
                self.assertAlmostEqual(got[index], part, places=9,
                                       msg='%s 分量%d' % (key, index))

    def test_hbeam_needs_no_offset(self):
        """工字钢 / H 型钢是对称截面，规则表里必须是 symmetric（不偏移）。"""
        self.assertEqual(geom._FIT_OFFSET_RULES.get('hot_rolled_h'),
                         ('symmetric',))
        self.assertEqual(geom._FIT_OFFSET_RULES.get('ordinary_ibeam'),
                         ('symmetric',))
        self.assertEqual(geom._FIT_OFFSET_RULES['equal_angle'],
                         ('clearance', geom.B_FIT_CLEARANCE_MM))
        self.assertEqual(geom._FIT_OFFSET_RULES['parallel_channel'],
                         ('half_width',))

    def test_angle_fit_offset_w_aligns_member_b_edge_with_member_a_face(self):
        """角钢：施加 w 偏移后，构件B 的下边必须正好落在构件A 的内侧肢面上。"""
        for key in ('A', 'B'):
            section = geom.section_dimensions(key, 'post')
            face = -(float(section['B']) / 2.0 - float(section['t']))
            half = geom.member_width(key, 'arm') / 2.0
            _fit_u, _fit_v, fit_w = geom.member_fit_offset(key, 'arm')
            self.assertAlmostEqual(fit_w - half, face, places=9, msg=key)

    def test_channel_fit_offset_releases_the_web_thickness(self):
        """槽钢：u 偏移 = −翼缘/2 + 腹板厚，即从半宽里扣掉一个腹板厚。"""
        for key in ('C', 'D', 'E'):
            fit_u, _fit_v, fit_w = geom.member_fit_offset(key, 'arm')
            half = geom.member_width(key, 'arm') / 2.0
            web = geom.member_web_thickness(key, 'arm')
            self.assertAlmostEqual(fit_u, -half + web, places=9, msg=key)
            self.assertAlmostEqual(fit_w, 0.0, places=9, msg=key)
            # 与「只让半宽」相比，偏移量减少的正好是腹板厚。
            self.assertAlmostEqual(fit_u + half, web, places=9, msg=key)

    def test_fit_offset_is_reported_in_path_points(self):
        line = make_line(1000.0)
        for key in sorted(geom.VARIANTS):
            points = geom.path_points(line, key, 1, 250.0)
            self.assertEqual(
                (points['fit_u_mm'], points['fit_v_mm'], points['fit_w_mm']),
                geom.member_fit_offset(key, 'arm'), msg=key)

    def test_member_b_placement_applies_the_offset(self):
        """member_placement 必须把偏移作用到构件B 的起点上（辅助线沿 +X）。"""
        line = make_line(1000.0)
        for key in sorted(geom.VARIANTS):
            points = geom.path_points(line, key, 1, 250.0)
            origin, _ax, _ay, _az, _length = geom.member_placement(
                key, 'arm', points, 1.0)
            self.assertAlmostEqual(
                origin[0], points['p3'][0] + points['fit_u_mm'], places=9,
                msg='%s u' % key)
            self.assertAlmostEqual(
                origin[1], points['p3'][1] + points['fit_v_mm'], places=9,
                msg='%s v' % key)
            self.assertAlmostEqual(
                origin[2], points['p3'][2] + points['fit_w_mm'], places=9,
                msg='%s w' % key)

    def test_member_a_placement_is_not_offset(self):
        line = make_line(1000.0)
        points = geom.path_points(line, 'A', 1, 250.0)
        origin, _ax, _ay, _az, length = geom.member_placement(
            'A', 'post', points, 1.0)
        self.assertEqual(origin, points['p0'])
        self.assertAlmostEqual(length, points['l1_mm'], places=9)


class FrameTests(unittest.TestCase):
    def test_frames_are_right_handed(self):
        """截面坐标架必须右手系，否则扫掠法向与路径相反。"""
        for key in sorted(geom.VARIANTS):
            for kind in ('post', 'arm'):
                ax, ay, az = geom.member_axes(key, kind)
                self.assertEqual(_cross(ax, ay), tuple(az),
                                 msg='%s %s' % (key, kind))

    def test_rotation_primitive_matches_bentley_convention(self):
        """旋转量约定：正角 = 沿轴看向原点时顺时针（与 rotate_frame(-a) 等价）。"""
        self.assertEqual(_round9(geom._rotate_about_axis((0.0, 0.0, 1.0),
                                                         (1.0, 0.0, 0.0), 90.0)),
                         (0.0, 1.0, 0.0))
        self.assertEqual(_round9(geom._rotate_about_axis((0.0, 0.0, 1.0),
                                                         (1.0, 0.0, 0.0), 180.0)),
                         (0.0, 0.0, -1.0))
        self.assertEqual(_round9(geom._rotate_about_axis((0.0, -1.0, 0.0),
                                                         (1.0, 0.0, 0.0), 90.0)),
                         (0.0, 0.0, 1.0))

    def test_rotation_keeps_frames_orthonormal(self):
        for key in sorted(geom.VARIANTS):
            for kind in ('post', 'arm'):
                for vector in geom.member_axes(key, kind):
                    self.assertAlmostEqual(_norm(vector), 1.0, places=9)

    def test_rotation_amounts_per_family(self):
        """构件A 与构件B：角钢 180°、槽钢 / 工字钢 / H 型钢 90°。"""
        expected = {'A': 180.0, 'B': 180.0, 'C': 90.0, 'D': 90.0, 'E': 90.0}
        for key, value in expected.items():
            self.assertAlmostEqual(geom.member_rotation_deg(key, 'post'), value,
                                   places=9, msg='%s 构件A' % key)
            self.assertAlmostEqual(geom.member_rotation_deg(key, 'arm'), value,
                                   places=9, msg='%s 构件B' % key)

    def test_member_a_axes_after_rotation(self):
        """构件A 旋转后的实际轴：角钢 x->-w、槽钢 / H 型钢 x->+v。"""
        for key in ('A', 'B'):
            axis_x, axis_y, axis_z = geom.member_axes(key, 'post')
            self.assertEqual(_round9(axis_x), (0.0, 0.0, -1.0), msg=key)
            self.assertEqual(_round9(axis_z), (1.0, 0.0, 0.0), msg=key)
        for key in ('C', 'D', 'E'):
            axis_x, axis_y, axis_z = geom.member_axes(key, 'post')
            self.assertEqual(_round9(axis_x), (0.0, 1.0, 0.0), msg=key)
            self.assertEqual(_round9(axis_z), (1.0, 0.0, 0.0), msg=key)

    def test_member_b_axes_after_rotation(self):
        """构件B 旋转后的实际轴：角钢 x->-w、槽钢 x->-u；z 恒为 +v。"""
        for key in ('A', 'B'):
            axis_x, axis_y, axis_z = geom.member_axes(key, 'arm')
            self.assertEqual(_round9(axis_x), (0.0, 0.0, -1.0), msg=key)
            self.assertEqual(_round9(axis_z), (0.0, 1.0, 0.0), msg=key)
        for key in ('C', 'D', 'E'):
            axis_x, axis_y, axis_z = geom.member_axes(key, 'arm')
            self.assertEqual(_round9(axis_x), (-1.0, 0.0, 0.0), msg=key)
            self.assertEqual(_round9(axis_z), (0.0, 1.0, 0.0), msg=key)

    def test_frame_axes_are_orthonormal(self):
        line = make_line(1000.0, base=(100.0, 200.0, 300.0),
                         direction=(1.0, 1.0, 0.0))
        u_dir, v_dir, w_dir = geom.frame_axes(line)
        for vector in (u_dir, v_dir, w_dir):
            self.assertAlmostEqual(_norm(vector), 1.0, places=9)
        self.assertAlmostEqual(_dot(u_dir, v_dir), 0.0, places=9)
        self.assertAlmostEqual(_dot(u_dir, w_dir), 0.0, places=9)
        self.assertEqual(w_dir, (0.0, 0.0, 1.0))


class VariantTests(unittest.TestCase):
    def test_variant_specifications_match_table_two(self):
        expected_a = {'A': '∠50×6', 'B': '∠75×7', 'C': '[10',
                      'D': 'H100×100×6×8', 'E': 'H150×150×7×10'}
        expected_b = {'A': '∠50×6', 'B': '∠75×7', 'C': '[14a',
                      'D': '[14a', 'E': '[20a'}
        for key, label in expected_a.items():
            self.assertEqual(geom.specification(key, 'post'), label,
                             msg='%s 构件A' % key)
        for key, label in expected_b.items():
            self.assertEqual(geom.specification(key, 'arm'), label,
                             msg='%s 构件B' % key)

    def test_hbeam_variants(self):
        self.assertFalse(geom.variant_is_hbeam('A'))
        self.assertFalse(geom.variant_is_hbeam('C'))
        self.assertTrue(geom.variant_is_hbeam('D'))
        self.assertTrue(geom.variant_is_hbeam('E'))

    def test_tb_is_web_or_leg_thickness(self):
        expected = {'A': 6.0, 'B': 7.0, 'C': 6.0, 'D': 6.0, 'E': 7.0}
        for key, value in expected.items():
            self.assertAlmostEqual(geom.member_web_thickness(key, 'arm'), value,
                                   places=9, msg='%s tb' % key)

    def test_half_width(self):
        expected = {'A': 25.0, 'B': 37.5, 'C': 24.0, 'D': 50.0, 'E': 75.0}
        for key, value in expected.items():
            self.assertAlmostEqual(geom.member_half_width(key, 'post'), value,
                                   places=9, msg='%s wA/2' % key)

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.specification('Z', 'post')
        with self.assertRaises(ValueError):
            geom.member_web_thickness('Z')


class LoadTableTests(unittest.TestCase):
    def test_table_one_values(self):
        expected = {
            ('A', 250): 0.3, ('A', 500): 0.15,
            ('B', 250): 1.0, ('C', 500): 1.0,
            ('D', 750): 2.5, ('E', 1000): 4.0,
        }
        for (key, l1), value in expected.items():
            self.assertAlmostEqual(geom.allowable_load(key, l1).value, value,
                                   places=9, msg='%s L1=%d' % (key, l1))

    def test_blank_cells_report_no_value(self):
        self.assertIsNone(geom.allowable_load('A', 750).value)
        self.assertIsNone(geom.allowable_load('B', 1000).value)
        self.assertIsNone(geom.allowable_load('D', 1000).value)

    def test_beyond_last_column_is_reported(self):
        result = geom.allowable_load('A', 1500.0)
        self.assertIsNone(result.value)
        self.assertIn('超出表中上限', result.message)

    def test_max_allowed_l1(self):
        expected = {'A': 500, 'B': 500, 'C': 500, 'D': 750, 'E': 1000}
        for key, value in expected.items():
            self.assertEqual(geom.max_allowed_l1(key), value, msg=key)

    def test_max_allowed_l2_depends_on_rack_type(self):
        expected = {'A': (250, 500), 'B': (250, 500), 'C': (250, 500),
                    'D': (250, 500), 'E': (500, 1000)}
        for key, (type_one, type_two) in expected.items():
            self.assertEqual(geom.max_allowed_l2(key, 1), type_one, msg=key)
            self.assertEqual(geom.max_allowed_l2(key, 2), type_two, msg=key)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(geom.pipe_rack_number(1, 'a', 'd', 994.0, 250.0),
                         'D15-1-A-D-994-250')
        self.assertEqual(geom.pipe_rack_number(2, 'e', 'f', 993.0, 1000.0),
                         'D15-2-E-F-993-1000')

    def test_stiffener_segment_is_optional_free_text(self):
        """筋板段是用户手输的纯文字：写了就附加到编号末尾，留空则整段不附加。"""
        # 写了：去掉首尾空白后原样附加（不做单位换算、不做格式校验）
        self.assertEqual(
            geom.pipe_rack_number(1, 'a', 'd', 994.0, 250.0, '10×100'),
            'D15-1-A-D-994-250-10×100')
        self.assertEqual(
            geom.pipe_rack_number(2, 'e', 'f', 993.0, 1000.0, ' h=10 w=100 '),
            'D15-2-E-F-993-1000-h=10 w=100')
        # 留空 / 只有空白 / None：都不附加该段
        for empty in ('', '   ', None):
            self.assertEqual(
                geom.pipe_rack_number(1, 'a', 'd', 994.0, 250.0, empty),
                'D15-1-A-D-994-250', msg=repr(empty))

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(-0.5), 0)

    def test_unknown_weld_joint_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.pipe_rack_number(1, 'A', 'Z', 1000.0, 250.0)

    def test_weld_joint_choices(self):
        codes = [code for code, _label in geom.weld_joint_choices()]
        self.assertEqual(codes, list('ABCDEF'))

    def test_eccentric_type_helper(self):
        self.assertFalse(geom.is_eccentric_type(1))
        self.assertTrue(geom.is_eccentric_type(2))
        self.assertFalse(geom.is_eccentric_type('x'))


# ---------------------------------------------------------------------------
# 向量工具
# ---------------------------------------------------------------------------


def _sub(first, second):
    return tuple(first[index] - second[index] for index in range(3))


def _dot(first, second):
    return sum(first[index] * second[index] for index in range(3))


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _norm(vector):
    return sum(component * component for component in vector) ** 0.5


def _round9(vector):
    return tuple(round(component, 9) + 0.0 for component in vector)


def _distance(first, second):
    return _norm(_sub(first, second))


if __name__ == '__main__':
    unittest.main()
