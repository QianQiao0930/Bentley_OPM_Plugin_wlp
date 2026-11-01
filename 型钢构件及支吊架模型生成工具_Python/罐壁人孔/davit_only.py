# -*- coding: utf-8 -*-
"""罐壁人孔吊杆（davit）单独建模脚本 —— 仅绘制吊杆，便于先单独测试。

按图 BN-DS-A 4《DAVIT FOR MANWAY COVERS》的吊杆细节：

* 下部（立柱 / 回转段）为**实心圆钢**，直径按吊杆直径表 D
  （24" + ASA 150 lbs → φ45）。
* 圆钢向上经 **R=220** 弯头折成水平臂，跨过盖板中心。
* 臂的**最末端为扁头**：**100 宽 × 120 长 × D/2 厚**，中开
  **40 × 22 腰形孔**，套在盖板顶部竖直的 M20 吊环螺栓上。
* 扁头与圆管之间用**放样过渡**：一个断面是 ØD 的圆、一个断面是
  100 × D/2 的矩形，放样长度 = **1.5 D**。
* 立柱下端穿过法兰上的一对吊耳环 **RING 16 THK**（销孔 = D + 3，两环
  净距 128，中间夹 BRASS RING 3 THK），立柱下端伸出 25，销孔 20 处插
  **Ø5 开口销**防脱（可关掉吊耳环，只留吊杆本体）。

本脚本**不包含**人孔法兰、盖板、螺栓、把手 —— 那些在
`tank_wall_manhole.py` 里。此处只出吊杆，且不修改原脚本。

坐标：点取点为**扁头正中心**（长圆孔中心 = M20 螺栓轴线）在扁头中面标高，
局部 +x 为水平切向、+y 由扁头指向立柱、+z 竖直向上；朝向参数绕 z 旋转。

纯 Python 可先验算尺寸：`python -B davit_only.py --self-test`
（只跑不依赖 Bentley 的布局 / 校验计算，不生成图元）。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import print_function

from math import atan2, cos, hypot, pi, radians, sin
import os
import sys
import traceback

# 自检模式（--self-test）只跑纯数学布局，不依赖 Bentley / 图形库，因此把
# MSPy、win32gui、tkinter 都挡在后面，并用占位基类代替相应基类。
_SELF_TEST = "--self-test" in sys.argv

if _SELF_TEST:
    import types as _types

    class _PlaceholderTk(object):
        def __init__(self, *args, **kwargs):
            pass

    class DgnPrimitiveTool(object):
        def __init__(self, *args, **kwargs):
            pass

    tk = _types.SimpleNamespace(Tk=_PlaceholderTk)
    tkinter = _types.SimpleNamespace(_default_root=None)
else:
    import tkinter as tk
    import tkinter
    import win32gui

    from MSPyBentley import *
    from MSPyBentleyGeom import *
    from MSPyDgnPlatform import *
    from MSPyDgnView import *
    from MSPyMstnPlatform import *


# ---------------------------------------------------------------------------
# 尺寸（mm）—— 图纸标注与本次确认的扁头 / 放样尺寸
# ---------------------------------------------------------------------------

DAVIT_DIA_DEFAULT = 45.0      # 吊杆直径 D：24" + ASA 150 lbs
BEND_RADIUS = 220.0           # R=220（圆钢弯头中心线半径）

# 扁头（只有吊杆臂的最末端这一段是扁的）
FLAT_HEAD_WIDTH = 100.0       # 扁头宽（水平、垂直于臂轴线）
FLAT_HEAD_LENGTH = 120.0      # 扁头长（沿臂轴线）
FLAT_HEAD_HEIGHT_FACTOR = 0.5  # 扁头厚 = D / 2
LOFT_LENGTH_FACTOR = 1.5      # 圆管→矩形的放样长度 = 1.5 D
SLOT_LENGTH = 40.0            # 长圆孔长（沿臂轴线，套 M20 螺栓起调整作用）
SLOT_WIDTH = 22.0             # 长圆孔宽（= 两端半圆直径）
SLOT_END_SEGMENTS = 12        # 长圆孔两端半圆的分段数（直边恒为直线）

# 立柱与吊耳环
ARM_REACH_DEFAULT = 500.0     # 扁头腰形孔中心到立柱轴线的水平距离
RING_LEVEL_DEFAULT = -280.0   # 上吊耳环销孔中心标高（必须在弯头起点以下）
RING_THICKNESS = 16.0         # RING 16 THK
RING_GAP = 128.0              # 两吊耳环之间的净距
BRASS_THICKNESS = 3.0         # BRASS RING 3 THK（黄铜垫环）
RING_WALL = 16.0              # 吊耳环径向壁厚（图纸未注，经验值）
RING_HOLE_CLEARANCE = 3.0     # 吊耳环销孔 = D + 3
POST_BELOW = 25.0             # 立柱下端伸出下吊耳环底面的长度
COTTER_OFFSET = 20.0          # 开口销孔到立柱下端的距离
COTTER_DIA = 5.0              # 5mm DIA FOR COTTER PIN
COTTER_HOLE_DIA = 5.5
MIN_ARM_SEGMENT = 20.0        # 放样起点到弯头末端至少要留的直臂长度

# 放样：两个断面用同一组角度采样（段数、起点一一对应），避免直纹过渡扭转。
LOFT_SIDES = 24               # 圆端近似多边形的边数
LOFT_SLICES = 24              # 直纹放样不可用时的台阶近似段数

COLOR_DAVIT = 2
COLOR_FLAT = 4
COLOR_LOFT = 4
COLOR_RING = 3
COLOR_BRASS = 6
COLOR_PIN = 5

CELL_NAME = "DAVIT"

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150

DEFAULT_OPTIONS = {
    "davit_dia": DAVIT_DIA_DEFAULT,
    "arm_reach": ARM_REACH_DEFAULT,
    "ring_level": RING_LEVEL_DEFAULT,
    "flat_width": FLAT_HEAD_WIDTH,
    "flat_length": FLAT_HEAD_LENGTH,
    "heading_deg": 0.0,
    "include_rings": True,
    "mirrored": False,
}


def _succeeded(status):
    """Bentley 状态码为 0 表示成功；兼容不导出 BentleyStatus 的版本。"""
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _write_debug_log(title, detail):
    try:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "davit_only_debug_log.txt",
        )
        with open(path, "a") as stream:
            stream.write("=== %s ===\n%s\n" % (title, detail))
    except Exception:
        pass


def _apply_color(element, color):
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)


def _resolve_options(options=None):
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        for key in options:
            if key not in resolved:
                raise ValueError("未知选项：%s" % key)
            resolved[key] = options[key]

    for key, label in (
        ("davit_dia", "吊杆直径"),
        ("arm_reach", "立柱偏距"),
        ("ring_level", "上吊耳环标高"),
        ("flat_width", "扁头宽"),
        ("flat_length", "扁头长"),
    ):
        try:
            resolved[key] = float(resolved[key])
        except (TypeError, ValueError):
            raise ValueError("%s必须是数字（mm）。" % label)

    if resolved["davit_dia"] <= 0.0:
        raise ValueError("吊杆直径必须大于零。")
    if resolved["arm_reach"] <= 2.0 * BEND_RADIUS:
        raise ValueError(
            "立柱偏距必须大于 2 × R220 = %.0f mm，否则弯头与立柱重叠。"
            % (2.0 * BEND_RADIUS)
        )
    if resolved["flat_width"] <= SLOT_WIDTH:
        raise ValueError("扁头宽必须大于长圆孔宽 %.0f mm。" % SLOT_WIDTH)
    if resolved["flat_length"] < SLOT_LENGTH + 20.0:
        raise ValueError(
            "扁头长至少应有 %.0f mm，长圆孔（%.0f）居中后两侧还要留料。"
            % (SLOT_LENGTH + 20.0, SLOT_LENGTH)
        )
    # R220 弯头起点在 z = -220，吊耳环必须在其下方，否则立柱穿不过吊耳环。
    if resolved["ring_level"] + RING_THICKNESS / 2.0 > -BEND_RADIUS:
        raise ValueError(
            "上吊耳环标高的顶部必须不高于弯头起点 z = -%.0f mm（建议 ≤ %.0f）。"
            % (BEND_RADIUS, -BEND_RADIUS - RING_THICKNESS / 2.0)
        )
    # 放样 + 扁头要能放进弯头末端与连接点之间。
    reach_for_head = (resolved["flat_length"] / 2.0
                      + resolved["davit_dia"] * LOFT_LENGTH_FACTOR)
    if resolved["arm_reach"] - BEND_RADIUS - reach_for_head < MIN_ARM_SEGMENT:
        raise ValueError(
            "立柱偏距太小：放样与扁头占 %.0f mm，直臂至少还要 %.0f mm，"
            "请把立柱偏距加大到 %.0f mm 以上。"
            % (reach_for_head, MIN_ARM_SEGMENT,
               reach_for_head + MIN_ARM_SEGMENT + BEND_RADIUS)
        )

    try:
        heading = float(resolved["heading_deg"])
    except (TypeError, ValueError):
        raise ValueError("朝向必须是数字（度）。")
    if heading != heading or heading in (float("inf"), float("-inf")):
        raise ValueError("朝向必须是有限数字。")

    resolved["heading_deg"] = heading
    resolved["include_rings"] = bool(resolved["include_rings"])
    resolved["mirrored"] = bool(resolved["mirrored"])
    return resolved


def _davit_layout(resolved):
    """算出各标高 / 站位；吊耳环与立柱下端由吊耳环标高推导，保证都在立柱上。"""
    diameter = resolved["davit_dia"]
    upper_ring_z = resolved["ring_level"]
    lower_ring_z = upper_ring_z - (RING_GAP + RING_THICKNESS)
    post_bottom = lower_ring_z - RING_THICKNESS / 2.0 - POST_BELOW

    # 沿臂轴线（局部 y）从外端向立柱方向的各站位。
    # 点取点为扁头正中心，长圆孔因此天然居中；扁头前后各半长。
    y_tip = -resolved["flat_length"] / 2.0
    y_rect = resolved["flat_length"] / 2.0                # 扁头/放样的矩形断面
    y_round = y_rect + diameter * LOFT_LENGTH_FACTOR      # 放样/圆管的圆形断面

    return {
        "arm_reach": resolved["arm_reach"],
        "bend_center_y": resolved["arm_reach"] - BEND_RADIUS,
        "bend_center_z": -BEND_RADIUS,
        "bend_end_y": resolved["arm_reach"] - BEND_RADIUS,
        "upper_ring_z": upper_ring_z,
        "lower_ring_z": lower_ring_z,
        "ring_outer_r": (diameter + RING_HOLE_CLEARANCE) / 2.0 + RING_WALL,
        "ring_inner_r": (diameter + RING_HOLE_CLEARANCE) / 2.0,
        "post_bottom": post_bottom,
        "cotter_z": post_bottom + COTTER_OFFSET,
        "flat_thickness": diameter * FLAT_HEAD_HEIGHT_FACTOR,
        "loft_length": diameter * LOFT_LENGTH_FACTOR,
        "y_tip": y_tip,
        "y_rect": y_rect,
        "y_round": y_round,
    }


class _DavitFrame(object):
    """吊杆局部坐标：x 水平切向、y 由扁头指向立柱、z 竖直向上。"""

    def __init__(self, origin, uor_per_mm, heading_deg):
        angle = radians(heading_deg)
        self.origin = origin
        self.uor_per_mm = uor_per_mm
        self.u = (cos(angle), sin(angle))
        self.v = (-sin(angle), cos(angle))

    def point(self, x_mm, y_mm, z_mm):
        scale = self.uor_per_mm
        return DPoint3d.From(
            self.origin.x + (self.u[0] * x_mm + self.v[0] * y_mm) * scale,
            self.origin.y + (self.u[1] * x_mm + self.v[1] * y_mm) * scale,
            self.origin.z + z_mm * scale,
        )

    def uor(self, mm):
        return mm * self.uor_per_mm


# ---------------------------------------------------------------------------
# 基本几何件
# ---------------------------------------------------------------------------


def _cylinder_element(dgn_model, start, end, radius):
    detail = DgnConeDetail(start, end, radius, radius, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return element


def _cylinder_body(dgn_model, start, end, radius):
    element = _cylinder_element(dgn_model, start, end, radius)
    if element is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if not _succeeded(status):
        return None
    return body


def _element_from_body(dgn_model, body, template, color):
    finished = EditElementHandle()
    if not _succeeded(SolidUtil.Convert.BodyToElement(finished, body, template, dgn_model)):
        return None
    if color is not None:
        _apply_color(finished, color)
    return finished


def _subtract(body, cutters):
    """一次布尔调用减掉全部孔，避免多次相减在共面处出错。"""
    tools = ISolidKernelEntityPtrArray()
    count = 0
    for cutter in cutters:
        if cutter is None:
            continue
        tools.append(cutter)
        count += 1
    if count:
        SolidUtil.Modify.BooleanSubtract(body, tools)


def _solid_cylinder(dgn_model, start, end, radius_uor, color, holes=()):
    """实心圆柱；holes 为 (start, end, radius_uor)，写入前先掏掉。"""
    outer = _cylinder_element(dgn_model, start, end, radius_uor)
    if outer is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if not _succeeded(status):
        return None
    _subtract(body, [_cylinder_body(dgn_model, s, e, r) for s, e, r in holes])
    return _element_from_body(dgn_model, body, outer, color)


def _hollow_cylinder(dgn_model, start, end, outer_r_uor, inner_r_uor, color):
    """空心圆柱（吊耳环）：外圆柱减内圆柱，内圆柱两端各外伸 2 mm。"""
    outer = _cylinder_element(dgn_model, start, end, outer_r_uor)
    if outer is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if not _succeeded(status):
        return None
    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    length = hypot(hypot(dx, dy), dz)
    if length <= 1.0e-9:
        return None
    extension = 2.0 / length
    inner = _cylinder_body(
        dgn_model,
        DPoint3d.From(start.x - dx * extension, start.y - dy * extension,
                      start.z - dz * extension),
        DPoint3d.From(end.x + dx * extension, end.y + dy * extension,
                      end.z + dz * extension),
        inner_r_uor,
    )
    _subtract(body, [inner])
    return _element_from_body(dgn_model, body, outer, color)


def _torus_pipe(dgn_model, center, vector_x, vector_y, major_uor, minor_uor, sweep):
    detail = DgnTorusPipeDetail(
        center, vector_x, vector_y, major_uor, minor_uor, sweep, True
    )
    primitive = ISolidPrimitive.CreateDgnTorusPipe(detail)
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return element


def _plate_with_holes(dgn_model, profile_points, thickness_uor, color,
                      holes=(), cutter_elements=()):
    """按闭合轮廓沿法向拉伸成板，再一次减掉全部刀具体。

    holes 为 (start, end, radius_uor) 圆柱孔；cutter_elements 为已建好的
    刀具体（例如长圆孔），两者一起在**同一次**布尔里减掉。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    if not _succeeded(
        ShapeHandler.CreateShapeElement(
            profile, None, profile_points, model_ref.Is3d(), model_ref
        )
    ):
        return None
    status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if not _succeeded(status):
        return None
    if not _succeeded(SolidUtil.Modify.ThickenSheet(body, thickness_uor, 0.0)):
        return None
    cutters = [_cylinder_body(dgn_model, s, e, r) for s, e, r in holes]
    for element in cutter_elements:
        if element is None:
            continue
        cutter_status, cutter_body = SolidUtil.Convert.ElementToBody(
            element, True, True, False
        )
        if _succeeded(cutter_status):
            cutters.append(cutter_body)
    _subtract(body, cutters)
    return _element_from_body(dgn_model, body, profile, color)


