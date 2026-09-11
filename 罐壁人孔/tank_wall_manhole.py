# -*- coding: utf-8 -*-
"""在 MicroStation / OpenPlant Modeler 的活动 3D 模型中交互放置罐壁人孔。

本脚本按图 BN-DS-A 4 "DAVIT FOR MANWAY COVERS"（Sheet 1 of 2）绘制一个
**罐壁（筒体）人孔**：轴线水平的筒节 + 带螺栓孔的法兰 + 盲盖板 + 盖板把手，
并可选装盖板的**铰链（hinge，绕竖直销轴侧开）**或**吊杆（davit，R220 弯臂
吊起盖板）**两种开启机构。吊杆直径按图纸表格由"人孔公称尺寸 + 法兰压力
等级"查得；铰链/吊杆的销孔、开口销、吊环螺栓等尺寸也取自该图。

图纸尺寸与脚本的对应关系见 README.md。

工作方式与 `安保围栏-门/security_fence_gate.py` 一致：在工具设置面板里选
公称尺寸、压力等级与连接形式，在模型中点取罐壁上的放置点后立即生成一版
**预览**；改动选项自动重建（模型里始终只有一版预览），点【确定】就地保留，
点【取消】放弃。整组人孔写成一个普通单元（Normal Cell），可整体选中、移动、
复制或删除。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import print_function

from math import atan2, cos, hypot, pi, radians, sin, sqrt
import os
import traceback

import tkinter as tk
import tkinter

import win32gui

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# ---------------------------------------------------------------------------
# 图纸尺寸（mm）
# ---------------------------------------------------------------------------

# 吊杆直径 "D"：图 BN-DS-A 4 表格 MANWAY NOM. SIZE × ASA 压力等级。
DAVIT_DIA_TABLE = {
    18: {150: 35.0, 300: 45.0, 600: 50.0},
    20: {150: 40.0, 300: 50.0, 600: 60.0},
    24: {150: 45.0, 300: 55.0, 600: 65.0},
}

# 人孔本体参考尺寸。原图（Sheet 1 of 2）只给了吊杆细节，没给人孔法兰本体
# 尺寸；这里按公称尺寸给出一组可用的参考值，正式建模前应在面板中改成项目
# 实际采用的人孔标准尺寸（人孔规格书或 ASME B16.5）。
MANWAY_TABLE = {
    18: {
        "bore": 450.0,
        "neck_od": 480.0,
        "flange_od": 700.0,
        "flange_t": 45.0,
        "bolt_circle": 610.0,
        "bolt_count": 16,
        "bolt_dia": 20.0,
        "cover_t": 45.0,
    },
    20: {
        "bore": 500.0,
        "neck_od": 530.0,
        "flange_od": 770.0,
        "flange_t": 50.0,
        "bolt_circle": 675.0,
        "bolt_count": 20,
        "bolt_dia": 20.0,
        "cover_t": 50.0,
    },
    24: {
        "bore": 600.0,
        "neck_od": 635.0,
        "flange_od": 890.0,
        "flange_t": 55.0,
        "bolt_circle": 790.0,
        "bolt_count": 20,
        "bolt_dia": 24.0,
        "cover_t": 55.0,
    },
}

NECK_LENGTH_DEFAULT = 150.0   # 筒节长度（罐壁外表面到法兰背面）
GASKET_T = 2.0                # 法兰与盖板之间的垫片厚度（留缝，避免共面）
BOLT_HOLE_CLEARANCE = 2.0     # 螺栓孔径 = 螺栓直径 + 该间隙

# --- 吊杆（davit）-----------------------------------------------------------
DAVIT_BEND_RADIUS = 220.0     # R=220，吊杆主弯头中心线半径
DAVIT_POST_MARGIN = 55.0      # 立柱轴线到法兰外缘的径向距离
DAVIT_POST_BOTTOM = -160.0    # 立柱下端 z（吊耳以下，用于插开口销）
DAVIT_POST_COTTER_OFFSET = 45.0   # 立柱开口销孔到立柱下端的距离
DAVIT_HOLE_CLEARANCE = 3.0    # 吊耳销孔直径 = 吊杆直径 D + 3（图中 "D"+3）
DAVIT_COTTER_DIA = 5.0        # 吊杆开口销直径（图中 5 mm DIA）
DAVIT_COTTER_HOLE_DIA = 5.5
DAVIT_PLANE_OFFSET = 10.0     # 吊杆平面到盖板外面的距离
DAVIT_ARM_RISE = 140.0        # 盖板顶边（法兰半径）到水平臂 / 扁头的高度

# 吊杆回转支撑件：矩形截面沿 ] 形路径扫掠成一体支架。
DAVIT_SUPPORT_THICKNESS = 16.0       # 矩形截面厚度 / 直板厚度
DAVIT_SUPPORT_CLEAR_HEIGHT = 128.0   # 上下水平板之间的净高
DAVIT_SUPPORT_OUTER_RADIUS = 20.0    # 背部上下外侧圆角
DAVIT_SUPPORT_INNER_RADIUS = 10.0    # 背部上下内侧圆角
DAVIT_SUPPORT_CHAMFER_ANGLE = 30.0   # 自由端倒角与板长方向夹角
DAVIT_SUPPORT_END_BELOW = 25.0       # 立柱低于下板底面的长度
DAVIT_SUPPORT_COTTER_FROM_END = 20.0 # 开口销孔中心距立柱下端

# 扁头（吊杆臂最末端）与圆管→矩形放样
FLAT_HEAD_WIDTH = 100.0       # 扁头宽（水平、垂直于臂轴线）
FLAT_HEAD_LENGTH = 120.0      # 扁头长（沿臂轴线）
FLAT_HEAD_HEIGHT_FACTOR = 0.5  # 扁头厚 = D / 2
LOFT_LENGTH_FACTOR = 1.5      # 放样长度 = 1.5 D
SLOT_LENGTH = 40.0            # 扁头长圆孔长（沿臂轴线，套 M20 调节螺栓）
SLOT_WIDTH = 22.0             # 扁头长圆孔宽（= 两端半圆直径）
SLOT_END_SEGMENTS = 12        # 长圆孔两端半圆分段数（直边恒为直线）
LOFT_SIDES = 24               # 放样断面边数
LOFT_SLICES = 24              # 直纹放样不可用时的台阶近似段数

# --- 法兰上的回转吊耳与铰链销轴 ---------------------------------------------
LUG_WIDTH = 50.0              # LUGS 50 WIDE
LUG_THICKNESS = 16.0          # RING 16 THK
LUG_GAP = 75.0                # 法兰上两只回转吊耳之间的净距（图中 75）
LUG_Z = LUG_GAP / 2.0 + LUG_THICKNESS / 2.0   # ±45.5，与图中 45 一致
HINGE_PIN_DIA = 16.0          # 图中 16 DIA
HINGE_PIN_HOLE_DIA = 18.0
PIN_EXTENSION = 20.0          # 销轴伸出上下吊耳的长度
COTTER_DIA = 4.0              # 图中 4 mm DIA FOR COTTER PIN
COTTER_HOLE_DIA = 4.5

# --- 盖板顶部连接：盖板边缘吊耳 + 全螺纹螺柱 + 竖向 M20 调节吊环螺栓 ----------
# 吊耳**只焊在盖板（盲法兰）边缘**，不跨到人孔法兰上。
COVER_LUG_THICKNESS = 16.0    # RING 16 THK
COVER_LUG_GAP = 34.0          # 两吊耳之间的净距（容纳吊环）
COVER_LUG_BACK = 0.0          # 吊耳后端从盖板背面起（不伸到人孔法兰上）
COVER_LUG_FRONT = 25.0        # 吊耳伸出盖板外面的长度
COVER_LUG_DOWN = 50.0         # 吊耳向下埋入盖板顶边的深度
COVER_LUG_TOP = 60.0          # 吊耳高出盖板顶边（法兰半径）的长度
STUD_Z_RISE = 40.0            # 全螺纹螺柱中心高出盖板顶边
STUD_DIA = 16.0               # 全螺纹螺柱（图中 16 DIA）
STUD_HOLE_CLEARANCE = 1.0     # 螺柱孔直径 = 螺柱直径 + 该间隙
STUD_END_LENGTH = 26.0        # 螺柱伸出吊耳外侧、装螺母的长度
STUD_NUT_COUNT = 2            # 螺柱两端各一个螺母

# M20 吊环螺栓（做法与参数照 eye_bolt_only.py：孔心为原点、孔轴为局部 Y）
EYE_BOLT_DIA = 20.0           # M.20 BOLT
EYE_BOLT_HOLE_DIA = 30.0      # 图中 30（吊环孔）
EYE_BOLT_TOP_HEIGHT = 200.0   # 孔心到杆顶的距离（图中 200）
EYE_BOLT_THREAD_LENGTH = 100.0  # 100 MIN
EYE_BOLT_BEND_RADIUS = 30.0   # R=30（颈弯中心线半径）
EYE_BOLT_NUT_COUNT = 2        # 2 NUTS WITH WASHER

# --- 盖板把手（两个，各距竖直中心线 175，垂直于盖板法兰）---------------------
# 把手从盖板外面**垂直伸出**，再 90° 下弯成竖直段，下端 180° 卷钩。
HANDLE_BAR_DIA = 20.0         # 20 DIA.
HANDLE_OFFSET = 175.0         # 把手中心到竖直中心线（图中 175 | 175）
HANDLE_LENGTH = 150.0         # 把手竖直总高（图中 150）
HANDLE_PROJECTION = 60.0      # 从盖板外面垂直伸出的长度
HANDLE_TOP_BEND_RADIUS = 40.0  # 上端 90° 下弯中心线半径
HANDLE_CURL_RADIUS = 22.0     # 下端 180° 卷钩中心线半径

NUT_ACROSS_FLATS_FACTOR = 1.5   # 六角对边距 ≈ 1.5 × 螺纹直径
NUT_HEIGHT_FACTOR = 0.8
HEAD_HEIGHT_FACTOR = 0.6
WASHER_OD_FACTOR = 1.85
WASHER_THICKNESS = 3.0

# MicroStation 颜色表编号（0-31）。
COLOR_NECK = 7
COLOR_FLANGE = 7
COLOR_COVER = 6
COLOR_BOLT = 1
COLOR_HANDGRIP = 4
COLOR_LUG = 2
COLOR_DAVIT = 2
COLOR_EYE_BOLT = 3
COLOR_PIN = 5
COLOR_FLAT = 4
COLOR_LOFT = 4

CELL_NAME = "TANK_WALL_MANHOLE"

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150

DEFAULT_OPTIONS = {
    "nominal_size": 20,       # 18 / 20 / 24（英寸）
    "rating": 150,            # 150 / 300 / 600（ASA lbs）
    "mode": "davit",          # hinge（铰链）/ davit（吊杆）
    "heading_deg": 0.0,       # 人孔轴线方向：0° 沿模型 +X，逆时针为正
    "neck_length": NECK_LENGTH_DEFAULT,
    "mirrored": False,        # 反向：人孔轴线转 180°
    "include_bolts": True,    # 生成法兰螺栓 / 螺母
    "include_lifting": True,  # 生成铰链或吊杆
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
    """把失败信息写到本目录的日志，便于在 OPM 里排查几何内核错误。"""
    try:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tank_wall_manhole_debug_log.txt",
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
    """合并默认值、校验选项，并算出本次生成用的全部毫米尺寸。"""
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        for key in options:
            if key not in resolved:
                raise ValueError("未知选项：%s" % key)
            resolved[key] = options[key]

    try:
        size = int(resolved["nominal_size"])
    except (TypeError, ValueError):
        raise ValueError("人孔公称尺寸必须是 18、20 或 24。")
    if size not in MANWAY_TABLE:
        raise ValueError("人孔公称尺寸只支持 18\"、20\"、24\"。")

    try:
        rating = int(resolved["rating"])
    except (TypeError, ValueError):
        raise ValueError("压力等级必须是 150、300 或 600。")
    if rating not in DAVIT_DIA_TABLE[size]:
        raise ValueError("压力等级只支持 ASA 150 / 300 / 600 lbs。")

    mode = resolved["mode"]
    if mode not in ("hinge", "davit"):
        raise ValueError("连接形式必须为 hinge（铰链）或 davit（吊杆）。")

    try:
        heading = float(resolved["heading_deg"])
    except (TypeError, ValueError):
        raise ValueError("朝向必须是数字（度）。")
    if heading != heading or heading in (float("inf"), float("-inf")):
        raise ValueError("朝向必须是有限数字。")

    try:
        neck_length = float(resolved["neck_length"])
    except (TypeError, ValueError):
        raise ValueError("筒节长度必须是数字（mm）。")
    if neck_length <= 0.0:
        raise ValueError("筒节长度必须大于零。")

    dims = dict(MANWAY_TABLE[size])
    dims["neck_length"] = neck_length
    dims["cover_od"] = dims["flange_od"]
    dims["davit_dia"] = DAVIT_DIA_TABLE[size][rating]

    resolved["nominal_size"] = size
    resolved["rating"] = rating
    resolved["heading_deg"] = heading
    resolved["neck_length"] = neck_length
    resolved["mirrored"] = bool(resolved["mirrored"])
    resolved["include_bolts"] = bool(resolved["include_bolts"])
    resolved["include_lifting"] = bool(resolved["include_lifting"])
    resolved["dims"] = dims
    return resolved


def _manway_layout(dims):
    """把毫米尺寸换算成局部坐标下的各站位与半径。

    吊杆不再落到盖板中心：扁头（水平臂末端）落在**盖板顶部**，水平销与
    M20 调节吊环螺栓也在盖板顶边之上，法兰吊耳从法兰边缘伸上来承接。
    """
    flange_r = dims["flange_od"] / 2.0
    cover_r = dims["cover_od"] / 2.0
    diameter = dims["davit_dia"]
    x_flange_back = dims["neck_length"]
    x_flange_front = x_flange_back + dims["flange_t"]
    x_cover_back = x_flange_front + GASKET_T
    x_cover_front = x_cover_back + dims["cover_t"]
    z_arm = flange_r + DAVIT_ARM_RISE
    return {
        "x_flange_back": x_flange_back,
        "x_flange_front": x_flange_front,
        "x_cover_back": x_cover_back,
        "x_cover_front": x_cover_front,
        "flange_r": flange_r,
        "cover_r": cover_r,
        "bolt_circle_r": dims["bolt_circle"] / 2.0,
        "bolt_hole_r": (dims["bolt_dia"] + BOLT_HOLE_CLEARANCE) / 2.0,
        "x_davit": x_cover_front + DAVIT_PLANE_OFFSET,
        "y_post": flange_r + DAVIT_POST_MARGIN,
        "z_arm": z_arm,
        "z_post_top": z_arm - DAVIT_BEND_RADIUS,
        "stud_z": flange_r + STUD_Z_RISE,
        "flat_thickness": diameter * FLAT_HEAD_HEIGHT_FACTOR,
        "loft_length": diameter * LOFT_LENGTH_FACTOR,
    }


class _ManholeFrame(object):
    """人孔局部坐标系：x 沿人孔轴线（由罐壁向外）、y 水平切向、z 竖直向上。

    原点取用户点取的罐壁外表面人孔中心点；0° 时 +x 沿模型 +X。所有换算都按
    mm 输入、UOR 输出，因此不要求 DGN 主单位是 mm。
    """

    def __init__(self, origin, uor_per_mm, heading_deg):
        angle = radians(heading_deg)
        self.origin = origin
        self.uor_per_mm = uor_per_mm
        self.u = (cos(angle), sin(angle))     # 人孔轴线方向（局部 +x）
        self.v = (-sin(angle), cos(angle))    # 水平切向（局部 +y）

    def point(self, x_mm, y_mm, z_mm):
        scale = self.uor_per_mm
        return DPoint3d.From(
            self.origin.x + (self.u[0] * x_mm + self.v[0] * y_mm) * scale,
            self.origin.y + (self.u[1] * x_mm + self.v[1] * y_mm) * scale,
            self.origin.z + z_mm * scale,
        )

    def uor(self, mm):
        return mm * self.uor_per_mm

    def offset(self, dx_mm, dy_mm, dz_mm):
        """局部平移出一个人孔轴向的子坐标系（用于把扁头/放样摆到盖板顶部）。"""
        shifted = _ManholeFrame.__new__(_ManholeFrame)
        shifted.origin = self.point(dx_mm, dy_mm, dz_mm)
        shifted.uor_per_mm = self.uor_per_mm
        shifted.u = self.u
        shifted.v = self.v
        return shifted


# ---------------------------------------------------------------------------
# 基本几何件
# ---------------------------------------------------------------------------


def _cylinder_element(dgn_model, start, end, radius):
    """创建一个尚未写入模型的实心圆柱元素。"""
    detail = DgnConeDetail(start, end, radius, radius, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return element


def _cylinder_body(dgn_model, start, end, radius):
    """创建一个圆柱实体（供布尔运算使用）。"""
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
    for cutter in cutters:
        if cutter is None:
            continue
        tools = ISolidKernelEntityPtrArray()
        tools.append(cutter)
        SolidUtil.Modify.BooleanSubtract(body, tools)


def _solid_cylinder(dgn_model, start, end, radius_uor, color, holes=()):
    """实心圆柱；holes 为 (start, end, radius_uor)，在写入前先掏掉。"""
    outer = _cylinder_element(dgn_model, start, end, radius_uor)
    if outer is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if not _succeeded(status):
        return None
    cutters = [_cylinder_body(dgn_model, s, e, r) for s, e, r in holes]
    _subtract(body, cutters)
    return _element_from_body(dgn_model, body, outer, color)


def _torus_element(dgn_model, center, vector_x, vector_y, major, minor, sweep):
    detail = DgnTorusPipeDetail(
        center, vector_x, vector_y, major, minor, sweep, True
    )
    primitive = ISolidPrimitive.CreateDgnTorusPipe(detail)
    element = EditElementHandle()
    if not _succeeded(DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return element


def _prism_with_holes(dgn_model, corners, thickness_uor, color, holes=(),
                      cutter_elements=()):
    """按闭合轮廓沿法向拉伸成实体，再一次减掉全部刀具体。

    轮廓绕向决定拉伸方向（右手法向）。holes 为 (start, end, radius_uor)
    圆柱孔；cutter_elements 为已建好的刀具体（如长圆孔、方形），
    两者一起在**同一次**布尔里减掉，避免分次相减在共面处出错。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    if not _succeeded(
        ShapeHandler.CreateShapeElement(
            profile, None, corners, model_ref.Is3d(), model_ref
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


def _plate_xz(dgn_model, frame, points_xz, y_mm, thickness_mm, color, holes=()):
    """竖直板（厚度沿 y，轮廓在 x-z 平面内），用于盖板顶部的法兰吊耳。

    points_xz 按 (x, z) **逆时针**给出，法向为 -y，因此沿 -y 拉伸：板占
    y ∈ [y_mm - thickness_mm, y_mm]。holes 为 (start, end, radius_uor)。
    """
    points = DPoint3dArray()
    for x, z in points_xz:
        points.append(frame.point(x, y_mm, z))
    return _prism_with_holes(
        dgn_model, points, frame.uor(thickness_mm), color, holes
    )


def _hollow_disk(dgn_model, frame, x_back, x_front, outer_r, inner_r, color, holes=()):
    """圆盘/法兰：外圆柱减中心孔与若干平行于 x 轴的小孔。

    holes 为 (y_mm, z_mm, hole_r_mm) 列表；inner_r 为 0 时不掏中心孔。
    """
    outer = _cylinder_element(
        dgn_model, frame.point(x_back, 0.0, 0.0), frame.point(x_front, 0.0, 0.0),
        frame.uor(outer_r),
    )
    if outer is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if not _succeeded(status):
        return None

    extension = 2.0
    cutters = []
    if inner_r > 0.0:
        cutters.append(_cylinder_body(
            dgn_model,
            frame.point(x_back - extension, 0.0, 0.0),
            frame.point(x_front + extension, 0.0, 0.0),
            frame.uor(inner_r),
        ))
    for y, z, radius in holes:
        cutters.append(_cylinder_body(
            dgn_model,
            frame.point(x_back - extension, y, z),
            frame.point(x_front + extension, y, z),
            frame.uor(radius),
        ))
    _subtract(body, cutters)
    return _element_from_body(dgn_model, body, outer, color)


def _plate(frame, x0, x1, y0, y1, z0):
    """水平板（厚度沿 z）的 4 角点 + 回环点，逆时针（法向 +z）。"""
    points = DPoint3dArray()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)):
        points.append(frame.point(x, y, z0))
    return points


