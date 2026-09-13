# -*- coding: utf-8 -*-
"""沿用户选择的水平或带坡度 SmartLine 创建普通钢结构围栏。

第一版构件：
* 立柱：48.3 x 3.2 钢管；按三维路径实长排布，最大间距 2000 mm。
* 顶部扶手：42.4 x 3.2 钢管，中心标高 1017 mm。
* 中间横杆：33.7 x 3.2 钢管，中心标高 560 mm。
* 杆件交点：直径 76 mm 的实体连接球。
* 踢脚板：130 x 6 mm，位于路径选定内侧，通过支架连接立柱。
* 折点：水平转角按中心线 R140；纯变坡点保留尖折并设置立柱。
* 可选端部闭合：顶部扶手在端部以 U 形弯回中间横杆。

所有构件使用精确 RGB (255, 204, 0)，整道围栏封装为普通单元
STEEL_HANDRAIL。脚本面向 Bentley Power Platform Python (MSPy)。
"""

from __future__ import print_function

from math import acos, ceil, cos, floor, hypot, pi, sin, tan
import json
import os
import tkinter as tk
import tkinter
from tkinter import ttk
import win32gui

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# --- 图纸参数（mm）----------------------------------------------------------
TOP_RAIL_Z = 1017.0              # 顶部扶手管中心相对路径标高的高度。
KNEE_RAIL_Z = 560.0              # 中间横杆管中心相对路径标高的高度。
TOP_RAIL_OD = 42.4               # 顶部扶手钢管外径。
TOP_RAIL_WALL = 3.2              # 顶部扶手钢管壁厚。
KNEE_RAIL_OD = 33.7              # 中间横杆钢管外径。
KNEE_RAIL_WALL = 3.2             # 中间横杆钢管壁厚。
STANCHION_OD = 48.3              # 立柱钢管外径。
STANCHION_WALL = 3.2             # 立柱钢管壁厚。
BALL_DIAMETER = 76.0             # 横杆与立柱交点处连接球直径。
KICKPLATE_HEIGHT = 130.0         # 踢脚板竖向高度。
KICKPLATE_THICKNESS = 6.0        # 踢脚板厚度。
KICKPLATE_BOTTOM_Z = 10.0        # 踢脚板底边相对路径标高的净高。
KICKPLATE_CLEARANCE = 10.0       # 立柱外壁至踢脚板近侧表面的净距。
KICKPLATE_BRACKET_WIDTH = 6.0    # 踢脚板连接支架沿路径方向的宽度。
KICKPLATE_BRACKET_HEIGHT = 50.0  # 踢脚板连接支架的竖向高度。

# 类型2：立柱下弯后侧装在钢结构腹板上的典型节点。
TYPE2_BEND_RADIUS = 76.0                 # 类型2立柱下弯段的管中心线半径。
TYPE2_STRUCTURE_OFFSET_DEFAULT = 120.0  # 类型2立柱中心至结构连接板中心的默认距离。
TYPE2_PLATE_HORIZONTAL = 146.0          # 类型1/2竖向连接板的水平边长度。
TYPE2_PLATE_VERTICAL = 75.0             # 类型1/2竖向连接板的竖向边长度。
TYPE2_PLATE_THICKNESS = 10.0            # 类型1/2竖向连接板厚度。
TYPE2_TUBE_PLATE_OVERLAP = 2.0          # 类型2水平管端伸入连接板的搭接量。
TYPE1_PLATE_CENTER_DROP = 76.0          # 类型1连接板中心相对立柱起点的下落高度。
# 压扁端暂定尺寸，可按节点详图调整；长轴沿路径水平切向。
TYPE1_FLAT_MAJOR = 70.0                 # 类型1压扁端椭圆截面的长轴全长。
TYPE1_FLAT_MINOR = STANCHION_OD / 3.0  # 类型1压扁端椭圆截面的短轴全长。
TYPE1_TRANSITION_LENGTH = 38.5         # 类型1圆管过渡至压扁截面的竖向长度。
TYPE3_PLATE_LENGTH = 145.0             # 类型3水平底板沿路径方向的长度。
TYPE3_PLATE_WIDTH = 75.0               # 类型3水平底板横向宽度。
TYPE3_PLATE_THICKNESS = 10.0           # 类型3水平底板厚度。
# CONNECTION_TYPE_DEFAULT：未由调用方指定时采用的立柱连接形式。
# CONNECTION_TYPE_LABELS：设置界面中显示的立柱连接形式选项。
# CONNECTION_LABEL_TO_VALUE：把界面中文选项映射为内部连接类型代码。
CONNECTION_TYPE_DEFAULT = "type2"
CONNECTION_TYPE_LABELS = (
    "类型1（直柱贴板侧装）",
    "类型2（侧装钢结构）",
    "类型3（底板顶装）",
    "类型4（预留）",
)
CONNECTION_LABEL_TO_VALUE = {
    "类型1（直柱贴板侧装）": "type1",
    "类型2（侧装钢结构）": "type2",
    "类型3（底板顶装）": "type3",
    "类型4（预留）": "type4",
}

POST_SPACING_MAX = 2000.0       # 相邻立柱沿栏杆路径允许的最大中心距。
MODULE = 50.0                   # 立柱跨距优先采用的尺寸模数。
CORNER_POST_NOMINAL = 300.0     # 转角顶点至两侧邻近立柱的目标距离。
CORNER_RADIUS = 140.0           # 水平转角处横杆中心线的圆弧半径。
PATH_LATERAL_OFFSET = -34.2      # 有符号横向偏移；正值向所选侧，负值向所选侧的反方向。
END_CLOSURE_REACH = 300.0       # 端部闭合回弯沿路径方向伸出的总距离。

# 端部闭合：不闭合 / 仅始端 / 仅末端 / 两端。
# END_CLOSURE_DEFAULT：未指定时采用的端部闭合模式。
# END_CLOSURE_LABELS：设置界面中显示的端部闭合选项。
# END_CLOSURE_LABEL_TO_VALUE：把界面中文选项映射为内部闭合模式代码。
END_CLOSURE_DEFAULT = "none"
END_CLOSURE_LABELS = (
    "不闭合",
    "仅始端",
    "仅末端",
    "两端",
)
END_CLOSURE_LABEL_TO_VALUE = {
    "不闭合": "none",
    "仅始端": "start",
    "仅末端": "end",
    "两端": "both",
}

COLOR_RGB = (255, 204, 0)  # 新生成围栏元素采用的RGB显示颜色。
# CELL_NAME：生成的普通单元名称。
CELL_NAME = "STEEL_HANDRAIL"
PATH_TOLERANCE_MM = 0.01   # 路径清理、重合判断和几何连续性检查容差。
REGENERATE_DELAY_MS = 150  # 界面选项改变后延迟刷新预览的时间（毫秒）。

# --- 钢材清单 ItemType（属性名保持英文，值可为中文）---------------------------
ITEM_LIBRARY_NAME = "SteelHandrailComponents"
ITEM_TYPE_PREFIX = "SteelHandrailComponent"
ITEM_PROPERTY_DEFINITIONS = (
    ("ComponentName", CustomProperty.Type1.eString),
    ("Specification", CustomProperty.Type1.eString),
    ("DesignLengthMm", CustomProperty.Type1.eDouble),
    ("Quantity", CustomProperty.Type1.eInteger),
    ("Unit", CustomProperty.Type1.eString),
)
BOM_JSON_NAME = "普通钢结构围栏_bom.json"


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _point_uor(origin, point_mm, uor_per_mm):
    return DPoint3d.From(
        origin.x + point_mm[0] * uor_per_mm,
        origin.y + point_mm[1] * uor_per_mm,
        origin.z + point_mm[2] * uor_per_mm,
    )


def _element_color():
    """返回可直接写入元素的精确 RGB 颜色编码，不改写活动颜色表。"""
    color_def = IntColorDef(COLOR_RGB[0], COLOR_RGB[1], COLOR_RGB[2])
    return DgnColorMap.CreateElementColor(
        color_def, None, None, ISessionMgr.GetActiveDgnFile()
    )


def _apply_color(element, color):
    if element is None:
        return None
    if color is None:
        return element
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)
    return element


class _HandrailCellBuilder(object):
    def __init__(self, dgn_model):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, CELL_NAME, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("围栏子元素创建失败。")
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError("无法将围栏子元素加入普通单元。")
        self.child_count += 1

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError("无法完成围栏普通单元。")

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError("无法将围栏写入活动模型。")
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


def _primitive_to_element(dgn_model, primitive, color):
    if primitive is None:
        return None
    element = EditElementHandle()
    status = DraftingElementSchema.ToElement(element, primitive, None, dgn_model)
    if not _succeeded(status):
        return None
    return _apply_color(element, color)


def _create_cylinder(dgn_model, start, end, radius):
    return _primitive_to_element(
        dgn_model,
        ISolidPrimitive.CreateDgnCone(DgnConeDetail(start, end, radius, radius, True)),
        None,
    )


def _create_sphere(dgn_model, center, radius, color):
    detail = DgnSphereDetail(center, radius)
    return _primitive_to_element(
        dgn_model, ISolidPrimitive.CreateDgnSphere(detail), color
    )


def _create_torus(dgn_model, center, vector_x, vector_y, major, minor, sweep):
    detail = DgnTorusPipeDetail(
        center, vector_x, vector_y, major, minor, sweep, True
    )
    return _primitive_to_element(
        dgn_model, ISolidPrimitive.CreateDgnTorusPipe(detail), None
    )


def _boolean_hollow(dgn_model, outer, inner, color):
    if outer is None or inner is None:
        return None
    outer_status, outer_body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    inner_status, inner_body = SolidUtil.Convert.ElementToBody(inner, True, True, False)
    if not _succeeded(outer_status) or not _succeeded(inner_status):
        return None
    tools = ISolidKernelEntityPtrArray()
    tools.append(inner_body)
    if not _succeeded(SolidUtil.Modify.BooleanSubtract(outer_body, tools)):
        return None
    result = EditElementHandle()
    if not _succeeded(SolidUtil.Convert.BodyToElement(result, outer_body, outer, dgn_model)):
        return None
    return _apply_color(result, color)


def _create_hollow_tube(
    dgn_model, origin, uor_per_mm, start_mm, end_mm, outside_diameter, wall, color
):
    if wall <= 0.0 or outside_diameter <= 2.0 * wall:
        raise ValueError("钢管外径必须大于两倍壁厚。")
    delta = tuple(end_mm[i] - start_mm[i] for i in range(3))
    length = hypot(hypot(delta[0], delta[1]), delta[2])
    if length <= PATH_TOLERANCE_MM:
        raise ValueError("钢管长度必须大于零。")
    start = _point_uor(origin, start_mm, uor_per_mm)
    end = _point_uor(origin, end_mm, uor_per_mm)
    outer = _create_cylinder(
        dgn_model, start, end, outside_diameter * uor_per_mm / 2.0
    )
    extension = 2.0 / length
    inner_start_mm = tuple(start_mm[i] - delta[i] * extension for i in range(3))
    inner_end_mm = tuple(end_mm[i] + delta[i] * extension for i in range(3))
    inner = _create_cylinder(
        dgn_model,
        _point_uor(origin, inner_start_mm, uor_per_mm),
        _point_uor(origin, inner_end_mm, uor_per_mm),
        (outside_diameter / 2.0 - wall) * uor_per_mm,
    )
    return _boolean_hollow(dgn_model, outer, inner, color)


