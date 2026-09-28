# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 逻辑库供 ``双三角架_几何.py`` 与单测 ``import`` 调用，
# 没有独立入口，也不依赖 Bentley 运行时，可在纯 CPython 下单测。
# =============================================================================
"""N 系列设备上生根管架 —— 设备上生根的双三角架（N4）数据模块。

用户在模型中绘制一条**水平辅助线**：**起点＝设备中心点、终点＝管道（立管）中心**，
该线**总长 = L**（到设备中心的距离），方向 = 径向（由设备指向管道）。据此生成
**两套对称的三角架** + 两根构件C：

    * 构件A（横担）：两根，位于中心线两侧 ±L2/2，沿径向自端板外表面 r=0 伸到
      r = L1 + L3 + 构件C宽 + 50（外端超出外侧构件C 外缘 50）；
    * 构件B（斜撑）：每根横担一根，45°，连接设备上的连接板与横担（同 N3）；
    * 构件C（连接横担的横担）：两根，垂直于横担，分别位于**管道中心**朝设备侧
      L4、朝外侧 L3，两 C 净距 = L3 + L4；
    * 连接板 + 螺栓：复用 N8，规格按表 3 自动取；交点 10mm 筋板。

**端板外表面（＝设备预焊件外表面）到管道中心的距离 L1 由辅助线总长算出**：

    L1 = L − √(R² − L2²/4) − D          （R = 设备外径/2，D = 设备预焊件长度）

其中 √(R² − L2²/4) 是两根横担所在的切向位置（±L2/2）处，设备表面到设备中心的
距离（两根横担按弦向生根，不是沿设备半径）。

径向坐标 r 自**端板外表面**起算、向**外**（远离设备、指向管道）为正，
管道中心落在 r = L1，L3 / L4 都以管道中心为基准：

    r=0       内侧构件C        管道中心       外侧构件C          横担外端
    端板   [L1−L4−C宽, L1−L4]   r=L1    [L1+L3, L1+L3+C宽]  r=L1+L3+C宽+50
    |            |              |              |                 |
    设备侧 ←———————— 径向 r ————————→ 管道侧

内侧构件C 必须整体留在端板外侧，即 **L1 − L4 − 构件C宽 ≥ 0**（图上 L4 自管道中心
朝设备量、L3 自管道中心朝外量）。横担**长度 = L1 + L3 + 50 + 构件C宽**。

H 为横担顶面到斜撑连接板中心的竖直距离（用户输入，校核 MIN.H）；L2 为两横担
间距（用户输入，校核 MIN.L2）。类型 1 = 斜撑在下、类型 2 = 斜撑在上（同 N3）。

表 1 的跨距 **a ＝ L1**：允许的垂直荷载按 L1 查表，且 **L1 不得超过该子项的最大
a 列**（A 1000 / B 1250 / C 1750 / D 2000 / E 2500 / F 2500，见 ``MAX_L1``）。

``show_preweld`` 打开时另附**设备预焊件**（显示用、75% 透明、不进清单）：
φ100 圆管沿径向焊在设备壁上，管端焊一块与端板同规格的板（E×E×T + 同样的孔），
该板正好落在 N8 螺栓为「另一片连接板」预留的位置（两垫片间距 = 2T）。

表 3（子项 A~F）：

    子项  构件A          构件B           构件C            连接板类型  MIN.H  MIN.L2
    A    [14a           [10             [14a             类型 2     390    390
    B    [20a           [12.6           [20a             类型 3     480    480
    C    H148x100x6x9   H100x100x6x8    H125x125x6.5x9   类型 2     390    390
    D    H194x150x6x9   H125x125x6.5x9  H175x175x7.5x11  类型 3     480    480
    E    H244x175x7x11  H150x150x7x10   H200x200x8x12    类型 4     500    500
    F    H294x200x8x12  H200x200x8x12   H250x250x9x14    类型 5     590    590

管架编号：``N4-类型-子项-H-L1-L2-L3-L4``。
"""

from __future__ import division

import math
import os
import sys

# 复用 N3 的截面表（同一套 [14a / H148×100 等）。
_HERE = os.path.dirname(os.path.abspath(__file__))
_N3_DIR = os.path.join(os.path.dirname(_HERE), '单三角架')
if _N3_DIR not in sys.path:
    sys.path.insert(0, _N3_DIR)

