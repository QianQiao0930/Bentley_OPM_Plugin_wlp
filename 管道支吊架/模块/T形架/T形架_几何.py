# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``T形架.py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""T 形架（类型 1）纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

对应「T 形架」：**单根立柱 + 居中横担**，构成 T 形。两种型式：

* **类型 1（正 T 形架）**：立柱在下、横担在上；所选竖直线下端为基座（落在已有
  钢结构上），顶端为横担顶面（固定管子的面，即高度 H）。
* **类型 2（吊架，立柱在上）**：横担在所选竖直线下端、**管位朝上（与类型 1
  同向）**，立柱向上到竖直线顶端（接已有结构）。两种型式都保留横担长边水平、
  管位面朝上，用于放管道。

* 解析用户绘制的 **竖直线**（立柱轴线；允许 **±5° 以内**的轻微倾斜，与门型架
  一致）为立柱长 H，取线上两端点的 Z 差。**Z 较高的一端为顶部**（横担 / 管子），
  较低端为基座（落在已有钢结构上）。
* 横担（长 L，面板输入）**世界水平**、垂直于立柱，方向由面板「朝向」给定。
* 提供表 3 的子项 A~G 型钢截面表（A~C 角钢 / D~G 热轧 H 型钢）与表 1 / 表 2
  的允许垂直荷载查询，以及每个子项的**最大允许 H / L**（表中尚有可用值的最大
  行 / 列）。
* 立柱与横担同规格（构件 A）：
  - 角钢子项（A~C）**背靠背**：立柱的 u-w 平面肢与横担竖直肢背面相贴（两角钢
    背靠背）；立柱**非通长**，与横担的贴合段外留 10 mm 施焊间隙；
  - H 型钢子项（D~G）**端面焊接**：立柱端面焊接横担翼缘面，两者腹板共面（v = 0）。

布置约定（局部基 u-v-w，原点取所选竖直线 **下端**，w = Z 向上）：

    u = 横担长度方向（世界水平、垂直于立柱；面板「朝向」）
    v = w × u（横担截面法向，管道轴线方向）
    w = Z（竖直向上；立柱轴线）

* 立柱：截面在 u-v 平面内、沿 ±w 扫掠；**外接矩形中心**落在立柱轴线上（u = 0），
  故立柱在 u 向的截面宽 W 对称于轴线。
* 横担：截面在 v-w 平面内、沿 ∓u 扫掠；**以 u = 0 为中点**，管位面水平。

**类型 1**：横担管位面（水平）落在 ``w = H``（竖直线顶端）；立柱自基座（w = 0）
向上，与横担背靠背或端面焊。
**类型 2**：横担管位面（水平）落在 ``w = 0``（竖直线下端）；立柱向上到
``w = H``（结构端）——角钢立柱下探到管位面以下与横担竖直肢背靠背搭接，
H 型钢端面焊在横担上表面。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/T形架/，插件根目录需上溯两级。
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

# 立柱轴线偏离竖直方向的上限（°）：在此范围内视为竖直，横担方向由「朝向」定。
VERTICAL_TOLERANCE_DEG = 5.0
# 立柱最小长度、横担最小长度（mm）：过短无法形成有效 T 形架。
MIN_LINE_LENGTH_MM = 150.0
MIN_ARM_LENGTH_MM = 50.0
# 荷载表的匹配容差（mm）。
LOAD_TOLERANCE_MM = 1.0

# 类型 1：正 T 形架（立柱在下、横担在上，管道坐横担顶面）。
# 类型 2：吊架（立柱在横担上、横担在下端，管道坐横担顶面）。
ALL_RACK_TYPES = (1, 2)
HANGER_RACK_TYPES = (2,)


def hanger_type(rack_type):
    """是否为类型 2（立柱在横担上的吊架）。"""
    try:
        return int(rack_type) in HANGER_RACK_TYPES
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


def variant_family(variant_key):
    return _variant(variant_key)['family']