def _rectangle_perimeter(half_width_mm, half_thickness_mm, per_side):
    """矩形边界采样点（**含 4 个角点**），逆时针，从 (w, -t) 起。

    每边取 per_side 个点（含起点），因此相邻点都在同一条直边上，
    折线严格等于矩形本身，放样矩形端才能与扁头端面对齐、不留缺口。
    """
    corners = ((half_width_mm, -half_thickness_mm),
               (half_width_mm, half_thickness_mm),
               (-half_width_mm, half_thickness_mm),
               (-half_width_mm, -half_thickness_mm))
    points = []
    for index in range(4):
        x0, z0 = corners[index]
        x1, z1 = corners[(index + 1) % 4]
        for step in range(per_side):
            ratio = float(step) / per_side
            points.append((x0 + (x1 - x0) * ratio, z0 + (z1 - z0) * ratio))
    return points


def _section_offsets(half_width_mm, half_thickness_mm, radius_mm, t,
                     per_side=None):
    """断面点列（纯数学）：t=0 为矩形、t=1 为 ØD 圆，两端按序号配对。

    序号按角度均匀铺在圆上、起点与矩形首点同方向，因此放样不会扭转。
    """
    if per_side is None:
        per_side = max(1, LOFT_SIDES // 4)
    rectangle = _rectangle_perimeter(half_width_mm, half_thickness_mm, per_side)
    count = len(rectangle)
    start_angle = atan2(-half_thickness_mm, half_width_mm)
    offsets = []
    for index, (rect_x, rect_z) in enumerate(rectangle):
        angle = start_angle + 2.0 * pi * index / count
        circle_x = radius_mm * cos(angle)
        circle_z = radius_mm * sin(angle)
        offsets.append((
            (1.0 - t) * rect_x + t * circle_x,
            (1.0 - t) * rect_z + t * circle_z,
        ))
    return offsets


def _section_points(frame, y_mm, half_width_mm, half_thickness_mm, radius_mm, t):
    """断面点列 → 模型点列（位于 y = y_mm 平面内）。"""
    points = DPoint3dArray()
    for x, z in _section_offsets(half_width_mm, half_thickness_mm, radius_mm, t):
        points.append(frame.point(x, y_mm, z))
    points.append(points[0])
    return points


def _obround_profile(half_width_mm, half_length_mm, end_segments):
    """长圆孔轮廓（逆时针）：两条**直边** + 两端半圆。

    half_length 为孔半长、half_width 为孔半宽（= 半圆半径）。
    """
    straight = half_length_mm - half_width_mm
    points = [(half_width_mm, -straight), (half_width_mm, straight)]
    for index in range(1, end_segments):
        angle = pi * index / end_segments
        points.append((half_width_mm * cos(angle),
                       straight + half_width_mm * sin(angle)))
    points.append((-half_width_mm, straight))
    points.append((-half_width_mm, -straight))
    for index in range(1, end_segments):
        angle = pi + pi * index / end_segments
        points.append((half_width_mm * cos(angle),
                       -straight + half_width_mm * sin(angle)))
    return points


def _section_curve(frame, y_mm, half_width_mm, half_thickness_mm, radius_mm, t):
    """断面点列 → CurveVector（供直纹放样使用）。"""
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    points = _section_points(frame, y_mm, half_width_mm, half_thickness_mm,
                             radius_mm, t)
    if not _succeeded(
        ShapeHandler.CreateShapeElement(profile, None, points, model_ref.Is3d(), model_ref)
    ):
        return None
    return ICurvePathQuery.ElementToCurveVector(profile)


def _ruled_sweep_element(dgn_model, section_a, section_b, color):
    """两个断面之间的直纹放样实体。返回 (实体, 失败原因)。"""
    if section_a is None or section_b is None:
        return None, "断面创建失败"
    try:
        detail = DgnRuledSweepDetail(section_a, section_b, True)
    except Exception as error:
        return None, "DgnRuledSweepDetail: %s" % error
    try:
        primitive = ISolidPrimitive.CreateDgnRuledSweep(detail)
    except Exception as error:
        return None, "CreateDgnRuledSweep: %s" % error
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None, "ToElement 返回失败"
    _apply_color(element, color)
    return element, ""


def _body_from_loft_element(dgn_model, sections, color):
    """备选：SolidUtil.Create.BodyFromLoft（部分版本才有）。返回 (实体, 失败原因)。"""
    create = getattr(getattr(SolidUtil, "Create", None), "BodyFromLoft", None)
    array_type = globals().get("CurveVectorArray")
    if create is None:
        return None, "无 SolidUtil.Create.BodyFromLoft"
    if array_type is None:
        return None, "无 CurveVectorArray"
    try:
        container = array_type()
        for section in sections:
            container.append(section)
        result = create(container, True, dgn_model)
    except Exception as error:
        return None, "BodyFromLoft: %s" % error
    if isinstance(result, tuple):
        status, body = result[0], result[1]
        if not _succeeded(status):
            return None, "BodyFromLoft 返回失败"
        element = EditElementHandle()
        if not _succeeded(SolidUtil.Convert.BodyToElement(element, body, None, dgn_model)):
            return None, "BodyFromLoft 转元素失败"
        _apply_color(element, color)
        return element, ""
    if result is None:
        return None, "BodyFromLoft 返回空"
    _apply_color(result, color)
    return result, ""


def _union_elements(dgn_model, elements, color):
    """把多个实体并成一个；任何一步失败返回 None（调用方退化为分开写入）。"""
    if len(elements) < 2:
        return None
    bodies = []
    for element in elements:
        status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
        if not _succeeded(status):
            return None
        bodies.append(body)
    target = bodies[0]
    tools = ISolidKernelEntityPtrArray()
    for body in bodies[1:]:
        tools.append(body)
    if not _succeeded(SolidUtil.Modify.BooleanUnion(target, tools)):
        return None
    return _element_from_body(dgn_model, target, elements[0], color)


def _morph_slice_elements(dgn_model, frame, resolved, layout):
    """台阶近似：把放样切成若干薄片，逐片用同一组角度采样的小棱柱。"""
    half_width = resolved["flat_width"] / 2.0
    half_thickness = layout["flat_thickness"] / 2.0
    radius = resolved["davit_dia"] / 2.0
    y_rect = layout["y_rect"]
    y_round = layout["y_round"]
    step = (y_round - y_rect) / LOFT_SLICES
    if step <= 0.0:
        return []
    elements = []
    for index in range(LOFT_SLICES):
        t = float(index) / LOFT_SLICES
        y = y_rect + step * index
        points = _section_points(frame, y, half_width, half_thickness, radius, t)
        # 反序（法向 +y，即朝圆管一侧），ThickenSheet 便沿 +y 拉伸。
        reversed_points = DPoint3dArray()
        for point in reversed(list(points)):
            reversed_points.append(point)
        element = _plate_with_holes(
            dgn_model, reversed_points, frame.uor(step), COLOR_LOFT
        )
        if element is None:
            return []
        elements.append(element)
    return elements


# ---------------------------------------------------------------------------
# 吊杆
# ---------------------------------------------------------------------------


def _add_flat_head(builder, frame, resolved, layout):
    """扁头：100 宽 × 120 长 × D/2 厚的矩形板，正中心裁 40×22 长圆孔。

    长圆孔用**一个**刀具体（两条直边 + 两端半圆的闭合轮廓拉伸而成），
    因此长边是真正的直线；不用三个圆柱相并（那样侧面会形成波浪缺口）。
    """
    dgn_model = builder.dgn_model
    half_width = resolved["flat_width"] / 2.0
    thickness = layout["flat_thickness"]
    half_thickness = thickness / 2.0
    z0 = -half_thickness
    extension = 2.0
    y_tip = layout["y_tip"]
    y_rect = layout["y_rect"]

    # 矩形轮廓（逆时针，法向 +z），沿 +z 拉伸成板。
    points = DPoint3dArray()
    for x, y in ((-half_width, y_tip), (half_width, y_tip),
                 (half_width, y_rect), (-half_width, y_rect),
                 (-half_width, y_tip)):
        points.append(frame.point(x, y, z0))

    # 长圆孔刀具体：竖直方向贯穿板厚，孔心在扁头正中心（局部原点）。
    cutter_points = DPoint3dArray()
    for x, y in _obround_profile(SLOT_WIDTH / 2.0, SLOT_LENGTH / 2.0,
                                 SLOT_END_SEGMENTS):
        cutter_points.append(frame.point(x, y, z0 - extension))
    cutter_points.append(cutter_points[0])
    cutter = _plate_with_holes(
        dgn_model, cutter_points, frame.uor(thickness + 2.0 * extension), None
    )

    builder.add(_plate_with_holes(
        dgn_model, points, frame.uor(thickness), COLOR_FLAT,
        cutter_elements=[cutter],
    ))


def _add_loft(builder, frame, resolved, layout):
    """圆管（ØD）与扁头矩形（100 × D/2）之间的放样，长度 1.5 D。

    依次尝试：直纹放样 → SolidUtil.Create.BodyFromLoft → 多段台阶近似。
    台阶近似虽然外表面是分段的，但保证圆管与扁头之间一定连上，不会断开。
    """
    dgn_model = builder.dgn_model
    radius = resolved["davit_dia"] / 2.0
    half_width = resolved["flat_width"] / 2.0
    half_thickness = layout["flat_thickness"] / 2.0
    y_rect = layout["y_rect"]
    y_round = layout["y_round"]

    rectangle = _section_curve(frame, y_rect, half_width, half_thickness, radius, 0.0)
    circle = _section_curve(frame, y_round, half_width, half_thickness, radius, 1.0)

    element, reason = _ruled_sweep_element(dgn_model, rectangle, circle, COLOR_LOFT)
    if element is not None:
        builder.add(element)
        return "ruled"

    element, alternate_reason = _body_from_loft_element(
        dgn_model, [rectangle, circle], COLOR_LOFT
    )
    if element is not None:
        builder.add(element)
        return "loft"

    slices = _morph_slice_elements(dgn_model, frame, resolved, layout)
    if not slices:
        builder.note("放样失败，且台阶近似也没建出来：%s" % reason)
        return None
    united = _union_elements(dgn_model, slices, COLOR_LOFT)
    if united is not None:
        builder.add(united)
    else:
        for slice_element in slices:
            builder.add(slice_element)
    builder.note(
        "直纹放样不可用（%s / %s），已改用 %d 段台阶近似过渡（外表面分段）。"
        % (reason, alternate_reason, len(slices))
    )
    _write_debug_log(
        "直纹放样失败",
        "ruled: %s\nbody_from_loft: %s\n" % (reason, alternate_reason),
    )
    return "stepped"


def _add_round_bar(builder, frame, resolved, layout):
    """实心圆钢：立柱 + R220 弯头 + 水平臂（到放样的圆形断面为止）。"""
    dgn_model = builder.dgn_model
    radius = frame.uor(resolved["davit_dia"] / 2.0)
    y_post = layout["arm_reach"]
    bend_y = layout["bend_center_y"]
    bend_z = layout["bend_center_z"]
    cotter_z = layout["cotter_z"]
    y_round = layout["y_round"]

    # 立柱：从下端到弯头起点，下端掏 Ø5 开口销孔。
    post_hole = (
        frame.point(0.0, y_post - 2.0, cotter_z),
        frame.point(0.0, y_post + 2.0, cotter_z),
        frame.uor(COTTER_HOLE_DIA / 2.0),
    )
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(0.0, y_post, layout["post_bottom"]),
        frame.point(0.0, y_post, bend_z),
        radius, COLOR_DAVIT, [post_hole],
    ))

    # R220 弯头：从竖直（+z）转到水平（-y）。
    vector_x = DVec3d.From(frame.v[0], frame.v[1], 0.0)   # 指向立柱（+y）
    vector_y = DVec3d.From(0.0, 0.0, 1.0)                 # 竖直向上
    bend = _torus_pipe(
        dgn_model, frame.point(0.0, bend_y, bend_z),
        vector_x, vector_y, frame.uor(BEND_RADIUS), radius, pi / 2.0,
    )
    if bend is not None:
        _apply_color(bend, COLOR_DAVIT)
        builder.add(bend)

    # 水平臂：从弯头末端（y = bend_y）到放样的圆形断面（y = y_round）。
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(0.0, bend_y, 0.0),
        frame.point(0.0, y_round, 0.0),
        radius, COLOR_DAVIT,
    ))

    # 开口销。
    half = 14.0
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(0.0, y_post - half, cotter_z),
        frame.point(0.0, y_post + half, cotter_z),
        frame.uor(COTTER_DIA / 2.0), COLOR_PIN,
    ))


