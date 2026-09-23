# -*- coding: utf-8 -*-
"""立管的耳轴（F6/F7 · DN50~DN1200）—— 选一条竖直主管，在点击处生成耳轴。

运行后**点选一条竖直线**（立管轴线），在**点击位置**（该点投影到轴线上，即耳轴
的轴向标高）按面板选择的类型 / 主管管径 / 耳轴管径 / 材料代码 / L / 端板类型 /
方位角 / 补强板厚度生成：

* **F6** 单耳轴 / **F7** 双耳轴（180° 对称）；
* 耳轴为**空心管**，外径查 DN 表、壁厚默认 **STD**（可覆盖），内端到主管外壁并
  用主管外圆柱布尔减切出**弧形鞍口**；
* **端板**：圆板，直径 = 耳轴外径 + 12；厚度按端板类型（A=6 / B=表 2 / C=无）；
* **补强板**：贴主管外壁、围绕耳轴根部的**弯曲圆形钢板**，外径 = 主管外径 + 2W，
  内孔 = 耳轴外径，厚度默认 5 mm（可改、可关闭）；
* **方位角**：``方向 = (sinθ, cosθ, 0)``（0° = 世界 +Y，顺时针）。

主管来源：点选**管道**自动读公称直径；点选**普通直线**用面板管径；与竖直方向
夹角超过 ``±5°`` 时拒绝。可连续点选，右键退出。

本插件遵循 管道支吊架 公共 ItemType 契约，写入库 ``PipeSupportComponents``，
``SupportType='立管的耳轴'``。

EC 读取不在工具回调里做：点选只把「元素 ID + 点击点」入队，真正的读取与建模由
面板主循环在 ``PyCadInputQueue.PythonMainLoop()`` 返回之后执行。
"""

from __future__ import division

import importlib
import importlib.util
import math
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


# ---------------------------------------------------------------------------
# 路径与依赖
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '立管的耳轴')
PIPE_INFO_DIR = os.path.join(REPO_ROOT, '管道信息查询', '模块', '管道信息')

for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR, PIPE_INFO_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _load_pipe_reader():
    name = '管道信息_读取'
    path = os.path.join(PIPE_INFO_DIR, '管道信息_读取.py')
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
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
    SlimScrollbar,
)

import 立管的耳轴_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

UI_TITLE = 'F6_F7-[立管的耳轴]'
SUPPORT_TYPE = 'F6_F7-[立管的耳轴]'
SUPPORT_CODE = 'VP_TRUNNION'
_CELL_NAME = 'VP_TRUNNION'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '立管的耳轴_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

_THROUGH_MARGIN_MM = 5.0
# 耳轴外径与主管外径相等时两圆柱相切、布尔减会失败；刀具体放大此值避让。
_SADDLE_CLEARANCE_MM = 0.5


def _log(message):
    try:
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (stamp, message))
            stream.flush()
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


# ---------------------------------------------------------------------------
# 向量 / 坐标架
# ---------------------------------------------------------------------------


def _uor_per_mm(dgn_model=None):
    model = dgn_model or ISessionMgr.GetActiveDgnModel()
    return model.GetModelInfo().GetUorPerMeter() / 1000.0


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normalize(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1.0e-12:
        raise ValueError('方向向量长度为零。')
    return (v[0] / length, v[1] / length, v[2] / length)


def _is_vertical(axis, tolerance_deg=geom.VERTICAL_TOLERANCE_DEG):
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length <= 1.0e-12:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(axis[2]) / length)))
    return angle <= float(tolerance_deg)


def _frame(axis, azimuth_deg):
    """本地方位系 ``(ex, ey, ez)``：ez=管轴（朝上），ex=方位角方向（水平）。"""
    ez = _normalize(axis)
    if ez[2] < 0.0:
        ez = (-ez[0], -ez[1], -ez[2])
    angle = math.radians(float(azimuth_deg))
    ref = (math.sin(angle), math.cos(angle), 0.0)  # 0° = +Y，顺时针
    projected = (ref[0] - _dot(ref, ez) * ez[0],
                 ref[1] - _dot(ref, ez) * ez[1],
                 ref[2] - _dot(ref, ez) * ez[2])
    ex = _normalize(projected)
    ey = _cross(ez, ex)
    return ex, ey, ez


