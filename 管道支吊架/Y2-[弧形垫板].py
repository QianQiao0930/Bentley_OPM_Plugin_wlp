# -*- coding: utf-8 -*-
"""弧形垫板（Y2，1/2″~36″，即 DN15~900）放置工具。

运行后**点选一根水平管道或一条水平直线段**，在**点击处**沿其轴线生成一块
「弧形垫板」：垫板贴附焊接在管道**外壁**上、居中于**管底竖直向下**方向，
沿管轴长 **L**（由面板输入，居中于点击处 / 支承位置）。可连续点选，右键退出。

几何做法（按图集 Y2）：

    截面（垂直于管轴的平面内）＝ 两段同心圆弧 + 两条径向直线：
        内弧半径 = 管道外径 / 2（贴管壁）
        外弧半径 = 内弧半径 + T（T = 板厚，见表 1）
        两弧张角 α（注 3 缺省 120°；注 4：4″/5″ 与 K1 组合时 180°）
    沿管轴拉伸 L；垫板最低点中央开 气孔 Ø6（贯穿板厚）。

数据来源：
* 选中**管道**：自动读公称直径 → 匹配 DN → 按 **ASME B36.10M** 取外径；
* 选中**直线段 / 读不到管道属性**：用面板输入的公称直径（外径同样按 ASME 表）。

管道信息（轴线起终点 / 公称直径）取自 ``管道信息查询`` 插件的读取库
``pipe_placement_info``（对普通直线同样返回其轴线）。并遵循它的一条铁律：
**EC 读取不在工具回调里做**——点选只把「元素 ID + 点击点」入队，真正的读取与
建模由面板主循环在 ``PyCadInputQueue.PythonMainLoop()`` 返回之后执行。

清单写入**管道支吊架公共库**，`SupportType='Y2-[弧形垫板]'`，可统一统计 / 导出。
纯几何 / 数据逻辑在 ``模块/弧形垫板/弧形垫板_几何.py``（可脱离 Bentley 单测）。

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

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '弧形垫板')
PIPE_INFO_DIR = os.path.join(REPO_ROOT, '管道信息查询', '模块', '管道信息')
for _path in (COMMON_DIR, GEOM_DIR, PIPE_INFO_DIR, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ---------------------------------------------------------------------------
# 管道信息读取库（轴线 / 公称直径）
# ---------------------------------------------------------------------------


def _load_pipe_reader():
    """按文件路径加载（必要时强制重读）管道信息读取库，规避模块缓存。"""
    name = '管道信息_读取'
    path = os.path.join(PIPE_INFO_DIR, '管道信息_读取.py')
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    if PIPE_INFO_DIR not in sys.path:
        sys.path.insert(0, PIPE_INFO_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipe_reader = _load_pipe_reader()

# ``from MSPyX import *`` 不一定导出这些符号，按名字在已加载的 MSPy 模块里补齐。
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())


# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
for _path in (REPO_ROOT, COMMON_DIR):
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

import 弧形垫板_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


UI_TITLE = 'Y2-[弧形垫板]'
SUPPORT_TYPE = 'Y2-[弧形垫板]'
SUPPORT_CODE = 'Y2_ARC_PAD'
CELL_NAME = 'Y2_ARC_PAD'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '弧形垫板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 兜底管径：读不到管道公称直径 / 不在表内时使用。
DEFAULT_DN = 100
DEFAULT_LENGTH_MM = 300.0
DEFAULT_MATERIAL_CODE = geom.DEFAULT_MATERIAL_CODE
DEFAULT_ALPHA_DEG = geom.DEFAULT_ALPHA_DEG

# 水平管判定容差（°）：与水平面夹角不超过该值才允许（垫板恒居中于管底）。
HORIZONTAL_TOLERANCE_DEG = 5.0

# 气孔布尔减时两端各多伸出的余量（mm）。
VENT_HOLE_MARGIN_MM = 1.0


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


def _reload_runtime_modules():
    importlib.invalidate_caches()
    for module in (geom, psb):
        try:
            importlib.reload(module)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 向量 / 本地方位系
# ---------------------------------------------------------------------------


def _dot(first, second):
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _normalize(vector):
    length = math.sqrt(vector[0] * vector[0] + vector[1] * vector[1]
                       + vector[2] * vector[2])
    if length <= 1.0e-12:
        raise ValueError('方向向量长度为零。')
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _frame(axis, origin_mm):
    """本地方位系 ``(ex, ey, ez, origin)``：X=管轴，Z≈竖直向上。

    垫板截面居中于 **−Z**（管底竖直向下）方向，因此绕管轴的角度自动确定。
    """
    ex = _normalize(axis)
    up = (0.0, 0.0, 1.0)
    if abs(_dot(ex, up)) > 0.99:
        up = (1.0, 0.0, 0.0)
    ey = _normalize(_cross(up, ex))
    ez = _normalize(_cross(ex, ey))
    if ez[2] < 0.0:
        ey = (-ey[0], -ey[1], -ey[2])
        ez = (-ez[0], -ez[1], -ez[2])
    return (ex, ey, ez, tuple(float(v) for v in origin_mm))


def _world(frame, x, y, z):
    ex, ey, ez, origin = frame
    return (origin[0] + x * ex[0] + y * ey[0] + z * ez[0],
            origin[1] + x * ex[1] + y * ey[1] + z * ez[1],
            origin[2] + x * ex[2] + y * ey[2] + z * ez[2])


def _world_dir(frame, x, y, z):
    ex, ey, ez, _origin = frame
    return (x * ex[0] + y * ey[0] + z * ez[0],
            x * ex[1] + y * ey[1] + z * ez[1],
            x * ex[2] + y * ey[2] + z * ez[2])


def _is_horizontal(axis):
    limit = math.sin(math.radians(HORIZONTAL_TOLERANCE_DEG))
    return abs(float(axis[2])) <= limit


# ---------------------------------------------------------------------------
# 实体构造
# ---------------------------------------------------------------------------


def _succeeded(status):
    if isinstance(status, tuple):
        status = status[0] if status else None
    return BentleyStatus.eSUCCESS == status


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _profile_body(points_mm, sweep_mm, dgn_model, uor_per_mm):
    """由共面点列构造截面，再沿 sweep 拉伸成一个体；失败返回 None。"""
    points = DPoint3dArray()
    for point in points_mm:
        points.append(DPoint3d(point[0] * uor_per_mm, point[1] * uor_per_mm,
                               point[2] * uor_per_mm))
    profile = EditElementHandle()
    if BentleyStatus.eSUCCESS != ShapeHandler.CreateShapeElement(
            profile, None, points, dgn_model.Is3d(), dgn_model):
        return None
    if BentleyStatus.eSUCCESS != profile.AddToModel():
        return None
    result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if result is None or not _succeeded(result[0]):
        return None
    body = result[1]
    sweep = DVec3d(sweep_mm[0] * uor_per_mm, sweep_mm[1] * uor_per_mm,
                   sweep_mm[2] * uor_per_mm)
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body, sweep):
        return None
    return body


def _sweep_profile(frame, uor_per_mm, local_points, local_sweep, dgn_model):
    """折线近似截面沿管轴拉伸（回退路径，表面会有棱面）。"""
    points = [_world(frame, *point) for point in local_points]
    sweep = _world_dir(frame, *local_sweep)
    return _profile_body(points, sweep, dgn_model, uor_per_mm)


def _sweep_arc_profile(frame, uor_per_mm, local_segments, local_sweep, dgn_model):
    """「直线 + 真圆弧」截面沿管轴拉伸；失败返回 None。

    圆弧用 ``DEllipse3d.FromPointsOnArc`` 由三个控制点还原成精确圆弧，因此拉伸出的
    内 / 外表面是**光滑圆柱面**，而不是折线近似产生的多段棱面（「格格」）。
    """
    curves = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for kind, points in local_segments:
        world = []
        for point in points:
            x, y, z = _world(frame, *point)
            world.append(DPoint3d(x * uor_per_mm, y * uor_per_mm,
                                  z * uor_per_mm))
        if kind == 'arc':
            curves.Add(ICurvePrimitive.CreateArc(
                DEllipse3d.FromPointsOnArc(world[0], world[1], world[2])))
        else:
            curves.Add(ICurvePrimitive.CreateLine(
                DSegment3d(world[0], world[1])))

    profile = EditElementHandle()
    try:
        status = DraftingElementSchema.ToElement(
            profile, curves, None, dgn_model.Is3d(), dgn_model)
    except Exception as error:
        _log('arc profile raised: %r' % error)
        return None
    if not _succeeded(status):
        _log('arc profile element failed: %r' % (status,))
        return None
    if BentleyStatus.eSUCCESS != profile.AddToModel():
        _log('arc profile could not be added to model')
        return None

    result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if result is None or not _succeeded(result[0]):
        _log('arc profile could not be converted to a body')
        return None
    body = result[1]
    sweep = _world_dir(frame, *local_sweep)
    sweep = DVec3d(sweep[0] * uor_per_mm, sweep[1] * uor_per_mm,
                   sweep[2] * uor_per_mm)
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body, sweep):
        _log('arc profile sweep failed')
        return None
    return body


def _mm_point(frame, uor_per_mm, x, y, z):
    world = _world(frame, x, y, z)
    return DPoint3d(world[0] * uor_per_mm, world[1] * uor_per_mm,
                    world[2] * uor_per_mm)


def _cone_body(frame, uor_per_mm, start, end, radius, dgn_model):
    """真正的圆柱实体；起点、终点为本地坐标（mm）。失败返回 None。"""
    p0 = _mm_point(frame, uor_per_mm, *start)
    p1 = _mm_point(frame, uor_per_mm, *end)
    detail = DgnConeDetail(p0, p1, radius * uor_per_mm, radius * uor_per_mm, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if BentleyStatus.eSUCCESS != DraftingElementSchema.ToElement(
            element, primitive, None, dgn_model):
        return None
    result = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if result is None or not _succeeded(result[0]):
        return None
    return result[1]


def _boolean(target, tools, subtract):
    array = ISolidKernelEntityPtrArray()
    for tool in tools:
        array.append(tool)
    try:
        if subtract:
            status = SolidUtil.Modify.BooleanSubtract(target, array)
        else:
            status = SolidUtil.Modify.BooleanUnion(target, array)
    except Exception as error:
        _log('boolean exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    return BentleyStatus.eSUCCESS == status


def _assembly_element(dgn_model, bodies):
    """把垫板装入 Cell 后一次写入模型。"""
    cell = EditElementHandle()
    NormalCellHeaderHandler.CreateOrphanCellElement(cell, CELL_NAME, True, dgn_model)
    for name, body in bodies:
        child = EditElementHandle()
        if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
                child, body, None, dgn_model):
            raise RuntimeError('%s转模型元素失败。' % name)
        if BentleyStatus.eSUCCESS != NormalCellHeaderHandler.AddChildElement(cell, child):
            raise RuntimeError('%s加入单元失败。' % name)
    if BentleyStatus.eSUCCESS != NormalCellHeaderHandler.AddChildComplete(cell):
        raise RuntimeError('完成垫板单元失败。')
    if BentleyStatus.eSUCCESS != cell.AddToModel():
        raise RuntimeError('写入垫板单元失败。')
    return cell


# ---------------------------------------------------------------------------
# 建模
# ---------------------------------------------------------------------------


def _attach_support_items(cell, layout):
    """把垫板写入共享支吊架库（整组记录 + 构件记录），供统一统计 / 清单。"""
    specification = 'DN%d（%s）OD%.1f，T%.0f，L%.0f，α%.0f°，%s' % (
        layout.dn, layout.nps, layout.od_mm, layout.thickness,
        layout.length_mm, layout.alpha_deg, layout.pad_material)
    components = [{
        'code': 'Pad',
        'name': '弧形垫板',
        'specification': specification,
        'length': float(layout.length_mm),
        'quantity': 1,
        'unit': '件',
    }]
    try:
        return psb.attach_components(
            cell, support_type=SUPPORT_TYPE, support_code=SUPPORT_CODE,
            assembly_tag=layout.number, assembly_spec=specification,
            components=components)
    except Exception:
        _log_exception('attach support items failed')
        return 0


def build_pad(center_mm, axis, dn, length_mm,
              material_code=DEFAULT_MATERIAL_CODE, alpha_deg=DEFAULT_ALPHA_DEG):
    """沿管轴 ``axis`` 在 ``center_mm`` 处生成一块弧形垫板。

    垫板居中于 ``center_mm``（= 支承位置），贴附在管道**管底**外壁上。
    返回 ``(模型单元, layout)``。
    """
    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise ValueError('请在三维模型中运行。')
    if not _is_horizontal(axis):
        raise ValueError('该元素不是水平管（与水平面夹角超过 ±%.0f°），'
                         '垫板恒居中于管底，只适用于水平管道。'
                         % HORIZONTAL_TOLERANCE_DEG)

    layout = geom.build_layout(dn, length_mm, material_code, alpha_deg)
    uor_per_mm = _uor_per_mm(dgn_model)
    frame = _frame(axis, center_mm)

    # 截面：位于 x = −L/2 的 Y-Z 平面内（垫板居中于点击处），沿 +X 拉伸 L。
    # 优先用「直线 + 真圆弧」截面，拉伸面为光滑圆柱面；失败才退回折线近似。
    x_start = -layout.half_length_mm
    local_segments = [
        (kind, [(x_start, y, z) for (y, z) in points])
        for kind, points in geom.section_segments(layout)]
    sweep = (layout.length_mm, 0.0, 0.0)
    body = _sweep_arc_profile(frame, uor_per_mm, local_segments, sweep, dgn_model)
    if body is None:
        _log('arc profile unavailable; falling back to faceted polyline profile')
        local_points = [(x_start, y, z) for (y, z) in geom.section_points(layout)]
        body = _sweep_profile(frame, uor_per_mm, local_points, sweep, dgn_model)
    if body is None:
        raise RuntimeError('创建垫板拉伸体失败（截面或拉伸无效）。')

    # 气孔 Ø6：垫板最低点中央，沿径向（−Z）贯穿板厚。
    if layout.has_vent_hole:
        radius = layout.vent_hole_dia / 2.0
        hole = _cone_body(
            frame, uor_per_mm,
            (0.0, 0.0, -(layout.outer_radius + VENT_HOLE_MARGIN_MM)),
            (0.0, 0.0, -(layout.inner_radius - VENT_HOLE_MARGIN_MM)),
            radius, dgn_model)
        if hole is None:
            _log('vent hole cylinder failed; pad generated without hole')
        elif not _boolean(body, [hole], True):
            _log('vent hole boolean failed; pad generated without hole')

    cell = _assembly_element(dgn_model, [('弧形垫板', body)])
    _attach_support_items(cell, layout)
    return cell, layout


def _is_pipe_placement(placement):
    """判断本次点选到的是**管道**（有 OpenPlant EC 实例）还是普通直线段。"""
    snapshot = placement.get('snapshot') or {}
    return bool((snapshot.get('ec') or {}).get('found'))


def _build_message(layout, is_pipe, matched, nominal, placement):
    parts = []
    if is_pipe:
        if matched is not None:
            parts.append('管道公称直径 %.1f mm。' % nominal)
        else:
            parts.append('管道公称直径 %s 未匹配到表，改用面板管径 DN%d。'
                         % ('未知' if nominal is None else '%.1f mm' % nominal,
                            layout.dn))
    else:
        parts.append('按所选直线作为管轴；未读到管道属性，改用面板参数。')
    if not placement.get('exact', True):
        parts.append('按包围盒最长边近似管轴（仅对与世界坐标轴平行的直管段可靠）。')
    orientation = placement.get('orientation')
    slope = placement.get('slope_percent')
    if orientation:
        text = '走向%s' % orientation
        if slope is not None:
            text += '（坡度 %.2f%%）' % slope
        parts.append(text + '。')
    skip = ('没有找到 OpenPlant', '公称直径', '没有读到公称直径', '标定属性单位')
    warnings = [text for text in (placement.get('warnings') or [])
                if text and not (is_pipe is False
                                 and any(mark in text for mark in skip))]
    if warnings:
        parts.append('注意：%s' % '；'.join(warnings))

    parts.append('已生成%s：内弧 R%.1f（OD%.1f/2）、外弧 R%.1f（+T%.0f）、'
                 'α%.0f°、沿管轴 L%.0f、气孔 Ø%.0f；护板材料 %s。'
                 % (layout.number, layout.inner_radius, layout.od_mm,
                    layout.outer_radius, layout.thickness, layout.alpha_deg,
                    layout.length_mm, layout.vent_hole_dia,
                    layout.pad_material))
    return ''.join(parts)


def build_on_pick(placement, click_mm, fallback_dn=DEFAULT_DN,
                  fallback_length_mm=DEFAULT_LENGTH_MM,
                  fallback_material=DEFAULT_MATERIAL_CODE,
                  fallback_alpha_deg=DEFAULT_ALPHA_DEG):
    """按所选元素（管道或直线段）与点击点生成弧形垫板。

    * 选中**管道**：用其公称直径匹配 DN，外径按 ASME B36.10M 取；
    * 选中**直线段 / 读不到管道属性**：以该直线为管轴，用面板参数建模。

    ``click_mm`` 为点击点（mm），投影到轴线后即垫板的轴向中点（支承位置）。
    返回 ``(模型单元, 提示文本)``。
    """
    start = placement.get('start_mm')
    end = placement.get('end_mm')
    axis = placement.get('axis')
    if not start or not end or axis is None:
        raise ValueError('该元素没有可用的轴线（起点 / 终点不可用），无法定位垫板；'
                         '请点选水平管道或一条水平直线段。')

    if click_mm is not None:
        center = pipe_reader.project_onto_axis(click_mm, start, end)
    else:
        center = placement.get('center_mm') or start

    is_pipe = _is_pipe_placement(placement)
    nominal = placement.get('nominal_diameter_mm')
    matched = geom.match_dn(nominal)
    dn = matched if matched is not None else fallback_dn

    cell, layout = build_pad(center, axis, dn, fallback_length_mm,
                             fallback_material, fallback_alpha_deg)
    return cell, _build_message(layout, is_pipe, matched, nominal, placement)


# ---------------------------------------------------------------------------
# 面板：显示生成记录与状态（不向控制台打印）
# ---------------------------------------------------------------------------


class _PadPanel(GlassDialog):
    """点选提示 + 参数输入 + 生成记录 + 状态；同时驱动点选主循环。

    MicroStation 的原生回调里**不做 EC 读取、也不碰 Tk**：只把
    (元素 ID, 点击点) 放进 ``pending``、把提示放进 ``_pending_status``。
    真正的读取 EC 与建模都在主循环 ``PyCadInputQueue.PythonMainLoop()``
    返回之后调用 :meth:`_run_pending` 完成。
    """

    STATE_KEY = 'Y2ArcPad'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False

        self._dn = tk.StringVar()
        self._length = tk.StringVar(value='%.0f' % DEFAULT_LENGTH_MM)
        self._material = tk.StringVar()
        self._alpha = tk.StringVar(value='%.0f' % DEFAULT_ALPHA_DEG)
        self._dn_by_label = {}
        self._material_by_label = {}
        self._info_text = tk.StringVar(value='—')

        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.close_panel)
        try:
            self.minsize(440, 720)
        except tk.TclError:
            pass
        self._refresh_info()
        _log('panel built file=%s' % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点选水平管道或直线，在点击处沿管轴生成弧形垫板；右键退出')
        form.columnconfigure(0, weight=1)

        hint_frame, hint_text = self._text_field(form, height=3)
        hint_frame.grid(row=0, column=0, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一根水平管道或一条水平直线段：垫板将在点击处（支承位置）'
            '沿管轴生成，贴附在管道**管底**外壁上。管道自动读取公称直径并按 '
            'ASME B36.10M 取外径；选中直线、或读不到管道属性时，改用下面面板'
            '输入的公称直径建模。可连续点选，右键退出。'))

        ttk.Label(form, text='垫板参数', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(6, 2))

        # 管径
        dn_row = tk.Frame(form, bg=CARD)
        dn_row.grid(row=2, column=0, sticky='w')
        tk.Label(dn_row, text='公称直径', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        dn_labels = []
        for key in geom.dn_choices():
            label = geom.dn_label(key)
            dn_labels.append(label)
            self._dn_by_label[label] = key
        self._dn_combo = ttk.Combobox(
            dn_row, textvariable=self._dn, state='readonly', width=22,
            style='Glass.TCombobox', values=dn_labels)
        self._dn_combo.pack(side='left', padx=(10, 0))
        self._dn_combo.bind('<<ComboboxSelected>>', self._on_param_changed)

        # 材料代码
        mat_row = tk.Frame(form, bg=CARD)
        mat_row.grid(row=3, column=0, sticky='w', pady=(6, 0))
        tk.Label(mat_row, text='材料代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        mat_labels = []
        for code, label in geom.material_choices():
            mat_labels.append(label)
            self._material_by_label[label] = code
        self._material_combo = ttk.Combobox(
            mat_row, textvariable=self._material, state='readonly', width=34,
            style='Glass.TCombobox', values=mat_labels)
        self._material_combo.pack(side='left', padx=(10, 0))
        self._material_combo.bind('<<ComboboxSelected>>', self._on_param_changed)

        # 长度 L 与张角 α
        num_row = tk.Frame(form, bg=CARD)
        num_row.grid(row=4, column=0, sticky='w', pady=(6, 0))
        tk.Label(num_row, text='垫板长度 L', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        self._length_entry = self._entry(num_row, self._length, width=9)
        self._length_entry.pack(side='left', padx=(10, 4), ipady=3)
        tk.Label(num_row, text='mm', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        tk.Label(num_row, text='张角 α', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(16, 0))
        self._alpha_entry = self._entry(num_row, self._alpha, width=7)
        self._alpha_entry.pack(side='left', padx=(10, 4), ipady=3)
        tk.Label(num_row, text='°', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        for var in (self._length, self._alpha):
            var.trace_add('write', lambda *_a: self._refresh_info())

        self._note_label = tk.Label(
            form, text='注 3：α 缺省 120°；注 4：4″/5″（DN100/DN125）与 K1 '
                       '限位架组合使用时 α 宜取 180°。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left', wraplength=400)
        self._note_label.grid(row=5, column=0, sticky='w', pady=(4, 0))

        # 只读信息
        info_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                              highlightthickness=1)
        info_frame.grid(row=6, column=0, sticky='ew', pady=(8, 0))
        tk.Label(info_frame, textvariable=self._info_text, bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_SMALL, justify='left', wraplength=400,
                 anchor='w').pack(fill='x', padx=10, pady=7)

        ttk.Label(form, text='生成记录', style='Section.TLabel').grid(
            row=7, column=0, sticky='w', pady=(8, 2))
        log_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.grid(row=8, column=0, sticky='nsew')
        form.rowconfigure(8, weight=1)
        self._log_view = tk.Text(
            log_frame, height=14, width=38, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=6, cursor='arrow')
        log_bar = SlimScrollbar(log_frame, command=self._log_view.yview,
                                trough=CARD_SOFT)
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side='left', fill='both', expand=True)
        log_bar.pack(side='right', fill='y')
        self._log_view.configure(state='disabled')

        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=9, column=0, sticky='ew', pady=(6, 0))
        self._set_text(self._status_text, '请在模型中点选水平管道或直线。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=10, column=0, sticky='ew', pady=(8, 0))
        self.clear_button = RoundButton(
            buttons, '清空记录', self.clear_log, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button = RoundButton(
            buttons, '退出', self.close_panel, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button.pack(side='right')
        self.clear_button.pack(side='right', padx=(0, 8))

    def _entry(self, parent, variable, width=9):
        return tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT,
            fg=INK, bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')

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

    # -- 面板输入 ----------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = None
        fallback = None
        for label, key in self._dn_by_label.items():
            if fallback is None or key == DEFAULT_DN:
                fallback = label
            if key == state.get('dn'):
                selected = label
        self._dn.set(selected or fallback)

        mat_selected = None
        mat_fallback = None
        for label, code in self._material_by_label.items():
            if mat_fallback is None or code == DEFAULT_MATERIAL_CODE:
                mat_fallback = label
            if code == state.get('material'):
                mat_selected = label
        self._material.set(mat_selected or mat_fallback)

        value = state.get('length')
        if isinstance(value, str) and value.strip():
            self._length.set(value)
        value = state.get('alpha')
        if isinstance(value, str) and value.strip():
            self._alpha.set(value)

    def persist_state(self, state):
        try:
            state['dn'] = self.current_dn()
            state['material'] = self.current_material()
            state['length'] = self._length.get()
            state['alpha'] = self._alpha.get()
        except Exception:
            pass

    def _on_param_changed(self, _event=None):
        self._refresh_info()

    def current_dn(self):
        return self._dn_by_label.get(self._dn.get(), DEFAULT_DN)

    def current_material(self):
        return self._material_by_label.get(self._material.get(),
                                           DEFAULT_MATERIAL_CODE)

    def current_length(self):
        try:
            value = float((self._length.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_LENGTH_MM
        return value if math.isfinite(value) else DEFAULT_LENGTH_MM

    def current_alpha(self):
        try:
            value = float((self._alpha.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_ALPHA_DEG
        return value if math.isfinite(value) else DEFAULT_ALPHA_DEG

    def _refresh_info(self):
        try:
            layout = geom.build_layout(
                self.current_dn(), self.current_length(),
                self.current_material(), self.current_alpha())
            text = ('%s\nOD %.1f（内弧 R %.1f）· 板厚 T %.0f（外弧 R %.1f）· '
                    'α %.0f° · L %.0f · 气孔 Ø%.0f · 护板 %s · 约 %.2f kg'
                    % (layout.number, layout.od_mm, layout.inner_radius,
                       layout.thickness, layout.outer_radius, layout.alpha_deg,
                       layout.length_mm, layout.vent_hole_dia,
                       layout.pad_material, geom.plate_mass_kg(layout)))
        except Exception as error:
            text = '参数无效：%s' % error
        try:
            self._info_text.set(text)
        except tk.TclError:
            pass

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
        """在 ``PythonMainLoop`` 返回之后执行：安全读取 EC 并建模。"""
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
        # 这里已不在工具回调内（PythonMainLoop 返回之后），可安全读取 EC。
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
            _cell, message = build_on_pick(
                placement, click_mm,
                self.current_dn(), self.current_length(),
                self.current_material(), self.current_alpha())
        except Exception as error:
            _log_exception('build pad failed')
            self.set_status('生成失败：%s' % error, True)
            return
        self.append_log(message)
        self.set_status('已生成一块弧形垫板。继续点选水平管道或直线，右键退出。')

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
# 交互工具：点选管道 / 直线（只入队，EC 读取在面板循环里）
# ---------------------------------------------------------------------------


class Y2ArcPadPipeTool(DgnElementSetTool):
    """点选**水平管道或直线段**，在点击处沿其轴线生成弧形垫板。

    ``_OnPostLocate`` 只记元素 ID；``_OnDataButton`` 只把 (元素 ID, 点击点)
    交给面板排队并消费点击——**回调内不做任何 EC 读取**。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('Y2ArcPadPipeTool')

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
            self.panel.set_status('请点选一根水平管道或一条水平直线段；右键退出。')

    def _OnPostLocate(self, path, cant_accept_reason):
        """只记下定位到的元素 ID（不保存句柄、不读属性）。"""
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
        """把 (元素 ID, 点击点) 入队；返回 True 消费本次点击。"""
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            self.panel.set_status(
                '没有定位到元素：请把光标放在管道或直线上再点击。', True)
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
        # 保留面板引用重装工具，从而可以连续点取。
        panel = self.panel
        self.panel = None
        Y2ArcPadPipeTool.InstallNewInstance(self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = Y2ArcPadPipeTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_pad_panel():
    """打开面板；已在运行时把已有窗口提到前台，避免重复窗口残留。"""
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel.winfo_exists():
                _active_panel.lift()
                return None
        except tk.TclError:
            pass
    panel = _PadPanel()
    _active_panel = panel
    try:
        return Y2ArcPadPipeTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


# ---------------------------------------------------------------------------
# 清单导出 / 键入命令
# ---------------------------------------------------------------------------


def export_bom_json(output_path=None):
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '弧形垫板_bom.json')
    return psb.export_combined_bom(output_path)


def export_y2_pad_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYY2PAD PLACE / PYY2PAD EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '弧形垫板.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenY2Pad():
    PyMain()


def ExportY2PadBom():
    export_y2_pad_bom()


def PyMain():
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        _log('PyMain: entry')
        return show_pad_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('pad tool start failed')
        print('弧形垫板启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '弧形垫板启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None


if __name__ == '__main__':
    PyMain()