# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``保温管夹.py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""保温管夹（高温隔热限位管托，图集 T4）纯几何 / 数据逻辑（可单测）。

对应图集：适用范围 **管径 3″~24″，即 DN80~600**。结构（详图 A / C、截面 A-A）：

* **承重板（上 / 下两组）** = 包在保温层外的两块弧形板（板厚 ``T3``），对开
  45°、两端用**耳板 + 螺栓**（带碟簧垫圈）连接，两块承重板之间留**间隙 J**；
* **管夹底座**（截面 A-A）= 由**顶部承重板 + 腹板 + 底部承重板**（长 L＞600 时
  再加中间肋板）组合成的截面，沿管轴拉伸；**底板宽度 W 由保温层外径 D 查表 2**；
* 以所选**管道中线为坐标原点**，先画截面关键控制点，再沿管轴拉伸。

数据来源：
* **表 1**：螺栓直径、耳板大小、螺栓中心线尺寸 ``C``、耳板焊缝腰高 ``k``、
  承重板间隙 ``J``；以及鞍座和承重板尺寸 ``T1 / T2 / T3``、允许荷载；
* **表 2**：隔热层外径 ``D`` → 底板宽度 ``W``；
* **用户输入**：隔热层厚度 ``B``、``H``、``L``。

本模块只做**数据与截面点**推导（:func:`build_layout` / :func:`clamp_half_points` /
:func:`shoe_section_points`），三维实体由 ``保温管夹.py`` 拉伸得到。图中未给死的
尺寸用顶部默认常量。
"""

from __future__ import division

import math
from collections import namedtuple


DN_MIN = 80
DN_MAX = 600
MIN_SHOE_LENGTH_MM = 300.0
MIN_INSULATION_MM = 1.0
MIN_HEIGHT_MM = 1.0

# 长 L 超过该值时，管夹底座加盖中间肋板（截面 A-A 的 L＞600 分支）。
MIDDLE_RIB_LENGTH_MM = 600.0
# 管夹对开方位角（°）：0 = 正上方（+Z），45 = 图上 45° 螺栓线。
DEFAULT_SPLIT_ANGLE_DEG = 45.0
# 承重板螺栓在管夹宽度方向的排布（2 颗）。
BOLTS_PER_JOINT = 2
# 截面圆弧的离散段数（纯数据，供建模用）。
SECTION_ARC_STEPS = 24
# 螺栓在两侧承重板之外的长度（mm，含螺母/碟簧余量）。
BOLT_EXTRA_MM = 25.0


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
                 clamp_width_mm=75.0,
                 split_angle_deg=DEFAULT_SPLIT_ANGLE_DEG):
    """按 DN + 用户输入推导整套尺寸（mm），供截面绘制 / 拉伸使用。

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


def _angle_point(radius, angle):
    """角度 θ 从 +Z 起算、向 +Y 为正：返回 (y, z)。"""
    return (math.sin(angle) * radius, math.cos(angle) * radius)


def clamp_half_points(layout, upper, steps=SECTION_ARC_STEPS):
    """半片**承重板（管夹）**截面关键控制点 ``(y, z)``（mm，管中为原点）。

    承重板内径 = 保温层外径 D/2、外径 = D/2 + T3；两半在 ``split_angle`` 处对开、
    端部留**间隙 J**（沿中性层弧长）。上半覆盖对开面之间经管顶的一段，下半经管底。
    """
    r_in = layout.insulation_radius
    r_out = r_in + layout.t3
    r_mid = (r_in + r_out) / 2.0
    half_gap = (layout.plate_gap_j / 2.0) / r_mid
    split = math.radians(layout.split_angle_deg)
    if upper:
        start = split + half_gap
        end = split + math.pi - half_gap
    else:
        start = split + math.pi + half_gap
        end = split + 2.0 * math.pi - half_gap
    points = []
    for index in range(steps + 1):
        angle = start + (end - start) * index / steps
        points.append(_angle_point(r_out, angle))
    for index in range(steps, -1, -1):
        angle = start + (end - start) * index / steps
        points.append(_angle_point(r_in, angle))
    return points


def shoe_section_points(layout):
    """**管夹底座**截面（截面 A-A）关键控制点 ``(y, z)``（mm，管中为原点）。

    工字形：顶部承重板 + 腹板（T2）+ 底部承重板；L＞600 时中间加肋板（同 T2）。
    顶部板顶面 = 承重板最低点；底板底面 = 管托底面。
    """
    w = layout.base_width
    t2 = layout.t2
    t_bot = layout.base_plate_thickness
    z_top = layout.top_plate_top_z
    z_bot = layout.shoe_bottom_z
    z_base_top = layout.base_top_z
    half_w = w / 2.0
    half_web = t2 / 2.0

    points = [
        (-half_w, z_top),
        (half_w, z_top),
        (half_w, z_top - t2),
        (half_web, z_top - t2),
    ]
    if layout.has_middle_rib:
        z_mid = (z_base_top + (z_top - t2)) / 2.0
        points += [(half_web, z_mid + t2 / 2.0),
                   (half_w, z_mid + t2 / 2.0),
                   (half_w, z_mid - t2 / 2.0),
                   (half_web, z_mid - t2 / 2.0)]
    points += [
        (half_web, z_base_top),
        (half_w, z_base_top),
        (half_w, z_bot),
        (-half_w, z_bot),
        (-half_w, z_base_top),
        (-half_web, z_base_top),
    ]
    if layout.has_middle_rib:
        points += [(-half_web, z_mid - t2 / 2.0),
                   (-half_w, z_mid - t2 / 2.0),
                   (-half_w, z_mid + t2 / 2.0),
                   (-half_web, z_mid + t2 / 2.0)]
    points += [
        (-half_web, z_top - t2),
        (-half_w, z_top - t2),
    ]
    return points


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