def _create_hollow_arc(
    dgn_model, origin, uor_per_mm, center_mm, radial_start, tangent_start,
    sweep, outside_diameter, wall, color, centerline_radius=CORNER_RADIUS
):
    if sweep <= 0.0 or sweep >= 2.0 * pi:
        raise ValueError("弯管圆弧角度无效。")
    center = _point_uor(origin, center_mm, uor_per_mm)
    vector_x = DVec3d.From(radial_start[0], radial_start[1], radial_start[2])
    vector_y = DVec3d.From(tangent_start[0], tangent_start[1], tangent_start[2])
    outer = _create_torus(
        dgn_model, center, vector_x, vector_y,
        centerline_radius * uor_per_mm,
        outside_diameter * uor_per_mm / 2.0,
        sweep,
    )

    extension = 2.0 / centerline_radius
    c = cos(extension)
    s = sin(extension)
    inner_x = DVec3d.From(
        radial_start[0] * c - tangent_start[0] * s,
        radial_start[1] * c - tangent_start[1] * s,
        radial_start[2] * c - tangent_start[2] * s,
    )
    inner_y = DVec3d.From(
        radial_start[0] * s + tangent_start[0] * c,
        radial_start[1] * s + tangent_start[1] * c,
        radial_start[2] * s + tangent_start[2] * c,
    )
    inner = _create_torus(
        dgn_model, center, inner_x, inner_y,
        centerline_radius * uor_per_mm,
        (outside_diameter / 2.0 - wall) * uor_per_mm,
        sweep + 2.0 * extension,
    )
    return _boolean_hollow(dgn_model, outer, inner, color)


def _create_prism_from_corners(dgn_model, corners, thickness_uor, color):
    points = DPoint3dArray()
    for point in corners:
        points.append(point)
    points.append(corners[0])
    profile = EditElementHandle()
    model_ref = ISessionMgr.ActiveDgnModelRef
    status = ShapeHandler.CreateShapeElement(
        profile, None, points, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        return None
    body_status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if not _succeeded(body_status):
        return None
    if not _succeeded(SolidUtil.Modify.ThickenSheet(body, thickness_uor, 0.0)):
        return None
    result = EditElementHandle()
    if not _succeeded(SolidUtil.Convert.BodyToElement(result, body, profile, dgn_model)):
        return None
    return _apply_color(result, color)


def _create_kickplate_bracket(
    dgn_model, origin, uor_per_mm, point, tangent, side_sign, color
):
    """创建立柱至踢脚板的短连接板。

    连接板位于“内侧法向-Z”平面内，沿路径切向厚 6 mm；靠立柱端轻微
    伸入管外轮廓 2 mm，保证显示和实体接触稳定，另一端伸入踢脚板。
    """
    tx, ty, _ = _horizontal_unit(tangent)
    nx, ny, _ = _horizontal_normal(tangent, side_sign)
    half_width = KICKPLATE_BRACKET_WIDTH / 2.0
    # 对左侧，轮廓法向为 +tangent；对右侧为 -tangent。轮廓放在相反一侧，
    # 拉伸后连接板便以立柱里程面为中心。
    tangent_offset = -side_sign * half_width
    radial_start = STANCHION_OD / 2.0 - 2.0
    radial_end = (
        STANCHION_OD / 2.0
        + KICKPLATE_CLEARANCE
        + KICKPLATE_THICKNESS
    )
    center_z = point[2] + KICKPLATE_BOTTOM_Z + KICKPLATE_HEIGHT / 2.0
    z_start = center_z - KICKPLATE_BRACKET_HEIGHT / 2.0
    z_end = center_z + KICKPLATE_BRACKET_HEIGHT / 2.0

    def bracket_point(radial, z):
        return _point_uor(
            origin,
            (
                point[0] + tx * tangent_offset + nx * radial,
                point[1] + ty * tangent_offset + ny * radial,
                z,
            ),
            uor_per_mm,
        )

    corners = [
        bracket_point(radial_start, z_start),
        bracket_point(radial_end, z_start),
        bracket_point(radial_end, z_end),
        bracket_point(radial_start, z_end),
    ]
    return _create_prism_from_corners(
        dgn_model, corners, KICKPLATE_BRACKET_WIDTH * uor_per_mm, color
    )


def _distance3(a, b):
    return hypot(hypot(b.x - a.x, b.y - a.y), b.z - a.z)


def _collect_linear_pieces(curve_vector, pieces):
    for primitive in curve_vector:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
            segment = primitive.GetLine()
            pieces.append([_copy_dpoint(segment.StartPoint), _copy_dpoint(segment.EndPoint)])
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
            points = [_copy_dpoint(point) for point in primitive.GetLineString()]
            if len(points) >= 2:
                pieces.append(points)
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
            child = primitive.GetChildCurveVector()
            if child is None:
                raise ValueError("复杂链包含无法读取的子路径。")
            _collect_linear_pieces(child, pieces)
        else:
            raise ValueError("所选路径含圆弧或曲线；第一版请选择纯直线 SmartLine。")


def _extract_linear_vertices(element_handle, uor_per_mm):
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError("请选择非闭合直线、折线或纯直线复杂链。")
    pieces = []
    _collect_linear_pieces(curve, pieces)
    tolerance = PATH_TOLERANCE_MM * uor_per_mm
    vertices = []
    for piece in pieces:
        cleaned = [piece[0]]
        for point in piece[1:]:
            if _distance3(cleaned[-1], point) > tolerance:
                cleaned.append(point)
        if len(cleaned) < 2:
            continue
        if not vertices:
            vertices.extend(cleaned)
        elif _distance3(vertices[-1], cleaned[0]) <= tolerance:
            vertices.extend(cleaned[1:])
        elif _distance3(vertices[-1], cleaned[-1]) <= tolerance:
            cleaned.reverse()
            vertices.extend(cleaned[1:])
        else:
            raise ValueError("复杂链中的直线段不连续。")
    if len(vertices) < 2:
        raise ValueError("路径至少需要两个不同顶点。")
    if _distance3(vertices[0], vertices[-1]) <= tolerance:
        raise ValueError("第一版暂不支持闭合围栏路径。")
    return vertices


def _to_local_path(vertices, uor_per_mm):
    origin = _copy_dpoint(vertices[0])
    points = [
        (
            (point.x - origin.x) / uor_per_mm,
            (point.y - origin.y) / uor_per_mm,
            (point.z - origin.z) / uor_per_mm,
        )
        for point in vertices
    ]
    return origin, points


def _horizontal_unit(tangent):
    """返回三维切向在水平面的单位投影。"""
    length = hypot(tangent[0], tangent[1])
    if length <= 1.0e-12:
        raise ValueError("路径包含竖直段，无法确定围栏内外侧。")
    return (tangent[0] / length, tangent[1] / length, 0.0)


def _horizontal_normal(tangent, side_sign):
    tx, ty, _ = _horizontal_unit(tangent)
    return (-ty * side_sign, tx * side_sign, 0.0)

def _offset_path_points(points, side_sign, offset):
    '''将辅助线路径向所选内侧平移，折点取相邻偏移直线的交点。'''
    points = _clean_and_validate_points(points)
    tangents = []
    for start, end in zip(points, points[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        tangents.append((dx / length, dy / length, (end[2] - start[2]) / length))

    def shifted(point, tangent):
        normal = _horizontal_normal(tangent, side_sign)
        return (point[0] + normal[0] * offset,
                point[1] + normal[1] * offset, point[2])

    result = [shifted(points[0], tangents[0])]
    for index in range(1, len(points) - 1):
        incoming, outgoing = tangents[index - 1], tangents[index]
        turn = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
        dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
        first = shifted(points[index], incoming)
        if abs(turn) <= 1.0e-12:
            if dot < 0.0:
                raise ValueError('路径包含 180° 折返，无法计算横向偏移。')
            result.append(first)
            continue
        if abs(incoming[2]) > 1.0e-9 or abs(outgoing[2]) > 1.0e-9:
            raise ValueError('同一折点同时存在平面转向和坡度，无法计算横向偏移。')
        second = shifted(points[index], outgoing)
        dx, dy = second[0] - first[0], second[1] - first[1]
        advance = (dx * outgoing[1] - dy * outgoing[0]) / turn
        result.append((first[0] + incoming[0] * advance,
                       first[1] + incoming[1] * advance, points[index][2]))
    result.append(shifted(points[-1], tangents[-1]))
    return result


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point, start, end):
    scale = max(1.0, hypot(end[0] - start[0], end[1] - start[1]))
    if abs(_cross(start, end, point)) > PATH_TOLERANCE_MM * scale:
        return False
    return (
        min(start[0], end[0]) - PATH_TOLERANCE_MM <= point[0] <= max(start[0], end[0]) + PATH_TOLERANCE_MM
        and min(start[1], end[1]) - PATH_TOLERANCE_MM <= point[1] <= max(start[1], end[1]) + PATH_TOLERANCE_MM
    )


def _segments_intersect(a, b, c, d):
    ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
    cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
    if (ab_c > 0.0) != (ab_d > 0.0) and (cd_a > 0.0) != (cd_b > 0.0):
        return True
    return any((
        abs(ab_c) <= PATH_TOLERANCE_MM and _point_on_segment(c, a, b),
        abs(ab_d) <= PATH_TOLERANCE_MM and _point_on_segment(d, a, b),
        abs(cd_a) <= PATH_TOLERANCE_MM and _point_on_segment(a, c, d),
        abs(cd_b) <= PATH_TOLERANCE_MM and _point_on_segment(b, c, d),
    ))


def _clean_and_validate_points(points):
    cleaned = [points[0]]
    for point in points[1:]:
        distance = hypot(
            hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]),
            point[2] - cleaned[-1][2],
        )
        if distance > PATH_TOLERANCE_MM:
            cleaned.append(point)
    if len(cleaned) < 2:
        raise ValueError("路径长度必须大于零。")
    for start, end in zip(cleaned, cleaned[1:]):
        if hypot(end[0] - start[0], end[1] - start[1]) <= PATH_TOLERANCE_MM:
            raise ValueError("路径包含竖直段，无法确定围栏内外侧。")
    for i in range(len(cleaned) - 1):
        for j in range(i + 2, len(cleaned) - 1):
            if _segments_intersect(cleaned[i], cleaned[i + 1], cleaned[j], cleaned[j + 1]):
                raise ValueError("路径存在自交或重叠，请先整理 SmartLine。")
    return cleaned


