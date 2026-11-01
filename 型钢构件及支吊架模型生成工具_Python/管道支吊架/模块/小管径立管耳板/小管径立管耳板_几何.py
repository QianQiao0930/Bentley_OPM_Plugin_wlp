# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 尺寸推导库供 ``F10-[小管径立管耳板].py`` 等插件 ``import``
# 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""小管径立管耳板（DN15~DN50）纯数据 / 尺寸推导（不依赖 Bentley 运行时可单测）。

本模块把「小管径立管耳板」标准图的规则集中在一起，供 ``F10-[小管径立管耳板].py``
调用；只做**数据与尺寸**，不涉及任何 Bentley 几何调用。

设计口径（按用户提供的资料）：

* **管径** DN15~DN50，管外径按 **ASME B36.10M** 公称外径查表；
* **长度代码**（表 1）：``1/2/3`` → 耳板宽 ``L = 100/150/200`` mm；
* **高度代码**（表 2）：``A/B/C/D`` → 耳板高 ``H = 50/100/150/200`` mm
  （``H`` 为「耳板上缘 → 底板顶面」的距离），并附「允许垂直管长度」；
* **材料代码**（表 3）：``L / C1 / C2 / A1 / A2 / S`` → 管道材料 + 温度范围、
  **耳板材料**、**底板材料**（底板恒为 Q235B）；
* 两块耳板绕管轴 **180° 对称**；耳板为**径向竖直板**，内立边与管外壁相焊；
* **底板** ``70（径向）× 120（切向）× 10``，**外缘与耳板外缘齐平**，顶面与
  耳板底端直接焊接；
* **固定 Y**：底板每块开 2×Ø14 孔并配 M12×40 单头螺栓；**不固定 N**：不开孔、
  不配螺栓；
* 编号：``F10-长度代码-高度代码-材料代码-方位角-固定标志``，方位角只标较小的
  那一个（0~180）。