def _add_rings(builder, frame, resolved, layout):
    """法兰上的两只吊耳环（RING 16 THK）+ 中间黄铜垫环（BRASS RING 3 THK）。"""
    dgn_model = builder.dgn_model
    y_post = layout["arm_reach"]
    outer_r = frame.uor(layout["ring_outer_r"])
    inner_r = frame.uor(layout["ring_inner_r"])
    upper_z = layout["upper_ring_z"]
    lower_z = layout["lower_ring_z"]

    for base_z in (upper_z - RING_THICKNESS / 2.0, lower_z - RING_THICKNESS / 2.0):
        builder.add(_hollow_cylinder(
            dgn_model,
            frame.point(0.0, y_post, base_z),
            frame.point(0.0, y_post, base_z + RING_THICKNESS),
            outer_r, inner_r, COLOR_RING,
        ))

    # 黄铜垫环紧贴在上吊耳环下方。
    brass_top = upper_z - RING_THICKNESS / 2.0
    builder.add(_hollow_cylinder(
        dgn_model,
        frame.point(0.0, y_post, brass_top - BRASS_THICKNESS),
        frame.point(0.0, y_post, brass_top),
        outer_r, inner_r, COLOR_BRASS,
    ))


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _DavitCellBuilder(object):
    def __init__(self, dgn_model):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, CELL_NAME, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("吊杆子元素创建失败。")
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError("无法将吊杆子元素加入单元。")
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError("无法完成吊杆单元。")
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError("无法将吊杆单元写入活动模型。")
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


