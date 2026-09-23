# -*- coding: utf-8 -*-
"""所选 90° 弯头的纯几何解析逻辑（不依赖 Bentley 运行时）。"""

from __future__ import division

import math


ORIENTATION_TOLERANCE = 0.02


def _finite(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError("缺少或无法读取 %s。" % name)
    if math.isnan(result) or math.isinf(result):
        raise ValueError("%s 不是有效数值。" % name)
    return result


def _normalize(vector, name):
    values = tuple(_finite(value, name) for value in vector)
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1.0e-9:
        raise ValueError("%s 为零向量。" % name)
    return tuple(value / length for value in values)


def _add(point, vector, distance):
    return tuple(point[index] + vector[index] * distance for index in range(3))


def _negate(vector):
    return tuple(-value for value in vector)


def dimension_scale_to_mm(unit_of_measure, nominal_diameter_raw=None):
    """按 EC 单位标记返回毫米换算系数；缺标记时用公称直径量级兜底。"""
    unit = str(unit_of_measure or "").strip().upper()
    if unit in ("MM", "MILLIMETER", "MILLIMETRE", "毫米"):
        return 1.0
    if unit in ("M", "METER", "METRE", "米"):
        return 1000.0
    if unit in ("IN", "INCH", "INCHES"):
        return 25.4
    try:
        nominal = abs(float(nominal_diameter_raw))
    except (TypeError, ValueError):
        nominal = 0.0
    # OPM 公称直径若以米保存通常小于 2；常见 DN 的毫米值则大于 10。
    return 1000.0 if 0.0 < nominal < 2.0 else 1.0


def elbow_frame_from_matrix(matrix, uor_per_mm, run_length_mm,
                            outlet_length_mm,
                            tolerance=ORIENTATION_TOLERANCE):
    """由 OPM 3x4 变换矩阵解析两个端口、圆心与水平端方向。

    OPM 标准弯头局部坐标约定为：端口 0 位于矩阵原点，局部 X 是端口 0
    进入弯头的切线方向，局部 Z 是端口 1 的出弯方向。圆弧中心位于
    ``原点 + 局部 Z × Outlet 中心距``。
    """
    if matrix is None or len(matrix) < 12:
        raise ValueError("弯头缺少完整的 TRANSFORMATION_MATRIX。")
    uor_per_mm = _finite(uor_per_mm, "模型 UOR/mm")
    if uor_per_mm <= 0.0:
        raise ValueError("模型 UOR/mm 必须大于 0。")
    run_length_mm = _finite(run_length_mm, "中心至 Run 端距离")
    outlet_length_mm = _finite(outlet_length_mm, "中心至 Outlet 端距离")
    if run_length_mm <= 0.0 or outlet_length_mm <= 0.0:
        raise ValueError("弯头两端中心距必须大于 0。")
    if abs(run_length_mm - outlet_length_mm) > max(
            run_length_mm, outlet_length_mm) * 0.02:
        raise ValueError("弯头两端中心距不一致，第一版只支持标准 90° 圆弧弯头。")

    values = [_finite(value, "变换矩阵") for value in matrix[:12]]
    axis_x = _normalize((values[0], values[4], values[8]), "局部 X 轴")
    axis_z = _normalize((values[2], values[6], values[10]), "局部 Z 轴")
    if abs(sum(axis_x[i] * axis_z[i] for i in range(3))) > tolerance:
        raise ValueError("弯头变换矩阵的 X/Z 轴不正交。")

    origin = (values[3] / uor_per_mm,
              values[7] / uor_per_mm,
              values[11] / uor_per_mm)
    arc_center = _add(origin, axis_z, outlet_length_mm)
    port0 = origin
    port1 = _add(_add(origin, axis_x, run_length_mm),
                 axis_z, outlet_length_mm)

    x_is_horizontal = abs(axis_x[2]) <= tolerance
    x_is_vertical = abs(axis_x[2]) >= 1.0 - tolerance
    z_is_horizontal = abs(axis_z[2]) <= tolerance
    z_is_vertical = abs(axis_z[2]) >= 1.0 - tolerance

    if x_is_horizontal and z_is_vertical:
        horizontal_port = port0
        vertical_port = port1
        horizontal_direction = axis_x
        vertical_outward = axis_z
    elif x_is_vertical and z_is_horizontal:
        horizontal_port = port1
        vertical_port = port0
        horizontal_direction = _negate(axis_z)
        vertical_outward = _negate(axis_x)
    else:
        raise ValueError(
            "所选弯头不是竖直弯头：两个端口必须一端水平、另一端竖直。")

    if vertical_outward[2] < 1.0 - tolerance:
        raise ValueError("所选弯头的竖直端朝下；第一版仅支持竖直端朝上的弯头。")

    horizontal_direction = _normalize(
        (horizontal_direction[0], horizontal_direction[1], 0.0),
        "水平端方向")
    return {
        "origin_mm": origin,
        "axis_x": axis_x,
        "axis_z": axis_z,
        "horizontal_port_mm": horizontal_port,
        "vertical_port_mm": vertical_port,
        "arc_center_mm": arc_center,
        "horizontal_direction": horizontal_direction,
        "vertical_outward_direction": vertical_outward,
        "run_length_mm": run_length_mm,
        "outlet_length_mm": outlet_length_mm,
    }


def support_base_from_height(frame, height_h_mm, plate_thickness_mm):
    """由既有弯头和 H 反算底板下表面中心及耳轴底端。"""
    height_h_mm = _finite(height_h_mm, "高度 H")
    plate_thickness_mm = _finite(plate_thickness_mm, "底板厚度")
    if height_h_mm <= 0.0 or plate_thickness_mm < 0.0:
        raise ValueError("高度 H 必须大于 0，底板厚度不能为负。")
    horizontal = frame["horizontal_port_mm"]
    vertical = frame["vertical_port_mm"]
    plate_top_z = horizontal[2] - height_h_mm
    if vertical[2] <= plate_top_z:
        raise ValueError("高度 H 使耳轴上端不高于底端，无法建模。")
    return {
        "plate_top_z_mm": plate_top_z,
        "base_bottom_mm": (vertical[0], vertical[1],
                           plate_top_z - plate_thickness_mm),
        "trunnion_bottom_mm": (vertical[0], vertical[1], plate_top_z),
        "trunnion_top_mm": vertical,
    }