"""

from __future__ import division

import math
from collections import namedtuple


# ---------------------------------------------------------------------------
# 管径：DN → 公称外径（ASME B36.10M）
# ---------------------------------------------------------------------------

DN_MIN = 15
DN_MAX = 50

# DN -> (公称外径 mm, NPS 文本)
DN_OD_TABLE = {
    15: (21.3, '1/2"'),
    20: (26.7, '3/4"'),
    25: (33.4, '1"'),
    32: (42.2, '1 1/4"'),
    40: (48.3, '1 1/2"'),
    50: (60.3, '2"'),
}

# 公称直径匹配容差（mm）：读到的管道公称直径与表中 DN 的允许偏差。
DN_MATCH_ABS_MM = 3.0
DN_MATCH_RATIO = 0.15


def dn_choices():
    """返回 ``(dn, 显示文本)``，按 DN 升序，供下拉框使用。"""
    return tuple((dn, dn_label(dn)) for dn in sorted(DN_OD_TABLE))


def dn_label(dn):
    od, nps = _row(dn)
    return 'DN%d  |  %s  |  OD %.1f' % (int(dn), nps, od)


def od_mm(dn):
    return float(_row(dn)[0])


def nps_text(dn):
    return _row(dn)[1]


def _row(dn):
    try:
        return DN_OD_TABLE[int(dn)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('管径 DN%s 超出本次范围 DN%d~DN%d。'
                         % (dn, DN_MIN, DN_MAX))


def match_dn(nominal_mm):
    """把管道公称直径（mm）匹配到表内 DN；匹配不上返回 ``None``。"""
    if nominal_mm is None:
        return None
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    if value <= 0.0:
        return None
    best = min(DN_OD_TABLE, key=lambda key: abs(key - value))
    if abs(best - value) <= max(DN_MATCH_ABS_MM, DN_MATCH_RATIO * value):
        return best
    return None


# ---------------------------------------------------------------------------
# 表 1 / 表 2 / 表 3
# ---------------------------------------------------------------------------

# 表 1：长度代码 → 耳板宽 L（mm）。
LENGTH_CODES = {
    '1': 100.0,
    '2': 150.0,
    '3': 200.0,
}

# 表 2：高度代码 → 耳板高 H（mm）+ 允许的垂直管长度（m）。
HEIGHT_CODES = {
    'A': (50.0, 10.0),
    'B': (100.0, 20.0),
    'C': (150.0, 40.0),
    'D': (200.0, 60.0),
}

# 表 3：材料代码 → 管道材料 / 温度范围 / 耳板材料 / 底板材料。
MATERIAL_CODES = {
    'L': {'pipe_material': '低温碳钢', 'temp_range': '-40 ~ -21',
          'ear_material': 'Q345R', 'base_material': 'Q235B'},
    'C1': {'pipe_material': '碳钢', 'temp_range': '-20 ~ 300',
           'ear_material': 'Q235B', 'base_material': 'Q235B'},
    'C2': {'pipe_material': '碳钢', 'temp_range': '301 ~ 425',
           'ear_material': 'Q345R', 'base_material': 'Q235B'},
    'A1': {'pipe_material': '铬钼钢', 'temp_range': '≤500',
           'ear_material': '15CrMoR', 'base_material': 'Q235B'},
    'A2': {'pipe_material': '铬钼钢', 'temp_range': '501 ~ 550',
           'ear_material': '12Cr1MoVR', 'base_material': 'Q235B'},
    'S': {'pipe_material': '不锈钢', 'temp_range': '-196 ~ 700',
          'ear_material': '06Cr19Ni10', 'base_material': 'Q235B'},
}

DEFAULT_DN = 25
DEFAULT_LENGTH_CODE = '1'
DEFAULT_HEIGHT_CODE = 'A'
DEFAULT_MATERIAL_CODE = 'C1'
DEFAULT_AZIMUTH_DEG = 0.0

# 管架名称前缀（图 1：名称 = F10）。
PIPE_NAME_PREFIX = 'F10'

# 固定常量（图中未随 DN 变化）。
EAR_THICKNESS_MM = 10.0          # 耳板厚度
BASE_PLATE_RADIAL_MM = 70.0      # 底板径向（70）
BASE_PLATE_TANGENTIAL_MM = 120.0  # 底板切向（120）
BASE_PLATE_THICKNESS_MM = 10.0   # 底板厚度
HOLE_DIAMETER_MM = 14.0          # 2×Ø14
BOLT_SPEC = 'M12×40'             # M12×40 单头螺栓
BOLT_DIAMETER_MM = 12.0
BOLT_LENGTH_MM = 40.0
# 两个螺栓孔沿切向的偏置（孔心距 = 2×偏置 = 80）。
HOLE_TANGENTIAL_OFFSET_MM = 40.0

# 螺栓头简化比例（对边 ≈ 1.5d，头高 ≈ 0.7d）。
BOLT_HEAD_ACROSS_FLATS_RATIO = 1.5
BOLT_HEAD_HEIGHT_RATIO = 0.7

# 管轴竖直判定容差（°）：与竖直方向夹角不超过该值即视为立管。
VERTICAL_TOLERANCE_DEG = 5.0


def length_choices():
    return tuple((code, length_label(code)) for code in sorted(LENGTH_CODES))


def length_label(code):
    return '%s  |  L = %d mm' % (code, int(length_for_code(code)))


def height_choices():
    return tuple((code, height_label(code)) for code in sorted(HEIGHT_CODES))


def height_label(code):
    height, allowable = height_for_code(code)
    return '%s  |  H = %d mm  |  允许垂直管 %.0f m' % (
        code, int(height), allowable)


def material_choices():
    return tuple((code, material_label(code)) for code in sorted(MATERIAL_CODES))


def material_label(code):
    row = material_for_code(code)
    return '%s  |  %s %s  |  耳板 %s' % (
        code, row['pipe_material'], row['temp_range'], row['ear_material'])


def length_for_code(code):
    try:
        return float(LENGTH_CODES[str(code).upper()])
    except KeyError:
        raise ValueError('未知长度代码：%s（应为 1/2/3）。' % code)


def height_for_code(code):
    try:
        return HEIGHT_CODES[str(code).upper()]
    except KeyError:
        raise ValueError('未知高度代码：%s（应为 A/B/C/D）。' % code)


def material_for_code(code):
    try:
        return dict(MATERIAL_CODES[str(code).upper()])
    except KeyError:
        raise ValueError('未知材料代码：%s（应为 L/C1/C2/A1/A2/S）。' % code)


def allowable_vertical_pipe_m(code):
    return float(height_for_code(code)[1])


# ---------------------------------------------------------------------------
# 方位角与编号
# ---------------------------------------------------------------------------


def normalize_azimuth(azimuth_deg):
    """把方位角归一到 ``[0, 360)``。"""
    return float(azimuth_deg) % 360.0


def label_azimuth_deg(azimuth_deg):
    """编号里使用的方位角：两块耳板只标较小的那一个（``[0, 180)``）。"""
    return normalize_azimuth(azimuth_deg) % 180.0


def format_angle(deg):
    """角度文本：整数不带小数，其余最多 1 位小数（省略 ° 符号）。"""
    value = float(deg)
    if abs(value - round(value)) < 1.0e-9:
        return str(int(round(value)))
    return ('%.1f' % value).rstrip('0').rstrip('.')


def round_half_up(value):
    """四舍五入到整数（Python 的 round 为「银行家舍入」，不用于编号）。"""
    return int(math.floor(float(value) + 0.5))


def build_pipe_rack_number(length_code, height_code, material_code, azimuth_deg,
                           fixed):
    """管架编号：``F10-长度代码-高度代码-材料代码-方位角-Y/N``。"""
    return '%s-%s-%s-%s-%s-%s' % (
        PIPE_NAME_PREFIX,
        str(length_code).upper(),
        str(height_code).upper(),
        str(material_code).upper(),
        format_angle(label_azimuth_deg(azimuth_deg)),
        'Y' if fixed else 'N',
    )


# ---------------------------------------------------------------------------
# 尺寸推导
# ---------------------------------------------------------------------------

Layout = namedtuple(
    'Layout',
    'dn od_mm ear_width_mm ear_height_mm ear_thickness_mm '
    'base_radial_mm base_tangential_mm base_thickness_mm '
    'hole_diameter_mm hole_tangential_offset_mm bolt_spec bolt_diameter_mm '
    'bolt_length_mm fixed azimuth_deg azimuth_label '
    'length_code height_code material_code ear_material base_material '
    'pipe_material temp_range allowable_vertical_pipe_m number')


def build_layout(dn=DEFAULT_DN, length_code=DEFAULT_LENGTH_CODE,
                 height_code=DEFAULT_HEIGHT_CODE,
                 material_code=DEFAULT_MATERIAL_CODE,
                 azimuth_deg=DEFAULT_AZIMUTH_DEG, fixed=True):
    """按所选参数推导整组耳板的全部尺寸，返回 :class:`Layout`。"""
    dn = int(dn)
    od = od_mm(dn)
    ear_width = length_for_code(length_code)
    ear_height, allowable = height_for_code(height_code)
    material = material_for_code(material_code)
    azimuth = normalize_azimuth(azimuth_deg)

    values = (od, ear_width, ear_height, EAR_THICKNESS_MM,
              BASE_PLATE_RADIAL_MM, BASE_PLATE_TANGENTIAL_MM,
              BASE_PLATE_THICKNESS_MM, HOLE_DIAMETER_MM,
              HOLE_TANGENTIAL_OFFSET_MM)
    if not all(math.isfinite(value) and value > 0.0 for value in values):
        raise ValueError('尺寸参数必须是有限的正数。')
    if ear_width <= BASE_PLATE_RADIAL_MM:
        raise ValueError('耳板宽 L=%.1f mm 应大于底板径向 %.1f mm。'
                         % (ear_width, BASE_PLATE_RADIAL_MM))

    number = build_pipe_rack_number(
        length_code, height_code, material_code, azimuth, bool(fixed))

    return Layout(
        dn=dn,
        od_mm=od,
        ear_width_mm=ear_width,
        ear_height_mm=ear_height,
        ear_thickness_mm=EAR_THICKNESS_MM,
        base_radial_mm=BASE_PLATE_RADIAL_MM,
        base_tangential_mm=BASE_PLATE_TANGENTIAL_MM,
        base_thickness_mm=BASE_PLATE_THICKNESS_MM,
        hole_diameter_mm=HOLE_DIAMETER_MM,
        hole_tangential_offset_mm=HOLE_TANGENTIAL_OFFSET_MM,
        bolt_spec=BOLT_SPEC,
        bolt_diameter_mm=BOLT_DIAMETER_MM,
        bolt_length_mm=BOLT_LENGTH_MM,
        fixed=bool(fixed),
        azimuth_deg=azimuth,
        azimuth_label=format_angle(label_azimuth_deg(azimuth)),
        length_code=str(length_code).upper(),
        height_code=str(height_code).upper(),
        material_code=str(material_code).upper(),
        ear_material=material['ear_material'],
        base_material=material['base_material'],
        pipe_material=material['pipe_material'],
        temp_range=material['temp_range'],
        allowable_vertical_pipe_m=float(allowable),
        number=number,
    )


# ---------------------------------------------------------------------------
# 本地方位（radial / tangential / vertical）下的板件范围
# ---------------------------------------------------------------------------
#
# 约定：局部坐标 ``(r, t, z)``，r = 径向（从管轴向外为正），t = 切向，
# z = 竖直向上（管轴方向）；``z = 0`` 为底板顶面。一块耳板 + 一块底板构成
# 一侧「耳板组件」，另一侧绕管轴旋转 180°。


def ear_radial_span(layout):
    """耳板径向范围 ``(内缘, 外缘)``：内缘在管外壁。"""
    inner = layout.od_mm / 2.0
    return (inner, inner + layout.ear_width_mm)


def base_radial_span(layout):
    """底板径向范围 ``(内缘, 外缘)``：外缘与耳板外缘齐平。"""
    outer = ear_radial_span(layout)[1]
    return (outer - layout.base_radial_mm, outer)


def base_tangential_span(layout):
    """底板切向范围 ``(-半宽, +半宽)``。"""
    half = layout.base_tangential_mm / 2.0
    return (-half, half)


def ear_z_span(layout):
    """耳板竖直范围 ``(下缘, 上缘)``：下缘落在底板顶面（z=0），为干净矩形。"""
    return (0.0, layout.ear_height_mm)


def hole_centers(layout):
    """螺栓孔圆心 ``(r, t)`` 列表；不固定时返回空。"""
    if not layout.fixed:
        return ()
    inner, outer = base_radial_span(layout)
    r = (inner + outer) / 2.0
    offset = layout.hole_tangential_offset_mm
    return ((r, -offset), (r, offset))


def ear_plate_outline(layout):
    """耳板在 (r, z) 平面上的 4 个角点（逆时针）。"""
    r_inner, r_outer = ear_radial_span(layout)
    z_bottom, z_top = ear_z_span(layout)
    return ((r_inner, z_bottom), (r_outer, z_bottom),
            (r_outer, z_top), (r_inner, z_top))


def base_plate_outline(layout):
    """底板在 (r, t) 平面上的 4 个角点（逆时针）。"""
    r_inner, r_outer = base_radial_span(layout)
    t_min, t_max = base_tangential_span(layout)
    return ((r_inner, t_min), (r_outer, t_min),
            (r_outer, t_max), (r_inner, t_max))


# ---------------------------------------------------------------------------
# 构件清单（写入公共支吊架库）
# ---------------------------------------------------------------------------


def component_items(layout):
    """返回整组耳板的构件列表（供 ``支吊架公共库.attach_components``）。"""
    items = [
        {'code': 'EarPlate', 'name': '耳板',
         'specification': '耳板 %d×%d×%d %s' % (
             round_half_up(layout.ear_width_mm),
             round_half_up(layout.ear_height_mm),
             round_half_up(layout.ear_thickness_mm),
             layout.ear_material),
         'length': layout.ear_width_mm, 'quantity': 2},
        {'code': 'BasePlate', 'name': '底板',
         'specification': '底板 %d×%d×%d %s' % (
             round_half_up(layout.base_radial_mm),
             round_half_up(layout.base_tangential_mm),
             round_half_up(layout.base_thickness_mm),
             layout.base_material),
         'length': layout.base_tangential_mm, 'quantity': 2},
    ]
    if layout.fixed:
        items.append({
            'code': 'Bolt', 'name': '螺栓',
            'specification': '%s 单头螺栓' % layout.bolt_spec,
            'length': layout.bolt_length_mm, 'quantity': 4})
    return items


def specification(layout):
    """整组规格文本（写入整组记录 / 编号）。"""
    return 'DN%d %s 耳板 L%d H%d %s' % (
        layout.dn, nps_text(layout.dn),
        round_half_up(layout.ear_width_mm),
        round_half_up(layout.ear_height_mm),
        layout.ear_material)


def describe(layout):
    """一行摘要，供面板预览 / 状态显示。"""
    text = ('DN%d（%s，OD %.1f）；L=%.0f，H=%.0f，方位角 %s°；'
            '耳板 %.0f×%.0f×%.0f %s；底板 %.0f×%.0f×%.0f %s'
            % (layout.dn, nps_text(layout.dn), layout.od_mm,
               layout.ear_width_mm, layout.ear_height_mm, layout.azimuth_label,
               layout.ear_width_mm, layout.ear_height_mm,
               layout.ear_thickness_mm, layout.ear_material,
               layout.base_radial_mm, layout.base_tangential_mm,
               layout.base_thickness_mm, layout.base_material))
    text += '；固定' if layout.fixed else '；不固定（不开孔、不配螺栓）'
    return text
