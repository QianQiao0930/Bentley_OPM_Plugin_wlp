# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``三角架.py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""端焊三角架（选线版 + 可选端板）纯几何 / 数据模块（无界面依赖）。

集中「点选一条水平直线 → 横担上表面，可选在起点创建端板（横担 + 斜撑各
一块，含 4 根膨胀锚栓）」的全部建模逻辑：

* 所选直线 = 横担上翼缘上表面（整组最高点），直线长 = 横担总长 L2；
* 斜撑位置 L1 = L2 − 肢宽×√2/2 − E；
* 勾选端板时横担起点顺延端板厚、长度改为 ``L2 − 端板厚``，斜撑仍从焊接面
  按 L1 起算；横担端板 + 斜撑端板完全同规格，孔距 S 按横担截面自动取整；
* 整组（横担 + 斜撑 + 可选两块端板 + 8 根锚栓）写成一个普通单元。

本模块不含任何 PyQt5 / Tkinter 界面代码，也不再依赖早期插件
``端焊三角架_选线版.py`` 或 PyQt5 基础模块 ``端焊三角架_基础.py``；
端板 / 锚栓几何复用 ``混凝土锚板.py``，清单写入 ``支吊架公共库``。
"""

from __future__ import division

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


# 本文件位于 模块/端焊三角架/，插件根目录需上溯两级；公共库在 模块/公共/。
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_COMMON_DIR = os.path.join(_PLUGIN_ROOT, '模块', '公共')
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(_PLUGIN_ROOT, '模块', '日志', '三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 直线两端 Z 的最大允许差值（mm）。超出即判定不水平并提示不合规。
HORIZONTAL_TOLERANCE_MM = 0.5
# 直线的最短有效长度（mm）。
MIN_LINE_LENGTH_MM = 50.0
# E 的最小值、横担总长上限（mm）。
MIN_END_OVERHANG = 150.0
MAX_BEAM_LENGTH = 2500.0
DEFAULT_END_OVERHANG = 150.0
# 端板孔距 S 自动取整目数（mm）。
SPACING_STEP_MM = 25.0
DEFAULT_PLATE_SUBTYPE = 'A'

# 整组构件写入的普通单元名。
CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET_WITH_PLATE'

# 共享支吊架清单模块所需的类型标识。
SUPPORT_TYPE = '端焊三角架'
SUPPORT_CODE = 'TRIANGLE_BRACKET'

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
DEFAULT_VARIANT = 'A'

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'
COMPONENT_PLATE_NAME = '端板'
COMPONENT_BRACE_PLATE_NAME = '斜撑端板'
COMPONENT_BOLT_NAME = '膨胀锚栓'
COMPONENT_BRACE_BOLT_NAME = '斜撑膨胀锚栓'


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


# ---------------------------------------------------------------------------
# 低层工具（原 端焊三角架_基础.py 中无界面依赖的部分）
# ---------------------------------------------------------------------------


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerStorage()


def mm(value, dgn_model=None):
    return value * _uor_per_mm(dgn_model)


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _point_to_mm(point):
    if point is None:
        return None
    uor = _uor_per_mm()
    return (point.x / uor, point.y / uor, point.z / uor)


def _add(point, vector, distance):
    return (
        point[0] + vector[0] * distance,
        point[1] + vector[1] * distance,
        point[2] + vector[2] * distance,
    )


# ---------------------------------------------------------------------------
# 描述文本
# ---------------------------------------------------------------------------


def variant_label(variant_key):
    variant = VARIANTS[variant_key]
    return '%s  |  %s  |  %s' % (variant_key, variant['h_beam_specification'],
                                 variant['angle_specification'])


def plate_subtype_label(subtype):
    table = anchor.ANCHOR_TABLE[subtype]
    return ('%s  |  M%.0f×%.0f  |  板厚 %.0f  |  孔 φ%.0f'
            % (subtype, table['bolt_dia'], table['length'],
               table['plate_t'], table['hole_dia']))


def describe_spec(variant_key):
    variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
    return ('横担 %s + 斜撑 %s；斜撑位置 L1 = L2 − %.1f×√2/2 − E，'
            '直线长 L2 ≤ %.0f mm。'
            % (variant['h_beam_specification'], variant['angle_specification'],
               variant['angle'][0], MAX_BEAM_LENGTH))


def describe_plate(resolved):
    return ('端板 %.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f）；'
            'M%.0f×%.0f 膨胀锚栓 ×4，埋深 %.0f。'
            % (resolved['plate_side'], resolved['plate_side'],
               resolved['plate_t'], resolved['hole_dia'], resolved['spacing'],
               resolved['bolt_dia'], resolved['bolt_length'],
               resolved['embedment_actual']))


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
    uor_per_mm = _uor_per_mm()
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
        'start_mm': _point_to_mm(start),
        'end_mm': _point_to_mm(end),
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
    """闭合轮廓转成元素（mirror_z 不为 None 时关于该平面上下镜像）。"""
    if mirror_z is not None:
        points_mm = [(p[0], p[1], 2.0 * mirror_z - p[2])
                     for p in reversed(points_mm)]
    points = DPoint3dArray()
    for point in points_mm:
        world = to_world(point)
        points.append(DPoint3d(mm(world[0], dgn_model),
                               mm(world[1], dgn_model),
                               mm(world[2], dgn_model)))
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
    sweep = DVec3d(0.0, 0.0, mm(height, dgn_model))
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


def _subtract_body(target_body, tool_body):
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanSubtract(target_body, tools)
    except Exception as error:
        _log('BooleanSubtract exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if BentleyStatus.eSUCCESS != status:
        _log('BooleanSubtract failed: %r' % (status,))
        return False
    return True


def _sweep_vector(sweep_mm, dgn_model, to_world_vector, mirror_z=None):
    if mirror_z is not None:
        sweep_mm = (sweep_mm[0], sweep_mm[1], -sweep_mm[2])
    world = to_world_vector(sweep_mm)
    return DVec3d(mm(world[0], dgn_model),
                  mm(world[1], dgn_model),
                  mm(world[2], dgn_model))


def _create_h_beam_element(beam_length, h_beam_spec, dgn_model,
                           to_world, to_world_vector):
    """局部 +X 方向的 H 型钢横担，截面为 YZ 平面。"""
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
    """局部 XZ 平面内的 45° 角钢斜撑；下端 YZ 切面、上端 XY 水平切面。"""
    if horizontal_distance <= 0.0 or vertical_distance <= 0.0:
        _log('brace projections must be greater than zero')
        return None

    angle_width, angle_thickness = angle_spec
    length = math.hypot(horizontal_distance, vertical_distance)
    axis = (horizontal_distance / length, 0.0, vertical_distance / length)

    start_overrun = ((angle_width + angle_thickness) * axis[2] / axis[0])
    outer_corner = _add(origin, axis, -start_overrun)
    leg_y_axis = (0.0, 1.0, 0.0)
    face_axis = (axis[2], 0.0, -axis[0])
    p1 = _add(outer_corner, leg_y_axis, angle_width)
    p2 = _add(p1, face_axis, angle_thickness)
    p3 = _add(_add(outer_corner, leg_y_axis, angle_thickness),
              face_axis, angle_thickness)
    p4 = _add(_add(outer_corner, leg_y_axis, angle_thickness),
              face_axis, angle_width)
    p5 = _add(outer_corner, face_axis, angle_width)
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
    if bottom_cutter is None or not _subtract_body(body_result[1],
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
    if cutter is None or not _subtract_body(body_result[1], cutter):
        _log('brace: failed to create horizontal top cut')
        return None
    return _body_to_element(body_result[1], dgn_model, 'angle brace')


# ---------------------------------------------------------------------------
# 校验与编号
# ---------------------------------------------------------------------------


def resolve_l1(line_length, end_overhang, variant_key):
    """由直线长度反算 L1（焊接端面至斜撑上端中心线的水平距离）。"""
    spec = VARIANTS[variant_key]
    return (line_length - spec['angle'][0] * math.sqrt(2.0) / 2.0
            - float(end_overhang))


def _validate(line, end_overhang, variant_key):
    if variant_key not in VARIANTS:
        raise ValueError('未知子项：%s。' % variant_key)
    spec = VARIANTS[variant_key]
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

    brace_sweep_projection = (line_length - angle_width * math.sqrt(2.0)
                              - end_overhang)
    if brace_sweep_projection <= 0.0:
        raise ValueError(
            '所选直线太短：L2=%.0f mm，需大于 肢宽×√2 + E = %.0f mm。'
            % (line_length, angle_width * math.sqrt(2.0) + end_overhang))
    return spec, line_length, end_overhang, brace_sweep_projection


def round_half_up(value):
    return int(math.floor(float(value) + 0.5))


def build_pipe_rack_number(name, rack_type, subtype, l1_mm, l2_mm):
    """管架编号：名称-类型-子项-L1-L2；名称为空时返回空串。"""
    label = str(name).strip()
    if not label:
        return ''
    return '%s-%d-%s-%d-%d' % (label, int(rack_type), subtype,
                               round_half_up(l1_mm), round_half_up(l2_mm))


# ---------------------------------------------------------------------------
# 端板几何：复用 混凝土锚板.py 的板 + 锚栓
# ---------------------------------------------------------------------------


def auto_plate_spacing(h_beam_spec, min_spacing):
    """按横担截面外形自动取孔距 S：严格大于截面最大边长，按 25 向上取整。"""
    max_dim = max(float(h_beam_spec[0]), float(h_beam_spec[1]))
    steps = math.floor(max_dim / SPACING_STEP_MM) + 1
    spacing = steps * SPACING_STEP_MM
    return max(spacing, float(min_spacing))


def _resolve_plate_options(plate_subtype, heading_deg, h_beam_spec=None):
    """校验并展开端板参数（板尺寸 / 厚度 / 孔径 / 锚栓）。"""
    table = anchor.ANCHOR_TABLE.get(plate_subtype)
    spacing = None
    if table is not None and h_beam_spec is not None:
        spacing = auto_plate_spacing(h_beam_spec, table['min_spacing'])
    return anchor.resolve_options({
        'subtype': plate_subtype,
        'spacing': spacing,
        'heading_deg': heading_deg,
    })


def _add_end_plate_at(builder, resolved, line, center_local, dgn_model,
                      to_world):
    """在局部坐标 center_local 处加一块 G2 正方形端板 + 4 根膨胀锚栓。"""
    origin_mm = to_world(center_local)
    uor_per_mm = _uor_per_mm(dgn_model)
    origin = DPoint3d.From(mm(origin_mm[0], dgn_model),
                           mm(origin_mm[1], dgn_model),
                           mm(origin_mm[2], dgn_model))
    frame = anchor._PlateFrame(origin, uor_per_mm, line['heading_deg'])
    anchor._add_plate(builder, frame, dgn_model, resolved)
    anchor._add_bolts(builder, frame, dgn_model, resolved)


def _brace_end_face_center(brace_origin, angle_width, mirror_z):
    """斜撑下端面（局部 x=0 竖直面）的中心。"""
    center_y = brace_origin[1] + angle_width / 2.0
    center_z = brace_origin[2] - angle_width * math.sqrt(2.0) / 2.0
    if mirror_z is not None:
        center_z = 2.0 * mirror_z - center_z
    return (0.0, center_y, center_z)


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _TriangleBracketCellBuilder(object):
    """收集端焊三角架子元素，全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell_name = cell_name or CELL_NAME
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('三角架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法将三角架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成端焊三角架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法将端焊三角架单元写入活动模型。')
        return self.cell


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


