# -*- coding: utf-8 -*-
"""N 系列设备上生根管架 —— 设备上生根的单三角架（N3）放置工具。

在模型中绘制一条**水平辅助线**作为**管底**（＝三角架横担／构件A 的顶面）：

    线长 = P0 至 P3 的总长 L；线起点 P0 = 设备表面；线方向 = 由设备向外。
    连接板占 P0 至 P1（厚 T），横担从 P1 至 P3，实体长度 L-T。

直线画反了（起点落在管外侧）时勾选面板的**「反向」**：起点改用直线另一端、
朝向反转 180°，P0…P4 与整组构件一起翻到正确一侧。

据此生成整组单三角架：横担（构件A）+ 斜撑（构件B，45°）+ 两块 N8 连接板
（规格按表 2 自动取）+ 交点 10mm 筋板，整组写成一个普通单元。

两种类型：**类型 1** 斜撑在下（由下方连接板向上撑到横担）；**类型 2** 斜撑在上
（由上方连接板向下拉到横担）。H 为横担顶面到斜撑连接板中心的竖直距离。

编号：``N3-类型-子项-H-L``。清单写入共享支吊架库
``支吊架公共库``（``SupportType='N3-[设备上生根单三角架]'``）。

建模逻辑在纯几何模块 ``模块/单三角架/单三角架_几何.py``；本文件只负责
**Tkinter** 面板与交互工具，外观沿用仓库共享的 ``bentley_ui``。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import importlib.util
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

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
GEOM_DIR = os.path.join(HERE, '模块', '单三角架')
PLATE_DIR = os.path.join(HERE, '模块', '连接板')
COMMON_DIR = os.path.join(HERE, '模块', '公共')
for _path in (COMMON_DIR, GEOM_DIR, PLATE_DIR, REPO_ROOT):
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

import 单三角架_数据 as data  # noqa: E402
import 单三角架_几何 as geom  # noqa: E402


DEBUG_LOG = os.path.join(HERE, '模块', '日志', '单三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'N3-[设备上生根单三角架]'
REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750


def _reload_runtime_modules():
    """强制重读本插件的数据 / 几何模块，规避 MicroStation 的模块缓存。

    否则改了数据模块（如 ``build_number`` 形参）后，运行时仍会拿到上一次
    加载的旧版本，出现「missing required positional argument」之类的错。
    """
    importlib.invalidate_caches()
    for module in (data, geom):
        try:
            importlib.reload(module)
        except Exception:
            _log_exception('reload %s failed' % getattr(module, '__name__', '?'))


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


class _SingleBracketDialog(GlassDialog):
    """类型 / 子项 / H / 编号 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'N3SingleBracket'

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
        self._series = tk.StringVar(value=data.DEFAULT_SERIES)
        self._keep_line = tk.BooleanVar(value=True)
        self._reverse = tk.BooleanVar(value=False)
        self._member_a = tk.StringVar(value='—')
        self._member_b = tk.StringVar(value='—')
        self._plate = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
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
        _log('panel built rev=single-bracket-tk file=%s'
             % os.path.abspath(__file__))

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点选一条水平直线（管底＝横担顶面）· 类型 / 子项 / H 可调')
        form.columnconfigure(1, weight=1)

        tk.Label(
            form,
            text='绘制并点选一条水平直线作为管底（＝横担顶面）：线长＝P0 到 P3 的 L，'
                 '起点 P0＝设备面，横担从板外表面 P1 开始。直线画反了（起点落在管外侧）'
                 '时勾选【反向】把起点换到另一端。点选后可改类型 / 子项 / H / 编号，'
                 '预览会自动重建；点【确定】保留，点【取消】或右键放弃。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=470).grid(row=0, column=0, columnspan=2, sticky='w')

        ttk.Label(form, text='构件规格（表 2）', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(10, 4))

        ttk.Label(form, text='类型', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=5)
        type_labels = []
        for key, label in data.TYPE_OPTIONS:
            type_labels.append(label)
            self._type_by_label[label] = key
        self._type_combo = ttk.Combobox(
            form, textvariable=self._type, state='readonly', width=34,
            style='Glass.TCombobox', values=type_labels)
        self._type_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=5)
        self._type_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(form, text='子项', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=5)
        subtype_labels = []
        for key in data.SUBTYPE_KEYS:
            label = data.subtype_label(key)
            subtype_labels.append(label)
            self._subtype_by_label[label] = key
        self._subtype_combo = ttk.Combobox(
            form, textvariable=self._subtype, state='readonly', width=34,
            style='Glass.TCombobox', values=subtype_labels)
        self._subtype_combo.grid(row=3, column=1, sticky='ew', padx=(10, 0),
                                 pady=5)
        self._subtype_combo.bind('<<ComboboxSelected>>',
                                 self.on_subtype_changed)

        ttk.Label(form, text='构件A（横担）', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._member_a, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=5)

        ttk.Label(form, text='构件B（斜撑）', style='GlassMuted.TLabel').grid(
            row=5, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._member_b, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=5, column=1, sticky='w', padx=(10, 0), pady=5)

        ttk.Label(form, text='连接板', style='GlassMuted.TLabel').grid(
            row=6, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._plate, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=330).grid(row=6, column=1, sticky='w',
                                      padx=(10, 0), pady=5)

        ttk.Label(form, text='允许荷载', style='GlassMuted.TLabel').grid(
            row=7, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._load, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=7, column=1, sticky='w', padx=(10, 0), pady=5)

        ttk.Separator(form, orient='horizontal').grid(
            row=8, column=0, columnspan=2, sticky='ew', pady=8)

        ttk.Label(form, text='尺寸参数', style='Section.TLabel').grid(
            row=9, column=0, columnspan=2, sticky='w', pady=(0, 4))

        ttk.Label(form, text='H', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='w', pady=5)
        h_row = tk.Frame(form, bg=CARD)
        h_row.grid(row=10, column=1, sticky='w', padx=(10, 0), pady=5)
        self._height_entry = self._entry(h_row, self._height, 9)
        tk.Label(h_row, text='mm　横担顶面→斜撑连接板中心（≥MIN.H）',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        ttk.Label(form, text='L / 余量', style='GlassMuted.TLabel').grid(
            row=11, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._dims, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=330).grid(row=11, column=1, sticky='w',
                                      padx=(10, 0), pady=5)

        ttk.Separator(form, orient='horizontal').grid(
            row=12, column=0, columnspan=2, sticky='ew', pady=8)

        ttk.Label(form, text='管架编号', style='Section.TLabel').grid(
            row=13, column=0, columnspan=2, sticky='w', pady=(0, 4))

        ttk.Label(form, text='系列', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='w', pady=5)
        series_row = tk.Frame(form, bg=CARD)
        series_row.grid(row=14, column=1, sticky='w', padx=(10, 0), pady=5)
        self._series_entry = self._entry(series_row, self._series, 10)
        tk.Label(series_row, text='编号前缀（默认 N3）；留空则不附加编号',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        checks = tk.Frame(form, bg=CARD)
        checks.grid(row=15, column=0, columnspan=2, sticky='w')
        self._keep_check = tk.Checkbutton(
            checks, text='创建后保留所选辅助线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT_SMALL, highlightthickness=0, bd=0)
        self._keep_check.pack(side='left')
        # 反向：直线画反了（起点落在管外侧）时交换两端，整组构件的生成方向随之翻转。
        self._reverse_check = tk.Checkbutton(
            checks, text='反向（起点取直线另一端）', variable=self._reverse,
            command=self.on_options_changed,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT_SMALL, highlightthickness=0, bd=0)
        self._reverse_check.pack(side='left', padx=(12, 0))

        ttk.Label(form, text='编号', style='GlassMuted.TLabel').grid(
            row=16, column=0, sticky='w', pady=5)
        tk.Label(form, textvariable=self._number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=16, column=1, sticky='w', padx=(10, 0), pady=5)

        ttk.Separator(form, orient='horizontal').grid(
            row=17, column=0, columnspan=2, sticky='ew', pady=8)

        tk.Label(form, textvariable=self._spec, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL, justify='left', anchor='w',
                 wraplength=470).grid(row=18, column=0, columnspan=2,
                                      sticky='w')
        tk.Label(form, textvariable=self._preview_info, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=470).grid(row=19, column=0, columnspan=2,
                                      sticky='w', pady=(4, 0))
        self.make_status_chip(form, self._status, wraplength=470).grid(
            row=20, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=21, column=0, columnspan=2, sticky='ew', pady=(12, 0))
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

        self._series.trace_add('write', self.on_text_changed)
        self._height.trace_add('write', self.on_text_changed)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        # 获得焦点即全选：再次输入时**整体替换**已有数值，而不是在其前后插入。
        entry.bind('<FocusIn>',
                   lambda event, widget=entry: widget.select_range(0, 'end'))
        return entry

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected_type = fallback_type = None
        for label, key in self._type_by_label.items():
            if fallback_type is None:
                fallback_type = label
            if key == state.get('type'):
                selected_type = label
        self._type.set(selected_type or fallback_type)

        selected_sub = fallback_sub = None
        for label, key in self._subtype_by_label.items():
            if fallback_sub is None:
                fallback_sub = label
            if key == state.get('subtype'):
                selected_sub = label
        self._subtype.set(selected_sub or fallback_sub)

        height = state.get('height')
        if isinstance(height, str) and height.strip():
            self._height.set(height)
        series = state.get('series')
        if isinstance(series, str):
            self._series.set(series)
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        if isinstance(state.get('reverse'), bool):
            self._reverse.set(state.get('reverse'))
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['type'] = self.current_type()
            state['subtype'] = self.current_subtype()
            state['height'] = self._height.get()
            state['series'] = self._series.get()
            state['keep_line'] = bool(self._keep_line.get())
            state['reverse'] = bool(self._reverse.get())
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_type(self):
        return self._type_by_label.get(self._type.get(), data.TYPE_KEYS[0])

    def current_subtype(self):
        return self._subtype_by_label.get(self._subtype.get(),
                                          data.SUBTYPE_KEYS[0])

    def current_options(self):
        try:
            height = float((self._height.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('H 必须是数字（mm）。')
        return {'subtype': self.current_subtype(), 'type': self.current_type(),
                'height_mm': height, 'series': self._series.get(),
                'reverse': bool(self._reverse.get())}

    def current_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            height = float((self._height.get() or '').strip())
        except (TypeError, ValueError):
            return ''
        return data.build_number(self._series.get(), self.current_type(),
                                 self.current_subtype(), height,
                                 line['length_mm'])

    def set_status(self, message, is_error=False):
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass

    def set_result(self, result):
        self._preview_info.set(
            '预览：子项 %s，类型 %d，横担 %s，斜撑 %s，连接板类型 %d，'
            '单元含 %d 个子元素，编号 %s。' % (
                result['subtype'], result['type'], result['comp_a'],
                result['comp_b'], result['plate_type'], result['child_count'],
                result.get('number') or '—'))

    def refresh_spec(self):
        subtype = self.current_subtype()
        info = data.SUBTYPES.get(subtype)
        if info is None:
            self._spec.set('子项有误。')
            return
        self._member_a.set(info['comp_a'])
        self._member_b.set(info['comp_b'])
        self._plate.set('类型 %d（N8，规格自动）' % info['plate_type'])
        # 注意：不要在这里回填 H —— 用户清空重输时会被立刻填回，导致新数字
        # 只能插在旧值前面。H 的默认值只在切换子项 / 首次载入时设置。
        if self.line is None:
            self._load.set('—')
            self._dims.set('—')
            self._number.set('—')
            self._spec.set('请在模型中点选一条水平直线段（管底＝横担顶面）。')
            return
        try:
            resolved = self.current_resolved()
        except (ValueError, RuntimeError) as error:
            self._load.set('—')
            self._dims.set('—')
            self._spec.set('参数有误：%s' % error)
            self._number.set('—')
            return
        load = resolved['allowable_load']
        if load is None:
            self._load.set(resolved['allowable_load_note'] or '—')
        else:
            self._load.set('%.0f kN（a=%.0f）' % (load,
                                                 resolved['allowable_load_span']))
        dims = ('L=%.0f，横担长 %.0f，斜撑投影 %.0f，端部余量 %.0f（≥150）' % (
            resolved['L'], resolved['beam_length'], resolved['brace_run'],
            resolved['end_overhang']))
        if resolved.get('reverse'):
            dims = '已反向｜' + dims
        self._dims.set(dims)
        self._spec.set(data.describe_spec(resolved))
        number = self.current_number()
        self._number.set(number if number else '（系列留空，不附加编号）')

    def current_resolved(self):
        line = self.line if self.line is not None else {'length_mm': 1.0}
        return data.resolve_options(self.current_options(), line['length_mm'])

    def _set_busy(self, busy):
        # 只锁下拉框与按钮；文本框不锁，避免重建预览时打断正在进行的输入。
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
        self.set_status('正在生成单三角架预览，请稍候……')
        try:
            new_handle, result, deleted = geom.replace_single_bracket(
                self.line, options, self.preview_handle,
                self.current_number())
        except Exception as error:
            message = '单三角架生成失败：%s' % error
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
        message = ('预览已更新%s：子项 %s，类型 %d，H=%.0f，L=%.0f，端部余量 %.0f，'
                   '连接板类型 %d，单元含 %d 个子元素，编号 %s。%s改参数会自动'
                   '重建；点【确定】保留，点【取消】放弃。'
                   % ('（已反向）' if result.get('reverse') else '',
                      result['subtype'], result['type'], result['H'],
                      result['L'], result['end_overhang'], result['plate_type'],
                      result['child_count'], result.get('number') or '—',
                      '已替换上一版预览。' if deleted else ''))
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


class SingleBracketByLineTool(DgnElementSetTool):
    """点选一条水平直线段（管底）并放置单三角架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('SingleBracketByLineTool')

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
            '请点选一条水平直线段作为管底（＝横担顶面）：线长为设备面 P0 到横担末端 P3 的 L，'
            '起点为设备面；画反了可在面板勾选【反向】。右键放弃。')

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
            line = geom.extract_horizontal_line(eeh)
            result = self.tool_settings.regenerate(line, eeh)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            message = '单三角架生成失败：%s' % error
            _log_exception('element modify failed')
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            print(message)
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        SingleBracketByLineTool.InstallNewInstance(
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
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(SingleBracketByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _SingleBracketDialog())
        if owner:
            SingleBracketByLineTool._active_settings = settings
        tool = SingleBracketByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                SingleBracketByLineTool._active_settings = None
        return tool


def show_single_bracket_dialog():
    return SingleBracketByLineTool.InstallNewInstance(0)


def export_single_bracket_bom():
    return geom.export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYNSINGLE PLACE / PYNSINGLE EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '单三角架.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenNSingle():
    PyMain()


def ExportNSingleBom():
    export_single_bracket_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _log('PyMain: entry')
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_single_bracket_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('单三角架工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'N3-单三角架启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