def _build_fillet_path(points):
    """生成稳妥的三维路径：坡段保留，水平转角采用 R140。"""
    points = _clean_and_validate_points(points)
    segments = []
    for index in range(len(points) - 1):
        dx = points[index + 1][0] - points[index][0]
        dy = points[index + 1][1] - points[index][1]
        dz = points[index + 1][2] - points[index][2]
        horizontal_length = hypot(dx, dy)
        length = hypot(horizontal_length, dz)
        segments.append({
            "horizontal_length": horizontal_length,
            "length": length,
            "horizontal_tangent": (dx / horizontal_length, dy / horizontal_length),
            "tangent": (dx / length, dy / length, dz / length),
            "grade": dz / horizontal_length,
        })

    corners = [None] * len(points)
    for index in range(1, len(points) - 1):
        incoming_segment = segments[index - 1]
        outgoing_segment = segments[index]
        incoming = incoming_segment["horizontal_tangent"]
        outgoing = outgoing_segment["horizontal_tangent"]
        dot = max(-1.0, min(1.0, incoming[0] * outgoing[0] + incoming[1] * outgoing[1]))
        turn = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
        angle = acos(dot)
        if angle < 1.0e-7:
            if abs(incoming_segment["grade"] - outgoing_segment["grade"]) > 1.0e-9:
                corners[index] = {"kind": "grade_break", "point": points[index]}
            continue
        if abs(pi - angle) < 1.0e-5:
            raise ValueError("路径包含 180° 折返，无法生成 R140 转角。")
        if (
            abs(incoming_segment["grade"]) > 1.0e-9
            or abs(outgoing_segment["grade"]) > 1.0e-9
        ):
            raise ValueError(
                "同一折点同时存在平面转向和坡度，稳妥版不生成空间弯头；请拆分或调整路径。"
            )
        tangent_distance = CORNER_RADIUS * tan(angle / 2.0)
        if tangent_distance > CORNER_POST_NOMINAL + PATH_TOLERANCE_MM:
            raise ValueError("转角过尖，R140 的切点距离超过 300 mm；请放缓转角。")
        vertex = points[index]
        start = (
            vertex[0] - incoming[0] * tangent_distance,
            vertex[1] - incoming[1] * tangent_distance,
            vertex[2],
        )
        end = (
            vertex[0] + outgoing[0] * tangent_distance,
            vertex[1] + outgoing[1] * tangent_distance,
            vertex[2],
        )
        side = 1.0 if turn > 0.0 else -1.0
        left = (-incoming[1], incoming[0])
        center = (
            start[0] + left[0] * side * CORNER_RADIUS,
            start[1] + left[1] * side * CORNER_RADIUS,
            vertex[2],
        )
        radial = ((start[0] - center[0]) / CORNER_RADIUS, (start[1] - center[1]) / CORNER_RADIUS, 0.0)
        corners[index] = {
            "kind": "fillet",
            "start": start,
            "end": end,
            "center": center,
            "radial": radial,
            "tangent": (incoming[0], incoming[1], 0.0),
            "angle": angle,
            "turn_sign": side,
            "tangent_distance": tangent_distance,
        }

    # 相邻圆角不得在同一原始线段内重叠。
    for index, segment in enumerate(segments):
        start_corner = corners[index]
        end_corner = corners[index + 1]
        used_at_start = (
            start_corner["tangent_distance"]
            if start_corner and start_corner["kind"] == "fillet" else 0.0
        )
        used_at_end = (
            end_corner["tangent_distance"]
            if end_corner and end_corner["kind"] == "fillet" else 0.0
        )
        if used_at_start + used_at_end >= segment["horizontal_length"] - PATH_TOLERANCE_MM:
            raise ValueError("相邻转角距离过短，无法容纳 R140 圆角。")

    pieces = []
    corner_records = []
    station = 0.0
    current = points[0]
    for index in range(len(points) - 1):
        next_corner = corners[index + 1]
        line_end = (
            next_corner["start"]
            if next_corner and next_corner["kind"] == "fillet"
            else points[index + 1]
        )
        delta = tuple(line_end[i] - current[i] for i in range(3))
        line_length = hypot(hypot(delta[0], delta[1]), delta[2])
        if line_length > PATH_TOLERANCE_MM:
            tangent = tuple(value / line_length for value in delta)
            pieces.append({"type": "line", "start": current, "end": line_end,
                           "tangent": tangent, "start_station": station,
                           "end_station": station + line_length, "length": line_length})
            station += line_length
        if next_corner and next_corner["kind"] == "fillet":
            arc_length = CORNER_RADIUS * next_corner["angle"]
            arc = dict(next_corner)
            arc.update({"type": "arc", "start_station": station,
                        "end_station": station + arc_length, "length": arc_length})
            pieces.append(arc)
            corner_records.append(arc)
            station += arc_length
            current = next_corner["end"]
        else:
            current = points[index + 1]
            if next_corner and next_corner["kind"] == "grade_break":
                grade_break = dict(next_corner)
                grade_break["station"] = station
                corner_records.append(grade_break)
    return pieces, corner_records, station


def _point_tangent_at_station(pieces, station):
    for piece in pieces:
        if station <= piece["end_station"] + PATH_TOLERANCE_MM:
            fraction = (station - piece["start_station"]) / piece["length"]
            fraction = max(0.0, min(1.0, fraction))
            if piece["type"] == "line":
                start, end = piece["start"], piece["end"]
                point = tuple(start[i] + (end[i] - start[i]) * fraction for i in range(3))
                return point, piece["tangent"]
            theta = piece["angle"] * fraction
            radial, tangent0 = piece["radial"], piece["tangent"]
            c, s = cos(theta), sin(theta)
            radial_now = tuple(radial[i] * c + tangent0[i] * s for i in range(3))
            tangent_now = tuple(-radial[i] * s + tangent0[i] * c for i in range(3))
            point = tuple(piece["center"][i] + radial_now[i] * CORNER_RADIUS for i in range(3))
            return point, tangent_now
    last = pieces[-1]
    return last["end"], last.get("tangent", (1.0, 0.0, 0.0))


def _merge_stations(stations, total_length):
    merged = []
    for station in sorted(max(0.0, min(total_length, value)) for value in stations):
        if not merged or abs(station - merged[-1]) > PATH_TOLERANCE_MM:
            merged.append(station)
    return merged


def _end_first_span_order(count):
    """返回末端、起端、再逐步向中间的跨序号。"""
    order = []
    left = 0
    right = count - 1
    while left <= right:
        order.append(right)
        if left != right:
            order.append(left)
        left += 1
        right -= 1
    return order


def _build_modular_span_lengths(span):
    """按 50 mm 模数优先分配一个控制区间内的各跨长度。

    先保证跨数足以满足最大 2000 mm；基础跨距按 50 mm 向下圆整，
    完整的 50 mm 余量优先分配到首尾，最后不足 50 mm 的尾数只放入
    一个仍有容量的跨。返回值之和严格等于输入区间长度。
    """
    if span <= PATH_TOLERANCE_MM:
        return []
    count = max(1, int(ceil(span / POST_SPACING_MAX - 1.0e-9)))
    raw_step = span / count
    base_step = floor((raw_step + PATH_TOLERANCE_MM) / MODULE) * MODULE
    if base_step <= 0.0:
        # 极短区间无法按完整模数排布，只能作为一跨保留。
        return [span]

    lengths = [base_step] * count
    remainder = span - base_step * count
    module_count = int(floor((remainder + PATH_TOLERANCE_MM) / MODULE))
    remainder -= module_count * MODULE
    if remainder < 0.0 and abs(remainder) <= PATH_TOLERANCE_MM:
        remainder = 0.0

    order = _end_first_span_order(count)
    for index in order:
        if module_count <= 0:
            break
        candidate = lengths[index] + MODULE
        if candidate <= POST_SPACING_MAX + PATH_TOLERANCE_MM:
            lengths[index] = candidate
            module_count -= 1
    if module_count:
        raise RuntimeError("50 mm 模数余量无法在最大柱距内完成分配。")

    if remainder > PATH_TOLERANCE_MM:
        placed = False
        for index in order:
            if lengths[index] + remainder <= POST_SPACING_MAX + PATH_TOLERANCE_MM:
                lengths[index] += remainder
                placed = True
                break
        if not placed:
            raise RuntimeError("非模数尾数无法在最大柱距内完成分配。")

    # 浮点运算误差统一并入优先级最低的中间跨，保持总长严格闭合。
    correction = span - sum(lengths)
    if abs(correction) > 1.0e-8:
        target = order[-1]
        lengths[target] += correction
    if any(
        length <= PATH_TOLERANCE_MM
        or length > POST_SPACING_MAX + PATH_TOLERANCE_MM
        for length in lengths
    ):
        raise RuntimeError("模数化后的立柱跨距超出有效范围。")
    return lengths


def _build_post_stations(total_length, corners):
    controls = [0.0, total_length]
    for corner in corners:
        if corner.get("kind") == "grade_break":
            controls.append(corner["station"])
        else:
            extra = max(0.0, CORNER_POST_NOMINAL - corner["tangent_distance"])
            controls.extend((corner["start_station"] - extra, corner["end_station"] + extra))
    controls = _merge_stations(controls, total_length)
    stations = []
    for index in range(len(controls) - 1):
        start, end = controls[index], controls[index + 1]
        if not stations or abs(start - stations[-1]) > PATH_TOLERANCE_MM:
            stations.append(start)
        span_lengths = _build_modular_span_lengths(end - start)
        current_station = start
        for part, step in enumerate(span_lengths):
            # 最后一根柱直接使用控制区间终点，避免累计浮点误差。
            current_station = (
                end
                if part == len(span_lengths) - 1
                else current_station + step
            )
            stations.append(current_station)
    return _merge_stations(stations, total_length)


def _add_rails(builder, origin, uor_per_mm, pieces, color):
    for z, diameter, wall in (
        (TOP_RAIL_Z, TOP_RAIL_OD, TOP_RAIL_WALL),
        (KNEE_RAIL_Z, KNEE_RAIL_OD, KNEE_RAIL_WALL),
    ):
        for piece in pieces:
            if piece["type"] == "line":
                start = (piece["start"][0], piece["start"][1], piece["start"][2] + z)
                end = (piece["end"][0], piece["end"][1], piece["end"][2] + z)
                builder.add(_create_hollow_tube(
                    builder.dgn_model, origin, uor_per_mm, start, end,
                    diameter, wall, color
                ))
            else:
                center = (piece["center"][0], piece["center"][1], piece["center"][2] + z)
                builder.add(_create_hollow_arc(
                    builder.dgn_model, origin, uor_per_mm, center,
                    piece["radial"], piece["tangent"], piece["angle"],
                    diameter, wall, color
                ))


