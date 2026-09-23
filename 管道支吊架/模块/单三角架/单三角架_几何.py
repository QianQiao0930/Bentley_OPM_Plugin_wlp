# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为建模库供入口 ``N3-[设备上生根单三角架].py`` 等插件 ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""N 系列设备上生根管架 —— 设备上生根的单三角架（N3）建模库（无界面）。

用户在模型中绘制一条**水平辅助线**作为**管底**（＝横担顶面），据此生成：

    * 构件A（横担）：截面沿辅助线方向扫掠，**顶面落在辅助线上**；
    * 构件B（斜撑）：45°，连接设备上的连接板与横担；
    * 连接板 + 螺栓：复用 N8 ``连接板_几何``，规格按表 2 自动取；
    * 交点处 10mm 筋板。

局部坐标（x=0 在辅助线起点、设备表面所在竖直面上）：

    +x = 由设备向外（辅助线方向）   +y = 水平面内垂直 +x   +z = 竖直向上

类型 1：斜撑在下（由下方连接板向上撑到横担下缘）；
类型 2：斜撑在上（由上方连接板向下拉到横担顶面）。

连接板连同螺栓螺母**整体镜像**放置：连接板落在设备一侧（x ∈ [-T, 0]，外表面
与设备面 x=0 齐平），螺栓头朝外、螺母朝设备内。

构件实体用「截面轮廓 → 实体 → 沿轴扫掠」构造（与端焊三角架一致），这样端面
可用布尔运算切割。清单写入共享支吊架库 ``支吊架公共库``。

主要接口::

    import 单三角架_几何 as geom
    cell, result = geom.draw_single_bracket(line, options)
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


