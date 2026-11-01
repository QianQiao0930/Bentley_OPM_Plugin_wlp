# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``G6-[地面上生根的门型架（槽钢和H型钢组合）].py``
# 等插件 ``import`` 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中
# 直接加载运行。
# =============================================================================
"""G6 地面上生根的门型架（槽钢和 H 型钢组合）：纯几何 / 数据逻辑（可单测）。

构件组合（图 表 1 / 表 2，子项按**表 2 的字母 A~D**）：

    子项   构件A（立柱）        构件B（横担：两片背靠背槽钢）   S     锚板/锚栓
     A     H100×100×6×8        [5                                25    见表 2
     B     H150×150×7×10       [10                               50
     C     H200×200×8×12       [16a                              70
     D     H250×250×9×14       [20a                             100

* **构件A（两根立柱）**：热轧 H 型钢，腹板在门架平面内（v = 0），截面高 ``d`` 沿
  u、翼缘宽 ``B`` 沿 v。所选竖直线＝整组中心线，**两立柱外缘间距 ＝ L**（用户
  输入），故立柱轴线在 ``∓(L − d)/2``、**净距 ＝ L − 2d**。
* **构件B（横担）**：两片槽钢**背靠背**（腹板相对、开口朝外），两腹板之间的
  **净距 ＝ S**（表 2）、关于门架平面对称；整组**夹在两根立柱之间、不外伸**，
  即横担长度 ＝ ``L − 2d``（两端面顶在两立柱的内侧翼缘面上）；槽钢**截面高竖直**
  （腹板竖直、翼缘水平），故**管位面 ＝ 两片槽钢上翼缘的顶面**，落在
  ``w = 构架高度``。两片槽钢合起来的 v 向宽度 ``2×b + S`` 不大于立柱翼缘宽 ``B``
  （A 99≤100 / B 146≤150 / C 196≤200 / D 246≤250，见图）。
* **柱顶高出横担顶面 ``POST_TOP_RISE_MM`` ＝ 50**（图上 50）：立柱自锚板顶面
  （w = 0）扫到 ``w = 构架高度 + 50``，故立柱下料长 ＝ 构架高度 + 50。
* **底部地面生根基础件**复用 ``模块/公共/混凝土锚板.py`` 的
  ``build_ground_base()``：现场灌浆梯台（:data:`GROUND_GROUT_THICKNESS_MM`）→
  锚板（表 2 的 ``T``）→ 立柱底面；钢构架整体抬升 ``ground_lift()`` ＝ 梯台厚 +
  锚板厚，故送进本模块的**构架高度 ＝ H − ground_lift()**。
* 允许荷载按**表 1**（子项 × MAX.H 行 × L 列，kN）查 —— 表 1 的字母是 D~G，
  与本模块的 A~D 一一对应（D→A、E→B、F→C、G→D），数据取自表 1；锚板 / 膨胀
  锚栓按**表 2**（E / F / G / T、锚栓直径 / L / h_ef、地坪最小厚度 MIN.h）。

布置约定（局部基 u-v-w，原点取所选竖直线的下端 ＝ 地面中心）：

    u = 门架平面内的水平方向（面板「朝向」；也是横担长度方向）
    v = Z × u（水平法向，管道轴线方向）
    w = Z（竖直向上）

其中 **u = 0 即所选竖直线**（整组中心线）：两立柱轴线对称于它，横担也以它为中点。
立柱截面沿 +w 扫掠；横担两片槽钢的截面在 v-w 平面内、沿 +u 扫掠。

注：本模块的 ``height_mm`` 一律指**构架高度**（锚板顶面 → 横担顶面 ＝ 管位面），
与面板上的门架高 ``H``（地面 → 横担顶面）相差 ``ground_lift()``。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/G6门型架/，插件根目录需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_channel_data  # noqa: E402
from steel_sections import steel_channel_geometry  # noqa: E402
from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_hbeam_geometry  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 容差与尺寸限制
# ---------------------------------------------------------------------------

# 所选竖直线偏离竖直方向的上限（°）。
VERTICAL_TOLERANCE_DEG = 5.0
# 构架最小高度（锚板顶面 → 横担顶面，mm）与横担最小长度（mm）。
MIN_FRAME_HEIGHT_MM = 150.0
MIN_CROSSARM_LENGTH_MM = 50.0
# 表 1 的 MAX.H 匹配容差（mm）。
LOAD_TOLERANCE_MM = 1.0

# 柱顶高出横担顶面（管位面）的固定长度（mm）：图上 50。
POST_TOP_RISE_MM = 50.0

# 现场灌浆保护层：高度（mm）与相对锚板每边的斜向外扩量（mm）。
GROUND_GROUT_THICKNESS_MM = 25.0
GROUND_GROUT_FLARE_MM = 20.0


# ---------------------------------------------------------------------------
# 子项（表 1 / 表 2）：构件A H 型钢 + 构件B 两片槽钢 + 间距 S
# ---------------------------------------------------------------------------

VARIANTS = {
    'A': {
        'beam_profile': 'H100x100x6x8xr8',
        'beam_specification': 'H100×100×6×8',
        'channel_profile': '5',
        'channel_specification': '[5',
        'gap': 25.0,
    },
    'B': {
        'beam_profile': 'H150x150x7x10xr8',
        'beam_specification': 'H150×150×7×10',
        'channel_profile': '10',
        'channel_specification': '[10',
        'gap': 50.0,
    },
    'C': {
        'beam_profile': 'H200x200x8x12xr13',
        'beam_specification': 'H200×200×8×12',
        'channel_profile': '16a',
        'channel_specification': '[16a',
        'gap': 70.0,
    },
    'D': {
        'beam_profile': 'H250x250x9x14xr13',
        'beam_specification': 'H250×250×9×14',
        'channel_profile': '20a',
        'channel_specification': '[20a',
        'gap': 100.0,
    },
}

DEFAULT_VARIANT = 'A'

# 地面固定（表 2）：子项 -> 锚板 / 膨胀锚栓参数（mm）。
GROUND_ANCHOR_TABLE = {
    'A': dict(plate_e=260.0, hole_spacing_f=200.0, hole_dia_g=18.0,
              plate_t=12.0, bolt_dia=16.0, bolt_len=180.0, embed=100.0,
              min_h=150.0),
    'B': dict(plate_e=350.0, hole_spacing_f=250.0, hole_dia_g=22.0,
              plate_t=16.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
    'C': dict(plate_e=400.0, hole_spacing_f=300.0, hole_dia_g=22.0,
              plate_t=20.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
    'D': dict(plate_e=500.0, hole_spacing_f=400.0, hole_dia_g=22.0,
              plate_t=20.0, bolt_dia=20.0, bolt_len=220.0, embed=125.0,
              min_h=150.0),
}


def variant_choices():
    """返回 ``(代号, 显示文本)``，按代号排序，供下拉框使用。"""
    return tuple((key, variant_label(key)) for key in sorted(VARIANTS))


def variant_label(variant_key):
    variant = _variant(variant_key)
    return '%s  |  %s + %s（S=%.0f）' % (
        variant_key, variant['beam_specification'],
        variant['channel_specification'], variant['gap'])


def _variant(variant_key):
    try:
        return VARIANTS[variant_key]
    except KeyError:
        raise ValueError('未知子项：%s。' % variant_key)


def beam_specification(variant_key):
    """构件A（立柱）规格。"""
    return _variant(variant_key)['beam_specification']


def channel_specification(variant_key):
    """构件B（横担，两片槽钢）规格。"""
    return _variant(variant_key)['channel_specification']


def beam_dimensions(variant_key):
    """构件A（H 型钢）截面尺寸字典（mm）：H / B / t1 / t2 / r。"""
    return steel_hbeam_data.get_section(_variant(variant_key)['beam_profile'])


def channel_dimensions(variant_key):
    """构件B（槽钢）截面尺寸字典（mm）：H / B / tw / tf。"""
    return steel_channel_data.get_section(
        _variant(variant_key)['channel_profile'])


def post_depth(variant_key):
    """立柱截面高 ``d``（mm，沿 u）：两立柱外缘间距 L 的扣减量。"""
    return float(beam_dimensions(variant_key)['H'])


def post_flange_width(variant_key):
    """立柱翼缘宽（mm，沿 v）。"""
    return float(beam_dimensions(variant_key)['B'])


def post_web_thickness(variant_key):
    """立柱腹板厚（mm）：应小于槽钢腹板间距 S，避免与横担相碰。"""
    return float(beam_dimensions(variant_key)['t1'])


def channel_height(variant_key):
    """槽钢截面高（mm，竖直方向）。"""
    return float(channel_dimensions(variant_key)['H'])


def channel_flange_width(variant_key):
    """槽钢翼缘宽（mm，沿 v）。"""
    return float(channel_dimensions(variant_key)['B'])


def channel_gap(variant_key):
    """两片槽钢**腹板之间的净距** S（mm，表 2）。"""
    return float(_variant(variant_key)['gap'])


def channel_pair_width(variant_key):
    """两片槽钢合起来的 v 向总宽（mm）＝ 2×翼缘宽 + S。"""
    return 2.0 * channel_flange_width(variant_key) + channel_gap(variant_key)


def channel_pair_fits_post(variant_key):
    """两片槽钢的总宽是否不超过立柱翼缘宽（图上四组都刚好放得下）。"""
    return channel_pair_width(variant_key) <= post_flange_width(variant_key)


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
    锚板，故立柱底面（锚板顶面）比线端高 ``梯台厚 + 锚板厚``；横担顶面（管位面）
    仍落在所选直线的上端。
    """
    return (GROUND_GROUT_THICKNESS_MM
            + ground_anchor_spec(variant_key)['plate_t'])


