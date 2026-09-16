# -*- coding: utf-8 -*-
"""端焊三角架（选线版）放置工具。

与 端焊三角架.py / end_welded_triangle_bracket.py 的区别：**不输入横担长度**，
而是在模型中点选一条用户绘制的**水平直线段**，该直线即横担**上翼缘上表面**
（也就是整组支架的最高点，横担整体向下展开）：

    起点 = 横担焊接端面的上表面中点（与既有钢结构的焊接面）
    终点 = 横担最远端的上表面中点
    直线长度 = 横担总长 L2
    直线方向（XY 平面内）= 横担方向，三角架随之旋转

直线两端的 Z 必须一致（要求水平）；Z 有变化时提示不合规并拒绝选取。

E 值仍需输入（默认 150 mm）：横担最远端至斜撑上端外侧斜角的距离。斜撑位置
由 E 反算：L1 = L2 − 肢宽×√2/2 − E，因此直线过短时同样会提示不合规。

整组构件（横担 + 斜撑）写成一个普通单元（Normal Cell），并附加 ItemType
清单属性；用户可选择创建后是否保留所选直线。

几何做法、单元封装、ItemType 与 PyQt5 面板全部沿用
end_welded_triangle_bracket.py（本文件只读引用，不修改它）。
"""

from __future__ import division

import importlib
import math
import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyECObjects import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEventLoop, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                             QVBoxLayout, QWidget)

import end_welded_triangle_bracket as base


def _reload_base(module):
    """每次运行都强制重新读取基础模块。

    MicroStation 的 Python 会话会把已导入的模块留在 sys.modules 里：改完
    end_welded_triangle_bracket.py 后只重跑本文件，拿到的仍是上一次的模块。
    这里显式重载，规避该缓存。
    """
    name = module.__name__
    try:
        return importlib.reload(module)
    except Exception:
        pass
    try:
        sys.modules.pop(name, None)
        return importlib.import_module(name)
    except Exception:
        return module


base = _reload_base(base)


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '端焊三角架_选线版_debug_log.txt')

UI_TITLE = '端焊三角架（选线版）'
UI_REVISION = 'line-select-1'

# 与其它端焊三角架工具区分开的 ItemType 前缀。
ITEM_TYPE_PREFIX = 'EndWeldedTriangleBracketByLineComponent'

# 直线两端 Z 的最大允许差值（mm）。超出即判定不水平并提示不合规。
HORIZONTAL_TOLERANCE_MM = 0.5

# 直线的最短有效长度（mm）：至少要放下斜撑与端部挑出。
MIN_LINE_LENGTH_MM = 50.0

VARIANTS = {
    'A': {
        'h_beam': (125.0, 125.0, 6.5, 9.0),
        'angle': (100.0, 10.0),
        'h_beam_specification': 'H125×125×6.5×9',
        'angle_specification': '∠100×10',
    },
    'B': {
        'h_beam': (150.0, 150.0, 7.0, 10.0),
        'angle': (125.0, 10.0),
        'h_beam_specification': 'H150×150×7×10',
        'angle_specification': '∠125×10',
    },
    'C': {
        'h_beam': (200.0, 200.0, 8.0, 12.0),
        'angle': (160.0, 12.0),
        'h_beam_specification': 'H200×200×8×12',
        'angle_specification': '∠160×12',
    },
    'D': {
        'h_beam': (250.0, 250.0, 9.0, 14.0),
        'angle': (200.0, 14.0),
        'h_beam_specification': 'H250×250×9×14',
        'angle_specification': '∠200×14',
    },
}

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'

# 交付给基础模块的覆盖项：子项表、构件名、ItemType 前缀与日志文件。
base.VARIANTS = VARIANTS
base.DEFAULT_VARIANT = 'A'
base.ITEM_TYPE_PREFIX = ITEM_TYPE_PREFIX
base.H_BEAM_COMPONENT_NAME = COMPONENT_A_NAME
base.ANGLE_COMPONENT_NAME = COMPONENT_B_NAME
base.CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET'
base.DEBUG_LOG = DEBUG_LOG

MIN_END_OVERHANG = base.MIN_END_OVERHANG
MAX_BEAM_LENGTH = base.MAX_BEAM_LENGTH
DEFAULT_VARIANT = base.DEFAULT_VARIANT
DEFAULT_END_OVERHANG = 150.0

