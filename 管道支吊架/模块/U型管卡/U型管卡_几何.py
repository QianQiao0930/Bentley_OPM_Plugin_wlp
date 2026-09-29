# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为 A1 U 型管卡的纯几何 / 数据模块供入口插件 ``import`` 调用，
# 没有独立入口，也不依赖任何 Bentley 运行时符号（可被普通 CPython 单测）。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""A1 U 型管卡 —— 表 1 数据、几何推导与校验（纯 Python，可单测）。

图集口径（HG/T 21629 A1「U 形螺栓管夹」）
-----------------------------------------

表 1 每行给出公称管径 ``DN`` / ``NPS``、U 型螺栓规格（``M6``~``M24``）与四个
尺寸 ``B`` / ``C`` / ``D`` / ``E``，本模块按下面的口径把它们变成几何：

=========  ====================================================================
尺寸       含义（本插件采用的口径）
=========  ====================================================================
``B``      两腿**内边距**（与管外径相当）。用于校验：``B = C − 螺栓直径``。
``C``      两腿**中心距**。腿中心线距管轴 = ``C / 2``。
``D``      管中心 → **腿端**（螺纹端头）的距离。
``E``      **弯弧起点 → 腿端**的直腿段长度（直腿部分）。
=========  ====================================================================

局部坐标架（原点 = 管道中心，即示意图中心）
-------------------------------------------

``X``  管轴方向；
``Y``  开口方向（两条腿伸出的方向），由放置角度绕 ``X`` 旋转得到，默认朝上；
``Z``  管轴与开口方向之外的第三轴。

弯弧定位（**关键口径，2026-09-28 按实机反馈修正**）
--------------------------------------------------

U 型螺栓的弯弧与两条直腿**相切**、半径 ``C / 2``，且**圆心强制落在管轴上**
（``y = 0``）：

* 相切点（弯弧起点）在 ``y = 0``；
* 弯弧最低点在 ``y = −C / 2``；
* 直腿从 ``y = D`` 到 ``y = 0``，长度 = ``D``。

> **为什么弧心必须在管轴上**：螺栓**内表面**到管轴的距离 = ``C/2 − d/2`` = ``B/2``，
> 恰好比管外半径大约 **1.8~3.2 mm** —— 这正是 ``B`` 的物理含义（U 型卡与管子之间的
> 设计间隙），于是弯弧从**外面**包住管子 ✓。
>
> 早期版本按「弧心在 ``D − E``」理解，会把弧心顶到管轴**上方**（DN100：+35），
> 弧底只到 ``−31`` 而管底在 ``−57.1``，于是 **21/27 档管径的弯弧吃进管子内部**
> （DN100 侵入 26 mm、DN900 侵入 398 mm）——实机建模已复现该问题。
>
> 因此表 1 的 ``E`` 在本插件里**只作参考值**（``D − E`` 等于原误解下弧心相对管轴的
> 偏移量 `leg_center_offset`），实际直腿段长 = ``D``。若甲方确认 ``E`` 另有含义
> （例如螺纹段长度），改 :meth:`UBoltsGeometry.straight_mm` 的来源即可。

表 1 全表都满足 ``C = B + d``（``d`` = 螺栓公称直径），这正是「``B`` 是内边距、
``C`` 是中心距」的必然结果，本模块在 :func:`check_table` 里逐行校验。

每腿两颗螺母
------------

螺母沿腿的位置按**甲方口径**：**以「距腿端 ``(D − 管道半径) / 2``」处为中心**，
每腿 2 颗螺母以该中心**对称布置、两两相贴**（``NUT_GAP_MM = 0``）。

DN100 例：``D = 115``、管外半径 ``57.15`` → 中心距腿端 ``28.9``，即螺母中心在
``y = 86.1``，两颗占 ``76.5 ~ 95.7``，完全落在直腿段（``0 ~ 115``）内，腿端还
留 ``19.3`` 的丝头。管外径表里查不到该 DN 时退回 ``BOLT_TIP_EXTRA_MM`` 兜底长度。

刻度说明（与图集有出入、已按甲方口径简化）
------------------------------------------

* **不建顶板（通板）与垫圈**：图集每副 U 型管卡另配一块通板（图上两腿之间那块
  带孔板）；本插件按甲方要求只建 U 型螺栓 + 每腿 2 颗螺母，通板只进清单。
* **不做螺纹牙型的真实几何**：图上腿端画了螺纹示意线，本插件按甲方要求把腿端
  做成**光杆**，螺纹只在清单规格里以 ``M12-6g`` 之类的文字体现。
