# -*- coding: utf-8 -*-
"""沿用户选择的一条“竖直线”创建墙面爬梯（第一版）。

约定
----
所选竖直线同时代表：
* 墙面（Face of Concrete）；以及
* 爬梯正中心在墙面上的投影线。

因此爬梯位于该线所在竖直平面、并向“出梯方向”一侧伸出：
* 两根立柱（Ladder Stile）为扁钢，中心线距墙面 ``STANDOFF_FROM_WALL``（默认 220）；
* 立柱扁钢规格按支架跨距自动选型（75x12 / 75x16 / 75x20）；
* 横担（Rung）为 φ24 圆钢，两端各突出立柱外侧面 ``RUNG_PROTRUSION``（默认 10）；
* 最低一节横担距竖直线最低点 ``FIRST_RUNG_HEIGHT``（默认 400），其余横担间距
  在 250（首选下限）～300 之间自动分配；
* 中间支架为 **75×10 角钢**（长度沿出梯方向从墙面伸到立柱前缘，开口向外，
  一肢背靠背贴立柱），墙端焊一块贴墙钢板；最低点、最高点均不设支架。
  支架沿高度按 ``BRACKET_SPACING``（默认 1500）在两端之间排布。

本脚本把纯几何（可在无 MicroStation 环境下自检）与 Bentley 实体创建分离。
面向 Bentley Power Platform Python (MSPy)。
"""

from __future__ import print_function

from math import ceil, cos, floor, hypot, pi, sin
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


# --- 尺寸与默认值（mm）------------------------------------------------------
RUNG_DIAMETER = 24.0
STANDOFF_FROM_WALL = 220.0
LADDER_WIDTH = 400.0
RUNG_PROTRUSION = 10.0
FIRST_RUNG_HEIGHT = 400.0
RUNG_MIN_SPACING = 250.0
RUNG_MAX_SPACING = 300.0
# 最顶部一节横担低于立柱顶端的高度（立柱比最顶踏步高出这么多，踏步不冒出立柱）。
TOP_RUNG_CLEARANCE = 50.0
# 平台以上立柱与护笼的延长量（标准 5.2.6：顶部超出平台 1.2 m 以上）；该段不设踏步。
TOP_EXTENSION = 1200.0

BRACKET_SPACING = 1500.0
# 中间支架：75x10 角钢，长度水平（墙面 → 立柱），开口向外，一肢背靠背贴立柱。
BRACKET_ANGLE_LEG = 75.0
BRACKET_ANGLE_THICKNESS = 10.0
# 墙端贴墙钢板（只建板，不建螺栓）。
WALL_PLATE_WIDTH = 100.0
WALL_PLATE_HEIGHT = 100.0
WALL_PLATE_THICKNESS = 10.0

# --- 防护围栏（护笼，单位 mm）----------------------------------------------
CAGE_ENABLED = True
# 护笼半宽（＝端头圆头半径，图纸 R355）；两侧直段中心线在 t = ±CAGE_HALF_WIDTH。
CAGE_HALF_WIDTH = 355.0
# 端头回环（绕立柱，水平面）：自立柱几何中心起算。
CAGE_TAB_INWARD = 60.0      # 沿 t 向梯子中心
CAGE_HOOK_N_INWARD = 105.0  # 沿 n 向墙面
# 立柱中心 → 直段末端（弯起点）。
CAGE_STRAIGHT_END_OFFSET = 410.0
# 环的竖向布置。
CAGE_HOOP_FIRST_Z = 2000.0
CAGE_HOOP_SPACING = 1500.0
# 环扁钢（宽面竖直）。
CAGE_HOOP_FLAT_WIDTH = 50.0
CAGE_HOOP_FLAT_THICKNESS = 5.0
# 环间竖杆（沿护笼外圈均布）。
CAGE_BAR_COUNT = 11
CAGE_BAR_FLAT_WIDTH = 30.0
CAGE_BAR_FLAT_THICKNESS = 5.0
# 最顶环两侧的倒 L 拉结（固定到平台/屋面/设备面）：竖段在 n=CAGE_TOP_HOOK_N 处
# 自平台面立起，顶部朝 +n 折到顶环近侧直段（路径 n_hook）。截面同环扁钢。
CAGE_TOP_HOOK = True
CAGE_TOP_HOOK_N = -700.0

# Ladder Stile 选型表：(MAX SUPPORT CENTRES mm, 扁钢宽 mm, 扁钢厚 mm)
STILE_FLAT_TABLE = (
    (4500.0, 75.0, 12.0),
    (5500.0, 75.0, 16.0),
    (6000.0, 75.0, 20.0),
)

COLOR_RGB = (255, 204, 0)
PATH_TOLERANCE_MM = 1.0e-6
VERTICAL_TOLERANCE_MM = 5.0
REGENERATE_DELAY_MS = 150
# 确认后爬梯、护笼分别组成一个普通单元。
LADDER_CELL_NAME = "WALL_LADDER"
CAGE_CELL_NAME = "WALL_LADDER_CAGE"


# ============================================================================
# 纯几何（无 Bentley 依赖，可被 _wall_ladder_selftest.py 抽取运行）
# ============================================================================

def select_stile_flat(span_mm):
    """按支架跨距（mm）选择立柱扁钢，返回 (宽, 厚)。

    映射：<=4500 → 75x12；<=5500 → 75x16；<=6000 → 75x20。
    """
    if span_mm <= 0.0:
        raise ValueError("支架跨距必须大于零。")
    for max_span, width, thickness in STILE_FLAT_TABLE:
        if span_mm <= max_span + 1.0e-6:
            return (width, thickness)
    raise ValueError(
        "支架跨距 %.0f mm 超过 75x20 扁钢的 6000 mm 上限，请增设中间支承。" % span_mm
    )


def compute_rung_levels(height_mm, first_mm=FIRST_RUNG_HEIGHT,
                        min_spacing_mm=RUNG_MIN_SPACING,
                        max_spacing_mm=RUNG_MAX_SPACING,
                        top_clearance_mm=TOP_RUNG_CLEARANCE):
    """返回横担中心相对竖直线最低点的高度列表（mm）。

    最低一节固定在 ``first_mm``；其余间距优先落在 [min_spacing, max_spacing]，
    最高一节停在 ``height_mm - top_clearance_mm``（立柱顶端之上不再有踏步）。
    高度不足以再放一节时，只返回最低一节。
    """
    if min_spacing_mm <= 0.0 or max_spacing_mm < min_spacing_mm:
        raise ValueError("横担间距上下限无效。")
    effective_top = height_mm - top_clearance_mm
    if effective_top < first_mm - 1.0e-9:
        return []
    available = effective_top - first_mm
    if available < min_spacing_mm - 1.0e-9:
        return [first_mm]

    # n 为区间数：n 大 → 间距小。n_lo 保证间距 <= max，n_hi 保证间距 >= min。
    n_lo = max(1, int(ceil(available / max_spacing_mm - 1.0e-9)))
    n_hi = int(floor(available / min_spacing_mm + 1.0e-9))
    if n_lo <= n_hi:
        n = n_lo
    else:
        # 短爬梯可能出现无解区间（n_lo = n_hi + 1）：取越界更小的那一种。
        spacing_lo = available / n_lo
        spacing_hi = available / n_hi
        violation_lo = max(0.0, min_spacing_mm - spacing_lo)
        violation_hi = max(0.0, spacing_hi - max_spacing_mm)
        n = n_lo if violation_lo <= violation_hi else n_hi
        n = max(1, n)
    spacing = available / n
    return [first_mm + index * spacing for index in range(n + 1)]


