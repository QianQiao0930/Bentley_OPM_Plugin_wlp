# -*- coding: utf-8 -*-
"""标准型 2 螺栓管夹（剪切建模）—— 点选管道或直线自动放置。

运行后**点选一根管道或一条直线段**，在**点击处**沿其轴线生成一组「标准型 2
螺栓管夹」。可连续点选（管道、直线可交替），右键退出（保留已生成模型）。

* 选中**管道**：读取其轴线、公称直径与保温厚度，DN 由公称直径自动查表 1；
* 选中**直线段**：以该直线为管轴，未读到管道属性时用脚本顶部 ``DN`` 兜底。

管夹依托轴线定位：本地 X 轴沿轴线，本地 Z 轴自动取竖直向上（无需手选角度）。
保温厚度按开关 ``ACCOMMODATE_INSULATION`` 决定是否放大内孔
（内孔 A' = A + 2×保温厚度）。

管道信息（轴线起终点 / 公称直径 / 保温厚度 / 走向坡度）取自 ``管道信息查询``
插件的读取库 ``pipe_placement_info``（对普通直线同样返回其轴线）。并遵循它的
一条铁律：**EC 读取不在工具回调里做**——点选只把「元素 ID + 点击点」入队，
真正的读取与建模由面板主循环在 ``PyCadInputQueue.PythonMainLoop()`` 返回之后
执行（实测回调内访问 EC 实例会让 OPM 崩溃）。

**输出全部在面板里**：生成结果与提示写入面板的「生成记录」，不再打印到
Python 控制台；异常只写调试日志文件（``模块/日志/``）。

G 列形如 "t x w"（板厚 x 板宽）：t 取 × 前的厚度值，w 取 × 后的值。

本阶段做管架本体的五步：
  1) 圆柱：以管道轴线为管轴，直径 = A + 2t，轴向长 = w；
  2) 长方体：与圆柱布尔并；厚度 = w（与圆柱一致），
     长度 = A + 2D + 2t（沿本地 Y），宽度 = C + 2t（沿本地 Z）；
  3) 剪切截面：直径 A 的圆 + 长度 A + 2t + 2D、宽度 C 的矩形（沿本地 Y/Z），
     沿轴向贯穿，从本体中减去，得到管夹状；
  4) 上下两对耳板开螺栓孔：孔心距中心 = B（沿本地 Y），孔径 = F 数字 + 2，
     沿本地 Z 贯穿两片耳板；
  5) 每个螺栓孔穿一套简化紧固件（螺杆 + 六角头 + 六角螺母，独立实体）；
  6) 整组依托管道轴线定位，绕轴角度自动对齐（本地 Z 竖直向上）。

DN100 例（表 1：A=117, B=84, C=20, D=50, F=M16, G=8 x 50）：
  圆柱 φ133（=117+2×8）、轴向长 50；长方体 233×36×50；
  剪切截面 = φ117 圆 + 233×20 矩形；螺栓孔 φ18（16+2），孔心 Y=±84；
  M16 螺栓：螺杆 φ16 贯穿，+Z 侧六角头（对边 24、高 10），
  -Z 侧六角螺母（对边 24、高 13），螺杆穿出 4。
"""

import importlib
import importlib.util
import math
import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEvent, QEventLoop, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                             QPlainTextEdit, QVBoxLayout, QWidget)


# ---------------------------------------------------------------------------
# 复用 管道信息查询 的读取库（轴线 / 公称直径 / 保温厚度）
# ---------------------------------------------------------------------------

# 本文件在 管道支吊架/ 下，读取库在 管道信息查询/模块/管道信息/ 下。
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_PIPE_INFO_DIR = os.path.join(_REPO_ROOT, '管道信息查询', '模块', '管道信息')


def _load_pipe_reader():
    """按文件路径加载（必要时强制重读）管道信息读取库，规避模块缓存。"""
    name = '管道信息_读取'
    path = os.path.join(_PIPE_INFO_DIR, '管道信息_读取.py')
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    if _PIPE_INFO_DIR not in sys.path:
        sys.path.insert(0, _PIPE_INFO_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipe_reader = _load_pipe_reader()

# ``from MSPyX import *`` 不一定导出这些符号（ISessionMgr / ElementHandle /
# PyCadInputQueue 都是典型漏网的），按名字在已加载的 MSPy 模块里补齐。
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())


