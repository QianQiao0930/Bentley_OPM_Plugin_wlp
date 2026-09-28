# -*- coding: utf-8 -*-
"""G5-[地面上生根的门型架]（角钢 / 热轧 H 型钢）放置工具。

在模型中点选一条用户绘制的 **竖直线**（**整组门型架的中心线**），并在面板上
输入 **横担全长 L**、**朝向** 与 **名称**，据此生成一组「地面上生根的门型架」：

    竖直线   = 整组门型架的中心线（过横担中点、两立柱轴线关于它对称）
    线上端   = 管底标高 = 横担顶面（固定管子的面）
    线下端   = 地面（现场灌浆梯台底面）中心
    线长     = 门架高 H（地面 → 横担顶面）
    立柱轴线 = 中心线 ∓(L − 2×25 − W)/2（W = 立柱在横担长度方向的截面宽）
    横担     = 以中心线为中点、全长 L，两端各超出立柱外缘 25（图上标注）
    两柱净距 B = L − 2×25 − 2W（自动计算，面板只读显示，用于查表 1）

一组的构件：**2 立柱 + 1 横担 + 2 套地面生根基础件**。地面生根按表 2 复用
``模块/公共/混凝土锚板.py``：自下而上为 **现场灌浆梯台（高 25）→ 锚板（E×E×T，
4-φG 孔，方阵 F×F 居中）→ 立柱底面**，配 4 根膨胀锚栓（M d×L）+ 4 个六角螺母；
故钢构架整体比地面抬高 ``ground_lift()`` = 灌浆厚 + 锚板厚，送进几何模块的
**构架高度** = ``H − ground_lift()``（锚板顶面 → 横担顶面）。

子项 A~C 为等边角钢、D~G 为热轧 H 型钢（表 1 / 表 2）：

* 角钢：立柱与横担**背靠背**（右柱在 u 方向镜像，两柱互为镜像、开口朝门架外），
  立柱非通长，最高点比横担水平肢低 10 mm 留作施焊，力由贴合焊缝传走；
* H 型钢：立柱腹板与横担腹板共面，立柱端面顶焊在横担下翼缘下表面。

校验（不满足即报错、面板只提示不生成）：

* ``L`` 必须使 ``net_span(variant, L) ≥ MIN_SPAN_MM``（否则提示 L 太小）；
* ``H ≤ max_height(variant)``（表 1 的 MAX.H）；
* ``L ≤ max_arm_length(variant)``（表 1 的 L 上限）；
* 构架高度 ``H − ground_lift(variant)`` 必须 ``≥ MIN_FRAME_HEIGHT_MM``。

整组写成一个普通单元（Normal Cell），清单写入**管道支吊架公共库**
``支吊架公共库``（`SupportType='G5-[地面上生根的门型架]'`），可导出统一 JSON
清单（与端焊三角架、L 型管架、D8 门型架等一起统计）。**预览阶段只出几何，
点【确定】时才写一次公共库**（原因见文件下方「清单写库策略」）。

几何做法（型钢截面真实圆弧轮廓 + 沿路径扫掠）复用仓库内 ``型钢截面生成器``；
面板外观沿用仓库共享的 Tkinter 工具箱 ``bentley_ui``；纯几何 / 数据逻辑在
``模块/G5门型架/G5门型架_几何.py``（可单测），本文件只负责取样、装配与界面。

键入命令：``PYG5FRAME PLACE``（打开面板）/ ``PYG5FRAME EXPORT``（导出统一清单）。

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
# 公共库 / 地面锚板在 模块/公共/，本插件几何在 模块/G5门型架/，仓库根提供共享
# Tkinter 工具箱 ``bentley_ui``。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'G5门型架')
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

import 混凝土锚板 as anchor  # noqa: E402
import G5门型架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'G5-[地面上生根的门型架]'
SUPPORT_CODE = 'G5_GROUND_PORTAL_FRAME'


def _reload_runtime_modules():
    """每次运行都强制重新读取本插件与依赖模块，规避 MicroStation 缓存。"""
    importlib.invalidate_caches()
    for module in (geom, anchor, steel_sweep_geometry, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass
    # 型钢几何 / 数据模块随 G5门型架_几何 一并重新加载。
    for name in ('steel_sections.steel_equal_angle_data',
                 'steel_sections.steel_equal_angle_geometry',
                 'steel_sections.steel_hbeam_data',
                 'steel_sections.steel_hbeam_geometry'):
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'G5门型架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'G5-[地面上生根的门型架]'
UI_REVISION = 'line-select-tk-1-ground-portal-frame'

# 整组构件写入的普通单元名。
CELL_NAME = 'G5_GROUND_PORTAL_FRAME'

COMPONENT_POST_NAME = '立柱'
COMPONENT_ARM_NAME = '横担'
COMPONENT_PLATE_NAME = '锚板'
COMPONENT_BOLT_NAME = '膨胀锚栓'
COMPONENT_NUT_NAME = '螺母'
COMPONENT_GROUT_NAME = '现场灌浆'

# 默认横担全长 L（mm）。1000 对全部子项都合规（各子项表 1 的 L 上限 ≥ 1000），
# 编号示例即 ``G5-A-500-1000``（名称-子项-H-L）。
DEFAULT_ARM_LENGTH_MM = 1000.0
# 默认门架平面朝向（°）：0 = 世界 +X。
DEFAULT_HEADING_DEG = 0.0
# 默认管架系列代号（编号 = 名称-子项-H-L）。
DEFAULT_RACK_NAME = 'G5'

# ---------------------------------------------------------------------------
# 清单写库（共享支吊架库 ItemType）策略
# ---------------------------------------------------------------------------
# 背景：写公共库走 MicroStation 原生 EC 调用（``ItemTypeLibrary.Write()`` /
# ``CustomItemHost.ApplyCustomItem``）。实测**预览阶段每改一次参数就写一次库**，
# 第二次写库即卡死十几秒后 access violation（见 模块/日志/G5门型架_fault.log：
# 崩溃栈全在 支吊架公共库.py 的 _get_or_create_item_type / _attach_item_with_defaults），
# 与几何、清单数据无关 —— 每次改参数都会得到新的 AssemblyTag（编号含尺寸），
# 于是每次都要新建 ItemType 并重写库。
#
# 因此照 ``D5_D6_G12_D19`` / ``D8`` / ``G2`` 的既有做法：
#   1) ATTACH_ON_CONFIRM：**只在点【确定】时写库**，预览阶段只出几何。写库次数
#      从"每改一次参数一次"降到"每套一次"，也不会为取消掉的预览在公共库里
#      留下垃圾 ItemType。
#   2) ITEM_TYPE_ATTACH：逃生开关。若本机该原生调用持续崩溃，置 False 后几何
#      照常生成、照常落图，只是这批门型架不进清单统计。
ATTACH_ON_CONFIRM = True
ITEM_TYPE_ATTACH = True

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
            path = os.path.join(HERE, '模块', '日志', 'G5门型架_fault.log')
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
    """提取并校验竖直线（整组中心线），返回 ``G5门型架_几何.VerticalPost``。

    返回的 ``height_mm`` 即**门架高 H**（地面 → 横担顶面，＝所选竖直线线长）；
    ``base`` 是线下端（地面 / 灌浆梯台底面中心）。
    """
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


def _local_to_world_mm(offset_uv_mm, run_dir, v_dir):
    """把局部基 (u, v) 偏移（mm）换算为世界水平方向偏移（mm）。"""
    u_offset, v_offset = offset_uv_mm
    return (u_offset * run_dir[0] + v_offset * v_dir[0],
            u_offset * run_dir[1] + v_offset * v_dir[1])


def _build_member_element(variant_key, member_kind, post, frame_height_mm,
                          arm_length_mm, heading_deg, post_axis_u, uor_per_mm,
                          dgn_model, mirror_u=False):
    """构建一个构件（立柱 / 横担）实体元素，不写入模型。

    ``frame_height_mm`` 是**构架高度**（锚板顶面 → 横担顶面）＝ ``H −
    ground_lift()``；立柱自锚板顶面（局部 w = 0）向上，横担顶面落在
    ``w = 构架高度``。局部基 (u, v, w) 的原点取所选竖直线的下端（地面中心）。

    截面朝向与扫掠起点由 ``G5门型架_几何`` 的 ``member_axes`` /
    ``member_origin_length`` 给出：立柱轴线在 ``post_axis_u``、并按
    ``post_v_offset`` 在 v 方向平移（角钢背靠背；H 型钢腹板共面、不偏移）。
    """
    _log('build member enter: %s/%s mirror=%s' % (member_kind, variant_key,
                                                  mirror_u))
    geometry = geom.member_geometry(variant_key, member_kind, uor_per_mm)
    run_dir, v_dir = _plane_dirs(heading_deg)
    axis_x, axis_y, axis_z = geom.member_axes(variant_key, member_kind,
                                              mirror_u)
    axis_x = _world_axis(axis_x, run_dir, v_dir)
    axis_y = _world_axis(axis_y, run_dir, v_dir)
    axis_z = _world_axis(axis_z, run_dir, v_dir)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, frame_height_mm, arm_length_mm, post_axis_u)

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
    """把两立柱、横担与两套地面基础件一次性写成一个普通单元。"""

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

    def add_all(self, children):
        for child in children or ():
            self.add(child)
        return self.child_count

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


def _plate_specification(ground_spec):
    """锚板规格 ``E×E×T``（mm）。"""
    return '%.0f×%.0f×%.0f' % (ground_spec['plate_e'], ground_spec['plate_e'],
                                ground_spec['plate_t'])


def _hole_specification(ground_spec):
    """螺栓孔规格：4-φG 孔、方阵 F×F 居中（mm）。"""
    return '4-φ%.0f（%.0f×%.0f 方阵居中）' % (
        ground_spec['hole_dia_g'], ground_spec['hole_spacing_f'],
        ground_spec['hole_spacing_f'])


def _bolt_specification(ground_spec):
    """膨胀锚栓规格 ``M d×L``（mm）。"""
    return 'M%.0f×%.0f' % (ground_spec['bolt_dia'], ground_spec['bolt_len'])


def _assembly_specification(result):
    """整组记录用的规格文字（写进公共库 Specification 字段，只作提示）。"""
    ground_spec = result.get('ground_spec') or {}
    return ('G5-%s：门架高 H=%.0f（构架 %.0f），横担全长 L=%.0f，净距 B=%.0f；'
            '构件A %s；锚板 %s（%s）×2；膨胀锚栓 %s ×8；现场灌浆 高 %.0f ×2'
            % (result.get('variant', ''),
               float(result.get('height', 0.0)),
               float(result.get('frame_height', 0.0)),
               float(result.get('arm_length', 0.0)),
               float(result.get('span', 0.0)),
               result.get('specification', ''),
               _plate_specification(ground_spec) if ground_spec else '—',
               _hole_specification(ground_spec) if ground_spec else '—',
               _bolt_specification(ground_spec) if ground_spec else '—',
               geom.GROUND_GROUT_THICKNESS_MM))


def _attach_support_items(cell, result):
    """把整组门型架写入共享支吊架库（整组记录 + 各构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=result.get('specification', ''),
        components=result.get('bom_items', ()),
    )


