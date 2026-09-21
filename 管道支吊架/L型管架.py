# -*- coding: utf-8 -*-
"""L 型管架（选线版）放置工具。

在模型中点选一条用户绘制的 **L 形智能线**（两段直线，共享拐点），据此生成
一组 L 型管架：

    竖直线 = 立杆（轴线）       —— 截面重心落在该竖直线上
    水平线 = 横担顶面（固定管子的面）—— 截面最高面落在该水平线上

整组构件（立杆 + 横担）写成一个普通单元（Normal Cell），清单写入**管道支吊架
公共库** ``支吊架公共库``（`SupportType='L型管架'`），可与端焊三角架一起
统计；可导出 JSON / Excel 清单。

几何做法（型钢截面的真实圆弧轮廓与沿路径扫掠）复用仓库内
``型钢截面生成器`` 的数据 / 几何模块与 ``steel_sweep_geometry``；
面板用 **Tkinter**，外观复用仓库共享的 ``bentley_ui`` 主题。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import importlib.util
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

# 通配导入不一定导出这两个符号，显式再导入一次（与 型钢截面生成器.py 一致）。
from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

# tkinter 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致 tk / ttk 被替换、建控件 / 事件循环时直接崩溃。
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
# 公共库在 模块/公共/，本插件几何在 模块/L型管架/；仓库根提供共享 UI 工具箱。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'L型管架')
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

import L型管架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'L型管架'
SUPPORT_CODE = 'L_PIPE_RACK'


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'L型管架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'L 型管架'

# 整组构件写入的普通单元名。
CELL_NAME = 'L_PIPE_RACK'

COMPONENT_POST_NAME = '立杆'
COMPONENT_ARM_NAME = '横担'

# 允许荷载查询用的默认 B（mm）。
DEFAULT_WIDTH_B_MM = 250.0

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖，避免打到一半就重建


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
    for module in (geom, steel_sweep_geometry, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass
    # 型钢几何 / 数据模块随 L型管架_几何 一并重新加载。
    for name in ('steel_sections.steel_equal_angle_data', 'steel_sections.steel_equal_angle_geometry',
                 'steel_sections.steel_channel_data', 'steel_sections.steel_channel_geometry',
                 'steel_sections.steel_hbeam_data', 'steel_sections.steel_hbeam_geometry'):
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 单位换算
# ---------------------------------------------------------------------------


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
            raise ValueError('所选元素含圆弧或曲线；请选择一条 L 形折线（直线段）。')


def extract_l_shape(element_handle, hanger=False):
    """从所选元素提取并校验 L 形线，返回 ``L型管架_几何.LShape``。

    ``hanger=True``（类型 3/4）要求立杆在上（竖直段在拐点上方）。
    """
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条 L 形折线（两段直线：一竖一横）。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    pieces_mm = [[_point_to_mm(point, uor_per_mm) for point in piece]
                 for piece in pieces]
    return geom.parse_l_shape(pieces_mm, hanger)


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


def _build_member_element(variant_key, member_kind, line, vertex, run_dir, v_dir,
                          uor_per_mm, dgn_model, hanger=False):
    """构建一个构件（立杆 / 横担）实体元素，不写入模型。

    截面朝向与扫掠起点由 ``L型管架_几何`` 的
    ``member_section_params`` / ``member_axes`` / ``member_origin_length``
    给出，坐标系为支架局部基 (u, v, w)，原点取 L 形线拐点。
    """
    geometry = geom.member_geometry(variant_key, member_kind, uor_per_mm, hanger)
    axis_x, axis_y, axis_z = geom.member_axes(variant_key, member_kind, hanger)
    axis_x = _world_axis(axis_x, run_dir, v_dir)
    axis_y = _world_axis(axis_y, run_dir, v_dir)
    axis_z = _world_axis(axis_z, run_dir, v_dir)
    origin_uvw, length_mm = geom.member_origin_length(
        variant_key, member_kind, line.post_height_mm, line.arm_length_mm, hanger)

    origin = (
        vertex[0] + origin_uvw[0] * uor_per_mm * run_dir[0]
        + origin_uvw[1] * uor_per_mm * v_dir[0],
        vertex[1] + origin_uvw[0] * uor_per_mm * run_dir[1]
        + origin_uvw[1] * uor_per_mm * v_dir[1],
        vertex[2] + origin_uvw[2] * uor_per_mm,
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


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


class _PipeRackCellBuilder(object):
    """把立杆、横担子元素一次性写成一个普通单元。"""

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
            raise RuntimeError('L 型管架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法把 L 型管架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成 L 型管架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法把 L 型管架单元写入活动模型。')
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
# ItemType：构件清单与管架编号
# ---------------------------------------------------------------------------


def _attach_support_items(cell, result):
    """把整组管架写入共享支吊架库（整组记录 + 立杆/横担构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=result.get('specification', ''),
        components=result.get('bom_items', ()),
    )