def min_pavement_thickness(variant_key):
    """地坪最小厚度 MIN.h（mm，表 2）。"""
    return ground_anchor_spec(variant_key)['min_h']


# ---------------------------------------------------------------------------
# 布置
# ---------------------------------------------------------------------------


def crossarm_length(variant_key, post_span_mm):
    """横担（两片槽钢）长度（mm）＝ 净距 ＝ ``L − 2d``。

    ``post_span_mm`` ＝ L ＝ **两立柱外缘间距**（用户输入）。
    """
    length = float(post_span_mm) - 2.0 * post_depth(variant_key)
    if length <= 0.0:
        raise ValueError(
            '两立柱外缘间距 L=%.1f mm 过小：扣除 2×立柱截面高 %.0f 后横担长度'
            '为负。' % (post_span_mm, post_depth(variant_key)))
    return length


def net_span(variant_key, post_span_mm):
    """两立柱净距（内缘到内缘，mm）＝ 横担长度 ＝ ``L − 2d``。"""
    return crossarm_length(variant_key, post_span_mm)


def post_axis_offset(variant_key, post_span_mm, side='left'):
    """立柱轴线相对所选竖直线（整组中心线）的 u 偏移（mm）。

    两立柱**外缘**分别在 ``∓L/2``，故轴线在 ``∓(L − d)/2``。
    """
    post_span_mm = float(post_span_mm)
    offset = (post_span_mm - post_depth(variant_key)) / 2.0
    if side == 'left':
        return -offset
    if side == 'right':
        return offset
    raise ValueError("side 只能是 'left' 或 'right'。")