def _hex_corners_x(frame, x, y, z, across_flats):
    """沿局部 x 轴拉伸的六角形轮廓（法向 +x）。"""
    radius = across_flats / 2.0 / cos(radians(30.0))
    points = DPoint3dArray()
    for index in range(7):
        angle = radians(60.0 * (index % 6))
        points.append(frame.point(x, y + radius * cos(angle), z + radius * sin(angle)))
    return points


def _hex_corners_y(frame, x, y, z, across_flats):
    """沿局部 y 轴拉伸的六角形轮廓（法向 -y）。"""
    radius = across_flats / 2.0 / cos(radians(30.0))
    points = DPoint3dArray()
    for index in range(7):
        angle = radians(60.0 * (index % 6))
        points.append(frame.point(x + radius * cos(angle), y, z + radius * sin(angle)))
    return points


def _hex_corners_z(frame, x, y, z, across_flats):
    """沿局部 z 轴拉伸的六角形轮廓（法向 +z）。"""
    radius = across_flats / 2.0 / cos(radians(30.0))
    points = DPoint3dArray()
    for index in range(7):
        angle = radians(60.0 * (index % 6))
        points.append(frame.point(x + radius * cos(angle), y + radius * sin(angle), z))
    return points


def _line_component(start, end):
    model_ref = ISessionMgr.ActiveDgnModelRef
    element = EditElementHandle()
    status = LineHandler.CreateLineElement(
        element, None, DSegment3d(start, end), model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        return None
    return element


def _arc_component(start, middle, end):
    model_ref = ISessionMgr.ActiveDgnModelRef
    element = EditElementHandle()
    arc = DEllipse3d.FromPointsOnArc(start, middle, end)
    status = ArcHandler.CreateArcElement(
        element, None, arc, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        return None
    return element


def _body_from_sweep(profile_vector, path_vector, model_ref, path_start):
    """沿开放路径扫掠闭合截面（兼容 OPM 各版本的签名差异）。"""
    try:
        result = SolidUtil.Create.BodyFromSweep(
            profile_vector, path_vector, model_ref, False, True, False
        )
    except TypeError:
        result = SolidUtil.Create.BodyFromSweep(
            profile_vector,
            path_vector,
            model_ref,
            False,  # alignParallel：截面始终垂直于路径
            True,   # selfRepair
            False,  # createSheet：生成实体
            DVec3d.From(0.0, 0.0, 0.0),
            0.0,    # 扭转角
            1.0,    # 比例
            path_start,
        )
    if len(result) < 2 or not _succeeded(result[0]):
        raise RuntimeError("圆钢沿路径扫掠失败。")
    return result[1]


def _swept_round_bar(dgn_model, segments, profile_center, profile_normal,
                     radius_uor, color, holes=()):
    """把一系列直线/圆弧段组成的路径扫掠成圆钢，并可预先掏横向孔。

    segments 元素为 ('line', p0, p1) 或 ('arc', p0, pmid, p1)，p 为 model 点。
    """
    components = []
    for segment in segments:
        if segment[0] == "line":
            components.append(_line_component(segment[1], segment[2]))
        else:
            components.append(
                _arc_component(segment[1], segment[2], segment[3])
            )

    model_ref = ISessionMgr.ActiveDgnModelRef
    path = EditElementHandle()
    status = ChainHeaderHandler.CreateChainHeaderElement(
        path, None, False, model_ref.Is3d(), model_ref
    )
    # 个别 OPM 版本此函数成功时也返回 None；因此只在明确非零时报错。
    if status is not None and not _succeeded(status):
        return None
    for component in components:
        if component is None:
            return None
        ChainHeaderHandler.AddComponentElement(path, component)
    ChainHeaderHandler.AddComponentComplete(path)

    path_vector = ICurvePathQuery.ElementToCurveVector(path)
    if path_vector is None:
        return None
    ellipse = DEllipse3d.FromCenterNormalRadius(
        profile_center, DVec3d.From(*profile_normal), radius_uor
    )
    profile_vector = CurveVector.CreateDisk(
        ellipse, CurveVector.eBOUNDARY_TYPE_Outer
    )
    body = _body_from_sweep(profile_vector, path_vector, model_ref, profile_center)
    cutters = [_cylinder_body(dgn_model, s, e, r) for s, e, r in holes]
    _subtract(body, cutters)
    return _element_from_body(dgn_model, body, path, color)


def _arc_midpoint(center, start, end):
    """圆心 + 起点 + 终点 → 圆弧中点（≤180°）。"""
    v0 = (start[0] - center[0], start[1] - center[1])
    v1 = (end[0] - center[0], end[1] - center[1])
    mx, my = v0[0] + v1[0], v0[1] + v1[1]
    length = hypot(mx, my)
    radius = hypot(v0[0], v0[1])
    if length <= 1.0e-9:
        return start
    return (center[0] + mx / length * radius, center[1] + my / length * radius)


def _bolt_positions(count, radius):
    """沿螺栓圆均布，起点取半个节距，避免正上方有一颗螺栓。"""
    step = 2.0 * pi / count
    return [
        (radius * cos(step * (index + 0.5)), radius * sin(step * (index + 0.5)))
        for index in range(count)
    ]


# ---------------------------------------------------------------------------
# 扁头与圆管→矩形放样（与 davit_only.py 同一套做法）
# ---------------------------------------------------------------------------


def _rectangle_perimeter(half_width_mm, half_thickness_mm, per_side):
    """矩形边界采样点（**含 4 个精确角点**），逆时针，从 (w, -t) 起。

    每边取 per_side 个点（含起点），相邻点都在同一条直边上，折线严格等于
    矩形本身，放样矩形端才能与扁头端面对齐、角上不留缺口。
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
    """断面点列（纯数学）：t=0 为矩形、t=1 为 ØD 圆，两端按序号配对。"""
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
    """断面点列 → 模型点列（位于 y = y_mm 平面内，闭合）。"""
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
        ShapeHandler.CreateShapeElement(
            profile, None, points, model_ref.Is3d(), model_ref
        )
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
    """备选：SolidUtil.Create.BodyFromLoft（部分版本才有）。返回 (实体, 原因)。"""
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


def _morph_slice_elements(dgn_model, frame, y_rect, y_round, half_width,
                          half_thickness, radius, color):
    """台阶近似：把放样切成若干薄片，逐片用同一组角度采样的小棱柱。"""
    step = (y_round - y_rect) / LOFT_SLICES
    if step <= 0.0:
        return []
    elements = []
    for index in range(LOFT_SLICES):
        t = float(index) / LOFT_SLICES
        y = y_rect + step * index
        points = _section_points(frame, y, half_width, half_thickness, radius, t)
        # 反序（法向 +y，朝圆管一侧），ThickenSheet 便沿 +y 拉伸。
        reversed_points = DPoint3dArray()
        for point in reversed(list(points)):
            reversed_points.append(point)
        element = _prism_with_holes(
            dgn_model, reversed_points, frame.uor(step), color
        )
        if element is None:
            return []
        elements.append(element)
    return elements


# ---------------------------------------------------------------------------
# 人孔本体
# ---------------------------------------------------------------------------


def _add_manway(builder, frame, resolved, layout):
    """筒节 + 法兰 + 盖板 +（可选）螺栓 + 把手。"""
    dgn_model = builder.dgn_model
    dims = resolved["dims"]
    bolt_holes = [
        (y, z, layout["bolt_hole_r"])
        for y, z in _bolt_positions(dims["bolt_count"], layout["bolt_circle_r"])
    ]

    builder.add(_hollow_disk(
        dgn_model, frame, 0.0, layout["x_flange_back"],
        dims["neck_od"] / 2.0, dims["bore"] / 2.0, COLOR_NECK,
    ))
    builder.add(_hollow_disk(
        dgn_model, frame, layout["x_flange_back"], layout["x_flange_front"],
        layout["flange_r"], dims["bore"] / 2.0, COLOR_FLANGE, bolt_holes,
    ))
    builder.add(_hollow_disk(
        dgn_model, frame, layout["x_cover_back"], layout["x_cover_front"],
        layout["cover_r"], 0.0, COLOR_COVER, bolt_holes,
    ))

    if resolved["include_bolts"]:
        _add_bolts(builder, frame, dims, layout)

    _add_handles(builder, frame, layout)


def _add_bolts(builder, frame, dims, layout):
    """每个螺栓：六角头 + 杆 + 垫圈 + 螺母。"""
    dgn_model = builder.dgn_model
    dia = dims["bolt_dia"]
    across_flats = dia * NUT_ACROSS_FLATS_FACTOR
    head_h = dia * HEAD_HEIGHT_FACTOR
    nut_h = dia * NUT_HEIGHT_FACTOR
    washer_od = dia * WASHER_OD_FACTOR

    x_back = layout["x_flange_back"]
    x_front = layout["x_cover_front"]
    for y, z in _bolt_positions(dims["bolt_count"], layout["bolt_circle_r"]):
        # 六角头（贴在法兰背面）。
        builder.add(_prism_with_holes(
            dgn_model, _hex_corners_x(frame, x_back - head_h, y, z, across_flats),
            frame.uor(head_h), COLOR_BOLT,
        ))
        # 杆：从头下表面一直伸到螺母外端。
        builder.add(_solid_cylinder(
            dgn_model, frame.point(x_back - head_h, y, z),
            frame.point(x_front + WASHER_THICKNESS + nut_h, y, z),
            frame.uor(dia / 2.0), COLOR_BOLT,
        ))
        # 盖板侧垫圈。
        builder.add(_solid_cylinder(
            dgn_model, frame.point(x_front, y, z),
            frame.point(x_front + WASHER_THICKNESS, y, z),
            frame.uor(washer_od / 2.0), COLOR_BOLT,
        ))
        # 螺母。
        builder.add(_prism_with_holes(
            dgn_model,
            _hex_corners_x(frame, x_front + WASHER_THICKNESS, y, z, across_flats),
            frame.uor(nut_h), COLOR_BOLT,
        ))


def _handle_path(y_center, length):
    """一只把手在 (x, z) 平面内的路径：垂直伸出 → 90° 下弯 → 竖直段 → 180° 卷钩。

    把手平面垂直于盖板法兰（含人孔轴线与竖直方向）；卷钩朝回盖板一侧。
    返回 (二维点段列表, 起点, 起点切向)。
    """
    half = length / 2.0
    curl_r = HANDLE_CURL_RADIUS
    bend_r = HANDLE_TOP_BEND_RADIUS
    projection = HANDLE_PROJECTION

    z_top = half
    z_bottom = -half + curl_r
    x_out = projection                      # 伸出段末端
    x_leg = x_out + bend_r                  # 竖直段所在 x
    if z_top - bend_r <= z_bottom:
        raise RuntimeError("把手尺寸不成立：请检查总高、伸出量、弯头与卷钩半径的关系。")

    bend_center = (x_out, z_top - bend_r)
    bend_end = (x_leg, z_top - bend_r)
    curl_center = (x_leg - curl_r, z_bottom)
    curl_mid = (x_leg - curl_r, z_bottom - curl_r)
    curl_tip = (x_leg - 2.0 * curl_r, z_bottom)

    segments = [
        ("line", (0.0, z_top), (x_out, z_top)),
        ("arc", (x_out, z_top),
         _arc_midpoint(bend_center, (x_out, z_top), bend_end), bend_end),
        ("line", bend_end, (x_leg, z_bottom)),
        ("arc", (x_leg, z_bottom), curl_mid, curl_tip),
    ]
    return segments, (0.0, z_top), None


def _add_handles(builder, frame, layout):
    """盖板外面两个 Ø20 卷钩把手：各距竖直中心线 175、垂直于盖板法兰。"""
    dgn_model = builder.dgn_model
    x_face = layout["x_cover_front"]

    for y_center in (-HANDLE_OFFSET, HANDLE_OFFSET):
        segments_2d, start_2d, _unused = _handle_path(y_center, HANDLE_LENGTH)

        def point(value):
            return frame.point(x_face + value[0], y_center, value[1])

        segments = []
        for segment in segments_2d:
            if segment[0] == "line":
                segments.append(("line", point(segment[1]), point(segment[2])))
            else:
                segments.append(("arc", point(segment[1]), point(segment[2]),
                                 point(segment[3])))
        builder.add(_swept_round_bar(
            dgn_model, segments, point(start_2d),
            (frame.u[0], frame.u[1], 0.0),
            frame.uor(HANDLE_BAR_DIA / 2.0), COLOR_HANDGRIP,
        ))


def _add_flange_lug(builder, frame, layout, pivot_x, hole_radius, z, color):
    """一只焊在法兰上的吊耳：内块贴法兰边缘，外块（50 宽）承销轴。

    外块上开竖直圆孔（吊杆立柱或铰链销轴穿过）；孔在写入单元前先掏好。
    pivot_x 为销轴/立柱轴线的人孔轴向位置。
    """
    dgn_model = builder.dgn_model
    flange_r = layout["flange_r"]
    y_post = layout["y_post"]
    x_front = layout["x_flange_front"]
    x_back = layout["x_flange_back"]
    x_out = pivot_x + 25.0
    half = LUG_THICKNESS / 2.0
    extension = 2.0

    # 内块：x 落在法兰厚度内，径向压住法兰边缘形成焊接。
    builder.add(_prism_with_holes(
        dgn_model,
        _plate(frame, x_back - 20.0, x_front, flange_r - 45.0,
               y_post + LUG_WIDTH / 2.0, z - half),
        frame.uor(LUG_THICKNESS), color,
    ))
    # 外块：从法兰前面伸到销轴位置，整体位于盖板半径之外。
    hole = (
        frame.point(pivot_x, y_post, z - half - extension),
        frame.point(pivot_x, y_post, z + half + extension),
        frame.uor(hole_radius),
    )
    builder.add(_prism_with_holes(
        dgn_model,
        _plate(frame, x_front, x_out, y_post - LUG_WIDTH / 2.0,
               y_post + LUG_WIDTH / 2.0, z - half),
        frame.uor(LUG_THICKNESS), color, [hole],
    ))


def _add_hinge(builder, frame, resolved, layout):
    """铰链：两只法兰吊耳 + 盖板吊耳（40×22 腰形孔）+ 竖直销轴 + 开口销。"""
    dgn_model = builder.dgn_model
    hole_r = HINGE_PIN_HOLE_DIA / 2.0
    y_post = layout["y_post"]
    x_davit = layout["x_davit"]
    half = LUG_THICKNESS / 2.0
    extension = 2.0

    for z in (LUG_Z, -LUG_Z):
        _add_flange_lug(builder, frame, layout, x_davit, hole_r, z, COLOR_LUG)

    # 盖板吊耳：夹在两只法兰吊耳之间，压在盖板外面，开 40×22 长圆孔。
    # 长圆孔用一个刀具体（两条直边 + 两端半圆），长边沿人孔轴线方向。
    slot_points = []
    for u, v in _obround_profile(SLOT_WIDTH / 2.0, SLOT_LENGTH / 2.0,
                                 SLOT_END_SEGMENTS):
        slot_points.append(frame.point(x_davit + v, y_post + u,
                                       -half - extension))
    slot_points.reverse()          # 换轴后恢复逆时针，法向 +z
    cutter_points = DPoint3dArray()
    for point in slot_points:
        cutter_points.append(point)
    cutter_points.append(cutter_points[0])
    cutter = _prism_with_holes(
        dgn_model, cutter_points, frame.uor(LUG_THICKNESS + 2.0 * extension), None
    )
    builder.add(_prism_with_holes(
        dgn_model,
        _plate(frame, layout["x_cover_front"] - 30.0, x_davit + 25.0,
               layout["cover_r"] - 25.0, y_post + LUG_WIDTH / 2.0, -half),
        frame.uor(LUG_THICKNESS), COLOR_LUG, [], [cutter],
    ))

    pin_half = LUG_Z + half + PIN_EXTENSION
    # 销轴下端的开口销孔（掏在销轴上）。
    cotter_z = -pin_half + 12.0
    pin_hole = (
        frame.point(x_davit, y_post - extension, cotter_z),
        frame.point(x_davit, y_post + extension, cotter_z),
        frame.uor(COTTER_HOLE_DIA / 2.0),
    )
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(x_davit, y_post, -pin_half),
        frame.point(x_davit, y_post, pin_half),
        frame.uor(HINGE_PIN_DIA / 2.0), COLOR_PIN, [pin_hole],
    ))
    builder.add(_cotter_pin(builder, frame, x_davit, y_post, cotter_z, COTTER_DIA))


def _cotter_pin(builder, frame, x, y, z, dia):
    """开口销：一根沿局部 y 的细圆柱。"""
    half = 14.0
    return _solid_cylinder(
        builder.dgn_model,
        frame.point(x, y - half, z), frame.point(x, y + half, z),
        frame.uor(dia / 2.0), COLOR_PIN,
    )


def _flat_head_stations(diameter, flat_length):
    """扁头（长圆孔在正中）各 y 站位：外端 / 矩形端 / 放样圆形端。"""
    y_tip = -flat_length / 2.0
    y_rect = flat_length / 2.0
    y_round = y_rect + diameter * LOFT_LENGTH_FACTOR
    return y_tip, y_rect, y_round


def _add_flat_head(builder, head_frame, flat_width, flat_length, thickness):
    """扁头：flat_width × flat_length × thickness 水平矩形板，正中心裁 40×22 长圆孔。

    长圆孔用**一个**刀具体（两条直边 + 两端半圆的闭合轮廓拉伸而成），因此长边
    是真正的直线；不用几个圆柱相并（那样侧面会出现波浪缺口）。
    """
    dgn_model = builder.dgn_model
    half_width = flat_width / 2.0
    half_thickness = thickness / 2.0
    z0 = -half_thickness
    extension = 2.0
    y_tip = -flat_length / 2.0
    y_rect = flat_length / 2.0

    points = DPoint3dArray()
    for x, y in ((-half_width, y_tip), (half_width, y_tip),
                 (half_width, y_rect), (-half_width, y_rect),
                 (-half_width, y_tip)):
        points.append(head_frame.point(x, y, z0))

    cutter_points = DPoint3dArray()
    for x, y in _obround_profile(SLOT_WIDTH / 2.0, SLOT_LENGTH / 2.0,
                                 SLOT_END_SEGMENTS):
        cutter_points.append(head_frame.point(x, y, z0 - extension))
    cutter_points.append(cutter_points[0])
    cutter = _prism_with_holes(
        dgn_model, cutter_points, head_frame.uor(thickness + 2.0 * extension),
        None,
    )
    builder.add(_prism_with_holes(
        dgn_model, points, head_frame.uor(thickness), COLOR_FLAT,
        cutter_elements=[cutter],
    ))


def _add_loft(builder, head_frame, diameter, flat_width, thickness,
              y_rect, y_round):
    """圆管（ØD）与扁头矩形（flat_width × thickness）之间的放样，长度 1.5 D。

    依次尝试：直纹放样 → BodyFromLoft → 多段台阶近似；末级保证圆管与扁头之间
    一定连上，不会断开。返回实际使用的方式字符串。
    """
    dgn_model = builder.dgn_model
    radius = diameter / 2.0
    half_width = flat_width / 2.0
    half_thickness = thickness / 2.0

    rectangle = _section_curve(head_frame, y_rect, half_width, half_thickness,
                               radius, 0.0)
    circle = _section_curve(head_frame, y_round, half_width, half_thickness,
                            radius, 1.0)

    element, reason = _ruled_sweep_element(dgn_model, rectangle, circle, COLOR_LOFT)
    if element is not None:
        builder.add(element)
        return "ruled"

    element, alternate = _body_from_loft_element(
        dgn_model, [rectangle, circle], COLOR_LOFT
    )
    if element is not None:
        builder.add(element)
        return "loft"

    slices = _morph_slice_elements(dgn_model, head_frame, y_rect, y_round,
                                   half_width, half_thickness, radius, COLOR_LOFT)
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
        % (reason, alternate, len(slices))
    )
    _write_debug_log("直纹放样失败",
                     "ruled: %s\nbody_from_loft: %s\n" % (reason, alternate))
    return "stepped"


def _add_cover_lugs(builder, frame, layout, stud_hole_r):
    """只焊在**盖板（盲法兰）边缘**的两只吊耳，中间穿全螺纹螺柱。

    吊耳是两块竖板（法向沿 y）：下缘埋入盖板顶边（与盖板形成焊接），上缘高出
    盖板顶边、并延伸到盖板外面之前；螺柱孔开在盖板顶边之上。
    """
    dgn_model = builder.dgn_model
    x_back = layout["x_cover_back"] - COVER_LUG_BACK
    x_front = layout["x_cover_front"] + COVER_LUG_FRONT
    z_low = layout["flange_r"] - COVER_LUG_DOWN
    z_high = layout["flange_r"] + COVER_LUG_TOP
    stud_z = layout["stud_z"]
    x_stud = layout["x_davit"]
    half_gap = COVER_LUG_GAP / 2.0
    outline = ((x_back, z_low), (x_front, z_low),
               (x_front, z_high), (x_back, z_high))

    for sign in (-1.0, 1.0):
        # 轮廓在 x-z 平面内逆时针，法向 -y，沿 -y 拉伸：
        # +y 侧从外表面 +33 拉到 +17；-y 侧从 -17 拉到 -33（两侧对称）。
        if sign > 0.0:
            y_face = half_gap + COVER_LUG_THICKNESS
        else:
            y_face = -half_gap
        hole = (
            frame.point(x_stud, sign * (half_gap + COVER_LUG_THICKNESS + 12.0), stud_z),
            frame.point(x_stud, sign * (half_gap - 12.0), stud_z),
            frame.uor(stud_hole_r),
        )
        builder.add(_plate_xz(dgn_model, frame, outline, y_face,
                              COVER_LUG_THICKNESS, COLOR_LUG, [hole]))


def _add_connect_stud(builder, frame, layout):
    """穿过两只盖板吊耳与吊环的全螺纹螺柱，两端各一个螺母（图中 16 DIA）。

    用全螺纹螺柱代替原来的插销：螺柱穿过吊耳销孔与吊环孔，两端螺母夹住，
    图纸的 4 mm 开口销因此取消。
    """
    dgn_model = builder.dgn_model
    x_stud = layout["x_davit"]
    stud_z = layout["stud_z"]
    half_span = COVER_LUG_GAP / 2.0 + COVER_LUG_THICKNESS + STUD_END_LENGTH
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(x_stud, -half_span, stud_z),
        frame.point(x_stud, half_span, stud_z),
        frame.uor(STUD_DIA / 2.0), COLOR_PIN,
    ))

    across_flats = STUD_DIA * NUT_ACROSS_FLATS_FACTOR
    nut_h = STUD_DIA * NUT_HEIGHT_FACTOR
    for sign in (-1.0, 1.0):
        # 轮廓法向 -y、沿 -y 拉伸，因此螺母在螺柱端部的落位左右对称。
        y_plane = sign * half_span if sign > 0.0 else -half_span + nut_h
        builder.add(_prism_with_holes(
            dgn_model,
            _hex_corners_y(frame, x_stud, y_plane, stud_z, across_flats),
            frame.uor(nut_h), COLOR_PIN,
        ))


def _add_adjuster_bolt(builder, frame, resolved, layout):
    """竖向 M20 调节吊环螺栓：下端吊环套在水平销上，杆穿过扁头长圆孔，双螺母压紧。

    形状与参数照 `eye_bolt_only.py`：孔心为原点、孔轴为局部 Y（这里正好是水平
    销方向），圆环中心线半径 = 孔半径 + 圆钢半径，颈弯 R30 与圆环外切，杆顶到
    孔心 200，螺纹段 100 MIN。拧双螺母即可调节扁头（吊杆）相对盖板的高度。
    """
    dgn_model = builder.dgn_model
    bar_r = EYE_BOLT_DIA / 2.0
    eye_r = EYE_BOLT_HOLE_DIA / 2.0 + bar_r
    bend_r = EYE_BOLT_BEND_RADIUS
    neck_h = sqrt((bend_r + eye_r) ** 2 - bend_r ** 2)
    neck_angle = atan2(neck_h, bend_r)
    thread_start = EYE_BOLT_TOP_HEIGHT - EYE_BOLT_THREAD_LENGTH
    if thread_start <= neck_h:
        raise ValueError("吊环螺栓螺纹起点必须高于颈弯切点，请加大 200 或减小 R30。")
    x_davit = layout["x_davit"]
    z0 = layout["stud_z"]
    u = frame.u

    # 吊环：圆环，孔轴沿局部 y（水平销方向）。
    ring = _torus_element(
        dgn_model, frame.point(x_davit, 0.0, z0),
        DVec3d.From(u[0], u[1], 0.0), DVec3d.From(0.0, 0.0, 1.0),
        frame.uor(eye_r), frame.uor(bar_r), 2.0 * pi,
    )
    if ring is not None:
        _apply_color(ring, COLOR_EYE_BOLT)
        builder.add(ring)

    # 颈弯：与圆环外切，向下弯到杆轴。
    neck = _torus_element(
        dgn_model, frame.point(x_davit - bend_r, 0.0, z0 + neck_h),
        DVec3d.From(u[0], u[1], 0.0), DVec3d.From(0.0, 0.0, -1.0),
        frame.uor(bend_r), frame.uor(bar_r), neck_angle,
    )
    if neck is not None:
        _apply_color(neck, COLOR_EYE_BOLT)
        builder.add(neck)

    # 光杆 + 螺纹包络（两段圆柱，端面标记螺纹起点）。
    for bottom, top in ((neck_h, thread_start),
                        (thread_start, EYE_BOLT_TOP_HEIGHT)):
        builder.add(_solid_cylinder(
            dgn_model, frame.point(x_davit, 0.0, z0 + bottom),
            frame.point(x_davit, 0.0, z0 + top),
            frame.uor(bar_r), COLOR_EYE_BOLT,
        ))

    # 扁头上的 2 个螺母 + 垫圈（压在扁头上面，拧动即可调节高度）。
    across_flats = EYE_BOLT_DIA * NUT_ACROSS_FLATS_FACTOR
    nut_h = EYE_BOLT_DIA * NUT_HEIGHT_FACTOR
    washer_od = EYE_BOLT_DIA * WASHER_OD_FACTOR
    z = layout["z_arm"] + layout["flat_thickness"] / 2.0
    for _ in range(EYE_BOLT_NUT_COUNT):
        builder.add(_solid_cylinder(
            dgn_model, frame.point(x_davit, 0.0, z),
            frame.point(x_davit, 0.0, z + WASHER_THICKNESS),
            frame.uor(washer_od / 2.0), COLOR_EYE_BOLT,
        ))
        z += WASHER_THICKNESS
        builder.add(_prism_with_holes(
            dgn_model, _hex_corners_z(frame, x_davit, 0.0, z, across_flats),
            frame.uor(nut_h), COLOR_EYE_BOLT,
        ))
        z += nut_h


def _davit_support_layout(davit_dia, flange_edge_thickness):
    """回转支撑件的局部尺寸；sx 沿自由端到背板，sy 沿人孔轴向。"""
    width = davit_dia + 30.0
    length = 25.0 + davit_dia + 20.0
    hole_sx = 25.0 + davit_dia / 2.0
    if not 0.0 < flange_edge_thickness < width:
        raise ValueError("吊杆支撑件要求 0 < 法兰边缘厚度 < D+30。")
    chamfer_inset = (width - flange_edge_thickness) / 2.0
    chamfer_distance = chamfer_inset * (sin(radians(60.0)) / cos(radians(60.0)))
    if chamfer_distance >= length - DAVIT_SUPPORT_INNER_RADIUS:
        raise ValueError("吊杆支撑件端部倒角过长，已进入背部圆角区域。")
    return {
        "width": width,
        "length": length,
        "hole_sx": hole_sx,
        "hole_dia": davit_dia + DAVIT_HOLE_CLEARANCE,
        "flange_edge_thickness": flange_edge_thickness,
        "chamfer_inset": chamfer_inset,
        "chamfer_distance": chamfer_distance,
        "chamfer_angle": radians(DAVIT_SUPPORT_CHAMFER_ANGLE),
    }


def _support_blend_targets(spec):
    """扫掠毛坯中需要倒圆的四条横棱：外 R20 两条、内 R10 两条。"""
    length = spec["length"]
    width = spec["width"]
    thick = DAVIT_SUPPORT_THICKNESS
    height = DAVIT_SUPPORT_CLEAR_HEIGHT
    return [
        ((length + thick, -width / 2.0, -thick),
         (length + thick, width / 2.0, -thick), DAVIT_SUPPORT_OUTER_RADIUS),
        ((length + thick, -width / 2.0, height + thick),
         (length + thick, width / 2.0, height + thick), DAVIT_SUPPORT_OUTER_RADIUS),
        ((length, -width / 2.0, 0.0),
         (length, width / 2.0, 0.0), DAVIT_SUPPORT_INNER_RADIUS),
        ((length, -width / 2.0, height),
         (length, width / 2.0, height), DAVIT_SUPPORT_INNER_RADIUS),
    ]


def _support_edge_at(solid, start, end, tolerance):
    """按几何端点定位实体棱，避免依赖不稳定的内核边序号。"""
    edges = ISubEntityPtrArray()
    SolidUtil.GetBodyEdges(edges, solid)

    def close(a, b):
        return hypot(hypot(a.x - b.x, a.y - b.y), a.z - b.z) <= tolerance

    matches = []
    for edge in edges:
        vertices = ISubEntityPtrArray()
        if not _succeeded(SolidUtil.GetEdgeVertices(vertices, edge)) or len(vertices) != 2:
            continue
        a = DPoint3d.From(0.0, 0.0, 0.0)
        b = DPoint3d.From(0.0, 0.0, 0.0)
        if not _succeeded(SolidUtil.EvaluateVertex(vertices[0], a)):
            continue
        if not _succeeded(SolidUtil.EvaluateVertex(vertices[1], b)):
            continue
        matched = ((close(a, start) and close(b, end)) or
                   (close(a, end) and close(b, start)))
        if not matched:
            transform = solid.GetEntityTransform()
            transform.Multiply(a)
            transform.Multiply(b)
            matched = ((close(a, start) and close(b, end)) or
                       (close(a, end) and close(b, start)))
        if matched:
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError("吊杆支撑件预期找到 1 条圆角棱，实际找到 %d 条。" % len(matches))
    return matches[0]


def _support_chamfer_polygons(spec):
    """端部两侧倒角刀具；斜边由距离公式和30度角精确定义。"""
    extension = 2.0
    slope = sin(spec["chamfer_angle"]) / cos(spec["chamfer_angle"])
    nose = spec["flange_edge_thickness"] / 2.0
    half = spec["width"] / 2.0
    polygons = []
    for sign in (-1.0, 1.0):
        vertices = [
            (-extension, sign * (nose - extension * slope)),
            (spec["chamfer_distance"] + extension / slope,
             sign * (half + extension)),
            (-extension, sign * (half + extension)),
        ]
        if sign < 0.0:
            vertices.reverse()
        polygons.append(tuple(vertices + [vertices[0]]))
    return polygons


def _add_davit_pivot_support(builder, frame, resolved, layout):
    """矩形截面沿 ] 路径扫掠、钻双孔、R20/R10 圆角及30度端部倒角。"""
    dgn_model = builder.dgn_model
    model_ref = ISessionMgr.ActiveDgnModelRef
    diameter = resolved["dims"]["davit_dia"]
    spec = _davit_support_layout(diameter, resolved["dims"]["flange_t"])
    width = spec["width"]
    length = spec["length"]
    thick = DAVIT_SUPPORT_THICKNESS
    height = DAVIT_SUPPORT_CLEAR_HEIGHT
    x_post = layout["x_davit"]
    y_post = layout["y_post"]
    z_start = -height / 2.0
    # sx=hole_sx 落在吊杆轴线上；+sx 从自由端走向法兰/背板。
    y_start = y_post + spec["hole_sx"]

    def point(local):
        sx, sy, sz = local
        return frame.point(x_post + sy, y_start - sx, z_start + sz)

    profile_points = DPoint3dArray()
    for local in ((0.0, -width / 2.0, -thick),
                  (0.0, width / 2.0, -thick),
                  (0.0, width / 2.0, 0.0),
                  (0.0, -width / 2.0, 0.0),
                  (0.0, -width / 2.0, -thick)):
        profile_points.append(point(local))
    profile = EditElementHandle()
    if not _succeeded(ShapeHandler.CreateShapeElement(
            profile, None, profile_points, model_ref.Is3d(), model_ref)):
        raise RuntimeError("无法创建吊杆支撑件矩形截面。")
    profile_vector = ICurvePathQuery.ElementToCurveVector(profile)
    if profile_vector is None:
        raise RuntimeError("无法读取吊杆支撑件矩形截面。")

    path_locals = ((0.0, 0.0, 0.0), (length, 0.0, 0.0),
                   (length, 0.0, height), (0.0, 0.0, height))
    path = EditElementHandle()
    status = ChainHeaderHandler.CreateChainHeaderElement(
        path, None, False, model_ref.Is3d(), model_ref)
    if status is not None and not _succeeded(status):
        raise RuntimeError("无法创建吊杆支撑件扫掠路径。")
    for start, end in zip(path_locals, path_locals[1:]):
        component = _line_component(point(start), point(end))
        if component is None:
            raise RuntimeError("无法创建吊杆支撑件路径线段。")
        ChainHeaderHandler.AddComponentElement(path, component)
    ChainHeaderHandler.AddComponentComplete(path)
    path_vector = ICurvePathQuery.ElementToCurveVector(path)
    if path_vector is None:
        raise RuntimeError("无法读取吊杆支撑件扫掠路径。")
    solid = _body_from_sweep(profile_vector, path_vector, model_ref,
                             point(path_locals[0]))

    # 一根刀具同时贯穿上下水平板，孔轴与吊杆立柱严格重合。
    extension = 2.0
    cutter = _cylinder_body(
        dgn_model,
        frame.point(x_post, y_post, z_start - thick - extension),
        frame.point(x_post, y_post, z_start + height + thick + extension),
        frame.uor(spec["hole_dia"] / 2.0),
    )
    tools = ISolidKernelEntityPtrArray()
    tools.append(cutter)
    if not _succeeded(SolidUtil.Modify.BooleanSubtract(solid, tools)):
        raise RuntimeError("吊杆支撑件 Ø(D+3) 双孔加工失败。")

    # 扫掠后倒圆：外侧 R20、内侧 R10。
    edges = ISubEntityPtrArray()
    radii = DoubleArray()
    tolerance = max(frame.uor(1.0e-4), 1.0e-7)
    for start, end, radius in _support_blend_targets(spec):
        edges.append(_support_edge_at(solid, point(start), point(end), tolerance))
        radii.append(frame.uor(radius))
    if not _succeeded(SolidUtil.Modify.BlendEdges(solid, edges, radii, False)):
        raise RuntimeError("吊杆支撑件外 R20 / 内 R10 圆角失败。")

    # 端部倒角用精确平面刀具完成：沿板长距离 c，角度30度，端宽=法兰厚度。
    chamfer_tools = ISolidKernelEntityPtrArray()
    cutter_z0 = -thick - extension
    cutter_height = height + 2.0 * thick + 2.0 * extension
    for polygon in _support_chamfer_polygons(spec):
        points = DPoint3dArray()
        for sx, sy in polygon:
            points.append(point((sx, sy, cutter_z0)))
        chamfer_element = _prism_with_holes(
            dgn_model, points, frame.uor(cutter_height), None)
        if chamfer_element is None:
            raise RuntimeError("无法创建吊杆支撑件端部倒角刀具。")
        status, chamfer_body = SolidUtil.Convert.ElementToBody(
            chamfer_element, True, True, False)
        if not _succeeded(status) or chamfer_body is None:
            raise RuntimeError("无法转换吊杆支撑件端部倒角刀具。")
        chamfer_tools.append(chamfer_body)
    if not _succeeded(SolidUtil.Modify.BooleanSubtract(solid, chamfer_tools)):
        raise RuntimeError("吊杆支撑件30度端部倒角失败。")

    finished = _element_from_body(dgn_model, solid, path, COLOR_LUG)
    if finished is None:
        raise RuntimeError("无法生成吊杆一体回转支撑件实体。")
    builder.add(finished)


def _add_davit(builder, frame, resolved, layout):
    """吊杆：法兰回转吊耳 + 立柱 + R220 弯臂 + 扁头 + 放样 + 盖板顶部连接。

    与之前不同：扁头（臂末端）落在**盖板顶部**，水平销与 M20 调节吊环螺栓也在
    盖板顶边之上，法兰吊耳从法兰边缘伸上来承接，不再落到盖板中心。
    """
    dgn_model = builder.dgn_model
    davit_dia = resolved["dims"]["davit_dia"]
    hole_r = (davit_dia + DAVIT_HOLE_CLEARANCE) / 2.0
    x_bar = layout["x_davit"]
    y_post = layout["y_post"]
    z_arm = layout["z_arm"]
    z_top = layout["z_post_top"]
    thickness = layout["flat_thickness"]
    flat_length = FLAT_HEAD_LENGTH
    _y_tip, y_rect, y_round = _flat_head_stations(davit_dia, flat_length)

    # 1) 一体扫掠回转支撑件：上下孔同轴，吊杆从中穿过并可绕轴线回转。
    _add_davit_pivot_support(builder, frame, resolved, layout)

    # 2) 立柱 + 下端开口销。
    support_lower_top = -DAVIT_SUPPORT_CLEAR_HEIGHT / 2.0
    support_lower_bottom = support_lower_top - DAVIT_SUPPORT_THICKNESS
    post_bottom = support_lower_bottom - DAVIT_SUPPORT_END_BELOW
    cotter_z = post_bottom + DAVIT_SUPPORT_COTTER_FROM_END
    post_hole = (
        frame.point(x_bar, y_post - 2.0, cotter_z),
        frame.point(x_bar, y_post + 2.0, cotter_z),
        frame.uor(DAVIT_COTTER_HOLE_DIA / 2.0),
    )
    builder.add(_solid_cylinder(
        dgn_model,
        frame.point(x_bar, y_post, post_bottom),
        frame.point(x_bar, y_post, z_top),
        frame.uor(davit_dia / 2.0), COLOR_DAVIT, [post_hole],
    ))
    builder.add(_cotter_pin(builder, frame, x_bar, y_post, cotter_z,
                            DAVIT_COTTER_DIA))

    # 3) R220 弯头：竖直 → 水平（真圆弧）。
    bend_y = y_post - DAVIT_BEND_RADIUS
    bend = _torus_element(
        dgn_model, frame.point(x_bar, bend_y, z_arm - DAVIT_BEND_RADIUS),
        DVec3d.From(frame.v[0], frame.v[1], 0.0), DVec3d.From(0.0, 0.0, 1.0),
        frame.uor(DAVIT_BEND_RADIUS), frame.uor(davit_dia / 2.0), pi / 2.0,
    )
    if bend is not None:
        _apply_color(bend, COLOR_DAVIT)
        builder.add(bend)

    # 4) 扁头 + 圆→矩形放样 + 水平臂（在平移后的子坐标系里建，落到盖板顶部）。
    head_frame = frame.offset(x_bar, 0.0, z_arm)
    _add_flat_head(builder, head_frame, FLAT_HEAD_WIDTH, flat_length, thickness)
    loft_mode = _add_loft(builder, head_frame, davit_dia, FLAT_HEAD_WIDTH,
                          thickness, y_rect, y_round)
    builder.add(_solid_cylinder(
        dgn_model, head_frame.point(0.0, bend_y, 0.0),
        head_frame.point(0.0, y_round, 0.0),
        frame.uor(davit_dia / 2.0), COLOR_DAVIT,
    ))

    # 5) 盖板顶部连接：法兰吊耳 + 水平销 + 竖向 M20 调节吊环螺栓 + 双螺母。
    _add_cover_lugs(builder, frame, layout, (STUD_DIA + STUD_HOLE_CLEARANCE) / 2.0)
    _add_connect_stud(builder, frame, layout)
    _add_adjuster_bolt(builder, frame, resolved, layout)
    return loft_mode


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _ManholeCellBuilder(object):
    """收集人孔子元素，全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model):
        self.dgn_model = dgn_model
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        # Bentley 此创建函数返回 None；后续 AddChildElement/AddChildComplete
        # 的状态值用于判断单元构造是否成功。
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, CELL_NAME, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError("人孔子元素创建失败。")
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError("无法将人孔子元素加入单元。")
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError("无法完成人孔单元。")
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError("无法将人孔单元写入活动模型。")
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