_log = base._log


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _variant_label(variant_key):
    variant = VARIANTS[variant_key]
    return '%s  |  %s  |  %s' % (variant_key, variant['h_beam_specification'],
                                 variant['angle_specification'])


def describe_spec(variant_key):
    variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
    return ('横担 %s + 斜撑 %s；斜撑位置 L1 = L2 − %.1f×√2/2 − E，'
            '直线长 L2 ≤ %.0f mm。'
            % (variant['h_beam_specification'], variant['angle_specification'],
               variant['angle'][0], MAX_BEAM_LENGTH))


# ---------------------------------------------------------------------------
# 直线提取与校验
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
            raise ValueError('所选元素含圆弧或曲线；请选择一条水平直线段。')


def extract_horizontal_line(element_handle):
    """从所选元素提取一条水平直线段。

    返回 ``{'start_mm', 'end_mm', 'length_mm', 'heading_deg', 'z_mm'}``；
    两端 Z 差值超过 ``HORIZONTAL_TOLERANCE_MM`` 时抛 ValueError。
    """
    uor_per_mm = base._uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条开放的水平直线段。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if len(pieces) != 1:
        raise ValueError('请选择单条水平直线段（不要选折线或复杂链）。')
    piece = pieces[0]
    if len(piece) != 2:
        raise ValueError('请选择单条水平直线段（不要选折线或复杂链）。')

    start, end = piece[0], piece[1]
    z_delta_mm = abs(end.z - start.z) / uor_per_mm
    if z_delta_mm > HORIZONTAL_TOLERANCE_MM:
        raise ValueError(
            '所选直线不水平：两端 Z 相差 %.1f mm，要求 ≤ %.1f mm。'
            % (z_delta_mm, HORIZONTAL_TOLERANCE_MM))

    dx = end.x - start.x
    dy = end.y - start.y
    length_mm = math.hypot(dx, dy) / uor_per_mm
    if length_mm < MIN_LINE_LENGTH_MM:
        raise ValueError('所选直线长度 %.1f mm 过短（要求 ≥ %.0f mm）。'
                         % (length_mm, MIN_LINE_LENGTH_MM))

    return {
        'start_mm': base._point_to_mm(start),
        'end_mm': base._point_to_mm(end),
        'length_mm': length_mm,
        'heading_deg': math.degrees(math.atan2(dy, dx)),
        'z_mm': start.z / uor_per_mm,
    }


# ---------------------------------------------------------------------------
# 几何：支持绕 Z 旋转的横担 / 斜撑
# ---------------------------------------------------------------------------


def _make_frame(origin_mm, heading_deg):
    """把局部坐标（+X 沿横担）映射到世界坐标的闭包。"""
    angle = math.radians(heading_deg)
    c, s = math.cos(angle), math.sin(angle)

    def to_world(point_mm):
        x, y, z = point_mm
        return (origin_mm[0] + x * c - y * s,
                origin_mm[1] + x * s + y * c,
                origin_mm[2] + z)

    def to_world_vector(vector_mm):
        x, y, z = vector_mm
        return (x * c - y * s, x * s + y * c, z)

    return to_world, to_world_vector


def _create_shape(points_mm, dgn_model, to_world, mirror_z=None):
    """闭合轮廓转成元素。

    mirror_z 不为 None 时先把局部 z 关于该平面上下镜像。镜像会反转闭合
    轮廓的绕向，因此同时把点序倒过来，保持"法向 vs 扫掠方向"的关系与
    未镜像时一致，避免生成反向实体。
    """
    if mirror_z is not None:
        points_mm = [(p[0], p[1], 2.0 * mirror_z - p[2])
                     for p in reversed(points_mm)]
    points = DPoint3dArray()
    for point in points_mm:
        world = to_world(point)
        points.append(DPoint3d(base.mm(world[0], dgn_model),
                               base.mm(world[1], dgn_model),
                               base.mm(world[2], dgn_model)))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, points, dgn_model.Is3d(), dgn_model)
    if BentleyStatus.eSUCCESS != status:
        return None
    if BentleyStatus.eSUCCESS != profile.AddToModel():
        return None
    return profile


