# -*- coding: utf-8 -*-
"""在 MicroStation / OpenPlant Modeler 的活动 3D 模型中交互放置安保围栏。

运行脚本后会打开一个工具设置窗口。用户在模型中选择一条水平直线、折线或
仅由直线组成的复杂链，程序沿其路径生成围栏。围栏作为一个普通单元
（Normal Cell）写入模型，因此可以整体选中、移动、复制或删除。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import print_function

from math import cos, hypot, radians, sin, sqrt
import tkinter as tk

import tkinter
import win32gui

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# --- 围栏尺寸（mm）----------------------------------------------------------
FENCE_HEIGHT = 1800.0
DEFAULT_FENCE_LENGTH = 8000.0
MESH_OPENING = 64.0
MESH_WIRE_DIAMETER = 2.5
TENSION_WIRE_DIAMETER = 4.0
TENSION_WIRE_Z = (250.0, 750.0, 1250.0, 1750.0)

OVERHANG_LENGTH = 450.0
OVERHANG_ANGLE_DEG = 45.0
ELBOW_CENTERLINE_RADIUS = 100.0
BARBED_WIRE_DIAMETER = 2.5
BARBED_WIRE_COUNT = 3
BARB_DIAMETER = 1.2
BARB_LENGTH = 28.0
BARB_SPACING = 500.0

INTERMEDIATE_POST_OD = 50.0
INTERMEDIATE_POST_EMBEDMENT = 600.0
TERMINAL_POST_OD = 100.0
TERMINAL_POST_EMBEDMENT = 800.0
STEEL_TUBE_WALL = 4.0


# MicroStation 颜色表编号及线宽（0-31）。
COLOR_POST = 7
COLOR_MESH = 9
COLOR_TENSION = 4
COLOR_BARBED = 2

CELL_NAME = "SECURITY_FENCE"
POST_SPACING = 4000.0
HEAVY_POST_SPACING = 8000.0
PATH_TOLERANCE_MM = 0.01
HORIZONTAL_TOLERANCE_MM = 1.0


def _point_mm(origin, x_mm, y_mm, z_mm, uor_per_mm):
    """把相对毫米坐标转换为以用户点选位置为原点的 DGN UOR 坐标。"""
    return DPoint3d.From(
        origin.x + x_mm * uor_per_mm,
        origin.y + y_mm * uor_per_mm,
        origin.z + z_mm * uor_per_mm,
    )


def _line_weight(diameter_mm):
    """将真实直径映射为便于观察的 MicroStation 线宽。"""
    return max(1, min(31, int(round(diameter_mm / 2.0))))


class _FenceCellBuilder(object):
    """收集围栏子元素，并在全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        # Bentley 的此创建函数返回 None；后续 AddChildElement/AddChildComplete
        # 的状态值用于判断单元构造是否成功。
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, CELL_NAME, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("围栏子元素创建失败。")
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法将围栏子元素加入单元。")
        self.child_count += 1

    def write_to_model(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法完成围栏单元。")
        if self.cell.AddToModel() != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法将围栏单元写入活动模型。")
        return self.child_count


def _create_line_element(dgn_model, origin, uor_per_mm, start_mm, end_mm, color, diameter_mm):
    """创建一个尚未写入模型的 3D 线元素。"""
    eeh = EditElementHandle()
    segment = DSegment3d(
        _point_mm(origin, start_mm[0], start_mm[1], start_mm[2], uor_per_mm),
        _point_mm(origin, end_mm[0], end_mm[1], end_mm[2], uor_per_mm),
    )
    status = LineHandler.CreateLineElement(eeh, None, segment, dgn_model.Is3d(), dgn_model)
    if status != BentleyStatus.eSUCCESS:
        return None

    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.SetWeight(_line_weight(diameter_mm))
    properties.Apply(eeh)
    return eeh


def _create_cylinder_element(dgn_model, start_point, end_point, radius):
    """创建一个尚未写入模型的实心圆柱元素。"""
    detail = DgnConeDetail(start_point, end_point, radius, radius, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    eeh = EditElementHandle()
    status = DraftingElementSchema.ToElement(eeh, primitive, None, dgn_model)
    if status != BentleyStatus.eSUCCESS:
        return None
    return eeh


def _create_torus_pipe_element(dgn_model, center, vector_x, vector_y, major_radius, minor_radius, sweep_angle):
    """创建一个尚未写入模型的圆弧弯管实心元素。"""
    detail = DgnTorusPipeDetail(
        center, vector_x, vector_y, major_radius, minor_radius, sweep_angle, True
    )
    primitive = ISolidPrimitive.CreateDgnTorusPipe(detail)
    eeh = EditElementHandle()
    status = DraftingElementSchema.ToElement(eeh, primitive, None, dgn_model)
    if status != BentleyStatus.eSUCCESS:
        return None
    return eeh


def _create_hollow_difference(dgn_model, outer, inner, color):
    """以 outer 减去 inner，返回尚未写入模型的空心实体元素。"""
    if outer is None or inner is None:
        return None

    outer_status, outer_body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    inner_status, inner_body = SolidUtil.Convert.ElementToBody(inner, True, True, False)
    if outer_status != BentleyStatus.eSUCCESS or inner_status != BentleyStatus.eSUCCESS:
        return None

    cutting_tools = ISolidKernelEntityPtrArray()
    cutting_tools.append(inner_body)
    if SolidUtil.Modify.BooleanSubtract(outer_body, cutting_tools) != BentleyStatus.eSUCCESS:
        return None

    finished = EditElementHandle()
    if SolidUtil.Convert.BodyToElement(finished, outer_body, outer, dgn_model) != BentleyStatus.eSUCCESS:
        return None
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(finished)
    return finished


def _create_hollow_tube(
    dgn_model, origin, uor_per_mm, start_mm, end_mm, outside_diameter_mm, wall_mm, color
):
    """创建尚未写入模型的空心钢管。"""
    if wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("钢管外径必须大于两倍壁厚。")

    dx = end_mm[0] - start_mm[0]
    dy = end_mm[1] - start_mm[1]
    dz = end_mm[2] - start_mm[2]
    length = hypot(hypot(dx, dy), dz)
    if length <= 1.0e-6:
        raise ValueError("钢管长度必须大于零。")

    start = _point_mm(origin, start_mm[0], start_mm[1], start_mm[2], uor_per_mm)
    end = _point_mm(origin, end_mm[0], end_mm[1], end_mm[2], uor_per_mm)
    outer = _create_cylinder_element(
        dgn_model, start, end, outside_diameter_mm * uor_per_mm / 2.0
    )

    # 内圆柱在两端各伸出 2 mm，避免共面端面导致布尔减法失败。
    extension = 2.0 / length
    inner_start = _point_mm(
        origin,
        start_mm[0] - dx * extension,
        start_mm[1] - dy * extension,
        start_mm[2] - dz * extension,
        uor_per_mm,
    )
    inner_end = _point_mm(
        origin,
        end_mm[0] + dx * extension,
        end_mm[1] + dy * extension,
        end_mm[2] + dz * extension,
        uor_per_mm,
    )
    inner = _create_cylinder_element(
        dgn_model,
        inner_start,
        inner_end,
        (outside_diameter_mm / 2.0 - wall_mm) * uor_per_mm,
    )
    return _create_hollow_difference(dgn_model, outer, inner, color)


def _create_hollow_elbow(
    dgn_model,
    origin,
    uor_per_mm,
    base_mm,
    arm_normal,
    outside_diameter_mm,
    wall_mm,
    color,
):
    """创建由竖直方向向指定防攀侧平滑过渡的空心实体弯头。"""
    radius = ELBOW_CENTERLINE_RADIUS
    if radius <= 0.0 or wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("弯头半径、外径或壁厚参数无效。")

    sweep = radians(OVERHANG_ANGLE_DEG)
    nx, ny = arm_normal
    center_mm = (
        base_mm[0] + nx * radius,
        base_mm[1] + ny * radius,
        base_mm[2] + FENCE_HEIGHT,
    )
    center = _point_mm(
        origin, center_mm[0], center_mm[1], center_mm[2], uor_per_mm
    )
    vector_x = DVec3d.From(-nx, -ny, 0.0)
    vector_y = DVec3d.From(0.0, 0.0, 1.0)
    outer = _create_torus_pipe_element(
        dgn_model,
        center,
        vector_x,
        vector_y,
        radius * uor_per_mm,
        outside_diameter_mm * uor_per_mm / 2.0,
        sweep,
    )

    # 内弧两端各超出 2 mm，避免内外弯头端面共面。
    end_extension_angle = 2.0 / radius
    inner_vector_x = DVec3d.From(0.0, -cos(end_extension_angle), -sin(end_extension_angle))
    inner_vector_y = DVec3d.From(0.0, sin(end_extension_angle), cos(end_extension_angle))
    inner = _create_torus_pipe_element(
        dgn_model,
        center,
        inner_vector_x,
        inner_vector_y,
        radius * uor_per_mm,
        (outside_diameter_mm / 2.0 - wall_mm) * uor_per_mm,
        sweep + 2.0 * end_extension_angle,
    )
    return _create_hollow_difference(dgn_model, outer, inner, color)


def _clipped_diagonal_segments(width, height, slope):
    """返回裁剪到网片矩形内的 45 度菱形网线段端点（X、Z）。"""
    minimum = -width if slope == 1 else 0.0
    maximum = height if slope == 1 else width + height
    intercept = minimum
    while intercept <= maximum + 1.0e-6:
        points = []
        for x in (0.0, width):
            z = slope * x + intercept
            if -1.0e-6 <= z <= height + 1.0e-6:
                points.append((x, z))
        for z in (0.0, height):
            x = (z - intercept) / slope
            if -1.0e-6 <= x <= width + 1.0e-6:
                points.append((x, z))

        unique = []
        for point in points:
            if not any(hypot(point[0] - item[0], point[1] - item[1]) < 1.0e-5 for item in unique):
                unique.append(point)
        if len(unique) >= 2:
            unique.sort()
            yield unique[0], unique[-1]
        intercept += MESH_OPENING


def _distance3(point_a, point_b):
    return sqrt(
        (point_b.x - point_a.x) ** 2
        + (point_b.y - point_a.y) ** 2
        + (point_b.z - point_a.z) ** 2
    )


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _collect_linear_pieces(curve_vector, pieces):
    """递归提取 CurveVector 中的直线或折线顶点。"""
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
                raise ValueError("复杂链中包含无法读取的子路径。")
            _collect_linear_pieces(child, pieces)
        else:
            raise ValueError("所选路径包含圆弧或曲线，只支持纯直线折线。")


def _extract_linear_vertices(element_handle, uor_per_mm):
    """从 Line、Line String 或纯直线 Complex String 中提取有序顶点。"""
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError("请选择一条非闭合的直线或折线。")

    pieces = []
    _collect_linear_pieces(curve, pieces)
    if not pieces:
        raise ValueError("所选元素中没有可用的直线段。")

    tolerance_uor = PATH_TOLERANCE_MM * uor_per_mm
    vertices = []
    for piece in pieces:
        cleaned = [piece[0]]
        for point in piece[1:]:
            if _distance3(cleaned[-1], point) > tolerance_uor:
                cleaned.append(point)
        if len(cleaned) < 2:
            continue

        if not vertices:
            vertices.extend(cleaned)
        elif _distance3(vertices[-1], cleaned[0]) <= tolerance_uor:
            vertices.extend(cleaned[1:])
        elif _distance3(vertices[-1], cleaned[-1]) <= tolerance_uor:
            cleaned.reverse()
            vertices.extend(cleaned[1:])
        else:
            raise ValueError("复杂链中的直线段不连续。")

    if len(vertices) < 2:
        raise ValueError("路径至少需要两个不同的顶点。")
    if _distance3(vertices[0], vertices[-1]) <= tolerance_uor:
        raise ValueError("暂不支持闭合路径。")
    return vertices


def _to_local_path(vertices, uor_per_mm):
    """把 UOR 顶点转换为以首点为原点的毫米坐标。"""
    origin = _copy_dpoint(vertices[0])
    points = [
        (
            (point.x - origin.x) / uor_per_mm,
            (point.y - origin.y) / uor_per_mm,
            (point.z - origin.z) / uor_per_mm,
        )
        for point in vertices
    ]
    z_values = [point[2] for point in points]
    if max(z_values) - min(z_values) > HORIZONTAL_TOLERANCE_MM:
        raise ValueError("首版只支持水平 SmartLine；所选路径存在高程变化。")
    return origin, [(point[0], point[1], 0.0) for point in points]


def _cross2(point_a, point_b, point_c):
    return (point_b[0] - point_a[0]) * (point_c[1] - point_a[1]) - (
        point_b[1] - point_a[1]
    ) * (point_c[0] - point_a[0])


def _point_on_segment_2d(point, start, end):
    scale = max(1.0, hypot(end[0] - start[0], end[1] - start[1]))
    if abs(_cross2(start, end, point)) > PATH_TOLERANCE_MM * scale:
        return False
    return (
        min(start[0], end[0]) - PATH_TOLERANCE_MM
        <= point[0]
        <= max(start[0], end[0]) + PATH_TOLERANCE_MM
        and min(start[1], end[1]) - PATH_TOLERANCE_MM
        <= point[1]
        <= max(start[1], end[1]) + PATH_TOLERANCE_MM
    )


def _segments_intersect_2d(first, second):
    a, b = first["start"], first["end"]
    c, d = second["start"], second["end"]
    cross_ac = _cross2(a, b, c)
    cross_ad = _cross2(a, b, d)
    cross_ca = _cross2(c, d, a)
    cross_cb = _cross2(c, d, b)
    proper_crossing = (cross_ac > 0.0) != (cross_ad > 0.0) and (
        (cross_ca > 0.0) != (cross_cb > 0.0)
    )
    if proper_crossing:
        return True
    return any(
        (
            abs(cross_ac) <= PATH_TOLERANCE_MM * max(1.0, first["length"])
            and _point_on_segment_2d(c, a, b),
            abs(cross_ad) <= PATH_TOLERANCE_MM * max(1.0, first["length"])
            and _point_on_segment_2d(d, a, b),
            abs(cross_ca) <= PATH_TOLERANCE_MM * max(1.0, second["length"])
            and _point_on_segment_2d(a, c, d),
            abs(cross_cb) <= PATH_TOLERANCE_MM * max(1.0, second["length"])
            and _point_on_segment_2d(b, c, d),
        )
    )


def _validate_no_self_intersection(segments):
    for first_index in range(len(segments)):
        for second_index in range(first_index + 2, len(segments)):
            if _segments_intersect_2d(
                segments[first_index], segments[second_index]
            ):
                raise ValueError("路径存在自交或重复相交，请先整理 SmartLine。")


def _build_path_segments(points):
    """建立带累计里程的水平直线段列表。"""
    segments = []
    vertex_stations = [0.0]
    station = 0.0
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = hypot(dx, dy)
        if length <= PATH_TOLERANCE_MM:
            raise ValueError("路径包含长度为零或近似为零的线段。")
        segment = {
            "start": start,
            "end": end,
            "start_station": station,
            "end_station": station + length,
            "length": length,
            "tangent": (dx / length, dy / length),
        }
        segments.append(segment)
        station += length
        vertex_stations.append(station)
    _validate_no_self_intersection(segments)
    return segments, vertex_stations, station


def _corner_stations(segments, vertex_stations):
    """返回真正发生方向变化的折点里程，忽略共线的冗余顶点。"""
    corners = []
    for index in range(1, len(vertex_stations) - 1):
        incoming = segments[index - 1]["tangent"]
        outgoing = segments[index]["tangent"]
        if hypot(
            incoming[0] - outgoing[0], incoming[1] - outgoing[1]
        ) > 1.0e-8:
            corners.append(vertex_stations[index])
    return corners


def _merge_stations(stations):
    merged = []
    for station in sorted(stations):
        if not merged or abs(station - merged[-1]) > PATH_TOLERANCE_MM:
            merged.append(station)
    return merged


def _is_near_any(value, candidates):
    return any(abs(value - candidate) <= PATH_TOLERANCE_MM for candidate in candidates)


def _build_post_layout(total_length, corner_stations):
    """合并 4 m 分柱点、8 m 粗柱点、始末端和所有折点。"""
    candidates = list(corner_stations)
    station = POST_SPACING
    while station < total_length - PATH_TOLERANCE_MM:
        candidates.append(station)
        station += POST_SPACING
    candidates.extend((0.0, total_length))

    heavy_stations = [0.0, total_length]
    station = HEAVY_POST_SPACING
    while station < total_length - PATH_TOLERANCE_MM:
        heavy_stations.append(station)
        station += HEAVY_POST_SPACING

    layout = []
    for station in _merge_stations(candidates):
        is_heavy = _is_near_any(station, heavy_stations) or _is_near_any(
            station, corner_stations
        )
        layout.append({"station": station, "is_heavy": is_heavy})
    return layout


def _point_at_station(segments, station):
    for segment in segments:
        if station <= segment["end_station"] + PATH_TOLERANCE_MM:
            fraction = (station - segment["start_station"]) / segment["length"]
            fraction = max(0.0, min(1.0, fraction))
            start = segment["start"]
            end = segment["end"]
            return (
                start[0] + (end[0] - start[0]) * fraction,
                start[1] + (end[1] - start[1]) * fraction,
                0.0,
            )
    return segments[-1]["end"]


def _segment_at_station(segments, station):
    for segment in segments:
        if (
            segment["start_station"] - PATH_TOLERANCE_MM
            <= station
            <= segment["end_station"] + PATH_TOLERANCE_MM
        ):
            return segment
    return segments[-1]


def _normal_for_station(segments, station, side_sign):
    """计算普通柱法向或转角柱两侧法向的角平分方向。"""
    tangents = []
    for segment in segments:
        if (
            segment["start_station"] - PATH_TOLERANCE_MM
            <= station
            <= segment["end_station"] + PATH_TOLERANCE_MM
        ):
            tangent = segment["tangent"]
            if not tangents or hypot(
                tangent[0] - tangents[-1][0], tangent[1] - tangents[-1][1]
            ) > 1.0e-8:
                tangents.append(tangent)

    normals = [(-tangent[1] * side_sign, tangent[0] * side_sign) for tangent in tangents]
    nx = sum(normal[0] for normal in normals)
    ny = sum(normal[1] for normal in normals)
    magnitude = hypot(nx, ny)
    if magnitude <= 1.0e-8:
        raise ValueError("路径包含 180 度折返，无法确定转角柱防攀方向。")
    return nx / magnitude, ny / magnitude


def _frame_point(base, tangent, normal, x, y, z):
    return (
        base[0] + tangent[0] * x + normal[0] * y,
        base[1] + tangent[1] * x + normal[1] * y,
        base[2] + z,
    )


def _offset_point(base, normal, offset, z):
    return (
        base[0] + normal[0] * offset,
        base[1] + normal[1] * offset,
        base[2] + z,
    )


def _add_post_and_arm(builder, origin, uor_per_mm, base_mm, arm_normal, is_heavy):
    """向围栏单元加入一根粗/细立柱及其防攀悬臂。"""
    if is_heavy:
        diameter = TERMINAL_POST_OD
        embedment = TERMINAL_POST_EMBEDMENT
    else:
        diameter = INTERMEDIATE_POST_OD
        embedment = INTERMEDIATE_POST_EMBEDMENT

    builder.add(
        _create_hollow_tube(
            builder.dgn_model,
            origin,
            uor_per_mm,
            (base_mm[0], base_mm[1], base_mm[2] - embedment),
            (base_mm[0], base_mm[1], base_mm[2] + FENCE_HEIGHT),
            diameter,
            STEEL_TUBE_WALL,
            COLOR_POST,
        )
    )

    angle = radians(OVERHANG_ANGLE_DEG)
    elbow_length = ELBOW_CENTERLINE_RADIUS * angle
    straight_length = OVERHANG_LENGTH - elbow_length
    if straight_length <= 0.0:
        raise ValueError("OVERHANG_LENGTH 必须大于弯头中心线弧长。")

    builder.add(
        _create_hollow_elbow(
            builder.dgn_model,
            origin,
            uor_per_mm,
            base_mm,
            arm_normal,
            diameter,
            STEEL_TUBE_WALL,
            COLOR_POST,
        )
    )

    nx, ny = arm_normal
    elbow_end = (
        base_mm[0] + nx * ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle)),
        base_mm[1] + ny * ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle)),
        base_mm[2] + FENCE_HEIGHT + ELBOW_CENTERLINE_RADIUS * sin(angle),
    )
    arm_end = (
        elbow_end[0] + nx * straight_length * sin(angle),
        elbow_end[1] + ny * straight_length * sin(angle),
        elbow_end[2] + straight_length * cos(angle),
    )
    builder.add(
        _create_hollow_tube(
            builder.dgn_model,
            origin,
            uor_per_mm,
            elbow_end,
            arm_end,
            diameter,
            STEEL_TUBE_WALL,
            COLOR_POST,
        )
    )


