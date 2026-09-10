# -*- coding: utf-8 -*-
"""在 MicroStation / OpenPlant Modeler 的活动 3D 模型中交互放置安保围栏大门。

尺寸依据 GS-M16《Specification for 1.83m Security Fence》"Double and Single
Gates" 一节：门扇用 φ42.8 × 2 钢管制作、四角斜接，斜撑用 φ21.4 钢管，镀锌
菱形网 64 × 2.5 覆盖门框；门扇顶部防攀悬臂为竖直段（450 mm），门柱与围栏
一致为 45° 斜挑；门扇经 3 个简化活页（竖直销轴 + 上下连接板）与门柱连接。
门柱与围栏的转角 / 拉紧柱同规格（φ100 × 2 mm、长 2.6 m、400 × 400 × 600
B 级混凝土基础），可用面板开关选择是否建模。单扇门宽 1.2 m、双扇门宽
4.270 m（均为门洞净宽，可在面板中修改）。

工作方式与 `安保围栏/security_fence_body.py` 一致：在面板里选门型与朝向，
在模型中点取门洞中心的地面点后立即生成一版**预览**；改动选项会自动重建
（模型里始终只有一版预览），点【确定】就地保留，点【取消】放弃。整樘大门
写成一个普通单元（Normal Cell），因此可以整体选中、移动、复制或删除。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import print_function

from math import cos, hypot, radians, sin
import tkinter as tk

import tkinter
import win32gui

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# --- 门扇尺寸（mm）----------------------------------------------------------
# GS-M16 "Double and Single Gates"：门框 φ42.8 × 2 钢管、四角斜接；斜撑
# φ21.4 钢管；镀锌菱形网覆盖门框；防攀悬臂与围栏一致。
GATE_FRAME_OD = 42.8
GATE_FRAME_WALL = 2.0
GATE_BRACE_OD = 21.4
GATE_BRACE_WALL = 2.0
# 斜撑端头沿管轴缩进门框的深度：避免平口端面从门框斜接面的内孔处穿出。
BRACE_END_RECESS = GATE_FRAME_OD / 2.0

GATE_HEIGHT = 1800.0          # 门扇顶标高，与围栏网片顶（及悬臂起点）齐平
GATE_BOTTOM_CLEARANCE = 50.0  # 门扇下缘离地间隙，便于开启
GATE_WIDTH_SINGLE = 1200.0    # 单扇门门洞净宽
GATE_WIDTH_DOUBLE = 4270.0    # 双扇门门洞净宽
MIN_OPENING_WIDTH = 600.0     # 门洞净宽下限（再小无法做成斜接门框）
MAX_OPENING_WIDTH = 20000.0
LEAF_POST_CLEARANCE = 20.0    # 门扇与门柱内表面之间的安装间隙
LEAF_MEETING_GAP = 20.0       # 双扇门两扇在中缝处的间隙

# GS-M16 "Corner - Gate - Straining Posts"：门柱与转角柱 / 拉紧柱同规格。
GATE_POST_OD = 100.0
GATE_POST_LENGTH = 2600.0
GATE_POST_WALL = 4.0
FOUNDATION_POST = (400.0, 400.0, 600.0)

# 防攀悬臂与刺钢丝：尺寸与安保围栏主体完全一致。
OVERHANG_LENGTH = 450.0
OVERHANG_ANGLE_DEG = 45.0
ELBOW_CENTERLINE_RADIUS = 100.0
BARBED_WIRE_DIAMETER = 2.5
BARBED_WIRE_COUNT = 3
BARB_DIAMETER = 1.2
BARB_LENGTH = 28.0
BARB_SPACING = 500.0

# 门扇顶部防攀悬臂为竖直段（0°），门柱仍与围栏一致为 45° 斜挑。
LEAF_OVERHANG_ANGLE_DEG = 0.0

# 活页（合页）：简化成"竖直销轴 + 上下两块连接板"，尺寸为经验值，无规范依据。
HINGE_PIN_DIAMETER = 16.0       # 销轴直径
HINGE_PIN_LENGTH = 90.0         # 销轴长度（竖直）
HINGE_PLATE_WIDTH = 40.0        # 连接板宽度（沿门扇法向 y）
HINGE_PLATE_THICKNESS = 6.0     # 连接板厚度（竖直）
HINGE_PLATE_OFFSET = 25.0       # 上下两块连接板到销轴中心的距离
HINGE_HEIGHT_FRACTIONS = (0.25, 0.5, 0.75)  # 每扇门 3 个，沿门扇高度均布

MESH_OPENING = 64.0
MESH_WIRE_DIAMETER = 2.5

# 斜接切刀：贴在 45° 切平面上的方块，尺寸只需盖住管径。
MITRE_CUTTER_SIZE = 300.0
MITRE_CUTTER_DEPTH = 300.0
# 门框构件两端沿轴线外伸量：让 45° 切平面切出完整端面（外伸部分会被切掉）。
MITRE_END_EXTENSION = GATE_FRAME_OD

# MicroStation 颜色表编号及线宽（0-31），与安保围栏主体一致。
COLOR_FRAME = 7
COLOR_MESH = 9
COLOR_BRACE = 4
COLOR_BARBED = 2
COLOR_FOUNDATION = 3
COLOR_HINGE = 1

CELL_NAME = "SECURITY_GATE"

# 两道刺钢丝之间至少要有的长度，用于判断是否需要拉线（门柱悬臂彼此重合时不拉线）。
MIN_STRAND_LENGTH = 1.0

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150

DEFAULT_OPTIONS = {
    "gate_type": "single",       # single / double
    "opening_width": None,       # None 表示按门型取默认门洞净宽
    "heading_deg": 0.0,          # 门洞方向：0° 沿模型 +X，逆时针为正
    "mirrored": False,           # 反向：悬臂改朝另一侧（等价于转角 +180°）
    "include_posts": True,       # 生成 φ100 门柱
    "include_foundation": True,  # 门柱混凝土基础
    "include_overhang": True,    # 防攀悬臂与刺钢丝
}


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _line_weight(diameter_mm):
    """将真实直径映射为便于观察的 MicroStation 线宽。"""
    return max(1, min(31, int(round(diameter_mm / 2.0))))


def _resolve_options(options=None):
    """合并默认值并校验选项，返回一份完整的参数字典。"""
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        for key in options:
            if key not in resolved:
                raise ValueError("未知选项：%s" % key)
            resolved[key] = options[key]

    gate_type = resolved["gate_type"]
    if gate_type not in ("single", "double"):
        raise ValueError("门型必须为 single（单扇）或 double（双扇）。")

    if resolved["opening_width"] is None:
        resolved["opening_width"] = (
            GATE_WIDTH_SINGLE if gate_type == "single" else GATE_WIDTH_DOUBLE
        )
    opening_width = float(resolved["opening_width"])
    if not (MIN_OPENING_WIDTH <= opening_width <= MAX_OPENING_WIDTH):
        raise ValueError(
            "门洞净宽应在 %.0f–%.0f mm 之间。" % (MIN_OPENING_WIDTH, MAX_OPENING_WIDTH)
        )
    resolved["opening_width"] = opening_width

    try:
        heading = float(resolved["heading_deg"])
    except (TypeError, ValueError):
        raise ValueError("转角必须是数字（度）。")
    if heading != heading or heading in (float("inf"), float("-inf")):
        raise ValueError("转角必须是有限数字。")
    resolved["heading_deg"] = heading
    resolved["mirrored"] = bool(resolved["mirrored"])
    resolved["include_posts"] = bool(resolved["include_posts"])
    resolved["include_foundation"] = bool(resolved["include_foundation"])
    resolved["include_overhang"] = bool(resolved["include_overhang"])
    return resolved


class _GateFrame(object):
    """大门的局部坐标系：x 沿门洞宽度、y 沿防攀悬臂一侧、z 竖直向上。

    原点取用户点取的门洞中心地面点；0° 时 +x 沿模型 +X，悬臂朝 +Y 侧。
    所有换算都按 mm 输入、UOR 输出，不要求主单位是 mm。
    """

    def __init__(self, origin, uor_per_mm, heading_deg):
        angle = radians(heading_deg)
        self.origin = origin
        self.uor_per_mm = uor_per_mm
        self.u = (cos(angle), sin(angle))
        self.v = (-sin(angle), cos(angle))

    def point(self, x_mm, y_mm, z_mm):
        """本地 (x, y, z) 毫米坐标 → 模型 UOR 点。"""
        u = self.u
        v = self.v
        scale = self.uor_per_mm
        return DPoint3d.From(
            self.origin.x + (u[0] * x_mm + v[0] * y_mm) * scale,
            self.origin.y + (u[1] * x_mm + v[1] * y_mm) * scale,
            self.origin.z + z_mm * scale,
        )

    def plane_normal(self, nx, nz):
        """本地 x-z 平面内（即门扇平面内）的方向 → 模型空间单位向量。

        斜接切平面垂直于门扇平面，因此切平面法向在该平面内没有 y 分量。
        """
        u = self.u
        return (u[0] * nx, u[1] * nx, nz)


class _GateCellBuilder(object):
    """收集大门子元素，并在全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        # Bentley 的此创建函数返回 None；后续 AddChildElement/AddChildComplete
        # 的状态值用于判断单元构造是否成功。
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, CELL_NAME, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("大门子元素创建失败。")
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法将大门子元素加入单元。")
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        """完成单元构造（仍在内存中，尚未写入模型）。"""
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法完成大门单元。")
        return self.child_count

    def commit(self):
        """把已构建好的单元写入活动模型，返回单元句柄。"""
        if self.cell.AddToModel() != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法将大门单元写入活动模型。")
        return self.cell


