# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``D15-[水平T形架].py`` 插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""水平 T 形架（D15）纯几何 / 数据逻辑（不依赖 Bentley 运行时可单测）。

由用户点选一条**水平直线**作为辅助线生成 T 形架：

* **辅助线**：起点为 ``P0``，方向为局部 ``u``。其长度 = ``L1 + tb``，其中
  ``L1`` 为构件A 的长度、``tb`` 为构件B 的腹板厚 / 肢厚。
* **构件A**：水平，起点 ``P0``、末端 ``P2 = P1 - tb*u``，长度 ``L1``。
* **构件B**：垂直于构件A（沿局部 ``v``），高度 ``L2``（用户输入），
  路径为 ``P3 -> P4``。

五个路径点（局部基 u-v-w，原点取辅助线起点）：

    u = 辅助线方向（世界水平）
    w = Z 向上
    v = w x u            （构件B 的展开方向）

    P0 = 0                        辅助线起点 = 构件A 起点
    P1 = P0 + (L1 + tb)*u         辅助线终点
    P2 = P1 - tb*u                构件A 末端
    P3/P4 = 构件B 路径两端，见 :func:`path_points`

两个类型只在构件B 的偏心方式上不同：

* **类型 1**：构件B 以 ``P2`` 为中心上下对称展开 —— ``P3 = P2 - (L2/2)v``、
  ``P4 = P2 + (L2/2)v``。
* **类型 2**：构件B 从构件A 的下侧偏心起算 —— ``P3 = P2 - (wA/2 + 15)v``、
  ``P4 = P3 + L2*v``（``wA`` 为构件A 的截面宽度）。两种类型的 ``|P3P4|``
  都等于 ``L2``。

**插入基准（拉伸起点）**：等边角钢取「外接正方形中心」；槽钢与工字钢 / H 型钢
取「几何中心」。基准点即扫掠起点，落在上述路径点上。

本模块只做纯数学：不引用 Bentley API、不读文件、不建模型。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple

_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/水平T形架/，插件根目录需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_registry  # noqa: E402


# ---------------------------------------------------------------------------
# 容差与限制
# ---------------------------------------------------------------------------

# 辅助线偏离水平方向的上限（°）：超出即拒绝，避免把斜线当水平辅助线。
HORIZONTAL_TOLERANCE_DEG = 5.0
# 辅助线最小长度（mm）。
MIN_LINE_LENGTH_MM = 150.0
# 构件B 最小高度（mm）。
MIN_ARM_LENGTH_MM = 50.0
# 荷载表的匹配容差（mm）。
LOAD_TOLERANCE_MM = 1.0
# 类型 2 中构件B 自构件A 下侧再向下的固定偏心量（mm）。
TYPE2_DROP_MM = 15.0

# 构件B 的贴合偏移（mm）——非对称截面必须错位才能与构件A 贴合：
#   等边角钢：沿轴线方向让开 ``翼缘/2 − 10``（50×6 即 15），再竖直上移
#             ``肢端面宽度``（即肢厚 t，50×6 即 6）使内侧肢面与构件A 贴合。
#   槽钢：沿轴线方向让开 ``翼缘宽度/2``（[14a 即 29）。
#   工字钢 / H 型钢：对称截面，无需偏移。
#
# 两个分量分别作用在局部 ``v``（沿构件B 自身展开方向）与 ``w``（竖直）上；
# 只有 ``w`` 分量影响构件A、构件B 的贴面是否吻合。
B_FIT_CLEARANCE_MM = 10.0

# 贴合偏移规则（按构件B 的型式）：
#   'clearance'  —— u 让开 (翼缘/2 − B_FIT_CLEARANCE_MM)，w 上移肢厚（角钢）；
#   'half_width' —— u 偏移 = −翼缘/2 + 腹板厚（槽钢）：从半宽里**扣掉**腹板厚，
#                   使腹板侧让到构件A 末端面以内；
#   'symmetric'  —— 对称截面，不偏移（工字钢 / H 型钢）。
_FIT_OFFSET_RULES = {
    'equal_angle': ('clearance', B_FIT_CLEARANCE_MM),
    'parallel_channel': ('half_width',),
    'ordinary_ibeam': ('symmetric',),
    'hot_rolled_h': ('symmetric',),
}