def _add_fence_panel(
    builder,
    origin,
    uor_per_mm,
    start_point,
    end_point,
    tangent,
    start_normal,
    end_normal,
    panel_length,
):
    """在同一条直线段的相邻两根柱之间加入网片、拉线和刺丝。"""
    dgn_model = builder.dgn_model

    for slope in (1, -1):
        for mesh_start, mesh_end in _clipped_diagonal_segments(
            panel_length, FENCE_HEIGHT, slope
        ):
            builder.add(
                _create_line_element(
                    dgn_model,
                    origin,
                    uor_per_mm,
                    _frame_point(
                        start_point, tangent, start_normal, mesh_start[0], 0.0, mesh_start[1]
                    ),
                    _frame_point(
                        start_point, tangent, start_normal, mesh_end[0], 0.0, mesh_end[1]
                    ),
                    COLOR_MESH,
                    MESH_WIRE_DIAMETER,
                )
            )

    for z in TENSION_WIRE_Z:
        builder.add(
            _create_line_element(
                dgn_model,
                origin,
                uor_per_mm,
                _offset_point(start_point, start_normal, -TENSION_WIRE_DIAMETER / 2.0, z),
                _offset_point(end_point, end_normal, -TENSION_WIRE_DIAMETER / 2.0, z),
                COLOR_TENSION,
                TENSION_WIRE_DIAMETER,
            )
        )

    angle = radians(OVERHANG_ANGLE_DEG)
    elbow_length = ELBOW_CENTERLINE_RADIUS * angle
    straight_length = OVERHANG_LENGTH - elbow_length
    elbow_wire_offset = ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle))
    elbow_wire_z = FENCE_HEIGHT + ELBOW_CENTERLINE_RADIUS * sin(angle)
    for row in range(1, BARBED_WIRE_COUNT + 1):
        fraction = float(row) / BARBED_WIRE_COUNT
        offset = elbow_wire_offset + straight_length * fraction * sin(angle)
        z = elbow_wire_z + straight_length * fraction * cos(angle)
        wire_start = _offset_point(start_point, start_normal, offset, z)
        wire_end = _offset_point(end_point, end_normal, offset, z)
        builder.add(
            _create_line_element(
                dgn_model,
                origin,
                uor_per_mm,
                wire_start,
                wire_end,
                COLOR_BARBED,
                BARBED_WIRE_DIAMETER,
            )
        )

        x = BARB_SPACING / 2.0
        while x < panel_length:
            position_fraction = x / panel_length
            anchor = (
                wire_start[0] + (wire_end[0] - wire_start[0]) * position_fraction,
                wire_start[1] + (wire_end[1] - wire_start[1]) * position_fraction,
                wire_start[2] + (wire_end[2] - wire_start[2]) * position_fraction,
            )
            nx = start_normal[0] + (end_normal[0] - start_normal[0]) * position_fraction
            ny = start_normal[1] + (end_normal[1] - start_normal[1]) * position_fraction
            normal_length = hypot(nx, ny)
            if normal_length > 1.0e-8:
                nx /= normal_length
                ny /= normal_length
            else:
                nx, ny = start_normal

            for direction in (-1.0, 1.0):
                barb_start = (
                    anchor[0] - nx * BARB_LENGTH / 2.0,
                    anchor[1] - ny * BARB_LENGTH / 2.0,
                    anchor[2],
                )
                barb_end = (
                    anchor[0] + nx * BARB_LENGTH / 2.0,
                    anchor[1] + ny * BARB_LENGTH / 2.0,
                    anchor[2] + direction * BARB_LENGTH / 3.0,
                )
                builder.add(
                    _create_line_element(
                        dgn_model,
                        origin,
                        uor_per_mm,
                        barb_start,
                        barb_end,
                        COLOR_BARBED,
                        BARB_DIAMETER,
                    )
                )
            x += BARB_SPACING