import 单三角架_数据 as n3_data  # noqa: E402

DEFAULT_SERIES = 'N4'

# 横担外端超出外侧构件C 外缘的长度（mm）。
OUTER_OVERHANG = 50.0
# 筋板厚度（mm）。
STIFFENER_T = 10.0
BRACE_ANGLE_DEG = 45.0
# 横担外端到斜撑交点的最小水平余量（mm）。
MIN_END_OVERHANG = 150.0

# ---------------------------------------------------------------------------
# 设备预焊件（``show_preweld`` 打开时附加的**显示用**参照件）
# ---------------------------------------------------------------------------
# 做法：φ100 圆管沿径向焊在设备壁上，管端焊一块**与端板同规格**的板
# （E×E×T + 同样的螺栓孔），该板正落在 N8 螺栓为「另一片连接板」预留的
# 位置（垫片A / 垫片B 间距 = 2T）上。整件按 75% 透明度显示（0.0＝不透明）。
PREWELD_PIPE_OD = 100.0          # 圆管外径（mm）
PREWELD_PIPE_WALL = 4.0          # 圆管壁厚（mm，仅显示用）
PREWELD_PIPE_SEGMENTS = 24       # 圆管外圆的分段数
PREWELD_TRANSPARENCY = 0.75      # 透明度 75%（1.0＝全透明）
PREWELD_COLOR = 3                # 色号（与 N8 连接板同色）

# 表 3：子项定义。
SUBTYPES = {
    'A': dict(comp_a='[14a', comp_b='[10', comp_c='[14a',
              plate_type=2, min_h=390.0, min_l2=390.0),
    'B': dict(comp_a='[20a', comp_b='[12.6', comp_c='[20a',
              plate_type=3, min_h=480.0, min_l2=480.0),
    'C': dict(comp_a='H148x100x6x9', comp_b='H100x100x6x8',
              comp_c='H125x125x6.5x9', plate_type=2, min_h=390.0, min_l2=390.0),
    'D': dict(comp_a='H194x150x6x9', comp_b='H125x125x6.5x9',
              comp_c='H175x175x7.5x11', plate_type=3, min_h=480.0,
              min_l2=480.0),
    'E': dict(comp_a='H244x175x7x11', comp_b='H150x150x7x10',
              comp_c='H200x200x8x12', plate_type=4, min_h=500.0, min_l2=500.0),
    'F': dict(comp_a='H294x200x8x12', comp_b='H200x200x8x12',
              comp_c='H250x250x9x14', plate_type=5, min_h=590.0, min_l2=590.0),
}
SUBTYPE_KEYS = tuple(sorted(SUBTYPES))

# 截面表：在 N3 的基础上补充构件C 用到的两种 H 型钢。
SECTIONS = dict(n3_data.SECTIONS)
SECTIONS.update({
    'H175x175x7.5x11': ('H', 175.0, 175.0, 7.5, 11.0),
    'H250x250x9x14': ('H', 250.0, 250.0, 9.0, 14.0),
})

# 表 1：允许的垂直荷载 / kN，按子项与跨距 a（＝L1，mm）查。
LOAD_VERTICAL = {
    'A': {500: 76.0, 750: 56.0, 1000: 36.0},
    'B': {750: 80.0, 1000: 70.0, 1250: 60.0},
    'C': {750: 140.0, 1000: 130.0, 1250: 120.0, 1500: 100.0, 1750: 80.0},
    'D': {750: 240.0, 1000: 220.0, 1250: 200.0, 1500: 180.0, 1750: 150.0,
          2000: 120.0},
    'E': {750: 360.0, 1000: 300.0, 1250: 300.0, 1500: 240.0, 1750: 240.0,
          2000: 200.0, 2250: 200.0, 2500: 200.0},
    'F': {750: 500.0, 1000: 500.0, 1250: 450.0, 1500: 450.0, 1750: 450.0,
          2000: 400.0, 2250: 400.0, 2500: 400.0},
}

