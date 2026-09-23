# -*- coding: utf-8 -*-
"""管道信息查询 —— 在 OPM 中点取一个管道，读出它的属性与定位信息。

**做什么**：面板上点【点取管道】，然后在模型里点一个管道（或管道元件），
面板立刻显示：

* **管道属性（EC）**：管线号、公称直径、外径、壁厚、保温材料 / 保温厚度、
  管道等级、材质、元件名称……（读 OpenPlant 3D 实例的
  ``PIPING_COMPONENT`` / ``PIPE`` 属性）；
* **几何 / 定位**：中心线标高、管段长度、起终点坐标、走向（水平 / 竖直 / 倾斜）；
* **推算**：保温后外径（= 外径 + 2×保温厚度）、保温层外半径、由外径反查公称直径。

**关于单位**：OpenPlant 3D 的 EC Schema 里长度属性是裸 double，没有单位标注，
存米还是存毫米取决于项目。本工具不猜死，而是拿**属性 ``LENGTH`` 与几何长度
互校**自动标定（见 ``模块/管道信息/管道信息_读取.py``），并在面板上给出
「属性单位」下拉供手动指定；标定不成立时会明确提示"建议手动确认"。

**只读**：本插件不生成、不修改任何几何，也不写 ItemType。

面板用 **Tkinter** 实现，外观沿用仓库共享的 ``bentley_ui`` 主题（卡片 / 圆角
按钮 / 细滚动条），并自动记住上次窗口位置与单位选择。

命令：``PYPIPEINFO PICK``（打开面板点取）、``PYPIPEINFO REPORT``
（对当前选择集第一个元素直接出报告，不打开面板）。

运行环境：OpenPlant Modeler / MicroStation MSPython。
"""

from __future__ import division

import datetime
import importlib
import importlib.util
import os
import sys
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *  # noqa: F401,F403
from MSPyBentleyGeom import *  # noqa: F401,F403
from MSPyECObjects import *  # noqa: F401,F403
from MSPyDgnPlatform import *  # noqa: F401,F403
from MSPyDgnView import *  # noqa: F401,F403
from MSPyMstnPlatform import *  # noqa: F401,F403

# 通配导入不一定导出这两个符号，显式再导入一次；万一显式导入也失败，
# 下面 fill_mspy_symbols 还会按名字再补一次。
try:
    from MSPyBentley import WString  # noqa: E402,F811
except Exception:
    pass
try:
    from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 仓库根提供共享 UI 工具箱 bentley_ui；本插件自身的读取库在 模块/管道信息/。
INFO_DIR = os.path.join(HERE, '模块', '管道信息')
for _path in (REPO_ROOT, INFO_DIR):
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
    BG,
    BORDER,
    CARD,
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


def _load_module(name, file_path):
    """按文件路径加载模块；已加载则强制重读，规避 MicroStation 的模块缓存。

    必须这样做：MicroStation 会话里 ``sys.modules`` 会保留**上次运行**加载的
    模块对象，直接 ``import`` 只会拿到旧代码（旧版本没有新加的接口，
    于是报 "module has no attribute ..."）。
    """
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


# 读取库按文件路径强制重读：它是最常改动、接口也最容易变的一块。
reader = _load_module('管道信息_读取',
                      os.path.join(INFO_DIR, '管道信息_读取.py'))

# 接口版本自检：磁盘上是旧版读取库时给出明确提示，而不是崩在导入期。
REQUIRED_READER_API = 11
READER_API_OK = (getattr(reader, 'READER_API_VERSION', None)
                 == REQUIRED_READER_API)


# 本插件（入口 + 读取库）用到的 Bentley 符号。``from MSPyX import *`` 只导出
# 其中一部分——``ISessionMgr`` 就是典型漏网的——所以统一按名字补绑，
# 不再逐个去猜"这个符号属于哪个模块"。
ENTRY_MSPY_SYMBOLS = (
    'AccuSnap',
    'DgnElementSetTool',
    'ElementHandle',
    'MessageCenter',
    'NotificationManager',
    'PyCadInputQueue',
    'PythonKeyinManager',
    'SelectionSetManager',
    'WString',
)
# 补齐入口脚本自己用到的符号；读取库缺 fill_mspy_symbols（旧版本）时降级为空。
_fill_mspy = getattr(reader, 'fill_mspy_symbols', None)
ENTRY_MSPY_BOUND = _fill_mspy(ENTRY_MSPY_SYMBOLS, globals()) if _fill_mspy else []
MISSING_MSPY_SYMBOLS = [name for name in ENTRY_MSPY_SYMBOLS
                        if name not in globals()]