# ---------------------------------------------------------------------------
# 构建整组（选线版 + 可选端板）
# ---------------------------------------------------------------------------


def _build_triangle_bracket_cell(line, end_overhang,
                                 variant_key=DEFAULT_VARIANT,
                                 brace_down=True, rack_number=None,
                                 add_end_plate=False,
                                 plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """按所选直线与端板选项构建整组单元但**不写入模型**。

    返回 ``(builder, 统计字典)``。
    """
    spec, line_length, end_overhang, brace_sweep_projection = _validate(
        line, end_overhang, variant_key)
    angle_width = spec['angle'][0]
    h_beam_height = spec['h_beam'][0]

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    resolved_plate = None
    plate_t = 0.0
    if add_end_plate:
        resolved_plate = _resolve_plate_options(plate_subtype,
                                                line['heading_deg'],
                                                spec['h_beam'])
        plate_t = float(resolved_plate['plate_t'])

    beam_start_x = plate_t
    beam_length = float(line_length) - beam_start_x
    if beam_length <= 0.0:
        raise ValueError('扣除端板厚度 %.0f mm 后横担长度 %.1f mm 不足，'
                         '请换用更长的直线或更薄的端板。'
                         % (plate_t, beam_length))

    l1 = resolve_l1(line_length, end_overhang, variant_key)

    to_world, to_world_vector = _make_frame(line['start_mm'],
                                            line['heading_deg'])
    heading = math.radians(line['heading_deg'])
    beam_start_mm = (line['start_mm'][0] + beam_start_x * math.cos(heading),
                     line['start_mm'][1] + beam_start_x * math.sin(heading),
                     line['start_mm'][2])
    beam_to_world, _ = _make_frame(beam_start_mm, line['heading_deg'])

    brace_top_z = -h_beam_height
    brace_origin = (0.0, -angle_width / 2.0,
                    brace_top_z - brace_sweep_projection)
    mirror_z = None if brace_down else (-h_beam_height / 2.0)

    builder = _TriangleBracketCellBuilder(dgn_model)
    brace = _create_angle_brace_element(
        brace_sweep_projection, brace_sweep_projection, brace_origin,
        spec['angle'], dgn_model, to_world, to_world_vector, mirror_z)
    if brace is None:
        raise RuntimeError('斜撑实体创建失败。')
    builder.add(brace)

    beam = _create_h_beam_element(
        beam_length, spec['h_beam'], dgn_model, beam_to_world,
        to_world_vector)
    if beam is None:
        raise RuntimeError('横担实体创建失败。')
    builder.add(beam)

    if resolved_plate is not None:
        _add_end_plate_at(builder, resolved_plate, line,
                          (0.0, 0.0, -h_beam_height / 2.0),
                          dgn_model, to_world)
        brace_center = _brace_end_face_center(brace_origin, angle_width,
                                              mirror_z)
        _add_end_plate_at(builder, resolved_plate, line, brace_center,
                          dgn_model, to_world)

    builder.build()
    brace_length = math.hypot(brace_sweep_projection, brace_sweep_projection)
    bom_items = [
        {'code': 'HBeam', 'name': COMPONENT_A_NAME,
         'specification': spec['h_beam_specification'],
         'length': beam_length},
        {'code': 'AngleBrace', 'name': COMPONENT_B_NAME,
         'specification': spec['angle_specification'],
         'length': brace_length},
    ]
    if resolved_plate is not None:
        plate_spec = '%.0f×%.0f×%.0f（S=%.0f，4-φ%.0f）' % (
            resolved_plate['plate_side'], resolved_plate['plate_side'],
            resolved_plate['plate_t'], resolved_plate['spacing'],
            resolved_plate['hole_dia'])
        bolt_spec = 'M%.0f×%.0f' % (
            resolved_plate['bolt_dia'], resolved_plate['bolt_length'])
        bom_items.append({
            'code': 'EndPlate', 'name': COMPONENT_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceEndPlate', 'name': COMPONENT_BRACE_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'AnchorBolt', 'name': COMPONENT_BOLT_NAME,
            'specification': bolt_spec,
            'length': resolved_plate['bolt_length'],
            'quantity': 4, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceAnchorBolt', 'name': COMPONENT_BRACE_BOLT_NAME,
            'specification': bolt_spec,
            'length': resolved_plate['bolt_length'],
            'quantity': 4, 'unit': '件',
        })

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
        'beam_start_x': beam_start_x,
        'beam_length': beam_length,
        'end_plate': (dict(resolved_plate) if resolved_plate else None),
        'brace_end_plate': (dict(resolved_plate) if resolved_plate else None),
        'h_beam_specification': spec['h_beam_specification'],
        'angle_specification': spec['angle_specification'],
        'bom_items': bom_items,
        'warnings': list(builder.warnings),
    }
    _log('bracket by line with plate: variant=%s, type=%d, L2=%.1f, E=%.1f, '
         'L1=%.1f, beamStart=%.1f, beamLen=%.1f, plate=%s, heading=%.2f, '
         'cells=%d, rack=%s' %
         (variant_key, result['rack_type'], line_length, end_overhang, l1,
          beam_start_x, beam_length,
          plate_subtype if resolved_plate else '-', line['heading_deg'],
          builder.child_count, result['pipe_rack_number'] or '-'))
    return builder, result


def _attach_result_items(cell, result):
    """把整组三角架写入共享支吊架库（整组记录 + 各构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec='%s + %s' % (result.get('h_beam_specification', ''),
                                   result.get('angle_specification', '')),
        components=result.get('bom_items', ()),
    )


def replace_end_welded_triangle_bracket(line, end_overhang, previous_handle,
                                        variant_key=DEFAULT_VARIANT,
                                        brace_down=True, rack_number=None,
                                        add_end_plate=False,
                                        plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """重建整组：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    new_handle = builder.commit()
    _attach_result_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_end_welded_triangle_bracket(line, end_overhang,
                                     variant_key=DEFAULT_VARIANT,
                                     brace_down=True, rack_number=None,
                                     add_end_plate=False,
                                     plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    cell = builder.commit()
    _attach_result_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(_PLUGIN_ROOT, '模块', '输出', '三角架_bom.json')
    return psb.export_combined_bom(output_path)
