# -*- coding: utf-8 -*-
"""N 系列设备上生根管架 —— 设备预焊件用连接板 + 螺栓 放置工具。

在三维 DGN 模型中点取**设备表面**上连接板背面的中心点，按表 1 / 图 1 / 图 2
生成一块正方形连接板与配套螺栓：

    * 连接板：正方形 E×E×T，在 F×F 方阵上开螺栓孔，孔径 G；类型 0~3 四角
      4 孔（图 1），类型 4、5 四角 + 四边中点 8 孔（图 2）。
    * 螺栓：一根**贯穿连接板**的六角头螺栓 —— 六角头 + 垫片A + 垫片B + 六角螺母；
      垫片A 紧贴连接板背面，垫片B 距连接板外表面一个板厚 T（给**另一片连接板**
      留位），两垫片间距 = 2T；螺栓长度 L 按**保温 H / 保冷 C** 工况取值（表 1），
      螺栓朝向**垂直于设备表面**。
    * 安装面可选**竖直设备表面**（螺栓垂直于表面、水平）或**水平设备顶面 /
      底面**（螺栓垂直于表面、朝下 / 朝上）；「朝向」在各自平面内绕外法向旋转。

建模逻辑全部在 ``模块/连接板/连接板_几何.py`` 中，不含任何界面依赖，其它
插件可直接 ``import 连接板_几何`` 调用：

    import 连接板_几何 as geom
    cell, result = geom.draw_connection_plate(placement_point, options)

几何复用 ``模块/公共/混凝土锚板.py`` 的基础构件；清单写入共享支吊架库
``支吊架公共库``（``SupportType='N8-[设备预焊件连接板]'``），可与其它管道
支吊架一起统计。

本文件只负责 **Tkinter** 面板与交互工具，外观沿用仓库共享的 ``bentley_ui``
主题（卡片 / 圆角按钮），并自动记住上次窗口位置与类型 / 工况 / 安装面等。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import importlib.util
import os
import sys
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 通配导入不一定导出这两个符号，显式再导入一次（与其它插件一致）。
from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 仓库根提供共享 UI 工具箱 bentley_ui；本插件几何在 模块/连接板/；
# 建模复用的公共库在 模块/公共/。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '连接板')
for _path in (COMMON_DIR, GEOM_DIR, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

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
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
)

import 连接板_数据 as data  # noqa: E402
import 连接板_几何 as geom  # noqa: E402


DEBUG_LOG = os.path.join(HERE, '模块', '日志', '连接板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'N8-[设备预焊件连接板]'

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖，避免打到一半就重建


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


# ---------------------------------------------------------------------------
# 设置面板（Tkinter）
# ---------------------------------------------------------------------------


class _ConnectionPlateDialog(GlassDialog):
    """类型 / 工况 / 编号 / 安装面 / 朝向 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'N8ConnectionPlate'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.placement_point = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._regen_job = None

        self._type = tk.StringVar()
        self._mode = tk.StringVar(value=data.MODE_OPTIONS[0][1])
        self._series = tk.StringVar(value=data.DEFAULT_SERIES)
        self._mount = tk.StringVar(value=data.MOUNT_OPTIONS[0][1])
        self._heading = tk.StringVar(value='0')
        self._plate_text = tk.StringVar(value='—')
        self._hole_text = tk.StringVar(value='—')
        self._bolt_text = tk.StringVar(value='—')
        self._number_text = tk.StringVar(value='—')
        self._spec = tk.StringVar()
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar()
        self._type_by_label = {}
        self._mode_by_label = {}
        self._mount_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()

        # 关闭窗口时按"取消"处理：丢弃预览并结束工具。
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        _log('panel built rev=connection-plate-tk file=%s'
             % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点取设备表面连接板中心 · 类型 / 工况 / 朝向可调，自动预览')
        form.columnconfigure(1, weight=1)

        tk.Label(
            form,
            text='在模型中点取设备表面上连接板背面的中心点；螺栓垂直于设备表面'
                 '向外伸出（竖直设备表面＝水平方向，水平设备表面＝竖直方向）。'
                 '点取后可改类型 / 工况 / 系列 / 安装面 / 朝向，预览会自动'
                 '重建；点【确定】保留，点【取消】或右键放弃。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=450,
        ).grid(row=0, column=0, columnspan=2, sticky='w')

        ttk.Label(form, text='连接板（表 1）', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(10, 4))

        ttk.Label(form, text='类型', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=6)
        type_labels = []
        for key in data.TYPE_KEYS:
            label = data.type_label(key)
            type_labels.append(label)
            self._type_by_label[label] = key
        self._type_combo = ttk.Combobox(
            form, textvariable=self._type, state='readonly', width=34,
            style='Glass.TCombobox', values=type_labels)
        self._type_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0), pady=6)
        self._type_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(form, text='工况', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=6)
        mode_labels = []
        for key, label in data.MODE_OPTIONS:
            mode_labels.append(label)
            self._mode_by_label[label] = key
        self._mode_combo = ttk.Combobox(
            form, textvariable=self._mode, state='readonly', width=34,
            style='Glass.TCombobox', values=mode_labels)
        self._mode_combo.grid(row=3, column=1, sticky='w', padx=(10, 0), pady=6)
        self._mode_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(form, text='连接板', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._plate_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=340).grid(row=4, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Label(form, text='螺栓孔', style='GlassMuted.TLabel').grid(
            row=5, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._hole_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=340).grid(row=5, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Label(form, text='螺栓', style='GlassMuted.TLabel').grid(
            row=6, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._bolt_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=340).grid(row=6, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Separator(form, orient='horizontal').grid(
            row=7, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(form, text='管架编号', style='Section.TLabel').grid(
            row=8, column=0, columnspan=2, sticky='w', pady=(0, 4))

        ttk.Label(form, text='系列', style='GlassMuted.TLabel').grid(
            row=9, column=0, sticky='w', pady=6)
        series_row = tk.Frame(form, bg=CARD)
        series_row.grid(row=9, column=1, sticky='w', padx=(10, 0), pady=6)
        self._series_entry = self._entry(series_row, self._series, 10)
        tk.Label(series_row, text='编号前缀（默认 N8）；留空则不附加编号',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        ttk.Label(form, text='编号', style='GlassMuted.TLabel').grid(
            row=10, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._number_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=340).grid(row=10, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Separator(form, orient='horizontal').grid(
            row=12, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(form, text='布置参数', style='Section.TLabel').grid(
            row=13, column=0, columnspan=2, sticky='w', pady=(0, 4))

        ttk.Label(form, text='安装面', style='GlassMuted.TLabel').grid(
            row=14, column=0, sticky='w', pady=6)
        mount_labels = []
        for key, label in data.MOUNT_OPTIONS:
            mount_labels.append(label)
            self._mount_by_label[label] = key
        self._mount_combo = ttk.Combobox(
            form, textvariable=self._mount, state='readonly', width=34,
            style='Glass.TCombobox', values=mount_labels)
        self._mount_combo.grid(row=14, column=1, sticky='w', padx=(10, 0),
                               pady=6)
        self._mount_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(form, text='朝向', style='GlassMuted.TLabel').grid(
            row=15, column=0, sticky='w', pady=6)
        heading_row = tk.Frame(form, bg=CARD)
        heading_row.grid(row=15, column=1, sticky='w', padx=(10, 0), pady=6)
        self._heading_entry = self._entry(heading_row, self._heading, 9)
        tk.Label(heading_row, text='°　竖直设备表面为绕 Z 方位角，水平设备表面为绕竖轴转角',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=16, column=0, columnspan=2, sticky='ew', pady=10)

        tk.Label(form, textvariable=self._spec, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL, justify='left', anchor='w',
                 wraplength=450).grid(row=17, column=0, columnspan=2,
                                      sticky='w')
        tk.Label(form, textvariable=self._preview_info, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=450).grid(row=18, column=0, columnspan=2,
                                      sticky='w', pady=(4, 0))

        self.make_status_chip(form, self._status, wraplength=450).grid(
            row=19, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=20, column=0, columnspan=2, sticky='ew', pady=(12, 0))
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
        self._heading.trace_add('write', self.on_text_changed)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        # 获得焦点即全选：再次输入时整体替换，而不是在旧值前后插入。
        entry.bind('<FocusIn>',
                   lambda event, widget=entry: widget.select_range(0, 'end'))
        return entry

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected_type = None
        fallback_type = None
        for label, key in self._type_by_label.items():
            if fallback_type is None:
                fallback_type = label
            if key == state.get('type'):
                selected_type = label
        self._type.set(selected_type or fallback_type)

        selected_mode = None
        fallback_mode = None
        for label, key in self._mode_by_label.items():
            if fallback_mode is None:
                fallback_mode = label
            if key == state.get('mode'):
                selected_mode = label
        self._mode.set(selected_mode or fallback_mode)

        selected_mount = None
        fallback_mount = None
        for label, key in self._mount_by_label.items():
            if fallback_mount is None:
                fallback_mount = label
            if key == state.get('mount'):
                selected_mount = label
        self._mount.set(selected_mount or fallback_mount)

        series = state.get('series')
        if isinstance(series, str):
            self._series.set(series)
        heading = state.get('heading')
        if isinstance(heading, str) and heading.strip():
            self._heading.set(heading)
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['type'] = self.current_type()
            state['mode'] = self.current_mode()
            state['mount'] = self.current_mount()
            state['series'] = self._series.get()
            state['heading'] = self._heading.get()
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_type(self):
        return self._type_by_label.get(self._type.get(), data.TYPE_KEYS[0])

    def current_mode(self):
        return self._mode_by_label.get(self._mode.get(), data.MODE_KEYS[0])

    def current_mount(self):
        return self._mount_by_label.get(self._mount.get(), 'wall')

    def current_options(self):
        type_key = self.current_type()
        if type_key not in data.PLATE_TABLE:
            raise ValueError('未知类型：%s。' % type_key)
        try:
            heading = float((self._heading.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('朝向必须是数字（度）。')
        return {'type': type_key, 'mode': self.current_mode(),
                'heading_deg': heading, 'mount': self.current_mount()}

    def current_number(self):
        return data.build_plate_number(
            self._series.get(), self.current_type(), self.current_mode())

    def set_status(self, message, is_error=False):
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass

    def set_result(self, result):
        self._preview_info.set(
            '预览：%s，连接板 %.0f×%.0f×%.0f，%d-φ%.0f 孔（F=%.0f），'
            'M%.0f×%.0f 螺栓 ×%d，单元含 %d 个子元素。' % (
                data.mode_label(result['mode']),
                result['E'], result['E'], result['T'],
                result['bolt_count'], result['G'], result['F'],
                result['bolt_dia'], result['bolt_length'],
                result['bolt_count'], result['child_count'],
            )
        )

    def refresh_spec(self):
        type_key = self.current_type()
        table = data.PLATE_TABLE.get(type_key)
        if table is None:
            self._spec.set('类型有误。')
            return
        mode = self.current_mode()
        hole_dia = table['G_ins'] if mode == 'H' else table['G_cold']
        bolt_length = table['L_ins'] if mode == 'H' else table['L_cold']
        self._plate_text.set('%.0f×%.0f×%.0f（板厚 T=%.0f）' % (
            table['E'], table['E'], table['T'], table['T']))
        self._hole_text.set('%d-φ%.0f 孔，F=%.0f 方阵（%s）' % (
            table['bolt_count'], hole_dia, table['F'], data.mode_label(mode)))
        self._bolt_text.set('M%.0f×%.0f 六角头螺栓 ×%d' % (
            table['D'], bolt_length, table['bolt_count']))
        number = self.current_number()
        self._number_text.set(number if number else '（系列留空，不附加编号）')
        try:
            self._spec.set(data.describe_spec(self.current_options()))
        except (ValueError, RuntimeError) as error:
            self._spec.set('参数有误：%s' % error)

    def _set_busy(self, busy):
        for combo in (self._type_combo, self._mode_combo, self._mount_combo):
            try:
                combo.configure(state='disabled' if busy else 'readonly')
            except tk.TclError:
                pass
        for entry in (self._series_entry, self._heading_entry):
            try:
                entry.configure(state='disabled' if busy else 'normal')
            except tk.TclError:
                pass
        for button in (self.confirm_button, self.cancel_button):
            button.set_enabled(not busy)
        try:
            self.update_idletasks()
        except tk.TclError:
            pass

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay):
        self._cancel_pending_regeneration()
        if self.placement_point is None:
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

    def regenerate(self, placement_point=None):
        """按当前选项重建预览：先建新的一版，成功后再删掉旧的。"""
        self._cancel_pending_regeneration()
        if placement_point is not None:
            self.placement_point = _copy_dpoint(placement_point)
        if self.placement_point is None:
            return None

        try:
            options = self.current_options()
            data.resolve_options(options)
        except (ValueError, RuntimeError) as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成连接板预览，请稍候……')
        try:
            handle, result, deleted = geom.replace_connection_plate(
                self.placement_point, options, self.preview_handle,
                self.current_number())
        except Exception as error:
            message = '连接板生成失败：%s' % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.set_result(result)
        self.refresh_spec()
        message = (
            '预览已更新：%s，连接板 %.0f×%.0f×%.0f，%d-φ%.0f 孔，'
            'M%.0f×%.0f 螺栓 ×%d，单元含 %d 个子元素，编号 %s。%s'
            '改参数会自动重建；点【确定】保留，点【取消】放弃。'
            % (data.mode_label(result['mode']), result['E'], result['E'],
               result['T'], result['bolt_count'], result['G'],
               result['bolt_dia'], result['bolt_length'],
               result['bolt_count'], result['child_count'],
               result.get('plate_number') or '—',
               '已替换上一版预览。' if deleted else ''))
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return geom._delete_element(handle)

    def export_bom(self):
        output_path = geom.export_bom_json()
        if output_path is not None:
            self.set_status('清单已导出：%s' % output_path)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        """结束原生工具并收起面板：点【确定】/【取消】/关闭都走这里，退回默认命令。"""
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
# 交互工具
# ---------------------------------------------------------------------------


class ConnectionPlatePlacementTool(DgnPrimitiveTool):
    """点取设备表面上的连接板中心并放置连接板（含螺栓）的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('ConnectionPlatePlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            '请点取设备表面上连接板背面的中心点；点取后可改类型 / 工况 / '
            '系列 / 安装面 / 朝向，预览会自动重建，点【确定】保留，'
            '点【取消】或右键放弃。')

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            try:
                settings.after(0, settings.cancel_tool)
            except Exception:
                pass
        return True

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
            active = getattr(ConnectionPlatePlacementTool,
                             '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _ConnectionPlateDialog())
        if owner:
            ConnectionPlatePlacementTool._active_settings = settings
        tool = ConnectionPlatePlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                ConnectionPlatePlacementTool._active_settings = None
        return tool


def show_connection_plate_dialog():
    return ConnectionPlatePlacementTool.InstallNewInstance(0)


def export_connection_plate_bom():
    return geom.export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYNPLATE PLACE / PYNPLATE EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '连接板.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenNPlate():
    PyMain()


def ExportNPlateBom():
    export_connection_plate_bom()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _log('PyMain: entry')
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_connection_plate_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('连接板工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'N8-设备连接板启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


show_connection_plate_dialog_entry = PyMain


if __name__ == '__main__':
    PyMain()