def _delete_preview(handle):
    """删除上一版预览单元；句柄失效或删除失败都不影响后续生成。"""
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def _create_line_element(dgn_model, start, end, color, diameter_mm):
    """创建一个尚未写入模型的 3D 线元素。"""
    eeh = EditElementHandle()
    segment = DSegment3d(start, end)
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


def _create_solid_cylinder(dgn_model, start_point, end_point, radius, color):
    """创建一个实心圆柱并设置颜色（用于活页销轴）。"""
    eeh = _create_cylinder_element(dgn_model, start_point, end_point, radius)
    if eeh is None:
        return None
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(eeh)
    return eeh


def _create_torus_pipe_element(
    dgn_model, center, vector_x, vector_y, major_radius, minor_radius, sweep_angle
):
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


def _subtract_bodies(target_body, tools):
    """用 tools（已转成实体的列表）逐一减去；返回是否全部成功。"""
    ok = True
    for tool in tools:
        cutting_tools = ISolidKernelEntityPtrArray()
        cutting_tools.append(tool)
        if SolidUtil.Modify.BooleanSubtract(target_body, cutting_tools) != BentleyStatus.eSUCCESS:
            ok = False
    return ok


def _create_cut_box(dgn_model, plane_point, normal, size_mm, thickness_mm, uor_per_mm):
    """创建一把斜接切刀：背面贴在切平面上、沿法向向外延伸的方块。

    切平面法向 normal 必须是从构件内部指向外部的方向（即被切掉的一侧）。
    方块底面四点的绕向按法向取右手方向，ThickenSheet 便沿 +normal 拉伸，
    于是方块占据切平面外侧的半个空间，把管端切成 45°。
    """
    magnitude = hypot(hypot(normal[0], normal[1]), normal[2])
    if magnitude <= 1.0e-12:
        return None
    n = (normal[0] / magnitude, normal[1] / magnitude, normal[2] / magnitude)

    # 取一组正交基，使 u × v = n，保证轮廓绕向与法向一致。
    reference = (1.0, 0.0, 0.0) if abs(n[2]) > 0.9 else (0.0, 0.0, 1.0)
    u = (
        reference[1] * n[2] - reference[2] * n[1],
        reference[2] * n[0] - reference[0] * n[2],
        reference[0] * n[1] - reference[1] * n[0],
    )
    u_length = hypot(hypot(u[0], u[1]), u[2])
    if u_length <= 1.0e-12:
        return None
    u = (u[0] / u_length, u[1] / u_length, u[2] / u_length)
    v = (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )

    half = size_mm * uor_per_mm / 2.0
    points = DPoint3dArray()
    for su, sv in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0)):
        points.append(
            DPoint3d.From(
                plane_point.x + (u[0] * su + v[0] * sv) * half,
                plane_point.y + (u[1] * su + v[1] * sv) * half,
                plane_point.z + (u[2] * su + v[2] * sv) * half,
            )
        )
    return _create_prism_from_corners(
        dgn_model, points, thickness_mm * uor_per_mm, None
    )


