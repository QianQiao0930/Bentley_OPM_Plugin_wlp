# -*- coding: utf-8 -*-
"""L 型管架纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

本模块把「图集 L 型管架」的规则集中在一起，供 ``l_pipe_rack.py`` 调用：

* 解析用户绘制的 **L 形智能线**（一段竖直、一段水平，共享拐点）为
  「立杆 + 横担」两个构件；竖直线是立杆轴线，水平线是横担顶面。
* 提供表 3 的子项 A~F 型钢截面表（A~D 为角钢 / 槽钢，E、F 为 H 型钢）。
* 提供表 1 / 表 2 的允许垂直荷载查询。
* 提供型钢截面在「立杆」「横担」两种构件下的本地方位与锚点，使：

  - 立杆：截面重心落在立杆轴线上（用户所选竖直线）；
  - 横担：截面最高面（固定管子的面）落在用户所选水平线上。

* 生成管架编号「名称-类型-子项-H-L」。

型钢截面本身不重复实现，直接复用仓库内 ``型钢截面生成器`` 的数据与几何
模块（``steel_equal_angle_*`` / ``steel_channel_*`` / ``steel_hbeam_*``）。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


import steel_channel_data  # noqa: E402
import steel_channel_geometry  # noqa: E402
import steel_equal_angle_data  # noqa: E402
import steel_equal_angle_geometry  # noqa: E402
import steel_hbeam_data  # noqa: E402
import steel_hbeam_geometry  # noqa: E402
import steel_sweep_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 容差与尺寸限制
# ---------------------------------------------------------------------------

# L 形线两段共用拐点的最大允许间隙（mm）。
CORNER_TOLERANCE_MM = 0.5
# 水平段的倾角上限、竖直段偏离竖直的上限（°）。
HORIZONTAL_TOLERANCE_DEG = 5.0
VERTICAL_TOLERANCE_DEG = 5.0
# 立杆最小高度、横担最小长度（mm）：过短无法形成有效管架。
MIN_POST_HEIGHT_MM = 150.0
MIN_ARM_LENGTH_MM = 150.0
# 荷载表 H 的匹配容差（mm）。
LOAD_HEIGHT_TOLERANCE_MM = 1.0

# 类型 1/2：立杆在下（类型 2 为侧焊，本插件与类型 1 相同）；
# 类型 3/4：立杆在上（吊架；类型 4 为侧焊，与类型 3 相同）。
# 子项 E、F（工字钢）仅对端焊类型 1 和 3 有效（表 3 注）。
ALL_RACK_TYPES = (1, 2, 3, 4)


def hanger_type(rack_type):
    """类型 3/4 为立杆在上的吊架，返回 True。"""
    try:
        return int(rack_type) in (3, 4)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 子项（表 3）与型钢截面
# ---------------------------------------------------------------------------

# family 指向 型钢截面生成器 的型式；profile 为其规格名。
VARIANTS = {
    'A': {
        'family': 'equal_angle',
        'profile': 'L50x50x6',
        'specification': '∠50×6',
        'allowed_types': ALL_RACK_TYPES,
    },
    'B': {
        'family': 'equal_angle',
        'profile': 'L75x75x7',
        'specification': '∠75×7',
        'allowed_types': ALL_RACK_TYPES,
    },
    'C': {
        'family': 'equal_angle',
        'profile': 'L100x100x10',
        'specification': '∠100×10',
        'allowed_types': ALL_RACK_TYPES,
    },
    'D': {
        'family': 'channel',
        'profile': '16a',
        'specification': '[16a',
        'allowed_types': ALL_RACK_TYPES,
    },
    'E': {
        'family': 'hbeam',
        'profile': 'H125x125x6.5x9xr8',
        'specification': 'H125×125×6.5×9',
        'allowed_types': (1, 3),
    },
    'F': {
        'family': 'hbeam',
        'profile': 'H150x150x7x10xr8',
        'specification': 'H150×150×7×10',
        'allowed_types': (1, 3),
    },
}

DEFAULT_VARIANT = 'A'

_FAMILIES = {
    'equal_angle': {
        'data': steel_equal_angle_data,
        'geometry': steel_equal_angle_geometry,
        'builder': 'build_equal_angle_geometry',
    },
    'channel': {
        'data': steel_channel_data,
        'geometry': steel_channel_geometry,
        'builder': 'build_channel_geometry',
    },
    'hbeam': {
        'data': steel_hbeam_data,
        'geometry': steel_hbeam_geometry,
        'builder': 'build_hbeam_geometry',
    },
}

def variant_choices():
    """返回 ``(代号, 显示文本)``，按代号排序，供下拉框使用。"""
    return tuple((key, variant_label(key)) for key in sorted(VARIANTS))


def variant_label(variant_key):
    variant = _variant(variant_key)
    return '%s  |  %s' % (variant_key, variant['specification'])


def _variant(variant_key):
    try:
        return VARIANTS[variant_key]
    except KeyError:
        raise ValueError('未知子项：%s。' % variant_key)


def section_dimensions(variant_key):
    """返回所选子项的型钢截面尺寸字典（mm）。"""
    variant = _variant(variant_key)
    family = _FAMILIES[variant['family']]
    return family['data'].get_section(variant['profile'])


def specification(variant_key):
    return _variant(variant_key)['specification']


def allowed_rack_types(variant_key):
    return tuple(_variant(variant_key)['allowed_types'])


def variant_supports_type(variant_key, rack_type):
    try:
        rack_type = int(rack_type)
    except (TypeError, ValueError):
        return False
    return rack_type in allowed_rack_types(variant_key)


def variant_is_h_section(variant_key):
    return _variant(variant_key)['family'] == 'hbeam'


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------
#
# 统一用支架局部基 (u, v, w) 描述：u = 所选水平线方向（横担方向），
# v = Z × u（水平法向），w = Z（竖直向上）；原点取 L 形线的拐点。
#
# 截面 local (x, y) 经坐标架映射到世界：world = origin + x*axis_x + y*axis_y，
# 沿 axis_z 扫掠。各构件给出：
#   * member_section_params  —— 截面外角 / 重心等锚点在 local 的落点；
#   * member_axes            —— axis_x / axis_y / axis_z 在 (u, v, w) 下的分量；
#   * member_origin_length   —— 扫掠起点（相对拐点，mm）与扫掠长度。
#
# 角钢（A/B/C，详图 X）做法：
#   横担角钢开口朝向立杆侧：水平肢在上作固定管子的面，竖直肢靠立杆一侧
#   向下；横担后端（水平肢与竖直肢同端）超出立杆背面 ARM_BACK_OVERHANG_MM。
#   立杆角钢一条肢平贴在横担竖直肢的【内侧（开口侧）】面上，立杆重心仍落在
#   所选竖直线上；立杆另一条肢沿横担方向展开。
#
# 槽钢（D，详图 X）做法：
#   两个槽钢【背靠背】：腹板竖直、外背相贴，开口朝向相反。
#   横担开口朝 +v（法兰朝管侧），顶面为上面法兰外表面；立杆开口朝 -v。
#   公共腹板背面取在所选竖直线上（即拐点）；横担后端超出立杆 -u 边缘
#   ARM_BACK_OVERHANG_MM。立杆在 u 向以竖直线居中，顶面低于横担顶面一个
#   法兰厚 tf（图中 10）。
#
# H 型钢（E/F，详图 X）做法：
#   横担正立（腹板竖直、H 向竖立），顶面为上面翼缘外表面、宽度方向居中；
#   立杆正立，重心在竖直线 (u, v) 原点，腹板位于支架竖直平面内。
#   立杆顶面顶焊在横担【下翼缘下表面】（“另一个面”），即立杆顶 = -H；
#   横担后端超出立杆 -u 边缘 ARM_BACK_OVERHANG_MM。

# 横担后端超出立杆边缘（背面 / 最外侧）的固定长度（mm）。
ARM_BACK_OVERHANG_MM = 15.0


def member_section_params(variant_key, member_kind, hanger=False):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。"""
    variant = _variant(variant_key)
    section = section_dimensions(variant_key)
    family = variant['family']
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")

    if family == 'equal_angle':
        z0 = float(section['Z0'])
        if member_kind == 'post':
            if hanger:
                # 吊架立杆角钢与横担竖直肢【背靠背】：外角由 origin 定位。
                return 'outer_corner', (0.0, 0.0)
            # 外角置于 (-Z0, -Z0)：两条肢分别沿 +u、+v 展开，截面重心
            # 恰好落在竖直线（拐点）上。
            return 'outer_corner', (-z0, -z0)
        # 横担外角置于 (vc, 0)，vc = -Z0 - t：竖直肢的 +v 面正是立杆贴合面，
        # 水平肢顶面落在 y=0（即所选水平线上）。
        return 'outer_corner', (-z0 - float(section['t']), 0.0)

    if family == 'channel':
        # 槽钢背靠背：外角（腹板外背 / 下法兰外角）置于 local 原点，
        # 由 member_axes / member_origin_length 定出世界位置。
        return 'lower_left', (0.0, 0.0)

    if member_kind == 'post':
        # H 型钢立杆：重心落在竖直线上。
        return 'centroid', (0.0, 0.0)
    # 热轧 H 型钢正立：顶面为上面翼缘外表面、宽度方向居中。
    return 'geometric_center', (0.0, -float(section['H']) / 2.0)