def variant_is_hbeam(variant_key):
    """是否为 H 型钢子项（端面焊接）；否则为角钢（背靠背）。"""
    return variant_family(variant_key) == 'hbeam'


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


# ---------------------------------------------------------------------------
# 构件截面尺寸
# ---------------------------------------------------------------------------

# 立柱（角钢）顶端比横担水平肢低出的焊接间隙（mm）。
WELD_GAP_MM = 10.0

# 截面外接矩形中心：角钢 / H 型钢的几何模块都提供 geometric_center 插入点，
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
    """立柱在 u 向的截面宽 W（mm）。

    立柱截面局部 +y 映射到 ±u：角钢为肢宽 B，H 型钢为截面高 H。
    """
    return section_box(variant_key)[1]


def beam_depth(variant_key):
    """横担在竖直方向（w）上的厚度（mm），同取截面局部 y 向尺寸。"""
    return section_box(variant_key)[1]


def beam_flange_thickness(variant_key):
    """横担「水平肢 / 上翼缘」的厚度（mm）：角钢取肢厚 t、H 型钢取翼缘厚 t2。"""
    section = section_dimensions(variant_key)
    return float(section['t'] if 't' in section else section['t2'])


def post_v_offset(variant_key):
    """立柱截面在 v 方向的偏移（mm），使立柱与横担连接方式成立。

    角钢：立柱的 u-w 平面肢与横担竖直肢**背面相贴**（背靠背），偏移 ``+W``
    （与门型架左立柱同做法）。H 型钢：腹板共面（端面焊接），偏移 0。
    """
    if variant_is_hbeam(variant_key):
        return 0.0
    return inplane_width(variant_key)


def post_length(variant_key, height_mm, rack_type=1):
    """立柱下料长度（mm）。

    类型 1（立柱在横担下）：
      角钢非通长，``H - 肢厚 - 10``（顶端留 10 mm 施焊间隙）；H 型钢端面焊接，
      ``H - 横担截面高``（立柱顶面顶焊在横担下翼缘下表面）。
    类型 2（吊架，立柱在横担上）：
      H 型钢端面焊接，立柱下端面焊在横担上表面，``H``；角钢背靠背、底端留
      10 mm 施焊间隙，``H - 10``。
    """
    height_mm = float(height_mm)
    hbeam = variant_is_hbeam(variant_key)
    if hanger_type(rack_type):
        # 角钢背靠背：横担竖直肢（位于管位面以下）与立柱 u-w 平面肢搭接，
        # 立柱下端下探同样的搭接长度；故长度 H + (W - 肢厚 - 10)。
        # H 型钢端面焊在横担上表面，长度就是 H。
        length = (height_mm if hbeam
                  else height_mm + weld_contact_length(variant_key))
        if length <= 0.0:
            raise ValueError(
                '子项 %s 的立柱长 H=%.1f mm 过小。' % (variant_key, height_mm))
        return length
    if hbeam:
        length = height_mm - beam_depth(variant_key)
        if length <= 0.0:
            raise ValueError(
                '子项 %s 的立柱长 H=%.1f mm 过小：扣除横担截面高 %.1f 后为负。'
                % (variant_key, height_mm, beam_depth(variant_key)))
        return length
    thickness = beam_flange_thickness(variant_key)
    length = height_mm - thickness - WELD_GAP_MM
    if length <= 0.0:
        raise ValueError(
            '子项 %s 的立柱长 H=%.1f mm 过小：扣除肢厚 %.1f 与焊接间隙 %.0f '
            '后为负。' % (variant_key, height_mm, thickness, WELD_GAP_MM))
    return length


def weld_contact_length(variant_key, rack_type=1):
    """角钢立柱肢与横担竖直肢的贴合（焊缝）段高度（mm）。

    ``beam_depth - 肢厚 - 10``（两类型相同）。H 型钢为端面焊接，无搭接段，返回 0。
    """
    if variant_is_hbeam(variant_key):
        return 0.0
    contact = (beam_depth(variant_key) - beam_flange_thickness(variant_key)
               - WELD_GAP_MM)
    if contact <= 0.0:
        raise ValueError('子项 %s 的立柱与横担肢无有效搭接长度。' % variant_key)
    return contact


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------