_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_COMMON_DIR = os.path.join(_PLUGIN_ROOT, '模块', '公共')
_PLATE_DIR = os.path.join(_PLUGIN_ROOT, '模块', '连接板')
for _path in (_HERE, _PLATE_DIR, _COMMON_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 单三角架_数据 as data  # noqa: E402
import 连接板_数据 as plate_data  # noqa: E402
import 连接板_几何 as plate_geom  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


CELL_NAME = 'EQUIPMENT_SINGLE_BRACKET'

SUPPORT_TYPE = 'N3-[设备上生根单三角架]'
SUPPORT_CODE = 'N3_SINGLE_BRACKET'

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'
COMPONENT_PLATE_NAME = '连接板'
COMPONENT_BOLT_NAME = '连接板螺栓'
COMPONENT_STIFFENER_NAME = '筋板'

HORIZONTAL_TOLERANCE_MM = 0.5
MIN_LINE_LENGTH_MM = 50.0

DEBUG_LOG = os.path.join(
    _PLUGIN_ROOT, '模块', '日志', '单三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _uor(dgn_model):
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


# ---------------------------------------------------------------------------
# 辅助线提取
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

    返回 ``{'start_mm','end_mm','length_mm','heading_deg','z_mm'}``。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('请先打开并激活一个 DGN 模型。')
    uor = _uor(model_ref.GetDgnModel())
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条开放的水平直线段。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if len(pieces) != 1 or len(pieces[0]) != 2:
        raise ValueError('请选择单条水平直线段（不要选折线或复杂链）。')

    start, end = pieces[0][0], pieces[0][1]
    z_delta = abs(end.z - start.z) / uor
    if z_delta > HORIZONTAL_TOLERANCE_MM:
        raise ValueError('所选直线不水平：两端 Z 相差 %.1f mm，要求 ≤ %.1f mm。'
                         % (z_delta, HORIZONTAL_TOLERANCE_MM))
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy) / uor
    if length < MIN_LINE_LENGTH_MM:
        raise ValueError('所选直线长度 %.1f mm 过短（要求 ≥ %.0f mm）。'
                         % (length, MIN_LINE_LENGTH_MM))
    return {
        'start_mm': (start.x / uor, start.y / uor, start.z / uor),
        'end_mm': (end.x / uor, end.y / uor, end.z / uor),
        'length_mm': length,
        'heading_deg': math.degrees(math.atan2(dy, dx)),
        'z_mm': start.z / uor,
    }


# ---------------------------------------------------------------------------
# 局部坐标架 / 截面轮廓
# ---------------------------------------------------------------------------


def _frame_vectors(heading_deg):
    angle = math.radians(heading_deg)
    c, s = math.cos(angle), math.sin(angle)
    return (c, s, 0.0), (-s, c, 0.0)


def _make_frame(origin_mm, heading_deg):
    x_axis, y_axis = _frame_vectors(heading_deg)

    def to_world(point_mm):
        x, y, z = point_mm
        return (origin_mm[0] + x * x_axis[0] + y * y_axis[0],
                origin_mm[1] + x * x_axis[1] + y * y_axis[1],
                origin_mm[2] + z)
    return to_world


def _section_points(spec):
    """截面轮廓（闭合）：(depth, width)；depth 0=参考面、正=远离参考面。"""
    dims = data.section_dims(spec)
    height, width, tw, tf = (dims['height'], dims['width'],
                             dims['tw'], dims['tf'])
    hb, hw = width / 2.0, tw / 2.0
    if dims['kind'] == 'H':
        return [(0.0, -hb), (0.0, hb), (tf, hb), (tf, hw),
                (height - tf, hw), (height - tf, hb), (height, hb),
                (height, -hb), (height - tf, -hb), (height - tf, -hw),
                (tf, -hw), (tf, -hb)]
    # 槽钢：腹板在 width = -B/2，翼缘伸向 +B/2。
    return [(0.0, -hb), (0.0, hb), (tf, hb), (tf, -hb + tw),
            (height - tf, -hb + tw), (height - tf, hb), (height, hb),
            (height, -hb)]


# ---------------------------------------------------------------------------
# 低层：轮廓 -> 实体 -> 扫掠 / 布尔
# ---------------------------------------------------------------------------


def _create_shape(points_mm, dgn_model):
    """闭合轮廓（世界 mm）-> 已入模的 Shape 元素。"""
    model_ref = ISessionMgr.ActiveDgnModelRef
    uor = _uor(dgn_model)
    points = DPoint3dArray()
    for point in points_mm:
        points.append(DPoint3d.From(point[0] * uor, point[1] * uor,
                                    point[2] * uor))
    profile = EditElementHandle()
    if not _succeeded(ShapeHandler.CreateShapeElement(
            profile, None, points, model_ref.Is3d(), model_ref)):
        return None
    if not _succeeded(profile.AddToModel()):
        return None
    return profile


def _sweep_shape_to_body(profile, sweep_mm, dgn_model):
    """把 Shape 转成实体并沿 sweep_mm（世界 mm）扫掠。"""
    result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if result is None or not _succeeded(result[0]):
        return None
    uor = _uor(dgn_model)
    sweep = DVec3d(sweep_mm[0] * uor, sweep_mm[1] * uor, sweep_mm[2] * uor)
    if not _succeeded(SolidUtil.Modify.SweepBody(result[1], sweep)):
        return None
    return result[1]


def _body_to_element(body, dgn_model, component_name):
    solid = EditElementHandle()
    if not _succeeded(
            SolidUtil.Convert.BodyToElement(solid, body, None, dgn_model)):
        _log('%s: BodyToElement failed' % component_name)
        return None
    return solid


def _subtract_body(target_body, tool_body):
    if tool_body is None:
        return False
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanSubtract(target_body, tools)
    except Exception as error:
        _log('BooleanSubtract exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if status is None:
        return True
    return BentleyStatus.eSUCCESS == status


def _world_profile(origin_mm, depth_dir, width_dir, spec, depth_offset=0.0):
    """把截面轮廓映射到世界点列。depth 沿 depth_dir、width 沿 width_dir。"""
    points = []
    for depth, width in _section_points(spec):
        d = depth + depth_offset
        points.append((
            origin_mm[0] + d * depth_dir[0] + width * width_dir[0],
            origin_mm[1] + d * depth_dir[1] + width * width_dir[1],
            origin_mm[2] + d * depth_dir[2] + width * width_dir[2]))
    return points


# ---------------------------------------------------------------------------
# 构件
# ---------------------------------------------------------------------------


def _crossbeam_body(spec, line, length_mm, dgn_model, mirror=False):
    """横担（构件A）的实体（未转元素）。``mirror`` 时截面关于扫掠轴镜像。"""
    x_axis, y_axis = _frame_vectors(line['heading_deg'])
    if mirror:
        y_axis = (-y_axis[0], -y_axis[1], 0.0)
    start = line['start_mm']
    # 截面点 (depth, width) -> 世界；depth 向下（-z），width 沿 +y。
    points = _world_profile(start, (0.0, 0.0, -1.0), y_axis, spec)
    profile = _create_shape(points, dgn_model)
    if profile is None:
        return None
    return _sweep_shape_to_body(
        profile, (x_axis[0] * length_mm, x_axis[1] * length_mm, 0.0), dgn_model)


def _build_crossbeam(spec, line, length_mm, dgn_model, mirror=False):
    """横担（构件A）：截面沿辅助线扫掠，顶面落在辅助线上。

    ``mirror=True`` 时截面关于扫掠轴镜像（槽钢背靠背用：两根腹板朝向相反）。
    """
    body = _crossbeam_body(spec, line, length_mm, dgn_model, mirror)
    if body is None:
        return None
    return _body_to_element(body, dgn_model, 'crossbeam')


def _brace_axes(type_key):
    """返回 (axis, up)（局部，x-z 平面内）。"""
    c = math.cos(math.radians(data.BRACE_ANGLE_DEG))
    s = math.sin(math.radians(data.BRACE_ANGLE_DEG))
    if type_key == 1:
        return (c, 0.0, s), (-s, 0.0, c)
    return (c, 0.0, -s), (s, 0.0, c)


def _to_world_local(local_mm, start_mm, heading_deg):
    x_axis, y_axis = _frame_vectors(heading_deg)
    x, y, z = local_mm
    return (start_mm[0] + x * x_axis[0] + y * y_axis[0],
            start_mm[1] + x * x_axis[1] + y * y_axis[1],
            start_mm[2] + z)


def _build_brace(spec, line, resolved, dgn_model):
    """斜撑（构件B）：45°，两端分别切至设备面与横担面。"""
    type_key = resolved['type']
    height = resolved['H']
    depth_a = resolved['section_a']['height']
    depth_b = resolved['section_b']['height']
    axis, up = _brace_axes(type_key)
    plate_z = -height if type_key == 1 else height
    run = resolved['brace_run']
    length = math.hypot(run, run)
    # 两端各预留一小段供布尔切割；切割失败时伸出量也不至于过大。
    overrun = 50.0

    # 轴心起点（局部），沿轴预留 overrun 以便切割。
    local_origin = (-axis[0] * overrun, 0.0, plate_z - axis[2] * overrun)
    origin_world = _to_world_local(local_origin, line['start_mm'],
                                   line['heading_deg'])
    # 世界方向。
    x_axis, y_axis = _frame_vectors(line['heading_deg'])
    axis_world = (axis[0] * x_axis[0], axis[0] * x_axis[1], axis[2])
    up_world = (up[0] * x_axis[0], up[0] * x_axis[1], up[2])

    # 截面以轴心为中心：depth ∈ [-h/2, h/2]。
    points = _world_profile(origin_world, up_world, y_axis, spec,
                            depth_offset=-depth_b / 2.0)
    profile = _create_shape(points, dgn_model)
    if profile is None:
        return None
    sweep_mm = (axis_world[0] * (length + 2.0 * overrun),
                axis_world[1] * (length + 2.0 * overrun),
                axis_world[2] * (length + 2.0 * overrun))
    body = _sweep_shape_to_body(profile, sweep_mm, dgn_model)
    if body is None:
        return None

    to_world = _make_frame(line['start_mm'], line['heading_deg'])
    big = 2000.0
    cutter = _box_body(-big, -big, -big, 0.0, big, big, to_world, dgn_model)
    if not _subtract_body(body, cutter):
        _log('brace: equipment-face cut failed')
    if type_key == 1:
        cutter = _box_body(-big, -big, -depth_a, big, big, big, to_world,
                           dgn_model)
    else:
        cutter = _box_body(-big, -big, -big, big, big, 0.0, to_world, dgn_model)
    if not _subtract_body(body, cutter):
        _log('brace: crossbeam-face cut failed')
    return _body_to_element(body, dgn_model, 'brace')


def _box_body(x0, y0, z0, x1, y1, z1, to_world, dgn_model):
    """局部坐标盒体（用于端面切割）。"""
    rectangle = [to_world((x0, y0, z0)), to_world((x1, y0, z0)),
                 to_world((x1, y1, z0)), to_world((x0, y1, z0))]
    profile = _create_shape(rectangle, dgn_model)
    if profile is None:
        return None
    return _sweep_shape_to_body(profile, (0.0, 0.0, z1 - z0), dgn_model)


def _stiffener_body(line, resolved, dgn_model, x_mm=None, y_min=None,
                    y_max=None):
    """筋板实体（未转元素）；``y_min``/``y_max`` 可限定只贴腹板某一侧。"""
    to_world = _make_frame(line['start_mm'], line['heading_deg'])
    t = resolved['stiffener_t']
    section_a = resolved['section_a']
    height_a = section_a['height']
    tf_a = section_a['tf']
    x = resolved['attach_x'] if x_mm is None else float(x_mm)
    if y_min is None or y_max is None:
        y_half = section_a['width'] / 2.0
        y_min, y_max = -y_half, y_half
    z_bottom = -(height_a - tf_a)   # 下翼缘内表面
    z_top = -tf_a                   # 上翼缘内表面
    points = [to_world((x, y_min, z_bottom)), to_world((x, y_max, z_bottom)),
              to_world((x, y_max, z_top)), to_world((x, y_min, z_top))]
    profile = _create_shape(points, dgn_model)
    if profile is None:
        return None
    x_axis, _y_axis = _frame_vectors(line['heading_deg'])
    return _sweep_shape_to_body(
        profile, (x_axis[0] * t, x_axis[1] * t, 0.0), dgn_model)


def _build_stiffener(line, resolved, dgn_model, x_mm=None):
    """交点处 10mm 筋板：**通长**覆盖横担上下翼缘内表面。

    筋板为横担腹板平面内、垂直于横担轴的竖直板（默认位于 x = attach_x，
    可用 ``x_mm`` 指定其它位置），高度方向由**下翼缘内表面**一直到
    **上翼缘内表面**，宽度取横担截面宽。
    """
    body = _stiffener_body(line, resolved, dgn_model, x_mm)
    if body is None:
        return None
    return _body_to_element(body, dgn_model, 'stiffener')


def _union_body(target_body, tool_body):
    """把 tool_body 并入 target_body（并集），失败返回 False。"""
    if tool_body is None:
        return False
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanUnion(target_body, tools)
    except Exception as error:
        _log('BooleanUnion exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if status is None:
        return True
    return BentleyStatus.eSUCCESS == status


def _add_plate_at(builder, line, center_mm, plate_resolved, dgn_model):
    """在设备面（x=0）上的 center_mm 处放一块 N8 连接板 + 螺栓（整体镜像）。

    连接板落在设备一侧（x ∈ [-T, 0]，外表面与 x=0 齐平），螺栓头朝外。
    """
    to_world = _make_frame(line['start_mm'], line['heading_deg'])
    origin_mm = to_world(center_mm)
    uor = _uor(dgn_model)
    origin = DPoint3d.From(origin_mm[0] * uor, origin_mm[1] * uor,
                           origin_mm[2] * uor)
    # 朝向 +180°，使连接板沿 -x 方向（设备一侧）伸出。
    frame = anchor._PlateFrame(origin, uor, line['heading_deg'] + 180.0)
    plate_geom._add_plate(builder, frame, dgn_model, plate_resolved)
    for hole_y, hole_z in plate_resolved['holes']:
        plate_geom._add_bolt(builder, frame, dgn_model, plate_resolved,
                             hole_y, hole_z)


# ---------------------------------------------------------------------------
# 单元装配与清单
# ---------------------------------------------------------------------------


def _build_bom_items(resolved, plate_resolved):
    plate_spec = '%.0f×%.0f×%.0f' % (
        plate_resolved['E'], plate_resolved['E'], plate_resolved['T'])
    bolt_spec = 'M%.0f×%.0f' % (
        plate_resolved['bolt_dia'], plate_resolved['bolt_length'])
    return [
        {'code': 'MemberA', 'name': COMPONENT_A_NAME,
         'specification': resolved['comp_a'], 'length': resolved['L'],
         'quantity': 1, 'unit': '件'},
        {'code': 'MemberB', 'name': COMPONENT_B_NAME,
         'specification': resolved['comp_b'],
         'length': round(resolved['brace_length'], 1),
         'quantity': 1, 'unit': '件'},
        {'code': 'Plate', 'name': COMPONENT_PLATE_NAME,
         'specification': plate_spec, 'length': plate_resolved['T'],
         'quantity': 2, 'unit': '件'},
        {'code': 'Bolt', 'name': COMPONENT_BOLT_NAME,
         'specification': bolt_spec, 'length': plate_resolved['bolt_length'],
         'quantity': plate_resolved['bolt_count'] * 2, 'unit': '件'},
        {'code': 'Stiffener', 'name': COMPONENT_STIFFENER_NAME,
         'specification': '%.0f 厚' % resolved['stiffener_t'],
         'length': resolved['stiffener_t'], 'quantity': 1, 'unit': '件'},
    ]


def _attach_items(cell, result):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('number', ''),
        assembly_spec='%s + %s' % (result.get('comp_a', ''),
                                   result.get('comp_b', '')),
        components=result.get('bom_items', ()))


# ---------------------------------------------------------------------------
# 对外建模接口
# ---------------------------------------------------------------------------


def build_single_bracket_cell(line, options=None, number=''):
    """构建单三角架单元但**不写入模型**，返回 ``(builder, 统计字典)``。"""
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('请先打开并激活一个 DGN 模型。')
    dgn_model = model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    resolved = data.resolve_options(options, line['length_mm'])
    plate_resolved = plate_data.resolve_options({
        'type': resolved['plate_type'], 'mode': 'H',
        'heading_deg': line['heading_deg'], 'mount': 'wall'})

    builder = anchor._AnchorPlateCellBuilder(dgn_model, CELL_NAME)

    crossbeam = _build_crossbeam(resolved['comp_a'], line, resolved['L'],
                                 dgn_model)
    if crossbeam is None:
        raise RuntimeError('横担（构件A）创建失败。')
    builder.add(crossbeam)

    brace = _build_brace(resolved['comp_b'], line, resolved, dgn_model)
    if brace is None:
        raise RuntimeError('斜撑（构件B）创建失败。')
    builder.add(brace)

    stiffener = _build_stiffener(line, resolved, dgn_model)
    if stiffener is not None:
        builder.add(stiffener)

    depth_a = resolved['section_a']['height']
    _add_plate_at(builder, line, (0.0, 0.0, -depth_a / 2.0),
                  plate_resolved, dgn_model)
    brace_center_z = (-resolved['H'] if resolved['type'] == 1
                      else resolved['H'])
    _add_plate_at(builder, line, (0.0, 0.0, brace_center_z),
                  plate_resolved, dgn_model)

    builder.build()
    result = dict(resolved)
    result['child_count'] = builder.child_count
    result['cell_name'] = CELL_NAME
    result['number'] = str(number or '')
    result['plate_resolved'] = dict(plate_resolved)
    result['bom_items'] = _build_bom_items(resolved, plate_resolved)
    _log('single bracket: subtype=%s type=%d H=%.0f L=%.0f run=%.0f '
         'overhang=%.0f plate=%d cells=%d number=%s'
         % (resolved['subtype'], resolved['type'], resolved['H'],
            resolved['L'], resolved['brace_run'], resolved['end_overhang'],
            resolved['plate_type'], builder.child_count, result['number'] or '-'))
    return builder, result


def draw_single_bracket(line, options=None, number=''):
    """创建整组单三角架单元并写入活动模型，返回 ``(cell, 统计字典)``。"""
    builder, result = build_single_bracket_cell(line, options, number)
    cell = builder.commit()
    _attach_items(cell, result)
    return cell, result


def _delete_element(handle):
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def replace_single_bracket(line, options, previous_handle, number=''):
    """重建单三角架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = build_single_bracket_cell(line, options, number)
    new_handle = builder.commit()
    _attach_items(new_handle, result)
    deleted = _delete_element(previous_handle)
    return new_handle, result, deleted


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(
            _PLUGIN_ROOT, '模块', '输出', '单三角架_bom.json')
    return psb.export_combined_bom(output_path)