def _write_support_items(handle, result):
    """把一整组写进共享支吊架库（原生 EC 写入），返回写入条目数，失败只记日志。

    先记一条含 ItemType 名字的日志：这个原生调用是本插件已知的偶发卡死点，
    崩了也能从日志最后一行看出崩在哪一项（见文件顶部策略说明）。
    """
    if not ITEM_TYPE_ATTACH:
        _log('attach skipped (ITEM_TYPE_ATTACH=False)')
        return 0
    _log('attach: type=%s tag=%s spec=%s items=%s'
         % (SUPPORT_TYPE, result.get('pipe_rack_number') or '-',
            result.get('specification') or '-',
            [str(item.get('code')) for item in result.get('bom_items', ())]))
    try:
        return _attach_support_items(handle, result)
    except Exception:
        _log_exception('attach failed')
        return 0


# ---------------------------------------------------------------------------
# 尺寸校验 / 派生量
# ---------------------------------------------------------------------------


def _frame_metrics(variant_key, height_mm, arm_length_mm):
    """校验尺寸并算出面板只读显示 / 建模所需的派生量；不合规抛 ``ValueError``。

    ``height_mm`` 为面板上的**门架高 H**（地面 → 横担顶面，＝所选竖直线线长）；
    ``arm_length_mm`` 为**横担全长 L**。返回字典中的 ``frame_height`` 才是送进
    几何模块的**构架高度**（锚板顶面 → 横担顶面）＝ ``H − ground_lift()``。
    """
    variant_key = str(variant_key).upper()
    height_mm = float(height_mm)
    arm_length_mm = float(arm_length_mm)

    # 1) H 不超表 1 的 MAX.H。
    max_height = geom.max_height(variant_key)
    if height_mm > max_height + geom.LOAD_TOLERANCE_MM:
        raise ValueError(
            '门架高 H=%.0f mm 超出表 1 的 MAX.H=%.0f mm。'
            % (height_mm, max_height))

    # 2) L 不超表 1 的 L 上限。
    max_arm = geom.max_arm_length(variant_key)
    if arm_length_mm > max_arm:
        raise ValueError(
            '横担全长 L=%.0f mm 超出表 1 的 L 上限=%.0f mm。'
            % (arm_length_mm, max_arm))

    # 3) L 不能太小：净距 B = L − 2×25 − 2W 必须 ≥ MIN_SPAN_MM。
    width = geom.inplane_width(variant_key)
    span = None
    try:
        span = geom.net_span(variant_key, arm_length_mm)
    except ValueError:
        span = None
    if span is None or span < geom.MIN_SPAN_MM:
        raise ValueError(
            '横担全长 L=%.0f mm 过小：扣除两端各 %.0f 与 2×立柱截面宽 %.0f 后'
            '两立柱净距 B=%.1f mm，要求 ≥ %.0f mm。'
            % (arm_length_mm, geom.ARM_END_OVERHANG_MM, width,
               span if span is not None else 0.0, geom.MIN_SPAN_MM))

    # 4) 构架高度（锚板顶面 → 横担顶面）＝ H − 抬升量，必须够高。
    ground_spec = geom.ground_anchor_spec(variant_key)
    lift = geom.ground_lift(variant_key)
    frame_height = height_mm - lift
    if frame_height < geom.MIN_FRAME_HEIGHT_MM:
        raise ValueError(
            '构架高度（锚板顶面 → 横担顶面）＝ H %.0f − 抬升量 %.0f = %.1f mm '
            '过小，要求 ≥ %.0f mm（抬升量 ＝ 灌浆 %.0f + 锚板厚 %.0f）。'
            % (height_mm, lift, frame_height, geom.MIN_FRAME_HEIGHT_MM,
               geom.GROUND_GROUT_THICKNESS_MM, ground_spec['plate_t']))
    try:
        post_cut_length = geom.post_length(variant_key, frame_height)
    except ValueError as error:
        raise ValueError('构架高度 %.1f mm 过小：%s' % (frame_height, error))

    return {
        'variant': variant_key,
        'height': height_mm,                # 门架高 H（地面 → 横担顶面）
        'frame_height': frame_height,       # 构架高度（锚板顶面 → 横担顶面）
        'arm_length': arm_length_mm,        # 横担全长 L
        'span': span,                       # 两立柱净距 B
        'width': width,                     # 立柱在 u 向的截面宽 W
        'post_cut_length': post_cut_length,  # 立柱下料长
        'weld_contact_length': geom.weld_contact_length(variant_key),
        'allowable_load': geom.allowable_load(variant_key, height_mm,
                                              arm_length_mm),
        'ground_spec': ground_spec,
        'min_pavement_thickness': geom.min_pavement_thickness(variant_key),
    }