def member_axes(variant_key, member_kind, hanger=False):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。"""
    family = _variant(variant_key)['family']
    if family == 'equal_angle':
        if member_kind == 'post':
            if hanger:
                # 背靠背：+x -> +u、+y -> -v（开口朝 +u, -v），沿 -w 由顶向下扫掠
                # 到横担竖直肢范围内。
                return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0)
            # +x -> +u，+y -> +v，沿 +w 向上扫掠。
            return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
        # +x -> +v（水平肢），+y -> -w（竖直肢向下）；沿 -u 由横担远端向后扫掠。
        return (0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0)

    if family == 'channel':
        if member_kind == 'post':
            # 开口朝 -v：+x -> -v，+y -> +u，沿 +w 向上扫掠。
            return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
        # 开口朝 +v：+x -> +v，+y -> -w；沿 -u 由横担远端向后扫掠。
        return (0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (-1.0, 0.0, 0.0)

    if member_kind == 'post':
        # H 型钢：+x -> -v，+y -> +u，沿 +w 向上扫掠。
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    # H 型钢：+x -> +v，+y -> +w，沿 +u 扫掠。
    return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def member_origin_length(variant_key, member_kind, post_height_mm, arm_length_mm,
                         hanger=False):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对拐点）与扫掠长度。"""
    variant = _variant(variant_key)
    family = variant['family']
    section = section_dimensions(variant_key)
    post_height_mm = float(post_height_mm)
    arm_length_mm = float(arm_length_mm)

    if member_kind == 'post':
        if family == 'equal_angle':
            if hanger:
                # 背靠背：腹板背（此处为竖直肢外皮）取横担竖直肢 +v 面外侧；
                # 下段向下伸入竖直肢范围（到 -B）。
                z0 = float(section['Z0'])
                thickness = float(section['t'])
                return ((-z0, -z0 - thickness, post_height_mm),
                        post_height_mm + float(section['B']))
            # 立杆顶面贴横担水平肢下表面（w=-t），故长度扣除一个肢厚。
            return (0.0, 0.0, -post_height_mm), post_height_mm - float(section['t'])
        if family == 'channel':
            half_h = float(section['H']) / 2.0
            if hanger:
                # 背靠背：腹板背在 v=0，u 向以竖直线居中；
                # 下段向下伸入横担腹板范围（到 -H）。
                return ((-half_h, 0.0, -float(section['H'])),
                        post_height_mm + float(section['H']))
            # 立杆腹板背在 v=0，u 向以竖直线居中；顶面低于横担顶面一个 tf。
            return ((-half_h, 0.0, -post_height_mm),
                    post_height_mm - float(section['tf']))
        if hanger:
            # H 型钢立杆：下端顶焊在横担上翼缘上表面（w=0），向上延伸。
            return (0.0, 0.0, 0.0), post_height_mm
        # H 型钢立杆：重心在 (u, v) 原点；顶面顶在横担下翼缘下表面
        # （w=-H），故长度扣除横担高度 H。
        return ((0.0, 0.0, -post_height_mm),
                post_height_mm - float(section['H']))

    # 横担（吊架与类型 1/2 相同：顶面在水平线上、朝上承管）
    if family == 'equal_angle':
        z0 = float(section['Z0'])
        # 从水平线远端（u=arm_length）沿 -u 向后扫掠；后端超出立杆背面 15 mm。
        return ((arm_length_mm, 0.0, 0.0),
                arm_length_mm + z0 + ARM_BACK_OVERHANG_MM)
    if family == 'channel':
        # 腹板背在 v=0；后端超出立杆 -u 边缘 15 mm（立杆 -u 边缘 = -H/2）。
        half_h = float(section['H']) / 2.0
        return ((arm_length_mm, 0.0, 0.0),
                arm_length_mm + half_h + ARM_BACK_OVERHANG_MM)
    # H 型钢横担：正立、宽度方向以水平线居中；从后端沿 +u 扫掠，
    # 后端超出立杆 -u 边缘 15 mm（立杆 -u 边缘 = -H/2）。
    half_h = float(section['H']) / 2.0
    return ((-half_h - ARM_BACK_OVERHANG_MM, 0.0, 0.0),
            arm_length_mm + half_h + ARM_BACK_OVERHANG_MM)


