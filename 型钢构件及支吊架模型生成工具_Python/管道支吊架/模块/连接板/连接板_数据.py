# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯数据 / 逻辑库供 ``连接板_几何.py`` 与单测 ``import`` 调用，
# 没有独立入口，也不依赖 Bentley 运行时，可在纯 CPython 下单测。
# =============================================================================
"""N 系列设备上生根管架 —— 设备预焊件用连接板（表 1 / 图 1 / 图 2）数据模块。

连接板是设备上的**预焊件**：正方形钢板 E×E×T，在 F×F 方阵上开螺栓孔，孔径 G，
管道支吊架用螺栓 M D 固定在该板上。孔的数量与工况有关：

    * 类型 0、1、2、3 —— 图 1：四角 4 个孔（4 颗螺栓 / 套）；
    * 类型 4、5       —— 图 2：四角 + 四边中点 8 个孔（8 颗螺栓 / 套）。

保温（H）与保冷（C）两种工况的孔径 G 与螺栓长度 L 不同（表 1）；另有
**无保温（N）** 工况，尺寸与保温完全相同，仅编号中不写工况后缀：

    类型   E    F    G(保温) G(保冷)  T    D     L(保温) L(保冷) 螺栓数/套
    0     180  100    18      24     10   M16    40      120       4
    1     290  200    22      28     12   M20    50      120       4
    2     370  270    27      33     16   M24    60      140       4
    3     460  340    33      39     20   M30    80      160       4
    4     480  380    27      33     20   M24    70      150       8
    5     570  450    33      39     25   M30    90      170       8

管架编号：``N8-类型-H/C``（保温 / 保冷）或 ``N8-类型``（无保温）。
"""

from __future__ import division

import math

# 连接板系列默认代号（编号首段）。
DEFAULT_SERIES = 'N8'

# 表 1：连接板尺寸（mm）与螺栓规格。G_ins / L_ins 为保温（H），
# G_cold / L_cold 为保冷（C）；D 为螺栓公称直径，bolt_count 为每套螺栓数。
PLATE_TABLE = {
    0: dict(E=180.0, F=100.0, G_ins=18.0, G_cold=24.0, T=10.0,
            D=16.0, L_ins=40.0, L_cold=120.0, bolt_count=4),
    1: dict(E=290.0, F=200.0, G_ins=22.0, G_cold=28.0, T=12.0,
            D=20.0, L_ins=50.0, L_cold=120.0, bolt_count=4),
    2: dict(E=370.0, F=270.0, G_ins=27.0, G_cold=33.0, T=16.0,
            D=24.0, L_ins=60.0, L_cold=140.0, bolt_count=4),
    3: dict(E=460.0, F=340.0, G_ins=33.0, G_cold=39.0, T=20.0,
            D=30.0, L_ins=80.0, L_cold=160.0, bolt_count=4),
    4: dict(E=480.0, F=380.0, G_ins=27.0, G_cold=33.0, T=20.0,
            D=24.0, L_ins=70.0, L_cold=150.0, bolt_count=8),
    5: dict(E=570.0, F=450.0, G_ins=33.0, G_cold=39.0, T=25.0,
            D=30.0, L_ins=90.0, L_cold=170.0, bolt_count=8),
}

TYPE_KEYS = tuple(sorted(PLATE_TABLE))

# 工况：H = 保温（Hot），C = 保冷（Cold）。孔径与螺栓长度按工况取值。
# 无保温工况代号：尺寸与 H（保温）完全相同，但编号中不写工况后缀。
NO_INSULATION_MODE = 'N'

MODE_OPTIONS = (
    ('H', 'H 保温'),
    ('C', 'C 保冷'),
    ('N', '无保温（数据同 H）'),
)
MODE_KEYS = tuple(key for key, _label in MODE_OPTIONS)
MODE_LABELS = dict(MODE_OPTIONS)

# 安装面：与 混凝土锚板.py 的 ``_PlateFrame`` 一致（wall / floor / ceiling）。
# 螺栓轴线恒为设备表面的外法向，即**垂直于设备表面**伸出。
MOUNT_OPTIONS = (
    ('wall', '竖直设备表面（螺栓垂直于表面·水平）'),
    ('floor', '水平设备顶面（螺栓垂直于表面·朝下）'),
    ('ceiling', '水平设备底面（螺栓垂直于表面·朝上）'),
)
MOUNT_KEYS = tuple(key for key, _label in MOUNT_OPTIONS)
MOUNT_LABELS = dict(MOUNT_OPTIONS)

# 六角头螺栓 / 螺母 / 垫片标准尺寸（GB/T 5782、6170、97.1，近似值），
# 以公称直径 mm 为键，仅用于成形。head_h / nut_h 为头高 / 螺母高，
# *_af 为对边距（对边宽度），washer_od / washer_t 为垫片外径 / 厚。
BOLT_TABLE = {
    16.0: dict(head_af=24.0, head_h=10.0, nut_af=24.0, nut_h=13.0,
               washer_od=30.0, washer_t=3.0),
    20.0: dict(head_af=30.0, head_h=12.5, nut_af=30.0, nut_h=16.0,
               washer_od=37.0, washer_t=3.0),
    24.0: dict(head_af=36.0, head_h=15.0, nut_af=36.0, nut_h=19.0,
               washer_od=44.0, washer_t=4.0),
    30.0: dict(head_af=46.0, head_h=18.7, nut_af=46.0, nut_h=24.0,
               washer_od=56.0, washer_t=4.0),
}

