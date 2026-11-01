# -*- coding: utf-8 -*-
"""沿用户选择的水平或带坡度 SmartLine 创建可拆卸钢结构栏杆。

可拆卸做法（与普通钢结构围栏的区别）：
* 固定件：只有一段 DN50（φ60.3×4.5）套管，长 150，顶面比所选线段低 10
  （定位环厚度），让定位环坐在套管口、避免两者相碰。
* 可拆件：DN40（φ48.3×3.2）立杆自线段向上为栏杆高度，向下一段插入
  套管；顶部带定位环（locating collar），定位环为 10 mm 厚钢片、上边缘
  与线段平齐。松开单侧螺栓后可整根上拔。
* 横杆：顶部扶手 42.4×3.2（中心 1017）与中间横杆 33.7×3.2
  （中心 560），杆件交点用 φ76 连接球表示。
* 挡板：130×6，位于所选内侧，底边高于线段 10，内侧面与立杆外圆相切，
  总长比线段长 50（两端各外伸 25）。
* 面板分格：相邻立柱不超过 1800（MAX PANEL CRS），两端均设柱（退让 0）。

整道栏杆拆成两个普通单元：固定件写入 REMOVABLE_HANDRAIL_SOCKET，
可拆面板写入 REMOVABLE_HANDRAIL_PANEL，因此永久件与可拆卸件在模型里
可以分别选中、隐藏或导出。所有构件使用精确 RGB (255, 204, 0)。
脚本面向 Bentley Power Platform Python (MSPy)。
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


# --- 立杆 / 套管 / 定位环（mm）---------------------------------------------
STANCHION_OD = 48.3
STANCHION_WALL = 3.2
SLEEVE_OD = 60.3
SLEEVE_WALL = 4.5
SLEEVE_LENGTH = 150.0
STANCHION_INSERT = 150.0
COLLAR_OD = 76.0
COLLAR_THICKNESS = 10.0
STANCHION_BORE_CLEARANCE = (SLEEVE_OD - 2.0 * SLEEVE_WALL - STANCHION_OD) / 2.0

# --- 底部挡板（mm）----------------------------------------------------------
KICKPLATE_HEIGHT = 130.0
KICKPLATE_THICKNESS = 6.0
KICKPLATE_BOTTOM_Z = 10.0
KICKPLATE_END_EXTENSION = 25.0

# --- 横杆 / 分格（mm）-------------------------------------------------------
TOP_RAIL_Z = 1017.0
KNEE_RAIL_Z = 560.0
TOP_RAIL_OD = 42.4
TOP_RAIL_WALL = 3.2
KNEE_RAIL_OD = 33.7
KNEE_RAIL_WALL = 3.2
BALL_DIAMETER = 76.0
POST_SPACING_MAX = 1800.0
MODULE = 50.0
CORNER_POST_NOMINAL = 300.0
CORNER_RADIUS = 140.0

COLOR_RGB = (255, 204, 0)
SOCKET_CELL_NAME = "REMOVABLE_HANDRAIL_SOCKET"
PANEL_CELL_NAME = "REMOVABLE_HANDRAIL_PANEL"
PATH_TOLERANCE_MM = 0.01
REGENERATE_DELAY_MS = 150

# --- 钢材清单 ItemType（属性名保持英文，值可为中文）---------------------------
ITEM_LIBRARY_NAME = "RemovableHandrailComponents"
ITEM_TYPE_PREFIX = "RemovableHandrailComponent"
ITEM_PROPERTY_DEFINITIONS = (
    ("ComponentName", CustomProperty.Type1.eString),
    ("Specification", CustomProperty.Type1.eString),
    ("DesignLengthMm", CustomProperty.Type1.eDouble),
    ("Quantity", CustomProperty.Type1.eInteger),
    ("Unit", CustomProperty.Type1.eString),
)
BOM_JSON_NAME = "可拆卸栏杆_bom.json"


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


class _CellBuilder(object):
    """把一个部件集合封装成指定名称的普通单元。"""

    def __init__(self, dgn_model, cell_name):
        self.dgn_model = dgn_model
        self.cell_name = cell_name
        self.cell = EditElementHandle()
        self.child_count = 0
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, cell_name, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("栏杆子元素创建失败（%s）。" % self.cell_name)
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError("无法将子元素加入普通单元 %s。" % self.cell_name)
        self.child_count += 1

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError("无法完成普通单元 %s。" % self.cell_name)

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError("无法将 %s 写入活动模型。" % self.cell_name)
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


def _delete_previews(handles):
    deleted = False
    for handle in handles or ():
        deleted = _delete_preview(handle) or deleted
    return deleted


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


# --- 路径几何（纯函数，供自检复用）-----------------------------------------

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
            raise ValueError("所选路径含圆弧或曲线；请选择纯直线 SmartLine。")


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
        raise ValueError("暂不支持闭合栏杆路径。")
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
        raise ValueError("路径包含竖直段，无法确定栏杆走向。")
    return (tangent[0] / length, tangent[1] / length, 0.0)


def _horizontal_normal(tangent, side_sign):
    tx, ty, _ = _horizontal_unit(tangent)
    return (-ty * side_sign, tx * side_sign, 0.0)


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
            raise ValueError("路径包含竖直段，无法确定栏杆走向。")
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


def _build_modular_span_lengths(span, max_spacing=POST_SPACING_MAX):
    """按 50 mm 模数优先分配一个控制区间内的各跨长度。

    先保证跨数足以满足最大间距；基础跨距按 50 mm 向下圆整，完整的
    50 mm 余量优先分配到首尾，最后不足 50 mm 的尾数只放入一个仍有
    容量的跨。返回值之和严格等于输入区间长度。
    """
    if span <= PATH_TOLERANCE_MM:
        return []
    if max_spacing <= PATH_TOLERANCE_MM:
        raise ValueError("立柱最大间距必须大于零。")
    count = max(1, int(ceil(span / max_spacing - 1.0e-9)))
    raw_step = span / count
    base_step = floor((raw_step + PATH_TOLERANCE_MM) / MODULE) * MODULE
    if base_step <= 0.0:
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
        if candidate <= max_spacing + PATH_TOLERANCE_MM:
            lengths[index] = candidate
            module_count -= 1
    if module_count:
        raise RuntimeError("50 mm 模数余量无法在最大柱距内完成分配。")

    if remainder > PATH_TOLERANCE_MM:
        placed = False
        for index in order:
            if lengths[index] + remainder <= max_spacing + PATH_TOLERANCE_MM:
                lengths[index] += remainder
                placed = True
                break
        if not placed:
            raise RuntimeError("非模数尾数无法在最大柱距内完成分配。")

    correction = span - sum(lengths)
    if abs(correction) > 1.0e-8:
        target = order[-1]
        lengths[target] += correction
    if any(
        length <= PATH_TOLERANCE_MM
        or length > max_spacing + PATH_TOLERANCE_MM
        for length in lengths
    ):
        raise RuntimeError("模数化后的立柱跨距超出有效范围。")
    return lengths


def _build_post_stations(
    total_length, corners, max_spacing=POST_SPACING_MAX
):
    """沿完整路径按模数排布立柱站号，两端均设柱（端部退让为 0）。"""
    if max_spacing <= PATH_TOLERANCE_MM:
        raise ValueError("立柱最大间距必须大于零。")

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
        if end - start <= PATH_TOLERANCE_MM:
            continue
        if not stations or abs(start - stations[-1]) > PATH_TOLERANCE_MM:
            stations.append(start)
        span_lengths = _build_modular_span_lengths(end - start, max_spacing)
        current_station = start
        for part, step in enumerate(span_lengths):
            current_station = (
                end if part == len(span_lengths) - 1 else current_station + step
            )
            stations.append(current_station)
    return _merge_stations(stations, total_length)


def _socket_geometry(point, tangent):
    """计算可拆卸节点的毫米坐标几何。

    所选路径线段即安装基准面：定位环为 10 mm 厚钢片、上边缘与线段平齐；
    固定套管 150 长，其顶面比线段低一个定位环厚度（10），让定位环坐在套管
    口、避免两者相碰；可拆立杆自该线段向上为栏杆高度、向下插入套管。
    """
    if STANCHION_INSERT <= PATH_TOLERANCE_MM:
        raise ValueError("立杆插入深度必须大于零。")
    if STANCHION_INSERT > SLEEVE_LENGTH + PATH_TOLERANCE_MM:
        raise ValueError("立杆插入深度不能大于套管长度。")
    if STANCHION_OD >= SLEEVE_OD - 2.0 * SLEEVE_WALL - PATH_TOLERANCE_MM:
        raise ValueError("立杆外径必须小于套管内径，才能插入。")
    if STANCHION_BORE_CLEARANCE <= PATH_TOLERANCE_MM:
        raise ValueError("立杆与套管之间没有插拔间隙。")
    if COLLAR_OD <= STANCHION_OD:
        raise ValueError("定位环外径必须大于立杆外径。")
    if COLLAR_THICKNESS <= PATH_TOLERANCE_MM:
        raise ValueError("定位环厚度必须大于零。")

    line_z = point[2]
    sleeve_top_z = line_z - COLLAR_THICKNESS
    return {
        "line_z": line_z,
        "sleeve_start": (point[0], point[1], sleeve_top_z - SLEEVE_LENGTH),
        "sleeve_end": (point[0], point[1], sleeve_top_z),
        "stanchion_start": (point[0], point[1], line_z - STANCHION_INSERT),
        "stanchion_end": (point[0], point[1], line_z + TOP_RAIL_Z),
        "collar_start": (point[0], point[1], line_z - COLLAR_THICKNESS),
        "collar_end": (point[0], point[1], line_z),
    }


def _steel_inventory(pieces, post_count, total_length):
    """本道栏杆所用钢材清单（纯几何，长度 mm；host 指挂到哪个单元）。"""
    items = [
        {"host": "socket", "code": "Sleeve", "name": "固定套管",
         "spec": "钢管 φ60.3×4.5", "length": SLEEVE_LENGTH,
         "quantity": post_count},
        {"host": "panel", "code": "Stanchion", "name": "可拆立杆",
         "spec": "钢管 φ48.3×3.2", "length": STANCHION_INSERT + TOP_RAIL_Z,
         "quantity": post_count},
        {"host": "panel", "code": "Collar", "name": "定位环",
         "spec": "钢板 φ76×10", "length": 0.0, "quantity": post_count},
    ]
    for code, name, diameter, wall in (
        ("TopRail", "顶部扶手", TOP_RAIL_OD, TOP_RAIL_WALL),
        ("KneeRail", "中间横杆", KNEE_RAIL_OD, KNEE_RAIL_WALL),
    ):
        spec = "钢管 φ%.1f×%.1f" % (diameter, wall)
        for piece in pieces:
            items.append({"host": "panel", "code": code, "name": name,
                          "spec": spec, "length": piece["length"], "quantity": 1})
    items.append({"host": "panel", "code": "Kickplate", "name": "底部挡板",
                  "spec": "钢板 %d×%d" % (KICKPLATE_HEIGHT, KICKPLATE_THICKNESS),
                  "length": total_length + 2.0 * KICKPLATE_END_EXTENSION,
                  "quantity": 1})
    # 同一（单元 / 代号 / 规格 / 长度）合并为一项，每个 ItemType 只附加一次。
    merged = {}
    order = []
    for item in items:
        key = (item["host"], item["code"], item["spec"], item["length"])
        if key not in merged:
            merged[key] = dict(item)
            order.append(key)
        else:
            merged[key]["quantity"] += item["quantity"]
    return [merged[key] for key in order]


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


def _offset_kickplate_pieces(pieces, side_sign, center_offset):
    """构造与栏杆路径平行、且与立杆外圆相切的挡板中心路径。"""
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
        radius = CORNER_RADIUS - piece["turn_sign"] * side_sign * center_offset
        if radius <= KICKPLATE_THICKNESS / 2.0 + PATH_TOLERANCE_MM:
            raise ValueError("转角内侧半径不足，挡板扫掠会自交。")
        radial = piece["radial"]
        tangent = piece["tangent"]
        angle = piece["angle"]
        c, s = cos(angle), sin(angle)
        end_radial = tuple(radial[i] * c + tangent[i] * s for i in range(3))
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
            raise RuntimeError("挡板偏移路径不连续（缝隙 %.6f mm）。" % gap)
    return offset_pieces


def _extend_offset_path(offset_pieces, extension):
    """把首末直线段各外伸一个 extension，使总长比定位线长 2×extension。"""
    if extension <= PATH_TOLERANCE_MM or not offset_pieces:
        return offset_pieces
    pieces = [dict(piece) for piece in offset_pieces]
    first = pieces[0]
    if first["type"] == "line":
        tangent = first["tangent"]
        first["start"] = tuple(
            first["start"][i] - tangent[i] * extension for i in range(3)
        )
    last = pieces[-1]
    if last["type"] == "line":
        tangent = last["tangent"]
        last["end"] = tuple(
            last["end"][i] + tangent[i] * extension for i in range(3)
        )
    return pieces


def _curve_vector_from_kickplate_pieces(origin, uor_per_mm, offset_pieces, path_z):
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
                piece["center"][0] + piece["tangent"][0] * piece["radius"],
                piece["center"][1] + piece["tangent"][1] * piece["radius"],
                piece["center"][2] + path_z,
            ),
            uor_per_mm,
        )
        ellipse = DEllipse3d.FromPoints(center, start, point90, 0.0, piece["angle"])
        path.Add(ICurvePrimitive.CreateArc(ellipse))
    return path


def _create_swept_kickplate(dgn_model, origin, uor_per_mm, pieces, side_sign, color):
    """用单个 130×6 mm 闭合截面沿偏移路径连续扫掠挡板。"""
    # 中心线偏移到立杆外圆相切：内侧面正好落在立杆外缘。
    center_offset = STANCHION_OD / 2.0 + KICKPLATE_THICKNESS / 2.0
    offset_pieces = _offset_kickplate_pieces(pieces, side_sign, center_offset)
    offset_pieces = _extend_offset_path(offset_pieces, KICKPLATE_END_EXTENSION)
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

    # 锁定 Z 方向，避免水平路径转角时 130 mm 高的截面发生扭转。
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
        builder.dgn_model, origin, uor_per_mm, pieces, side_sign, color
    ))


def _add_socket(builder, origin, uor_per_mm, geometry, color):
    """固定件：只有一段 150 长的套管。"""
    builder.add(_create_hollow_tube(
        builder.dgn_model, origin, uor_per_mm,
        geometry["sleeve_start"], geometry["sleeve_end"],
        SLEEVE_OD, SLEEVE_WALL, color,
    ))


def _add_removable_post(builder, origin, uor_per_mm, geometry, color):
    """可拆件：立杆 + 定位环 + 两个连接球。"""
    builder.add(_create_hollow_tube(
        builder.dgn_model, origin, uor_per_mm,
        geometry["stanchion_start"], geometry["stanchion_end"],
        STANCHION_OD, STANCHION_WALL, color,
    ))
    collar_wall = (COLLAR_OD - STANCHION_OD) / 2.0
    builder.add(_create_hollow_tube(
        builder.dgn_model, origin, uor_per_mm,
        geometry["collar_start"], geometry["collar_end"],
        COLLAR_OD, collar_wall, color,
    ))
    base_x, base_y = geometry["stanchion_start"][0], geometry["stanchion_start"][1]
    for z in (KNEE_RAIL_Z, TOP_RAIL_Z):
        builder.add(_create_sphere(
            builder.dgn_model,
            _point_uor(origin, (base_x, base_y, geometry["line_z"] + z), uor_per_mm),
            BALL_DIAMETER * uor_per_mm / 2.0,
            color,
        ))


def _build_removable_handrail_cells(
    vertices,
    side="left",
    reverse=False,
    panel_spacing=POST_SPACING_MAX,
):
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型。")
    if side not in ("left", "right"):
        raise ValueError("挡板侧向必须为 left 或 right。")
    try:
        panel_spacing = float(panel_spacing)
    except (TypeError, ValueError):
        raise ValueError("立柱最大间距必须是数字。")

    path_vertices = [_copy_dpoint(point) for point in vertices]
    if reverse:
        path_vertices.reverse()
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    origin, points = _to_local_path(path_vertices, uor_per_mm)
    pieces, corners, total_length = _build_fillet_path(points)
    stations = _build_post_stations(total_length, corners, panel_spacing)
    if not stations:
        raise ValueError("路径上未能布置任何立柱。")
    color = _element_color()
    side_sign = 1.0 if side == "left" else -1.0

    socket_builder = _CellBuilder(dgn_model, SOCKET_CELL_NAME)
    panel_builder = _CellBuilder(dgn_model, PANEL_CELL_NAME)
    _add_rails(panel_builder, origin, uor_per_mm, pieces, color)
    _add_kickplate(panel_builder, origin, uor_per_mm, pieces, side_sign, color)
    for station in stations:
        point, tangent = _point_tangent_at_station(pieces, station)
        geometry = _socket_geometry(point, tangent)
        _add_socket(socket_builder, origin, uor_per_mm, geometry, color)
        _add_removable_post(panel_builder, origin, uor_per_mm, geometry, color)

    socket_builder.build()
    panel_builder.build()
    result = {
        "length_mm": total_length,
        "posts": len(stations),
        "sockets": len(stations),
        "side": side,
        "kickplate_length": total_length + 2.0 * KICKPLATE_END_EXTENSION,
        "panel_spacing": panel_spacing,
        "socket_children": socket_builder.child_count,
        "panel_children": panel_builder.child_count,
        "corners": sum(corner.get("kind") == "fillet" for corner in corners),
        "grade_breaks": sum(corner.get("kind") == "grade_break" for corner in corners),
        "color_rgb": COLOR_RGB,
        "steel_items": _steel_inventory(pieces, len(stations), total_length),
    }
    return socket_builder, panel_builder, result


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


def _get_or_create_component_item_type(
    component_code, component_name, specification, design_length_mm, quantity
):
    """获取或创建带本构件清单默认值的 ItemType。

    当前 MicroStation Python 版本无法把 ApplyCustomItem 的返回值转给
    Python，所以把清单值写成专用 ItemType 的默认值，附加时无需再编辑实例。
    """
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


def _attach_component_item(
    element, component_code, component_name, specification,
    design_length_mm, quantity=1,
):
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


def _attach_steel_items(element, items, host):
    attached = 0
    for item in items:
        if item["host"] != host:
            continue
        if _attach_component_item(
            element, item["code"], item["name"], item["spec"],
            item["length"], item["quantity"],
        ):
            attached += 1
    return attached


def export_removable_handrail_bom_json(output_path=None):
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


def draw_removable_handrail_along_path(
    vertices,
    side="left",
    reverse=False,
    panel_spacing=POST_SPACING_MAX,
):
    socket_builder, panel_builder, result = _build_removable_handrail_cells(
        vertices, side, reverse, panel_spacing
    )
    socket_cell = socket_builder.commit()
    panel_cell = panel_builder.commit()
    _attach_steel_items(socket_cell, result["steel_items"], "socket")
    _attach_steel_items(panel_cell, result["steel_items"], "panel")
    return result


def replace_removable_handrail(
    vertices,
    side,
    reverse,
    panel_spacing,
    previous_handles,
):
    socket_builder, panel_builder, result = _build_removable_handrail_cells(
        vertices, side, reverse, panel_spacing
    )
    socket_cell = socket_builder.commit()
    panel_cell = panel_builder.commit()
    _attach_steel_items(socket_cell, result["steel_items"], "socket")
    _attach_steel_items(panel_cell, result["steel_items"], "panel")
    new_handles = (socket_cell, panel_cell)
    deleted = _delete_previews(previous_handles)
    return new_handles, result, deleted


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


class _RemovableHandrailSettingsDialog(_MicroStationTk):
    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("可拆卸钢结构栏杆")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)
        self.path_vertices = None
        self.preview_handles = None
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
        tk.Label(title_row, text="可拆卸钢结构栏杆", bg=bg, fg=ink,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="固定 DN50 套管 · 可插拔 DN40 立杆 · 沿智能线生成",
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

        ttk.Label(form, text="挡板侧（内侧）", style="GlassMuted.TLabel").grid(
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

        ttk.Label(form, text="立柱最大间距", style="GlassMuted.TLabel").grid(
            row=3, column=0, sticky="w", pady=7)
        spacing_row = tk.Frame(form, bg=card)
        spacing_row.grid(row=3, column=1, columnspan=2, sticky="w",
                         padx=(12, 0), pady=7)
        self.panel_spacing_var = tk.StringVar(value=str(int(POST_SPACING_MAX)))
        self.panel_spacing_entry = tk.Entry(
            spacing_row, textvariable=self.panel_spacing_var, width=10,
            font=ui_font, fg=ink, bg=field, relief="flat",
            highlightthickness=1, highlightbackground=border,
            highlightcolor="#9FB4CC", insertbackground=ink, justify="center")
        self.panel_spacing_entry.pack(side="left", ipady=4)
        self.panel_spacing_entry.bind("<Return>", self.on_options_changed)
        tk.Label(spacing_row, text="mm", bg=card, fg=muted,
                 font=ui_font_small).pack(side="left", padx=(8, 0))

        ttk.Separator(form, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="预览", style="GlassMuted.TLabel").grid(
            row=5, column=0, sticky="nw", pady=3)
        self.info_label = ttk.Label(form, text="—", style="Glass.TLabel",
                                    justify="left", wraplength=350)
        self.info_label.grid(row=5, column=1, columnspan=2, sticky="w",
                             padx=(12, 0), pady=3)

        ttk.Label(form, text="操作", style="GlassMuted.TLabel").grid(
            row=6, column=0, sticky="nw", pady=3)
        ttk.Label(form, text="点选水平或带单一坡度智能线，可即时预览",
                  style="Glass.TLabel", justify="left", wraplength=350).grid(
                      row=6, column=1, columnspan=2, sticky="w",
                      padx=(12, 0), pady=3)

        status_chip = tk.Frame(form, bg=card_soft, highlightbackground=border,
                               highlightthickness=1)
        status_chip.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(status_chip, text="请在模型中点选路径。",
                                     bg=card_soft, fg="#1f5f99",
                                     font=ui_font_small, wraplength=350,
                                     justify="left")
        self.status_label.pack(anchor="w", padx=12, pady=8)

        button_bar = tk.Frame(form, bg=card)
        button_bar.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 0))
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

        self.option_widgets = [left, right, reverse, self.panel_spacing_entry]
        self.action_buttons = [
            self.export_button, self.confirm_button, self.cancel_button
        ]

    def export_bom(self):
        if self._busy or self._closing:
            return
        try:
            output_path = export_removable_handrail_bom_json()
        except Exception as error:
            self.set_status("导出清单失败：%s" % error, True)
            return
        if output_path:
            message = "钢材清单已导出：%s" % output_path
            self.set_status(message)
            NotificationManager.OutputPrompt(message)
        else:
            self.set_status("当前模型中没有带钢材清单的栏杆，未导出。", True)

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
        self.update_idletasks()

    def get_panel_spacing(self):
        try:
            return float(self.panel_spacing_var.get())
        except (TypeError, ValueError):
            raise ValueError("立柱最大间距必须是数字。")

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
        self.set_status("正在生成可拆卸栏杆预览，请稍候……")
        try:
            handles, result, deleted = replace_removable_handrail(
                self.path_vertices, self.side_var.get(), bool(self.reverse_var.get()),
                self.get_panel_spacing(), self.preview_handles
            )
        except Exception as error:
            message = "栏杆生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return None
        finally:
            self._set_busy(False)
        self.preview_handles = handles
        self.preview_result = result
        self.info_label.configure(text=(
            "路径 %.3f m；挡板 %.3f m；转角 %d；变坡点 %d；立柱 %d；最大间距 %.0f" % (
                result["length_mm"] / 1000.0, result["kickplate_length"] / 1000.0,
                result["corners"], result["grade_breaks"],
                result["posts"], result["panel_spacing"]
            )
        ))
        message = "预览已更新，固定件 %d 个、可拆面板 %d 个子元素。%s" % (
            result["socket_children"], result["panel_children"],
            "已替换上一版预览。" if deleted else ""
        )
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handles = self.preview_handles
        self.preview_handles = None
        self.preview_result = None
        return _delete_previews(handles)

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
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass
        PyCommandState.StartDefaultCommand()


class RemovableHandrailPathTool(DgnElementSetTool):
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
        NotificationManager.OutputPrompt("请选择用于生成可拆卸栏杆的水平或带坡度 SmartLine。")

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
            message = "栏杆生成失败：%s" % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        RemovableHandrailPathTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _GetToolName(self, name):
        return WString("RemovableHandrailPathTool")

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
        settings = tool_settings if tool_settings is not None else _RemovableHandrailSettingsDialog()
        tool = RemovableHandrailPathTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    RemovableHandrailPathTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
