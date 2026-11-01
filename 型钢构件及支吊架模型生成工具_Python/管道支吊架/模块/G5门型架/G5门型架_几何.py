# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``G5-[地面上生根的门型架].py`` 等插件
# ``import`` 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中
# 直接加载运行。
# =============================================================================
"""G5 地面上生根的门型架：纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

对应「地面上生根的门型架」（两立柱 + 顶部横担，构件 A 为角钢或 H 型钢）：

* 解析用户绘制的 **竖直线**（**整组门型架的中心线**）：
  **上端** ＝ 管底标高 ＝ 横担顶面（固定管子的面），**下端** ＝ 地面
  （现场灌浆梯台底面）中心；线长 ＝ 门架高 ``H``（地面 → 横担顶面）。
* 底部为**地面生根基础件**（复用 ``模块/公共/混凝土锚板.py``）：
  自下而上 现场灌浆梯台（:data:`GROUND_GROUT_THICKNESS_MM`）→ 锚板（表 2 的
  ``T``）→ 立柱底面；钢构架整体抬升 ``ground_lift()`` ＝ 梯台厚 + 锚板厚，
  故送进本模块的「构架高度」＝ ``H − ground_lift()``（见 :func:`post_length`）。
* **L 为横担全长**（用户输入）：横担以中心线为中点横跨两根立柱、两端各超出
  立柱外缘 :data:`ARM_END_OVERHANG_MM`（图上 25），故两立柱**净距**
  ``B = L − 2×25 − 2×W``（``W`` ＝ 立柱在横担长度方向的截面宽度）。
* 子项 A~C 为等边角钢（立柱与横担**背靠背**，搭接焊缝传力）、D~G 为热轧
  H 型钢（腹板共面、立柱端面顶焊横担翼缘）。
* 允许荷载按**表 1**（子项 × MAX.H 行 × L 列，kN）查；锚板 / 膨胀锚栓按
  **表 2**（E / F / G / T、锚栓直径 / L / h_ef、地坪最小厚度 MIN.h）。

型钢截面本身不重复实现，直接复用仓库内 ``型钢截面生成器`` 的数据与几何模块
（``steel_equal_angle_*`` / ``steel_hbeam_*``）。

布置约定（局部基 u-v-w，原点取所选竖直线的下端 ＝ 地面中心）：

    u = 门架平面内的水平方向（面板「朝向」；也是横担长度方向）
    v = Z × u（水平法向，管道轴线方向）
    w = Z（竖直向上）

其中 **u = 0 即所选竖直线**（整组中心线）：两立柱轴线对称于它、分别在
``∓(L − 50 − W)/2``；横担也以它为中点。立柱截面沿 +w 扫掠，横担截面在
v-w 平面内沿 +u 扫掠，管位面（横担顶面）落在 ``w = 构架高度``。

注：本模块的 ``height_mm`` 一律指**构架高度**（锚板顶面 → 横担顶面），
与面板上的门架高 ``H``（地面 → 横担顶面）相差 ``ground_lift()``。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/G5门型架/，插件根目录需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_equal_angle_data  # noqa: E402
from steel_sections import steel_equal_angle_geometry  # noqa: E402
from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_hbeam_geometry  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 容差与尺寸限制
# ---------------------------------------------------------------------------

# 所选竖直线偏离竖直方向的上限（°）。
VERTICAL_TOLERANCE_DEG = 5.0
# 构架最小高度（锚板顶面 → 横担顶面，mm）与最小净距（mm）。
MIN_FRAME_HEIGHT_MM = 150.0
MIN_SPAN_MM = 50.0
# 表 1 的 MAX.H 匹配容差（mm）。
LOAD_TOLERANCE_MM = 1.0

# 横担两端各超出立柱外缘的固定长度（mm）：图上 25。
ARM_END_OVERHANG_MM = 25.0
# 角钢立柱最高点比横担水平肢低出的焊接间隙（mm）。
WELD_GAP_MM = 10.0

# 现场灌浆保护层：高度（mm）与相对锚板每边的斜向外扩量（mm）。
GROUND_GROUT_THICKNESS_MM = 25.0
GROUND_GROUT_FLARE_MM = 20.0


# ---------------------------------------------------------------------------
# 子项（表 1 / 表 2 的构件 A：A~C 角钢、D~G 热轧 H 型钢）
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
        'family': 'hbeam',
        'profile': 'H100x100x6x8xr8',
        'specification': 'H100×100×6×8',
    },
    'E': {
        'family': 'hbeam',
        'profile': 'H150x150x7x10xr8',
        'specification': 'H150×150×7×10',
    },
    'F': {
        'family': 'hbeam',
        'profile': 'H200x200x8x12xr13',
        'specification': 'H200×200×8×12',
    },
    'G': {
        'family': 'hbeam',
        'profile': 'H250x250x9x14xr13',
        'specification': 'H250×250×9×14',
    },
}

DEFAULT_VARIANT = 'A'

_FAMILIES = {
    'equal_angle': {
        'data': steel_equal_angle_data,
        'geometry': steel_equal_angle_geometry,
        'builder': 'build_equal_angle_geometry',
    },
    'hbeam': {
        'data': steel_hbeam_data,
        'geometry': steel_hbeam_geometry,
        'builder': 'build_hbeam_geometry',
    },
}

# 地面固定（表 2）：子项 -> 锚板 / 膨胀锚栓参数（mm）。
#   plate_e        锚板边长 E（锚板 E×E）
#   hole_spacing_f 螺栓孔中心距 F（方阵 F×F，居中）
#   hole_dia_g     螺栓孔径 G
#   plate_t        锚板厚 T
#   bolt_dia       膨胀锚栓直径（M8 ~ M20）
#   bolt_len       锚栓总长 L
#   embed          有效埋深 h_ef（mm，最小值）
#   min_h          地坪最小厚度 MIN.h
GROUND_ANCHOR_TABLE = {
    'A': dict(plate_e=150.0, hole_spacing_f=100.0, hole_dia_g=10.0,
              plate_t=10.0, bolt_dia=8.0, bolt_len=120.0, embed=55.0,
              min_h=100.0),
    'B': dict(plate_e=210.0, hole_spacing_f=150.0, hole_dia_g=14.0,
              plate_t=10.0, bolt_dia=12.0, bolt_len=160.0, embed=90.0,
              min_h=150.0),
    'C': dict(plate_e=260.0, hole_spacing_f=200.0, hole_dia_g=18.0,
              plate_t=12.0, bolt_dia=16.0, bolt_len=180.0, embed=100.0,
              min_h=150.0),
    'D': dict(plate_e=260.0, hole_spacing_f=200.0, hole_dia_g=18.0,
              plate_t=12.0, bolt_dia=16.0, bolt_len=180.0, embed=100.0,
              min_h=150.0),
    'E': dict(plate_e=350.0, hole_spacing_f=250.0, hole_dia_g=22.0,
              plate_t=16.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
    'F': dict(plate_e=400.0, hole_spacing_f=300.0, hole_dia_g=22.0,
              plate_t=20.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
    'G': dict(plate_e=500.0, hole_spacing_f=400.0, hole_dia_g=22.0,
              plate_t=20.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
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


def variant_is_hbeam(variant_key):
    return _variant(variant_key)['family'] == 'hbeam'


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

    角钢为肢宽 B；H 型钢截面高 H 朝向 u（腹板在门架平面内）。
    """
    if variant_is_hbeam(variant_key):
        return float(section_dimensions(variant_key)['H'])
    return section_box(variant_key)[1]