def draw_security_fence_along_path(vertices, side="left", reverse=False):
    """沿选定的水平直线/折线路径创建一个整体围栏单元。"""
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型，再运行安保围栏工具。")
    if side not in ("left", "right"):
        raise ValueError("防攀侧必须为 left 或 right。")
    if len(vertices) < 2:
        raise ValueError("路径至少需要两个顶点。")

    path_vertices = [_copy_dpoint(point) for point in vertices]
    if reverse:
        path_vertices.reverse()

    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    origin, points = _to_local_path(path_vertices, uor_per_mm)
    segments, vertex_stations, total_length = _build_path_segments(points)
    corner_stations = _corner_stations(segments, vertex_stations)
    post_layout = _build_post_layout(total_length, corner_stations)
    side_sign = 1.0 if side == "left" else -1.0

    for item in post_layout:
        item["point"] = _point_at_station(segments, item["station"])
        item["normal"] = _normal_for_station(segments, item["station"], side_sign)

    builder = _FenceCellBuilder(dgn_model)
    for item in post_layout:
        _add_post_and_arm(
            builder,
            origin,
            uor_per_mm,
            item["point"],
            item["normal"],
            item["is_heavy"],
        )

    for index in range(len(post_layout) - 1):
        start_item = post_layout[index]
        end_item = post_layout[index + 1]
        panel_length = end_item["station"] - start_item["station"]
        midpoint_station = (start_item["station"] + end_item["station"]) / 2.0
        segment = _segment_at_station(segments, midpoint_station)
        _add_fence_panel(
            builder,
            origin,
            uor_per_mm,
            start_item["point"],
            end_item["point"],
            segment["tangent"],
            start_item["normal"],
            end_item["normal"],
            panel_length,
        )

    child_count = builder.write_to_model()
    heavy_count = sum(1 for item in post_layout if item["is_heavy"])
    return {
        "child_count": child_count,
        "length_mm": total_length,
        "heavy_posts": heavy_count,
        "light_posts": len(post_layout) - heavy_count,
        "corners": len(corner_stations),
    }