def _type2_connection_geometry(point, tangent, side_sign, structure_offset):
    """计算类型2底部连接节点的毫米坐标几何。"""
    try:
        structure_offset = float(structure_offset)
    except (TypeError, ValueError):
        raise ValueError("类型2的结构连接距离必须是数字。")
    minimum_offset = (
        TYPE2_BEND_RADIUS
        + TYPE2_PLATE_THICKNESS / 2.0
        + TYPE2_TUBE_PLATE_OVERLAP
    )
    if structure_offset <= minimum_offset + PATH_TOLERANCE_MM:
        raise ValueError(
            "类型2的立柱中心至连接板距离必须大于 %.1f mm。"
            % minimum_offset
        )

    tangent_length = hypot(hypot(tangent[0], tangent[1]), tangent[2])
    if tangent_length <= 1.0e-12:
        raise ValueError("立柱所在位置的路径切向长度为零。")
    plate_long = tuple(value / tangent_length for value in tangent)
    tx, ty, _ = _horizontal_unit(tangent)
    nx, ny, _ = _horizontal_normal(tangent, side_sign)
    # 连接板板面由路径三维切向和与之正交的短边组成；短边采用
    # 内侧水平法向 × 三维切向，保证三轴互相垂直。
    plate_short = (
        ny * plate_long[2],
        -nx * plate_long[2],
        nx * plate_long[1] - ny * plate_long[0],
    )
    radius = TYPE2_BEND_RADIUS
    elbow_center = (
        point[0] + nx * radius,
        point[1] + ny * radius,
        point[2],
    )
    elbow_end = (
        point[0] + nx * radius,
        point[1] + ny * radius,
        point[2] - radius,
    )
    plate_center = (
        point[0] + nx * structure_offset,
        point[1] + ny * structure_offset,
        point[2] - radius,
    )
    tube_end_distance = (
        structure_offset
        - TYPE2_PLATE_THICKNESS / 2.0
        + TYPE2_TUBE_PLATE_OVERLAP
    )
    tube_end = (
        point[0] + nx * tube_end_distance,
        point[1] + ny * tube_end_distance,
        point[2] - radius,
    )
    return {
        "normal": (nx, ny, 0.0),
        "tangent": (tx, ty, 0.0),
        "plate_long": plate_long,
        "plate_short": plate_short,
        "elbow_center": elbow_center,
        "elbow_end": elbow_end,
        "plate_center": plate_center,
        "tube_end": tube_end,
        "structure_offset": structure_offset,
    }


def _type1_connection_geometry(point, tangent, side_sign):
    """圆管至椭圆压扁端的放样截面；靠板侧外轮廓始终与板近面相切。"""
    if not (2.0 * STANCHION_WALL < TYPE1_FLAT_MINOR < STANCHION_OD <= TYPE1_FLAT_MAJOR):
        raise ValueError("压扁端须满足：两倍壁厚 < 短轴 < 管外径 <= 长轴。")
    if TYPE1_TRANSITION_LENGTH <= PATH_TOLERANCE_MM:
        raise ValueError("类型1压扁过渡长度必须大于零。")
    tangent_length = hypot(hypot(tangent[0], tangent[1]), tangent[2])
    if tangent_length <= 1.0e-12:
        raise ValueError("立柱所在位置的路径切向长度为零。")
    plate_long = tuple(value / tangent_length for value in tangent)
    nx, ny, _ = _horizontal_normal(tangent, side_sign)
    plate_short = (
        ny * plate_long[2],
        -nx * plate_long[2],
        nx * plate_long[1] - ny * plate_long[0],
    )
    offset = STANCHION_OD / 2.0 + TYPE2_PLATE_THICKNESS / 2.0
    center = (
        point[0] + nx * offset,
        point[1] + ny * offset,
        point[2] - TYPE1_PLATE_CENTER_DROP,
    )
    # 管底对齐连接板在立柱相切线处的下缘；坡段仍保持立柱竖直。
    vertical_half_height = min(
        half_size / abs(axis[2])
        for half_size, axis in (
            (TYPE2_PLATE_HORIZONTAL / 2.0, plate_long),
            (TYPE2_PLATE_VERTICAL / 2.0, plate_short),
        )
        if abs(axis[2]) > 1.0e-12
    )
    bottom_z = center[2] - vertical_half_height
    transition_z = point[2] - TYPE1_TRANSITION_LENGTH
    if transition_z <= bottom_z + PATH_TOLERANCE_MM:
        raise ValueError("类型1压扁过渡必须在连接板下缘上方结束。")
    # 压扁时向板侧偏移中心，防止短轴缩小后与板面出现间隙。
    shift = (STANCHION_OD - TYPE1_FLAT_MINOR) / 2.0
    flat_xy = (point[0] + nx * shift, point[1] + ny * shift)
    sections = [
        (tuple(point), STANCHION_OD / 2.0, STANCHION_OD / 2.0),
        ((flat_xy[0], flat_xy[1], transition_z), TYPE1_FLAT_MAJOR / 2.0, TYPE1_FLAT_MINOR / 2.0),
        ((flat_xy[0], flat_xy[1], bottom_z), TYPE1_FLAT_MAJOR / 2.0, TYPE1_FLAT_MINOR / 2.0),
    ]
    return {
        "normal": (nx, ny, 0.0),
        "plate_long": plate_long,
        "plate_short": plate_short,
        "plate_center": center,
        "post_bottom": sections[-1][0],
        "section_long": _horizontal_unit(tangent),
        "sections": sections,
    }


def _type1_inner_sections(sections):
    """内腔用半轴减壁厚的椭圆近似，两端延长以避免布尔运算共面。"""
    inner = [(center, major - STANCHION_WALL, minor - STANCHION_WALL)
             for center, major, minor in sections]
    first, major, minor = inner[0]
    last, last_major, last_minor = inner[-1]
    return ([( (first[0], first[1], first[2] + 2.0), major, minor)]
            + inner
            + [((last[0], last[1], last[2] - 2.0), last_major, last_minor)])


def _create_elliptic_loft(dgn_model, origin, uor_per_mm, sections, long_axis, normal):
    """由同向、同起点的解析椭圆截面生成封闭直纹放样实体。"""
    profiles = CurveVectorPtrArray()
    for center_mm, major, minor in sections:
        center = _point_uor(origin, center_mm, uor_per_mm)
        point0 = _point_uor(origin, tuple(
            center_mm[i] + major * long_axis[i] for i in range(3)
        ), uor_per_mm)
        point90 = _point_uor(origin, tuple(
            center_mm[i] + minor * normal[i] for i in range(3)
        ), uor_per_mm)
        profile = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
        profile.Add(ICurvePrimitive.CreateArc(
            DEllipse3d.FromPoints(center, point0, point90, 0.0, 2.0 * pi)
        ))
        profiles.append(profile)
    detail = DgnRuledSweepDetail(profiles, True)
    return _primitive_to_element(
        dgn_model, ISolidPrimitive.CreateDgnRuledSweep(detail), None
    )


def _create_type1_flattened_end(dgn_model, origin, uor_per_mm, geometry, color):
    sections = geometry["sections"]
    outer = _create_elliptic_loft(
        dgn_model, origin, uor_per_mm, sections,
        geometry["section_long"], geometry["normal"],
    )
    inner = _create_elliptic_loft(
        dgn_model, origin, uor_per_mm, _type1_inner_sections(sections),
        geometry["section_long"], geometry["normal"],
    )
    result = _boolean_hollow(dgn_model, outer, inner, color)
    if result is None:
        raise RuntimeError("类型1圆管至椭圆压扁端放样或内腔扣除失败。")
    return result


def _create_connection_plate(
    dgn_model, origin, uor_per_mm, geometry, color
):
    """创建长边跟随路径三维切向的 146×75×10 连接板。"""
    plate_long = geometry["plate_long"]
    plate_short = geometry["plate_short"]
    normal = geometry["normal"]
    center = geometry["plate_center"]
    half_long = TYPE2_PLATE_HORIZONTAL / 2.0
    half_short = TYPE2_PLATE_VERTICAL / 2.0
    half_thickness = TYPE2_PLATE_THICKNESS / 2.0
    # 轮廓放在靠立柱的一面，再沿水平内侧法向拉伸 10 mm。
    base = (
        center[0] - normal[0] * half_thickness,
        center[1] - normal[1] * half_thickness,
        center[2],
    )

    def plate_point(longitudinal, transverse):
        return _point_uor(
            origin,
            (
                base[0]
                + plate_long[0] * longitudinal
                + plate_short[0] * transverse,
                base[1]
                + plate_long[1] * longitudinal
                + plate_short[1] * transverse,
                base[2]
                + plate_long[2] * longitudinal
                + plate_short[2] * transverse,
            ),
            uor_per_mm,
        )

    corners = [
        plate_point(-half_long, -half_short),
        plate_point(half_long, -half_short),
        plate_point(half_long, half_short),
        plate_point(-half_long, half_short),
    ]
    # plate_long × plate_short 与内侧法向同向，因此正厚度始终朝内侧。
    return _create_prism_from_corners(
        dgn_model, corners, TYPE2_PLATE_THICKNESS * uor_per_mm, color
    )


def _add_type2_structure_connection(
    builder, origin, uor_per_mm, point, tangent, side_sign,
    structure_offset, color
):
    geometry = _type2_connection_geometry(
        point, tangent, side_sign, structure_offset
    )
    normal = geometry["normal"]
    builder.add(_create_hollow_arc(
        builder.dgn_model,
        origin,
        uor_per_mm,
        geometry["elbow_center"],
        (-normal[0], -normal[1], 0.0),
        (0.0, 0.0, -1.0),
        pi / 2.0,
        STANCHION_OD,
        STANCHION_WALL,
        color,
        TYPE2_BEND_RADIUS,
    ))
    builder.add(_create_hollow_tube(
        builder.dgn_model,
        origin,
        uor_per_mm,
        geometry["elbow_end"],
        geometry["tube_end"],
        STANCHION_OD,
        STANCHION_WALL,
        color,
    ))
    builder.add(_create_connection_plate(
        builder.dgn_model,
        origin,
        uor_per_mm,
        geometry,
        color,
    ))