def compute_bracket_levels(height_mm, spacing_mm=BRACKET_SPACING):
    """返回中间支架高度列表（mm）。

    只返回**中间**支架：最低点直接固定到地面、最高点与顶部平台连接，
    因此两端都不设中间支架（第一处从 ``spacing_mm`` 起，最后严格小于顶高）。
    """
    if spacing_mm <= 0.0:
        raise ValueError("支架间距必须大于零。")
    if height_mm <= 0.0:
        return []
    levels = []
    level = spacing_mm
    while level < height_mm - 1.0e-9:
        levels.append(level)
        level += spacing_mm
    return levels


def compute_cage_hoop_rungs(rung_levels, first_z=CAGE_HOOP_FIRST_Z,
                            max_spacing=CAGE_HOOP_SPACING):
    """选择护笼环所吸附的踏步标高（mm）。

    最低环吸附到离 ``first_z`` 最近的踏步；其余环在“相邻环间距不超过
    ``max_spacing``（最大值）”的前提下，尽量取更远的踏步（环数最少）。
    """
    if max_spacing <= 0.0:
        raise ValueError("护笼环最大间距必须大于零。")
    levels = sorted(rung_levels)
    if not levels:
        return []
    start = min(range(len(levels)), key=lambda index: abs(levels[index] - first_z))
    chosen = [levels[start]]
    index = start
    while True:
        advance = None
        for candidate in range(index + 1, len(levels)):
            if levels[candidate] - chosen[-1] <= max_spacing + 1.0e-9:
                advance = candidate
            else:
                break
        if advance is None:
            break
        index = advance
        chosen.append(levels[index])
    return chosen


def build_cage_hoop_path(width_mm, standoff_mm=STANDOFF_FROM_WALL,
                         half_width_mm=CAGE_HALF_WIDTH,
                         tab_inward_mm=CAGE_TAB_INWARD,
                         hook_n_inward_mm=CAGE_HOOK_N_INWARD,
                         straight_offset_mm=CAGE_STRAIGHT_END_OFFSET,
                         end_radius_mm=None):
    """构造护笼环的平面路径（局部 n=出梯、t=宽度，单位 mm）。

    路径为对称的 11 点折线（10 段），默认参数下各关键点为：

        (220,  200) 立柱几何中心
        (220,  140) 沿 t 往梯子中心 60
        (115,  140) 沿 n 往墙面 105
        (115,  355) 沿 t 向外到护笼半宽
        (630,  355) 沿 n 到直段末端（弯起点）
        (985,    0) 圆头顶点（630 + 355）
        (630, -355) 对称回位
        (115, -355)
        (115, -140)
        (220, -140)
        (220, -200) 另一立柱几何中心

    圆头为两段 90° 圆弧，半径 ``end_radius_mm``（默认＝护笼半宽）。
    """
    if width_mm <= 0.0:
        raise ValueError("梯宽必须大于零。")
    if half_width_mm <= 0.0 or tab_inward_mm < 0.0 or hook_n_inward_mm < 0.0:
        raise ValueError("护笼半宽、端头内伸必须为非负。")
    if end_radius_mm is None:
        end_radius_mm = half_width_mm
    half = width_mm / 2.0
    t_start = half
    t_tab = half - tab_inward_mm
    if t_tab <= 0.0:
        raise ValueError("端头内伸不得大于半个梯宽。")
    n_hook = standoff_mm - hook_n_inward_mm
    n_curve = standoff_mm + straight_offset_mm
    if n_hook <= 0.0:
        raise ValueError("端头回环的 n 向进深过大。")
    if n_curve <= n_hook:
        raise ValueError("直段长度必须大于零。")
    cage_half = half_width_mm
    radius = end_radius_mm
    if abs(radius - cage_half) > 1.0e-9:
        raise ValueError("本版端头半径取护笼半宽。")
    segments = [
        {"type": "line", "start": (standoff_mm, t_start),
         "end": (standoff_mm, t_tab)},
        {"type": "line", "start": (standoff_mm, t_tab), "end": (n_hook, t_tab)},
        {"type": "line", "start": (n_hook, t_tab), "end": (n_hook, cage_half)},
        {"type": "line", "start": (n_hook, cage_half), "end": (n_curve, cage_half)},
        {"type": "arc", "center": (n_curve, 0.0), "radius": radius,
         "start_angle": 90.0, "end_angle": 0.0},
        {"type": "arc", "center": (n_curve, 0.0), "radius": radius,
         "start_angle": 0.0, "end_angle": -90.0},
        {"type": "line", "start": (n_curve, -cage_half), "end": (n_hook, -cage_half)},
        {"type": "line", "start": (n_hook, -cage_half), "end": (n_hook, -t_tab)},
        {"type": "line", "start": (n_hook, -t_tab), "end": (standoff_mm, -t_tab)},
        {"type": "line", "start": (standoff_mm, -t_tab),
         "end": (standoff_mm, -t_start)},
    ]
    return {
        "half_width": cage_half,
        "near_n": standoff_mm,
        "n_hook": n_hook,
        "curve_n": n_curve,
        "t_tab": t_tab,
        "segments": segments,
    }


def build_cage_top_path(width_mm, height_mm, standoff_mm=STANDOFF_FROM_WALL,
                        half_width_mm=CAGE_HALF_WIDTH,
                        hook_n_inward_mm=CAGE_HOOK_N_INWARD,
                        straight_offset_mm=CAGE_STRAIGHT_END_OFFSET,
                        top_extension_mm=TOP_EXTENSION,
                        hoop_width_mm=CAGE_HOOP_FLAT_WIDTH,
                        leg_n=CAGE_TOP_HOOK_N):
    """最顶环 + 两侧倒 L 的**单一 9 点路径**（局部 n=出梯、t=宽度、z 自地面起，mm）。

    依次为：左倒 L 脚 → 左倒 L 顶 → 顶环左外角 → 顶环左直段末端 → 圆头顶点 → 顶环右直段末端
    → 顶环右外角 → 右倒 L 顶 → 右倒 L 脚。其中圆头顶点不单独给段，由两段 90° 圆弧
    （圆心在直段末端、半径=护笼半宽）形成，顶点即弧的中点。
    """
    if width_mm <= 0.0:
        raise ValueError("梯宽必须大于零。")
    if half_width_mm <= 0.0 or hook_n_inward_mm < 0.0:
        raise ValueError("护笼半宽、端头内伸必须为非负。")
    if top_extension_mm <= 0.0:
        raise ValueError("没有顶部延长段，无需最顶组合路径。")
    n_hook = standoff_mm - hook_n_inward_mm
    n_curve = standoff_mm + straight_offset_mm
    if n_hook <= 0.0:
        raise ValueError("端头内伸过大，外角落到墙后。")
    if n_curve <= n_hook:
        raise ValueError("直段长度必须大于零。")
    B = half_width_mm
    z_bottom = height_mm
    z_top = height_mm + top_extension_mm
    z_ring = z_top - hoop_width_mm / 2.0
    segments = [
        {"type": "line", "start": (leg_n, -B, z_bottom), "end": (leg_n, -B, z_top)},
        {"type": "line", "start": (leg_n, -B, z_top), "end": (n_hook, -B, z_ring)},
        {"type": "line", "start": (n_hook, -B, z_ring), "end": (n_curve, -B, z_ring)},
        {"type": "arc", "center": (n_curve, 0.0, z_ring), "radius": B,
         "start_angle": -90.0, "end_angle": 0.0},
        {"type": "arc", "center": (n_curve, 0.0, z_ring), "radius": B,
         "start_angle": 0.0, "end_angle": 90.0},
        {"type": "line", "start": (n_curve, B, z_ring), "end": (n_hook, B, z_ring)},
        {"type": "line", "start": (n_hook, B, z_ring), "end": (leg_n, B, z_top)},
        {"type": "line", "start": (leg_n, B, z_top), "end": (leg_n, B, z_bottom)},
    ]
    return {
        "half_width": B,
        "n_hook": n_hook,
        "curve_n": n_curve,
        "leg_n": leg_n,
        "ring_z": z_ring,
        "leg_top_z": z_top,
        "leg_bottom_z": z_bottom,
        "segments": segments,
    }