def beam_depth(variant_key):
    """横担在竖直方向（w）上的厚度（mm）。"""
    return section_box(variant_key)[1]


def beam_flange_thickness(variant_key):
    """横担「水平肢 / 翼缘」的厚度（mm）：角钢取肢厚 t、H 型钢取翼缘厚 t2。"""
    section = section_dimensions(variant_key)
    if variant_is_hbeam(variant_key):
        return float(section['t2'])
    return float(section['t'])


# ---------------------------------------------------------------------------
# 底部地面生根（表 2）
# ---------------------------------------------------------------------------


def ground_anchor_spec(variant_key):
    """返回该子项地面固定用的锚板 / 锚栓参数副本（mm）。"""
    _variant(variant_key)
    try:
        return dict(GROUND_ANCHOR_TABLE[variant_key])
    except KeyError:
        raise ValueError('子项 %s 没有地面固定用的锚板数据（表 2）。'
                         % variant_key)


def ground_lift(variant_key):
    """钢构架整体抬升量（mm）＝ 现场灌浆梯台厚 + 锚板厚。

    所选竖直线的下端取**梯台底面（地面）中心**；自下而上依次为灌浆梯台与
    锚板，故立柱底面（锚板顶面）比线端高 ``梯台厚 + 锚板厚``；横担顶面仍落在
    所选直线的上端。
    """
    return (GROUND_GROUT_THICKNESS_MM
            + ground_anchor_spec(variant_key)['plate_t'])


