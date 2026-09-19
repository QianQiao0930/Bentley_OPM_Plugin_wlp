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

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEvent, QEventLoop, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                             QVBoxLayout, QWidget)


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
# 公共库在 模块/公共/，本插件几何在 模块/T形架/。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'T形架')
for _path in (COMMON_DIR, GEOM_DIR, STEEL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 端焊三角架_基础 as base  # noqa: E402
import T形架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'T形架'
SUPPORT_CODE = 'T_FRAME'


def _apply_base_overrides():
    """把本插件的日志写入基础模块（重载后会丢失）。"""
    base.DEBUG_LOG = DEBUG_LOG


def _reload_runtime_modules():
    """每次运行都强制重新读取本插件与依赖模块，规避 MicroStation 缓存。"""
    importlib.invalidate_caches()
    for module in (geom, steel_sweep_geometry, psb, base):
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
    _apply_base_overrides()


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'T形架_debug_log.txt')

UI_TITLE = 'T形架'
UI_REVISION = 'line-select-1'

# 整组构件写入的普通单元名。
CELL_NAME = 'T_FRAME'

COMPONENT_POST_NAME = '立柱'
COMPONENT_ARM_NAME = '横担'

# 默认横担长 L（mm）、横担方向「朝向」（°）：0 = 世界 +X（立柱竖直时使用）。
DEFAULT_ARM_LENGTH_MM = 500.0
DEFAULT_HEADING_DEG = 0.0

# 交付给基础模块的覆盖项：日志。
base.DEBUG_LOG = DEBUG_LOG

_log = base._log


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


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
                        heading_deg, rack_name=None):
    """按所选竖直线与横担长 L 构建 T形架单元但**不写入模型**。

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
    builder.build()

    spec = geom.specification(variant_key)
    post_cut_length = geom.post_length(variant_key, line.length_mm, rack_type)
    weld_contact = geom.weld_contact_length(variant_key, rack_type)
    rack_number = geom.build_pipe_rack_number(
        rack_name or '', rack_type, variant_key, line.length_mm, arm_length_mm)

    load = geom.allowable_load(variant_key, line.length_mm, arm_length_mm)
    if load.value is None:
        builder.note('允许垂直荷载未取到：%s' % load.message)

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
        'bom_items': [
            {'code': 'Post', 'name': COMPONENT_POST_NAME,
             'specification': spec, 'length': post_cut_length},
            {'code': 'Arm', 'name': COMPONENT_ARM_NAME,
             'specification': spec, 'length': arm_length_mm},
        ],
        'warnings': list(builder.warnings),
    }
    _log('t frame built: variant=%s, type=%d, H=%.1f, L=%.1f, post=%.1f, '
         'weld=%.1f, hbeam=%s, heading=%.2f, cells=%d, number=%s' %
         (variant_key, int(rack_type), line.length_mm, arm_length_mm,
          post_cut_length, weld_contact, result['is_hbeam'],
          float(heading_deg), builder.child_count,
          result['pipe_rack_number'] or '-'))
    return builder, result


def replace_t_frame(line, variant_key, previous_handle, rack_type=1,
                    arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                    heading_deg=DEFAULT_HEADING_DEG, rack_name=None):
    """重建 T形架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_t_frame_cell(
        line, variant_key, rack_type, arm_length_mm, heading_deg, rack_name)
    new_handle = builder.commit()
    _attach_support_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_t_frame(line, variant_key, rack_type=1,
                 arm_length_mm=DEFAULT_ARM_LENGTH_MM,
                 heading_deg=DEFAULT_HEADING_DEG, rack_name=None):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_t_frame_cell(
        line, variant_key, rack_type, arm_length_mm, heading_deg, rack_name)
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