def _cage_segment_length(segment):
    if segment["type"] == "line":
        return hypot(segment["end"][0] - segment["start"][0],
                     segment["end"][1] - segment["start"][1])
    radius = segment["radius"]
    return radius * abs(segment["end_angle"] - segment["start_angle"]) * pi / 180.0


def cage_path_length(path_segments):
    return sum(_cage_segment_length(segment) for segment in path_segments)


def cage_point_at(path_segments, distance_mm):
    """返回沿路径行走 ``distance_mm`` 处的 (n, t, 切向单位向量)。"""
    if distance_mm < 0.0:
        raise ValueError("路径里程不能为负。")
    remaining = distance_mm
    for segment in path_segments:
        length = _cage_segment_length(segment)
        if remaining > length + 1.0e-9:
            remaining -= length
            continue
        if length <= 1.0e-12:
            remaining = 0.0
        if segment["type"] == "line":
            sx, sy = segment["start"]
            ex, ey = segment["end"]
            ratio = remaining / length if length > 0.0 else 0.0
            tangent = ((ex - sx) / length, (ey - sy) / length)
            return (sx + (ex - sx) * ratio, sy + (ey - sy) * ratio, tangent)
        center = segment["center"]
        radius = segment["radius"]
        angle_deg = segment["start_angle"] + (remaining / radius) * 180.0 / pi
        if segment["end_angle"] < segment["start_angle"]:
            angle_deg = segment["start_angle"] - (remaining / radius) * 180.0 / pi
        angle = angle_deg * pi / 180.0
        sign = 1.0 if segment["end_angle"] >= segment["start_angle"] else -1.0
        point = (center[0] + radius * cos(angle), center[1] + radius * sin(angle))
        tangent = (-sign * sin(angle), sign * cos(angle))
        return (point[0], point[1], tangent)
    # 末端：返回最后一段的终点。
    last = path_segments[-1]
    if last["type"] == "line":
        sx, sy = last["start"]
        ex, ey = last["end"]
        length = hypot(ex - sx, ey - sy)
        return (ex, ey, ((ex - sx) / length, (ey - sy) / length))
    center = last["center"]
    radius = last["radius"]
    angle = last["end_angle"] * pi / 180.0
    sign = 1.0 if last["end_angle"] >= last["start_angle"] else -1.0
    return (center[0] + radius * cos(angle), center[1] + radius * sin(angle),
            (-sign * sin(angle), sign * cos(angle)))


def cage_station_points(path_segments, count, start_mm=0.0, end_mm=None):
    """在路径 ``[start_mm, end_mm]`` 区间内等弧长取 ``count`` 个站点。

    返回 [(n, t, 切向), ...]。默认覆盖整条路径；护笼竖杆通常只在
    “立柱以外”的外圈区间内均布，此时传入端头长度作为 ``start_mm``。
    """
    if count <= 0:
        raise ValueError("竖杆数量必须大于零。")
    total = cage_path_length(path_segments)
    if total <= 0.0:
        raise ValueError("护笼路径长度必须大于零。")
    if end_mm is None:
        end_mm = total
    if end_mm - start_mm <= 0.0:
        raise ValueError("竖杆分布区间长度必须大于零。")
    span = end_mm - start_mm
    return [cage_point_at(path_segments, start_mm + span * (index + 0.5) / count)
            for index in range(count)]


def build_cage_layout(width_mm, rung_levels, rung_diameter_mm, height_mm,
                      standoff_mm=STANDOFF_FROM_WALL,
                      half_width_mm=CAGE_HALF_WIDTH,
                      straight_offset_mm=CAGE_STRAIGHT_END_OFFSET,
                      tab_inward_mm=CAGE_TAB_INWARD,
                      hook_n_inward_mm=CAGE_HOOK_N_INWARD,
                      first_z=CAGE_HOOP_FIRST_Z,
                      max_spacing=CAGE_HOOP_SPACING,
                      hoop_width_mm=CAGE_HOOP_FLAT_WIDTH,
                      hoop_thickness_mm=CAGE_HOOP_FLAT_THICKNESS,
                      bar_count=CAGE_BAR_COUNT,
                      bar_width_mm=CAGE_BAR_FLAT_WIDTH,
                      bar_thickness_mm=CAGE_BAR_FLAT_THICKNESS,
                      top_extension_mm=TOP_EXTENSION,
                      top_hook_enabled=CAGE_TOP_HOOK,
                      top_hook_n=CAGE_TOP_HOOK_N):
    """生成护笼的构件布局（毫米级）。

    平台（＝攀爬高度 ``height_mm``）以下：每个环吸附到最近的踏步，环顶紧贴
    踏步底面，环中心 `z = 踏步 z − 踏步半径 − 半个环宽`，相邻环间距不超过
    ``max_spacing``。平台以上 ``top_extension_mm`` 延长段没有踏步，护笼继续
    按不超过 ``max_spacing`` 的间距补环，最顶一环的环顶与立柱顶端齐平。

    返回 dict：
    * ``hoop_rungs`` / ``hoop_levels``：吸附的踏步标高 / 全部环中心标高；
    * ``path``：平面路径；
    * ``stations``：竖杆站位 [(n, t, 切向), ...]；
    * ``primitives``：``sweep``（环扁钢扫掠）+ ``box``（竖杆）。
    """
    path = build_cage_hoop_path(width_mm, standoff_mm, half_width_mm,
                                tab_inward_mm, hook_n_inward_mm, straight_offset_mm)
    hoop_rungs = compute_cage_hoop_rungs(rung_levels, first_z, max_spacing)
    hoop_levels = [rung - rung_diameter_mm / 2.0 - hoop_width_mm / 2.0
                   for rung in hoop_rungs]

    # 平台以上延长段：无踏步，护笼继续向上，环间距不超过 max_spacing，
    # 最顶一环的环顶与立柱顶端（height + extension）齐平。
    if top_extension_mm > 0.0:
        top_hoop = height_mm + top_extension_mm - hoop_width_mm / 2.0
        if hoop_levels:
            level = hoop_levels[-1] + max_spacing
        else:
            level = first_z - rung_diameter_mm / 2.0 - hoop_width_mm / 2.0
        while level < top_hoop - 1.0e-9:
            hoop_levels.append(level)
            level += max_spacing
        hoop_levels.append(top_hoop)

    # 最顶一环 + 两侧倒 L 合成**一条 9 点路径**（同一根扁钢扫掠）；
    # 因此最顶环不再单独做普通环。
    use_top_path = bool(top_hook_enabled and top_extension_mm > 0.0 and hoop_levels)
    if use_top_path:
        top_path = build_cage_top_path(
            width_mm, height_mm, standoff_mm, half_width_mm,
            hook_n_inward_mm, straight_offset_mm, top_extension_mm,
            hoop_width_mm, top_hook_n)
        normal_levels = hoop_levels[:-1]
    else:
        top_path = None
        normal_levels = hoop_levels

    primitives = []
    for level in normal_levels:
        primitives.append({
            "type": "sweep",
            "level": level,
            "path": path["segments"],
            "flat_width": hoop_width_mm,
            "flat_thickness": hoop_thickness_mm,
        })
    if top_path is not None:
        primitives.append({
            "type": "sweep3d",
            "path": top_path["segments"],
            "flat_width": hoop_width_mm,
            "flat_thickness": hoop_thickness_mm,
        })

    # 竖杆只布置在立柱以外的外圈：跳过两端绕立柱的回环（各 3 段）。
    segments = path["segments"]
    lengths = [_cage_segment_length(segment) for segment in segments]
    total_length = sum(lengths)
    start_mm = sum(lengths[:3])
    end_mm = total_length - sum(lengths[-3:])
    stations = cage_station_points(segments, bar_count, start_mm, end_mm)
    offset = hoop_thickness_mm / 2.0 + bar_thickness_mm / 2.0
    for index in range(len(hoop_levels) - 1):
        z0 = hoop_levels[index]
        z1 = hoop_levels[index + 1]
        for station in stations:
            sx, sy, tangent = station
            radial = (tangent[1], -tangent[0])
            center = (sx + radial[0] * offset, sy + radial[1] * offset,
                      (z0 + z1) / 2.0)
            primitives.append({
                "type": "box",
                "center": center,
                "axes": ((radial[0], radial[1], 0.0), (tangent[0], tangent[1], 0.0), "z"),
                "size": (bar_thickness_mm, bar_width_mm, z1 - z0),
            })

    return {
        "hoop_rungs": hoop_rungs,
        "hoop_levels": hoop_levels,
        "path": path,
        "stations": stations,
        "primitives": primitives,
    }


