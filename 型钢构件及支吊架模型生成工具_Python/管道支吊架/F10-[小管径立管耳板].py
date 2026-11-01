# -*- coding: utf-8 -*-
"""小管径立管耳板（DN15~DN50）—— 选一条竖直线，在点击处生成建模实体。

运行后**点选一条竖直线**（立管轴线），在**点击位置**（该点投影到轴线上，即
底板顶面标高）按面板选择的管径 / 长度代码 / 高度代码 / 材料代码 / 方位角 /
是否固定生成整组耳板。可连续点选，右键退出（保留已生成模型）。

* 选中**管道**：读取其公称直径，DN 自动取表（须在 DN15~DN50 内）；
* 选中**直线段**：以该直线为管轴，DN 用面板选择的管径；
* 竖直线校验：与竖直方向夹角超过 ``±5°`` 时拒绝。

几何口径（详见 ``模块/小管径立管耳板/小管径立管耳板_几何.py``）：

* 两块耳板绕管轴 **180° 对称**；耳板为**径向竖直板**，宽 ``L``（径向）×
  高 ``H``（竖直）× 厚 ``10``，内立边与管外壁相焊；
* 底板 ``70（径向）× 120（切向）× 10``，**外缘与耳板外缘齐平**，顶面与耳板
  底端直接焊接；
* **固定 Y**：每块底板 2×Ø14 孔 + M12×40 单头螺栓；**不固定 N**：不开孔、
  不配螺栓。

本插件遵循 管道支吊架 公共 ItemType 契约，写入库 ``PipeSupportComponents``，
``SupportType='小管径立管耳板'``，从而进入统一统计 / 清单导出。

EC 读取不在工具回调里做：点选只把「元素 ID + 点击点」入队，真正的读取与建模
由面板主循环在 ``PyCadInputQueue.PythonMainLoop()`` 返回之后执行。
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
GEOM_DIR = os.path.join(HERE, '模块', '小管径立管耳板')
# 管道信息读取库在 管道信息查询/模块/管道信息/。
PIPE_INFO_DIR = os.path.join(REPO_ROOT, '管道信息查询', '模块', '管道信息')

for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR, PIPE_INFO_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _load_pipe_reader():
    """按文件路径加载（必要时强制重读）管道信息读取库，规避模块缓存。"""
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

# 通配导入不一定导出这些符号，按名字在已加载的 MSPy 模块里补齐。
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())

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
    SlimScrollbar,
)

import 小管径立管耳板_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

UI_TITLE = 'F10-[小管径立管耳板]'
SUPPORT_TYPE = 'F10-[小管径立管耳板]'
SUPPORT_CODE = 'VP_EAR_PLATE'
_CELL_NAME = 'VP_EAR_PLATE'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '小管径立管耳板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 孔 / 布尔贯穿余量（mm）。
_THROUGH_MARGIN_MM = 5.0


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
# 基础几何：向量 / 坐标架
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
    """判断方向是否近似竖直（与 ±Z 夹角 ≤ 容差）。"""
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length <= 1.0e-12:
        return False
    angle = math.degrees(math.acos(min(1.0, abs(axis[2]) / length)))
    return angle <= float(tolerance_deg)


def _frame(axis, azimuth_deg):
    """由管轴与方位角构造本地方位系 ``(ex, ey, ez)``。

    ``ez`` = 管轴（朝上），``ex`` = 方位角方向的径向，``ey`` = 切向；
    ``ex`` / ``ey`` 张成水平面，方位角自世界 +X 起、绕 ``ez`` 逆时针。
    """
    ez = _normalize(axis)
    if ez[2] < 0.0:
        ez = (-ez[0], -ez[1], -ez[2])
    ref = (1.0, 0.0, 0.0)
    if abs(_dot(ref, ez)) > 0.99:
        ref = (0.0, 1.0, 0.0)
    # ref 在垂直于 ez 的平面内的分量。
    projected = (ref[0] - _dot(ref, ez) * ez[0],
                 ref[1] - _dot(ref, ez) * ez[1],
                 ref[2] - _dot(ref, ez) * ez[2])
    e0 = _normalize(projected)
    angle = math.radians(float(azimuth_deg))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    spin = _cross(ez, e0)
    ex = (e0[0] * cos_a + spin[0] * sin_a,
          e0[1] * cos_a + spin[1] * sin_a,
          e0[2] * cos_a + spin[2] * sin_a)
    ex = _normalize(ex)
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


# ---------------------------------------------------------------------------
# 基础几何：实体
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


def _hex_body(model, point, direction, x, y, z0, z1, across_flats):
    """沿本地 Z 拉伸的六角棱柱（螺栓头），对边尺寸为 across_flats。"""
    radius = across_flats / (2.0 * math.cos(math.pi / 6.0))
    points = DPoint3dArray()
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        points.append(point(x + radius * math.cos(theta),
                            y + radius * math.sin(theta), z0))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建六角截面')
    _check(profile.AddToModel(), '创建六角临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '六角截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除六角临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(0.0, 0.0, z1 - z0)),
           '拉伸螺栓头')
    return body


def _bolt_bodies(model, point, direction, uor, x, y, layout):
    """M12×40 单头螺栓：贯穿底板的螺杆 + 顶面六角头（沿本地 Z）。"""
    dia = layout.bolt_diameter_mm
    head_height = dia * geom.BOLT_HEAD_HEIGHT_RATIO
    across = dia * geom.BOLT_HEAD_ACROSS_FLATS_RATIO
    shank = _cylinder_between(
        model, point(x, y, -layout.bolt_length_mm), point(x, y, 0.0),
        dia / 2.0, uor)
    head = _hex_body(model, point, direction, x, y, 0.0, head_height, across)
    return [('螺杆', shank), ('螺栓头', head)]


def _assembly_element(model, bodies):
    """把耳板组件装入 Cell 后一次写入模型。"""
    cell = EditElementHandle()
    NormalCellHeaderHandler.CreateOrphanCellElement(cell, _CELL_NAME, True, model)
    for name, body in bodies:
        child = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(child, body, None, model),
               name + '转模型元素')
        _check(NormalCellHeaderHandler.AddChildElement(cell, child),
               name + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成耳板单元')
    _check(cell.AddToModel(), '写入耳板单元')
    return cell


# ---------------------------------------------------------------------------
# 建模：单侧耳板组件
# ---------------------------------------------------------------------------


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


def _build_side(model, point, direction, uor, layout):
    """一侧的「耳板 + 底板」实体与螺栓。

    耳板是干净的 ``H×L×10`` 矩形体，底端坐在底板顶面上（焊接），**不与底板
    布尔并**；底板单独开螺栓孔。
    """
    r_in, r_out = geom.ear_radial_span(layout)
    t_half = layout.ear_thickness_mm / 2.0
    z_bottom, z_top = geom.ear_z_span(layout)
    ear = _box_body(model, point, direction, r_in, r_out,
                    -t_half, t_half, z_bottom, z_top)

    b_in, b_out = geom.base_radial_span(layout)
    t_min, t_max = geom.base_tangential_span(layout)
    base = _box_body(model, point, direction, b_in, b_out,
                     t_min, t_max, -layout.base_thickness_mm, 0.0)

    centers = geom.hole_centers(layout)
    if centers:
        hole_radius = layout.hole_diameter_mm / 2.0
        cutters = ISolidKernelEntityPtrArray()
        for (hole_r, hole_t) in centers:
            cutters.append(_cylinder_between(
                model,
                point(hole_r, hole_t, -layout.base_thickness_mm - _THROUGH_MARGIN_MM),
                point(hole_r, hole_t, _THROUGH_MARGIN_MM),
                hole_radius, uor))
        _check(SolidUtil.Modify.BooleanSubtract(base, cutters), '底板开螺栓孔')

    bolts = []
    for (hole_r, hole_t) in centers:
        bolts.extend(_bolt_bodies(model, point, direction, uor,
                                  hole_r, hole_t, layout))
    return ear, base, bolts


def build_ear_plate(layout, base_point_mm, axis):
    """按轴线与底板顶面点构建整组耳板单元，返回模型单元句柄。

    ``base_point_mm`` 为底板顶面标高（点击点在轴线上的投影），``axis`` 为管轴。
    """
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    uor = _uor_per_mm(model)
    ex, ey, ez = _frame(axis, layout.azimuth_deg)
    center = (float(base_point_mm[0]), float(base_point_mm[1]),
              float(base_point_mm[2]))

    bodies = []
    for side, (sx, sy) in enumerate(((ex, ey), (_neg(ex), _neg(ey))), start=1):
        point, direction = _make_mappers(center, sx, sy, ez, uor)
        ear, base, bolts = _build_side(model, point, direction, uor, layout)
        bodies.append(('耳板%d' % side, ear))
        bodies.append(('底板%d' % side, base))
        for index, (name, bolt) in enumerate(bolts, start=1):
            bodies.append(('螺栓%d-%d %s' % (side, index, name), bolt))
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


def build_on_pick(placement, click_mm, panel_dn, panel_azimuth_deg, panel_fixed):
    """按所选元素（管道或直线）与点击点生成整组耳板。

    返回 ``(模型单元, 提示文本)``。
    """
    start = placement.get('start_mm')
    end = placement.get('end_mm')
    axis = placement.get('axis')
    if not start or not end or axis is None:
        raise ValueError('该元素没有可用的轴线，无法定位耳板；'
                         '请点选立管（管道）或一条竖直线。')

    if not _is_vertical(axis):
        raise ValueError('请选择一条竖直线（立管轴线）；'
                         '与竖直方向夹角须在 ±%.0f° 以内。'
                         % geom.VERTICAL_TOLERANCE_DEG)

    is_pipe = _is_pipe_placement(placement)
    nominal = placement.get('nominal_diameter_mm')
    matched = geom.match_dn(nominal)
    if is_pipe:
        if matched is None:
            raise ValueError('所选管道公称直径 %s 不在 DN15~DN50 范围内。'
                             % ('未知' if nominal is None else '%.1f mm' % nominal))
        dn = matched
    else:
        dn = panel_dn

    if click_mm is not None:
        base_point = pipe_reader.project_onto_axis(click_mm, start, end)
    else:
        base_point = placement.get('center_mm') or start

    layout = geom.build_layout(
        dn=dn,
        length_code=_PANEL['length_code'],
        height_code=_PANEL['height_code'],
        material_code=_PANEL['material_code'],
        azimuth_deg=panel_azimuth_deg, fixed=panel_fixed)

    cell = build_ear_plate(layout, base_point, axis)
    attached = _attach_support_items(cell, layout)

    parts = ['已生成小管径立管耳板：%s' % geom.describe(layout)]
    parts.append('编号 %s；已写入统计 %d 条。' % (layout.number, attached))
    parts.append('允许垂直管长度 %.0f m。' % layout.allowable_vertical_pipe_m)
    if not is_pipe:
        parts.append('（按所选直线作为立管轴线，管径用面板 DN%d。）' % dn)
    else:
        parts.append('（管道公称直径 %.1f mm，自动匹配 DN%d。）' % (nominal, dn))
    return cell, ''.join(parts)


# 面板参数缓存：供建模函数读取（由面板每次建模前刷新）。
_PANEL = {
    'length_code': geom.DEFAULT_LENGTH_CODE,
    'height_code': geom.DEFAULT_HEIGHT_CODE,
    'material_code': geom.DEFAULT_MATERIAL_CODE,
}


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _VpEarPlatePanel(GlassDialog):
    """参数选择 + 生成记录 + 状态；同时驱动点选主循环。"""

    STATE_KEY = 'VpEarPlate'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        self._dn = tk.StringVar()
        self._length = tk.StringVar()
        self._height = tk.StringVar()
        self._material = tk.StringVar()
        self._azimuth = tk.StringVar(value='0')
        self._fixed = tk.BooleanVar(value=True)
        self._dn_by_label = {}
        self._length_by_label = {}
        self._height_by_label = {}
        self._material_by_label = {}
        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.close_panel)
        try:
            self.minsize(430, 780)
        except tk.TclError:
            pass
        _log('panel built file=%s' % os.path.abspath(__file__))

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点选一条竖直线（立管轴线），在点击处生成耳板；右键退出')
        form.columnconfigure(0, weight=1)

        hint_frame, hint_text = self._text_field(form, height=3)
        hint_frame.grid(row=0, column=0, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一条竖直线（立管轴线）：整组耳板将在点击处生成，'
            '点击点在轴线上的投影即底板顶面标高。选中管道时自动读取公称直径'
            '（须在 DN15~DN50 内）；选中普通直线时用下面的管径。'
            '可连续点选，右键退出。'))

        ttk.Label(form, text='1. 管径 / 截面代码', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(6, 2))

        dn_row = tk.Frame(form, bg=CARD)
        dn_row.grid(row=2, column=0, sticky='w')
        tk.Label(dn_row, text='管径', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        dn_labels = []
        for key, label in geom.dn_choices():
            dn_labels.append(label)
            self._dn_by_label[label] = key
        self._dn_combo = ttk.Combobox(
            dn_row, textvariable=self._dn, state='readonly', width=24,
            style='Glass.TCombobox', values=dn_labels)
        self._dn_combo.pack(side='left', padx=(10, 0))
        tk.Label(form, text='选中直线 / 读不到管道公称直径时，按此管径建模',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).grid(
            row=3, column=0, sticky='w')

        length_row = tk.Frame(form, bg=CARD)
        length_row.grid(row=4, column=0, sticky='w', pady=(6, 0))
        tk.Label(length_row, text='长度代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        length_labels = []
        for code, label in geom.length_choices():
            length_labels.append(label)
            self._length_by_label[label] = code
        self._length_combo = ttk.Combobox(
            length_row, textvariable=self._length, state='readonly', width=24,
            style='Glass.TCombobox', values=length_labels)
        self._length_combo.pack(side='left', padx=(10, 0))

        height_row = tk.Frame(form, bg=CARD)
        height_row.grid(row=5, column=0, sticky='w', pady=(6, 0))
        tk.Label(height_row, text='高度代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        height_labels = []
        for code, label in geom.height_choices():
            height_labels.append(label)
            self._height_by_label[label] = code
        self._height_combo = ttk.Combobox(
            height_row, textvariable=self._height, state='readonly', width=24,
            style='Glass.TCombobox', values=height_labels)
        self._height_combo.pack(side='left', padx=(10, 0))

        material_row = tk.Frame(form, bg=CARD)
        material_row.grid(row=6, column=0, sticky='w', pady=(6, 0))
        tk.Label(material_row, text='材料代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        material_labels = []
        for code, label in geom.material_choices():
            material_labels.append(label)
            self._material_by_label[label] = code
        self._material_combo = ttk.Combobox(
            material_row, textvariable=self._material, state='readonly',
            width=24, style='Glass.TCombobox', values=material_labels)
        self._material_combo.pack(side='left', padx=(10, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=7, column=0, sticky='ew', pady=10)

        ttk.Label(form, text='2. 方位角 / 固定', style='Section.TLabel').grid(
            row=8, column=0, sticky='w', pady=(0, 2))

        azimuth_row = tk.Frame(form, bg=CARD)
        azimuth_row.grid(row=9, column=0, sticky='w')
        tk.Label(azimuth_row, text='方位角（顺时针自世界 +X，°）', bg=CARD,
                 fg=INK, font=UI_FONT_BOLD).pack(side='left')
        self._azimuth_entry = tk.Entry(
            azimuth_row, textvariable=self._azimuth, width=8, font=UI_FONT,
            fg=INK, bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        self._azimuth_entry.pack(side='left', padx=(10, 0), ipady=3)

        fixed_row = tk.Frame(form, bg=CARD)
        fixed_row.grid(row=10, column=0, sticky='w', pady=(6, 0))
        self._fixed_check = tk.Checkbutton(
            fixed_row, text='固定（Y：底板开孔并配 M12×40 单头螺栓）',
            variable=self._fixed, bg=CARD, fg=INK, activebackground=CARD,
            selectcolor=CARD, font=UI_FONT, highlightthickness=0, bd=0)
        self._fixed_check.pack(side='left')
        tk.Label(form, text='不勾选 = 不固定（N）：不开孔、不配螺栓',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).grid(
            row=11, column=0, sticky='w', padx=(22, 0))

        ttk.Label(form, text='生成记录', style='Section.TLabel').grid(
            row=12, column=0, sticky='w', pady=(8, 2))
        log_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.grid(row=13, column=0, sticky='nsew')
        form.rowconfigure(13, weight=1)
        self._log_view = tk.Text(
            log_frame, height=12, width=36, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=6, cursor='arrow')
        log_bar = SlimScrollbar(log_frame, command=self._log_view.yview,
                                trough=CARD_SOFT)
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side='left', fill='both', expand=True)
        log_bar.pack(side='right', fill='y')
        self._log_view.configure(state='disabled')

        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=14, column=0, sticky='ew', pady=(6, 0))
        self._set_text(self._status_text, '请在模型中点选一条竖直线。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=15, column=0, sticky='ew', pady=(8, 0))
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
            frame, height=height, width=36, wrap='word', font=UI_FONT_SMALL,
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

    # -- 面板输入 ----------------------------------------------------------

    def restore_state(self):
        state = self.ui_state

        def pick(by_label, key, fallback_label):
            selected = None
            for label, value in by_label.items():
                if value == key:
                    selected = label
                    break
            return selected or fallback_label

        self._dn.set(pick(self._dn_by_label, state.get('dn', geom.DEFAULT_DN),
                          self._first(self._dn_by_label)))
        self._length.set(pick(self._length_by_label,
                              state.get('length_code', geom.DEFAULT_LENGTH_CODE),
                              self._first(self._length_by_label)))
        self._height.set(pick(self._height_by_label,
                              state.get('height_code', geom.DEFAULT_HEIGHT_CODE),
                              self._first(self._height_by_label)))
        self._material.set(pick(self._material_by_label,
                                state.get('material_code', geom.DEFAULT_MATERIAL_CODE),
                                self._first(self._material_by_label)))
        azimuth = state.get('azimuth')
        if isinstance(azimuth, str) and azimuth.strip():
            self._azimuth.set(azimuth)
        if isinstance(state.get('fixed'), bool):
            self._fixed.set(state.get('fixed'))

    @staticmethod
    def _first(by_label):
        for label in by_label:
            return label
        return ''

    def persist_state(self, state):
        try:
            state['dn'] = self.current_dn()
            state['length_code'] = self.current_length_code()
            state['height_code'] = self.current_height_code()
            state['material_code'] = self.current_material_code()
            state['azimuth'] = self._azimuth.get()
            state['fixed'] = bool(self._fixed.get())
        except Exception:
            pass

    def current_dn(self):
        return self._dn_by_label.get(self._dn.get(), geom.DEFAULT_DN)

    def current_length_code(self):
        return self._length_by_label.get(self._length.get(),
                                         geom.DEFAULT_LENGTH_CODE)

    def current_height_code(self):
        return self._height_by_label.get(self._height.get(),
                                         geom.DEFAULT_HEIGHT_CODE)

    def current_material_code(self):
        return self._material_by_label.get(self._material.get(),
                                           geom.DEFAULT_MATERIAL_CODE)

    def current_azimuth(self):
        text = (self._azimuth.get() or '').strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            raise ValueError('方位角必须是数字（单位：度）。')

    def current_fixed(self):
        return bool(self._fixed.get())

    # -- 输出（只在主循环 / Tk 上下文里调用） ------------------------------

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

    # -- 原生回调入口：只写普通 Python 状态，绝不碰 Tk / EC ---------------

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
            _PANEL['length_code'] = self.current_length_code()
            _PANEL['height_code'] = self.current_height_code()
            _PANEL['material_code'] = self.current_material_code()
            _cell, message = build_on_pick(
                placement, click_mm, self.current_dn(),
                self.current_azimuth(), self.current_fixed())
        except Exception as error:
            _log_exception('build ear plate failed')
            self.set_status('生成失败：%s' % error, True)
            return
        self.append_log(message)
        self.set_status('已生成一组小管径立管耳板。继续点选竖直线，右键退出。')

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
        """Tk 主循环：UI 事件 + MicroStation；EC 读取放在 PythonMainLoop 之后。"""
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
# 交互工具：点选竖直线 / 管道
# ---------------------------------------------------------------------------


class VpEarPlateLineTool(DgnElementSetTool):
    """点选竖直线（立管轴线），在点击处生成整组耳板。

    ``_OnPostLocate`` 只记元素 ID；``_OnDataButton`` 只把 (元素 ID, 点击点)
    交给面板排队并消费点击——**回调内不做任何 EC 读取**。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('VpEarPlateLineTool')

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
            self.panel.set_status('请点选一条竖直线（立管轴线）；右键退出。')

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
        VpEarPlateLineTool.InstallNewInstance(
            self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = VpEarPlateLineTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_ear_plate_panel():
    """打开面板；已在运行时把已有窗口提到前台，避免重复窗口残留。"""
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel.winfo_exists():
                _active_panel.lift()
                return None
        except tk.TclError:
            pass
    panel = _VpEarPlatePanel()
    _active_panel = panel
    try:
        return VpEarPlateLineTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


# ---------------------------------------------------------------------------
# 清单导出 / 键入命令
# ---------------------------------------------------------------------------


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '小管径立管耳板_bom.json')
    return psb.export_combined_bom(output_path)


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYVPEAR PLACE / PYVPEAR EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '小管径立管耳板.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenVpEarPlate():
    PyMain()


def ExportVpEarPlateBom():
    export_bom_json()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _log('PyMain: entry')
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_ear_plate_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('ear plate tool start failed')
        print('小管径立管耳板启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '小管径立管耳板启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