def _create_prism_from_corners(dgn_model, points, thickness_uor, color):
    """按闭合轮廓（底面四点 + 回环点）沿轮廓法向拉伸出一个实体块。

    与安保围栏的混凝土块做法一致：轮廓用活动模型引用创建、不写入模型，
    拉伸后再转成元素。color 为 None 时只作为布尔运算的切刀使用。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, points, model_ref.Is3d(), model_ref
    )
    if status != BentleyStatus.eSUCCESS:
        return None

    body_status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if body_status != BentleyStatus.eSUCCESS:
        return None
    if SolidUtil.Modify.ThickenSheet(body, thickness_uor, 0.0) != BentleyStatus.eSUCCESS:
        return None

    finished = EditElementHandle()
    if SolidUtil.Convert.BodyToElement(finished, body, profile, dgn_model) != BentleyStatus.eSUCCESS:
        return None
    if color is not None:
        properties = ElementPropertiesSetter()
        properties.SetColor(color)
        properties.Apply(finished)
    return finished


def _create_hollow_tube(
    dgn_model,
    start,
    end,
    outside_diameter_mm,
    wall_mm,
    uor_per_mm,
    color,
    cutters=(),
    warnings=None,
):
    """创建尚未写入模型的空心钢管（UOR 端点）。

    cutters 是可选的斜接切刀元素，用来把管端切成 45°；切刀创建或布尔运算
    失败时该端退化为平口，并在 warnings 里留一条说明，不中断整樘门的生成。
    """
    if wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("钢管外径必须大于两倍壁厚。")

    dx = end.x - start.x
    dy = end.y - start.y
    dz = end.z - start.z
    length = hypot(hypot(dx, dy), dz)
    if length <= 1.0e-6:
        raise ValueError("钢管长度必须大于零。")

    outer = _create_cylinder_element(
        dgn_model, start, end, outside_diameter_mm * uor_per_mm / 2.0
    )
    if outer is None:
        return None
    outer_status, outer_body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if outer_status != BentleyStatus.eSUCCESS:
        return None

    cut_tools = []
    for cutter in cutters:
        if cutter is None:
            if warnings is not None:
                warnings.append("斜接切刀创建失败，该端按平口处理。")
            continue
        cut_status, cut_body = SolidUtil.Convert.ElementToBody(cutter, True, True, False)
        if cut_status != BentleyStatus.eSUCCESS:
            if warnings is not None:
                warnings.append("斜接切刀转换失败，该端按平口处理。")
            continue
        cut_tools.append(cut_body)
    if cut_tools and not _subtract_bodies(outer_body, cut_tools):
        if warnings is not None:
            warnings.append("45° 斜接布尔运算失败，该端按平口处理。")

    # 内圆柱两端各外伸 2 mm，避免共面端面导致布尔减法失败；外伸出斜接面
    # 也无妨，内圆柱只作为切刀使用。
    extension = 2.0 * uor_per_mm / length
    inner_start = DPoint3d.From(start.x - dx * extension, start.y - dy * extension,
                                start.z - dz * extension)
    inner_end = DPoint3d.From(end.x + dx * extension, end.y + dy * extension,
                              end.z + dz * extension)
    inner = _create_cylinder_element(
        dgn_model,
        inner_start,
        inner_end,
        (outside_diameter_mm / 2.0 - wall_mm) * uor_per_mm,
    )
    if inner is None:
        return None
    inner_status, inner_body = SolidUtil.Convert.ElementToBody(inner, True, True, False)
    if inner_status != BentleyStatus.eSUCCESS:
        return None
    if not _subtract_bodies(outer_body, [inner_body]):
        return None

    finished = EditElementHandle()
    if SolidUtil.Convert.BodyToElement(finished, outer_body, outer, dgn_model) != BentleyStatus.eSUCCESS:
        return None
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(finished)
    return finished


def _elbow_inner_frame(vector_x, vector_y, radius_mm):
    """返回内弧的向量基和两端额外扫掠的角度（弧度）。

    外弧的向量基是 (vx, vy)，所在平面的法向为 vx × vy。把这一组基绕该法向
    旋转 -e（e = 2mm / 中心线半径），即得到同一平面内、起点和终点各向外
    延伸 e 的内弧向量基：

        vx' = vx·cos e - vy·sin e
        vy' = vy·cos e + vx·sin e

    这样内弧永远与外弧共面，与门洞走向 / 悬臂朝向无关。
    """
    extension = 2.0 / radius_mm
    cos_extension = cos(extension)
    sin_extension = sin(extension)
    inner_x = tuple(
        vector_x[i] * cos_extension - vector_y[i] * sin_extension for i in range(3)
    )
    inner_y = tuple(
        vector_y[i] * cos_extension + vector_x[i] * sin_extension for i in range(3)
    )
    return inner_x, inner_y, extension


def _create_hollow_elbow(
    dgn_model,
    center,
    vector_x,
    vector_y,
    major_radius_uor,
    outside_diameter_mm,
    wall_mm,
    uor_per_mm,
    color,
    sweep_radians,
):
    """创建由竖直方向向悬臂侧平滑过渡的空心实体弯头。"""
    if wall_mm <= 0.0 or outside_diameter_mm <= 2.0 * wall_mm:
        raise ValueError("弯头外径必须大于两倍壁厚。")

    outer = _create_torus_pipe_element(
        dgn_model,
        center,
        DVec3d.From(vector_x[0], vector_x[1], vector_x[2]),
        DVec3d.From(vector_y[0], vector_y[1], vector_y[2]),
        major_radius_uor,
        outside_diameter_mm * uor_per_mm / 2.0,
        sweep_radians,
    )
    if outer is None:
        return None
    outer_status, outer_body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if outer_status != BentleyStatus.eSUCCESS:
        return None

    inner_x, inner_y, end_extension_angle = _elbow_inner_frame(
        vector_x, vector_y, ELBOW_CENTERLINE_RADIUS
    )
    inner = _create_torus_pipe_element(
        dgn_model,
        center,
        DVec3d.From(inner_x[0], inner_x[1], inner_x[2]),
        DVec3d.From(inner_y[0], inner_y[1], inner_y[2]),
        major_radius_uor,
        (outside_diameter_mm / 2.0 - wall_mm) * uor_per_mm,
        sweep_radians + 2.0 * end_extension_angle,
    )
    if inner is None:
        return None
    inner_status, inner_body = SolidUtil.Convert.ElementToBody(inner, True, True, False)
    if inner_status != BentleyStatus.eSUCCESS:
        return None
    if not _subtract_bodies(outer_body, [inner_body]):
        return None

    finished = EditElementHandle()
    if SolidUtil.Convert.BodyToElement(finished, outer_body, outer, dgn_model) != BentleyStatus.eSUCCESS:
        return None
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(finished)
    return finished


def _clipped_diagonal_segments(width, height, slope):
    """返回裁剪到矩形内的 45 度菱形网线段端点（X、Z）。"""
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
            if not any(
                hypot(point[0] - item[0], point[1] - item[1]) < 1.0e-5 for item in unique
            ):
                unique.append(point)
        if len(unique) >= 2:
            unique.sort()
            yield unique[0], unique[-1]
        intercept += MESH_OPENING


def _gate_layout(gate_type, opening_width):
    """按门型计算门柱位置、门扇数量与每扇宽度（原点为门洞中心）。"""
    post_offset = opening_width / 2.0 + GATE_POST_OD / 2.0
    if gate_type == "single":
        leaf_width = opening_width - 2.0 * LEAF_POST_CLEARANCE
        leaf_centers = (0.0,)
    else:
        leaf_width = (opening_width - 2.0 * LEAF_POST_CLEARANCE - LEAF_MEETING_GAP) / 2.0
        leaf_centers = (
            -(LEAF_MEETING_GAP + leaf_width) / 2.0,
            (LEAF_MEETING_GAP + leaf_width) / 2.0,
        )
    if leaf_width <= 4.0 * GATE_FRAME_OD:
        raise ValueError("门洞净宽太小，无法生成斜接门框。")
    return {
        "post_offset": post_offset,
        "leaf_width": leaf_width,
        "leaf_centers": leaf_centers,
    }


def _add_mitred_member(builder, frame, start_xz, end_xz, other_start, other_end):
    """加入一根两端 45° 斜接的空心门框构件（门扇平面内）。

    start_xz / end_xz 是构件中心线端点的本地 (x, z)；other_start / other_end
    是该端另一根构件**朝向自身管身**的方向。

    斜接面过角落的中心线交点，外法向指向"另一根构件"一侧（即切掉会与对方重叠
    的那半），两根构件的法向相反：

        外法向 n = 另一根构件朝向管身的方向 − 本构件朝向管身的方向

    例如左下角：下横杆朝向管身是 +x、左立柱朝向管身是 +z，于是下横杆
    n = (0,1)-(1,0) = (-1,1)/√2，左立柱 n = (1,0)-(0,1) = (1,-1)/√2，两者
    相反。管身两端各沿轴线外伸 MITRE_END_EXTENSION 再切，切出的 45° 端面是
    完整椭圆，两根构件在角点处完整拼合、外角不留缺口。
    """
    dgn_model = builder.dgn_model
    uor_per_mm = frame.uor_per_mm
    dx = end_xz[0] - start_xz[0]
    dz = end_xz[1] - start_xz[1]
    span = hypot(dx, dz)
    if span <= 1.0e-9:
        raise ValueError("门框构件长度必须大于零。")
    ax = dx / span
    az = dz / span

    cutters = []
    for corner, other, own in (
        (start_xz, other_start, (ax, az)),
        (end_xz, other_end, (-ax, -az)),
    ):
        nx = other[0] - own[0]
        nz = other[1] - own[1]
        normal_length = hypot(nx, nz)
        if normal_length <= 1.0e-9:
            cutters.append(None)
            continue
        cutters.append(
            _create_cut_box(
                dgn_model,
                frame.point(corner[0], 0.0, corner[1]),
                frame.plane_normal(nx / normal_length, nz / normal_length),
                MITRE_CUTTER_SIZE,
                MITRE_CUTTER_DEPTH,
                uor_per_mm,
            )
        )

    # 管身两端各沿轴线外伸，让切平面切出完整端面；外伸部分会被切刀全部切掉，
    # 最终端面仍落在过角点的 45° 斜接面上。
    tube_start = (start_xz[0] - ax * MITRE_END_EXTENSION,
                  start_xz[1] - az * MITRE_END_EXTENSION)
    tube_end = (end_xz[0] + ax * MITRE_END_EXTENSION,
                end_xz[1] + az * MITRE_END_EXTENSION)
    builder.add(
        _create_hollow_tube(
            dgn_model,
            frame.point(tube_start[0], 0.0, tube_start[1]),
            frame.point(tube_end[0], 0.0, tube_end[1]),
            GATE_FRAME_OD,
            GATE_FRAME_WALL,
            uor_per_mm,
            COLOR_FRAME,
            cutters=cutters,
            warnings=builder.warnings,
        )
    )


def _add_overhang(builder, frame, x_start, x_end, outside_diameter_mm, wall_mm, color,
                  angle_deg=OVERHANG_ANGLE_DEG):
    """在两根立柱之间加入 450 mm 防攀悬臂，并沿悬臂直段加 3 道刺钢丝。

    angle_deg 为悬臂相对竖直方向的倾角：45° 是围栏主体的斜挑，0° 则是垂直
    向上的门扇悬臂（无弯头，直段直接向上 450 mm）。刺钢丝的 1/3、2/3、3/3
    分档和每 500 mm 一对 V 形刺，都与安保围栏主体一致。x_start 与 x_end 重合
    时只生成悬臂、不拉刺丝（门柱悬臂不跨门洞，跨门洞的刺丝在门扇上）。
    """
    dgn_model = builder.dgn_model
    uor_per_mm = frame.uor_per_mm
    angle = radians(angle_deg)
    elbow_length = ELBOW_CENTERLINE_RADIUS * angle
    straight_length = OVERHANG_LENGTH - elbow_length
    if straight_length <= 0.0:
        raise ValueError("OVERHANG_LENGTH 必须大于弯头中心线弧长。")

    vector_x = (-frame.v[0], -frame.v[1], 0.0)
    vector_y = (0.0, 0.0, 1.0)
    elbow_end_offset = ELBOW_CENTERLINE_RADIUS * (1.0 - cos(angle))
    elbow_end_z = GATE_HEIGHT + ELBOW_CENTERLINE_RADIUS * sin(angle)
    span = x_end - x_start
    # 单点悬臂（门柱）只生成一组；x_start 与 x_end 不同时才是门扇两端各一组。
    arm_positions = (x_start,) if span <= MIN_STRAND_LENGTH else (x_start, x_end)
    for x in arm_positions:
        if elbow_length > 1.0e-9:
            builder.add(
                _create_hollow_elbow(
                    dgn_model,
                    frame.point(x, ELBOW_CENTERLINE_RADIUS, GATE_HEIGHT),
                    vector_x,
                    vector_y,
                    ELBOW_CENTERLINE_RADIUS * uor_per_mm,
                    outside_diameter_mm,
                    wall_mm,
                    uor_per_mm,
                    color,
                    angle,
                )
            )
        builder.add(
            _create_hollow_tube(
                dgn_model,
                frame.point(x, elbow_end_offset, elbow_end_z),
                frame.point(
                    x,
                    elbow_end_offset + straight_length * sin(angle),
                    elbow_end_z + straight_length * cos(angle),
                ),
                outside_diameter_mm,
                wall_mm,
                uor_per_mm,
                color,
            )
        )

    if span <= MIN_STRAND_LENGTH:
        # 门柱悬臂不跨门洞，刺钢丝在门扇上。
        return

    for row in range(1, BARBED_WIRE_COUNT + 1):
        fraction = float(row) / BARBED_WIRE_COUNT
        offset = elbow_end_offset + straight_length * fraction * sin(angle)
        z = elbow_end_z + straight_length * fraction * cos(angle)
        builder.add(
            _create_line_element(
                dgn_model,
                frame.point(x_start, offset, z),
                frame.point(x_end, offset, z),
                COLOR_BARBED,
                BARBED_WIRE_DIAMETER,
            )
        )

        position = BARB_SPACING / 2.0
        while position < span:
            anchor_x = x_start + position
            for direction in (-1.0, 1.0):
                builder.add(
                    _create_line_element(
                        dgn_model,
                        frame.point(anchor_x, offset - BARB_LENGTH / 2.0, z),
                        frame.point(
                            anchor_x,
                            offset + BARB_LENGTH / 2.0,
                            z + direction * BARB_LENGTH / 3.0,
                        ),
                        COLOR_BARBED,
                        BARB_DIAMETER,
                    )
                )
            position += BARB_SPACING


def _add_hinge(builder, frame, hinge_x, post_x, hinge_side, hinge_z):
    """加入一个简化活页：竖直销轴 + 上下两块连接板。

    销轴位于门扇外缘与门柱内表面之间的缝隙中点；两块连接板沿 x 方向从门扇
    立柱中心线跨到门柱中心线（因此立柱不建模时，连接板仍伸到预埋柱位置）。
    尺寸为经验值，见 HINGE_* 常量。
    """
    dgn_model = builder.dgn_model
    uor_per_mm = frame.uor_per_mm
    half_width = HINGE_PLATE_WIDTH / 2.0
    leaf_edge = hinge_x + hinge_side * GATE_FRAME_OD / 2.0
    post_face = post_x - hinge_side * GATE_POST_OD / 2.0
    axis_x = (leaf_edge + post_face) / 2.0

    builder.add(
        _create_solid_cylinder(
            dgn_model,
            frame.point(axis_x, 0.0, hinge_z - HINGE_PIN_LENGTH / 2.0),
            frame.point(axis_x, 0.0, hinge_z + HINGE_PIN_LENGTH / 2.0),
            HINGE_PIN_DIAMETER / 2.0 * uor_per_mm,
            COLOR_HINGE,
        )
    )

    # 连接板轮廓按逆时针排列（法向 +z），ThickenSheet 便沿 +z 拉伸出厚度。
    if post_x >= hinge_x:
        corners = ((hinge_x, -half_width), (post_x, -half_width),
                   (post_x, half_width), (hinge_x, half_width))
    else:
        corners = ((post_x, -half_width), (hinge_x, -half_width),
                   (hinge_x, half_width), (post_x, half_width))
    for plate_z in (hinge_z + HINGE_PLATE_OFFSET, hinge_z - HINGE_PLATE_OFFSET):
        points = DPoint3dArray()
        for px, py in corners:
            points.append(
                frame.point(px, py, plate_z - HINGE_PLATE_THICKNESS / 2.0)
            )
        builder.add(
            _create_prism_from_corners(
                dgn_model, points, HINGE_PLATE_THICKNESS * uor_per_mm, COLOR_HINGE
            )
        )


def _add_gate_post(builder, frame, x_mm, include_foundation, include_overhang):
    """加入一根 φ100 门柱、可选混凝土基础与防攀悬臂。"""
    dgn_model = builder.dgn_model
    uor_per_mm = frame.uor_per_mm
    embedment = GATE_POST_LENGTH - GATE_HEIGHT
    if embedment <= 0.0:
        raise ValueError("门柱管长必须大于门扇高度。")

    builder.add(
        _create_hollow_tube(
            dgn_model,
            frame.point(x_mm, 0.0, -embedment),
            frame.point(x_mm, 0.0, GATE_HEIGHT),
            GATE_POST_OD,
            GATE_POST_WALL,
            uor_per_mm,
            COLOR_FRAME,
        )
    )

    if include_foundation:
        width_mm, breadth_mm, depth_mm = FOUNDATION_POST
        half_width = width_mm / 2.0
        half_breadth = breadth_mm / 2.0
        points = DPoint3dArray()
        for x_offset, y_offset in (
            (-half_width, -half_breadth),
            (half_width, -half_breadth),
            (half_width, half_breadth),
            (-half_width, half_breadth),
            (-half_width, -half_breadth),
        ):
            points.append(frame.point(x_mm + x_offset, y_offset, -depth_mm))
        builder.add(
            _create_prism_from_corners(
                dgn_model, points, depth_mm * uor_per_mm, COLOR_FOUNDATION
            )
        )

    if include_overhang:
        _add_overhang(
            builder, frame, x_mm, x_mm, GATE_POST_OD, GATE_POST_WALL, COLOR_FRAME
        )


def _add_gate_leaf(builder, frame, leaf_center_x, leaf_width, hinge_side, include_overhang,
                   post_x):
    """加入一扇门扇：斜接门框 + 斜撑 + 菱形网 + 活页（+ 门顶防攀悬臂与刺钢丝）。

    hinge_side 为 -1 / +1，表示合页在门扇的哪一侧；斜撑按常规从合页面下端
    沿对角线升到自由端（中缝侧）上端。post_x 是该侧门柱的中心线位置，活页
    连接到该位置（门柱不建模时活页仍按预埋柱位置生成）。
    """
    dgn_model = builder.dgn_model
    uor_per_mm = frame.uor_per_mm
    half_radius = GATE_FRAME_OD / 2.0

    # 门框中心线相对门扇外缘内缩半个管径，使门框外表面正好落在门扇外缘；
    # 门框上表面因此正好在 GATE_HEIGHT（1800），下表面正好在离地间隙处。
    left = leaf_center_x - leaf_width / 2.0 + half_radius
    right = leaf_center_x + leaf_width / 2.0 - half_radius
    bottom = GATE_BOTTOM_CLEARANCE + half_radius
    top = GATE_HEIGHT - half_radius
    if right - left <= 3.0 * GATE_FRAME_OD or top - bottom <= 3.0 * GATE_FRAME_OD:
        raise ValueError("门扇尺寸太小，无法生成斜接门框。")

    # 四根构件的中心线端点（本地 x-z 平面）与斜接方向。每个元素的第 3、4 项是
    # 起点端 / 终点端 **另一根构件朝向自身管身** 的方向，与 _add_mitred_member
    # 里的本构件方向相加取反，得到该角落一致的外斜接面。
    bottom_left = (left, bottom)
    bottom_right = (right, bottom)
    top_left = (left, top)
    top_right = (right, top)
    members = (
        (bottom_left, bottom_right, (0.0, 1.0), (0.0, 1.0)),    # 下横杆：两端接立柱（立柱向上）
        (top_left, top_right, (0.0, -1.0), (0.0, -1.0)),        # 上横杆：两端接立柱（立柱向下）
        (bottom_left, top_left, (1.0, 0.0), (1.0, 0.0)),        # 左立柱：两端接横杆（横杆向右）
        (bottom_right, top_right, (-1.0, 0.0), (-1.0, 0.0)),    # 右立柱：两端接横杆（横杆向左）
    )
    for start_xz, end_xz, other_start, other_end in members:
        _add_mitred_member(builder, frame, start_xz, end_xz, other_start, other_end)

    hinge_x = left if hinge_side < 0.0 else right
    latch_x = right if hinge_side < 0.0 else left
    brace_dx = latch_x - hinge_x
    brace_dz = top - bottom
    brace_span = hypot(brace_dx, brace_dz)
    brace_ux = brace_dx / brace_span
    brace_uz = brace_dz / brace_span
    # 斜撑两端沿管轴各缩进门框 BRACE_END_RECESS，平口端面藏在门框管内，
    # 避免从门框斜接面的内孔处穿出。
    builder.add(
        _create_hollow_tube(
            dgn_model,
            frame.point(hinge_x + brace_ux * BRACE_END_RECESS, 0.0,
                        bottom + brace_uz * BRACE_END_RECESS),
            frame.point(latch_x - brace_ux * BRACE_END_RECESS, 0.0,
                        top - brace_uz * BRACE_END_RECESS),
            GATE_BRACE_OD,
            GATE_BRACE_WALL,
            uor_per_mm,
            COLOR_BRACE,
        )
    )

    mesh_width = right - left
    mesh_height = top - bottom
    for slope in (1, -1):
        for mesh_start, mesh_end in _clipped_diagonal_segments(mesh_width, mesh_height, slope):
            builder.add(
                _create_line_element(
                    dgn_model,
                    frame.point(left + mesh_start[0], 0.0, bottom + mesh_start[1]),
                    frame.point(left + mesh_end[0], 0.0, bottom + mesh_end[1]),
                    COLOR_MESH,
                    MESH_WIRE_DIAMETER,
                )
            )

    if include_overhang:
        _add_overhang(
            builder,
            frame,
            left,
            right,
            GATE_FRAME_OD,
            GATE_FRAME_WALL,
            COLOR_FRAME,
            angle_deg=LEAF_OVERHANG_ANGLE_DEG,
        )

    # 活页：3 个沿门扇高度均布，连接合页侧立柱与门柱（或预埋柱位置）。
    for fraction in HINGE_HEIGHT_FRACTIONS:
        _add_hinge(
            builder,
            frame,
            hinge_x,
            post_x,
            hinge_side,
            bottom + (top - bottom) * fraction,
        )


def _build_security_gate_cell(placement_point, options=None):
    """构建大门单元但**不写入模型**，返回 (builder, 统计字典)。"""
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型，再运行安保围栏大门工具。")
    if placement_point is None:
        raise ValueError("请先在模型中点取门洞中心的地面点。")

    resolved = _resolve_options(options)
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    origin = _copy_dpoint(placement_point)
    heading = resolved["heading_deg"] + (180.0 if resolved["mirrored"] else 0.0)
    frame = _GateFrame(origin, uor_per_mm, heading)
    layout = _gate_layout(resolved["gate_type"], resolved["opening_width"])

    builder = _GateCellBuilder(dgn_model)
    if resolved["include_posts"]:
        for side in (-1.0, 1.0):
            _add_gate_post(
                builder,
                frame,
                side * layout["post_offset"],
                resolved["include_foundation"],
                resolved["include_overhang"],
            )
    for index, leaf_center in enumerate(layout["leaf_centers"]):
        hinge_side = -1.0 if index == 0 else 1.0
        _add_gate_leaf(
            builder,
            frame,
            leaf_center,
            layout["leaf_width"],
            hinge_side,
            resolved["include_overhang"],
            hinge_side * layout["post_offset"],
        )

    builder.build()
    result = {
        "child_count": builder.child_count,
        "gate_type": resolved["gate_type"],
        "opening_width": resolved["opening_width"],
        "leaf_count": len(layout["leaf_centers"]),
        "leaf_width": layout["leaf_width"],
        "gate_height": GATE_HEIGHT,
        "heading_deg": heading,
        "posts": 2 if resolved["include_posts"] else 0,
        "foundation": bool(resolved["include_foundation"] and resolved["include_posts"]),
        "overhang": bool(resolved["include_overhang"]),
        "warnings": list(builder.warnings),
    }
    return builder, result


def draw_security_gate(placement_point, options=None):
    """在给定位置创建一个整体大门单元，返回统计字典。"""
    builder, result = _build_security_gate_cell(placement_point, options)
    builder.commit()
    return result


def replace_security_gate(placement_point, options, previous_handle):
    """重建大门：先构建并写入新的一版，成功后再删除上一版预览。

    新的一版构建失败时旧预览保持不动，因此改选项不会把模型里的大门改没了。
    返回 (新单元句柄, 统计字典, 是否删掉了旧预览)。
    """
    builder, result = _build_security_gate_cell(placement_point, options)
    new_handle = builder.commit()
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


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


class _GateSettingsDialog(_MicroStationTk):
    """门型选择、朝向调整、预览 / 确定 / 取消界面。"""

    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("安保围栏大门")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)

        # 预览状态挂在面板上：工具实例可能在选点后重启，而面板对象是跨实例
        # 传递的，所以状态放这里才不会丢。
        self.placement_point = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._pending_regeneration = None

        body = tk.Frame(self, padx=12, pady=10)
        body.grid(row=0, column=0, sticky="nsew")

        tk.Label(
            body,
            text="在模型中点取门洞中心的地面点（点取位置的 Z 即地面标高）。",
            justify="left",
            fg="#333333",
            wraplength=390,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        tk.Label(body, text="门型：").grid(row=1, column=0, pady=(10, 0), sticky="w")
        self.gate_type_var = tk.StringVar(value="single")
        single_radio = tk.Radiobutton(
            body,
            text="单扇门（默认 1.2 m）",
            variable=self.gate_type_var,
            value="single",
            command=self.on_gate_type_changed,
        )
        single_radio.grid(row=1, column=1, pady=(10, 0), sticky="w")
        double_radio = tk.Radiobutton(
            body,
            text="双扇门（默认 4.27 m）",
            variable=self.gate_type_var,
            value="double",
            command=self.on_gate_type_changed,
        )
        double_radio.grid(row=1, column=2, pady=(10, 0), sticky="w")

        tk.Label(body, text="门洞净宽：").grid(row=2, column=0, pady=(6, 0), sticky="w")
        self.width_var = tk.StringVar(value="%.0f" % GATE_WIDTH_SINGLE)
        self.width_entry = tk.Entry(body, textvariable=self.width_var, width=12)
        self.width_entry.grid(row=2, column=1, pady=(6, 0), sticky="w")
        tk.Label(body, text="mm（两门柱内表面之间）").grid(
            row=2, column=2, pady=(6, 0), sticky="w"
        )
        self.width_var.trace_add("write", self.on_entry_changed)

        tk.Label(body, text="转角：").grid(row=3, column=0, pady=(6, 0), sticky="w")
        self.heading_var = tk.StringVar(value="0")
        self.heading_entry = tk.Entry(body, textvariable=self.heading_var, width=12)
        self.heading_entry.grid(row=3, column=1, pady=(6, 0), sticky="w")
        tk.Label(body, text="°（0° 沿 +X，逆时针为正）").grid(
            row=3, column=2, pady=(6, 0), sticky="w"
        )
        self.heading_var.trace_add("write", self.on_entry_changed)

        self.mirror_var = tk.BooleanVar(value=False)
        mirror_check = tk.Checkbutton(
            body,
            text="反向（防攀悬臂改朝另一侧）",
            variable=self.mirror_var,
            command=self.on_options_changed,
        )
        mirror_check.grid(row=4, column=0, columnspan=3, pady=(6, 0), sticky="w")

        self.posts_var = tk.BooleanVar(value=True)
        posts_check = tk.Checkbutton(
            body,
            text="生成门柱（φ100 × 2 钢管、长 2.6 m，与转角柱同规格）",
            variable=self.posts_var,
            command=self.on_options_changed,
        )
        posts_check.grid(row=5, column=0, columnspan=3, pady=(2, 0), sticky="w")

        self.foundation_var = tk.BooleanVar(value=True)
        foundation_check = tk.Checkbutton(
            body,
            text="门柱增加混凝土基础（400×400×600，顶面与地面齐平）",
            variable=self.foundation_var,
            command=self.on_options_changed,
        )
        foundation_check.grid(row=6, column=0, columnspan=3, pady=(2, 0), sticky="w")

        self.overhang_var = tk.BooleanVar(value=True)
        overhang_check = tk.Checkbutton(
            body,
            text="生成防攀悬臂与刺钢丝（门扇垂直 450、门柱 45°）",
            variable=self.overhang_var,
            command=self.on_options_changed,
        )
        overhang_check.grid(row=7, column=0, columnspan=3, pady=(2, 0), sticky="w")

        self.option_widgets = [
            single_radio,
            double_radio,
            self.width_entry,
            self.heading_entry,
            mirror_check,
            posts_check,
            foundation_check,
            overhang_check,
        ]

        self.gate_info_label = tk.Label(
            body, text="大门：尚未放置", justify="left", fg="#333333"
        )
        self.gate_info_label.grid(row=8, column=0, columnspan=3, pady=(10, 0), sticky="w")

        self.preview_info_label = tk.Label(
            body, text="预览：—", justify="left", fg="#333333"
        )
        self.preview_info_label.grid(row=9, column=0, columnspan=3, sticky="w")

        self.status_label = tk.Label(
            body,
            text="请在模型中点取门洞中心的地面点；点取后可改选项，预览会自动重建。",
            justify="left",
            fg="#1f5f99",
            wraplength=390,
        )
        self.status_label.grid(row=10, column=0, columnspan=3, pady=(10, 0), sticky="w")

        button_row = tk.Frame(body)
        button_row.grid(row=11, column=0, columnspan=3, pady=(10, 0), sticky="e")
        confirm_button = tk.Button(
            button_row, text="确定", width=10, command=self.confirm_tool
        )
        confirm_button.pack(side="right")
        cancel_button = tk.Button(
            button_row, text="取消", width=10, command=self.cancel_tool
        )
        cancel_button.pack(side="right", padx=(0, 6))
        self.action_widgets = [confirm_button, cancel_button]

    def current_options(self):
        """读取面板选项；门洞净宽 / 转角无法解析时抛 ValueError。"""
        try:
            opening_width = float(self.width_var.get())
        except (TypeError, ValueError):
            raise ValueError("门洞净宽必须是数字（mm）。")
        try:
            heading = float(self.heading_var.get())
        except (TypeError, ValueError):
            raise ValueError("转角必须是数字（度）。")
        return {
            "gate_type": self.gate_type_var.get(),
            "opening_width": opening_width,
            "heading_deg": heading,
            "mirrored": bool(self.mirror_var.get()),
            "include_posts": bool(self.posts_var.get()),
            "include_foundation": bool(self.foundation_var.get()),
            "include_overhang": bool(self.overhang_var.get()),
        }

    def set_status(self, message, is_error=False):
        self.status_label.configure(
            text=message,
            fg="#b42318" if is_error else "#1f5f99",
        )
        self.update_idletasks()

    def set_result(self, result):
        leaf_text = (
            "单扇门" if result["gate_type"] == "single" else "双扇门"
        )
        self.gate_info_label.configure(
            text="大门：%s，门洞净宽 %.0f mm，转角 %.1f°" % (
                leaf_text,
                result["opening_width"],
                result["heading_deg"],
            )
        )
        self.preview_info_label.configure(
            text="预览：门扇 %d 扇 × %.0f mm，门柱 %d 根；基础：%s；防攀悬臂：%s" % (
                result["leaf_count"],
                result["leaf_width"],
                result["posts"],
                "已生成" if result["foundation"] else "未生成",
                "已生成" if result["overhang"] else "未生成",
            )
        )

    def _set_busy(self, busy):
        """生成期间禁用所有控件，避免重复触发或中途点确定/取消。"""
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in self.option_widgets + self.action_widgets:
            widget.configure(state=state)
        self.update_idletasks()

    def on_gate_type_changed(self):
        """切换门型时把门洞净宽恢复成该门型的规范默认值。"""
        default_width = (
            GATE_WIDTH_SINGLE
            if self.gate_type_var.get() == "single"
            else GATE_WIDTH_DOUBLE
        )
        # 设置输入框会触发 on_entry_changed，两次重建请求由防抖合成一次。
        self.width_var.set("%.0f" % default_width)
        self.on_options_changed()

    def on_entry_changed(self, *_unused):
        """输入框改动后延迟重建；这里不区分是哪一次 set，交给防抖处理。"""
        self.on_options_changed()

    def on_options_changed(self):
        """选项变化后延迟重建，连点几下也只重建一次。"""
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
            # 定时器可能已经触发过，忽略即可。
            return

    def _run_pending_regeneration(self):
        self._pending_regeneration = None
        self.regenerate()

    def regenerate(self, placement_point=None):
        """按当前选项重建预览：先建新的一版，成功后再删掉旧的。"""
        # 直接调用（例如刚点取了位置）时，取消掉排队中的那次重建。
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
        self.set_status("正在生成大门预览，请稍候……")
        try:
            handle, result, deleted = replace_security_gate(
                self.placement_point, options, self.preview_handle
            )
        except Exception as error:
            # 新的一版没建起来，旧预览保持不动。
            message = "大门生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.set_result(result)
        message = (
            "预览已更新：%s，门洞净宽 %.0f mm，门扇 %d 扇 × %.0f mm，门柱 %d 根，"
            "%s，%s，共 %d 个子元素。%s改选项会自动重建；点【确定】保留，点【取消】放弃。"
            % (
                "单扇门" if result["gate_type"] == "single" else "双扇门",
                result["opening_width"],
                result["leaf_count"],
                result["leaf_width"],
                result["posts"],
                "含混凝土基础" if result["foundation"] else "不含混凝土基础",
                "含防攀悬臂" if result["overhang"] else "不含防攀悬臂",
                result["child_count"],
                "已替换上一版预览。" if deleted else "",
            )
        )
        if result["warnings"]:
            message += "注意：%s" % "；".join(result["warnings"])
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        """删除当前预览，返回是否真的删掉了。"""
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def confirm_tool(self):
        """保留当前预览并结束工具。"""
        self._cancel_pending_regeneration()
        self.confirmed = True
        self.finish_tool()

    def cancel_tool(self):
        """删除预览并结束工具。"""
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        PyCommandState.StartDefaultCommand()


class SecurityFenceGatePlacementTool(DgnPrimitiveTool):
    """点取门洞中心地面点并放置安保围栏大门的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString("SecurityFenceGatePlacementTool")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            "请点取门洞中心的地面点；点取后可改门型等选项，预览会自动重建，"
            "点【确定】保留，点【取消】或右键放弃。"
        )

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        # regenerate() 内部会先建新的一版、成功后再删掉上一版预览，
        # 失败时保留旧预览并给出提示。再点一次即把预览移到新位置。
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        """右键结束工具：放弃尚未确定的预览。

        取消动作延到 Tk 空转时再执行：真正的结束是 PyCommandState.StartDefaultCommand()，
        它会在回调返回前卸载工具，放到 Tk 事件里走更稳妥。
        """
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
            tool_settings if tool_settings is not None else _GateSettingsDialog()
        )
        tool = SecurityFenceGatePlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    SecurityFenceGatePlacementTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