def _type3_connection_geometry(point, tangent):
    """水平底板底面位于安装面，立柱居中；长边沿路径水平投影。"""
    long_axis = _horizontal_unit(tangent)
    short_axis = _horizontal_normal(tangent, 1.0)
    corners = [
        tuple(point[i] + along * long_axis[i] + across * short_axis[i]
              for i in range(3))
        for along, across in (
            (-TYPE3_PLATE_LENGTH / 2.0, -TYPE3_PLATE_WIDTH / 2.0),
            (TYPE3_PLATE_LENGTH / 2.0, -TYPE3_PLATE_WIDTH / 2.0),
            (TYPE3_PLATE_LENGTH / 2.0, TYPE3_PLATE_WIDTH / 2.0),
            (-TYPE3_PLATE_LENGTH / 2.0, TYPE3_PLATE_WIDTH / 2.0),
        )
    ]
    return {
        "corners": corners,
        "post_bottom": (point[0], point[1], point[2] + TYPE3_PLATE_THICKNESS),
    }


def _add_posts_balls_and_brackets(
    builder, origin, uor_per_mm, pieces, stations, side_sign,
    connection_type, structure_offset, color
):
    for station in stations:
        point, tangent = _point_tangent_at_station(pieces, station)
        type1_geometry = (
            _type1_connection_geometry(point, tangent, side_sign)
            if connection_type == "type1" else None
        )
        type3_geometry = (
            _type3_connection_geometry(point, tangent)
            if connection_type == "type3" else None
        )
        builder.add(_create_hollow_tube(
            builder.dgn_model, origin, uor_per_mm,
            type3_geometry["post_bottom"] if type3_geometry else point,
            (point[0], point[1], point[2] + TOP_RAIL_Z),
            STANCHION_OD, STANCHION_WALL, color
        ))
        for z in (KNEE_RAIL_Z, TOP_RAIL_Z):
            builder.add(_create_sphere(
                builder.dgn_model,
                _point_uor(origin, (point[0], point[1], point[2] + z), uor_per_mm),
                BALL_DIAMETER * uor_per_mm / 2.0,
                color,
            ))
        builder.add(_create_kickplate_bracket(
            builder.dgn_model, origin, uor_per_mm,
            point, tangent, side_sign, color
        ))
        if type1_geometry is not None:
            builder.add(_create_type1_flattened_end(
                builder.dgn_model, origin, uor_per_mm, type1_geometry, color
            ))
            builder.add(_create_connection_plate(
                builder.dgn_model, origin, uor_per_mm, type1_geometry, color
            ))
        elif type3_geometry is not None:
            builder.add(_create_prism_from_corners(
                builder.dgn_model,
                [_point_uor(origin, corner, uor_per_mm)
                 for corner in type3_geometry["corners"]],
                TYPE3_PLATE_THICKNESS * uor_per_mm,
                color,
            ))
        elif connection_type == "type2":
            _add_type2_structure_connection(
                builder,
                origin,
                uor_per_mm,
                point,
                tangent,
                side_sign,
                structure_offset,
                color,
            )


def _offset_kickplate_pieces(pieces, side_sign, center_offset):
    """构造与栏杆路径平行且严格连续的踢脚板中心路径。"""
    offset_pieces = []
    for piece in pieces:
        if piece["type"] == "line":
            tangent = piece["tangent"]
            normal = _horizontal_normal(tangent, side_sign)
            start = tuple(
                piece["start"][i] + normal[i] * center_offset for i in range(3)
            )
            end = tuple(
                piece["end"][i] + normal[i] * center_offset for i in range(3)
            )
            offset_pieces.append({
                "type": "line",
                "start": start,
                "end": end,
                "tangent": tangent,
            })
            continue

        # 左转时左侧是圆弧内侧，右转时右侧是圆弧内侧。
        radius = (
            CORNER_RADIUS
            - piece["turn_sign"] * side_sign * center_offset
        )
        if radius <= KICKPLATE_THICKNESS / 2.0 + PATH_TOLERANCE_MM:
            raise ValueError("转角内侧半径不足，130×6 踢脚板扫掠会自交。")
        radial = piece["radial"]
        tangent = piece["tangent"]
        angle = piece["angle"]
        c, s = cos(angle), sin(angle)
        end_radial = tuple(
            radial[i] * c + tangent[i] * s for i in range(3)
        )
        start = tuple(
            piece["center"][i] + radial[i] * radius for i in range(3)
        )
        end = tuple(
            piece["center"][i] + end_radial[i] * radius for i in range(3)
        )
        offset_pieces.append({
            "type": "arc",
            "start": start,
            "end": end,
            "center": piece["center"],
            "radial": radial,
            "tangent": tangent,
            "angle": angle,
            "radius": radius,
        })

    for index in range(len(offset_pieces) - 1):
        end = offset_pieces[index]["end"]
        start = offset_pieces[index + 1]["start"]
        gap = hypot(end[0] - start[0], end[1] - start[1])
        if gap > PATH_TOLERANCE_MM:
            raise RuntimeError("踢脚板偏移路径不连续（缝隙 %.6f mm）。" % gap)
    return offset_pieces


def _curve_vector_from_kickplate_pieces(
    origin, uor_per_mm, offset_pieces, path_z
):
    """按各路径点的局部标高加 path_z，生成 Bentley 开放路径。"""
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    for piece in offset_pieces:
        if piece["type"] == "line":
            start = _point_uor(
                origin,
                (piece["start"][0], piece["start"][1], piece["start"][2] + path_z),
                uor_per_mm,
            )
            end = _point_uor(
                origin,
                (piece["end"][0], piece["end"][1], piece["end"][2] + path_z),
                uor_per_mm,
            )
            path.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
            continue

        center = _point_uor(
            origin,
            (piece["center"][0], piece["center"][1], piece["center"][2] + path_z),
            uor_per_mm,
        )
        start = _point_uor(
            origin,
            (piece["start"][0], piece["start"][1], piece["start"][2] + path_z),
            uor_per_mm,
        )
        point90 = _point_uor(
            origin,
            (
                piece["center"][0]
                + piece["tangent"][0] * piece["radius"],
                piece["center"][1]
                + piece["tangent"][1] * piece["radius"],
                piece["center"][2] + path_z,
            ),
            uor_per_mm,
        )
        ellipse = DEllipse3d.FromPoints(
            center, start, point90, 0.0, piece["angle"]
        )
        path.Add(ICurvePrimitive.CreateArc(ellipse))
    return path


def _create_swept_kickplate(
    dgn_model, origin, uor_per_mm, pieces, side_sign, color
):
    """用单个 130×6 mm 闭合截面沿完整偏移路径连续扫掠。"""
    center_offset = (
        STANCHION_OD / 2.0
        + KICKPLATE_CLEARANCE
        + KICKPLATE_THICKNESS / 2.0
    )
    offset_pieces = _offset_kickplate_pieces(
        pieces, side_sign, center_offset
    )
    path_z = KICKPLATE_BOTTOM_Z + KICKPLATE_HEIGHT / 2.0
    path = _curve_vector_from_kickplate_pieces(
        origin, uor_per_mm, offset_pieces, path_z
    )

    first = offset_pieces[0]
    tangent = first["tangent"]
    normal = _horizontal_normal(tangent, 1.0)
    half_thickness = KICKPLATE_THICKNESS / 2.0
    start = first["start"]
    profile_mm = (
        (
            start[0] - normal[0] * half_thickness,
            start[1] - normal[1] * half_thickness,
            start[2] + KICKPLATE_BOTTOM_Z,
        ),
        (
            start[0] + normal[0] * half_thickness,
            start[1] + normal[1] * half_thickness,
            start[2] + KICKPLATE_BOTTOM_Z,
        ),
        (
            start[0] + normal[0] * half_thickness,
            start[1] + normal[1] * half_thickness,
            start[2] + KICKPLATE_BOTTOM_Z + KICKPLATE_HEIGHT,
        ),
        (
            start[0] - normal[0] * half_thickness,
            start[1] - normal[1] * half_thickness,
            start[2] + KICKPLATE_BOTTOM_Z + KICKPLATE_HEIGHT,
        ),
    )
    profile_points = DPoint3dArray()
    for point in profile_mm:
        profile_points.append(_point_uor(origin, point, uor_per_mm))
    profile_points.append(_point_uor(origin, profile_mm[0], uor_per_mm))

    model_ref = ISessionMgr.ActiveDgnModelRef
    profile_element = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile_element, None, profile_points, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        return None
    profile = ICurvePathQuery.ElementToCurveVector(profile_element)
    if profile is None:
        return None

    # 与官方 SolidModification.py 示例一致；锁定 Z 方向避免水平路径转角时
    # 130 mm 高的矩形截面发生扭转。
    sweep_result = SolidUtil.Create.BodyFromSweep(
        profile,
        path,
        model_ref,
        False,
        True,
        False,
        DVec3d.From(0.0, 0.0, 1.0),
        None,
        None,
        None,
    )
    if not _succeeded(sweep_result[0]):
        return None
    result = EditElementHandle()
    if not _succeeded(
        SolidUtil.Convert.BodyToElement(
            result, sweep_result[1], profile_element, dgn_model
        )
    ):
        return None
    return _apply_color(result, color)


def _add_kickplate(builder, origin, uor_per_mm, pieces, side_sign, color):
    builder.add(_create_swept_kickplate(
        builder.dgn_model, origin, uor_per_mm,
        pieces, side_sign, color
    ))


def _normalize_close_ends(close_ends):
    """把布尔或字符串统一为 none / start / end / both。"""
    if isinstance(close_ends, bool):
        return "both" if close_ends else "none"
    mode = str(close_ends).strip().lower()
    if mode not in ("none", "start", "end", "both"):
        raise ValueError("未知的端部闭合方式：%s" % close_ends)
    return mode


