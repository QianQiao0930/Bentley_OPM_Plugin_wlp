# -*- coding: utf-8 -*-
"""端焊三角架（选线版 + 可选端板）放置工具。

本文件是 端焊三角架_选线版.py 的扩展版，**不改动原版**：几何、直线校验、
横担 / 斜撑创建、管架编号与面板外观都直接复用原版模块；本文件只增加：

    * 面板上「创建端板」勾选项与端板子项（A~D）下拉；
    * 勾选后在所选直线**起点处**放端板（板面垂直于横担轴线，即焊接端面），
      端板 + 4 根膨胀锚栓的绘制逻辑复用 ``模块/公共/混凝土锚板.py``；
    * 端板的孔距 S 按横担截面自动选取：严格大于截面最大边长（高 / 宽），
      再按 25 mm 向上取整，且不小于该子项的 MIN.S；板边长 = S + 100；
    * 端板占用直线起点的 plate_t 厚度，横担相应缩短为 L2 − plate_t
      （即"扣除端板厚度后再创建端焊三角架"）；
    * 端板截面中心对准横担截面中心（±Y、竖直方向都居中）；
    * 斜撑也放一块**完全相同**的端板（含 4 锚栓），位于斜撑下端面（局部
      x=0 竖直面）并与横担端板同一平面、同法向，板中心对准斜撑端面中心；
    * 端板、锚栓、横担、斜撑一起写进****同一个普通单元****，清单（ItemType）
      也附加在同一单元上。

坐标约定与原版一致：所选直线为横担上翼缘上表面（整组最高点），局部 +X 沿
直线方向（指向横担远端），局部 +Z 竖直向上，局部 z=0 为横担上翼缘上表面。
端板局部坐标再复用 G2 的 _PlateFrame：+X 为锚栓外法向（与横担方向一致），
板背面（贴既有结构面）位于所选直线起点。
"""

from __future__ import division

import importlib
import importlib.util
import math
import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyECObjects import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEventLoop, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                             QVBoxLayout, QWidget)


