# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``弯头垫板.py`` 插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""弯头弧形垫板纯几何 / 数据逻辑（可脱离 Bentley 单测）。

贴附焊接在 **90° 弯头背弧（外弯侧 / extrados）** 上的弧形护板：

* **截面**（垂直于弯头中心线）与 Y2 弧形垫板一致 —— 内弧半径 ``R = 管外径/2``
  （贴管壁）、外弧半径 ``R + T``（``T`` = 板厚，沿用 Y2 表 1），张角
  ``α = 120°``（图右侧视图），两端由径向直线封闭，**居中于背弧方向**；
* 截面沿**弯头中心线圆弧**扫掠，沿弯头方向覆盖 ``75°``（图左侧），居中于弯头
  ``45°`` 中点 —— 因此内表面正好是弯头外壁的**环面**，真正贴合弯头；
* 弯头弯曲半径 ``R = 倍率 × 公称直径``（ASME B16.9：90° 长半径 1.5D → 1.5，
  短半径 1.0D → 1.0）；
* 垫板中央（覆盖中点、背弧冠线）开 **气孔 Ø6**，沿背弧径向贯穿板厚。

编号：``弯头垫板-管径-弯头倍率``（如 ``弯头垫板-100-1.5``）—— 图集未给编号，
直接按名称编号，故编号中**不含**材料代码与长度。

弯头局部坐标（OPM 约定，沿用 ``F5-[水平弯头的水平耳轴]`` 的解析）：

    origin      = 端口 0
    axis_x      = 端口 0 处进入弯头的切线方向
    axis_z      = 由端口 0 指向弯曲中心的方向
    arc_center  = origin + R * axis_z

中心线上角度参数 ``t``（``0°`` = 端口 0，``90°`` = 端口 1）：

    r(t) = -axis_z * cos t + axis_x * sin t     # 半径方向（背弧方向）
    P(t) = arc_center + R * r(t)                # 中心线点
    T(t) =  axis_z * sin t + axis_x * cos t     # 切线（扫掠方向）

本模块只做**数据与尺寸推导**；三维实体（截面沿中心线圆弧扫掠 + 中央气孔布尔减）
由 ``弯头垫板.py`` 生成。截面轮廓与板厚 / 材料表复用 ``弧形垫板_几何``。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple


_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_HERE)
_PAD_DIR = os.path.join(_MODULE_DIR, '弧形垫板')
if _PAD_DIR not in sys.path:
    sys.path.insert(0, _PAD_DIR)

import 弧形垫板_几何 as pad_geom  # noqa: E402


# ---------------------------------------------------------------------------
# 常量：弯头与覆盖角
# ---------------------------------------------------------------------------

# 只支持标准 90° 圆弧弯头（与 F5 一致）。
ELBOW_ANGLE_DEG = 90.0
# 垫板沿弯头弯曲方向覆盖的角度（图左侧 75°）。
COVERAGE_DEG = 75.0
# 覆盖区间居中于弯头中点（背弧冠线），即 90° / 2。
COVERAGE_CENTER_DEG = ELBOW_ANGLE_DEG / 2.0
# 截面周向包角（图右侧 120°），居中于背弧方向。
WRAP_ALPHA_DEG = 120.0

MIN_COVERAGE_DEG = 1.0
MAX_COVERAGE_DEG = ELBOW_ANGLE_DEG

# 常用弯头倍率（1.0D 短半径 / 1.5D 长半径 / 2.0D~3.0D）。
STANDARD_MULTIPLIERS = (1.0, 1.5, 2.0, 2.5, 3.0)
DEFAULT_MULTIPLIER = 1.5
MIN_MULTIPLIER = 0.5
MAX_MULTIPLIER = 5.0

DEFAULT_MATERIAL_CODE = pad_geom.DEFAULT_MATERIAL_CODE
VENT_HOLE_DIA_MM = pad_geom.VENT_HOLE_DIA_MM
STEEL_DENSITY_KG_MM3 = pad_geom.STEEL_DENSITY_KG_MM3
DN_MIN = pad_geom.DN_MIN
DN_MAX = pad_geom.DN_MAX


