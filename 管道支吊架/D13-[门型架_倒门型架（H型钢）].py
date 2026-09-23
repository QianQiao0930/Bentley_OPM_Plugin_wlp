# -*- coding: utf-8 -*-
"""门型架（H型钢）（图 C.4-8 门形架 · H 型钢 · 类型 1）放置工具。

在模型中点选一条用户绘制的 **竖直线**（整组门型架的中心线），并在面板上输入
横担全长 **L**，据此生成一组 H 型钢门型架：

    竖直线   = 整组中心线（过横担中点、两立柱轴线关于它对称），线长即门架高 H
    立柱轴线 = 竖直线 ∓(L - 100 - 立柱截面高)/2
    L        = 横担全长（用户输入，表 1 的查表参数之一）
    两立柱净距 B = L - 2×50 - 2×立柱截面高
                 （横担两端各超出立柱外缘 50，图上 50 (TYP.)）

横担以该中心线为中点**横跨两根立柱**：两端各超出立柱外缘 50 mm，顶面（固定
管子的面）落在所选竖直线的顶端（即高度 H 处）；立柱**顶面顶焊在横担下翼缘下
表面**，两者腹板同处于门架平面内、翼缘对称于该平面。竖直线本身不能确定门架
平面，故水平走向由面板的「朝向」给出。

整组构件（两立柱 + 横担）写成一个普通单元（Normal Cell），清单写入**管道支吊架
公共库** ``支吊架公共库``（`SupportType='门型架（H型钢）'`），可与端焊三角架、
L 型管架、门型架（角钢和槽钢）一起统计；可导出 JSON / Excel 清单。

几何做法（型钢截面的真实圆弧轮廓与沿路径扫掠）复用仓库内
``型钢截面生成器`` 的数据 / 几何模块与 ``steel_sweep_geometry``；
面板外观沿用仓库共享的 Tkinter 工具箱 ``bentley_ui``（卡片 / 圆角按钮）；
纯几何 / 数据逻辑在 ``门型架_H型钢_几何.py``（可单测）。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import faulthandler
import importlib
import math
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 通配导入不一定导出这两个符号，显式再导入一次（与 型钢截面生成器.py 一致）。
from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
# 公共库在 模块/公共/，本插件几何在 模块/门型架H型钢/，仓库根提供共享
# Tkinter 工具箱 ``bentley_ui``。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '门型架H型钢')
for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR, STEEL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
try:
    import bentley_ui.glass as _glass_module
    import bentley_ui as _bentley_ui_module
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
    SlimScrollbar,
)

import 门型架_H型钢_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'D13-[门型架_倒门型架（H型钢）]'
SUPPORT_CODE = 'PORTAL_FRAME_H'


def _reload_runtime_modules():
    """每次运行都强制重新读取本插件与依赖模块，规避 MicroStation 缓存。"""
    importlib.invalidate_caches()
    for module in (geom, steel_sweep_geometry, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass
    # 型钢几何 / 数据模块随 门型架_H型钢_几何 一并重新加载。
    for name in ('steel_sections.steel_hbeam_data', 'steel_sections.steel_hbeam_geometry'):
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '门型架（H型钢）_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'D13-[门型架_倒门型架（H型钢）]'
UI_REVISION = 'line-select-tk-5'

# 整组构件写入的普通单元名。
CELL_NAME = 'PORTAL_FRAME_H'

COMPONENT_POST_NAME = '立柱'
COMPONENT_ARM_NAME = '横担'

# 默认横担长 L（mm）：取表 1 的最小列。
DEFAULT_ARM_LENGTH_MM = 1000.0
# 默认门架平面朝向（°）：0 = 世界 +X。
DEFAULT_HEADING_DEG = 0.0

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖，避免打到一半就重建


def _log(message):
    """Append one timestamped line to the plug-in debug log (best effort)."""
    try:
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (stamp, message))
            stream.flush()
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


_FAULT_FILE = None
_LAST_HOVER_LOG = [0.0]


def _log_hover(message):
    """鼠标悬停会高频触发；同一秒内只记一条，避免刷爆日志。"""
    now = time.monotonic()
    if now - _LAST_HOVER_LOG[0] < 1.0:
        return
    _LAST_HOVER_LOG[0] = now
    _log(message)


def _enable_fault_logging():
    """把 Python 级崩溃栈写入 fault 日志，便于定位硬崩溃 / 卡死。

    * ``faulthandler.enable``：捕获访问冲突等致命错误。
    * ``faulthandler.dump_traceback_later``：主线程一旦卡死（超过 8s 没有
      更新心跳），C 级看门狗线程会自动把所有线程的调用栈写进日志，从而看出
      卡在哪个原生调用上——这种死锁不会抛异常，只能靠它定位。
    """
    global _FAULT_FILE
    try:
        if _FAULT_FILE is None:
            path = os.path.join(HERE, '模块', '日志', '门型架（H型钢）_fault.log')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _FAULT_FILE = open(path, 'a', encoding='utf-8')
            faulthandler.enable(_FAULT_FILE)
        _FAULT_FILE.write(
            '=== session start %s rev=%s ===\n'
            % (time.strftime('%Y-%m-%d %H:%M:%S'), UI_REVISION))
        _FAULT_FILE.flush()
        # 每次入口都重新布防看门狗（主线程卡死 8s 即自动 dump 全部线程栈）。
        faulthandler.dump_traceback_later(8.0, repeat=True, file=_FAULT_FILE)
    except Exception:
        pass


def _disable_fault_logging():
    try:
        faulthandler.cancel_dump_traceback_later()
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


_EXTRACT_TRACE = [0]
_LOCATE_TRACE = [0]


def extract_vertical_post(element_handle):
    """从所选元素提取并校验竖直线（整组中心线），返回 ``门型架_H型钢_几何.VerticalPost``。"""
    # 前几次调用逐步记录，便于定位卡在哪个原生调用（之后不再逐步记录）。
    trace = _EXTRACT_TRACE[0] < 5
    _EXTRACT_TRACE[0] += 1
    if trace:
        _log('extract: step1 uor_per_mm')
    uor_per_mm = _uor_per_mm()
    if trace:
        _log('extract: step2 ElementToCurveVector')
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if trace:
        _log('extract: step3 got curve, IsOpenPath')
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条竖直线段（整组中心线）。')
    if trace:
        _log('extract: step4 collect pieces')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if trace:
        _log('extract: step5 point_to_mm')
    pieces_mm = [[_point_to_mm(point, uor_per_mm) for point in piece]
                 for piece in pieces]
    if trace:
        _log('extract: step6 parse_vertical_post')
    post = geom.parse_vertical_post(pieces_mm)
    _log_hover('extract_vertical_post: ok H=%.1f' % post.height_mm)
    return post


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


def _world_axis(components, run_dir, v_dir):
    """把截面轴在 (u, v, w) 下的分量换算为世界方向向量。"""
    ux, vx, wx = components
    return (
        ux * run_dir[0] + vx * v_dir[0],
        ux * run_dir[1] + vx * v_dir[1],
        wx,
    )


def _plane_dirs(heading_deg):
    """门架局部基的水平方向：u（横担长度方向）与 v（管道方向，Z × u）。"""
    heading = math.radians(float(heading_deg))
    return ((math.cos(heading), math.sin(heading), 0.0),
            (-math.sin(heading), math.cos(heading), 0.0))


def _build_member_element(variant_key, member_kind, post, heading_deg,
                          post_axis_u, arm_length_mm, uor_per_mm, dgn_model):
    """构建一个构件（立柱 / 横担）实体元素，不写入模型。

    截面朝向与扫掠起点由 ``门型架_H型钢_几何`` 的 ``member_section_params`` /
    ``member_axes`` / ``member_origin_length`` 给出，坐标系为门架局部基
    (u, v, w)，原点取所选竖直线的下端（基座）。
    """
    _log('build member enter: %s/%s' % (member_kind, variant_key))
    geometry = geom.member_geometry(variant_key, member_kind, uor_per_mm)
    run_dir, v_dir = _plane_dirs(heading_deg)
    axis_x, axis_y, axis_z = geom.member_axes(variant_key, member_kind)
    axis_x = _world_axis(axis_x, run_dir, v_dir)
    axis_y = _world_axis(axis_y, run_dir, v_dir)
    axis_z = _world_axis(axis_z, run_dir, v_dir)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, post.height_mm, arm_length_mm, post_axis_u)

    vertex = _to_uor(post.base, uor_per_mm)
    origin = (
        vertex[0] + origin_uvw[0] * uor_per_mm * run_dir[0]
        + origin_uvw[1] * uor_per_mm * v_dir[0],
        vertex[1] + origin_uvw[0] * uor_per_mm * run_dir[1]
        + origin_uvw[1] * uor_per_mm * v_dir[1],
        vertex[2] + origin_uvw[2] * uor_per_mm,
    )
    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    _log('build member %s: building profile, len=%.1f' % (member_kind, length_mm))
    profile = _profile_curve(geometry, frame)
    length = length_mm * uor_per_mm
    end = (origin[0] + axis_z[0] * length,
           origin[1] + axis_z[1] * length,
           origin[2] + axis_z[2] * length)
    path = _line_curve(origin, end)
    _log('build member %s: sweeping' % member_kind)
    body = _sweep_body(profile, path, dgn_model, frame.origin, frame.axis_y)
    _log('build member %s: sweep ok, converting to element' % member_kind)
    element = _body_to_element(body, dgn_model, member_kind)
    _log('build member %s: done' % member_kind)
    return element


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


class _PortalFrameCellBuilder(object):
    """把两立柱、横担子元素一次性写成一个普通单元。"""

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
            raise RuntimeError('门型架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法把门型架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成门型架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法把门型架单元写入活动模型。')
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
    """把整组门型架写入共享支吊架库（整组记录 + 立柱/横担构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=result.get('specification', ''),
        components=result.get('bom_items', ()),
    )