def _startup_notice():
    """环境自检：缺符号 / 读取库版本不对时给出可读提示。

    这两种情况都是"装了旧文件"或"运行环境缺符号"造成的，提前说清楚，
    而不是等到点取时才抛一个莫名的 NameError / AttributeError。
    """
    problems = []
    if not READER_API_OK:
        problems.append(
            '读取库版本不匹配（需要 v%s，磁盘上是 %s）——请用完整的新版本覆盖 '
            '管道信息查询 整个目录。'
            % (REQUIRED_READER_API,
               getattr(reader, 'READER_API_VERSION', '未标注版本')))
    missing = list(getattr(reader, 'MSPY_MISSING', None) or [])
    missing += list(MISSING_MSPY_SYMBOLS)
    if missing:
        problems.append('运行环境缺少 Bentley 符号：%s。' % '、'.join(missing))
    return '；'.join(problems) if problems else None


STARTUP_NOTICE = _startup_notice()


LOG_DIR = os.path.join(HERE, '模块', '日志')
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    pass
DEBUG_LOG = os.path.join(LOG_DIR, '管道信息查询_debug_log.txt')

UI_TITLE = '管道信息查询'


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n'
                         % (datetime.datetime.now().strftime('%H:%M:%S'),
                            message))
    except Exception:
        pass


def _log_exception(title):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('%s: %s\n' % (title, traceback.format_exc()))
    except Exception:
        pass


def _reset_log():
    """每次启动清空调试日志——只保留最近一次运行，避免长期累积占空间。"""
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(DEBUG_LOG, 'w', encoding='utf-8') as stream:
            # 用 chr(10) 而不是转义写法，免得脚本层再吞一次反斜杠。
            stream.write('=== 管道信息查询启动 %s ===%s' % (stamp, chr(10)))
    except Exception:
        pass


def _reload_runtime_modules():
    """每次运行都强制重新读取依赖，规避 MicroStation 的模块缓存。"""
    importlib.invalidate_caches()
    try:
        importlib.reload(reader)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 「全部属性」窗口：把选中元素上的 EC 属性原样列出来，便于排查
# ---------------------------------------------------------------------------


