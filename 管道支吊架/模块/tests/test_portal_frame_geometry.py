# -*- coding: utf-8 -*-
"""门型架纯几何 / 数据逻辑单测（不依赖 Bentley 运行时）。

覆盖：竖直线解析、立柱与横担的布置不变量、截面朝向与右手系、表 1 荷载查询、
管架编号。门架几何的核心约定是「所选竖直线为整组中心线、B 为两立柱净距」——
两立柱轴线关于该线对称，横担以其为中点**横跨两根立柱顶面**、两端各超出立柱
外缘 15 mm，故 ``横担长 L = B + 2W + 30``。
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
_GEOM_DIR = os.path.join(_MODULE_DIR, '门型架')
for _path in (_GEOM_DIR, os.path.join(_REPO_ROOT, '型钢截面生成器')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 门型架_几何 as geom  # noqa: E402
from steel_sections import steel_sweep_geometry as ssg  # noqa: E402


TOL = 1.0e-9


def _plane_dirs(heading_deg):
    heading = math.radians(heading_deg)
    return ((math.cos(heading), math.sin(heading), 0.0),
            (-math.sin(heading), math.cos(heading), 0.0))


def _member_axes_world(variant_key, member_kind, heading_deg=0.0,
                       mirror_u=False):
    run_dir, v_dir = _plane_dirs(heading_deg)
    world = []
    for ux, vx, wx in geom.member_axes(variant_key, member_kind, mirror_u):
        world.append((ux * run_dir[0] + vx * v_dir[0],
                      ux * run_dir[1] + vx * v_dir[1],
                      wx))
    return tuple(world)


def _post(base=(0.0, 0.0, 0.0), height_mm=1000.0):
    return geom.VerticalPost(
        base=tuple(float(v) for v in base),
        top=(base[0], base[1], base[2] + float(height_mm)),
        height_mm=float(height_mm),
    )


def _member_world(variant_key, member_kind, post, span_mm,
                  heading_deg=0.0, post_axis_u=0.0, mirror_u=False):
    """返回 ``(origin, axis_z, length_mm, world_points)``。

    ``world_points`` 是截面轮廓（未扫掠）映射到世界的点列，与
    ``门型架（角钢和槽钢）.py`` 中 ``_build_member_element`` 的做法一致。
    """
    run_dir, v_dir = _plane_dirs(heading_deg)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, post.height_mm, span_mm, post_axis_u)
    origin = (
        post.base[0] + origin_uvw[0] * run_dir[0] + origin_uvw[1] * v_dir[0],
        post.base[1] + origin_uvw[0] * run_dir[1] + origin_uvw[1] * v_dir[1],
        post.base[2] + origin_uvw[2],
    )
    axis_x, axis_y, axis_z = _member_axes_world(
        variant_key, member_kind, heading_deg, mirror_u)
    frame = ssg.Frame(origin, axis_x, axis_y, axis_z)
    points = [point
              for segment in geom.sample_member(variant_key, member_kind, frame)
              for point in segment]
    return origin, axis_z, length_mm, points


def _bbox(points):
    return (
        min(point[0] for point in points), max(point[0] for point in points),
        min(point[1] for point in points), max(point[1] for point in points),
        min(point[2] for point in points), max(point[2] for point in points),
    )


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


class ParseVerticalPostTests(unittest.TestCase):
    def test_single_vertical_segment(self):
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, 1200.0)]])
        self.assertAlmostEqual(post.height_mm, 1200.0, places=6)
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 1200.0))

    def test_downward_segment_is_normalised(self):
        """端点顺序颠倒时，低端始终是基座。"""
        post = geom.parse_vertical_post([[(0.0, 0.0, 900.0), (0.0, 0.0, 0.0)]])
        self.assertEqual(post.base, (0.0, 0.0, 0.0))
        self.assertEqual(post.top, (0.0, 0.0, 900.0))
        self.assertAlmostEqual(post.height_mm, 900.0, places=6)

    def test_slight_tilt_within_tolerance_is_accepted(self):
        tilt_deg = geom.VERTICAL_TOLERANCE_DEG - 2.0
        self.assertGreater(tilt_deg, 0.0)
        tilt = math.radians(tilt_deg)
        top = (1000.0 * math.sin(tilt), 0.0, 1000.0 * math.cos(tilt))
        post = geom.parse_vertical_post([[(0.0, 0.0, 0.0), top]])
        self.assertAlmostEqual(post.height_mm, 1000.0 * math.cos(tilt),
                               places=6)

    def test_horizontal_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (500.0, 0.0, 0.0)]])

    def test_forty_five_degree_segment_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (500.0, 0.0, 500.0)]])

    def test_two_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post(
                [[(0.0, 0.0, 0.0), (0.0, 0.0, 500.0), (0.0, 500.0, 500.0)]])

    def test_too_short_is_rejected(self):
        short = geom.MIN_POST_HEIGHT_MM - 1.0
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([[(0.0, 0.0, 0.0), (0.0, 0.0, short)]])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.parse_vertical_post([])


class LayoutTests(unittest.TestCase):
    """B 为两立柱净距时的一整套布置不变量。"""

    def _members(self, variant_key, span_mm, height_mm=1000.0, heading_deg=0.0):
        post = _post(height_mm=height_mm)
        width = geom.inplane_width(variant_key)
        left = _member_world(variant_key, 'post', post, span_mm, heading_deg,
                             geom.post_axis_offset(variant_key, span_mm, 'left'))
        right = _member_world(variant_key, 'post', post, span_mm, heading_deg,
                              geom.post_axis_offset(variant_key, span_mm, 'right'),
                              mirror_u=True)
        arm = _member_world(variant_key, 'arm', post, span_mm, heading_deg)
        return post, width, left, right, arm

    def test_net_span_between_inner_faces_equals_b(self):
        for variant_key in sorted(geom.VARIANTS):
            for span in (250.0, 500.0, 1500.0):
                post, width, left, right, arm = self._members(variant_key, span)
                left_box = _bbox(left[3])
                right_box = _bbox(right[3])
                self.assertAlmostEqual(right_box[0] - left_box[1], span,
                                       places=6,
                                       msg='%s B=%.0f' % (variant_key, span))

    def test_selected_line_is_the_assembly_centreline(self):
        """所选竖直线是整组中心线：两立柱轴对称，横担亦以它为中点。"""
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            span = 500.0
            post, w, left, right, arm = self._members(variant_key, span)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            # 两立柱轴线对称于 u = 0，截面外缘也对称。
            self.assertAlmostEqual(
                geom.post_axis_offset(variant_key, span, 'left'),
                -geom.post_axis_offset(variant_key, span, 'right'), places=9)
            self.assertAlmostEqual(left_box[0], -right_box[1], places=6)
            self.assertAlmostEqual(left_box[0], -(span + 2.0 * width) / 2.0,
                                   places=6)
            # 横担两端同样对称于中心线。
            beam_start, beam_len = geom.beam_span(variant_key, span)
            self.assertAlmostEqual(beam_start, -beam_len / 2.0, places=9)
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertAlmostEqual(arm[0][0], -beam_end, places=6)

    def test_post_section_is_centred_on_its_own_axis(self):
        """每个立柱截面外接矩形中心落在自身轴线上，故轴线两侧各为 ∓W/2。"""
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            post, w, left, right, arm = self._members(variant_key, 500.0)
            left_axis = geom.post_axis_offset(variant_key, 500.0, 'left')
            left_box = _bbox(left[3])
            self.assertAlmostEqual(left_box[0], left_axis - width / 2.0,
                                   places=6)
            self.assertAlmostEqual(left_box[1], left_axis + width / 2.0,
                                   places=6)

    def test_post_axes_are_symmetric_about_the_selected_line(self):
        """两立柱轴线间距为 B + W，且关于所选中心线对称。"""
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            pitch = 500.0 + width
            left_axis = geom.post_axis_offset(variant_key, 500.0, 'left')
            right_axis = geom.post_axis_offset(variant_key, 500.0, 'right')
            self.assertAlmostEqual(left_axis, -pitch / 2.0, places=9)
            self.assertAlmostEqual(right_axis, pitch / 2.0, places=9)
            self.assertAlmostEqual(right_axis - left_axis, pitch, places=9)
            right_box = _bbox(self._members(variant_key, 500.0)[3][3])
            self.assertAlmostEqual(right_box[0], right_axis - width / 2.0,
                                   places=6)

    def test_arm_length_is_b_plus_twice_w_plus_30(self):
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            for span in (250.0, 500.0, 2000.0):
                self.assertAlmostEqual(
                    geom.arm_length(variant_key, span),
                    span + 2.0 * width + 2.0 * geom.ARM_BACK_OVERHANG_MM,
                    places=9)

    def test_beam_left_end_overhangs_left_post_outer_face_by_15(self):
        for variant_key in sorted(geom.VARIANTS):
            width = geom.inplane_width(variant_key)
            post, w, left, right, arm = self._members(variant_key, 500.0)
            u_start, length = geom.beam_span(variant_key, 500.0)
            left_box = _bbox(left[3])
            # 左端 = 左立柱外缘 - 15。
            left_axis = geom.post_axis_offset(variant_key, 500.0, 'left')
            self.assertAlmostEqual(left_box[0], left_axis - width / 2.0,
                                   places=6)
            self.assertAlmostEqual(
                left_box[0] - u_start, geom.ARM_BACK_OVERHANG_MM, places=9)

    def test_beam_right_end_overhangs_right_post_outer_face_by_15(self):
        for variant_key in sorted(geom.VARIANTS):
            post, width, left, right, arm = self._members(variant_key, 500.0)
            right_box = _bbox(right[3])
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertAlmostEqual(
                beam_end - right_box[1], geom.ARM_BACK_OVERHANG_MM, places=6)

    def test_beam_spans_over_both_post_tops(self):
        """横担横跨两根立柱，两腿都被压在横担下面。"""
        for variant_key in sorted(geom.VARIANTS):
            post, width, left, right, arm = self._members(variant_key, 500.0)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            u_start = geom.beam_span(variant_key, 500.0)[0]
            beam_end = arm[0][0] + arm[2] * arm[1][0]
            self.assertLessEqual(u_start, left_box[0])
            self.assertGreaterEqual(beam_end, right_box[1])

    # -- 立柱与横担背靠背 --------------------------------------------------

    def test_angle_post_is_back_to_back_with_arm_vertical_leg(self):
        """角钢：立柱镜像到横担竖直肢外侧，两肢的【背面】在 v = W/2 相贴。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            self.assertAlmostEqual(geom.post_v_offset(variant_key), width,
                                   places=9)
            post, w, left, right, arm = self._members(variant_key, 500.0)
            arm_box = _bbox(arm[3])
            # 横担竖直肢在 [W/2 - t, W/2]，其背面（外角侧）即横担截面的 +v 极值。
            self.assertAlmostEqual(arm_box[3], width / 2.0, places=6)
            # 两根立柱的截面都整体在横担竖直肢之外，背面与横担背面同面 -> 相贴。
            for leg in (left, right):
                leg_box = _bbox(leg[3])
                self.assertAlmostEqual(leg_box[2], arm_box[3], places=6)
                self.assertGreaterEqual(leg_box[2], arm_box[3] - TOL)

    def test_angle_post_does_not_intrude_into_arm_vertical_leg(self):
        """回归：立柱不得落进横担竖直肢所占的 [W/2 - t, W/2] 区间。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            post, w, left, right, arm = self._members(variant_key, 500.0)
            leg_box = _bbox(left[3])
            self.assertGreaterEqual(leg_box[2], width / 2.0 - TOL)
            self.assertGreaterEqual(leg_box[2], leg_box[3] - width - TOL)

    def test_arm_vertical_leg_is_on_the_plus_v_side(self):
        """横担竖直肢挂在 +v 侧，其内侧面即立柱贴合面。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            thickness = geom.section_dimensions(variant_key)['t']
            post, w, left, right, arm = self._members(variant_key, 500.0)
            arm_box = _bbox(arm[3])
            # 截面局部 +y -> -w，故竖直肢在局部 x 最小端，即 +v 侧。
            self.assertAlmostEqual(arm_box[3], width / 2.0, places=6)
            self.assertAlmostEqual(arm_box[2], -width / 2.0, places=6)
            self.assertGreater(thickness, 0.0)

    def test_legs_are_mirror_symmetric_with_openings_outward(self):
        """两根立柱互为镜像（右柱在 u 方向镜像），开口都朝门架外。"""
        for variant_key in ('A', 'B', 'C'):
            left = geom.post_opening_direction(variant_key, mirror_u=False)
            right = geom.post_opening_direction(variant_key, mirror_u=True)
            # 左柱朝 -u（门架外），右柱朝 +u（门架外），v 分量相同。
            self.assertAlmostEqual(left[0], -1.0, places=9)
            self.assertAlmostEqual(right[0], 1.0, places=9)
            self.assertAlmostEqual(left[1], 1.0, places=9)
            self.assertAlmostEqual(right[1], 1.0, places=9)
            # 两者关于 u 互为镜像。
            self.assertAlmostEqual(left[0], -right[0], places=9)
            self.assertAlmostEqual(left[1], right[1], places=9)
        for variant_key in ('D', 'E'):
            # 槽钢截面本身关于 u 中心线对称，无开口朝向可言，镜像也不改变形状。
            self.assertEqual(geom.post_opening_direction(variant_key), (0.0, 0.0))
            self.assertEqual(
                geom.post_opening_direction(variant_key, mirror_u=True),
                (0.0, 0.0))

    def test_mirrored_post_frame_is_still_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for mirror_u in (False, True):
                axis_x, axis_y, axis_z = geom.member_axes(
                    variant_key, 'post', mirror_u)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)

    def test_both_posts_keep_the_same_back_to_back_fit(self):
        """镜像不改变 v 向关系：两柱的 v 范围一致，贴合面不变。"""
        for variant_key in sorted(geom.VARIANTS):
            post, width, left, right, arm = self._members(variant_key, 500.0)
            left_box = _bbox(left[3])
            right_box = _bbox(right[3])
            self.assertAlmostEqual(left_box[2], right_box[2], places=6)
            self.assertAlmostEqual(left_box[3], right_box[3], places=6)

    def test_channel_post_and_arm_webs_are_back_to_back(self):
        """槽钢两腹板的背面在 v = -B/2 相贴，翼缘各自朝外。"""
        for variant_key in ('D', 'E'):
            flange = geom.section_box(variant_key)[0]
            post, w, left, right, arm = self._members(variant_key, 500.0)
            leg_box = _bbox(left[3])
            arm_box = _bbox(arm[3])
            # 立柱整体在 -v 侧（腹板朝 +v 的背面即贴合面），横担腹板在其 +v 侧。
            self.assertLess(leg_box[3], 0.0)
            self.assertAlmostEqual(leg_box[3], arm_box[2], places=6)
            self.assertAlmostEqual(leg_box[3], -flange / 2.0, places=6)

    def test_beam_top_face_lies_at_the_height_of_the_selected_line(self):
        for variant_key in sorted(geom.VARIANTS):
            post, width, left, right, arm = self._members(variant_key, 500.0)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], post.height_mm, places=6)

    def test_channel_post_web_is_back_to_back_with_arm_web(self):
        """槽钢：立柱腹板贴横担腹板的【背面】，两腹板背靠背（不是顶面承压）。"""
        for variant_key in ('D', 'E'):
            flange = geom.section_box(variant_key)[0]
            post, width, left, right, arm = self._members(variant_key, 500.0)
            self.assertAlmostEqual(geom.post_v_offset(variant_key), -flange,
                                   places=9)
            arm_box = _bbox(arm[3])
            # 横担腹板在 -v 端，其背面即横担截面的 -v 极值。
            self.assertAlmostEqual(arm_box[2], -flange / 2.0, places=6)
            for leg in (left, right):
                leg_box = _bbox(leg[3])
                # 立柱在横担腹板之外，背面与横担腹板背面同面 -> 相贴。
                self.assertAlmostEqual(leg_box[3], arm_box[2], places=6)
                self.assertLessEqual(leg_box[3], arm_box[2] + TOL)
                # 立柱不再压在横担下表面之下：顶端高于横担底面。
                leg_top = leg[0][2] + leg[2] * leg[1][2]
                self.assertGreater(leg_top, arm_box[4])

    def test_angle_post_stops_10mm_below_the_arm_horizontal_leg(self):
        """角钢：立柱非通长，顶端比横担水平肢低 10 mm 留作施焊。"""
        for variant_key in ('A', 'B', 'C'):
            thickness = geom.section_dimensions(variant_key)['t']
            post, width, left, right, arm = self._members(variant_key, 500.0,
                                                          height_mm=1000.0)
            height = post.height_mm
            expected = height - thickness - geom.WELD_GAP_MM
            self.assertAlmostEqual(
                geom.post_length(variant_key, height), expected, places=9)
            # 截面轮廓点落在基座平面上，故立柱顶端取「起点 + 沿 +w 的扫掠长度」。
            leg_top = left[0][2] + left[2] * left[1][2]
            self.assertAlmostEqual(leg_top, expected, places=6)
            # 与横担水平肢的下表面（H - t）之间正好留出 10 mm。
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[5], height, places=6)
            self.assertAlmostEqual(arm_box[5] - thickness - leg_top,
                                   geom.WELD_GAP_MM, places=6)

    def test_angle_weld_contact_length(self):
        """角钢立柱肢与横担竖直肢的搭接高度 = W - t - 10，且为正值。"""
        for variant_key in ('A', 'B', 'C'):
            width = geom.inplane_width(variant_key)
            thickness = geom.section_dimensions(variant_key)['t']
            contact = geom.weld_contact_length(variant_key)
            self.assertAlmostEqual(
                contact, width - thickness - geom.WELD_GAP_MM, places=9)
            self.assertGreater(contact, 0.0)

    def test_channel_weld_contact_length(self):
        """槽钢立柱腹板与横担腹板的搭接高度 = 横担截面高 - 翼缘厚 - 10。"""
        for variant_key in ('D', 'E'):
            contact = geom.weld_contact_length(variant_key)
            self.assertAlmostEqual(
                contact, geom.beam_depth(variant_key)
                - geom.beam_flange_thickness(variant_key) - geom.WELD_GAP_MM,
                places=9)
            self.assertGreater(contact, 0.0)

    def test_angle_post_top_is_above_the_arm_underside(self):
        """角钢立柱顶端伸到横担竖直肢范围内（靠侧焊缝传力，不是顶面承压）。"""
        for variant_key in ('A', 'B', 'C'):
            post, width, left, right, arm = self._members(variant_key, 500.0,
                                                          height_mm=1000.0)
            leg_top = left[0][2] + left[2] * left[1][2]
            arm_box = _bbox(arm[3])
            self.assertGreater(leg_top, arm_box[4])
            self.assertLessEqual(leg_top, arm_box[5])

    def test_post_length_uses_the_beam_flange_thickness(self):
        """两类子项统一：立柱下料长 = H - 翼缘厚 - 10。"""
        for variant_key in sorted(geom.VARIANTS):
            thickness = geom.beam_flange_thickness(variant_key)
            _, post_length = geom.member_origin_length(
                variant_key, 'post', 1000.0, 500.0, 0.0)
            self.assertAlmostEqual(
                post_length, 1000.0 - thickness - geom.WELD_GAP_MM, places=9)
            self.assertAlmostEqual(
                geom.post_length(variant_key, 1000.0), post_length, places=9)

    def test_beam_flange_thickness_per_family(self):
        for variant_key in ('A', 'B', 'C'):
            self.assertAlmostEqual(
                geom.beam_flange_thickness(variant_key),
                geom.section_dimensions(variant_key)['t'], places=9)
        for variant_key in ('D', 'E'):
            self.assertAlmostEqual(
                geom.beam_flange_thickness(variant_key),
                geom.section_dimensions(variant_key)['tf'], places=9)

    def test_beam_section_is_centred_on_the_frame_plane(self):
        for variant_key in sorted(geom.VARIANTS):
            x_extent = geom.section_box(variant_key)[0]
            post, width, left, right, arm = self._members(variant_key, 500.0)
            arm_box = _bbox(arm[3])
            self.assertAlmostEqual(arm_box[2], -x_extent / 2.0, places=6)
            self.assertAlmostEqual(arm_box[3], x_extent / 2.0, places=6)

    def test_heading_rotates_the_frame_plane(self):
        post = _post()
        # 横担左端在左立柱外缘之外 15 mm，即 u = -L/2（以整组中心线为中点）。
        start = geom.beam_span('A', 500.0)[0]
        for heading in (0.0, 90.0, 180.0, 270.0):
            run_dir, _v_dir = _plane_dirs(heading)
            origin, axis_z, length, points = _member_world(
                'A', 'arm', post, 500.0, heading)
            self.assertAlmostEqual(axis_z[0], run_dir[0], places=9)
            self.assertAlmostEqual(axis_z[1], run_dir[1], places=9)
            # 横担左端 u = start 落在朝向方向上。
            self.assertAlmostEqual(origin[0], run_dir[0] * start, places=6)
            self.assertAlmostEqual(origin[1], run_dir[1] * start, places=6)
            # 截面整体位于横担起端面（过 origin、垂直于朝向）上。
            for point in points:
                projected = ((point[0] - origin[0]) * run_dir[0]
                             + (point[1] - origin[1]) * run_dir[1])
                self.assertAlmostEqual(projected, 0.0, places=6)
            # 顶面仍落在 H，与朝向无关。
            self.assertAlmostEqual(_bbox(points)[5], post.height_mm, places=6)

    def test_member_frames_are_right_handed(self):
        for variant_key in sorted(geom.VARIANTS):
            for member_kind in ('post', 'arm'):
                axis_x, axis_y, axis_z = geom.member_axes(variant_key, member_kind)
                product = _cross(axis_x, axis_y)
                for index in range(3):
                    self.assertAlmostEqual(product[index], axis_z[index],
                                           places=12)

    def test_angle_post_is_mirrored_in_v(self):
        """角钢立柱已镜像：外角落在 (u = +W/2, v = W/2)，开口朝 (-u, +v)。"""
        post = _post()
        origin, axis_z, length, points = _member_world('A', 'post', post, 500.0)
        side = geom.section_dimensions('A')['B']
        self.assertAlmostEqual(geom.post_v_offset('A'), side, places=9)
        # 外角尖点落在 (u = +W/2, v = W/2)。
        self.assertTrue(any(
            abs(point[0] - side / 2.0) < 1.0e-6
            and abs(point[1] - side / 2.0) < 1.0e-6
            for point in points))

    def test_channel_webs_lie_in_the_frame_plane(self):
        """槽钢立柱与横担的腹板都在 u-w 平面内（腹板竖直）。"""
        post = _post()
        for member_kind, offset in (('post', 0.0), ('arm', 0.0)):
            origin, axis_z, length, points = _member_world(
                'E', member_kind, post, 500.0, post_axis_u=offset)
            thickness = geom.section_dimensions('E')['tw']
            # 腹板沿 v 的厚度只有 tw，且位于截面的 ±v 一侧。
            v_values = sorted(set(round(point[1], 9) for point in points))
            self.assertLessEqual(len(v_values), 5)
            self.assertTrue(any(
                abs((max(v_values) - value) - thickness) < 1.0e-6
                or abs((value - min(v_values)) - thickness) < 1.0e-6
                for value in v_values))

    def test_angle_arm_puts_the_horizontal_leg_on_top(self):
        """横担角钢：水平肢在顶（固定管子的面），竖直肢在 +v 侧向下。"""
        post = _post()
        origin, axis_z, length, points = _member_world('A', 'arm', post, 500.0)
        side = geom.section_dimensions('A')['B']
        thickness = geom.section_dimensions('A')['t']
        # 顶面（w = 0 局部最高）上存在 y 跨满整肢宽的点。
        top = [point for point in points if abs(point[2] - post.height_mm) < 1.0e-6]
        self.assertTrue(top)
        self.assertGreaterEqual(max(point[1] for point in top)
                                - min(point[1] for point in top), side - thickness)
        # 竖直肢在 +v 侧：v 最大处向下延伸整肢宽。
        self.assertAlmostEqual(max(point[1] for point in points), side / 2.0,
                               places=6)
        lowest = min(point[2] for point in points)
        self.assertAlmostEqual(post.height_mm - lowest, side, places=6)