# ---------------------------------------------------------------------------
# 构建整组门型架
# ---------------------------------------------------------------------------


def _build_portal_frame_cell(post, variant_key, rack_type, arm_length_mm,
                             heading_deg, rack_name=None):
    """按竖直线与横担长 L 构建门型架单元但**不写入模型**。

    返回 ``(builder, 统计字典)``。
    """
    if not geom.variant_supports_type(variant_key, rack_type):
        raise ValueError(
            '本插件仅实现类型 %s；子项 %s 不适用于类型 %s。'
            % ('/'.join(str(t) for t in geom.allowed_rack_types(variant_key)),
               variant_key, rack_type))

    arm_length_mm = float(arm_length_mm)
    span_mm = geom.net_span(variant_key, arm_length_mm)
    if span_mm < geom.MIN_SPAN_MM:
        raise ValueError('两立柱净距 B=%.1f mm 过小，要求 ≥ %.0f mm。'
                         % (span_mm, geom.MIN_SPAN_MM))

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    uor_per_mm = _uor_per_mm(dgn_model)
    _log('portal frame (h-beam) build start: variant=%s type=%d L=%.1f H=%.1f '
         'heading=%.2f' % (variant_key, int(rack_type), arm_length_mm,
                           post.height_mm, float(heading_deg)))

    # 两立柱：所选竖直线为整组中心线，两立柱轴线对称于它、在
    # ∓(L - 100 - 立柱截面高)/2 处。
    # H 型钢截面本身关于腹板平面对称，两根立柱完全相同、无需镜像。
    left_axis = geom.post_axis_offset(variant_key, arm_length_mm, 'left')
    right_axis = geom.post_axis_offset(variant_key, arm_length_mm, 'right')
    left = _build_member_element(
        variant_key, 'post', post, heading_deg, left_axis, arm_length_mm,
        uor_per_mm, dgn_model)
    if left is None:
        raise RuntimeError('左立柱实体创建失败。')
    right = _build_member_element(
        variant_key, 'post', post, heading_deg, right_axis, arm_length_mm,
        uor_per_mm, dgn_model)
    if right is None:
        raise RuntimeError('右立柱实体创建失败。')

    # 横担：两端各超立柱外缘 50，顶面在高度 H 处。
    arm = _build_member_element(
        variant_key, 'arm', post, heading_deg, 0.0, arm_length_mm,
        uor_per_mm, dgn_model)
    if arm is None:
        raise RuntimeError('横担实体创建失败。')

    builder = _PortalFrameCellBuilder(dgn_model)
    builder.add(left)
    builder.add(right)
    builder.add(arm)
    builder.build()
    _log('portal frame (h-beam): cell assembled, %d children' % builder.child_count)

    spec = geom.specification(variant_key)
    post_cut_length = geom.member_origin_length(
        variant_key, 'post', post.height_mm, arm_length_mm, left_axis)[1]
    rack_number = geom.build_pipe_rack_number(
        rack_name or '', rack_type, variant_key, post.height_mm, arm_length_mm)

    load = geom.allowable_load(variant_key, post.height_mm, arm_length_mm)
    if load.value is None:
        builder.note('允许垂直荷载未取到：%s' % load.message)

    result = {
        'variant': variant_key,
        'rack_type': int(rack_type),
        'child_count': builder.child_count,
        'height': post.height_mm,
        'span': span_mm,
        'arm_length': arm_length_mm,
        'post_cut_length': post_cut_length,
        'heading_deg': float(heading_deg),
        'specification': spec,
        'allowable_load': load.value,
        'pipe_rack_number': rack_number or '',
        'bom_items': [
            {'code': 'Post', 'name': COMPONENT_POST_NAME,
             'specification': spec, 'length': post_cut_length, 'quantity': 2},
            {'code': 'Arm', 'name': COMPONENT_ARM_NAME,
             'specification': spec, 'length': arm_length_mm},
        ],
        'warnings': list(builder.warnings),
    }
    _log('portal frame (h-beam) built: variant=%s, type=%d, L=%.1f, H=%.1f, '
         'B=%.1f, post=%.1f, heading=%.2f, cells=%d, number=%s' %
         (variant_key, int(rack_type), arm_length_mm, post.height_mm, span_mm,
          post_cut_length, float(heading_deg), builder.child_count,
          result['pipe_rack_number'] or '-'))
    return builder, result