def _build_manhole_cell(placement_point, options=None):
    """构建人孔单元但**不写入模型**，返回 (builder, 统计字典)。"""
    active_model_ref = ISessionMgr.ActiveDgnModelRef
    dgn_model = active_model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError("请先激活一个 3D DGN 模型，再运行罐壁人孔工具。")
    if placement_point is None:
        raise ValueError("请先在模型中点取罐壁上的放置点。")

    resolved = _resolve_options(options)
    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    heading = resolved["heading_deg"] + (180.0 if resolved["mirrored"] else 0.0)
    frame = _ManholeFrame(_copy_dpoint(placement_point), uor_per_mm, heading)
    layout = _manway_layout(resolved["dims"])

    builder = _ManholeCellBuilder(dgn_model)
    _add_manway(builder, frame, resolved, layout)
    loft_mode = None
    if resolved["include_lifting"]:
        if resolved["mode"] == "hinge":
            _add_hinge(builder, frame, resolved, layout)
        else:
            loft_mode = _add_davit(builder, frame, resolved, layout)

    builder.build()
    result = {
        "child_count": builder.child_count,
        "nominal_size": resolved["nominal_size"],
        "rating": resolved["rating"],
        "mode": resolved["mode"],
        "davit_dia": resolved["dims"]["davit_dia"],
        "bolt_count": resolved["dims"]["bolt_count"] if resolved["include_bolts"] else 0,
        "heading_deg": heading,
        "neck_length": resolved["neck_length"],
        "lifting": bool(resolved["include_lifting"]),
        "bolts": bool(resolved["include_bolts"]),
        "loft": loft_mode,
        "warnings": list(builder.warnings),
    }
    return builder, result