def _neg(v):
    return (-v[0], -v[1], -v[2])


def _check(status, operation):
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        code = int(status)
    except (TypeError, ValueError):
        raise RuntimeError('%s未返回有效状态码：%r' % (operation, status))
    if code != 0:
        raise RuntimeError('%s失败，状态：%s' % (operation, status))


def _ptr_array(*bodies):
    array = ISolidKernelEntityPtrArray()
    for body in bodies:
        array.append(body)
    return array


# ---------------------------------------------------------------------------
# 基础实体
# ---------------------------------------------------------------------------


def _cylinder_between(model, start, end, radius, uor):
    detail = DgnConeDetail(start, end, radius * uor, radius * uor, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    _check(DraftingElementSchema.ToElement(element, primitive, None, model),
           '创建圆柱')
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    _check(status, '圆柱转内核体')
    return body


def _assembly_element(model, bodies):
    cell = EditElementHandle()
    NormalCellHeaderHandler.CreateOrphanCellElement(cell, _CELL_NAME, True, model)
    for name, body in bodies:
        child = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(child, body, None, model),
               name + '转模型元素')
        _check(NormalCellHeaderHandler.AddChildElement(cell, child),
               name + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成耳轴单元')
    _check(cell.AddToModel(), '写入耳轴单元')
    return cell


def _make_mappers(center_mm, ex, ey, ez, uor):
    def point(x, y, z):
        return DPoint3d(
            (center_mm[0] + x * ex[0] + y * ey[0] + z * ez[0]) * uor,
            (center_mm[1] + x * ex[1] + y * ey[1] + z * ez[1]) * uor,
            (center_mm[2] + x * ex[2] + y * ey[2] + z * ez[2]) * uor)

    def direction(x, y, z):
        return DVec3d(
            (x * ex[0] + y * ey[0] + z * ez[0]) * uor,
            (x * ex[1] + y * ey[1] + z * ez[1]) * uor,
            (x * ex[2] + y * ey[2] + z * ez[2]) * uor)

    return point, direction


def _box_body(model, point, direction, x0, x1, y0, y1, z0, z1):
    points = DPoint3dArray()
    for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
        points.append(point(x0, y, z))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建长方体截面')
    _check(profile.AddToModel(), '创建长方体临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '长方体截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除长方体临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(x1 - x0, 0.0, 0.0)),
           '拉伸长方体')
    return body


# ---------------------------------------------------------------------------
# 建模：单根耳轴（空心管 + 端板 + 鞍口）
# ---------------------------------------------------------------------------