def _create_box_body(minimum, maximum, dgn_model, to_world, mirror_z=None):
    """创建用于端面切割的临时盒状实体；只沿 ±Z 扫掠。"""
    min_x, min_y, min_z = minimum
    max_x, max_y, max_z = maximum
    profile = _create_shape([
        (min_x, min_y, min_z),
        (max_x, min_y, min_z),
        (max_x, max_y, min_z),
        (min_x, max_y, min_z),
    ], dgn_model, to_world, mirror_z)
    if profile is None:
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        return None

    height = max_z - min_z
    if mirror_z is not None:
        height = -height
    sweep = DVec3d(0.0, 0.0, base.mm(height, dgn_model))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        return None
    return body_result[1]


def _body_to_element(body, dgn_model, component_name):
    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(solid, body, None, dgn_model)
    if BentleyStatus.eSUCCESS != status:
        _log('%s: BodyToElement failed: %r' % (component_name, status))
        return None
    return solid


def _sweep_vector(sweep_mm, dgn_model, to_world_vector, mirror_z=None):
    if mirror_z is not None:
        sweep_mm = (sweep_mm[0], sweep_mm[1], -sweep_mm[2])
    world = to_world_vector(sweep_mm)
    return DVec3d(base.mm(world[0], dgn_model),
                  base.mm(world[1], dgn_model),
                  base.mm(world[2], dgn_model))


def _create_h_beam_element(beam_length, h_beam_spec, dgn_model,
                           to_world, to_world_vector):
    """局部 +X 方向的 H 型钢横担，截面为 YZ 平面。

    局部 z=0 为横担**上翼缘上表面**（即所选直线所在标高），横担整体向下
    展开到 z=-height，保证所选直线是整组支架的最高点。
    """
    if beam_length <= 0.0:
        _log('H beam length must be greater than zero')
        return None

    height, width, web_thickness, flange_thickness = h_beam_spec
    half_width = width / 2.0
    half_web = web_thickness / 2.0
    top_z = 0.0
    bottom_z = -height
    top_inner_z = -flange_thickness
    bottom_inner_z = -height + flange_thickness

    profile_points = [
        (0.0, -half_width, bottom_z),
        (0.0, half_width, bottom_z),
        (0.0, half_width, bottom_inner_z),
        (0.0, half_web, bottom_inner_z),
        (0.0, half_web, top_inner_z),
        (0.0, half_width, top_inner_z),
        (0.0, half_width, top_z),
        (0.0, -half_width, top_z),
        (0.0, -half_width, top_inner_z),
        (0.0, -half_web, top_inner_z),
        (0.0, -half_web, bottom_inner_z),
        (0.0, -half_width, bottom_inner_z),
    ]
    profile = _create_shape(profile_points, dgn_model, to_world)
    if profile is None:
        _log('H beam: failed to create profile')
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        _log('H beam: failed to convert profile to body')
        return None

    sweep = _sweep_vector((beam_length, 0.0, 0.0), dgn_model, to_world_vector)
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        _log('H beam: sweep failed')
        return None
    return _body_to_element(body_result[1], dgn_model, 'H beam')