# DN → NPS 英寸公称直径（mm，= 英寸 × 25.4）。
# 弯头弯曲半径按**英寸公称**计算（ASME B16.9：中心至端面 = 1.5 × NPS 英寸），
# 不用公制 DN 名义值 —— 例如 DN100 = 4″ → 101.6 mm，1.5D 半径 = 152.4 mm。
NOMINAL_INCH_MM = {
    15: 12.7, 20: 19.05, 25: 25.4, 32: 31.75, 40: 38.1, 50: 50.8,
    65: 63.5, 80: 76.2, 90: 88.9, 100: 101.6, 125: 127.0, 150: 152.4,
    200: 203.2, 250: 254.0, 300: 304.8, 350: 355.6, 400: 406.4, 450: 457.2,
    500: 508.0, 600: 609.6, 650: 660.4, 700: 711.2, 750: 762.0, 800: 812.8,
    850: 863.6, 900: 914.4,
}


# ---------------------------------------------------------------------------
# 查询 / 匹配
# ---------------------------------------------------------------------------


def dn_choices():
    return pad_geom.dn_choices()


def od_mm(dn):
    """按 ASME B36.10M 返回公称直径对应的管外径（mm）。"""
    return pad_geom.od_mm(dn)


def nps_text(dn):
    return pad_geom.nps_text(dn)


def dn_label(dn):
    return pad_geom.dn_label(dn)


def match_dn(nominal_mm, tolerance=5.0, ratio=0.05):
    """把弯头信息里的直径匹配到最近 DN；超出容差返回 ``None``。"""
    return pad_geom.match_dn(nominal_mm, tolerance, ratio)


def plate_thickness_mm(dn):
    """按 Y2 表 1 由管径取板厚 T（mm）。"""
    return pad_geom.plate_thickness_mm(dn)


def material_choices():
    return pad_geom.material_choices()


def material_label(code):
    return pad_geom.material_label(code)


def material_for_code(code):
    return pad_geom.material_for_code(code)


def nominal_mm(dn):
    """NPS 英寸公称直径（mm）。弯头弯曲半径按此计算。"""
    dn = int(dn)
    if dn in NOMINAL_INCH_MM:
        return float(NOMINAL_INCH_MM[dn])
    raise ValueError('未知公称直径：DN%d（应在 DN%d~%d）。'
                     % (dn, DN_MIN, DN_MAX))


def multiplier_choices():
    return tuple(STANDARD_MULTIPLIERS)


def multiplier_label(multiplier):
    return '%.1fD' % float(multiplier)


def snap_multiplier(ratio):
    """把实测的「中心至端面 ÷ 英寸公称」比值吸附到最近的标准倍率。"""
    value = float(ratio)
    return min(STANDARD_MULTIPLIERS, key=lambda item: abs(item - value))


def multiplier_from_center_to_end(dn, center_to_end_mm):
    """由模型实测的中心至端面长度反推弯头倍率（90° 弯头该长度即弯曲半径）。

    返回 ``(倍率, 是否与标准倍率吻合)``；比值离最近标准值超过 5% 时后者为
    ``False``，提示模型可能不是标准弯头（面板会据此给出告警）。
    """
    try:
        center_to_end = float(center_to_end_mm)
    except (TypeError, ValueError):
        raise ValueError('弯头中心至端面长度无效：%r' % (center_to_end_mm,))
    if not math.isfinite(center_to_end) or center_to_end <= 0.0:
        raise ValueError('弯头中心至端面长度必须大于 0（实测 %.3f mm）。'
                         % center_to_end)
    ratio = center_to_end / nominal_mm(dn)
    snapped = snap_multiplier(ratio)
    return snapped, abs(ratio - snapped) <= 0.05 * snapped