def arm_axis_y_is_up(variant_key):
    """横担截面 local +y 是否指向世界 +Z（供纯几何测试与说明使用）。"""
    return member_axes(variant_key, 'arm')[1][2] > 0.0


def member_geometry(variant_key, member_kind, scale=1.0, hanger=False):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。

    返回 型钢截面生成器 的 geometry 对象，其 ``segments`` 为线 / 弧段，
    与 ``steel_sweep_geometry.sample_segment`` 兼容。
    """
    variant = _variant(variant_key)
    family = _FAMILIES[variant['family']]
    geometry_module = family['geometry']
    section = family['data'].get_section(variant['profile'])
    scaled = geometry_module.scale_section(section, float(scale))
    mode, insertion_point = member_section_params(
        variant_key, member_kind, hanger)
    point = geometry_module.Point2d(
        insertion_point[0] * float(scale), insertion_point[1] * float(scale))
    builder = getattr(geometry_module, family['builder'])
    return builder(scaled, mode, point)


def sample_member(variant_key, member_kind, frame, scale=1.0, hanger=False):
    """按坐标架把构件截面采样为世界点，供纯几何测试使用。"""
    geometry = member_geometry(variant_key, member_kind, scale, hanger)
    return tuple(
        steel_sweep_geometry.sample_segment(segment, frame)
        for segment in geometry.segments
    )


# ---------------------------------------------------------------------------
# L 形智能线解析
# ---------------------------------------------------------------------------

LShape = namedtuple(
    'LShape',
    'post_end corner arm_end post_height_mm arm_length_mm heading_deg is_hanger')


def parse_l_shape(pieces_mm, hanger=False):
    """把所选元素的折线（mm 点列）解析为 L 形，并校验合规性。

    ``pieces_mm`` 为若干折线，每条折线是其顶点 ``(x, y, z)`` 的序列。要求
    展开后恰好为两段直线：一段竖直（立杆轴线）、一段水平（横担顶面），
    两者共用拐点。

    ``hanger=False``（类型 1/2）：竖直段在拐点**下方**（立杆在下、横担在上）；
    ``hanger=True``（类型 3/4，吊架）：竖直段在拐点**上方**（立杆在上）。
    """
    segments = _flatten_segments(pieces_mm)
    if len(segments) != 2:
        raise ValueError(
            '请选择由两段直线组成的 L 形线（一竖一横），当前为 %d 段。' % len(segments))

    (a0, a1), (b0, b1) = segments
    shared = _shared_corner(a0, a1, b0, b1)
    if shared is None:
        raise ValueError('L 形线的两段没有共用拐点，请重新绘制 L 形折线。')
    corner, first_end, second_end = shared

    first_dir = _sub(first_end, corner)
    second_dir = _sub(second_end, corner)
    first_vertical = _is_vertical(first_dir)
    first_horizontal = _is_horizontal(first_dir)
    second_vertical = _is_vertical(second_dir)
    second_horizontal = _is_horizontal(second_dir)

    if first_vertical and second_horizontal:
        post_end, arm_end = first_end, second_end
    elif second_vertical and first_horizontal:
        post_end, arm_end = second_end, first_end
    else:
        raise ValueError(
            'L 形线必须由一段竖直（立杆）和一段水平（横担）组成，'
            '且两段大致垂直；请检查所选折线。')

    if hanger:
        if post_end[2] - corner[2] <= 0.0:
            raise ValueError(
                '类型 3/4（吊架）要求立杆在上：竖直段应在拐点上方。')
        post_height = post_end[2] - corner[2]
    else:
        if corner[2] - post_end[2] <= 0.0:
            raise ValueError(
                '类型 1/2 要求立杆在下：竖直段应在拐点下方。')
        post_height = corner[2] - post_end[2]

    if post_height < MIN_POST_HEIGHT_MM:
        raise ValueError('立杆高 H=%.1f mm 过短，要求 ≥ %.0f mm。'
                         % (post_height, MIN_POST_HEIGHT_MM))

    run_x = arm_end[0] - corner[0]
    run_y = arm_end[1] - corner[1]
    arm_length = math.hypot(run_x, run_y)
    if arm_length < MIN_ARM_LENGTH_MM:
        raise ValueError('横担长 L=%.1f mm 过短，要求 ≥ %.0f mm。'
                         % (arm_length, MIN_ARM_LENGTH_MM))

    return LShape(
        post_end=tuple(float(value) for value in post_end),
        corner=tuple(float(value) for value in corner),
        arm_end=tuple(float(value) for value in arm_end),
        post_height_mm=float(post_height),
        arm_length_mm=float(arm_length),
        heading_deg=math.degrees(math.atan2(run_y, run_x)),
        is_hanger=bool(hanger),
    )


def _flatten_segments(pieces_mm):
    segments = []
    for piece in pieces_mm:
        points = [tuple(float(value) for value in point) for point in piece]
        if len(points) < 2:
            raise ValueError('所选元素包含无效的折线段。')
        for index in range(len(points) - 1):
            segments.append((points[index], points[index + 1]))
    return segments


def _shared_corner(a0, a1, b0, b1):
    for end_a, other_a in ((a0, a1), (a1, a0)):
        for end_b, other_b in ((b0, b1), (b1, b0)):
            if _distance(end_a, end_b) <= CORNER_TOLERANCE_MM:
                return _midpoint(end_a, end_b), other_a, other_b
    return None


def _is_vertical(vector):
    length = _norm(vector)
    if length <= 1.0e-9:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(vector[2]) / length)))
    return angle <= VERTICAL_TOLERANCE_DEG


def _is_horizontal(vector):
    length = _norm(vector)
    if length <= 1.0e-9:
        return False
    angle = math.degrees(math.asin(min(1.0, abs(vector[2]) / length)))
    return angle <= HORIZONTAL_TOLERANCE_DEG


def _sub(left, right):
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _norm(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def _distance(left, right):
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _midpoint(left, right):
    return tuple((left[index] + right[index]) / 2.0 for index in range(3))


# ---------------------------------------------------------------------------
# 允许垂直荷载（表 1 / 表 2，单位 kN；None 表示表格中的「—」）
# ---------------------------------------------------------------------------

LOAD_TABLE = {
    'A': {
        500: {250: 0.3, 500: None},
        1000: {250: 0.15, 500: None},
    },
    'B': {
        500: {250: 1.0, 500: None},
        1000: {250: 0.7, 500: None},
        1500: {250: 0.5, 500: None},
    },
    'C': {
        500: {250: 3.0, 500: 2.0},
        1000: {250: 1.6, 500: 1.0},
        1500: {250: 1.2, 500: 0.8},
        2000: {250: 0.8, 500: 0.6},
    },
    'D': {
        500: {250: 8.0, 500: 6.0},
        1000: {250: 5.0, 500: 4.0},
        1500: {250: 3.5, 500: 3.0},
        2000: {250: 2.5, 500: 2.0},
        2500: {250: 1.5, 500: 1.2},
        3000: {250: 1.0, 500: 0.5},
    },
    'E': {
        500: {250: 15.0, 500: 8.0, 750: 5.0},
        1000: {250: 10.0, 500: 5.0, 750: 3.0},
        1500: {250: 6.0, 500: 3.5, 750: 2.0},
        2000: {250: 4.0, 500: 2.5, 750: 1.5},
        2500: {250: 3.0, 500: 2.0, 750: 1.0},
        3000: {250: 2.0, 500: 1.0, 750: 0.7},
    },
    'F': {
        500: {250: 25.0, 500: 15.0, 750: 8.0},
        1000: {250: 15.0, 500: 10.0, 750: 6.0},
        1500: {250: 12.0, 500: 6.0, 750: 4.0},
        2000: {250: 8.0, 500: 5.0, 750: 3.0},
        2500: {250: 6.0, 500: 4.0, 750: 2.0},
        3000: {250: 4.0, 500: 3.0, 750: 1.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm message')


def allowable_load(variant_key, height_mm, width_mm):
    """按表 1 / 表 2 查允许垂直荷载。

    ``height_mm`` 为立杆高 H；``width_mm`` 为管架水平参数 B。H 取不超过输入
    的最大表列值（偏安全）；B 取不小于输入的最小列。返回 :class:`LoadResult`，
    查不到时 ``value`` 为 None 并在 ``message`` 中说明。
    """
    variant_key = str(variant_key).upper()
    table = LOAD_TABLE.get(variant_key)
    if table is None:
        return LoadResult(None, None, '子项 %s 无荷载表。' % variant_key)

    heights = sorted(table)
    usable = [h for h in heights if h <= float(height_mm) + LOAD_HEIGHT_TOLERANCE_MM]
    if not usable:
        return LoadResult(
            None, None,
            'H=%.0f mm 小于表中最小值 %d mm。' % (height_mm, heights[0]))
    used_height = usable[-1]
    row = table[used_height]

    columns = sorted(row)
    chosen = None
    for column in columns:
        if float(width_mm) <= column:
            chosen = column
            break
    if chosen is None:
        return LoadResult(
            None, used_height,
            'B=%.0f mm 超出表中上限 %d mm。' % (width_mm, columns[-1]))
    value = row[chosen]
    if value is None:
        return LoadResult(
            None, used_height,
            '子项 %s、H=%d、B≤%d 一栏表中为空（—）。'
            % (variant_key, used_height, chosen))
    return LoadResult(
        float(value), used_height,
        '按 H=%d mm、B≤%d mm 取用。' % (used_height, chosen))


# ---------------------------------------------------------------------------
# 管架编号
# ---------------------------------------------------------------------------

def round_half_up(value):
    """四舍五入到整数（Python 的 round 为「银行家舍入」，不可用于编号）。"""
    return int(math.floor(float(value) + 0.5))


def build_pipe_rack_number(name, rack_type, variant_key, height_mm, arm_mm):
    """管架编号「名称-类型-子项-H-L」；名称为空时返回空串（不附加编号）。"""
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%d-%s-%d-%d' % (
        label, int(rack_type), str(variant_key).upper(),
        round_half_up(height_mm), round_half_up(arm_mm))
