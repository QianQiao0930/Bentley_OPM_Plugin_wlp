# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``D13-[门型架_倒门型架（H型钢）].py`` 等插件 ``import``
# 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""H 型钢门型架纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

对应「图 C.4-8 门形架（H 型钢）」类型 1：

* 解析用户绘制的 **竖直线**（**整组门型架的中心线**）为门架高 H；水平布置
  方向由面板的「朝向」给定 —— 竖直线本身不能确定门架平面。
* 提供表 1 的子项 A~D 型钢截面表（H100x100x6x8 ~ H250x250x9x14）与允许垂直
  荷载查询（按 **H** 与 **L** 双参数查表）。
* 给出立柱与横担的布置：**L 为横担全长**，两立柱轴线对称于所选竖直线，横担
  以该线为中点、两端各超出立柱外缘 ``ARM_END_OVERHANG_MM``（图上 50 TYP.），
  故两立柱**净距** ``B = L - 2*50 - 2*立柱截面高``。

型钢截面本身不重复实现，直接复用仓库内 ``型钢截面生成器`` 的数据与几何模块
（``steel_hbeam_data`` / ``steel_hbeam_geometry``）。

布置约定（局部基 u-v-w，原点取所选竖直线的下端）：

    u = 门架平面内的水平方向（面板「朝向」；也是横担长度方向）
    v = Z × u（水平法向，管道轴线方向）
    w = Z（竖直向上）

其中 **u = 0 即所选竖直线**，也就是整组门型架的中心线：两立柱轴线对称于它，
横担也以它为中点。

* 立柱：截面在 u-v 平面内，沿 +w 由下向上扫掠；截面高 ``H`` 朝向 u、翼缘宽
  ``B`` 朝向 v，**腹板位于 v = 0（门架平面内）**、翼缘对称于该面；外接矩形
  中心落在自身轴线上（左 / 右轴线在 ``∓(L - 100 - H)/2``），故内缘恰好在
  轴线 ±H/2 处。
* 横担：截面在 v-w 平面内，沿 +u 扫掠；截面高 ``H`` 竖直、翼缘宽 ``B`` 朝向
  v，腹板同样在 v = 0；顶面（固定管子的面）落在 w = H。
* 立柱顶面顶焊在横担下翼缘下表面（腹板共面，力经该接触面下传），立柱长度
  因此扣除横担截面高。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/门型架H型钢/，插件根目录需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_hbeam_geometry  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


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

# 类型 1：正门形架（立柱在下、横担在上）。
# 类型 3/4 为倒门形架（吊架），留待后续实现，此处不接受。
ALL_RACK_TYPES = (1,)
HANGER_RACK_TYPES = ()


def hanger_type(rack_type):
    """本插件仅实现类型 1；倒门形架（立柱在上）尚未支持，恒为 False。"""
    try:
        return int(rack_type) in HANGER_RACK_TYPES
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 子项（表 1）与型钢截面
# ---------------------------------------------------------------------------

# profile 为 型钢截面生成器 的规格名（含圆角半径后缀）。
VARIANTS = {
    'A': {
        'profile': 'H100x100x6x8xr8',
        'specification': 'H100×100×6×8',
    },
    'B': {
        'profile': 'H150x150x7x10xr8',
        'specification': 'H150×150×7×10',
    },
    'C': {
        'profile': 'H200x200x8x12xr13',
        'specification': 'H200×200×8×12',
    },
    'D': {
        'profile': 'H250x250x9x14xr13',
        'specification': 'H250×250×9×14',
    },
}

DEFAULT_VARIANT = 'A'

# 横担两端各超出立柱外缘的固定长度（mm）：图上 50 (TYP.)。
ARM_END_OVERHANG_MM = 50.0


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
    """返回所选子项的 H 型钢截面尺寸字典（mm）：H / B / t1 / t2 / r。"""
    variant = _variant(variant_key)
    return steel_hbeam_data.get_section(variant['profile'])


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


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------

def member_depth(variant_key, member_kind):
    """构件的「截面高 H」（mm）：立柱取 u 向尺寸、横担取竖直尺寸。"""
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return float(section_dimensions(variant_key)['H'])