def arm_span(variant_key, arm_length_mm, rack_type=1):
    """返回横担的 ``(u_start_mm, length_mm)``：以 u = 0 为中点，故起点 ``-L/2``。

    两类型的横担都沿 +u 扫掠、管位面朝上，仅置放高度不同（见
    :func:`member_origin_length`）。
    """
    length = float(arm_length_mm)
    return (-length / 2.0, length)


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标，mm）。"""
    _variant(variant_key)
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    return (_INSERTION_MODE, _INSERTION_POINT)


def member_axes(variant_key, member_kind, rack_type=1):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    各坐标架都保持右手系（axis_x × axis_y = axis_z），使闭合截面沿 axis_z
    扫掠时法向与扫掠方向一致。
    """
    variant = _variant(variant_key)
    family = variant['family']
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")

    if member_kind == 'post':
        if family == 'equal_angle':
            # 立柱（角钢）：截面的 x -> +v、y -> -u，开口朝 (-u, +v)。
            # 其 u-w 平面肢落在 +v 侧，与横担竖直肢背面相贴（见 post_v_offset）。
            return (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
        # H 型钢立柱：截面的 x(翼缘宽 B) -> -v、y(截面高 H) -> +u，沿 +w 扫掠。
        # 腹板在 v = 0，与横担腹板共面。
        return (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)

    if family == 'equal_angle':
        # 横担角钢：x -> -v、y -> -w，沿 +u 扫掠。竖直肢在 +v 侧向下，
        # 水平肢在顶部、其上表面即固定管子的面（管位面朝上；两类型同向）。
        return (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
    # 横担 H 型钢：x(翼缘宽 B) -> +v、y(截面高 H) -> +w，沿 +u 扫掠。
    # 腹板竖直、在 v = 0；管位面为上面翼缘外表面（类型 1 在 w = H、类型 2 在 w = 0）。
    return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)


def post_opening_direction(variant_key):
    """立柱角钢开口的朝向，返回 (u, v) 分量。H 型钢无此概念，返回 (0, 0)。"""
    if variant_is_hbeam(variant_key):
        return (0.0, 0.0)
    axis_x, axis_y, _axis_z = member_axes(variant_key, 'post')
    return (axis_x[0] + axis_y[0], axis_x[1] + axis_y[1])


def member_origin_length(variant_key, member_kind, height_mm, arm_length_mm,
                         rack_type=1):
    """返回 ``(origin_uvw_mm, length_mm)``：扫掠起点（相对所选线下端）与长度。

    两类型的横担都同向（管位面朝上），仅置放高度不同：
      类型 1：横担中心 ``w = H - 深度/2``（管位面在 w = H）；立柱自基座（w = 0）向上。
      类型 2：横担中心 ``w = -深度/2``（管位面在 w = 0）；立柱向上到 w = H，
              角钢立柱下端下探到 ``WELD_GAP - W`` 与横担竖直肢搭接（见 :func:`post_length`）。
    立柱轴线在 u = 0，v 向按 :func:`post_v_offset` 平移。
    """
    _variant(variant_key)
    height_mm = float(height_mm)
    depth = beam_depth(variant_key)
    hanger = hanger_type(rack_type)

    if member_kind == 'post':
        post_v = post_v_offset(variant_key)
        if hanger and not variant_is_hbeam(variant_key):
            # 角钢吊架：立柱下端下探到管位面以下，与横担竖直肢背靠背搭接
            # （搭接长度 = weld_contact_length）。
            bottom = -weld_contact_length(variant_key)
        else:
            bottom = 0.0
        return ((0.0, post_v, bottom),
                post_length(variant_key, height_mm, rack_type))
    if member_kind == 'arm':
        u_start, length = arm_span(variant_key, arm_length_mm, rack_type)
        if hanger:
            return ((u_start, 0.0, -depth / 2.0), length)
        return ((u_start, 0.0, height_mm - depth / 2.0), length)
    raise ValueError("member_kind 只能是 'post' 或 'arm'。")


def member_geometry(variant_key, member_kind, scale=1.0):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。"""
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


def world_direction(u_dir, v_dir, w_dir, components):
    """把截面轴在 (u, v, w) 下的分量换算为世界方向向量。"""
    ux, vx, wx = components
    return tuple(
        ux * u_dir[index] + vx * v_dir[index] + wx * w_dir[index]
        for index in range(3)
    )


# ---------------------------------------------------------------------------
# 所选直线的解析与坐标架
# ---------------------------------------------------------------------------

SelectedLine = namedtuple('SelectedLine', 'base top length_mm')


def parse_selected_line(pieces_mm):
    """把所选元素的折线（mm 点列）解析为竖直线（立柱轴线），并校验合规性。

    ``pieces_mm`` 为若干折线，每条折线是其顶点 ``(x, y, z)`` 的序列。要求展开后
    恰好为一段直线，且该段大致竖直（±:data:`VERTICAL_TOLERANCE_DEG` 内）。返回
    :class:`SelectedLine`：**base 为下端（基座）**、**top 为上端（横担端）**，
    ``length_mm`` 取两端的 Z 差（即立柱长 H）。
    """
    segments = _flatten_segments(pieces_mm)
    if len(segments) != 1:
        raise ValueError(
            '请选择一条竖直线段（立柱轴线），当前为 %d 段。' % len(segments))

    first, second = segments[0]
    if not _is_vertical(_sub(second, first)):
        raise ValueError('所选线段不是竖直线；请选择一条竖直的线段作为立柱轴线。')

    if second[2] >= first[2]:
        base, top = first, second
    else:
        base, top = second, first
    height = top[2] - base[2]
    if height < MIN_LINE_LENGTH_MM:
        raise ValueError('立柱长 H=%.1f mm 过短，要求 ≥ %.0f mm。'
                         % (height, MIN_LINE_LENGTH_MM))

    return SelectedLine(
        base=tuple(float(value) for value in base),
        top=tuple(float(value) for value in top),
        length_mm=float(height),
    )


def frame_axes(heading_deg=0.0):
    """返回世界坐标下的 ``(u_dir, v_dir, w_dir)`` 单位向量（立柱竖直）。

    ``w = Z``（竖直向上）；``u`` = 横担方向 = 面板「朝向」的水平方向；
    ``v = w × u``（管道轴线方向）。三者构成右手系。
    """
    heading = math.radians(float(heading_deg))
    u_dir = (math.cos(heading), math.sin(heading), 0.0)
    w_dir = (0.0, 0.0, 1.0)
    v_dir = _cross(w_dir, u_dir)
    return u_dir, v_dir, w_dir


def _is_vertical(vector):
    length = _norm(vector)
    if length <= 1.0e-9:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(vector[2]) / length)))
    return angle <= VERTICAL_TOLERANCE_DEG


def _flatten_segments(pieces_mm):
    segments = []
    for piece in pieces_mm:
        points = [tuple(float(value) for value in point) for point in piece]
        if len(points) < 2:
            raise ValueError('所选元素包含无效的折线段。')
        for index in range(len(points) - 1):
            segments.append((points[index], points[index + 1]))
    return segments


def _sub(left, right):
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _norm(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


# ---------------------------------------------------------------------------
# 允许垂直荷载（表 1 / 表 2，单位 kN；None 表示表格中的「—」）
# ---------------------------------------------------------------------------

# 表 1：角钢子项 A~C，列 L ≤ 250 / 500 / 750 / 1000。
LOAD_TABLE = {
    'A': {
        500: {250: 1.0, 500: None, 750: None, 1000: None},
        1000: {250: 0.5, 500: None, 750: None, 1000: None},
    },
    'B': {
        500: {250: 2.8, 500: 1.8, 750: None, 1000: None},
        1000: {250: 1.8, 500: 1.2, 750: None, 1000: None},
    },
    'C': {
        500: {250: 6.0, 500: 4.0, 750: 3.0, 1000: 2.4},
        1000: {250: 2.4, 500: 1.6, 750: 1.2, 1000: 0.9},
        1500: {250: 1.8, 500: 1.2, 750: 0.9, 1000: 0.6},
    },
    # 表 2：H 型钢子项 D~G，列 L ≤ 500 / 1000 / 1500 / 2000。
    'D': {
        1000: {500: 20.0, 1000: 10.0, 1500: None, 2000: None},
        2000: {500: 5.0, 1000: 5.0, 1500: None, 2000: None},
        3000: {500: None, 1000: None, 1500: None, 2000: None},
        4000: {500: None, 1000: None, 1500: None, 2000: None},
    },
    'E': {
        1000: {500: 40.0, 1000: 30.0, 1500: 20.0, 2000: 15.0},
        2000: {500: 20.0, 1000: 20.0, 1500: 20.0, 2000: 15.0},
        3000: {500: 10.0, 1000: 10.0, 1500: 10.0, 2000: 10.0},
        4000: {500: None, 1000: None, 1500: None, 2000: None},
    },
    'F': {
        1000: {500: 70.0, 1000: 40.0, 1500: 30.0, 2000: 25.0},
        2000: {500: 40.0, 1000: 40.0, 1500: 30.0, 2000: 25.0},
        3000: {500: 20.0, 1000: 20.0, 1500: 20.0, 2000: 20.0},
        4000: {500: 10.0, 1000: 10.0, 1500: 10.0, 2000: 10.0},
    },
    'G': {
        1000: {500: 100.0, 1000: 60.0, 1500: 50.0, 2000: 40.0},
        2000: {500: 50.0, 1000: 50.0, 1500: 50.0, 2000: 40.0},
        3000: {500: 35.0, 1000: 35.0, 1500: 35.0, 2000: 35.0},
        4000: {500: 20.0, 1000: 20.0, 1500: 20.0, 2000: 20.0},
    },
}

LoadResult = namedtuple('LoadResult', 'value used_height_mm used_arm_mm message')


def max_allowed_height(variant_key):
    """子项的最大允许立柱长 H（mm）：表中尚有可用（非「—」）值的最大行。"""
    table = LOAD_TABLE.get(str(variant_key).upper())
    if not table:
        return None
    usable = [h for h, row in table.items()
              if any(value is not None for value in row.values())]
    return max(usable) if usable else None


def max_allowed_arm_length(variant_key):
    """子项的最大允许横担长 L（mm）：表中尚有可用（非「—」）值的最大列。"""
    table = LOAD_TABLE.get(str(variant_key).upper())
    if not table:
        return None
    columns = set()
    for row in table.values():
        columns.update(row)
    usable = [column for column in columns
              if any(row.get(column) is not None for row in table.values())]
    return max(usable) if usable else None


def allowable_load(variant_key, height_mm, arm_length_mm):
    """按表 1 / 表 2 查允许垂直荷载。

    ``height_mm`` 为立柱长 H；``arm_length_mm`` 为横担长 L。H 取不超过输入的
    最大表列值（偏安全）；L 取不小于输入的最小列。返回 :class:`LoadResult`，
    查不到时 ``value`` 为 None 并在 ``message`` 中说明。
    """
    variant_key = str(variant_key).upper()
    table = LOAD_TABLE.get(variant_key)
    if table is None:
        return LoadResult(None, None, None, '子项 %s 无荷载表。' % variant_key)

    heights = sorted(table)
    usable = [h for h in heights
              if h <= float(height_mm) + LOAD_TOLERANCE_MM]
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