def _create_angle_brace_element(horizontal_distance, vertical_distance,
                                origin, angle_spec, dgn_model,
                                to_world, to_world_vector, mirror_z=None):
    """局部 XZ 平面内的 45° 角钢斜撑；下端 YZ 切面、上端 XY 水平切面。

    origin 为斜撑扫掠基准的局部坐标（同基础版的 brace_origin）。
    mirror_z 不为 None 时整根斜撑关于该水平面上下镜像（类型 2 斜撑朝上）。
    """
    if horizontal_distance <= 0.0 or vertical_distance <= 0.0:
        _log('brace projections must be greater than zero')
        return None

    angle_width, angle_thickness = angle_spec
    length = math.hypot(horizontal_distance, vertical_distance)
    axis = (horizontal_distance / length, 0.0, vertical_distance / length)

    start_overrun = ((angle_width + angle_thickness) * axis[2] / axis[0])
    outer_corner = base._add(origin, axis, -start_overrun)
    leg_y_axis = (0.0, 1.0, 0.0)
    face_axis = (axis[2], 0.0, -axis[0])
    p1 = base._add(outer_corner, leg_y_axis, angle_width)
    p2 = base._add(p1, face_axis, angle_thickness)
    p3 = base._add(base._add(outer_corner, leg_y_axis, angle_thickness),
                   face_axis, angle_thickness)
    p4 = base._add(base._add(outer_corner, leg_y_axis, angle_thickness),
                   face_axis, angle_width)
    p5 = base._add(outer_corner, face_axis, angle_width)
    profile = _create_shape([outer_corner, p1, p2, p3, p4, p5],
                            dgn_model, to_world, mirror_z)
    if profile is None:
        _log('brace: failed to create angle profile')
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        _log('brace: failed to convert profile to body')
        return None

    overrun = ((angle_width + angle_thickness) * axis[0] / axis[2])
    raw_length = start_overrun + length + overrun
    sweep = _sweep_vector((axis[0] * raw_length, 0.0, axis[2] * raw_length),
                          dgn_model, to_world_vector, mirror_z)
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        _log('brace: sweep failed')
        return None

    raw_end_x = outer_corner[0] + axis[0] * raw_length
    margin = angle_width + angle_thickness
    bottom_cutter = _create_box_body(
        (outer_corner[0] - margin,
         origin[1] - margin,
         outer_corner[2] - angle_width - margin),
        (origin[0],
         origin[1] + angle_width + margin,
         origin[2] + vertical_distance + margin),
        dgn_model, to_world, mirror_z)
    if bottom_cutter is None or not base._subtract_body(body_result[1],
                                                        bottom_cutter):
        _log('brace: failed to create YZ bottom cut')
        return None

    top_cut_z = origin[2] + vertical_distance
    cutter = _create_box_body(
        (min(outer_corner[0], raw_end_x) - margin,
         origin[1] - margin,
         top_cut_z),
        (max(origin[0], raw_end_x) + margin,
         origin[1] + angle_width + margin,
         top_cut_z + raw_length * axis[2] + margin),
        dgn_model, to_world, mirror_z)
    if cutter is None or not base._subtract_body(body_result[1], cutter):
        _log('brace: failed to create horizontal top cut')
        return None
    return _body_to_element(body_result[1], dgn_model, 'angle brace')


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def resolve_l1(line_length, end_overhang, variant_key):
    """由直线长度反算 L1（焊接端面至斜撑上端中心线的水平距离）。"""
    spec = base.VARIANTS[variant_key]
    return (line_length - spec['angle'][0] * math.sqrt(2.0) / 2.0
            - float(end_overhang))


def _validate(line, end_overhang, variant_key):
    if variant_key not in base.VARIANTS:
        raise ValueError('未知子项：%s。' % variant_key)
    spec = base.VARIANTS[variant_key]
    angle_width = spec['angle'][0]

    try:
        end_overhang = float(end_overhang)
    except (TypeError, ValueError):
        raise ValueError('E 必须是数字（mm）。')
    if end_overhang < MIN_END_OVERHANG:
        raise ValueError('E 不得小于 %.0f mm。' % MIN_END_OVERHANG)

    line_length = float(line['length_mm'])
    if line_length > MAX_BEAM_LENGTH:
        raise ValueError('所选直线长 L2=%.0f mm，不能大于 %.0f mm。'
                         % (line_length, MAX_BEAM_LENGTH))

    # 斜撑扫掠量 = L1 − 肢宽×√2/2 = L2 − 肢宽×√2 − E，必须为正。
    brace_sweep_projection = (line_length - angle_width * math.sqrt(2.0)
                              - end_overhang)
    if brace_sweep_projection <= 0.0:
        raise ValueError(
            '所选直线太短：L2=%.0f mm，需大于 肢宽×√2 + E = %.0f mm。'
            % (line_length, angle_width * math.sqrt(2.0) + end_overhang))
    return spec, line_length, end_overhang, brace_sweep_projection


# ---------------------------------------------------------------------------
# 管架编号
# ---------------------------------------------------------------------------

PIPE_RACK_ITEM_TYPE_PREFIX = 'PipeRackNumber'
PIPE_RACK_PROPERTY = 'PipeRackNumber'


def round_half_up(value):
    """四舍五入到整数（Python 的 round 是"银行家舍入"，不能用）。"""
    return int(math.floor(float(value) + 0.5))


def build_pipe_rack_number(name, rack_type, subtype, l1_mm, l2_mm):
    """管架编号：名称-类型-子项-L1-L2。

    暂不含末段的 h×w 筋板尺寸（图注 2，暂不考虑端板）。name 为空串时
    返回空串，表示本次不附加编号。
    """
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%d-%s-%d-%d' % (label, int(rack_type), subtype,
                               round_half_up(l1_mm), round_half_up(l2_mm))


def _rack_item_type_name(rack_number):
    safe = ''.join(ch if ch.isalnum() else '_' for ch in rack_number)
    return '%s_%s' % (PIPE_RACK_ITEM_TYPE_PREFIX, safe)