def crossarm_span(variant_key, post_span_mm):
    """返回横担的 ``(u_start_mm, length_mm)``：夹在两柱之间，故起点 ``-(L-2d)/2``。"""
    length = crossarm_length(variant_key, post_span_mm)
    return (-length / 2.0, length)


def post_length(variant_key, height_mm):
    """立柱下料长度（mm）＝ 构架高度 + :data:`POST_TOP_RISE_MM`。

    ``height_mm`` 为**构架高度**（锚板顶面 → 横担顶面）：立柱自锚板顶面
    （w = 0）向上，柱顶高出横担顶面 50（图上 50），故下料长 ＝ 构架高度 + 50。
    """
    _variant(variant_key)
    height_mm = float(height_mm)
    if height_mm <= 0.0:
        raise ValueError('构架高度 H=%.1f mm 无效。' % height_mm)
    return height_mm + POST_TOP_RISE_MM


def channel_v_offset(variant_key, side='plus'):
    """单片槽钢截面外接矩形中心相对门架平面（v = 0）的偏移（mm）。

    ``side='plus'``：腹板内表面在 ``v = +S/2``、开口朝 +v，故外接矩形中心在
    ``+(S/2 + b/2)``；``side='minus'`` 为镜像（中心在 ``−(S/2 + b/2)``）。
    """
    offset = channel_gap(variant_key) / 2.0 + channel_flange_width(variant_key) / 2.0
    if side == 'plus':
        return offset
    if side == 'minus':
        return -offset
    raise ValueError("side 只能是 'plus' 或 'minus'。")