# 表 1 的最大 a 列 ＝ 该子项**允许的最大 L1**（端板外表面 → 管道中心，mm）：
#   A 1000 / B 1250 / C 1750 / D 2000 / E 2500 / F 2500。
MAX_L1 = dict((key, float(max(table))) for key, table in LOAD_VERTICAL.items())

# 表 2：允许的水平荷载 / kN，按子项与跨距 b（mm）查。
LOAD_HORIZONTAL = {
    'A': {500: 6.0, 750: 3.0},
    'B': {500: 12.0, 750: 6.0, 1000: 4.0},
    'C': {500: 16.0, 750: 7.0, 1000: 5.0, 1250: 4.0},
    'D': {500: 40.0, 750: 18.0, 1000: 12.0, 1250: 10.0, 1500: 5.0},
    'E': {500: 70.0, 750: 40.0, 1000: 25.0, 1250: 16.0, 1500: 12.0},
    'F': {500: 90.0, 750: 60.0, 1000: 45.0, 1250: 30.0, 1500: 20.0},
}

TYPE_OPTIONS = (
    (1, '类型 1  |  斜撑向下（在下·向上撑）'),
    (2, '类型 2  |  斜撑向上（在上·向下拉）'),
)
TYPE_KEYS = tuple(key for key, _label in TYPE_OPTIONS)
TYPE_LABELS = dict(TYPE_OPTIONS)

DEFAULT_OPTIONS = {
    'subtype': 'A',
    'type': 1,
    'height_mm': None,       # None 取 MIN.H
    'l2_mm': None,           # None 取 MIN.L2
    'l3_mm': None,           # None 取一个默认（见 resolve）
    'l4_mm': None,
    'equipment_od_mm': None,  # 设备外径 2R（必填，mm）
    'preweld_mm': 0.0,       # 设备预焊件长度 D（可 0，mm）
    'show_preweld': False,   # True 附带设备预焊件（φ100 管 + 板，半透明·仅显示）
    'reverse': False,        # True 交换辅助线两端（起点改用另一端＝设备中心）
    'series': DEFAULT_SERIES,
}


def subtype_label(subtype):
    """下拉框用短标签：子项 + 三根构件截面（板号 / MIN 值在面板信息行里显示）。"""
    info = SUBTYPES[subtype]
    return ('%s | %s + %s + %s'
            % (subtype, info['comp_a'], info['comp_b'], info['comp_c']))


def subtype_detail(subtype):
    """子项补充说明：连接板类型与 MIN.H / MIN.L2。"""
    info = SUBTYPES[subtype]
    return '板%d ｜ MIN.H %.0f ｜ MIN.L2 %.0f' % (
        info['plate_type'], info['min_h'], info['min_l2'])


def section_dims(spec):
    if spec not in SECTIONS:
        raise ValueError('未知截面：%s' % spec)
    kind, height, width, tw, tf = SECTIONS[spec]
    return dict(kind=kind, height=height, width=width, tw=tw, tf=tf)


def type_label(type_key):
    return TYPE_LABELS.get(int(type_key), str(type_key))


def _lookup(table, span_mm, label):
    columns = sorted(table)
    span = float(span_mm)
    if span <= columns[0]:
        return table[columns[0]], columns[0], ''
    for column in columns:
        if span <= column:
            return table[column], column, ''
    return None, None, '%s=%.0f 超出表中上限 %.0f' % (label, span, columns[-1])


def vertical_load(subtype, a_mm):
    return _lookup(LOAD_VERTICAL.get(subtype, {}), a_mm, 'a')


def horizontal_load(subtype, b_mm):
    return _lookup(LOAD_HORIZONTAL.get(subtype, {}), b_mm, 'b')


# ---------------------------------------------------------------------------
# 辅助线：设备中心 → 管道中心
# ---------------------------------------------------------------------------