def _build_trunnion(model, point, uor, layout):
    """单根耳轴：空心管 + 端板，内端用主管外圆柱切出弧形鞍口。"""
    od = layout.trunnion_od
    inner_radius = geom.trunnion_inner_radius(layout)
    length = layout.length_mm
    end_t = layout.end_plate_thickness_mm

    # 外圆柱（沿本地 +X，从管轴处到端板外端面 L）。
    outer = _cylinder_between(
        model, point(-_THROUGH_MARGIN_MM, 0.0, 0.0), point(length, 0.0, 0.0),
        od / 2.0, uor)
    # 内孔（空心管），两端各留余量。
    inner = _cylinder_between(
        model, point(-_THROUGH_MARGIN_MM * 2.0, 0.0, 0.0),
        point(length + _THROUGH_MARGIN_MM, 0.0, 0.0), inner_radius, uor)
    _check(SolidUtil.Modify.BooleanSubtract(outer, _ptr_array(inner)), '耳轴空心')

    if end_t > 0.0:
        plate = _cylinder_between(
            model, point(length - end_t, 0.0, 0.0), point(length, 0.0, 0.0),
            layout.end_plate_dia_mm / 2.0, uor)
        _check(SolidUtil.Modify.BooleanUnion(outer, _ptr_array(plate)), '端板与耳轴并')

    # 主管外圆柱（沿本地 Z）布尔减，切出弧形鞍口。
    # 耳轴外径与主管外径相等/相近时两圆柱相切，布尔减会失败；此时刀具体略放大。
    pipe_radius = layout.pipe_od / 2.0
    if layout.trunnion_od >= layout.pipe_od - 1.0:
        pipe_radius += _SADDLE_CLEARANCE_MM
    reach = length + layout.pipe_od
    pipe = _cylinder_between(
        model, point(0.0, 0.0, -reach), point(0.0, 0.0, reach),
        pipe_radius, uor)
    _check(SolidUtil.Modify.BooleanSubtract(outer, _ptr_array(pipe)), '耳轴鞍口')
    return outer


# ---------------------------------------------------------------------------
# 建模：补强板（贴主管外壁的弯曲圆形钢板）
# ---------------------------------------------------------------------------


def _build_pad(model, point, direction, uor, layout):
    """补强板：贴主管外壁、围绕耳轴根部的弯曲圆形钢板。

    按用户口径：沿耳轴轴拉伸一个直径 = **耳轴外径 + 2W** 的圆柱（伸到管道轴线），
    与绕主管轴、由 ``R_pipe`` 到 ``R_pipe + t`` 的**管壁圆环**求交，只保留 5 mm
    厚的弯曲板。内核无布尔交，用恒等式 ``A∩B = A−(A−B)`` 以减法实现。

    注 7：当补强板越过主管中心线（即绕管超过半圈）时，用「过管轴、垂直于耳轴」
    的平面（本地 ``x = 0``）把越过的部分切掉，使其与主管中心线平齐。
    """
    r_pipe = layout.pipe_od / 2.0
    t_pad = layout.pad_thickness_mm
    r_disc = layout.trunnion_od / 2.0 + layout.pad_w_mm  # = 补强板外半径
    half = r_disc + _THROUGH_MARGIN_MM                   # 壳沿管轴的半长

    # 管壁圆环（绕主管轴）：内径 = 主管外径，外径 = 主管外径 + 2t。
    shell_outer = _cylinder_between(
        model, point(0.0, 0.0, -half), point(0.0, 0.0, half),
        r_pipe + t_pad, uor)
    shell_inner = _cylinder_between(
        model, point(0.0, 0.0, -half - _THROUGH_MARGIN_MM),
        point(0.0, 0.0, half + _THROUGH_MARGIN_MM), r_pipe, uor)
    _check(SolidUtil.Modify.BooleanSubtract(
        shell_outer, _ptr_array(shell_inner)), '补强板圆环')

    # 沿耳轴轴（本地 +X）的大圆柱，直径 = 耳轴外径 + 2W，伸到管道轴线外。
    disc_reach = r_pipe + t_pad + _THROUGH_MARGIN_MM

    def make_disc():
        return _cylinder_between(
            model, point(0.0, 0.0, 0.0), point(disc_reach, 0.0, 0.0),
            r_disc, uor)

    disc_a = make_disc()
    disc_b = make_disc()
    _check(SolidUtil.Modify.BooleanSubtract(
        disc_b, _ptr_array(shell_outer)), '补强板求交-补')
    _check(SolidUtil.Modify.BooleanSubtract(
        disc_a, _ptr_array(disc_b)), '补强板求交')

    # 注 7：切掉越过主管中心线的部分（保留本地 x >= 0 的半边）。
    reach = r_disc + r_pipe + _THROUGH_MARGIN_MM
    half_space = _box_body(model, point, direction,
                           -reach, 0.0, -reach, reach, -reach, reach)
    _check(SolidUtil.Modify.BooleanSubtract(disc_a, _ptr_array(half_space)),
           '补强板中心线齐平')
    return disc_a