def min_pavement_thickness(variant_key):
    """地坪最小厚度 MIN.h（mm，表 2）。"""
    return ground_anchor_spec(variant_key)['min_h']


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------


def post_axis_pitch(variant_key, arm_length_mm):
    """两立柱轴线间距（mm）＝ 净距 B + 立柱在 u 向的截面宽 W。"""
    return (float(arm_length_mm) - 2.0 * ARM_END_OVERHANG_MM
            - inplane_width(variant_key))


def net_span(variant_key, arm_length_mm):
    """两立柱净距（内缘到内缘，mm）B = L − 2×25 − 2W。"""
    span = (float(arm_length_mm) - 2.0 * ARM_END_OVERHANG_MM
            - 2.0 * inplane_width(variant_key))
    if span < 0.0:
        raise ValueError(
            '横担全长 L=%.1f mm 过小：扣除两端各 %.0f 与 2×立柱截面宽 %.0f 后'
            '净距为负。' % (arm_length_mm, ARM_END_OVERHANG_MM,
                            inplane_width(variant_key)))
    return span


def post_axis_offset(variant_key, arm_length_mm, side='left'):
    """立柱轴线相对所选竖直线（整组中心线）的 u 偏移（mm）。

    所选竖直线是**整组门型架的中心线**，两立柱轴线对称于它，分别在
    ``∓(L − 50 − W)/2``。
    """
    pitch = post_axis_pitch(variant_key, arm_length_mm)
    if side == 'left':
        return -pitch / 2.0
    if side == 'right':
        return pitch / 2.0
    raise ValueError("side 只能是 'left' 或 'right'。")


def beam_span(variant_key, arm_length_mm):
    """返回横担的 ``(u_start_mm, length_mm)``：以中心线为中点，起点 ``-L/2``。"""
    _variant(variant_key)
    length = float(arm_length_mm)
    return (-length / 2.0, length)


def post_v_offset(variant_key):
    """立柱截面在 v 方向的偏移（mm），使立柱与横担**背靠背**。

    角钢立柱的 u-w 平面肢须与横担竖直肢背面相贴，故整体偏移 ``+W``（截面落在
    ``v ∈ [W/2, W/2 + W]``）；H 型钢立柱腹板与横担腹板共面（v = 0），不偏移。
    """
    if variant_is_hbeam(variant_key):
        return 0.0
    return inplane_width(variant_key)


def post_length(variant_key, height_mm):
    """立柱下料长度（mm）。

    ``height_mm`` 为**构架高度**（锚板顶面 → 横担顶面）：

    * 角钢：非通长，最高点比横担水平肢低 ``WELD_GAP_MM``，即
      ``构架高度 − 肢厚 − 10``，力由贴合焊缝传走；
    * H 型钢：端面焊接，立柱顶面顶焊在横担下翼缘下表面，即
      ``构架高度 − 横担截面高``。
    """
    height_mm = float(height_mm)
    if variant_is_hbeam(variant_key):
        length = height_mm - beam_depth(variant_key)
        if length <= 0.0:
            raise ValueError(
                '构架高度 H=%.1f mm 过小：扣除横担截面高 %.1f 后立柱长度为负。'
                % (height_mm, beam_depth(variant_key)))
        return length
    thickness = beam_flange_thickness(variant_key)
    length = height_mm - thickness - WELD_GAP_MM
    if length <= 0.0:
        raise ValueError(
            '构架高度 H=%.1f mm 过小：扣除肢厚 %.1f 与焊接间隙 %.0f 后立柱'
            '长度为负。' % (height_mm, thickness, WELD_GAP_MM))
    return length


