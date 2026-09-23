# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 逻辑库供 ``单三角架_几何.py`` 与单测 ``import`` 调用，
# 没有独立入口，也不依赖 Bentley 运行时，可在纯 CPython 下单测。
# =============================================================================
"""N 系列设备上生根管架 —— 设备上生根的单三角架（N3）数据模块。

用户在模型中绘制一条**水平辅助线**，作为**管底**（＝三角架横担／构件A 的顶面）：

    线长 = 横担全长 L；线起点 = 横担靠设备一端的顶面点（设备表面所在竖直面）；
    线方向 = 由设备向外。

三角架由两根构件与两块连接板（复用 N8 连接板）组成：

    构件A = 横担（水平，顶面在辅助线上）；
    构件B = 斜撑（45°，连接设备上的连接板与横担）；
    连接板 = 设备预焊件，规格按表 2 自动取（类型 2~5）。

类型：**类型 1** 斜撑在下（由下方连接板向上撑到横担）；**类型 2** 斜撑在上
（由上方连接板向下拉到横担）。H 为横担顶面到斜撑连接板中心的竖直距离。

表 2（子项 A~F）：

    子项   构件A            构件B             连接板类型   MIN.H
    A     [14a             [10               类型 2      390
    B     [20a             [12.6             类型 3      480
    C     H148×100×6×9     H100×100×6×8      类型 2      390
    D     H194×150×6×9     H125×125×6.5×9    类型 3      480
    E     H244×175×7×11    H150×150×7×10     类型 4      500
    F     H294×200×8×12    H200×200×8×12     类型 5      590

表 1（允许的垂直荷载 / kN，按子项与跨距 a 查）见 ``LOAD_TABLE``。

管架编号：``N3-类型-子项-H-L``。
"""

from __future__ import division

import math

# 系列默认代号（编号首段）。
DEFAULT_SERIES = 'N3'

# 斜撑与横担的夹角（度）。
BRACE_ANGLE_DEG = 45.0
# 横担外端到斜撑交点的最小水平余量（mm）。
MIN_END_OVERHANG = 150.0
# 横担与斜撑交点处的筋板厚度（mm）。
STIFFENER_T = 10.0

# 表 2：子项定义。
SUBTYPES = {
    'A': dict(comp_a='[14a', comp_b='[10', plate_type=2, min_h=390.0),
    'B': dict(comp_a='[20a', comp_b='[12.6', plate_type=3, min_h=480.0),
    'C': dict(comp_a='H148x100x6x9', comp_b='H100x100x6x8',
              plate_type=2, min_h=390.0),
    'D': dict(comp_a='H194x150x6x9', comp_b='H125x125x6.5x9',
              plate_type=3, min_h=480.0),
    'E': dict(comp_a='H244x175x7x11', comp_b='H150x150x7x10',
              plate_type=4, min_h=500.0),
    'F': dict(comp_a='H294x200x8x12', comp_b='H200x200x8x12',
              plate_type=5, min_h=590.0),
}
SUBTYPE_KEYS = tuple(sorted(SUBTYPES))

# 截面尺寸：规格 -> (型式, 高 H, 宽 B, 腹板厚 tw, 翼缘厚 tf)。
# 型式 'C' = 槽钢（腹板竖直、开口朝一侧）；'H' = H 型钢。
SECTIONS = {
    '[14a': ('C', 140.0, 58.0, 6.0, 9.5),
    '[20a': ('C', 200.0, 73.0, 7.0, 11.0),
    '[10': ('C', 100.0, 48.0, 5.3, 8.5),
    '[12.6': ('C', 126.0, 53.0, 5.5, 9.0),
    'H148x100x6x9': ('H', 148.0, 100.0, 6.0, 9.0),
    'H100x100x6x8': ('H', 100.0, 100.0, 6.0, 8.0),
    'H194x150x6x9': ('H', 194.0, 150.0, 6.0, 9.0),
    'H125x125x6.5x9': ('H', 125.0, 125.0, 6.5, 9.0),
    'H244x175x7x11': ('H', 244.0, 175.0, 7.0, 11.0),
    'H150x150x7x10': ('H', 150.0, 150.0, 7.0, 10.0),
    'H294x200x8x12': ('H', 294.0, 200.0, 8.0, 12.0),
    'H200x200x8x12': ('H', 200.0, 200.0, 8.0, 12.0),
}

# 表 1：允许的垂直荷载 / kN，按子项与跨距 a（mm）查。缺项表示该跨度无值。
LOAD_TABLE = {
    'A': {500: 38.0, 750: 28.0, 1000: 18.0},
    'B': {750: 40.0, 1000: 35.0, 1250: 30.0},
    'C': {750: 70.0, 1000: 65.0, 1250: 60.0, 1500: 50.0, 1750: 40.0},
    'D': {750: 120.0, 1000: 110.0, 1250: 100.0, 1500: 90.0, 1750: 75.0,
          2000: 60.0},
    'E': {750: 180.0, 1000: 150.0, 1250: 150.0, 1500: 120.0, 1750: 120.0,
          2000: 100.0, 2250: 100.0, 2500: 100.0},
    'F': {750: 250.0, 1000: 250.0, 1250: 225.0, 1500: 225.0, 1750: 225.0,
          2000: 200.0, 2250: 200.0, 2500: 200.0},
}

# 类型：1 斜撑在下（向上撑），2 斜撑在上（向下拉）。
TYPE_OPTIONS = (
    (1, '类型 1  |  斜撑向下（在下·向上撑）'),
    (2, '类型 2  |  斜撑向上（在上·向下拉）'),
)
TYPE_KEYS = tuple(key for key, _label in TYPE_OPTIONS)
TYPE_LABELS = dict(TYPE_OPTIONS)