def member_flange_width(variant_key, member_kind):
    """构件的「翼缘宽 B」（mm）：两类构件都朝向 v（管道方向）。"""
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return float(section_dimensions(variant_key)['B'])


def net_span(variant_key, arm_length_mm):
    """两立柱净距（内缘到内缘，mm）B = L - 2×50 - 2×立柱截面高。"""
    leg_depth = member_depth(variant_key, 'post')
    span = (float(arm_length_mm) - 2.0 * ARM_END_OVERHANG_MM
            - 2.0 * leg_depth)
    if span < 0.0:
        raise ValueError(
            '横担长 L=%.1f mm 过小：扣除两端各 %.0f 与立柱截面高 %.0f 后净距为负。'
            % (arm_length_mm, ARM_END_OVERHANG_MM, leg_depth))
    return span


def beam_span(variant_key, arm_length_mm):
    """返回横担的 ``(u_start_mm, length_mm)``。

    横担以所选竖直线（整组中心线，u = 0）为中点，全长即用户输入的 L，故
    ``u_start = -L/2``；两端各超出立柱外缘 ``ARM_END_OVERHANG_MM``。
    """
    return (-float(arm_length_mm) / 2.0, float(arm_length_mm))


def post_axis_pitch(variant_key, arm_length_mm):
    """两立柱轴线间距（mm）= L - 2*50 - 立柱截面高。"""
    return (float(arm_length_mm) - 2.0 * ARM_END_OVERHANG_MM
            - member_depth(variant_key, 'post'))


def post_axis_offset(variant_key, arm_length_mm, side='left'):
    """立柱轴线相对所选竖直线（整组中心线）的 u 偏移（mm）。

    所选竖直线是**整组门型架的中心线**，两立柱轴线对称于它，分别在
    ``∓(L - 2*50 - 立柱截面高)/2``；故左立柱轴线不再与所选线重合。
    """
    pitch = post_axis_pitch(variant_key, arm_length_mm)
    if side == 'left':
        return -pitch / 2.0
    if side == 'right':
        return pitch / 2.0
    raise ValueError("side 只能是 'left' 或 'right'。")


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。

    H 型钢截面关于自身几何中心对称，故都用「几何中心」作插入点并置于截面
    局部原点：立柱内 / 外缘恰在轴线 ±H/2，横担腹板落在 v = 0、翼缘对称。
    """
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return ('geometric_center', (0.0, 0.0))


def member_axes(variant_key, member_kind):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    ``steel_hbeam_geometry`` 的截面局部坐标里 **局部 +y 为截面高 H、局部 x
    为翼缘宽 B**；这里据此把截面高摆到 u（立柱）/ w（横担）、翼缘宽摆到 v，
    使腹板平面与门架平面重合。各坐标架都保持右手系。
    """
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")

    if member_kind == 'post':
        # 立柱：截面局部 x(翼缘宽 B) -> -v、y(截面高 H) -> +u，沿 +w 向上扫掠。
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    # 横担：截面局部 x(翼缘宽 B) -> +v、y(截面高 H) -> +w，沿 +u 扫掠。
    return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def member_origin_length(variant_key, member_kind, height_mm, arm_length_mm,
                         post_axis_u=0.0):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对所选线下端）与长度。

    立柱由基座（w = 0）向上扫掠到横担下翼缘下表面，u 位置即自身轴线（由
    :func:`post_axis_offset` 按整组中心线给出的 ``∓(L-100-H)/2``），长度扣除
    横担截面高；横担以整组中心线为中点，自左端（左立柱外缘外 50，即
    ``u = -L/2``）沿 +u 扫掠 L，截面中心置于 ``w = H - 截面高/2``（顶面恰在 H）。
    """
    _variant(variant_key)
    height_mm = float(height_mm)
    arm_depth = member_depth(variant_key, 'arm')

    if member_kind == 'post':
        length = height_mm - arm_depth
        if length <= 0.0:
            raise ValueError(
                '门架高 H=%.1f mm 过小：扣除横担截面高 %.0f 后立柱长度为负。'
                % (height_mm, arm_depth))
        return ((float(post_axis_u), 0.0, 0.0), length)
    if member_kind == 'arm':
        u_start, length = beam_span(variant_key, arm_length_mm)
        return ((u_start, 0.0, height_mm - arm_depth / 2.0), length)
    raise ValueError("member_kind 只能是 'post' 或 'arm'。")


def member_geometry(variant_key, member_kind, scale=1.0):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。

    返回 型钢截面生成器 的 geometry 对象，其 ``segments`` 为线 / 弧段，
    与 ``steel_sweep_geometry.sample_segment`` 兼容。
    """
    variant = _variant(variant_key)
    section = steel_hbeam_data.get_section(variant['profile'])
    scaled = steel_hbeam_geometry.scale_section(section, float(scale))
    mode, insertion_point = member_section_params(variant_key, member_kind)
    point = steel_hbeam_geometry.Point2d(
        insertion_point[0] * float(scale), insertion_point[1] * float(scale))
    return steel_hbeam_geometry.build_hbeam_geometry(scaled, mode, point)