def draw_security_fence(total_length=DEFAULT_FENCE_LENGTH, placement_point=None):
    """兼容原调用方式：从指定起点沿模型 +X 方向生成直线围栏。"""
    total_length = float(total_length)
    if total_length <= 0.0:
        raise ValueError("围栏长度必须大于 0 mm。")

    dgn_model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    if placement_point is None:
        placement_point = DPoint3d.From(0.0, 0.0, 0.0)
    start = _copy_dpoint(placement_point)
    end = DPoint3d.From(
        start.x + total_length * uor_per_mm,
        start.y,
        start.z,
    )
    return draw_security_fence_along_path([start, end])["child_count"]


class _MicroStationTk(tk.Tk):
    """可挂接到 MicroStation 工具设置区的 Tk 根窗口。"""

    def __init__(self):
        tk.Tk.__init__(self)
        self._attached_to_mstn = False

    def microstation_mainloop(self):
        while tkinter._default_root is not None:
            self.update()
            if tkinter._default_root is None:
                break
            if not win32gui.IsWindow(self.winfo_id()):
                break

            if not self._attached_to_mstn:
                frame_handle = win32gui.GetParent(self.winfo_id())
                if frame_handle != 0:
                    PyCadInputQueue.AttachTkinterToolSetting(frame_handle)
                    self._attached_to_mstn = True

            PyCadInputQueue.PythonMainLoop()