# ---------------------------------------------------------------------------
# 构建整组门型架
# ---------------------------------------------------------------------------


def _build_bom_items(metrics, variant_key):
    """整组清单条目（至少含立柱 / 横担 / 锚板 / 膨胀锚栓 / 螺母 / 现场灌浆）。"""
    ground_spec = metrics['ground_spec']
    steel_spec = geom.specification(variant_key)
    return [
        {'code': 'Post', 'name': COMPONENT_POST_NAME,
         'specification': steel_spec, 'length': metrics['post_cut_length'],
         'quantity': 2},
        {'code': 'Arm', 'name': COMPONENT_ARM_NAME,
         'specification': steel_spec, 'length': metrics['arm_length'],
         'quantity': 1},
        # 地面生根：每柱 1 块锚板（共 2 块）；长度记板厚（同 G2 锚板口径）。
        {'code': 'AnchorPlate', 'name': COMPONENT_PLATE_NAME,
         'specification': _plate_specification(ground_spec),
         'length': ground_spec['plate_t'], 'quantity': 2, 'unit': '块'},
        # 每块锚板 4 根膨胀锚栓，2 柱共 8 根；长度记锚栓总长 L。
        {'code': 'AnchorBolt', 'name': COMPONENT_BOLT_NAME,
         'specification': _bolt_specification(ground_spec),
         'length': ground_spec['bolt_len'], 'quantity': 8, 'unit': '根'},
        # 每根锚栓 1 个六角螺母，共 8 个（螺母无下料长度）。
        {'code': 'Nut', 'name': COMPONENT_NUT_NAME,
         'specification': 'M%.0f' % ground_spec['bolt_dia'],
         'length': 0.0, 'quantity': 8, 'unit': '个'},
        # 现场灌浆梯台：每柱 1 处（共 2 处），高度 25。
        {'code': 'GroundGrout', 'name': COMPONENT_GROUT_NAME,
         'specification': '高 %.0f（底面向外扩 %.0f 的梯台）'
                          % (geom.GROUND_GROUT_THICKNESS_MM,
                             geom.GROUND_GROUT_FLARE_MM),
         'length': geom.GROUND_GROUT_THICKNESS_MM, 'quantity': 2, 'unit': '处'},
    ]