class _DumpWindow(tk.Toplevel):
    """把当前元素上的全部 EC 属性原样显示出来（只读）。"""

    def __init__(self, master, text):
        tk.Toplevel.__init__(self, master)
        self.title('全部 EC 属性')
        self.configure(bg=BG)
        self.transient(master)
        try:
            self.attributes('-topmost', True)
        except tk.TclError:
            pass

        shell = tk.Frame(self, bg=BG, padx=12, pady=12)
        shell.pack(fill='both', expand=True)

        header = tk.Frame(shell, bg=BG)
        header.pack(fill='x', pady=(0, 8))
        dot = tk.Canvas(header, width=9, height=9, bg=BG,
                        highlightthickness=0, bd=0)
        dot.create_oval(1, 1, 8, 8, fill="#4A66E0", outline="")
        dot.pack(side='left', pady=(6, 0), padx=(2, 8))
        tk.Label(header, text='全部 EC 属性', bg=BG, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')

        card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill='both', expand=True)
        text_frame = tk.Frame(card, bg=CARD)
        text_frame.pack(fill='both', expand=True, padx=8, pady=8)

        self._text = tk.Text(
            text_frame, wrap='word', bg=CARD, fg=INK, relief='flat',
            highlightthickness=0, bd=0, font=('Consolas', 10), padx=4, pady=4)
        scroll = SlimScrollbar(text_frame, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.insert('1.0', text)
        self._text.configure(state='disabled')
        self._text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        close_button = RoundButton(shell, '关闭', self.destroy, bg=BG,
                                   font=UI_FONT, font_bold=UI_FONT_BOLD)
        close_button.pack(anchor='e', pady=(8, 0))

        self.update_idletasks()
        self.geometry('%dx%d' % (min(760, self.winfo_screenwidth() - 120),
                                 min(560, self.winfo_screenheight() - 160)))
        if master is not None:
            try:
                x = master.winfo_rootx() + 60
                y = master.winfo_rooty() + 40
                self.geometry('+%d+%d' % (x, y))
            except tk.TclError:
                pass


# ---------------------------------------------------------------------------
# 主面板
# ---------------------------------------------------------------------------


class _PipeInfoDialog(GlassDialog):
    STATE_KEY = 'PipeInfoQuery'
    # 分组顺序；没读到的分组不显示占位行。
    GROUP_ORDER = ('元素', '单位', '管道属性', '几何', '推算')

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self._status = tk.StringVar()
        self._pending_element_id = None
        self._element_id = None
        self._info = None
        self._dump_window = None
        self._unit_value_by_label = {label: value
                                     for value, label in reader.UNIT_OPTIONS}

        self._build()
        self._render(None)
        self.restore_state()
        self.restore_position()
        self.after(80, self._poll_pending)
        if STARTUP_NOTICE:
            self.set_status(STARTUP_NOTICE, True)

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点取管道读取属性与定位信息 · 只读')
        form.columnconfigure(0, weight=1)

        tk.Label(
            form,
            text='点【点取管道】后在模型中点一个管道 / 管道元件；右键退出点取，'
                 '可继续点其它管道。本工具只读，不修改模型。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=380,
        ).grid(row=0, column=0, sticky='w')

        report_box = tk.Frame(form, bg=CARD, highlightbackground=BORDER,
                              highlightthickness=1)
        report_box.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        self._report_scroll = ScrollFrame(report_box, bg=CARD, height=330)
        self._report_scroll.pack(fill='both', expand=True)
        self._report_body = self._report_scroll.body
        self._report_body.columnconfigure(0, minsize=104)
        self._report_body.columnconfigure(1, weight=1)
        self.bind('<MouseWheel>', self._on_report_wheel)

        self.make_status_chip(form, self._status, wraplength=380).grid(
            row=2, column=0, sticky='ew', pady=(8, 0))

        options = tk.Frame(form, bg=CARD)
        options.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        tk.Label(options, text='属性单位：', bg=CARD, fg=INK,
                 font=UI_FONT).pack(side='left')
        self._unit = tk.StringVar(value=reader.UNIT_OPTIONS[0][1])
        self._unit_combo = ttk.Combobox(
            options, textvariable=self._unit, state='readonly', width=10,
            style='Glass.TCombobox',
            values=[label for _value, label in reader.UNIT_OPTIONS])
        self._unit_combo.pack(side='left', padx=(6, 0))
        self._unit_combo.bind('<<ComboboxSelected>>', self.on_unit_changed)
        self._element_label = tk.Label(options, text='', bg=CARD, fg=MUTED,
                                       font=UI_FONT_SMALL)
        self._element_label.pack(side='left', padx=(12, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=4, column=0, sticky='ew', pady=(10, 0))
        self._pick_button = RoundButton(
            buttons, '点取构件', self.start_pick, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._dump_button = RoundButton(
            buttons, '全部属性', self.show_dump, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._clear_button = RoundButton(
            buttons, '清空', self.clear_info, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._close_button = RoundButton(
            buttons, '关闭', self.destroy, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._pick_button.pack(side='left')
        self._close_button.pack(side='right')
        self._clear_button.pack(side='right', padx=(0, 8))
        self._dump_button.pack(side='right', padx=(0, 8))

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        unit = self.ui_state.get('unit')
        if unit:
            for value, label in reader.UNIT_OPTIONS:
                if value == unit:
                    self._unit.set(label)
                    break

    def persist_state(self, state):
        try:
            state['unit'] = self._unit_value_by_label.get(
                self._unit.get(), 'auto')
        except Exception:
            pass

    # -- 渲染 --------------------------------------------------------------

    def _render(self, info):
        for child in self._report_body.winfo_children():
            child.destroy()
        rows = reader.build_report_rows(info) if info else []
        grouped = {}
        order = []
        for group, item, value, note in rows:
            if group not in grouped:
                grouped[group] = []
                order.append(group)
            grouped[group].append((item, value, note))
        line = 0
        for group in order:
            if line:
                separator = tk.Frame(self._report_body, bg=BORDER, height=1)
                separator.grid(row=line, column=0, columnspan=2, sticky='ew',
                               pady=(9, 4))
                line += 1
            tk.Label(self._report_body, text=group, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w').grid(
                         row=line, column=0, columnspan=2, sticky='w')
            line += 1
            for item, value, note in grouped[group]:
                tk.Label(self._report_body, text=item, bg=CARD, fg=MUTED,
                         font=UI_FONT, anchor='nw', justify='left',
                         wraplength=104).grid(row=line, column=0, sticky='nw',
                                              padx=(2, 8), pady=2)
                cell = tk.Frame(self._report_body, bg=CARD)
                cell.grid(row=line, column=1, sticky='ew', pady=2)
                tk.Label(cell, text=value, bg=CARD, fg=INK, font=UI_FONT_BOLD,
                         anchor='w', justify='left', wraplength=250).pack(
                             anchor='w')
                if note:
                    tk.Label(cell, text=note, bg=CARD, fg=MUTED,
                             font=UI_FONT_SMALL, anchor='w', justify='left',
                             wraplength=250).pack(anchor='w')
                line += 1
        self._report_scroll.scroll_to_top()
        self._show_warnings(info)

    def _on_report_wheel(self, event):
        self._report_scroll.scroll_units(-1 if event.delta > 0 else 1)
        return 'break'

    def _show_warnings(self, info):
        if not info:
            self.set_status('等待点取管道……')
            return
        warnings = info.get('warnings') or []
        if warnings:
            self.set_status('；'.join(warnings), True)
            return
        geometry = info.get('geometry') or {}
        bbox = info.get('bbox') or {}
        if geometry.get('centerline_z_mm') is not None:
            elevation_text = '%.1f mm' % geometry['centerline_z_mm']
        elif bbox.get('center_mm'):
            elevation_text = '%.1f mm（包围盒近似）' % bbox['center_mm'][2]
        else:
            elevation_text = '—'
        message = (
            '已读取：%s ｜ 中心线标高 %s ｜ 走向 %s。右键退出点取。'
            % (info.get('ec', {}).get('class') or '未知类',
               elevation_text,
               geometry.get('orientation') or '—'))
        notes = info.get('notes') or []
        if notes:
            message = '%s\n%s' % (message, ' '.join(notes))
        if info.get('bbox_cross_note'):
            message = '%s\n%s' % (message, info['bbox_cross_note'])
        self.set_status(message)

    def set_status(self, message, is_error=False):
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass

    # -- 读取 --------------------------------------------------------------

    def _poll_pending(self):
        pending = self._pending_element_id
        if pending is not None:
            self._pending_element_id = None
            self.inspect_element(pending)
        if tk._default_root is not None:
            try:
                self.after(80, self._poll_pending)
            except tk.TclError:
                pass

    def queue_inspect(self, element_id):
        """点取工具调用：只排队，不在工具回调里做 EC 读取。"""
        self._pending_element_id = element_id
        self.set_status('已定位元素 %s，正在读取……' % element_id)

    def inspect_element(self, element_id):
        """按元素 ID 读取并刷新面板（工具回调 / keyin 都走这里）。

        这里**只把元素 ID 传进来**，句柄当场按 ID 重新取、用完即弃，
        不在面板里保留任何 Bentley 对象。
        """
        _log('[点取] --- 元素 %s ---' % element_id)
        try:
            handle = reader.element_handle_by_id(element_id)
        except Exception as error:
            _log_exception('open element handle failed')
            self.set_status('打开元素失败：%s' % error, True)
            return None
        if handle is None:
            self.set_status('元素 ID %s 已失效（可能已被删除）。' % element_id,
                            True)
            return None

        override = self._unit_value_by_label.get(self._unit.get(), 'auto')
        try:
            info = reader.collect_pipe_info(handle, override, log=_log)
        except Exception as error:
            _log_exception('collect pipe info failed')
            self.set_status('读取失败：%s' % error, True)
            return None

        self._element_id = info.get('elementId') or element_id
        self._info = info
        self._render(info)
        ec = info.get('ec') or {}
        try:
            self._element_label.configure(
                text='元素 ID %s ｜ %s'
                     % (self._element_id,
                        ec.get('class') or '无管道 EC 实例'))
        except tk.TclError:
            pass
        _log(reader.format_report_text(info))
        self.lift()
        return info

    def on_unit_changed(self, event=None):
        """切换属性单位：只重算快照，不再访问元素。"""
        if self._info is None:
            return
        try:
            info = reader.reapply_unit(self._info, self._unit_value_by_label.get(
                self._unit.get(), 'auto'))
        except Exception as error:
            _log_exception('unit override refresh failed')
            self.set_status('切换单位失败：%s' % error, True)
            return
        self._render(info)
        _log(reader.format_report_text(info))

    def clear_info(self):
        self._element_id = None
        self._info = None
        try:
            self._element_label.configure(text='')
        except tk.TclError:
            pass
        self._render(None)

    def show_dump(self):
        """列出当前元素上的**全部** EC 属性（原样），便于排查属性名。"""
        info = self._info or {}
        lines = []
        if self._element_id is None:
            lines.append('当前没有读取过元素。请先点取一个管道。')
        else:
            lines.append(reader.format_report_text(info) if info else '')
            lines.append('')
            # 实时按 ID 重新取句柄，不依赖任何缓存的 Bentley 对象。
            lines.append(reader.dump_element(self._element_id))
        if self._dump_window is not None:
            try:
                self._dump_window.destroy()
            except Exception:
                pass
        try:
            self._dump_window = _DumpWindow(self, '\n'.join(lines))
        except Exception:
            _log_exception('open dump window failed')

    # -- 点取 --------------------------------------------------------------

    def start_pick(self):
        self.set_status('请在模型中点取一个管道 / 管道元件；右键退出点取。')
        self.lift()
        try:
            PipeInfoPickTool.InstallNewInstance(0, self, False)
        except Exception as error:
            _log_exception('install pick tool failed')
            self.set_status('点取工具启动失败：%s' % error, True)

    def on_tool_started(self):
        """工具装好后把面板提到最前，免得点取时读不到数。"""
        self.lift()

    def on_tool_stopped(self, message=None):
        if message:
            self.set_status(message)

    # -- 窗口 --------------------------------------------------------------

    def destroy(self):
        try:
            if self._dump_window is not None:
                self._dump_window.destroy()
                self._dump_window = None
        except Exception:
            pass
        GlassDialog.destroy(self)


# ---------------------------------------------------------------------------
# 交互工具：点取管道（只读）
# ---------------------------------------------------------------------------


class PipeInfoPickTool(DgnElementSetTool):
    """点取一个管道 / 管道元件，把属性读进面板；可连续点取。

    **只读工具**：刻意不实现 ``_OnElementModify``——那是"元素即将被修改"的
    回调，只读查询走它会让框架进入修改 / 替换元素的流程。这里改为：

    * ``_OnPostLocate``：鼠标定位到元素时只记下**元素 ID**（不保留句柄）；
    * ``_OnDataButton``：把元素 ID 交给面板排队，立刻返回、消费掉这次点击。

    **EC 读取不在回调里做**：实测在工具回调内部访问 EC 实例会让 OPM 直接崩溃，
    而在"脚本 / 事件循环"上下文里同样的调用完全正常。所以点击只排队，真正的
    读取由面板的事件循环在 ``PythonMainLoop()`` 返回之后执行。
    """

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = None
        self._located_id = None

    def _GetToolName(self, name):
        return WString('PipeInfoPickTool')

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
            '请点取一个管道 / 管道元件以读取其属性；可连续点取，右键退出。')
        if self.panel is not None:
            try:
                self.panel.on_tool_started()
            except Exception:
                pass

    def _OnPostLocate(self, path, cant_accept_reason):
        """记录当前定位到的元素 ID（只取 ID，不保存句柄）。"""
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = reader.read_element_id(handle)
            return self._located_id is not None
        except Exception:
            _log_exception('post locate failed')
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        """把定位到的元素 ID 交给面板排队；返回 True 消费本次点击。

        这里**刻意不做任何 EC 读取**——回调内部访问 EC 实例会让 OPM 崩溃，
        读取由面板事件循环在 PythonMainLoop 返回之后执行。
        """
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            try:
                self.panel.set_status(
                    '没有定位到元素：请把光标放在管道上再点击。', True)
            except Exception:
                pass
            return True
        try:
            self.panel.queue_inspect(element_id)
        except Exception:
            _log_exception('queue inspect failed')
        return True

    def _OnRestartTool(self):
        # 保留面板引用重装工具，从而可以连续点取多个管道。
        panel = self.panel
        self.panel = None
        PipeInfoPickTool.InstallNewInstance(self.GetToolId(), panel, False)

    def _OnCleanup(self):
        panel = self.panel
        self.panel = None
        if panel is None:
            return
        try:
            panel.on_tool_stopped('已退出点取模式；再点【点取管道】可继续。')
        except Exception:
            pass

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_ui_loop=True):
        tool = PipeInfoPickTool(tool_id)
        tool.panel = panel
        tool.InstallTool()
        if start_ui_loop and panel is not None:
            panel.run_bentley_loop()
        return tool


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

_active_dialog = None


def show_pipe_info_panel():
    """打开管道信息面板；已打开时只把窗口提到前台，避免重复窗口。"""
    global _active_dialog
    if _active_dialog is not None:
        try:
            if _active_dialog.winfo_exists():
                _active_dialog.lift()
                return _active_dialog
        except tk.TclError:
            pass
    dialog = _PipeInfoDialog()
    _active_dialog = dialog
    try:
        dialog.run_bentley_loop()
    finally:
        _active_dialog = None
    return dialog


def _first_selected_element():
    """取选择集里第一个元素句柄；没有选中元素时返回 ``None``。"""
    try:
        manager = SelectionSetManager.GetManager()
        if manager.NumSelected() <= 0:
            return None
        handle = ElementHandle()
        manager.GetElement(0, handle)
        if handle.IsValid():
            return handle
    except Exception:
        _log_exception('read selection set failed')
    return None


def report_selected_pipe():
    """``PYPIPEINFO REPORT``：对当前选中的第一个元素直接出报告（不开面板）。"""
    handle = _first_selected_element()
    if handle is None:
        MessageCenter.ShowErrorMessage(
            '请先在模型中选中一个管道 / 管道元件，再执行 PYPIPEINFO REPORT。',
            '', False)
        return None
    try:
        info = reader.collect_pipe_info(handle, 'auto', log=_log)
    except Exception as error:
        _log_exception('report selected pipe failed')
        MessageCenter.ShowErrorMessage('读取失败：%s' % error, '', False)
        return None
    text = reader.format_report_text(info)
    _log(text)
    try:
        print(text)
    except Exception:
        pass
    MessageCenter.ShowInfoMessage(
        '管道信息已读出（共 %d 行），详见控制台与调试日志：\n%s'
        % (len(text.splitlines()), DEBUG_LOG), '', False)
    return info


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYPIPEINFO PICK / PYPIPEINFO REPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(INFO_DIR, '管道信息查询.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenPipeInfoPanel():
    show_pipe_info_panel()


def ReportSelectedPipe():
    report_selected_pipe()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _reload_runtime_modules()
    _reset_log()
    _log('MSPy 符号自检：读取库补齐 %s / 缺失 %s；入口补齐 %s / 缺失 %s'
         % (reader.MSPY_BOUND, reader.MSPY_MISSING,
            ENTRY_MSPY_BOUND, MISSING_MSPY_SYMBOLS))
    if STARTUP_NOTICE:
        print(STARTUP_NOTICE)
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        show_pipe_info_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('pipe info tool start failed')
        print('管道信息查询插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '管道信息查询启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