def weld_contact_length(variant_key):
    """角钢立柱肢与横担竖直肢的贴合（焊缝）段高度（mm）；H 型钢为端面焊，返回 0。"""
    if variant_is_hbeam(variant_key):
        return 0.0
    contact = (beam_depth(variant_key) - beam_flange_thickness(variant_key)
               - WELD_GAP_MM)
    if contact <= 0.0:
        raise ValueError('子项 %s 的立柱与横担无有效搭接长度。' % variant_key)
    return contact


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。

    两类构件都用「外接矩形中心」作插入点并置于截面局部原点，于是立柱内 / 外缘
    恰在轴线 ±W/2，横担截面绕 v 居中。
    """
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return ('geometric_center', (0.0, 0.0))


def member_axes(variant_key, member_kind, mirror_u=False):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    各坐标架都保持右手系（axis_x × axis_y = axis_z）。``mirror_u=True`` 只对
    角钢立柱有意义（右柱在 u 方向镜像，使两根立柱互为镜像、开口都朝门架外）；
    H 型钢截面关于腹板平面对称，镜像不改变形状。
    """
    variant = _variant(variant_key)
    family = variant['family']
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")

    if member_kind == 'post':
        if family == 'equal_angle':
            if mirror_u:
                # 右柱：截面 x -> +u、y -> +v，开口朝 (+u, +v)（外角在轴线外侧）。
                return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
            # 左柱：截面 x -> +v、y -> -u，u-w 平面肢落在 +v 端，与横担竖直肢
            # 背面相贴（见 post_v_offset）。
            return (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
        # H 型钢立柱：截面局部 x(翼缘宽 B) -> -v、y(截面高 H) -> +u，沿 +w 扫掠；
        # 腹板在 v = 0（门架平面内）。
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)

    if family == 'equal_angle':
        # 横担角钢：x -> -v、y -> -w，沿 +u 扫掠。竖直肢在 +v 侧向下，
        # 水平肢在顶部、其上表面即固定管子的面。
        return (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    # 横担 H 型钢：x(翼缘宽 B) -> +v、y(截面高 H) -> +w，沿 +u 扫掠；
    # 腹板竖直、在 v = 0，顶面为上面翼缘外表面。
    return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def post_opening_direction(variant_key, mirror_u=False):
    """立柱角钢开口的朝向，返回 (u, v) 分量（未归一化）。

    两根立柱互为镜像、开口都朝门架外时，分别为 ``(-1, +1)``（左柱）与
    ``(+1, +1)``（右柱）。H 型钢截面无此朝向概念，返回 ``(0, 0)``。
    """
    if variant_is_hbeam(variant_key):
        return (0.0, 0.0)
    axis_x, axis_y, _axis_z = member_axes(variant_key, 'post', mirror_u)
    return (axis_x[0] + axis_y[0], axis_x[1] + axis_y[1])


def member_origin_length(variant_key, member_kind, height_mm, arm_length_mm,
                         post_axis_u=0.0):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对所选线下端）与长度。

    ``height_mm`` 为**构架高度**（锚板顶面 → 横担顶面）。

    立柱自锚板顶面（w = 0）向上扫掠，u 位置即自身轴线（由
    :func:`post_axis_offset` 按整组中心线给出），并按 :func:`post_v_offset`
    在 v 方向平移使两者背靠背；横担以整组中心线为中点，自左端（左立柱外缘外
    25 mm，即 ``u = -L/2``）沿 +u 扫掠 L，截面中心置于 ``w = 构架高度 − 深度/2``。
    """
    _variant(variant_key)
    height_mm = float(height_mm)
    depth = beam_depth(variant_key)

    if member_kind == 'post':
        return ((float(post_axis_u), post_v_offset(variant_key), 0.0),
                post_length(variant_key, height_mm))
    if member_kind == 'arm':
        u_start, length = beam_span(variant_key, arm_length_mm)
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
    """把所选元素的折线（mm 点列）解析为整组中心线，并校验合规性。

    要求展开后恰好为一段直线，且该段大致竖直。返回的 ``base`` 是较低的一端
    （＝地面 / 梯台底面中心），``top`` 是较高的一端（＝横担顶面）。
    """
    segments = _flatten_segments(pieces_mm)
    if len(segments) != 1:
        raise ValueError(
            '请选择一条竖直线段（整组中心线），当前为 %d 段。' % len(segments))

    first, second = segments[0]
    direction = _sub(second, first)
    if not _is_vertical(direction):
        raise ValueError('所选线段不是竖直线；请选择一条竖直的线段作为整组中心线。')

    if second[2] >= first[2]:
        base, top = first, second
    else:
        base, top = second, first
    height = top[2] - base[2]
    if height < MIN_FRAME_HEIGHT_MM:
        raise ValueError('门架高 H=%.1f mm 过短，要求 ≥ %.0f mm。'
                         % (height, MIN_FRAME_HEIGHT_MM))

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
#
# 表结构：子项 -> MAX.H（表行）-> L 列 -> 允许垂直荷载（kN）。
# 查表口径：**行是 MAX.H**，故 H 取「覆盖输入的最小 MAX.H 行」（MAX.H ≥ H 中最
# 小的那一行，H 小于全部行时取第一行），H 超出最大的 MAX.H 才算超限；
# L 取不小于输入的最小列；取到「—」时报告未取到。见 :func:`allowable_load`。

LOAD_TABLE = {
    'A': {
        500: {500: 2.0, 1000: None},
    },
    'B': {
        500: {500: 4.0, 1000: 2.0},
        1000: {500: 2.0, 1000: 1.0},
    },
    'C': {
        500: {500: 8.0, 1000: 4.0},
        1000: {500: 4.0, 1000: 2.0},
    },
    'D': {
        1000: {500: 20.0, 1000: 10.0},
        1500: {500: 8.0, 1000: 8.0},
    },
    'E': {
        1000: {1000: 40.0, 1500: 20.0, 2000: 20.0},
        2000: {1000: 20.0, 1500: 20.0, 2000: 20.0},
    },
    'F': {
        1000: {1000: 60.0, 1500: 40.0, 2000: 40.0},
        2000: {1000: 40.0, 1500: 30.0, 2000: 30.0},
        3000: {1000: 20.0, 1500: 20.0, 2000: 20.0},
    },
    'G': {
        1000: {1000: 100.0, 1500: 80.0, 2000: 80.0},
        2000: {1000: 60.0, 1500: 60.0, 2000: 60.0},
        3000: {1000: 40.0, 1500: 40.0, 2000: 40.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm used_arm_mm message')


def max_height(variant_key):
    """该子项表 1 中最大的 MAX.H（mm）＝允许的最大门架高 H。"""
    table = LOAD_TABLE[str(variant_key).upper()]
    return max(table)


def max_arm_length(variant_key):
    """该子项表 1 中最大的 L 列（mm）＝允许的最大横担全长。"""
    table = LOAD_TABLE[str(variant_key).upper()]
    columns = set()
    for row in table.values():
        columns.update(row)
    return max(columns)


def allowable_load(variant_key, height_mm, arm_length_mm):
    """按表 1 查允许垂直荷载。

    ``height_mm`` 为门架高 H（地面 → 横担顶面）；``arm_length_mm`` 为横担全长 L。

    **表 1 的行是 MAX.H**（该行适用的最大门架高），故：

    * H 取**覆盖输入的最小 MAX.H 行**（``MAX.H ≥ H`` 中最小的那一行）——
      例如 G 子项 H=1500 落在 MAX.H=2000 行（荷载 60 kN），而不是 MAX.H=1000
      行；H 小于全部 MAX.H 时同样落在第一行；H 超出最大的 MAX.H 才算超限。
    * L 取不小于输入的最小列（偏安全）。

    返回 :class:`LoadResult`；查不到时 ``value`` 为 None 并在 ``message`` 中说明。
    """
    variant_key = str(variant_key).upper()
    table = LOAD_TABLE.get(variant_key)
    if table is None:
        return LoadResult(None, None, None, '子项 %s 无荷载表。' % variant_key)

    heights = sorted(table)                      # MAX.H，升序
    covering = [h for h in heights
                if h + LOAD_TOLERANCE_MM >= float(height_mm)]
    if not covering:
        return LoadResult(
            None, None, None,
            'H=%.0f mm 超出表中最大 MAX.H=%d mm。' % (height_mm, heights[-1]))
    used_height = covering[0]
    row = table[used_height]

    columns = sorted(row)
    chosen = None
    for column in columns:
        if float(arm_length_mm) <= column:
            chosen = column
            break
    if chosen is None:
        return LoadResult(
            None, used_height, None,
            'L=%.0f mm 超出表中上限 %d mm。' % (arm_length_mm, columns[-1]))
    value = row[chosen]
    if value is None:
        return LoadResult(
            None, used_height, chosen,
            '子项 %s、MAX.H=%d、L≤%d 一栏表中为空（—）。'
            % (variant_key, used_height, chosen))
    return LoadResult(
        float(value), used_height, chosen,
        '按 MAX.H=%d mm、L≤%d mm 取用。' % (used_height, chosen))


# ---------------------------------------------------------------------------
# 管架编号
# ---------------------------------------------------------------------------


def round_half_up(value):
    """四舍五入到整数（Python 的 round 为「银行家舍入」，不可用于编号）。"""
    return int(math.floor(float(value) + 0.5))


def build_pipe_rack_number(name, variant_key, height_mm, arm_mm):
    """管架编号「名称-子项-H-L」（如 ``G5-A-500-1000``）；名称为空时返回空串。"""
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%s-%d-%d' % (
        label, str(variant_key).upper(),
        round_half_up(height_mm), round_half_up(arm_mm))
