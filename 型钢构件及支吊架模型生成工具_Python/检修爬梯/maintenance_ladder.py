# -*- coding: utf-8 -*-
"""移动式检修爬梯（登高平台梯）建模。

按参考照片创建一个整体式检修爬梯（Mobile Maintenance Ladder）：

* **斜梯**：与水平面成 **45°**，由两侧斜梁 + 花纹钢板踏步组成；
* **顶部平台**：**1 m × 1 m**，平台面标高默认 **2000**，四周设边缘框架；
* **平台护栏**：后侧与左右两侧设上下横杆 + 立柱 + 踢脚板（前侧为梯口，敞开）；
* **斜梯扶手**：沿斜面两侧设上下扶手管 + 竖立柱；
* **底部**：矩形底架 + 4 个万向脚轮（可开关）。

坐标约定（局部，单位 mm）
--------------------------
* ``n``：爬升方向（水平，指向平台一侧）；
* ``t``：梯宽方向；
* ``z``：竖直向上。

放置点为**底架中心在地面（脚轮落地平面）上的投影**：整个爬梯以其为中心，
向 ``n`` 方向爬升。出梯方向由界面参数**水平角**给出（``0° = +X``，``90° = +Y``）。

本脚本把纯几何（可在无 MicroStation 环境下自检）与 Bentley 实体创建分离。
面向 Bentley Power Platform Python (MSPy)。
"""

from __future__ import print_function

from math import ceil, cos, hypot, pi, radians, sin, tan
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


# --- 主尺寸与默认值（mm）----------------------------------------------------
PLATFORM_HEIGHT = 2000.0      # 平台面标高（自地面起）
PLATFORM_WIDTH = 1000.0       # 平台宽（梯宽方向）
PLATFORM_DEPTH = 1000.0       # 平台深（爬升方向）
STAIR_ANGLE_DEG = 45.0        # 斜梯与水平面夹角
STEP_TARGET_RISER = 220.0     # 目标级高，用于推踏步数量
TREAD_THICKNESS = 30.0        # 踏步板折边厚

LEG_SIZE = 40.0               # 立柱方管边长
BASE_BEAM_SIZE = 40.0         # 底架方管边长
STRINGER_WIDTH = 40.0         # 斜梁宽（梯宽方向）
STRINGER_DEPTH = 80.0         # 斜梁高（垂直斜面）
PLATFORM_FRAME_SIZE = 40.0    # 平台边缘框架方管
PLATFORM_PLATE_THICKNESS = 4.0  # 平台花纹板厚
TOE_HEIGHT = 100.0            # 踢脚板高
TOE_THICKNESS = 3.0           # 踢脚板厚

RAIL_DIAMETER = 33.5          # 圆管扶手外径
RAIL_HEIGHT = 1000.0          # 平台护栏顶杆高（自平台面）
RAIL_MID_HEIGHT = 500.0       # 平台护栏中杆高
STAIR_RAIL_HEIGHT = 1000.0    # 斜梯扶手顶杆高（垂直斜面）
STAIR_RAIL_MID_HEIGHT = 500.0  # 斜梯扶手中杆高
STAIR_POST_SPACING = 750.0    # 斜梯扶立柱沿斜面的最大间距

GUARD_ENABLED = True          # 是否生成平台护栏与斜梯扶手
CASTER_ENABLED = True         # 是否生成脚轮
CASTER_WHEEL_DIAMETER = 125.0  # 脚轮直径（＝底架抬升高度）
CASTER_WHEEL_WIDTH = 40.0     # 脚轮宽
CASTER_PLATE_SIZE = 100.0     # 脚轮安装板边长
CASTER_PLATE_THICKNESS = 6.0  # 脚轮安装板厚
BRACE_ENABLED = True          # 是否生成斜撑
BRACE_DIAMETER = 20.0         # 斜撑圆管外径

COLOR_RGB = (200, 205, 208)
BODY_CELL_NAME = "MAINTENANCE_LADDER"
GUARD_CELL_NAME = "MAINTENANCE_LADDER_GUARD"
REGENERATE_DELAY_MS = 150


# ============================================================================
# 纯几何（无 Bentley 依赖，可被 _maintenance_ladder_selftest.py 抽取运行）
# ============================================================================

def build_frame(outward):
    """由水平爬升方向返回正交单位基 (n, t, z)。

    * n：爬升方向（水平，指向平台一侧）；
    * t：梯宽方向，t = z × n；
    * z：竖直向上。满足 n × t = z。
    """
    ox, oy = outward
    length = hypot(ox, oy)
    if length <= 1.0e-12:
        raise ValueError("爬升方向不能为零向量。")
    nx, ny = ox / length, oy / length
    n = (nx, ny, 0.0)
    t = (-ny, nx, 0.0)
    z = (0.0, 0.0, 1.0)
    return n, t, z