# 螺杆外端超出螺母外端面的长度（mm）：露出的丝头。
BOLT_PROTRUSION_MM = 5.0

DEFAULT_OPTIONS = {
    'type': 0,            # 0 ~ 5
    'mode': 'H',          # H 保温 / C 保冷
    'heading_deg': 0.0,   # 朝向：竖直设备表面为绕 Z 方位角，水平设备表面为绕竖轴转角
    'mount': 'wall',      # 安装面：wall / floor / ceiling
}


# ---------------------------------------------------------------------------
# 数据查询
# ---------------------------------------------------------------------------


def type_label(type_key):
    """下拉框显示用的类型说明。"""
    table = PLATE_TABLE[int(type_key)]
    return ('类型 %d  |  %.0f×%.0f×%.0f  |  %d-φ%.0f/%.0f  |  M%.0f'
            % (int(type_key), table['E'], table['E'], table['T'],
               table['bolt_count'], table['G_ins'], table['G_cold'],
               table['D']))


def mode_label(mode):
    return MODE_LABELS.get(str(mode), str(mode))


def hole_positions(type_key):
    """孔中心在板面内的 (y, z) 坐标（mm），板中心为原点。

    类型 0~3 为四角 4 孔；类型 4、5 为四角 + 四边中点 8 孔，均沿方阵
    F×F 布置（图 1 / 图 2），并绕行一周给出，便于成对生成。
    """
    table = PLATE_TABLE[int(type_key)]
    half = table['F'] / 2.0
    if table['bolt_count'] == 4:
        return [(-half, -half), (half, -half), (half, half), (-half, half)]
    return [(-half, -half), (0.0, -half), (half, -half),
            (half, 0.0), (half, half), (0.0, half),
            (-half, half), (-half, 0.0)]


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


def resolve_options(options=None):
    """合并默认值、校验选项，并算出本次生成用的全部毫米尺寸。

    返回字典含：type / mode / heading_deg / mount / E / F / G / T /
    bolt_dia / bolt_length / bolt_count / holes，以及螺栓紧固件的
    head_af / head_h / nut_af / nut_h / washer_od / washer_t。
    """
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(resolved)
        if unknown:
            raise ValueError('未知选项：%s' % '、'.join(sorted(unknown)))
        resolved.update(options)

    try:
        type_key = int(resolved['type'])
    except (TypeError, ValueError):
        raise ValueError('类型必须是整数 0~5。')
    if type_key not in PLATE_TABLE:
        raise ValueError('类型只支持 %s。' % '、'.join(str(k) for k in TYPE_KEYS))

    mode = str(resolved['mode']).strip().upper()
    if mode not in MODE_KEYS:
        raise ValueError('工况只支持 H（保温）/ C（保冷）/ 无保温。')

    try:
        heading = float(resolved['heading_deg'])
    except (TypeError, ValueError):
        raise ValueError('朝向必须是数字（度）。')
    if not math.isfinite(heading):
        raise ValueError('朝向必须是有限数字。')

    mount = resolved.get('mount') or 'wall'
    if mount not in MOUNT_KEYS:
        raise ValueError('安装面只支持：%s。' % '、'.join(MOUNT_KEYS))

    # 保冷（C）取保冷列；保温（H）与无保温（N）尺寸相同，取保温列。
    table = PLATE_TABLE[type_key]
    if mode == 'C':
        hole_dia = table['G_cold']
        bolt_length = table['L_cold']
    else:
        hole_dia = table['G_ins']
        bolt_length = table['L_ins']
    bolt = BOLT_TABLE.get(float(table['D']))
    if bolt is None:
        raise RuntimeError('缺少 M%.0f 螺栓的紧固件尺寸。' % table['D'])

    return {
        'type': type_key,
        'mode': mode,
        'heading_deg': heading,
        'mount': mount,
        'E': table['E'],
        'F': table['F'],
        'G': hole_dia,
        'T': table['T'],
        'bolt_dia': table['D'],
        'bolt_length': bolt_length,
        'bolt_count': table['bolt_count'],
        'holes': hole_positions(type_key),
        'head_af': bolt['head_af'],
        'head_h': bolt['head_h'],
        'nut_af': bolt['nut_af'],
        'nut_h': bolt['nut_h'],
        'washer_od': bolt['washer_od'],
        'washer_t': bolt['washer_t'],
    }


def describe_spec(options=None):
    """面板信息行用的规格说明。"""
    if isinstance(options, dict) and 'holes' in options:
        resolved = options
    else:
        resolved = resolve_options(options)
    return ('连接板 %.0f×%.0f×%.0f，%d-φ%.0f 孔（F=%.0f 方阵）；'
            'M%.0f×%.0f 螺栓 ×%d；工况 %s。'
            % (resolved['E'], resolved['E'], resolved['T'],
               resolved['bolt_count'], resolved['G'], resolved['F'],
               resolved['bolt_dia'], resolved['bolt_length'],
               resolved['bolt_count'], mode_label(resolved['mode'])))


def build_plate_number(series, type_key, mode):
    """管架编号：``系列-类型``（无保温）或 ``系列-类型-H/C``；系列为空返回空串。

    无保温工况（``NO_INSULATION_MODE``）不写工况后缀，如 ``N8-1``；
    保温 / 保冷写作 ``N8-1-H`` / ``N8-1-C``。
    """
    text = str(series or '').strip()
    if not text:
        return ''
    parts = [text, str(int(type_key))]
    mode = str(mode).strip().upper()
    if mode != NO_INSULATION_MODE:
        parts.append(mode)
    return '-'.join(parts)