class _FencePathSettingsDialog(_MicroStationTk):
    """SmartLine 路径选择、方向和生成结果界面。"""

    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("安保围栏—沿路径生成")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.finish_tool)

        body = tk.Frame(self, padx=12, pady=10)
        body.grid(row=0, column=0, sticky="nsew")

        tk.Label(
            body,
            text="选择一条水平直线、折线或纯直线复杂链。",
            justify="left",
            fg="#333333",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        tk.Label(body, text="防攀侧：").grid(row=1, column=0, pady=(10, 0), sticky="w")
        self.side_var = tk.StringVar(value="left")
        tk.Radiobutton(body, text="路径左侧", variable=self.side_var, value="left").grid(
            row=1, column=1, pady=(10, 0), sticky="w"
        )
        tk.Radiobutton(body, text="路径右侧", variable=self.side_var, value="right").grid(
            row=1, column=2, pady=(10, 0), sticky="w"
        )

        self.reverse_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body,
            text="反转路径方向（会改变起点及 8 m 粗柱里程）",
            variable=self.reverse_var,
        ).grid(row=2, column=0, columnspan=3, pady=(4, 0), sticky="w")

        self.path_info_label = tk.Label(
            body,
            text="路径：尚未生成",
            justify="left",
            fg="#333333",
        )
        self.path_info_label.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky="w")

        self.post_info_label = tk.Label(
            body,
            text="立柱：—",
            justify="left",
            fg="#333333",
        )
        self.post_info_label.grid(row=4, column=0, columnspan=3, sticky="w")

        self.status_label = tk.Label(
            body,
            text="请在模型中点选路径；选择后立即生成。",
            justify="left",
            fg="#1f5f99",
            wraplength=390,
        )
        self.status_label.grid(row=5, column=0, columnspan=3, pady=(10, 0), sticky="w")

        tk.Button(body, text="结束", width=10, command=self.finish_tool).grid(
            row=6, column=0, columnspan=3, pady=(10, 0), sticky="e"
        )

    def get_side(self):
        return self.side_var.get()

    def get_reverse(self):
        return bool(self.reverse_var.get())

    def set_status(self, message, is_error=False):
        self.status_label.configure(
            text=message,
            fg="#b42318" if is_error else "#1f5f99",
        )
        self.update_idletasks()

    def set_result(self, result):
        self.path_info_label.configure(
            text="路径：%.3f m，折点 %d 个" % (
                result["length_mm"] / 1000.0,
                result["corners"],
            )
        )
        self.post_info_label.configure(
            text="立柱：粗柱 %d 根，细柱 %d 根" % (
                result["heavy_posts"],
                result["light_posts"],
            )
        )

    def finish_tool(self):
        PyCommandState.StartDefaultCommand()


