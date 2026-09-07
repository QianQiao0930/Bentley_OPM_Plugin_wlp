# -*- coding: utf-8 -*-
"""在 MicroStation / OpenPlant Modeler 活动 3D DGN 中绘制安保围栏。

运行环境：Bentley Power Platform Python（MSPy）。
运行结果：在当前活动的 3D 模型中创建围栏实体钢管，并创建网片、拉线和刺丝。

坐标约定：X 为围栏延伸方向，+Y 为受保护侧，+Z 向上。所有构件参数均以 mm
定义。默认假定 DGN 的主单位为 m（OpenPlant 项目中常见）；如当前 DGN 使用
mm、ft 等其他主单位，只需修改 MASTER_UNITS_PER_METRE。
"""

from __future__ import print_function

from math import cos, hypot, radians, sin

# 保持与 Bentley 安装示例相同的导入方式。不同 OPM 更新版会把部分公共
# 枚举（例如 BentleyStatus）导出到不同的 MSPy 模块中，不能使用窄化导入。
from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyMstnPlatform import *


# --- DGN 单位与放置位置 ---------------------------------------------------
# 1 个 metre 等于多少个当前 DGN 的主单位：m=1，mm=1000，ft=3.280839895。
MASTER_UNITS_PER_METRE = 1000.0
ORIGIN_X_MASTER = 0.0
ORIGIN_Y_MASTER = 0.0
ORIGIN_Z_MASTER = 0.0


# --- 围栏尺寸（mm） -------------------------------------------------------
FENCE_HEIGHT = 1800.0
BAY_WIDTH = 4000.0
BAY_COUNT = 2
MESH_OPENING = 64.0
MESH_WIRE_DIAMETER = 2.5
TENSION_WIRE_DIAMETER = 4.0
TENSION_WIRE_Z = (250.0, 750.0, 1250.0, 1750.0)

OVERHANG_LENGTH = 450.0
OVERHANG_ANGLE_DEG = 45.0
# 弯头按围栏所有支臂采用相同的 100 mm 中心线半径，便于刺丝保持在同一条直线上。
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


# MicroStation 色表编号及线宽（0–31）。可按项目标准调整。
COLOR_POST = 7
COLOR_MESH = 9
COLOR_TENSION = 4
COLOR_BARBED = 2


def _point_mm(x_mm, y_mm, z_mm, uor_per_master):
    """把相对毫米坐标转换为当前 DGN 内部 UOR 坐标。"""
    uor_per_mm = uor_per_master * MASTER_UNITS_PER_METRE / 1000.0
    return DPoint3d.From(
        ORIGIN_X_MASTER * uor_per_master + x_mm * uor_per_mm,
        ORIGIN_Y_MASTER * uor_per_master + y_mm * uor_per_mm,
        ORIGIN_Z_MASTER * uor_per_master + z_mm * uor_per_mm,
    )


def _line_weight(diameter_mm):
    """将真实直径映射为便于观察的 MicroStation 线宽。"""
    return max(1, min(31, int(round(diameter_mm / 2.0))))


def _add_line(dgn_model, uor_per_master, start_mm, end_mm, color, diameter_mm):
    """创建并写入一条 3D 线元素，返回成功状态。"""
    eeh = EditElementHandle()
    segment = DSegment3d(
        _point_mm(start_mm[0], start_mm[1], start_mm[2], uor_per_master),
        _point_mm(end_mm[0], end_mm[1], end_mm[2], uor_per_master),
    )
    status = LineHandler.CreateLineElement(eeh, None, segment, True, dgn_model)
    if status != BentleyStatus.eSUCCESS:
        return False

    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.SetWeight(_line_weight(diameter_mm))
    properties.Apply(eeh)
    return eeh.AddToModel() == BentleyStatus.eSUCCESS


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