def _build_davit_cell(placement_point, options=None):
    """构建吊杆单元但不写入模型，返回 (builder, 统计字典)。"""
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型，再运行吊杆工具。")
    if placement_point is None:
        raise ValueError("请先在模型中点取放置点。")

    resolved = _resolve_options(options)
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    heading = resolved["heading_deg"] + (180.0 if resolved["mirrored"] else 0.0)
    frame = _DavitFrame(_copy_dpoint(placement_point), uor_per_mm, heading)
    layout = _davit_layout(resolved)

    builder = _DavitCellBuilder(dgn_model)
    _add_flat_head(builder, frame, resolved, layout)
    loft_mode = _add_loft(builder, frame, resolved, layout)
    _add_round_bar(builder, frame, resolved, layout)
    if resolved["include_rings"]:
        _add_rings(builder, frame, resolved, layout)
    builder.build()

    result = {
        "child_count": builder.child_count,
        "davit_dia": resolved["davit_dia"],
        "arm_reach": resolved["arm_reach"],
        "flat_width": resolved["flat_width"],
        "flat_length": resolved["flat_length"],
        "flat_thickness": layout["flat_thickness"],
        "loft_length": layout["loft_length"],
        "heading_deg": heading,
        "rings": bool(resolved["include_rings"]),
        "loft": loft_mode,
        "warnings": list(builder.warnings),
    }
    return builder, result