def compute_step_count(rise_mm, target_riser_mm):
    """按目标级高估算踏步数量，最少 2 级。"""
    if rise_mm <= 0.0:
        raise ValueError("爬升高度必须大于零。")
    if target_riser_mm <= 0.0:
        raise ValueError("目标级高必须大于零。")
    count = int(round(rise_mm / target_riser_mm))
    return max(2, count)


def compute_stair_geometry(platform_height_mm, platform_width_mm,
                           platform_depth_mm, stair_angle_deg,
                           step_target_riser_mm, base_z_mm):
    """返回斜梯与平台的毫米级派生几何（局部 n/t/z）。

    ``base_z_mm`` 为底架落地点标高（带脚轮时＝脚轮直径），斜梯的 45° 指向
    “底架 → 平台”的实际爬升段；平台面仍位于 ``platform_height_mm``。
    """
    if platform_height_mm <= 0.0:
        raise ValueError("平台高度必须大于零。")
    if platform_width_mm <= 0.0 or platform_depth_mm <= 0.0:
        raise ValueError("平台宽度、深度必须大于零。")
    if base_z_mm < 0.0:
        raise ValueError("底架标高不能为负。")
    if not (5.0 < stair_angle_deg < 85.0):
        raise ValueError("爬梯角度应在 5°～85° 之间。")

    rise = platform_height_mm - base_z_mm
    if rise <= 0.0:
        raise ValueError("平台高度必须高于底架标高。")

    angle = radians(stair_angle_deg)
    run = rise / tan(angle)
    step_count = compute_step_count(rise, step_target_riser_mm)
    riser = rise / step_count
    going = run / step_count

    total_depth = run + platform_depth_mm
    half_depth = total_depth / 2.0
    toe_n = -half_depth
    platform_front_n = toe_n + run
    platform_back_n = half_depth
    platform_center_n = (platform_front_n + platform_back_n) / 2.0

    return {
        "base_z": base_z_mm,
        "rise": rise,
        "run": run,
        "angle_rad": angle,
        "step_count": step_count,
        "riser": riser,
        "going": going,
        "slope_length": hypot(run, rise),
        "total_depth": total_depth,
        "half_depth": half_depth,
        "toe_n": toe_n,
        "platform_front_n": platform_front_n,
        "platform_back_n": platform_back_n,
        "platform_center_n": platform_center_n,
    }


def _add_box(primitives, center, axes, size):
    primitives.append({"type": "box", "center": center, "axes": axes, "size": size})


def _add_cylinder(primitives, center, axis, length, diameter):
    primitives.append({
        "type": "cylinder", "center": center, "axis": axis,
        "length": length, "diameter": diameter,
    })