def bend_radius_mm(dn, multiplier):
    """弯头中心线弯曲半径 R = 倍率 × 英寸公称直径（mm）。"""
    dn = int(dn)
    if dn < DN_MIN or dn > DN_MAX:
        raise ValueError('管径 DN%d 超出本次范围 DN%d~%d。' % (dn, DN_MIN, DN_MAX))
    value = float(multiplier)
    if not math.isfinite(value) or not (MIN_MULTIPLIER <= value <= MAX_MULTIPLIER):
        raise ValueError('弯头倍率 %.3f 不合理，要求 %.1f~%.1f。'
                         % (value, MIN_MULTIPLIER, MAX_MULTIPLIER))
    return value * nominal_mm(dn)


# ---------------------------------------------------------------------------
# 编号
# ---------------------------------------------------------------------------


def build_number(dn, multiplier):
    """垫板编号：``弯头垫板-管径-弯头倍率``（如 ``弯头垫板-100-1.5``）。"""
    return '弯头垫板-%d-%.1f' % (int(dn), float(multiplier))


# ---------------------------------------------------------------------------
# 尺寸推导
# ---------------------------------------------------------------------------

ElbowFrame = namedtuple('ElbowFrame', 'arc_center axis_x axis_z radius_mm')

Layout = namedtuple('Layout', (
    'dn', 'nps', 'od_mm', 'pipe_radius',
    'thickness', 'inner_radius', 'outer_radius',
    'alpha_deg', 'alpha_rad',
    'multiplier', 'bend_radius_mm', 'elbow_angle_deg',
    'coverage_deg', 'coverage_start_deg', 'coverage_end_deg',
    'arc_length_mm',
    'material_code', 'pipe_material', 'temp_range', 'pad_material',
    'vent_hole_dia', 'has_vent_hole',
    'number',
))


def build_layout(dn, multiplier=DEFAULT_MULTIPLIER,
                 material_code=DEFAULT_MATERIAL_CODE,
                 alpha_deg=WRAP_ALPHA_DEG, coverage_deg=COVERAGE_DEG,
                 has_vent_hole=True):
    """按 DN + 弯头倍率推导整套尺寸（mm），供建模 / 清单使用。

    截面与 Y2 一致（内弧 = 管外径/2，外弧 = 内弧 + T，张角 ``alpha_deg``），
    沿弯头中心线圆弧扫掠，覆盖 ``coverage_deg`` 且居中于弯头中点。
    """
    dn = int(dn)
    if dn < DN_MIN or dn > DN_MAX:
        raise ValueError('管径 DN%d 超出本次范围 DN%d~%d。'
                         % (dn, DN_MIN, DN_MAX))

    radius = bend_radius_mm(dn, multiplier)
    multiplier = float(multiplier)

    row = material_for_code(material_code)
    code = str(material_code).strip().upper()

    alpha = float(alpha_deg)
    if not math.isfinite(alpha) or not (pad_geom.MIN_ALPHA_DEG
                                        <= alpha <= pad_geom.MAX_ALPHA_DEG):
        raise ValueError('截面张角 α=%.3f° 不合理，要求 %.0f°~%.0f°。'
                         % (alpha, pad_geom.MIN_ALPHA_DEG,
                            pad_geom.MAX_ALPHA_DEG))

    coverage = float(coverage_deg)
    if (not math.isfinite(coverage)
            or not (MIN_COVERAGE_DEG <= coverage <= MAX_COVERAGE_DEG)):
        raise ValueError('沿弯头覆盖角 %.3f° 不合理，要求 %.0f°~%.0f°。'
                         % (coverage, MIN_COVERAGE_DEG, MAX_COVERAGE_DEG))

    half = coverage / 2.0
    start = COVERAGE_CENTER_DEG - half
    end = COVERAGE_CENTER_DEG + half

    od = od_mm(dn)
    thickness = plate_thickness_mm(dn)
    inner_radius = od / 2.0
    outer_radius = inner_radius + thickness

    return Layout(
        dn=dn, nps=nps_text(dn), od_mm=od, pipe_radius=inner_radius,
        thickness=thickness, inner_radius=inner_radius,
        outer_radius=outer_radius,
        alpha_deg=alpha, alpha_rad=math.radians(alpha),
        multiplier=multiplier, bend_radius_mm=radius,
        elbow_angle_deg=ELBOW_ANGLE_DEG,
        coverage_deg=coverage, coverage_start_deg=start, coverage_end_deg=end,
        arc_length_mm=radius * math.radians(coverage),
        material_code=code,
        pipe_material=row['pipe_material'], temp_range=row['temp_range'],
        pad_material=row['pad_material'],
        vent_hole_dia=float(VENT_HOLE_DIA_MM),
        has_vent_hole=bool(has_vent_hole),
        number=build_number(dn, multiplier),
    )


