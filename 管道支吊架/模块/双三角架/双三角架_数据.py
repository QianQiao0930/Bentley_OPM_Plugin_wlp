# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 逻辑库供 ``双三角架_几何.py`` 与单测 ``import`` 调用，
# 没有独立入口，也不依赖 Bentley 运行时，可在纯 CPython 下单测。
# =============================================================================
"""N 系列设备上生根管架 —— 设备上生根的双三角架（N4）数据模块。

用户在模型中绘制一条**水平辅助线**作为整组**中心线**（径向，指向设备外侧），
其**长度 = L1**（立管中心线 → 端板外表面），据此生成**两套对称的三角架**：

    * 构件A（横担）：两根，位于中心线两侧 ±L2/2，沿径向从端板 r=L1 伸到
      r = L3 + C宽 + 50（外端超出外侧构件C 外缘 50）；
    * 构件B（斜撑）：每根横担一根，45°，连接设备上的连接板与横担（同 N3）；
    * 构件C（连接横担的横担）：两根，**分居端板两侧、方向相反**，内边缘分别在
      r=L1−L4（朝设备侧）、r=L1+L3（朝外侧），两 C 净距 = L3 + L4；
    * 连接板 + 螺栓：复用 N8，规格按表 3 自动取；交点 10mm 筋板。

径向坐标 r 从**立管中心线**起算、向外为正。横担自中心线 r=0 沿径向伸出，
**长度 = L1 + L3 + 50 + 构件C宽**；端板在 r=L1，L3 / L4 自端板量起、方向相反：

    0       内侧C内缘   端板     外侧C内缘   外侧C外缘         横担外端
    |           |        |          |           |                |
    r=0      r=L1-L4   r=L1     r=L1+L3  r=L1+L3+C宽  r=L1+L3+C宽+50

H 为横担顶面到斜撑连接板中心的竖直距离（用户输入，校核 MIN.H）；L2 为两横担
间距（用户输入，校核 MIN.L2）。类型 1 = 斜撑在下、类型 2 = 斜撑在上（同 N3）。

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

# 表 1：允许的垂直荷载 / kN，按子项与跨距 a（mm）查。
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
    'height_mm': None,     # None 取 MIN.H
    'l2_mm': None,         # None 取 MIN.L2
    'l3_mm': None,         # None 取一个默认（见 resolve）
    'l4_mm': None,
    'series': DEFAULT_SERIES,
}


def subtype_label(subtype):
    info = SUBTYPES[subtype]
    return ('%s  |  A:%s  B:%s  C:%s  |  连接板 %d  |  MIN.H %.0f  MIN.L2 %.0f'
            % (subtype, info['comp_a'], info['comp_b'], info['comp_c'],
               info['plate_type'], info['min_h'], info['min_l2']))


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


def resolve_options(options, line_length):
    """合并默认值、校验选项，并算出全部毫米尺寸。

    ``line_length`` = 所选辅助线长度 = L1（立管中心线 → 端板外表面）。
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
        l1 = float(line_length)
    except (TypeError, ValueError):
        raise ValueError('辅助线长度无效。')
    if l1 <= 0.0:
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

    # 斜撑几何（同 N3），先算出来以便给 L3 一个合适的默认值。
    if type_key == 1:
        run = height - section_a['height']
        attach_z = -section_a['height']
    else:
        run = height
        attach_z = 0.0
    if run <= 0.0:
        raise ValueError('H=%.0f mm 过小：斜撑水平投影非正。' % height)

    # L3 / L4 都自端板 r=L1 量起；内侧构件C 由 L4 控制，可与 L3 相同甚至更大。
    l3 = _positive(resolved['l3_mm'], max(1.0, l1 * 0.5), 'L3')
    l4 = _positive(resolved['l4_mm'], max(1.0, l1 * 0.25), 'L4')

    # 横担：自辅助线起点（中心线 r=0）沿径向伸出，长度 = L1 + L3 + 50 + C宽。
    beam_start_r = 0.0
    beam_length = l1 + l3 + OUTER_OVERHANG + c_width
    outer_end = beam_length

    attach_x = run                       # 距横担内端（r=0）的水平距离
    end_overhang = beam_length - attach_x
    if end_overhang < MIN_END_OVERHANG - 1.0e-9:
        raise ValueError('横担外端余量 %.0f mm 小于 %.0f mm：请增大 L3 或减小 H。'
                         % (end_overhang, MIN_END_OVERHANG))

    brace_length = math.hypot(run, run)
    v_load, v_span, v_note = vertical_load(subtype, run)
    h_load, h_span, h_note = horizontal_load(subtype, l2)

    return {
        'subtype': subtype, 'type': type_key,
        'series': str(resolved['series'] or ''),
        'L1': l1, 'L2': l2, 'L3': l3, 'L4': l4,
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
    v = resolved.get('vertical_load')
    h = resolved.get('horizontal_load')
    v_text = ('%.0f' % v) if v is not None else '—'
    h_text = ('%.0f' % h) if h is not None else '—'
    return ('子项 %s：A %s×2 / B %s×2 / C %s×2；连接板类型 %d；类型 %d；'
            'H=%.0f，L1=%.0f，L2=%.0f，L3=%.0f，L4=%.0f，横担长 %.0f；'
            '允许荷载 垂直 %s / 水平 %s kN。'
            % (resolved['subtype'], resolved['comp_a'], resolved['comp_b'],
               resolved['comp_c'], resolved['plate_type'], resolved['type'],
               resolved['H'], resolved['L1'], resolved['L2'], resolved['L3'],
               resolved['L4'], resolved['beam_length'], v_text, h_text))