def _add_hollow_difference(dgn_model, outer, inner, color):
    """从 outer 实体减去 inner 实体，并将结果作为实体元素写入模型。"""
    if outer is None or inner is None:
        return False

    outer_status, outer_body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    inner_status, inner_body = SolidUtil.Convert.ElementToBody(inner, True, True, False)
    if outer_status != BentleyStatus.eSUCCESS or inner_status != BentleyStatus.eSUCCESS:
        return False

    cutting_tools = ISolidKernelEntityPtrArray()
    cutting_tools.append(inner_body)
    if SolidUtil.Modify.BooleanSubtract(outer_body, cutting_tools) != BentleyStatus.eSUCCESS:
        return False

    finished = EditElementHandle()
    if SolidUtil.Convert.BodyToElement(finished, outer_body, outer, dgn_model) != BentleyStatus.eSUCCESS:
        return False
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(finished)
    return finished.AddToModel() == BentleyStatus.eSUCCESS


def _add_hollow_tube(dgn_model, uor_per_master, start_mm, end_mm, outside_diameter_mm, wall_mm, color):
    """创建实体空心钢管：外圆柱减去同轴内圆柱，壁厚由 *wall_mm* 控制。"""
    if wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("钢管外径必须大于两倍壁厚。")

    dx = end_mm[0] - start_mm[0]
    dy = end_mm[1] - start_mm[1]
    dz = end_mm[2] - start_mm[2]
    length = hypot(hypot(dx, dy), dz)
    if length <= 1.0e-6:
        raise ValueError("钢管长度必须大于零。")

    start = _point_mm(start_mm[0], start_mm[1], start_mm[2], uor_per_master)
    end = _point_mm(end_mm[0], end_mm[1], end_mm[2], uor_per_master)
    uor_per_mm = uor_per_master * MASTER_UNITS_PER_METRE / 1000.0
    outer = _create_cylinder_element(dgn_model, start, end, outside_diameter_mm * uor_per_mm / 2.0)
    # 内圆柱在两端各伸出 2 mm，避免布尔运算出现共面端面，从而得到真正贯通的管腔。
    extension = 2.0 / length
    inner_start = _point_mm(
        start_mm[0] - dx * extension,
        start_mm[1] - dy * extension,
        start_mm[2] - dz * extension,
        uor_per_master,
    )
    inner_end = _point_mm(
        end_mm[0] + dx * extension,
        end_mm[1] + dy * extension,
        end_mm[2] + dz * extension,
        uor_per_master,
    )
    inner = _create_cylinder_element(
        dgn_model,
        inner_start,
        inner_end,
        (outside_diameter_mm / 2.0 - wall_mm) * uor_per_mm,
    )
    return _add_hollow_difference(dgn_model, outer, inner, color)


def _add_hollow_elbow(dgn_model, uor_per_master, x, start_z, outside_diameter_mm, wall_mm, color):
    """创建从竖直方向平滑过渡至 +Y/+Z 45° 方向的空心实体弯头。"""
    radius = ELBOW_CENTERLINE_RADIUS
    if radius <= 0.0 or wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("弯头半径、外径和壁厚参数无效。")

    sweep = radians(OVERHANG_ANGLE_DEG)
    uor_per_mm = uor_per_master * MASTER_UNITS_PER_METRE / 1000.0
    center = _point_mm(x, radius, start_z, uor_per_master)
    # P(0) 位于立柱轴线且切向为 +Z；45° 后切向转为 +Y/+Z。
    vector_x = DVec3d.From(0.0, -1.0, 0.0)
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
    # 内弧两端各超出 2 mm，避免内、外弯头端面共面导致布尔减法失败。
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
    return _add_hollow_difference(dgn_model, outer, inner, color)


def _clipped_diagonal_segments(width, height, slope):
    """返回裁剪到网片矩形内的 45° 菱形网线段端点（X、Z）。"""
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


