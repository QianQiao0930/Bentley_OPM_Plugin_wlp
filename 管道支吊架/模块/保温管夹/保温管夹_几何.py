# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``保温管夹.py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""保温管夹（高温隔热限位管托，图集 T4）纯几何 / 数据逻辑（可单测）。

对应图集：适用范围 **管径 3″~24″，即 DN80~600**。结构（详图 A / C、截面 A-A）：

* **承重板（上 / 下两组）** = 包在保温层外的筒形板（板厚 ``T3``），对开 45°、
  两端用**耳板 + 螺栓**（带碟簧垫圈）连接，两块承重板之间留**间隙 J**；
* **管夹底座** = 底板 + 两道（L＞600 时三道）横向弧顶支撑 + 中央纵向腹板；
* 以所选**管道中线为坐标原点**，X 沿管轴，Z 竖直向上。

数据来源：
* **表 1**：螺栓直径、耳板大小、螺栓中心线尺寸 ``C``、耳板焊缝腰高 ``k``、
  承重板间隙 ``J``；以及鞍座和承重板尺寸 ``T1 / T2 / T3``、允许荷载；
* **表 2**：隔热层外径 ``D`` → 底板宽度 ``W``；
* **用户输入**：隔热层厚度 ``B``、``L``（``H`` 由 ``B`` 查表）。

