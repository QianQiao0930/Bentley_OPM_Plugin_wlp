# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 尺寸推导库供 ``立管的耳轴.py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""立管的耳轴（F6/F7 · DN50~DN1200）纯数据 / 尺寸推导（不依赖 Bentley 运行时可单测）。

本模块把「立管耳轴（F6 单耳轴 / F7 双耳轴）」标准图的规则集中在一起，供
``立管的耳轴.py`` 调用；只做**数据与尺寸**，不涉及任何 Bentley 几何调用。

设计口径（按用户提供的资料）：

* 主管为**立管**（竖直管），DN50~DN1200；耳轴**垂直于管轴、位于水平面内**；
* **方位角**：``方向 = (sinθ, cosθ, 0)``（0° = 世界 +Y，顺时针）；
* **F6** 单耳轴 / **F7** 双耳轴（180° 对称）；
* **L**：主管**轴线** → 端板**外端面**（mm，用户输入）；
* **耳轴**：空心管，外径查 DN 表，壁厚默认 **STD**（≤24″，注 3，可覆盖）；
  内端到主管外壁，用主管外圆柱布尔减切出**弧形鞍口**；
* **端板**：圆板，直径 = **耳轴外径 + 12**；厚度按端板类型：
  **A = 6**、**B = 表 2**、**C = 无端板**；
* **补强板**：贴主管外壁、围绕耳轴根部的**弯曲圆形钢板**，外径 = **耳轴外径 + 2W**
  （W 查补强板表，按主管管径分档），厚度为变量（暂按 5 mm）；缺省不建（注 11）；