class VariantTests(unittest.TestCase):
    def test_specifications_match_table_two(self):
        expected = {'A': '∠50×6', 'B': '∠75×7', 'C': '∠100×10',
                    'D': '[14a', 'E': '[20a'}
        self.assertEqual(
            dict((key, geom.specification(key)) for key in geom.VARIANTS),
            expected)

    def test_section_dimensions_resolve(self):
        self.assertAlmostEqual(geom.section_dimensions('A')['B'], 50.0)
        self.assertAlmostEqual(geom.section_dimensions('B')['B'], 75.0)
        self.assertAlmostEqual(geom.section_dimensions('C')['B'], 100.0)
        self.assertAlmostEqual(geom.section_dimensions('D')['H'], 140.0)
        self.assertAlmostEqual(geom.section_dimensions('E')['H'], 200.0)

    def test_channel_width_is_the_section_height(self):
        self.assertEqual(geom.inplane_width('D'), 140.0)
        self.assertEqual(geom.inplane_width('E'), 200.0)
        self.assertTrue(geom.variant_is_channel('D'))
        self.assertTrue(geom.variant_is_channel('E'))
        self.assertFalse(geom.variant_is_channel('A'))

    def test_angle_width_is_the_leg_width(self):
        for key in ('A', 'B', 'C'):
            self.assertEqual(geom.inplane_width(key),
                             geom.section_dimensions(key)['B'])

    def test_only_type_one_is_supported(self):
        for key in sorted(geom.VARIANTS):
            self.assertTrue(geom.variant_supports_type(key, 1))
            self.assertFalse(geom.variant_supports_type(key, 3))
            self.assertFalse(geom.variant_supports_type(key, 'x'))
        self.assertFalse(geom.hanger_type(1))
        self.assertFalse(geom.hanger_type(3))

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            geom.specification('Z')