def orient_line(line, reverse=False):
    """按「起点＝设备中心、终点＝管道中心」的口径返回辅助线**副本**。

    辅助线约定**起点**为设备中心点、**方向**为由设备指向管道；直线画反了
    （起点落在管道侧）时用 ``reverse=True`` 交换两端：起点取原终点、
    方向反转 180°，于是全部构件一起翻到正确一侧。

    ``length_mm`` / ``z_mm`` 不变；不修改传入的字典（``reverse=False`` 时
    也返回副本）。
    """
    oriented = dict(line)
    if not reverse:
        return oriented

    start = line.get('start_mm')
    end = line.get('end_mm')
    if start is not None and end is not None:
        oriented['start_mm'] = tuple(end)
        oriented['end_mm'] = tuple(start)

    try:
        heading = float(line.get('heading_deg') or 0.0) + 180.0
    except (TypeError, ValueError):
        heading = 0.0
    # 归一化到 (-180, 180]，与 extract_horizontal_line() 的 atan2 取值域一致。
    while heading > 180.0:
        heading -= 360.0
    while heading <= -180.0:
        heading += 360.0
    oriented['heading_deg'] = heading
    return oriented


def plate_line(line, l1_mm):
    """把「设备中心 → 管道中心」的辅助线内缩 L1，得到**施工基准线**。

    返回副本的**起点＝端板外表面**（设备预焊件外表面，即管道中心沿辅助线
    回退 L1 处），**方向不变**（仍由设备指向管道），``length_mm`` = L1。
    构件全部以该起点为 r=0 定位（对应图上 L1：端板外表面 → 管道中心）。
    """
    if line.get('end_mm') is None:
        raise ValueError('辅助线缺少终点（管道中心）。')

    end = tuple(line['end_mm'])
    try:
        heading = float(line.get('heading_deg') or 0.0)
    except (TypeError, ValueError):
        heading = 0.0
    radians = math.radians(heading)
    ux, uy = math.cos(radians), math.sin(radians)
    length = float(l1_mm)

    oriented = dict(line)
    oriented['start_mm'] = (end[0] - ux * length, end[1] - uy * length, end[2])
    oriented['end_mm'] = end
    oriented['length_mm'] = length
    return oriented


def equipment_face_r(radius_mm, l2_mm):
    """两横担切向位置（±L2/2）处，设备表面到设备中心的距离 √(R² − L2²/4)。"""
    half = float(l2_mm) / 2.0
    if half >= radius_mm:
        raise ValueError('L2/2=%.0f mm 已不小于设备半径 R=%.0f mm（设备外径 2R=%.0f mm）：'
                         '两根横担超出设备外圆，无法生根。'
                         % (half, radius_mm, radius_mm * 2.0))
    return math.sqrt(radius_mm * radius_mm - half * half)


def compute_l1(total_length_mm, radius_mm, l2_mm, preweld_mm):
    """L1 = L − √(R² − L2²/4) − D（端板外表面 → 管道中心）。"""
    return (float(total_length_mm)
            - equipment_face_r(radius_mm, l2_mm)
            - float(preweld_mm))