# 复用 管道支吊架 的统一面板外观（与其它插件一致的控件与配色）。
_UI_DIR = os.path.join(_HERE, '模块', '公共')
if _UI_DIR not in sys.path:
    sys.path.insert(0, _UI_DIR)
import 端焊三角架_基础 as base  # noqa: E402

UI_TITLE = '标准型2螺栓管夹（剪切测试）'
base.DEBUG_LOG = os.path.join(_HERE, '模块', '日志',
                              '标准型2螺栓管夹_剪切测试_debug_log.txt')
_log = base._log


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

# 兜底管径：管道公称直径读不到 / 不在表 1 时使用。正常按管道自动查表。
DN = 100

# 保温管是否按保温层外径放大内孔：True 时内孔 A' = A + 2×保温厚度。
ACCOMMODATE_INSULATION = True

# 表 1：DN -> 尺寸。t = G 列 × 前的板厚，w = G 列 × 后的板宽。
TABLE = {
    15:  {'nps': '1/2"',   'A': 25,  'B': 28,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    20:  {'nps': '3/4"',   'A': 30,  'B': 30,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    25:  {'nps': '1"',     'A': 37,  'B': 34,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    32:  {'nps': '1 1/4"', 'A': 45,  'B': 38,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    40:  {'nps': '1 1/2"', 'A': 51,  'B': 41,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    50:  {'nps': '2"',     'A': 63,  'B': 52,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    65:  {'nps': '2 1/2"', 'A': 79,  'B': 60,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    80:  {'nps': '3"',     'A': 92,  'B': 66,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    90:  {'nps': '3 1/2"', 'A': 105, 'B': 73,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    100: {'nps': '4"',     'A': 117, 'B': 84,  'C': 20, 'D': 50,  'F': 'M16', 't': 8,  'w': 50},
    125: {'nps': '5"',     'A': 143, 'B': 97,  'C': 20, 'D': 50,  'F': 'M16', 't': 8,  'w': 50},
    150: {'nps': '6"',     'A': 171, 'B': 116, 'C': 25, 'D': 60,  'F': 'M20', 't': 10, 'w': 60},
    200: {'nps': '8"',     'A': 222, 'B': 141, 'C': 25, 'D': 60,  'F': 'M20', 't': 10, 'w': 60},
    250: {'nps': '10"',    'A': 276, 'B': 176, 'C': 25, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    300: {'nps': '12"',    'A': 328, 'B': 202, 'C': 25, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    350: {'nps': '14"',    'A': 359, 'B': 217, 'C': 30, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    400: {'nps': '16"',    'A': 409, 'B': 242, 'C': 30, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    450: {'nps': '18"',    'A': 460, 'B': 268, 'C': 35, 'D': 75,  'F': 'M24', 't': 16, 'w': 75},
    500: {'nps': '20"',    'A': 511, 'B': 301, 'C': 35, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    550: {'nps': '22"',    'A': 563, 'B': 327, 'C': 35, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    600: {'nps': '24"',    'A': 613, 'B': 352, 'C': 40, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    650: {'nps': '26"',    'A': 663, 'B': 387, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
    700: {'nps': '28"',    'A': 714, 'B': 412, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
    750: {'nps': '30"',    'A': 765, 'B': 438, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
}

_THROUGH_MARGIN_MM = 5.0
_CELL_NAME = 'STD_2BOLT_CLAMP_TEST'

# 简化紧固件比例（精度不要求细致，能看出螺栓/螺母即可）。
_HEX_ACROSS_FLATS_RATIO = 1.5   # 六角对边 ≈ 1.5 d（M16→24）。
_BOLT_HEAD_HEIGHT_RATIO = 0.625  # 头高 ≈ 0.625 d（M16→10）。
_NUT_HEIGHT_RATIO = 0.8          # 螺母高 ≈ 0.8 d（M16→13）。
_BOLT_TIP_EXTRA_MM = 4.0         # 螺杆穿出螺母的长度。


def _row(dn):
    if dn not in TABLE:
        raise ValueError('表 1 中无 DN%d。' % dn)
    return TABLE[dn]


def _match_table_dn(nominal_mm):
    """把管道公称直径（mm）匹配到表 1 的 DN 键；匹配不上返回 ``None``。"""
    if nominal_mm is None:
        return None
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    best = min(TABLE, key=lambda key: abs(key - value))
    if abs(best - value) <= max(5.0, 0.15 * value):
        return best
    return None


def _check(status, operation):
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        code = int(status)
    except (TypeError, ValueError):
        raise RuntimeError('%s未返回有效状态码：%r' % (operation, status))
    if code != 0:
        raise RuntimeError('%s失败，状态：%s' % (operation, status))


def _cylinder_between(model, start, end, radius, uor):
    # 使用真正的圆柱曲面，不用多边形近似圆。
    detail = DgnConeDetail(start, end, radius * uor, radius * uor, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    _check(DraftingElementSchema.ToElement(element, primitive, None, model),
           '创建圆柱')
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    _check(status, '圆柱转内核体')
    return body


def _box_body(model, point, direction, x0, x1, y0, y1, z0, z1):
    points = DPoint3dArray()
    for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
        points.append(point(x0, y, z))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建长方体截面')
    _check(profile.AddToModel(), '创建长方体临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '长方体截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除长方体临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(x1 - x0, 0.0, 0.0)),
           '拉伸长方体')
    return body


def _cutter_section(model, point, direction, uor, row):
    """管夹状剪切截面：直径 A 的圆 + 长度 A+2t+2D、宽度 C 的矩形（沿 Y/Z）。

    整体沿管轴（本地 X）贯穿，比本体两端各多出余量以保证布尔干净。
    """
    a = float(row['A'])
    c = float(row['C'])
    d = float(row['D'])
    thickness = float(row['t'])
    width = float(row['w'])
    half = width / 2.0 + _THROUGH_MARGIN_MM
    bore = _cylinder_between(model, point(-half, 0.0, 0.0),
                             point(half, 0.0, 0.0), a / 2.0, uor)
    length = a + 2.0 * thickness + 2.0 * d + 2.0 * _THROUGH_MARGIN_MM
    box = _box_body(model, point, direction, -half, half,
                    -length / 2.0, length / 2.0, -c / 2.0, c / 2.0)
    return [bore, box]


def _hex_body(model, point, direction, x, y, z0, z1, across_flats):
    """沿本地 Z 拉伸的六角棱柱（六角头 / 螺母），对边尺寸为 across_flats。"""
    radius = across_flats / (2.0 * math.cos(math.pi / 6.0))
    points = DPoint3dArray()
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        points.append(point(x + radius * math.cos(theta),
                            y + radius * math.sin(theta), z0))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建六角截面')
    _check(profile.AddToModel(), '创建六角临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '六角截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除六角临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(0.0, 0.0, z1 - z0)),
           '拉伸六角头 / 螺母')
    return body


def _fastener_bodies(model, point, direction, uor, x, y, seat, bolt_dia,
                     hole_radius):
    """一套简化紧固件：贯穿的螺杆 + 一侧六角螺栓头 + 另一侧六角螺母。

    ``seat`` 为耳板外侧面的本地 Z 坐标；螺栓头在 +Z 侧、螺母在 -Z 侧。
    """
    head_height = bolt_dia * _BOLT_HEAD_HEIGHT_RATIO
    nut_height = bolt_dia * _NUT_HEIGHT_RATIO
    across = bolt_dia * _HEX_ACROSS_FLATS_RATIO
    shank = _cylinder_between(
        model, point(x, y, -seat - nut_height - _BOLT_TIP_EXTRA_MM),
        point(x, y, seat), bolt_dia / 2.0, uor)
    head = _hex_body(model, point, direction, x, y, seat,
                     seat + head_height, across)
    nut = _hex_body(model, point, direction, x, y, -seat - nut_height,
                    -seat, across)
    bits = ISolidKernelEntityPtrArray()
    bits.append(_cylinder_between(
        model, point(x, y, -seat - nut_height - _THROUGH_MARGIN_MM),
        point(x, y, -seat + _THROUGH_MARGIN_MM), hole_radius, uor))
    _check(SolidUtil.Modify.BooleanSubtract(nut, bits), '螺母中心孔')
    return [('螺杆', shank), ('六角螺栓头', head), ('六角螺母', nut)]


def _assembly_element(model, bodies):
    """把管架本体装入 Cell 后一次写入模型。"""
    cell = EditElementHandle()
    # 此API返回None，不是状态码；后续加入子元素、完成及写入均检查状态。
    NormalCellHeaderHandler.CreateOrphanCellElement(
        cell, _CELL_NAME, True, model)
    for name, body in bodies:
        child = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(child, body, None, model),
               name + '转模型元素')
        _check(NormalCellHeaderHandler.AddChildElement(cell, child),
               name + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成管架单元')
    _check(cell.AddToModel(), '写入管架单元')
    return cell


# ---------------------------------------------------------------------------
# 向量 / 本地方位系
# ---------------------------------------------------------------------------


def _uor_per_mm():
    model = ISessionMgr.GetActiveDgnModel()
    return model.GetModelInfo().GetUorPerMeter() / 1000.0


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normalize(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1.0e-12:
        raise ValueError('方向向量长度为零。')
    return (v[0] / length, v[1] / length, v[2] / length)


def _frame(axis):
    """由管轴方向构造本地方位系 ``(ex, ey, ez)``：X=管轴，Z≈竖直向上。

    绕管轴的角度由此自动确定，无需手动指定旋转角。
    """
    ex = _normalize(axis)
    up = (0.0, 0.0, 1.0)
    if abs(_dot(ex, up)) > 0.99:
        up = (1.0, 0.0, 0.0)
    ey = _normalize(_cross(up, ex))
    ez = _normalize(_cross(ex, ey))
    if ez[2] < 0.0:
        ey = (-ey[0], -ey[1], -ey[2])
        ez = (-ez[0], -ez[1], -ez[2])
    return ex, ey, ez


# ---------------------------------------------------------------------------
# 建模
# ---------------------------------------------------------------------------


def build_clamp(center_mm, axis, dn=None, insulation_mm=0.0, note=''):
    """沿管轴 ``axis`` 在 ``center_mm`` 处生成一组管夹，角度自动对齐。

    ``dn`` 为表 1 的 DN 键（None 时用脚本顶部 ``DN``）；``insulation_mm`` 为
    保温厚度，``ACCOMMODATE_INSULATION`` 为真时会把内孔放大 ``2×保温厚度``。
    返回 ``(模型单元, 提示文本)``，提示文本由面板显示。
    """
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    dn = DN if dn is None else dn
    row = dict(_row(dn))
    insulation_mm = float(insulation_mm or 0.0)
    if ACCOMMODATE_INSULATION and insulation_mm > 0.0:
        row['A'] = float(row['A']) + 2.0 * insulation_mm

    a = float(row['A'])
    c = float(row['C'])
    d = float(row['D'])
    thickness = float(row['t'])
    width = float(row['w'])

    cylinder_dia = a + 2.0 * thickness
    cylinder_radius = cylinder_dia / 2.0
    box_length = a + 2.0 * d + 2.0 * thickness
    box_width = c + 2.0 * thickness
    values = (a, c, d, thickness, width, cylinder_dia, box_length, box_width)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('尺寸参数必须是有限的正数。')

    uor = model.GetModelInfo().GetUorPerMeter() / 1000.0

    # 自动调整角度：本地 X 沿所选管轴，本地 Z 尽量竖直向上。
    ex, ey, ez = _frame(axis)
    center = (float(center_mm[0]), float(center_mm[1]), float(center_mm[2]))

    def point(x, y, z):
        return DPoint3d(
            (center[0] + x * ex[0] + y * ey[0] + z * ez[0]) * uor,
            (center[1] + x * ex[1] + y * ey[1] + z * ez[1]) * uor,
            (center[2] + x * ex[2] + y * ey[2] + z * ez[2]) * uor)

    def direction(x, y, z):
        return DVec3d(
            (x * ex[0] + y * ey[0] + z * ez[0]) * uor,
            (x * ex[1] + y * ey[1] + z * ez[1]) * uor,
            (x * ex[2] + y * ey[2] + z * ez[2]) * uor)

    # 1) 圆柱：轴向沿本地 X，长 = w（即长方体厚度）。
    half_w = width / 2.0
    ring = _cylinder_between(model, point(-half_w, 0.0, 0.0),
                             point(half_w, 0.0, 0.0), cylinder_radius, uor)
    # 2) 长方体：与圆柱同厚 w（沿 X），长 box_length（沿 Y），宽 box_width（沿 Z）。
    box = _box_body(model, point, direction, -half_w, half_w,
                    -box_length / 2.0, box_length / 2.0,
                    -box_width / 2.0, box_width / 2.0)

    parts = ISolidKernelEntityPtrArray()
    parts.append(box)
    _check(SolidUtil.Modify.BooleanUnion(ring, parts), '长方体与圆柱布尔并')

    # 3) 剪切截面（φA 圆 + 长度 A+2t+2D、宽度 C 的矩形）贯穿减去，成管夹状。
    cutters = ISolidKernelEntityPtrArray()
    for body in _cutter_section(model, point, direction, uor, row):
        cutters.append(body)
    _check(SolidUtil.Modify.BooleanSubtract(ring, cutters), '剪切截面裁切管架本体')

    # 4) 上下两对耳板开螺栓孔：孔心距中心 B（沿本地 Y），孔径 = F 数字 + 2，沿本地 Z 贯穿。
    f_number = int(''.join(ch for ch in row['F'] if ch.isdigit()))
    hole_radius = (f_number + 2.0) / 2.0
    hole_half = box_width / 2.0 + _THROUGH_MARGIN_MM
    holes = ISolidKernelEntityPtrArray()
    for sign in (1.0, -1.0):
        y = sign * float(row['B'])
        holes.append(_cylinder_between(model, point(0.0, y, -hole_half),
                                       point(0.0, y, hole_half),
                                       hole_radius, uor))
    _check(SolidUtil.Modify.BooleanSubtract(ring, holes), '耳板开螺栓孔')

    bodies = [('管架本体', ring)]
    # 5) 每个螺栓孔穿一套简化紧固件（独立实体，与本体分开）。
    for sign in (1.0, -1.0):
        y = sign * float(row['B'])
        bodies.extend(_fastener_bodies(model, point, direction, uor, 0.0, y,
                                       box_width / 2.0, f_number, hole_radius))
    result = _assembly_element(model, bodies)

    message = ('已生成标准型2螺栓管夹（DN%d，%s，%s）：'
               '圆柱 φ%.1f（A+2t=%.0f+2×%.0f）、轴向长 %.0f；'
               '长方体 长%.1f（A+2D+2t）×宽%.1f（C+2t）×厚%.0f；'
               '剪切截面 φ%.0f（A） + 长%.1f×宽%.0f（C）矩形；'
               '螺栓孔 φ%.0f（%s+2），孔心距中心 %.0f（B）；'
               '每孔配 1 套简化螺栓（%s：螺杆 φ%.0f + 六角头 + 六角螺母）；'
               '整组依托所选轴线定位，绕轴角度自动对齐（本地 Z 竖直向上）。'
               % (dn, row['nps'], row['F'], cylinder_dia, a, thickness, width,
                  box_length, box_width, width, a, box_length, c,
                  f_number + 2.0, row['F'], float(row['B']),
                  row['F'], float(f_number)))
    if insulation_mm > 0.0:
        message += (' 保温厚度 %.1f mm%s。'
                    % (insulation_mm,
                       '，已放大内孔' if ACCOMMODATE_INSULATION else '（未放大内孔）'))
    if note:
        message += ' ' + note
    return result, message


def _is_pipe_placement(placement):
    """判断本次点选到的是**管道**（有 OpenPlant EC 实例）还是普通直线段。"""
    snapshot = placement.get('snapshot') or {}
    return bool((snapshot.get('ec') or {}).get('found'))


def build_on_pick(placement, click_mm):
    """按所选元素（管道或直线段）与点击点生成管夹。

    * 选中**管道**：用其公称直径自动查表，并按其保温厚度决定是否放大内孔；
    * 选中**直线段**：以该直线为管轴，未读到管道属性时用脚本顶部 ``DN`` 兜底。

    ``placement`` 为读取库 ``pipe_placement_info`` 的返回（对普通直线同样适用）；
    ``click_mm`` 为点击点（mm），投影到轴线后即管夹的轴向中心。
    返回 ``(模型单元, 提示文本)``，提示文本由面板显示。
    """
    start = placement.get('start_mm')
    end = placement.get('end_mm')
    axis = placement.get('axis')
    if not start or not end or axis is None:
        raise ValueError('该元素没有可用的轴线（起点 / 终点不可用），无法定位管夹；'
                         '请点选管道或一条直线段。')

    if click_mm is not None:
        center = pipe_reader.project_onto_axis(click_mm, start, end)
    else:
        center = placement.get('center_mm') or start

    is_pipe = _is_pipe_placement(placement)
    nominal = placement.get('nominal_diameter_mm')
    matched = _match_table_dn(nominal)
    dn = matched if matched is not None else DN
    raw_warnings = [text for text in (placement.get('warnings') or []) if text]

    parts = []
    if is_pipe:
        if matched is not None:
            parts.append('管道公称直径 %.1f mm。' % nominal)
        else:
            parts.append('管道公称直径 %s 未匹配到表 1，管径暂用 DN%d。'
                         % ('未知' if nominal is None else '%.1f mm' % nominal, DN))
        warnings = raw_warnings
    else:
        parts.append('按所选直线作为管轴；未读到管道属性，管径暂用 DN%d。' % DN)
        # 直线元素上"没有管道实例 / 没有公称直径 / 无法标定属性单位"属正常，
        # 都是面向管道 EC 属性的提示，对直线无意义。
        skip = ('没有找到 OpenPlant', '公称直径', '没有读到公称直径',
                '标定属性单位')
        warnings = [text for text in raw_warnings
                    if not any(mark in text for mark in skip)]

    if not placement.get('exact', True):
        parts.append('按包围盒最长边近似管轴（仅对与世界坐标轴平行的直管段可靠）。')
    orientation = placement.get('orientation')
    slope = placement.get('slope_percent')
    if orientation:
        text = '走向%s' % orientation
        if slope is not None:
            text += '（坡度 %.2f%%）' % slope
        parts.append(text + '。')
    if warnings:
        parts.append('注意：%s' % '；'.join(warnings))

    return build_clamp(center, axis, dn,
                       placement.get('insulation_thickness_mm') or 0.0,
                       ''.join(parts))


# ---------------------------------------------------------------------------
# 面板：显示生成记录与状态（不向控制台打印）
# ---------------------------------------------------------------------------


class _ClampPanel(QWidget):
    """简易面板：点选提示 + 生成记录 + 状态；同时驱动点选主循环。"""

    RADIUS = base.UI_RADIUS

    def __init__(self):
        self._app = base.ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, base.UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self.pending = []          # [(element_id, click_mm)]
        self._running = True
        self._allow_close = False
        self._finish_requested = False
        self._event_loop = QEventLoop()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(base.NeuTitleBar(UI_TITLE, self.showMinimized,
                                         self.close_panel))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel(
            '在模型中点选一根管道或一条直线段：管夹将在点击处沿其轴线生成。'
            '管道自动读取公称直径 / 保温厚度；直线用默认 DN%d。'
            '可连续点选（管道 / 直线可交替），右键退出。' % DN)
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = base.NeuCard('生成记录')
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(240)
        self.log.setStyleSheet(
            'QPlainTextEdit {border: none; background: #E7EBF2;'
            ' color: #39435A; font-size: 12px;}')
        card.content.addWidget(self.log, 0, 0)
        body.addWidget(card)

        summary = base.NeuPanel()
        self.status_label = QLabel('请在模型中点选管道或直线。')
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet('color: #2F6FB5; font-size: 11px;')
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.clear_button = base.NeuButton('清空记录')
        self.clear_button.setFixedWidth(130)
        self.clear_button.clicked.connect(self.log.clear)
        self.close_button = base.NeuButton('退出', accent=True)
        self.close_button.setFixedWidth(126)
        self.close_button.clicked.connect(self.close_panel)
        button_row.addStretch(1)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.close_button)
        body.addLayout(button_row)

        self.setMinimumWidth(560)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        self.hwnd = int(self.winId())
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)

    # -- 输出 --------------------------------------------------------------

    def set_status(self, message, is_error=False):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        QApplication.processEvents()

    def append_log(self, message):
        self.log.appendPlainText(message)
        self.log.appendPlainText('')

    # -- 点选队列 ----------------------------------------------------------

    def queue_pick(self, element_id, click_mm):
        self.pending.append((element_id, click_mm))

    def _drain_pending(self):
        pending, self.pending = self.pending, []
        for element_id, click_mm in pending:
            self._process(element_id, click_mm)

    def _process(self, element_id, click_mm):
        # 这里已不在工具回调内（PythonMainLoop 返回之后），可安全读取 EC。
        try:
            handle = pipe_reader.element_handle_by_id(element_id)
        except Exception as error:
            _log_exception('open element failed')
            self.set_status('打开元素失败：%s' % error, True)
            return
        if handle is None:
            self.set_status('元素 ID %s 已失效（可能已被删除）。' % element_id,
                            True)
            return
        try:
            placement = pipe_reader.pipe_placement_info(handle, 'auto')
            result, message = build_on_pick(placement, click_mm)
        except Exception as error:
            _log_exception('build clamp failed')
            self.set_status('生成失败：%s' % error, True)
            return
        self.append_log(message)
        self.set_status('已生成一组管夹。继续点选管道或直线，右键退出。')

    # -- 收尾 --------------------------------------------------------------

    def close_panel(self):
        self._running = False
        self._finish_requested = True

    def _finish_tool(self):
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        if not self._running and self._allow_close:
            return
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            pass

    # -- 窗口 --------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(210, 218, 231), 1.0))
        painter.setBrush(base.UI_BG)
        painter.drawRoundedRect(frame, self.RADIUS, self.RADIUS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.close_panel()

    def run_dialog_loop(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2,
                      area.center().y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        while self._running:
            self._event_loop.processEvents()
            if self._finish_requested:
                self._finish_requested = False
                self._finish_tool()
                continue
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception:
                _log_exception('PythonMainLoop failed')
                break
            self._drain_pending()
        self._teardown_window()

    def _teardown_window(self):
        """退出事件泵后收尾：关闭窗口、冲刷重绘并延迟销毁，避免 UI 残留。"""
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            return
        QApplication.processEvents()
        try:
            self.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        except (RuntimeError, TypeError):
            pass
        QApplication.processEvents()


# ---------------------------------------------------------------------------
# 交互工具：点选管道 / 直线（只入队，EC 读取在面板循环里）
# ---------------------------------------------------------------------------


class Std2BoltClampPipeTool(DgnElementSetTool):
    """点选**管道或直线段**，在点击处沿其轴线生成标准型 2 螺栓管夹。

    选中管道时自动读取公称直径 / 保温厚度；选中普通直线段时以该直线为管轴、
    管径用脚本顶部 ``DN`` 兜底。两种元素都支持，可连续点选。

    ``_OnPostLocate`` 只记元素 ID；``_OnDataButton`` 只把 (元素 ID, 点击点)
    交给面板排队并消费点击——**回调内不做任何 EC 读取**。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('Std2BoltClampPipeTest')

    def _DoGroups(self):
        return False

    def _AllowSelection(self):
        return DgnElementSetTool.eUSES_SS_None

    def _NeedAcceptPoint(self):
        return False

    def _WantDynamics(self):
        return False

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnElementSetTool._OnPostInstall(self)
        if self.panel is not None:
            self.panel.set_status('请点选一根管道或一条直线段；右键退出。')

    def _OnPostLocate(self, path, cant_accept_reason):
        """只记下定位到的元素 ID（不保存句柄、不读属性）。"""
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = pipe_reader.read_element_id(handle)
            return self._located_id is not None
        except Exception:
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        """把 (元素 ID, 点击点) 入队；返回 True 消费本次点击。"""
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            self.panel.set_status(
                '没有定位到元素：请把光标放在管道或直线上再点击。', True)
            return True
        try:
            point = event.GetPoint()
            uor = _uor_per_mm()
            click_mm = (point.x / uor, point.y / uor, point.z / uor)
        except Exception:
            click_mm = None
        self.panel.queue_pick(element_id, click_mm)
        return True

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.close_panel()
        return True

    def _OnRestartTool(self):
        # 保留面板引用重装工具，从而可以连续点取。
        panel = self.panel
        self.panel = None
        Std2BoltClampPipeTool.InstallNewInstance(
            self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = Std2BoltClampPipeTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_clamp_panel():
    """打开面板；已在运行时把已有窗口提到前台，避免重复窗口残留。"""
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel._running:
                _active_panel.raise_()
                _active_panel.activateWindow()
                return None
        except RuntimeError:
            pass
    panel = _ClampPanel()
    _active_panel = panel
    try:
        return Std2BoltClampPipeTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


def PyMain():
    try:
        return show_clamp_panel()
    except Exception as error:
        _log_exception('clamp tool start failed')
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, UI_TITLE, '启动失败：%s' % error)
        except Exception:
            pass
        return None


if __name__ == '__main__':
    PyMain()