def _build_portal_frame_cell(post, variant_key, arm_length_mm, heading_deg,
                             rack_name=None):
    """按竖直线（整组中心线）与横担全长 L 构建门型架单元但**不写入模型**。

    返回 ``(builder, 统计字典)``。一组 ＝ **2 立柱 + 1 横担 + 2 套地面基础件**：

    * 构架高度 ＝ ``H − geom.ground_lift(variant)``（锚板顶面 → 横担顶面）；
    * 两立柱轴线 ＝ 整组中心线 ``∓post_axis_offset(...)``，右柱
      ``mirror_u=True``（H 型钢镜像无害，照传）；
    * 横担以中心线为中点、全长 L，管位面（顶面）落在构架高度处；
    * 每个立柱下各一套地面基础件（``anchor.build_ground_base``）。
    """
    metrics = _frame_metrics(variant_key, post.height_mm, arm_length_mm)
    variant_key = metrics['variant']
    # 钢构架整体抬升量 ＝ 现场灌浆梯台厚 + 锚板厚（几何模块口径）：线下端取梯台
    # 底面（地面）中心，故立柱底面（锚板顶面）比线端高 ground_lift，横担顶面仍
    # 落在所选竖直线的上端 —— 送进几何的「构架高度」＝ H − geom.ground_lift()。
    ground_lift = geom.ground_lift(variant_key)
    frame_height = metrics['frame_height']
    arm_length_mm = metrics['arm_length']
    ground_spec = metrics['ground_spec']

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    uor_per_mm = _uor_per_mm(dgn_model)
    _log('portal frame build start: variant=%s H=%.1f frame=%.1f L=%.1f '
         'B=%.1f lift=%.1f heading=%.2f'
         % (variant_key, metrics['height'], frame_height, arm_length_mm,
            metrics['span'], ground_lift, float(heading_deg)))

    # 两立柱：所选竖直线为整组中心线，两立柱轴线对称于它、在 ∓(L−50−W)/2 处。
    # 右立柱在 u 方向镜像，使两根立柱互为镜像、开口都朝门架外。
    left_axis = geom.post_axis_offset(variant_key, arm_length_mm, 'left')
    right_axis = geom.post_axis_offset(variant_key, arm_length_mm, 'right')

    left = _build_member_element(
        variant_key, 'post', post, frame_height, arm_length_mm, heading_deg,
        left_axis, uor_per_mm, dgn_model, mirror_u=False)
    if left is None:
        raise RuntimeError('左立柱实体创建失败。')
    right = _build_member_element(
        variant_key, 'post', post, frame_height, arm_length_mm, heading_deg,
        right_axis, uor_per_mm, dgn_model, mirror_u=True)
    if right is None:
        raise RuntimeError('右立柱实体创建失败。')

    # 横担：以整组中心线为中点、全长 L，两端各超立柱外缘 25，管位面朝上。
    arm = _build_member_element(
        variant_key, 'arm', post, frame_height, arm_length_mm, heading_deg,
        0.0, uor_per_mm, dgn_model)
    if arm is None:
        raise RuntimeError('横担实体创建失败。')

    builder = _PortalFrameCellBuilder(dgn_model)
    builder.add(left)
    builder.add(right)
    builder.add(arm)

    # 底部地面生根：**每个立柱下各一套**基础件，中心与该侧立柱轴线重合 ——
    # 线下端（地面 / 灌浆梯台底面中心）＋ post_axis_offset(variant, L, side)
    # × u方向 ＋ post_v_offset(variant) × v方向（v 偏移使角钢立柱与横担背靠背）。
    # 一套 ＝ 1 锚板 + 4 膨胀锚栓 + 4 六角螺母 + 1 现场灌浆梯台（共 10 个元素），
    # 由 模块/公共/混凝土锚板.py 的 anchor.build_ground_base 成形。
    run_dir, v_dir = _plane_dirs(heading_deg)
    vertex = _to_uor(post.base, uor_per_mm)
    v_offset = geom.post_v_offset(variant_key)
    base_count = 0
    for side in ('left', 'right'):
        u_offset = geom.post_axis_offset(variant_key, arm_length_mm, side)
        dx_mm, dy_mm = _local_to_world_mm((u_offset, v_offset), run_dir, v_dir)
        cx = vertex[0] + dx_mm * uor_per_mm
        cy = vertex[1] + dy_mm * uor_per_mm
        _log('ground base %s: u=%.1f v=%.1f centre=(%.1f, %.1f, %.1f) mm '
             'plate=%.0f×%.0f×%.0f holes=4-φ%.0f@%.0f bolts=4-M%.0f×%.0f '
             'grout=%.0f'
             % (side, u_offset, v_offset, vertex[0] / uor_per_mm,
                vertex[1] / uor_per_mm, vertex[2] / uor_per_mm,
                ground_spec['plate_e'], ground_spec['plate_e'],
                ground_spec['plate_t'], ground_spec['hole_dia_g'],
                ground_spec['hole_spacing_f'], ground_spec['bolt_dia'],
                ground_spec['bolt_len'], geom.GROUND_GROUT_THICKNESS_MM))
        # 任一件失败即抛 RuntimeError（单元尚未提交，模型里不会留半套）。
        elements = anchor.build_ground_base(
            dgn_model, cx, cy, vertex[2], ground_spec, uor_per_mm,
            grout_thickness_mm=geom.GROUND_GROUT_THICKNESS_MM,
            grout_flare_mm=geom.GROUND_GROUT_FLARE_MM)
        builder.add_all(elements)
        base_count += len(elements)
        _log('ground base %s: %d element(s)' % (side, len(elements)))

    builder.build()
    _log('portal frame: cell assembled, %d children (steel 3 + ground %d)'
         % (builder.child_count, base_count))

    load = metrics['allowable_load']
    if load.value is None:
        builder.note('允许垂直荷载未取到：%s' % load.message)

    steel_spec = geom.specification(variant_key)
    rack_number = geom.build_pipe_rack_number(
        rack_name or '', variant_key, metrics['height'], arm_length_mm)

    result = {
        'variant': variant_key,
        'child_count': builder.child_count,
        'steel_child_count': 3,
        'ground_child_count': base_count,
        'height': metrics['height'],                # 门架高 H
        'frame_height': frame_height,               # 构架高度
        'ground_lift': ground_lift,                 # 灌浆 25 + 锚板厚 T
        'span': metrics['span'],
        'width': metrics['width'],
        'arm_length': arm_length_mm,
        'post_cut_length': metrics['post_cut_length'],
        'weld_contact_length': metrics['weld_contact_length'],
        'heading_deg': float(heading_deg),
        'specification': steel_spec,
        'allowable_load': load.value,
        'allowable_load_message': load.message,
        'ground_spec': metrics['ground_spec'],
        'min_pavement_thickness': metrics['min_pavement_thickness'],
        'pipe_rack_number': rack_number or '',
        'bom_items': _build_bom_items(metrics, variant_key),
        'warnings': list(builder.warnings),
    }
    _log('portal frame built: variant=%s, H=%.1f, frame=%.1f, L=%.1f, B=%.1f, '
         'post=%.1f, weld=%.1f, heading=%.2f, children=%d (ground %d), '
         'number=%s'
         % (variant_key, metrics['height'], frame_height, arm_length_mm,
            metrics['span'], metrics['post_cut_length'],
            metrics['weld_contact_length'], float(heading_deg),
            builder.child_count, base_count, result['pipe_rack_number'] or '-'))
    return builder, result


