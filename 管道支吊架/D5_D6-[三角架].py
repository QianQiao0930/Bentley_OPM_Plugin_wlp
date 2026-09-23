# -*- coding: utf-8 -*-
"""三角架（端焊三角架 · 选线版 + 可选端板）放置工具。

在模型中点选一条**水平直线段**作为横担上表面（整组最高点）：

    起点 = 横担焊接端面的上表面中点（与既有钢结构的焊接面）
    终点 = 横担最远端的上表面中点
    直线长度 = 横担总长 L2；直线方向（XY 内）= 横担方向

可选「创建端板」：在直线起点放端板（横担 + 斜撑各一块，含 4 根膨胀锚栓），
孔距 S 按横担截面自动取整，横担相应缩短端板厚度。整组写成一个普通单元，
清单写入**管道支吊架公共库**，可导出 JSON / Excel。

几何 / 数据逻辑集中在 ``模块/端焊三角架/端焊三角架_选线_几何.py``；本文件负责
Tkinter 面板与交互工具、拼装整组单元并写入公共支吊架库，外观沿用仓库共享的
``bentley_ui``。
本文件不依赖早期插件 ``端焊三角架_选线版.py``，也不再使用 PyQt5。

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

# 通配导入不一定导出这两个符号，显式再导入一次。
from MSPyBentley import WString  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 公共库在 模块/公共/；纯几何模块在 模块/端焊三角架/；仓库根提供 bentley_ui。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '端焊三角架')
for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR):
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

import 端焊三角架_选线_几何 as geom  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


UI_TITLE = 'D5_D6-[三角架]'
UI_REVISION = 'tk-1'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 选项变化后延迟重建的毫秒数。
REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750


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


_FAULT_FILE = None


def _enable_fault_logging():
    global _FAULT_FILE
    try:
        if _FAULT_FILE is None:
            path = os.path.join(HERE, '模块', '日志', '三角架_fault.log')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _FAULT_FILE = open(path, 'a', encoding='utf-8')
            faulthandler.enable(_FAULT_FILE)
        _FAULT_FILE.write(
            '=== session start %s rev=%s ===\n'
            % (time.strftime('%Y-%m-%d %H:%M:%S'), UI_REVISION))
        _FAULT_FILE.flush()
        faulthandler.dump_traceback_later(8.0, repeat=True, file=_FAULT_FILE)
    except Exception:
        pass


def _disable_fault_logging():
    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass


def _reload_runtime_modules():
    importlib.invalidate_caches()
    try:
        importlib.reload(geom)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 面板（Tkinter / bentley_ui）
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _TriangleBracketCellBuilder(object):
    """收集端焊三角架子元素，全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell_name = cell_name or geom.CELL_NAME
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('三角架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not geom._succeeded(status):
            raise RuntimeError('无法将三角架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not geom._succeeded(status):
            raise RuntimeError('无法完成端焊三角架单元。')
        return self.child_count

    def commit(self):
        if not geom._succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法将端焊三角架单元写入活动模型。')
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
# 构建整组（选线版 + 可选端板）
# ---------------------------------------------------------------------------


def _build_triangle_bracket_cell(line, end_overhang,
                                 variant_key=geom.DEFAULT_VARIANT,
                                 brace_down=True, rack_number=None,
                                 add_end_plate=False,
                                 plate_subtype=geom.DEFAULT_PLATE_SUBTYPE):
    """按所选直线与端板选项构建整组单元但**不写入模型**。

    返回 ``(builder, 统计字典)``。
    """
    spec, line_length, end_overhang, brace_sweep_projection = geom._validate(
        line, end_overhang, variant_key)
    angle_width = spec['angle'][0]
    h_beam_height = spec['h_beam'][0]

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    resolved_plate = None
    plate_t = 0.0
    if add_end_plate:
        resolved_plate = geom._resolve_plate_options(plate_subtype,
                                                line['heading_deg'],
                                                spec['h_beam'])
        plate_t = float(resolved_plate['plate_t'])

    beam_start_x = plate_t
    beam_length = float(line_length) - beam_start_x
    if beam_length <= 0.0:
        raise ValueError('扣除端板厚度 %.0f mm 后横担长度 %.1f mm 不足，'
                         '请换用更长的直线或更薄的端板。'
                         % (plate_t, beam_length))

    l1 = geom.resolve_l1(line_length, end_overhang, variant_key)

    to_world, to_world_vector = geom._make_frame(line['start_mm'],
                                            line['heading_deg'])
    heading = math.radians(line['heading_deg'])
    beam_start_mm = (line['start_mm'][0] + beam_start_x * math.cos(heading),
                     line['start_mm'][1] + beam_start_x * math.sin(heading),
                     line['start_mm'][2])
    beam_to_world, _ = geom._make_frame(beam_start_mm, line['heading_deg'])

    brace_top_z = -h_beam_height
    brace_origin = (0.0, -angle_width / 2.0,
                    brace_top_z - brace_sweep_projection)
    mirror_z = None if brace_down else (-h_beam_height / 2.0)

    builder = _TriangleBracketCellBuilder(dgn_model)
    brace = geom._create_angle_brace_element(
        brace_sweep_projection, brace_sweep_projection, brace_origin,
        spec['angle'], dgn_model, to_world, to_world_vector, mirror_z)
    if brace is None:
        raise RuntimeError('斜撑实体创建失败。')
    builder.add(brace)

    beam = geom._create_h_beam_element(
        beam_length, spec['h_beam'], dgn_model, beam_to_world,
        to_world_vector)
    if beam is None:
        raise RuntimeError('横担实体创建失败。')
    builder.add(beam)

    if resolved_plate is not None:
        geom._add_end_plate_at(builder, resolved_plate, line,
                          (0.0, 0.0, -h_beam_height / 2.0),
                          dgn_model, to_world)
        brace_center = geom._brace_end_face_center(brace_origin, angle_width,
                                              mirror_z)
        geom._add_end_plate_at(builder, resolved_plate, line, brace_center,
                          dgn_model, to_world)

    builder.build()
    brace_length = math.hypot(brace_sweep_projection, brace_sweep_projection)
    bom_items = [
        {'code': 'HBeam', 'name': geom.COMPONENT_A_NAME,
         'specification': spec['h_beam_specification'],
         'length': beam_length},
        {'code': 'AngleBrace', 'name': geom.COMPONENT_B_NAME,
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
            'code': 'EndPlate', 'name': geom.COMPONENT_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceEndPlate', 'name': geom.COMPONENT_BRACE_PLATE_NAME,
            'specification': plate_spec, 'length': resolved_plate['plate_t'],
            'quantity': 1, 'unit': '件',
        })
        bom_items.append({
            'code': 'AnchorBolt', 'name': geom.COMPONENT_BOLT_NAME,
            'specification': bolt_spec,
            'length': resolved_plate['bolt_length'],
            'quantity': 4, 'unit': '件',
        })
        bom_items.append({
            'code': 'BraceAnchorBolt', 'name': geom.COMPONENT_BRACE_BOLT_NAME,
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


def _attach_result_items(cell, result):
    """把整组三角架写入共享支吊架库（整组记录 + 各构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=geom.SUPPORT_TYPE,
        support_code=geom.SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec='%s + %s' % (result.get('h_beam_specification', ''),
                                   result.get('angle_specification', '')),
        components=result.get('bom_items', ()),
    )


def replace_end_welded_triangle_bracket(line, end_overhang, previous_handle,
                                        variant_key=geom.DEFAULT_VARIANT,
                                        brace_down=True, rack_number=None,
                                        add_end_plate=False,
                                        plate_subtype=geom.DEFAULT_PLATE_SUBTYPE):
    """重建整组：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    new_handle = builder.commit()
    _attach_result_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def draw_end_welded_triangle_bracket(line, end_overhang,
                                     variant_key=geom.DEFAULT_VARIANT,
                                     brace_down=True, rack_number=None,
                                     add_end_plate=False,
                                     plate_subtype=geom.DEFAULT_PLATE_SUBTYPE):
    """直接创建整组单元并写入模型，返回 (cell, 统计字典)。"""
    builder, result = _build_triangle_bracket_cell(
        line, end_overhang, variant_key, brace_down, rack_number,
        add_end_plate, plate_subtype)
    cell = builder.commit()
    _attach_result_items(cell, result)
    return cell, result


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '三角架_bom.json')
    return psb.export_combined_bom(output_path)


class _TriangleBracketDialog(GlassDialog):
    """子项 / E / 端板 / 编号 / 保留直线 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'TriangleBracketByLinePlate'
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        # 原生回调只写 Python 状态；所有 Tk 刷新由常驻定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._hover_line = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False

        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._plate_subtype = tk.StringVar()
        self._rack_name = tk.StringVar(value='D5')
        self._overhang = tk.StringVar(value='%.0f' % geom.DEFAULT_END_OVERHANG)
        self._add_plate = tk.BooleanVar(value=False)
        self._keep_line = tk.BooleanVar(value=True)
        self._beam = tk.StringVar(value='—')
        self._angle = tk.StringVar(value='—')
        self._length = tk.StringVar(value='—')
        self._l1 = tk.StringVar(value='—')
        self._beam_length = tk.StringVar(value='—')
        self._plate_dim = tk.StringVar(value='—')
        self._plate_bolt = tk.StringVar(value='—')
        self._rack_number = tk.StringVar(value='—')
        self._variant_by_label = {}
        self._rack_type_by_label = {}
        self._plate_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()
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
            '点选一条水平直线（横担上表面）· E / 端板可选，自动预览')
        shell_form.columnconfigure(0, weight=1)
        shell_form.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(shell_form, bg=CARD, height=340)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(1, weight=1)

        hint_frame, hint_text = self._text_field(body, height=2)
        hint_frame.grid(row=0, column=0, columnspan=2, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一条水平直线段作为横担上表面（整组最高点）：起点为'
            '焊接端面，终点为横担末端，直线两端 Z 必须一致。勾选【创建端板】后'
            '会在直线起点放端板（横担 + 斜撑各一块，含 4 根锚栓），孔距 S 按'
            '横担截面自动取整，横担相应缩短端板厚度。点取后可改 E / 子项 / '
            '端板，预览会自动重建；点【确定】保留，点【取消】或右键放弃。'))

        ttk.Label(body, text='构件规格', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(6, 2))

        ttk.Label(body, text='子项', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=3)
        labels = []
        for key in sorted(geom.VARIANTS):
            label = geom.variant_label(key)
            labels.append(label)
            self._variant_by_label[label] = key
        self._variant_combo = ttk.Combobox(
            body, textvariable=self._variant, state='readonly', width=30,
            style='Glass.TCombobox', values=labels)
        self._variant_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0),
                                 pady=3)
        self._variant_combo.bind('<<ComboboxSelected>>',
                                 self.on_options_changed)

        ttk.Label(body, text='构件A（横担）', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._beam, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=3, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(body, text='构件B（斜撑）', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._angle, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=5, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(body, text='尺寸参数', style='Section.TLabel').grid(
            row=6, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(body, text='E', style='GlassMuted.TLabel').grid(
            row=7, column=0, sticky='nw', pady=3)
        e_holder = tk.Frame(body, bg=CARD)
        e_holder.grid(row=7, column=1, sticky='w', padx=(10, 0), pady=3)
        e_input = tk.Frame(e_holder, bg=CARD)
        e_input.pack(anchor='w')
        self._overhang_entry = self._entry(e_input, self._overhang, 9)
        tk.Label(e_holder, text='mm　横担最远端至斜撑上端外侧斜角（≥150）',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w',
                                                             pady=(1, 0))

        ttk.Label(body, text='直线长 L2', style='GlassMuted.TLabel').grid(
            row=8, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._length, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=8, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(body, text='斜撑位置 L1', style='GlassMuted.TLabel').grid(
            row=9, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._l1, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=9, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(body, text='横担长', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._beam_length, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=10, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=11, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(body, text='端板', style='Section.TLabel').grid(
            row=12, column=0, columnspan=2, sticky='w', pady=(0, 2))
        self._plate_check = tk.Checkbutton(
            body, text='创建端板（横担 + 斜撑各一块，含 4 锚栓）',
            variable=self._add_plate, command=self.on_plate_changed,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._plate_check.grid(row=13, column=0, columnspan=2, sticky='w')

        ttk.Label(body, text='端板子项', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='w', pady=3)
        plate_labels = []
        for key in sorted(anchor.ANCHOR_TABLE):
            label = geom.plate_subtype_label(key)
            plate_labels.append(label)
            self._plate_by_label[label] = key
        self._plate_combo = ttk.Combobox(
            body, textvariable=self._plate_subtype, state='disabled', width=30,
            style='Glass.TCombobox', values=plate_labels)
        self._plate_combo.grid(row=14, column=1, sticky='ew', padx=(10, 0),
                               pady=3)
        self._plate_combo.bind('<<ComboboxSelected>>', self.on_plate_changed)

        ttk.Label(body, text='端板', style='GlassMuted.TLabel').grid(
            row=15, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._plate_dim, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=15, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(body, text='锚栓', style='GlassMuted.TLabel').grid(
            row=16, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._plate_bolt, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=16, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=17, column=0, columnspan=2, sticky='ew', pady=6)

        ttk.Label(body, text='管架编号', style='Section.TLabel').grid(
            row=18, column=0, columnspan=2, sticky='w', pady=(0, 2))

        ttk.Label(body, text='名称', style='GlassMuted.TLabel').grid(
            row=19, column=0, sticky='nw', pady=3)
        name_holder = tk.Frame(body, bg=CARD)
        name_holder.grid(row=19, column=1, sticky='w', padx=(10, 0), pady=3)
        name_input = tk.Frame(name_holder, bg=CARD)
        name_input.pack(anchor='w')
        self._rack_name_entry = self._entry(name_input, self._rack_name, 12)
        tk.Label(name_holder, text='管架系列代号；留空则不附加编号', bg=CARD,
                 fg=MUTED, font=UI_FONT_SMALL).pack(anchor='w', pady=(1, 0))

        ttk.Label(body, text='类型', style='GlassMuted.TLabel').grid(
            row=20, column=0, sticky='w', pady=3)
        type_labels = []
        for key, label in ((1, '类型1  |  斜撑向下'), (2, '类型2  |  斜撑向上')):
            type_labels.append(label)
            self._rack_type_by_label[label] = key
        self._rack_type_combo = ttk.Combobox(
            body, textvariable=self._rack_type, state='readonly', width=30,
            style='Glass.TCombobox', values=type_labels)
        self._rack_type_combo.grid(row=20, column=1, sticky='ew',
                                   padx=(10, 0), pady=3)
        self._rack_type_combo.bind('<<ComboboxSelected>>',
                                   self.on_options_changed)

        ttk.Label(body, text='编号', style='GlassMuted.TLabel').grid(
            row=21, column=0, sticky='w', pady=3)
        tk.Label(body, textvariable=self._rack_number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=21, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Separator(body, orient='horizontal').grid(
            row=22, column=0, columnspan=2, sticky='ew', pady=6)

        self._keep_check = tk.Checkbutton(
            body, text='创建后保留所选直线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.grid(row=23, column=0, columnspan=2, sticky='w')

        # 说明 / 端板 / 预览 / 状态固定在滚动区下方，始终可见。
        info = tk.Frame(shell_form, bg=CARD)
        info.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self._spec_frame, self._spec_text = self._text_field(info, height=2)
        self._spec_frame.pack(fill='x')
        self._plate_frame, self._plate_text = self._text_field(info, height=2)
        self._plate_frame.pack(fill='x', pady=(4, 0))
        self._preview_frame, self._preview_text = self._text_field(info,
                                                                   height=2)
        self._preview_frame.pack(fill='x', pady=(4, 0))
        self._status_frame, self._status_text = self._text_field(info, height=2)
        self._status_frame.pack(fill='x', pady=(4, 0))
        self._set_text(self._plate_text, '端板：未创建')
        self._set_text(self._preview_text, '预览：—')
        self._set_text(self._status_text,
                       '请在模型中点选一条水平直线段；改参数会自动重建预览。')

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

        self._overhang.trace_add('write', self.on_text_changed)
        self._rack_name.trace_add('write', self.on_text_changed)
        self._bind_wheel(self._scroll)

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

    def _bind_wheel(self, scroll):
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

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = None
        fallback = None
        for label, key in self._variant_by_label.items():
            if fallback is None:
                fallback = label
            if key == geom.DEFAULT_VARIANT:
                fallback = label
            if key == state.get('variant'):
                selected = label
        self._variant.set(selected or fallback)

        selected_type = None
        fallback_type = None
        for label, key in self._rack_type_by_label.items():
            if fallback_type is None:
                fallback_type = label
            if key == state.get('rack_type'):
                selected_type = label
        self._rack_type.set(selected_type or fallback_type)

        selected_plate = None
        fallback_plate = None
        for label, key in self._plate_by_label.items():
            if fallback_plate is None:
                fallback_plate = label
            if key == geom.DEFAULT_PLATE_SUBTYPE:
                fallback_plate = label
            if key == state.get('plate_subtype'):
                selected_plate = label
        self._plate_subtype.set(selected_plate or fallback_plate)

        value = state.get('overhang')
        if isinstance(value, str) and value.strip():
            self._overhang.set(value)
        name = state.get('rack_name')
        if isinstance(name, str):
            self._rack_name.set(name)
        if isinstance(state.get('add_plate'), bool):
            self._add_plate.set(state.get('add_plate'))
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['plate_subtype'] = self.current_plate_subtype()
            state['rack_name'] = self._rack_name.get()
            state['overhang'] = self._overhang.get()
            state['add_plate'] = bool(self._add_plate.get())
            state['keep_line'] = bool(self._keep_line.get())
        except tk.TclError:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(
            self._variant.get(), geom.DEFAULT_VARIANT)

    def current_rack_type(self):
        return self._rack_type_by_label.get(self._rack_type.get(), 1)

    def current_plate_subtype(self):
        return self._plate_by_label.get(
            self._plate_subtype.get(), geom.DEFAULT_PLATE_SUBTYPE)

    def current_add_end_plate(self):
        return bool(self._add_plate.get())

    def current_options(self):
        variant_key = self.current_variant()
        if variant_key not in geom.VARIANTS:
            raise ValueError('未知子项：%s。' % variant_key)
        try:
            end_overhang = float((self._overhang.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('E 必须是数字（mm）。')
        if end_overhang < geom.MIN_END_OVERHANG:
            raise ValueError('E 不得小于 %.0f mm。' % geom.MIN_END_OVERHANG)
        return {
            'variant': variant_key,
            'end_overhang': end_overhang,
            'brace_down': self.current_rack_type() == 1,
            'rack_name': self._rack_name.get().strip(),
            'rack_type': self.current_rack_type(),
            'add_end_plate': self.current_add_end_plate(),
            'plate_subtype': self.current_plate_subtype(),
        }

    def current_rack_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            end_overhang = float((self._overhang.get() or '').strip())
        except (TypeError, ValueError):
            return ''
        variant_key = self.current_variant()
        l2 = line['length_mm']
        l1 = geom.resolve_l1(l2, end_overhang, variant_key)
        return geom.build_pipe_rack_number(
            self._rack_name.get(), self.current_rack_type(), variant_key,
            l1, l2)

    # -- 显示 --------------------------------------------------------------

    def set_status(self, message, is_error=False, flush=True):
        self._set_text(getattr(self, '_status_text', None), message)

    def set_result(self, result):
        plate = result.get('end_plate')
        if plate:
            self._set_text(self._plate_text,
                "端板：%s 子项，%.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f 自动），"
                "横担 + 斜撑各一块，每块 M%.0f×%.0f 锚栓 ×4；"
                "横担自 %.0f mm 起，长 %.0f mm。"
                % (plate['subtype'], plate['plate_side'], plate['plate_side'],
                   plate['plate_t'], plate['hole_dia'], plate['spacing'],
                   plate['bolt_dia'], plate['bolt_length'],
                   result['beam_start_x'], result['beam_length']))
        else:
            self._set_text(self._plate_text, '端板：未创建（横担长即 L2）。')
        number = result.get('pipe_rack_number') or '—'
        self._set_text(self._preview_text,
            "预览：子项 %s，类型 %d，横担 %s，L2=%.0f mm，L1=%.0f mm，"
            "E=%.0f mm，斜撑轴长 %.0f mm，单元含 %d 个子元素；编号 %s。" % (
                result['variant'], result['rack_type'],
                result['h_beam_specification'], result['line_length'],
                result['l1'], result['end_overhang'], result['brace_length'],
                result['child_count'], number))

    def refresh_spec(self):
        variant_key = self.current_variant()
        variant = geom.VARIANTS.get(variant_key,
                                    geom.VARIANTS[geom.DEFAULT_VARIANT])
        self._beam.set(variant['h_beam_specification'])
        self._angle.set('%s（45°）' % variant['angle_specification'])
        self._set_text(self._spec_text, geom.describe_spec(variant_key))
        self._sync_plate_widgets()
        self.refresh_line_labels()

    def _sync_plate_widgets(self):
        enabled = self.current_add_end_plate()
        try:
            self._plate_combo.configure(
                state='readonly' if enabled else 'disabled')
        except tk.TclError:
            pass
        if not enabled:
            self._plate_dim.set('—')
            self._plate_bolt.set('—')
            self._set_text(self._plate_text, '端板：未创建')
            return
        subtype = self.current_plate_subtype()
        table = anchor.ANCHOR_TABLE.get(subtype)
        if table is None:
            self._plate_dim.set('—')
            self._plate_bolt.set('—')
            return
        variant = geom.VARIANTS.get(self.current_variant(),
                                    geom.VARIANTS[geom.DEFAULT_VARIANT])
        resolved = geom._resolve_plate_options(subtype, 0.0, variant['h_beam'])
        self._plate_dim.set(
            '%.0f×%.0f×%.0f（板厚 T=%.0f，孔距 S=%.0f 自动）' % (
                resolved['plate_side'], resolved['plate_side'],
                resolved['plate_t'], resolved['plate_t'],
                resolved['spacing']))
        self._plate_bolt.set(
            'M%.0f×%.0f 膨胀锚栓，每块 4 根，孔径 φ%.0f' % (
                resolved['bolt_dia'], resolved['bolt_length'],
                resolved['hole_dia']))
        self._set_text(self._plate_text,
            '端板：横担 + 斜撑各一块（同规格，S 按横担截面自动取）；%s'
            % geom.describe_plate(resolved))

    def _show_line_values(self, line):
        if line is None:
            self._length.set('—')
            self._l1.set('—')
            self._beam_length.set('—')
            self._rack_number.set('—')
            return
        length = line['length_mm']
        self._length.set('%.1f' % length)
        try:
            end_overhang = float((self._overhang.get() or '').strip())
        except (TypeError, ValueError):
            self._l1.set('—')
            self._beam_length.set('—')
            self._rack_number.set('—')
            return
        self._l1.set('%.1f' % geom.resolve_l1(
            length, end_overhang, self.current_variant()))
        plate_t = 0.0
        if self.current_add_end_plate():
            table = anchor.ANCHOR_TABLE.get(self.current_plate_subtype())
            if table is not None:
                plate_t = float(table['plate_t'])
        self._beam_length.set('%.1f' % (length - plate_t))
        number = self.current_rack_number(line)
        self._rack_number.set(number if number else '（名称留空，不附加）')

    def refresh_line_labels(self):
        self._show_line_values(self.line)

    # -- UI 刷新：只允许在这个 Tk 定时器里碰控件 ---------------------------

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

    def note_hover(self, line):
        self._hover_line = line

    def note_hover_error(self, message):
        self._pending_message = message
        self._pending_is_error = True

    def request_cancel(self):
        self._cancel_requested = True

    def request_shutdown(self):
        self._shutdown_requested = True

    # -- 事件 --------------------------------------------------------------

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_plate_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay_ms):
        self._cancel_pending_regeneration()
        if self.line is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前直线与选项重建预览；只做 Bentley 建模，UI 刷新交给定时器。"""
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            self._pending_message = '参数有误：%s' % error
            self._pending_is_error = True
            return None

        rack_number = self.current_rack_number()
        _log('regenerate: options=%s rack=%s' % (options, rack_number or '-'))
        try:
            handle, result, deleted = replace_end_welded_triangle_bracket(
                self.line, options['end_overhang'], self.preview_handle,
                options['variant'], options['brace_down'], rack_number,
                options['add_end_plate'], options['plate_subtype'])
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
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
               '已替换上一版预览。' if deleted else ''))
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
        if self.preview_handle is not None and not self._keep_line.get():
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
        _disable_fault_logging()
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 交互工具：点选水平直线
# ---------------------------------------------------------------------------


class TriangleBracketByLineTool(DgnElementSetTool):
    """点选一条水平直线段并放置端焊三角架（可选端板）的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('TriangleBracketByLineTool')

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
            '请点选一条水平直线段作为横担上表面（起点为焊接端面，终点为横担'
            '末端）；直线两端 Z 必须一致。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            line = geom.extract_horizontal_line(handle)
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
        settings = self.tool_settings
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = geom.extract_horizontal_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '端焊三角架生成失败：%s' % error
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
        TriangleBracketByLineTool.InstallNewInstance(
            self.GetToolId(), settings, False)

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
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(TriangleBracketByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _TriangleBracketDialog())
        if owner:
            TriangleBracketByLineTool._active_settings = settings
        tool = TriangleBracketByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                TriangleBracketByLineTool._active_settings = None
        return tool


def show_triangle_bracket_dialog():
    return TriangleBracketByLineTool.InstallNewInstance(0)


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _enable_fault_logging()
    _log('PyMain: entry rev=%s' % UI_REVISION)
    _reload_runtime_modules()
    try:
        show_triangle_bracket_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('tool start failed')
        print('三角架工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '三角架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