def resolve_options(options, line_length):
    """合并默认值、校验选项，并算出全部毫米尺寸。

    ``line_length`` = 所选辅助线**总长 L**（设备中心 → 管道中心）；
    L1 = L − √(R² − L2²/4) − D 在本函数内算出。
    """
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(resolved)
        if unknown:
            raise ValueError('未知选项：%s' % '、'.join(sorted(unknown)))
        resolved.update(options)

    subtype = resolved['subtype']
    if subtype not in SUBTYPES:
        raise ValueError('子项只支持 %s。' % '、'.join(SUBTYPE_KEYS))
    info = SUBTYPES[subtype]
    section_a = section_dims(info['comp_a'])
    section_b = section_dims(info['comp_b'])
    section_c = section_dims(info['comp_c'])
    c_width = section_c['width']   # 构件C 的宽度（径向）

    try:
        type_key = int(resolved['type'])
    except (TypeError, ValueError):
        raise ValueError('类型必须是 1 或 2。')
    if type_key not in TYPE_KEYS:
        raise ValueError('类型只支持 1（斜撑在下）/ 2（斜撑在上）。')

    try:
        l_total = float(line_length)
    except (TypeError, ValueError):
        raise ValueError('辅助线长度无效。')
    if l_total <= 0.0:
        raise ValueError('辅助线长度必须大于零。')

    def _positive(value, default, name):
        if value is None:
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError('%s 必须是数字（mm）。' % name)
        if number <= 0.0:
            raise ValueError('%s 必须大于零。' % name)
        return number

    height = _positive(resolved['height_mm'], info['min_h'], 'H')
    if height < info['min_h'] - 1.0e-9:
        raise ValueError('H=%.0f mm 小于该子项的 MIN.H=%.0f mm。'
                         % (height, info['min_h']))
    l2 = _positive(resolved['l2_mm'], info['min_l2'], 'L2')
    if l2 < info['min_l2'] - 1.0e-9:
        raise ValueError('L2=%.0f mm 小于该子项的 MIN.L2=%.0f mm。'
                         % (l2, info['min_l2']))

    # 设备外径 2R（必填）与设备预焊件长度 D（可 0）。
    od_value = resolved['equipment_od_mm']
    od_blank = isinstance(od_value, str) and not od_value.strip()
    if od_value is None or od_blank:
        raise ValueError('请填写设备外径 2R（mm）。')
    try:
        equipment_od = float(od_value)
    except (TypeError, ValueError):
        raise ValueError('设备外径 2R 必须是数字（mm）。')
    if equipment_od <= 0.0:
        raise ValueError('设备外径 2R 必须大于零。')
    radius = equipment_od / 2.0                 # R = 设备外径/2

    preweld_value = resolved['preweld_mm']
    if preweld_value is None or (isinstance(preweld_value, str)
                                 and not preweld_value.strip()):
        preweld = 0.0
    else:
        try:
            preweld = float(preweld_value)
        except (TypeError, ValueError):
            raise ValueError('设备预焊件长度 D 必须是数字（mm）。')
    if preweld < 0.0:
        raise ValueError('设备预焊件长度 D 不能为负。')

    # 端板外表面（设备预焊件外表面）→ 管道中心：
    #     L1 = L − √(R² − L2²/4) − D
    l1 = compute_l1(l_total, radius, l2, preweld)
    if l1 <= 0.0:
        raise ValueError('辅助线总长 L=%.0f mm 过短（或 2R / D 过大）：算得 '
                         'L1=L-sqrt(R^2-L2^2/4)-D=%.0f mm，必须大于零。'
                         % (l_total, l1))

    # 表 1 的 a ＝ L1：L1 不得超过该子项的最大 a 列（＝最大允许 L1）。
    max_l1 = MAX_L1.get(subtype)
    if max_l1 is not None and l1 > max_l1 + 1.0e-9:
        raise ValueError('L1=%.0f mm 超出子项 %s 的最大允许值 a=%.0f mm（表 1）：'
                         '请缩短辅助线、减小 2R / D，或改用更大的子项。'
                         % (l1, subtype, max_l1))

    # 斜撑几何（同 N3），先算出来以便给 L3 一个合适的默认值。
    if type_key == 1:
        run = height - section_a['height']
        attach_z = -section_a['height']
    else:
        run = height
        attach_z = 0.0
    if run <= 0.0:
        raise ValueError('H=%.0f mm 过小：斜撑水平投影非正。' % height)

    # L3 / L4 都自**管道中心**（r=L1）量起：内侧构件C 朝设备、外侧构件C 朝外，
    # 两 C 净距 = L3 + L4；内侧构件C 必须整体留在端板外侧。
    l3 = _positive(resolved['l3_mm'], max(1.0, l1 * 0.5), 'L3')
    l4 = _positive(resolved['l4_mm'], max(1.0, l1 * 0.25), 'L4')
    if l1 - l4 - c_width < -1.0e-9:
        raise ValueError('L4=%.0f mm 过大：内侧构件C（宽 %.0f mm）越过端板外表面'
                         '（需要 L1 - L4 - 构件C宽 >= 0，当前 %.0f mm）。'
                         % (l4, c_width, l1 - l4 - c_width))

    # 横担：自辅助线起点（端板外表面 r=0）沿径向伸出，
    # 长度 = L1 + L3 + 50 + 构件C宽。
    beam_start_r = 0.0
    beam_length = l1 + l3 + OUTER_OVERHANG + c_width
    outer_end = beam_length

    attach_x = run                       # 距横担内端（r=0）的水平距离
    end_overhang = beam_length - attach_x
    if end_overhang < MIN_END_OVERHANG - 1.0e-9:
        raise ValueError('横担外端余量 %.0f mm 小于 %.0f mm：请增大 L3 或减小 H。'
                         % (end_overhang, MIN_END_OVERHANG))

    brace_length = math.hypot(run, run)
    # 表 1 的 a ＝ L1（端板外表面 → 管道中心）；表 2 的 b ＝ L2。
    v_load, v_span, v_note = vertical_load(subtype, l1)
    h_load, h_span, h_note = horizontal_load(subtype, l2)

    return {
        'subtype': subtype, 'type': type_key,
        'series': str(resolved['series'] or ''),
        'reverse': bool(resolved['reverse']),
        'show_preweld': bool(resolved['show_preweld']),
        # L = 辅助线总长（设备中心 → 管道中心）；L1 = 端板外表面 → 管道中心。
        'L': l_total, 'L1': l1, 'L2': l2, 'L3': l3, 'L4': l4,
        'OD': equipment_od, 'R': radius, 'D': preweld,
        'face_r': equipment_face_r(radius, l2),
        # 表 1 的跨距 a ＝ L1；max_l1 ＝ 该子项允许的最大 L1（表 1 最大 a 列）。
        'a': l1, 'max_l1': max_l1,
        'H': height, 'min_h': info['min_h'], 'min_l2': info['min_l2'],
        'plate_type': info['plate_type'],
        'comp_a': info['comp_a'], 'comp_b': info['comp_b'],
        'comp_c': info['comp_c'],
        'section_a': section_a, 'section_b': section_b, 'section_c': section_c,
        'c_width': c_width,
        # 构件C 的切向跨距（两端焊到横担腹板）：
        #   槽钢背靠背：两腹板外表面净距 = L2 − 构件A宽；
        #   工字钢：两腹板侧面净距 = L2 − 构件A腹板厚。
        'connector_span': (l2 - section_a['width']
                           if section_a['kind'] == 'C'
                           else l2 - section_a['tw']),
        'outer_end': outer_end, 'beam_length': beam_length,
        'beam_start_r': beam_start_r, 'beam_offset': l2 / 2.0,
        'brace_run': run, 'brace_length': brace_length,
        'attach_x': attach_x, 'attach_z': attach_z,
        'end_overhang': end_overhang,
        'stiffener_t': STIFFENER_T,
        'outer_overhang': OUTER_OVERHANG,
        'brace_angle_deg': BRACE_ANGLE_DEG,
        'vertical_load': v_load, 'vertical_load_span': v_span,
        'vertical_load_note': v_note,
        'horizontal_load': h_load, 'horizontal_load_span': h_span,
        'horizontal_load_note': h_note,
    }