class LoadTableTests(unittest.TestCase):
    def test_table_one_values(self):
        expected = {
            ('A', 500, 500): 3.0,
            ('A', 1000, 500): 1.0,
            ('B', 500, 1000): 5.0,
            ('B', 1000, 1000): 3.0,
            ('C', 500, 1000): 10.0,
            ('C', 1500, 1000): 2.5,
            ('D', 500, 2000): 12.0,
            ('D', 1500, 2000): 8.0,
            ('E', 500, 2000): 20.0,
            ('E', 2000, 2000): 10.0,
        }
        for (key, height, span), value in expected.items():
            self.assertAlmostEqual(
                geom.allowable_load(key, height, span).value, value, places=9,
                msg='%s H=%d B=%d' % (key, height, span))

    def test_blank_cells_report_no_value(self):
        self.assertIsNone(geom.allowable_load('A', 500, 1000).value)
        self.assertIsNone(geom.allowable_load('B', 500, 1500).value)
        self.assertIsNone(geom.allowable_load('C', 1500, 1500).value)

    def test_height_is_rounded_down_conservatively(self):
        """H=990 按表中 500 取用（偏安全），而不是 1000。"""
        exact = geom.allowable_load('E', 1000.0, 500.0)
        rounded = geom.allowable_load('E', 990.0, 500.0)
        self.assertAlmostEqual(rounded.value, 50.0, places=9)
        self.assertEqual(rounded.used_height_mm, 500)
        self.assertAlmostEqual(exact.value, 40.0, places=9)

    def test_span_rounds_up_to_the_next_column(self):
        self.assertAlmostEqual(
            geom.allowable_load('E', 500.0, 501.0).value, 40.0, places=9)

    def test_out_of_range_is_reported(self):
        below = geom.allowable_load('A', 400.0, 500.0)
        self.assertIsNone(below.value)
        self.assertIn('小于表中最小值', below.message)
        above = geom.allowable_load('A', 1000.0, 2500.0)
        self.assertIsNone(above.value)
        self.assertIn('超出表中上限', above.message)


class NumberingTests(unittest.TestCase):
    def test_number_format(self):
        self.assertEqual(
            geom.build_pipe_rack_number('D8', 1, 'a', 1000.0, 565.0),
            'D8-1-A-1000-565')

    def test_empty_name_produces_no_number(self):
        self.assertEqual(geom.build_pipe_rack_number('', 1, 'A', 1000, 565), '')
        self.assertEqual(geom.build_pipe_rack_number('   ', 1, 'A', 1000, 565), '')

    def test_round_half_up(self):
        self.assertEqual(geom.round_half_up(0.5), 1)
        self.assertEqual(geom.round_half_up(1.5), 2)
        self.assertEqual(geom.round_half_up(2.5), 3)
        self.assertEqual(geom.round_half_up(564.5), 565)
        self.assertEqual(geom.round_half_up(-0.5), 0)

    def test_number_uses_the_derived_arm_length(self):
        arm = geom.arm_length('A', 500.0)
        self.assertAlmostEqual(arm, 630.0, places=9)
        self.assertEqual(
            geom.build_pipe_rack_number('D8', 1, 'A', 1000.0, arm),
            'D8-1-A-1000-630')


if __name__ == '__main__':
    unittest.main()