def _get_or_create_rack_item_type(rack_number):
    """创建/获取只带一个字符串属性的 ItemType（值写在默认值里）。

    与基础模块的构件清单同样做法：ApplyCustomItem 的返回值无法封送到
    Python，因此把编号写进 ItemType 的默认值再附加。
    """
    dgn_file = ISessionMgr.GetActiveDgnFile()
    item_type_name = _rack_item_type_name(rack_number)
    try:
        item_library = ItemTypeLibrary.FindByName(base.ITEM_LIBRARY_NAME, dgn_file)
        changed = False
        if item_library is None:
            item_library = ItemTypeLibrary(base.ITEM_LIBRARY_NAME, dgn_file, False)
            changed = True
        item_type = item_library.GetItemTypeByName(item_type_name)
        if item_type is None:
            item_type = item_library.AddItemType(item_type_name, False)
            changed = True
        if item_type is None:
            _log('rack item type: failed to create %s' % item_type_name)
            return None
        prop = item_type.GetPropertyByName(PIPE_RACK_PROPERTY)
        if prop is None:
            prop = item_type.AddProperty(PIPE_RACK_PROPERTY, False)
            if prop is None or not prop.SetType(CustomProperty.Type1.eString):
                _log('rack item type: failed to add property')
                return None
            if not prop.SetDefaultValue(base._new_ec_value(str(rack_number))):
                _log('rack item type: failed to set default value')
                return None
            changed = True
        if changed and not item_library.Write():
            _log('rack item type: failed to write library')
            return None
        item_library = ItemTypeLibrary.FindByName(base.ITEM_LIBRARY_NAME, dgn_file)
        return item_library.GetItemTypeByName(item_type_name)
    except Exception as error:
        _log('rack item type: setup exception: %r' % error)
        return None


def _attach_pipe_rack_number(cell, rack_number):
    """把管架编号作为 ItemType 属性附加到整组单元上。"""
    item_type = _get_or_create_rack_item_type(rack_number)
    if item_type is None:
        return False
    try:
        item_host = CustomItemHost(cell, False)
        try:
            item_host.ApplyCustomItem(item_type)
        except TypeError as error:
            if 'Unable to convert function return value' in str(error):
                _log('rack number attached (return conversion unavailable): %s'
                     % rack_number)
                return True
            raise
        return True
    except Exception as error:
        _log('rack number attach exception: %r' % error)
        return False


def _build_triangle_bracket_cell(line, end_overhang, variant_key=DEFAULT_VARIANT,
                                 brace_down=True, rack_number=None):
    """按所选直线构建端焊三角架单元但**不写入模型**。

    brace_down=True 为类型 1（斜撑向下，当前做法）；False 为类型 2
    （斜撑朝上，整根斜撑关于横担水平中面上下镜像）。所选直线在两种类型
    下都是横担上翼缘上表面。rack_number 非空时记入统计字典，由调用方
    附加到单元上。

    返回 (builder, 统计字典)。
    """
    spec, line_length, end_overhang, brace_sweep_projection = _validate(
        line, end_overhang, variant_key)
    angle_width = spec['angle'][0]
    h_beam_height = spec['h_beam'][0]

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    l1 = resolve_l1(line_length, end_overhang, variant_key)
    to_world, to_world_vector = _make_frame(line['start_mm'],
                                            line['heading_deg'])

    # 局部坐标：所选直线即横担上翼缘上表面（局部 z=0），横担向下到
    # z=-height；斜撑上端贴横担下翼缘（z=-height），基准外角后移半个
    # 肢宽使角钢轮廓关于横担中心面居中（与基础版一致）。
    # 类型 2 把整根斜撑关于横担水平中面 z=-height/2 镜像，于是它的水平
    # 切面落到横担上翼缘 z=0 并朝上展开；横担因截面上下对称而不变。
    brace_top_z = -h_beam_height
    brace_origin = (0.0, -angle_width / 2.0,
                    brace_top_z - brace_sweep_projection)
    mirror_z = None if brace_down else (-h_beam_height / 2.0)

    builder = base._TriangleBracketCellBuilder(dgn_model)
    brace = _create_angle_brace_element(
        brace_sweep_projection, brace_sweep_projection, brace_origin,
        spec['angle'], dgn_model, to_world, to_world_vector, mirror_z)
    if brace is None:
        raise RuntimeError('斜撑实体创建失败。')
    builder.add(brace)

    beam = _create_h_beam_element(
        line_length, spec['h_beam'], dgn_model, to_world, to_world_vector)
    if beam is None:
        raise RuntimeError('横担实体创建失败。')
    builder.add(beam)

    builder.build()
    brace_length = math.hypot(brace_sweep_projection, brace_sweep_projection)
    result = {
        'variant': variant_key,
        'child_count': builder.child_count,
        'line_length': line_length,
        'end_overhang': end_overhang,
        'l1': l1,
        'heading_deg': line['heading_deg'],
        'brace_length': brace_length,
        'brace_down': bool(brace_down),
        'rack_type': 1 if brace_down else 2,
        'pipe_rack_number': rack_number or '',
        'h_beam_specification': spec['h_beam_specification'],
        'angle_specification': spec['angle_specification'],
        'bom_items': [
            {'code': 'HBeam', 'name': COMPONENT_A_NAME,
             'specification': spec['h_beam_specification'],
             'length': line_length},
            {'code': 'AngleBrace', 'name': COMPONENT_B_NAME,
             'specification': spec['angle_specification'],
             'length': brace_length},
        ],
        'warnings': list(builder.warnings),
    }
    _log('bracket by line: variant=%s, type=%d, L2=%.1f, E=%.1f, L1=%.1f, '
         'heading=%.2f, braceProj=%.3f, cells=%d, rack=%s' %
         (variant_key, result['rack_type'], line_length, end_overhang, l1,
          line['heading_deg'], brace_sweep_projection, builder.child_count,
          result['pipe_rack_number'] or '-'))
    return builder, result