def replace_portal_frame(post, variant_key, previous_handle, rack_type=1,
                         arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                         heading_deg=DEFAULT_HEADING_DEG, rack_name=None):
    """重建门型架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_portal_frame_cell(
        post, variant_key, rack_type, arm_length_mm, heading_deg, rack_name)
    _log('replace_portal_frame: committing cell')
    new_handle = builder.commit()
    _log('replace_portal_frame: attaching ItemType/公共库')
    _attach_support_items(new_handle, result)
    _log('replace_portal_frame: deleting previous preview')
    deleted = _delete_preview(previous_handle)
    _log('replace_portal_frame: done (deleted=%s)' % bool(deleted))
    return new_handle, result, deleted


def draw_portal_frame(post, variant_key, rack_type=1,
                      arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                      heading_deg=DEFAULT_HEADING_DEG, rack_name=None):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_portal_frame_cell(
        post, variant_key, rack_type, arm_length_mm, heading_deg, rack_name)
    cell = builder.commit()
    _attach_support_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。

    本插件不单独维护自己的库，统一走 ``支吊架公共库``；因此清单里会同时包含
    端焊三角架、L 型管架、门型架（角钢和槽钢）、门型架（H型钢）以及今后接入
    的其它支吊架。
    """
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '门型架（H型钢）_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 面板（Tkinter / bentley_ui）
# ---------------------------------------------------------------------------