HERE = os.path.dirname(os.path.abspath(__file__))
# base / 混凝土锚板 / 公共支吊架模块在 模块/公共/；选线版本体在 模块/端焊三角架/。
_COMMON_DIR = os.path.join(HERE, '模块', '公共')
_LINE_DIR = os.path.join(HERE, '模块', '端焊三角架')
for _path in (HERE, _COMMON_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 端焊三角架_基础 as base
import 混凝土锚板 as anchor
import 支吊架公共库 as psb


def _load_module(name, file_path):
    """按文件路径加载模块；已加载则强制重新读取，规避 MicroStation 缓存。"""
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# 选线版原版模块：只读复用其直线提取、几何与清单逻辑。
linebase = _load_module('triangle_bracket_by_line',
                        os.path.join(_LINE_DIR, '端焊三角架_选线版.py'))


# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------

DEBUG_LOG = os.path.join(
    HERE, '模块', '日志', '端焊三角架_选线版_端板_debug_log.txt')

UI_TITLE = '端焊三角架（选线版·带端板）'
UI_REVISION = 'line-select-endplate-1'

# 与其它端焊三角架工具区分开的 ItemType 前缀。
ITEM_TYPE_PREFIX = 'EndWeldedTriangleBracketWithPlateByLineComponent'

# 共享支吊架清单模块所需的类型标识。
SUPPORT_TYPE = '端焊三角架'
SUPPORT_CODE = 'TRIANGLE_BRACKET'

# 直线两端 Z 的最大允许差值（mm）。超出即判定不水平并提示不合规。
HORIZONTAL_TOLERANCE_MM = linebase.HORIZONTAL_TOLERANCE_MM

# 直线的最短有效长度（mm）。
MIN_LINE_LENGTH_MM = linebase.MIN_LINE_LENGTH_MM

VARIANTS = linebase.VARIANTS
DEFAULT_VARIANT = base.DEFAULT_VARIANT
DEFAULT_END_OVERHANG = linebase.DEFAULT_END_OVERHANG
DEFAULT_PLATE_SUBTYPE = 'A'

# 端板孔距 S 的自动取整目数（mm）：S 严格大于横担截面最大边长后按 25 取整。
SPACING_STEP_MM = 25.0

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'
COMPONENT_PLATE_NAME = '端板'
COMPONENT_BRACE_PLATE_NAME = '斜撑端板'
COMPONENT_BOLT_NAME = '膨胀锚栓'
COMPONENT_BRACE_BOLT_NAME = '斜撑膨胀锚栓'

# 交付给基础模块的覆盖项：子项表、构件名、ItemType 前缀与日志文件。
base.VARIANTS = VARIANTS
base.DEFAULT_VARIANT = 'A'
base.ITEM_TYPE_PREFIX = ITEM_TYPE_PREFIX
base.H_BEAM_COMPONENT_NAME = COMPONENT_A_NAME
base.ANGLE_COMPONENT_NAME = COMPONENT_B_NAME
base.CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET_WITH_PLATE'
base.DEBUG_LOG = DEBUG_LOG

MIN_END_OVERHANG = base.MIN_END_OVERHANG
MAX_BEAM_LENGTH = base.MAX_BEAM_LENGTH

_log = base._log
_log_exception = linebase._log_exception

# 直接复用原版选线版的函数。
extract_horizontal_line = linebase.extract_horizontal_line
_make_frame = linebase._make_frame
_create_h_beam_element = linebase._create_h_beam_element
_create_angle_brace_element = linebase._create_angle_brace_element
resolve_l1 = linebase.resolve_l1
_validate = linebase._validate
_build_pipe_rack_number = linebase.build_pipe_rack_number


def _attach_result_items(cell, result):
    """把整组三角架写入共享支吊架库（整组记录 + 横担/斜撑/端板/锚栓构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec='%s + %s' % (result.get('h_beam_specification', ''),
                                   result.get('angle_specification', '')),
        components=result.get('bom_items', ()),
    )


def _variant_label(variant_key):
    variant = VARIANTS[variant_key]
    return '%s  |  %s  |  %s' % (variant_key, variant['h_beam_specification'],
                                 variant['angle_specification'])


def _plate_subtype_label(subtype):
    table = anchor.ANCHOR_TABLE[subtype]
    return ('%s  |  M%.0f×%.0f  |  板厚 %.0f  |  孔 φ%.0f'
            % (subtype, table['bolt_dia'], table['length'],
               table['plate_t'], table['hole_dia']))


def describe_spec(variant_key):
    variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
    return ('横担 %s + 斜撑 %s；斜撑位置 L1 = L2 − %.1f×√2/2 − E，'
            '直线长 L2 ≤ %.0f mm。'
            % (variant['h_beam_specification'], variant['angle_specification'],
               variant['angle'][0], MAX_BEAM_LENGTH))


def describe_plate(resolved):
    return ('端板 %.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f）；'
            'M%.0f×%.0f 膨胀锚栓 ×4，埋深 %.0f。'
            % (resolved['plate_side'], resolved['plate_side'],
               resolved['plate_t'], resolved['hole_dia'], resolved['spacing'],
               resolved['bolt_dia'], resolved['bolt_length'],
               resolved['embedment_actual']))


# ---------------------------------------------------------------------------
    # 端板几何：复用 混凝土锚板.py 的板 + 锚栓
# ---------------------------------------------------------------------------


def auto_plate_spacing(h_beam_spec, min_spacing):
    """按横担截面外形自动取孔距 S。

    取横担截面最大边长（高 / 宽中的较大者），要求 S 严格大于它，并按
    ``SPACING_STEP_MM``（25 mm）向上取整；同时不得小于该端板子项的
    MIN.S，保证锚栓边距要求。
    """
    max_dim = max(float(h_beam_spec[0]), float(h_beam_spec[1]))
    steps = math.floor(max_dim / SPACING_STEP_MM) + 1
    spacing = steps * SPACING_STEP_MM
    return max(spacing, float(min_spacing))


def _resolve_plate_options(plate_subtype, heading_deg, h_beam_spec=None):
    """校验并展开端板参数（板尺寸 / 厚度 / 孔径 / 锚栓）。

    传入 h_beam_spec（高, 宽, 腹板厚, 翼缘厚）时，孔距 S 由横担截面自动
    选取；否则沿用 G2 子项的 MIN.S。
    """
    table = anchor.ANCHOR_TABLE.get(plate_subtype)
    spacing = None
    if table is not None and h_beam_spec is not None:
        spacing = auto_plate_spacing(h_beam_spec, table['min_spacing'])
    return anchor.resolve_options({
        'subtype': plate_subtype,
        'spacing': spacing,
        'heading_deg': heading_deg,
    })


def _add_end_plate_at(builder, resolved, line, center_local, dgn_model,
                      to_world):
    """在局部坐标 center_local 处加一块 G2 正方形端板 + 4 根膨胀锚栓。

    G2 局部原点 = 板背面中心（贴既有结构面）；把该原点放到 center_local
    的模型位置，G2 的 +X 与横担方向一致，因此板面垂直于横担轴线、背面
    落在 center_local 所在竖直面（局部 x=0 平面）。
    """
    origin_mm = to_world(center_local)
    uor_per_mm = base._uor_per_mm(dgn_model)
    origin = DPoint3d.From(base.mm(origin_mm[0], dgn_model),
                           base.mm(origin_mm[1], dgn_model),
                           base.mm(origin_mm[2], dgn_model))
    frame = anchor._PlateFrame(origin, uor_per_mm, line['heading_deg'])
    anchor._add_plate(builder, frame, dgn_model, resolved)
    anchor._add_bolts(builder, frame, dgn_model, resolved)


def _brace_end_face_center(brace_origin, angle_width, mirror_z):
    """斜撑下端面（局部 x=0 竖直面）的中心。

    端面为 45° 角钢被竖直面切出的斜截面：宽度方向仍为一个肢宽（沿 y），
    高度方向为 √2×肢宽（45° 切割），故中心在肢宽/2 与 (√2/2)×肢宽 处。
    类型 2 的斜撑整体关于 mirror_z 上下镜像，端面中心同样镜像。
    """
    center_y = brace_origin[1] + angle_width / 2.0
    center_z = brace_origin[2] - angle_width * math.sqrt(2.0) / 2.0
    if mirror_z is not None:
        center_z = 2.0 * mirror_z - center_z
    return (0.0, center_y, center_z)


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


def _build_triangle_bracket_cell(line, end_overhang,
                                 variant_key=DEFAULT_VARIANT,
                                 brace_down=True, rack_number=None,
                                 add_end_plate=False,
                                 plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """按所选直线与端板选项构建整组单元但**不写入模型**。

    勾选端板时：端板占直线起点的 plate_t 厚度（局部 x ∈ [0, plate_t]），
    横担起点顺延到 plate_t、长度改为 L2 − plate_t，保证总长仍是所选直线
    长 L2；斜撑仍从焊接面（局部 x=0）按 L1 起算。返回 (builder, 统计字典)。
    """
    spec, line_length, end_overhang, brace_sweep_projection = _validate(
        line, end_overhang, variant_key)
    angle_width = spec['angle'][0]
    h_beam_height = spec['h_beam'][0]

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    resolved_plate = None
    plate_t = 0.0
    if add_end_plate:
        # 孔距 S 由横担截面自动选取；斜撑端板与横担端板完全一致（复制）。
        resolved_plate = _resolve_plate_options(plate_subtype,
                                                line['heading_deg'],
                                                spec['h_beam'])
        plate_t = float(resolved_plate['plate_t'])

    beam_start_x = plate_t
    beam_length = float(line_length) - beam_start_x
    if beam_length <= 0.0:
        raise ValueError('扣除端板厚度 %.0f mm 后横担长度 %.1f mm 不足，'
                         '请换用更长的直线或更薄的端板。'
                         % (plate_t, beam_length))

    l1 = resolve_l1(line_length, end_overhang, variant_key)

    to_world, to_world_vector = _make_frame(line['start_mm'],
                                            line['heading_deg'])
    # 横担整体沿直线方向后移 plate_t：用平移后的局部坐标系创建即可。
    heading = math.radians(line['heading_deg'])
    beam_start_mm = (line['start_mm'][0] + beam_start_x * math.cos(heading),
                     line['start_mm'][1] + beam_start_x * math.sin(heading),
                     line['start_mm'][2])
    beam_to_world, _ = _make_frame(beam_start_mm, line['heading_deg'])

    # 斜撑与端板无关，仍以焊接面（局部 x=0）为基准。
    brace_top_z = -h_beam_height
    brace_origin = (0.0, -angle_width / 2.0,
                    brace_top_z - brace_sweep_projection)
    mirror_z = None if brace_down else (-h_beam_height / 2.0)

    builder = base._TriangleBracketCellBuilder(dgn_model)
    brace = _create_angle_brace_element(
        brace_sweep_projection, brace_sweep_projection, brace_origin,
        spec['angle'], dgn_model, to_world, to_world_vector, mirror_z)
    if brace is None:
        raise RuntimeError('斜撑实体创建失败。')
    builder.add(brace)

    beam = _create_h_beam_element(
        beam_length, spec['h_beam'], dgn_model, beam_to_world,
        to_world_vector)
    if beam is None:
        raise RuntimeError('横担实体创建失败。')
    builder.add(beam)

    if resolved_plate is not None:
        # 横担端板：中心对准横担截面中心 (y=0, z=−高/2)。
        _add_end_plate_at(builder, resolved_plate, line,
                          (0.0, 0.0, -h_beam_height / 2.0),
                          dgn_model, to_world)
        # 斜撑端板：斜撑下端面（局部 x=0 竖直面）中心；与横担端板同一
        # 平面、同法向，板中心对准斜撑端面中心。
        brace_center = _brace_end_face_center(brace_origin, angle_width,
                                              mirror_z)
        _add_end_plate_at(builder, resolved_plate, line, brace_center,
                          dgn_model, to_world)

    builder.build()
    brace_length = math.hypot(brace_sweep_projection, brace_sweep_projection)
    bom_items = [
        {'code': 'HBeam', 'name': COMPONENT_A_NAME,
         'specification': spec['h_beam_specification'],
         'length': beam_length},
        {'code': 'AngleBrace', 'name': COMPONENT_B_NAME,
         'specification': spec['angle_specification'],
         'length': brace_length},
    ]
    if resolved_plate is not None:
        plate_spec = '%.0f×%.0f×%.0f（S=%.0f，4-φ%.0f）' % (
            resolved_plate['plate_side'], resolved_plate['plate_side'],
            resolved_plate['plate_t'], resolved_plate['spacing'],
            resolved_plate['hole_dia'])
        bolt_spec = 'M%.0f×%.0f' % (
            resolved_plate['bolt_dia'], resolved_plate['bolt_length'])
        bom_items.append({
            'code': 'EndPlate', 'name': COMPONENT_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceEndPlate', 'name': COMPONENT_BRACE_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'AnchorBolt', 'name': COMPONENT_BOLT_NAME,
            'specification': bolt_spec,
            'length': resolved_plate['bolt_length'],
            'quantity': 4, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceAnchorBolt', 'name': COMPONENT_BRACE_BOLT_NAME,
            'specification': bolt_spec,
            'length': resolved_plate['bolt_length'],
            'quantity': 4, 'unit': '件',
        })

    result = {
        'variant': variant_key,
        'child_count': builder.child_count,
        'line_length': line_length,
        'end_overhang': end_overhang,
        'l1': l1,
        'heading_deg': line['heading_deg'],
        'brace_length': brace_length,
        'brace_down': bool(brace_down),
        'rack_type': 1 if brace_down else 2,
        'pipe_rack_number': rack_number or '',
        'beam_start_x': beam_start_x,
        'beam_length': beam_length,
        'end_plate': (dict(resolved_plate) if resolved_plate else None),
        'brace_end_plate': (dict(resolved_plate) if resolved_plate else None),
        'h_beam_specification': spec['h_beam_specification'],
        'angle_specification': spec['angle_specification'],
        'bom_items': bom_items,
        'warnings': list(builder.warnings),
    }
    _log('bracket by line with plate: variant=%s, type=%d, L2=%.1f, E=%.1f, '
         'L1=%.1f, beamStart=%.1f, beamLen=%.1f, plate=%s, heading=%.2f, '
         'cells=%d, rack=%s' %
         (variant_key, result['rack_type'], line_length, end_overhang, l1,
          beam_start_x, beam_length,
          plate_subtype if resolved_plate else '-', line['heading_deg'],
          builder.child_count, result['pipe_rack_number'] or '-'))
    return builder, result


def replace_end_welded_triangle_bracket(line, end_overhang, previous_handle,
                                        variant_key=DEFAULT_VARIANT,
                                        brace_down=True, rack_number=None,
                                        add_end_plate=False,
                                        plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """重建整组：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    new_handle = builder.commit()
    _attach_result_items(new_handle, result)
    deleted = base._delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_end_welded_triangle_bracket(line, end_overhang,
                                     variant_key=DEFAULT_VARIANT,
                                     brace_down=True, rack_number=None,
                                     add_end_plate=False,
                                     plate_subtype=DEFAULT_PLATE_SUBTYPE):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    cell = builder.commit()
    _attach_result_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。

    清单里会同时包含端焊三角架、L 型管架以及今后接入的其它支吊架。
    """
    if output_path is None:
        output_path = os.path.join(
            HERE, '模块', '输出', '端焊三角架_选线版_端板_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 工具设置面板
# ---------------------------------------------------------------------------


class _BracketByLinePlateSettingsDialog(QWidget):
    """子项 / E / 端板 / 编号 / 保留直线 选择，预览 / 确定 / 取消面板。"""

    RADIUS = base.UI_RADIUS

    def __init__(self):
        self._app = base.ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
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
        outer.addWidget(base.NeuTitleBar(UI_TITLE, self._minimize,
                                         self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点选一条水平直线段作为横担上表面（即整组支架最高点）："
                      "起点为焊接端面，终点为横担末端，直线方向即横担方向。"
                      "直线两端 Z 必须一致。勾选【创建端板】后，会在直线起点放端板"
                      "（横担 + 斜撑各一块，含 4 根锚栓），孔距 S 按横担截面自动取整，"
                      "横担相应缩短端板厚度。点取后可改 E / 子项 / 端板，预览会自动重建；"
                      "点【确定】保留，点【取消】或右键放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = base.NeuCard("构件规格")
        self.variant_combo = self._register(base.NeuCombo(
            [(key, _variant_label(key)) for key in sorted(VARIANTS)],
            current=DEFAULT_VARIANT, on_change=self.on_options_changed))
        self._row(card.content, 0, "子项：", [self.variant_combo], 16)
        self.beam_label = self._value()
        self._row(card.content, 1, "构件A（横担）：", [self.beam_label])
        self.angle_label = self._value()
        self._row(card.content, 2, "构件B（斜撑）：", [self.angle_label])
        body.addWidget(card)

        card = base.NeuCard("尺寸参数")
        self.overhang_edit = self._edit_row(
            card.content, 0, "E：", '%.0f' % DEFAULT_END_OVERHANG,
            "mm　横担最远端至斜撑上端外侧斜角（≥150）")
        self.length_label = self._value()
        self._row(card.content, 1, "直线长 L2：",
                  [self.length_label, self._note("mm　由所选直线自动读取")], 8)
        self.l1_label = self._value()
        self._row(card.content, 2, "斜撑位置 L1：",
                  [self.l1_label, self._note("mm　= L2 − 肢宽×√2/2 − E")], 8)
        self.beam_length_label = self._value()
        self._row(card.content, 3, "横担长：",
                  [self.beam_length_label,
                   self._note("mm　= L2 − 端板厚（未勾选端板时即 L2）")], 8)
        body.addWidget(card)

        card = base.NeuCard("端板")
        self.plate_toggle = base.NeuToggle("创建端板（横担 + 斜撑各一块，含 4 锚栓）")
        self.plate_toggle.setChecked(False)
        self.plate_toggle.toggled.connect(self.on_plate_changed)
        card.content.addWidget(self.plate_toggle, 0, 0, 1, 2)
        self.plate_combo = self._register(base.NeuCombo(
            [(key, _plate_subtype_label(key))
             for key in sorted(anchor.ANCHOR_TABLE)],
            current=DEFAULT_PLATE_SUBTYPE, on_change=self.on_plate_changed))
        self._row(card.content, 1, "端板子项：", [self.plate_combo], 16)
        self.plate_label = self._value()
        self._row(card.content, 2, "端板：", [self.plate_label])
        self.plate_bolt_label = self._value()
        self._row(card.content, 3, "锚栓：", [self.plate_bolt_label])
        body.addWidget(card)

        card = base.NeuCard("管架编号")
        self.rack_name_edit = self._edit_row(
            card.content, 0, "名称：", 'D5', "管架系列代号；留空则不附加编号")
        self.rack_type_combo = self._register(base.NeuCombo(
            [(1, '类型1  |  斜撑向下'), (2, '类型2  |  斜撑向上')],
            current=1, on_change=self.on_options_changed))
        self._row(card.content, 1, "类型：", [self.rack_type_combo], 16)
        self.rack_label = self._value()
        self._row(card.content, 2, "编号：",
                  [self.rack_label, self._note("名称-类型-子项-L1-L2（整数）")], 8)
        body.addWidget(card)

        card = base.NeuCard("创建选项")
        self.keep_toggle = self._register(base.NeuToggle("创建后保留所选直线"))
        self.keep_toggle.setChecked(True)
        card.content.addWidget(self.keep_toggle, 0, 0, 1, 2)
        body.addWidget(card)

        summary = base.NeuPanel()
        self.spec_label = self._info("", base.UI_TEXT)
        summary.content.addWidget(self.spec_label)
        self.plate_info_label = self._info("端板：未创建", base.UI_TEXT)
        summary.content.addWidget(self.plate_info_label)
        self.preview_info_label = self._info("预览：—", base.UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点选一条水平直线段；改参数会自动重建预览。",
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
            return DEFAULT_VARIANT
        return self.variant_combo.value() or DEFAULT_VARIANT

    def current_rack_type(self):
        if self.rack_type_combo is None:
            return 1
        try:
            return int(self.rack_type_combo.value())
        except (TypeError, ValueError):
            return 1

    def current_add_end_plate(self):
        return self.plate_toggle.isChecked()

    def current_plate_subtype(self):
        if self.plate_combo is None:
            return DEFAULT_PLATE_SUBTYPE
        return self.plate_combo.value() or DEFAULT_PLATE_SUBTYPE

    def current_options(self):
        variant_key = self.current_variant()
        if variant_key not in VARIANTS:
            raise ValueError('未知子项：%s。' % variant_key)
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            raise ValueError('E 必须是数字（mm）。')
        if end_overhang < MIN_END_OVERHANG:
            raise ValueError('E 不得小于 %.0f mm。' % MIN_END_OVERHANG)
        return {
            'variant': variant_key,
            'end_overhang': end_overhang,
            'brace_down': self.current_rack_type() == 1,
            'rack_name': self.rack_name_edit.value().strip(),
            'rack_type': self.current_rack_type(),
            'add_end_plate': self.current_add_end_plate(),
            'plate_subtype': self.current_plate_subtype(),
        }

    def current_rack_number(self, line=None):
        """按当前直线 / 子项 / E / 名称 / 类型合成管架编号；无直线时返回 ''。"""
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            return ''
        variant_key = self.current_variant()
        l2 = line['length_mm']
        l1 = resolve_l1(l2, end_overhang, variant_key)
        return _build_pipe_rack_number(self.rack_name_edit.value(),
                                       self.current_rack_type(), variant_key,
                                       l1, l2)

    def set_status(self, message, is_error=False, flush=True):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        if flush:
            QApplication.processEvents()

    def set_result(self, result):
        plate = result.get('end_plate')
        if plate:
            self.plate_info_label.setText(
                "端板：%s 子项，%.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f 自动），"
                "横担 + 斜撑各一块，每块 M%.0f×%.0f 锚栓 ×4；"
                "横担自 %.0f mm 起，长 %.0f mm。"
                % (plate['subtype'], plate['plate_side'], plate['plate_side'],
                   plate['plate_t'], plate['hole_dia'], plate['spacing'],
                   plate['bolt_dia'], plate['bolt_length'],
                   result['beam_start_x'], result['beam_length']))
        else:
            self.plate_info_label.setText("端板：未创建（横担长即 L2）。")
        number = result.get('pipe_rack_number') or '—'
        self.preview_info_label.setText(
            "预览：子项 %s，类型 %d，横担 %s，L2=%.0f mm，L1=%.0f mm，"
            "E=%.0f mm，斜撑轴长 %.0f mm，单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'],
                result['h_beam_specification'], result['line_length'],
                result['l1'], result['end_overhang'], result['brace_length'],
                result['child_count'], number,
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
        self.beam_label.setText(variant['h_beam_specification'])
        self.angle_label.setText('%s（45°）' % variant['angle_specification'])
        self.spec_label.setText(describe_spec(variant_key))
        self._sync_plate_widgets()
        self.refresh_line_labels()

    def _sync_plate_widgets(self):
        enabled = self.current_add_end_plate()
        self.plate_combo.setEnabled(enabled)
        if not enabled:
            self.plate_label.setText('—')
            self.plate_bolt_label.setText('—')
            self.plate_info_label.setText("端板：未创建")
            return
        subtype = self.current_plate_subtype()
        table = anchor.ANCHOR_TABLE.get(subtype)
        if table is None:
            self.plate_label.setText('—')
            self.plate_bolt_label.setText('—')
            return
        variant = VARIANTS.get(self.current_variant(),
                               VARIANTS[DEFAULT_VARIANT])
        resolved = _resolve_plate_options(subtype, 0.0, variant['h_beam'])
        self.plate_label.setText(
            '%.0f×%.0f×%.0f（板厚 T=%.0f，孔距 S=%.0f 自动）' % (
                resolved['plate_side'], resolved['plate_side'],
                resolved['plate_t'], resolved['plate_t'],
                resolved['spacing']))
        self.plate_bolt_label.setText(
            'M%.0f×%.0f 膨胀锚栓，每块 4 根，孔径 φ%.0f' % (
                resolved['bolt_dia'], resolved['bolt_length'],
                resolved['hole_dia']))
        self.plate_info_label.setText(
            '端板：横担 + 斜撑各一块（同规格，S 按横担截面自动取）；%s'
            % describe_plate(resolved))

    def _show_line_values(self, line):
        """显示给定直线的 L2、按当前子项 / E 反算的 L1 与管架编号。"""
        if line is None:
            self.length_label.setText('—')
            self.l1_label.setText('—')
            self.beam_length_label.setText('—')
            self.rack_label.setText('—')
            return
        length = line['length_mm']
        self.length_label.setText('%.1f' % length)
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            self.l1_label.setText('—')
            self.beam_length_label.setText('—')
            self.rack_label.setText('—')
            return
        self.l1_label.setText(
            '%.1f' % resolve_l1(length, end_overhang, self.current_variant()))
        plate_t = 0.0
        if self.current_add_end_plate():
            table = anchor.ANCHOR_TABLE.get(self.current_plate_subtype())
            if table is not None:
                plate_t = float(table['plate_t'])
        self.beam_length_label.setText('%.1f' % (length - plate_t))
        number = self.current_rack_number(line)
        self.rack_label.setText(number if number else '（名称留空，不附加）')

    def refresh_line_labels(self):
        """按当前所选直线与 E 刷新 L2 / L1 / 编号显示。"""
        self._show_line_values(self.line)

    def _set_busy(self, busy):
        for widget in self.option_widgets + self.action_widgets:
            widget.setEnabled(not busy)
        if not busy:
            self._sync_plate_widgets()
        QApplication.processEvents()

    def on_options_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._regen_timer)

    def on_plate_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._regen_timer)

    def on_text_changed(self, *_unused):
        self.refresh_spec()
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
        """悬停到一条合规直线上：只刷新数值显示，不改变已选定的直线。"""
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

        rack_number = self.current_rack_number()

        self._set_busy(True)
        self.set_status('正在生成端焊三角架预览，请稍候……')
        try:
            handle, result, deleted = replace_end_welded_triangle_bracket(
                self.line, options['end_overhang'], self.preview_handle,
                options['variant'], options['brace_down'], rack_number,
                options['add_end_plate'], options['plate_subtype'])
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
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
        plate_note = ('含端板 ×2（横担 + 斜撑，%s）'
                      % result['end_plate']['subtype']
                      if result['end_plate'] else '不含端板')
        message = (
            "预览已更新：子项 %s，类型 %d，%s，横担 %s，L2=%.0f mm，"
            "L1=%.0f mm，单元含 %d 个子元素，编号 %s。%s改参数会自动重建；"
            "点【确定】保留，点【取消】放弃。"
            % (result['variant'], result['rack_type'], plate_note,
               result['h_beam_specification'], result['line_length'],
               result['l1'], result['child_count'],
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
        return base._delete_preview(handle)

    def delete_source_line(self):
        """按“创建后保留所选直线”开关，删除用户所选直线。"""
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
        PyCommandState.StartDefaultCommand()

    def shutdown(self):
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            pass

    # -- 窗口 --------------------------------------------------------------

    def _minimize(self):
        self.showMinimized()

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
        # 关窗口等同于取消：先撤掉预览，再由主循环退出原生工具。
        event.ignore()
        self.cancel_tool()

    def run_dialog_loop(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x()-self.width()//2,
                      area.center().y()-self.height()//2)
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


# ---------------------------------------------------------------------------
# 交互工具：点选水平直线
# ---------------------------------------------------------------------------


class BracketByLinePlateTool(DgnElementSetTool):
    """点选一条水平直线段并放置端焊三角架（可选端板）的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('EndWeldedTriangleBracketByLineWithPlateTool')

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
            '请点选一条水平直线段作为横担上表面（起点为焊接端面，终点为横担末端）；'
            '直线两端 Z 必须一致。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            line = extract_horizontal_line(handle)
            if self.tool_settings is not None:
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                self.tool_settings.set_status(str(error), True, flush=False)
            return False

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_horizontal_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
            self.tool_settings.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('element modify failed')
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        BracketByLinePlateTool.InstallNewInstance(self.GetToolId(), settings,
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
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        settings = (tool_settings if tool_settings is not None
                    else _BracketByLinePlateSettingsDialog())
        tool = BracketByLinePlateTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        if start_ui_loop:
            settings.run_dialog_loop()
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    try:
        BracketByLinePlateTool.InstallNewInstance(0)
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('端焊三角架（选线版·带端板）工具启动失败：%s\n%s' % (error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE, '工具启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


show_triangle_bracket_dialog = PyMain


if __name__ == '__main__':
    PyMain()