DEFAULT_OPTIONS = {
    'subtype': 'A',
    'type': 1,
    'height_mm': None,     # None 取该子项 MIN.H
    'series': DEFAULT_SERIES,
}


# ---------------------------------------------------------------------------
# 数据查询
# ---------------------------------------------------------------------------


def subtype_label(subtype):
    info = SUBTYPES[subtype]
    return ('%s  |  A: %s  |  B: %s  |  连接板类型 %d  |  MIN.H %.0f'
            % (subtype, info['comp_a'], info['comp_b'],
               info['plate_type'], info['min_h']))


def section_dims(spec):
    if spec not in SECTIONS:
        raise ValueError('未知截面：%s' % spec)
    kind, height, width, tw, tf = SECTIONS[spec]
    return dict(kind=kind, height=height, width=width, tw=tw, tf=tf)


def type_label(type_key):
    return TYPE_LABELS.get(int(type_key), str(type_key))


def allowable_load(subtype, span_mm):
    """表 1 查值：按子项与跨距 a（向下取表列值）。返回 (值, 用到的列, 说明)。"""
    table = LOAD_TABLE.get(subtype)
    if not table:
        return None, None, '未知子项'
    span = float(span_mm)
    columns = sorted(table)
    if span <= columns[0]:
        return table[columns[0]], columns[0], ''
    for column in columns:
        if span <= column:
            return table[column], column, ''
    return None, None, '跨距 a=%.0f mm 超出表中上限 %.0f mm' % (span, columns[-1])


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


def resolve_options(options, line_length):
    """合并默认值、校验选项，并算出本次生成用的全部毫米尺寸。

    ``line_length`` 为所选辅助线长度（＝横担全长 L）。
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

    try:
        type_key = int(resolved['type'])
    except (TypeError, ValueError):
        raise ValueError('类型必须是 1 或 2。')
    if type_key not in TYPE_KEYS:
        raise ValueError('类型只支持 1（斜撑在下）/ 2（斜撑在上）。')

    try:
        line_length = float(line_length)
    except (TypeError, ValueError):
        raise ValueError('辅助线长度无效。')
    if line_length <= 0.0:
        raise ValueError('辅助线长度必须大于零。')

    if resolved['height_mm'] is None:
        height = info['min_h']
    else:
        try:
            height = float(resolved['height_mm'])
        except (TypeError, ValueError):
            raise ValueError('H 必须是数字（mm）。')
    if height < info['min_h'] - 1.0e-9:
        raise ValueError('H=%.0f mm 小于该子项的 MIN.H=%.0f mm。'
                         % (height, info['min_h']))

    # 斜撑的水平投影（45° 时＝竖直投影）。类型 1 从横担下缘起算，类型 2 从横担顶面起算。
    if type_key == 1:
        run = height - section_a['height']
        attach_z = -section_a['height']
    else:
        run = height
        attach_z = 0.0
    if run <= 0.0:
        raise ValueError('H=%.0f mm 过小：斜撑水平投影 %.1f mm 非正。'
                         % (height, run))

    end_overhang = line_length - run
    if end_overhang < MIN_END_OVERHANG - 1.0e-9:
        raise ValueError(
            '横担外端余量 %.0f mm 小于 %.0f mm：请增大辅助线长 L 或减小 H。'
            % (end_overhang, MIN_END_OVERHANG))

    brace_length = math.hypot(run, run)
    load, load_span, load_note = allowable_load(subtype, run)

    return {
        'subtype': subtype,
        'type': type_key,
        'series': str(resolved['series'] or ''),
        'L': line_length,
        'H': height,
        'min_h': info['min_h'],
        'plate_type': info['plate_type'],
        'comp_a': info['comp_a'],
        'comp_b': info['comp_b'],
        'section_a': section_a,
        'section_b': section_b,
        'brace_angle_deg': BRACE_ANGLE_DEG,
        'brace_run': run,
        'brace_length': brace_length,
        'attach_x': run,
        'attach_z': attach_z,
        'end_overhang': end_overhang,
        'stiffener_t': STIFFENER_T,
        'allowable_load': load,
        'allowable_load_span': load_span,
        'allowable_load_note': load_note,
    }


def build_number(series, type_key, subtype, height_mm, length_mm):
    """管架编号：``系列-类型-子项-H-L``；系列留空则不附加编号。"""
    text = str(series or '').strip()
    if not text:
        return ''
    return '-'.join((text, str(int(type_key)), str(subtype),
                     '%d' % int(round(height_mm)),
                     '%d' % int(round(length_mm))))


def describe_spec(resolved):
    load = resolved.get('allowable_load')
    if load is None:
        load_text = '允许荷载：%s' % (resolved.get('allowable_load_note') or '—')
    else:
        load_text = '允许荷载 %.0f kN（按 a=%.0f 查表）' % (
            load, resolved.get('allowable_load_span') or resolved['brace_run'])
    return ('子项 %s：构件A %s，构件B %s，连接板类型 %d；类型 %d；'
            'H=%.0f（≥%.0f），L=%.0f，斜撑投影 %.0f，端部余量 %.0f；%s。'
            % (resolved['subtype'], resolved['comp_a'], resolved['comp_b'],
               resolved['plate_type'], resolved['type'], resolved['H'],
               resolved['min_h'], resolved['L'], resolved['brace_run'],
               resolved['end_overhang'], load_text))
