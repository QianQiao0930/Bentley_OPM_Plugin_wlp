# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为读取库供 ``管道信息查询.py`` ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""管道信息读取 —— OPM 管道元件的 EC 属性 + 轴线几何（共享模块）。

点取一个 OPM 管道 / 管道元件后，本模块负责把两路信息合起来：

1. **EC 属性**：元素上挂的 OpenPlant 3D 实例（``PIPE`` / ``PIPE_ELBOW`` …，
   基类 ``PIPING_COMPONENT``）里的
   ``LINENUMBER`` / ``NOMINAL_DIAMETER`` / ``OUTSIDE_DIAMETER`` /
   ``WALL_THICKNESS`` / ``INSULATION`` / ``INSULATION_THICKNESS`` /
   ``SPECIFICATION`` / ``MATERIAL`` 等；
2. **轴线几何**：由元素的曲线求起点、终点、走向与**中心线标高**（几何值，
   与 EC 属性无关，因此永远可信）。

**单位**：OpenPlant_3D 的 EC Schema 里长度类属性是裸 double，没有 KindOfQuantity，
不同项目的 DGN 可能存米、也可能存毫米。本模块不硬编码，而是
用 **属性 ``LENGTH`` ↔ 几何长度** 标定出真正的存储单位
（:func:`detect_length_scale`），标定不成立时退回兜底规则
（:func:`guess_length_scale`）并在报告里标注"低置信度"，同时在面板上提供
「属性单位」手动覆盖。