* 编号：``F6/F7-主管管径-耳轴管径(壁厚)-材料代码-L-端板类型-方位角[-补强板厚度]``。
"""

from __future__ import division

import math
from collections import namedtuple


# ---------------------------------------------------------------------------
# 管径：DN → 公称外径（ASME B36.10M）与 NPS 文本
# ---------------------------------------------------------------------------

DN_MIN = 50
DN_MAX = 1200

DN_OD_TABLE = {
    50: (60.3, '2"'), 65: (73.0, '2 1/2"'), 80: (88.9, '3"'),
    90: (101.6, '3 1/2"'), 100: (114.3, '4"'), 125: (141.3, '5"'),
    150: (168.3, '6"'), 200: (219.1, '8"'), 250: (273.0, '10"'),
    300: (323.9, '12"'), 350: (355.6, '14"'), 400: (406.4, '16"'),
    450: (457.2, '18"'), 500: (508.0, '20"'), 550: (558.8, '22"'),
    600: (609.6, '24"'), 650: (660.4, '26"'), 700: (711.2, '28"'),
    750: (762.0, '30"'), 800: (812.8, '32"'), 850: (863.6, '34"'),
    900: (914.4, '36"'), 950: (965.2, '38"'), 1000: (1016.0, '40"'),
    1050: (1066.8, '42"'), 1100: (1117.6, '44"'), 1150: (1168.4, '46"'),
    1200: (1219.2, '48"'),
}

# 公称直径匹配容差（mm）。
DN_MATCH_ABS_MM = 3.0
DN_MATCH_RATIO = 0.15


def dn_choices():
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
# 表 1：主管管径 → 耳轴管径（区间可重叠，取候选）
# ---------------------------------------------------------------------------

TRUNNION_SELECTION = (
    (50, 100, 50),
    (80, 150, 80),
    (100, 200, 100),
    (150, 300, 150),
    (250, 350, 200),
    (300, 500, 250),
    (350, 600, 300),
    (400, 700, 350),
    (450, 800, 400),
    (500, 900, 450),
    (550, 1000, 500),
    (650, 1200, 600),
)


def trunnion_candidates(pipe_dn):
    """返回该主管管径可选的耳轴管径（表 1 区间包含它），升序、去重。"""
    pipe_dn = int(pipe_dn)
    found = sorted({trunnion for low, high, trunnion in TRUNNION_SELECTION
                    if low <= pipe_dn <= high})
    if not found:
        raise ValueError('表 1 中无主管 DN%d 对应的耳轴管径。' % pipe_dn)
    return tuple(found)


def default_trunnion_dn(pipe_dn):
    """默认耳轴管径：表 1 候选中取最大者（偏安全，用户可改）。"""
    return trunnion_candidates(pipe_dn)[-1]


# ---------------------------------------------------------------------------
# 补强板：主管管径 → W（环宽；外径 = 主管外径 + 2W）
# ---------------------------------------------------------------------------

# (主管管径上限 DN, W mm)；按上限分档。
PAD_W_TABLE = (
    (150, 50.0),
    (400, 75.0),
    (600, 100.0),
    (1000, 150.0),
    (2000, 200.0),
    (3000, 300.0),
    (4000, 400.0),
)


def pad_w_mm(pipe_dn):
    """补强板环宽 W（mm）；按主管管径分档。"""
    pipe_dn = int(pipe_dn)
    for upper, width in PAD_W_TABLE:
        if pipe_dn <= upper:
            return float(width)
    return float(PAD_W_TABLE[-1][1])


# 补强板默认厚度（mm）；后续给出更详细参数后可改，面板可覆盖。
DEFAULT_PAD_THICKNESS_MM = 5.0


# ---------------------------------------------------------------------------
# 表 2：耳轴管径 → 端板厚度 t（仅类型 B）
# ---------------------------------------------------------------------------

# (耳轴管径上限 DN, 端板厚度 mm)。
END_PLATE_TABLE = (
    (80, 10.0),
    (200, 12.0),
    (300, 16.0),
    (450, 20.0),
    (600, 25.0),
    (100000, 30.0),
)

# 端板类型：A 固定 6 mm；B 查表 2；C 无端板。
END_PLATE_TYPE_A = 'A'
END_PLATE_TYPE_B = 'B'
END_PLATE_TYPE_C = 'C'
END_PLATE_TYPES = (END_PLATE_TYPE_A, END_PLATE_TYPE_B, END_PLATE_TYPE_C)
END_PLATE_TYPE_A_THICKNESS_MM = 6.0
# 端板直径 = 耳轴外径 + 该值。
END_PLATE_DIA_EXTRA_MM = 12.0


def end_plate_thickness_mm(trunnion_dn):
    """按表 2 由耳轴管径取端板厚度（mm，类型 B）。"""
    trunnion_dn = int(trunnion_dn)
    for upper, thickness in END_PLATE_TABLE:
        if trunnion_dn <= upper:
            return float(thickness)
    return float(END_PLATE_TABLE[-1][1])


def end_plate_thickness_for_type(end_type, trunnion_dn):
    """按端板类型取厚度：A→6；B→表 2；C→0（无端板）。"""
    code = str(end_type).upper()
    if code == END_PLATE_TYPE_A:
        return END_PLATE_TYPE_A_THICKNESS_MM
    if code == END_PLATE_TYPE_B:
        return end_plate_thickness_mm(trunnion_dn)
    if code == END_PLATE_TYPE_C:
        return 0.0
    raise ValueError('未知端板类型：%s（应为 A/B/C）。' % end_type)


# ---------------------------------------------------------------------------
# 耳轴壁厚（默认 STD，注 3）与材料（表 3）
# ---------------------------------------------------------------------------

# ASME B36.10M STD 壁厚（mm）；耳轴 DN50~600（≤24″）默认 STD。
TRUNNION_WALL_STD = {
    50: 3.91, 65: 5.16, 80: 5.49, 90: 5.74, 100: 6.02, 125: 6.55,
    150: 7.11, 200: 8.18, 250: 9.27, 300: 9.53, 350: 9.53, 400: 9.53,
    450: 9.53, 500: 9.53, 550: 9.53, 600: 9.53,
}


def trunnion_wall_std_mm(trunnion_dn):
    try:
        return float(TRUNNION_WALL_STD[int(trunnion_dn)])
    except (KeyError, TypeError, ValueError):
        raise ValueError('耳轴 DN%s 无 STD 壁厚数据。' % trunnion_dn)


MATERIAL_CODES = {
    'L': {'pipe_material': '低温碳钢', 'temp_range': '-40 ~ -21',
          'trunnion_material': 'Q345E 或与管道同材质', 'base_material': 'Q235B'},
    'C1': {'pipe_material': '碳钢', 'temp_range': '-20 ~ 300',
           'trunnion_material': 'Q235B 或与管道同材质', 'base_material': 'Q235B'},
    'C2': {'pipe_material': '碳钢', 'temp_range': '301 ~ 425',
           'trunnion_material': '20 或与管道同材质', 'base_material': 'Q235B'},
    'A1': {'pipe_material': '铬钼钢', 'temp_range': '≤500',
           'trunnion_material': '15CrMoG 或与管道同材质', 'base_material': 'Q235B'},
    'A2': {'pipe_material': '铬钼钢', 'temp_range': '501 ~ 550',
           'trunnion_material': '12Cr1MoVG 或与管道同材质',
           'base_material': 'Q235B'},
    'S': {'pipe_material': '不锈钢', 'temp_range': '-196 ~ 700',
          'trunnion_material': '06Cr19Ni10 或与管道同材质',
          'base_material': 'Q235B'},
    'S1': {'pipe_material': '不锈钢', 'temp_range': '常温',
           'trunnion_material': 'Q235B 或相近材料（注 12）',
           'base_material': 'Q235B'},
}

DEFAULT_PIPE_DN = 100
DEFAULT_MATERIAL_CODE = 'C1'
DEFAULT_L = 500.0
DEFAULT_END_TYPE = END_PLATE_TYPE_A
DEFAULT_AZIMUTH_DEG = 0.0
DEFAULT_TYPE_CODE = 'F6'

TYPE_CODES = ('F6', 'F7')

# 管轴竖直判定容差（°）。
VERTICAL_TOLERANCE_DEG = 5.0

# S1 必须选用补强板（注 12）。
PAD_REQUIRED_MATERIALS = ('S1',)


def material_choices():
    return tuple((code, material_label(code)) for code in sorted(MATERIAL_CODES))


def material_label(code):
    row = material_for_code(code)
    return '%s  |  %s %s  |  耳轴 %s' % (
        code, row['pipe_material'], row['temp_range'], row['trunnion_material'])


def material_for_code(code):
    try:
        return dict(MATERIAL_CODES[str(code).upper()])
    except KeyError:
        raise ValueError('未知材料代码：%s（应为 L/C1/C2/A1/A2/S/S1）。' % code)


def pad_required(material_code):
    return str(material_code).upper() in PAD_REQUIRED_MATERIALS


def type_choices():
    return (('F6', 'F6  |  单耳轴'), ('F7', 'F7  |  双耳轴（180° 对称）'))


def end_type_choices():
    return (('A', 'A  |  端板 6 mm'),
            ('B', 'B  |  端板厚度见表 2'),
            ('C', 'C  |  无端板'))


# ---------------------------------------------------------------------------
# 方位角与编号
# ---------------------------------------------------------------------------


def normalize_azimuth(azimuth_deg):
    return float(azimuth_deg) % 360.0


def format_angle(deg):
    value = float(deg)
    if abs(value - round(value)) < 1.0e-9:
        return str(int(round(value)))
    return ('%.1f' % value).rstrip('0').rstrip('.')


def format_number(value):
    """尺寸数字文本（如壁厚 22.23、补强板厚 5）。"""
    return ('%g' % float(value))


def round_half_up(value):
    return int(math.floor(float(value) + 0.5))


def azimuth_label(type_code, azimuth_deg):
    """编号里的方位角：F7 双耳轴只标较小的那一个（0~180），F6 取 0~360。"""
    azimuth = normalize_azimuth(azimuth_deg)
    if str(type_code).upper() == 'F7':
        azimuth = azimuth % 180.0
    return format_angle(azimuth)


def build_number(type_code, pipe_dn, trunnion_dn, trunnion_wall_mm,
                 wall_is_default, material_code, length_mm, end_type,
                 azimuth_deg, pad_thickness_mm):
    """编号：``F6/F7-主管管径-耳轴管径(壁厚)-材料代码-L-端板类型-方位角[-补强板厚度]``。"""
    wall_suffix = '' if wall_is_default else '(%s)' % format_number(trunnion_wall_mm)
    text = '%s-%s-%s%s-%s-%s-%s-%s' % (
        str(type_code).upper(),
        nps_text(pipe_dn),
        nps_text(trunnion_dn),
        wall_suffix,
        str(material_code).upper(),
        round_half_up(length_mm),
        str(end_type).upper(),
        azimuth_label(type_code, azimuth_deg),
    )
    if pad_thickness_mm and float(pad_thickness_mm) > 0.0:
        text += '-%s' % format_number(pad_thickness_mm)
    return text


# ---------------------------------------------------------------------------
# 尺寸推导
# ---------------------------------------------------------------------------

Layout = namedtuple(
    'Layout',
    'type_code pipe_dn pipe_od pipe_nps trunnion_dn trunnion_od trunnion_nps '
    'trunnion_wall_mm wall_is_default material_code pipe_material '
    'trunnion_material base_material temp_range length_mm end_type '
    'end_plate_thickness_mm end_plate_dia_mm pad_w_mm pad_od_mm '
    'pad_thickness_mm has_pad azimuth_deg azimuth_label number')


def build_layout(type_code=DEFAULT_TYPE_CODE, pipe_dn=DEFAULT_PIPE_DN,
                 trunnion_dn=None, material_code=DEFAULT_MATERIAL_CODE,
                 length_mm=DEFAULT_L, end_type=DEFAULT_END_TYPE,
                 azimuth_deg=DEFAULT_AZIMUTH_DEG,
                 pad_thickness_mm=DEFAULT_PAD_THICKNESS_MM,
                 trunnion_wall_override_mm=None):
    """按所选参数推导整组耳轴的全部尺寸，返回 :class:`Layout`。"""
    type_code = str(type_code).upper()
    if type_code not in TYPE_CODES:
        raise ValueError('未知类型：%s（应为 F6/F7）。' % type_code)

    pipe_dn = int(pipe_dn)
    pipe_od = od_mm(pipe_dn)
    if trunnion_dn is None:
        trunnion_dn = default_trunnion_dn(pipe_dn)
    trunnion_dn = int(trunnion_dn)
    trunnion_od = od_mm(trunnion_dn)

    if trunnion_wall_override_mm is None:
        trunnion_wall = trunnion_wall_std_mm(trunnion_dn)
        wall_is_default = True
    else:
        trunnion_wall = float(trunnion_wall_override_mm)
        wall_is_default = abs(trunnion_wall - trunnion_wall_std_mm(trunnion_dn)) < 1.0e-9

    material = material_for_code(material_code)
    end_type = str(end_type).upper()
    end_plate_thickness = end_plate_thickness_for_type(end_type, trunnion_dn)
    end_plate_dia = trunnion_od + END_PLATE_DIA_EXTRA_MM

    pad_w = pad_w_mm(pipe_dn)
    pad_od = trunnion_od + 2.0 * pad_w
    pad_thickness = float(pad_thickness_mm or 0.0)
    has_pad = pad_thickness > 0.0

    length_mm = float(length_mm)
    if length_mm <= 0.0:
        raise ValueError('L 必须是正数。')
    if trunnion_wall <= 0.0 or trunnion_wall >= trunnion_od / 2.0:
        raise ValueError('耳轴壁厚 %.2f mm 不合理（须 >0 且 <外径一半）。'
                         % trunnion_wall)
    if has_pad and pad_od <= trunnion_od:
        raise ValueError('补强板外径应大于耳轴外径。')

    number = build_number(
        type_code, pipe_dn, trunnion_dn, trunnion_wall, wall_is_default,
        material_code, length_mm, end_type, azimuth_deg, pad_thickness)

    return Layout(
        type_code=type_code,
        pipe_dn=pipe_dn,
        pipe_od=pipe_od,
        pipe_nps=nps_text(pipe_dn),
        trunnion_dn=trunnion_dn,
        trunnion_od=trunnion_od,
        trunnion_nps=nps_text(trunnion_dn),
        trunnion_wall_mm=trunnion_wall,
        wall_is_default=wall_is_default,
        material_code=str(material_code).upper(),
        pipe_material=material['pipe_material'],
        trunnion_material=material['trunnion_material'],
        base_material=material['base_material'],
        temp_range=material['temp_range'],
        length_mm=length_mm,
        end_type=end_type,
        end_plate_thickness_mm=end_plate_thickness,
        end_plate_dia_mm=end_plate_dia,
        pad_w_mm=pad_w,
        pad_od_mm=pad_od,
        pad_thickness_mm=pad_thickness,
        has_pad=has_pad,
        azimuth_deg=normalize_azimuth(azimuth_deg),
        azimuth_label=azimuth_label(type_code, azimuth_deg),
        number=number,
    )


def trunnion_count(layout):
    """F6 → 1，F7 → 2。"""
    return 2 if layout.type_code == 'F7' else 1


def trunnion_azimuths(layout):
    """各耳轴的方位角（°）：F6 单个 θ，F7 θ 与 θ+180。"""
    if layout.type_code == 'F7':
        return (layout.azimuth_deg, (layout.azimuth_deg + 180.0) % 360.0)
    return (layout.azimuth_deg,)


def trunnion_inner_radius(layout):
    return layout.trunnion_od / 2.0 - layout.trunnion_wall_mm


def specification(layout):
    return '%s DN%d×%s 耳轴 L%d %s' % (
        layout.type_code, layout.pipe_dn, layout.trunnion_nps,
        round_half_up(layout.length_mm), layout.trunnion_material)


# ---------------------------------------------------------------------------
# 构件清单（写入公共支吊架库）
# ---------------------------------------------------------------------------


def component_items(layout):
    count = trunnion_count(layout)
    items = [
        {'code': 'Trunnion', 'name': '耳轴',
         'specification': '耳轴 %s φ%.1f×%.2f %s' % (
             layout.trunnion_nps, layout.trunnion_od, layout.trunnion_wall_mm,
             layout.trunnion_material),
         'length': layout.length_mm, 'quantity': count},
    ]
    if layout.end_plate_thickness_mm > 0.0:
        items.append({
            'code': 'EndPlate', 'name': '端板',
            'specification': '端板 %s φ%.1f×%s %s' % (
                layout.end_type, layout.end_plate_dia_mm,
                round_half_up(layout.end_plate_thickness_mm),
                layout.trunnion_material),
            'length': layout.end_plate_dia_mm, 'quantity': count})
    if layout.has_pad:
        items.append({
            'code': 'Pad', 'name': '补强板',
            'specification': '补强板 φ%.1f×%s %s' % (
                layout.pad_od_mm, format_number(layout.pad_thickness_mm),
                layout.pipe_material),
            'length': layout.pad_od_mm, 'quantity': count})
    return items


def describe(layout):
    """一行摘要，供面板状态显示。"""
    text = ('%s；主管 DN%d（%s，OD %.1f）；耳轴 DN%d（%s，OD %.1f，壁厚 %.2f%s）；'
            'L=%.0f；端板 %s' % (
                layout.number, layout.pipe_dn, layout.pipe_nps, layout.pipe_od,
                layout.trunnion_dn, layout.trunnion_nps, layout.trunnion_od,
                layout.trunnion_wall_mm,
                '默认' if layout.wall_is_default else '覆盖',
                layout.length_mm, layout.end_type))
    if layout.end_plate_thickness_mm > 0.0:
        text += '（φ%.1f×%s）' % (layout.end_plate_dia_mm,
                                 round_half_up(layout.end_plate_thickness_mm))
    if layout.has_pad:
        text += '；补强板 φ%.1f×%s' % (layout.pad_od_mm,
                                       format_number(layout.pad_thickness_mm))
    else:
        text += '；无补强板'
    return text
