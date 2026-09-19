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
面板外观复用 ``模块/公共/端焊三角架_基础.py``。

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

# 通配导入不一定导出这两个符号，显式再导入一次（与 型钢截面生成器.py 一致）。
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
# 公共库在 模块/公共/，本插件几何在 模块/L型管架/。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', 'L型管架')
for _path in (COMMON_DIR, GEOM_DIR, STEEL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 端焊三角架_基础 as base  # noqa: E402
import L型管架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'L型管架'
SUPPORT_CODE = 'L_PIPE_RACK'


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
    _apply_base_overrides()


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'L型管架_debug_log.txt')

UI_TITLE = 'L 型管架'
UI_REVISION = 'line-select-1'

# 整组构件写入的普通单元名。
CELL_NAME = 'L_PIPE_RACK'

COMPONENT_POST_NAME = '立杆'
COMPONENT_ARM_NAME = '横担'

# 允许荷载查询用的默认 B（mm）。
DEFAULT_WIDTH_B_MM = 250.0

# 交付给基础模块的覆盖项：日志。
base.DEBUG_LOG = DEBUG_LOG

_log = base._log


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


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


class _PipeRackTitleBar(QWidget):
    """无边框窗口的自绘标题栏：只保留关闭钮，空白处按住可拖动窗口。"""

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


