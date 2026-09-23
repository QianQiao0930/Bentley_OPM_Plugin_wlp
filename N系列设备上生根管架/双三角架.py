# -*- coding: utf-8 -*-
"""N 系列设备上生根管架 —— 设备上生根的双三角架（N4）放置工具。

在模型中绘制一条**水平辅助线**作为整组**中心线**（径向），线长 = L1
（立管中心线 → 端板外表面）。据此生成两套对称的三角架 + 两根构件C：

    构件A（横担）×2、构件B（斜撑）×2、构件C（连接横担）×2、
    连接板 + 螺栓（N8，规格按表 3 自动）、交点 10mm 筋板。

径向尺寸链（r 从立管中心线起）：端板 r=L1；构件C 内边缘 r=L4、r=L3；
横担外端 r=L3+C宽+50（超出外侧构件C 外缘 50）。

面板输入 H（≥MIN.H）、L2（≥MIN.L2）、L3、L4；类型 1/2 = 斜撑在下/在上。
编号：``N4-类型-子项-H-L1-L2-L3-L4``。清单写入共享支吊架库
``支吊架公共库``（``SupportType='N系列设备上生根管架'``）。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import os
import sys
import traceback
import tkinter as tk
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
GEOM_DIR = os.path.join(HERE, '模块', '双三角架')
N3_DIR = os.path.join(HERE, '模块', '单三角架')
PLATE_DIR = os.path.join(HERE, '模块', '连接板')
SUPPORT_COMMON = os.path.join(REPO_ROOT, '管道支吊架', '模块', '公共')
for _path in (REPO_ROOT, GEOM_DIR, N3_DIR, PLATE_DIR, SUPPORT_COMMON):
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
    BORDER, CARD, CARD_SOFT, FIELD, INK, MUTED, UI_FONT, UI_FONT_BOLD,
    UI_FONT_SMALL, GlassDialog, RoundButton, ScrollFrame,
)

import 双三角架_数据 as data  # noqa: E402
import 双三角架_几何 as geom  # noqa: E402


DEBUG_LOG = os.path.join(HERE, '模块', '日志', '双三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'N4-设备上生根的双三角架'
REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    """强制重读本插件的数据 / 几何模块，以及被复用的单三角架几何。

    N4 复用了 ``单三角架_几何``（其 ``_build_crossbeam`` 有 ``mirror`` 形参）；
    若不重读，MicroStation 会拿上一次加载的旧版本，报
    「got an unexpected keyword argument」之类的错。
    """
    importlib.invalidate_caches()
    modules = []
    for name in ('n3', 'plate_geom'):
        module = getattr(geom, name, None)
        if module is not None:
            modules.append(module)
    modules += [data, geom]
    for module in modules:
        try:
            importlib.reload(module)
        except Exception:
            _log_exception('reload failed')


class _DoubleBracketDialog(GlassDialog):
    """类型 / 子项 / H / L2 / L3 / L4 / 编号 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'N4DoubleBracket'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._regen_job = None

        self._type = tk.StringVar()
        self._subtype = tk.StringVar()
        self._height = tk.StringVar(value='')
        self._l2 = tk.StringVar(value='')
        self._l3 = tk.StringVar(value='')
        self._l4 = tk.StringVar(value='')
        self._series = tk.StringVar(value=data.DEFAULT_SERIES)
        self._keep_line = tk.BooleanVar(value=True)
        self._members = tk.StringVar(value='—')
        self._loads = tk.StringVar(value='—')
        self._dims = tk.StringVar(value='—')
        self._number = tk.StringVar(value='—')
        self._spec = tk.StringVar()
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar()
        self._type_by_label = {}
        self._subtype_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        _log('panel built rev=double-bracket-tk file=%s'
             % os.path.abspath(__file__))

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点选一条水平直线（整组中心线）· 类型 / 子项 / H / L2 / L3 / L4')
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)

        # 参数区放进可滚动容器，保证按钮始终可见；行距压到最小、信息尽量并排。
        scroll = ScrollFrame(form, bg=CARD, height=520)
        scroll.grid(row=0, column=0, sticky='nsew')
        body = scroll.body
        body.columnconfigure(3, weight=1)
        small = UI_FONT_SMALL
        p = 1

        tk.Label(
            body,
            text='点选一条水平直线作为整组中心线（径向）：线长 = L1（立管中心线 → '
                 '端板外表面）；两根横担关于它对称、切向相距 L2。改参数自动重建预览；'
                 '点【确定】保留，点【取消】或右键放弃。',
            bg=CARD, fg=MUTED, font=small, justify='left',
            wraplength=470).grid(row=0, column=0, columnspan=4, sticky='w')

        ttk.Label(body, text='构件规格（表 3）', style='Section.TLabel').grid(
            row=1, column=0, columnspan=4, sticky='w', pady=(3, 0))

        ttk.Label(body, text='类型', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=p)
        type_labels = []
        for key, label in data.TYPE_OPTIONS:
            type_labels.append(label)
            self._type_by_label[label] = key
        self._type_combo = ttk.Combobox(
            body, textvariable=self._type, state='readonly', width=34,
            style='Glass.TCombobox', values=type_labels)
        self._type_combo.grid(row=2, column=1, columnspan=3, sticky='ew',
                              padx=(10, 0), pady=p)
        self._type_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(body, text='子项', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=p)
        subtype_labels = []
        for key in data.SUBTYPE_KEYS:
            label = data.subtype_label(key)
            subtype_labels.append(label)
            self._subtype_by_label[label] = key
        self._subtype_combo = ttk.Combobox(
            body, textvariable=self._subtype, state='readonly', width=34,
            style='Glass.TCombobox', values=subtype_labels)
        self._subtype_combo.grid(row=3, column=1, columnspan=3, sticky='ew',
                                 padx=(10, 0), pady=p)
        self._subtype_combo.bind('<<ComboboxSelected>>',
                                 self.on_subtype_changed)

        # 构件A/B/C 并排成一行；连接板与允许荷载并排成一行。
        ttk.Label(body, text='构件A/B/C', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=p)
        tk.Label(body, textvariable=self._members, bg=CARD, fg=INK,
                 font=small, anchor='w', justify='left', wraplength=350).grid(
            row=4, column=1, columnspan=3, sticky='w', padx=(10, 0), pady=p)

        ttk.Label(body, text='连接板/荷载', style='GlassMuted.TLabel').grid(
            row=5, column=0, sticky='nw', pady=p)
        tk.Label(body, textvariable=self._loads, bg=CARD, fg=INK, font=small,
                 anchor='w', justify='left', wraplength=350).grid(
            row=5, column=1, columnspan=3, sticky='w', padx=(10, 0), pady=p)

        ttk.Separator(body, orient='horizontal').grid(
            row=6, column=0, columnspan=4, sticky='ew', pady=3)
        ttk.Label(body, text='尺寸参数（H/L2、L3/L4 各并排一列）',
                  style='Section.TLabel').grid(
            row=7, column=0, columnspan=4, sticky='w', pady=(0, 2))

        self._height_entry = self._dim_cell(body, 8, 0, 'H', self._height)
        self._l2_entry = self._dim_cell(body, 8, 2, 'L2', self._l2)
        self._l3_entry = self._dim_cell(body, 9, 0, 'L3', self._l3)
        self._l4_entry = self._dim_cell(body, 9, 2, 'L4', self._l4)
        tk.Label(body,
                 text='H 横担顶面→斜撑连接板中心（≥MIN.H）　'
                      'L2 两横担间距（≥MIN.L2）　L3/L4 端板→构件C 内边缘',
                 bg=CARD, fg=MUTED, font=small, justify='left',
                 wraplength=470).grid(row=10, column=0, columnspan=4,
                                      sticky='w', pady=(1, 0))

        ttk.Label(body, text='L1 / 横担', style='GlassMuted.TLabel').grid(
            row=11, column=0, sticky='w', pady=p)
        tk.Label(body, textvariable=self._dims, bg=CARD, fg=INK, font=small,
                 anchor='w', justify='left', wraplength=350).grid(
            row=11, column=1, columnspan=3, sticky='w', padx=(10, 0), pady=p)

        ttk.Separator(body, orient='horizontal').grid(
            row=12, column=0, columnspan=4, sticky='ew', pady=3)
        ttk.Label(body, text='管架编号', style='Section.TLabel').grid(
            row=13, column=0, columnspan=4, sticky='w', pady=(0, 2))

        ttk.Label(body, text='系列 / 编号', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='w', pady=p)
        number_row = tk.Frame(body, bg=CARD)
        number_row.grid(row=14, column=1, columnspan=3, sticky='w',
                        padx=(10, 0), pady=p)
        self._series_entry = self._entry(number_row, self._series, 8)
        tk.Label(number_row, textvariable=self._number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(10, 0))

        self._keep_check = tk.Checkbutton(
            body, text='创建后保留所选辅助线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=small, highlightthickness=0, bd=0)
        self._keep_check.grid(row=15, column=0, columnspan=4, sticky='w')

        # 说明 / 预览 / 状态与按钮固定在滚动区下方；各信息框**固定高度**，
        # 文字再长也不许把面板撑大（超出部分裁掉）。
        info = tk.Frame(form, bg=CARD)
        info.grid(row=1, column=0, sticky='ew', pady=(4, 0))
        tk.Label(info, textvariable=self._spec, bg=CARD, fg=MUTED, font=small,
                 justify='left', anchor='nw', wraplength=470, height=2).pack(
            fill='x')
        tk.Label(info, textvariable=self._preview_info, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='nw',
                 wraplength=470, height=2).pack(fill='x', pady=(2, 0))
        status = tk.Frame(info, bg=CARD_SOFT, highlightbackground=BORDER,
                          highlightthickness=1)
        status.pack(fill='x', pady=(4, 0))
        tk.Label(status, textvariable=self._status, bg=CARD_SOFT, fg='#1f5f99',
                 font=small, justify='left', anchor='nw', wraplength=450,
                 height=2).pack(fill='x', padx=8, pady=3)

        buttons = tk.Frame(form, bg=CARD)
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

        for var in (self._series, self._height, self._l2, self._l3, self._l4):
            var.trace_add('write', self.on_text_changed)

    def _dim_cell(self, parent, row, col, label, variable):
        """一个尺寸输入格：标签在 col、输入框在 col+1，右侧跟 mm。"""
        ttk.Label(parent, text=label, style='GlassMuted.TLabel').grid(
            row=row, column=col, sticky='w', pady=1)
        holder = tk.Frame(parent, bg=CARD)
        holder.grid(row=row, column=col + 1, sticky='w', padx=(6, 14), pady=1)
        entry = self._entry(holder, variable, 8)
        tk.Label(holder, text='mm', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(4, 0))
        return entry

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        entry.bind('<FocusIn>',
                   lambda event, widget=entry: widget.select_range(0, 'end'))
        return entry

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = fallback = None
        for label, key in self._type_by_label.items():
            if fallback is None:
                fallback = label
            if key == state.get('type'):
                selected = label
        self._type.set(selected or fallback)

        selected = fallback = None
        for label, key in self._subtype_by_label.items():
            if fallback is None:
                fallback = label
            if key == state.get('subtype'):
                selected = label
        self._subtype.set(selected or fallback)

        for key, var in (('height', self._height), ('l2', self._l2),
                         ('l3', self._l3), ('l4', self._l4)):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                var.set(value)
        series = state.get('series')
        if isinstance(series, str):
            self._series.set(series)
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['type'] = self.current_type()
            state['subtype'] = self.current_subtype()
            state['height'] = self._height.get()
            state['l2'] = self._l2.get()
            state['l3'] = self._l3.get()
            state['l4'] = self._l4.get()
            state['series'] = self._series.get()
            state['keep_line'] = bool(self._keep_line.get())
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_type(self):
        return self._type_by_label.get(self._type.get(), data.TYPE_KEYS[0])

    def current_subtype(self):
        return self._subtype_by_label.get(self._subtype.get(),
                                          data.SUBTYPE_KEYS[0])

    def _number_value(self, var):
        text = (var.get() or '').strip()
        return float(text) if text else None

    def current_options(self):
        return {
            'subtype': self.current_subtype(),
            'type': self.current_type(),
            'height_mm': self._number_value(self._height),
            'l2_mm': self._number_value(self._l2),
            'l3_mm': self._number_value(self._l3),
            'l4_mm': self._number_value(self._l4),
            'series': self._series.get(),
        }

    def current_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            resolved = data.resolve_options(self.current_options(),
                                            line['length_mm'])
        except (ValueError, RuntimeError):
            return ''
        return data.build_number(self._series.get(), resolved['type'],
                                 resolved['subtype'], resolved['H'],
                                 resolved['L1'], resolved['L2'],
                                 resolved['L3'], resolved['L4'])

    def set_status(self, message, is_error=False):
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass

    def set_result(self, result):
        self._preview_info.set(
            '预览：子项 %s 类型 %d ｜ A %s×2 / B %s×2 / C %s×2 ｜ 连接板类型 %d '
            '｜ %d 个子元素 ｜ 编号 %s' % (
                result['subtype'], result['type'], result['comp_a'],
                result['comp_b'], result['comp_c'], result['plate_type'],
                result['child_count'], result.get('number') or '—'))

    def refresh_spec(self):
        subtype = self.current_subtype()
        info = data.SUBTYPES.get(subtype)
        if info is None:
            self._spec.set('子项有误。')
            return
        self._members.set('A %s×2 ｜ B %s×2 ｜ C %s×2' % (
            info['comp_a'], info['comp_b'], info['comp_c']))
        plate_text = '连接板 类型 %d（N8 自动）' % info['plate_type']
        # 默认值只在切换子项 / 首次载入时给，编辑过程中不回填。
        if self.line is None:
            self._loads.set(plate_text)
            self._dims.set('—')
            self._number.set('—')
            self._spec.set('请在模型中点选一条水平直线段（整组中心线）。')
            return
        try:
            resolved = data.resolve_options(self.current_options(),
                                            self.line['length_mm'])
        except (ValueError, RuntimeError) as error:
            self._loads.set(plate_text)
            self._dims.set('—')
            self._number.set('—')
            self._spec.set('参数有误：%s' % error)
            return
        v = resolved['vertical_load']
        h = resolved['horizontal_load']
        v_text = ('%.0f kN（a=%.0f）' % (v, resolved['vertical_load_span'])
                  if v is not None else (resolved['vertical_load_note'] or '—'))
        h_text = ('%.0f kN（b=%.0f）' % (h, resolved['horizontal_load_span'])
                  if h is not None else (resolved['horizontal_load_note'] or '—'))
        self._loads.set('%s；垂直 %s ｜ 水平 %s' % (plate_text, v_text, h_text))
        self._dims.set('L1=%.0f，横担长 %.0f，外端 %.0f，端部余量 %.0f（≥150）'
                       % (resolved['L1'], resolved['beam_length'],
                          resolved['outer_end'], resolved['end_overhang']))
        self._spec.set(data.describe_spec(resolved))
        number = self.current_number()
        self._number.set(number if number else '（系列留空，不附加编号）')

    def _set_busy(self, busy):
        for combo in (self._type_combo, self._subtype_combo):
            try:
                combo.configure(state='disabled' if busy else 'readonly')
            except tk.TclError:
                pass
        for button in (self.confirm_button, self.cancel_button):
            button.set_enabled(not busy)
        try:
            self.update_idletasks()
        except tk.TclError:
            pass

    def on_subtype_changed(self, event=None):
        info = data.SUBTYPES.get(self.current_subtype())
        if info is not None:
            self._height.set('%.0f' % info['min_h'])
            self._l2.set('%.0f' % info['min_l2'])
        self.on_options_changed()

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay):
        self._cancel_pending_regeneration()
        if self.line is None:
            return
        try:
            self._regen_job = self.after(delay, self._run_pending_regeneration)
        except tk.TclError:
            self._regen_job = None

    def _cancel_pending_regeneration(self):
        if self._regen_job is not None:
            try:
                self.after_cancel(self._regen_job)
            except Exception:
                pass
            self._regen_job = None

    def _run_pending_regeneration(self):
        self._regen_job = None
        self.regenerate()

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None
        try:
            options = self.current_options()
            data.resolve_options(options, self.line['length_mm'])
        except (ValueError, RuntimeError) as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成双三角架预览，请稍候……')
        try:
            new_handle, result, deleted = geom.replace_double_bracket(
                self.line, options, self.preview_handle, self.current_number())
        except Exception as error:
            message = '双三角架生成失败：%s' % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = new_handle
        self.preview_result = result
        self.set_result(result)
        self.refresh_spec()
        message = ('预览已更新：子项 %s，类型 %d，编号 %s，单元含 %d 个子元素。'
                   '%s点【确定】保留，点【取消】放弃。'
                   % (result['subtype'], result['type'],
                      result.get('number') or '—', result['child_count'],
                      '已替换上一版。' if deleted else ''))
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return geom._delete_element(handle)

    def delete_source_line(self):
        handle = self.line_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                return True
        except Exception:
            _log_exception('delete source line failed')
        return False

    def export_bom(self):
        output_path = geom.export_bom_json()
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
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 交互工具：点选水平直线
# ---------------------------------------------------------------------------


class DoubleBracketByLineTool(DgnElementSetTool):
    """点选一条水平直线段（整组中心线）并放置双三角架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('DoubleBracketByLineTool')

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
            '请点选一条水平直线段作为整组中心线（径向）：线长 = L1（立管中心线'
            '→端板外表面）。右键放弃。')

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            try:
                settings.after(0, settings.cancel_tool)
            except Exception:
                pass
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = geom.n3.extract_horizontal_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '双三角架生成失败：%s' % error
            _log_exception('element modify failed')
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            print(message)
            return BentleyStatus.eERROR

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
            active = getattr(DoubleBracketByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _DoubleBracketDialog())
        if owner:
            DoubleBracketByLineTool._active_settings = settings
        tool = DoubleBracketByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                DoubleBracketByLineTool._active_settings = None
        return tool


def show_double_bracket_dialog():
    return DoubleBracketByLineTool.InstallNewInstance(0)


def export_double_bracket_bom():
    return geom.export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYNDOUBLE PLACE / PYNDOUBLE EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '双三角架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenNDouble():
    PyMain()


def ExportNDoubleBom():
    export_double_bracket_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _log('PyMain: entry')
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_double_bracket_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('双三角架工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'N4-双三角架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