def draw_davit(placement_point, options=None):
    """在给定位置创建一根吊杆，返回统计字典。"""
    builder, result = _build_davit_cell(placement_point, options)
    builder.commit()
    return result


def replace_davit(placement_point, options, previous_handle):
    """重建吊杆：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_davit_cell(placement_point, options)
    new_handle = builder.commit()
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


# ---------------------------------------------------------------------------
# MicroStation 工具面板
# ---------------------------------------------------------------------------


class _MicroStationTk(tk.Tk):
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


class _DavitSettingsDialog(_MicroStationTk):
    """吊杆参数 + 预览 / 确定 / 取消。"""

    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("罐壁人孔吊杆（单独测试）")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)

        self.placement_point = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._pending_regeneration = None

        body = tk.Frame(self, padx=12, pady=10)
        body.grid(row=0, column=0, sticky="nsew")

        tk.Label(
            body,
            text="点取“扁头腰形孔中心（即 M20 螺栓轴线）在扁头中面”的位置。",
            justify="left", fg="#333333", wraplength=400,
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        rows = (
            ("吊杆直径 D：", "davit_dia", "%.1f" % DAVIT_DIA_DEFAULT),
            ("立柱偏距：", "arm_reach", "%.0f" % ARM_REACH_DEFAULT),
            ("上吊耳环 z：", "ring_level", "%.0f" % RING_LEVEL_DEFAULT),
            ("扁头宽：", "flat_width", "%.1f" % FLAT_HEAD_WIDTH),
            ("扁头长：", "flat_length", "%.1f" % FLAT_HEAD_LENGTH),
        )
        self.entries = {}
        for index, (label, key, value) in enumerate(rows, start=1):
            tk.Label(body, text=label).grid(row=index, column=0, pady=(6, 0), sticky="w")
            variable = tk.StringVar(value=value)
            tk.Entry(body, textvariable=variable, width=10).grid(
                row=index, column=1, pady=(6, 0), sticky="w")
            tk.Label(body, text="mm").grid(
                row=index, column=2, pady=(6, 0), sticky="w")
            variable.trace_add("write", self.on_entry_changed)
            self.entries[key] = variable

        tk.Label(body, text="朝向：").grid(row=6, column=0, pady=(6, 0), sticky="w")
        self.heading_var = tk.StringVar(value="0")
        tk.Entry(body, textvariable=self.heading_var, width=10).grid(
            row=6, column=1, pady=(6, 0), sticky="w")
        tk.Label(body, text="°（0° 沿 +X）").grid(
            row=6, column=2, pady=(6, 0), sticky="w")
        self.heading_var.trace_add("write", self.on_entry_changed)

        self.rings_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            body, text="生成吊耳环 RING 16 THK ×2（间距 128，孔 = D+3）",
            variable=self.rings_var, command=self.on_options_changed,
        ).grid(row=7, column=0, columnspan=4, pady=(6, 0), sticky="w")

        self.mirror_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body, text="反向（转到另一侧）", variable=self.mirror_var,
            command=self.on_options_changed,
        ).grid(row=8, column=0, columnspan=4, pady=(2, 0), sticky="w")

        tk.Label(
            body,
            text="扁头厚 = D/2，放样长 = 1.5 D，腰形孔 40 × 22（自动推导）",
            justify="left", fg="#666666", wraplength=400,
        ).grid(row=9, column=0, columnspan=4, pady=(8, 0), sticky="w")

        self.preview_info_label = tk.Label(
            body, text="预览：—", justify="left", fg="#333333", wraplength=400,
        )
        self.preview_info_label.grid(row=10, column=0, columnspan=4, pady=(10, 0),
                                    sticky="w")

        self.status_label = tk.Label(
            body, text="请点取放置点；点取后可改参数，预览会自动重建。",
            justify="left", fg="#1f5f99", wraplength=400,
        )
        self.status_label.grid(row=11, column=0, columnspan=4, pady=(10, 0), sticky="w")

        button_row = tk.Frame(body)
        button_row.grid(row=12, column=0, columnspan=4, pady=(10, 0), sticky="e")
        confirm_button = tk.Button(button_row, text="确定", width=10,
                                   command=self.confirm_tool)
        confirm_button.pack(side="right")
        cancel_button = tk.Button(button_row, text="取消", width=10,
                                  command=self.cancel_tool)
        cancel_button.pack(side="right", padx=(0, 6))

        self.option_widgets = []
        for child in body.winfo_children():
            if isinstance(child, (tk.Checkbutton, tk.Entry)):
                self.option_widgets.append(child)
        self.action_widgets = [confirm_button, cancel_button]

    def current_options(self):
        options = {
            "heading_deg": float(self.heading_var.get()),
            "include_rings": bool(self.rings_var.get()),
            "mirrored": bool(self.mirror_var.get()),
        }
        labels = {
            "davit_dia": "吊杆直径", "arm_reach": "立柱偏距",
            "ring_level": "上吊耳环标高", "flat_width": "扁头宽",
            "flat_length": "扁头长",
        }
        for key, variable in self.entries.items():
            try:
                options[key] = float(variable.get())
            except (TypeError, ValueError):
                raise ValueError("%s必须是数字（mm）。" % labels[key])
        return options

    def set_status(self, message, is_error=False):
        self.status_label.configure(
            text=message, fg="#b42318" if is_error else "#1f5f99"
        )
        self.update_idletasks()

    def set_result(self, result):
        loft_text = {
            "ruled": "直纹放样",
            "loft": "BodyFromLoft 放样",
            "stepped": "台阶近似",
            None: "未生成",
        }.get(result["loft"], str(result["loft"]))
        self.preview_info_label.configure(
            text="预览：吊杆 φ%.1f，立柱偏距 %.0f，扁头 %.0f×%.0f×%.1f，"
                 "放样长 %.1f（%s）；吊耳环：%s；共 %d 个子元素"
            % (result["davit_dia"], result["arm_reach"], result["flat_width"],
               result["flat_length"], result["flat_thickness"],
               result["loft_length"], loft_text,
               "已生成" if result["rings"] else "未生成",
               result["child_count"])
        )

    def _set_busy(self, busy):
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in self.option_widgets + self.action_widgets:
            widget.configure(state=state)
        self.update_idletasks()

    def on_entry_changed(self, *_unused):
        self.on_options_changed()

    def on_options_changed(self):
        if self.placement_point is None:
            return
        self._cancel_pending_regeneration()
        self._pending_regeneration = self.after(
            REGENERATE_DELAY_MS, self._run_pending_regeneration
        )

    def _cancel_pending_regeneration(self):
        pending = self._pending_regeneration
        self._pending_regeneration = None
        if pending is None:
            return
        try:
            self.after_cancel(pending)
        except tk.TclError:
            return

    def _run_pending_regeneration(self):
        self._pending_regeneration = None
        self.regenerate()

    def regenerate(self, placement_point=None):
        self._cancel_pending_regeneration()
        if placement_point is not None:
            self.placement_point = _copy_dpoint(placement_point)
        if self.placement_point is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            self.set_status("参数有误：%s" % error, True)
            return None

        self._set_busy(True)
        self.set_status("正在生成吊杆预览，请稍候……")
        try:
            handle, result, deleted = replace_davit(
                self.placement_point, options, self.preview_handle
            )
        except Exception as error:
            message = "吊杆生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _write_debug_log(message, traceback.format_exc())
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.set_result(result)
        message = (
            "预览已更新：吊杆 φ%.1f，扁头 %.0f×%.0f×%.1f，放样 %.1f，共 %d 个子元素。"
            "%s改参数会自动重建；点【确定】保留，点【取消】放弃。"
            % (result["davit_dia"], result["flat_width"], result["flat_length"],
               result["flat_thickness"], result["loft_length"],
               result["child_count"],
               "已替换上一版预览。" if deleted else "")
        )
        if result["warnings"]:
            message += "注意：%s" % "；".join(result["warnings"])
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        PyCommandState.StartDefaultCommand()


class DavitPlacementTool(DgnPrimitiveTool):
    """点取放置点并放置吊杆的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString("DavitPlacementTool")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            "请点取吊杆扁头腰形孔中心的位置；点取后可改参数，预览会自动重建，"
            "点【确定】保留，点【取消】或右键放弃。"
        )

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            settings.after_idle(settings.cancel_tool)
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
        settings = (
            tool_settings if tool_settings is not None else _DavitSettingsDialog()
        )
        tool = DavitPlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    DavitPlacementTool.InstallNewInstance(0)


