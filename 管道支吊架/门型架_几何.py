# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``门型架（角钢和槽钢）.py`` 等插件
# ``import`` 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中
# 直接加载运行。
# =============================================================================
"""门型架纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

本模块把「图 C.4-8 门形 / 倒门形架（角钢和槽钢）」类型 1 的规则集中在一起，
供 ``门型架（角钢和槽钢）.py`` 调用：

* 解析用户绘制的 **竖直线**（立杆轴线）为立柱高度 H；水平布置方向由面板的
  「朝向」给定 —— 竖直线本身不能确定门架平面。
* 提供表 2 的子项 A~E 型钢截面表（A~C 为角钢 / D、E 为槽钢），与表 1 的
  允许垂直荷载查询。
* 给出立柱与横担的布置：**B 为两立柱净距**（内缘到内缘），横担**横跨两根立柱
  的顶面**、两端各超出立柱外缘 15 mm，故横担长 L = B + 2W + 30
  （W 为立柱在横担长度方向的截面宽度）。

型钢截面本身不重复实现，直接复用仓库内 ``型钢截面生成器`` 的数据与几何模块
（``steel_equal_angle_*`` / ``steel_channel_*``）。

布置约定（局部基 u-v-w，原点取所选竖直线的下端）：

    u = 门架平面内的水平方向（面板「朝向」；也是横担长度方向）
    v = Z × u（水平法向，管道轴线方向）
    w = Z（竖直向上）

* 立柱：截面在 u-v 平面内，沿 +w 由下向上扫掠；**外接矩形中心**落在立杆轴线
  上，故内缘恰好在轴线 ±W/2 处，B 即为两内缘之间的净距。立柱**非通长**
  —— 顶端止于 ``H - 翼缘厚 - 10``，比横担水平肢 / 上翼缘低 10 mm 留作施焊。
* 横担：截面在 v-w 平面内，沿 +u 扫掠；顶面（固定管子的面）落在 w = H，
  且横跨两根立柱。
* 立柱与横担**背靠背**：横担的竖直肢贴在立柱的 u-w 平面肢外侧，立柱该肢
  平贴横担竖直肢的**内侧（开口侧）面**（与 L 型管架角钢同做法，见
  :func:`post_v_offset`），力经该贴合焊缝下传（见
  :func:`weld_contact_length`）；槽钢子项的立柱腹板贴横担腹板背面、两腹板
  背靠背，同样不做顶面承压。
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
import steel_sweep_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 容差与尺寸限制
# ---------------------------------------------------------------------------

# 所选竖直线偏离竖直方向的上限（°）。
VERTICAL_TOLERANCE_DEG = 5.0
# 立杆最小高度、最小净距（mm）：过短 / 过窄无法形成有效门架。
MIN_POST_HEIGHT_MM = 150.0
MIN_SPAN_MM = 50.0
# 荷载表 H 的匹配容差（mm）。
LOAD_HEIGHT_TOLERANCE_MM = 1.0

# 类型 1：正门形架（立杆在下、横担在上）。
# 类型 3/4 为倒门形架（吊架），留待后续实现，此处不接受。
ALL_RACK_TYPES = (1,)
HANGER_RACK_TYPES = ()


def hanger_type(rack_type):
    """本插件仅实现类型 1；倒门形架（立杆在上）尚未支持，恒为 False。"""
    try:
        return int(rack_type) in HANGER_RACK_TYPES
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 子项（表 2）与型钢截面
# ---------------------------------------------------------------------------

# family 指向 型钢截面生成器 的型式；profile 为其规格名。
VARIANTS = {
    'A': {
        'family': 'equal_angle',
        'profile': 'L50x50x6',
        'specification': '∠50×6',
    },
    'B': {
        'family': 'equal_angle',
        'profile': 'L75x75x7',
        'specification': '∠75×7',
    },
    'C': {
        'family': 'equal_angle',
        'profile': 'L100x100x10',
        'specification': '∠100×10',
    },
    'D': {
        'family': 'channel',
        'profile': '14a',
        'specification': '[14a',
    },
    'E': {
        'family': 'channel',
        'profile': '20a',
        'specification': '[20a',
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
    return tuple(ALL_RACK_TYPES)


def variant_supports_type(variant_key, rack_type):
    _variant(variant_key)
    try:
        rack_type = int(rack_type)
    except (TypeError, ValueError):
        return False
    return rack_type in ALL_RACK_TYPES


def variant_is_channel(variant_key):
    return _variant(variant_key)['family'] == 'channel'


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------

# 横担两端各超出立柱外缘的固定长度（mm）。与图上 15 一致，也与 L 型管架
# ``ARM_BACK_OVERHANG_MM``（横担后端超出立杆外缘）取同一做法。
ARM_BACK_OVERHANG_MM = 15.0

# 角钢立柱最高点比横担水平肢低出的焊接间隙（mm）：立柱非通长，顶端留出这一段
# 便于施焊，立柱与横担靠「立柱肢 ↔ 横担竖直肢」的贴合焊缝传力。
WELD_GAP_MM = 10.0

# 截面外接矩形中心：角钢与槽钢的几何模块都提供 geometric_center 插入点，
# 使外接矩形中心恰落在截面局部原点上。
_INSERTION_MODE = 'geometric_center'
_INSERTION_POINT = (0.0, 0.0)


def section_box(variant_key):
    """返回截面外接矩形的 ``(x_extent, y_extent)``（mm，截面局部坐标）。"""
    variant = _variant(variant_key)
    section = section_dimensions(variant_key)
    if variant['family'] == 'equal_angle':
        side = float(section['B'])
        return (side, side)
    return (float(section['B']), float(section['H']))


def inplane_width(variant_key):
    """立柱在横担长度方向（u）上的宽度 W（mm）。

    立柱截面局部 +y 映射到 ±u，故 W 取截面的 y 向尺寸：角钢为肢宽 B，
    槽钢为型钢高度 H（腹板竖直、在门架平面内）。
    """
    return section_box(variant_key)[1]


def beam_depth(variant_key):
    """横担在竖直方向（w）上的厚度（mm）。

    横担截面局部 +y 映射到 ±w，故深度同样取截面的 y 向尺寸。
    """
    return section_box(variant_key)[1]


def beam_flange_thickness(variant_key):
    """横担「水平肢 / 上翼缘」的厚度（mm）。

    角钢为肢厚 ``t``，槽钢为翼缘厚 ``tf``；立柱顶端据此留出焊接间隙。
    """
    section = section_dimensions(variant_key)
    return float(section['t'] if 't' in section else section['tf'])


def beam_span(variant_key, span_mm):
    """返回横担的 ``(u_start_mm, length_mm)``。

    横担横跨两根立柱的顶面、两端各超出立柱外缘 15 mm，故
    ``length = B + 2W + 30``。
    """
    width = inplane_width(variant_key)
    return (-width / 2.0 - ARM_BACK_OVERHANG_MM,
            arm_length(variant_key, span_mm))


def arm_length(variant_key, span_mm):
    """横担下料长度 L = B + 2W + 30（mm）。"""
    return (float(span_mm) + 2.0 * inplane_width(variant_key)
            + 2.0 * ARM_BACK_OVERHANG_MM)


def post_axis_offset(variant_key, span_mm, side='left'):
    """立柱轴线相对所选竖直线的 u 偏移（mm）。

    左立柱轴线即所选竖直线（偏移 0）；右立柱内缘在 ``W/2 + B``，故轴线在
    ``B + W`` 处。
    """
    if side == 'left':
        return 0.0
    if side == 'right':
        return float(span_mm) + inplane_width(variant_key)
    raise ValueError("side 只能是 'left' 或 'right'。")


def post_v_offset(variant_key):
    """立柱截面在 v 方向的偏移（mm），使立柱与横担**背靠背**。

    角钢立柱的 u-w 平面肢须与横担竖直肢**背面相贴**（两角钢背靠背）：
    横担截面绕 v 居中，其竖直肢在 ``v ∈ [W/2 - t, W/2]``，背面（外角侧）
    在 ``v = W/2``；立柱该肢的背面同样落在 ``v = W/2``，故立柱截面整体位于
    ``v ∈ [W/2, W/2 + W]``，即偏移 ``+W``（配合 :func:`member_axes` 中角钢
    立柱的镜像轴系）。

    槽钢立柱同理：横担腹板在 ``v ∈ [-B/2, -B/2 + tw]``、背面朝 -v，立柱沿 -v
    平移一个翼缘宽 ``B`` 后，其腹板落在 ``v ∈ [-B/2 - tw, -B/2]``、背面朝 +v，
    两块腹板背面在 ``v = -B/2`` 相贴，翼缘各自朝外。
    """
    variant = _variant(variant_key)
    if variant['family'] == 'equal_angle':
        return inplane_width(variant_key)
    return -section_box(variant_key)[0]


def post_length(variant_key, height_mm):
    """立柱下料长度（mm）。

    两类子项都**非通长**：最高点比横担的水平肢 / 上翼缘低 ``WELD_GAP_MM``，
    即 ``H - 翼缘厚 - WELD_GAP_MM``，留出的间隙用于施焊；横担不落在立柱顶面
    上，力由「立柱腹板 / 肢 ↔ 横担腹板 / 竖直肢」的贴合焊缝传走。
    """
    height_mm = float(height_mm)
    thickness = beam_flange_thickness(variant_key)
    length = height_mm - thickness - WELD_GAP_MM
    if length <= 0.0:
        raise ValueError(
            '子项 %s 的门架高 H=%.1f mm 过小：扣除翼缘厚 %.1f 与焊接间隙 '
            '%.0f 后立柱长度为负。'
            % (variant_key, height_mm, thickness, WELD_GAP_MM))
    return length


def weld_contact_length(variant_key):
    """角钢立柱肢与横担竖直肢的贴合（焊缝）段高度（mm）。

    横担的竖直肢 / 腹板自横担顶面下伸 ``beam_depth``，立柱顶面止于
    ``H - 翼缘厚 - WELD_GAP_MM``，故搭接高度为
    ``beam_depth - 翼缘厚 - WELD_GAP_MM``。
    """
    contact = (beam_depth(variant_key) - beam_flange_thickness(variant_key)
               - WELD_GAP_MM)
    if contact <= 0.0:
        raise ValueError('子项 %s 的立柱与横担腹板无有效搭接长度。'
                         % variant_key)
    return contact


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。

    两类构件都用「外接矩形中心」作插入点并置于截面局部原点，于是：
    立柱内 / 外缘恰在轴线 ±W/2，横担截面绕 v 居中。
    """
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return (_INSERTION_MODE, _INSERTION_POINT)