def replace_portal_frame(post, variant_key, previous_handle,
                         arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                         heading_deg=DEFAULT_HEADING_DEG, rack_name=None,
                         attach=None):
    """重建门型架：先建新的一版并写入，成功后再删除上一版预览。

    ``attach=None`` 时按 :data:`ATTACH_ON_CONFIRM` 决定：**预览阶段默认不写公共库**
    （原生 EC 写入反复触发会卡死，见文件顶部说明），写库推迟到点【确定】。
    """
    builder, result = _build_portal_frame_cell(
        post, variant_key, arm_length_mm, heading_deg, rack_name)
    _log('replace_portal_frame: committing cell')
    new_handle = builder.commit()
    write_items = (not ATTACH_ON_CONFIRM) if attach is None else bool(attach)
    if write_items:
        _log('replace_portal_frame: attaching ItemType/公共库')
        _write_support_items(new_handle, result)
    else:
        _log('replace_portal_frame: 预览不写库（写库推迟到【确定】）')
    _log('replace_portal_frame: deleting previous preview')
    deleted = _delete_preview(previous_handle)
    _log('replace_portal_frame: done (deleted=%s)' % bool(deleted))
    return new_handle, result, deleted


def draw_portal_frame(post, variant_key, arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                      heading_deg=DEFAULT_HEADING_DEG, rack_name=None):
    """直接创建整组单元并写入模型（**直接落图，故写库**），返回 (cell, 统计字典)。"""
    builder, result = _build_portal_frame_cell(
        post, variant_key, arm_length_mm, heading_deg, rack_name)
    cell = builder.commit()
    _write_support_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。

    本插件不单独维护自己的库，统一走 ``支吊架公共库``；因此清单里会同时包含
    端焊三角架、L 型管架、D8 门型架、G5 地面上生根的门型架等全部支吊架。
    """
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', 'G5门型架_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 说明文字（面板复用）
# ---------------------------------------------------------------------------
# 面板上的文字块只保留「预览」「状态」两块（提示太密集会刷屏），因此原来
# 拆成多段的构件型式 / 连接 / 地面生根说明已删掉，必要信息改由：
#   * 只读行（构件A、立柱宽度 W、锚板 / 孔 / 锚栓 / 灌浆 / MIN.h）承载；
#   * 面板顶部的 hint 文本框用一两句话概括。


def _load_text(load):
    """允许荷载显示：取到只给数值；未取到才附一句原因（面板尽量少字）。"""
    if load.value is None:
        return '—（%s）' % load.message
    return '%.2f kN' % load.value


# ---------------------------------------------------------------------------
# 面板（Tkinter / bentley_ui）
# ---------------------------------------------------------------------------


class _PortalFrameSettingsDialog(GlassDialog):
    """子项 / 横担全长 L / 朝向 / 编号 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'G5PortalFrame'
    # UI 刷新轮询周期（ms）：原生回调只写状态，由这个周期统一刷进控件。
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.post = None
        self.post_handle = None
        self.preview_handle = None
        self.preview_result = None
        # 当前预览是否已写进共享支吊架库（预览阶段不写，见文件顶部策略说明）。
        self._preview_attached = False
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
        self._rack_name = tk.StringVar(value=DEFAULT_RACK_NAME)
        self._arm = tk.StringVar(value='%.0f' % DEFAULT_ARM_LENGTH_MM)
        self._heading = tk.StringVar(value='%.0f' % DEFAULT_HEADING_DEG)
        self._keep_line = tk.BooleanVar(value=True)
        self._spec = tk.StringVar(value='—')
        self._width = tk.StringVar(value='—')
        self._height = tk.StringVar(value='—')
        self._arm_length = tk.StringVar(value='—')
        self._span = tk.StringVar(value='—')
        self._frame_height = tk.StringVar(value='—')
        self._post_length = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._plate = tk.StringVar(value='—')
        self._holes = tk.StringVar(value='—')
        self._bolt = tk.StringVar(value='—')
        self._grout = tk.StringVar(value='—')
        self._min_h = tk.StringVar(value='—')
        self._rack_number = tk.StringVar(value='—')
        self._variant_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()

        # 关闭窗口时按"取消"处理：丢弃预览并结束工具。
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        try:
            self.minsize(620, 700)
        except tk.TclError:
            pass
        _log('panel built rev=%s file=%s'
             % (UI_REVISION, os.path.abspath(__file__)))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        shell_form = self.build_shell(
            UI_TITLE,
            '点选一条竖直线（整组中心线）· 输入横担全长 L 与朝向 · 自动预览，'
            '地面生根：锚板 + 4 膨胀锚栓 + 现场灌浆')
        # 整块内容放进固定高度的滚动容器，保证面板再长也不超出屏幕；
        # 鼠标滚轮或右侧细滚动条查看。
        shell_form.columnconfigure(0, weight=1)
        shell_form.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(shell_form, bg=CARD, height=360)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        form = self._scroll.body
        form.columnconfigure(1, weight=1)

        hint_frame, hint_text = self._text_field(form, height=3)
        hint_frame.grid(row=0, column=0, columnspan=2, sticky='ew')
        self._set_text(hint_text, (
            '点选一条竖直线＝整组门型架的中心线：线的【上端】＝管底标高＝横担顶面，'
            '【下端】＝地面；线长即门架高 H。面板输入【横担全长 L】：横担以中心线为'
            '中点、两端各超立柱外缘 25，净距 B ＝ L − 2×25 − 2W 自动计算。'
            '每根立柱下自动生成锚板 + 4 膨胀锚栓 + 螺母 + 现场灌浆梯台（高 25），'
            '钢构架整体抬高（灌浆 + 板厚）。'))

        ttk.Label(form, text='构件规格（表 1 / 表 2）',
                  style='Section.TLabel').grid(
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

        ttk.Label(form, text='立柱宽度 W', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._width, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(form, orient='horizontal').grid(
            row=5, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='尺寸参数（H 由所选竖直线线长给出）',
                  style='Section.TLabel').grid(
            row=6, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(form, text='门架高 H', style='GlassMuted.TLabel').grid(
            row=7, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._height, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=7, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='横担全长 L', style='GlassMuted.TLabel').grid(
            row=8, column=0, sticky='nw', pady=3)
        arm_holder = tk.Frame(form, bg=CARD)
        arm_holder.grid(row=8, column=1, sticky='w', padx=(10, 0), pady=3)
        arm_input = tk.Frame(arm_holder, bg=CARD)
        arm_input.pack(anchor='w')
        self._arm_entry = self._entry(arm_input, self._arm, 9)
        tk.Label(arm_holder,
                 text='mm　横担全长（两端各超立柱外缘 %.0f；净距 B 自动计算）'
                      % geom.ARM_END_OVERHANG_MM,
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w',
                                                             pady=(1, 0))

        ttk.Label(form, text='横担长 L（用于编号 / 清单）',
                  style='GlassMuted.TLabel').grid(row=9, column=0, sticky='w',
                                                  pady=3)
        tk.Label(form, textvariable=self._arm_length, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=9, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='两立柱净距 B', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._span, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=10, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='构架高度（锚板顶面→横担顶面）',
                  style='GlassMuted.TLabel').grid(row=11, column=0, sticky='w',
                                                  pady=3)
        tk.Label(form, textvariable=self._frame_height, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=11, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='立柱下料长', style='GlassMuted.TLabel').grid(
            row=12, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._post_length, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=12, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='允许垂直荷载', style='GlassMuted.TLabel').grid(
            row=13, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._load, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=330).grid(
            row=13, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='朝向', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='nw', pady=3)
        heading_holder = tk.Frame(form, bg=CARD)
        heading_holder.grid(row=14, column=1, sticky='w', padx=(10, 0), pady=3)
        heading_input = tk.Frame(heading_holder, bg=CARD)
        heading_input.pack(anchor='w')
        self._heading_entry = self._entry(heading_input, self._heading, 9)
        tk.Label(heading_holder, text='°　门架平面内的横担指向（0 = 世界 +X）',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w',
                                                             pady=(1, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=15, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='地面生根（表 2，每个立柱下一套）',
                  style='Section.TLabel').grid(
            row=16, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(form, text='锚板', style='GlassMuted.TLabel').grid(
            row=17, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._plate, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=17, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='螺栓孔', style='GlassMuted.TLabel').grid(
            row=18, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._holes, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=18, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='膨胀锚栓（每柱 4 根）',
                  style='GlassMuted.TLabel').grid(row=19, column=0, sticky='w',
                                                  pady=3)
        tk.Label(form, textvariable=self._bolt, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=19, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='现场灌浆', style='GlassMuted.TLabel').grid(
            row=20, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._grout, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=20, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='地坪最小厚度 MIN.h',
                  style='GlassMuted.TLabel').grid(row=21, column=0, sticky='w',
                                                  pady=3)
        tk.Label(form, textvariable=self._min_h, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=21, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(form, orient='horizontal').grid(
            row=22, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='管架编号', style='Section.TLabel').grid(
            row=23, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(form, text='名称', style='GlassMuted.TLabel').grid(
            row=24, column=0, sticky='nw', pady=3)
        name_holder = tk.Frame(form, bg=CARD)
        name_holder.grid(row=24, column=1, sticky='w', padx=(10, 0), pady=3)
        name_input = tk.Frame(name_holder, bg=CARD)
        name_input.pack(anchor='w')
        self._rack_name_entry = self._entry(name_input, self._rack_name, 12)
        tk.Label(name_holder, text='管架系列代号；编号 = 名称-子项-H-L，留空则不附加',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w',
                                                             pady=(1, 0))

        ttk.Label(form, text='编号', style='GlassMuted.TLabel').grid(
            row=25, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._rack_number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=25, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(form, orient='horizontal').grid(
            row=26, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(form, text='创建选项', style='Section.TLabel').grid(
            row=27, column=0, columnspan=2, sticky='w', pady=(0, 2))
        self._keep_check = tk.Checkbutton(
            form, text='创建后保留所选竖直线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.grid(row=28, column=0, columnspan=2, sticky='w')

        # 预览 / 状态固定在滚动区下方，始终可见（提示只留这两块，避免刷屏）。
        info = tk.Frame(shell_form, bg=CARD)
        info.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self._preview_info_frame, self._preview_info_text = self._text_field(
            info, height=3)
        self._preview_info_frame.pack(fill='x')
        self._status_frame, self._status_text = self._text_field(info, height=2)
        self._status_frame.pack(fill='x', pady=(4, 0))
        self._set_text(self._preview_info_text, '预览：—')
        self._set_text(self._status_text,
                       '请点选一条竖直线（整组中心线）；改参数会自动重建预览。')

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

        self._arm.trace_add('write', self.on_text_changed)
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

        for key, variable in (('arm', self._arm),
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
            state['rack_name'] = self._rack_name.get()
            state['arm'] = self._arm.get()
            state['heading'] = self._heading.get()
            state['keep_line'] = bool(self._keep_line.get())
        except tk.TclError:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(
            self._variant.get(), geom.DEFAULT_VARIANT)

    def current_arm_length(self):
        try:
            return float((self._arm.get() or '').strip())
        except (TypeError, ValueError):
            return None

    def current_heading(self):
        try:
            return float((self._heading.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_HEADING_DEG

    def current_options(self):
        arm_length = self.current_arm_length()
        if arm_length is None:
            raise ValueError('横担全长 L 请填写数字（mm）。')
        return {
            'variant': self.current_variant(),
            'arm_length': arm_length,
            'heading': self.current_heading(),
            'rack_name': self._rack_name.get().strip(),
        }

    def current_rack_number(self, post=None):
        post = post if post is not None else self.post
        arm_length = self.current_arm_length()
        if post is None or arm_length is None:
            return ''
        return geom.build_pipe_rack_number(
            self._rack_name.get(), self.current_variant(), post.height_mm,
            arm_length)

    def set_status(self, message, is_error=False, flush=True):
        # 只在 Tk 定时器上下文里刷新控件（见 _poll_ui/_flush_ui）。
        self._set_text(getattr(self, '_status_text', None), message)

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        self._set_text(self._preview_info_text,
            '预览：%s %s，H=%.0f（构架 %.1f），L=%.0f，B=%.1f，'
            '立柱下料 %.1f，朝向 %.0f°，%d 个子元素，编号 %s。'
            % (result['variant'], result['specification'], result['height'],
               result['frame_height'], result['arm_length'], result['span'],
               result['post_cut_length'], result['heading_deg'],
               result['child_count'], number)
        )

    def refresh_spec(self):
        """按当前子项刷新规格 / 地面生根 / 只读尺寸（不生成几何）。"""
        variant_key = self.current_variant()
        self._spec.set(geom.specification(variant_key))
        self._width.set('%.0f' % geom.inplane_width(variant_key))

        ground_spec = geom.ground_anchor_spec(variant_key)
        self._plate.set(_plate_specification(ground_spec))
        self._holes.set(_hole_specification(ground_spec))
        self._bolt.set('%s（h_ef≥%.0f）'
                       % (_bolt_specification(ground_spec),
                          ground_spec['embed']))
        self._grout.set('高 %.0f（每边外扩 %.0f）'
                        % (geom.GROUND_GROUT_THICKNESS_MM,
                           geom.GROUND_GROUT_FLARE_MM))
        self._min_h.set('%.0f' % geom.min_pavement_thickness(variant_key))
        self.refresh_line_labels()

    def refresh_line_labels(self):
        self._show_line_values(self.post)

    def refresh_check(self):
        """尺寸不合规时把原因写进状态栏；合规时**不写**（数字已在只读行里）。"""
        post = self.post
        if post is None:
            return
        try:
            _frame_metrics(self.current_variant(), post.height_mm,
                           self.current_arm_length())
        except (ValueError, TypeError) as error:
            self.set_status('尺寸不合规：%s' % error, True)

    def _show_line_values(self, post):
        if post is None:
            self._height.set('—')
            self._arm_length.set('—')
            self._span.set('—')
            self._frame_height.set('—')
            self._post_length.set('—')
            self._load.set('—')
            self._rack_number.set('—')
            self.refresh_check()
            return
        # 门架高 H ＝ 所选竖直线线长（地面 → 横担顶面）。
        self._height.set('%.1f' % post.height_mm)
        arm_length = self.current_arm_length()
        self._arm_length.set('—' if arm_length is None else '%.1f' % arm_length)
        try:
            metrics = _frame_metrics(self.current_variant(), post.height_mm,
                                     arm_length)
        except (ValueError, TypeError) as error:
            _log('line values rejected: %s' % error)
            self._span.set('—')
            self._frame_height.set('—')
            self._post_length.set('—')
            self._load.set('—')
        else:
            self._span.set('%.1f' % metrics['span'])
            self._frame_height.set('%.1f' % metrics['frame_height'])
            self._post_length.set('%.1f' % metrics['post_cut_length'])
            self._load.set(_load_text(metrics['allowable_load']))
        number = self.current_rack_number(post)
        self._rack_number.set(number if number else '（名称留空，不附加）')
        self.refresh_check()

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
        if self.current_arm_length() is None:
            # L 不是数字：不生成（并撤掉可能过期的预览），只提示。
            self._cancel_pending_regeneration()
            self.discard_preview()
            self.set_status('横担全长 L 请填写数字（mm），当前不生成预览。', True)
            return
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
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
            self.discard_preview()
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None

        _log('regenerate: start options=%s' % (options,))
        try:
            handle, result, deleted = replace_portal_frame(
                self.post, options['variant'], self.preview_handle,
                options['arm_length'], options['heading'],
                options['rack_name'])
        except Exception as error:
            # 参数 / 几何不合规**只写进面板状态栏**：不 print 到控制台、也不弹
            # MicroStation 消息 —— 高频改参数时会刷屏。细节仍进调试日志。
            if isinstance(error, ValueError):
                _log('regenerate rejected: %s' % error)
            else:
                _log_exception('preview failed')
            self.discard_preview()
            self._pending_message = '无法生成：%s' % error
            self._pending_is_error = True
            return None

        self.preview_handle = handle
        self.preview_result = result
        self._preview_attached = False
        message = (
            '预览已更新：%s %s，H=%.0f（构架 %.1f），L=%.0f，B=%.1f，'
            '编号 %s。点【确定】保留并写入清单。' % (
                result['variant'], result['specification'], result['height'],
                result['frame_height'], result['arm_length'], result['span'],
                result['pipe_rack_number'] or '—',
            )
        )
        if result['warnings']:
            message += '注意：%s' % '；'.join(result['warnings'])
        self._pending_result = result
        self._pending_message = message
        self._pending_is_error = False
        _log('regenerate: done')
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        self._preview_attached = False
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
        if self.current_arm_length() is None:
            self.set_status('横担全长 L 请填写数字（mm），无法生成。', True)
            return
        self.confirmed = True
        # 清单写库在【确定】这一刻做（预览阶段完全不碰 ItemType，见文件顶部策略）：
        # 原生 EC 写入次数从"每改一次参数一次"降到"每套一次"，也不会为取消掉的
        # 预览在公共库里留下垃圾 ItemType。
        self.attach_result()
        if self.preview_handle is not None and not self._keep_line.get():
            self.delete_source_line()
        self.finish_tool()

    def attach_result(self):
        """把当前预览写进共享支吊架库（整组 + 各构件）；失败只记日志，不影响落图。"""
        handle = self.preview_handle
        result = self.preview_result
        if handle is None or result is None:
            return 0
        if self._preview_attached:
            _log('attach skipped: preview already written')
            return 0
        try:
            if not handle.IsValid():
                _log('attach skipped: preview handle invalid')
                return 0
        except Exception:
            _log_exception('attach handle check failed')
            return 0
        count = _write_support_items(handle, result)
        if count:
            self._preview_attached = True
            _log('attach on confirm: %s item(s) written' % count)
            self.set_status('已保留门型架，清单已写入公共库（%d 项）。' % count)
            try:
                NotificationManager.OutputPrompt(
                    '%s：清单已写入公共库（%d 项）' % (UI_TITLE, count))
            except Exception:
                _log_exception('OutputPrompt failed')
        else:
            message = ('%s：公共库清单未写入（几何已保留、不受影响），详见日志。'
                       % UI_TITLE)
            self.set_status(message, True)
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                _log_exception('OutputPrompt failed')
        return count

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


# ---------------------------------------------------------------------------
# 交互工具：点选竖直线
# ---------------------------------------------------------------------------


class PortalFrameByLineTool(DgnElementSetTool):
    """点选一条竖直线（整组中心线）并放置地面上生根门型架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('G5GroundPortalFrameByLineTool')

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
            '请点选一条竖直线段（整组中心线）：上端＝横担顶面、下端＝地面。')

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
            # 同样只走面板状态栏（不弹消息、不 print），避免点错元素时刷屏。
            _log_exception('element modify failed')
            try:
                self.tool_settings.note_hover_error('无法生成：%s' % error)
            except Exception:
                pass
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        PortalFrameByLineTool.InstallNewInstance(self.GetToolId(), settings,
                                                 False)

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


def show_g5_portal_frame_dialog():
    return PortalFrameByLineTool.InstallNewInstance(0)


def export_g5_portal_frame_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYG5FRAME PLACE / PYG5FRAME EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, 'G5门型架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenG5PortalFrame():
    PyMain()


def ExportG5PortalFrameBom():
    export_g5_portal_frame_bom()


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
        show_g5_portal_frame_dialog()
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
