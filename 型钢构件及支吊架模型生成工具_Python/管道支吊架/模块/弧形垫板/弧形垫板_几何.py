# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``Y2-[弧形垫板].py`` 插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""弧形垫板（Y2，1/2″~36″，即 DN15~900）纯几何 / 数据逻辑（可脱离 Bentley 单测）。

对应图集 Y2「弧形垫板」：

* 垫板是**贴附焊接在管道外壁上**的一块弧形钢板（护板），用于支承处扩散局部荷载；
* **截面**（垂直于管轴的平面内）＝ **两段同心圆弧 + 两条径向直线**：
    - 内弧半径 ``R = 管道外径 / 2``（贴管壁），
    - 外弧半径 ``R + T``（``T`` = 板厚，见表 1），
    - 两弧均张角 ``α``（见图；**居中于管底竖直向下方向**，即支承位置正上方）；
* 截面**沿管轴拉伸 L**（L 由用户输入，居中于支承位置 / 点取处）；
* 垫板最低点中央开 **气孔 Ø6**（焊接排气，贯穿板厚）。

数据来源：
* **表 1**：板厚 ``T`` —— DN15~200（1/2″~8″）→ 6；DN250~450（10″~18″）→ 8；
  DN500~900（20″~36″）→ 10；
* **表 2**：材料代码 —— ``L / C1 / C2 / A1 / A2 / S`` → 管道材料 + 温度范围 + 护板材料；
* **注 3**：``α`` 缺省 ``120°``；
* **注 4**：4″/5″（DN100/DN125）管道与 K1 限位架组合使用时 ``α = 180°``。

编号：``Y2-管径- L- 材料代码- α``（如 ``Y2-100-500-C1-120``）。

局部坐标约定（原点 = 点取处 / 支承位置，即垫板沿轴中点）：

    X = 管轴方向（水平）
    Y = 垂直管轴的水平方向
    Z = 竖直向上；垫板居中于 **−Z**（管底竖直向下）方向

本模块只做**数据与尺寸推导**（:func:`build_layout` / :func:`section_segments`）。
三维实体（截面沿管轴拉伸 + 中央气孔布尔减）由 ``Y2-[弧形垫板].py`` 生成。