"""

from __future__ import division

import math

# ---------------------------------------------------------------------------
# 建模常量（比例均为「螺栓公称直径 d 的倍数」，与 管道支吊架 其它插件口径一致）
# ---------------------------------------------------------------------------

#: 六角螺母对边宽 ≈ 1.5 d（M12 → 18，与 GB/T 6170 一致）。
HEX_ACROSS_FLATS_RATIO = 1.5
#: 六角螺母高 ≈ 0.8 d（M12 → 9.6，GB/T 6170 的 M12 螺母高 10.8，偏薄可接受）。
NUT_HEIGHT_RATIO = 0.8
#: 螺母**中心**到腿端的距离 = ``(D − 管道半径) / 该除数``（甲方口径）。
NUT_END_OFFSET_DIVISOR = 2.0
#: 管外径表里查不到该 DN 时，螺母中心到腿端的兜底距离（mm）。
BOLT_TIP_EXTRA_MM = 4.0
#: 两颗螺母之间的间隙（mm）：0 = 相贴（背帽）。
NUT_GAP_MM = 0.0
#: 螺母中心孔单边间隙（mm）：孔径 = d + 2×该值。
NUT_HOLE_CLEARANCE_MM = 1.0
#: 布尔运算贯穿余量（mm）。
THROUGH_MARGIN_MM = 5.0

#: 表 1 允许的角度档位（度）：绕管轴，0° = 开口朝上。
ANGLE_STEPS_DEG = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)
#: 默认角度（开口朝上）。
DEFAULT_ANGLE_DEG = 0.0
#: 兜底管径（管道读不到 / 所选管径不在表 1 时使用）。
DEFAULT_DN = 100

#: 表 1 四列在局部坐标里的「语义名」——改动口径只需改这一行 + 表 1 的列名。
DIMENSION_LEG_INNER = 'B'    # 两腿内边距
DIMENSION_LEG_CENTER = 'C'   # 两腿中心距
DIMENSION_LEG_TIP = 'D'      # 管中心 → 腿端
DIMENSION_STRAIGHT = 'E'     # 原图「直腿段」列（本插件作参考值，见模块文档）

#: 弯弧圆心在管轴上的垂距（mm）。**口径固定值**：弧心必须落在管轴上，弯弧才能从
#: 外面包住管子；详见模块文档「弯弧定位」。改这个值等于换一套包管口径。
ARC_CENTER_ON_AXIS_MM = 0.0


# ---------------------------------------------------------------------------
# 表 1：DN -> 尺寸 / 螺栓 / 允许荷载
# ---------------------------------------------------------------------------
# 表 1 原表的尺寸列从左到右为 A / B / C / D / E，其中 **A 列是螺栓规格**
# （M6 / M10 / …），故这里把 A 列读成 bolt，B~E 读成 B / C / D / E。
# 允许荷载取原表「允许荷载 / kN (20℃)」的正向 / 横向两列，横向为 None 表示原表「—」。

TABLE = {
    # DN15 的 C 列：原图印的是 27，但 27 与同行 B=25 / M6 不自洽（应为 25+6=31），
    # 且 DN20 起全表都严格满足 C = B + d，故这里按 31 录入并列入 KNOWN_TABLE_ISSUES。
    15:  {'nps': '1/2"',   'bolt': 'M6',  'B': 25,  'C': 31,  'D': 70,  'E': 65,
          'load_axial': 2.4, 'load_lateral': 0.6, 'weight_kg': 0.05},
    20:  {'nps': '3/4"',   'bolt': 'M6',  'B': 33,  'C': 39,  'D': 70,  'E': 65,
          'load_axial': 2.4, 'load_lateral': 0.6, 'weight_kg': 0.05},
    25:  {'nps': '1"',     'bolt': 'M6',  'B': 39,  'C': 45,  'D': 70,  'E': 65,
          'load_axial': 2.4, 'load_lateral': 0.6, 'weight_kg': 0.05},
    32:  {'nps': '1 1/4"', 'bolt': 'M10', 'B': 48,  'C': 58,  'D': 75,  'E': 65,
          'load_axial': 2.4, 'load_lateral': 0.6, 'weight_kg': 0.13},
    40:  {'nps': '1 1/2"', 'bolt': 'M10', 'B': 54,  'C': 64,  'D': 75,  'E': 65,
          'load_axial': 6.4, 'load_lateral': 1.6, 'weight_kg': 0.14},
    50:  {'nps': '2"',     'bolt': 'M10', 'B': 66,  'C': 76,  'D': 85,  'E': 70,
          'load_axial': 6.4, 'load_lateral': 1.6, 'weight_kg': 0.15},
    65:  {'nps': '2 1/2"', 'bolt': 'M12', 'B': 79,  'C': 91,  'D': 95,  'E': 80,
          'load_axial': 12.0, 'load_lateral': 3.0, 'weight_kg': 0.32},
    80:  {'nps': '3"',     'bolt': 'M12', 'B': 95,  'C': 107, 'D': 100, 'E': 80,
          'load_axial': 12.0, 'load_lateral': 3.0, 'weight_kg': 0.35},
    90:  {'nps': '3 1/2"', 'bolt': 'M12', 'B': 108, 'C': 120, 'D': 115, 'E': 80,
          'load_axial': 12.0, 'load_lateral': 3.0, 'weight_kg': 0.38},
    100: {'nps': '4"',     'bolt': 'M12', 'B': 120, 'C': 132, 'D': 115, 'E': 80,
          'load_axial': 12.0, 'load_lateral': 3.0, 'weight_kg': 0.41},
    125: {'nps': '5"',     'bolt': 'M12', 'B': 147, 'C': 159, 'D': 130, 'E': 80,
          'load_axial': 12.0, 'load_lateral': 3.0, 'weight_kg': 0.47},
    150: {'nps': '6"',     'bolt': 'M16', 'B': 174, 'C': 190, 'D': 155, 'E': 95,
          'load_axial': 18.0, 'load_lateral': 4.5, 'weight_kg': 0.91},
    200: {'nps': '8"',     'bolt': 'M16', 'B': 225, 'C': 241, 'D': 180, 'E': 95,
          'load_axial': 18.0, 'load_lateral': 4.5, 'weight_kg': 1.0},
    250: {'nps': '10"',    'bolt': 'M20', 'B': 279, 'C': 299, 'D': 215, 'E': 110,
          'load_axial': 28.0, 'load_lateral': 7.0, 'weight_kg': 2.2},
    300: {'nps': '12"',    'bolt': 'M20', 'B': 330, 'C': 350, 'D': 245, 'E': 110,
          'load_axial': 28.0, 'load_lateral': 7.0, 'weight_kg': 3.5},
    350: {'nps': '14"',    'bolt': 'M20', 'B': 362, 'C': 382, 'D': 260, 'E': 110,
          'load_axial': 28.0, 'load_lateral': 7.0, 'weight_kg': 3.8},
    400: {'nps': '16"',    'bolt': 'M20', 'B': 412, 'C': 432, 'D': 285, 'E': 110,
          'load_axial': 28.0, 'load_lateral': 7.0, 'weight_kg': 4.2},
    450: {'nps': '18"',    'bolt': 'M24', 'B': 461, 'C': 485, 'D': 320, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 6.1},
    500: {'nps': '20"',    'bolt': 'M24', 'B': 514, 'C': 538, 'D': 345, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 6.6},
    550: {'nps': '22"',    'bolt': 'M24', 'B': 565, 'C': 589, 'D': 375, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 7.1},
    600: {'nps': '24"',    'bolt': 'M24', 'B': 616, 'C': 640, 'D': 400, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 7.7},
    650: {'nps': '26"',    'bolt': 'M24', 'B': 666, 'C': 690, 'D': 425, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 8.1},
    700: {'nps': '28"',    'bolt': 'M24', 'B': 717, 'C': 741, 'D': 450, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 8.4},
    750: {'nps': '30"',    'bolt': 'M24', 'B': 768, 'C': 792, 'D': 475, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 8.7},
    800: {'nps': '32"',    'bolt': 'M24', 'B': 819, 'C': 843, 'D': 500, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 9.3},
    850: {'nps': '34"',    'bolt': 'M24', 'B': 870, 'C': 894, 'D': 525, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 9.8},
    900: {'nps': '36"',    'bolt': 'M24', 'B': 920, 'C': 944, 'D': 550, 'E': 125,
          'load_axial': 52.0, 'load_lateral': None, 'weight_kg': 10.5},
}

#: 表 1 中**已知的原图偏差**（记录在此，避免后来人以为是录入错误又改回去）。
#: DN15：原图 C 列印作 27，与同行 ``B=25`` / ``M6`` 不自洽（``B + d = 31``）；
#: 且 DN20~DN900 共 26 行全部严格满足 ``C = B + d``，故本表按 **31** 录入。
#: 若甲方确认原图 27 无误，改回 :data:`TABLE` 的 DN15 ``C`` 并在此删掉该条即可。
KNOWN_TABLE_ISSUES = {
    15: 'C 列原图 27，按 B + d 修正为 31',
}

# ---------------------------------------------------------------------------
# 管外径（ASME B36.10M，mm）—— 只用于「弯弧是否包住管子」的自检与提示
# ---------------------------------------------------------------------------

#: DN -> 管外径（mm）。与仓库其它插件（T4 / F6F7 / 保温管夹）用的同一张表。
PIPE_OUTSIDE_DIAMETERS = {
    15: 21.3, 20: 26.7, 25: 33.4, 32: 42.2, 40: 48.3, 50: 60.3, 65: 73.0,
    80: 88.9, 90: 101.6, 100: 114.3, 125: 141.3, 150: 168.3, 200: 219.1,
    250: 273.0, 300: 323.9, 350: 355.6, 400: 406.4, 450: 457.2, 500: 508.0,
    550: 558.8, 600: 609.6, 650: 660.4, 700: 711.2, 750: 762.0, 800: 812.8,
    850: 863.6, 900: 914.4,
}

#: 表 2 材料代码：管道材料 + 螺栓 / 螺母材料。
MATERIALS = {
    'C1': {'pipe': '碳钢',   'temperature': '-',       'bolt_material': 'Q235B或20'},
    'S':  {'pipe': '不锈钢', 'temperature': '-',       'bolt_material': '06Cr19Ni10'},
    'S1': {'pipe': '不锈钢', 'temperature': '≤120',    'bolt_material': 'Q235B或20'},
}

#: 表 3 允许荷载修正系数：温度档 -> 各材料代码的系数。
CORRECTION_FACTORS = {
    '≤150': {'C1': 1.0, 'S': 1.03},
    '200':  {'C1': 0.94, 'S': 0.96},
    '250':  {'C1': 0.82, 'S': 0.9},
    '300':  {'C1': 0.75, 'S': 0.85},
}


# ---------------------------------------------------------------------------
# 查表
# ---------------------------------------------------------------------------


def get_row(dn):
    """取表 1 的 DN 行（副本）；DN 不在表内时抛中文异常。"""
    key = int(dn)
    if key not in TABLE:
        raise ValueError('表 1 中无 DN%d；可选 %d~%d（共 %d 档）。'
                         % (key, min(TABLE), max(TABLE), len(TABLE)))
    row = dict(TABLE[key])
    row['dn'] = key
    return row


def table_dns():
    """表 1 的全部 DN（升序）。"""
    return sorted(TABLE)


def dn_choices():
    """面板下拉用：``[(dn, 'DN100  |  4"')]``。"""
    return [(dn, 'DN%d  |  %s' % (dn, TABLE[dn]['nps'])) for dn in sorted(TABLE)]


def match_table_dn(nominal_mm, tolerance_ratio=0.15, tolerance_mm=5.0):
    """把管道读到的公称直径（mm）匹配到表 1 的 DN 键；匹配不上返回 ``None``。

    与 ``A2-[标准型2螺栓管夹].py`` 的 ``_match_table_dn`` 同一口径：按**公称直径
    数值**就近匹配（不比外径），误差不超过 ``max(5, 15%)`` 才算命中。
    """
    if nominal_mm is None:
        return None
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    best = min(TABLE, key=lambda key: abs(key - value))
    if abs(best - value) <= max(tolerance_mm, tolerance_ratio * value):
        return best
    return None


def bolt_diameter(label):
    """``'M12'`` -> ``12.0``（从规格文字里取数字）。"""
    digits = ''.join(ch for ch in str(label) if ch.isdigit())
    if not digits:
        raise ValueError('无法从螺栓规格 %r 中读出公称直径。' % (label,))
    return float(digits)


def check_table(table=None):
    """逐行校验表 1 自洽性，返回问题清单（空 = 全部通过）。

    校验项：``C = B + d``、``E < D``、``C > B``、数值为正、相邻 DN 的 ``C`` 递增。
    :data:`KNOWN_TABLE_ISSUES` 里登记的既有偏差不计入问题（当前只有 DN15 的 ``C``，
    已按 ``B + d`` 修正录入）。
    """
    table = TABLE if table is None else table
    problems = []
    previous = None
    for dn in sorted(table):
        row = table[dn]
        label = 'DN%d' % dn
        diameter = bolt_diameter(row['bolt'])
        inner = float(row['B'])
        center = float(row['C'])
        tip = float(row['D'])
        straight = float(row['E'])
        if min(inner, center, tip, straight, diameter) <= 0.0:
            problems.append('%s：尺寸 / 直径必须为正数。' % label)
            continue
        if abs(center - (inner + diameter)) > 1.0e-6:
            problems.append('%s：C(%.0f) ≠ B(%.0f) + d(%.0f)。'
                            % (label, center, inner, diameter))
        if straight >= tip:
            problems.append('%s：直腿段 E(%.0f) 必须小于 D(%.0f)。'
                            % (label, straight, tip))
        if center <= inner:
            problems.append('%s：两腿中心距 C 必须大于内边距 B。' % label)
        if previous is not None and center <= previous:
            problems.append('%s：两腿中心距 C 未随管径递增。' % label)
        previous = center
    return problems


# ---------------------------------------------------------------------------
# 几何推导
# ---------------------------------------------------------------------------


class UBoltsGeometry(object):
    """一副 A1 U 型管卡的几何（全部为 mm，局部坐标系见模块文档）。

    ====================  =========================================================
    属性                   含义
    ====================  =========================================================
    ``dn`` / ``nps``      公称管径
    ``bolt`` / ``d``      螺栓规格文字 / 公称直径
    ``r_leg``             腿中心线到管轴的距离（= ``C / 2``），即弯弧半径
    ``leg_tip_y``         腿端坐标（= ``D``）
    ``arc_center_y``      弯弧圆心沿开口方向的坐标（= 0，**固定在管轴上**）
    ``bend_start_y``      弯弧起点 / 直腿下端（= ``arc_center_y`` = 0）
    ``arc_bottom_y``      弯弧最低点（= ``−C / 2``）
    ``straight_mm``       直腿段长（= ``D − bend_start_y``；弧心在管轴上时 = ``D``）
    ``inner_face_radius`` 弯弧处螺栓**内表面**到管轴的距离（= ``C/2 − d/2`` = ``B/2``）
    ``pipe_od_mm``        管外径（ASME B36.10M；表内没有该 DN 时为 ``None``）
    ``pipe_clearance_mm`` 螺栓内表面相对**管外表面**的净空（> 0 = 包在管外）
    ``arc_hugs_pipe``     弯弧是否确实包在管子外面（表内没有该 DN 时为 ``None``）
    ``leg_center_offset`` 原图 ``D − E``（旧口径下弧心相对管轴的偏移，仅参考）
    ``nuts``              每腿螺母：``[(index, 沿开口方向的下底面, 上顶面)]``
    ``nut_top_y``         螺母最高点
    ``height_mm``         整组沿开口方向的总高（螺母顶 → 弯弧最低点）
    ====================  =========================================================
    """

    def __init__(self, dn, **overrides):
        row = get_row(dn)
        self.dn = row['dn']
        self.nps = row['nps']
        self.bolt = row['bolt']
        self.d = bolt_diameter(self.bolt)
        self.inner_mm = float(row['B'])
        self.center_mm = float(row['C'])
        self.tip_mm = float(row['D'])
        # 表 1 的 E 列在本插件里**只作参考**（见模块文档「弯弧定位」）。
        self.table_straight_mm = float(row['E'])
        self.load_axial_kn = row.get('load_axial')
        self.load_lateral_kn = row.get('load_lateral')
        self.weight_kg = row.get('weight_kg')
        self.overrides = dict(overrides)

        self.r_leg = self.center_mm / 2.0
        self.leg_tip_y = self.tip_mm
        # 弯弧圆心固定在管轴上，于是相切点（弯弧起点 / 直腿段下端）就是 y = 0。
        self.arc_center_y = float(ARC_CENTER_ON_AXIS_MM)
        self.bend_start_y = self.arc_center_y
        self.arc_bottom_y = self.arc_center_y - self.r_leg
        # 直腿段长 = 腿端 → 弯弧起点；弧心在管轴上时它就等于 D。
        self.straight_mm = self.leg_tip_y - self.bend_start_y
        # 原误解（弧心在 D−E）下弧心相对管轴的偏移量——留作参考与提示。
        self.leg_center_offset = self.tip_mm - self.table_straight_mm
        self.bend_deviation = self.arc_bottom_y

        self.nut_height = self.d * NUT_HEIGHT_RATIO
        self.nut_across_flats = self.d * HEX_ACROSS_FLATS_RATIO
        self.nut_hole_radius = (self.d + 2.0 * NUT_HOLE_CLEARANCE_MM) / 2.0

        # 螺母沿腿的位置（甲方口径）：**螺母组的中心**距腿端 ``(D − 管道半径)/2``，
        # 每腿 2 颗以该中心对称、相贴上下排布（两螺母的相接面正好落在该中心）。
        # DN100：D=115、管外半径 57.15 → 中心距腿端 28.9、即 y = 86.1，
        # 两颗占 76.5~95.7，落在直腿段（0~115）内、腿端余 19.3。
        self.nut_center_y = self.leg_tip_y - self.nut_end_offset_mm()
        first_bottom = self.nut_center_y - self.nut_height - NUT_GAP_MM / 2.0
        self.nuts = ((1, first_bottom, first_bottom + self.nut_height),
                     (2, first_bottom + self.nut_height + NUT_GAP_MM,
                      first_bottom + 2.0 * self.nut_height + NUT_GAP_MM))
        self.nut_top_y = self.nuts[1][2]

        self.height_mm = self.nut_top_y - self.arc_bottom_y
        self.span_mm = self.center_mm          # 两腿中心距（= 弯弧直径）
        self.outer_span_mm = self.center_mm + self.d  # 两腿外缘

    def nut_end_offset_mm(self):
        """螺母**中心**到腿端的距离（mm）= ``(D − 管道半径) / 2``。

        甲方口径。管外径未知（表 1 有该 DN 但外径表里没有）时退回
        :data:`BOLT_TIP_EXTRA_MM`，保证仍能建模并给出提示。
        """
        diameter = self.pipe_od_mm
        if diameter is None:
            return BOLT_TIP_EXTRA_MM
        return (self.tip_mm - diameter / 2.0) / NUT_END_OFFSET_DIVISOR

    # -- 派生量 ------------------------------------------------------------

    @property
    def hole_radius(self):
        return self.nut_hole_radius

    @property
    def inner_face_radius(self):
        """弯弧处螺栓**内表面**到管轴的距离（mm）= ``C/2 − d/2`` = ``B/2``。"""
        return self.r_leg - self.d / 2.0

    @property
    def pipe_od_mm(self):
        """管外径（mm）；表里没有该 DN 时返回 ``None``。"""
        return PIPE_OUTSIDE_DIAMETERS.get(self.dn)

    def pipe_clearance_mm(self):
        """螺栓内表面相对**管外表面**的净空（mm）。

        正值 = 弯弧从外面包住管子（应该总是正的，约 1.8~3.2 mm）；
        管外径未知时返回 ``None``。
        """
        diameter = self.pipe_od_mm
        if diameter is None:
            return None
        return self.inner_face_radius - diameter / 2.0

    def arc_hugs_pipe(self):
        """弯弧是否确实包在管子外面；管外径未知时返回 ``None``。"""
        clearance = self.pipe_clearance_mm()
        if clearance is None:
            return None
        return clearance > 0.0

    def nut_positions(self):
        """螺母沿开口方向的 ``(下底面, 上顶面, 所在腿的 ±1)`` 序列（共 4 颗）。"""
        result = []
        for sign in (1.0, -1.0):
            for _index, low, high in self.nuts:
                result.append((low, high, sign))
        return result

    def sweep_path(self):
        """扫掠路径的关键点 / 圆弧（局部 ``(x=0, y, z)`` 平面内）。

        返回::

            {'start': (y, z), 'leg_end': (y, z),
             'arc': ((cy, cz), 半径, 起始角°, 扫掠角°), 'end': (y, z)}

        ``leg_end`` 为 +Y 侧直腿与弯弧的相切点，``arc`` 自该点起绕弯弧圆心扫
        180°（经管轴下方）到 −Y 侧相切点；``start`` / ``end`` 为两个腿端。
        弧心在管轴上时，弯弧最低点落在 ``y = −C/2``，即**从外面兜住管子**。
        """
        return {
            'start': (self.leg_tip_y, self.r_leg),
            'leg_end': (self.bend_start_y, self.r_leg),
            'arc': ((self.arc_center_y, 0.0), self.r_leg, 90.0, 180.0),
            'end': (self.leg_tip_y, -self.r_leg),
        }

    def nut_clearance_mm(self):
        """最下面那颗螺母的下底面**高出弯弧起点**的余量（mm）。

        正值 = 螺母完全落在直腿段内（不会压进弯弧）。弧心在管轴上时弯弧起点就是
        管轴所在高度，全表都是正值（最小 DN900 约 337 mm），故该值只作自检与
        提示用。
        """
        return self.nuts[0][1] - self.bend_start_y

    def warnings(self):
        """建模前值得提醒用户的点（不阻断生成）。"""
        notes = []
        if self.nut_clearance_mm() < 0.0:
            notes.append('直腿段（%.0f）过短，两颗螺母已越过弯弧起点。'
                         % self.straight_mm)
        clearance = self.pipe_clearance_mm()
        if clearance is None:
            notes.append('表内没有 DN%d 的管外径，无法核对弯弧与管子的净空。'
                         % self.dn)
        elif clearance <= 0.0:
            notes.append('弯弧内表面（半径 %.1f）已进入 DN%d 管外径（%.1f）之内，'
                         '干涉 %.1f mm。' % (self.inner_face_radius, self.dn,
                                            self.pipe_od_mm, -clearance))
        elif clearance < 1.0:
            notes.append('弯弧与管外表面净空仅 %.1f mm，偏紧。' % clearance)
        return notes


def build_geometry(dn, **overrides):
    """构造一副 U 型管卡的几何；``overrides`` 用于将来覆盖个别尺寸（当前留空）。"""
    return UBoltsGeometry(dn, **overrides)


def assembly_tag(dn, bolt, angle_deg):
    """支吊架编号：``A1-DN100-M12-0°``（角度为面板给出的绕管轴角）。"""
    return 'A1-DN%d-%s-%g°' % (int(dn), bolt, float(angle_deg))


def assembly_spec(dn, geometry):
    """整组规格文字（写进公共库的 Assembly 记录）。"""
    return ('U型螺栓 %s（DN%d / %s）：两腿中心距 C=%.0f、管中心→腿端 D=%.0f、'
            '直腿段 %.0f、腿端在管轴两侧 ±%.0f、弯弧包管净空 %s'
            % (geometry.bolt, int(dn), geometry.nps, geometry.center_mm,
               geometry.tip_mm, geometry.straight_mm, geometry.r_leg,
               _clearance_text(geometry)))


def _clearance_text(geometry):
    """净空的中文描述（管外径未知时说明原因）。"""
    clearance = geometry.pipe_clearance_mm()
    if clearance is None:
        return '未知（表内无该 DN 的管外径）'
    return '%.1f' % clearance


def bom_items(geometry, nut_count=4):
    """构件清单（公共库 ``attach_components`` 的 ``components`` 参数）。

    只列 **U 型螺栓**（1 件）与 **螺母**（每腿 2 颗 × 2 腿 = 4 件）；图上另配的
    **通板（顶板）**按甲方要求不建模，也就不进清单。
    """
    items = [
        {'code': 'U_BOLT', 'name': 'U型螺栓',
         'specification': '%s×%.0f（C=%.0f，D=%.0f，直腿段 %.0f）'
                         % (geometry.bolt, geometry.height_mm,
                            geometry.center_mm, geometry.tip_mm,
                            geometry.straight_mm),
         'length': geometry.height_mm, 'quantity': 1, 'unit': '件'},
        {'code': 'NUT', 'name': '螺母',
         'specification': '%s（对边 %.0f）' % (geometry.bolt,
                                              geometry.nut_across_flats),
         'length': 0.0, 'quantity': int(nut_count), 'unit': '件'},
    ]
    return items


def corrected_load(geometry, material_code, temperature_key):
    """按表 3 修正允许荷载，返回 ``(正向, 横向, 系数)``（横向取不到时为 None）。"""
    if material_code not in CORRECTION_FACTORS.get(temperature_key, {}):
        raise ValueError('表 3 中无「材料 %s × 温度 %s」组合。'
                         % (material_code, temperature_key))
    factor = float(CORRECTION_FACTORS[temperature_key][material_code])
    axial = geometry.load_axial_kn
    lateral = geometry.load_lateral_kn
    return (None if axial is None else axial * factor,
            None if lateral is None else lateral * factor,
            factor)


def angle_choices():
    """面板下拉用：``[(角度, '标签')]``。"""
    labels = {}
    for angle in ANGLE_STEPS_DEG:
        labels[angle] = '%g°' % angle
    labels[0.0] = '0°（开口朝上，默认）'
    labels[90.0] = '90°（开口朝 +Y）'
    labels[180.0] = '180°（开口朝下）'
    labels[270.0] = '270°（开口朝 −Y）'
    return [(angle, labels[angle]) for angle in ANGLE_STEPS_DEG]


def normalize_angle(value):
    """把用户输入的角度规整到 ``[0, 360)``，非法输入抛中文异常。"""
    try:
        angle = float(value)
    except (TypeError, ValueError):
        raise ValueError('角度必须是数字（度）。')
    if not math.isfinite(angle):
        raise ValueError('角度必须是有限数字。')
    return angle % 360.0


# ---------------------------------------------------------------------------
# 摆放坐标架（纯数学，不依赖 Bentley）
# ---------------------------------------------------------------------------


def _orthonormal_frame(axis_x, up=None):
    """由管轴单位向量给出 ``(ex, ey, ez)`` 正交基。

    ``ex`` = 管轴；``ey`` = 世界 +Z 在垂直管轴平面内的投影（近竖直管时退回
    世界 +X）；``ez = ex × ey``。返回 ``(ex, ey, ez)`` 或 ``None``（轴为零向量）。
    """
    length = math.sqrt(axis_x[0] ** 2 + axis_x[1] ** 2 + axis_x[2] ** 2)
    if length <= 1.0e-12:
        return None
    ex = (axis_x[0] / length, axis_x[1] / length, axis_x[2] / length)
    reference = (0.0, 0.0, 1.0) if up is None else tuple(up)
    dot = sum(ex[i] * reference[i] for i in range(3))
    ey = tuple(reference[i] - dot * ex[i] for i in range(3))
    norm = math.sqrt(sum(component * component for component in ey))
    if norm <= 1.0e-9:
        # 管轴近似竖直：竖直方向无法定义开口基准，退回世界 +X。
        reference = (1.0, 0.0, 0.0)
        dot = sum(ex[i] * reference[i] for i in range(3))
        ey = tuple(reference[i] - dot * ex[i] for i in range(3))
        norm = math.sqrt(sum(component * component for component in ey))
        if norm <= 1.0e-9:
            return None
    ey = tuple(component / norm for component in ey)
    ez = (ex[1] * ey[2] - ex[2] * ey[1],
          ex[2] * ey[0] - ex[0] * ey[2],
          ex[0] * ey[1] - ex[1] * ey[0])
    return ex, ey, ez


def placement_frame(axis_x, angle_deg=0.0, up=None):
    """给出放置坐标架 ``(ex, ey, ez)``：``ex`` = 管轴，``ey`` = 开口方向。

    开口方向 = 基准方向（默认世界 +Z，近竖直管时为世界 +X）在垂直管轴平面内
    的投影，再**绕管轴旋转** ``angle_deg``（右手定则）。角度 0° 即「开口朝上」
    （水平管）/「开口朝 +X」（竖直管）。
    """
    frame = _orthonormal_frame(axis_x, up)
    if frame is None:
        return None
    ex, base_y, base_z = frame
    angle = math.radians(float(angle_deg))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    ey = tuple(cos_a * base_y[i] + sin_a * base_z[i] for i in range(3))
    ez = tuple(-sin_a * base_y[i] + cos_a * base_z[i] for i in range(3))
    return ex, ey, ez


def local_to_world(center_mm, frame, x=0.0, y=0.0, z=0.0):
    """把局部坐标 ``(x, y, z)`` 映射到世界（mm）。"""
    ex, ey, ez = frame
    return (center_mm[0] + x * ex[0] + y * ey[0] + z * ez[0],
            center_mm[1] + x * ex[1] + y * ey[1] + z * ez[1],
            center_mm[2] + x * ex[2] + y * ey[2] + z * ez[2])


def describe(geometry, angle_deg):
    """生成给面板「生成记录」用的中文说明（纯文字，可单测）。"""
    angle = normalize_angle(angle_deg)
    lines = [
        'U型管卡 A1（DN%d / %s，螺栓 %s）' % (geometry.dn, geometry.nps,
                                              geometry.bolt),
        '表 1 尺寸：B（两腿内边距）=%.0f、C（两腿中心距）=%.0f、'
        'D（管中心→腿端）=%.0f、E（原图直腿段列，仅参考）=%.0f'
        % (geometry.inner_mm, geometry.center_mm, geometry.tip_mm,
           geometry.table_straight_mm),
        '弯弧：半径 C/2=%.1f，**圆心在管轴上**、与两条直腿相切；'
        '最低点在管轴 %.1f 处（= −C/2）'
        % (geometry.r_leg, geometry.arc_bottom_y),
        '直腿段长 = D = %.0f（弯弧起点在管轴高度 y=0，直腿从 y=0 到 y=D）'
        % geometry.straight_mm,
        '螺母：每腿 2 颗 %s 六角（对边 %.1f、高 %.1f），'
        '中心距腿端 (D−管半径)/2 = %.1f（y=%.1f）；'
        '下螺母 %.1f~%.1f、上螺母 %.1f~%.1f，腿端余 %.1f'
        % (geometry.bolt, geometry.nut_across_flats, geometry.nut_height,
           geometry.nut_end_offset_mm(), geometry.nut_center_y,
           geometry.nuts[0][1], geometry.nuts[0][2],
           geometry.nuts[1][1], geometry.nuts[1][2],
           geometry.leg_tip_y - geometry.nuts[1][2]),
        '放置角度 %g°（绕管轴，0° = 开口朝上）' % angle,
    ]
    clearance = geometry.pipe_clearance_mm()
    if clearance is None:
        lines.append('弯弧包管净空：未知（表内没有 DN%d 的管外径）。'
                     % geometry.dn)
    else:
        lines.append('弯弧包管：螺栓内表面半径 %.1f（= B/2）> 管外半径 %.1f，'
                     '净空 %.1f mm ✓'
                     % (geometry.inner_face_radius,
                        geometry.pipe_od_mm / 2.0, clearance))
    if geometry.load_axial_kn is not None:
        load = '表 1 允许荷载（20℃）：正向 %.1f kN' % geometry.load_axial_kn
        if geometry.load_lateral_kn is not None:
            load += '、横向 %.1f kN' % geometry.load_lateral_kn
        lines.append(load)
    for note in geometry.warnings():
        lines.append('注意：%s' % note)
    return '\n'.join(lines)