def draw_tank_wall_manhole(placement_point, options=None):
    """在给定位置创建整组罐壁人孔，返回统计字典。"""
    builder, result = _build_manhole_cell(placement_point, options)
    builder.commit()
    return result


def replace_tank_wall_manhole(placement_point, options, previous_handle):
    """重建人孔：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_manhole_cell(placement_point, options)
    new_handle = builder.commit()
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def describe_spec(nominal_size, rating, mode):
    """面板信息行用的规格说明。"""
    dims = MANWAY_TABLE[int(nominal_size)]
    davit = DAVIT_DIA_TABLE[int(nominal_size)][int(rating)]
    return (
        "%d\" / ASA %d lbs：筒节 φ%.0f、法兰 φ%.0f×%.0f、盖板 φ%.0f×%.0f、"
        "螺栓 %d×M%.0f；%s φ%.0f"
        % (
            int(nominal_size), int(rating),
            dims["neck_od"], dims["flange_od"], dims["flange_t"],
            dims["flange_od"], dims["cover_t"],
            dims["bolt_count"], dims["bolt_dia"],
            "吊杆" if mode == "davit" else "铰链销轴", davit,
        )
    )


# ---------------------------------------------------------------------------
# MicroStation 工具面板
# ---------------------------------------------------------------------------


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


class _ManholeSettingsDialog(_MicroStationTk):
    """尺寸/形式选择、预览 / 确定 / 取消界面。"""

    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("罐壁人孔")
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
            text="在模型中点取罐壁外表面上的人孔中心点；点取位置的 Z 即该点标高。",
            justify="left", fg="#333333", wraplength=400,
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        tk.Label(body, text="公称尺寸：").grid(row=1, column=0, pady=(10, 0), sticky="w")
        self.size_var = tk.StringVar(value="20")
        for index, size in enumerate(("18", "20", "24")):
            tk.Radiobutton(
                body, text='%s"' % size, variable=self.size_var, value=size,
                command=self.on_options_changed,
            ).grid(row=1, column=1 + index, pady=(10, 0), sticky="w")

        tk.Label(body, text="压力等级：").grid(row=2, column=0, pady=(6, 0), sticky="w")
        self.rating_var = tk.StringVar(value="150")
        for index, rating in enumerate(("150", "300", "600")):
            tk.Radiobutton(
                body, text="ASA %s" % rating, variable=self.rating_var,
                value=rating, command=self.on_options_changed,
            ).grid(row=2, column=1 + index, pady=(6, 0), sticky="w")

        tk.Label(body, text="连接形式：").grid(row=3, column=0, pady=(6, 0), sticky="w")
        self.mode_var = tk.StringVar(value="davit")
        tk.Radiobutton(
            body, text="吊杆 davit", variable=self.mode_var, value="davit",
            command=self.on_options_changed,
        ).grid(row=3, column=1, pady=(6, 0), sticky="w")
        tk.Radiobutton(
            body, text="铰链 hinge", variable=self.mode_var, value="hinge",
            command=self.on_options_changed,
        ).grid(row=3, column=2, pady=(6, 0), sticky="w")

        tk.Label(body, text="朝向：").grid(row=4, column=0, pady=(6, 0), sticky="w")
        self.heading_var = tk.StringVar(value="0")
        tk.Entry(body, textvariable=self.heading_var, width=10).grid(
            row=4, column=1, pady=(6, 0), sticky="w")
        tk.Label(body, text="°（0° 沿 +X，逆时针为正）").grid(
            row=4, column=2, columnspan=2, pady=(6, 0), sticky="w")
        self.heading_var.trace_add("write", self.on_entry_changed)

        tk.Label(body, text="筒节长度：").grid(row=5, column=0, pady=(6, 0), sticky="w")
        self.neck_var = tk.StringVar(value="%.0f" % NECK_LENGTH_DEFAULT)
        tk.Entry(body, textvariable=self.neck_var, width=10).grid(
            row=5, column=1, pady=(6, 0), sticky="w")
        tk.Label(body, text="mm（罐壁外表面到法兰背面）").grid(
            row=5, column=2, columnspan=2, pady=(6, 0), sticky="w")
        self.neck_var.trace_add("write", self.on_entry_changed)

        self.mirror_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body, text="反向（人孔轴线转 180°）", variable=self.mirror_var,
            command=self.on_options_changed,
        ).grid(row=6, column=0, columnspan=4, pady=(6, 0), sticky="w")

        self.bolts_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            body, text="生成法兰螺栓与螺母", variable=self.bolts_var,
            command=self.on_options_changed,
        ).grid(row=7, column=0, columnspan=4, pady=(2, 0), sticky="w")

        self.lifting_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            body, text="生成铰链 / 吊杆及盖板吊耳、吊环螺栓",
            variable=self.lifting_var, command=self.on_options_changed,
        ).grid(row=8, column=0, columnspan=4, pady=(2, 0), sticky="w")

        self.spec_label = tk.Label(
            body, text=describe_spec(20, 150, "davit"),
            justify="left", fg="#333333", wraplength=400,
        )
        self.spec_label.grid(row=9, column=0, columnspan=4, pady=(10, 0), sticky="w")

        self.preview_info_label = tk.Label(
            body, text="预览：—", justify="left", fg="#333333", wraplength=400,
        )
        self.preview_info_label.grid(row=10, column=0, columnspan=4, sticky="w")

        self.status_label = tk.Label(
            body, text="请在模型中点取人孔中心点；点取后可改选项，预览会自动重建。",
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
            if isinstance(child, (tk.Radiobutton, tk.Checkbutton, tk.Entry)):
                self.option_widgets.append(child)
        self.action_widgets = [confirm_button, cancel_button]

    def current_options(self):
        try:
            heading = float(self.heading_var.get())
        except (TypeError, ValueError):
            raise ValueError("朝向必须是数字（度）。")
        try:
            neck_length = float(self.neck_var.get())
        except (TypeError, ValueError):
            raise ValueError("筒节长度必须是数字（mm）。")
        return {
            "nominal_size": int(self.size_var.get()),
            "rating": int(self.rating_var.get()),
            "mode": self.mode_var.get(),
            "heading_deg": heading,
            "neck_length": neck_length,
            "mirrored": bool(self.mirror_var.get()),
            "include_bolts": bool(self.bolts_var.get()),
            "include_lifting": bool(self.lifting_var.get()),
        }

    def set_status(self, message, is_error=False):
        self.status_label.configure(
            text=message, fg="#b42318" if is_error else "#1f5f99"
        )
        self.update_idletasks()

    def set_result(self, result):
        self.preview_info_label.configure(
            text="预览：%d\" / ASA %d lbs，%s（φ%.0f），螺栓 %d 颗，共 %d 个子元素" % (
                result["nominal_size"], result["rating"],
                "吊杆" if result["mode"] == "davit" else "铰链",
                result["davit_dia"], result["bolt_count"], result["child_count"],
            )
        )

    def refresh_spec(self):
        try:
            self.spec_label.configure(text=describe_spec(
                int(self.size_var.get()), int(self.rating_var.get()),
                self.mode_var.get(),
            ))
        except (TypeError, ValueError):
            self.spec_label.configure(text="规格有误。")

    def _set_busy(self, busy):
        state = tk.DISABLED if busy else tk.NORMAL
        for widget in self.option_widgets + self.action_widgets:
            widget.configure(state=state)
        self.update_idletasks()

    def on_entry_changed(self, *_unused):
        self.on_options_changed()

    def on_options_changed(self):
        self.refresh_spec()
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
        """按当前选项重建预览：先建新的一版，成功后再删掉旧的。"""
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
        self.set_status("正在生成人孔预览，请稍候……")
        try:
            handle, result, deleted = replace_tank_wall_manhole(
                self.placement_point, options, self.preview_handle
            )
        except Exception as error:
            message = "人孔生成失败：%s" % error
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
            "预览已更新：%d\" / ASA %d lbs，%s φ%.0f，共 %d 个子元素。%s"
            "改选项会自动重建；点【确定】保留，点【取消】放弃。"
            % (
                result["nominal_size"], result["rating"],
                "吊杆" if result["mode"] == "davit" else "铰链",
                result["davit_dia"], result["child_count"],
                "已替换上一版预览。" if deleted else "",
            )
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


class TankWallManholePlacementTool(DgnPrimitiveTool):
    """点取罐壁上的人孔中心点并放置罐壁人孔的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString("TankWallManholePlacementTool")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            "请点取罐壁上的人孔中心点；点取后可改尺寸/形式，预览会自动重建，"
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
            tool_settings if tool_settings is not None else _ManholeSettingsDialog()
        )
        tool = TankWallManholePlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    TankWallManholePlacementTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
