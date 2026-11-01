# -*- coding: utf-8 -*-
"""管道支吊架统计（只读）。

统计当前活动 DGN 中的**管道支吊架**（端焊三角架、L 型管架、门型架，以及今后
接入的其它支吊架）——按类型统计套数，并可导出：

* **Excel**：一张 .xlsx，含「汇总 / 支吊架表 / 材料汇总表」三个工作表；
* **JSON**：统一清单（供程序读取）。

本插件**不生成任何几何**，只读取公共库 ``PipeSupportComponents``。

面板用 **Tkinter**，外观沿用仓库共享的 ``bentley_ui``（卡片 / 圆角按钮）。
运行环境：OpenPlant / MicroStation MSPython。
"""

from __future__ import division

import datetime
import importlib
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import filedialog, ttk

from MSPyBentley import *  # noqa: F401,F403
from MSPyDgnView import *  # noqa: F401,F403
from MSPyMstnPlatform import *  # noqa: F401,F403


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 仓库根提供共享 UI 工具箱 bentley_ui；公共库在 模块/公共/。
_COMMON_DIR = os.path.join(HERE, '模块', '公共')
for _path in (REPO_ROOT, _COMMON_DIR):
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
    CARD_SOFT,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    SlimScrollbar,
)

import 支吊架公共库 as psb  # noqa: E402