def build_trunnion_assembly(layout, base_point_mm, axis):
    """按轴线与耳轴标高构建整组耳轴单元，返回模型单元句柄。"""
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    uor = _uor_per_mm(model)
    center = (float(base_point_mm[0]), float(base_point_mm[1]),
              float(base_point_mm[2]))

    bodies = []
    for index, azimuth in enumerate(geom.trunnion_azimuths(layout), start=1):
        ex, ey, ez = _frame(axis, azimuth)
        point, direction = _make_mappers(center, ex, ey, ez, uor)
        bodies.append(('耳轴%d' % index, _build_trunnion(model, point, uor, layout)))
        if layout.has_pad:
            bodies.append(('补强板%d' % index,
                           _build_pad(model, point, direction, uor, layout)))
    return _assembly_element(model, bodies)


# ---------------------------------------------------------------------------
# 公共库
# ---------------------------------------------------------------------------


def _attach_support_items(cell, layout):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=layout.number,
        assembly_spec=geom.specification(layout),
        components=geom.component_items(layout),
    )


# ---------------------------------------------------------------------------
# 点选 → 生成
# ---------------------------------------------------------------------------


def _is_pipe_placement(placement):
    snapshot = placement.get('snapshot') or {}
    return bool((snapshot.get('ec') or {}).get('found'))