def sample_member(variant_key, member_kind, frame, scale=1.0):
    """按坐标架把构件截面采样为世界点，供纯几何测试使用。"""
    geometry = member_geometry(variant_key, member_kind, scale)
    return tuple(
        steel_sweep_geometry.sample_segment(segment, frame)
        for segment in geometry.segments
    )


def web_plane_offset(variant_key, member_kind):
    """腹板中心平面到截面原点的 v 向距离（mm）：两者都取 0（共面）。"""
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return 0.0


# ---------------------------------------------------------------------------
# 竖直线的解析
# ---------------------------------------------------------------------------

VerticalPost = namedtuple('VerticalPost', 'base top height_mm')


def parse_vertical_post(pieces_mm):
    """把所选元素的折线（mm 点列）解析为整组中心线，并校验合规性。

    ``pieces_mm`` 为若干折线，每条折线是其顶点 ``(x, y, z)`` 的序列。要求
    展开后恰好为一段直线，且该段大致竖直。
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
        1000: {1000: 20.0, 2000: None, 3000: None},
        2000: {1000: 10.0, 2000: None, 3000: None},
        3000: {1000: None, 2000: None, 3000: None},
        4000: {1000: None, 2000: None, 3000: None},
    },
    'B': {
        1000: {1000: 80.0, 2000: 60.0, 3000: None},
        2000: {1000: 40.0, 2000: 40.0, 3000: None},
        3000: {1000: 20.0, 2000: 20.0, 3000: None},
        4000: {1000: None, 2000: None, 3000: None},
    },
    'C': {
        1000: {1000: 140.0, 2000: 80.0, 3000: 60.0},
        2000: {1000: 80.0, 2000: 80.0, 3000: 60.0},
        3000: {1000: 40.0, 2000: 40.0, 3000: 40.0},
        4000: {1000: 20.0, 2000: 20.0, 3000: 20.0},
    },
    'D': {
        1000: {1000: 200.0, 2000: 120.0, 3000: 100.0},
        2000: {1000: 100.0, 2000: 100.0, 3000: 100.0},
        3000: {1000: 70.0, 2000: 70.0, 3000: 70.0},
        4000: {1000: 40.0, 2000: 40.0, 3000: 40.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm used_arm_mm message')


def allowable_load(variant_key, height_mm, arm_length_mm):
    """按表 1 查允许垂直荷载。

    ``height_mm`` 为门架高 H，``arm_length_mm`` 为横担长 L。H 取不超过输入的
    最大表列值（偏安全）；L 取不小于输入的最小列。返回 :class:`LoadResult`，
    查不到时 ``value`` 为 None 并在 ``message`` 中说明。
    """
    variant_key = str(variant_key).upper()
    table = LOAD_TABLE.get(variant_key)
    if table is None:
        return LoadResult(None, None, None, '子项 %s 无荷载表。' % variant_key)

    heights = sorted(table)
    usable = [h for h in heights if h <= float(height_mm) + LOAD_HEIGHT_TOLERANCE_MM]
    if not usable:
        return LoadResult(
            None, None, None,
            'H=%.0f mm 小于表中最小值 %d mm。' % (height_mm, heights[0]))
    used_height = usable[-1]
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
            '子项 %s、H=%d、L≤%d 一栏表中为空（—）。'
            % (variant_key, used_height, chosen))
    return LoadResult(
        float(value), used_height, chosen,
        '按 H=%d mm、L≤%d mm 取用。' % (used_height, chosen))


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