# ---------------------------------------------------------------------------
# 弯头中心线（圆弧）几何
# ---------------------------------------------------------------------------


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1.0e-12:
        raise ValueError('方向向量长度为零。')
    return tuple(component / length for component in vector)


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def build_frame(origin_mm, axis_x, axis_z, dn, multiplier):
    """由 OPM 弯头局部坐标（端口 0 原点 / 入口切线 / 指向弯曲中心方向）建系。

    与 ``F5`` 的 ``horizontal_elbow_frame_from_matrix`` 同一套解析，但这里
    **不限制**弯头所在的平面（背弧垫板对任何朝向的弯头都成立）。
    """
    axis_x = _normalize(axis_x)
    axis_z = _normalize(axis_z)
    if abs(sum(axis_x[index] * axis_z[index] for index in range(3))) > 0.02:
        raise ValueError('弯头变换矩阵的 X/Z 轴不正交。')
    radius = bend_radius_mm(dn, multiplier)
    origin = tuple(float(value) for value in origin_mm)
    arc_center = tuple(origin[index] + axis_z[index] * radius
                       for index in range(3))
    return ElbowFrame(arc_center, axis_x, axis_z, radius)


def extrados_dir(frame, t_deg):
    """参数 ``t`` 处的**背弧方向**（由弯曲中心指向管外，半径方向）。"""
    angle = math.radians(float(t_deg))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return tuple(frame.axis_x[index] * sin_a - frame.axis_z[index] * cos_a
                 for index in range(3))


def path_tangent(frame, t_deg):
    """参数 ``t`` 处的中心线切线（= 扫掠方向）。"""
    angle = math.radians(float(t_deg))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return tuple(frame.axis_z[index] * sin_a + frame.axis_x[index] * cos_a
                 for index in range(3))


def path_point(frame, t_deg):
    """参数 ``t`` 处的中心线点 ``P(t) = arc_center + R * r(t)``。"""
    outward = extrados_dir(frame, t_deg)
    return tuple(frame.arc_center[index] + frame.radius_mm * outward[index]
                 for index in range(3))


def bend_plane_normal(frame):
    """弯曲平面法向（截面周向），= axis_x × axis_z。"""
    return _normalize(_cross(frame.axis_x, frame.axis_z))


def path_points(frame, layout):
    """中心线圆弧的 ``(起点, 中点, 终点)``，供三点定弧构造扫掠路径。"""
    return (path_point(frame, layout.coverage_start_deg),
            path_point(frame, COVERAGE_CENTER_DEG),
            path_point(frame, layout.coverage_end_deg))


def sweep_frame(frame, layout):
    """扫掠起点处的本地方位系 ``(ex, ey, ez, origin)``。

    * ``ex`` = 中心线切线（**扫掠方向**，与 Y2 ``_frame`` 的 ``ex`` 同位）；
    * ``ez`` = **背弧方向的反向**，使截面局部 ``+z`` 指向管内、垫板居中于
      ``−z``（背弧）——与 Y2 ``section_segments`` 的约定一致；
    * ``ey`` = 弯曲平面法向（截面周向），取 ``ez × ex`` 保持右手系；
    * ``origin`` = 覆盖起点（``t = coverage_start``）的中心线点。

    ``world = origin + x * ex + y * ey + z * ez``，与 Y2 的 ``_world`` 同构，
    因此 ``section_segments`` 的 ``(y, z)`` 可直接喂进来。
    """
    start_deg = layout.coverage_start_deg
    outward = extrados_dir(frame, start_deg)
    tangent = path_tangent(frame, start_deg)
    ez = (-outward[0], -outward[1], -outward[2])
    ey = _cross(ez, tangent)
    return (tangent, ey, ez, path_point(frame, start_deg))


