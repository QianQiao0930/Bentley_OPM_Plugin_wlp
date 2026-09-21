# -*- coding: utf-8 -*-
"""T 形架（类型 1）放置工具。

在模型中点选一条用户绘制的 **竖直线**（立柱轴线；允许 ±5° 以内的轻微倾斜），
并在面板上输入横担全长 **L**、选择类型，据此生成一组 T 形架：

    所选竖直线 = 立柱轴线；线长即立柱长 H
    L          = 横担全长（用户输入，表 1 / 表 2 的查表参数之一）
    横担以所选竖直线为中点、垂直于立柱，取**世界水平**方向（面板「朝向」）

单根立柱居中、横担居中，构成 T 形；两类型都保留横担长边水平、用于放管道：

* **类型 1（正 T 形架）**：横担在竖直线顶端（管位朝上），下端为基座（落在已有
  钢结构上）。
* **类型 2（倒 T 形吊架，立柱在上）**：横担在竖直线下端（管位朝上，与类型 1
  同向），立柱向上到竖直线顶端（接已有结构）。

立柱与横担**同规格**（构件 A）：

* 角钢子项（A~C）**背靠背**：立柱的 u-w 平面肢与横担竖直肢背面相贴，留 10 mm
  施焊间隙；
* H 型钢子项（D~G）**端面焊接**：立柱端面焊接横担翼缘面，两者腹板共面。

每个子项都有**最大允许 H / L**（见表 1 / 表 2），超限会被拒绝生成。

整组构件（立柱 + 横担）写成一个普通单元（Normal Cell），清单写入**管道支吊架
公共库** ``支吊架公共库``（`SupportType='T形架'`），可与端焊三角架、L 型管架、
门型架一起统计；可导出 JSON / Excel 清单。

几何做法（型钢截面的真实圆弧轮廓与沿路径扫掠）复用仓库内
``型钢截面生成器`` 的数据 / 几何模块与 ``steel_sweep_geometry``；
面板外观复用 ``模块/公共/端焊三角架_基础.py``；
纯几何 / 数据逻辑在 ``T形架_几何.py``（可单测）。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import math
import os
import sys
import time
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 通配导入不一定导出这两个符号，显式再导入一次（与其它插件一致）。
from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

# tkinter 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致 tk / ttk 被替换、建控件 / 事件循环时直接崩溃。
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
# 公共库在 模块/公共/，本插件几何在 模块/T形架/；仓库根提供共享 UI 工具箱。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'T形架')
for _path in (COMMON_DIR, GEOM_DIR, STEEL_DIR, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
try:
    import bentley_ui.glass as _glass_module  # noqa: F401
    import bentley_ui as _bentley_ui_module  # noqa: F401
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (  # noqa: E402
    BORDER,
    CARD,
    CARD_SOFT,
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    ScrollFrame,
)

import T形架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402  地面固定的锚板 / 锚栓基元
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'T形架'
SUPPORT_CODE = 'T_FRAME'


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'T形架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'T形架'

# 整组构件写入的普通单元名。
CELL_NAME = 'T_FRAME'

COMPONENT_POST_NAME = '立柱'
COMPONENT_ARM_NAME = '横担'

# 默认横担长 L（mm）、横担方向「朝向」（°）：0 = 世界 +X（立柱竖直时使用）。
DEFAULT_ARM_LENGTH_MM = 500.0
DEFAULT_HEADING_DEG = 0.0

# 现场灌浆保护层的元素颜色（混凝土色；可按项目色表调整）。
GROUND_GROUT_COLOR = 5

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    """每次运行都强制重新读取本插件与依赖模块，规避 MicroStation 缓存。"""
    importlib.invalidate_caches()
    for module in (geom, steel_sweep_geometry, psb, anchor):
        try:
            importlib.reload(module)
        except Exception:
            pass
    for name in ('steel_sections.steel_equal_angle_data', 'steel_sections.steel_equal_angle_geometry',
                 'steel_sections.steel_hbeam_data', 'steel_sections.steel_hbeam_geometry'):
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception:
                pass


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _point_to_mm(point, uor_per_mm):
    return (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)


def _to_uor(point_mm, uor_per_mm):
    return (point_mm[0] * uor_per_mm, point_mm[1] * uor_per_mm,
            point_mm[2] * uor_per_mm)


# ---------------------------------------------------------------------------
# 所选元素提取（UOR -> mm 点列）
# ---------------------------------------------------------------------------


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _collect_linear_pieces(curve_vector, pieces):
    for primitive in curve_vector:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
            segment = primitive.GetLine()
            pieces.append([_copy_dpoint(segment.StartPoint),
                           _copy_dpoint(segment.EndPoint)])
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
            points = [_copy_dpoint(point) for point in primitive.GetLineString()]
            if len(points) >= 2:
                pieces.append(points)
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
            child = primitive.GetChildCurveVector()
            if child is None:
                raise ValueError('所选元素含无法读取的子路径。')
            _collect_linear_pieces(child, pieces)
        else:
            raise ValueError('所选元素含圆弧或曲线；请选择一条竖直的直线段。')


def extract_line(element_handle):
    """从所选元素提取并校验竖直线（立柱轴线），返回 ``T形架_几何.SelectedLine``。"""
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条竖直线段（立柱轴线）。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    pieces_mm = [[_point_to_mm(point, uor_per_mm) for point in piece]
                 for piece in pieces]
    return geom.parse_selected_line(pieces_mm)


# ---------------------------------------------------------------------------
# 型钢截面 -> Bentley 曲线 -> 扫掠实体
# ---------------------------------------------------------------------------


def _dpoint(point):
    try:
        return DPoint3d.From(point[0], point[1], point[2])
    except Exception:
        return DPoint3d(point[0], point[1], point[2])


def _open_boundary_type():
    for name in ('eBOUNDARY_TYPE_Open', 'eBOUNDARY_TYPE_Outer'):
        value = getattr(CurveVector, name, None)
        if value is not None:
            return value
    return CurveVector.eBOUNDARY_TYPE_Outer


def _profile_curve(geometry, frame):
    """把截面轮廓按坐标架映射到世界，构建闭合 CurveVector（保留真圆弧）。"""
    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for segment in geometry.segments:
        points = steel_sweep_geometry.sample_segment(segment, frame)
        world = [_dpoint(point) for point in points]
        if len(world) == 2:
            profile.Add(ICurvePrimitive.CreateLine(DSegment3d(world[0], world[1])))
        else:
            profile.Add(ICurvePrimitive.CreateArc(
                DEllipse3d.FromPointsOnArc(world[0], world[1], world[2])))
    return profile


def _line_curve(start, end):
    curve = CurveVector(_open_boundary_type())
    curve.Add(ICurvePrimitive.CreateLine(
        DSegment3d(_dpoint(start), _dpoint(end))))
    return curve


def _sweep_body(profile_curve, path_curve, model_ref, origin, up_axis):
    """沿直线路径扫掠截面，兼容 BodyFromSweep 的不同签名。"""
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    start = DPoint3d.From(origin[0], origin[1], origin[2])

    def ten_arg_none():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, None, None, None,
        )

    def ten_arg_scalars():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, 0.0, 1.0, start,
        )

    def six_arg():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False
        )

    last_error = None
    for attempt in (ten_arg_none, ten_arg_scalars, six_arg):
        try:
            result = attempt()
        except Exception as error:
            last_error = error
            continue
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            continue
        if result[0] == BentleyStatus.eSUCCESS and result[1] is not None:
            return result[1]
    raise RuntimeError('沿路径扫掠失败：%s' % last_error)


def _body_to_element(body, dgn_model, component_name):
    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
            solid, body, None, dgn_model):
        _log('%s: BodyToElement failed' % component_name)
        return None
    return solid


def _build_member_element(variant_key, member_kind, line, heading_deg,
                          arm_length_mm, uor_per_mm, dgn_model, rack_type=1):
    """构建一个构件（立柱 / 横担）实体元素，不写入模型。

    截面朝向与扫掠起点由 ``T形架_几何`` 的 ``member_section_params`` /
    ``member_axes`` / ``member_origin_length`` 给出，坐标系为局部基 (u, v, w)，
    原点取所选竖直线的下端；``frame_axes`` 把 (u, v, w) 换算到世界。
    """
    geometry = geom.member_geometry(variant_key, member_kind, uor_per_mm)
    u_dir, v_dir, w_dir = geom.frame_axes(heading_deg)
    axes = geom.member_axes(variant_key, member_kind, rack_type)
    axis_x = geom.world_direction(u_dir, v_dir, w_dir, axes[0])
    axis_y = geom.world_direction(u_dir, v_dir, w_dir, axes[1])
    axis_z = geom.world_direction(u_dir, v_dir, w_dir, axes[2])
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, line.length_mm, arm_length_mm, rack_type)

    base_uor = _to_uor(line.base, uor_per_mm)
    origin = (
        base_uor[0] + origin_uvw[0] * uor_per_mm * u_dir[0]
        + origin_uvw[1] * uor_per_mm * v_dir[0]
        + origin_uvw[2] * uor_per_mm * w_dir[0],
        base_uor[1] + origin_uvw[0] * uor_per_mm * u_dir[1]
        + origin_uvw[1] * uor_per_mm * v_dir[1]
        + origin_uvw[2] * uor_per_mm * w_dir[1],
        base_uor[2] + origin_uvw[0] * uor_per_mm * u_dir[2]
        + origin_uvw[1] * uor_per_mm * v_dir[2]
        + origin_uvw[2] * uor_per_mm * w_dir[2],
    )
    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    profile = _profile_curve(geometry, frame)
    length = length_mm * uor_per_mm
    end = (origin[0] + axis_z[0] * length,
           origin[1] + axis_z[1] * length,
           origin[2] + axis_z[2] * length)
    path = _line_curve(origin, end)
    body = _sweep_body(profile, path, dgn_model, frame.origin, frame.axis_y)
    return _body_to_element(body, dgn_model, member_kind)


def _square_corners(cx, cy, z, side):
    """返回水平正方形（边长 side，中心 (cx, cy)，高度 z）的 4 个角点。"""
    half = side / 2.0
    corners = DPoint3dArray()
    for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
        corners.append(DPoint3d.From(cx + dx, cy + dy, z))
    return corners


def _triangle_corners(points):
    corners = DPoint3dArray()
    for x, y, z in points:
        corners.append(DPoint3d.From(x, y, z))
    return corners


def _element_body(element):
    if element is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if not _succeeded(status):
        return None
    return body


def _build_frustum_elements(dgn_model, cx, cy, bottom_z, bottom_side,
                            top_z, top_side, color, label):
    """生成梯台：先建方体，再对顶面四条棱做 45° 倒角（切削楔体）。

    底面 bottom_side、顶面 top_side、高 top_z-bottom_z；倒角量为
    ``(bottom_side - top_side) / 2``，即 45°（斜向外扩）。返回 [元素]。
    """
    height = top_z - bottom_z
    if height <= 0.0:
        return []
    chamfer = (bottom_side - top_side) / 2.0

    box = anchor._prism_with_holes(
        dgn_model, _square_corners(cx, cy, bottom_z, bottom_side), height,
        color, ())
    body = _element_body(box)
    if body is None:
        _log('%s: 方体创建失败' % label)
        return []
    if chamfer <= 1.0e-9:
        return [box]

    half = bottom_side / 2.0
    xl, xr = cx - half, cx + half
    yl, yr = cy - half, cy + half
    z_ch = top_z - chamfer            # 倒角起始高度（留 5mm 直段）
    length = bottom_side              # 楔体沿棱方向跨满整个边长

    # 4 个 45° 楔形刀：+Y / -Y 棱沿 X 拉伸；+X / -X 棱沿 Y 拉伸。
    wedges = (
        ((xl, yr, z_ch), (xl, yr, top_z), (xl, yr - chamfer, top_z)),
        ((xl, yl, z_ch), (xl, yl + chamfer, top_z), (xl, yl, top_z)),
        ((xr, yl, z_ch), (xr - chamfer, yl, top_z), (xr, yl, top_z)),
        ((xl, yl, z_ch), (xl, yl, top_z), (xl + chamfer, yl, top_z)),
    )
    cutters = []
    for wedge in wedges:
        cutter = anchor._prism_with_holes(
            dgn_model, _triangle_corners(wedge), length, color, ())
        cutter_body = _element_body(cutter)
        if cutter_body is not None:
            cutters.append(cutter_body)
    if cutters:
        anchor._subtract(body, cutters)

    element = EditElementHandle()
    if _succeeded(SolidUtil.Convert.BodyToElement(element, body, box, dgn_model)):
        return [anchor._apply_color(element, color)]
    _log('%s: 倒角后实体转元素失败' % label)
    return []


def _nut_size_for(bolt_dia):
    """按锚栓直径返回六角螺母的 (对边宽, 高)（mm）。"""
    for entry in anchor.ANCHOR_TABLE.values():
        if abs(float(entry['bolt_dia']) - float(bolt_dia)) < 1.0e-6:
            return float(entry['nut_af']), float(entry['nut_h'])
    dia = float(bolt_dia)
    return (dia * 1.6, dia * 0.8)


def _build_ground_anchor_elements(dgn_model, line, variant_key, uor_per_mm):
    """地面固定：锚板 + 4 根膨胀锚栓 + 现场灌浆保护层（返回元素列表）。

    锚板参数取自 ``T形架_几何.GROUND_ANCHOR_TABLE``（表 2）：
    锚板 E×E×T，四角 4-φG 孔按 F×F 居中布置；锚栓沿孔位向下埋入；
    锚板下方为现场灌浆保护层：顶面与锚板同尺寸、向下高
    :data:`geom.GROUND_GROUT_THICKNESS_MM`、每边斜向外扩
    :data:`geom.GROUND_GROUT_FLARE_MM`（梯台/棱台状）。以所选竖直线的
    下端（基座）为锚板**顶面中心**。
    """
    spec = geom.ground_anchor_spec(variant_key)
    e = spec['plate_e'] * uor_per_mm
    f = spec['hole_spacing_f'] * uor_per_mm
    g = spec['hole_dia_g'] * uor_per_mm
    t = spec['plate_t'] * uor_per_mm
    bolt_r = spec['bolt_dia'] * uor_per_mm / 2.0
    bolt_len = spec['bolt_len'] * uor_per_mm
    grout_t = geom.GROUND_GROUT_THICKNESS_MM * uor_per_mm
    grout_flare = geom.GROUND_GROUT_FLARE_MM * uor_per_mm

    bx, by, bz = _to_uor(line.base, uor_per_mm)
    hole_half = f / 2.0
    hole_r = g / 2.0
    plate_bottom = bz - t

    elements = []

    # 锚板：顶面在基座高度，向下厚 T；四个螺栓孔。
    holes = []
    for dx in (-hole_half, hole_half):
        for dy in (-hole_half, hole_half):
            holes.append((
                DPoint3d.From(bx + dx, by + dy, plate_bottom - 2.0 * uor_per_mm),
                DPoint3d.From(bx + dx, by + dy, bz + 2.0 * uor_per_mm),
                hole_r,
            ))
    plate = anchor._prism_with_holes(
        dgn_model, _square_corners(bx, by, plate_bottom, e), t,
        anchor.COLOR_PLATE, holes)
    if plate is None:
        raise RuntimeError('锚板实体创建失败。')
    elements.append(plate)

    # 膨胀锚栓：总长 L 不变；螺杆顶端高出螺母顶面 5 mm，底端按总长回算。
    nut_af, nut_h = _nut_size_for(spec['bolt_dia'])
    bolt_top = bz + (nut_h + anchor.BOLT_PROTRUSION) * uor_per_mm
    bolt_bottom = bolt_top - bolt_len
    for dx in (-hole_half, hole_half):
        for dy in (-hole_half, hole_half):
            rod = anchor._cylinder(
                dgn_model,
                DPoint3d.From(bx + dx, by + dy, bolt_top),
                DPoint3d.From(bx + dx, by + dy, bolt_bottom),
                bolt_r, anchor.COLOR_BOLT)
            if rod is None:
                raise RuntimeError('膨胀锚栓实体创建失败。')
            elements.append(rod)
            # 螺母：坐在锚板顶面上方（局部 X = 世界 +Z 的竖直六棱柱）。
            frame = anchor._PlateFrame(
                DPoint3d.From(bx + dx, by + dy, bz), uor_per_mm, 0.0, 'floor')
            nut = anchor._hex_prism(
                dgn_model, frame, 0.0, 0.0, 0.0, nut_h, nut_af,
                anchor.COLOR_NUT)
            if nut is None:
                raise RuntimeError('螺母实体创建失败。')
            elements.append(nut)

    # 现场灌浆保护层：锚板下方，顶面 E×E、底面 (E+2×外扩)×(...) 的梯台。
    grout_top = plate_bottom
    grout_bottom = plate_bottom - grout_t
    grout_elements = _build_frustum_elements(
        dgn_model, bx, by, grout_bottom, e + 2.0 * grout_flare,
        grout_top, e, GROUND_GROUT_COLOR, '现场灌浆')
    if not grout_elements:
        raise RuntimeError('现场灌浆保护层实体创建失败。')
    elements.extend(grout_elements)

    _log('ground anchor built: variant=%s E=%.0f F=%.0f G=%.0f T=%.0f '
         'bolt=M%.0f×%.0f grout(h=%.0f,flare=%.0f)' % (
             variant_key, spec['plate_e'], spec['hole_spacing_f'],
             spec['hole_dia_g'], spec['plate_t'], spec['bolt_dia'],
             spec['bolt_len'], geom.GROUND_GROUT_THICKNESS_MM,
             geom.GROUND_GROUT_FLARE_MM))
    return elements


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


class _TFrameCellBuilder(object):
    """把立柱、横担子元素一次性写成一个普通单元。"""

    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell_name = cell_name or CELL_NAME
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('T形架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法把 T形架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成 T形架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法把 T形架单元写入活动模型。')
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


# ---------------------------------------------------------------------------
# ItemType：写入公共支吊架库
# ---------------------------------------------------------------------------


def _attach_support_items(cell, result):
    """把整组 T形架写入共享支吊架库（整组记录 + 立柱/横担构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=result.get('specification', ''),
        components=result.get('bom_items', ()),
    )