def channel_web_faces(variant_key):
    """返回两片槽钢**腹板相对的两个面**在 v 上的位置 ``(-S/2, +S/2)``（mm）。"""
    half = channel_gap(variant_key) / 2.0
    return (-half, half)


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。

    立柱（H 型钢）与横担（槽钢）都用「外接矩形中心」作插入点并置于截面局部
    原点：立柱内 / 外缘恰在轴线 ±d/2，槽钢截面绕自身外接矩形中心摆位。
    """
    _variant(variant_key)
    if member_kind not in ('post', 'arm_plus', 'arm_minus'):
        raise ValueError(
            "member_kind 只能是 'post' / 'arm_plus' / 'arm_minus'。")
    return ('geometric_center', (0.0, 0.0))


def member_axes(variant_key, member_kind):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    各坐标架都保持右手系（axis_x × axis_y = axis_z）：

    * 立柱（H 型钢）：截面局部 x(翼缘宽 B) -> -v、y(截面高 d) -> +u、z -> +w，
      沿 +w 向上扫掠；腹板在 v = 0（门架平面内）。
    * 横担 +v 片槽钢：x(翼缘宽 b) -> +v（开口朝 +v）、y(截面高) -> +w，
      沿 +u 扫掠；
    * 横担 -v 片槽钢：x -> -v、y -> -w（槽钢截面关于腹板中线对称，y 反向等价），
      沿 +u 扫掠 —— 与另一片互为镜像。
    """
    _variant(variant_key)
    if member_kind == 'post':
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    if member_kind == 'arm_plus':
        return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)
    if member_kind == 'arm_minus':
        return (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    raise ValueError("member_kind 只能是 'post' / 'arm_plus' / 'arm_minus'。")


def member_origin_length(variant_key, member_kind, height_mm, post_span_mm,
                         post_axis_u=0.0):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对所选线下端）与长度。

    ``height_mm`` 为**构架高度**（锚板顶面 → 横担顶面），``post_span_mm`` ＝ L
    ＝ 两立柱外缘间距。

    * 立柱：起点 ``(post_axis_u, 0, 0)``（锚板顶面），长度 ＝ 构架高度 + 50；
    * 横担 +v 片：起点 ``(-(L-2d)/2, +(S/2 + b/2), 构架高度 − 槽钢高/2)``，
      长度 ＝ L − 2d，沿 +u 扫掠（顶面落在构架高度）；
    * 横担 -v 片：同上但 v 取负。
    """
    _variant(variant_key)
    height_mm = float(height_mm)

    if member_kind == 'post':
        return ((float(post_axis_u), 0.0, 0.0),
                post_length(variant_key, height_mm))
    if member_kind in ('arm_plus', 'arm_minus'):
        u_start, length = crossarm_span(variant_key, post_span_mm)
        side = 'plus' if member_kind == 'arm_plus' else 'minus'
        v_offset = channel_v_offset(variant_key, side)
        top = height_mm
        w_center = top - channel_height(variant_key) / 2.0
        return ((u_start, v_offset, w_center), length)
    raise ValueError("member_kind 只能是 'post' / 'arm_plus' / 'arm_minus'。")


def member_geometry(variant_key, member_kind, scale=1.0):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。

    返回 型钢截面生成器 的 geometry 对象，其 ``segments`` 为线 / 弧段，
    与 ``steel_sweep_geometry.sample_segment`` 兼容。
    """
    variant = _variant(variant_key)
    if member_kind == 'post':
        module = steel_hbeam_geometry
        section = steel_hbeam_data.get_section(variant['beam_profile'])
        builder = steel_hbeam_geometry.build_hbeam_geometry
        point_factory = steel_hbeam_geometry.Point2d
    elif member_kind in ('arm_plus', 'arm_minus'):
        module = steel_channel_geometry
        section = steel_channel_data.get_section(variant['channel_profile'])
        builder = steel_channel_geometry.build_channel_geometry
        point_factory = steel_channel_geometry.Point2d
    else:
        raise ValueError("member_kind 只能是 'post' / 'arm_plus' / 'arm_minus'。")

    scaled = module.scale_section(section, float(scale))
    mode, insertion_point = member_section_params(variant_key, member_kind)
    point = point_factory(insertion_point[0] * float(scale),
                          insertion_point[1] * float(scale))
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
    （＝地面 / 梯台底面中心），``top`` 是较高的一端（＝横担顶面 / 管位面）。
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
# 表结构：子项（A~D，对应图 表 1 的 D~G）-> MAX.H（表行）-> L 列 -> 荷载（kN）。
# 查表口径：**行是 MAX.H**，故 H 取「覆盖输入的最小 MAX.H 行」（MAX.H ≥ H 中最
# 小的那一行，H 小于全部行时取第一行），H 超出最大的 MAX.H 才算超限；
# L 取不小于输入的最小列；取到「—」时报告未取到。

LOAD_TABLE = {
    'A': {                                  # 图 表 1 子项 D（H100×100×6×8）
        1000: {500: 15.0, 1000: 10.0},
        1500: {500: 8.0, 1000: 8.0},
    },
    'B': {                                  # 图 表 1 子项 E（H150×150×7×10）
        1000: {1000: 40.0, 1500: 20.0},
        2000: {1000: 20.0, 1500: 20.0},
    },
    'C': {                                  # 图 表 1 子项 F（H200×200×8×12）
        1000: {1000: 60.0, 1500: 40.0, 2000: 40.0},
        2000: {1000: 40.0, 1500: 30.0, 2000: 30.0},
        3000: {1000: 20.0, 1500: 20.0, 2000: 20.0},
    },
    'D': {                                  # 图 表 1 子项 G（H250×250×9×14）
        1000: {1000: 100.0, 1500: 80.0, 2000: 80.0},
        2000: {1000: 60.0, 1500: 60.0, 2000: 60.0},
        3000: {1000: 40.0, 1500: 40.0, 2000: 40.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm used_arm_mm message')


def max_height(variant_key):
    """该子项表 1 中最大的 MAX.H（mm）＝允许的最大门架高 H。"""
    return max(LOAD_TABLE[str(variant_key).upper()])


def max_arm_length(variant_key):
    """该子项表 1 中最大的 L 列（mm）＝允许的最大立柱外缘间距 L。"""
    columns = set()
    for row in LOAD_TABLE[str(variant_key).upper()].values():
        columns.update(row)
    return max(columns)


def allowable_load(variant_key, height_mm, arm_length_mm):
    """按表 1 查允许垂直荷载。

    ``height_mm`` 为门架高 H（地面 → 横担顶面）；``arm_length_mm`` 为两立柱
    外缘间距 L（表 1 的 L 列口径与图一致）。H 取覆盖输入的最小 MAX.H 行、
    L 取不小于输入的最小列。返回 :class:`LoadResult`；查不到时 ``value`` 为
    None 并在 ``message`` 中说明。
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
    """管架编号「名称-子项-H-L」（如 ``G6-A-1000-1500``）；名称为空时返回空串。"""
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%s-%d-%d' % (
        label, str(variant_key).upper(),
        round_half_up(height_mm), round_half_up(arm_mm))