ALL_RACK_TYPES = (1, 2)
# 类型 2：构件B 偏心。类型 1：构件B 与构件A 同中心。
ECCENTRIC_RACK_TYPES = (2,)

# 接点焊接形式（图注）：只进入管架编号，不影响几何与截面选型。
WELD_JOINT_CODES = ('A', 'B', 'C', 'D', 'E', 'F')
DEFAULT_WELD_JOINT = 'A'


def is_eccentric_type(rack_type):
    """是否为类型 2（构件B 向下偏心）。"""
    try:
        return int(rack_type) in ECCENTRIC_RACK_TYPES
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 子项（图 表 2 / 表 3）与型钢截面
# ---------------------------------------------------------------------------

# 图 表 3 的子项代号与构件A 显示名。
VARIANT_LABELS = {
    'A': '∠50×6',
    'B': '∠75×7',
    'C': '[10',
    'D': 'H100×100×6×8',
    'E': 'H150×150×7×10',
}
DEFAULT_VARIANT = 'A'

# 表 2：构件A / 构件B 的型钢来源（family 指向 型钢截面生成器 的型式）。
VARIANTS = {
    'A': {
        'member_a': {'family': 'equal_angle', 'profile': 'L50x50x6'},
        'member_b': {'family': 'equal_angle', 'profile': 'L50x50x6'},
    },
    'B': {
        'member_a': {'family': 'equal_angle', 'profile': 'L75x75x7'},
        'member_b': {'family': 'equal_angle', 'profile': 'L75x75x7'},
    },
    'C': {
        'member_a': {'family': 'parallel_channel', 'profile': '10'},
        'member_b': {'family': 'parallel_channel', 'profile': '14a'},
    },
    'D': {
        'member_a': {'family': 'hot_rolled_h', 'profile': 'H100x100x6x8xr8'},
        'member_b': {'family': 'parallel_channel', 'profile': '14a'},
    },
    'E': {
        'member_a': {'family': 'hot_rolled_h', 'profile': 'H150x150x7x10xr8'},
        'member_b': {'family': 'parallel_channel', 'profile': '20a'},
    },
}


def variant_choices():
    """返回 ``(代号, 显示文本)``，按代号排序，供下拉框使用。"""
    return tuple((key, variant_label(key)) for key in sorted(VARIANTS))


def variant_label(variant_key):
    return '%s  |  %s' % (variant_key, VARIANT_LABELS.get(
        str(variant_key).upper(), variant_key))


def weld_joint_choices():
    """接点焊接形式的下拉项（仅编号使用）。"""
    return tuple((code, '型式 %s' % code) for code in WELD_JOINT_CODES)


def _variant(variant_key):
    try:
        return VARIANTS[str(variant_key).upper()]
    except KeyError:
        raise ValueError('未知子项：%s。' % variant_key)


def variant_is_hbeam(variant_key):
    """构件A 是否为 H 型钢 / 工字钢（几何中心 = 重心）。"""
    return _variant(variant_key)['member_a']['family'] in (
        'hot_rolled_h', 'ordinary_ibeam')


def member_source(variant_key, member_kind):
    """返回构件的 ``(family, profile)``。"""
    if member_kind not in ('post', 'arm'):
        raise ValueError("member_kind 只能是 'post'（构件A）或 'arm'（构件B）。")
    key = 'member_a' if member_kind == 'post' else 'member_b'
    source = _variant(variant_key)[key]
    return source['family'], source['profile']


def section_dimensions(variant_key, member_kind):
    """返回构件的型钢截面尺寸字典（mm）。"""
    family, profile = member_source(variant_key, member_kind)
    return steel_registry.get_section(family, profile)


def specification(variant_key, member_kind):
    """构件的显示规格文本。"""
    family, profile = member_source(variant_key, member_kind)
    section = steel_registry.get_section(family, profile)
    if family == 'equal_angle':
        return '∠%g×%g' % (section['B'], section['t'])
    if family == 'parallel_channel':
        return '[%s' % profile
    return 'H%s×%s×%s×%s' % (section['H'], section['B'],
                              _web_thickness(section),
                              _flange_thickness(section))