截面轮廓由 :func:`section_segments` 以「直线 + **真圆弧**」给出（只给三个控制点，
由建模端还原精确圆弧），因此拉伸出的内 / 外柱面是**光滑圆柱面**；
:func:`section_points` 则是同一轮廓的折线近似，仅用于面积 / 长度等量算与回退建模。
"""

from __future__ import division

import math
from collections import namedtuple


# ---------------------------------------------------------------------------
# 管径（ASME B36.10M 外径，mm）与 NPS
# ---------------------------------------------------------------------------

DN_OD_TABLE = (
    (15, 21.3), (20, 26.7), (25, 33.4), (32, 42.2), (40, 48.3), (50, 60.3),
    (65, 73.0), (80, 88.9), (90, 101.6), (100, 114.3), (125, 141.3),
    (150, 168.3), (200, 219.1), (250, 273.0), (300, 323.8), (350, 355.6),
    (400, 406.4), (450, 457.0), (500, 508.0), (600, 609.6), (650, 660.4),
    (700, 711.2), (750, 762.0), (800, 812.8), (850, 863.6), (900, 914.4),
)

NPS_BY_DN = {
    15: '1/2"', 20: '3/4"', 25: '1"', 32: '1 1/4"', 40: '1 1/2"', 50: '2"',
    65: '2 1/2"', 80: '3"', 90: '3 1/2"', 100: '4"', 125: '5"', 150: '6"',
    200: '8"', 250: '10"', 300: '12"', 350: '14"', 400: '16"', 450: '18"',
    500: '20"', 600: '24"', 650: '26"', 700: '28"', 750: '30"', 800: '32"',
    850: '34"', 900: '36"',
}

DN_MIN = 15
DN_MAX = 900


# ---------------------------------------------------------------------------
# 表 1：管径 → 板厚 T（护板厚）
# ---------------------------------------------------------------------------

PLATE_THICKNESS_TABLE = (
    (200, 6.0),   # DN15~200 （1/2″~8″）
    (450, 8.0),   # DN250~450（10″~18″）
    (900, 10.0),  # DN500~900（20″~36″）
)


# ---------------------------------------------------------------------------
# 表 2：材料代码 → 管道材料 / 温度范围 / 护板材料
# ---------------------------------------------------------------------------

MATERIAL_CODES = {
    'L': {'pipe_material': '低温碳钢', 'temp_range': '-40 ~ -21',
          'pad_material': 'Q345R'},
    'C1': {'pipe_material': '碳钢', 'temp_range': '-20 ~ 300',
           'pad_material': 'Q235B'},
    'C2': {'pipe_material': '碳钢', 'temp_range': '301 ~ 425',
           'pad_material': 'Q345R'},
    'A1': {'pipe_material': '铬钼钢', 'temp_range': '≤500',
           'pad_material': '15CrMoR'},
    'A2': {'pipe_material': '铬钼钢', 'temp_range': '501 ~ 550',
           'pad_material': '12Cr1MoVR'},
    'S': {'pipe_material': '不锈钢', 'temp_range': '≤700',
          'pad_material': '06Cr19Ni10'},
}

DEFAULT_MATERIAL_CODE = 'C1'


# ---------------------------------------------------------------------------
# 角度 α 与其它常量
# ---------------------------------------------------------------------------

# 注 3：缺省 α = 120°。
DEFAULT_ALPHA_DEG = 120.0
# 常用角度（面板候选）：120（注 3 缺省）/ 180（注 4 K1 组合）。
ALPHA_CHOICES = (120.0, 180.0)
# 注 4：4″ / 5″（DN100 / DN125）与 K1 限位架组合使用时 α = 180°。
K1_ALPHA_DEG = 180.0
K1_ALPHA_DNS = (100, 125)

MIN_ALPHA_DEG = 1.0
MAX_ALPHA_DEG = 359.0

MIN_LENGTH_MM = 1.0

# 气孔 Ø6（垫板最低点中央、径向贯穿）。
VENT_HOLE_DIA_MM = 6.0
# 注 2：k = 焊缝腰高 = 管道壁厚，最大到 6mm（仅作说明，不建模）。
WELD_LEG_MAX_MM = 6.0

# 钢密度（kg/mm³）：7.85 g/cm³。
STEEL_DENSITY_KG_MM3 = 7.85e-6

# 圆弧离散化步长（°）：仅用于 ``section_points`` 的折线近似（量算 / 回退建模）。
# 正式建模走 ``section_segments`` 的真圆弧路径，不依赖此值。
ARC_SEGMENT_DEG = 5.0


# ---------------------------------------------------------------------------
# 查询 / 匹配
# ---------------------------------------------------------------------------


def dn_choices():
    return tuple(dn for dn, _od in DN_OD_TABLE)


def od_mm(dn):
    """按 ASME B36.10M 返回公称直径对应的管外径（mm）。"""
    dn = int(dn)
    for key, value in DN_OD_TABLE:
        if key == dn:
            return float(value)
    raise ValueError('未知公称直径：DN%d（应在 DN%d~%d）。' % (dn, DN_MIN, DN_MAX))


def nps_text(dn):
    return NPS_BY_DN.get(int(dn), '')


def dn_label(dn):
    dn = int(dn)
    nps = nps_text(dn)
    return 'DN%d（%s）' % (dn, nps) if nps else 'DN%d' % dn


def match_dn(nominal_mm, tolerance=5.0, ratio=0.05):
    """把管道信息里的直径（公称值或外径）匹配到最近 DN；超出容差返回 ``None``。"""
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    if value <= 0.0:
        return None
    by_dn = min(DN_OD_TABLE, key=lambda row: abs(row[0] - value))
    error_dn = abs(by_dn[0] - value)
    by_od = min(DN_OD_TABLE, key=lambda row: abs(row[1] - value))
    error_od = abs(by_od[1] - value)
    best, error = (by_dn, error_dn) if error_dn <= error_od else (by_od, error_od)
    if error <= max(tolerance, ratio * best[1]):
        return best[0]
    return None


def plate_thickness_mm(dn):
    """按表 1 由管径取板厚 T（mm）。"""
    dn = int(dn)
    if dn < DN_MIN or dn > DN_MAX:
        raise ValueError('管径 DN%d 超出本次范围 DN%d~%d。'
                         % (dn, DN_MIN, DN_MAX))
    for limit, thickness in PLATE_THICKNESS_TABLE:
        if dn <= limit:
            return float(thickness)
    return float(PLATE_THICKNESS_TABLE[-1][1])


def plate_thickness_label(dn):
    return 'T = %.0f mm' % plate_thickness_mm(dn)


def material_choices():
    return tuple((code, material_label(code)) for code in sorted(MATERIAL_CODES))


def material_label(code):
    row = material_for_code(code)
    return '%s  |  %s %s  |  护板 %s' % (
        code, row['pipe_material'], row['temp_range'], row['pad_material'])


def material_for_code(code):
    try:
        return dict(MATERIAL_CODES[str(code).strip().upper()])
    except KeyError:
        raise ValueError('未知材料代码：%s（应为 L/C1/C2/A1/A2/S）。' % code)


def alpha_choices():
    return tuple(ALPHA_CHOICES)


def alpha_label(alpha_deg):
    return '%.0f°' % float(alpha_deg)


def k1_alpha_note(dn):
    """注 4：4″/5″ 与 K1 组合使用时宜取 α = 180°；否则返回空串。"""
    if int(dn) in K1_ALPHA_DNS:
        return '注 4：DN%d（%s）与 K1 限位架组合使用时 α 宜取 180°。' % (
            int(dn), nps_text(dn))
    return ''


# ---------------------------------------------------------------------------
# 编号
# ---------------------------------------------------------------------------


def _fmt_number(value):
    """整数去掉小数点，否则保留原值（如 500.0→'500'、120.5→'120.5'）。"""
    number = float(value)
    if abs(number - round(number)) < 1.0e-9:
        return str(int(round(number)))
    return ('%.3f' % number).rstrip('0').rstrip('.')


def build_number(dn, length_mm, material_code, alpha_deg):
    """垫板编号：``Y2-管径-L-材料代码-α``（如 ``Y2-100-500-C1-120``）。"""
    return 'Y2-%d-%s-%s-%s' % (
        int(dn), _fmt_number(length_mm),
        str(material_code).strip().upper(), _fmt_number(alpha_deg))


# ---------------------------------------------------------------------------
# 尺寸推导
# ---------------------------------------------------------------------------

Layout = namedtuple('Layout', (
    'dn', 'nps', 'od_mm', 'pipe_radius',
    'thickness', 'inner_radius', 'outer_radius',
    'length_mm', 'half_length_mm',
    'alpha_deg', 'alpha_rad',
    'material_code', 'pipe_material', 'temp_range', 'pad_material',
    'vent_hole_dia', 'has_vent_hole',
    'number',
))


def build_layout(dn, length_mm, material_code=DEFAULT_MATERIAL_CODE,
                 alpha_deg=None, has_vent_hole=True):
    """按 DN + 用户输入推导整套尺寸（mm），供建模 / 清单使用。

    坐标系：原点取**支承位置**（= 垫板沿轴中点），X 沿管轴，Z 竖直向上，
    垫板居中于 **−Z**（管底）方向。内弧半径 = 管外径/2，外弧 = 内弧 + T。
    """
    dn = int(dn)
    if dn < DN_MIN or dn > DN_MAX:
        raise ValueError('管径 DN%d 超出本次范围 DN%d~%d。'
                         % (dn, DN_MIN, DN_MAX))

    row = material_for_code(material_code)
    code = str(material_code).strip().upper()

    length = float(length_mm)
    if not math.isfinite(length) or length < MIN_LENGTH_MM:
        raise ValueError('垫板长度 L=%.3f mm 过小，要求 ≥ %.0f mm。'
                         % (length, MIN_LENGTH_MM))

    if alpha_deg is None:
        alpha_deg = DEFAULT_ALPHA_DEG
    alpha = float(alpha_deg)
    if not math.isfinite(alpha) or not (MIN_ALPHA_DEG <= alpha <= MAX_ALPHA_DEG):
        raise ValueError('张角 α=%.3f° 不合理，要求 %.0f°~%.0f°。'
                         % (alpha, MIN_ALPHA_DEG, MAX_ALPHA_DEG))

    od = od_mm(dn)
    thickness = plate_thickness_mm(dn)
    inner_radius = od / 2.0
    outer_radius = inner_radius + thickness

    return Layout(
        dn=dn, nps=nps_text(dn), od_mm=od, pipe_radius=inner_radius,
        thickness=thickness, inner_radius=inner_radius,
        outer_radius=outer_radius,
        length_mm=length, half_length_mm=length / 2.0,
        alpha_deg=alpha, alpha_rad=math.radians(alpha),
        material_code=code,
        pipe_material=row['pipe_material'], temp_range=row['temp_range'],
        pad_material=row['pad_material'],
        vent_hole_dia=float(VENT_HOLE_DIA_MM),
        has_vent_hole=bool(has_vent_hole),
        number=build_number(dn, length, code, alpha),
    )


# ---------------------------------------------------------------------------
# 截面点（垂直于管轴的平面内；局部 (y, z)，mm）
# ---------------------------------------------------------------------------


def arc_step_count(alpha_deg, segment_deg=ARC_SEGMENT_DEG):
    """把张角 ``alpha_deg`` 按 ``segment_deg`` 离散成多少段（≥2）。"""
    return max(2, int(math.ceil(abs(float(alpha_deg)) / float(segment_deg))))


def section_points(layout, segment_deg=ARC_SEGMENT_DEG):
    """返回垫板截面（垂直于管轴）的**闭合多边形**点列 ``(y, z)``（mm）。

    这是 :func:`section_segments` 同一轮廓的**折线近似**：圆弧按 ``segment_deg``
    离散成短直线段，用于面积 / 长度等量算，以及真圆弧建模失败时的回退。
    正式建模请用 :func:`section_segments`，否则拉伸面会出现棱面。

    顺序：内弧（−α/2 → +α/2）→ 外弧（+α/2 → −α/2）；两弧端点由径向直线连接，
    因此点列首尾相接即为「两弧 + 两直线」的封闭截面。角度自 **−Z（管底）**
    起算，绕管轴偏向 ±Y；φ = 0 即管底最低点。
    """
    alpha = float(layout.alpha_deg)
    half = math.radians(alpha / 2.0)
    steps = arc_step_count(alpha, segment_deg)
    inner_radius = float(layout.inner_radius)
    outer_radius = float(layout.outer_radius)

    inner = []
    outer = []
    for index in range(steps + 1):
        phi = -half + (2.0 * half) * index / steps
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        inner.append((inner_radius * sin_phi, -inner_radius * cos_phi))
        outer.append((outer_radius * sin_phi, -outer_radius * cos_phi))
    outer.reverse()
    return tuple(inner + outer)


def _polar(radius, phi):
    """以管底（−Z）为 φ=0、绕管轴偏向 ±Y 的极坐标点 ``(y, z)``（mm）。"""
    return (radius * math.sin(phi), -radius * math.cos(phi))


def section_segments(layout):
    """返回截面轮廓的**有序段列表**，供按「直线 + 真圆弧」建模（不平滑化）。

    每段为 ``(kind, points)``：

    * ``('arc', (起点, 中点, 终点))`` —— 真圆弧，三点定弧（``FromPointsOnArc``）；
    * ``('line', (起点, 终点))`` —— 径向直线。

    顺序：内弧（−α/2 → +α/2）→ 径向外连线 → 外弧（+α/2 → −α/2）→ 径向内连线，
    首尾相接构成闭合截面。圆弧只给三个控制点，由建模端还原精确圆弧，因此沿管轴
    拉伸出的内 / 外表面是**光滑圆柱面**，不会出现折线近似的棱面（「格格」）。
    """
    alpha = float(layout.alpha_deg)
    half = math.radians(alpha / 2.0)
    inner_radius = float(layout.inner_radius)
    outer_radius = float(layout.outer_radius)

    inner_start = _polar(inner_radius, -half)
    inner_mid = _polar(inner_radius, 0.0)
    inner_end = _polar(inner_radius, half)
    outer_start = _polar(outer_radius, -half)
    outer_mid = _polar(outer_radius, 0.0)
    outer_end = _polar(outer_radius, half)

    return (
        ('arc', (inner_start, inner_mid, inner_end)),
        ('line', (inner_end, outer_end)),
        ('arc', (outer_end, outer_mid, outer_start)),
        ('line', (outer_start, inner_start)),
    )


def section_area_mm2(layout):
    """截面面积（mm²）：环形扇形 − 气孔。"""
    alpha_rad = float(layout.alpha_rad)
    inner_radius = float(layout.inner_radius)
    outer_radius = float(layout.outer_radius)
    area = 0.5 * alpha_rad * (outer_radius ** 2 - inner_radius ** 2)
    if layout.has_vent_hole:
        area -= math.pi * (float(layout.vent_hole_dia) / 2.0) ** 2
    return max(0.0, area)


def plate_volume_mm3(layout):
    return section_area_mm2(layout) * float(layout.length_mm)


def plate_mass_kg(layout):
    """护板理论质量（kg）：截面积 × 长 L × 钢密度。"""
    return plate_volume_mm3(layout) * STEEL_DENSITY_KG_MM3


def layout_summary(layout):
    """一行文字摘要（面板显示用）。"""
    return ('%s：%s OD%.1f / 内弧 R%.1f / 外弧 R%.1f（T%.0f）/ L%.0f / α%.0f° / '
            '%s %s' % (
                layout.number, dn_label(layout.dn), layout.od_mm,
                layout.inner_radius, layout.outer_radius, layout.thickness,
                layout.length_mm, layout.alpha_deg,
                layout.material_code, layout.pad_material))