def _steel_inventory(
    pieces, station_count, total_length, connection_type,
    structure_offset, close_mode,
):
    """本道围栏所用钢材清单（纯几何，长度 mm）。

    管类按中心线长度计，球 / 板 / 支架按件计（DesignLengthMm 记其代表性
    长度或 0）。压扁端与类型2下弯段按水平路径的代表长度计，坡段为近似。
    """
    items = []
    for piece in pieces:
        items.append({"code": "TopRail", "name": "顶部扶手",
                      "spec": "钢管 φ42.4×3.2", "length": piece["length"],
                      "quantity": 1})
    for piece in pieces:
        items.append({"code": "KneeRail", "name": "中间横杆",
                      "spec": "钢管 φ33.7×3.2", "length": piece["length"],
                      "quantity": 1})
    stanchion_length = (
        TOP_RAIL_Z - TYPE3_PLATE_THICKNESS
        if connection_type == "type3" else TOP_RAIL_Z
    )
    items.append({"code": "Stanchion", "name": "立柱",
                  "spec": "钢管 φ48.3×3.2", "length": stanchion_length,
                  "quantity": station_count})
    # 连接球：每根立柱上、下横杆交点各一个。
    items.append({"code": "Ball", "name": "连接球",
                  "spec": "实心球 φ76", "length": 0.0,
                  "quantity": station_count * 2})
    items.append({"code": "Kickplate", "name": "踢脚板",
                  "spec": "钢板 130×6", "length": total_length, "quantity": 1})
    items.append({"code": "Bracket", "name": "踢脚板支架",
                  "spec": "钢板 %d×%d" % (KICKPLATE_BRACKET_WIDTH,
                                         KICKPLATE_BRACKET_HEIGHT),
                  "length": KICKPLATE_BRACKET_HEIGHT, "quantity": station_count})
    if connection_type in ("type1", "type2"):
        items.append({"code": "BasePlate", "name": "底部连接板",
                      "spec": "钢板 146×75×10", "length": 0.0,
                      "quantity": station_count})
    elif connection_type == "type3":
        items.append({"code": "BasePlate", "name": "底部连接板",
                      "spec": "钢板 145×75×10", "length": 0.0,
                      "quantity": station_count})
    if connection_type == "type1":
        # 压扁端长度：板中心下落 + 竖板半高（水平路径的代表值）。
        items.append({"code": "FlattenEnd", "name": "压扁端",
                      "spec": "钢管 φ48.3×3.2",
                      "length": TYPE1_PLATE_CENTER_DROP + TYPE2_PLATE_VERTICAL / 2.0,
                      "quantity": station_count})
    if connection_type == "type2":
        elbow_length = (pi / 2.0) * TYPE2_BEND_RADIUS
        horizontal = (
            structure_offset - TYPE2_PLATE_THICKNESS / 2.0
            + TYPE2_TUBE_PLATE_OVERLAP - TYPE2_BEND_RADIUS
        )
        items.append({"code": "DownBend", "name": "立柱下弯段",
                      "spec": "钢管 φ48.3×3.2",
                      "length": elbow_length + max(0.0, horizontal),
                      "quantity": station_count})
    closure_length = (
        2.0 * (END_CLOSURE_REACH - CORNER_RADIUS)
        + max(0.0, TOP_RAIL_Z - KNEE_RAIL_Z - 2.0 * CORNER_RADIUS)
        + 2.0 * (pi / 2.0) * CORNER_RADIUS
    )
    for end_mode in ("start", "end"):
        if close_mode in (end_mode, "both"):
            items.append({"code": "EndClosure", "name": "端部闭合回弯",
                          "spec": "钢管 φ42.4×3.2", "length": closure_length,
                          "quantity": 1})
    # 同一（代号 / 规格 / 长度）合并为一项，每个 ItemType 只附加一次。
    merged = {}
    order = []
    for item in items:
        key = (item["code"], item["spec"], item["length"])
        if key not in merged:
            merged[key] = dict(item)
            order.append(key)
        else:
            merged[key]["quantity"] += item["quantity"]
    return [merged[key] for key in order]


def _add_end_closure(builder, origin, uor_per_mm, endpoint, tangent, direction, color):
    """沿端点水平切向，以两个 R140 弯头把顶部扶手接回中间横杆。

    坡度路径的回弯仍位于全局竖直平面，并以端点的局部路径标高
    为基准；坡扶手和回弯入口之间允许形成与坡度一致的折角。
    """
    radius = CORNER_RADIUS
    straight = END_CLOSURE_REACH - radius
    if straight <= 0.0:
        raise ValueError("端部闭合长度必须大于闭合弯头半径。")
    vertical = TOP_RAIL_Z - KNEE_RAIL_Z - 2.0 * radius
    if vertical < -PATH_TOLERANCE_MM:
        raise ValueError("上下横杆中心距不足以容纳两个 R140 闭合弯头。")
    horizontal = _horizontal_unit(tangent)
    tx, ty = horizontal[0] * direction, horizontal[1] * direction
    base_z = endpoint[2]
    tangent_point = (
        endpoint[0] + tx * straight,
        endpoint[1] + ty * straight,
        base_z,
    )
    # 闭合回弯是顶部扶手管的连续回转，整段均采用 42.4 x 3.2。
    for z in (base_z + TOP_RAIL_Z, base_z + KNEE_RAIL_Z):
        builder.add(_create_hollow_tube(
            builder.dgn_model, origin, uor_per_mm,
            (endpoint[0], endpoint[1], z),
            (tangent_point[0], tangent_point[1], z),
            TOP_RAIL_OD, TOP_RAIL_WALL, color
        ))

    upper_center = (
        tangent_point[0], tangent_point[1], base_z + TOP_RAIL_Z - radius
    )
    builder.add(_create_hollow_arc(
        builder.dgn_model, origin, uor_per_mm, upper_center,
        (0.0, 0.0, 1.0), (tx, ty, 0.0), pi / 2.0,
        TOP_RAIL_OD, TOP_RAIL_WALL, color, radius
    ))

    outer_x = endpoint[0] + tx * END_CLOSURE_REACH
    outer_y = endpoint[1] + ty * END_CLOSURE_REACH
    upper_vertical_z = base_z + TOP_RAIL_Z - radius
    lower_vertical_z = base_z + KNEE_RAIL_Z + radius
    if vertical > PATH_TOLERANCE_MM:
        builder.add(_create_hollow_tube(
            builder.dgn_model, origin, uor_per_mm,
            (outer_x, outer_y, upper_vertical_z),
            (outer_x, outer_y, lower_vertical_z),
            TOP_RAIL_OD, TOP_RAIL_WALL, color
        ))

    lower_center = (
        tangent_point[0], tangent_point[1], base_z + KNEE_RAIL_Z + radius
    )
    builder.add(_create_hollow_arc(
        builder.dgn_model, origin, uor_per_mm, lower_center,
        (tx, ty, 0.0), (0.0, 0.0, -1.0), pi / 2.0,
        TOP_RAIL_OD, TOP_RAIL_WALL, color, radius
    ))


def _build_handrail_cell(
    vertices,
    side="left",
    reverse=False,
    close_ends=END_CLOSURE_DEFAULT,
    connection_type=CONNECTION_TYPE_DEFAULT,
    structure_offset=TYPE2_STRUCTURE_OFFSET_DEFAULT,
):
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型。")
    if side not in ("left", "right"):
        raise ValueError("踢脚板侧向必须为 left 或 right。")
    if connection_type not in ("type1", "type2", "type3", "type4"):
        raise ValueError("未知的立柱连接形式：%s" % connection_type)
    close_mode = _normalize_close_ends(close_ends)
    try:
        structure_offset = float(structure_offset)
    except (TypeError, ValueError):
        raise ValueError("立柱中心至连接板距离必须是数字。")
    path_vertices = [_copy_dpoint(point) for point in vertices]
    if reverse:
        path_vertices.reverse()
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    origin, points = _to_local_path(path_vertices, uor_per_mm)
    side_sign = 1.0 if side == 'left' else -1.0
    points = _offset_path_points(points, side_sign, PATH_LATERAL_OFFSET)
    pieces, corners, total_length = _build_fillet_path(points)
    stations = _build_post_stations(total_length, corners)
    color = _element_color()
    side_sign = 1.0 if side == "left" else -1.0

    builder = _HandrailCellBuilder(dgn_model)
    _add_rails(builder, origin, uor_per_mm, pieces, color)
    _add_posts_balls_and_brackets(
        builder,
        origin,
        uor_per_mm,
        pieces,
        stations,
        side_sign,
        connection_type,
        structure_offset,
        color,
    )
    _add_kickplate(builder, origin, uor_per_mm, pieces, side_sign, color)
    if close_mode in ("start", "both"):
        start_point, start_tangent = _point_tangent_at_station(pieces, 0.0)
        _add_end_closure(builder, origin, uor_per_mm, start_point, start_tangent, -1.0, color)
    if close_mode in ("end", "both"):
        end_point, end_tangent = _point_tangent_at_station(pieces, total_length)
        _add_end_closure(builder, origin, uor_per_mm, end_point, end_tangent, 1.0, color)
    builder.build()
    return builder, {
        "child_count": builder.child_count,
        "length_mm": total_length,
        "posts": len(stations),
        "balls": len(stations) * 2,
        "brackets": len(stations),
        "connection_type": connection_type,
        "structure_connections": len(stations) if connection_type in ("type1", "type2", "type3") else 0,
        "structure_offset": structure_offset,
        "corners": sum(corner.get("kind") == "fillet" for corner in corners),
        "grade_breaks": sum(corner.get("kind") == "grade_break" for corner in corners),
        "close_ends": close_mode,
        "close_start": close_mode in ("start", "both"),
        "close_end": close_mode in ("end", "both"),
        "color_rgb": COLOR_RGB,
        "steel_items": _steel_inventory(
            pieces, len(stations), total_length, connection_type,
            structure_offset, close_mode,
        ),
    }


def draw_steel_handrail_along_path(
    vertices,
    side="left",
    reverse=False,
    close_ends=END_CLOSURE_DEFAULT,
    connection_type=CONNECTION_TYPE_DEFAULT,
    structure_offset=TYPE2_STRUCTURE_OFFSET_DEFAULT,
):
    builder, result = _build_handrail_cell(
        vertices,
        side,
        reverse,
        close_ends,
        connection_type,
        structure_offset,
    )
    cell = builder.commit()
    _attach_steel_items(cell, result["steel_items"])
    return result


def replace_steel_handrail(
    vertices,
    side,
    reverse,
    close_ends,
    connection_type,
    structure_offset,
    previous_handle,
):
    builder, result = _build_handrail_cell(
        vertices,
        side,
        reverse,
        close_ends,
        connection_type,
        structure_offset,
    )
    new_handle = builder.commit()
    _attach_steel_items(new_handle, result["steel_items"])
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


# --- 钢材清单 ItemType 与 JSON 导出（沿用端焊三角架的构件项做法）-------------

def _new_ec_value(value):
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(value)
    return ec_value


def _component_item_type_name(component_code, design_length_mm):
    length_key = ("%.3f" % design_length_mm).replace(".", "_").replace("-", "N")
    return "%s_%s_L%s" % (ITEM_TYPE_PREFIX, component_code, length_key)


def _get_or_create_component_item_type(component_code, component_name,
                                       specification, design_length_mm, quantity):
    """获取或创建带本构件清单默认值的 ItemType。"""
    dgn_file = ISessionMgr.GetActiveDgnFile()
    item_type_name = _component_item_type_name(component_code, design_length_mm)
    default_values = {
        "ComponentName": component_name,
        "Specification": specification,
        "DesignLengthMm": float(design_length_mm),
        "Quantity": int(quantity),
        "Unit": "件",
    }
    try:
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        changed = False
        if library is None:
            library = ItemTypeLibrary(ITEM_LIBRARY_NAME, dgn_file, False)
            changed = True
        item_type = library.GetItemTypeByName(item_type_name)
        if item_type is None:
            item_type = library.AddItemType(item_type_name, False)
            changed = True
        if item_type is None:
            return None
        for property_name, property_type in ITEM_PROPERTY_DEFINITIONS:
            item_property = item_type.GetPropertyByName(property_name)
            if item_property is None:
                item_property = item_type.AddProperty(property_name, False)
                if item_property is None or not item_property.SetType(property_type):
                    return None
                if not item_property.SetDefaultValue(
                    _new_ec_value(default_values[property_name])
                ):
                    return None
                changed = True
        if changed and not library.Write():
            return None
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        return library.GetItemTypeByName(item_type_name)
    except Exception:
        return None


