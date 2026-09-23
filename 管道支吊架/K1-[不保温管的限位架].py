# -*- coding: utf-8 -*-
"""K1 限位架（不保温管的限位架 1/2″~36″）放置工具。

在模型中**点选一根管道**（自动读管径）或一条**普通直线段**（用面板 DN），
在点击处沿其轴线生成一组 K1 限位架：

    子项 A  半片 T **竖直放置**：翼缘（内侧竖直面）夹住已有钢构，管道焊在其顶端截面
    子项 B/C **水平工字钢、长度沿管轴**：腹板水平、两翼缘竖直，管道骑在两翼缘
             端面上；底板焊在朝已有钢构那一端的**截面**上

    限位块 ×2         沿管轴一前一后，中间夹着（与管轴垂直的）已有钢结构
    底板 ×2           仅子项 B/C

子项（按管径）：
    A  DN15~80  （1/2″~3″）  半片 T（H100×100 沿腹板高度中点剖开，总深 50）竖直立柱高 100，无底板
    B  DN100~250（4″~10″）   H100×100×6×8，沿管轴长 150 + 底板 150×150×10
    C  DN300~900（12″~36″）  H150×150×7×10，沿管轴长 200 + 底板 200×200×10

两限位块**内侧面**间距 = 用户输入的**底部已有钢构宽度 W**。
不建：管道本体、已有钢结构/混凝土、弧形垫板、筋板。
编号 ``K1-子项-管径``（注 5：子项 A 省略管径）。
注 2：k = 焊缝腰高 = 管壁厚，最大 6（仅记录，不建模）。

整组写成一个普通单元，清单写入**管道支吊架公共库**，可导出 JSON / Excel。
几何做法复用 ``型钢截面生成器`` 的 H 型钢数据 / 几何与 ``steel_sweep_geometry``；
纯几何 / 数据逻辑在 ``模块/K1限位架/K1限位架_几何.py``。

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
from collections import namedtuple

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'K1限位架')
for _path in (COMMON_DIR, GEOM_DIR, STEEL_DIR, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

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
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    ScrollFrame,
)

import K1限位架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


SUPPORT_TYPE = 'K1-[不保温管的限位架]'
SUPPORT_CODE = 'K1_LIMIT_FRAME'


DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'K1限位架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'K1-[不保温管的限位架]'
CELL_NAME = 'K1_LIMIT_FRAME'

DEFAULT_MATERIAL = geom.DEFAULT_MATERIAL
DEFAULT_DN = 150
DEFAULT_EXISTING_WIDTH_MM = geom.DEFAULT_EXISTING_WIDTH_MM

REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    importlib.invalidate_caches()
    for module in (geom, steel_sweep_geometry, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass
    for name in ('steel_sections.steel_hbeam_data',
                 'steel_sections.steel_hbeam_geometry'):
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


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 1.0e-12:
        return None
    return tuple(component / length for component in vector)


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


# ---------------------------------------------------------------------------
# 管道信息读取
# ---------------------------------------------------------------------------

_PIPE_INFO_DIR = os.path.join(REPO_ROOT, '管道信息查询', '模块', '管道信息')


def _load_pipe_reader():
    name = '管道信息_读取'
    path = os.path.join(_PIPE_INFO_DIR, '管道信息_读取.py')
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    if _PIPE_INFO_DIR not in sys.path:
        sys.path.insert(0, _PIPE_INFO_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipe_reader = _load_pipe_reader()
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())


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
            raise ValueError('所选元素含圆弧或曲线；请选择一条直线段。')


def extract_line_axis(element_handle):
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一根管道或一条直线段。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    if not pieces:
        raise ValueError('未取到有效线段。')
    points = pieces[0]
    return (_point_to_mm(points[0], uor_per_mm),
            _point_to_mm(points[-1], uor_per_mm))


def _project_onto_axis(point_mm, p0_mm, p1_mm):
    d = (p1_mm[0] - p0_mm[0], p1_mm[1] - p0_mm[1], p1_mm[2] - p0_mm[2])
    length2 = _dot(d, d)
    if length2 <= 1.0e-9:
        return p0_mm
    t = _dot((point_mm[0] - p0_mm[0], point_mm[1] - p0_mm[1],
              point_mm[2] - p0_mm[2]), d) / length2
    return (p0_mm[0] + t * d[0], p0_mm[1] + t * d[1], p0_mm[2] + t * d[2])


def _axis_midpoint(p0_mm, p1_mm):
    return ((p0_mm[0] + p1_mm[0]) / 2.0, (p0_mm[1] + p1_mm[1]) / 2.0,
            (p0_mm[2] + p1_mm[2]) / 2.0)


def _horizontal_frame(axis):
    """由管轴方向给出 ``(pipe_dir, perp_dir)``：均为水平单位向量，
    ``pipe_dir × perp_dir = +Z``，管道近似水平才有效。"""
    direction = _normalize(axis)
    if direction is None:
        raise ValueError('管道轴线长度为零，无法定位。')
    horizontal = (direction[0], direction[1], 0.0)
    pipe_dir = _normalize(horizontal)
    if pipe_dir is None:
        raise ValueError('管道接近竖直，K1 限位架仅适用于水平（或微倾）管道。')
    if abs(direction[2]) > math.sin(math.radians(5.0)):
        raise ValueError('管道与水平面夹角超过 5°，K1 限位架仅适用于水平管道。')
    perp_dir = _normalize(_cross((0.0, 0.0, 1.0), pipe_dir))
    return pipe_dir, perp_dir


# ---------------------------------------------------------------------------
# 型钢截面 -> Bentley 曲线 -> 竖直扫掠实体
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
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    start = DPoint3d.From(origin[0], origin[1], origin[2])

    def ten_arg_none():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, None, None, None)

    def ten_arg_scalars():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, 0.0, 1.0, start)

    def six_arg():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False)

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


def _build_sweep_element(geometry, origin, axis_x, axis_y, axis_z, length_mm,
                         uor_per_mm, dgn_model, component_name):
    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    profile = _profile_curve(geometry, frame)
    length = float(length_mm) * uor_per_mm
    end = tuple(origin[index] + axis_z[index] * length for index in range(3))
    path = _line_curve(origin, end)
    body = _sweep_body(profile, path, dgn_model, origin, axis_y)
    return _body_to_element(body, dgn_model, component_name)


def _build_block_element(subitem, side, center_mm, width_mm, od, pipe_dir,
                         uor_per_mm, dgn_model):
    geometry = geom.member_geometry(subitem, uor_per_mm)
    origin_mm, axis_x, axis_y, axis_z, length = geom.member_frame(
        subitem, side, center_mm, width_mm, od, pipe_dir)
    origin = _to_uor(origin_mm, uor_per_mm)
    return _build_sweep_element(
        geometry, origin, axis_x, axis_y, axis_z, length, uor_per_mm,
        dgn_model, '限位块')


_RPoint = namedtuple('_RPoint', 'x y')
_RSegment = namedtuple('_RSegment', 'start end')


class _RectGeometry(object):
    """底板用的矩形截面 (0,0)-(w,0)-(w,h)-(0,h)（已按 UOR 给定尺寸）。"""

    def __init__(self, width, height):
        self.segments = (
            _RSegment(_RPoint(0.0, 0.0), _RPoint(width, 0.0)),
            _RSegment(_RPoint(width, 0.0), _RPoint(width, height)),
            _RSegment(_RPoint(width, height), _RPoint(0.0, height)),
            _RSegment(_RPoint(0.0, height), _RPoint(0.0, 0.0)),
        )
        self.arc_count = 0
        self.line_count = 4


def _build_plate_element(subitem, side, center_mm, width_mm, od, pipe_dir,
                         uor_per_mm, dgn_model):
    box = geom.plate_box(subitem, side, center_mm, width_mm, od, pipe_dir)
    if box is None:
        return None
    perp = _cross((0.0, 0.0, 1.0), pipe_dir)
    origin_mm = (center_mm[0] + box.u0 * pipe_dir[0] + box.v0 * perp[0],
                 center_mm[1] + box.u0 * pipe_dir[1] + box.v0 * perp[1],
                 box.z0)
    origin = _to_uor(origin_mm, uor_per_mm)
    width = (box.u1 - box.u0) * uor_per_mm
    depth = (box.v1 - box.v0) * uor_per_mm
    return _build_sweep_element(
        _RectGeometry(width, depth), origin, pipe_dir, perp, (0.0, 0.0, 1.0),
        (box.z1 - box.z0), uor_per_mm, dgn_model, '底板')


def _succeeded(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


class _K1CellBuilder(object):
    """把限位块、底板子元素一次性写成一个普通单元。"""

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
            raise RuntimeError('K1限位架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法把 K1限位架子元素加入普通单元。')
        self.child_count += 1

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成 K1限位架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法把 K1限位架单元写入活动模型。')
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


def _attach_support_items(cell, result):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('number', ''),
        assembly_spec=result.get('specification', ''),
        components=result.get('bom_items', ()),
    )


# ---------------------------------------------------------------------------
# 构建整组 K1 限位架
# ---------------------------------------------------------------------------


def _build_k1_cell(axis, center_mm, layout, uor_per_mm, dgn_model):
    pipe_dir, _perp = _horizontal_frame(axis)
    width = layout.existing_width_mm
    od = layout.od
    builder = _K1CellBuilder(dgn_model)
    for side in (1, -1):
        block = _build_block_element(
            layout.subitem, side, center_mm, width, od, pipe_dir, uor_per_mm,
            dgn_model)
        if block is None:
            raise RuntimeError('限位块实体创建失败。')
        builder.add(block)
    if layout.plate is not None:
        for side in (1, -1):
            plate = _build_plate_element(
                layout.subitem, side, center_mm, width, od, pipe_dir,
                uor_per_mm, dgn_model)
            if plate is None:
                raise RuntimeError('底板实体创建失败。')
            builder.add(plate)
    builder.build()

    result = {
        'dn': layout.dn,
        'subitem': layout.subitem,
        'number': layout.number,
        'specification': layout.spec,
        'size': layout.size_mm,
        'size_label': layout.size_label,
        'existing_width': width,
        'child_count': builder.child_count,
        'bom_items': geom.component_items(layout),
        'warnings': list(builder.warnings),
    }
    _log('k1 rack built: dn=%d, subitem=%s, W=%.0f, size=%.0f, cells=%d, number=%s'
         % (layout.dn, layout.subitem, width, layout.size_mm,
            builder.child_count, layout.number))
    return builder, result


def replace_k1_rack(axis, center_mm, layout, previous_handle):
    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')
    uor_per_mm = _uor_per_mm(dgn_model)
    builder, result = _build_k1_cell(axis, center_mm, layout, uor_per_mm,
                                     dgn_model)
    new_handle = builder.commit()
    _attach_support_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_k1_rack(axis, center_mm, layout):
    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')
    uor_per_mm = _uor_per_mm(dgn_model)
    builder, result = _build_k1_cell(axis, center_mm, layout, uor_per_mm,
                                     dgn_model)
    cell = builder.commit()
    _attach_support_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', 'K1限位架_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _K1RackDialog(GlassDialog):
    STATE_KEY = 'K1Rack'
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.axis = None
        self.center = None
        self.axis_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False

        self._poll_job = None
        self._regen_deadline = None
        self._pending_dn = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False
        self._pick_note = ''
        self._syncing = False
        self._subitem_pinned = False
        self.pending = []
        self._active_dn = None

        self._dn = tk.StringVar()
        self._subitem = tk.StringVar()
        self._width = tk.StringVar(value='%.0f' % DEFAULT_EXISTING_WIDTH_MM)
        self._material = tk.StringVar(value=DEFAULT_MATERIAL)
        self._keep = tk.BooleanVar(value=True)

        self._od_text = tk.StringVar(value='—')
        self._length_text = tk.StringVar(value='—')
        self._plate_text = tk.StringVar(value='—')
        self._number_text = tk.StringVar(value='—')
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar(value='请点选一根管道或一条直线段；右键退出。')

        self._dn_by_label = {}
        self._subitem_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()
        self.on_options_changed()

        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        _log('panel built file=%s' % os.path.abspath(__file__))

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点选管道或直线 · 在点击处生成 K1 限位架 · 改参数自动重建')
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(form, bg=CARD, height=500)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text='点选管道（自动读管径）或一条普通直线段（用面板 DN）；在点击处'
                 '沿其轴线生成两个限位块（一前一后夹住中间与管轴垂直的已有钢构）：'
                 '子项 A 为竖直半片 T（翼缘夹钢构、管道焊在顶端）；子项 B/C 为'
                 '水平工字钢沿管轴（管道骑在两翼缘端面）+ 两块底板。'
                 '点【确定】保留，点【取消】放弃。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=520,
        ).grid(row=0, column=0, sticky='ew')

        ttk.Label(body, text='管径与子项', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(12, 5))

        selection = tk.Frame(body, bg=CARD)
        selection.grid(row=2, column=0, sticky='ew')
        selection.columnconfigure(0, weight=1, uniform='sel')
        selection.columnconfigure(1, weight=2, uniform='sel')

        dn_cell = tk.Frame(selection, bg=CARD)
        dn_cell.grid(row=0, column=0, sticky='nsew')
        ttk.Label(dn_cell, text='公称直径 DN', style='GlassMuted.TLabel').pack(
            anchor='w')
        dn_labels = []
        for dn in geom.dn_choices():
            label = geom.dn_label(dn)
            dn_labels.append(label)
            self._dn_by_label[label] = dn
        self._dn_combo = ttk.Combobox(
            dn_cell, textvariable=self._dn, state='readonly',
            style='Glass.TCombobox', values=dn_labels)
        self._dn_combo.pack(fill='x', pady=(3, 0))
        self._dn_combo.bind('<<ComboboxSelected>>', self._on_dn_changed)
        self._dn.set(geom.dn_label(DEFAULT_DN))

        subitem_cell = tk.Frame(selection, bg=CARD)
        subitem_cell.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(subitem_cell, text='子项（按 DN 自动，可改）',
                  style='GlassMuted.TLabel').pack(anchor='w')
        subitem_labels = []
        for key in geom.subitem_choices():
            label = geom.subitem_label(key)
            subitem_labels.append(label)
            self._subitem_by_label[label] = key
        self._subitem_combo = ttk.Combobox(
            subitem_cell, textvariable=self._subitem, state='readonly',
            style='Glass.TCombobox', values=subitem_labels)
        self._subitem_combo.pack(fill='x', pady=(3, 0))
        self._subitem_combo.bind('<<ComboboxSelected>>', self._on_subitem_changed)
        self._subitem.set(self._label_for_subitem(
            geom.subitem_for_dn(DEFAULT_DN), subitem_labels))

        ttk.Separator(body, orient='horizontal').grid(
            row=3, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='尺寸', style='Section.TLabel').grid(
            row=4, column=0, sticky='w', pady=(0, 5))

        dimensions = tk.Frame(body, bg=CARD)
        dimensions.grid(row=5, column=0, sticky='ew')
        dimensions.columnconfigure(0, weight=1, uniform='dim')
        dimensions.columnconfigure(1, weight=1, uniform='dim')
        self._od_text_label = self._compact_value(
            dimensions, 0, 0, '管外径 OD', self._od_text, unit='mm',
            note='按 ASME B36.10M')
        self._length_label = self._compact_value(
            dimensions, 0, 1, '主尺寸', self._length_text, unit='mm',
            note='A 立柱高 100 / B 长 150 / C 长 200')
        width_cell = tk.Frame(dimensions, bg=CARD)
        width_cell.grid(row=1, column=0, sticky='nsew', pady=(3, 4))
        ttk.Label(width_cell, text='底部已有钢构宽度 W',
                  style='GlassMuted.TLabel').pack(anchor='w')
        self._width_entry = tk.Entry(
            width_cell, textvariable=self._width, font=UI_FONT, bg=CARD, fg=INK,
            relief='flat', highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BORDER)
        self._width_entry.pack(fill='x', pady=(3, 0))
        self._compact_value(
            dimensions, 1, 1, '底板', self._plate_text, note='B/C 子项')

        ttk.Separator(body, orient='horizontal').grid(
            row=6, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='编号与材料', style='Section.TLabel').grid(
            row=7, column=0, sticky='w', pady=(0, 5))

        options = tk.Frame(body, bg=CARD)
        options.grid(row=8, column=0, sticky='ew')
        options.columnconfigure(0, weight=1, uniform='opt')
        options.columnconfigure(1, weight=1, uniform='opt')
        self._compact_value(options, 0, 0, '编号', self._number_text,
                            note='K1-子项-管径（A 省管径）')
        material_cell = tk.Frame(options, bg=CARD)
        material_cell.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        ttk.Label(material_cell, text='材料', style='GlassMuted.TLabel').pack(
            anchor='w')
        self._material_entry = tk.Entry(
            material_cell, textvariable=self._material, font=UI_FONT, bg=CARD,
            fg=INK, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER)
        self._material_entry.pack(fill='x', pady=(3, 0))

        self._width.trace_add('write', self.on_text_changed)
        self._material.trace_add('write', self.on_text_changed)

        preview = tk.Frame(body, bg=CARD_SOFT, highlightbackground=BORDER,
                           highlightthickness=1)
        preview.grid(row=10, column=0, sticky='ew', pady=(8, 0))
        tk.Label(preview, textvariable=self._preview_info, bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=500).pack(fill='x', padx=10, pady=7)

        chip = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                        highlightthickness=1)
        chip.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self._status_label = tk.Label(
            chip, textvariable=self._status, bg=CARD_SOFT, fg='#1f5f99',
            font=UI_FONT_SMALL, wraplength=520, justify='left', anchor='w')
        self._status_label.pack(fill='x', padx=10, pady=7)

        creation_options = tk.Frame(form, bg=CARD)
        creation_options.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self._keep_check = tk.Checkbutton(
            creation_options, text='创建后保留所选元素', variable=self._keep,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.pack(side='left')

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

    def _compact_value(self, parent, row, column, name, textvariable,
                       unit='', note='', columnspan=1):
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
            tk.Label(value_line, text=' %s' % unit, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w').pack(side='left')
        if note:
            tk.Label(cell, text=note, bg=CARD, fg=MUTED, font=UI_FONT_SMALL,
                     anchor='w', justify='left').pack(anchor='w')
        return cell

    # -- 状态 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        dn = state.get('dn')
        if dn in self._dn_by_label.values():
            self._dn.set(geom.dn_label(dn))
        if isinstance(state.get('subitem_pinned'), bool):
            self._subitem_pinned = state.get('subitem_pinned')
        subitem = state.get('subitem')
        if self._subitem_pinned and subitem in self._subitem_by_label.values():
            label = self._label_for_subitem(subitem)
            if label:
                self._subitem.set(label)
        width = state.get('width')
        if isinstance(width, str) and width.strip():
            self._width.set(width)
        material = state.get('material')
        if material:
            self._material.set(str(material))
        if not self._subitem_pinned:
            self._sync_subitem_to_dn()

    def persist_state(self, state):
        state['dn'] = self._panel_dn()
        state['subitem'] = self._panel_subitem()
        state['subitem_pinned'] = bool(self._subitem_pinned)
        state['width'] = self._width.get()
        state['material'] = self._material.get()
        return state

    def _label_for_subitem(self, key, labels=None):
        labels = labels if labels is not None else list(self._subitem_by_label)
        for label in labels:
            if self._subitem_by_label.get(label) == key:
                return label
        return labels[0] if labels else ''

    def _panel_dn(self):
        return self._dn_by_label.get(self._dn.get(), DEFAULT_DN)

    def _panel_subitem(self):
        return self._subitem_by_label.get(self._subitem.get(), None)

    def _effective_dn(self):
        return self._active_dn if self._active_dn is not None else self._panel_dn()

    def _existing_width(self):
        try:
            value = float((self._width.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('底部已有钢构宽度 W 必须是数字（mm）。')
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError('底部已有钢构宽度 W 必须是正数（mm）。')
        return value

    def current_layout(self):
        subitem = self._panel_subitem() if self._subitem_pinned else None
        return geom.build_layout(self._effective_dn(), subitem,
                                 self._existing_width(), self._material.get())

    def refresh_spec(self):
        try:
            layout = self.current_layout()
        except (KeyError, ValueError) as error:
            self._od_text.set('—')
            self._length_text.set('—')
            self._plate_text.set('—')
            self._number_text.set(str(error))
            return
        self._od_text.set('%.1f' % layout.od)
        self._length_text.set('%.0f' % layout.size_mm)
        self._plate_text.set(
            '%.0f×%.0f×%.0f ×2' % layout.plate if layout.plate else '无')
        self._number_text.set(layout.number)

    def set_status(self, message, is_error=False, flush=True):
        self._status.set(message)
        try:
            self._status_label.configure(fg='#b23b3b' if is_error else '#1f5f99')
        except tk.TclError:
            pass
        if flush:
            try:
                self.update_idletasks()
            except tk.TclError:
                pass

    def set_result(self, result):
        try:
            text = geom.describe(self.current_layout())
        except (KeyError, ValueError):
            text = '预览：—'
        self._preview_info.set(text)

    # -- 事件 --------------------------------------------------------------

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _on_dn_changed(self, event=None):
        if self._syncing:
            return
        self._active_dn = None
        self._subitem_pinned = False
        self._sync_subitem_to_dn()
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _on_subitem_changed(self, event=None):
        if self._syncing:
            return
        self._subitem_pinned = True
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def _sync_subitem_to_dn(self):
        label = self._label_for_subitem(geom.subitem_for_dn(self._panel_dn()))
        if not label:
            return
        self._syncing = True
        try:
            self._subitem.set(label)
        finally:
            self._syncing = False

    def on_text_changed(self, *_args):
        if self._syncing:
            return
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay_ms):
        self._cancel_pending_regeneration()
        if self.axis is None or self.center is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    def note_hover(self, axis, center, handle, note=''):
        self.axis = axis
        self.center = center
        self.axis_handle = handle
        self._pick_note = note

    def queue_pick(self, element_id, click_uor):
        self.pending.append((element_id, click_uor))

    def _run_pending(self):
        pending, self.pending = self.pending, []
        for element_id, click_uor in pending:
            self._process(element_id, click_uor)

    def _process(self, element_id, click_uor):
        try:
            handle = pipe_reader.element_handle_by_id(element_id)
        except Exception as error:
            _log_exception('open element failed')
            self.set_status('打开元素失败：%s' % error, True)
            return
        if handle is None:
            self.set_status('元素 ID %s 已失效（可能已被删除）。' % element_id,
                            True)
            return
        try:
            placement = pipe_reader.pipe_placement_info(handle, 'auto')
        except Exception as error:
            _log_exception('read pipe info failed')
            self.set_status('读取管道信息失败：%s' % error, True)
            return

        start = placement.get('start_mm')
        end = placement.get('end_mm')
        axis = placement.get('axis')
        if not start or not end or axis is None:
            try:
                start, end = extract_line_axis(handle)
                axis = _normalize((end[0] - start[0], end[1] - start[1],
                                   end[2] - start[2]))
            except Exception as error:
                self.set_status('该元素没有可用的轴线，无法定位：%s' % error,
                                True)
                return

        is_pipe = bool((((placement.get('snapshot') or {}).get('ec') or {})
                        .get('found')))
        note = ''
        if is_pipe:
            nominal = placement.get('nominal_diameter_mm')
            matched = geom.match_dn(nominal) if nominal is not None else None
            if matched is not None:
                self._active_dn = matched
                self._pending_dn = matched
                # 按管径自动选子项：点选管道时清除手动「钉住」，保证跟随管径。
                self._subitem_pinned = False
                note = '按管道：公称直径 %.1f mm → DN%d。' % (nominal, matched)
            else:
                note = '管道公称直径 %s 未匹配，DN 用面板值 %d。' % (
                    '未知' if nominal is None else '%.1f mm' % nominal,
                    self._panel_dn())
        else:
            note = '按面板：DN%d。' % self._panel_dn()

        if click_uor is not None:
            uor_per_mm = _uor_per_mm()
            click_mm = tuple(value / uor_per_mm for value in click_uor)
            center = _project_onto_axis(click_mm, start, end)
        else:
            center = placement.get('center_mm') or _axis_midpoint(start, end)

        self.note_hover(axis, center, handle, note)
        self.regenerate()

    # -- UI 刷新 -----------------------------------------------------------

    def _start_poll(self):
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
            if self._pending_dn is not None:
                dn = self._pending_dn
                self._pending_dn = None
                self._syncing = True
                try:
                    self._dn.set(geom.dn_label(dn))
                    if not self._subitem_pinned:
                        label = self._label_for_subitem(geom.subitem_for_dn(dn))
                        if label:
                            self._subitem.set(label)
                finally:
                    self._syncing = False
                self.refresh_spec()
            if self._pending_result is not None:
                result = self._pending_result
                message = self._pending_message or ''
                self._pending_result = None
                self._pending_message = None
                self._pending_is_error = False
                self.refresh_spec()
                self.set_result(result)
                self.set_status(message)
            elif self._pending_message is not None:
                message = self._pending_message
                is_error = self._pending_is_error
                self._pending_message = None
                self._pending_is_error = False
                self.set_status(message, is_error)
        except tk.TclError:
            pass

    # -- 预览 --------------------------------------------------------------

    def regenerate(self):
        self._cancel_pending_regeneration()
        if self.axis is None or self.center is None:
            return None
        try:
            layout = self.current_layout()
        except (KeyError, ValueError) as error:
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None
        try:
            handle, result, deleted = replace_k1_rack(
                self.axis, self.center, layout, self.preview_handle)
        except Exception as error:
            message = 'K1限位架生成失败：%s' % error
            if isinstance(error, ValueError):
                _log('preview rejected: %s' % error)
            else:
                _log_exception('preview failed')
            self._pending_message = message
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            return None

        self.preview_handle = handle
        self.preview_result = result
        message = ('预览已更新：编号 %s，子项 %s，%s %.0f mm，'
                   '两限位块间距 %.0f mm，单元含 %d 个子元素，%s。'
                   '改参数会自动重建；点【确定】保留，点【取消】放弃。'
                   % (result['number'], result['subitem'], result['size_label'],
                      result['size'], result['existing_width'],
                      result['child_count'],
                      '已替换上一版预览' if deleted else '已生成'))
        if self._pick_note:
            message = self._pick_note + message
            self._pick_note = ''
        self._pending_result = result
        self._pending_message = message
        self._pending_is_error = False
        try:
            NotificationManager.OutputPrompt(message)
        except Exception:
            pass
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def delete_source_line(self):
        handle = self.axis_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                return True
        except Exception:
            _log_exception('delete source element failed')
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

    def request_cancel(self):
        self._cancel_requested = True

    def request_shutdown(self):
        self._shutdown_requested = True

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        if self.preview_handle is not None and not self._keep.get():
            self.delete_source_line()
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
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
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    def run_dialog_loop(self):
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.finish_tool()
                break
            if self._cancel_requested:
                self._cancel_requested = False
                self.cancel_tool()
                break
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception:
                _log_exception('PythonMainLoop failed')
                break
            self._run_pending()


# ---------------------------------------------------------------------------
# 交互工具
# ---------------------------------------------------------------------------


class K1RackTool(DgnElementSetTool):
    """点选**管道或直线段**，在点击处沿其轴线放置 K1 限位架。"""

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('K1RackTool')

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
            '请点选一根管道或一条直线段：在点击处生成 K1 限位架。右键放弃。')
        if self.panel is not None:
            self.panel.set_status('请点选一根管道或一条直线段；右键退出。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = pipe_reader.read_element_id(handle)
            return self._located_id is not None
        except Exception:
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            self.panel.set_status(
                '没有定位到元素：请把光标放在管道或直线上再点击。', True)
            return True
        try:
            point = event.GetPoint()
            click_uor = (point.x, point.y, point.z)
        except Exception:
            click_uor = None
        self.panel.queue_pick(element_id, click_uor)
        return True

    def _OnResetButton(self, event):
        settings = self.panel
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnRestartTool(self):
        panel = self.panel
        self.panel = None
        K1RackTool.InstallNewInstance(self.GetToolId(), panel, False)

    def _OnCleanup(self):
        settings = self.panel
        if settings is None:
            return
        self.panel = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_ui_loop=True):
        settings = panel if panel is not None else _K1RackDialog()
        tool = K1RackTool(tool_id, settings)
        tool.InstallTool()
        if start_ui_loop:
            settings.run_dialog_loop()
        return tool


_active_settings = None


def show_k1_rack_dialog():
    global _active_settings
    if _active_settings is not None:
        try:
            if _active_settings.winfo_exists():
                _active_settings.lift()
                return None
        except tk.TclError:
            pass
    settings = _K1RackDialog()
    _active_settings = settings
    try:
        return K1RackTool.InstallNewInstance(0, settings, True)
    finally:
        _active_settings = None


def export_k1_rack_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYK1RACK PLACE / PYK1RACK EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, 'K1限位架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenK1Rack():
    PyMain()


def ExportK1RackBom():
    export_k1_rack_bom()


def PyMain():
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_k1_rack_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('k1 rack tool start failed')
        print('K1限位架插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'K1限位架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