# ---------------------------------------------------------------------------
# 构建整组管架
# ---------------------------------------------------------------------------


def _build_pipe_rack_cell(line, variant_key, rack_type=1, rack_name=None):
    """按 L 形线构建 L 型管架单元但**不写入模型**。

    返回 ``(builder, 统计字典)``。
    """
    if not geom.variant_supports_type(variant_key, rack_type):
        raise ValueError(
            '子项 %s 仅对类型 %s 有效，请调整类型或子项。'
            % (variant_key, '/'.join(str(t) for t in geom.allowed_rack_types(variant_key))))

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    uor_per_mm = _uor_per_mm(dgn_model)
    vertex = _to_uor(line.corner, uor_per_mm)
    hanger = geom.hanger_type(rack_type)

    heading = math.radians(line.heading_deg)
    run_dir = (math.cos(heading), math.sin(heading), 0.0)
    v_dir = (-math.sin(heading), math.cos(heading), 0.0)

    # 立杆：类型 1/2 在下、类型 3/4 在上（吊架）。
    post = _build_member_element(
        variant_key, 'post', line, vertex, run_dir, v_dir, uor_per_mm, dgn_model,
        hanger)
    if post is None:
        raise RuntimeError('立杆实体创建失败。')

    # 横担：顶面在所选水平线上、朝上承管；后端超出立杆边缘 15 mm。
    arm = _build_member_element(
        variant_key, 'arm', line, vertex, run_dir, v_dir, uor_per_mm, dgn_model,
        hanger)
    if arm is None:
        raise RuntimeError('横担实体创建失败。')

    builder = _PipeRackCellBuilder(dgn_model)
    builder.add(post)
    builder.add(arm)
    builder.build()

    spec = geom.specification(variant_key)
    rack_number = _build_rack_number(
        rack_name, rack_type, variant_key, line.post_height_mm, line.arm_length_mm)
    # 实际下料长度：立杆扣除与横担相贴/相交部分，横担含后端 15 mm 与偏置。
    _, post_cut_length = geom.member_origin_length(
        variant_key, 'post', line.post_height_mm, line.arm_length_mm, hanger)
    _, arm_cut_length = geom.member_origin_length(
        variant_key, 'arm', line.post_height_mm, line.arm_length_mm, hanger)
    result = {
        'variant': variant_key,
        'rack_type': int(rack_type),
        'child_count': builder.child_count,
        'post_height': line.post_height_mm,
        'arm_length': line.arm_length_mm,
        'post_cut_length': post_cut_length,
        'arm_cut_length': arm_cut_length,
        'heading_deg': line.heading_deg,
        'specification': spec,
        'pipe_rack_number': rack_number or '',
        'bom_items': [
            {'code': 'Post', 'name': COMPONENT_POST_NAME,
             'specification': spec, 'length': post_cut_length},
            {'code': 'Arm', 'name': COMPONENT_ARM_NAME,
             'specification': spec, 'length': arm_cut_length},
        ],
        'warnings': list(builder.warnings),
    }
    _log('l pipe rack built: variant=%s, type=%d, H=%.1f, L=%.1f, heading=%.2f, '
         'cells=%d, number=%s' %
         (variant_key, int(rack_type), line.post_height_mm, line.arm_length_mm,
          line.heading_deg, builder.child_count, result['pipe_rack_number'] or '-'))
    return builder, result