def _attach_component_item(element, component_code, component_name,
                           specification, design_length_mm, quantity=1):
    item_type = _get_or_create_component_item_type(
        component_code, component_name, specification, design_length_mm, quantity
    )
    if item_type is None:
        return False
    try:
        item_host = CustomItemHost(element, False)
        try:
            instance = item_host.ApplyCustomItem(item_type)
        except TypeError as error:
            if "Unable to convert function return value" in str(error):
                return True
            raise
        if instance is None:
            return False
        instance.WriteChanges()
        return True
    except Exception:
        return False


def _get_item_property_value(item, property_name, value_kind):
    ec_value = ECValue()
    status = item.GetValue(ec_value, property_name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or ec_value.IsNull():
        return None
    if value_kind == "double":
        return ec_value.GetDouble()
    if value_kind == "integer":
        return ec_value.GetInteger()
    return ec_value.GetString()


def _attach_steel_items(element, items):
    attached = 0
    for item in items:
        if _attach_component_item(element, item["code"], item["name"],
                                  item["spec"], item["length"], item["quantity"]):
            attached += 1
    return attached


def export_steel_handrail_bom_json(output_path=None):
    """扫描当前 DGN 中本插件的构件项，按规格汇总后写 JSON，返回文件路径。"""
    dgn_file = ISessionMgr.GetActiveDgnFile()
    library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
    if library is None:
        return None
    scope = FindInstancesScope.CreateScope(
        dgn_file, FindInstancesScopeOption(DgnECHostType.eElement, False)
    )
    query = ECQuery.CreateQuery(ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses)
    schema_name = str(library.GetInternalName())
    records = []
    summary_map = {}
    for item in DgnECManager.GetManager().FindInstances(scope, query)[0]:
        item_class = item.GetClass()
        if (
            str(item_class.GetSchema().GetName()) != schema_name
            or not str(item_class.GetName()).startswith(ITEM_TYPE_PREFIX + "_")
        ):
            continue
        element_instance = item.GetAsElementInstance()
        if element_instance is None:
            continue
        record = {
            "elementId": int(element_instance.ElementHandle.ElementId),
            "itemType": str(item_class.GetName()),
            "componentName": _get_item_property_value(item, "ComponentName", "string"),
            "specification": _get_item_property_value(item, "Specification", "string"),
            "designLengthMm": _get_item_property_value(item, "DesignLengthMm", "double"),
            "quantity": _get_item_property_value(item, "Quantity", "integer"),
            "unit": _get_item_property_value(item, "Unit", "string"),
        }
        if None in (
            record["componentName"], record["specification"],
            record["designLengthMm"], record["quantity"], record["unit"],
        ):
            continue
        records.append(record)
        key = (record["componentName"], record["specification"], record["unit"])
        if key not in summary_map:
            summary_map[key] = {
                "componentName": record["componentName"],
                "specification": record["specification"],
                "unit": record["unit"],
                "quantity": 0,
                "totalLengthMm": 0.0,
            }
        summary_map[key]["quantity"] += record["quantity"]
        summary_map[key]["totalLengthMm"] += (
            record["designLengthMm"] * record["quantity"]
        )
    if not records:
        return None
    summary = list(summary_map.values())
    for entry in summary:
        entry["totalLengthMm"] = round(entry["totalLengthMm"], 3)
    summary.sort(key=lambda entry: (entry["componentName"], entry["specification"]))
    records.sort(key=lambda entry: entry["elementId"])
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), BOM_JSON_NAME
        )
    with open(output_path, "w", encoding="utf-8") as output:
        json.dump(
            {
                "itemTypeLibrary": ITEM_LIBRARY_NAME,
                "recordCount": len(records),
                "records": records,
                "summary": summary,
            },
            output, ensure_ascii=False, indent=2,
        )
    return output_path


def _mix_color(source, target, ratio):
    """在两个 '#RRGGBB' 之间线性插值；ratio 0 取 source，1 取 target。"""
    source = source.lstrip("#")
    target = target.lstrip("#")
    blended = []
    for offset in (0, 2, 4):
        first = int(source[offset:offset + 2], 16)
        second = int(target[offset:offset + 2], 16)
        blended.append(max(0, min(255, int(round(first + (second - first) * ratio)))))
    return "#%02X%02X%02X" % tuple(blended)


