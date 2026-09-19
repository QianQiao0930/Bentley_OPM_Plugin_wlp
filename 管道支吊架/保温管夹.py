# -*- coding: utf-8 -*-
"""保温管夹（高温隔热限位管托，图集 T4）放置工具 —— DN80~600。

在模型中**点选一条管道轴线**取方向，并在**指定点**（= 管托 L 的中心，取点取
位置投影到轴线；取不到时用线中点）放置一组保温管夹：

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
import math
import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

from PyQt5.QtCore import QEvent, QEventLoop, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                             QVBoxLayout, QWidget)


HERE = os.path.dirname(os.path.abspath(__file__))
# 公共库在 模块/公共/，本插件几何在 模块/保温管夹/。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '保温管夹')
for _path in (COMMON_DIR, GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 端焊三角架_基础 as base  # noqa: E402
import 保温管夹_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


SUPPORT_TYPE = '保温管夹'
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
UI_TITLE = '保温管夹（高温隔热限位管托）'
UI_REVISION = 'point-select-1'

DEFAULT_DN = 200
DEFAULT_INSULATION_MM = 50.0
DEFAULT_HEIGHT_MM = geom.height_for_insulation(DEFAULT_INSULATION_MM)
DEFAULT_LENGTH_MM = 300.0

base.DEBUG_LOG = DEBUG_LOG
_log = base._log


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _apply_base_overrides():
    base.DEBUG_LOG = DEBUG_LOG


def _reload_runtime_modules():
    importlib.invalidate_caches()
    for module in (geom, psb, base):
        try:
            importlib.reload(module)
        except Exception:
            pass
    _apply_base_overrides()


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _point_to_mm(point, uor_per_mm):
    return (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)


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


class _ClampTitleBar(QWidget):
    def __init__(self, title, on_close, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._drag_offset = None
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 0, 10, 0)
        row.setSpacing(9)
        dot = QLabel(self)
        dot.setFixedSize(9, 9)
        dot.setStyleSheet('background: #4A66E0; border-radius: 4px;')
        dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        caption = QLabel(title, self)
        caption.setStyleSheet('font-size: 14px; font-weight: 600;'
                              ' color: #39435A;')
        caption.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(dot)
        row.addWidget(caption)
        row.addStretch(1)
        row.addWidget(base.NeuIconButton(self, 'close', on_close, danger=True))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (event.globalPos()
                                 - self.window().frameGeometry().topLeft())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class _ClampSettingsDialog(QWidget):
    RADIUS = base.UI_RADIUS

    def __init__(self):
        self._app = base.ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, base.UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self.axis = None
        self.center = None
        self.axis_handle = None
        self.preview_handle = None
        self.confirmed = False
        self.option_widgets = []
        self._running = True
        self._allow_close = False
        self._finish_requested = False
        self._event_loop = QEventLoop()

        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(base.REGENERATE_DELAY_MS)
        self._regen_timer.timeout.connect(self._run_pending_regeneration)
        self._text_timer = QTimer(self)
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(base.TEXT_REGENERATE_DELAY_MS)
        self._text_timer.timeout.connect(self._run_pending_regeneration)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_ClampTitleBar(UI_TITLE, self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel(
            "点选管道轴线取方向，在轴上点取放置点（= 管托 L 中心；未点取用线中点）。"
            "DN80~600；管夹本体 = 外圆柱 − 内圆柱 − 45° 对开贯穿体，底座 = 底板 + "
            "弧顶支撑 + 中央腹板；管道 / 保温层可选（默认不建）。"
            "改参数自动重建预览，点【确定】保留、点【取消】放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(3)

        card = base.NeuCard("管径（表 1，DN80~600）", margin_y=2, padding=6)
        self.dn_combo = self._register(base.NeuCombo(
            list(geom.dn_choices()), current=DEFAULT_DN,
            on_change=self.on_options_changed))
        self._row(card.content, 0, "管径：", [self.dn_combo], 16)
        self.od_label = self._value()
        self.load_label = self._value()
        self._pair(card.content, 1, 0, "外径 OD：",
                   [self.od_label, self._note("mm")])
        self._pair(card.content, 1, 2, "允许荷载：",
                   [self.load_label, self._note("kN 垂直/横向/轴向")])
        self.spec_label = self._value()
        self._row(card.content, 2, "螺栓 / T1 / T2 / T3：", [self.spec_label])
        body.addWidget(card)

        card = base.NeuCard("尺寸参数", margin_y=2, padding=6)
        self.insulation_edit = self._edit('%.0f' % DEFAULT_INSULATION_MM)
        self.height_label = self._value()
        self._pair(card.content, 0, 0, "隔热层厚度 B：",
                   [self.insulation_edit, self._note("mm")])
        self._pair(card.content, 0, 2, "H：",
                   [self.height_label, self._note("mm 由 B 查表")])
        self.length_edit = self._edit('%.0f' % DEFAULT_LENGTH_MM)
        self.clamp_od_label = self._value()
        self._pair(card.content, 1, 0, "L：",
                   [self.length_edit, self._note("mm ≥300")])
        self._pair(card.content, 1, 2, "管夹外径：",
                   [self.clamp_od_label, self._note("mm = OD+2B+2t")])
        body.addWidget(card)

        card = base.NeuCard("管架编号（T4）", margin_y=2, padding=6)
        self.name_edit = self._edit('T4')
        self.temp_edit = self._edit('')
        self._pair(card.content, 0, 0, "名称：", [self.name_edit])
        self._pair(card.content, 0, 2, "温度代码：", [self.temp_edit])
        self.material_edit = self._edit('')
        self.f_edit = self._edit('')
        self._pair(card.content, 1, 0, "材料代码：", [self.material_edit])
        self._pair(card.content, 1, 2, "F(注11)：", [self.f_edit])
        self.number_label = self._value()
        self._row(card.content, 2, "编号：", [self.number_label])
        body.addWidget(card)

        card = base.NeuCard("创建选项", margin_y=2, padding=6)
        self.pipe_toggle = self._register(base.NeuToggle("创建管道本体"))
        self.pipe_toggle.setChecked(False)
        self.insulation_toggle = self._register(base.NeuToggle("创建保温层"))
        self.insulation_toggle.setChecked(False)
        self.keep_toggle = self._register(base.NeuToggle("保留所选轴线"))
        self.keep_toggle.setChecked(True)
        card.content.addWidget(self.pipe_toggle, 0, 0)
        card.content.addWidget(self.insulation_toggle, 0, 1)
        card.content.addWidget(self.keep_toggle, 0, 2)
        body.addWidget(card)

        summary = base.NeuPanel(margin=1, padding=7)
        self.preview_info_label = self._info("预览：—", base.UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点选一条管道轴线；改参数会自动重建预览。", base.UI_INFO)
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.cancel_button = base.NeuButton("取消", margin_y=7)
        self.cancel_button.setFixedWidth(118)
        self.cancel_button.clicked.connect(self.cancel_tool)
        self.export_button = base.NeuButton("导出 JSON 清单", margin_y=7)
        self.export_button.setFixedWidth(142)
        self.export_button.clicked.connect(self.export_bom)
        self.confirm_button = base.NeuButton("确定", accent=True, margin_y=7)
        self.confirm_button.setFixedWidth(118)
        self.confirm_button.clicked.connect(self.confirm_tool)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.confirm_button)
        body.addLayout(button_row)
        self.action_widgets = [
            self.confirm_button, self.cancel_button, self.export_button]

        self.refresh_spec()
        self.setMinimumWidth(580)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        self.hwnd = int(self.winId())
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)

    # -- 控件 --------------------------------------------------------------

    def _register(self, widget):
        self.option_widgets.append(widget)
        return widget

    def _row(self, grid, row, name, widgets, spacing=18):
        label = QLabel(name, self)
        label.setStyleSheet('color: #39435A; font-size: 13px;')
        grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        holder = QWidget(self)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(spacing)
        for widget in widgets:
            line.addWidget(widget)
        line.addStretch(1)
        grid.addWidget(holder, row, 1)
        grid.setColumnStretch(1, 1)
        return holder

    def _pair(self, grid, row, col, name, widgets, spacing=10):
        """两列紧凑布局：在第 ``col`` / ``col+1`` 列放一组「标签 : 控件」。"""
        label = QLabel(name, self)
        label.setStyleSheet('color: #39435A; font-size: 13px;')
        grid.addWidget(label, row, col, Qt.AlignLeft | Qt.AlignVCenter)
        holder = QWidget(self)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(spacing)
        for widget in widgets:
            line.addWidget(widget)
        line.addStretch(1)
        grid.addWidget(holder, row, col + 1)
        grid.setColumnStretch(col + 1, 1)
        return holder

    def _edit(self, value, width=84):
        field = base.NeuEdit(value, width=width)
        self._register(field.edit)
        field.edit.textChanged.connect(self.on_text_changed)
        return field

    def _value(self):
        label = QLabel('—', self)
        label.setStyleSheet('color: #39435A; font-size: 13px;'
                            ' font-weight: 600;')
        return label

    def _note(self, text):
        label = QLabel(text, self)
        label.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        return label

    def _info(self, text, color):
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet('color: %s; font-size: 11px;' % color.name())
        return label

    # -- 取值 --------------------------------------------------------------

    def current_dn(self):
        try:
            return int(self.dn_combo.value())
        except (TypeError, ValueError):
            return DEFAULT_DN

    def _float(self, field, fallback):
        try:
            return float(field.value())
        except (TypeError, ValueError):
            return fallback

    def current_insulation(self):
        return self._float(self.insulation_edit, DEFAULT_INSULATION_MM)

    def current_height(self):
        # H 由保温厚度 B 查表决定，不作为独立输入。
        return geom.height_for_insulation(self.current_insulation())

    def current_length(self):
        return self._float(self.length_edit, DEFAULT_LENGTH_MM)

    def current_width(self):
        # 管夹宽度已是旧参数、不再参与建模：保留默认值，仅为 build_layout 完整。
        return geom.DEFAULT_CLAMP_WIDTH_MM

    def current_layout(self):
        return geom.build_layout(
            self.current_dn(), self.current_insulation(),
            self.current_height(), self.current_length(),
            clamp_width_mm=self.current_width())

    def current_number(self, layout=None):
        layout = layout if layout is not None else (
            self.current_layout() if self.axis is not None else None)
        if layout is None:
            return ''
        return geom.build_clamp_number(
            self.name_edit.value(), layout.dn, self.temp_edit.value(),
            layout.height_mm, layout.shoe_length_mm,
            self.material_edit.value(), self.f_edit.value())

    # -- 显示 --------------------------------------------------------------

    def set_status(self, message, is_error=False, flush=True):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        if flush:
            QApplication.processEvents()

    def refresh_spec(self):
        dn = self.current_dn()
        row = geom.get_row(dn)
        self.od_label.setText('%.1f' % row['od_mm'])
        self.spec_label.setText('%s　T1=%.0f / T2=%.0f / T3=%.0f'
                                % (row['bolt_dia'], row['T1'], row['T2'],
                                   row['T3']))
        loads = geom.allowable_loads(dn)
        self.load_label.setText('%.0f / %.0f / %.0f'
                                % (loads[0], loads[1], loads[2]))
        try:
            self.height_label.setText('%.0f' % self.current_height())
        except ValueError:
            self.height_label.setText('—')
        try:
            layout = self.current_layout()
            self.clamp_od_label.setText('%.1f'
                                        % (2.0 * layout.clamp_outer_radius))
            number = self.current_number(layout)
        except ValueError as error:
            self.clamp_od_label.setText('—')
            self.number_label.setText('—')
            self.set_status('参数有误：%s' % error, True)
            return
        self.number_label.setText(number if number else '（名称留空，不附加）')

    def _set_busy(self, busy):
        for widget in self.option_widgets + self.action_widgets:
            widget.setEnabled(not busy)
        QApplication.processEvents()

    def on_options_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._regen_timer)

    def on_text_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._text_timer)

    def _schedule_regeneration(self, timer):
        self._cancel_pending_regeneration()
        if self.axis is None:
            return
        timer.start()

    def _cancel_pending_regeneration(self):
        self._regen_timer.stop()
        self._text_timer.stop()

    def _run_pending_regeneration(self):
        self.regenerate()

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, axis=None, center=None, handle=None):
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
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成保温管夹预览，请稍候……')
        try:
            frame = _frame(self.axis, self.center)
            handle, result, deleted = replace_clamp(
                layout, frame, self.pipe_toggle.isChecked(),
                self.insulation_toggle.isChecked(), self.preview_handle)
        except Exception as error:
            message = '保温管夹生成失败：%s' % error
            self.set_status(message, True)
            if isinstance(error, ValueError):
                _log('preview rejected: %s' % error)
            else:
                _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.refresh_spec()
        number = result.get('clamp_number') or \
            self.current_number() or '—'
        loads = result['allowable_loads']
        self.preview_info_label.setText(
            "预览：DN%d（%s），OD %.1f，B=%.0f，H=%.0f，L=%.0f，管夹外径 "
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
        message = ('预览已更新：DN%d，H=%.0f，L=%.0f，%s。%s'
                   '改参数会自动重建；点【确定】保留，点【取消】放弃。'
                   % (result['dn'], result['height'], result['length'],
                      '已替换上一版预览' if deleted else '已生成',
                      ('注意：%s；' % '；'.join(result['warnings']))
                      if result['warnings'] else ''))
        self.set_status(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
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
        if self.preview_handle is not None and not self.keep_toggle.isChecked():
            self.delete_source_line()
        self._finish_requested = True

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self._finish_requested = True

    def finish_tool(self):
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
        self.cancel_tool()

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
                self.finish_tool()
                continue
            PyCadInputQueue.PythonMainLoop()
        self._teardown_window()

    def _teardown_window(self):
        """退出事件泵后收尾：关闭窗口、冲刷重绘并延迟销毁，避免 UI 残留。

        无边框 + setMask 的自绘窗口若只 ``close()`` 不重绘，容易在屏幕上留下
        残影；顶层窗口不 ``deleteLater()`` 会一直驻留。这里显式处理。
        """
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            return
        # 冲刷一次隐藏 / 重绘事件，再安排销毁（避免残留的窗口像素）。
        QApplication.processEvents()
        try:
            self.deleteLater()
            # 这里只有 processEvents、没有 exec 主循环，DeferredDelete 需显式派发，
            # 否则顶层窗口不会被销毁而驻留（表现为 UI 残留）。
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        except (RuntimeError, TypeError):
            pass
        QApplication.processEvents()


# ---------------------------------------------------------------------------
# 交互工具：点选管道轴线 + 指定点
# ---------------------------------------------------------------------------


class InsulatedClampTool(DgnElementSetTool):
    """点选管道轴线，并在轴上指定点放置保温管夹。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None
        self._pick_uor = None

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
            '请点选一条管道轴线取方向，再在轴上点取放置点（= 管托 L 中心）。'
            '右键放弃。')

    def _OnDataButton(self, event):
        try:
            point = event.GetPoint()
            self._pick_uor = (point.x, point.y, point.z)
        except Exception:
            self._pick_uor = None
        try:
            return DgnElementSetTool._OnDataButton(self, event)
        except Exception:
            return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            p0_mm, p1_mm = extract_pipe_axis(eeh)
            axis = (p1_mm[0] - p0_mm[0], p1_mm[1] - p0_mm[1],
                    p1_mm[2] - p0_mm[2])
            if self._pick_uor is not None:
                uor_per_mm = _uor_per_mm()
                pick_mm = tuple(value / uor_per_mm for value in self._pick_uor)
                center = _project_onto_axis(pick_mm, p0_mm, p1_mm)
            else:
                center = _axis_midpoint(p0_mm, p1_mm)
            result = self.tool_settings.regenerate(axis, center, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '保温管夹生成失败：%s' % error
            self.tool_settings.set_status(message, True)
            if isinstance(error, ValueError):
                _log('element modify rejected: %s' % error)
            else:
                _log_exception('element modify failed')
            return BentleyStatus.eERROR

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            QTimer.singleShot(0, settings.cancel_tool)
        return True

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        InsulatedClampTool.InstallNewInstance(self.GetToolId(), settings,
                                              False)

    def _OnCleanup(self):
        settings = self.tool_settings
        if settings is None:
            return
        self.tool_settings = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        settings = (tool_settings if tool_settings is not None
                    else _ClampSettingsDialog())
        tool = InsulatedClampTool(tool_id)
        tool.tool_settings = settings
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
            if _active_settings._running:
                _active_settings.raise_()
                _active_settings.activateWindow()
                return None
        except RuntimeError:
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
            QMessageBox.critical(None, UI_TITLE, '启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