# ---------------------------------------------------------------------------
# 构建整组 T形架
# ---------------------------------------------------------------------------


def _validate_limits(variant_key, height_mm, arm_length_mm):
    """校验子项的最大允许 H / L。"""
    max_height = geom.max_allowed_height(variant_key)
    if max_height is not None and height_mm > max_height + geom.LOAD_TOLERANCE_MM:
        raise ValueError(
            '立柱长 H=%.0f mm 超过子项 %s 的最大允许 H=%d mm。'
            % (height_mm, variant_key, max_height))
    max_arm = geom.max_allowed_arm_length(variant_key)
    if max_arm is not None and arm_length_mm > max_arm + geom.LOAD_TOLERANCE_MM:
        raise ValueError(
            '横担长 L=%.0f mm 超过子项 %s 的最大允许 L=%d mm。'
            % (arm_length_mm, variant_key, max_arm))


def _build_t_frame_cell(line, variant_key, rack_type, arm_length_mm,
                        heading_deg, rack_name=None, ground_fixed=False):
    """按所选竖直线与横担长 L 构建 T形架单元但**不写入模型**。

    ``ground_fixed=True`` 时额外生成地面固定的锚板 + 膨胀锚栓 + 现场灌浆
    保护层，并使用 ``G4-子项-H-L`` 编号（名称固定为 G4）。

    返回 ``(builder, 统计字典)``。
    """
    if not geom.variant_supports_type(variant_key, rack_type):
        raise ValueError(
            '本插件仅实现类型 %s；子项 %s 不适用于类型 %s。'
            % ('/'.join(str(t) for t in geom.allowed_rack_types(variant_key)),
               variant_key, rack_type))

    arm_length_mm = float(arm_length_mm)
    if arm_length_mm < geom.MIN_ARM_LENGTH_MM:
        raise ValueError('横担长 L=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (arm_length_mm, geom.MIN_ARM_LENGTH_MM))
    _validate_limits(variant_key, line.length_mm, arm_length_mm)
    if ground_fixed and geom.hanger_type(rack_type):
        raise ValueError('地面固定（生成锚板）只适用于类型 1（立柱在下）。')

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    uor_per_mm = _uor_per_mm(dgn_model)

    # 单根立柱：轴线即所选竖直线，截面外接矩形中心落在轴线上。
    post = _build_member_element(
        variant_key, 'post', line, heading_deg, arm_length_mm,
        uor_per_mm, dgn_model, rack_type)
    if post is None:
        raise RuntimeError('立柱实体创建失败。')

    # 横担：以所选竖直线为中点、两端各 L/2，管位面水平。
    arm = _build_member_element(
        variant_key, 'arm', line, heading_deg, arm_length_mm,
        uor_per_mm, dgn_model, rack_type)
    if arm is None:
        raise RuntimeError('横担实体创建失败。')

    builder = _TFrameCellBuilder(dgn_model)
    builder.add(post)
    builder.add(arm)

    # 地面固定：锚板 + 膨胀锚栓 + 现场灌浆保护层。
    if ground_fixed:
        for element in _build_ground_anchor_elements(
                dgn_model, line, variant_key, uor_per_mm):
            builder.add(element)

    builder.build()

    spec = geom.specification(variant_key)
    post_cut_length = geom.post_length(variant_key, line.length_mm, rack_type)
    weld_contact = geom.weld_contact_length(variant_key, rack_type)
    if ground_fixed:
        rack_number = geom.ground_anchor_number(
            variant_key, line.length_mm, arm_length_mm,
            geom.GROUND_ANCHOR_NAME)
    else:
        rack_number = geom.build_pipe_rack_number(
            rack_name or '', rack_type, variant_key, line.length_mm,
            arm_length_mm)

    load = geom.allowable_load(variant_key, line.length_mm, arm_length_mm)
    if load.value is None:
        builder.note('允许垂直荷载未取到：%s' % load.message)

    bom_items = [
        {'code': 'Post', 'name': COMPONENT_POST_NAME,
         'specification': spec, 'length': post_cut_length,
         'quantity': 1, 'unit': '根'},
        {'code': 'Arm', 'name': COMPONENT_ARM_NAME,
         'specification': spec, 'length': arm_length_mm,
         'quantity': 1, 'unit': '根'},
    ]
    anchor_spec = None
    if ground_fixed:
        anchor_spec = geom.ground_anchor_spec(variant_key)
        plate_spec = ('E×E×T=%.0f×%.0f×%.0f，4-φ%.0f 孔（F=%.0f）'
                      % (anchor_spec['plate_e'], anchor_spec['plate_e'],
                         anchor_spec['plate_t'], anchor_spec['hole_dia_g'],
                         anchor_spec['hole_spacing_f']))
        bom_items.append(
            {'code': 'AnchorPlate', 'name': '锚板',
             'specification': plate_spec, 'length': anchor_spec['plate_t'],
             'quantity': 1, 'unit': '块'})
        bom_items.append(
            {'code': 'AnchorBolt', 'name': '膨胀锚栓',
             'specification': 'M%.0f×%.0f（h_ef=%.0f）' % (
                 anchor_spec['bolt_dia'], anchor_spec['bolt_len'],
                 anchor_spec['embed']),
             'length': anchor_spec['bolt_len'],
             'quantity': 4, 'unit': '套'})
        bom_items.append(
            {'code': 'AnchorNut', 'name': '螺母',
             'specification': 'M%.0f' % anchor_spec['bolt_dia'],
             'quantity': 4, 'unit': '个'})
        bom_items.append(
            {'code': 'Grout', 'name': '现场灌浆',
             'specification': '高 %.0f，每边斜向外扩 %.0f（梯台）' % (
                 geom.GROUND_GROUT_THICKNESS_MM, geom.GROUND_GROUT_FLARE_MM),
             'length': geom.GROUND_GROUT_THICKNESS_MM,
             'quantity': 1, 'unit': '处'})

    result = {
        'variant': variant_key,
        'rack_type': int(rack_type),
        'child_count': builder.child_count,
        'height': line.length_mm,
        'arm_length': arm_length_mm,
        'post_cut_length': post_cut_length,
        'weld_contact_length': weld_contact,
        'is_hbeam': geom.variant_is_hbeam(variant_key),
        'heading_deg': float(heading_deg),
        'specification': spec,
        'allowable_load': load.value,
        'max_height': geom.max_allowed_height(variant_key),
        'max_arm_length': geom.max_allowed_arm_length(variant_key),
        'pipe_rack_number': rack_number or '',
        'ground_fixed': bool(ground_fixed),
        'ground_anchor': anchor_spec,
        'bom_items': bom_items,
        'warnings': list(builder.warnings),
    }
    _log('t frame built: variant=%s, type=%d, H=%.1f, L=%.1f, post=%.1f, '
         'weld=%.1f, hbeam=%s, heading=%.2f, ground=%s, cells=%d, number=%s' %
         (variant_key, int(rack_type), line.length_mm, arm_length_mm,
          post_cut_length, weld_contact, result['is_hbeam'],
          float(heading_deg), bool(ground_fixed), builder.child_count,
          result['pipe_rack_number'] or '-'))
    return builder, result


def replace_t_frame(line, variant_key, previous_handle, rack_type=1,
                    arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                    heading_deg=DEFAULT_HEADING_DEG, rack_name=None,
                    ground_fixed=False):
    """重建 T形架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_t_frame_cell(
        line, variant_key, rack_type, arm_length_mm, heading_deg, rack_name,
        ground_fixed)
    new_handle = builder.commit()
    _attach_support_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_t_frame(line, variant_key, rack_type=1,
                 arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                 heading_deg=DEFAULT_HEADING_DEG, rack_name=None,
                 ground_fixed=False):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_t_frame_cell(
        line, variant_key, rack_type, arm_length_mm, heading_deg, rack_name,
        ground_fixed)
    cell = builder.commit()
    _attach_support_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', 'T形架_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


RACK_TYPE_OPTIONS = (
    (1, '类型1  |  正 T 形架（立柱在下、横担在上）'),
    (2, '类型2  |  倒 T 形吊架（立柱在上、横担在下）'),
)


class _TFrameDialog(GlassDialog):
    """子项 / L / 朝向 / 编号 选择，预览 / 导出 / 确定 / 取消面板。"""

    STATE_KEY = 'TFrame'
    # UI 刷新轮询周期（ms）：原生回调只写状态，由这个常驻定时器统一刷进控件。
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False

        # 关键：MicroStation 的原生回调（_OnPostLocate / _OnElementModify /
        # _OnResetButton / _OnCleanup）会在 Tk 的 update() 里被**重入式**调用；
        # 此时任何 Tcl 调用（after / StringVar.set 或 .get / 控件 configure /
        # destroy）都可能弄坏 Tcl 事件队列，随后直接崩溃。因此回调里只写普通
        # Python 状态，所有 Tk 刷新交给常驻定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._hover_line = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False

        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._rack_name = tk.StringVar(value='D12')
        self._arm = tk.StringVar(value='%.0f' % DEFAULT_ARM_LENGTH_MM)
        self._heading = tk.StringVar(value='%.0f' % DEFAULT_HEADING_DEG)
        self._keep_line = tk.BooleanVar(value=True)
        self._ground_fixed = tk.BooleanVar(value=False)
        self._name_before_ground = 'D12'
        self._spec = tk.StringVar(value='—')
        self._width = tk.StringVar(value='—')
        self._connection = tk.StringVar(value='—')
        self._height = tk.StringVar(value='—')
        self._max_height = tk.StringVar(value='—')
        self._max_arm = tk.StringVar(value='—')
        self._post_length = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._load_note = tk.StringVar(value='')
        self._rack_number = tk.StringVar(value='—')
        self._spec_info = tk.StringVar(value='')
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar(value='请选择一条竖直线段（立柱轴线）。')
        self._variant_by_label = {}
        self._type_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()

        # 关闭窗口时按"取消"处理：丢弃预览并结束工具。
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        _log('panel built file=%s' % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点选竖直线生成 T 形架 · 改参数自动重建预览')
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)
        # 参数与预览可滚动；实时状态和操作区始终钉在底部。
        self._scroll = ScrollFrame(form, bg=CARD, height=500)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text='点选竖直线（立柱轴线，允许 ±5° 倾斜），线长即 H；输入 L、'
                 '选择类型后自动预览。类型1：立柱在下、横担在上；类型2：'
                 '立柱在上、横担在下。点【确定】保留，点【取消】放弃。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=520,
        ).grid(row=0, column=0, sticky='ew')

        ttk.Label(body, text='构件规格（表 3）', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(12, 5))

        specification = tk.Frame(body, bg=CARD)
        specification.grid(row=2, column=0, sticky='ew')
        specification.columnconfigure(0, weight=1)

        ttk.Label(specification, text='子项', style='GlassMuted.TLabel').grid(
            row=0, column=0, sticky='w', pady=(0, 3))
        labels = []
        for key, label in geom.variant_choices():
            labels.append(label)
            self._variant_by_label[label] = key
        self._variant_combo = ttk.Combobox(
            specification, textvariable=self._variant, state='readonly',
            style='Glass.TCombobox', values=labels)
        self._variant_combo.grid(row=1, column=0, sticky='ew')
        self._variant_combo.bind('<<ComboboxSelected>>', self.on_options_changed)
        self._variant.set(self._label_for_variant(geom.DEFAULT_VARIANT, labels))

        specification_data = tk.Frame(specification, bg=CARD)
        specification_data.grid(row=2, column=0, sticky='ew', pady=(7, 0))
        specification_data.columnconfigure(0, weight=1, uniform='spec')
        specification_data.columnconfigure(1, weight=1, uniform='spec')
        self._compact_value(
            specification_data, 0, 0, '构件A（立柱 / 横担）', self._spec)
        self._compact_value(
            specification_data, 0, 1, '立柱截面宽 W', self._width,
            unit='mm', note='横担长度方向的截面宽度')
        self._compact_value(
            specification_data, 1, 0, '连接方式', self._connection,
            columnspan=2)

        ttk.Separator(body, orient='horizontal').grid(
            row=3, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='尺寸参数', style='Section.TLabel').grid(
            row=4, column=0, sticky='w', pady=(0, 5))

        dimensions = tk.Frame(body, bg=CARD)
        dimensions.grid(row=5, column=0, sticky='ew')
        dimensions.columnconfigure(0, weight=1, uniform='dimension')
        dimensions.columnconfigure(1, weight=1, uniform='dimension')

        # 输入项置顶；自动读取 / 查表 / 计算结果放在后面。
        self._arm_entry = self._compact_entry(
            dimensions, 0, 0, '横担长 L', self._arm, 9,
            unit='mm', note='用户输入；表 1 / 表 2 查表参数之一')
        self._heading_entry = self._compact_entry(
            dimensions, 0, 1, '朝向', self._heading, 9,
            unit='°', note='横担方向（0 = 世界 +X）')

        self._compact_value(
            dimensions, 1, 0, '立柱长 H', self._height,
            unit='mm', note='由所选直线自动读取')
        self._compact_value(
            dimensions, 1, 1, '最大允许 H', self._max_height,
            unit='mm', note='表 1 / 表 2')
        self._compact_value(
            dimensions, 2, 0, '最大允许 L', self._max_arm,
            unit='mm', note='表 1 / 表 2')
        self._compact_value(
            dimensions, 2, 1, '允许垂直荷载', self._load,
            unit='kN', notevariable=self._load_note)
        self._compact_value(
            dimensions, 3, 0, '立柱下料长', self._post_length,
            unit='mm',
            note='角钢：H − 肢厚 − 10；H 型钢：H − 横担截面高',
            columnspan=2)

        ttk.Separator(body, orient='horizontal').grid(
            row=6, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='管架编号', style='Section.TLabel').grid(
            row=7, column=0, sticky='w', pady=(0, 5))

        numbering = tk.Frame(body, bg=CARD)
        numbering.grid(row=8, column=0, sticky='ew')
        numbering.columnconfigure(0, weight=2, uniform='numbering')
        numbering.columnconfigure(1, weight=3, uniform='numbering')

        self._rack_name_entry = self._compact_entry(
            numbering, 0, 0, '名称', self._rack_name, 12,
            note='管架系列代号；留空则不附加编号')

        type_cell = tk.Frame(numbering, bg=CARD)
        type_cell.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(type_cell, text='类型', style='GlassMuted.TLabel').pack(
            anchor='w')
        type_labels = []
        for key, label in RACK_TYPE_OPTIONS:
            type_labels.append(label)
            self._type_by_label[label] = key
        self._rack_type_combo = ttk.Combobox(
            type_cell, textvariable=self._rack_type, state='readonly',
            style='Glass.TCombobox', values=type_labels)
        self._rack_type_combo.pack(fill='x', pady=(3, 0))
        self._rack_type_combo.bind('<<ComboboxSelected>>',
                                   self.on_options_changed)
        self._rack_type.set(type_labels[0])

        self._compact_value(
            numbering, 1, 0, '编号', self._rack_number,
            note='名称-类型-子项-H-L（整数）', columnspan=2)

        ttk.Separator(body, orient='horizontal').grid(
            row=9, column=0, sticky='ew', pady=10)

        # 构造方式长说明不再占用界面；保留变量和控件供既有校验逻辑使用。
        self._spec_info_label = tk.Label(
            body, textvariable=self._spec_info, bg=CARD, fg=MUTED,
            font=UI_FONT_SMALL, justify='left', anchor='w', wraplength=520)

        preview = tk.Frame(body, bg=CARD_SOFT, highlightbackground=BORDER,
                           highlightthickness=1)
        preview.grid(row=10, column=0, sticky='ew')
        tk.Label(preview, textvariable=self._preview_info, bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=500).pack(fill='x', padx=10, pady=7)

        # 实时状态独立于滚动区，参数区滚到任何位置时都保持可见。
        chip = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                        highlightthickness=1)
        chip.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self._status_label = tk.Label(
            chip, textvariable=self._status, bg=CARD_SOFT, fg='#1f5f99',
            font=UI_FONT_SMALL, wraplength=520, justify='left', anchor='w')
        self._status_label.pack(fill='x', padx=10, pady=7)

        # -- 钉在底部：创建选项 + 按钮 --------------------------------------
        creation_options = tk.Frame(form, bg=CARD)
        creation_options.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self._ground_check = tk.Checkbutton(
            creation_options, text='地面固定（生成锚板与现场灌浆保护层）',
            variable=self._ground_fixed, command=self.on_ground_fixed_changed,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._ground_check.pack(side='left')

        self._keep_check = tk.Checkbutton(
            creation_options, text='创建后保留所选直线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.pack(side='left', padx=(10, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        self._confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._export_button = RoundButton(
            buttons, '导出清单', self.export_bom, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._confirm_button.pack(side='right')
        self._export_button.pack(side='right', padx=(0, 8))
        self._cancel_button.pack(side='right', padx=(0, 8))

        self._arm.trace_add('write', self.on_text_changed)
        self._heading.trace_add('write', self.on_text_changed)
        self._rack_name.trace_add('write', self.on_text_changed)

    def _compact_value(self, parent, row, column, name, textvariable,
                       unit='', note='', notevariable=None, columnspan=1):
        """两列信息块：标题在上，值 / 单位同行，备注紧随其后。"""
        cell = tk.Frame(parent, bg=CARD)
        left_pad = 8 if column else 0
        cell.grid(row=row, column=column, columnspan=columnspan,
                  sticky='nsew', padx=(left_pad, 0), pady=(3, 4))
        ttk.Label(cell, text=name, style='GlassMuted.TLabel').pack(anchor='w')
        value_line = tk.Frame(cell, bg=CARD)
        value_line.pack(fill='x', pady=(1, 0))
        tk.Label(value_line, textvariable=textvariable, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left').pack(side='left')
        if unit:
            tk.Label(value_line, text=unit, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side='left', padx=(5, 0))
        if notevariable is not None:
            tk.Label(cell, textvariable=notevariable, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=500).pack(anchor='w')
        elif note:
            tk.Label(cell, text=note, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=500).pack(anchor='w')
        return cell

    def _compact_entry(self, parent, row, column, name, variable, width,
                       unit='', note='', columnspan=1):
        """两列输入块：标题在上，输入框 / 单位同行，帮助文字紧随其后。"""
        cell = tk.Frame(parent, bg=CARD)
        left_pad = 8 if column else 0
        cell.grid(row=row, column=column, columnspan=columnspan,
                  sticky='nsew', padx=(left_pad, 0), pady=(3, 4))
        ttk.Label(cell, text=name, style='GlassMuted.TLabel').pack(anchor='w')
        entry_line = tk.Frame(cell, bg=CARD)
        entry_line.pack(fill='x', pady=(3, 0))
        entry = self._entry(entry_line, variable, width)
        if unit:
            tk.Label(entry_line, text=unit, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side='left', padx=(5, 0))
        if note:
            tk.Label(cell, text=note, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=500).pack(anchor='w', pady=(1, 0))
        return entry

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        return entry

    def _value_row(self, parent, row, name, textvariable, note=''):
        """左列名称、右列数值；备注放在数值**下方**，用更小的淡色字体。"""
        ttk.Label(parent, text=name, style='GlassMuted.TLabel').grid(
            row=row, column=0, sticky='nw', pady=6)
        holder = tk.Frame(parent, bg=CARD)
        holder.grid(row=row, column=1, sticky='w', padx=(10, 0), pady=6)
        tk.Label(holder, textvariable=textvariable, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=240).pack(anchor='w')
        if note:
            tk.Label(holder, text=note, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=240).pack(anchor='w')
        return holder

    def _entry_row(self, parent, row, name, variable, width, note=''):
        """左列名称、右列输入框；备注放在输入框**下方**，用更小的淡色字体。"""
        ttk.Label(parent, text=name, style='GlassMuted.TLabel').grid(
            row=row, column=0, sticky='nw', pady=6)
        holder = tk.Frame(parent, bg=CARD)
        holder.grid(row=row, column=1, sticky='w', padx=(10, 0), pady=6)
        entry_line = tk.Frame(holder, bg=CARD)
        entry_line.pack(anchor='w')
        entry = self._entry(entry_line, variable, width)
        if note:
            tk.Label(holder, text=note, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=240).pack(anchor='w')
        return entry

    def _label_for_variant(self, variant_key, labels=None):
        for label, key in self._variant_by_label.items():
            if key == variant_key:
                return label
        if labels:
            return labels[0]
        return ''

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        variant = state.get('variant')
        label = self._label_for_variant(variant)
        if label:
            self._variant.set(label)
        # 类型每次打开都从类型 1 开始，不恢复上次会话的类型选择。
        self._rack_type.set(RACK_TYPE_OPTIONS[0][1])
        rack_name = state.get('rack_name')
        if isinstance(rack_name, str):
            self._rack_name.set(rack_name)
        arm = state.get('arm')
        if isinstance(arm, str) and arm.strip():
            self._arm.set(arm)
        heading = state.get('heading')
        if isinstance(heading, str) and heading.strip():
            self._heading.set(heading)
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        if isinstance(state.get('ground_fixed'), bool):
            self._ground_fixed.set(state.get('ground_fixed'))
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['rack_name'] = self._rack_name.get()
            state['arm'] = self._arm.get()
            state['heading'] = self._heading.get()
            state['keep_line'] = bool(self._keep_line.get())
            state['ground_fixed'] = bool(self._ground_fixed.get())
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(self._variant.get(),
                                          geom.DEFAULT_VARIANT)

    def current_rack_type(self):
        return self._type_by_label.get(self._rack_type.get(), 1)

    def current_arm_length(self):
        try:
            return float((self._arm.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_ARM_LENGTH_MM

    def current_heading(self):
        try:
            return float((self._heading.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_HEADING_DEG

    def current_options(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        if not geom.variant_supports_type(variant_key, rack_type):
            raise ValueError(self._invalid_message())
        return {
            'variant': variant_key,
            'rack_type': rack_type,
            'rack_name': (self._rack_name.get() or '').strip(),
            'arm_length': self.current_arm_length(),
            'heading': self.current_heading(),
            'ground_fixed': bool(self._ground_fixed.get()),
        }

    def current_rack_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        if self._ground_fixed.get():
            return geom.ground_anchor_number(
                self.current_variant(), line.length_mm,
                self.current_arm_length(), geom.GROUND_ANCHOR_NAME)
        return geom.build_pipe_rack_number(
            self._rack_name.get(), self.current_rack_type(),
            self.current_variant(), line.length_mm, self.current_arm_length())

    def on_ground_fixed_changed(self):
        """切换"地面固定"：名称在 D12 / G4 之间联动，并重建预览。"""
        if self._ground_fixed.get():
            self._name_before_ground = self._rack_name.get() or 'D12'
            self._rack_name.set(geom.GROUND_ANCHOR_NAME)
        elif self._rack_name.get() == geom.GROUND_ANCHOR_NAME:
            self._rack_name.set(self._name_before_ground or 'D12')
        self.on_options_changed()

    def set_status(self, message, is_error=False, flush=True):
        # 只在 Tk 定时器 / 控件回调上下文里刷新；不调用 update_idletasks，
        # 避免在 after 回调里重入 Tk 的事件处理。
        try:
            self._status_label.configure(
                fg='#b42318' if is_error else '#1f5f99')
            self._status.set(message)
        except tk.TclError:
            pass

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        connection = ('H 型钢端面焊接' if result.get('is_hbeam')
                      else '角钢背靠背')
        text = (
            '预览：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，立柱下料 '
            '%.0f mm（%s），朝向 %.0f°，单元含 %d 个子元素；编号 %s。' % (
                result['variant'], result['rack_type'], result['specification'],
                result['height'], result['arm_length'],
                result['post_cut_length'], connection,
                result['heading_deg'], result['child_count'], number,
            )
        )
        if result.get('ground_fixed'):
            spec = result.get('ground_anchor') or {}
            text += (
                '\n地面固定：锚板 %.0f×%.0f×%.0f，4-φ%.0f 孔（F=%.0f），'
                'M%.0f×%.0f 膨胀锚栓 ×4（h_ef=%.0f），现场灌浆梯台高 %.0f、'
                '每边外扩 %.0f。' % (
                    spec.get('plate_e', 0.0), spec.get('plate_e', 0.0),
                    spec.get('plate_t', 0.0), spec.get('hole_dia_g', 0.0),
                    spec.get('hole_spacing_f', 0.0), spec.get('bolt_dia', 0.0),
                    spec.get('bolt_len', 0.0), spec.get('embed', 0.0),
                    geom.GROUND_GROUT_THICKNESS_MM,
                    geom.GROUND_GROUT_FLARE_MM,
                )
            )
        self._preview_info.set(text)

    def refresh_spec(self):
        variant_key = self.current_variant()
        self._spec.set(geom.specification(variant_key))
        self._width.set('%.0f' % geom.inplane_width(variant_key))
        self._connection.set(
            'H 型钢端面焊接（腹板共面）' if geom.variant_is_hbeam(variant_key)
            else '角钢背靠背（非通长、顶端留 10 焊缝间隙）')
        max_height = geom.max_allowed_height(variant_key)
        max_arm = geom.max_allowed_arm_length(variant_key)
        self._max_height.set('—' if max_height is None else '%.0f' % max_height)
        self._max_arm.set('—' if max_arm is None else '%.0f' % max_arm)
        if self._options_valid():
            self._spec_info_label.configure(fg=INK)
            if geom.hanger_type(self.current_rack_type()):
                type_text = ('类型 2 为倒 T 形吊架：横担在下端、管位朝上（同类型 1 '
                             '方向）；立柱向上到结构，角钢下探与横担竖直肢背靠背'
                             '搭接，H 型钢端面焊在横担上表面。')
            else:
                type_text = ('类型 1 为正 T 形架：单根立柱居中、横担居中，'
                             '横担顶面为固定管子的面。')
            text = ('构件A：立柱与横担同规格 %s（%s）；%s'
                    % (geom.specification(variant_key),
                       _family_description(variant_key), type_text))
            if self._ground_fixed.get():
                aspec = geom.ground_anchor_spec(variant_key)
                text += (' 地面固定：锚板 %.0f×%.0f×%.0f，4-φ%.0f 孔（F=%.0f），'
                         'M%.0f×%.0f 膨胀锚栓（h_ef=%.0f），现场灌浆梯台高 %.0f、'
                         '每边外扩 %.0f。'
                         % (aspec['plate_e'], aspec['plate_e'], aspec['plate_t'],
                            aspec['hole_dia_g'], aspec['hole_spacing_f'],
                            aspec['bolt_dia'], aspec['bolt_len'],
                            aspec['embed'], geom.GROUND_GROUT_THICKNESS_MM,
                            geom.GROUND_GROUT_FLARE_MM))
            self._spec_info.set(text)
        else:
            self._spec_info_label.configure(fg='#b42318')
            if (self._ground_fixed.get()
                    and geom.hanger_type(self.current_rack_type())):
                self._spec_info.set(
                    '地面固定（生成锚板）只适用于类型 1（立柱在下）；'
                    '请改选类型 1 或取消地面固定。')
            else:
                self._spec_info.set(self._invalid_message())
        self.refresh_line_labels()

    def _show_line_values(self, line):
        if line is None:
            self._height.set('—')
            self._post_length.set('—')
            self._load.set('—')
            self._load_note.set('')
            self._rack_number.set('—')
            return
        self._height.set('%.1f' % line.length_mm)
        variant_key = self.current_variant()
        try:
            self._post_length.set(
                '%.1f' % geom.post_length(variant_key, line.length_mm))
        except ValueError as error:
            self._post_length.set('—')
            self._load_note.set(str(error))

        result = geom.allowable_load(
            variant_key, line.length_mm, self.current_arm_length())
        if result.value is None:
            self._load.set('—')
        else:
            self._load.set('%.2f' % result.value)
        self._load_note.set(result.message or '')

        number = self.current_rack_number(line)
        self._rack_number.set(number if number else '（名称留空，不附加）')

    def refresh_line_labels(self):
        self._show_line_values(self.line)

    def on_options_changed(self, event=None):
        self.refresh_spec()
        if not self._options_valid():
            self._cancel_pending_regeneration()
            self.discard_preview()
            self.set_status(self._invalid_message(), True)
            return
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _options_valid(self):
        if not geom.variant_supports_type(
                self.current_variant(), self.current_rack_type()):
            return False
        if (self._ground_fixed.get()
                and geom.hanger_type(self.current_rack_type())):
            return False
        return True

    def _invalid_message(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        allowed = '/'.join(str(t) for t in geom.allowed_rack_types(variant_key))
        return ('不合法组合：子项 %s 仅对类型 %s 有效，当前为类型 %d。'
                % (variant_key, allowed, rack_type))

    def on_text_changed(self, *_args):
        self.refresh_spec()
        if not self._options_valid():
            return
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay_ms):
        # 纯 Python，不碰 Tcl：可能由原生回调调用。
        self._cancel_pending_regeneration()
        if self.line is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    def note_hover(self, line):
        """悬停到一条合规直线上：只记 Python 状态，由 poll 定时器刷新。"""
        self._hover_line = line

    def note_hover_error(self, message):
        """悬停到不合规元素：只登记提示（不碰 Tcl），由 poll 定时器刷新。"""
        self._pending_message = message
        self._pending_is_error = True

    def request_cancel(self):
        """原生回调里请求取消：只置标志，由 poll 定时器执行。"""
        self._cancel_requested = True

    def request_shutdown(self):
        """原生回调里请求关闭：只置标志，由 poll 定时器执行。"""
        self._shutdown_requested = True

    # -- UI 刷新：只允许在这个 Tk 定时器里碰控件 ---------------------------

    def _start_poll(self):
        """常驻 Tk 定时器：原生回调只写 Python 状态，真正刷新全在这里做。"""
        try:
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None

    def _poll_ui(self):
        self._poll_job = None
        try:
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.shutdown()
                return
            if self._cancel_requested:
                self._cancel_requested = False
                self.cancel_tool()
                return
            if (self._regen_deadline is not None
                    and time.monotonic() >= self._regen_deadline):
                self._regen_deadline = None
                self.regenerate()
            self._flush_ui()
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None
        except Exception:
            _log_exception('poll failed')
            try:
                self._poll_job = self.after(self.POLL_MS, self._poll_ui)
            except tk.TclError:
                self._poll_job = None

    def _flush_ui(self):
        try:
            if self._pending_result is not None:
                result = self._pending_result
                message = self._pending_message or ''
                self._pending_result = None
                self._pending_message = None
                self._pending_is_error = False
                self.refresh_line_labels()
                self.set_result(result)
                self.set_status(message)
            elif self._pending_message is not None:
                message = self._pending_message
                is_error = self._pending_is_error
                self._pending_message = None
                self._pending_is_error = False
                self.set_status(message, is_error)
            if self.line is None and self._hover_line is not None:
                self._show_line_values(self._hover_line)
        except tk.TclError:
            pass

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前直线与选项重建预览：先建新的一版，成功后再删掉旧的。

        可能由 MicroStation 的原生回调（选取元素）直接调用，故这里**只做
        Bentley 建模**，结果写进普通 Python 状态；所有 Tk 控件刷新由常驻
        定时器 :meth:`_poll_ui` 完成，避免在原生回调里重入 Tcl 崩溃。
        """
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            _log('regenerate: bad options: %s' % error)
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None

        _log('regenerate: start')
        try:
            handle, result, deleted = replace_t_frame(
                self.line, options['variant'], self.preview_handle,
                options['rack_type'], options['arm_length'],
                options['heading'], options['rack_name'],
                options['ground_fixed'])
        except Exception as error:
            # 超限 / 几何失败只写面板状态，不向控制台输出，避免干扰使用。
            message = 'T形架生成失败：%s' % error
            self._pending_message = message
            self._pending_is_error = True
            if isinstance(error, ValueError):
                _log('preview rejected: %s' % error)
            else:
                _log_exception('preview failed')
            return None

        self.preview_handle = handle
        self.preview_result = result
        message = (
            '预览已更新：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，'
            '朝向 %.0f°，单元含 %d 个子元素，编号 %s。%s'
            '改参数会自动重建；点【确定】保留，点【取消】放弃。' % (
                result['variant'], result['rack_type'], result['specification'],
                result['height'], result['arm_length'],
                result['heading_deg'], result['child_count'],
                result['pipe_rack_number'] or '—',
                '已替换上一版预览。' if deleted else '')
        )
        if result['warnings']:
            message += '注意：%s' % '；'.join(result['warnings'])
        self._pending_result = result
        self._pending_message = message
        self._pending_is_error = False
        try:
            NotificationManager.OutputPrompt(message)
        except Exception:
            _log_exception('OutputPrompt failed')
        _log('regenerate: done')
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def delete_source_line(self):
        handle = self.line_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                _log('source line deleted')
                return True
        except Exception:
            _log_exception('delete source line failed')
        self.set_status('所选直线删除失败，请手动删除。', True)
        return False

    def export_bom(self):
        try:
            output_path = export_bom_json()
        except Exception as error:
            _log_exception('export bom failed')
            self.set_status('导出清单失败：%s' % error, True)
            return
        if output_path is not None:
            self.set_status('清单已导出：%s' % output_path)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        if not self._options_valid():
            self.set_status(self._invalid_message(), True)
            return
        self.confirmed = True
        if self.preview_handle is not None and not self._keep_line.get():
            self.delete_source_line()
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        """结束原生工具并收起面板：点【确定】/【取消】/关闭都走这里，退回默认命令。"""
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        """关闭面板（可重复调用）。"""
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


def _family_description(variant_key):
    if geom.variant_is_hbeam(variant_key):
        return '热轧 H 型钢；立柱顶面顶焊在横担下翼缘下表面（端面焊接），'\
               '两者腹板共面'
    return '等边角钢；立柱镜像到横担竖直肢外侧、与横担背面相贴（背靠背），'\
           '立柱非通长、顶端留 10 mm 焊接间隙'


# ---------------------------------------------------------------------------
# 交互工具：点选直线
# ---------------------------------------------------------------------------


class TFrameByLineTool(DgnElementSetTool):
    """点选一条竖直线并放置 T形架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('TFrameByLineTool')

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
            '请点选一条竖直线段：线长即立柱长 H。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            line = extract_line(handle)
            if self.tool_settings is not None:
                # 只写 Python 状态，不碰 Tcl。
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                try:
                    self.tool_settings.note_hover_error(str(error))
                except Exception:
                    pass
            return False

    def _OnResetButton(self, event):
        # 右键放弃：等同【取消】。只置标志，由面板的 poll 定时器执行。
        settings = self.tool_settings
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_line(eeh)
            # regenerate 只做 Bentley 建模、写 Python 状态，不碰 Tcl。
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            # 只在面板显示，不向控制台 / 提示行输出。
            message = 'T形架生成失败：%s' % error
            if isinstance(error, ValueError):
                _log('element modify rejected: %s' % error)
            else:
                _log_exception('element modify failed')
            try:
                self.tool_settings.note_hover_error(message)
            except Exception:
                pass
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        TFrameByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _OnCleanup(self):
        settings = self.tool_settings
        if settings is None:
            return
        self.tool_settings = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        # 原生回调里不碰 Tcl；由 poll 定时器执行关闭。
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(TFrameByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _TFrameDialog())
        if owner:
            TFrameByLineTool._active_settings = settings
        tool = TFrameByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                TFrameByLineTool._active_settings = None
        return tool


def show_t_frame_dialog():
    return TFrameByLineTool.InstallNewInstance(0)


def export_t_frame_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYTFRAME PLACE / PYTFRAME EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, 'T形架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenTFrame():
    PyMain()


def ExportTFrameBom():
    export_t_frame_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_t_frame_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('t frame tool start failed')
        print('T形架插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'T形架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