class _PipeRackSettingsDialog(QWidget):
    """子项 / 类型 / B / 编号 选择，预览 / 确定 / 取消面板。"""

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
        outer.addWidget(_PipeRackTitleBar(UI_TITLE, self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点选一条 L 形折线：竖直线为立杆轴线，水平线为横担"
                      "顶面（固定管子的面）。两段须共享拐点、大致垂直。类型 1/2 要求"
                      "立杆在下（竖直段在拐点下方）；类型 3/4 为吊架、要求立杆在上"
                      "（竖直段在拐点上方）。点取后可改参数，预览自动重建；点【确定】"
                      "保留，点【取消】或右键放弃。")
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
        self._row(card.content, 1, "构件A（立杆 / 横担）：", [self.spec_label])
        body.addWidget(card)

        card = base.NeuCard("尺寸参数")
        self.post_label = self._value()
        self._row(card.content, 0, "立杆高 H：",
                  [self.post_label, self._note("mm　由所选竖直线自动读取")], 8)
        self.arm_label = self._value()
        self._row(card.content, 1, "横担长 L：",
                  [self.arm_label, self._note("mm　由所选水平线自动读取")], 8)
        self.width_edit = self._edit_row(
            card.content, 2, "B：", '%.0f' % DEFAULT_WIDTH_B_MM,
            "mm　管架水平参数，用于查允许垂直荷载")
        self.load_label = self._value()
        self._row(card.content, 3, "允许垂直荷载：",
                  [self.load_label, self._note("kN　按表 1 / 表 2")], 8)
        body.addWidget(card)

        card = base.NeuCard("管架编号")
        self.rack_name_edit = self._edit_row(
            card.content, 0, "名称：", 'D5', "管架系列代号；留空则不附加编号")
        self.rack_type_combo = self._register(base.NeuCombo(
            [(1, '类型1  |  立杆在下（端焊）'),
             (2, '类型2  |  立杆在下（侧焊）'),
             (3, '类型3  |  立杆在上（端焊·吊架）'),
             (4, '类型4  |  立杆在上（侧焊·吊架）')],
            current=1, on_change=self.on_options_changed))
        self._row(card.content, 1, "类型：", [self.rack_type_combo], 16)
        self.rack_label = self._value()
        self._row(card.content, 2, "编号：",
                  [self.rack_label, self._note("名称-类型-子项-H-L（整数）")], 8)
        body.addWidget(card)

        card = base.NeuCard("创建选项")
        self.keep_toggle = self._register(base.NeuToggle("创建后保留所选 L 形线"))
        self.keep_toggle.setChecked(True)
        card.content.addWidget(self.keep_toggle, 0, 0, 1, 2)
        body.addWidget(card)

        summary = base.NeuPanel()
        self.spec_info_label = self._info("", base.UI_TEXT)
        summary.content.addWidget(self.spec_info_label)
        self.preview_info_label = self._info("预览：—", base.UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点选一条 L 形折线；改参数会自动重建预览。",
            base.UI_INFO)
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

    def current_width(self):
        try:
            return float(self.width_edit.value())
        except (TypeError, ValueError):
            return DEFAULT_WIDTH_B_MM

    def current_hanger(self):
        return geom.hanger_type(self.current_rack_type())

    def current_options(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        if not geom.variant_supports_type(variant_key, rack_type):
            raise ValueError(self._invalid_message())
        return {
            'variant': variant_key,
            'rack_type': rack_type,
            'hanger': geom.hanger_type(rack_type),
            'rack_name': self.rack_name_edit.value().strip(),
            'width': self.current_width(),
        }

    def current_rack_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        return _build_rack_number(
            self.rack_name_edit.value(), self.current_rack_type(),
            self.current_variant(), line.post_height_mm, line.arm_length_mm)

    def set_status(self, message, is_error=False, flush=True):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        if flush:
            QApplication.processEvents()

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        self.preview_info_label.setText(
            "预览：子项 %s，类型 %d，%s，H=%.0f mm，L=%.0f mm，"
            "单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'],
                result['specification'], result['post_height'],
                result['arm_length'], result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        self.spec_label.setText(geom.specification(variant_key))
        hanger = self.current_hanger()
        position = '立杆在上（吊架）' if hanger else '立杆在下'
        if self._options_valid():
            self.spec_info_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_TEXT.name())
            self.spec_info_label.setText(
                '构件A：立杆与横担同规格 %s（%s）；%s。'
                % (geom.specification(variant_key),
                   _family_description(variant_key, hanger), position))
        else:
            self.spec_info_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_ERROR.name())
            self.spec_info_label.setText(self._invalid_message())
        self.refresh_line_labels()

    def _show_line_values(self, line):
        if line is None:
            self.post_label.setText('—')
            self.arm_label.setText('—')
            self.load_label.setText('—')
            self.load_label.setToolTip('')
            self.rack_label.setText('—')
            return
        self.post_label.setText('%.1f' % line.post_height_mm)
        self.arm_label.setText('%.1f' % line.arm_length_mm)

        result = geom.allowable_load(
            self.current_variant(), line.post_height_mm, self.current_width())
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
            # 子项与类型冲突：不生成（并撤掉可能过期的预览），只提示。
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
        allowed = '/'.join(
            str(t) for t in geom.allowed_rack_types(variant_key))
        return ('不合法组合：子项 %s（工字钢）仅对端焊类型 %s 有效；'
                '类型 %d 为侧焊、无工字钢构件。请改选子项或类型。'
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
        """悬停到一条合规 L 形线上：只刷新数值显示，不改变已选定的线。"""
        if self.line is None:
            self._show_line_values(line)

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前 L 形线与选项重建预览：先建新的一版，成功后再删掉旧的。"""
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
        self.set_status('正在生成 L 型管架预览，请稍候……')
        try:
            handle, result, deleted = replace_pipe_rack(
                self.line, options['variant'], self.preview_handle,
                options['rack_type'], options['rack_name'])
        except Exception as error:
            message = 'L 型管架生成失败：%s' % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
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
            "单元含 %d 个子元素，编号 %s。%s改参数会自动重建；"
            "点【确定】保留，点【取消】放弃。" % (
                result['variant'], result['rack_type'], result['specification'],
                result['post_height'], result['arm_length'],
                result['child_count'], result['pipe_rack_number'] or '—',
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
        self.set_status('所选 L 形线删除失败，请手动删除。', True)
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
        """结束原生工具并直接收起面板。

        正常路径下 StartDefaultCommand 会触发 _OnCleanup，再由其调用
        :meth:`shutdown`；这里同时直接 shutdown 作为兜底，保证点【确定】/
        【取消】后面板一定关闭，不会停在事件泵里。
        """
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
            hanger = (self.tool_settings is not None
                      and self.tool_settings.current_hanger())
            line = extract_l_shape(handle, hanger)
            if self.tool_settings is not None:
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True, flush=False)
            return False

    def _OnResetButton(self, event):
        # 右键放弃：等同【取消】，确保面板与预览一并收掉。
        settings = self.tool_settings
        if settings is not None:
            QTimer.singleShot(0, settings.cancel_tool)
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_l_shape(eeh, self.tool_settings.current_hanger())
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = 'L 型管架生成失败：%s' % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('element modify failed')
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
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(PipeRackByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active._running:
                        active.raise_()
                        active.activateWindow()
                        return None
                except RuntimeError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _PipeRackSettingsDialog())
        if owner:
            PipeRackByLineTool._active_settings = settings
        tool = PipeRackByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_dialog_loop()
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
            QMessageBox.critical(None, UI_TITLE, '工具启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