def _add_brace(primitives, start, end, diameter):
    """在两端点之间添加一根圆管斜撑（axis 归一化为单位向量）。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = hypot(hypot(dx, dy), dz)
    if length <= 0.0:
        return
    center = ((start[0] + end[0]) / 2.0,
              (start[1] + end[1]) / 2.0,
              (start[2] + end[2]) / 2.0)
    _add_cylinder(primitives, center, (dx / length, dy / length, dz / length),
                  length, diameter)


def _point_on_frame(frame, n, t, z):
    """把局部 (n, t, z) 分量映射为世界向量（含原点 0）。"""
    return (
        frame[0][0] * n + frame[1][0] * t + frame[2][0] * z,
        frame[0][1] * n + frame[1][1] * t + frame[2][1] * z,
        frame[0][2] * n + frame[1][2] * t + frame[2][2] * z,
    )


def build_maintenance_ladder_layout(
        platform_height_mm=PLATFORM_HEIGHT,
        platform_width_mm=PLATFORM_WIDTH,
        platform_depth_mm=PLATFORM_DEPTH,
        stair_angle_deg=STAIR_ANGLE_DEG,
        step_target_riser_mm=STEP_TARGET_RISER,
        tread_thickness_mm=TREAD_THICKNESS,
        leg_size_mm=LEG_SIZE,
        base_beam_size_mm=BASE_BEAM_SIZE,
        stringer_width_mm=STRINGER_WIDTH,
        stringer_depth_mm=STRINGER_DEPTH,
        platform_frame_size_mm=PLATFORM_FRAME_SIZE,
        platform_plate_thickness_mm=PLATFORM_PLATE_THICKNESS,
        toe_height_mm=TOE_HEIGHT,
        toe_thickness_mm=TOE_THICKNESS,
        rail_diameter_mm=RAIL_DIAMETER,
        rail_height_mm=RAIL_HEIGHT,
        rail_mid_height_mm=RAIL_MID_HEIGHT,
        stair_rail_height_mm=STAIR_RAIL_HEIGHT,
        stair_rail_mid_height_mm=STAIR_RAIL_MID_HEIGHT,
        stair_post_spacing_mm=STAIR_POST_SPACING,
        guard_enabled=GUARD_ENABLED,
        caster_enabled=CASTER_ENABLED,
        caster_wheel_diameter_mm=CASTER_WHEEL_DIAMETER,
        caster_wheel_width_mm=CASTER_WHEEL_WIDTH,
        caster_plate_size_mm=CASTER_PLATE_SIZE,
        caster_plate_thickness_mm=CASTER_PLATE_THICKNESS,
        brace_enabled=BRACE_ENABLED,
        brace_diameter_mm=BRACE_DIAMETER):
    """生成检修爬梯全部构件的毫米级布局（局部坐标：n=爬升、t=宽度、z=向上）。

    返回 dict，其中 ``primitives`` 为待创建的实体（``box`` / ``cylinder``）。
    ``body_primitive_count`` 划分「主体单元」与「护栏单元」。
    """
    for name, value in (
            ("平台高度", platform_height_mm),
            ("平台宽度", platform_width_mm),
            ("平台深度", platform_depth_mm),
            ("踏步厚", tread_thickness_mm),
            ("立柱", leg_size_mm),
            ("底架", base_beam_size_mm),
            ("斜梁宽", stringer_width_mm),
            ("斜梁高", stringer_depth_mm),
            ("平台框架", platform_frame_size_mm),
            ("平台板厚", platform_plate_thickness_mm),
            ("护栏高", rail_height_mm),
            ("扶手管径", rail_diameter_mm)):
        if value <= 0.0:
            raise ValueError("%s必须大于零。" % name)

    base_z = caster_wheel_diameter_mm if caster_enabled else 0.0
    geometry = compute_stair_geometry(
        platform_height_mm, platform_width_mm, platform_depth_mm,
        stair_angle_deg, step_target_riser_mm, base_z)

    angle = geometry["angle_rad"]
    run = geometry["run"]
    rise = geometry["rise"]
    step_count = geometry["step_count"]
    riser = geometry["riser"]
    going = geometry["going"]
    total_depth = geometry["total_depth"]
    toe_n = geometry["toe_n"]
    platform_front_n = geometry["platform_front_n"]
    platform_back_n = geometry["platform_back_n"]
    platform_center_n = geometry["platform_center_n"]

    half_width = platform_width_mm / 2.0
    stringer_t = half_width - stringer_width_mm / 2.0
    leg_t = half_width - leg_size_mm / 2.0
    stair_clear_width = platform_width_mm - 2.0 * stringer_width_mm
    if stair_clear_width <= 0.0:
        raise ValueError("斜梁过宽，净梯宽必须大于零。")

    n_front_leg = platform_front_n + leg_size_mm / 2.0
    n_back_leg = platform_back_n - leg_size_mm / 2.0

    slope_dir = (cos(angle), 0.0, sin(angle))
    slope_normal = (-sin(angle), 0.0, cos(angle))

    primitives = []

    # --- 主体：立柱、底架、斜梁、踏步、平台、脚轮、斜撑 --------------------
    for n_leg in (n_front_leg, n_back_leg):
        for side in (-1.0, 1.0):
            _add_box(primitives, (n_leg, side * leg_t, (base_z + platform_height_mm) / 2.0),
                     ("n", "t", "z"),
                     (leg_size_mm, leg_size_mm, platform_height_mm - base_z))

    base_center_z = base_z + base_beam_size_mm / 2.0
    for side in (-1.0, 1.0):
        _add_box(primitives, (0.0, side * leg_t, base_center_z), ("n", "t", "z"),
                 (total_depth, base_beam_size_mm, base_beam_size_mm))
    for n_beam in (toe_n, platform_back_n):
        _add_box(primitives, (n_beam, 0.0, base_center_z), ("n", "t", "z"),
                 (base_beam_size_mm, platform_width_mm, base_beam_size_mm))

    n_mid = (toe_n + platform_front_n) / 2.0
    z_mid = (base_z + platform_height_mm) / 2.0
    stringer_center = (n_mid + slope_normal[0] * (-stringer_depth_mm / 2.0),
                       0.0,
                       z_mid + slope_normal[2] * (-stringer_depth_mm / 2.0))
    for side in (-1.0, 1.0):
        _add_box(primitives, (stringer_center[0], side * stringer_t, stringer_center[2]),
                 ((0.0, 1.0, 0.0), slope_normal, slope_dir),
                 (stringer_width_mm, stringer_depth_mm, geometry["slope_length"]))

    for index in range(1, step_count + 1):
        tread_top = base_z + index * riser
        _add_box(primitives,
                 (toe_n + (index - 0.5) * going, 0.0, tread_top - tread_thickness_mm / 2.0),
                 ("n", "t", "z"),
                 (going, stair_clear_width, tread_thickness_mm))

    _add_box(primitives, (platform_center_n, 0.0,
                          platform_height_mm - platform_plate_thickness_mm / 2.0),
             ("n", "t", "z"),
             (platform_depth_mm, platform_width_mm, platform_plate_thickness_mm))

    frame_center_z = platform_height_mm - platform_plate_thickness_mm - platform_frame_size_mm / 2.0
    for side in (-1.0, 1.0):
        _add_box(primitives, (platform_center_n, side * (half_width - platform_frame_size_mm / 2.0),
                              frame_center_z), ("n", "t", "z"),
                 (platform_depth_mm, platform_frame_size_mm, platform_frame_size_mm))
    for n_frame in (platform_front_n + platform_frame_size_mm / 2.0,
                    platform_back_n - platform_frame_size_mm / 2.0):
        _add_box(primitives, (n_frame, 0.0, frame_center_z), ("n", "t", "z"),
                 (platform_frame_size_mm, platform_width_mm, platform_frame_size_mm))

    if caster_enabled:
        for n_caster in (toe_n, platform_back_n):
            for side in (-1.0, 1.0):
                _add_box(primitives,
                         (n_caster, side * leg_t, caster_plate_thickness_mm / 2.0),
                         ("n", "t", "z"),
                         (caster_plate_size_mm, caster_plate_size_mm,
                          caster_plate_thickness_mm))
                _add_cylinder(primitives,
                              (n_caster, side * leg_t, caster_wheel_diameter_mm / 2.0),
                              "t", caster_wheel_width_mm, caster_wheel_diameter_mm)

    if brace_enabled:
        # 后侧 X 撑：两根十字斜撑连接后立柱的底与顶。
        for sign in (-1.0, 1.0):
            _add_brace(primitives,
                       (n_back_leg, -sign * leg_t, base_z),
                       (n_back_leg, sign * leg_t, platform_height_mm),
                       brace_diameter_mm)
        # 左右侧撑：平台前上角 → 后立柱底，位于平台下方。
        for side in (-1.0, 1.0):
            _add_brace(primitives,
                       (platform_front_n, side * leg_t, platform_height_mm),
                       (platform_back_n, side * leg_t, base_z),
                       brace_diameter_mm)

    body_primitive_count = len(primitives)

    # --- 护栏：平台护栏 + 斜梯扶手（前侧梯口敞开）-------------------------
    if guard_enabled:
        # 护栏立柱自平台面立到顶杆高度。
        rail_center_z = platform_height_mm + rail_height_mm / 2.0

        # 平台后侧：顶杆 + 中杆 + 立柱 + 踢脚板。
        for z_rail in (platform_height_mm + rail_height_mm,
                       platform_height_mm + rail_mid_height_mm):
            _add_cylinder(primitives, (n_back_leg, 0.0, z_rail), "t",
                          platform_width_mm, rail_diameter_mm)
        for t_post in (-leg_t, 0.0, leg_t):
            _add_cylinder(primitives, (n_back_leg, t_post, rail_center_z), "z",
                          rail_height_mm, rail_diameter_mm)
        _add_box(primitives, (n_back_leg, 0.0, platform_height_mm + toe_height_mm / 2.0),
                 ("n", "t", "z"),
                 (toe_thickness_mm, platform_width_mm, toe_height_mm))

        # 平台左右两侧：顶杆 + 中杆 + 立柱 + 踢脚板。
        for side in (-1.0, 1.0):
            for z_rail in (platform_height_mm + rail_height_mm,
                           platform_height_mm + rail_mid_height_mm):
                _add_cylinder(primitives,
                              (platform_center_n, side * leg_t, z_rail), "n",
                              platform_depth_mm, rail_diameter_mm)
            for n_post in (platform_front_n, platform_center_n):
                _add_cylinder(primitives, (n_post, side * leg_t, rail_center_z), "z",
                              rail_height_mm, rail_diameter_mm)
            _add_box(primitives,
                     (platform_center_n, side * leg_t, platform_height_mm + toe_height_mm / 2.0),
                     ("n", "t", "z"),
                     (platform_depth_mm, toe_thickness_mm, toe_height_mm))

        # 斜梯扶手：沿斜面两侧的顶杆 + 中杆 + 竖立柱。
        post_length = stair_rail_height_mm / cos(angle)
        post_count = max(2, int(ceil(run / stair_post_spacing_mm)) + 1)
        for side in (-1.0, 1.0):
            for rail_h in (stair_rail_height_mm, stair_rail_mid_height_mm):
                _add_cylinder(primitives,
                              (n_mid + slope_normal[0] * rail_h, side * stringer_t,
                               z_mid + slope_normal[2] * rail_h),
                              slope_dir, geometry["slope_length"], rail_diameter_mm)
            for index in range(post_count):
                n_station = toe_n + run * index / (post_count - 1)
                z_base = base_z + (n_station - toe_n) * (rise / run) if run > 0.0 else base_z
                _add_cylinder(primitives,
                              (n_station, side * stringer_t, z_base + post_length / 2.0),
                              "z", post_length, rail_diameter_mm)

    return {
        "geometry": geometry,
        "platform_height": platform_height_mm,
        "platform_width": platform_width_mm,
        "platform_depth": platform_depth_mm,
        "base_z": base_z,
        "stringer_t": stringer_t,
        "leg_t": leg_t,
        "caster_enabled": bool(caster_enabled),
        "guard_enabled": bool(guard_enabled),
        "brace_enabled": bool(brace_enabled),
        "body_primitive_count": body_primitive_count,
        "primitives": primitives,
    }


# ============================================================================
# Bentley 实体创建
# ============================================================================

def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _uor_per_mm(dgn_model):
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _element_color():
    """返回可直接写入元素的精确 RGB 颜色编码，不改写活动颜色表。"""
    color_def = IntColorDef(COLOR_RGB[0], COLOR_RGB[1], COLOR_RGB[2])
    return DgnColorMap.CreateElementColor(
        color_def, None, None, ISessionMgr.GetActiveDgnFile()
    )


def _apply_color(element, color):
    if element is None or color is None:
        return element
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)
    return element


def _local_point(origin, frame, local_mm, uor_per_mm):
    """把局部毫米坐标 (n, t, z) 映射为世界 UOR 坐标元组。"""
    n, t, z = frame
    x_mm, y_mm, z_mm = local_mm
    x = origin.x + (n[0] * x_mm + t[0] * y_mm + z[0] * z_mm) * uor_per_mm
    y = origin.y + (n[1] * x_mm + t[1] * y_mm + z[1] * z_mm) * uor_per_mm
    z = origin.z + (n[2] * x_mm + t[2] * y_mm + z[2] * z_mm) * uor_per_mm
    return (x, y, z)


def _local_vector(frame, vec):
    """把局部 (n, t, z) 分量映射为世界单位向量（仅方向，不含原点平移）。"""
    n, t, z = frame
    a, b, c = vec
    return (
        a * n[0] + b * t[0] + c * z[0],
        a * n[1] + b * t[1] + c * z[1],
        a * n[2] + b * t[2] + c * z[2],
    )


def _axis_world(frame, spec):
    """把轴向说明（'n'/'t'/'z' 或局部三分量）解析为世界单位向量。"""
    if isinstance(spec, str):
        return {"n": frame[0], "t": frame[1], "z": frame[2]}[spec]
    return _local_vector(frame, spec)


def _create_box(dgn_model, center, axis_u, axis_v, axis_w,
                size_u, size_v, size_w, color):
    """创建任意定向的矩形实体块。

    矩形轮廓位于 u-v 平面、位于 center - w·size_w/2，沿 +w 拉伸 size_w，
    因此最终实体以 center 为中心。要求 axis_u × axis_v = axis_w（右手系）。
    """
    if size_u <= 0.0 or size_v <= 0.0 or size_w <= 0.0:
        raise ValueError("实体块尺寸必须大于零。")

    half_w = size_w / 2.0
    base = (
        center[0] - axis_w[0] * half_w,
        center[1] - axis_w[1] * half_w,
        center[2] - axis_w[2] * half_w,
    )

    def corner(sign_u, sign_v):
        su = sign_u * size_u / 2.0
        sv = sign_v * size_v / 2.0
        return DPoint3d.From(
            base[0] + axis_u[0] * su + axis_v[0] * sv,
            base[1] + axis_u[1] * su + axis_v[1] * sv,
            base[2] + axis_u[2] * su + axis_v[2] * sv,
        )

    points = DPoint3dArray()
    points.append(corner(-1.0, -1.0))
    points.append(corner(+1.0, -1.0))
    points.append(corner(+1.0, +1.0))
    points.append(corner(-1.0, +1.0))

    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    if not _succeeded(ShapeHandler.CreateShapeElement(
            profile, None, points, model_ref.Is3d(), model_ref)):
        return None

    status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if not _succeeded(status):
        return None
    if not _succeeded(SolidUtil.Modify.ThickenSheet(body, size_w, 0.0)):
        return None

    finished = EditElementHandle()
    if not _succeeded(SolidUtil.Convert.BodyToElement(finished, body, profile, dgn_model)):
        return None
    return _apply_color(finished, color)


def _create_cylinder(dgn_model, start, end, radius, color):
    """创建实心圆柱（任意方向）。start / end 为世界 UOR 坐标元组。"""
    detail = DgnConeDetail(
        DPoint3d.From(start[0], start[1], start[2]),
        DPoint3d.From(end[0], end[1], end[2]),
        radius, radius, True,
    )
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return _apply_color(element, color)


def _create_primitive_elements(dgn_model, origin, frame, primitive, uor_per_mm, color):
    """按一个布局原语创建（未写入模型的）元素，返回元素列表。"""
    if primitive["type"] == "box":
        center = _local_point(origin, frame, primitive["center"], uor_per_mm)
        axis_specs = primitive["axes"]
        size = primitive["size"]
        return [_create_box(
            dgn_model, center,
            _axis_world(frame, axis_specs[0]),
            _axis_world(frame, axis_specs[1]),
            _axis_world(frame, axis_specs[2]),
            size[0] * uor_per_mm, size[1] * uor_per_mm, size[2] * uor_per_mm,
            color,
        )]
    if primitive["type"] == "cylinder":
        center = _local_point(origin, frame, primitive["center"], uor_per_mm)
        axis = _axis_world(frame, primitive["axis"])
        half = primitive["length"] * uor_per_mm / 2.0
        start = tuple(center[i] - axis[i] * half for i in range(3))
        end = tuple(center[i] + axis[i] * half for i in range(3))
        return [_create_cylinder(
            dgn_model, start, end, primitive["diameter"] * uor_per_mm / 2.0, color)]
    raise ValueError("未知构件类型：%r" % primitive["type"])


class _CellBuilder(object):
    """把一组构件封装成指定名称的普通单元。"""

    def __init__(self, dgn_model, cell_name):
        self.dgn_model = dgn_model
        self.cell_name = cell_name
        self.cell = EditElementHandle()
        self.child_count = 0
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError("单元 %s 的子元素创建失败。" % self.cell_name)
        if not _succeeded(NormalCellHeaderHandler.AddChildElement(self.cell, child)):
            raise RuntimeError("无法将子元素加入普通单元 %s。" % self.cell_name)
        self.child_count += 1

    def commit(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError("无法完成普通单元 %s。" % self.cell_name)
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError("无法将普通单元 %s 写入模型。" % self.cell_name)
        return self.cell


def build_maintenance_ladder_elements(dgn_model, origin, frame, layout, color):
    """按布局创建检修爬梯并把**主体、护栏分别组成一个普通单元**写入模型。

    返回单元句柄列表。创建过程中不把零件单独写入模型，只有组装好的单元进模型，
    因此失败时不会留下零散构件。
    """
    uor_per_mm = _uor_per_mm(dgn_model)
    split = layout.get("body_primitive_count", len(layout["primitives"]))
    body_cell = _CellBuilder(dgn_model, BODY_CELL_NAME)
    guard_cell = _CellBuilder(dgn_model, GUARD_CELL_NAME)
    try:
        for index, primitive in enumerate(layout["primitives"]):
            elements = _create_primitive_elements(
                dgn_model, origin, frame, primitive, uor_per_mm, color)
            if not elements:
                raise RuntimeError("构件创建失败：%s" % primitive["type"])
            builder = body_cell if index < split else guard_cell
            for element in elements:
                if element is None:
                    raise RuntimeError("构件创建失败：%s" % primitive["type"])
                builder.add(element)
        cells = []
        if body_cell.child_count:
            cells.append(body_cell.commit())
        if guard_cell.child_count:
            cells.append(guard_cell.commit())
        return cells
    except Exception:
        _delete_elements([body_cell.cell, guard_cell.cell])
        raise


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


def _delete_elements(handles):
    deleted = False
    for handle in handles or ():
        deleted = _delete_element(handle) or deleted
    return deleted


def draw_maintenance_ladder(origin_point, outward=(1.0, 0.0), **params):
    """直接生成并写入模型，返回单元句柄列表（主体单元、护栏单元）。

    origin_point : 底架中心在地面上的世界 UOR 坐标 DPoint3d。
    outward      : 爬升方向（水平）。
    其余关键字参数传给 build_maintenance_ladder_layout。
    """
    dgn_model = ISessionMgr.GetActiveDgnModel()
    layout = build_maintenance_ladder_layout(**params)
    frame = build_frame(outward)
    return build_maintenance_ladder_elements(
        dgn_model, origin_point, frame, layout, _element_color())


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


# ============================================================================
# 界面辅助（与“墙面爬梯 / 可拆卸栏杆”保持一致的做法）
# ============================================================================

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


class _MaintenanceLadderSettingsDialog(_MicroStationTk):
    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("检修爬梯")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)
        self.origin_point = None
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
        tk.Label(title_row, text="检修爬梯", bg=bg, fg=ink,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="45° 斜梯 · 1 m×1 m 平台 · 平台高 2000 · 可选脚轮",
                 bg=bg, fg=muted, font=ui_font_small).pack(
                     anchor="w", pady=(4, 0), padx=(18, 0))

        card_frame = tk.Frame(shell, bg=card, highlightbackground=border,
                              highlightthickness=1)
        card_frame.pack(fill="both", expand=True)
        form = ttk.Frame(card_frame, style="Card.TFrame", padding=20)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        self.height_var = tk.StringVar(value=str(int(PLATFORM_HEIGHT)))
        self.width_var = tk.StringVar(value=str(int(PLATFORM_WIDTH)))
        self.depth_var = tk.StringVar(value=str(int(PLATFORM_DEPTH)))
        self.angle_var = tk.StringVar(value=str(int(STAIR_ANGLE_DEG)))
        self.riser_var = tk.StringVar(value=str(int(STEP_TARGET_RISER)))
        self.rail_var = tk.StringVar(value=str(int(RAIL_HEIGHT)))
        self.outward_var = tk.StringVar(value="0")

        ttk.Label(form, text="布置参数", style="GlassMuted.TLabel",
                  font=ui_font_small).grid(row=0, column=0, columnspan=3, sticky="w")

        entries = []
        rows = [
            ("平台高度（自地面）", self.height_var, "mm"),
            ("平台宽度", self.width_var, "mm"),
            ("平台深度", self.depth_var, "mm"),
            ("爬梯角度", self.angle_var, "°"),
            ("目标级高", self.riser_var, "mm"),
            ("平台护栏高", self.rail_var, "mm"),
            ("爬升方向水平角（0=+X，90=+Y）", self.outward_var, "°"),
        ]
        for index, (label, variable, unit) in enumerate(rows, start=1):
            ttk.Label(form, text=label, style="GlassMuted.TLabel").grid(
                row=index, column=0, sticky="w", pady=7)
            entry = tk.Entry(form, textvariable=variable, width=10, font=ui_font,
                             fg=ink, bg=field, relief="flat",
                             highlightthickness=1, highlightbackground=border,
                             highlightcolor="#9FB4CC", insertbackground=ink,
                             justify="center")
            entry.grid(row=index, column=1, sticky="w", padx=(12, 8), ipady=4)
            entry.bind("<Return>", self.on_options_changed)
            entry.bind("<FocusOut>", self.on_options_changed)
            entries.append(entry)
            ttk.Label(form, text=unit, style="GlassMuted.TLabel").grid(
                row=index, column=2, sticky="w", pady=7)

        self.guard_var = tk.BooleanVar(value=bool(GUARD_ENABLED))
        self.caster_var = tk.BooleanVar(value=bool(CASTER_ENABLED))
        self.brace_var = tk.BooleanVar(value=bool(BRACE_ENABLED))
        option_row = len(rows) + 1
        for text, variable in (("平台护栏 + 斜梯扶手", self.guard_var),
                               ("带脚轮（底架抬高 125）", self.caster_var),
                               ("加斜撑", self.brace_var)):
            check = tk.Checkbutton(
                form, text=text, variable=variable, command=self.on_options_changed,
                bg=card, fg=ink, activebackground=card, selectcolor=card,
                font=ui_font, highlightthickness=0, bd=0)
            check.grid(row=option_row, column=0, columnspan=3, sticky="w", pady=(2, 0))
            entries.append(check)
            option_row += 1

        separator_row = option_row
        ttk.Separator(form, orient="horizontal").grid(
            row=separator_row, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="预览", style="GlassMuted.TLabel").grid(
            row=separator_row + 1, column=0, sticky="nw", pady=3)
        self.info_label = ttk.Label(form, text="—", style="Glass.TLabel",
                                    justify="left", wraplength=340)
        self.info_label.grid(row=separator_row + 1, column=1, columnspan=2,
                             sticky="w", padx=(12, 0), pady=3)

        ttk.Label(form, text="操作", style="GlassMuted.TLabel").grid(
            row=separator_row + 2, column=0, sticky="nw", pady=3)
        ttk.Label(form, text="在模型中点取底架中心（地面）以放置，程序即时生成预览",
                  style="Glass.TLabel", justify="left", wraplength=340).grid(
                      row=separator_row + 2, column=1, columnspan=2, sticky="w",
                      padx=(12, 0), pady=3)

        status_chip = tk.Frame(form, bg=card_soft, highlightbackground=border,
                               highlightthickness=1)
        status_chip.grid(row=separator_row + 3, column=0, columnspan=3,
                         sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(status_chip, text="请在模型中点取底架中心。",
                                     bg=card_soft, fg="#1f5f99",
                                     font=ui_font_small, wraplength=340,
                                     justify="left")
        self.status_label.pack(anchor="w", padx=12, pady=8)

        button_bar = tk.Frame(form, bg=card)
        button_bar.grid(row=separator_row + 4, column=0, columnspan=3,
                        sticky="ew", pady=(14, 0))
        self.confirm_button = _RoundButton(
            button_bar, "确定", self.confirm_tool, primary=True, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.cancel_button = _RoundButton(
            button_bar, "取消", self.cancel_tool, bg=card,
            font=ui_font, font_bold=ui_font_bold)
        self.confirm_button.pack(side="right")
        self.cancel_button.pack(side="right", padx=(0, 8))

        self.option_widgets = entries
        self.action_buttons = [self.confirm_button, self.cancel_button]

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

    def get_params(self):
        try:
            height = float(self.height_var.get())
            width = float(self.width_var.get())
            depth = float(self.depth_var.get())
            angle = float(self.angle_var.get())
            riser = float(self.riser_var.get())
            rail = float(self.rail_var.get())
            outward_deg = float(self.outward_var.get())
        except (TypeError, ValueError):
            raise ValueError("所有输入都必须是数字。")
        if height <= 0.0 or width <= 0.0 or depth <= 0.0:
            raise ValueError("平台高度、宽度、深度必须大于零。")
        if not (5.0 < angle < 85.0):
            raise ValueError("爬梯角度应在 5°～85° 之间。")
        if riser <= 0.0 or rail <= 0.0:
            raise ValueError("目标级高、护栏高必须大于零。")
        radians_value = outward_deg * pi / 180.0
        return {
            "platform_height_mm": height,
            "platform_width_mm": width,
            "platform_depth_mm": depth,
            "stair_angle_deg": angle,
            "step_target_riser_mm": riser,
            "rail_height_mm": rail,
            "guard_enabled": bool(self.guard_var.get()),
            "caster_enabled": bool(self.caster_var.get()),
            "brace_enabled": bool(self.brace_var.get()),
            "outward": (cos(radians_value), sin(radians_value)),
        }

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
        if self.origin_point is not None:
            self._cancel_pending()
            self._pending_regeneration = self.after(
                REGENERATE_DELAY_MS, self._run_pending)

    def _run_pending(self):
        self._pending_regeneration = None
        if self._closing:
            return
        self.regenerate(self.origin_point)

    def regenerate(self, origin_point):
        self._cancel_pending()
        if origin_point is None:
            return None
        self.origin_point = _copy_dpoint(origin_point)
        self._set_busy(True)
        self.set_status("正在生成检修爬梯预览，请稍候……")
        try:
            dgn_model = ISessionMgr.GetActiveDgnModel()
            params = self.get_params()
            outward = params.pop("outward")
            layout = build_maintenance_ladder_layout(**params)
            frame = build_frame(outward)
            new_handles = build_maintenance_ladder_elements(
                dgn_model, origin_point, frame, layout, _element_color())
        except Exception as error:
            message = "爬梯生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return None
        finally:
            self._set_busy(False)

        self._delete_preview()
        self.preview_handles = new_handles
        self.preview_result = layout
        geometry = layout["geometry"]
        self.info_label.configure(text=(
            "平台 %.0f 高；%.0f 级踏步（级高 %.0f，踏面 %.0f）；"
            "底架深 %.0f；%s；%s" % (
                layout["platform_height"],
                geometry["step_count"], geometry["riser"], geometry["going"],
                layout["geometry"]["total_depth"],
                "带脚轮" if layout["caster_enabled"] else "无脚轮",
                "带护栏" if layout["guard_enabled"] else "无护栏")))
        message = "预览已更新：%d 个单元。" % len(new_handles)
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return layout

    def _delete_preview(self):
        handles = self.preview_handles
        self.preview_handles = None
        self.preview_result = None
        return _delete_elements(handles)

    def discard_preview(self):
        return self._delete_preview()

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


# ============================================================================
# 交互工具
# ============================================================================

class MaintenanceLadderPlacementTool(DgnPrimitiveTool):
    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString("MaintenanceLadderPlacementTool")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            "请点取检修爬梯底架中心（地面）；右键取消。")

    def _OnDataButton(self, event):
        if self.tool_settings is not None:
            try:
                self.tool_settings.regenerate(event.GetPoint())
            except Exception as error:
                message = "爬梯生成失败：%s" % error
                self.tool_settings.set_status(message, True)
                NotificationManager.OutputPrompt(message)
                print(message)
        return True

    def _OnResetButton(self, event):
        if self.tool_settings is not None:
            self.tool_settings.cancel_tool()
        else:
            self._ExitTool()
        return True

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
        settings = tool_settings if tool_settings is not None else _MaintenanceLadderSettingsDialog()
        tool = MaintenanceLadderPlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    MaintenanceLadderPlacementTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