class _RoundButton(tk.Canvas):
    """圆角画布按钮，带悬停渐变；可整体启用 / 禁用。"""

    def __init__(self, parent, text, command, primary=False, bg="#FFFFFF",
                 font=("Microsoft YaHei UI", 10), font_bold=None):
        self._command = command
        self._enabled = True
        self._ratio = 0.0
        self._target = 0.0
        self._job = None
        self._primary = primary
        self._text = text
        self._font = font_bold if (primary and font_bold) else font
        text_width = sum(14 if ord(char) > 127 else 7 for char in text)
        width = text_width + 44
        height = 36
        self._width = width
        self._height = height
        self._radius = 10
        self._idle = (
            "#2A3644" if primary else bg,
            "#2A3644" if primary else "#D8E0EA",
            "#FFFFFF" if primary else "#33415C",
        )
        self._hover = (
            "#3D4C5E" if primary else "#F0F5FA",
            "#3D4C5E" if primary else "#B9C6D6",
            "#FFFFFF" if primary else "#33415C",
        )
        tk.Canvas.__init__(self, parent, width=width, height=height, bg=bg,
                           highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Enter>", lambda event: self._set_target(1.0))
        self.bind("<Leave>", lambda event: self._set_target(0.0))
        self.bind("<Button-1>", self._on_click)
        self._paint()

    def _palette(self):
        if not self._enabled:
            return "#E7EBF1", "#E7EBF1", "#A9B3C2"
        return (
            _mix_color(self._idle[0], self._hover[0], self._ratio),
            _mix_color(self._idle[1], self._hover[1], self._ratio),
            _mix_color(self._idle[2], self._hover[2], self._ratio),
        )

    def _paint(self):
        self.delete("all")
        fill, edge, text_fill = self._palette()
        width, height, radius = self._width, self._height, self._radius
        x1, y1, x2, y2 = 1, 1, width - 1, height - 1
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        self.create_polygon(points, smooth=True, fill=fill, outline=edge)
        self.create_text(width / 2.0, height / 2.0, text=self._text,
                         fill=text_fill, font=self._font)

    def _step(self):
        if abs(self._target - self._ratio) < 0.04:
            self._ratio = self._target
            self._job = None
        else:
            self._ratio += (self._target - self._ratio) * 0.32
            self._job = self.after(16, self._step)
        self._paint()

    def _set_target(self, target):
        if not self._enabled:
            return
        self._target = target
        if self._job is None:
            self._step()

    def _on_click(self, event):
        if self._enabled and self._command is not None:
            self._command()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self._target = 0.0
        self.configure(cursor="hand2" if self._enabled else "arrow")
        self._paint()


class _MicroStationTk(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self._attached_to_mstn = False

    def microstation_mainloop(self):
        while tkinter._default_root is not None:
            self.update()
            if tkinter._default_root is None or not win32gui.IsWindow(self.winfo_id()):
                break
            if not self._attached_to_mstn:
                frame_handle = win32gui.GetParent(self.winfo_id())
                if frame_handle != 0:
                    PyCadInputQueue.AttachTkinterToolSetting(frame_handle)
                    self._attached_to_mstn = True
            PyCadInputQueue.PythonMainLoop()


class _HandrailSettingsDialog(_MicroStationTk):
    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("普通钢结构围栏")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)
        self.path_vertices = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._pending_regeneration = None
        self._busy = False
        self._closing = False

        bg = "#EEF2F7"
        card = "#FFFFFF"
        card_soft = "#F4F7FB"
        border = "#E3E9F1"
        ink = "#1F2A3D"
        muted = "#8C97A8"
        accent = "#E0A800"
        field = "#FBFCFE"
        ui_font = ("Microsoft YaHei UI", 10)
        ui_font_small = ("Microsoft YaHei UI", 9)
        ui_font_bold = ("Microsoft YaHei UI", 10, "bold")

        self.configure(bg=bg)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Card.TFrame", background=card)
        style.configure("Glass.TLabel", background=card, foreground=ink, font=ui_font)
        style.configure("GlassMuted.TLabel", background=card, foreground=muted,
                        font=ui_font)
        style.configure("TSeparator", background=border)
        style.configure("TCombobox", font=ui_font, padding=(10, 7),
                        fieldbackground=field, background="#FFFFFF",
                        foreground=ink, bordercolor=border, lightcolor=field,
                        darkcolor="#CBD5E1", arrowsize=15)
        style.map("TCombobox",
                  fieldbackground=[("readonly", field), ("active", "#FFFFFF")],
                  bordercolor=[("active", "#9FB4CC"), ("focus", "#9FB4CC")],
                  lightcolor=[("active", "#9FB4CC")],
                  arrowcolor=[("active", ink), ("!active", "#93A1B5")],
                  selectbackground=[("readonly", "#F0F5FA")],
                  selectforeground=[("readonly", ink)])

        shell = tk.Frame(self, bg=bg, padx=20, pady=18)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=bg)
        header.pack(fill="x", pady=(0, 12))
        title_row = tk.Frame(header, bg=bg)
        title_row.pack(anchor="w")
        dot = tk.Canvas(title_row, width=10, height=10, bg=bg,
                        highlightthickness=0, bd=0)
        dot.create_oval(1, 1, 9, 9, fill=accent, outline="")
        dot.pack(side="left", pady=(8, 0), padx=(0, 8))
        tk.Label(title_row, text="普通钢结构围栏", bg=bg, fg=ink,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="立柱 φ48.3×3.2 · 顶/中横杆 + 踢脚板 · 沿智能线生成",
                 bg=bg, fg=muted, font=ui_font_small).pack(
                     anchor="w", pady=(4, 0), padx=(18, 0))

        card_frame = tk.Frame(shell, bg=card, highlightbackground=border,
                              highlightthickness=1)
        card_frame.pack(fill="both", expand=True)
        form = ttk.Frame(card_frame, style="Card.TFrame", padding=20)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="布置参数", style="GlassMuted.TLabel",
                  font=ui_font_small).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(form, text="围栏内侧（踢脚板侧）", style="GlassMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=7)
        side_row = tk.Frame(form, bg=card)
        side_row.grid(row=1, column=1, columnspan=2, sticky="w",
                      padx=(12, 0), pady=7)
        self.side_var = tk.StringVar(value="left")
        left = tk.Radiobutton(side_row, text="路径左侧", variable=self.side_var,
                              value="left", command=self.on_options_changed,
                              bg=card, fg=ink, activebackground=card,
                              selectcolor=card, font=ui_font,
                              highlightthickness=0, bd=0)
        right = tk.Radiobutton(side_row, text="路径右侧", variable=self.side_var,
                               value="right", command=self.on_options_changed,
                               bg=card, fg=ink, activebackground=card,
                               selectcolor=card, font=ui_font,
                               highlightthickness=0, bd=0)
        left.pack(side="left")
        right.pack(side="left", padx=(14, 0))

        self.reverse_var = tk.BooleanVar(value=False)
        reverse = tk.Checkbutton(form, text="反转路径方向", variable=self.reverse_var,
                                 command=self.on_options_changed,
                                 bg=card, fg=ink, activebackground=card,
                                 selectcolor=card, font=ui_font,
                                 highlightthickness=0, bd=0)
        reverse.grid(row=2, column=1, columnspan=2, sticky="w",
                     padx=(12, 0), pady=7)

        ttk.Label(form, text="端部闭合回弯", style="GlassMuted.TLabel").grid(
            row=3, column=0, sticky="w", pady=7)
        self.close_mode_var = tk.StringVar(value=END_CLOSURE_LABELS[0])
        self.close_combo = ttk.Combobox(
            form, textvariable=self.close_mode_var,
            values=END_CLOSURE_LABELS, state="readonly", width=24)
        self.close_combo.grid(row=3, column=1, columnspan=2, sticky="w",
                              padx=(12, 0), pady=7)
        self.close_combo.bind("<<ComboboxSelected>>", self.on_options_changed)

        ttk.Label(form, text="立柱连接形式", style="GlassMuted.TLabel").grid(
            row=4, column=0, sticky="w", pady=7)
        self.connection_type_var = tk.StringVar(value="类型2（侧装钢结构）")
        self.connection_combo = ttk.Combobox(
            form, textvariable=self.connection_type_var,
            values=CONNECTION_TYPE_LABELS, state="readonly", width=24)
        self.connection_combo.grid(row=4, column=1, columnspan=2, sticky="w",
                                   padx=(12, 0), pady=7)
        self.connection_combo.bind(
            "<<ComboboxSelected>>", self.on_connection_type_changed)

        ttk.Label(form, text="立柱中心至连接板", style="GlassMuted.TLabel").grid(
            row=5, column=0, sticky="w", pady=7)
        offset_row = tk.Frame(form, bg=card)
        offset_row.grid(row=5, column=1, columnspan=2, sticky="w",
                        padx=(12, 0), pady=7)
        self.structure_offset_var = tk.StringVar(
            value=str(int(TYPE2_STRUCTURE_OFFSET_DEFAULT)))
        self.structure_offset_entry = tk.Entry(
            offset_row, textvariable=self.structure_offset_var, width=10,
            font=ui_font, fg=ink, bg=field, relief="flat",
            highlightthickness=1, highlightbackground=border,
            highlightcolor="#9FB4CC", insertbackground=ink, justify="center")
        self.structure_offset_entry.pack(side="left", ipady=4)
        self.structure_offset_entry.bind("<Return>", self.on_structure_offset_changed)
        tk.Label(offset_row, text="mm", bg=card, fg=muted,
                 font=ui_font_small).pack(side="left", padx=(8, 0))
        self.apply_offset_button = _RoundButton(
            offset_row, "更新", self.on_structure_offset_changed, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.apply_offset_button.pack(side="left", padx=(10, 0))

        ttk.Separator(form, orient="horizontal").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="预览", style="GlassMuted.TLabel").grid(
            row=7, column=0, sticky="nw", pady=3)
        self.info_label = ttk.Label(form, text="—", style="Glass.TLabel",
                                    justify="left", wraplength=340)
        self.info_label.grid(row=7, column=1, columnspan=2, sticky="w",
                             padx=(12, 0), pady=3)

        ttk.Label(form, text="操作", style="GlassMuted.TLabel").grid(
            row=8, column=0, sticky="nw", pady=3)
        ttk.Label(form, text="点选水平或带单一坡度智能线，可即时预览",
                  style="Glass.TLabel", justify="left", wraplength=340).grid(
                      row=8, column=1, columnspan=2, sticky="w",
                      padx=(12, 0), pady=3)

        status_chip = tk.Frame(form, bg=card_soft, highlightbackground=border,
                               highlightthickness=1)
        status_chip.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(status_chip, text="请在模型中点选路径。",
                                     bg=card_soft, fg="#1f5f99",
                                     font=ui_font_small, wraplength=340,
                                     justify="left")
        self.status_label.pack(anchor="w", padx=12, pady=8)

        button_bar = tk.Frame(form, bg=card)
        button_bar.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        self.export_button = _RoundButton(
            button_bar, "导出 JSON 清单", self.export_bom, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.confirm_button = _RoundButton(
            button_bar, "确定", self.confirm_tool, primary=True, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.cancel_button = _RoundButton(
            button_bar, "取消", self.cancel_tool, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.export_button.pack(side="left")
        self.confirm_button.pack(side="right")
        self.cancel_button.pack(side="right", padx=(0, 8))

        self.option_widgets = [left, right, reverse]
        self.action_buttons = [
            self.export_button, self.confirm_button, self.cancel_button
        ]

    def export_bom(self):
        if self._busy or self._closing:
            return
        try:
            output_path = export_steel_handrail_bom_json()
        except Exception as error:
            self.set_status("导出清单失败：%s" % error, True)
            return
        if output_path:
            message = "钢材清单已导出：%s" % output_path
            self.set_status(message)
            NotificationManager.OutputPrompt(message)
        else:
            self.set_status("当前模型中没有带钢材清单的围栏，未导出。", True)

    def set_status(self, message, is_error=False):
        self.status_label.configure(text=message, fg="#b42318" if is_error else "#1f5f99")
        self.update_idletasks()

    def _set_busy(self, busy):
        self._busy = bool(busy)
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in self.option_widgets:
            widget.configure(state=state)
        for button in self.action_buttons:
            button.set_enabled(not busy)
        self.connection_combo.configure(state="disabled" if busy else "readonly")
        self.close_combo.configure(state="disabled" if busy else "readonly")
        self._update_connection_controls()
        self.update_idletasks()

    def get_connection_type(self):
        return CONNECTION_LABEL_TO_VALUE.get(
            self.connection_type_var.get(), CONNECTION_TYPE_DEFAULT
        )

    def get_close_mode(self):
        return END_CLOSURE_LABEL_TO_VALUE.get(
            self.close_mode_var.get(), END_CLOSURE_DEFAULT
        )

    def get_structure_offset(self):
        try:
            return float(self.structure_offset_var.get())
        except (TypeError, ValueError):
            raise ValueError("立柱中心至连接板距离必须是数字。")

    def _update_connection_controls(self):
        enabled = (self.get_connection_type() == "type2") and not self._busy
        self.structure_offset_entry.configure(
            state=tk.NORMAL if enabled else tk.DISABLED)
        self.apply_offset_button.set_enabled(enabled)

    def on_connection_type_changed(self, event=None):
        self._update_connection_controls()
        self.on_options_changed()

    def on_structure_offset_changed(self, event=None):
        self.on_options_changed()

    def _cancel_pending(self):
        pending = self._pending_regeneration
        self._pending_regeneration = None
        if pending is not None:
            try:
                self.after_cancel(pending)
            except tk.TclError:
                pass

    def on_options_changed(self, event=None):
        if self._busy or self._closing:
            return
        if self.path_vertices:
            self._cancel_pending()
            self._pending_regeneration = self.after(REGENERATE_DELAY_MS, self._run_pending)

    def _run_pending(self):
        self._pending_regeneration = None
        if self._closing:
            return
        self.regenerate()

    def regenerate(self, vertices=None):
        self._cancel_pending()
        if vertices is not None:
            self.path_vertices = [_copy_dpoint(point) for point in vertices]
        if not self.path_vertices:
            return None
        self._set_busy(True)
        self.set_status("正在生成围栏预览，请稍候……")
        try:
            handle, result, deleted = replace_steel_handrail(
                self.path_vertices, self.side_var.get(), bool(self.reverse_var.get()),
                self.get_close_mode(), self.get_connection_type(),
                self.get_structure_offset(), self.preview_handle
            )
        except Exception as error:
            message = "围栏生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return None
        finally:
            self._set_busy(False)
        self.preview_handle = handle
        self.preview_result = result
        self.info_label.configure(text=(
            "路径 %.3f m；转角 %d；变坡点 %d；立柱 %d；连接球 %d；支架 %d；%s；RGB(%d,%d,%d)" % (
                result["length_mm"] / 1000.0, result["corners"], result["grade_breaks"], result["posts"],
                result["balls"], result["brackets"], self.connection_type_var.get(),
                result["color_rgb"][0], result["color_rgb"][1],
                result["color_rgb"][2]
            )
        ))
        message = "预览已更新，共 %d 个子元素。%s" % (
            result["child_count"], "已替换上一版预览。" if deleted else ""
        )
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def confirm_tool(self):
        if self._busy or self._closing:
            return
        self._closing = True
        self._cancel_pending()
        self.confirmed = True
        self.finish_tool()

    def cancel_tool(self):
        if self._busy or self._closing:
            return
        self._closing = True
        self._cancel_pending()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        # 主动销毁 Tk 窗口，使自定义消息循环立即退出；不再完全依赖
        # DgnElementSetTool._OnCleanup 的回调时机。
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass
        PyCommandState.StartDefaultCommand()


class SteelHandrailPathTool(DgnElementSetTool):
    def __init__(self, tool_id):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

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
        NotificationManager.OutputPrompt("请选择用于生成普通钢结构围栏的水平或带坡度 SmartLine。")

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
            scale = model.GetModelInfo().GetUorPerMeter() / 1000.0
            vertices = _extract_linear_vertices(handle, scale)
            _, points = _to_local_path(vertices, scale)
            _build_fillet_path(points)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True)
            return False

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
            scale = model.GetModelInfo().GetUorPerMeter() / 1000.0
            vertices = _extract_linear_vertices(eeh, scale)
            result = self.tool_settings.regenerate(vertices)
            return BentleyStatus.eSUCCESS if result is not None else BentleyStatus.eERROR
        except Exception as error:
            message = "围栏生成失败：%s" % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        SteelHandrailPathTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _GetToolName(self, name):
        return WString("SteelHandrailPathTool")

    def _OnCleanup(self):
        settings = self.tool_settings
        if settings is None:
            return
        self.tool_settings = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
            if settings.winfo_exists():
                settings.destroy()
        except tk.TclError:
            pass

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        settings = tool_settings if tool_settings is not None else _HandrailSettingsDialog()
        tool = SteelHandrailPathTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    SteelHandrailPathTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