def _self_test():
    """纯 Python 自检：只验算布局与参数校验，不依赖 Bentley。"""
    failures = []

    def check(name, condition, detail=""):
        print("[%s] %s%s" % ("PASS" if condition else "FAIL", name,
                             (" " + str(detail)) if detail else ""))
        if not condition:
            failures.append(name)

    def close(a, b, tolerance=1.0e-6):
        return abs(a - b) <= tolerance

    # 默认（D=45，即 24" + ASA 150 lbs）
    resolved = _resolve_options()
    layout = _davit_layout(resolved)
    check("默认吊杆 φ45", close(resolved["davit_dia"], 45.0))
    check("扁头厚 = D/2 = 22.5", close(layout["flat_thickness"], 22.5),
          layout["flat_thickness"])
    check("放样长 = 1.5D = 67.5", close(layout["loft_length"], 67.5),
          layout["loft_length"])
    check("扁头外端 y = -60（120 长居中）", close(layout["y_tip"], -60.0))
    check("扁头/矩形断面 y = 60（长 120）",
          close(layout["y_rect"] - layout["y_tip"], 120.0), layout["y_rect"])
    check("圆形断面 y = 127.5（60 + 67.5）", close(layout["y_round"], 127.5))
    check("R220 弯头起点 y = 280 / z = -220",
          close(layout["bend_end_y"], 280.0) and close(layout["bend_center_z"], -220.0))
    check("直臂长 = 280 - 127.5 = 152.5 > %.0f" % MIN_ARM_SEGMENT,
          layout["bend_end_y"] - layout["y_round"] >= MIN_ARM_SEGMENT)
    check("上吊耳环 z = -280", close(layout["upper_ring_z"], -280.0))
    check("下吊耳环销孔中心距 144",
          close(layout["upper_ring_z"] - layout["lower_ring_z"],
                RING_GAP + RING_THICKNESS))
    check("立柱下端 z = -457（下环底 -25）", close(layout["post_bottom"], -457.0),
          layout["post_bottom"])
    check("开口销孔 z = -437（立柱下端 +20）", close(layout["cotter_z"], -437.0))
    check("吊耳环销孔 = D+3 = 48", close(layout["ring_inner_r"] * 2.0, 48.0))

    # 大规格
    big = _resolve_options({"davit_dia": 65.0})
    big_layout = _davit_layout(big)
    check("D=65 → 扁头厚 32.5 / 放样 97.5",
          close(big_layout["flat_thickness"], 32.5)
          and close(big_layout["loft_length"], 97.5))

    # 扁头与长圆孔：孔心在扁头正中心，长圆孔长边是直线
    half_w = FLAT_HEAD_WIDTH / 2.0
    half_t = 45.0 * FLAT_HEAD_HEIGHT_FACTOR / 2.0
    check("扁头关于原点前后对称（孔在正中心）",
          close(layout["y_tip"] + layout["y_rect"], 0.0)
          and close(layout["y_rect"] - layout["y_tip"], 120.0),
          (layout["y_tip"], layout["y_rect"]))
    per_side = max(1, LOFT_SIDES // 4)
    rect = _rectangle_perimeter(half_w, half_t, per_side)
    corners = set(rect[i * per_side] for i in range(4))
    check("放样矩形断面含 4 个精确角点（角上不留缺口）",
          (half_w, -half_t) in corners and (half_w, half_t) in corners
          and (-half_w, half_t) in corners and (-half_w, -half_t) in corners,
          sorted(corners))
    check("放样矩形断面各点都在矩形边界上",
          all(close(max(abs(x) / half_w, abs(z) / half_t), 1.0)
              for x, z in rect))
    circle = _section_offsets(half_w, half_t, 22.5, 1.0)
    check("放样圆断面 t=1 各点半径 = 22.5",
          all(close(hypot(x, z), 22.5) for x, z in circle))
    check("放样两端断面点数一致 = %d" % LOFT_SIDES,
          len(rect) == len(circle) == LOFT_SIDES)

    profile = _obround_profile(SLOT_WIDTH / 2.0, SLOT_LENGTH / 2.0,
                               SLOT_END_SEGMENTS)
    xs = [p[0] for p in profile]
    ys = [p[1] for p in profile]
    check("长圆孔 40 × 22（x=±11、y=±20）",
          close(min(xs), -11.0) and close(max(xs), 11.0)
          and close(min(ys), -20.0) and close(max(ys), 20.0),
          (min(xs), max(xs), min(ys), max(ys)))
    straight_side = [p for p in profile if close(abs(p[0]), 11.0)]
    check("长圆孔两条长边为直线（x 恒 ±11，y = ±9）",
          len(straight_side) == 4
          and all(close(abs(p[1]), 9.0) for p in straight_side), straight_side)
    check("长圆孔两端为半圆（最远点 y = ±20、x = 0）",
          any(close(p[0], 0.0) and close(p[1], 20.0) for p in profile)
          and any(close(p[0], 0.0) and close(p[1], -20.0) for p in profile))

    # 非法参数
    for options, label in (
        ({"davit_dia": 0}, "直径 0"),
        ({"arm_reach": 300}, "偏距小于 2R"),
        ({"arm_reach": 420}, "偏距放不下放样与扁头"),
        ({"flat_width": 20}, "扁头宽小于孔宽"),
        ({"flat_length": 50}, "扁头长过短"),
        ({"ring_level": -100}, "吊耳环高于弯头起点"),
        ({"heading_deg": "abc"}, "朝向非数字"),
    ):
        try:
            _resolve_options(options)
            check("拒绝非法参数：%s" % label, False)
        except ValueError:
            check("拒绝非法参数：%s" % label, True)

    print("")
    if failures:
        print("FAILED CHECKS (%d): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("ALL LAYOUT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    if _SELF_TEST:
        sys.exit(_self_test())
    PyMain()