本模块不依赖 Qt / UI，可在纯 CPython 下单测其中的纯函数。
"""

from __future__ import division

import math
import re
import sys as _sys

# 本读取库的接口版本。入口脚本会核对这个号：MicroStation 会话里 sys.modules
# 会保留上次运行加载的**旧模块对象**，磁盘上若还是旧文件，就会在导入期报
# "no attribute ..."。有了版本号，这种情况会变成一句明确的中文提示。
READER_API_VERSION = 8

# Bentley 运行时：在 OPM / MicroStation 中存在；纯 CPython 下缺失，此时仍可
# 导入本模块以单测纯逻辑（EC / 几何相关函数不可调用）。
try:
    from MSPyBentley import *  # noqa: F401,F403
    from MSPyBentleyGeom import *  # noqa: F401,F403
    from MSPyECObjects import *  # noqa: F401,F403
    from MSPyDgnPlatform import *  # noqa: F401,F403
    from MSPyDgnView import *  # noqa: F401,F403
    from MSPyMstnPlatform import *  # noqa: F401,F403
except Exception:  # pragma: no cover - 仅在无 Bentley 运行时时触发
    pass

# 运行本插件时实际加载过的 MSPy 模块。同一个符号由哪个模块导出，各版本并不
# 一致（例如 ISessionMgr 就不在通配导入导出的范围内），所以下面统一按名字补齐。
MSPY_MODULES = ('MSPyBentley', 'MSPyBentleyGeom', 'MSPyECObjects',
                'MSPyDgnPlatform', 'MSPyDgnView', 'MSPyMstnPlatform')

# 本模块**必需**的 Bentley 符号。``from MSPyX import *`` 只导出其中一部分，
# 缺的那些由 :func:`fill_mspy_symbols` 在已加载的 MSPy 模块里按名字补绑。
# 少了任何一个，本模块就跑不起来，启动自检会把它报出来。
MSPY_SYMBOLS = (
    'ISessionMgr',
    'ICurvePrimitive',
    'ICurvePathQuery',
    'ECQuery',
    'ECQueryProcessFlags',
    'DgnECManager',
    'FindInstancesScope',
    'FindInstancesScopeOption',
    'DgnECHostType',
    'ECValue',
    'ECObjectsStatus',
    'ECValuesCollection',
    'EditElementHandle',
    'WString',
    'BentleyStatus',
)

# 只是**备用**路径的符号（查询标志的兜底写法），缺了不影响主流程，
# 因此只补绑、不参与"缺失报警"。
MSPY_OPTIONAL_SYMBOLS = (
    'eECQUERY_PROCESS_SearchAllClasses',
)


def _symbol_sources():
    """符号查找来源：已加载的 MSPy 模块，最后兜底内建命名空间。

    个别版本的 Python 宿主会把 MSPy 符号直接注入 ``builtins``，
    所以这里把内建也当成一个来源（只按明确的符号名查找，不会误绑）。
    """
    for module_name in MSPY_MODULES:
        module = _sys.modules.get(module_name)
        if module is not None:
            yield module
    try:
        import builtins
        yield builtins
    except Exception:
        return


def fill_mspy_symbols(names, namespace=None):
    """把通配导入没导出的 MSPy 符号，按名字补齐到 *namespace*（默认本模块）。

    MicroStation 各版本里"某个符号由哪个 MSPy 模块导出"并不固定，
    ``from MSPyX import *`` 也只导出其中一部分（``ISessionMgr`` 就是典型），
    所以这里不猜模块，直接在**已加载的 MSPy 模块**里按名字查找并补绑。

    返回本次补绑成功的符号名列表；调用方可用
    ``[n for n in names if n not in namespace]`` 得出仍缺失的符号。
    """
    target = globals() if namespace is None else namespace
    bound = []
    for name in names:
        if name in target:
            continue
        for source in _symbol_sources():
            try:
                value = getattr(source, name)
            except Exception:
                continue
            # 有的模块对未知属性返回 None 而不抛异常，那不是"找到了"。
            if value is None:
                continue
            target[name] = value
            bound.append(name)
            break
    return bound


# 导入本模块时立即补齐（在 Bentley 运行下生效；纯 CPython 下找不到任何模块，
# 各符号保持未定义，纯逻辑函数不受影响）。
MSPY_BOUND = fill_mspy_symbols(MSPY_SYMBOLS + MSPY_OPTIONAL_SYMBOLS)
MSPY_MISSING = [name for name in MSPY_SYMBOLS if name not in globals()]
HAS_BENTLEY = not MSPY_MISSING
_HAS_BENTLEY = HAS_BENTLEY  # 兼容旧名


# ---------------------------------------------------------------------------
# 属性清单：key → (EC 属性名, 中文名)
# ---------------------------------------------------------------------------

# 文本类属性（直接取字符串）。
TEXT_PROPERTIES = (
    ('linenumber', 'LINENUMBER', '管线号'),
    ('name', 'NAME', '名称 / 位号'),
    ('component_name', 'COMPONENT_NAME', '元件名称'),
    ('nominal_size', 'NOMINAL_SIZE', '公称尺寸（文本）'),
    ('specification', 'SPECIFICATION', '管道等级 / 规格'),
    ('material', 'MATERIAL', '材质'),
    ('material_mark', 'MATERIAL_MARK', '材质代号'),
    ('grade', 'GRADE', '等级'),
    ('insulation_material', 'INSULATION', '保温材料'),
    ('pipe_flange_type', 'PIPE_FLANGE_TYPE', '法兰型式'),
    ('shop_field', 'SHOP_FIELD', '车间 / 现场'),
    ('spool_id', 'SPOOL_ID', '管段号'),
)

# 长度类属性（数值，需要按标定出的单位换算到 mm）。
LENGTH_PROPERTIES = (
    ('nominal_diameter', 'NOMINAL_DIAMETER', '公称直径'),
    ('nominal_diameter_run_end', 'NOMINAL_DIAMETER_RUN_END',
     '公称直径（端部）'),
    ('outside_diameter', 'OUTSIDE_DIAMETER', '外径'),
    ('wall_thickness', 'WALL_THICKNESS', '壁厚'),
    ('insulation_thickness', 'INSULATION_THICKNESS', '保温厚度'),
    ('length', 'LENGTH', '长度（属性）'),
    ('elevation', 'ELEVATION', '标高（属性）'),
)

# 报告里长度类属性的展示顺序（与面板表格一致）。
LENGTH_ORDER = ('nominal_diameter', 'outside_diameter', 'wall_thickness',
                'insulation_thickness', 'length')

TEXT_ORDER = ('linenumber', 'name', 'component_name', 'nominal_size',
              'specification', 'material', 'grade', 'insulation_material',
              'material_mark', 'pipe_flange_type', 'shop_field', 'spool_id')


# ---------------------------------------------------------------------------
# 单位标定
# ---------------------------------------------------------------------------

SCALE_MM = 1.0
SCALE_M = 1000.0
UNIT_OPTIONS = (
    ('auto', '自动识别'),
    ('mm', '毫米'),
    ('m', '米'),
)
# 标定时允许的相对误差：几何长度与属性长度本应一致，偏差过大说明标定不可信。
CALIBRATION_TOLERANCE = 0.10


def detect_length_scale(raw_value, reference_mm):
    """用「属性长度 ↔ 几何长度」标定属性数值的存储单位。

    ``raw_value`` 为 EC 属性的原始数值，``reference_mm`` 为同一段管的几何长度
    （mm，由曲线算出，永远可信）。返回 ``{'scale', 'label', 'error',
    'source'}``；两种候选单位都对不上（相对误差 > 10%）时返回 ``None``，
    调用方应改用 :func:`guess_length_scale`。
    """
    try:
        raw = float(raw_value)
        reference = float(reference_mm)
    except (TypeError, ValueError):
        return None
    if raw == 0.0 or reference <= 0.0:
        return None
    best = None
    for scale, label in ((SCALE_MM, '毫米'), (SCALE_M, '米')):
        error = abs(raw * scale - reference) / reference
        if best is None or error < best[2]:
            best = (scale, label, error)
    if best is None or best[2] > CALIBRATION_TOLERANCE:
        return None
    return {'scale': best[0], 'label': best[1], 'error': best[2],
            'source': 'calibrated'}


def guess_length_scale(raw_value):
    """标定不成立时的兜底规则：绝对值 ≥ 1 视为毫米，否则视为米。

    该规则对管径 / 壁厚 / 保温厚度都成立（工程上这些值不会小于 1 mm），
    但对"用米存储的 DN1000 以上大管"会误判，因此返回值里 ``source``
    为 ``'heuristic'``，报告需据此提示用户手动指定单位。
    """
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return {'scale': SCALE_MM, 'label': '毫米', 'source': 'default'}
    if value != 0.0 and abs(value) < 1.0:
        return {'scale': SCALE_M, 'label': '米', 'source': 'heuristic'}
    return {'scale': SCALE_MM, 'label': '毫米', 'source': 'default'}


def resolve_length_unit(raw_length, geometric_length_mm, override=None):
    """确定本元素长度类属性的换算单位。

    ``override`` 取 ``'auto'`` / ``None`` 时先标定；``'mm'`` / ``'m'`` 为
    面板上的手动指定，直接采用。返回 ``{'scale', 'label', 'source',
    'warning'}``，``warning`` 为需要展示给用户的提示（没有则为 ``None``）。
    """
    if override == 'mm':
        return {'scale': SCALE_MM, 'label': '毫米', 'source': 'manual',
                'warning': None}
    if override == 'm':
        return {'scale': SCALE_M, 'label': '米', 'source': 'manual',
                'warning': None}
    calibrated = detect_length_scale(raw_length, geometric_length_mm)
    if calibrated is not None:
        calibrated['warning'] = None
        return calibrated
    guessed = guess_length_scale(raw_length)
    if guessed['source'] == 'heuristic':
        guessed['warning'] = (
            '无法用几何长度标定属性单位（属性长度与几何长度对不上），'
            '已按"数值 < 1 视为米"兜底，请在「属性单位」里手动确认。')
    elif raw_length in (None, 0):
        guessed['warning'] = '该元件没有可用的长度属性值，无法标定属性单位。'
    else:
        guessed['warning'] = None
    return guessed


def to_mm(raw_value, scale):
    """把属性原始数值按单位比例换算成 mm；无值 / nan 时返回 ``None``。"""
    if raw_value is None:
        return None
    try:
        return _finite_or_none(float(raw_value) * float(scale))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 由外径反查公称直径（用于交叉校核读到的外径是否合理）
# ---------------------------------------------------------------------------

# 常用钢管外径系列（ASME B36.10M / GB/T 9711 常用值），DN → 外径 mm。
DN_OD_TABLE = (
    (15, 21.3), (20, 26.9), (25, 33.4), (32, 42.2), (40, 48.3),
    (50, 60.3), (65, 73.0), (80, 88.9), (90, 101.6), (100, 114.3),
    (125, 141.3), (150, 168.3), (200, 219.1), (250, 273.0),
    (300, 323.9), (350, 355.6), (400, 406.4), (450, 457.2),
    (500, 508.0), (550, 558.8), (600, 609.6), (650, 660.0),
    (700, 711.0), (750, 762.0), (800, 813.0), (850, 864.0),
    (900, 914.0), (1000, 1016.0), (1100, 1118.0), (1200, 1219.0),
)

# 反查允许的相对误差：外径系列的间隔比 3% 大，超过 3% 说明不是标准管径。
DN_MATCH_TOLERANCE = 0.03


def nearest_dn(od_mm, tolerance=DN_MATCH_TOLERANCE):
    """由外径反查最接近的公称直径。

    返回 ``{'dn', 'od_mm', 'error', 'text'}``（``error`` 为相对误差）；
    超出容差（默认 3%）时返回 ``None``，表示不是标准系列外径。
    """
    try:
        od = float(od_mm)
    except (TypeError, ValueError):
        return None
    if od <= 0.0:
        return None
    best = None
    for dn, table_od in DN_OD_TABLE:
        error = abs(table_od - od) / table_od
        if best is None or error < best[2]:
            best = (dn, table_od, error)
    if best is None or best[2] > tolerance:
        return None
    return {'dn': best[0], 'od_mm': best[1], 'error': best[2],
            'text': 'DN%d（外径 %.1f mm）' % (best[0], best[1])}


# ---------------------------------------------------------------------------
# 元素范围（包围盒）：单元格（Cell）类管道没有中心线曲线时的替代来源
# ---------------------------------------------------------------------------

# 元素级实例（DgnElementSchema）上的范围属性名。
RANGE_LOW_NAME = 'RangeLow'
RANGE_HIGH_NAME = 'RangeHigh'
RANGE_WANTED_NAMES = (RANGE_LOW_NAME, RANGE_HIGH_NAME)

_NUMBER_UNIT_RE = re.compile(
    r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([a-zA-Z]{0,3})')
# 顺序要紧：先匹配 mm 再匹配 m，否则 "mm" 会被当成 "m"。
_LENGTH_UNITS = (('mm', 1.0), ('cm', 10.0), ('km', 1000000.0),
                 ('m', 1000.0), ('in', 25.4), ('ft', 304.8), ('yd', 914.4))


def _unit_scale(unit):
    """单位字母 → 换算到 mm 的比例；不认识返回 ``None``。"""
    for suffix, scale in _LENGTH_UNITS:
        if unit == suffix:
            return scale
    return None


def detect_text_unit_scale(text):
    """从"数值 + 单位"文本里识别单位，返回换算到 mm 的比例。

    只认**紧跟在数字后面**的单位字母，避免把单词里的字母当成单位
    （例如把 "unknown" 里的 m 当成米）。识别不出时按项目主单位（通常 mm）处理。
    """
    for match in _NUMBER_UNIT_RE.finditer(str(text)):
        scale = _unit_scale(match.group(2).lower())
        if scale is not None:
            return scale
    return 1.0


def parse_length_values(text):
    """解析 ``"1715.7mm, 1376.5mm, -134.1mm"`` 这类文本 → mm 数值列表。

    元素范围属性是以"数值 + 单位后缀"的文本给出的（单位随项目主单位变化），
    所以连单位一起识别并换算；个别分量没带单位时，用整串识别出的单位兜底。
    """
    if not text:
        return []
    fallback = detect_text_unit_scale(text)
    values = []
    for match in _NUMBER_UNIT_RE.finditer(str(text)):
        scale = _unit_scale(match.group(2).lower())
        if scale is None:
            scale = fallback
        try:
            values.append(float(match.group(1)) * scale)
        except ValueError:
            continue
    return values


def build_range_info(low_text, high_text):
    """由 RangeLow / RangeHigh 文本生成包围盒信息（mm）。

    返回 ``{'low_mm', 'high_mm', 'center_mm', 'span_mm', 'max_span_mm'}``；
    解析不出三个分量时返回 ``None``。
    """
    low = parse_length_values(low_text)
    high = parse_length_values(high_text)
    if len(low) < 3 or len(high) < 3:
        return None
    low, high = low[:3], high[:3]
    span = tuple(abs(high[index] - low[index]) for index in range(3))
    return {
        'low_mm': tuple(low),
        'high_mm': tuple(high),
        'center_mm': tuple((low[index] + high[index]) / 2.0
                           for index in range(3)),
        'span_mm': span,
        'max_span_mm': max(span),
    }


# ---------------------------------------------------------------------------
# 几何：轴线、中心线标高、走向
# ---------------------------------------------------------------------------

# 走向判定容差：竖直分量占比 ≤ 2% 记为水平，≥ 98% 记为竖直。
HORIZONTAL_RATIO = 0.02
VERTICAL_RATIO = 0.98


def active_dgn_model():
    """取当前活动 DGN 模型。

    两种写法在不同版本上都可能是"标准"的：本仓库其它插件多用
    ``ISessionMgr.GetActiveDgnModel()``，官方示例 ``ECDumpUtility`` 用
    ``ISessionMgr.ActiveDgnModelRef.GetDgnModel()``。这里依次尝试。
    """
    try:
        return ISessionMgr.GetActiveDgnModel()
    except Exception:
        pass
    try:
        return ISessionMgr.ActiveDgnModelRef.GetDgnModel()
    except Exception:
        pass
    return None


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = active_dgn_model()
    if dgn_model is None:
        raise RuntimeError('取不到活动 DGN 模型（ISessionMgr 不可用）。')
    return dgn_model.GetModelInfo().GetUorPerStorage()


def _point_to_mm(point, uor_per_mm):
    if point is None:
        return None
    return (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)


def _distance_mm(point_a, point_b):
    return math.sqrt(sum((point_b[index] - point_a[index]) ** 2
                         for index in range(3)))


def classify_orientation(start_mm, end_mm):
    """按两端高差判定走向，返回 ``(走向文字, 坡度百分比)``。

    坡度 = 高差 / 水平投影 × 100%；竖直管无水平投影，坡度记 ``None``。
    """
    if start_mm is None or end_mm is None:
        return '未知', None
    dx = end_mm[0] - start_mm[0]
    dy = end_mm[1] - start_mm[1]
    dz = end_mm[2] - start_mm[2]
    horizontal = math.hypot(dx, dy)
    length = math.hypot(horizontal, dz)
    if length <= 0.0:
        return '零长度', 0.0
    vertical_ratio = abs(dz) / length
    if vertical_ratio <= HORIZONTAL_RATIO:
        return '水平', 0.0
    if vertical_ratio >= VERTICAL_RATIO:
        return '竖直', None
    slope = dz / horizontal * 100.0 if horizontal > 0.0 else None
    return '倾斜', slope


def _point_of(obj, name):
    """取对象上的点成员：兼容"属性"与"方法"两种写法。

    同一族几何类在不同版本里写法不一致——本仓库里 ``LineSegment3d.StartPoint``
    是不带括号的属性，而别处又可能是方法。两种都试，失败返回 ``None``。
    """
    try:
        value = getattr(obj, name)
    except Exception:
        return None
    if not callable(value):
        return value
    try:
        return value()
    except Exception:
        return None


def _line_piece(primitive):
    """直线段 → ``(起点, 终点)``；非直线返回 ``None``。"""
    segment = primitive.GetLine()
    if segment is None:
        return None
    return segment.StartPoint, segment.EndPoint


def _collect_pieces(curve_vector, pieces):
    """把曲线路径拆成折线控制点序列，逐个追加到 ``pieces``。

    每段是点列 ``[p0, p1, ...]``；圆弧按弦近似（只用于取端点与走向，
    真正的弧长由 :func:`_curve_length_mm` 单独处理）。
    """
    for primitive in curve_vector:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
            piece = _line_piece(primitive)
            if piece is not None:
                pieces.append([piece[0], piece[1]])
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
            points = list(primitive.GetLineString())
            if len(points) >= 2:
                pieces.append(points)
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Arc:
            arc = primitive.GetArc()
            if arc is None:
                continue
            start = _point_of(arc, 'StartPoint')
            end = _point_of(arc, 'EndPoint')
            if start is not None and end is not None:
                pieces.append([start, end])
        elif (primitive_type
              == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector):
            child = primitive.GetChildCurveVector()
            if child is not None:
                _collect_pieces(child, pieces)


def extract_axis_geometry(element_handle):
    """从元素曲线提取管道轴线几何。

    返回 ``{'start_mm', 'end_mm', 'length_mm', 'centerline_z_mm',
    'z_span_mm', 'orientation', 'slope_percent', 'length_confidence',
    'is_open_path'}``：起终点与中心线标高均为 mm；``length_confidence`` 为
    ``'high'`` 时长度由曲线精确求出（直线 / 折线），``'low'`` 表示含圆弧等
    只能取端点；``is_open_path`` 为 ``False`` 说明这是闭合轮廓，
    起终点不是管道中心线端点，调用方必须提示用户。
    """
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None:
        raise ValueError('所选元素没有可读取的曲线几何。')
    is_open_path = True
    try:
        is_open_path = bool(curve.IsOpenPath())
    except Exception:
        is_open_path = True
    pieces = []
    _collect_pieces(curve, pieces)
    if not pieces:
        raise ValueError('所选元素没有可读取的直线/折线/圆弧段。')

    start_point = pieces[0][0]
    end_point = pieces[-1][-1]
    start_mm = _point_to_mm(start_point, uor_per_mm)
    end_mm = _point_to_mm(end_point, uor_per_mm)

    length_mm, confidence = _curve_length_mm(curve, uor_per_mm)
    if length_mm is None:
        length_mm, confidence = _polyline_length_mm(pieces, uor_per_mm), 'low'

    orientation, slope_percent = classify_orientation(start_mm, end_mm)
    return {
        'start_mm': start_mm,
        'end_mm': end_mm,
        'length_mm': length_mm,
        'centerline_z_mm': start_mm[2] if start_mm else None,
        'z_span_mm': (abs(end_mm[2] - start_mm[2])
                      if (start_mm and end_mm) else None),
        'orientation': orientation,
        'slope_percent': slope_percent,
        'length_confidence': confidence,
        'is_open_path': is_open_path,
    }


def _polyline_length_mm(pieces, uor_per_mm):
    total = 0.0
    for piece in pieces:
        for index in range(len(piece) - 1):
            start = _point_to_mm(piece[index], uor_per_mm)
            end = _point_to_mm(piece[index + 1], uor_per_mm)
            total += _distance_mm(start, end)
    return total


def _curve_length_mm(curve, uor_per_mm):
    """优先取曲线自身长度（含圆弧真弧长）。

    长度 API 在不同 MicroStation 版本上名字不一，这里逐个尝试；都不可用时
    返回 ``(None, 'low')`` 由调用方按折线近似。
    """
    for name in ('Length', 'GetLength'):
        getter = getattr(curve, name, None)
        if not callable(getter):
            continue
        try:
            length = float(getter())
        except Exception:
            continue
        if length > 0.0:
            return length / uor_per_mm, 'high'
    return None, 'low'


# ---------------------------------------------------------------------------
# EC 实例读取
# ---------------------------------------------------------------------------

# 管道元件的类名关键字：这些类才带 NOMINAL_DIAMETER / OUTSIDE_DIAMETER 等。
PIPING_CLASS_HINTS = (
    'PIPE', 'ELBOW', 'TEE', 'REDUCER', 'FLANGE', 'VALVE', 'GASKET',
    'COUPLING', 'NIPPLE', 'BEND', 'CAP', 'PLUG', 'UNION', 'CROSS',
    'ADAPTER', 'HUB', 'BUSHING', 'FERRULE', 'RETURN', 'STUB', 'NOZZLE',
    'INSTRUMENT', 'SUPPORT', 'CLAMP', 'HANGER', 'GUIDE', 'ANCHOR',
)

# 判断"这个实例是不是管道元件实例"用的探针属性：能读到其一即加分。
NUMBER_PROBES = ('OUTSIDE_DIAMETER', 'NOMINAL_DIAMETER')
TEXT_PROBES = ('LINENUMBER', 'SPECIFICATION')


def _search_all_flag():
    """EC 查询标志：不同版本导出位置不同，逐个尝试。"""
    try:
        return ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses
    except Exception:
        return eECQUERY_PROCESS_SearchAllClasses


def _safe_instance_id(instance):
    """取实例 ID（只是个字符串，在遍历内取出是安全的）。"""
    try:
        return str(instance.GetInstanceId())
    except Exception:
        return None


def collect_instance_records(element_handle, log=None):
    """查询元素上的 EC 实例，并把每个实例读成**纯 Python 记录**。

    **整个"查询 → 遍历 → 取值"都在这一个函数里完成，且直接遍历
    ``collection[0]``，不做 ``list()`` 物化。** 这一点是踩了多次崩溃才定下来的：

    * ``FindInstances`` 返回的实例只在**这次遍历过程中**有效；
    * 一旦把实例带出遍历（例如 ``list(collection[0])`` 存起来、或返回给调用方
      稍后再用），再访问 ``GetClass()`` / 枚举属性就会让 OPM **访问违例、进程
      直接消失**（catch 不到，日志都来不及写）；
    * Bentley 官方示例 ``ECDumpUtility`` 以及本仓库 ``支吊架公共库`` 都是
      "在原地遍历 `[0]`"，从不变着法子把实例带出去。

    返回的记录每项形如 ``{'index', 'schema', 'class', 'available',
    'rangeTexts', 'values', 'raw'}``，全部是纯 Python 数据——出了本函数就再没有
    任何 Bentley 对象，后续挑选 / 换算是纯计算，不可能再因此崩溃。
    """
    def note(message):
        if log is not None:
            try:
                log(message)
            except Exception:
                pass

    records = []
    try:
        manager = DgnECManager.GetManager()
        query = ECQuery.CreateQuery(_search_all_flag())
        scope = FindInstancesScope.CreateScope(
            element_handle, FindInstancesScopeOption(DgnECHostType.eElement))
        collection = manager.FindInstances(scope, query)
    except Exception as error:
        note('EC 实例查询失败：%s' % error)
        return records
    if collection is None:
        note('EC 实例查询返回空')
        return records

    for index, instance in enumerate(collection[0], start=1):
        # 每个实例的全部读取都留在本次遍历内完成，实例不外传。
        try:
            note('候选实例 %d：读取类信息' % index)
            schema_name, class_name = _instance_class(instance)
            note('候选实例 %d：%s.%s，开始枚举属性'
                 % (index, schema_name or '?', class_name or '?'))
            record = _read_instance_record(instance, index, schema_name,
                                          class_name, note)
            note('候选实例 %d：%s.%s，属性 %d 个'
                 % (index, schema_name or '?', class_name or '?',
                    len(record['available'])))
        except Exception as error:
            note('候选实例 %d 读取失败，跳过：%s' % (index, error))
            continue
        records.append(record)
    return records


def _read_instance_record(instance, index, schema_name, class_name, note):
    """在遍历内部把一个实例读成纯 Python 记录。"""
    available, range_texts = scan_instance(instance, wanted=RANGE_WANTED_NAMES)
    record = {
        'index': index,
        'schema': schema_name,
        'class': class_name,
        'instanceId': _safe_instance_id(instance),
        'available': available,
        'rangeTexts': range_texts,
        'values': {},
        'raw': {},
    }
    # 只读**实际存在**的属性：拿不存在的名字去问 Bentley 会让 OPM 崩溃。
    note('候选实例 %d：读取文本属性' % index)
    for key, property_name, _label in TEXT_PROPERTIES:
        if property_name in available:
            record['values'][key] = read_text(instance, property_name)
    note('候选实例 %d：读取长度属性' % index)
    for key, property_name, _label in LENGTH_PROPERTIES:
        if property_name in available:
            record['raw'][key] = read_number(instance, property_name)
    # 公称直径优先取 NOMINAL_DIAMETER，缺失时退回端部值。
    if (record['raw'].get('nominal_diameter') is None
            and 'NOMINAL_DIAMETER_RUN_END' in available):
        record['raw']['nominal_diameter'] = record['raw'].get(
            'nominal_diameter_run_end')
    return record


def dump_instances(element_handle, log=None):
    """遍历元素上的 EC 实例并**在遍历内**把全部属性转成文本行（供「全部属性」）。

    同样不物化实例、不带出遍历。
    """
    lines = []
    try:
        manager = DgnECManager.GetManager()
        query = ECQuery.CreateQuery(_search_all_flag())
        scope = FindInstancesScope.CreateScope(
            element_handle, FindInstancesScopeOption(DgnECHostType.eElement))
        collection = manager.FindInstances(scope, query)
    except Exception as error:
        return ['EC 实例查询失败：%s' % error]
    if collection is None:
        return ['该元素上没有 EC 实例。']
    count = 0
    for index, instance in enumerate(collection[0], start=1):
        count += 1
        schema_name, class_name = _instance_class(instance)
        lines.append('=' * 64)
        lines.append('实例 %d：%s.%s' % (index, schema_name, class_name))
        lines.append('=' * 64)
        try:
            for name, value in dump_instance_properties(instance):
                lines.append('%s = %s' % (name, value))
        except Exception as error:
            lines.append('<该实例属性展开失败：%s>' % error)
        lines.append('')
    if not count:
        lines.append('该元素上没有 EC 实例。')
    return lines


def _instance_class(instance):
    try:
        ec_class = instance.GetClass()
        return (str(ec_class.GetSchema().GetName()),
                str(ec_class.GetName()))
    except Exception:
        return '', ''


def format_property_text(instance, access_string, property_value):
    """取属性值的**文本形式**（与官方 ``ECDumpUtility`` 同法）。

    用于元素范围这类"数值 + 单位后缀"的属性——它们的文本形式形如
    ``"1715.7mm, 1376.5mm, -134.1mm"``，比按数值接口取更稳妥。
    """
    try:
        buffer = WString()
        if (instance.GetValueAsString(buffer, access_string, False, 0)
                == BentleyStatus.eSUCCESS):
            text = str(buffer).strip()
            if text:
                return text
    except Exception:
        pass
    try:
        value = property_value.GetValue()
        if value is None:
            return ''
        return str(value.ToString()).strip()
    except Exception:
        return ''


def scan_instance(instance, wanted=()):
    """一次遍历实例，返回 ``(属性名集合, {关心的属性名: 文本值})``。

    **必须逐个用枚举出来的真实属性名，不能拿名字去试探**：查询实例上不存在的
    属性会让 OPM 直接崩溃。本函数只在 :func:`collect_instance_records` 的
    **遍历内部**被调用——实例一旦离开那次遍历就会失效。
    """
    names = set()
    texts = {}
    wanted = set(wanted or ())
    try:
        collection = ECValuesCollection.Create(instance)
    except Exception:
        # 这个实例枚举不出来 → 当作不可用，交由调用方按得分跳过（不是致命错误）。
        return names, texts
    for property_value in collection:
        try:
            accessor = property_value.GetValueAccessor()
            access_string = str(accessor.GetManagedAccessString())
        except Exception:
            continue
        if not access_string:
            continue
        names.add(access_string)
        if access_string in wanted:
            texts[access_string] = format_property_text(
                instance, access_string, property_value)
    return names, texts


def instance_property_names(instance):
    """枚举实例上**实际存在**的属性名（顶层）。

    直接拿一个可能不存在的属性名去问 Bentley，在 OPM 里会让整个程序崩掉
    （不是返回错误码），所以一律先枚举、再按名字取值——官方 ``ECDumpUtility``
    就是这个做法。
    """
    return scan_instance(instance)[0]


def _score_instance(available, schema_name, class_name):
    """给实例打分（纯函数，可单测，不碰 Bentley 对象）。

    **只有 ``OpenPlant*`` schema 的实例才有资格**：OPM 的管道数据都在
    ``OpenPlant_3D*`` 里。本仓库支吊架插件写的 ItemType 实例库名是
    ``PipeSupportComponents``、类名也以 ``Pipe`` 开头，光看类名会把支吊架的
    设计长度当成管径，所以资格一律由 schema 决定。
    """
    if not schema_name.startswith('OpenPlant'):
        return 0
    score = 2
    upper_name = class_name.upper()
    if upper_name.startswith('PIPE') or any(
            hint in upper_name for hint in PIPING_CLASS_HINTS):
        score += 3
    if any(name in available for name in NUMBER_PROBES):
        score += 2
    elif any(name in available for name in TEXT_PROBES):
        score += 1
    return score


def pick_piping_record(records, log=None):
    """从实例记录里挑出管道元件记录（挑不到返回 ``None``）。

    纯函数：只吃 :func:`collect_instance_records` 产出的纯 Python 记录，
    不再碰任何 Bentley 对象。

    同一个元素上往往既有管道的 OpenPlant 实例，也有本插件自己写的 ItemType
    实例（库 ``PipeSupportComponents``）。这里只认 ``OpenPlant*`` schema 的
    记录，其余（ItemType、标注等）一律不参与。
    """
    def note(message):
        if log is not None:
            try:
                log(message)
            except Exception:
                pass

    best = None
    for record in records:
        score = _score_instance(record['available'], record['schema'],
                                record['class'])
        note('候选实例 %d：%s.%s，得分 %d'
             % (record['index'], record['schema'] or '?',
                record['class'] or '?', score))
        if score <= 0:
            continue
        if best is None or score > best['score']:
            best = dict(record)
            best['score'] = score
    return best


def range_from_records(records, log=None):
    """从实例记录里取元素范围（RangeLow / RangeHigh）→ 包围盒信息。

    单元格（Cell）类管道没有中心线曲线，元素范围是**唯一**能给出中心线标高
    与长度参考的来源。纯函数，不再碰 Bentley 对象。
    """
    for record in records:
        texts = record.get('rangeTexts') or {}
        low_text = texts.get(RANGE_LOW_NAME)
        high_text = texts.get(RANGE_HIGH_NAME)
        if not low_text or not high_text:
            continue
        info = build_range_info(low_text, high_text)
        if info is None:
            if log is not None:
                log('实例 %d 的范围文本解析失败：%r / %r'
                    % (record['index'], low_text, high_text))
            continue
        info['source'] = '实例 %d（%s）' % (record['index'],
                                          record['class'] or '?')
        return info
    return None


def read_number(instance, property_name):
    """读数值属性；值为空或非数值时返回 ``None``（不抛异常）。

    **调用方必须先确认该属性确实存在**（用 :func:`instance_property_names`
    的结果判断）——拿不存在的属性名去问 Bentley 会让 OPM 直接崩溃。

    注意：对**字符串**属性调用 ``GetDouble()`` 不会报错，而是返回 ``nan``
    （实测：``LINENUMBER`` → nan）。所以这里把 nan / inf 一律当作"没有值"，
    免得界面出现 "nan mm" 这种东西。
    """
    try:
        ec_value = ECValue()
        status = instance.GetValue(ec_value, property_name)
        if status != ECObjectsStatus.eECOBJECTS_STATUS_Success:
            return None
        if ec_value.IsNull():
            return None
    except Exception:
        return None
    for getter in ('GetDouble', 'GetInteger'):
        try:
            return _finite_or_none(float(getattr(ec_value, getter)()))
        except Exception:
            continue
    return None


def _finite_or_none(value):
    """把 nan / inf 归一成 ``None``。"""
    if value is None:
        return None
    try:
        if math.isnan(value) or math.isinf(value):
            return None
    except (TypeError, ValueError):
        return None
    return value


def read_text(instance, property_name):
    """读文本属性；属性不存在或为空时返回 ``None``（不抛异常）。"""
    try:
        ec_value = ECValue()
        status = instance.GetValue(ec_value, property_name)
        if status != ECObjectsStatus.eECOBJECTS_STATUS_Success:
            return None
        if ec_value.IsNull():
            return None
        text = str(ec_value.GetString()).strip()
        return text or None
    except Exception:
        return None


def dump_instance_properties(instance):
    """导出一个实例的全部属性（名称 → 字符串值），供「全部属性」查看。

    与 Bentley 官方示例 ``ECDumpUtility`` 同法：用 ``ECValuesCollection``
    递归展开，结构体 / 数组属性一并展开子值。
    """
    rows = []
    try:
        collection = ECValuesCollection.Create(instance)
    except Exception:
        return rows
    _walk_values(instance, collection, rows)
    return rows


def _walk_values(instance, collection, rows):
    for property_value in collection:
        access_string = ''
        try:
            accessor = property_value.GetValueAccessor()
            access_string = str(accessor.GetManagedAccessString())
        except Exception:
            continue
        text = ''
        try:
            value = property_value.GetValue()
            if value is None:
                text = ''
            elif value.IsStruct() or value.IsArray():
                text = '<结构 / 数组>'
            else:
                buffer = WString()
                if (instance.GetValueAsString(buffer, access_string, False, 0)
                        == BentleyStatus.eSUCCESS):
                    text = str(buffer)
                else:
                    text = str(value.ToString())
        except Exception:
            text = '<不可读>'
        rows.append((access_string, text))
        try:
            if property_value.HasChildValues():
                _walk_values(instance, property_value.GetChildValues(), rows)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# 汇总：点取一次 → 一份报告
# ---------------------------------------------------------------------------
#
# 设计要点：``collect_pipe_info`` 只返回**纯 Python 快照**，不保留任何 Bentley
# 对象（元素句柄 / EC 实例）。原因是 Bentley 句柄只在工具回调期间有效，出了
# 回调再使用会失效甚至让 OPM 崩溃；面板后续的"切换属性单位"因此改为在快照上
# 纯计算（:func:`reapply_unit`），"全部属性"则用元素 ID 重新取句柄
# （:func:`dump_element`）。


def collect_pipe_info(element_handle, unit_override=None, log=None):
    """读取一个元素的管道信息，返回纯 Python 报告快照。

    ``unit_override`` 取 ``'auto'`` / ``'mm'`` / ``'m'``；``log`` 为可选的
    日志回调（``fn(str)``），用于记录读取进度——一旦某步让 OPM 崩溃，
    调试日志的最后一行就是出问题的位置。

    快照含 ``elementId`` / ``ec`` / ``unit`` / ``raw`` / ``values`` /
    ``geometry`` / ``derived`` / ``warnings`` / ``notes`` /
    ``baseWarnings``；任何一项读不到都不报错，缺项即为 ``None``。

    ``warnings`` 只放**真问题**（几何读不到、没有管道实例、单位无法标定、
    公称直径与外径互不相符），面板会以醒目颜色提示；``notes`` 放信息性说明
    （如"属性单位已按几何长度标定为米"），不当作错误。
    """
    def note(message):
        if log is not None:
            try:
                log(message)
            except Exception:
                pass

    element_id = read_element_id(element_handle)
    note('读取开始：元素 ID %s' % element_id)

    snapshot = {
        'elementId': element_id,
        'ec': {'schema': None, 'class': None, 'instanceId': None,
               'found': False},
        'unit': {'scale': SCALE_MM, 'label': '毫米', 'source': 'default',
                 'warning': None},
        'raw': {},
        'values': {},
        'geometry': None,
        'bbox': None,
        'derived': {},
        'warnings': [],
        'notes': [],
        'baseWarnings': [],
    }
    base_warnings = snapshot['baseWarnings']

    try:
        snapshot['geometry'] = extract_axis_geometry(element_handle)
        note('几何读取完成：中心线标高 %s mm'
             % _round_or_none(snapshot['geometry'].get('centerline_z_mm')))
        if snapshot['geometry'].get('is_open_path') is False:
            base_warnings.append(
                '所选元素的曲线是**闭合轮廓**（不是管道中心线）：下面的起点 / '
                '终点 / 中心线标高按轮廓首点计算，不能当作管道中心线使用。')
            note('几何为闭合路径，轴线信息不可用')
    except Exception as error:
        base_warnings.append('几何读取失败：%s' % error)
        note('几何读取失败：%s' % error)

    # 一次遍历把实例读成**纯 Python 记录**：实例绝不带出遍历，也不物化
    # （带出去 / list() 物化后再用会让 OPM 访问违例崩溃）。
    records = []
    note('开始查询并读取 EC 实例')
    try:
        records = collect_instance_records(element_handle, log=note)
        note('EC 实例读取完成：共 %d 条记录' % len(records))
    except Exception as error:
        base_warnings.append('EC 实例查询失败：%s' % error)
        note('EC 实例查询失败：%s' % error)

    picked = pick_piping_record(records, log=note) if records else None
    if picked is None:
        base_warnings.append(
            '该元素上没有找到 OpenPlant 管道实例（PIPING_COMPONENT / PIPE）'
            '——它可能只是普通 MicroStation 图元，或属性挂在父单元上。'
            '下面只有几何信息可用。')
        note('未找到管道 EC 实例')
    else:
        snapshot['ec'] = {'schema': picked['schema'], 'class': picked['class'],
                          'instanceId': picked.get('instanceId'),
                          'found': True}
        snapshot['values'].update(picked['values'])
        snapshot['raw'].update(picked['raw'])
        note('选中实例：%s.%s（得分 %d）'
             % (picked['schema'], picked['class'], picked['score']))

    # 没有中心线曲线时（典型情况：管道是单元格 Cell），用元素范围兜底：
    # 它能给出包围盒中心（≈中心线位置）与最长边（≈管段长度）。
    if snapshot['geometry'] is None and records:
        note('尝试用元素范围（包围盒）兜底')
        snapshot['bbox'] = range_from_records(records, log=note)
        if snapshot['bbox'] is not None:
            note('包围盒：中心 %s，尺寸 %s'
                 % (_round_tuple(snapshot['bbox']['center_mm']),
                    _round_tuple(snapshot['bbox']['span_mm'])))

    _finalise_units(snapshot, unit_override)
    note('读取完成：单位按%s（%s）'
         % (snapshot['unit']['label'], snapshot['unit']['source']))
    return snapshot


def _round_tuple(values, digits=1):
    try:
        return tuple(round(float(value), digits) for value in values)
    except (TypeError, ValueError):
        return values


def read_element_id(element_handle):
    """取元素 ID（只读、不保留句柄）；取不到返回 ``None``。"""
    for getter in ('ElementId', 'GetElementId'):
        try:
            value = getattr(element_handle, getter)
        except Exception:
            continue
        try:
            return int(value() if callable(value) else value)
        except Exception:
            continue
    return None


def _round_or_none(value, digits=1):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def reference_length_mm(snapshot):
    """挑一个"几何量出来的长度"当单位标定基准。

    优先用曲线长度（最准）；单元格（Cell）类管道没有曲线，退而用元素范围
    （包围盒）的最长边——对直管段来说它就等于管段长度。
    """
    geometry = snapshot.get('geometry') or {}
    length = geometry.get('length_mm')
    if length:
        return length, '几何曲线'
    bbox = snapshot.get('bbox') or {}
    if bbox.get('max_span_mm'):
        return bbox['max_span_mm'], '元素范围（包围盒）最长边'
    return None, None


def _finalise_units(snapshot, unit_override):
    """在快照上算单位 / 换算长度 / 推算尺寸（纯 Python，可重复调用）。

    重复调用是幂等的：``warnings`` 每次都从 ``baseWarnings`` 重新展开，
    不会因切换单位而重复堆叠提示。
    """
    raw = snapshot.get('raw') or {}
    warnings = list(snapshot.get('baseWarnings') or [])
    notes = []
    snapshot['values'] = snapshot.get('values') or {}
    snapshot['warnings'] = warnings
    snapshot['notes'] = notes

    reference, reference_source = reference_length_mm(snapshot)
    unit = resolve_length_unit(raw.get('length'), reference, unit_override)
    snapshot['unit'] = unit
    if unit.get('warning'):
        warnings.append(unit['warning'])
    elif unit.get('source') == 'calibrated' and raw.get('length') is not None:
        notes.append(
            '属性单位按「属性长度 %.4g ↔ %s %.1f mm」标定为%s（误差 %.1f%%）。'
            % (raw['length'], reference_source or '参考长度', reference,
               unit['label'], unit['error'] * 100.0))

    scale = unit['scale']
    for key, _property_name, _label in LENGTH_PROPERTIES:
        snapshot['values'][key] = to_mm(raw.get(key), scale)

    snapshot['derived'] = {}
    snapshot['bbox_cross_note'] = None
    _fill_derived(snapshot, warnings)
    _fill_elevations(snapshot)
    _bbox_cross_check(snapshot)
    return snapshot


def effective_centerline_z(snapshot):
    """取"有效中心线标高"（mm）及其来源说明。

    优先用曲线轴线 Z（精确）；单元格（Cell）类管道没有曲线，退用包围盒中心 Z
    （近似）。取不到返回 ``(None, None)``。
    """
    geometry = snapshot.get('geometry') or {}
    if geometry.get('centerline_z_mm') is not None:
        return geometry['centerline_z_mm'], '曲线轴线'
    bbox = snapshot.get('bbox') or {}
    if bbox.get('center_mm'):
        return bbox['center_mm'][2], '包围盒中心（近似）'
    return None, None


def _fill_elevations(snapshot):
    """由中心线标高 + 外径 / 保温厚度推算管底标高与保温层底标高。

    管底标高 ＝ 中心线标高 − 外径/2；
    保温层底标高 ＝ 中心线标高 − 外径/2 − 保温厚度。
    这两个值是支吊架设计最直接的输入（管托坐在哪、保温层下皮在哪）。
    """
    derived = snapshot['derived']
    values = snapshot['values']
    centerline_z, source = effective_centerline_z(snapshot)
    derived['centerline_z_mm'] = centerline_z
    derived['centerline_z_source'] = source

    od_mm = values.get('outside_diameter')
    thickness_mm = values.get('insulation_thickness')
    if centerline_z is None or od_mm is None or od_mm <= 0:
        derived['pipe_bottom_z_mm'] = None
        derived['insulation_bottom_z_mm'] = None
        return
    half_od = od_mm / 2.0
    derived['pipe_bottom_z_mm'] = centerline_z - half_od
    if thickness_mm is None:
        derived['insulation_bottom_z_mm'] = None
    else:
        derived['insulation_bottom_z_mm'] = centerline_z - half_od - thickness_mm


def _bbox_cross_check(snapshot):
    """包围盒截面尺寸与「外径 + 2×保温厚度」吻合时，给一句**正向确认**。

    只在吻合时说话：弯头、阀门等元件的包围盒本来就不是圆截面，不吻合属正常，
    所以这里绝不报警，只用来增强"读到的外径 / 保温厚度可信"这个判断。
    """
    bbox = snapshot.get('bbox') or {}
    spans = sorted(bbox.get('span_mm') or ())
    target = (snapshot.get('derived') or {}).get('od_with_insulation_mm')
    if len(spans) != 3 or not target or target <= 0:
        return
    cross = spans[:2]  # 最小的两个跨度即截面方向
    if all(abs(value - target) / target <= 0.02 for value in cross):
        snapshot['bbox_cross_note'] = (
            '包围盒截面 %.1f × %.1f mm 与「外径 + 2×保温厚度」%.1f mm 吻合，'
            '说明读到的外径 / 保温厚度可信。' % (cross[0], cross[1], target))


def reapply_unit(snapshot, unit_override):
    """面板切换「属性单位」时用：只重算单位，不再访问元素。"""
    return _finalise_units(snapshot, unit_override)


def element_handle_by_id(element_id):
    """按元素 ID 重新取一个句柄（官方示例 ECDumpUtility 的做法）。

    用它而不用"记住旧句柄"：旧句柄在工具回调结束后已失效。
    """
    dgn_model = active_dgn_model()
    if dgn_model is None:
        raise RuntimeError('取不到活动 DGN 模型（ISessionMgr 不可用）。')
    handle = EditElementHandle(int(element_id), dgn_model)
    return handle if handle.IsValid() else None


def dump_element(element_id):
    """取该元素的**全部 EC 属性**文本（原样），供「全部属性」窗口。

    按 ID 重新取句柄（不缓存任何 Bentley 对象），再在**一次遍历内**把属性
    转成文本——实例不外传、不物化。
    """
    if element_id is None:
        return '当前没有可读取的元素。'
    try:
        handle = element_handle_by_id(element_id)
    except Exception as error:
        return '取元素句柄失败：%s' % error
    if handle is None:
        return '元素 ID %s 已失效（可能已被删除）。' % element_id
    return '\n'.join(dump_instances(handle))



def _fill_derived(report, warnings):
    """由外径 / 保温厚度推算常用尺寸，并交叉校核公称直径。"""
    values = report['values']
    derived = report['derived']
    od_mm = values.get('outside_diameter')
    thickness_mm = values.get('insulation_thickness')

    if od_mm is not None and thickness_mm is not None:
        derived['od_with_insulation_mm'] = od_mm + 2.0 * thickness_mm
        derived['insulation_outer_radius_mm'] = od_mm / 2.0 + thickness_mm
    else:
        derived['od_with_insulation_mm'] = None
        derived['insulation_outer_radius_mm'] = None

    matched = nearest_dn(od_mm)
    derived['dn_from_od'] = matched['dn'] if matched else None
    derived['dn_from_od_text'] = matched['text'] if matched else None
    if matched is None:
        if od_mm is not None:
            warnings.append(
                '外径 %.1f mm 不在常用钢管外径系列里，无法反查公称直径；'
                '请核对读到的外径单位是否选对。' % od_mm)
        derived['dn_consistent'] = None
        return

    nominal_mm = values.get('nominal_diameter')
    if nominal_mm is None or nominal_mm <= 0:
        derived['dn_consistent'] = None
        return
    error = abs(nominal_mm - matched['dn']) / matched['dn']
    derived['dn_consistent'] = error <= 0.02
    if not derived['dn_consistent']:
        warnings.append(
            '属性公称直径 %.1f 与外径 %.1f mm 反查出的 %s 不一致，'
            '请确认属性单位（当前按%s换算）。'
            % (nominal_mm, od_mm, matched['text'], report['unit']['label']))


# ---------------------------------------------------------------------------
# 报告排版（纯函数，供面板与单测共用）
# ---------------------------------------------------------------------------


def _fmt_mm(value, digits=1):
    if value is None:
        return '—'
    return '%.*f mm' % (digits, value)


def _fmt_xyz(point_mm):
    if point_mm is None:
        return '—'
    return '(%.1f, %.1f, %.1f)' % point_mm


def build_report_rows(info):
    """把报告字典排成面板表格行：``[(分组, 项目, 值, 备注), ...]``。"""
    rows = []
    ec = info.get('ec') or {}
    unit = info.get('unit') or {}
    values = info.get('values') or {}
    raw = info.get('raw') or {}
    geometry = info.get('geometry')
    derived = info.get('derived') or {}

    rows.append(('元素', '元素 ID', str(info.get('elementId') or '—'), ''))
    if ec.get('found'):
        rows.append(('元素', 'EC Schema', ec.get('schema') or '—', ''))
        rows.append(('元素', 'EC 类', ec.get('class') or '—', ''))
        rows.append(('元素', '实例 ID', ec.get('instanceId') or '—', ''))
    else:
        rows.append(('元素', 'EC 实例', '未找到管道实例', '仅有几何信息'))

    rows.append(('单位', '属性长度单位', unit.get('label') or '—',
                 _unit_source_text(unit)))

    for key in LENGTH_ORDER:
        label = _length_label(key)
        value_text = _fmt_mm(values.get(key))
        note = ''
        if raw.get(key) is not None:
            note = '原值 %.6g' % raw[key]
        rows.append(('管道属性', label, value_text, note))

    for key in TEXT_ORDER:
        text = values.get(key)
        if text:
            rows.append(('管道属性', _text_label(key), text, ''))

    if geometry is not None:
        rows.append(('几何', '中心线标高', _fmt_mm(geometry.get(
            'centerline_z_mm'), 1),
            '起点 Z' if geometry.get('z_span_mm') else ''))
        rows.append(('几何', '管段长度（几何）',
                     _fmt_mm(geometry.get('length_mm')),
                     '折线近似' if geometry.get('length_confidence') == 'low'
                     else '由曲线精确求得'))
        rows.append(('几何', '起点', _fmt_xyz(geometry.get('start_mm')), ''))
        rows.append(('几何', '终点', _fmt_xyz(geometry.get('end_mm')), ''))
        slope = geometry.get('slope_percent')
        rows.append(('几何', '走向', geometry.get('orientation') or '—',
                     ('坡度 %.2f%%' % slope) if slope else ''))
        if geometry.get('z_span_mm'):
            rows.append(('几何', '两端高差',
                         _fmt_mm(geometry.get('z_span_mm')), ''))
    elif info.get('bbox') is not None:
        # 单元格（Cell）类管道没有中心线曲线，用元素范围兜底。
        bbox = info['bbox']
        rows.append(('几何', '包围盒中心', _fmt_xyz(bbox.get('center_mm')),
                     '元素无中心线曲线，用元素范围兜底'))
        rows.append(('几何', '中心线标高（近似）',
                     _fmt_mm(bbox['center_mm'][2], 1),
                     '＝包围盒中心 Z'))
        rows.append(('几何', '包围盒尺寸', _fmt_xyz(bbox.get('span_mm')),
                     '最长边 ≈ 管段长度'))
        rows.append(('几何', '范围来源', bbox.get('source') or '—', ''))
    else:
        rows.append(('几何', '轴线几何', '读取失败', ''))

    # 由中心线标高推算的管底 / 保温层底标高（支吊架最直接的输入）。
    if derived.get('pipe_bottom_z_mm') is not None:
        rows.append(('几何', '管底标高',
                     _fmt_mm(derived['pipe_bottom_z_mm'], 1),
                     '中心线标高 − 外径/2'))
    if derived.get('insulation_bottom_z_mm') is not None:
        rows.append(('几何', '保温层底标高',
                     _fmt_mm(derived['insulation_bottom_z_mm'], 1),
                     '中心线标高 − 外径/2 − 保温厚度'))

    if info.get('bbox_cross_note'):
        rows.append(('推算', '截面尺寸校核', '一致',
                     info['bbox_cross_note']))

    rows.append(('推算', '保温后外径',
                 _fmt_mm(derived.get('od_with_insulation_mm')),
                 '外径 + 2×保温厚度'))
    rows.append(('推算', '保温层外半径',
                 _fmt_mm(derived.get('insulation_outer_radius_mm')),
                 '中心线 → 保温外皮'))
    rows.append(('推算', '由外径反查公称直径',
                 derived.get('dn_from_od_text') or '—',
                 _dn_consistent_text(derived.get('dn_consistent'))))
    return rows


def _length_label(key):
    for item_key, _property_name, label in LENGTH_PROPERTIES:
        if item_key == key:
            return label
    return key


def _text_label(key):
    for item_key, _property_name, label in TEXT_PROPERTIES:
        if item_key == key:
            return label
    return key


def _unit_source_text(unit):
    source = unit.get('source')
    if source == 'calibrated':
        return '由几何长度自动标定'
    if source == 'manual':
        return '面板手动指定'
    if source == 'heuristic':
        return '兜底规则判断，建议手动确认'
    return '默认按毫米'


def _dn_consistent_text(consistent):
    if consistent is True:
        return '与属性公称直径一致'
    if consistent is False:
        return '与属性公称直径不一致，请核对单位'
    return ''


def format_report_text(info):
    """把报告排成纯文本（用于日志与「全部属性」窗口的抬头）。"""
    lines = []
    for group, item, value, note in build_report_rows(info):
        suffix = '（%s）' % note if note else ''
        lines.append('[%s] %s：%s%s' % (group, item, value, suffix))
    for note in info.get('notes') or ():
        lines.append('[说明] %s' % note)
    for warning in info.get('warnings') or ():
        lines.append('[提示] %s' % warning)
    return '\n'.join(lines)