class _TFrameTitleBar(QWidget):
    """无边框窗口的自绘标题栏：只保留关闭钮，空白处可拖动窗口。"""

    def __init__(self, title, on_close, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._drag_offset = None
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 0, 10, 0)
        row.setSpacing(9)
        dot = QLabel(self)
        dot.setFixedSize(9, 9)
        dot.setStyleSheet('background: #4A66E0; border-radius: 4px;')
        dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        caption = QLabel(title, self)
        caption.setStyleSheet('font-size: 14px; font-weight: 600;'
                              ' color: #39435A;')
        caption.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(dot)
        row.addWidget(caption)
        row.addStretch(1)
        row.addWidget(base.NeuIconButton(self, 'close', on_close, danger=True))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (event.globalPos()
                                 - self.window().frameGeometry().topLeft())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class _TFrameSettingsDialog(QWidget):
    """子项 / L / 朝向 / 编号 选择，预览 / 确定 / 取消面板。"""

    RADIUS = base.UI_RADIUS

    def __init__(self):
        self._app = base.ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, base.UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self.variant_combo = None
        self.option_widgets = []
        self._running = True
        self._allow_close = False
        self._finish_requested = False
        self._event_loop = QEventLoop()

        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(base.REGENERATE_DELAY_MS)
        self._regen_timer.timeout.connect(self._run_pending_regeneration)
        self._text_timer = QTimer(self)
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(base.TEXT_REGENERATE_DELAY_MS)
        self._text_timer.timeout.connect(self._run_pending_regeneration)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_TFrameTitleBar(UI_TITLE, self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点选一条竖直线（立柱轴线，允许 ±5° 内轻微倾斜）："
                      "线长即立柱长 H。类型1 正 T 形架：下端为基座、上端放横担，"
                      "管道坐横担顶面；类型2 倒 T 形吊架：下端放横担（管位朝上，"
                      "同类型1方向），立柱向上到上端（接已有结构）。再输入横担全长 "
                      "L —— 横担以该线为中点、垂直于立柱、取世界水平方向（面板"
                      "「朝向」）。角钢子项（A~C）立柱与横担背靠背、留 10 施焊"
                      "间隙；H 型钢子项（D~G）端面焊接、腹板共面。各子项有最大"
                      "允许 H / L，超限会拒绝生成。点取后可改参数、预览自动重建；"
                      "点【确定】保留，点【取消】放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = base.NeuCard("构件规格（表 3）")
        self.variant_combo = self._register(base.NeuCombo(
            list(geom.variant_choices()),
            current=geom.DEFAULT_VARIANT, on_change=self.on_options_changed))
        self._row(card.content, 0, "子项：", [self.variant_combo], 16)
        self.spec_label = self._value()
        self._row(card.content, 1, "构件A（立柱 / 横担）：", [self.spec_label])
        self.width_label = self._value()
        self._row(card.content, 2, "立柱截面宽 W：",
                  [self.width_label, self._note("mm　在横担长度方向的截面宽度")],
                  8)
        self.connection_label = self._value()
        self._row(card.content, 3, "连接方式：", [self.connection_label])
        body.addWidget(card)

        card = base.NeuCard("尺寸参数")
        self.height_label = self._value()
        self._row(card.content, 0, "立柱长 H：",
                  [self.height_label, self._note("mm　由所选直线自动读取")], 8)
        self.max_height_label = self._value()
        self._row(card.content, 1, "最大允许 H：",
                  [self.max_height_label, self._note("mm　表 1 / 表 2")], 8)
        self.arm_edit = self._edit_row(
            card.content, 2, "横担长 L：", '%.0f' % DEFAULT_ARM_LENGTH_MM,
            "mm　用户输入，表 1 / 表 2 的查表参数之一")
        self.max_arm_label = self._value()
        self._row(card.content, 3, "最大允许 L：",
                  [self.max_arm_label, self._note("mm　表 1 / 表 2")], 8)
        self.post_length_label = self._value()
        self._row(card.content, 4, "立柱下料长：",
                  [self.post_length_label,
                   self._note("mm　角钢：H − 肢厚 − 10；H 型钢：H − 横担截面高")],
                  8)
        self.load_label = self._value()
        self._row(card.content, 5, "允许垂直荷载：",
                  [self.load_label, self._note("kN　按表 1 / 表 2")], 8)
        self.heading_edit = self._edit_row(
            card.content, 6, "朝向：", '%.0f' % DEFAULT_HEADING_DEG,
            "°　横担方向（0 = 世界 +X）")
        body.addWidget(card)

        card = base.NeuCard("管架编号")
        self.rack_name_edit = self._edit_row(
            card.content, 0, "名称：", 'D12', "管架系列代号；留空则不附加编号")
        self.rack_type_combo = self._register(base.NeuCombo(
            [(1, '类型1  |  正 T 形架（立柱在下、横担在上）'),
             (2, '类型2  |  倒 T 形吊架（立柱在上、横担在下）')],
            current=1, on_change=self.on_options_changed))
        self._row(card.content, 1, "类型：", [self.rack_type_combo], 16)
        self.rack_label = self._value()
        self._row(card.content, 2, "编号：",
                  [self.rack_label, self._note("名称-类型-子项-H-L（整数）")], 8)
        body.addWidget(card)

        card = base.NeuCard("创建选项")
        self.keep_toggle = self._register(base.NeuToggle("创建后保留所选直线"))
        self.keep_toggle.setChecked(True)
        card.content.addWidget(self.keep_toggle, 0, 0, 1, 2)
        body.addWidget(card)

        summary = base.NeuPanel()
        self.spec_info_label = self._info("", base.UI_TEXT)
        summary.content.addWidget(self.spec_info_label)
        self.preview_info_label = self._info("预览：—", base.UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点选一条竖直线；改参数会自动重建预览。", base.UI_INFO)
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.cancel_button = base.NeuButton("取消")
        self.cancel_button.setFixedWidth(126)
        self.cancel_button.clicked.connect(self.cancel_tool)
        self.export_button = base.NeuButton("导出 JSON 清单")
        self.export_button.setFixedWidth(150)
        self.export_button.clicked.connect(self.export_bom)
        self.confirm_button = base.NeuButton("确定", accent=True)
        self.confirm_button.setFixedWidth(126)
        self.confirm_button.clicked.connect(self.confirm_tool)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.confirm_button)
        body.addLayout(button_row)
        self.action_widgets = [
            self.confirm_button, self.cancel_button, self.export_button]

        self.refresh_spec()
        self.setMinimumWidth(560)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        try:
            _stamp = int(os.path.getmtime(os.path.abspath(__file__)))
        except Exception:
            _stamp = 0
        _log('panel built %dx%d rev=%s file=%s mtime=%d'
             % (self.width(), self.height(), UI_REVISION,
                os.path.abspath(__file__), _stamp))
        self.hwnd = int(self.winId())
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)

    # -- 控件构造 ----------------------------------------------------------

    def _register(self, widget):
        self.option_widgets.append(widget)
        return widget

    def _row(self, grid, row, name, widgets, spacing=18):
        label = QLabel(name, self)
        label.setStyleSheet('color: #39435A; font-size: 13px;')
        grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        holder = QWidget(self)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(spacing)
        for widget in widgets:
            line.addWidget(widget)
        line.addStretch(1)
        grid.addWidget(holder, row, 1)
        grid.setColumnStretch(1, 1)
        return holder

    def _edit_row(self, grid, row, name, value, note):
        field = base.NeuEdit(value, width=96)
        self._register(field.edit)
        field.edit.textChanged.connect(self.on_text_changed)
        self._row(grid, row, name, [field, self._note(note)], 8)
        return field

    def _value(self):
        label = QLabel('—', self)
        label.setStyleSheet('color: #39435A; font-size: 13px;'
                            ' font-weight: 600;')
        return label

    def _note(self, text):
        label = QLabel(text, self)
        label.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        return label

    def _info(self, text, color):
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet('color: %s; font-size: 11px;' % color.name())
        return label

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        if self.variant_combo is None:
            return geom.DEFAULT_VARIANT
        return self.variant_combo.value() or geom.DEFAULT_VARIANT

    def current_rack_type(self):
        if self.rack_type_combo is None:
            return 1
        try:
            return int(self.rack_type_combo.value())
        except (TypeError, ValueError):
            return 1

    def current_arm_length(self):
        try:
            return float(self.arm_edit.value())
        except (TypeError, ValueError):
            return DEFAULT_ARM_LENGTH_MM

    def current_heading(self):
        try:
            return float(self.heading_edit.value())
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
            'rack_name': self.rack_name_edit.value().strip(),
            'arm_length': self.current_arm_length(),
            'heading': self.current_heading(),
        }

    def current_rack_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        return geom.build_pipe_rack_number(
            self.rack_name_edit.value(), self.current_rack_type(),
            self.current_variant(), line.length_mm, self.current_arm_length())

    def set_status(self, message, is_error=False, flush=True):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        if flush:
            QApplication.processEvents()

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        connection = ('H 型钢端面焊接' if result.get('is_hbeam')
                      else '角钢背靠背')
        self.preview_info_label.setText(
            "预览：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，立柱下料 "
            "%.0f mm（%s），朝向 %.0f°，单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'], result['specification'],
                result['height'], result['arm_length'],
                result['post_cut_length'], connection,
                result['heading_deg'], result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        self.spec_label.setText(geom.specification(variant_key))
        self.width_label.setText('%.0f' % geom.inplane_width(variant_key))
        self.connection_label.setText(
            'H 型钢端面焊接（腹板共面）' if geom.variant_is_hbeam(variant_key)
            else '角钢背靠背（非通长、顶端留 10 焊缝间隙）')
        max_height = geom.max_allowed_height(variant_key)
        max_arm = geom.max_allowed_arm_length(variant_key)
        self.max_height_label.setText(
            '—' if max_height is None else '%.0f' % max_height)
        self.max_arm_label.setText(
            '—' if max_arm is None else '%.0f' % max_arm)
        if self._options_valid():
            self.spec_info_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_TEXT.name())
            if geom.hanger_type(self.current_rack_type()):
                type_text = ('类型 2 为倒 T 形吊架：横担在下端、管位朝上（同类型 1 '
                             '方向）；立柱向上到结构，角钢下探与横担竖直肢背靠背'
                             '搭接，H 型钢端面焊在横担上表面。')
            else:
                type_text = ('类型 1 为正 T 形架：单根立柱居中、横担居中，'
                             '横担顶面为固定管子的面。')
            self.spec_info_label.setText(
                '构件A：立柱与横担同规格 %s（%s）；%s'
                % (geom.specification(variant_key),
                   _family_description(variant_key), type_text))
        else:
            self.spec_info_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_ERROR.name())
            self.spec_info_label.setText(self._invalid_message())
        self.refresh_line_labels()

    def _show_line_values(self, line):
        if line is None:
            self.height_label.setText('—')
            self.post_length_label.setText('—')
            self.load_label.setText('—')
            self.load_label.setToolTip('')
            self.rack_label.setText('—')
            return
        self.height_label.setText('%.1f' % line.length_mm)
        variant_key = self.current_variant()
        try:
            self.post_length_label.setText(
                '%.1f' % geom.post_length(variant_key, line.length_mm))
        except ValueError as error:
            self.post_length_label.setText('—')
            self.post_length_label.setToolTip(str(error))

        result = geom.allowable_load(
            variant_key, line.length_mm, self.current_arm_length())
        if result.value is None:
            self.load_label.setText('—')
        else:
            self.load_label.setText('%.2f' % result.value)
        self.load_label.setToolTip(result.message or '')

        number = self.current_rack_number(line)
        self.rack_label.setText(number if number else '（名称留空，不附加）')

    def refresh_line_labels(self):
        self._show_line_values(self.line)

    def _set_busy(self, busy):
        for widget in self.option_widgets + self.action_widgets:
            widget.setEnabled(not busy)
        QApplication.processEvents()

    def on_options_changed(self, *_unused):
        self.refresh_spec()
        if not self._options_valid():
            self._cancel_pending_regeneration()
            self.discard_preview()
            self.set_status(self._invalid_message(), True)
            return
        self._schedule_regeneration(self._regen_timer)

    def _options_valid(self):
        return geom.variant_supports_type(
            self.current_variant(), self.current_rack_type())

    def _invalid_message(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        allowed = '/'.join(str(t) for t in geom.allowed_rack_types(variant_key))
        return ('不合法组合：子项 %s 仅对类型 %s 有效，当前为类型 %d。'
                % (variant_key, allowed, rack_type))

    def on_text_changed(self, *_unused):
        self.refresh_spec()
        if not self._options_valid():
            return
        self._schedule_regeneration(self._text_timer)

    def _schedule_regeneration(self, timer):
        self._cancel_pending_regeneration()
        if self.line is None:
            return
        timer.start()

    def _cancel_pending_regeneration(self):
        self._regen_timer.stop()
        self._text_timer.stop()

    def _run_pending_regeneration(self):
        self.regenerate()

    def note_hover(self, line):
        """悬停到一条合规直线上：只刷新数值显示，不改变已选定的线。"""
        if self.line is None:
            self._show_line_values(line)

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前直线与选项重建预览：先建新的一版，成功后再删掉旧的。"""
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成 T形架预览，请稍候……')
        try:
            handle, result, deleted = replace_t_frame(
                self.line, options['variant'], self.preview_handle,
                options['rack_type'], options['arm_length'],
                options['heading'], options['rack_name'])
        except Exception as error:
            # 超限 / 几何失败只写面板状态，不向控制台或提示行输出，避免干扰使用。
            message = 'T形架生成失败：%s' % error
            self.set_status(message, True)
            if isinstance(error, ValueError):
                _log('preview rejected: %s' % error)
            else:
                _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.refresh_line_labels()
        self.set_result(result)
        message = (
            "预览已更新：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，"
            "朝向 %.0f°，单元含 %d 个子元素，编号 %s。%s"
            "改参数会自动重建；点【确定】保留，点【取消】放弃。" % (
                result['variant'], result['rack_type'], result['specification'],
                result['height'], result['arm_length'],
                result['heading_deg'], result['child_count'],
                result['pipe_rack_number'] or '—',
                '已替换上一版预览。' if deleted else '')
        )
        if result['warnings']:
            message += '注意：%s' % '；'.join(result['warnings'])
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
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
        if self.preview_handle is not None and not self.keep_toggle.isChecked():
            self.delete_source_line()
        self._finish_requested = True

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self._finish_requested = True

    def finish_tool(self):
        """结束原生工具并直接收起面板。"""
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        """停止 Qt 事件泵并关闭面板（可重复调用）。"""
        if not self._running and self._allow_close:
            return
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            pass

    # -- 窗口 --------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(210, 218, 231), 1.0))
        painter.setBrush(base.UI_BG)
        painter.drawRoundedRect(frame, self.RADIUS, self.RADIUS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.cancel_tool()

    def run_dialog_loop(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2,
                      area.center().y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        while self._running:
            self._event_loop.processEvents()
            if self._finish_requested:
                self._finish_requested = False
                self.finish_tool()
                continue
            PyCadInputQueue.PythonMainLoop()
        self._teardown_window()

    def _teardown_window(self):
        """退出事件泵后收尾：关闭窗口、冲刷重绘并延迟销毁，避免 UI 残留。

        无边框 + setMask 的自绘窗口若只 ``close()`` 不重绘，容易在屏幕上留下
        残影；顶层窗口不 ``deleteLater()`` 会一直驻留。这里显式处理。
        """
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            return
        QApplication.processEvents()
        try:
            self.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        except (RuntimeError, TypeError):
            pass
        QApplication.processEvents()


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
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True, flush=False)
            return False

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            QTimer.singleShot(0, settings.cancel_tool)
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            # 只在面板显示，不向控制台 / 提示行输出。
            message = 'T形架生成失败：%s' % error
            self.tool_settings.set_status(message, True)
            if isinstance(error, ValueError):
                _log('element modify rejected: %s' % error)
            else:
                _log_exception('element modify failed')
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
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(TFrameByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active._running:
                        active.raise_()
                        active.activateWindow()
                        return None
                except RuntimeError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _TFrameSettingsDialog())
        if owner:
            TFrameByLineTool._active_settings = settings
        tool = TFrameByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_dialog_loop()
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
            QMessageBox.critical(None, UI_TITLE, '启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