class SecurityFencePathTool(DgnElementSetTool):
    """选择 SmartLine 并沿其路径生成围栏的交互工具。"""

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
        NotificationManager.OutputPrompt(
            "请选择水平直线、折线或仅由直线组成的复杂链。"
        )

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False

        try:
            element_handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            dgn_model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
            uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
            vertices = _extract_linear_vertices(element_handle, uor_per_mm)
            _, points = _to_local_path(vertices, uor_per_mm)
            _build_path_segments(points)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True)
            return False

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR

        try:
            self.tool_settings.set_status("正在读取路径并生成围栏，请稍候……")
            dgn_model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
            uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
            vertices = _extract_linear_vertices(eeh, uor_per_mm)
            result = draw_security_fence_along_path(
                vertices,
                self.tool_settings.get_side(),
                self.tool_settings.get_reverse(),
            )
            self.tool_settings.set_result(result)
            message = (
                "已生成 %.3f m 围栏：粗柱 %d 根，细柱 %d 根，整体含 %d 个子元素。"
                % (
                    result["length_mm"] / 1000.0,
                    result["heavy_posts"],
                    result["light_posts"],
                    result["child_count"],
                )
            )
            self.tool_settings.set_status(message)
            NotificationManager.OutputPrompt(message + " 可继续选择下一条路径，右键结束。")
            return BentleyStatus.eSUCCESS
        except Exception as error:
            message = "围栏生成失败：%s" % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        # DgnElementSetTool 每完成一次选择会重启工具；转交现有窗口，避免嵌套 UI 循环。
        settings = self.tool_settings
        self.tool_settings = None
        SecurityFencePathTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _GetToolName(self, name):
        return WString("SecurityFencePathTool")

    def _OnCleanup(self):
        if self.tool_settings is not None:
            try:
                if self.tool_settings.winfo_exists():
                    self.tool_settings.destroy()
            except tk.TclError:
                pass

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        settings = (
            tool_settings if tool_settings is not None else _FencePathSettingsDialog()
        )
        tool = SecurityFencePathTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    SecurityFencePathTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