def vent_hole_axis(frame, layout, margin_mm):
    """气孔轴线 ``(外端, 内端)``：位于覆盖中点背弧冠线，沿背弧径向贯穿板厚。

    垫板材料占据距弯曲中心 ``[R + Ri, R + Ro]`` 的环带，故外端在 ``R + Ro``
    之外、内端在 ``R + Ri`` 之内，轴线沿背弧方向 ``r``。
    """
    outward = extrados_dir(frame, COVERAGE_CENTER_DEG)
    center = path_point(frame, COVERAGE_CENTER_DEG)
    outer_end = tuple(center[index] + outward[index]
                      * (layout.outer_radius + margin_mm) for index in range(3))
    inner_end = tuple(center[index] + outward[index]
                      * (layout.inner_radius - margin_mm) for index in range(3))
    return outer_end, inner_end


# ---------------------------------------------------------------------------
# 截面轮廓（复用 Y2 的「直线 + 真圆弧」实现）
# ---------------------------------------------------------------------------


def section_segments(layout):
    """截面轮廓段（``('arc', 三点)`` / ``('line', 两点)``），真圆弧不平滑化。"""
    return pad_geom.section_segments(layout)


def section_points(layout, segment_deg=pad_geom.ARC_SEGMENT_DEG):
    """截面轮廓的折线近似点列（量算 / 建模回退用）。"""
    return pad_geom.section_points(layout, segment_deg)


def arc_step_count(alpha_deg, segment_deg=pad_geom.ARC_SEGMENT_DEG):
    return pad_geom.arc_step_count(alpha_deg, segment_deg)


# ---------------------------------------------------------------------------
# 量算
# ---------------------------------------------------------------------------


def section_area_mm2(layout):
    """截面面积（mm²）：环形扇形 − 气孔。"""
    return pad_geom.section_area_mm2(layout)


def section_centroid_offset_mm(layout):
    """截面形心到中心线的距离（mm，沿背弧方向为正）。

    环形扇形的形心在对称轴上，距圆心
    ``2·sin(α/2)·(Ro³−Ri³) / (3·(α/2)·(Ro²−Ri²))``；取背弧侧为正号。
    """
    half = layout.alpha_rad / 2.0
    inner_radius = float(layout.inner_radius)
    outer_radius = float(layout.outer_radius)
    numerator = 2.0 * math.sin(half) * (outer_radius ** 3 - inner_radius ** 3)
    denominator = 3.0 * half * (outer_radius ** 2 - inner_radius ** 2)
    return numerator / denominator


def plate_volume_mm3(layout):
    """护板体积（mm³）：帕普斯定理 —— 截面积 × 形心走过的弧长。"""
    centroid_radius = float(layout.bend_radius_mm) + section_centroid_offset_mm(layout)
    return (section_area_mm2(layout) * centroid_radius
            * math.radians(float(layout.coverage_deg)))


def plate_mass_kg(layout):
    """护板理论质量（kg）。"""
    return plate_volume_mm3(layout) * STEEL_DENSITY_KG_MM3


def layout_summary(layout):
    """一行文字摘要（面板显示用）。"""
    return ('%s：%s OD%.1f / 内弧 R%.1f / 外弧 R%.1f（T%.0f）/ 弯曲 R%.1f'
            '（%.1fD）/ 覆盖 %.0f° / 周向 %.0f° / %s %s' % (
                layout.number, dn_label(layout.dn), layout.od_mm,
                layout.inner_radius, layout.outer_radius, layout.thickness,
                layout.bend_radius_mm, layout.multiplier,
                layout.coverage_deg, layout.alpha_deg,
                layout.material_code, layout.pad_material))