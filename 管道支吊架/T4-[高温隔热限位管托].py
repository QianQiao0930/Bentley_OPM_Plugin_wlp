# -*- coding: utf-8 -*-
"""保温管夹（高温隔热限位管托，图集 T4）放置工具 —— DN80~600。

在模型中**点选一根管道或一条直线段**取方向，并在**点击处**（= 管托 L 的中心，
投影到轴线；取不到点击点时用线中点）放置一组保温管夹。选中管道时自动读取
公称直径 / 保温厚度，选中直线段（或读不到管道属性）时改用面板输入的
DN / 保温厚度：

    坐标系：原点 = 管道中线（管托 L 中心），X 沿管轴，Z 竖直向上
    承重板（上/下半）= 包在保温层外的筒形板（板厚 T3），对开 45°、两端留
                        间隙 J，用耳板 + 螺栓（带碟簧垫圈）连接
    管夹底座         = 底板 + 两道（L＞600 时三道）横向弧顶支撑 + 中央纵向腹板；
                        底板宽 W 查表 2
    H                = 管道（不含保温层）底部 → 管托底面；由保温厚度 B 查表
                        （≤75→150，76~125→200，126~175→250，176~225→300，
                        226~275→350）
    L                = 管托沿管轴总长（不含止推件），≥ 300（管夹环与底座同长）

``OD / 螺栓 / 耳板 / C / k / J / T1 T2 T3 / 允许荷载`` 来自表 1（DN80~600），
底板宽 ``W`` 由保温层外径 ``D = OD + 2B`` 查表 2；``H`` 由 ``B`` 查表，
``B / L`` 由面板输入。**管道本体 / 保温层可选**（默认都不建），限位块 /
止推件本次不建。

三维建模：管夹本体 = 外圆柱 − 内圆柱 − 45° 矩形贯穿体（真圆柱布尔，得到对开
两片）；耳板开螺栓通孔后与管夹布尔并；底座弧顶支撑用圆柱布尔剪切后与底板并；
紧固件为独立实体。所有构件先在本地方位系内造好再按所选管道轴线定位，最后装进
一个普通单元。清单写入公共库 ``SupportType='保温管夹'``。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import importlib.util
import math
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 公共库在 模块/公共/，本插件几何在 模块/保温管夹/，仓库根提供 bentley_ui。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '保温管夹')
for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
try:
    import bentley_ui.glass as _glass_module  # noqa: F401
    import bentley_ui as _bentley_ui_module  # noqa: F401
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (  # noqa: E402
    BORDER,
    CARD,
    CARD_SOFT,
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    ScrollFrame,
    SlimScrollbar,
)

import 保温管夹_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# ---------------------------------------------------------------------------
# 复用 管道信息查询 的读取库（管道轴线 / 公称直径 / 保温厚度）
# ---------------------------------------------------------------------------

_PIPE_INFO_DIR = os.path.join(REPO_ROOT, '管道信息查询', '模块', '管道信息')


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

# ``from MSPyX import *`` 不一定导出这些符号，按名字在已加载的 MSPy 模块里补齐。
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())


SUPPORT_TYPE = 'T4-[高温隔热限位管托]'
SUPPORT_CODE = 'INSULATED_PIPE_CLAMP'
CELL_NAME = 'INSULATED_PIPE_CLAMP'

# 管道 / 保温层配色（精确 RGB，不改活动颜色表）：钢灰 + 岩棉黄，便于区分。
PIPE_RGB = (148, 148, 148)
INSULATION_RGB = (245, 200, 90)

# --- 布尔建模常量（对齐「剪切测试」版） ------------------------------------
EAR_END_OFFSET_MM = 75.0      # 首 / 尾耳板中心到管夹轴向端部的距离。
EAR_GROUP_COUNT = 0           # 0=自动（L≤600 两组，L＞600 三组）。
SUPPORT_END_OFFSET_MM = 75.0  # 横向支撑中心到管夹轴向端部的距离。
SUPPORT_SIDE_INSET_MM = 10.0  # 横向支撑两侧距底板边缘。
SUPPORT_OVERLAP_MM = 1.0      # 支撑与承重板 / 底板的布尔搭接量。
EAR_SETBACK_MM = 10.0         # 耳板内侧面距承重板切口端面的退让距离。
EAR_ROOT_OVERLAP_MM = 1.0     # 耳板根部与承重板的搭接量。
HOLE_CLEARANCE_MM = 2.0       # 螺栓通孔相对螺杆直径的单边余量（M20→22）。
CUT_EXTRA_LENGTH_MM = 20.0    # 45° 贯穿切割体两端伸出外圆之外的余量。
THROUGH_MARGIN_MM = 5.0       # 布尔贯穿余量，避免共面失败。
# 简化紧固件比例；M20 时与「剪切测试」版一致（对边 30 / 头高 12.5 / 螺母高 16 /
# 垫圈外径 37）。
HEX_ACROSS_FLATS_RATIO = 1.5
BOLT_HEAD_HEIGHT_RATIO = 0.625
NUT_HEIGHT_RATIO = 0.8
WASHER_OD_RATIO = 1.85
WASHER_THICKNESS_MM = 3.0
BOLT_TIP_EXTRA_MM = 4.0

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '保温管夹_debug_log.txt')
UI_TITLE = 'T4-[高温隔热限位管托]'
UI_REVISION = 'point-select-1'

DEFAULT_DN = 200
DEFAULT_INSULATION_MM = 50.0
DEFAULT_HEIGHT_MM = geom.height_for_insulation(DEFAULT_INSULATION_MM)
DEFAULT_LENGTH_MM = 300.0

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖，避免打到一半就重建

def _log(message):
    try:
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (stamp, message))
            stream.flush()
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    importlib.invalidate_caches()
    for module in (geom, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _point_to_mm(point, uor_per_mm):
    return (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)


def _match_dn(nominal_mm):
    """把管道公称直径（mm）匹配到表 1 的 DN 键；匹配不上返回 ``None``。"""
    if nominal_mm is None:
        return None
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    if value <= 0.0:
        return None
    keys = sorted(geom.DN_TABLE)
    best = min(keys, key=lambda key: abs(key - value))
    if abs(best - value) <= max(5.0, 0.15 * value):
        return best
    return None


# ---------------------------------------------------------------------------
# 向量运算与本地方位系
# ---------------------------------------------------------------------------


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


def _frame(direction, origin_mm):
    """返回本地方位系 ``(ex, ey, ez, origin)``：X=管轴，Z≈竖直向上。"""
    ex = _normalize(direction)
    up = (0.0, 0.0, 1.0)
    if abs(_dot(ex, up)) > 0.99:
        up = (1.0, 0.0, 0.0)
    ey = _normalize(_cross(up, ex))
    ez = _normalize(_cross(ex, ey))
    if ez[2] < 0.0:
        ey = (-ey[0], -ey[1], -ey[2])
        ez = (-ez[0], -ez[1], -ez[2])
    return (ex, ey, ez, tuple(float(v) for v in origin_mm))


def _world(frame, x, y, z):
    ex, ey, ez, o = frame
    return (o[0] + x * ex[0] + y * ey[0] + z * ez[0],
            o[1] + x * ex[1] + y * ey[1] + z * ez[1],
            o[2] + x * ex[2] + y * ey[2] + z * ez[2])


def _world_dir(frame, x, y, z):
    ex, ey, ez, _o = frame
    return (x * ex[0] + y * ey[0] + z * ez[0],
            x * ex[1] + y * ey[1] + z * ez[1],
            x * ex[2] + y * ey[2] + z * ez[2])


# ---------------------------------------------------------------------------
# 实体构造
# ---------------------------------------------------------------------------


def _profile_body(points_mm, sweep_mm, dgn_model, uor_per_mm):
    """由共面点列构造截面，再沿 sweep 拉伸成一个体；返回内核体或 None。"""
    points = DPoint3dArray()
    for point in points_mm:
        points.append(DPoint3d(point[0] * uor_per_mm, point[1] * uor_per_mm,
                               point[2] * uor_per_mm))
    profile = EditElementHandle()
    if BentleyStatus.eSUCCESS != ShapeHandler.CreateShapeElement(
            profile, None, points, dgn_model.Is3d(), dgn_model):
        return None
    if BentleyStatus.eSUCCESS != profile.AddToModel():
        return None
    result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if result is None or BentleyStatus.eSUCCESS != result[0]:
        return None
    body = result[1]
    sweep = DVec3d(sweep_mm[0] * uor_per_mm, sweep_mm[1] * uor_per_mm,
                   sweep_mm[2] * uor_per_mm)
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body, sweep):
        return None
    return body


def _box_body(frame, low, high, dgn_model, uor_per_mm):
    """本地方位系内的长方体：low/high 为 (x, y, z)（mm）。"""
    corners = [(low[0], low[1], low[2]), (high[0], low[1], low[2]),
               (high[0], high[1], low[2]), (low[0], high[1], low[2])]
    points = [_world(frame, *corner) for corner in corners]
    sweep = _world_dir(frame, 0.0, 0.0, high[2] - low[2])
    return _profile_body(points, sweep, dgn_model, uor_per_mm)


def _boolean(target, tools, subtract):
    array = ISolidKernelEntityPtrArray()
    for tool in tools:
        array.append(tool)
    try:
        if subtract:
            status = SolidUtil.Modify.BooleanSubtract(target, array)
        else:
            status = SolidUtil.Modify.BooleanUnion(target, array)
    except Exception as error:
        _log('boolean exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    return BentleyStatus.eSUCCESS == status


def _tube_body(frame, base_local, axis_local, r_out, r_in, length, dgn_model,
               uor_per_mm):
    """圆环筒：外圆柱 − 内圆柱。

    用**真圆柱曲面**（``_cone_body`` / ``DgnConeDetail``），不再用多边形近似，
    因此管道 / 保温层表面与管夹环本体一致，无棱面。
    """
    axis = _normalize(axis_local)
    start = tuple(base_local[index] for index in range(3))
    end = tuple(base_local[index] + axis[index] * length for index in range(3))
    outer = _cone_body(frame, uor_per_mm, start, end, r_out, dgn_model)
    if outer is None:
        return None
    # 内圆柱两端各多伸 1mm，保证布尔减干净。
    margin = 1.0
    inner_start = tuple(start[index] - axis[index] * margin
                        for index in range(3))
    inner_end = tuple(end[index] + axis[index] * margin for index in range(3))
    inner = _cone_body(frame, uor_per_mm, inner_start, inner_end, r_in,
                       dgn_model)
    if inner is None or not _boolean(outer, [inner], True):
        return None
    return outer


def _body_to_element(body, dgn_model, name):
    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
            solid, body, None, dgn_model):
        _log('%s: BodyToElement failed' % name)
        return None
    return solid


def _element_color(rgb):
    """由 RGB 生成可直接写入元素的精确颜色编码（不改活动颜色表）。

    取色 API 缺符号 / 失败时返回 ``None``，由 :func:`_apply_color` 跳过上色，
    不影响几何生成。
    """
    try:
        color_def = IntColorDef(rgb[0], rgb[1], rgb[2])
        return DgnColorMap.CreateElementColor(
            color_def, None, None, ISessionMgr.GetActiveDgnFile())
    except Exception:
        _log_exception('element color failed')
        return None


def _apply_color(element, color):
    """把颜色写到元素上；``color`` 为 ``None`` 时原样返回。"""
    if element is None or color is None:
        return element
    try:
        properties = ElementPropertiesSetter()
        properties.SetColor(color)
        properties.Apply(element)
    except Exception:
        _log_exception('apply color failed')
    return element


# ---------------------------------------------------------------------------
# 布尔建模（管夹本体 / 耳板 / 底座 / 紧固件）
# ---------------------------------------------------------------------------


def _cut_frame(split_angle_deg):
    """返回切口坐标系方向余弦 ``(c, s)``：a 沿径向、b 沿切口法向。

    本地坐标点 = ``(x, a * c - b * s, a * s + b * c)``（X=管轴，Z 向上）。
    """
    angle = math.radians(float(split_angle_deg))
    return math.sin(angle), math.cos(angle)


def _mm_point(frame, uor_per_mm, x, y, z):
    world = _world(frame, x, y, z)
    return DPoint3d(world[0] * uor_per_mm, world[1] * uor_per_mm,
                    world[2] * uor_per_mm)


def _cone_body(frame, uor_per_mm, start, end, radius, dgn_model):
    """真正的圆柱实体；起点、终点为本地坐标（mm）。失败返回 None。"""
    p0 = _mm_point(frame, uor_per_mm, *start)
    p1 = _mm_point(frame, uor_per_mm, *end)
    r = radius * uor_per_mm
    detail = DgnConeDetail(p0, p1, r, r, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if BentleyStatus.eSUCCESS != DraftingElementSchema.ToElement(
            element, primitive, None, dgn_model):
        return None
    result = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if result is None or not _succeeded(result[0]):
        return None
    return result[1]


def _sweep_profile(frame, uor_per_mm, local_points, local_sweep, dgn_model):
    points = [_world(frame, *point) for point in local_points]
    sweep = _world_dir(frame, *local_sweep)
    return _profile_body(points, sweep, dgn_model, uor_per_mm)


def _require_boolean(target, tools, subtract, label):
    if not _boolean(target, tools, subtract):
        raise RuntimeError('布尔运算失败：%s' % label)


def _ear_body(frame, uor, split, center_x, a0, a1, b0, b1, width, dgn_model):
    c, s = _cut_frame(split)
    local = []
    for a, b in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
        local.append((center_x - width / 2.0, a * c - b * s, a * s + b * c))
    body = _sweep_profile(frame, uor, local, (width, 0.0, 0.0), dgn_model)
    if body is None:
        raise RuntimeError('创建耳板失败。')
    return body


def _rectangle_cutter(frame, uor, split, length, outer_radius, gap_j,
                      dgn_model):
    c, s = _cut_frame(split)
    half_length = outer_radius + CUT_EXTRA_LENGTH_MM / 2.0
    half_gap = gap_j / 2.0
    x0 = -length / 2.0 - THROUGH_MARGIN_MM
    corners = ((-half_length, -half_gap), (half_length, -half_gap),
               (half_length, half_gap), (-half_length, half_gap))
    local = [(x0, a * c - b * s, a * s + b * c) for a, b in corners]
    sweep = (length + 2.0 * THROUGH_MARGIN_MM, 0.0, 0.0)
    body = _sweep_profile(frame, uor, local, sweep, dgn_model)
    if body is None:
        raise RuntimeError('创建 45 度贯穿切割体失败。')
    return body


def _build_ring(frame, uor, bl, layout, dgn_model):
    """外圆柱 − 内圆柱 − 45° 矩形贯穿体，再逐块布尔并入开孔耳板。"""
    half_l = bl.clamp_length_mm / 2.0
    ring = _cone_body(frame, uor, (-half_l, 0.0, 0.0), (half_l, 0.0, 0.0),
                      bl.outer_radius, dgn_model)
    if ring is None:
        raise RuntimeError('创建管夹外圆柱失败。')
    bore = _cone_body(frame, uor,
                      (-half_l - THROUGH_MARGIN_MM, 0.0, 0.0),
                      (half_l + THROUGH_MARGIN_MM, 0.0, 0.0),
                      bl.inner_radius, dgn_model)
    _require_boolean(ring, [bore], True, '外圆柱减去管道及保温层圆柱')
    cutter = _rectangle_cutter(frame, uor, bl.cut_angle_deg,
                               bl.clamp_length_mm, bl.outer_radius,
                               bl.gap_j, dgn_model)
    _require_boolean(ring, [cutter], True, '圆环减去 45 度矩形贯穿体')

    c, s = _cut_frame(bl.cut_angle_deg)
    for center_x in bl.ear_center_x:
        for index, (a0, a1, b0, b1) in enumerate(bl.ear_bounds, 1):
            ear = _ear_body(frame, uor, bl.cut_angle_deg, center_x,
                            a0, a1, b0, b1, bl.ear_width, dgn_model)
            a = bl.ear_hole_a[index - 1]
            start_b = b0 - THROUGH_MARGIN_MM
            end_b = b1 + THROUGH_MARGIN_MM
            hole = _cone_body(
                frame, uor,
                (center_x, a * c - start_b * s, a * s + start_b * c),
                (center_x, a * c - end_b * s, a * s + end_b * c),
                bl.hole_dia / 2.0, dgn_model)
            _require_boolean(ear, [hole], True, '耳板%d开螺栓通孔' % index)
            _require_boolean(ring, [ear], False, '耳板%d与管夹布尔并' % index)
    return ring


def _build_support(frame, uor, bl, layout, ring, dgn_model):
    """底板 + 横向弧顶支撑 + 中央纵向腹板，弧顶减圆柱成形后并入管夹。"""
    length = bl.clamp_length_mm
    half_l = length / 2.0
    half_w = layout.base_width / 2.0
    base = _box_body(frame, (-half_l, -half_w, bl.base_bottom_z),
                     (half_l, half_w, bl.base_top_z), dgn_model, uor)
    if base is None:
        raise RuntimeError('创建底板失败。')
    half_t = layout.t2 / 2.0
    plates = [(x - half_t, x + half_t, -bl.support_half_span,
               bl.support_half_span) for x in bl.support_center_x]
    plates.append((bl.support_center_x[0], bl.support_center_x[-1],
                   -half_t, half_t))
    c, s = _cut_frame(bl.cut_angle_deg)
    for index, (x0, x1, y0, y1) in enumerate(plates, 1):
        plate = _box_body(frame, (x0, y0, bl.base_top_z - SUPPORT_OVERLAP_MM),
                          (x1, y1, bl.support_top_z), dgn_model, uor)
        if plate is None:
            raise RuntimeError('创建支撑%d失败。' % index)
        cutter = _cone_body(frame, uor,
                            (x0 - THROUGH_MARGIN_MM, 0.0, 0.0),
                            (x1 + THROUGH_MARGIN_MM, 0.0, 0.0),
                            bl.trim_radius, dgn_model)
        _require_boolean(plate, [cutter], True, '支撑%d剪切贴合圆弧' % index)
        max_b = max(-s * y + c * bl.support_top_z for y in (y0, y1))
        if max_b > -bl.gap_j / 2.0:
            slit = _rectangle_cutter(frame, uor, bl.cut_angle_deg, length,
                                     bl.outer_radius, bl.gap_j, dgn_model)
            _require_boolean(plate, [slit], True,
                             '支撑%d避让管夹对开间隙' % index)
        _require_boolean(base, [plate], False, '支撑%d连接底板' % index)
    _require_boolean(ring, [base], False, '支腿与下半承重板连接')


def _hex_body(frame, uor, split, center_x, a, b0, b1, across_flats, dgn_model):
    c, s = _cut_frame(split)
    radius = across_flats / (2.0 * math.cos(math.pi / 6.0))
    local = []
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        x = center_x + radius * math.cos(theta)
        radial = a + radius * math.sin(theta)
        local.append((x, radial * c - b0 * s, radial * s + b0 * c))
    distance = b1 - b0
    body = _sweep_profile(frame, uor, local,
                          (0.0, -s * distance, c * distance), dgn_model)
    if body is None:
        raise RuntimeError('创建六角头 / 螺母失败。')
    return body


def _fastener_bodies(frame, uor, bl, layout, center_x, a, dgn_model):
    """一套：贯穿两耳板的光杆、六角头、六角螺母、两只圆环垫圈。"""
    c, s = _cut_frame(bl.cut_angle_deg)
    d = layout.bolt_dia_mm

    def cylinder(b0, b1, radius):
        return _cone_body(frame, uor,
                          (center_x, a * c - b0 * s, a * s + b0 * c),
                          (center_x, a * c - b1 * s, a * s + b1 * c),
                          radius, dgn_model)

    far = bl.gap_j / 2.0 + bl.ear_setback + layout.ear_thickness
    seat = far + WASHER_THICKNESS_MM
    across = d * HEX_ACROSS_FLATS_RATIO
    head_h = d * BOLT_HEAD_HEIGHT_RATIO
    nut_h = d * NUT_HEIGHT_RATIO
    shank = cylinder(-seat, seat + nut_h + BOLT_TIP_EXTRA_MM, d / 2.0)
    head = _hex_body(frame, uor, bl.cut_angle_deg, center_x, a,
                     -seat - head_h, -seat, across, dgn_model)
    nut = _hex_body(frame, uor, bl.cut_angle_deg, center_x, a,
                    seat, seat + nut_h, across, dgn_model)
    _require_boolean(nut, [cylinder(seat - THROUGH_MARGIN_MM,
                                    seat + nut_h + THROUGH_MARGIN_MM,
                                    bl.hole_dia / 2.0)], True, '螺母中心孔')
    bodies = [('M%s螺杆' % int(d), shank), ('六角螺栓头', head), ('六角螺母', nut)]
    for b0, b1 in ((-seat, -far), (far, seat)):
        washer = cylinder(b0, b1, d * WASHER_OD_RATIO / 2.0)
        _require_boolean(washer, [cylinder(b0 - THROUGH_MARGIN_MM,
                                           b1 + THROUGH_MARGIN_MM,
                                           bl.hole_dia / 2.0)], True,
                         '垫圈中心孔')
        bodies.append(('垫圈', washer))
    return bodies


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


class _ClampCellBuilder(object):
    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, cell_name or CELL_NAME, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('保温管架构件创建失败。')
        if not _succeeded(NormalCellHeaderHandler.AddChildElement(self.cell,
                                                                  child)):
            raise RuntimeError('无法把构件加入单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError('无法完成保温管夹单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法把保温管夹单元写入模型。')
        return self.cell


# ---------------------------------------------------------------------------
# 整组建模
# ---------------------------------------------------------------------------


def _build_components(layout, frame, dgn_model, uor_per_mm):
    """布尔建模：管夹本体 + 耳板 + 弧顶支撑底座，返回 ``(构件列表, 布尔布局)``。

    坐标原点为管道中线；X=管轴，Z 竖直向上。管夹环、耳板、底座经布尔并合并为
    一个实体；紧固件为独立实体。
    """
    bl = geom.build_boolean_layout(
        layout,
        ear_end_offset=EAR_END_OFFSET_MM,
        ear_group_count=EAR_GROUP_COUNT,
        support_end_offset=SUPPORT_END_OFFSET_MM,
        support_side_inset=SUPPORT_SIDE_INSET_MM,
        support_overlap=SUPPORT_OVERLAP_MM,
        ear_setback=EAR_SETBACK_MM,
        ear_root_overlap=EAR_ROOT_OVERLAP_MM,
        hole_clearance=HOLE_CLEARANCE_MM)

    ring = _build_ring(frame, uor_per_mm, bl, layout, dgn_model)
    _build_support(frame, uor_per_mm, bl, layout, ring, dgn_model)

    results = [('管夹和支腿', ring)]
    for center_x in bl.ear_center_x:
        # 每个轴向位置有两处分口，各穿一套紧固件（孔心 a 取正、负各一）。
        for a in (bl.ear_hole_a[2], bl.ear_hole_a[0]):
            results.extend(
                _fastener_bodies(frame, uor_per_mm, bl, layout,
                                 center_x, a, dgn_model))
    return results, bl


def _build_clamp_cell(layout, frame, build_pipe, build_insulation, dgn_model):
    uor_per_mm = _uor_per_mm(dgn_model)
    components, bl = _build_components(layout, frame, dgn_model, uor_per_mm)
    length = bl.clamp_length_mm

    builder = _ClampCellBuilder(dgn_model)
    built = {'pipe': 0, 'insulation': 0}
    # 管道钢灰、保温层岩棉黄，便于在模型里区分（取色失败时自动跳过）。
    pipe_color = _element_color(PIPE_RGB)
    insulation_color = _element_color(INSULATION_RGB)
    if build_pipe:
        wall = max(3.0, layout.od_mm * 0.04)
        pipe = _tube_body(frame, (-length / 2.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                          layout.pipe_radius, layout.pipe_radius - wall,
                          length + 40.0, dgn_model, uor_per_mm)
        element = _body_to_element(pipe, dgn_model, '管道') \
            if pipe is not None else None
        if element is not None:
            _apply_color(element, pipe_color)
            builder.add(element)
            built['pipe'] = 1
        else:
            builder.note('管道本体创建失败，已跳过。')

    if build_insulation:
        insulation = _tube_body(frame, (-length / 2.0, 0.0, 0.0),
                                (1.0, 0.0, 0.0), layout.insulation_radius,
                                layout.pipe_radius, length, dgn_model,
                                uor_per_mm)
        element = _body_to_element(insulation, dgn_model, '保温层') \
            if insulation is not None else None
        if element is not None:
            _apply_color(element, insulation_color)
            builder.add(element)
            built['insulation'] = 1
        else:
            builder.note('保温层创建失败，已跳过。')

    for name, body in components:
        if body is None:
            builder.note('%s 创建失败，已跳过。' % name)
            continue
        element = _body_to_element(body, dgn_model, name)
        if element is None:
            builder.note('%s 转为元素失败，已跳过。' % name)
            continue
        builder.add(element)

    builder.build()
    return builder, built, bl


def _attach_items(cell, result):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('clamp_number', ''),
        assembly_spec='DN%d' % result['dn'],
        components=result.get('bom_items', ()),
    )


def replace_clamp(layout, frame, build_pipe, build_insulation,
                  previous_handle):
    dgn_model = ISessionMgr.GetActiveDgnModel()
    builder, built, bl = _build_clamp_cell(layout, frame, build_pipe,
                                           build_insulation, dgn_model)
    new_handle = builder.commit()
    result = _build_result(layout, builder, built, bl)
    _attach_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def _build_result(layout, builder, built, bl):
    loads = geom.allowable_loads(layout.dn)
    ear = '%.0f×%.0f×%.0f' % (layout.ear_width, layout.ear_height,
                              layout.ear_thickness)
    group_count = len(bl.ear_center_x)
    clamp_length = bl.clamp_length_mm
    post_items = []
    if built.get('pipe'):
        post_items.append({'code': 'Pipe', 'name': '管道',
                           'specification': 'OD%.1f' % layout.od_mm,
                           'length': clamp_length})
    if built.get('insulation'):
        post_items.append({'code': 'Insulation', 'name': '保温层',
                           'specification': 'B=%.0f' % layout.insulation_mm,
                           'length': clamp_length})
    post_items += [
        {'code': 'ClampUpper', 'name': '承重板（上半）',
         'specification': 'T3=%.0f' % layout.t3,
         'length': clamp_length},
        {'code': 'ClampLower', 'name': '承重板（下半）',
         'specification': 'T3=%.0f' % layout.t3,
         'length': clamp_length},
        {'code': 'Base', 'name': '管夹底座',
         'specification': 'W=%.0f / T2=%.0f' % (layout.base_width, layout.t2),
         'length': clamp_length},
        {'code': 'Ear', 'name': '耳板', 'specification': ear,
         'quantity': 4 * group_count},
        {'code': 'Bolt', 'name': '螺栓',
         'specification': layout.bolt_dia, 'length': layout.bolt_length_mm,
         'quantity': 2 * group_count},
    ]
    return {
        'dn': layout.dn, 'nps': layout.nps, 'od_mm': layout.od_mm,
        'height': layout.height_mm, 'length': layout.shoe_length_mm,
        'insulation': layout.insulation_mm,
        'clamp_outer_radius': layout.clamp_outer_radius,
        'base_width': layout.base_width,
        'middle_rib': layout.has_middle_rib,
        'child_count': builder.child_count,
        'pipe_built': bool(built.get('pipe')),
        'insulation_built': bool(built.get('insulation')),
        'allowable_loads': loads,
        'warnings': list(builder.warnings),
        'bom_items': post_items,
    }


def _delete_preview(handle):
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def export_bom_json(output_path=None):
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '保温管夹_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 所选管道轴线
# ---------------------------------------------------------------------------


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _collect_linear_pieces(curve_vector, pieces):
    for primitive in curve_vector:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
            segment = primitive.GetLine()
            pieces.append([_copy_dpoint(segment.StartPoint),
                           _copy_dpoint(segment.EndPoint)])
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
            points = [_copy_dpoint(point) for point in primitive.GetLineString()]
            if len(points) >= 2:
                pieces.append(points)
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
            child = primitive.GetChildCurveVector()
            if child is None:
                raise ValueError('所选元素含无法读取的子路径。')
            _collect_linear_pieces(child, pieces)
        else:
            raise ValueError('所选元素含圆弧或曲线；请选择一条直线段。')


def extract_pipe_axis(element_handle):
    """提取所选直线段（管道轴线），返回 ``(p0_mm, p1_mm)``。"""
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条直线段（管道轴线）。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if not pieces:
        raise ValueError('未取到有效线段。')
    points = pieces[0]
    return (_point_to_mm(points[0], uor_per_mm),
            _point_to_mm(points[-1], uor_per_mm))


def _project_onto_axis(point_mm, p0_mm, p1_mm):
    d = (p1_mm[0] - p0_mm[0], p1_mm[1] - p0_mm[1], p1_mm[2] - p0_mm[2])
    length2 = _dot(d, d)
    if length2 <= 1.0e-9:
        return p0_mm
    t = _dot((point_mm[0] - p0_mm[0], point_mm[1] - p0_mm[1],
              point_mm[2] - p0_mm[2]), d) / length2
    return (p0_mm[0] + t * d[0], p0_mm[1] + t * d[1], p0_mm[2] + t * d[2])


def _axis_midpoint(p0_mm, p1_mm):
    return ((p0_mm[0] + p1_mm[0]) / 2.0, (p0_mm[1] + p1_mm[1]) / 2.0,
            (p0_mm[2] + p1_mm[2]) / 2.0)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _ClampSettingsDialog(GlassDialog):
    """DN / B / L / 编号 / 创建选项 + 预览；点选轴线后自动重建。"""

    STATE_KEY = 'InsulatedClamp'
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.axis = None
        self.center = None
        self.axis_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        # 原生回调（点选）只把 (元素 ID, 点击点) 入队；EC 读取在主循环
        # PythonMainLoop 返回之后进行（在回调里读 EC 会让 OPM 崩溃）。
        self.pending = []
        # 本次点选确定的管径 / 保温厚度：None 表示用面板输入值。
        self._active_dn = None
        self._active_insulation = None
        self._pick_note = ''
        # 原生回调只写普通 Python 状态；Tk 刷新由常驻定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._pending_preview = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False

        self._dn = tk.StringVar()
        self._insulation = tk.StringVar(value='%.0f' % DEFAULT_INSULATION_MM)
        self._length = tk.StringVar(value='%.0f' % DEFAULT_LENGTH_MM)
        self._name = tk.StringVar(value='T4')
        self._temp = tk.StringVar(value='')
        self._material = tk.StringVar(value='')
        self._fcode = tk.StringVar(value='')
        self._od = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._spec = tk.StringVar(value='—')
        self._height = tk.StringVar(value='—')
        self._clamp_od = tk.StringVar(value='—')
        self._number = tk.StringVar(value='—')
        self._pipe = tk.BooleanVar(value=False)
        self._build_insulation = tk.BooleanVar(value=False)
        self._keep = tk.BooleanVar(value=True)
        self._dn_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        try:
            # 竖长（类手机）比例：窄而高。
            self.minsize(430, 760)
        except tk.TclError:
            pass
        _log('panel built rev=%s file=%s'
             % (UI_REVISION, os.path.abspath(__file__)))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        shell = self.build_shell(
            UI_TITLE,
            '点选管道轴线取方向，在轴上点取放置点（管托 L 中心）')
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(shell, bg=CARD, height=430)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(1, weight=1)

        hint_frame, hint_text = self._text_field(body, height=3)
        hint_frame.grid(row=0, column=0, columnspan=2, sticky='ew')
        self._set_text(hint_text, (
            '点选一根管道或一条直线段，在点击处沿其轴线放置管夹（= 管托 L 中心；'
            '未点取到点时用线中点）。选中管道自动读取公称直径 / 保温厚度；'
            '选中直线段或读不到管道属性时，改用面板输入的 DN / B。'
            'DN80~600；管夹本体 = 外圆柱 − 内圆柱 − 45° 对开贯穿体，底座 = '
            '底板 + 弧顶支撑 + 中央腹板；管道 / 保温层可选（默认不建）。'))

        ttk.Label(body, text='管径（表 1，DN80~600）',
                  style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(6, 2))
        ttk.Label(body, text='管径', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=3)
        dn_labels = []
        for dn, label in geom.dn_choices():
            dn_labels.append(label)
            self._dn_by_label[label] = dn
        self._dn_combo = ttk.Combobox(
            body, textvariable=self._dn, state='readonly', width=24,
            style='Glass.TCombobox', values=dn_labels)
        self._dn_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=3)
        self._dn_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(body, text='外径 OD', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._od, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=3, column=1, sticky='w', padx=(10, 0), pady=3)
        ttk.Label(body, text='允许荷载', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._load, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=3)
        ttk.Label(body, text='螺栓 / T1 / T2 / T3',
                  style='GlassMuted.TLabel').grid(
            row=5, column=0, sticky='nw', pady=3)
        tk.Label(body, textvariable=self._spec, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left').grid(
            row=5, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=6, column=0, columnspan=2, sticky='ew', pady=6)
        ttk.Label(body, text='尺寸参数', style='Section.TLabel').grid(
            row=7, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(body, text='隔热层厚度 B', style='GlassMuted.TLabel').grid(
            row=8, column=0, sticky='nw', pady=3)
        b_holder = tk.Frame(body, bg=CARD)
        b_holder.grid(row=8, column=1, sticky='w', padx=(10, 0), pady=3)
        b_input = tk.Frame(b_holder, bg=CARD)
        b_input.pack(anchor='w')
        self._insulation_entry = self._entry(b_input, self._insulation, 9)
        tk.Label(b_holder, text='mm　管夹内孔按 B 放大；H 由 B 查表', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(body, text='H', style='GlassMuted.TLabel').grid(
            row=9, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._height, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=9, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(body, text='L', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='nw', pady=3)
        l_holder = tk.Frame(body, bg=CARD)
        l_holder.grid(row=10, column=1, sticky='w', padx=(10, 0), pady=3)
        l_input = tk.Frame(l_holder, bg=CARD)
        l_input.pack(anchor='w')
        self._length_entry = self._entry(l_input, self._length, 9)
        tk.Label(l_holder, text='mm　管托沿管轴总长（≥300）', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(body, text='管夹外径', style='GlassMuted.TLabel').grid(
            row=11, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._clamp_od, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=11, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=12, column=0, columnspan=2, sticky='ew', pady=6)
        ttk.Label(body, text='管架编号（T4）', style='Section.TLabel').grid(
            row=13, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(body, text='名称', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='nw', pady=3)
        name_holder = tk.Frame(body, bg=CARD)
        name_holder.grid(row=14, column=1, sticky='w', padx=(10, 0), pady=3)
        name_input = tk.Frame(name_holder, bg=CARD)
        name_input.pack(anchor='w')
        self._name_entry = self._entry(name_input, self._name, 10)
        tk.Label(name_holder, text='管架系列代号；留空则不附加编号', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(body, text='温度代码', style='GlassMuted.TLabel').grid(
            row=15, column=0, sticky='w', pady=3)
        temp_row = tk.Frame(body, bg=CARD)
        temp_row.grid(row=15, column=1, sticky='w', padx=(10, 0), pady=3)
        self._temp_entry = self._entry(temp_row, self._temp, 10)

        ttk.Label(body, text='材料代码', style='GlassMuted.TLabel').grid(
            row=16, column=0, sticky='w', pady=3)
        material_row = tk.Frame(body, bg=CARD)
        material_row.grid(row=16, column=1, sticky='w', padx=(10, 0), pady=3)
        self._material_entry = self._entry(material_row, self._material, 10)

        ttk.Label(body, text='F(注11)', style='GlassMuted.TLabel').grid(
            row=17, column=0, sticky='nw', pady=3)
        f_holder = tk.Frame(body, bg=CARD)
        f_holder.grid(row=17, column=1, sticky='w', padx=(10, 0), pady=3)
        f_input = tk.Frame(f_holder, bg=CARD)
        f_input.pack(anchor='w')
        self._f_entry = self._entry(f_input, self._fcode, 10)
        tk.Label(f_holder, text='按图注 11 填；留空则不附加', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(body, text='编号', style='GlassMuted.TLabel').grid(
            row=18, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left').grid(
            row=18, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=19, column=0, columnspan=2, sticky='ew', pady=6)
        ttk.Label(body, text='创建选项', style='Section.TLabel').grid(
            row=20, column=0, columnspan=2, sticky='w', pady=(0, 2))
        self._pipe_check = tk.Checkbutton(
            body, text='创建管道本体', variable=self._pipe, bg=CARD, fg=INK,
            activebackground=CARD, selectcolor=CARD, font=UI_FONT,
            highlightthickness=0, bd=0)
        self._pipe_check.grid(row=21, column=0, columnspan=2, sticky='w')
        self._insulation_check = tk.Checkbutton(
            body, text='创建保温层', variable=self._build_insulation, bg=CARD,
            fg=INK, activebackground=CARD, selectcolor=CARD, font=UI_FONT,
            highlightthickness=0, bd=0)
        self._insulation_check.grid(row=22, column=0, columnspan=2, sticky='w')
        self._keep_check = tk.Checkbutton(
            body, text='保留所选轴线', variable=self._keep, bg=CARD, fg=INK,
            activebackground=CARD, selectcolor=CARD, font=UI_FONT,
            highlightthickness=0, bd=0)
        self._keep_check.grid(row=23, column=0, columnspan=2, sticky='w')

        # 预览 / 状态固定在滚动区下方，始终可见。
        info = tk.Frame(shell, bg=CARD)
        info.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self._preview_frame, self._preview_text = self._text_field(info, height=3)
        self._preview_frame.pack(fill='x')
        self._status_frame, self._status_text = self._text_field(info, height=3)
        self._status_frame.pack(fill='x', pady=(4, 0))
        self._set_text(self._preview_text, '预览：—')
        self._set_text(self._status_text,
                       '请在模型中点选一条管道轴线；改参数会自动重建预览。')

        buttons = tk.Frame(shell, bg=CARD)
        buttons.grid(row=2, column=0, sticky='ew', pady=(8, 0))
        self.confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button = RoundButton(
            buttons, '导出 JSON 清单', self.export_bom, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button.pack(side='left')
        self.confirm_button.pack(side='right')
        self.cancel_button.pack(side='right', padx=(0, 8))

        self._insulation.trace_add('write', self._on_insulation_changed)
        self._length.trace_add('write', self.on_text_changed)
        self._name.trace_add('write', self.on_text_changed)
        self._temp.trace_add('write', self.on_text_changed)
        self._material.trace_add('write', self.on_text_changed)
        self._fcode.trace_add('write', self.on_text_changed)
        self._bind_wheel(self._scroll)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        return entry

    def _text_field(self, parent, height=3):
        frame = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
        text = tk.Text(
            frame, height=height, width=36, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=5, cursor='arrow', takefocus=0)
        bar = SlimScrollbar(frame, command=text.yview, trough=CARD_SOFT)
        text.configure(yscrollcommand=bar.set)
        text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        text.configure(state='disabled')
        return frame, text

    def _set_text(self, text_widget, value):
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', value or '')
            text_widget.configure(state='disabled')
            text_widget.yview_moveto(0.0)
        except tk.TclError:
            pass

    def _bind_wheel(self, scroll):
        def on_wheel(event):
            scroll.scroll_units(-1 if event.delta > 0 else 1)
            return 'break'

        def walk(widget):
            if isinstance(widget, tk.Text):
                return
            widget.bind('<MouseWheel>', on_wheel)
            for child in widget.winfo_children():
                walk(child)
        walk(scroll)

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = None
        fallback = None
        for label, dn in self._dn_by_label.items():
            if fallback is None:
                fallback = label
            if dn == DEFAULT_DN:
                fallback = label
            if dn == state.get('dn'):
                selected = label
        self._dn.set(selected or fallback)
        for key, variable in (('insulation', self._insulation),
                              ('length', self._length),
                              ('name', self._name),
                              ('temp', self._temp),
                              ('material', self._material),
                              ('fcode', self._fcode)):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                variable.set(value)
        for key, variable in (('pipe', self._pipe),
                              ('build_insulation', self._build_insulation),
                              ('keep', self._keep)):
            if isinstance(state.get(key), bool):
                variable.set(state.get(key))
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['dn'] = self.current_dn()
            state['insulation'] = self._insulation.get()
            state['length'] = self._length.get()
            state['name'] = self._name.get()
            state['temp'] = self._temp.get()
            state['material'] = self._material.get()
            state['fcode'] = self._fcode.get()
            state['pipe'] = bool(self._pipe.get())
            state['build_insulation'] = bool(self._build_insulation.get())
            state['keep'] = bool(self._keep.get())
        except tk.TclError:
            pass

    # -- 取值 --------------------------------------------------------------

    def current_dn(self):
        if self._active_dn is not None:
            return self._active_dn
        return self._dn_by_label.get(self._dn.get(), DEFAULT_DN)

    def _float(self, variable, fallback):
        try:
            return float((variable.get() or '').strip())
        except (TypeError, ValueError):
            return fallback

    def current_insulation(self):
        if self._active_insulation is not None:
            return self._active_insulation
        return self._float(self._insulation, DEFAULT_INSULATION_MM)

    def current_height(self):
        # H 由保温厚度 B 查表决定，不作为独立输入。
        return geom.height_for_insulation(self.current_insulation())

    def current_length(self):
        return self._float(self._length, DEFAULT_LENGTH_MM)

    def current_layout(self):
        return geom.build_layout(
            self.current_dn(), self.current_insulation(),
            self.current_height(), self.current_length(),
            clamp_width_mm=geom.DEFAULT_CLAMP_WIDTH_MM)

    def current_number(self, layout=None):
        layout = layout if layout is not None else (
            self.current_layout() if self.axis is not None else None)
        if layout is None:
            return ''
        return geom.build_clamp_number(
            self._name.get(), layout.dn, self._temp.get(),
            layout.height_mm, layout.shoe_length_mm,
            self._material.get(), self._fcode.get())

    # -- 显示 --------------------------------------------------------------

    def refresh_spec(self):
        dn = self.current_dn()
        row = geom.get_row(dn)
        self._od.set('%.1f' % row['od_mm'])
        self._spec.set('%s　T1=%.0f / T2=%.0f / T3=%.0f'
                       % (row['bolt_dia'], row['T1'], row['T2'], row['T3']))
        loads = geom.allowable_loads(dn)
        self._load.set('%.0f / %.0f / %.0f' % (loads[0], loads[1], loads[2]))
        try:
            self._height.set('%.0f' % self.current_height())
        except ValueError:
            self._height.set('—')
        try:
            layout = self.current_layout()
            self._clamp_od.set('%.1f' % (2.0 * layout.clamp_outer_radius))
            number = self.current_number(layout)
        except ValueError as error:
            self._clamp_od.set('—')
            self._number.set('—')
            self.set_status('参数有误：%s' % error, True)
            return
        self._number.set(number if number else '（名称留空，不附加）')

    def _apply_status(self, message, is_error=False):
        self._set_text(getattr(self, '_status_text', None), message)

    def set_status(self, message, is_error=False, flush=True):
        # 只登记；由 poll 定时器统一刷进控件（原生回调调用时也安全）。
        self._pending_message = message
        self._pending_is_error = bool(is_error)

    def _preview_text_for(self, result):
        loads = result['allowable_loads']
        return ("预览：DN%d（%s），OD %.1f，B=%.0f，H=%.0f，L=%.0f，管夹外径 "
                "%.1f，底板宽 %.0f%s；单元含 %d 个子元素，管道%s / 保温层%s；"
                "允许荷载 %.0f/%.0f/%.0f kN。"
                % (result['dn'], result['nps'], result['od_mm'],
                   result['insulation'], result['height'], result['length'],
                   result['clamp_outer_radius'], result['base_width'],
                   '（含中间肋板）' if result['middle_rib'] else '',
                   result['child_count'],
                   '已建' if result['pipe_built'] else '未建',
                   '已建' if result['insulation_built'] else '未建',
                   loads[0], loads[1], loads[2]))

    # -- 事件 --------------------------------------------------------------

    def on_options_changed(self, event=None):
        # 用户改管径：切回面板参数（不再沿用上一次所选管道的信息）。
        self._active_dn = None
        self._active_insulation = None
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _on_insulation_changed(self, *_args):
        # 用户改保温厚度：只清掉保温覆盖，管径仍可沿用所选管道。
        self._active_insulation = None
        self.on_text_changed()

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay_ms):
        self._cancel_pending_regeneration()
        if self.axis is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    # -- UI 刷新：只允许在这个 Tk 定时器里碰控件 ---------------------------

    def _start_poll(self):
        try:
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None

    def _poll_ui(self):
        self._poll_job = None
        try:
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.shutdown()
                return
            if self._cancel_requested:
                self._cancel_requested = False
                self.cancel_tool()
                return
            if (self._regen_deadline is not None
                    and time.monotonic() >= self._regen_deadline):
                self._regen_deadline = None
                self.regenerate()
            self._flush_ui()
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None

    def _flush_ui(self):
        try:
            if self._pending_preview is not None:
                result = self._pending_preview
                message = self._pending_message or ''
                is_error = self._pending_is_error
                self._pending_preview = None
                self._pending_message = None
                self._pending_is_error = False
                self.refresh_spec()
                self._set_text(self._preview_text,
                               self._preview_text_for(result))
                self._apply_status(message, is_error)
            elif self._pending_message is not None:
                message = self._pending_message
                is_error = self._pending_is_error
                self._pending_message = None
                self._pending_is_error = False
                self._apply_status(message, is_error)
        except tk.TclError:
            pass

    def request_cancel(self):
        self._cancel_requested = True

    def request_shutdown(self):
        self._shutdown_requested = True

    # -- 点选队列（EC 读取在主循环 PythonMainLoop 返回之后） ----------------

    def queue_pick(self, element_id, click_uor):
        self.pending.append((element_id, click_uor))

    def _run_pending(self):
        pending, self.pending = self.pending, []
        for element_id, click_uor in pending:
            self._process(element_id, click_uor)

    def _process(self, element_id, click_uor):
        # 已不在工具回调内（PythonMainLoop 返回之后），可安全读取 EC。
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
        except Exception as error:
            _log_exception('read pipe info failed')
            self.set_status('读取管道信息失败：%s' % error, True)
            return
        start = placement.get('start_mm')
        end = placement.get('end_mm')
        axis = placement.get('axis')
        if not start or not end or axis is None:
            self.set_status('该元素没有可用的轴线，无法定位管夹；'
                            '请点选管道或一条直线段。', True)
            return
        if click_uor is not None:
            uor_per_mm = _uor_per_mm()
            click_mm = tuple(value / uor_per_mm for value in click_uor)
            center = _project_onto_axis(click_mm, start, end)
        else:
            center = placement.get('center_mm') or _axis_midpoint(start, end)

        dn, insulation, note = self._resolve_source(placement)
        self._active_dn = dn
        self._active_insulation = insulation
        self._pick_note = note
        self.regenerate(axis, center, handle)

    def _resolve_source(self, placement):
        """决定本次点选用管道信息还是面板参数，返回 ``(dn, B, 说明)``。"""
        is_pipe = bool((((placement.get('snapshot') or {}).get('ec') or {})
                        .get('found')))
        if not is_pipe:
            return (None, None,
                    '按面板参数：DN%d、B=%.1f。'
                    % (self._panel_dn(), self._panel_insulation()))
        nominal = placement.get('nominal_diameter_mm')
        matched = _match_dn(nominal)
        insulation = placement.get('insulation_thickness_mm')
        notes = []
        if matched is not None:
            notes.append('管道公称直径 %.1f mm' % nominal)
        else:
            notes.append('管道公称直径 %s 未匹配表 1，DN 用面板值'
                         % ('未知' if nominal is None else '%.1f mm' % nominal))
        if insulation is None:
            notes.append('未读到保温厚度，B 用面板值')
        else:
            notes.append('保温厚度 %.1f mm' % insulation)
        return (matched,
                (float(insulation) if insulation is not None else None),
                '按管道：' + '、'.join(notes) + '。')

    def _panel_dn(self):
        return self._dn_by_label.get(self._dn.get(), DEFAULT_DN)

    def _panel_insulation(self):
        return self._float(self._insulation, DEFAULT_INSULATION_MM)

    def run_dialog_loop(self):
        """Tk 主循环：UI 事件 + MicroStation；EC 读取放在 PythonMainLoop 之后。"""
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.finish_tool()
                break
            if self._cancel_requested:
                self._cancel_requested = False
                self.cancel_tool()
                break
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception:
                _log_exception('PythonMainLoop failed')
                break
            self._run_pending()

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, axis=None, center=None, handle=None):
        """按当前轴线与参数重建预览；只做 Bentley 建模，UI 刷新交给定时器。"""
        self._cancel_pending_regeneration()
        if axis is not None:
            self.axis = axis
            self.center = center
            self.axis_handle = handle
        if self.axis is None or self.center is None:
            return None

        try:
            layout = self.current_layout()
        except ValueError as error:
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None

        try:
            frame = _frame(self.axis, self.center)
            handle, result, deleted = replace_clamp(
                layout, frame, self._pipe.get(),
                self._build_insulation.get(), self.preview_handle)
        except Exception as error:
            message = '保温管夹生成失败：%s' % error
            if isinstance(error, ValueError):
                _log('preview rejected: %s' % error)
            else:
                _log_exception('preview failed')
            self._pending_message = message
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            return None

        self.preview_handle = handle
        self.preview_result = result
        message = ('预览已更新：DN%d，H=%.0f，L=%.0f，%s。改参数会自动重建；'
                   '点【确定】保留，点【取消】放弃。'
                   % (result['dn'], result['height'], result['length'],
                      '已替换上一版预览' if deleted else '已生成'))
        if self._pick_note:
            message = self._pick_note + message
            self._pick_note = ''
        if result['warnings']:
            message = ('注意：%s；' % '；'.join(result['warnings'])) + message
        self._pending_preview = result
        self._pending_message = message
        self._pending_is_error = False
        try:
            NotificationManager.OutputPrompt(message)
        except Exception:
            pass
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def delete_source_line(self):
        handle = self.axis_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                return True
        except Exception:
            _log_exception('delete source line failed')
        return False

    def export_bom(self):
        output_path = export_bom_json()
        if output_path is not None:
            self.set_status('清单已导出：%s' % output_path)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        if self.preview_handle is not None and not self._keep.get():
            self.delete_source_line()
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 交互工具：点选管道轴线 + 指定点
# ---------------------------------------------------------------------------


class InsulatedClampTool(DgnElementSetTool):
    """点选**管道或直线段**，在点击处沿其轴线放置保温管夹。

    选中管道时自动读取公称直径 / 保温厚度；选中普通直线段（或读不到管道属性）
    时改用面板输入的 DN / 保温厚度。``_OnPostLocate`` 只记元素 ID；
    ``_OnDataButton`` 只把 (元素 ID, 点击点) 交给面板排队——回调内不做 EC 读取。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('InsulatedClampTool')

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
        NotificationManager.OutputPrompt(
            '请点选一根管道或一条直线段：在点击处沿其轴线放置保温管夹。'
            '右键放弃。')
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
            click_uor = (point.x, point.y, point.z)
        except Exception:
            click_uor = None
        self.panel.queue_pick(element_id, click_uor)
        return True

    def _OnResetButton(self, event):
        settings = self.panel
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnRestartTool(self):
        panel = self.panel
        self.panel = None
        InsulatedClampTool.InstallNewInstance(self.GetToolId(), panel, False)

    def _OnCleanup(self):
        settings = self.panel
        if settings is None:
            return
        self.panel = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_ui_loop=True):
        settings = panel if panel is not None else _ClampSettingsDialog()
        tool = InsulatedClampTool(tool_id, settings)
        tool.InstallTool()
        if start_ui_loop:
            settings.run_dialog_loop()
        return tool


_active_settings = None


def show_clamp_dialog():
    """打开保温管夹面板；已在运行时只把已有窗口提到前台，避免重复窗口残留。"""
    global _active_settings
    if _active_settings is not None:
        try:
            if _active_settings.winfo_exists():
                _active_settings.lift()
                return None
        except tk.TclError:
            pass
    settings = _ClampSettingsDialog()
    _active_settings = settings
    try:
        return InsulatedClampTool.InstallNewInstance(0, settings, True)
    finally:
        _active_settings = None


def export_clamp_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYCLAMP PLACE / PYCLAMP EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '保温管夹.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenInsulatedClamp():
    PyMain()


def ExportInsulatedClampBom():
    export_clamp_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _log('PyMain: entry rev=%s' % UI_REVISION)
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_clamp_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('clamp tool start failed')
        print('保温管夹插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '保温管夹启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