def member_axes(variant_key, member_kind, mirror_u=False):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    各坐标架都保持右手系（axis_x × axis_y = axis_z），使闭合截面沿 axis_z
    扫掠时法向与扫掠方向一致。

    ``mirror_u=True`` 把截面在 u 方向镜像（相对该构件自身轴线），用于右立柱：
    两根立柱由此成为镜像对称，**开口都朝门架外**。槽钢截面本身关于 u 中心线
    对称，镜像不改变其形状。
    """
    variant = _variant(variant_key)
    family = variant['family']
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")

    if member_kind == 'post':
        if family == 'equal_angle':
            if mirror_u:
                # 镜像立柱（右柱）：截面的 x -> +u、y -> +v，开口朝 (+u, +v)，
                # 即外角/回折肢落在轴线外侧。
                return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
            # 立柱（左柱）：截面的 x -> +v、y -> -u，开口朝 (-u, +v)。
            # 其 u-w 平面肢落在 +v 端，与横担竖直肢背面相贴（见 post_v_offset）。
            return (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
        # 槽钢立柱：截面的 x -> -v、y -> +u，沿 +w 向上扫掠。
        # 腹板在门架平面内（+v 侧）、开口朝 -v；横担腹板在 -v 侧，两腹板本身
        # 即背靠背，无需镜像或偏移。
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)

    if family == 'equal_angle':
        # 横担角钢：x -> -v、y -> -w，沿 +u 扫掠。竖直肢在 +v 侧向下，
        # 水平肢在顶部、其上表面即固定管子的面（w = 0 处）。
        return (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    # 横担槽钢：x -> +v、y -> +w，沿 +u 扫掠。腹板竖直（在 u-w 平面内）且
    # 位于 -v 侧，开口朝 +v，顶面为上面翼缘外表面。
    return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def post_opening_direction(variant_key, mirror_u=False):
    """立柱角钢开口的朝向，返回 (u, v) 分量（未归一化，取自截面内角方向）。

    两根立柱互为镜像、开口都朝门架外时，分别为 ``(-1, +1)``（左柱，朝 -u）
    与 ``(+1, +1)``（右柱，朝 +u）。槽钢截面无此朝向概念，返回 ``(0, 0)``。
    """
    variant = _variant(variant_key)
    if variant['family'] != 'equal_angle':
        return (0.0, 0.0)
    axis_x, axis_y, _axis_z = member_axes(variant_key, 'post', mirror_u)
    return (axis_x[0] + axis_y[0], axis_x[1] + axis_y[1])


def member_origin_length(variant_key, member_kind, height_mm, span_mm,
                         post_axis_u=0.0):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对所选线下端）与长度。

    立柱由基座（w = 0）向上扫掠；长度见 :func:`post_length`（角钢非通长，
    顶端留 10 mm 焊接间隙），并按 :func:`post_v_offset` 在 v 方向平移使两者
    背靠背；横担自左端（左立柱外缘外 15 mm）沿 +u 扫掠 L，截面中心置于
    ``w = H - 深度/2``。
    """
    _variant(variant_key)
    height_mm = float(height_mm)
    depth = beam_depth(variant_key)

    if member_kind == 'post':
        # v 向偏移使立柱的 u-w 平面肢与横担竖直肢背靠背相贴（角钢）。
        return ((float(post_axis_u), post_v_offset(variant_key), 0.0),
                post_length(variant_key, height_mm))
    if member_kind == 'arm':
        u_start, length = beam_span(variant_key, span_mm)
        return ((u_start, 0.0, height_mm - depth / 2.0), length)
    raise ValueError("member_kind 只能是 'post' 或 'arm'。")