def assembly_specification(variant_key):
    """整组记录的规格文本：构件A / 构件B。"""
    return '%s + %s' % (specification(variant_key, 'post'),
                        specification(variant_key, 'arm'))


# ---------------------------------------------------------------------------
# 构件截面尺寸
# ---------------------------------------------------------------------------


def _web_thickness(section):
    """腹板厚度：槽钢 ``tw`` / H 型钢 ``t1``。"""
    for key in ('tw', 't1'):
        if key in section:
            return section[key]
    raise ValueError('截面缺少腹板厚度字段（tw / t1）。')


def _flange_thickness(section):
    """翼缘厚度：槽钢 ``tf`` / H 型钢 ``t2``；角钢退化为肢厚 ``t``。"""
    for key in ('tf', 't2', 't'):
        if key in section:
            return section[key]
    raise ValueError('截面缺少翼缘厚度字段（tf / t2）。')


def member_width(variant_key, member_kind):
    """构件截面在「基准所在平面内的宽度方向」上的总宽（mm）。

    等边角钢取外接正方形边长 ``B``；槽钢与工字钢 / H 型钢取翼缘宽 ``B``。
    """
    return float(section_dimensions(variant_key, member_kind)['B'])


def member_half_width(variant_key, member_kind='post'):
    """构件A 的半宽 ``wA/2``（类型 2 的偏心量用）。"""
    return member_width(variant_key, member_kind) / 2.0


def member_web_thickness(variant_key, member_kind='arm'):
    """构件B 的腹板厚 / 肢厚 ``tb``，也就是辅助线比构件A 长出的部分。"""
    section = section_dimensions(variant_key, member_kind)
    if member_source(variant_key, member_kind)[0] == 'equal_angle':
        return float(section['t'])
    return float(_web_thickness(section))