本模块只做**数据与尺寸**推导（:func:`build_layout` / :func:`build_boolean_layout`）。
三维实体（外圆柱 − 内圆柱 − 45° 贯穿体 = 两片管夹；耳板开孔后与管夹布尔并；
底座弧顶支撑减圆柱成形）由 ``保温管夹.py`` 做布尔运算得到。图中未给死的尺寸用
顶部默认常量。
"""

from __future__ import division

import math
from collections import namedtuple


DN_MIN = 80
DN_MAX = 600
MIN_SHOE_LENGTH_MM = 300.0
MIN_INSULATION_MM = 1.0
MIN_HEIGHT_MM = 1.0

# 长 L 超过该值时，管夹底座加盖中间横向支撑（截面 A-A 的 L＞600 分支）。
MIDDLE_RIB_LENGTH_MM = 600.0
# 管夹对开方位角（°）：0 = 正上方（+Z），45 = 图上 45° 螺栓线。
DEFAULT_SPLIT_ANGLE_DEG = 45.0
# 旧参数：管夹环轴向宽度默认值（本版管夹环沿轴长改用 L，仅保留兼容）。
DEFAULT_CLAMP_WIDTH_MM = 75.0
# 螺栓在两侧承重板之外的长度（mm，含螺母/碟簧余量）。
BOLT_EXTRA_MM = 25.0

# --- 布尔建模默认常量（对齐「剪切测试」版） --------------------------------
EAR_END_OFFSET_MM = 75.0      # 首 / 尾耳板中心到管夹轴向端部的距离。
SUPPORT_END_OFFSET_MM = 75.0  # 横向支撑中心到管夹轴向端部的距离。
SUPPORT_SIDE_INSET_MM = 10.0  # 横向支撑两侧距底板边缘。
SUPPORT_OVERLAP_MM = 1.0      # 支撑与承重板 / 底板的布尔搭接量。
EAR_SETBACK_MM = 10.0         # 耳板内侧面距承重板切口端面的退让距离。
EAR_ROOT_OVERLAP_MM = 1.0     # 耳板根部与承重板的搭接量。
HOLE_CLEARANCE_MM = 2.0       # 螺栓通孔相对螺杆直径的单边余量（M20→22）。


# ---------------------------------------------------------------------------
# 表 1：管径 → 螺栓 / 耳板 / 尺寸
# ---------------------------------------------------------------------------

# 字段：nps / od_mm / bolt_dia / ear(w,h,t) / C / k / J / T1 / T2 / T3 / loads
DN_TABLE = {
    80:  {'nps': '3"',  'od_mm': 88.9,  'bolt_dia': 'M12',
          'ear': (40.0, 40.0, 16.0), 'C': 25.0, 'k': 6.0, 'J': 25.0,
          'T1': 10.0, 'T2': 8.0,  'T3': 6.0,  'loads': (40.0, 8.0, 30.0)},
    100: {'nps': '4"',  'od_mm': 114.3, 'bolt_dia': 'M12',
          'ear': (40.0, 40.0, 16.0), 'C': 25.0, 'k': 6.0, 'J': 25.0,
          'T1': 10.0, 'T2': 8.0,  'T3': 6.0,  'loads': (40.0, 8.0, 30.0)},
    125: {'nps': '5"',  'od_mm': 141.3, 'bolt_dia': 'M16',
          'ear': (50.0, 50.0, 20.0), 'C': 30.0, 'k': 6.0, 'J': 25.0,
          'T1': 10.0, 'T2': 8.0,  'T3': 10.0, 'loads': (70.0, 15.0, 60.0)},
    150: {'nps': '6"',  'od_mm': 168.3, 'bolt_dia': 'M16',
          'ear': (50.0, 50.0, 20.0), 'C': 30.0, 'k': 6.0, 'J': 25.0,
          'T1': 10.0, 'T2': 8.0,  'T3': 10.0, 'loads': (70.0, 15.0, 60.0)},
    200: {'nps': '8"',  'od_mm': 219.1, 'bolt_dia': 'M20',
          'ear': (60.0, 60.0, 20.0), 'C': 35.0, 'k': 8.0, 'J': 30.0,
          'T1': 12.0, 'T2': 12.0, 'T3': 12.0, 'loads': (150.0, 30.0, 80.0)},
    250: {'nps': '10"', 'od_mm': 273.0, 'bolt_dia': 'M20',
          'ear': (60.0, 60.0, 20.0), 'C': 35.0, 'k': 8.0, 'J': 30.0,
          'T1': 12.0, 'T2': 12.0, 'T3': 12.0, 'loads': (150.0, 30.0, 80.0)},
    300: {'nps': '12"', 'od_mm': 323.9, 'bolt_dia': 'M20',
          'ear': (60.0, 60.0, 20.0), 'C': 35.0, 'k': 8.0, 'J': 30.0,
          'T1': 12.0, 'T2': 12.0, 'T3': 12.0, 'loads': (150.0, 30.0, 80.0)},
    350: {'nps': '14"', 'od_mm': 355.6, 'bolt_dia': 'M20',
          'ear': (60.0, 60.0, 20.0), 'C': 35.0, 'k': 8.0, 'J': 30.0,
          'T1': 12.0, 'T2': 12.0, 'T3': 12.0, 'loads': (200.0, 40.0, 100.0)},
    400: {'nps': '16"', 'od_mm': 406.4, 'bolt_dia': 'M20',
          'ear': (60.0, 60.0, 20.0), 'C': 35.0, 'k': 8.0, 'J': 30.0,
          'T1': 12.0, 'T2': 12.0, 'T3': 12.0, 'loads': (200.0, 40.0, 100.0)},
    450: {'nps': '18"', 'od_mm': 457.2, 'bolt_dia': 'M24',
          'ear': (70.0, 70.0, 25.0), 'C': 40.0, 'k': 10.0, 'J': 40.0,
          'T1': 14.0, 'T2': 12.0, 'T3': 14.0, 'loads': (300.0, 50.0, 120.0)},
    500: {'nps': '20"', 'od_mm': 508.0, 'bolt_dia': 'M24',
          'ear': (70.0, 70.0, 25.0), 'C': 40.0, 'k': 10.0, 'J': 40.0,
          'T1': 14.0, 'T2': 12.0, 'T3': 14.0, 'loads': (300.0, 50.0, 120.0)},
    550: {'nps': '22"', 'od_mm': 558.8, 'bolt_dia': 'M24',
          'ear': (70.0, 70.0, 25.0), 'C': 40.0, 'k': 10.0, 'J': 40.0,
          'T1': 14.0, 'T2': 12.0, 'T3': 14.0, 'loads': (300.0, 50.0, 120.0)},
    600: {'nps': '24"', 'od_mm': 609.6, 'bolt_dia': 'M24',
          'ear': (70.0, 70.0, 25.0), 'C': 40.0, 'k': 10.0, 'J': 40.0,
          'T1': 14.0, 'T2': 12.0, 'T3': 14.0, 'loads': (300.0, 50.0, 120.0)},
}

BOLT_DIAMETERS_MM = {'M12': 12.0, 'M16': 16.0, 'M20': 20.0,
                     'M24': 24.0, 'M30': 30.0}


def dn_choices():
    return tuple((dn, dn_label(dn)) for dn in sorted(DN_TABLE))


def dn_label(dn):
    row = get_row(dn)
    return 'DN%d  |  %s  |  OD %.1f' % (dn, row['nps'], row['od_mm'])


def get_row(dn):
    try:
        row = DN_TABLE[int(dn)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('管径 DN%s 超出本次范围 DN%d~%d。'
                         % (dn, DN_MIN, DN_MAX))
    row = dict(row)
    # DN80~600 均为 4 颗螺栓（表 1）。
    row.setdefault('bolt_count', 4)
    return row


def od_mm(dn):
    return float(get_row(dn)['od_mm'])


def bolt_dia_mm(dn):
    return BOLT_DIAMETERS_MM[get_row(dn)['bolt_dia']]


def allowable_loads(dn):
    return tuple(get_row(dn)['loads'])


# ---------------------------------------------------------------------------
# 表 2：隔热层外径 D → 底板宽度 W
# ---------------------------------------------------------------------------

# (D 上限 mm, 底板宽度 W mm)；D 为隔热层外径 = OD + 2B。
BASE_WIDTH_TABLE = (
    (200.0, 100.0),
    (300.0, 150.0),
    (400.0, 200.0),
    (500.0, 250.0),
    (600.0, 300.0),
    (800.0, 400.0),
    (1000.0, 500.0),
    (1200.0, 600.0),
    (1400.0, 700.0),
    (1600.0, 800.0),
)


def base_width_for_insulation_od(insulation_od_mm):
    """按表 2 由保温层外径 D 取底板宽度 W（mm）；超出表上限时报错。"""
    d = float(insulation_od_mm)
    for limit, width in BASE_WIDTH_TABLE:
        if d <= limit:
            return width
    raise ValueError('保温层外径 D=%.1f mm 超出表 2 上限 %.0f mm。'
                     % (d, BASE_WIDTH_TABLE[-1][0]))


# ---------------------------------------------------------------------------
# 表：保温厚度 B → H（管道不含保温底部 → 管托底面）
# ---------------------------------------------------------------------------

INSULATION_HEIGHT_TABLE = (
    (75.0, 150.0),
    (125.0, 200.0),
    (175.0, 250.0),
    (225.0, 300.0),
    (275.0, 350.0),
)


def height_for_insulation(insulation_mm):
    """按保温厚度 ``B`` 查表得到 ``H``（mm）；超出表上限时报错。"""
    b = float(insulation_mm)
    for limit, height in INSULATION_HEIGHT_TABLE:
        if b <= limit:
            return height
    raise ValueError('保温厚度 B=%.1f mm 超出表上限 %.0f mm。'
                     % (b, INSULATION_HEIGHT_TABLE[-1][0]))


# ---------------------------------------------------------------------------
# 尺寸与截面点推导
# ---------------------------------------------------------------------------

Layout = namedtuple('Layout', (
    'dn', 'nps', 'od_mm', 'pipe_radius',
    'insulation_mm', 'insulation_radius', 'insulation_od',
    't1', 't2', 't3',
    'clamp_outer_radius', 'clamp_width_mm',
    'height_mm', 'height1_mm', 'shoe_length_mm', 'shoe_bottom_z',
    'base_width', 'base_plate_thickness', 'base_top_z',
    'bolt_count', 'bolt_dia', 'bolt_dia_mm', 'bolt_length_mm',
    'ear_width', 'ear_height', 'ear_thickness',
    'bolt_center_c', 'weld_leg_k', 'plate_gap_j',
    'split_angle_deg', 'has_middle_rib',
    'top_plate_top_z',
))


def build_layout(dn, insulation_mm, height_mm, shoe_length_mm,
                 clamp_width_mm=DEFAULT_CLAMP_WIDTH_MM,
                 split_angle_deg=DEFAULT_SPLIT_ANGLE_DEG):
    """按 DN + 用户输入推导整套尺寸（mm），供布尔建模使用。

    坐标系：原点取 **管道轴线**（管托 L 中心），X 沿管轴，Z 竖直向上。
    ``shoe_bottom_z = -(管半径 + H)``（H = 管道底部 → 管托底面）。
    承重板（上/下）包在保温层外，板厚 ``T3``；底板宽度 W 查表 2。
    """
    row = get_row(dn)
    dn = int(dn)
    insulation_mm = float(insulation_mm)
    height_mm = float(height_mm)
    shoe_length_mm = float(shoe_length_mm)
    clamp_width_mm = float(clamp_width_mm)

    if insulation_mm < MIN_INSULATION_MM:
        raise ValueError('隔热层厚度 B=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (insulation_mm, MIN_INSULATION_MM))
    if height_mm < MIN_HEIGHT_MM:
        raise ValueError('管托高 H=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (height_mm, MIN_HEIGHT_MM))
    if shoe_length_mm < MIN_SHOE_LENGTH_MM:
        raise ValueError('管托长 L=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (shoe_length_mm, MIN_SHOE_LENGTH_MM))
    if clamp_width_mm <= 0.0:
        raise ValueError('管夹宽度必须为正。')

    t1 = float(row['T1'])
    t2 = float(row['T2'])
    t3 = float(row['T3'])
    ear_w, ear_h, ear_t = (float(v) for v in row['ear'])

    pipe_radius = float(row['od_mm']) / 2.0
    insulation_radius = pipe_radius + insulation_mm
    insulation_od = 2.0 * insulation_radius
    clamp_outer_radius = insulation_radius + t3
    base_width = base_width_for_insulation_od(insulation_od)
    shoe_bottom_z = -(pipe_radius + height_mm)
    base_top_z = shoe_bottom_z + t1
    # 管夹底座顶板顶面 = 承重板（管夹）最低点。
    top_plate_top_z = -clamp_outer_radius
    # H1：管道底部 → 底板顶面（= H − 底板厚）。
    height1_mm = height_mm - t1
    bolt_dia = row['bolt_dia']
    bolt_length = 2.0 * ear_t + BOLT_EXTRA_MM

    return Layout(
        dn=dn, nps=row['nps'], od_mm=float(row['od_mm']),
        pipe_radius=pipe_radius,
        insulation_mm=insulation_mm, insulation_radius=insulation_radius,
        insulation_od=insulation_od,
        t1=t1, t2=t2, t3=t3,
        clamp_outer_radius=clamp_outer_radius, clamp_width_mm=clamp_width_mm,
        height_mm=height_mm, height1_mm=height1_mm,
        shoe_length_mm=shoe_length_mm, shoe_bottom_z=shoe_bottom_z,
        base_width=base_width, base_plate_thickness=t1, base_top_z=base_top_z,
        bolt_count=int(row['bolt_count']),
        bolt_dia=bolt_dia, bolt_dia_mm=bolt_dia_mm(dn),
        bolt_length_mm=bolt_length,
        ear_width=ear_w, ear_height=ear_h, ear_thickness=ear_t,
        bolt_center_c=float(row['C']), weld_leg_k=float(row['k']),
        plate_gap_j=float(row['J']),
        split_angle_deg=float(split_angle_deg),
        has_middle_rib=shoe_length_mm > MIDDLE_RIB_LENGTH_MM,
        top_plate_top_z=top_plate_top_z,
    )


BooleanLayout = namedtuple('BooleanLayout', (
    'inner_radius', 'outer_radius', 'clamp_length_mm', 'cut_angle_deg', 'gap_j',
    'ear_center_x', 'support_center_x',
    'base_bottom_z', 'base_top_z', 'support_half_span', 'support_top_z',
    'trim_radius',
    'ear_bounds', 'ear_hole_a', 'hole_dia',
    'ear_width', 'ear_height', 'ear_thickness', 'ear_setback',
))


def _ear_hole_a(a0, a1, b0, b1, outer_radius, bolt_center_c, hole_dia, ear_w):
    """返回孔心的有符号 a 坐标；同一分口两孔取相同 a，保证同轴。"""
    b_mid = (b0 + b1) / 2.0
    contact_a = math.sqrt(outer_radius ** 2 - b_mid ** 2)
    side = 1.0 if a0 + a1 > 0 else -1.0
    hole_a = side * (contact_a + bolt_center_c)
    radius = hole_dia / 2.0
    if ear_w / 2.0 <= radius or not (a0 < hole_a - radius and
                                     hole_a + radius < a1):
        raise ValueError('孔超出耳板边界，请调整 C、孔径或耳板尺寸。')
    nearest_b = min(abs(b0), abs(b1))
    surface_a = math.sqrt(outer_radius ** 2 - nearest_b ** 2)
    if abs(hole_a) - radius <= surface_a:
        raise ValueError('孔与管夹本体相交，请增大 C 或减小孔径。')
    return hole_a


def build_boolean_layout(layout, ear_end_offset=EAR_END_OFFSET_MM,
                         ear_group_count=0,
                         support_end_offset=SUPPORT_END_OFFSET_MM,
                         support_side_inset=SUPPORT_SIDE_INSET_MM,
                         support_overlap=SUPPORT_OVERLAP_MM,
                         ear_setback=EAR_SETBACK_MM,
                         ear_root_overlap=EAR_ROOT_OVERLAP_MM,
                         hole_clearance=HOLE_CLEARANCE_MM):
    """由 :func:`build_layout` 推导布尔建模所需的全部尺寸（mm）。

    返回 :class:`BooleanLayout`。管夹环沿管轴长 ``L``；耳板沿轴均布 2 组
    （L≤600）或 3 组（L＞600），每组两处分口各 2 块耳板（共 4 块）；底座为
    底板 + 横向弧顶支撑 + 中央纵向腹板。坐标：X=管轴，Z=竖直向上，管中为原点。
    """
    length = float(layout.shoe_length_mm)
    outer_radius = float(layout.clamp_outer_radius)
    inner_radius = float(layout.insulation_radius)
    t1 = float(layout.t1)
    t2 = float(layout.t2)
    t3 = float(layout.t3)
    gap_j = float(layout.plate_gap_j)
    ear_w = float(layout.ear_width)
    ear_h = float(layout.ear_height)
    ear_t = float(layout.ear_thickness)

    if length < MIN_SHOE_LENGTH_MM:
        raise ValueError('管夹长度 L 必须至少 %.0f mm。' % MIN_SHOE_LENGTH_MM)
    if gap_j >= 2.0 * inner_radius:
        raise ValueError('承重板间隙 J 必须小于管夹内径。')
    if ear_group_count not in (0, 2, 3):
        raise ValueError('耳板组数只能取 0（自动）、2 或 3。')

    count = ear_group_count or (3 if length > MIDDLE_RIB_LENGTH_MM else 2)
    span = length - 2.0 * ear_end_offset
    if ear_end_offset < ear_w / 2.0 or span / (count - 1) <= ear_w:
        raise ValueError('耳板重叠或超出管夹端部，请增大 L 或调整端距及组数。')
    ear_center_x = tuple(-span / 2.0 + i * span / (count - 1)
                         for i in range(count))

    if not t2 / 2.0 < support_end_offset < length / 2.0 - t2:
        raise ValueError('横向支撑端距不合理。')
    support_center_x = [-length / 2.0 + support_end_offset,
                        length / 2.0 - support_end_offset]
    if length > MIDDLE_RIB_LENGTH_MM:
        support_center_x.insert(1, 0.0)

    base_bottom_z = float(layout.shoe_bottom_z)
    base_top_z = float(layout.base_top_z)
    if base_top_z >= -outer_radius:
        raise ValueError('H 不足，底板与管夹相交或没有支撑净高。')
    if support_overlap >= min(t3, t1):
        raise ValueError('搭接量必须小于承重板及底板厚度。')

    half_span = float(layout.base_width) / 2.0 - support_side_inset
    trim_radius = outer_radius - support_overlap
    if not t2 / 2.0 < half_span < trim_radius:
        raise ValueError('横向支撑宽度不适合当前管夹直径。')
    support_top_z = -math.sqrt(trim_radius ** 2 - half_span ** 2)

    b_near = gap_j / 2.0 + ear_setback
    b_far = b_near + ear_t
    if b_far >= outer_radius:
        raise ValueError('耳板位置超出管夹外圆，请调整间隙、退让或耳板厚度。')
    a_root = math.sqrt(outer_radius ** 2 - b_far ** 2) - ear_root_overlap
    if a_root <= 0 or math.hypot(a_root, b_near) <= inner_radius:
        raise ValueError('耳板根部会穿入保温层，请调整耳板位置或搭接量。')
    if ear_w > length:
        raise ValueError('耳板轴向宽度不得超过管夹长度。')
    if a_root + ear_h <= math.sqrt(outer_radius ** 2 - b_near ** 2):
        raise ValueError('耳板高度不足以伸出管夹外圆。')

    bounds = []
    for radial_side in (-1, 1):
        a0, a1 = sorted((radial_side * a_root,
                         radial_side * (a_root + ear_h)))
        for plate_side in (-1, 1):
            b0, b1 = sorted((plate_side * b_near, plate_side * b_far))
            bounds.append((a0, a1, b0, b1))

    hole_dia = float(layout.bolt_dia_mm) + hole_clearance
    hole_a = tuple(
        _ear_hole_a(a0, a1, b0, b1, outer_radius,
                    float(layout.bolt_center_c), hole_dia, ear_w)
        for (a0, a1, b0, b1) in bounds)

    angle = math.radians(float(layout.split_angle_deg))
    if math.cos(angle) <= 0.0:
        raise ValueError('切口角度不合理。')
    max_b = abs(math.sin(angle)) * half_span + math.cos(angle) * support_top_z
    if max_b >= gap_j / 2.0:
        raise ValueError('当前切口角度或支撑宽度会使支撑接触上半承重板。')

    return BooleanLayout(
        inner_radius=inner_radius, outer_radius=outer_radius,
        clamp_length_mm=length, cut_angle_deg=float(layout.split_angle_deg),
        gap_j=gap_j,
        ear_center_x=ear_center_x, support_center_x=tuple(support_center_x),
        base_bottom_z=base_bottom_z, base_top_z=base_top_z,
        support_half_span=half_span, support_top_z=support_top_z,
        trim_radius=trim_radius,
        ear_bounds=tuple(bounds), ear_hole_a=hole_a, hole_dia=hole_dia,
        ear_width=ear_w, ear_height=ear_h, ear_thickness=ear_t,
        ear_setback=ear_setback,
    )


# ---------------------------------------------------------------------------
# 管架编号（图 T4：名称-管径-温度代码-H-L-材料代码-F）
# ---------------------------------------------------------------------------

def round_half_up(value):
    return int(math.floor(float(value) + 0.5))


def build_clamp_number(name, dn, temperature_code, height_mm, length_mm,
                       material_code='', f_code=''):
    """管架编号 ``名称-管径-温度代码-H-L-材料代码-F``；名称为空则返回空串。"""
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%d-%s-%d-%d-%s-%s' % (
        label, int(dn), str(temperature_code).strip(),
        round_half_up(height_mm), round_half_up(length_mm),
        str(material_code).strip(), str(f_code).strip())