def build_frame(outward):
    """由水平出梯方向返回正交单位基 (n, t, z)。

    * n：出梯方向（水平，指向远离墙面）；
    * t：爬梯宽度方向，t = z × n；
    * z：竖直向上。满足 n × t = z。
    """
    ox, oy = outward
    length = hypot(ox, oy)
    if length <= 1.0e-12:
        raise ValueError("出梯方向不能为竖直方向。")
    nx, ny = ox / length, oy / length
    n = (nx, ny, 0.0)
    t = (-ny, nx, 0.0)
    z = (0.0, 0.0, 1.0)
    return n, t, z


def build_ladder_layout(height_mm, width_mm=LADDER_WIDTH, standoff_mm=STANDOFF_FROM_WALL,
                        rung_diameter_mm=RUNG_DIAMETER, rung_protrusion_mm=RUNG_PROTRUSION,
                        first_rung_mm=FIRST_RUNG_HEIGHT,
                        rung_min_spacing_mm=RUNG_MIN_SPACING,
                        rung_max_spacing_mm=RUNG_MAX_SPACING,
                        top_clearance_mm=TOP_RUNG_CLEARANCE,
                        top_extension_mm=TOP_EXTENSION,
                        bracket_spacing_mm=BRACKET_SPACING,
                        bracket_leg_mm=BRACKET_ANGLE_LEG,
                        bracket_thickness_mm=BRACKET_ANGLE_THICKNESS,
                        wall_plate_width_mm=WALL_PLATE_WIDTH,
                        wall_plate_height_mm=WALL_PLATE_HEIGHT,
                        wall_plate_thickness_mm=WALL_PLATE_THICKNESS,
                        cage_enabled=CAGE_ENABLED,
                        cage_half_width_mm=CAGE_HALF_WIDTH,
                        cage_straight_offset_mm=CAGE_STRAIGHT_END_OFFSET,
                        cage_tab_inward_mm=CAGE_TAB_INWARD,
                        cage_hook_n_inward_mm=CAGE_HOOK_N_INWARD,
                        cage_first_z=CAGE_HOOP_FIRST_Z,
                        cage_spacing=CAGE_HOOP_SPACING,
                        cage_hoop_width_mm=CAGE_HOOP_FLAT_WIDTH,
                        cage_hoop_thickness_mm=CAGE_HOOP_FLAT_THICKNESS,
                        cage_bar_count=CAGE_BAR_COUNT,
                        cage_bar_width_mm=CAGE_BAR_FLAT_WIDTH,
                        cage_bar_thickness_mm=CAGE_BAR_FLAT_THICKNESS,
                        cage_top_hook=CAGE_TOP_HOOK,
                        cage_top_hook_n=CAGE_TOP_HOOK_N,
                        stile_flat=None):
    """生成爬梯全部构件的毫米级布局（局部坐标：n=出梯、t=宽度、z=向上）。

    返回 dict，其中 ``primitives`` 为待创建的实体：
    * box：``center`` + ``axes``(轴向名或局部三分量) + ``size``；
    * cylinder：``center`` + ``axis`` + ``length`` + ``diameter``；
    * sweep：``level`` + ``path``(平面折线/圆弧) + 扁钢截面尺寸。
    """
    if height_mm <= 0.0:
        raise ValueError("爬梯高度（竖直线长度）必须大于零。")
    if width_mm <= 0.0:
        raise ValueError("爬梯宽度必须大于零。")
    if standoff_mm <= 0.0:
        raise ValueError("立柱中心距墙必须大于零。")

    if stile_flat is None:
        stile_width, stile_thickness = select_stile_flat(height_mm)
    else:
        stile_width, stile_thickness = stile_flat

    half_width = width_mm / 2.0
    rung_length = width_mm + stile_thickness + 2.0 * rung_protrusion_mm
    rung_levels = compute_rung_levels(height_mm, first_rung_mm,
                                      rung_min_spacing_mm, rung_max_spacing_mm,
                                      top_clearance_mm)
    bracket_levels = compute_bracket_levels(height_mm, bracket_spacing_mm)

    primitives = []

    # 立柱比攀爬高度高出 top_extension（平台以上延长段，无踏步，仅立柱 + 护笼）。
    stile_height = height_mm + top_extension_mm
    for stile_y in (-half_width, half_width):
        primitives.append({
            "type": "box",
            "center": (standoff_mm, stile_y, stile_height / 2.0),
            "axes": ("n", "t", "z"),
            "size": (stile_width, stile_thickness, stile_height),
        })

    # 横担：φ24 圆钢沿宽度方向 t，中心位于立柱中心面。
    for level in rung_levels:
        primitives.append({
            "type": "cylinder",
            "center": (standoff_mm, 0.0, level),
            "axis": "t",
            "length": rung_length,
            "diameter": rung_diameter_mm,
        })

    # 中间支架：75x10 角钢，长度沿 n 从墙面伸到立柱前缘；开口向外，一肢背靠背贴立柱。
    # 角钢用两段长方体拼成：竖肢（贴立柱）+ 水平肢（外伸，形成 L 开口）。
    angle_length = standoff_mm + stile_width / 2.0
    angle_center_n = angle_length / 2.0
    for level in bracket_levels:
        for side in (-1.0, 1.0):
            stile_y = side * half_width
            stile_out_edge = stile_y + side * stile_thickness / 2.0
            # 竖肢：面贴立柱外侧面（背靠背），75 高。
            primitives.append({
                "type": "box",
                "center": (angle_center_n,
                           stile_out_edge + side * bracket_thickness_mm / 2.0,
                           level),
                "axes": ("n", "t", "z"),
                "size": (angle_length, bracket_thickness_mm, bracket_leg_mm),
            })
            # 水平肢：自角部向“外”伸出，使 L 开口朝外，位于竖肢底端。
            primitives.append({
                "type": "box",
                "center": (angle_center_n,
                           stile_out_edge + side * bracket_leg_mm / 2.0,
                           level - bracket_leg_mm / 2.0 + bracket_thickness_mm / 2.0),
                "axes": ("n", "t", "z"),
                "size": (angle_length, bracket_leg_mm, bracket_thickness_mm),
            })
            # 墙端贴墙钢板（面平行墙面，100x100）：中心与 75 角钢截面中心对齐。
            primitives.append({
                "type": "box",
                "center": (wall_plate_thickness_mm / 2.0,
                           stile_out_edge + side * bracket_leg_mm / 2.0,
                           level),
                "axes": ("n", "t", "z"),
                "size": (wall_plate_thickness_mm,
                         wall_plate_width_mm, wall_plate_height_mm),
            })

    # 防护围栏（护笼）：环沿路径扫掠，竖杆沿外圈均布。
    # 记下爬梯构件数量，供分组时区分「爬梯单元」与「护笼单元」。
    ladder_primitive_count = len(primitives)
    cage = None
    if cage_enabled:
        cage = build_cage_layout(
            width_mm, rung_levels, rung_diameter_mm, height_mm, standoff_mm,
            cage_half_width_mm, cage_straight_offset_mm, cage_tab_inward_mm,
            cage_hook_n_inward_mm, cage_first_z, cage_spacing,
            cage_hoop_width_mm, cage_hoop_thickness_mm, cage_bar_count,
            cage_bar_width_mm, cage_bar_thickness_mm, top_extension_mm,
            cage_top_hook, cage_top_hook_n,
        )
        primitives.extend(cage["primitives"])

    return {
        "height": height_mm,
        "width": width_mm,
        "standoff": standoff_mm,
        "stile_flat": (stile_width, stile_thickness),
        "rung_length": rung_length,
        "rung_levels": rung_levels,
        "bracket_levels": bracket_levels,
        "cage": cage,
        "ladder_primitive_count": ladder_primitive_count,
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


def _build_sweep_path(origin, frame, level, path_segments, uor_per_mm):
    """把平面路径段组装成世界坐标的 CurveVector（供扫掠）。"""
    def point(local_nt):
        value = _local_point(origin, frame, (local_nt[0], local_nt[1], level), uor_per_mm)
        return DPoint3d.From(value[0], value[1], value[2])

    path_cv = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    for segment in path_segments:
        if segment["type"] == "line":
            path_cv.Add(ICurvePrimitive.CreateLine(
                DSegment3d(point(segment["start"]), point(segment["end"]))))
        elif segment["type"] == "arc":
            center = segment["center"]
            radius = segment["radius"]
            a0 = segment["start_angle"] * pi / 180.0
            a1 = segment["end_angle"] * pi / 180.0
            start = (center[0] + radius * cos(a0), center[1] + radius * sin(a0))
            end = (center[0] + radius * cos(a1), center[1] + radius * sin(a1))
            arc = DEllipse3d.FromArcCenterStartEnd(point(center), point(start), point(end))
            path_cv.Add(ICurvePrimitive.CreateArc(arc))
        else:
            raise ValueError("未知护笼路径段：%r" % segment["type"])
    return path_cv


def _up_candidates(frame, primary):
    """BodyFromSweep 的参考方向候选：先 None，再几个世界方向，逐个试。"""
    candidates = [None]
    for vec in (primary, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        world = _local_vector(frame, vec)
        candidates.append(DVec3d.From(world[0], world[1], world[2]))
    return candidates


def _sweep_profile_element(dgn_model, path_cv, profile_element, up_candidates):
    """尝试 BodyFromSweep 的多种调用形式/参考方向，返回首个成功实体。"""
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = ICurvePathQuery.ElementToCurveVector(profile_element)
    if profile is None:
        return None

    def finish(result):
        if result is None or not _succeeded(result[0]):
            return None
        element = EditElementHandle()
        if _succeeded(SolidUtil.Convert.BodyToElement(
                element, result[1], profile_element, dgn_model)):
            return element
        return None

    # 1) 6 参数形式。
    try:
        element = finish(SolidUtil.Create.BodyFromSweep(
            profile, path_cv, model_ref, False, True, False))
        if element is not None:
            return element
    except Exception:
        pass
    # 2) 10 参数形式 + 不同参考方向。
    for up in up_candidates:
        try:
            element = finish(SolidUtil.Create.BodyFromSweep(
                profile, path_cv, model_ref, False, True, False,
                up, None, None, None))
        except Exception:
            continue
        if element is not None:
            return element
    return None


def _reverse_segments(segments):
    """路径反向（供变换扫掠起点、绕开退化参考方向）。"""
    reversed_segments = []
    for segment in reversed(segments):
        if segment["type"] == "line":
            reversed_segments.append({
                "type": "line", "start": segment["end"], "end": segment["start"]})
        else:
            reversed_segments.append({
                "type": "arc", "center": segment["center"],
                "radius": segment["radius"],
                "start_angle": segment["end_angle"],
                "end_angle": segment["start_angle"]})
    return reversed_segments


def _sweep_flat_bar(dgn_model, origin, frame, level, path_segments,
                    flat_width, flat_thickness, color):
    """用 BodyFromSweep 把扁钢截面（竖直）沿水平路径扫掠成一个实体；失败返回 None。"""
    uor_per_mm = _uor_per_mm(dgn_model)
    try:
        first = path_segments[0]
        dx = first["end"][0] - first["start"][0]
        dy = first["end"][1] - first["start"][1]
        length = hypot(dx, dy)
        if length <= 0.0:
            return None
        tangent = (dx / length, dy / length)
        radial = (tangent[1], -tangent[0])
        axis_u = _local_vector(frame, (0.0, 0.0, 1.0))          # 竖直：扁钢宽面
        axis_v = _local_vector(frame, (radial[0], radial[1], 0.0))  # 径向：扁钢厚
        center = _local_point(origin, frame,
                              (first["start"][0], first["start"][1], level), uor_per_mm)
        half_u = flat_width * uor_per_mm / 2.0
        half_v = flat_thickness * uor_per_mm / 2.0

        def corner(su, sv):
            return DPoint3d.From(
                center[0] + axis_u[0] * su + axis_v[0] * sv,
                center[1] + axis_u[1] * su + axis_v[1] * sv,
                center[2] + axis_u[2] * su + axis_v[2] * sv,
            )

        profile_points = DPoint3dArray()
        profile_points.append(corner(-half_u, -half_v))
        profile_points.append(corner(+half_u, -half_v))
        profile_points.append(corner(+half_u, +half_v))
        profile_points.append(corner(-half_u, +half_v))
        profile_points.append(corner(-half_u, -half_v))

        model_ref = ISessionMgr.ActiveDgnModelRef
        profile_element = EditElementHandle()
        if not _succeeded(ShapeHandler.CreateShapeElement(
                profile_element, None, profile_points, model_ref.Is3d(), model_ref)):
            return None
        path_cv = _build_sweep_path(origin, frame, level, path_segments, uor_per_mm)
        element = _sweep_profile_element(
            dgn_model, path_cv, profile_element,
            _up_candidates(frame, radial))
        return _apply_color(element, color) if element is not None else None
    except Exception:
        return None


def _hoop_flat_bar_boxes(dgn_model, origin, frame, level, path_segments,
                         flat_width, flat_thickness, color, step_deg=7.5):
    """兜底做法：沿路径逐段建扁钢实体块（圆弧按 step_deg 折线近似）。"""
    uor_per_mm = _uor_per_mm(dgn_model)
    elements = []

    def add_chord(start_nt, end_nt):
        dx = end_nt[0] - start_nt[0]
        dy = end_nt[1] - start_nt[1]
        length = hypot(dx, dy)
        if length <= 1.0e-9:
            return
        tangent = (dx / length, dy / length)
        radial = (tangent[1], -tangent[0])
        local_center = ((start_nt[0] + end_nt[0]) / 2.0,
                        (start_nt[1] + end_nt[1]) / 2.0, level)
        world_center = _local_point(origin, frame, local_center, uor_per_mm)
        axis_u = _local_vector(frame, (radial[0], radial[1], 0.0))
        axis_v = _local_vector(frame, (tangent[0], tangent[1], 0.0))
        axis_w = _local_vector(frame, (0.0, 0.0, 1.0))
        element = _create_box(dgn_model, world_center, axis_u, axis_v, axis_w,
                              flat_thickness * uor_per_mm,
                              length * 1.02 * uor_per_mm,
                              flat_width * uor_per_mm, color)
        if element is not None:
            elements.append(element)

    for segment in path_segments:
        if segment["type"] == "line":
            add_chord(segment["start"], segment["end"])
        elif segment["type"] == "arc":
            center = segment["center"]
            radius = segment["radius"]
            a0 = segment["start_angle"]
            a1 = segment["end_angle"]
            steps = max(2, int(ceil(abs(a1 - a0) / step_deg - 1.0e-9)))
            for index in range(steps):
                aa = (a0 + (a1 - a0) * index / steps) * pi / 180.0
                ab = (a0 + (a1 - a0) * (index + 1) / steps) * pi / 180.0
                pa = (center[0] + radius * cos(aa), center[1] + radius * sin(aa))
                pb = (center[0] + radius * cos(ab), center[1] + radius * sin(ab))
                add_chord(pa, pb)
        else:
            raise ValueError("未知护笼路径段：%r" % segment["type"])
    return elements


def _create_flat_sweep(dgn_model, origin, frame, level, path_segments,
                       flat_width, flat_thickness, color):
    """优先扫掠；``BodyFromSweep`` 失败时退回逐段扁钢实体块，返回元素列表。"""
    element = _sweep_flat_bar(dgn_model, origin, frame, level, path_segments,
                              flat_width, flat_thickness, color)
    if element is not None:
        return [element]
    return _hoop_flat_bar_boxes(dgn_model, origin, frame, level, path_segments,
                                flat_width, flat_thickness, color)


def _cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _flat_bar_frame_local(tangent):
    """由局部切向给出扁钢的 (宽 50 方向, 厚 5 方向)。"""
    tx, ty, tz = tangent
    if abs(tz) > 0.999:
        five = (0.0, 1.0, 0.0)          # 竖段：厚沿 t
    else:
        five = (ty, -tx, 0.0)           # 水平段：厚沿水平法向
        length = hypot(five[0], five[1])
        five = (five[0] / length, five[1] / length, 0.0)
    fifty = _cross3(five, tangent)
    return fifty, five


def _build_sweep_path_3d(origin, frame, segments, uor_per_mm):
    """把 3D 路径段（局部 n,t,z）组装成世界坐标 CurveVector。"""
    def point(nt):
        value = _local_point(origin, frame, nt, uor_per_mm)
        return DPoint3d.From(value[0], value[1], value[2])

    path_cv = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    for segment in segments:
        if segment["type"] == "line":
            path_cv.Add(ICurvePrimitive.CreateLine(
                DSegment3d(point(segment["start"]), point(segment["end"]))))
        elif segment["type"] == "arc":
            center = segment["center"]
            radius = segment["radius"]
            a0 = segment["start_angle"] * pi / 180.0
            a1 = segment["end_angle"] * pi / 180.0
            start = (center[0] + radius * cos(a0), center[1] + radius * sin(a0), center[2])
            end = (center[0] + radius * cos(a1), center[1] + radius * sin(a1), center[2])
            arc = DEllipse3d.FromArcCenterStartEnd(point(center), point(start), point(end))
            path_cv.Add(ICurvePrimitive.CreateArc(arc))
        else:
            raise ValueError("未知护笼路径段：%r" % segment["type"])
    return path_cv


def _sweep_flat_bar_3d(dgn_model, origin, frame, segments,
                       flat_width, flat_thickness, color):
    """用 BodyFromSweep 沿完整 3D 路径扫掠成一个实体；失败返回 None。

    起点在竖段上、切向与 +Z 平行会让参考方向退化，因此按“正/反两向 × 多个
    参考方向”逐个尝试，尽量得到单个扫掠体。
    """
    uor_per_mm = _uor_per_mm(dgn_model)
    try:
        for use_reverse in (False, True):
            segs = _reverse_segments(segments) if use_reverse else list(segments)
            if not segs:
                continue
            first = segs[0]
            delta = (first["end"][0] - first["start"][0],
                     first["end"][1] - first["start"][1],
                     first["end"][2] - first["start"][2])
            length = hypot(hypot(delta[0], delta[1]), delta[2])
            if length <= 0.0:
                continue
            tangent = (delta[0] / length, delta[1] / length, delta[2] / length)
            fifty, five = _flat_bar_frame_local(tangent)
            center = _local_point(origin, frame, first["start"], uor_per_mm)
            axis_u = _local_vector(frame, fifty)
            axis_v = _local_vector(frame, five)
            half_u = flat_width * uor_per_mm / 2.0
            half_v = flat_thickness * uor_per_mm / 2.0

            def corner(su, sv):
                return DPoint3d.From(
                    center[0] + axis_u[0] * su + axis_v[0] * sv,
                    center[1] + axis_u[1] * su + axis_v[1] * sv,
                    center[2] + axis_u[2] * su + axis_v[2] * sv,
                )

            profile_points = DPoint3dArray()
            profile_points.append(corner(-half_u, -half_v))
            profile_points.append(corner(+half_u, -half_v))
            profile_points.append(corner(+half_u, +half_v))
            profile_points.append(corner(-half_u, +half_v))
            profile_points.append(corner(-half_u, -half_v))

            model_ref = ISessionMgr.ActiveDgnModelRef
            profile_element = EditElementHandle()
            if not _succeeded(ShapeHandler.CreateShapeElement(
                    profile_element, None, profile_points, model_ref.Is3d(), model_ref)):
                continue
            path_cv = _build_sweep_path_3d(origin, frame, segs, uor_per_mm)
            element = _sweep_profile_element(
                dgn_model, path_cv, profile_element,
                _up_candidates(frame, fifty))
            if element is not None:
                return _apply_color(element, color)
        return None
    except Exception:
        return None


def _flat_bar_boxes_3d(dgn_model, origin, frame, segments,
                       flat_width, flat_thickness, color, step_deg=7.5):
    """兜底：沿 3D 路径逐段建扁钢实体块。"""
    uor_per_mm = _uor_per_mm(dgn_model)
    elements = []

    def add_chord(p0, p1):
        delta = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        length = hypot(hypot(delta[0], delta[1]), delta[2])
        if length <= 1.0e-9:
            return
        tangent = (delta[0] / length, delta[1] / length, delta[2] / length)
        fifty, five = _flat_bar_frame_local(tangent)
        local_center = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0,
                        (p0[2] + p1[2]) / 2.0)
        world_center = _local_point(origin, frame, local_center, uor_per_mm)
        axis_u = _local_vector(frame, fifty)
        axis_v = _local_vector(frame, five)
        axis_w = _local_vector(frame, _cross3(fifty, five))
        element = _create_box(dgn_model, world_center, axis_u, axis_v, axis_w,
                              flat_width * uor_per_mm,
                              flat_thickness * uor_per_mm,
                              length * 1.02 * uor_per_mm, color)
        if element is not None:
            elements.append(element)

    for segment in segments:
        if segment["type"] == "line":
            add_chord(segment["start"], segment["end"])
        elif segment["type"] == "arc":
            center = segment["center"]
            radius = segment["radius"]
            a0 = segment["start_angle"]
            a1 = segment["end_angle"]
            steps = max(2, int(ceil(abs(a1 - a0) / step_deg - 1.0e-9)))
            for index in range(steps):
                aa = (a0 + (a1 - a0) * index / steps) * pi / 180.0
                ab = (a0 + (a1 - a0) * (index + 1) / steps) * pi / 180.0
                pa = (center[0] + radius * cos(aa), center[1] + radius * sin(aa), center[2])
                pb = (center[0] + radius * cos(ab), center[1] + radius * sin(ab), center[2])
                add_chord(pa, pb)
        else:
            raise ValueError("未知护笼路径段：%r" % segment["type"])
    return elements


def _create_sweep3d(dgn_model, origin, frame, segments,
                    flat_width, flat_thickness, color):
    """3D 路径（倒 L + 顶环）扫掠；失败退回逐段扁钢实体块。返回元素列表。"""
    element = _sweep_flat_bar_3d(dgn_model, origin, frame, segments,
                                 flat_width, flat_thickness, color)
    if element is not None:
        return [element]
    return _flat_bar_boxes_3d(dgn_model, origin, frame, segments,
                              flat_width, flat_thickness, color)


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
    if primitive["type"] == "sweep":
        return _create_flat_sweep(
            dgn_model, origin, frame, primitive["level"], primitive["path"],
            primitive["flat_width"], primitive["flat_thickness"], color)
    if primitive["type"] == "sweep3d":
        return _create_sweep3d(
            dgn_model, origin, frame, primitive["path"],
            primitive["flat_width"], primitive["flat_thickness"], color)
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


def build_wall_ladder_elements(dgn_model, origin, frame, layout, color):
    """按布局创建爬梯并把**爬梯、护笼分别组成一个普通单元**写入模型。

    返回单元句柄列表（爬梯单元、护笼单元）。创建过程中不把零件单独写入模型，
    只有组装好的单元进模型，因此失败时不会留下零散构件。
    """
    uor_per_mm = _uor_per_mm(dgn_model)
    split = layout.get("ladder_primitive_count", len(layout["primitives"]))
    ladder_cell = _CellBuilder(dgn_model, LADDER_CELL_NAME)
    cage_cell = _CellBuilder(dgn_model, CAGE_CELL_NAME)
    try:
        for index, primitive in enumerate(layout["primitives"]):
            elements = _create_primitive_elements(
                dgn_model, origin, frame, primitive, uor_per_mm, color)
            if not elements:
                raise RuntimeError("构件创建失败：%s" % primitive["type"])
            builder = ladder_cell if index < split else cage_cell
            for element in elements:
                if element is None:
                    raise RuntimeError("构件创建失败：%s" % primitive["type"])
                builder.add(element)
        cells = []
        if ladder_cell.child_count:
            cells.append(ladder_cell.commit())
        if cage_cell.child_count:
            cells.append(cage_cell.commit())
        return cells
    except Exception:
        _delete_elements([ladder_cell.cell, cage_cell.cell])
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


def draw_wall_ladder(base_point, top_point, outward=(1.0, 0.0), **params):
    """直接生成并写入模型，返回单元句柄列表（爬梯单元、护笼单元）。

    base_point / top_point : 竖直线的下、上端点（世界 UOR 坐标 DPoint3d）。
    outward                : 出梯方向（水平）。
    其余关键字参数传给 build_ladder_layout。
    """
    dgn_model = ISessionMgr.GetActiveDgnModel()
    uor_per_mm = _uor_per_mm(dgn_model)
    height_mm = (top_point.z - base_point.z) / uor_per_mm
    layout = build_ladder_layout(height_mm, **params)
    frame = build_frame(outward)
    return build_wall_ladder_elements(dgn_model, base_point, frame, layout, _element_color())


# ============================================================================
# 路径提取
# ============================================================================

def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _distance3(first, second):
    return hypot(hypot(second.x - first.x, second.y - first.y), second.z - first.z)


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
            raise ValueError("所选路径含圆弧或曲线；请选择一条竖直线段。")


def extract_vertical_line(element_handle, uor_per_mm):
    """从所选元素提取一条竖直线段，返回 (下限端点, 上限端点)。

    水平偏差不得超过 ``VERTICAL_TOLERANCE_MM``。
    """
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError("请选择一条开放的竖直线段。")
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if len(pieces) != 1:
        raise ValueError("请选择单条竖直线段（不要选折线或复杂链）。")
    piece = pieces[0]
    start, end = piece[0], piece[-1]
    dz = end.z - start.z
    vertical_mm = abs(dz) / uor_per_mm
    if vertical_mm <= PATH_TOLERANCE_MM:
        raise ValueError("所选线段长度必须大于零。")
    for point in piece:
        horizontal_mm = hypot(point.x - start.x, point.y - start.y) / uor_per_mm
        if horizontal_mm > VERTICAL_TOLERANCE_MM:
            raise ValueError("所选线段不是竖直线（水平偏差 %.1f mm）。" % horizontal_mm)
    if dz >= 0.0:
        return start, end
    return end, start


# ============================================================================
# 界面辅助（与“可拆卸栏杆”保持一致的做法）
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


class _WallLadderSettingsDialog(_MicroStationTk):
    def __init__(self):
        _MicroStationTk.__init__(self)
        self.title("墙面爬梯")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel_tool)
        self.base_point = None
        self.top_point = None
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
        tk.Label(title_row, text="墙面爬梯", bg=bg, fg=ink,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        tk.Label(header, text="选竖直线＝墙面 · φ24 横担 · 立柱扁钢按支架跨距选型",
                 bg=bg, fg=muted, font=ui_font_small).pack(
                     anchor="w", pady=(4, 0), padx=(18, 0))

        card_frame = tk.Frame(shell, bg=card, highlightbackground=border,
                              highlightthickness=1)
        card_frame.pack(fill="both", expand=True)
        form = ttk.Frame(card_frame, style="Card.TFrame", padding=20)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        self.width_var = tk.StringVar(value=str(int(LADDER_WIDTH)))
        self.standoff_var = tk.StringVar(value=str(int(STANDOFF_FROM_WALL)))
        self.first_rung_var = tk.StringVar(value=str(int(FIRST_RUNG_HEIGHT)))
        self.bracket_spacing_var = tk.StringVar(value=str(int(BRACKET_SPACING)))
        self.outward_var = tk.StringVar(value="0")

        ttk.Label(form, text="布置参数", style="GlassMuted.TLabel",
                  font=ui_font_small).grid(row=0, column=0, columnspan=3, sticky="w")

        entries = []
        rows = [
            ("爬梯宽度（两立柱中心距）", self.width_var, "mm"),
            ("立柱中心线距墙面", self.standoff_var, "mm"),
            ("最低横担离地", self.first_rung_var, "mm"),
            ("墙面支架间距", self.bracket_spacing_var, "mm"),
            ("出梯方向水平角（0=+X，90=+Y）", self.outward_var, "°"),
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

        self.cage_var = tk.BooleanVar(value=bool(CAGE_ENABLED))
        cage_check = tk.Checkbutton(
            form, text="加防护围栏（护笼，环 + 竖杆）", variable=self.cage_var,
            command=self.on_options_changed, bg=card, fg=ink,
            activebackground=card, selectcolor=card, font=ui_font,
            highlightthickness=0, bd=0)
        cage_check.grid(row=len(rows) + 1, column=0, columnspan=3,
                        sticky="w", pady=(2, 0))
        entries.append(cage_check)

        separator_row = len(rows) + 2
        ttk.Separator(form, orient="horizontal").grid(
            row=separator_row, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="选型", style="GlassMuted.TLabel").grid(
            row=separator_row + 1, column=0, sticky="nw", pady=3)
        self.stile_label = ttk.Label(form, text="—", style="Glass.TLabel",
                                     justify="left", wraplength=340)
        self.stile_label.grid(row=separator_row + 1, column=1, columnspan=2,
                              sticky="w", padx=(12, 0), pady=3)

        ttk.Label(form, text="预览", style="GlassMuted.TLabel").grid(
            row=separator_row + 2, column=0, sticky="nw", pady=3)
        self.info_label = ttk.Label(form, text="—", style="Glass.TLabel",
                                    justify="left", wraplength=340)
        self.info_label.grid(row=separator_row + 2, column=1, columnspan=2,
                             sticky="w", padx=(12, 0), pady=3)

        ttk.Label(form, text="操作", style="GlassMuted.TLabel").grid(
            row=separator_row + 3, column=0, sticky="nw", pady=3)
        ttk.Label(form, text="点选一条竖直线，程序即时生成预览",
                  style="Glass.TLabel", justify="left", wraplength=340).grid(
                      row=separator_row + 3, column=1, columnspan=2, sticky="w",
                      padx=(12, 0), pady=3)

        status_chip = tk.Frame(form, bg=card_soft, highlightbackground=border,
                               highlightthickness=1)
        status_chip.grid(row=separator_row + 4, column=0, columnspan=3,
                         sticky="ew", pady=(12, 0))
        self.status_label = tk.Label(status_chip, text="请在模型中点选竖直线。",
                                     bg=card_soft, fg="#1f5f99",
                                     font=ui_font_small, wraplength=340,
                                     justify="left")
        self.status_label.pack(anchor="w", padx=12, pady=8)

        button_bar = tk.Frame(form, bg=card)
        button_bar.grid(row=separator_row + 5, column=0, columnspan=3,
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
            width = float(self.width_var.get())
            standoff = float(self.standoff_var.get())
            first_rung = float(self.first_rung_var.get())
            bracket_spacing = float(self.bracket_spacing_var.get())
            outward_deg = float(self.outward_var.get())
        except (TypeError, ValueError):
            raise ValueError("所有输入都必须是数字。")
        if width <= 0.0 or standoff <= 0.0 or bracket_spacing <= 0.0:
            raise ValueError("宽度、距墙、支架间距必须大于零。")
        if first_rung < 0.0:
            raise ValueError("最低横担离地不能为负数。")
        angle = outward_deg * pi / 180.0
        return {
            "width_mm": width,
            "standoff_mm": standoff,
            "first_rung_mm": first_rung,
            "bracket_spacing_mm": bracket_spacing,
            "cage_enabled": bool(self.cage_var.get()),
            "outward": (cos(angle), sin(angle)),
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
        if self.base_point is not None:
            self._cancel_pending()
            self._pending_regeneration = self.after(
                REGENERATE_DELAY_MS, self._run_pending)

    def _run_pending(self):
        self._pending_regeneration = None
        if self._closing:
            return
        self.regenerate(self.base_point, self.top_point)

    def regenerate(self, base_point, top_point):
        self._cancel_pending()
        if base_point is None or top_point is None:
            return None
        self.base_point = _copy_dpoint(base_point)
        self.top_point = _copy_dpoint(top_point)
        self._set_busy(True)
        self.set_status("正在生成墙面爬梯预览，请稍候……")
        try:
            dgn_model = ISessionMgr.GetActiveDgnModel()
            uor_per_mm = _uor_per_mm(dgn_model)
            height_mm = (top_point.z - base_point.z) / uor_per_mm
            params = self.get_params()
            outward = params.pop("outward")
            layout = build_ladder_layout(height_mm, **params)
            frame = build_frame(outward)
            new_handles = build_wall_ladder_elements(
                dgn_model, base_point, frame, layout, _element_color())
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
        self.stile_label.configure(text="立柱扁钢 %d×%d，横担 φ%.0f，横担外伸 %d" % (
            layout["stile_flat"][0], layout["stile_flat"][1],
            RUNG_DIAMETER, int(RUNG_PROTRUSION)))
        rung_levels = layout["rung_levels"]
        if len(rung_levels) >= 2:
            spacing = rung_levels[1] - rung_levels[0]
        else:
            spacing = 0.0
        cage = layout.get("cage")
        cage_text = "护笼 关"
        if cage is not None:
            cage_text = "护笼 %d 环×%d 竖杆" % (
                len(cage["hoop_levels"]), len(cage["stations"]))
        self.info_label.configure(text="高度 %.0f；横担 %d 根（间距 %.0f）；支架 %d 处；%s" % (
            layout["height"], len(rung_levels), spacing,
            len(layout["bracket_levels"]), cage_text))
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

class WallLadderPathTool(DgnElementSetTool):
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
        NotificationManager.OutputPrompt("请选择用于生成爬梯的竖直线（视为墙面）。")

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
            scale = _uor_per_mm(model)
            extract_vertical_line(handle, scale)
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
            scale = _uor_per_mm(model)
            base_point, top_point = extract_vertical_line(eeh, scale)
            result = self.tool_settings.regenerate(base_point, top_point)
            return BentleyStatus.eSUCCESS if result is not None else BentleyStatus.eERROR
        except Exception as error:
            message = "爬梯生成失败：%s" % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        WallLadderPathTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _GetToolName(self, name):
        return WString("WallLadderPathTool")

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
        settings = tool_settings if tool_settings is not None else _WallLadderSettingsDialog()
        tool = WallLadderPathTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.microstation_mainloop()
        return tool


def PyMain():
    WallLadderPathTool.InstallNewInstance(0)


if __name__ == "__main__":
    PyMain()