def member_fit_offset(variant_key, member_kind='arm'):
    """构件B 为与构件A 贴合所需的偏移 ``(u_mm, v_mm, w_mm)``。

    非对称截面必须错位，否则无法与构件A 贴面。分量含义（局部基 u-v-w）：

    * **``w``**：竖直贴合分量。等边角钢取 ``+肢厚 t``，使构件B 的内侧肢面正好
      落在构件A 角钢的内侧肢面上（50×6 时 B 下边 −19 = A 肢面 −19，差值为 0）。
    * **``u``**：沿辅助线方向的让位分量。等边角钢取 ``−(翼缘/2 − 10)``
      （留出 10 mm 施焊槽）；槽钢取 ``−翼缘/2 + 腹板厚 tw``——从半宽里**扣掉**
      腹板厚，使腹板侧让到构件A 末端面以内。
    * **``v``**：沿构件B 自身展开方向，本规则不产生偏移。

    工字钢 / H 型钢为对称截面，无需偏移，返回 ``(0, 0, 0)``。
    """
    family, _profile = member_source(variant_key, member_kind)
    section = section_dimensions(variant_key, member_kind)
    width = float(section['B'])
    rule = _FIT_OFFSET_RULES.get(family, ('symmetric',))
    if rule[0] == 'clearance':
        return (-(width / 2.0 - rule[1]), 0.0, float(section['t']))
    if rule[0] == 'half_width':
        return (-width / 2.0 + _web_thickness(section), 0.0, 0.0)
    return (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# 所选直线的解析与坐标架
# ---------------------------------------------------------------------------

SelectedLine = namedtuple('SelectedLine', 'base top length_mm direction')


def parse_selected_line(pieces_mm):
    """把所选元素的折线（mm 点列）解析为水平辅助线并校验。

    要求展开后恰好为一段直线、且大致水平（±:data:`HORIZONTAL_TOLERANCE_DEG`
    以内）。返回 :class:`SelectedLine`，``base`` 为起点、``top`` 为终点，
    ``direction`` 为起点指向终点的单位向量。
    """
    segments = _flatten_segments(pieces_mm)
    if len(segments) != 1:
        raise ValueError(
            '请选择一条水平直线段（构件A 的辅助线），当前为 %d 段。' % len(segments))

    first, second = segments[0]
    vector = _sub(second, first)
    length = _norm(vector)
    if length <= 1.0e-9:
        raise ValueError('所选线段长度为零。')
    if not _is_horizontal(vector):
        raise ValueError('所选线段不是水平线；请选择一条水平线段作为辅助线。')
    if length < MIN_LINE_LENGTH_MM:
        raise ValueError('辅助线长 %.1f mm 过短，要求 ≥ %.0f mm。'
                         % (length, MIN_LINE_LENGTH_MM))

    base = tuple(float(value) for value in first)
    top = tuple(float(value) for value in second)
    direction = tuple(component / length for component in vector)
    return SelectedLine(base=base, top=top, length_mm=float(length),
                        direction=direction)


def frame_axes(line):
    """返回世界坐标下的 ``(u_dir, v_dir, w_dir)`` 单位向量。

    ``u`` = 辅助线方向；``w = Z``（竖直向上）；``v = w × u``。
    """
    u_dir = tuple(float(component) for component in line.direction)
    w_dir = (0.0, 0.0, 1.0)
    horizontal = math.sqrt(u_dir[0] * u_dir[0] + u_dir[1] * u_dir[1])
    if horizontal <= 1.0e-9:
        raise ValueError('辅助线不能是竖直的。')
    # w × u 在水平面内，且与 u 垂直。
    v_dir = (w_dir[1] * u_dir[2] - w_dir[2] * u_dir[1],
             w_dir[2] * u_dir[0] - w_dir[0] * u_dir[2],
             w_dir[0] * u_dir[1] - w_dir[1] * u_dir[0])
    return u_dir, v_dir, w_dir


def world_direction(u_dir, v_dir, w_dir, components):
    """把截面轴在 (u, v, w) 下的分量换算为世界方向向量。"""
    ux, vx, wx = components
    return tuple(
        ux * u_dir[index] + vx * v_dir[index] + wx * w_dir[index]
        for index in range(3)
    )


def world_point(base_mm, u_dir, v_dir, w_dir, u_offset, v_offset, w_offset=0.0):
    """把局部 (u, v, w) 偏移换算为世界坐标（mm）。"""
    return tuple(
        base_mm[index]
        + u_offset * u_dir[index]
        + v_offset * v_dir[index]
        + w_offset * w_dir[index]
        for index in range(3)
    )


# ---------------------------------------------------------------------------
# 五个路径点
# ---------------------------------------------------------------------------


def path_points(line, variant_key, rack_type, arm_length_mm):
    """计算 P0 ~ P4 的世界坐标与派生长度。

    返回字典：

        line_length_mm  辅助线长（= L1 + tb）
        tb_mm           构件B 腹板厚 / 肢厚
        l1_mm           构件A 长度 = 辅助线长 - tb
        l2_mm           构件B 高度（用户输入）
        w_a_mm          构件A 截面宽度
        offset_mm       类型 2 的下偏量 = wA/2 + 15（类型 1 不用）
        p0 .. p4        世界坐标（mm）
    """
    line_length = float(line.length_mm)
    l2 = float(arm_length_mm)
    if l2 < MIN_ARM_LENGTH_MM:
        raise ValueError('构件B 高度 L2=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (l2, MIN_ARM_LENGTH_MM))

    tb = member_web_thickness(variant_key, 'arm')
    l1 = line_length - tb
    if l1 <= 0.0:
        raise ValueError(
            '辅助线长 %.1f mm 过短：扣除构件B 腹板厚 %.1f mm 后构件A 长度为负。'
            % (line_length, tb))

    u_dir, v_dir, w_dir = frame_axes(line)
    base = line.base

    p0 = world_point(base, u_dir, v_dir, w_dir, 0.0, 0.0)
    p1 = world_point(base, u_dir, v_dir, w_dir, line_length, 0.0)
    p2 = world_point(base, u_dir, v_dir, w_dir, l1, 0.0)

    w_a = member_width(variant_key, 'post')
    fit_u, fit_v, fit_w = member_fit_offset(variant_key, 'arm')
    if is_eccentric_type(rack_type):
        drop = w_a / 2.0 + TYPE2_DROP_MM
        p3 = world_point(base, u_dir, v_dir, w_dir, l1, -drop)
        p4 = world_point(base, u_dir, v_dir, w_dir, l1, -drop + l2)
    else:
        drop = 0.0
        p3 = world_point(base, u_dir, v_dir, w_dir, l1, -l2 / 2.0)
        p4 = world_point(base, u_dir, v_dir, w_dir, l1, +l2 / 2.0)

    return {
        'line_length_mm': line_length,
        'tb_mm': tb,
        'l1_mm': l1,
        'l2_mm': l2,
        'w_a_mm': w_a,
        'offset_mm': drop,
        'fit_u_mm': fit_u,
        'fit_v_mm': fit_v,
        'fit_w_mm': fit_w,
        'p0': p0, 'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4,
        'u_dir': u_dir, 'v_dir': v_dir, 'w_dir': w_dir,
    }


def pipe_rack_number(rack_type, variant_key, weld_joint, l1_mm, l2_mm,
                     stiffener=None):
    """管架编号 ``D15-类型-子项-接点焊接形式-L1-L2[-筋板 h×w]``（尺寸取整）。

    末段 ``stiffener``（筋板尺寸 ``h × w``）是**用户手输的纯文字**：本版不建筋板
    实体，这段只写进编号 —— 写了就附加（去掉首尾空白、其余原样保留，不做单位换算
    也不校验），留空 / 只输空格则整段不附加。
    """
    joint = str(weld_joint).strip().upper()
    if joint not in WELD_JOINT_CODES:
        raise ValueError('未知接点焊接形式：%s（可选 %s）。'
                         % (weld_joint, '/'.join(WELD_JOINT_CODES)))
    number = 'D15-%d-%s-%s-%d-%d' % (
        int(rack_type), str(variant_key).upper(), joint,
        round_half_up(l1_mm), round_half_up(l2_mm))
    tail = str(stiffener or '').strip()
    return '%s-%s' % (number, tail) if tail else number


def round_half_up(value):
    """四舍五入到整数（Python 的 round 为「银行家舍入」，不可用于编号）。"""
    return int(math.floor(float(value) + 0.5))


# ---------------------------------------------------------------------------
# 构件截面本地方位与扫掠布局
# ---------------------------------------------------------------------------

# 构件截面在 (u, v, w) 下的基准三轴。每个坐标架都保持右手系
# （axis_x × axis_y = axis_z），使闭合截面沿 axis_z 扫掠时法向与扫掠方向一致。
#
# 基准取「截面高度方向竖直」；实际安装姿态再由 _ROTATION_DEG 绕扫掠轴旋转得到。
_BASE_MEMBER_AXES = {
    'post': ((0.0, 0.0, 1.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    'arm': ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
}

# 绕扫掠轴（axis_z）的截面旋转量（°），按「构件 + 型式」给出：
#   构件A（沿 u 扫掠）：等边角钢 180 —— 水平肢外表面朝上（原姿态上下颠倒）；
#                       槽钢 / 工字钢 / H 型钢 90。
#   构件B（沿 v 扫掠）：等边角钢 180 —— 同上；槽钢 90；工字钢 / H 型钢 90。
# **实测若姿态仍不对，只调这张表即可。**
_ROTATION_DEG = {
    ('post', 'equal_angle'): 180.0,
    ('post', 'parallel_channel'): 90.0,
    ('post', 'ordinary_ibeam'): 90.0,
    ('post', 'hot_rolled_h'): 90.0,
    ('arm', 'equal_angle'): 180.0,
    ('arm', 'parallel_channel'): 90.0,
    ('arm', 'ordinary_ibeam'): 90.0,
    ('arm', 'hot_rolled_h'): 90.0,
}

# 插入基准模式：等边角钢取外接正方形中心，槽钢 / 工字钢 / H 型钢取几何中心。
_INSERTION_MODES = {
    'equal_angle': 'geometric_center',
    'parallel_channel': 'geometric_center',
    'ordinary_ibeam': 'geometric_center',
    'hot_rolled_h': 'geometric_center',
}


def member_rotation_deg(variant_key, member_kind):
    """构件绕扫掠轴的截面旋转量（°）。"""
    _variant(variant_key)
    if member_kind not in _BASE_MEMBER_AXES:
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    family, _profile = member_source(variant_key, member_kind)
    return _ROTATION_DEG.get((member_kind, family), 0.0)


def member_axes(variant_key, member_kind):
    """返回 ``(axis_x, axis_y, axis_z)``，各为 (u, v, w) 下的分量。

    在基准姿态上叠加 :func:`member_rotation_deg` 的绕轴旋转；仍为右手系。
    """
    _variant(variant_key)
    if member_kind not in _BASE_MEMBER_AXES:
        raise ValueError("member_kind 只能是 'post' 或 'arm'。")
    axis_x, axis_y, axis_z = _BASE_MEMBER_AXES[member_kind]
    angle = member_rotation_deg(variant_key, member_kind)
    return (_rotate_about_axis(axis_x, axis_z, angle),
            _rotate_about_axis(axis_y, axis_z, angle),
            axis_z)


def member_section_params(variant_key, member_kind):
    """返回 ``(insertion_mode, insertion_point_mm)``（截面本地坐标）。"""
    family, _profile = member_source(variant_key, member_kind)
    mode = _INSERTION_MODES.get(family)
    if mode is None:
        raise ValueError('未登记插入基准的型式：%s。' % family)
    return mode, (0.0, 0.0)


def member_geometry(variant_key, member_kind, scale=1.0):
    """构建构件截面轮廓（mm，或以 ``scale`` 缩放到 UOR）。

    委托给 ``型钢截面生成器`` 的对应几何模块；轮廓保持真圆弧。
    """
    family, profile = member_source(variant_key, member_kind)
    section = steel_registry.get_section(family, profile)
    geometry_module = steel_registry.get_family(family).geometry
    scaled = geometry_module.scale_section(section, float(scale))
    mode, insertion_point = member_section_params(variant_key, member_kind)
    point = geometry_module.Point2d(insertion_point[0] * float(scale),
                                    insertion_point[1] * float(scale))
    builder = getattr(geometry_module,
                      steel_registry.get_family(family).builder)
    return builder(scaled, mode, point)


def member_placement(variant_key, member_kind, points, scale=1.0):
    """返回构件的 ``(origin_uor, axis_x, axis_y, axis_z, length_uor)``。

    ``post``（构件A）沿 +u 自 P0 扫掠至 P1；``arm``（构件B）沿 +v 自 P3 扫掠至 P4，
    并按 :func:`member_fit_offset` 做贴合偏移（非对称截面必须错位）。
    坐标架由 :func:`member_axes` 与 :func:`frame_axes` 给出。
    """
    u_dir, v_dir, w_dir = points['u_dir'], points['v_dir'], points['w_dir']
    axes = member_axes(variant_key, member_kind)
    axis_x = world_direction(u_dir, v_dir, w_dir, axes[0])
    axis_y = world_direction(u_dir, v_dir, w_dir, axes[1])
    axis_z = world_direction(u_dir, v_dir, w_dir, axes[2])
    if member_kind == 'post':
        origin = points['p0']
        length_mm = points['l1_mm']
    else:
        # 沿 u 让位、沿 v 平移、沿 w 竖直偏移，使构件B 与构件A 贴合。
        fit_u = points.get('fit_u_mm', 0.0)
        fit_v = points.get('fit_v_mm', 0.0)
        fit_w = points.get('fit_w_mm', 0.0)
        origin = tuple(
            points['p3'][index]
            + fit_u * u_dir[index]
            + fit_v * v_dir[index]
            + fit_w * w_dir[index]
            for index in range(3)
        )
        length_mm = points['l2_mm']
    origin_uor = tuple(component * float(scale) for component in origin)
    return (origin_uor, axis_x, axis_y, axis_z,
            length_mm * float(scale))


# ---------------------------------------------------------------------------
# 允许荷载（图 表 1）
# ---------------------------------------------------------------------------

# 表 1：``LOAD_TABLE[子项] = {L1 列: 允许荷载 kN 或 None}``；None 为图中的「—」。
LOAD_TABLE = {
    'A': {250: 0.3, 500: 0.15, 750: None, 1000: None},
    'B': {250: 1.0, 500: 0.5, 750: None, 1000: None},
    'C': {250: 2.0, 500: 1.0, 750: None, 1000: None},
    'D': {250: 8.0, 500: 4.0, 750: 2.5, 1000: None},
    'E': {250: 12.0, 500: 8.0, 750: 6.0, 1000: 4.0},
}

# 表 2：``MAX. L2``（mm），按类型分开。
MAX_L2_TABLE = {
    'A': {1: 250, 2: 500},
    'B': {1: 250, 2: 500},
    'C': {1: 250, 2: 500},
    'D': {1: 250, 2: 500},
    'E': {1: 500, 2: 1000},
}

LoadResult = namedtuple('LoadResult', 'value used_l1_mm message')


def max_allowed_l1(variant_key):
    """子项的最大允许构件A 长度 L1（mm）：表中尚有可用值的最大列。"""
    table = LOAD_TABLE.get(str(variant_key).upper())
    if not table:
        return None
    usable = [column for column, value in table.items() if value is not None]
    return max(usable) if usable else None


def max_allowed_l2(variant_key, rack_type):
    """子项在给定类型下的最大允许构件B 高度 L2（mm）。"""
    row = MAX_L2_TABLE.get(str(variant_key).upper())
    if not row:
        return None
    return row.get(int(rack_type))


def allowable_load(variant_key, l1_mm, rack_type=None):
    """按图 表 1 查允许荷载（kN）。

    ``l1_mm`` 为构件A 长度；L1 取不小于输入的最小列（偏保守）。
    """
    variant_key = str(variant_key).upper()
    table = LOAD_TABLE.get(variant_key)
    if table is None:
        return LoadResult(None, None, '子项 %s 无荷载表。' % variant_key)

    columns = sorted(table)
    chosen = None
    for column in columns:
        if float(l1_mm) <= column + LOAD_TOLERANCE_MM:
            chosen = column
            break
    if chosen is None:
        return LoadResult(
            None, None,
            'L1=%.0f mm 超出表中上限 %d mm。' % (l1_mm, columns[-1]))
    value = table[chosen]
    if value is None:
        return LoadResult(
            None, chosen,
            '子项 %s、L1≤%d 一栏表中为空（—）。' % (variant_key, chosen))
    return LoadResult(float(value), chosen,
                      '按 L1≤%d mm 取用。' % chosen)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _flatten_segments(pieces_mm):
    segments = []
    for piece in pieces_mm:
        points = [tuple(float(value) for value in point) for point in piece]
        if len(points) < 2:
            raise ValueError('所选元素包含无效的折线段。')
        for index in range(len(points) - 1):
            segments.append((points[index], points[index + 1]))
    return segments


def _is_horizontal(vector):
    length = _norm(vector)
    if length <= 1.0e-9:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(vector[2]) / length)))
    return 90.0 - angle <= HORIZONTAL_TOLERANCE_DEG


def _sub(left, right):
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _dot(first, second):
    return sum(first[index] * second[index] for index in range(3))


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _norm(vector):
    return math.sqrt(sum(component * component for component in vector))


def _rotate_about_axis(vector, axis, angle_deg):
    """把 *vector* 绕单位轴 *axis* 旋转 *angle_deg*（右手定则，**轴看向原点**）。

    与 ``steel_sweep_geometry.rotate_frame`` 同一约定：正角在沿轴观察时顺时针，
    即数学上是绕轴按右手定则旋转 −angle。轴为零向量或角度为零时原样返回。
    """
    angle = math.radians(float(angle_deg))
    if abs(angle) < 1.0e-12:
        return tuple(float(component) for component in vector)
    length = _norm(axis)
    if length <= 1.0e-12:
        return tuple(float(component) for component in vector)
    axis = tuple(component / length for component in axis)

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    cross = _cross(axis, vector)
    dot = _dot(axis, vector)
    return tuple(
        vector[index] * cos_a
        - cross[index] * sin_a
        + axis[index] * dot * (1.0 - cos_a)
        for index in range(3)
    )