DEBUG_LOG = os.path.join(HERE, '模块', '日志', '支吊架统计_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = '00-[支吊架统计]'
DEFAULT_XLSX = os.path.join(HERE, '模块', '输出', '管道支吊架_bom.xlsx')
DEFAULT_JSON = os.path.join(HERE, '模块', '输出', '管道支吊架_bom.json')


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


class _SupportReportDialog(GlassDialog):
    """统计结果 + 刷新 / 导出 Excel / 导出 JSON 面板。"""

    STATE_KEY = 'SupportStatistics'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.statistics = None
        self._total = tk.StringVar(value='—')
        self._detail = tk.StringVar(value='—')
        self._build()
        self.restore_position()
        try:
            self.minsize(620, 480)
        except tk.TclError:
            pass
        _log('panel built file=%s' % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '读取当前活动 DGN 中的管道支吊架 · 仅统计、不生成几何')
        form.columnconfigure(1, weight=1)

        tk.Label(
            form,
            text='点击【刷新】读取当前活动文件；统计结果来自公共库 '
                 'PipeSupportComponents，凡是按共享契约写入的支吊架都会汇总。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=560).grid(row=0, column=0, columnspan=2, sticky='w')

        ttk.Label(form, text='统计结果', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(8, 2))

        ttk.Label(form, text='支吊架总套数', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._total, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=2, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='按类型', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='nw', pady=3)
        self._type_frame, self._type_text = self._text_field(form, height=4)
        self._type_frame.grid(row=3, column=1, sticky='ew', padx=(10, 0),
                              pady=3)

        ttk.Label(form, text='记录数', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=3)
        tk.Label(form, textvariable=self._detail, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w').grid(
            row=4, column=1, sticky='w', padx=(10, 0), pady=3)

        ttk.Label(form, text='状态', style='Section.TLabel').grid(
            row=5, column=0, columnspan=2, sticky='w', pady=(8, 2))
        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=6, column=0, columnspan=2, sticky='ew')
        self._set_text(self._status_text, '点击【刷新】读取当前活动文件。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        self.refresh_button = RoundButton(
            buttons, '刷新', self.refresh, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.excel_button = RoundButton(
            buttons, '导出 Excel 清单', self.export_excel, primary=True,
            bg=CARD, font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.json_button = RoundButton(
            buttons, '导出 JSON', self.export_json, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button = RoundButton(
            buttons, '关闭', self.close_report, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button.pack(side='right')
        self.json_button.pack(side='right', padx=(0, 8))
        self.excel_button.pack(side='right', padx=(0, 8))
        self.refresh_button.pack(side='right', padx=(0, 8))

    def _text_field(self, parent, height=3):
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

    def set_status(self, message, is_error=False):
        self._set_text(getattr(self, '_status_text', None), message)

    # -- 统计 / 导出 -------------------------------------------------------

    def refresh(self):
        try:
            importlib.reload(psb)
        except Exception:
            pass
        self.set_status('正在读取当前活动文件……')
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        try:
            self.statistics = psb.collect_statistics()
        except Exception as error:
            _log_exception('collect statistics failed')
            self.set_status('读取失败：%s' % error, True)
            return
        statistics = self.statistics
        self._total.set('%d 套' % statistics['assemblyCount'])
        if statistics['supportsByType']:
            parts = ['%s %d 套' % (entry['supportType'], entry['assemblyCount'])
                     for entry in statistics['supportsByType']]
            self._set_text(self._type_text, '；'.join(parts))
        else:
            self._set_text(self._type_text, '（当前活动文件没有管道支吊架）')
        self._detail.set(
            '整组 %d 条，构件 %d 条，材料条目 %d 条。' % (
                len([r for r in statistics['records']
                     if r['recordKind'] == 'Assembly']),
                statistics['componentRecordCount'],
                len(statistics['materials'])))
        if statistics['records']:
            self.set_status('统计完成：共 %d 套管道支吊架。'
                            % statistics['assemblyCount'])
        else:
            self.set_status('当前活动文件没有管道支吊架记录（先用三角架 / '
                            'L 型管架 / 门型架插件放置）。')

    def _ask_save_path(self, default_path, title, kind):
        """弹原生「另存为」对话框，让用户选择保存位置；取消时返回 ''。"""
        initial_dir = os.path.dirname(default_path)
        if not os.path.isdir(initial_dir):
            initial_dir = HERE
        try:
            if kind == 'xlsx':
                filetypes = [('Excel 工作簿', '*.xlsx'), ('所有文件', '*.*')]
            else:
                filetypes = [('JSON 文件', '*.json'), ('所有文件', '*.*')]
            chosen = filedialog.asksaveasfilename(
                parent=self, title=title, initialdir=initial_dir,
                initialfile=os.path.basename(default_path),
                defaultextension='.%s' % kind, filetypes=filetypes)
        except tk.TclError:
            chosen = ''
        return chosen or ''

    def export_excel(self):
        self.refresh()
        if not self.statistics or not self.statistics['records']:
            self.set_status('没有可导出的管道支吊架。', True)
            return
        path = self._ask_save_path(DEFAULT_XLSX, '导出 Excel 清单', 'xlsx')
        if not path:
            self.set_status('已取消导出。')
            return
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        exported = psb.export_combined_xlsx(path, self.statistics, timestamp)
        if exported:
            self.set_status('Excel 清单已导出：%s' % exported)

    def export_json(self):
        self.refresh()
        if not self.statistics or not self.statistics['records']:
            self.set_status('没有可导出的管道支吊架。', True)
            return
        path = self._ask_save_path(DEFAULT_JSON, '导出 JSON 清单', 'json')
        if not path:
            self.set_status('已取消导出。')
            return
        exported = psb.export_combined_bom(path)
        if exported:
            self.set_status('JSON 清单已导出：%s' % exported)

    # -- 收尾 --------------------------------------------------------------

    def close_report(self):
        self.destroy()


_active_settings = None


def show_support_report():
    global _active_settings
    if _active_settings is not None:
        try:
            if _active_settings.winfo_exists():
                _active_settings.lift()
                return None
        except tk.TclError:
            pass
    dialog = _SupportReportDialog()
    _active_settings = dialog
    try:
        dialog.refresh()
        dialog.run_bentley_loop()
        return dialog
    finally:
        _active_settings = None


def PyMain():
    try:
        show_support_report()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('report tool start failed')
        print('管道支吊架统计启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '管道支吊架统计启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
