# -*- coding: utf-8 -*-
"""G6 地面上生根的门型架（槽钢和 H 型钢组合）：纯几何 / 数据逻辑单测。

覆盖：竖直线解析（地面 → 横担顶面）、布置不变量（**两立柱外缘间距 = L**、
净距 = 横担长度 = L − 2d、横担夹在两柱之间不外伸、管位面 = 上翼缘顶面 = 构架
高度、柱顶高出横担顶面 50）、两片槽钢**背靠背、腹板净距 S、关于门架平面对称**、
表 1 允许荷载（MAX.H × L，表 1 的 D~G 映射到 A~D）、表 2 锚板 / 锚栓 / MIN.h、
抬升量与编号 ``名称-子项-H-L``。
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
_GEOM_DIR = os.path.join(_MODULE_DIR, 'G6门型架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import G6门型架_几何 as geom  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-9


def _plane_dirs(heading_deg):
    heading = math.radians(heading_deg)
    return ((math.cos(heading), math.sin(heading), 0.0),
            (-math.sin(heading), math.cos(heading), 0.0))


def _member_axes_world(variant_key, member_kind, heading_deg=0.0):
    run_dir, v_dir = _plane_dirs(heading_deg)
    world = []
    for ux, vx, wx in geom.member_axes(variant_key, member_kind):
        world.append((ux * run_dir[0] + vx * v_dir[0],
                      ux * run_dir[1] + vx * v_dir[1],
                      wx))
    return tuple(world)


def _post(base=(0.0, 0.0, 0.0), height_mm=1000.0):
    """``base`` 取锚板顶面中心（局部 w = 0）；``height_mm`` 为构架高度。"""
    return geom.VerticalPost(
        base=tuple(float(v) for v in base),
        top=(base[0], base[1], base[2] + float(height_mm)),
        height_mm=float(height_mm),
    )


def _member_world(variant_key, member_kind, post, post_span_mm,
                  heading_deg=0.0, post_axis_u=0.0):
    """返回 ``(origin, axis_z, length_mm, world_points)``。

    ``world_points`` 是截面轮廓映射到世界的点列；扫掠范围要用
    「起点 + 长度×axis_z」一并算进去（截面在 u 方向没有厚度时同理）。
    """
    run_dir, v_dir = _plane_dirs(heading_deg)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, post.height_mm, post_span_mm, post_axis_u)
    origin = (
        post.base[0] + origin_uvw[0] * run_dir[0] + origin_uvw[1] * v_dir[0],
        post.base[1] + origin_uvw[0] * run_dir[1] + origin_uvw[1] * v_dir[1],
        post.base[2] + origin_uvw[2],
    )
    axis_x, axis_y, axis_z = _member_axes_world(
        variant_key, member_kind, heading_deg)
    frame = ssg.Frame(origin, axis_x, axis_y, axis_z)
    points = [point
              for segment in geom.sample_member(variant_key, member_kind, frame)
              for point in segment]
    return origin, axis_z, length_mm, points


def _bbox(points, origin=None, axis_z=None, length=None):
    """点云包围盒；给定扫掠信息时把「起点 + 长度」也算进 u / v / w 范围。"""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    if origin is not None and axis_z is not None and length is not None:
        for index, arrays in ((0, xs), (1, ys), (2, zs)):
            arrays.append(origin[index])
            arrays.append(origin[index] + length * axis_z[index])
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


class ParseVerticalPostTests(unittest.TestCase):
    def test_single_vertical_segment(self):
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, 800.0)]])
        self.assertAlmostEqual(post.height_mm, 800.0, places=6)
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 800.0))

    def test_downward_segment_is_normalised(self):
        post = geom.parse_vertical_post([[(0.0, 0.0, 900.0), (0.0, 0.0, 0.0)]])
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 900.0))

    def test_slight_tilt_within_tolerance_is_accepted(self):
        tilt = math.radians(geom.VERTICAL_TOLERANCE_DEG - 2.0)
        top = (1000.0 * math.sin(tilt), 0.0, 1000.0 * math.cos(tilt))
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), top]])
        self.assertAlmostEqual(post.height_mm, 1000.0 * math.cos(tilt),
                               places=6)

    def test_horizontal_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (500.0, 0.0, 0.0)]])

    def test_two_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post(
                [[(0.0, 0.0, 0.0), (0.0, 0.0, 500.0), (0.0, 500.0, 500.0)]])

    def test_too_short_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post(
                [[(0.0, 0.0, 0.0), (0.0, 0.0, geom.MIN_FRAME_HEIGHT_MM - 1.0)]])


class LayoutTests(unittest.TestCase):
    """L ＝ 两立柱外缘间距时的一整套布置不变量。"""

    POST_SPAN = 1500.0
    FRAME_HEIGHT = 1000.0

    def _members(self, variant_key, post_span=None, height_mm=None,
                 heading_deg=0.0):
        post_span = self.POST_SPAN if post_span is None else post_span
        height_mm = self.FRAME_HEIGHT if height_mm is None else height_mm
        post = _post(height_mm=height_mm)
        left = _member_world(
            variant_key, 'post', post, post_span, heading_deg,
            geom.post_axis_offset(variant_key, post_span, 'left'))
        right = _member_world(
            variant_key, 'post', post, post_span, heading_deg,
            geom.post_axis_offset(variant_key, post_span, 'right'))
        arm_plus = _member_world(variant_key, 'arm_plus', post, post_span,
                                 heading_deg)
        arm_minus = _member_world(variant_key, 'arm_minus', post, post_span,
                                  heading_deg)
        return post, left, right, arm_plus, arm_minus

    def _boxes(self, variant_key, post_span=None, height_mm=None,
               heading_deg=0.0):
        post, left, right, arm_plus, arm_minus = self._members(
            variant_key, post_span, height_mm, heading_deg)
        return (post,
                _bbox(left[3], left[0], left[1], left[2]),
                _bbox(right[3], right[0], right[1], right[2]),
                _bbox(arm_plus[3], arm_plus[0], arm_plus[1], arm_plus[2]),
                _bbox(arm_minus[3], arm_minus[0], arm_minus[1], arm_minus[2]))

    def test_post_outer_faces_span_equals_l(self):
        """两立柱**外缘**间距 ＝ L（用户输入）。"""
        for variant_key in sorted(geom.VARIANTS):
            post, left_box, right_box, _ap, _am = self._boxes(variant_key)
            self.assertAlmostEqual(right_box[1] - left_box[0],
                                   self.POST_SPAN, places=6, msg=variant_key)
            self.assertAlmostEqual(left_box[0], -self.POST_SPAN / 2.0,
                                   places=6, msg=variant_key)
            self.assertAlmostEqual(right_box[1], self.POST_SPAN / 2.0,
                                   places=6, msg=variant_key)
            self.assertAlmostEqual(
                geom.post_axis_offset(variant_key, self.POST_SPAN, 'left'),
                -geom.post_axis_offset(variant_key, self.POST_SPAN, 'right'),
                places=9)

    def test_post_axes_are_inset_by_half_the_post_depth(self):
        """立柱轴线在 ∓(L − d)/2：内侧翼缘面即净距边界 ∓(L − 2d)/2。"""
        for variant_key in sorted(geom.VARIANTS):
            depth = geom.post_depth(variant_key)
            axis = geom.post_axis_offset(variant_key, self.POST_SPAN, 'left')
            self.assertAlmostEqual(axis, -(self.POST_SPAN - depth) / 2.0,
                                   places=9)
            post, left_box, _rb, _ap, _am = self._boxes(variant_key)
            # 外缘在 -L/2，内侧翼缘面在 -L/2 + d = -(L-2d)/2。
            self.assertAlmostEqual(left_box[0], -self.POST_SPAN / 2.0,
                                   places=6)
            self.assertAlmostEqual(left_box[0] + depth,
                                   -geom.net_span(variant_key,
                                                  self.POST_SPAN) / 2.0,
                                   places=6)
            # 轴线＝截面外接矩形中心（H 型钢对称）。
            self.assertAlmostEqual(left_box[0] + depth / 2.0, axis, places=6)

    def test_crossarm_length_equals_net_span(self):
        for variant_key in sorted(geom.VARIANTS):
            depth = geom.post_depth(variant_key)
            expected = self.POST_SPAN - 2.0 * depth
            self.assertAlmostEqual(
                geom.crossarm_length(variant_key, self.POST_SPAN), expected,
                places=9)
            self.assertAlmostEqual(
                geom.net_span(variant_key, self.POST_SPAN), expected, places=9)

    def test_crossarm_is_between_the_posts_without_overhang(self):
        """横担夹在两柱之间、两端正好顶在立柱内侧翼缘面上（不外伸）。"""
        for variant_key in sorted(geom.VARIANTS):
            post, left_box, right_box, arm_box, arm_minus_box = self._boxes(
                variant_key)
            inner_left = left_box[1]      # 左柱内侧（+u 侧）翼缘面
            inner_right = right_box[0]    # 右柱内侧（-u 侧）翼缘面
            self.assertAlmostEqual(arm_box[0], inner_left, places=6,
                                   msg=variant_key)
            self.assertAlmostEqual(arm_box[1], inner_right, places=6,
                                   msg=variant_key)
            self.assertAlmostEqual(arm_minus_box[0], inner_left, places=6)
            self.assertAlmostEqual(arm_minus_box[1], inner_right, places=6)
            # 不外伸：横担整体落在两柱外缘之内。
            self.assertGreaterEqual(arm_box[0], left_box[0] - TOL)
            self.assertLessEqual(arm_box[1], right_box[1] + TOL)
            # 两片槽钢长度一致、都等于净距。
            self.assertAlmostEqual(arm_box[1] - arm_box[0],
                                   geom.crossarm_length(variant_key,
                                                        self.POST_SPAN),
                                   places=6)

    def test_seating_face_is_the_top_flange_of_both_channels(self):
        """管位面 ＝ 两片槽钢上翼缘顶面 ＝ 构架高度。"""
        for variant_key in sorted(geom.VARIANTS):
            post, _lb, _rb, arm_box, arm_minus_box = self._boxes(variant_key)
            self.assertAlmostEqual(arm_box[5], post.height_mm, places=6,
                                   msg=variant_key)
            self.assertAlmostEqual(arm_minus_box[5], post.height_mm, places=6)
            self.assertAlmostEqual(
                arm_box[5] - arm_box[4], geom.channel_height(variant_key),
                places=6)

    def test_post_tops_rise_50_above_the_seating_face(self):
        for variant_key in sorted(geom.VARIANTS):
            post, left_box, right_box, arm_box, _am = self._boxes(variant_key)
            for box in (left_box, right_box):
                self.assertAlmostEqual(box[5], post.height_mm
                                       + geom.POST_TOP_RISE_MM, places=6)
            self.assertAlmostEqual(
                geom.post_length(variant_key, post.height_mm),
                post.height_mm + geom.POST_TOP_RISE_MM, places=9)
            # 柱顶比横担顶面高 50。
            self.assertAlmostEqual(left_box[5] - arm_box[5],
                                   geom.POST_TOP_RISE_MM, places=6)

    def test_channels_are_back_to_back_with_gap_s(self):
        """两片槽钢腹板相对：内表面分别在 ∓S/2，净距 ＝ S，且关于 v = 0 对称。"""
        for variant_key in sorted(geom.VARIANTS):
            gap = geom.channel_gap(variant_key)
            flange = geom.channel_flange_width(variant_key)
            self.assertEqual(geom.channel_web_faces(variant_key),
                             (-gap / 2.0, gap / 2.0))
            self.assertAlmostEqual(
                geom.channel_v_offset(variant_key, 'plus'),
                gap / 2.0 + flange / 2.0, places=9)
            self.assertAlmostEqual(
                geom.channel_v_offset(variant_key, 'minus'),
                -(gap / 2.0 + flange / 2.0), places=9)
            post, _lb, _rb, arm_box, arm_minus_box = self._boxes(variant_key)
            # +v 片的腹板内表面在 v = +S/2（即其 v 最小值），外伸到 +S/2 + b。
            self.assertAlmostEqual(arm_box[2], gap / 2.0, places=6)
            self.assertAlmostEqual(arm_box[3], gap / 2.0 + flange, places=6)
            self.assertAlmostEqual(arm_minus_box[2], -gap / 2.0 - flange,
                                   places=6)
            self.assertAlmostEqual(arm_minus_box[3], -gap / 2.0, places=6)

    def test_channel_pair_fits_inside_the_post_flange(self):
        """两片槽钢的总宽 2b + S 不超过立柱翼缘宽（图上四组都正好放得下）。"""
        for variant_key in sorted(geom.VARIANTS):
            self.assertTrue(geom.channel_pair_fits_post(variant_key),
                            msg=variant_key)
            self.assertLessEqual(
                geom.channel_pair_width(variant_key),
                geom.post_flange_width(variant_key) + TOL)
        # 逐子项的具体数值（图上 99 / 146 / 196 / 246 ≤ 100 / 150 / 200 / 250）
        self.assertAlmostEqual(geom.channel_pair_width('A'), 99.0, places=9)
        self.assertAlmostEqual(geom.channel_pair_width('B'), 146.0, places=9)
        self.assertAlmostEqual(geom.channel_pair_width('C'), 196.0, places=9)
        self.assertAlmostEqual(geom.channel_pair_width('D'), 246.0, places=9)

    def test_post_web_is_inside_the_channel_gap(self):
        """立柱腹板（v = 0）落在两片槽钢的净距里，不与横担相碰。"""
        for variant_key in sorted(geom.VARIANTS):
            self.assertLess(geom.post_web_thickness(variant_key) / 2.0,
                            geom.channel_gap(variant_key) / 2.0)
            post, left_box, _rb, _ap, _am = self._boxes(variant_key)
            self.assertAlmostEqual(left_box[2], -geom.post_flange_width(
                variant_key) / 2.0, places=6)

    def test_post_flanges_are_perpendicular_to_the_frame_plane(self):
        """立柱腹板在门架平面（v = 0）、翼缘对称于该平面。"""
        for variant_key in sorted(geom.VARIANTS):
            flange = geom.post_flange_width(variant_key)
            post, left_box, right_box, _ap, _am = self._boxes(variant_key)
            for box in (left_box, right_box):
                self.assertAlmostEqual(box[2], -flange / 2.0, places=6)
                self.assertAlmostEqual(box[3], flange / 2.0, places=6)
                self.assertAlmostEqual(box[2] + box[3], 0.0, places=6)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm_plus', 'arm_minus'):
                axis_x, axis_y, axis_z = geom.member_axes(variant_key,
                                                          member_kind)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)

    def test_heading_rotates_the_frame_plane(self):
        post = _post(height_mm=self.FRAME_HEIGHT)
        variant_key = 'C'
        start = geom.crossarm_span(variant_key, self.POST_SPAN)[0]
        v_offset = geom.channel_v_offset(variant_key, 'plus')
        left_axis = geom.post_axis_offset(variant_key, self.POST_SPAN, 'left')
        for heading in (0.0, 90.0, 180.0, 270.0):
            run_dir, v_dir = _plane_dirs(heading)
            origin, axis_z, length, points = _member_world(
                variant_key, 'arm_plus', post, self.POST_SPAN, heading)
            # 横担起点 = 净距左端（沿 u） + 槽钢中心偏移（沿 v）。
            self.assertAlmostEqual(axis_z[0], run_dir[0], places=9)
            self.assertAlmostEqual(axis_z[1], run_dir[1], places=9)
            self.assertAlmostEqual(
                origin[0], start * run_dir[0] + v_offset * v_dir[0], places=6)
            self.assertAlmostEqual(
                origin[1], start * run_dir[1] + v_offset * v_dir[1], places=6)
            box = _bbox(points, origin, axis_z, length)
            self.assertAlmostEqual(box[5], post.height_mm, places=6)
            # 立柱轴线同样随朝向旋转。
            leg_origin = _member_world(
                variant_key, 'post', post, self.POST_SPAN, heading,
                left_axis)[0]
            self.assertAlmostEqual(leg_origin[0], left_axis * run_dir[0],
                                   places=6)
            self.assertAlmostEqual(leg_origin[1], left_axis * run_dir[1],
                                   places=6)

    def test_too_short_post_span_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.crossarm_length('D', 400.0)


class VariantTests(unittest.TestCase):
    def test_specifications_match_tables(self):
        expected = {
            'A': ('H100×100×6×8', '[5', 25.0),
            'B': ('H150×150×7×10', '[10', 50.0),
            'C': ('H200×200×8×12', '[16a', 70.0),
            'D': ('H250×250×9×14', '[20a', 100.0),
        }
        for variant_key, (beam, channel, gap) in expected.items():
            self.assertEqual(geom.beam_specification(variant_key), beam,
                             msg=variant_key)
            self.assertEqual(geom.channel_specification(variant_key), channel,
                             msg=variant_key)
            self.assertAlmostEqual(geom.channel_gap(variant_key), gap,
                                   places=9, msg=variant_key)

    def test_post_depth_and_flange(self):
        expected = {'A': (100.0, 100.0), 'B': (150.0, 150.0),
                    'C': (200.0, 200.0), 'D': (250.0, 250.0)}
        for variant_key, (depth, flange) in expected.items():
            self.assertAlmostEqual(geom.post_depth(variant_key), depth,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.post_flange_width(variant_key), flange,
                                   places=9, msg=variant_key)

    def test_channel_dimensions(self):
        expected = {'A': (50.0, 37.0), 'B': (100.0, 48.0),
                    'C': (160.0, 63.0), 'D': (200.0, 73.0)}
        for variant_key, (height, flange) in expected.items():
            self.assertAlmostEqual(geom.channel_height(variant_key), height,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.channel_flange_width(variant_key),
                                   flange, places=9, msg=variant_key)

    def test_variant_choices_are_sorted(self):
        self.assertEqual([key for key, _label in geom.variant_choices()],
                         ['A', 'B', 'C', 'D'])

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.beam_specification('Z')
        with self.assertRaises(ValueError):
            geom.ground_anchor_spec('Z')


class GroundBaseTests(unittest.TestCase):
    """表 2：锚板 / 膨胀锚栓 / 地坪最小厚度，以及钢构架抬升量。"""

    def test_table_two_values(self):
        expected = {
            'A': (260.0, 200.0, 18.0, 12.0, 16.0, 180.0, 100.0, 150.0),
            'B': (350.0, 250.0, 22.0, 16.0, 20.0, 220.0, 125.0, 150.0),
            'C': (400.0, 300.0, 22.0, 20.0, 20.0, 220.0, 125.0, 150.0),
            'D': (500.0, 400.0, 22.0, 20.0, 20.0, 220.0, 125.0, 150.0),
        }
        for variant_key, values in expected.items():
            spec = geom.ground_anchor_spec(variant_key)
            actual = (spec['plate_e'], spec['hole_spacing_f'],
                      spec['hole_dia_g'], spec['plate_t'], spec['bolt_dia'],
                      spec['bolt_len'], spec['embed'], spec['min_h'])
            self.assertEqual(actual, values, msg=variant_key)

    def test_ground_lift_is_grout_plus_plate(self):
        self.assertAlmostEqual(geom.ground_lift('A'), 37.0, places=9)
        self.assertAlmostEqual(geom.ground_lift('B'), 41.0, places=9)
        self.assertAlmostEqual(geom.ground_lift('C'), 45.0, places=9)
        self.assertAlmostEqual(geom.ground_lift('D'), 45.0, places=9)
        for variant_key in sorted(geom.VARIANTS):
            self.assertAlmostEqual(
                geom.ground_lift(variant_key),
                geom.GROUND_GROUT_THICKNESS_MM
                + geom.ground_anchor_spec(variant_key)['plate_t'], places=9)

    def test_min_pavement_thickness(self):
        for variant_key in sorted(geom.VARIANTS):
            self.assertAlmostEqual(geom.min_pavement_thickness(variant_key),
                                   150.0, places=9)

    def test_spec_is_a_copy(self):
        spec = geom.ground_anchor_spec('A')
        spec['plate_e'] = 999.0
        self.assertAlmostEqual(geom.ground_anchor_spec('A')['plate_e'], 260.0,
                               places=9)


class LoadTableTests(unittest.TestCase):
    """表 1 逐格核对（kN，表 1 的 D~G 对应本模块 A~D）；「—」为 None。"""

    def test_table_one_values(self):
        expected = {
            ('A', 1000, 500): 15.0,
            ('A', 1000, 1000): 10.0,
            ('A', 1500, 500): 8.0,
            ('A', 1500, 1000): 8.0,
            ('B', 1000, 1000): 40.0,
            ('B', 1000, 1500): 20.0,
            ('B', 2000, 1500): 20.0,
            ('C', 1000, 1000): 60.0,
            ('C', 1000, 1500): 40.0,
            ('C', 2000, 2000): 30.0,
            ('C', 3000, 1000): 20.0,
            ('D', 1000, 2000): 80.0,
            ('D', 2000, 1500): 60.0,
            ('D', 3000, 2000): 40.0,
        }
        for (key, height, arm), value in expected.items():
            result = geom.allowable_load(key, height, arm)
            self.assertAlmostEqual(result.value, value, places=9,
                                   msg='%s H=%d L=%d' % (key, height, arm))

    def test_row_without_that_column_reports_out_of_range(self):
        """表 1 的「—」是按列缺档：该行没有更大的 L 列时报「超出表中上限」。"""
        result = geom.allowable_load('A', 1000, 1500)
        self.assertIsNone(result.value)
        self.assertIn('超出表中上限', result.message)
        # L 取不小于输入的最小列（偏安全）：A 子项 L=600 取 L≤1000 列。
        self.assertAlmostEqual(
            geom.allowable_load('A', 1000.0, 600.0).used_arm_mm, 1000)
        self.assertAlmostEqual(
            geom.allowable_load('A', 1000.0, 600.0).value, 10.0, places=9)

    def test_height_uses_the_covering_max_height_row(self):
        result = geom.allowable_load('D', 1500.0, 1000.0)
        self.assertEqual(result.used_height_mm, 2000)
        self.assertAlmostEqual(result.value, 60.0, places=9)
        low = geom.allowable_load('D', 800.0, 1000.0)
        self.assertEqual(low.used_height_mm, 1000)
        self.assertAlmostEqual(low.value, 100.0, places=9)

    def test_arm_length_rounds_up_to_the_next_column(self):
        self.assertAlmostEqual(
            geom.allowable_load('D', 1000.0, 501.0).value, 100.0, places=9)
        self.assertAlmostEqual(
            geom.allowable_load('B', 1000.0, 1200.0).value, 20.0, places=9)

    def test_out_of_range_is_reported(self):
        above_height = geom.allowable_load('A', 1600.0, 500.0)
        self.assertIsNone(above_height.value)
        self.assertIn('超出表中最大 MAX.H', above_height.message)
        above_arm = geom.allowable_load('A', 1000.0, 2500.0)
        self.assertIsNone(above_arm.value)
        self.assertIn('超出表中上限', above_arm.message)

    def test_max_height_and_max_arm_length(self):
        expected = {'A': (1500.0, 1000.0), 'B': (2000.0, 1500.0),
                    'C': (3000.0, 2000.0), 'D': (3000.0, 2000.0)}
        for variant_key, (height, arm) in expected.items():
            self.assertAlmostEqual(geom.max_height(variant_key), height,
                                   places=9, msg=variant_key)
            self.assertAlmostEqual(geom.max_arm_length(variant_key), arm,
                                   places=9, msg=variant_key)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_pipe_rack_number('G6', 'a', 1000.0, 1500.0),
            'G6-A-1000-1500')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(geom.build_pipe_rack_number('', 'A', 1000, 1500), '')
        self.assertEqual(geom.build_pipe_rack_number('  ', 'A', 1000, 1500), '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(1.5), 2)
        self.assertEqual(geom.round_half_up(1499.5), 1500)


if __name__ == '__main__':
    unittest.main()