def _build_rack_number(rack_name, rack_type, variant_key, height_mm, arm_mm):
    return geom.build_pipe_rack_number(
        rack_name or '', rack_type, variant_key, height_mm, arm_mm)


def replace_pipe_rack(line, variant_key, previous_handle, rack_type=1,
                      rack_name=None):
    """重建管架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_pipe_rack_cell(line, variant_key, rack_type, rack_name)
    new_handle = builder.commit()
    _attach_support_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_pipe_rack(line, variant_key, rack_type=1, rack_name=None):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_pipe_rack_cell(line, variant_key, rack_type, rack_name)
    cell = builder.commit()
    _attach_support_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。

    本插件不再单独维护自己的库，统一走 ``支吊架公共库``；因此清单里会
    同时包含端焊三角架、L 型管架以及今后接入的其它支吊架。
    """
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', 'L型管架_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 工具设置面板
# ---------------------------------------------------------------------------


# 管架类型（编号后缀）选项：类型 1/2 立杆在下，类型 3/4 为吊架（立杆在上）。
RACK_TYPE_OPTIONS = (
    (1, '类型1  |  立杆在下（端焊）'),
    (2, '类型2  |  立杆在下（侧焊）'),
    (3, '类型3  |  立杆在上（端焊·吊架）'),
    (4, '类型4  |  立杆在上（侧焊·吊架）'),
)