def _attach_result_items(cell, result):
    """附加横担 / 斜撑清单项，以及可选的管架编号。"""
    base._attach_bracket_items(cell, result)
    if result.get('pipe_rack_number'):
        _attach_pipe_rack_number(cell, result['pipe_rack_number'])


def replace_end_welded_triangle_bracket(line, end_overhang, previous_handle,
                                        variant_key=DEFAULT_VARIANT,
                                        brace_down=True, rack_number=None):
    """重建三角架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number)
    new_handle = builder.commit()
    _attach_result_items(new_handle, result)
    deleted = base._delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_end_welded_triangle_bracket(line, end_overhang,
                                     variant_key=DEFAULT_VARIANT,
                                     brace_down=True, rack_number=None):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number)
    cell = builder.commit()
    _attach_result_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """只导出本插件的 ItemType，写 JSON 并返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '端焊三角架_选线版_bom.json')
    return base.export_triangle_bracket_bom_json(output_path)


# ---------------------------------------------------------------------------
# 工具设置面板
# ---------------------------------------------------------------------------


class _BracketByLineSettingsDialog(QWidget):
    """子项 / E / 保留直线 选择，预览 / 确定 / 取消面板。"""

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

        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self.variant_combo = None
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
        outer.addWidget(base.NeuTitleBar(UI_TITLE, self._minimize,
                                         self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点选一条水平直线段作为横担上表面（即整组支架最高点）："
                      "起点为焊接端面，终点为横担末端，直线方向即横担方向。"
                      "直线两端 Z 必须一致。点取后可改 E / 子项，预览会自动重建；"
                      "点【确定】保留，点【取消】或右键放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = base.NeuCard("构件规格")
        self.variant_combo = self._register(base.NeuCombo(
            [(key, _variant_label(key)) for key in sorted(VARIANTS)],
            current=DEFAULT_VARIANT, on_change=self.on_options_changed))
        self._row(card.content, 0, "子项：", [self.variant_combo], 16)
        self.beam_label = self._value()
        self._row(card.content, 1, "构件A（横担）：", [self.beam_label])
        self.angle_label = self._value()
        self._row(card.content, 2, "构件B（斜撑）：", [self.angle_label])
        body.addWidget(card)

        card = base.NeuCard("尺寸参数")
        self.overhang_edit = self._edit_row(
            card.content, 0, "E：", '%.0f' % DEFAULT_END_OVERHANG,
            "mm　横担最远端至斜撑上端外侧斜角（≥150）")
        self.length_label = self._value()
        self._row(card.content, 1, "直线长 L2：",
                  [self.length_label, self._note("mm　由所选直线自动读取")], 8)
        self.l1_label = self._value()
        self._row(card.content, 2, "斜撑位置 L1：",
                  [self.l1_label, self._note("mm　= L2 − 肢宽×√2/2 − E")], 8)
        body.addWidget(card)

        card = base.NeuCard("管架编号")
        self.rack_name_edit = self._edit_row(
            card.content, 0, "名称：", 'D5', "管架系列代号；留空则不附加编号")
        self.rack_type_combo = self._register(base.NeuCombo(
            [(1, '类型1  |  斜撑向下'), (2, '类型2  |  斜撑向上')],
            current=1, on_change=self.on_options_changed))
        self._row(card.content, 1, "类型：", [self.rack_type_combo], 16)
        self.rack_label = self._value()
        self._row(card.content, 2, "编号：",
                  [self.rack_label, self._note("名称-类型-子项-L1-L2（整数）")], 8)
        body.addWidget(card)

        card = base.NeuCard("创建选项")
        self.keep_toggle = self._register(base.NeuToggle("创建后保留所选直线"))
        self.keep_toggle.setChecked(True)
        card.content.addWidget(self.keep_toggle, 0, 0, 1, 2)
        body.addWidget(card)

        summary = base.NeuPanel()
        self.spec_label = self._info("", base.UI_TEXT)
        summary.content.addWidget(self.spec_label)
        self.preview_info_label = self._info("预览：—", base.UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点选一条水平直线段；改参数会自动重建预览。",
            base.UI_INFO)
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.cancel_button = base.NeuButton("取消")
        self.cancel_button.setFixedWidth(126)
        self.cancel_button.clicked.connect(self.cancel_tool)
        self.export_button = base.NeuButton("导出 JSON 清单")
        self.export_button.setFixedWidth(150)
        self.export_button.clicked.connect(self.export_bom)
        self.confirm_button = base.NeuButton("确定", accent=True)
        self.confirm_button.setFixedWidth(126)
        self.confirm_button.clicked.connect(self.confirm_tool)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.confirm_button)
        body.addLayout(button_row)
        self.action_widgets = [
            self.confirm_button, self.cancel_button, self.export_button]

        self.refresh_spec()
        self.setMinimumWidth(540)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        try:
            _stamp = int(os.path.getmtime(os.path.abspath(__file__)))
        except Exception:
            _stamp = 0
        _log('panel built %dx%d rev=%s file=%s mtime=%d'
             % (self.width(), self.height(), UI_REVISION,
                os.path.abspath(__file__), _stamp))
        self.hwnd = int(self.winId())
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)

    # -- 控件构造 ----------------------------------------------------------

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

    def _edit_row(self, grid, row, name, value, note):
        field = base.NeuEdit(value, width=96)
        self._register(field.edit)
        field.edit.textChanged.connect(self.on_text_changed)
        self._row(grid, row, name, [field, self._note(note)], 8)
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

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        if self.variant_combo is None:
            return DEFAULT_VARIANT
        return self.variant_combo.value() or DEFAULT_VARIANT

    def current_rack_type(self):
        if self.rack_type_combo is None:
            return 1
        try:
            return int(self.rack_type_combo.value())
        except (TypeError, ValueError):
            return 1

    def current_options(self):
        variant_key = self.current_variant()
        if variant_key not in VARIANTS:
            raise ValueError('未知子项：%s。' % variant_key)
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            raise ValueError('E 必须是数字（mm）。')
        if end_overhang < MIN_END_OVERHANG:
            raise ValueError('E 不得小于 %.0f mm。' % MIN_END_OVERHANG)
        return {
            'variant': variant_key,
            'end_overhang': end_overhang,
            'brace_down': self.current_rack_type() == 1,
            'rack_name': self.rack_name_edit.value().strip(),
            'rack_type': self.current_rack_type(),
        }

    def current_rack_number(self, line=None):
        """按当前直线 / 子项 / E / 名称 / 类型合成管架编号；无直线时返回 ''。"""
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            return ''
        variant_key = self.current_variant()
        l2 = line['length_mm']
        l1 = resolve_l1(l2, end_overhang, variant_key)
        return build_pipe_rack_number(self.rack_name_edit.value(),
                                      self.current_rack_type(), variant_key,
                                      l1, l2)

    def set_status(self, message, is_error=False, flush=True):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        if flush:
            QApplication.processEvents()

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        self.preview_info_label.setText(
            "预览：子项 %s，类型 %d，横担 %s，L2=%.0f mm，L1=%.0f mm，"
            "E=%.0f mm，斜撑轴长 %.0f mm，单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'],
                result['h_beam_specification'], result['line_length'],
                result['l1'], result['end_overhang'], result['brace_length'],
                result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
        self.beam_label.setText(variant['h_beam_specification'])
        self.angle_label.setText('%s（45°）' % variant['angle_specification'])
        self.spec_label.setText(describe_spec(variant_key))
        self.refresh_line_labels()

    def _show_line_values(self, line):
        """显示给定直线的 L2、按当前子项 / E 反算的 L1 与管架编号。"""
        if line is None:
            self.length_label.setText('—')
            self.l1_label.setText('—')
            self.rack_label.setText('—')
            return
        length = line['length_mm']
        self.length_label.setText('%.1f' % length)
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            self.l1_label.setText('—')
            self.rack_label.setText('—')
            return
        self.l1_label.setText(
            '%.1f' % resolve_l1(length, end_overhang, self.current_variant()))
        number = self.current_rack_number(line)
        self.rack_label.setText(number if number else '（名称留空，不附加）')

    def refresh_line_labels(self):
        """按当前所选直线与 E 刷新 L2 / L1 / 编号显示。"""
        self._show_line_values(self.line)

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
        if self.line is None:
            return
        timer.start()

    def _cancel_pending_regeneration(self):
        self._regen_timer.stop()
        self._text_timer.stop()

    def _run_pending_regeneration(self):
        self.regenerate()

    def note_hover(self, line):
        """悬停到一条合规直线上：只刷新数值显示，不改变已选定的直线。"""
        if self.line is None:
            self._show_line_values(line)

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前直线与选项重建预览：先建新的一版，成功后再删掉旧的。"""
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        rack_number = self.current_rack_number()

        self._set_busy(True)
        self.set_status('正在生成端焊三角架预览，请稍候……')
        try:
            handle, result, deleted = replace_end_welded_triangle_bracket(
                self.line, options['end_overhang'], self.preview_handle,
                options['variant'], options['brace_down'], rack_number)
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.refresh_line_labels()
        self.set_result(result)
        message = (
            "预览已更新：子项 %s，类型 %d，横担 %s，L2=%.0f mm，L1=%.0f mm，"
            "单元含 %d 个子元素，编号 %s。%s改参数会自动重建；"
            "点【确定】保留，点【取消】放弃。"
            % (result['variant'], result['rack_type'],
               result['h_beam_specification'], result['line_length'],
               result['l1'], result['child_count'],
               result['pipe_rack_number'] or '—',
               '已替换上一版预览。' if deleted else '')
        )
        if result['warnings']:
            message += '注意：%s' % '；'.join(result['warnings'])
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return base._delete_preview(handle)

    def delete_source_line(self):
        """按“创建后保留所选直线”开关，删除用户所选直线。"""
        handle = self.line_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                _log('source line deleted')
                return True
        except Exception:
            _log_exception('delete source line failed')
        self.set_status('所选直线删除失败，请手动删除。', True)
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
        PyCommandState.StartDefaultCommand()

    def shutdown(self):
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            pass

    # -- 窗口 --------------------------------------------------------------

    def _minimize(self):
        self.showMinimized()

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
        # 关窗口等同于取消：先撤掉预览，再由主循环退出原生工具。
        event.ignore()
        self.cancel_tool()

    def run_dialog_loop(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x()-self.width()//2,
                      area.center().y()-self.height()//2)
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


# ---------------------------------------------------------------------------
# 交互工具：点选水平直线
# ---------------------------------------------------------------------------


class BracketByLineTool(DgnElementSetTool):
    """点选一条水平直线段并放置端焊三角架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('EndWeldedTriangleBracketByLineTool')

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
            '请点选一条水平直线段作为横担中心线（起点为焊接端面，终点为横担末端）；'
            '直线两端 Z 必须一致。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            line = extract_horizontal_line(handle)
            if self.tool_settings is not None:
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True, flush=False)
            return False

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_horizontal_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('element modify failed')
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        BracketByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

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
                    else _BracketByLineSettingsDialog())
        tool = BracketByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.run_dialog_loop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    try:
        BracketByLineTool.InstallNewInstance(0)
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('端焊三角架（选线版）工具启动失败：%s\n%s' % (error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE, '工具启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


show_triangle_bracket_dialog = PyMain


if __name__ == '__main__':
    PyMain()