def build_number(series, type_key, subtype, height_mm, l1, l2, l3, l4):
    """管架编号：``N4-类型-子项-H-L1-L2-L3-L4``；系列留空则不附加编号。"""
    text = str(series or '').strip()
    if not text:
        return ''
    return '-'.join((text, str(int(type_key)), str(subtype),
                     '%d' % int(round(height_mm)), '%d' % int(round(l1)),
                     '%d' % int(round(l2)), '%d' % int(round(l3)),
                     '%d' % int(round(l4))))


def describe_spec(resolved):
    """一行式规格摘要（面板「说明」框；构件截面见面板的「构件A/B/C」行）。"""
    v = resolved.get('vertical_load')
    h = resolved.get('horizontal_load')
    v_text = ('%.0f' % v) if v is not None else '—'
    h_text = ('%.0f' % h) if h is not None else '—'
    return ('子项 %s ｜ 板%d ｜ 类型 %d ｜ L=%.0f（2R %.0f·D %.0f）→ L1=%.0f'
            '（表 1 a ≤ %.0f）｜ H %.0f L2 %.0f L3 %.0f L4 %.0f ｜ 横担 %.0f'
            ' ｜ 垂直 %s / 水平 %s kN'
            % (resolved['subtype'], resolved['plate_type'], resolved['type'],
               resolved['L'], resolved['OD'], resolved['D'], resolved['L1'],
               resolved['max_l1'] or 0.0, resolved['H'], resolved['L2'],
               resolved['L3'], resolved['L4'], resolved['beam_length'],
               v_text, h_text))