class _PipeRackDialog(GlassDialog):
    """子项 / 类型 / B / 编号 选择，预览 / 导出 / 确定 / 取消面板。"""

    STATE_KEY = 'LPipeRack'
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
        # 此时任何 Tcl 调用（after / StringVar.set / 控件 configure / destroy）
        # 都可能弄坏 Tcl 的事件队列，随后 update() 直接访问冲突崩溃。因此回调里
        # 只写普通 Python 状态，所有 Tk 刷新交给常驻定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._hover_line = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False
        # 供原生回调使用的纯 Python 缓存（绝不能在回调里读控件 = 调 Tcl）。
        self._rack_type_cache = 1

        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._width = tk.StringVar(value='%.0f' % DEFAULT_WIDTH_B_MM)
        self._rack_name = tk.StringVar(value='D5')
        self._keep_line = tk.BooleanVar(value=True)
        self._spec = tk.StringVar(value='—')
        self._post = tk.StringVar(value='—')
        self._arm = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._load_note = tk.StringVar(value='')
        self._rack_number = tk.StringVar(value='—')
        self._spec_info = tk.StringVar(value='')
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar(value='请选择一条 L 形折线。')
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
            UI_TITLE, '点选 L 形折线生成 L 型管架 · 改参数自动重建预览')
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)
        # 参数与预览可滚动；实时状态和操作区始终钉在底部。
        self._scroll = ScrollFrame(form, bg=CARD, height=500)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text='点选一条 L 形折线：竖直线为立杆轴线，水平线为横担顶面'
                 '（固定管子的面）；类型1/2 要求立杆在下，类型3/4 为吊架、'
                 '要求立杆在上。点【确定】保留，点【取消】放弃。',
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
        specification_data.columnconfigure(0, weight=1)
        self._compact_value(
            specification_data, 0, 0, '构件A（立杆 / 横担）', self._spec)

        ttk.Separator(body, orient='horizontal').grid(
            row=3, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='尺寸参数', style='Section.TLabel').grid(
            row=4, column=0, sticky='w', pady=(0, 5))

        dimensions = tk.Frame(body, bg=CARD)
        dimensions.grid(row=5, column=0, sticky='ew')
        dimensions.columnconfigure(0, weight=1, uniform='dimension')
        dimensions.columnconfigure(1, weight=1, uniform='dimension')

        # 输入项置顶；由折线读取和查表得到的数据放在后面。
        self._width_entry = self._compact_entry(
            dimensions, 0, 0, 'B', self._width, 9,
            unit='mm', note='管架水平参数；用于查允许垂直荷载',
            columnspan=2)
        self._compact_value(
            dimensions, 1, 0, '立杆高 H', self._post,
            unit='mm', note='由所选竖直线自动读取')
        self._compact_value(
            dimensions, 1, 1, '横担长 L', self._arm,
            unit='mm', note='由所选水平线自动读取')
        self._compact_value(
            dimensions, 2, 0, '允许垂直荷载', self._load,
            unit='kN', notevariable=self._load_note, columnspan=2)

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
        self._keep_check = tk.Checkbutton(
            form, text='创建后保留所选 L 形线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.grid(row=2, column=0, sticky='w', pady=(6, 0))

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

        self._width.trace_add('write', self.on_text_changed)
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
        # 与 T 形架一致：类型每次打开都从类型 1 开始。
        self._rack_type.set(RACK_TYPE_OPTIONS[0][1])
        width = state.get('width')
        if isinstance(width, str) and width.strip():
            self._width.set(width)
        rack_name = state.get('rack_name')
        if isinstance(rack_name, str):
            self._rack_name.set(rack_name)
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        self._rack_type_cache = self.current_rack_type()
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['width'] = self._width.get()
            state['rack_name'] = self._rack_name.get()
            state['keep_line'] = bool(self._keep_line.get())
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(self._variant.get(),
                                          geom.DEFAULT_VARIANT)

    def current_rack_type(self):
        return self._type_by_label.get(self._rack_type.get(), 1)

    def current_width(self):
        try:
            return float((self._width.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_WIDTH_B_MM

    def current_hanger(self):
        return geom.hanger_type(self.current_rack_type())

    def hanger_hint(self):
        """供原生回调使用：当前是否吊架。纯 Python，不读控件。"""
        return geom.hanger_type(self._rack_type_cache)

    def current_options(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        if not geom.variant_supports_type(variant_key, rack_type):
            raise ValueError(self._invalid_message())
        return {
            'variant': variant_key,
            'rack_type': rack_type,
            'hanger': geom.hanger_type(rack_type),
            'rack_name': (self._rack_name.get() or '').strip(),
            'width': self.current_width(),
        }

    def current_rack_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        return _build_rack_number(
            self._rack_name.get(), self.current_rack_type(),
            self.current_variant(), line.post_height_mm, line.arm_length_mm)

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
        self._preview_info.set(
            '预览：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，'
            '单元含 %d 个子元素；编号 %s。' % (
                result['variant'], result['rack_type'],
                result['specification'], result['post_height'],
                result['arm_length'], result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        self._spec.set(geom.specification(variant_key))
        hanger = self.current_hanger()
        position = '立杆在上（吊架）' if hanger else '立杆在下'
        if self._options_valid():
            self._spec_info_label.configure(fg=INK)
            self._spec_info.set(
                '构件A：立杆与横担同规格 %s（%s）；%s。'
                % (geom.specification(variant_key),
                   _family_description(variant_key, hanger), position))
        else:
            self._spec_info_label.configure(fg='#b42318')
            self._spec_info.set(self._invalid_message())
        self.refresh_line_labels()

    def _show_line_values(self, line):
        if line is None:
            self._post.set('—')
            self._arm.set('—')
            self._load.set('—')
            self._load_note.set('')
            self._rack_number.set('—')
            return
        self._post.set('%.1f' % line.post_height_mm)
        self._arm.set('%.1f' % line.arm_length_mm)

        result = geom.allowable_load(
            self.current_variant(), line.post_height_mm, self.current_width())
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
        # 在 Tk 事件里刷新原生回调要用的纯 Python 缓存（读控件在这里是安全的）。
        self._rack_type_cache = self.current_rack_type()
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
        allowed = '/'.join(
            str(t) for t in geom.allowed_rack_types(variant_key))
        return ('不合法组合：子项 %s（工字钢）仅对端焊类型 %s 有效；'
                '类型 %d 为侧焊、无工字钢构件。请改选子项或类型。'
                % (variant_key, allowed, rack_type))

    def on_text_changed(self, *_unused):
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
        """悬停到一条合规 L 形线上：只记 Python 状态，由 poll 定时器刷新。"""
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
        """按当前 L 形线与选项重建预览：先建新的一版，成功后再删掉旧的。

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
            handle, result, deleted = replace_pipe_rack(
                self.line, options['variant'], self.preview_handle,
                options['rack_type'], options['rack_name'])
        except Exception as error:
            message = 'L 型管架生成失败：%s' % error
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
            '预览已更新：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，'
            '单元含 %d 个子元素，编号 %s。%s改参数会自动重建；'
            '点【确定】保留，点【取消】放弃。' % (
                result['variant'], result['rack_type'], result['specification'],
                result['post_height'], result['arm_length'],
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
        self.set_status('所选 L 形线删除失败，请手动删除。', True)
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


def _family_description(variant_key, hanger=False):
    variant = geom.VARIANTS[variant_key]
    if hanger:
        labels = {
            'equal_angle': '等边角钢；立杆与横担背靠背、下段伸入横担竖直肢',
            'channel': '平行腿槽钢；立杆与横担背靠背、下段伸入横担腹板',
            'hbeam': '热轧 H 型钢；立杆下端顶焊在横担上翼缘上表面',
        }
    else:
        labels = {
            'equal_angle': '等边角钢；横担开口朝立杆侧、后端超立杆背面 15mm；立杆一条肢贴横担开口侧',
            'channel': '平行腿槽钢；立杆与横担背靠背、横担后端超立杆边缘 15mm',
            'hbeam': '热轧 H 型钢；立杆顶焊横担下翼缘、横担后端超立杆边缘 15mm',
        }
    return labels.get(variant['family'], '')


# ---------------------------------------------------------------------------
# 交互工具：点选 L 形折线
# ---------------------------------------------------------------------------


class PipeRackByLineTool(DgnElementSetTool):
    """点选一条 L 形折线并放置 L 型管架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('LPipeRackByLineTool')

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
            '请点选一条 L 形折线：竖直线=立杆轴线，水平线=横担顶面；'
            '两段共享拐点且大致垂直。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            # 只读纯 Python 缓存，**绝不读控件**（读 StringVar = 调 Tcl，
            # 会在 locate 回调里重入 Tcl 导致 OPM 原生崩溃）。
            hanger = (self.tool_settings.hanger_hint()
                      if self.tool_settings is not None else False)
            line = extract_l_shape(handle, hanger)
            if self.tool_settings is not None:
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
            line = extract_l_shape(eeh, self.tool_settings.hanger_hint())
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = 'L 型管架生成失败：%s' % error
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
        PipeRackByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

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
            active = getattr(PipeRackByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _PipeRackDialog())
        if owner:
            PipeRackByLineTool._active_settings = settings
        tool = PipeRackByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                PipeRackByLineTool._active_settings = None
        return tool


def show_l_pipe_rack_dialog():
    return PipeRackByLineTool.InstallNewInstance(0)


def export_l_pipe_rack_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYLPIPERACK PLACE / PYLPIPERACK EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, 'L型管架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenLPipeRack():
    PyMain()


def ExportLPipeRackBom():
    export_l_pipe_rack_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_l_pipe_rack_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('L 型管架工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'L 型管架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