def build_on_pick(placement, click_mm, params):
    """按所选元素（管道或直线）与点击点生成整组耳轴，返回 ``(单元, 提示)``。"""
    start = placement.get('start_mm')
    end = placement.get('end_mm')
    axis = placement.get('axis')
    if not start or not end or axis is None:
        raise ValueError('该元素没有可用的轴线，无法定位耳轴；'
                         '请点选立管（管道）或一条竖直线。')
    if not _is_vertical(axis):
        raise ValueError('请选择一条竖直线（立管轴线）；'
                         '与竖直方向夹角须在 ±%.0f° 以内。'
                         % geom.VERTICAL_TOLERANCE_DEG)

    is_pipe = _is_pipe_placement(placement)
    pipe_dn = params['pipe_dn']
    if is_pipe:
        nominal = placement.get('nominal_diameter_mm')
        matched = geom.match_dn(nominal)
        if matched is None:
            raise ValueError('所选管道公称直径 %s 不在 DN50~DN1200 范围内。'
                             % ('未知' if nominal is None else '%.1f mm' % nominal))
        pipe_dn = matched

    material_code = params['material_code']
    pad_thickness = params['pad_thickness_mm']
    if not params.get('build_pad', True):
        # 用户不勾选「建补强板」：整段补强板逻辑跳过。
        pad_thickness = 0.0
    if geom.pad_required(material_code) and (not pad_thickness or pad_thickness <= 0.0):
        pad_thickness = geom.DEFAULT_PAD_THICKNESS_MM

    layout = geom.build_layout(
        type_code=params['type_code'],
        pipe_dn=pipe_dn,
        trunnion_dn=params['trunnion_dn'],
        material_code=material_code,
        length_mm=params['length_mm'],
        end_type=params['end_type'],
        azimuth_deg=params['azimuth_deg'],
        pad_thickness_mm=pad_thickness,
        trunnion_wall_override_mm=params['trunnion_wall_mm'],
    )

    if click_mm is not None:
        base_point = pipe_reader.project_onto_axis(click_mm, start, end)
    else:
        base_point = placement.get('center_mm') or start

    cell = build_trunnion_assembly(layout, base_point, axis)
    attached = _attach_support_items(cell, layout)

    parts = ['已生成：%s' % geom.describe(layout)]
    parts.append('已写入统计 %d 条。' % attached)
    if geom.pad_required(material_code) and not params.get('build_pad', True):
        parts.append('（材料代码 S1 按注 12 强制建补强板。）')
    if not is_pipe:
        parts.append('（按所选直线作为立管轴线，管径用面板 DN%d。）' % pipe_dn)
    else:
        parts.append('（管道公称直径已自动匹配 DN%d。）' % pipe_dn)
    return cell, ''.join(parts)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _VpTrunnionPanel(GlassDialog):
    """参数选择 + 生成记录 + 状态；同时驱动点选主循环。"""

    STATE_KEY = 'VpTrunnion'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        self._type = tk.StringVar()
        self._pipe_dn = tk.StringVar()
        self._trunnion_dn = tk.StringVar()
        self._material = tk.StringVar()
        self._length = tk.StringVar(value=str(int(geom.DEFAULT_L)))
        self._end_type = tk.StringVar()
        self._azimuth = tk.StringVar(value='0')
        self._pad_thickness = tk.StringVar(value=str(geom.DEFAULT_PAD_THICKNESS_MM))
        self._wall = tk.StringVar(value='')
        self._build_pad = tk.BooleanVar(value=True)
        self._type_by_label = {}
        self._pipe_dn_by_label = {}
        self._trunnion_dn_by_label = {}
        self._material_by_label = {}
        self._end_type_by_label = {}
        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.close_panel)
        try:
            self.minsize(450, 800)
        except tk.TclError:
            pass
        _log('panel built file=%s' % os.path.abspath(__file__))

    def _combo_row(self, form, row, label, variable, by_label, width=26):
        frame = tk.Frame(form, bg=CARD)
        frame.grid(row=row, column=0, sticky='w', pady=(6, 0))
        tk.Label(frame, text=label, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        combo = ttk.Combobox(frame, textvariable=variable, state='readonly',
                             width=width, style='Glass.TCombobox')
        combo.pack(side='left', padx=(10, 0))
        return combo

    def _entry_row(self, form, row, label, variable, width=8, hint=''):
        frame = tk.Frame(form, bg=CARD)
        frame.grid(row=row, column=0, sticky='w', pady=(6, 0))
        tk.Label(frame, text=label, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        entry = tk.Entry(
            frame, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', padx=(10, 0), ipady=3)
        if hint:
            tk.Label(frame, text=hint, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side='left', padx=(6, 0))
        return entry

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点选一条竖直主管（立管轴线），在点击处生成 F6/F7 耳轴；右键退出')
        form.columnconfigure(0, weight=1)

        hint_frame, hint_text = self._text_field(form, height=3)
        hint_frame.grid(row=0, column=0, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一条竖直主管（管道或直线）：整组耳轴在点击处生成，'
            '点击点在轴线上的投影即耳轴标高。选中管道自动读公称直径；选中普通'
            '直线用下面的主管管径。可连续点选，右键退出。'))

        ttk.Label(form, text='1. 类型 / 管径 / 材料', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(6, 2))

        for code, label in geom.type_choices():
            self._type_by_label[label] = code
        self._type_combo = self._combo_row(
            form, 2, '类型', self._type, self._type_by_label)
        self._type_combo.configure(values=list(self._type_by_label))
        self._type_combo.bind('<<ComboboxSelected>>', self._on_type_changed)

        for dn, label in geom.dn_choices():
            self._pipe_dn_by_label[label] = dn
        self._pipe_combo = self._combo_row(
            form, 3, '主管管径', self._pipe_dn, self._pipe_dn_by_label)
        self._pipe_combo.configure(values=list(self._pipe_dn_by_label))
        self._pipe_combo.bind('<<ComboboxSelected>>', self._on_pipe_dn_changed)

        self._trunnion_combo = self._combo_row(
            form, 4, '耳轴管径', self._trunnion_dn, self._trunnion_dn_by_label)
        self._trunnion_combo.bind('<<ComboboxSelected>>', self._on_trunnion_changed)

        for code, label in geom.material_choices():
            self._material_by_label[label] = code
        self._material_combo = self._combo_row(
            form, 5, '材料代码', self._material, self._material_by_label)
        self._material_combo.configure(values=list(self._material_by_label))

        self._wall_entry = self._entry_row(
            form, 6, '耳轴壁厚', self._wall, width=8,
            hint='mm（空 = 默认 STD，注 3）')

        ttk.Separator(form, orient='horizontal').grid(
            row=7, column=0, sticky='ew', pady=10)

        ttk.Label(form, text='2. 尺寸 / 方位', style='Section.TLabel').grid(
            row=8, column=0, sticky='w', pady=(0, 2))

        self._length_entry = self._entry_row(
            form, 9, 'L（轴→端板外端面）', self._length, width=8, hint='mm')
        for code, label in geom.end_type_choices():
            self._end_type_by_label[label] = code
        self._end_combo = self._combo_row(
            form, 10, '端板类型', self._end_type, self._end_type_by_label)
        self._end_combo.configure(values=list(self._end_type_by_label))
        self._azimuth_entry = self._entry_row(
            form, 11, '方位角', self._azimuth, width=8,
            hint='°（0°=+Y，顺时针；F7 只标较小值）')

        pad_row = tk.Frame(form, bg=CARD)
        pad_row.grid(row=12, column=0, sticky='w', pady=(6, 0))
        self._pad_check = tk.Checkbutton(
            pad_row, text='建补强板', variable=self._build_pad, bg=CARD, fg=INK,
            activebackground=CARD, selectcolor=CARD, font=UI_FONT_BOLD,
            highlightthickness=0, bd=0, command=self._on_build_pad_changed)
        self._pad_check.pack(side='left')
        self._pad_entry = tk.Entry(
            pad_row, textvariable=self._pad_thickness, width=8, font=UI_FONT,
            fg=INK, bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        self._pad_entry.pack(side='left', padx=(10, 0), ipady=3)
        tk.Label(pad_row, text='mm 厚（不勾选 = 不建；S1 强制建）',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(
                     side='left', padx=(6, 0))

        ttk.Label(form, text='生成记录', style='Section.TLabel').grid(
            row=13, column=0, sticky='w', pady=(8, 2))
        log_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.grid(row=14, column=0, sticky='nsew')
        form.rowconfigure(14, weight=1)
        self._log_view = tk.Text(
            log_frame, height=11, width=38, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=6, cursor='arrow')
        log_bar = SlimScrollbar(log_frame, command=self._log_view.yview,
                                trough=CARD_SOFT)
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side='left', fill='both', expand=True)
        log_bar.pack(side='right', fill='y')
        self._log_view.configure(state='disabled')

        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=15, column=0, sticky='ew', pady=(6, 0))
        self._set_text(self._status_text, '请在模型中点选一条竖直主管。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=16, column=0, sticky='ew', pady=(8, 0))
        self.clear_button = RoundButton(
            buttons, '清空记录', self.clear_log, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button = RoundButton(
            buttons, '退出', self.close_panel, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button.pack(side='right')
        self.clear_button.pack(side='right', padx=(0, 8))

    def _text_field(self, parent, height=3):
        frame = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
        text = tk.Text(
            frame, height=height, width=38, wrap='word', font=UI_FONT_SMALL,
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

    # -- 联动 --------------------------------------------------------------

    def _on_type_changed(self, event=None):
        pass

    def _on_build_pad_changed(self):
        """不勾选「建补强板」时灰显并禁用补强板厚度输入。"""
        try:
            self._pad_entry.configure(
                state='normal' if self._build_pad.get() else 'disabled')
        except tk.TclError:
            pass

    def _on_pipe_dn_changed(self, event=None):
        """主管管径变化时刷新耳轴候选（表 1）。"""
        pipe_dn = self.current_pipe_dn()
        try:
            candidates = geom.trunnion_candidates(pipe_dn)
        except ValueError:
            candidates = ()
        self._trunnion_dn_by_label = {}
        labels = []
        for dn in candidates:
            label = geom.dn_label(dn)
            labels.append(label)
            self._trunnion_dn_by_label[label] = dn
        self._trunnion_combo.configure(values=labels)
        if labels:
            self._trunnion_dn.set(labels[-1])
        else:
            self._trunnion_dn.set('')

    def _on_trunnion_changed(self, event=None):
        pass

    # -- 面板输入 ----------------------------------------------------------

    def restore_state(self):
        state = self.ui_state

        def pick(by_label, key, fallback_label):
            for label, value in by_label.items():
                if value == key:
                    return label
            return fallback_label

        self._type.set(pick(self._type_by_label,
                            state.get('type_code', geom.DEFAULT_TYPE_CODE),
                            self._first(self._type_by_label)))
        self._pipe_dn.set(pick(self._pipe_dn_by_label,
                               state.get('pipe_dn', geom.DEFAULT_PIPE_DN),
                               self._first(self._pipe_dn_by_label)))
        self._on_pipe_dn_changed()
        trunnion = state.get('trunnion_dn')
        if trunnion is not None:
            self._trunnion_dn.set(pick(self._trunnion_dn_by_label, trunnion,
                                       self._trunnion_dn.get()))
        self._material.set(pick(self._material_by_label,
                                state.get('material_code', geom.DEFAULT_MATERIAL_CODE),
                                self._first(self._material_by_label)))
        self._end_type.set(pick(self._end_type_by_label,
                                state.get('end_type', geom.DEFAULT_END_TYPE),
                                self._first(self._end_type_by_label)))
        for name, var in (('length', self._length), ('azimuth', self._azimuth),
                          ('pad_thickness', self._pad_thickness),
                          ('wall', self._wall)):
            value = state.get(name)
            if isinstance(value, str) and value.strip():
                var.set(value)
        if isinstance(state.get('build_pad'), bool):
            self._build_pad.set(state.get('build_pad'))
        self._on_build_pad_changed()

    @staticmethod
    def _first(by_label):
        for label in by_label:
            return label
        return ''

    def persist_state(self, state):
        try:
            state['type_code'] = self.current_type_code()
            state['pipe_dn'] = self.current_pipe_dn()
            state['trunnion_dn'] = self.current_trunnion_dn()
            state['material_code'] = self.current_material_code()
            state['end_type'] = self.current_end_type()
            state['length'] = self._length.get()
            state['azimuth'] = self._azimuth.get()
            state['pad_thickness'] = self._pad_thickness.get()
            state['wall'] = self._wall.get()
            state['build_pad'] = bool(self._build_pad.get())
        except Exception:
            pass

    def current_type_code(self):
        return self._type_by_label.get(self._type.get(), geom.DEFAULT_TYPE_CODE)

    def current_pipe_dn(self):
        return self._pipe_dn_by_label.get(self._pipe_dn.get(), geom.DEFAULT_PIPE_DN)

    def current_trunnion_dn(self):
        value = self._trunnion_dn_by_label.get(self._trunnion_dn.get())
        if value is None:
            value = geom.default_trunnion_dn(self.current_pipe_dn())
        return value

    def current_material_code(self):
        return self._material_by_label.get(self._material.get(),
                                           geom.DEFAULT_MATERIAL_CODE)

    def current_end_type(self):
        return self._end_type_by_label.get(self._end_type.get(),
                                           geom.DEFAULT_END_TYPE)

    def _float(self, text, name, default=None):
        text = (text or '').strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            raise ValueError('%s必须是数字。' % name)

    def current_length(self):
        value = self._float(self._length.get(), 'L')
        if value is None:
            value = geom.DEFAULT_L
        return value

    def current_azimuth(self):
        value = self._float(self._azimuth.get(), '方位角')
        return 0.0 if value is None else value

    def current_pad_thickness(self):
        return self._float(self._pad_thickness.get(), '补强板厚度',
                           geom.DEFAULT_PAD_THICKNESS_MM)

    def current_wall_override(self):
        return self._float(self._wall.get(), '耳轴壁厚')

    def params(self):
        return {
            'type_code': self.current_type_code(),
            'pipe_dn': self.current_pipe_dn(),
            'trunnion_dn': self.current_trunnion_dn(),
            'material_code': self.current_material_code(),
            'length_mm': self.current_length(),
            'end_type': self.current_end_type(),
            'azimuth_deg': self.current_azimuth(),
            'pad_thickness_mm': self.current_pad_thickness(),
            'build_pad': bool(self._build_pad.get()),
            'trunnion_wall_mm': self.current_wall_override(),
        }

    # -- 输出 --------------------------------------------------------------

    def _apply_status(self, message, is_error=False):
        self._set_text(getattr(self, '_status_text', None), message)

    def append_log(self, message):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.insert('end', str(message) + '\n\n')
            text_widget.see('end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    def clear_log(self):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    def set_status(self, message, is_error=False):
        self._pending_status = message
        self._pending_status_is_error = bool(is_error)

    def queue_pick(self, element_id, click_mm):
        self.pending.append((element_id, click_mm))

    def close_panel(self):
        self._close_requested = True

    # -- 主循环 ------------------------------------------------------------

    def _run_pending(self):
        self._drain_pending()
        if self._pending_status is not None:
            message = self._pending_status
            is_error = self._pending_status_is_error
            self._pending_status = None
            self._pending_status_is_error = False
            self._apply_status(message, is_error)

    def _drain_pending(self):
        pending, self.pending = self.pending, []
        for element_id, click_mm in pending:
            self._process(element_id, click_mm)

    def _process(self, element_id, click_mm):
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
            _cell, message = build_on_pick(placement, click_mm, self.params())
        except Exception as error:
            _log_exception('build trunnion failed')
            self.set_status('生成失败：%s' % error, True)
            return
        self.append_log(message)
        self.set_status('已生成一组耳轴。继续点选竖直线，右键退出。')

    # -- 收尾 --------------------------------------------------------------

    def _finish_tool(self):
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
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
            if self._close_requested:
                self._close_requested = False
                self._finish_tool()
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


class VpTrunnionLineTool(DgnElementSetTool):
    """点选竖直主管（立管轴线），在点击处生成 F6/F7 耳轴。"""

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('VpTrunnionLineTool')

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
        if self.panel is not None:
            self.panel.set_status('请点选一条竖直主管（立管轴线）；右键退出。')

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
                '没有定位到元素：请把光标放在竖直线或管道上再点击。', True)
            return True
        try:
            point = event.GetPoint()
            uor = _uor_per_mm()
            click_mm = (point.x / uor, point.y / uor, point.z / uor)
        except Exception:
            click_mm = None
        self.panel.queue_pick(element_id, click_mm)
        return True

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.close_panel()
        return True

    def _OnRestartTool(self):
        panel = self.panel
        self.panel = None
        VpTrunnionLineTool.InstallNewInstance(self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = VpTrunnionLineTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_trunnion_panel():
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel.winfo_exists():
                _active_panel.lift()
                return None
        except tk.TclError:
            pass
    panel = _VpTrunnionPanel()
    _active_panel = panel
    try:
        return VpTrunnionLineTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


# ---------------------------------------------------------------------------
# 清单导出 / 键入命令
# ---------------------------------------------------------------------------


def export_bom_json(output_path=None):
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '立管的耳轴_bom.json')
    return psb.export_combined_bom(output_path)


_COMMANDS_LOADED = False


def RegisterKeyins():
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '立管的耳轴.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenVpTrunnion():
    PyMain()


def ExportVpTrunnionBom():
    export_bom_json()


def PyMain():
    _log('PyMain: entry')
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_trunnion_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('trunnion tool start failed')
        print('立管的耳轴启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '立管的耳轴启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