class _PortalFrameSettingsDialog(GlassDialog):
    """子项 / L / 朝向 / 编号 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'PortalFrameH'
    # UI 刷新轮询周期（ms）：原生回调只写状态，由这个周期统一刷进控件。
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.post = None
        self.post_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        # 关键：MicroStation 的原生回调（_OnPostLocate / _OnElementModify）
        # 会在 Tk 的 update() 里被重入式调用；此时**任何** Tcl 调用
        # （after/after_idle/StringVar.set/控件 configure）都可能弄坏 Tcl 的
        # 事件队列，随后 update() 直接访问冲突崩溃。因此回调里只写普通
        # Python 状态，所有 Tk 刷新交给一个常驻的 Tk 定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._hover_post = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False

        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._rack_name = tk.StringVar(value='D13')
        self._arm_length = tk.StringVar(value='%.0f' % DEFAULT_ARM_LENGTH_MM)
        self._heading = tk.StringVar(value='%.0f' % DEFAULT_HEADING_DEG)
        self._keep_line = tk.BooleanVar(value=True)
        self._spec = tk.StringVar(value='—')
        self._depth = tk.StringVar(value='—')
        self._height = tk.StringVar(value='—')
        self._span = tk.StringVar(value='—')
        self._post_length = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._rack_number = tk.StringVar(value='—')
        self._variant_by_label = {}
        self._rack_type_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()

        # 关闭窗口时按"取消"处理：丢弃预览并结束工具。
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        try:
            self.minsize(600, 640)
        except tk.TclError:
            pass
        _log('panel built rev=%s file=%s'
             % (UI_REVISION, os.path.abspath(__file__)))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        shell_form = self.build_shell(
            UI_TITLE,
            '点选一条竖直线（整组中心线）· 输入横担长 L，自动预览')
        # 整块内容放进固定高度的滚动容器，保证面板再长也不超出屏幕；
        # 鼠标滚轮或右侧细滚动条查看。
        shell_form.columnconfigure(0, weight=1)
        shell_form.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(shell_form, bg=CARD, height=380)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        form = self._scroll.body
        form.columnconfigure(1, weight=1)

        hint_frame, hint_text = self._text_field(form, height=2)
        hint_frame.grid(row=0, column=0, columnspan=2, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一条竖直线：线长即门架高 H（横担顶面到基座），'
            '该线是整组门型架的中心线（两立柱轴线关于它对称）。再输入'
            '横担全长 L —— 横担以中心线为中点、两端各超立柱外缘 50'
            '（图上 50 TYP.），两立柱净距 B = L − 2×50 − 2×立柱截面高'
            ' 自动计算。竖直线不能定出朝向，请用「朝向」指定门架平面。'
            '点取后可改参数、预览自动重建；点【确定】保留，点【取消】'
            '或右键放弃。'))

        ttk.Label(form, text='构件规格（表 1）', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(6, 2))

        ttk.Label(form, text='子项', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=3)
        labels = []
        for key, label in geom.variant_choices():
            labels.append(label)
            self._variant_by_label[label] = key
        self._variant_combo = ttk.Combobox(
            form, textvariable=self._variant, state='readonly', width=30,
            style='Glass.TCombobox', values=labels)
        self._variant_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0),
                                 pady=3)
        self._variant_combo.bind('<<ComboboxSelected>>',
                                 self.on_options_changed)

        ttk.Label(form, text='构件A（立柱 / 横担）',
                  style='GlassMuted.TLabel').grid(row=3, column=0, sticky='w',
                                                  pady=3)
        tk.Label(form, textvariable=self._spec, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=3, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='截面高 h', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._depth, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(form, orient='horizontal').grid(
            row=5, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='尺寸参数', style='Section.TLabel').grid(
            row=6, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(form, text='门架高 H', style='GlassMuted.TLabel').grid(
            row=7, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._height, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=7, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='横担长 L', style='GlassMuted.TLabel').grid(
            row=8, column=0, sticky='nw', pady=3)
        arm_holder = tk.Frame(form, bg=CARD)
        arm_holder.grid(row=8, column=1, sticky='w', padx=(10, 0), pady=3)
        arm_input = tk.Frame(arm_holder, bg=CARD)
        arm_input.pack(anchor='w')
        self._arm_entry = self._entry(arm_input, self._arm_length, 9)
        tk.Label(arm_holder, text='mm　横担全长，表 1 的查表参数', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(form, text='两立柱净距 B', style='GlassMuted.TLabel').grid(
            row=9, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._span, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=9, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='立柱下料长', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._post_length, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=10, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='允许垂直荷载', style='GlassMuted.TLabel').grid(
            row=11, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._load, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=11, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='朝向', style='GlassMuted.TLabel').grid(
            row=12, column=0, sticky='nw', pady=3)
        heading_holder = tk.Frame(form, bg=CARD)
        heading_holder.grid(row=12, column=1, sticky='w', padx=(10, 0), pady=3)
        heading_input = tk.Frame(heading_holder, bg=CARD)
        heading_input.pack(anchor='w')
        self._heading_entry = self._entry(heading_input, self._heading, 9)
        tk.Label(heading_holder, text='°　门架平面内的横担指向（0 = 世界 +X）',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w',
                                                             pady=(1, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=13, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='管架编号', style='Section.TLabel').grid(
            row=14, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(form, text='名称', style='GlassMuted.TLabel').grid(
            row=15, column=0, sticky='nw', pady=3)
        name_holder = tk.Frame(form, bg=CARD)
        name_holder.grid(row=15, column=1, sticky='w', padx=(10, 0), pady=3)
        name_input = tk.Frame(name_holder, bg=CARD)
        name_input.pack(anchor='w')
        self._rack_name_entry = self._entry(name_input, self._rack_name, 12)
        tk.Label(name_holder, text='管架系列代号；留空则不附加编号', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(form, text='类型', style='GlassMuted.TLabel').grid(
            row=16, column=0, sticky='w', pady=3)
        type_labels = []
        for key, label in ((1, '类型1  |  正门形架（立柱在下、横担在上）'),):
            type_labels.append(label)
            self._rack_type_by_label[label] = key
        self._rack_type_combo = ttk.Combobox(
            form, textvariable=self._rack_type, state='readonly', width=30,
            style='Glass.TCombobox', values=type_labels)
        self._rack_type_combo.grid(row=16, column=1, sticky='ew',
                                   padx=(10, 0), pady=3)
        self._rack_type_combo.bind('<<ComboboxSelected>>',
                                   self.on_options_changed)

        ttk.Label(form, text='编号', style='GlassMuted.TLabel').grid(
            row=17, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._rack_number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=17, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(form, orient='horizontal').grid(
            row=18, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='创建选项', style='Section.TLabel').grid(
            row=19, column=0, columnspan=2, sticky='w', pady=(0, 2))
        self._keep_check = tk.Checkbutton(
            form, text='创建后保留所选竖直线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.grid(row=20, column=0, columnspan=2, sticky='w')

        # 说明 / 预览 / 状态固定在滚动区下方，始终可见。
        info = tk.Frame(shell_form, bg=CARD)
        info.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self._spec_info_frame, self._spec_info_text = self._text_field(
            info, height=2)
        self._spec_info_frame.pack(fill='x')
        self._preview_info_frame, self._preview_info_text = self._text_field(
            info, height=2)
        self._preview_info_frame.pack(fill='x', pady=(4, 0))
        self._status_frame, self._status_text = self._text_field(info, height=2)
        self._status_frame.pack(fill='x', pady=(4, 0))
        self._set_text(self._preview_info_text, '预览：—')
        self._set_text(self._status_text,
                       '请在模型中点选一条竖直线；改参数会自动重建预览。')

        buttons = tk.Frame(shell_form, bg=CARD)
        buttons.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self.confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button = RoundButton(
            buttons, '导出 JSON 清单', self.export_bom, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button.pack(side='left')
        self.confirm_button.pack(side='right')
        self.cancel_button.pack(side='right', padx=(0, 8))

        self._arm_length.trace_add('write', self.on_text_changed)
        self._heading.trace_add('write', self.on_text_changed)
        self._rack_name.trace_add('write', self.on_text_changed)
        self._bind_wheel(self._scroll)

    def _bind_wheel(self, scroll):
        """让整块表单支持鼠标滚轮（只读文本框自己处理滚轮，不拦截）。"""
        def on_wheel(event):
            scroll.scroll_units(-1 if event.delta > 0 else 1)
            return 'break'

        def walk(widget):
            if isinstance(widget, tk.Text):
                return
            widget.bind('<MouseWheel>', on_wheel)
            for child in widget.winfo_children():
                walk(child)
        walk(scroll)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        return entry

    def _text_field(self, parent, height=2):
        """固定高度的只读文本框：内容超出时用右侧细滚动条 / 鼠标滚轮查看。"""
        frame = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
        text = tk.Text(
            frame, height=height, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=5, cursor='arrow', takefocus=0)
        bar = SlimScrollbar(frame, command=text.yview, trough=CARD_SOFT)
        text.configure(yscrollcommand=bar.set)
        text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        text.configure(state='disabled')
        return frame, text

    def _set_text(self, text_widget, value):
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', value or '')
            text_widget.configure(state='disabled')
            text_widget.yview_moveto(0.0)
        except tk.TclError:
            pass

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        variant = state.get('variant')
        selected = None
        fallback = None
        for label, key in self._variant_by_label.items():
            if fallback is None:
                fallback = label
            if key == geom.DEFAULT_VARIANT:
                fallback = label
            if key == variant:
                selected = label
        self._variant.set(selected or fallback)

        rack_type = state.get('rack_type')
        selected_type = None
        fallback_type = None
        for label, key in self._rack_type_by_label.items():
            if fallback_type is None:
                fallback_type = label
            if key == rack_type:
                selected_type = label
        self._rack_type.set(selected_type or fallback_type)

        for key, variable in (('arm_length', self._arm_length),
                              ('heading', self._heading)):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                variable.set(value)
        name = state.get('rack_name')
        if isinstance(name, str):
            self._rack_name.set(name)
        keep = state.get('keep_line')
        if isinstance(keep, bool):
            self._keep_line.set(keep)
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['rack_name'] = self._rack_name.get()
            state['arm_length'] = self._arm_length.get()
            state['heading'] = self._heading.get()
            state['keep_line'] = bool(self._keep_line.get())
        except tk.TclError:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(
            self._variant.get(), geom.DEFAULT_VARIANT)

    def current_rack_type(self):
        return self._rack_type_by_label.get(self._rack_type.get(), 1)

    def current_arm_length(self):
        try:
            return float((self._arm_length.get() or '').strip())
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
            'rack_name': self._rack_name.get().strip(),
            'arm_length': self.current_arm_length(),
            'heading': self.current_heading(),
        }

    def current_rack_number(self, post=None):
        post = post if post is not None else self.post
        if post is None:
            return ''
        return geom.build_pipe_rack_number(
            self._rack_name.get(), self.current_rack_type(),
            self.current_variant(), post.height_mm,
            self.current_arm_length())

    def set_status(self, message, is_error=False, flush=True):
        # 只在 Tk 定时器上下文里刷新控件（见 _poll_ui/_flush_ui）。
        self._set_text(getattr(self, '_status_text', None), message)

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        self._set_text(self._preview_info_text,
            "预览：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，B=%.0f mm，"
            "立柱下料 %.0f mm，朝向 %.0f°，单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'],
                result['specification'], result['height'],
                result['arm_length'], result['span'],
                result['post_cut_length'], result['heading_deg'],
                result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        self._spec.set(geom.specification(variant_key))
        try:
            self._depth.set('%.0f' % geom.member_depth(variant_key, 'post'))
        except ValueError:
            self._depth.set('—')
        if self._options_valid():
            self._set_text(self._spec_info_text,
                '构件A：立柱与横担同为 %s（%s）。立柱与横担腹板同处于门架'
                '平面内、翼缘对称；立柱顶面顶焊在横担下翼缘下表面。'
                % (geom.specification(variant_key),
                   _family_description(variant_key)))
        else:
            self._set_text(self._spec_info_text, self._invalid_message())
        self.refresh_line_labels()

    def refresh_line_labels(self):
        self._show_line_values(self.post)

    def _show_line_values(self, post):
        if post is None:
            self._height.set('—')
            self._span.set('—')
            self._post_length.set('—')
            self._load.set('—')
            self._rack_number.set('—')
            return
        variant_key = self.current_variant()
        arm_length = self.current_arm_length()
        self._height.set('%.1f' % post.height_mm)
        try:
            self._span.set('%.1f' % geom.net_span(variant_key, arm_length))
        except ValueError:
            self._span.set('—')
        try:
            self._post_length.set(
                '%.1f' % geom.member_origin_length(
                    variant_key, 'post', post.height_mm, arm_length, 0.0)[1])
        except ValueError:
            self._post_length.set('—')

        result = geom.allowable_load(variant_key, post.height_mm, arm_length)
        if result.value is None:
            self._load.set('—')
        else:
            self._load.set('%.2f' % result.value)

        number = self.current_rack_number(post)
        self._rack_number.set(number if number else '（名称留空，不附加）')

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
            if self.post is None and self._hover_post is not None:
                self._show_line_values(self._hover_post)
        except tk.TclError:
            pass

    def note_hover_error(self, message):
        """悬停到不合规元素：只登记提示（不碰 Tcl），由 poll 定时器刷新。"""
        self._pending_message = message
        self._pending_is_error = True

    def request_cancel(self):
        """原生回调里请求取消：只置标志，由 poll 定时器执行。"""
        self._cancel_requested = True

    def request_shutdown(self):
        self._shutdown_requested = True

    def on_options_changed(self, event=None):
        self.refresh_spec()
        if not self._options_valid():
            # 子项与类型冲突：不生成（并撤掉可能过期的预览），只提示。
            self._cancel_pending_regeneration()
            self.discard_preview()
            self.set_status(self._invalid_message(), True)
            return
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _options_valid(self):
        return geom.variant_supports_type(
            self.current_variant(), self.current_rack_type())

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
        self._cancel_pending_regeneration()
        if self.post is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        # 纯 Python，不碰 Tcl：可能由原生回调调用。
        self._regen_deadline = None

    def note_hover(self, post):
        """悬停到一条合规竖直线上：只记 Python 状态，由 poll 定时器刷新。"""
        self._hover_post = post

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, post=None, handle=None):
        """按当前竖直线与选项重建预览：先建新的一版，成功后再删掉旧的。

        可能由 MicroStation 的原生回调（选取元素）直接调用，故这里**只做
        Bentley 建模**，结果写进普通 Python 状态；所有 Tk 控件刷新由
        常驻定时器 :meth:`_poll_ui` 完成，避免在原生回调里重入 Tcl 崩溃。
        """
        self._cancel_pending_regeneration()
        if post is not None:
            self.post = post
            self.post_handle = handle
        if self.post is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            _log('regenerate: bad options: %s' % error)
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None

        _log('regenerate: start options=%s' % (options,))
        try:
            handle, result, deleted = replace_portal_frame(
                self.post, options['variant'], self.preview_handle,
                options['rack_type'], options['arm_length'],
                options['heading'], options['rack_name'])
        except Exception as error:
            message = '门型架生成失败：%s' % error
            _log_exception('preview failed')
            self._pending_message = message
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                _log_exception('OutputPrompt failed')
            print(message)
            return None

        self.preview_handle = handle
        self.preview_result = result
        message = (
            "预览已更新：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，"
            "B=%.0f mm，立柱下料 %.0f mm，朝向 %.0f°，单元含 %d 个子元素，"
            "编号 %s。%s改参数会自动重建；点【确定】保留，点【取消】放弃。" % (
                result['variant'], result['rack_type'], result['specification'],
                result['height'], result['arm_length'], result['span'],
                result['post_cut_length'], result['heading_deg'],
                result['child_count'], result['pipe_rack_number'] or '—',
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
        handle = self.post_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                _log('source line deleted')
                return True
        except Exception:
            _log_exception('delete source line failed')
        self.set_status('所选竖直线删除失败，请手动删除。', True)
        return False

    def export_bom(self):
        output_path = export_bom_json()
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
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        _disable_fault_logging()
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


def _family_description(variant_key):
    """构件型式说明（本插件只有热轧 H 型钢一种型式）。"""
    geom.VARIANTS[variant_key]  # 校验子项
    return ('热轧 H 型钢；立柱与横担腹板共面、翼缘对称，'
            '立柱顶面顶焊横担下翼缘下表面')


# ---------------------------------------------------------------------------
# 交互工具：点选竖直线
# ---------------------------------------------------------------------------


class PortalFrameByLineTool(DgnElementSetTool):
    """点选一条竖直线并放置门型架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('PortalFrameHBeamByLineTool')

    def _DoGroups(self):
        return False

    def _AllowSelection(self):
        return DgnElementSetTool.eUSES_SS_None

    def _NeedAcceptPoint(self):
        return False

    def _WantDynamics(self):
        return False

    def _OnPostInstall(self):
        _log('_OnPostInstall: enter')
        AccuSnap.GetInstance().EnableSnap(True)
        DgnElementSetTool._OnPostInstall(self)
        _log('_OnPostInstall: base done')
        NotificationManager.OutputPrompt(
            '请点选一条竖直线段：线长即门架高 H（横担顶面到基座），'
            '该线为整组门型架的中心线。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if _LOCATE_TRACE[0] < 5:
            _LOCATE_TRACE[0] += 1
            _log('_OnPostLocate: call %d' % _LOCATE_TRACE[0])
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            post = extract_vertical_post(handle)
            if self.tool_settings is not None:
                self.tool_settings.note_hover(post)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                try:
                    self.tool_settings.note_hover_error(str(error))
                except Exception:
                    pass
            return False

    def _OnResetButton(self, event):
        # 右键放弃：等同【取消】，确保面板与预览一并收掉。
        settings = self.tool_settings
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        _log('_OnElementModify: selected element')
        try:
            post = extract_vertical_post(eeh)
            result = self.tool_settings.regenerate(post, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '门型架生成失败：%s' % error
            _log_exception('element modify failed')
            try:
                self.tool_settings.note_hover_error(message)
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        PortalFrameByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

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
        _log('_OnCleanup: requesting panel close')
        # 原生回调里不碰 Tcl；由 poll 定时器执行关闭。
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(PortalFrameByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _PortalFrameSettingsDialog())
        if owner:
            PortalFrameByLineTool._active_settings = settings
        tool = PortalFrameByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                PortalFrameByLineTool._active_settings = None
        return tool


def show_portal_frame_dialog():
    return PortalFrameByLineTool.InstallNewInstance(0)


def export_portal_frame_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYPORTALFRAMEH PLACE / PYPORTALFRAMEH EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '门型架（H型钢）.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenPortalFrame():
    PyMain()


def ExportPortalFrameBom():
    export_portal_frame_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _enable_fault_logging()
    _log('PyMain: entry rev=%s' % UI_REVISION)
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_portal_frame_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('portal frame tool start failed')
        print('门型架插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '门型架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