def _add_post_and_arm(dgn_model, uor_per_master, x, is_terminal):
    """添加一根立柱及其 45° 防攀爬悬臂。"""
    if is_terminal:
        diameter = TERMINAL_POST_OD
        embedment = TERMINAL_POST_EMBEDMENT
    else:
        diameter = INTERMEDIATE_POST_OD
        embedment = INTERMEDIATE_POST_EMBEDMENT

    count = 0
    if _add_hollow_tube(
        dgn_model,
        uor_per_master,
        (x, 0.0, -embedment),
        (x, 0.0, FENCE_HEIGHT),
        diameter,
        STEEL_TUBE_WALL,
        COLOR_POST,
    ):
        count += 1

    angle = radians(OVERHANG_ANGLE_DEG)
    elbow_length = ELBOW_CENTERLINE_RADIUS * angle
    straight_length = OVERHANG_LENGTH - elbow_length
    if straight_length <= 0.0:
        raise ValueError("OVERHANG_LENGTH 必须大于弯头中心线弧长。")

    if _add_hollow_elbow(
        dgn_model,
        uor_per_master,
        x,
        FENCE_HEIGHT,
        diameter,
        STEEL_TUBE_WALL,
        COLOR_POST,
    ):
        count += 1

    elbow_end = (
        x,
        ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle)),
        FENCE_HEIGHT + ELBOW_CENTERLINE_RADIUS * sin(angle),
    )
    arm_end = (
        x,
        elbow_end[1] + straight_length * sin(angle),
        elbow_end[2] + straight_length * cos(angle),
    )
    if _add_hollow_tube(
        dgn_model,
        uor_per_master,
        elbow_end,
        arm_end,
        diameter,
        STEEL_TUBE_WALL,
        COLOR_POST,
    ):
        count += 1
    return count


def draw_security_fence():
    """在活动 3D DGN 模型中落图，并返回已创建元素的数量。"""
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型，再运行 security_fence_body.py。")

    # DPoint3d 的数值使用 UOR；将毫米输入转换为当前模型的 UOR。
    uor_per_master = ModelRef.GetUorPerMaster(dgn_model)
    total_length = BAY_COUNT * BAY_WIDTH
    created = 0

    # 端柱、4 m 间距中间柱和防攀爬悬臂。
    for index in range(BAY_COUNT + 1):
        created += _add_post_and_arm(dgn_model, uor_per_master, index * BAY_WIDTH, index in (0, BAY_COUNT))

    # 64 mm 镀锌菱形网：两组相交的 45° 线。
    for slope in (1, -1):
        for start, end in _clipped_diagonal_segments(total_length, FENCE_HEIGHT, slope):
            if _add_line(
                dgn_model,
                uor_per_master,
                (start[0], 0.0, start[1]),
                (end[0], 0.0, end[1]),
                COLOR_MESH,
                MESH_WIRE_DIAMETER,
            ):
                created += 1

    # 网片背侧的 4 根水平拉线。
    for z in TENSION_WIRE_Z:
        if _add_line(
            dgn_model,
            uor_per_master,
            (0.0, -TENSION_WIRE_DIAMETER / 2.0, z),
            (total_length, -TENSION_WIRE_DIAMETER / 2.0, z),
            COLOR_TENSION,
            TENSION_WIRE_DIAMETER,
        ):
            created += 1

    # 沿弯头之后的 45° 直管布置的 3 排刺丝，带可见的交叉刺钉。
    angle = radians(OVERHANG_ANGLE_DEG)
    elbow_length = ELBOW_CENTERLINE_RADIUS * angle
    straight_length = OVERHANG_LENGTH - elbow_length
    elbow_wire_y = ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle))
    elbow_wire_z = FENCE_HEIGHT + ELBOW_CENTERLINE_RADIUS * sin(angle)
    for row in range(1, BARBED_WIRE_COUNT + 1):
        fraction = float(row) / BARBED_WIRE_COUNT
        y = elbow_wire_y + straight_length * fraction * sin(angle)
        z = elbow_wire_z + straight_length * fraction * cos(angle)
        if _add_line(
            dgn_model,
            uor_per_master,
            (0.0, y, z),
            (total_length, y, z),
            COLOR_BARBED,
            BARBED_WIRE_DIAMETER,
        ):
            created += 1

        x = BARB_SPACING / 2.0
        while x < total_length:
            for direction in (-1.0, 1.0):
                start = (x, y - BARB_LENGTH / 2.0, z)
                end = (x, y + BARB_LENGTH / 2.0, z + direction * BARB_LENGTH / 3.0)
                if _add_line(dgn_model, uor_per_master, start, end, COLOR_BARBED, BARB_DIAMETER):
                    created += 1
            x += BARB_SPACING

    return created


def PyMain():
    """供 MicroStation 的 Python 宏运行器调用。"""
    return draw_security_fence()


if __name__ == "__main__":
    PyMain()