def member_geometry(variant_key, member_kind, scale=1.0):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。

    返回 型钢截面生成器 的 geometry 对象，其 ``segments`` 为线 / 弧段，
    与 ``steel_sweep_geometry.sample_segment`` 兼容。
    """
    variant = _variant(variant_key)
    family = _FAMILIES[variant['family']]
    geometry_module = family['geometry']
    section = family['data'].get_section(variant['profile'])
    scaled = geometry_module.scale_section(section, float(scale))
    mode, insertion_point = member_section_params(variant_key, member_kind)
    point = geometry_module.Point2d(
        insertion_point[0] * float(scale), insertion_point[1] * float(scale))
    builder = getattr(geometry_module, family['builder'])
    return builder(scaled, mode, point)


def sample_member(variant_key, member_kind, frame, scale=1.0):
    """按坐标架把构件截面采样为世界点，供纯几何测试使用。"""
    geometry = member_geometry(variant_key, member_kind, scale)
    return tuple(
        steel_sweep_geometry.sample_segment(segment, frame)
        for segment in geometry.segments
    )


# ---------------------------------------------------------------------------
# 竖直线的解析
# ---------------------------------------------------------------------------

VerticalPost = namedtuple('VerticalPost', 'base top height_mm')


def parse_vertical_post(pieces_mm):
    """把所选元素的折线（mm 点列）解析为立杆轴线，并校验合规性。

    ``pieces_mm`` 为若干折线，每条折线是其顶点 ``(x, y, z)`` 的序列。要求
    展开后恰好为一段直线，且该段大致竖直。
    """
    segments = _flatten_segments(pieces_mm)
    if len(segments) != 1:
        raise ValueError(
            '请选择一条竖直线段（立杆轴线），当前为 %d 段。' % len(segments))

    first, second = segments[0]
    direction = _sub(second, first)
    if not _is_vertical(direction):
        raise ValueError('所选线段不是竖直线；请选择一条竖直的线段作为立杆轴线。')

    if second[2] >= first[2]:
        base, top = first, second
    else:
        base, top = second, first
    height = top[2] - base[2]
    if height < MIN_POST_HEIGHT_MM:
        raise ValueError('立杆高 H=%.1f mm 过短，要求 ≥ %.0f mm。'
                         % (height, MIN_POST_HEIGHT_MM))

    return VerticalPost(
        base=tuple(float(value) for value in base),
        top=tuple(float(value) for value in top),
        height_mm=float(height),
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


def _is_vertical(vector):
    length = _norm(vector)
    if length <= 1.0e-9:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(vector[2]) / length)))
    return angle <= VERTICAL_TOLERANCE_DEG


def _sub(left, right):
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _norm(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


# ---------------------------------------------------------------------------
# 允许垂直荷载（表 1，单位 kN；None 表示表格中的「—」）
# ---------------------------------------------------------------------------

LOAD_TABLE = {
    'A': {
        500: {500: 3.0, 1000: None, 1500: None, 2000: None},
        1000: {500: 1.0, 1000: None, 1500: None, 2000: None},
    },
    'B': {
        500: {500: 10.0, 1000: 5.0, 1500: None, 2000: None},
        1000: {500: 6.0, 1000: 3.0, 1500: None, 2000: None},
    },
    'C': {
        500: {500: 20.0, 1000: 10.0, 1500: None, 2000: None},
        1000: {500: 10.0, 1000: 5.0, 1500: None, 2000: None},
        1500: {500: 5.0, 1000: 2.5, 1500: None, 2000: None},
    },
    'D': {
        500: {500: 30.0, 1000: 20.0, 1500: 15.0, 2000: 12.0},
        1000: {500: 20.0, 1000: 15.0, 1500: 12.0, 2000: 10.0},
        1500: {500: 15.0, 1000: 12.0, 1500: 10.0, 2000: 8.0},
    },
    'E': {
        500: {500: 50.0, 1000: 40.0, 1500: 30.0, 2000: 20.0},
        1000: {500: 40.0, 1000: 30.0, 1500: 20.0, 2000: 15.0},
        1500: {500: 30.0, 1000: 20.0, 1500: 15.0, 2000: 12.0},
        2000: {500: 20.0, 1000: 15.0, 1500: 12.0, 2000: 10.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm message')


def allowable_load(variant_key, height_mm, span_mm):
    """按表 1 查允许垂直荷载。

    ``height_mm`` 为立杆高 H；``span_mm`` 为两立柱净距 B。H 取不超过输入的
    最大表列值（偏安全）；B 取不小于输入的最小列。返回 :class:`LoadResult`，
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
        if float(span_mm) <= column:
            chosen = column
            break
    if chosen is None:
        return LoadResult(
            None, used_height,
            'B=%.0f mm 超出表中上限 %d mm。' % (span_mm, columns[-1]))
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
