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
import traceback

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

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEvent, QEventLoop, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QAbstractScrollArea, QApplication, QFrame,
                             QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                             QScrollArea, QVBoxLayout, QWidget)

# pywin32 只用于"面板保持在 OPM 之上"这一条：缺了也不影响读取功能。
try:
    import win32gui
    import win32process
except Exception:  # pragma: no cover - 仅在无 pywin32 时触发
    win32gui = None
    win32process = None


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 点取工具的"统一外观 / 单位换算"公共库沿用 管道支吊架 的 模块/公共。
# 本插件自身的读取库在 模块/管道信息/。
SUPPORT_COMMON = os.path.join(REPO_ROOT, '管道支吊架', '模块', '公共')
INFO_DIR = os.path.join(HERE, '模块', '管道信息')
for _path in (SUPPORT_COMMON, INFO_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 端焊三角架_基础 as base  # noqa: E402


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
        base._log(message)
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


def _apply_base_overrides():
    """公共库的日志写到本插件目录（base 重新加载后会丢失，需重设）。"""
    base.DEBUG_LOG = DEBUG_LOG


def _reload_runtime_modules():
    """每次运行都强制重新读取依赖，规避 MicroStation 的模块缓存。"""
    importlib.invalidate_caches()
    for module in (reader, base):
        try:
            importlib.reload(module)
        except Exception:
            pass
    _apply_base_overrides()


def _host_window_hwnd():
    """找出当前 OPM 进程的主窗口（用于"面板始终在软件之上"）。"""
    if win32gui is None or win32process is None:
        return None
    candidates = []

    def collect(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32process.GetWindowThreadProcessId(hwnd)[1] != os.getpid():
                return
            if win32gui.GetWindow(hwnd, 4):
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            candidates.append(((right - left) * (bottom - top), hwnd))
        except Exception:
            return

    try:
        win32gui.EnumWindows(collect, None)
    except Exception:
        return None
    return max(candidates)[1] if candidates else None


# ---------------------------------------------------------------------------
# 无边框窗口的自绘标题栏（与 支吊架统计 一致：只保留关闭钮，空白处可拖动）
# ---------------------------------------------------------------------------


class _TitleBar(QWidget):

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


# ---------------------------------------------------------------------------
# 「全部属性」窗口：把选中元素上的 EC 属性原样列出来，便于排查
# ---------------------------------------------------------------------------


class _DumpDialog(QWidget):
    """「全部 EC 属性」窗口。

    以主面板为父窗口（Qt.Window + parent = 归属窗口）：作为面板的附属窗口，
    自然随面板一起保持在 OPM 之上，并在 OPM 最小化时一起收起。
    """

    RADIUS = base.UI_RADIUS

    def __init__(self, text, parent=None):
        base.ensure_qt_app()
        super().__init__(parent)
        self.setWindowTitle('全部 EC 属性')
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, base.UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')
        self._allow_close = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_TitleBar('全部 EC 属性', self.close_dump))

        body = QVBoxLayout()
        body.setContentsMargins(6, 0, 6, 6)
        body.setSpacing(6)
        outer.addLayout(body)

        self.view = QPlainTextEdit(text, self)
        self.view.setReadOnly(True)
        self.view.setStyleSheet(
            'QPlainTextEdit {background: #FFFFFF; border: none;'
            ' border-radius: 10px; padding: 8px; color: #39435A;'
            ' font-family: Consolas, "Microsoft YaHei UI"; font-size: 12px;}')
        body.addWidget(self.view)

        row = QHBoxLayout()
        row.addStretch(1)
        close_button = base.NeuButton('关闭')
        close_button.setFixedWidth(96)
        close_button.clicked.connect(self.close_dump)
        row.addWidget(close_button)
        body.addLayout(row)

        self.resize(720, 560)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.setMaximumSize(int(available.width() * 0.9),
                                int(available.height() * 0.9))
        # 停靠在主面板上方居中，避免默认落到屏幕角落。
        if parent is not None:
            center = parent.frameGeometry().center()
            self.move(max(0, center.x() - self.width() // 2),
                      max(0, center.y() - self.height() // 2))

    def close_dump(self):
        self._allow_close = True
        self.close()
        self.deleteLater()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.close_dump()

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


# ---------------------------------------------------------------------------
# 主面板
# ---------------------------------------------------------------------------


class _PipeInfoDialog(QWidget):

    RADIUS = base.UI_RADIUS
    # 卡片按这个顺序出现；每次都重建行，保证"读不到的不显示占位"。
    GROUP_ORDER = ('元素', '单位', '管道属性', '几何', '推算')

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

        self._running = True
        self._allow_close = False
        self._event_loop = QEventLoop()
        # 只记元素 ID，不留 Bentley 句柄：句柄只在工具回调期间有效。
        self._element_id = None
        # 点取工具排进来的待读元素 ID，由事件循环取出执行（不在回调里读）。
        self._pending_element_id = None
        self._info = None
        self._dump_dialog = None
        self._host_hwnd = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_TitleBar(UI_TITLE, self.close_panel))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(6)
        outer.addLayout(body)

        hint = QLabel('点【点取管道】后在模型中点一个管道 / 管道元件；'
                      '右键退出点取，可继续点其它管道。本工具只读，不修改模型。')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        body.addWidget(hint)

        # 卡片放进滚动区：属性行数可能到 30+，必须能滚动，否则会超出屏幕。
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.scroll.setStyleSheet(
            'QScrollArea {background: transparent; border: none;}'
            'QScrollArea > QWidget > QWidget {background: transparent;}'
            'QScrollBar:vertical {background: transparent; width: 8px;'
            ' margin: 2px;}'
            'QScrollBar::handle:vertical {background: #C3CCDC;'
            ' border-radius: 4px; min-height: 30px;}'
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical'
            ' {height: 0px;}')
        holder = QWidget(self.scroll)
        self._card_holder = QVBoxLayout(holder)
        self._card_holder.setContentsMargins(0, 0, 0, 0)
        self._card_holder.setSpacing(6)
        # 卡片一次性按 GROUP_ORDER 建好并隐藏；之后只显示 / 填内容，
        # 这样分组顺序永远固定，不会因某次读取缺项而错位。
        self._cards = {}
        for group in self.GROUP_ORDER:
            card = base.NeuCard(group)
            self._card_holder.addWidget(card)
            card.hide()
            self._cards[group] = card
        self._card_holder.addStretch(1)
        self.scroll.setWidget(holder)
        body.addWidget(self.scroll, 1)

        summary = base.NeuPanel()
        self.status_label = QLabel('等待点取管道……', self)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;' % base.UI_INFO.name())
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        option_row = QHBoxLayout()
        option_row.setContentsMargins(6, 0, 6, 0)
        option_row.setSpacing(8)
        unit_caption = QLabel('属性单位：', self)
        unit_caption.setStyleSheet('color: #39435A; font-size: 12px;')
        option_row.addWidget(unit_caption)
        self.unit_combo = base.NeuCombo(
            reader.UNIT_OPTIONS, current='auto',
            on_change=self.on_unit_changed, parent=self)
        option_row.addWidget(self.unit_combo)
        self.element_label = QLabel('', self)
        self.element_label.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        option_row.addWidget(self.element_label)
        option_row.addStretch(1)
        body.addLayout(option_row)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        self.pick_button = base.NeuButton('点取管道', accent=True)
        self.pick_button.setFixedWidth(140)
        self.pick_button.clicked.connect(self.start_pick)
        self.dump_button = base.NeuButton('全部属性')
        self.dump_button.setFixedWidth(120)
        self.dump_button.clicked.connect(self.show_dump)
        self.clear_button = base.NeuButton('清空')
        self.clear_button.setFixedWidth(96)
        self.clear_button.clicked.connect(self.clear_info)
        self.close_button = base.NeuButton('关闭')
        self.close_button.setFixedWidth(96)
        self.close_button.clicked.connect(self.close_panel)
        button_row.addStretch(1)
        button_row.addWidget(self.pick_button)
        button_row.addWidget(self.dump_button)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.close_button)
        body.addLayout(button_row)

        self.setMinimumWidth(660)
        self._cap_height()
        self._render(None)
        # 面板只在打开时定一次尺寸：无边框窗口不能拖边缩放，固定高度 +
        # 滚动区比"每次点取都自动伸缩"更稳定（不会跳来跳去）。
        self.resize(800, min(860, self.maximumHeight()))
        self._attach_to_host()
        if STARTUP_NOTICE:
            self.set_status(STARTUP_NOTICE, True)

    # -- 始终显示在 OPM 之上 ------------------------------------------------

    def _attach_to_host(self):
        """把自己挂成 OPM 的工具设置窗，并周期性地保持不被主窗遮挡。

        ``AttachQtToolSetting`` 让本窗口被 OPM 主窗"拥有"：始终位于主窗之上，
        且 **OPM 整体最小化时随主窗一起收起**——正是所需的行为。
        个别情况下仅靠它仍会被主窗遮住，所以再加一个只在"OPM 在前台"时才
        把自己提到最前的定时器；OPM 被最小化或切到别的程序时不动。
        """
        self._host_hwnd = _host_window_hwnd()
        try:
            self.hwnd = int(self.winId())
            PyCadInputQueue.AttachQtToolSetting(self.hwnd)
        except Exception:
            _log_exception('attach qt tool setting failed')

        self._top_timer = QTimer(self)
        self._top_timer.setInterval(1200)
        self._top_timer.timeout.connect(self._keep_above_host)
        self._top_timer.start()

    def _keep_above_host(self):
        if self._host_hwnd is None or not self.isVisible():
            return
        if win32gui is None:
            return
        try:
            if not win32gui.IsWindow(self._host_hwnd):
                return
            # 只有 OPM 处于前台而本面板被压到后面时才提上来；
            # OPM 最小化（不在前台）时保持不动，不打扰其它程序。
            if win32gui.GetForegroundWindow() != self._host_hwnd:
                return
        except Exception:
            return
        try:
            self.raise_()
        except RuntimeError:
            pass

    def _cap_height(self):
        """窗口高度不超过屏幕可用高度的 85%，超出部分交给滚动区。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.setMaximumHeight(int(available.height() * 0.85))
        self.setMaximumWidth(int(available.width() * 0.9))

    # -- 渲染 --------------------------------------------------------------

    def _clear_grid(self, grid):
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _render(self, info):
        rows = reader.build_report_rows(info) if info else []
        grouped = {}
        for group, item, value, note in rows:
            grouped.setdefault(group, []).append((item, value, note))
        for group in self.GROUP_ORDER:
            card = self._cards[group]
            entries = grouped.get(group)
            self._clear_grid(card.content)
            if not entries:
                card.hide()
                continue
            for row_index, (item, value, note) in enumerate(entries):
                caption = QLabel(item, self)
                caption.setStyleSheet('color: #7D8AA0; font-size: 12px;')
                value_label = QLabel(value, self)
                value_label.setWordWrap(True)
                value_label.setStyleSheet(
                    'color: #39435A; font-size: 13px; font-weight: 600;')
                card.content.addWidget(caption, row_index, 0,
                                       Qt.AlignLeft | Qt.AlignTop)
                # 值与备注**放在同一个单元格里上下排**：两者都吃满整列宽度。
                # 之前分成两列且加了 AlignLeft，标签只占"最小宽度"，导致列很宽
                # 而标签很窄——短数据也被折行、备注被挤出高度而显示不全。
                cell = QWidget(self)
                cell_box = QVBoxLayout(cell)
                cell_box.setContentsMargins(0, 0, 0, 0)
                cell_box.setSpacing(1)
                cell_box.addWidget(value_label)
                if note:
                    note_label = QLabel(note, self)
                    note_label.setWordWrap(True)
                    note_label.setStyleSheet(
                        'color: #9AA6BA; font-size: 11px;')
                    cell_box.addWidget(note_label)
                # 只用 AlignTop：横向**填满**单元格，文字才有足够宽度不折行。
                card.content.addWidget(cell, row_index, 1, Qt.AlignTop)
            # 名称列按内容取最小宽度，其余全给"值 + 备注"列。
            card.content.setColumnStretch(0, 0)
            card.content.setColumnStretch(1, 1)
            card.show()
            card.adjustSize()
        self._show_warnings(info)

    def _show_warnings(self, info):
        if not info:
            self.status_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_INFO.name())
            self.status_label.setText('等待点取管道……')
            return
        warnings = info.get('warnings') or []
        if warnings:
            self.status_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_ERROR.name())
            self.status_label.setText('；'.join(warnings))
        else:
            geometry = info.get('geometry') or {}
            bbox = info.get('bbox') or {}
            if geometry.get('centerline_z_mm') is not None:
                elevation_text = '%.1f mm' % geometry['centerline_z_mm']
            elif bbox.get('center_mm'):
                elevation_text = '%.1f mm（包围盒近似）' % bbox['center_mm'][2]
            else:
                elevation_text = '—'
            self.status_label.setStyleSheet(
                'color: %s; font-size: 11px;' % base.UI_INFO.name())
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
            self.status_label.setText(message)

    def set_status(self, message, is_error=False):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        QApplication.processEvents()

    # -- 读取 --------------------------------------------------------------

    def _log_stage(self, message):
        """读取过程的阶段日志：崩溃时最后一行即出问题的步骤。"""
        _log('[点取] %s' % message)

    def queue_inspect(self, element_id):
        """点取工具调用：只排队，不在工具回调里做 EC 读取。"""
        self._pending_element_id = element_id
        self.set_status('已定位元素 %s，正在读取……' % element_id)

    def inspect_element(self, element_id):
        """按元素 ID 读取并刷新面板（工具回调 / keyin 都走这里）。

        这里**只把元素 ID 传进来**，句柄当场按 ID 重新取、用完即弃，
        不在面板里保留任何 Bentley 对象。
        """
        self._log_stage('--- 元素 %s ---' % element_id)
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

        override = self.unit_combo.value()
        try:
            info = reader.collect_pipe_info(handle, override,
                                            log=self._log_stage)
        except Exception as error:
            _log_exception('collect pipe info failed')
            self.set_status('读取失败：%s' % error, True)
            return None

        self._element_id = info.get('elementId') or element_id
        self._info = info
        self._render(info)
        ec = info.get('ec') or {}
        self.element_label.setText(
            '元素 ID %s ｜ %s' % (self._element_id,
                                 ec.get('class') or '无管道 EC 实例'))
        _log(reader.format_report_text(info))
        self._raise_now()
        return info

    def _raise_now(self):
        """读到新数据后把自己提到最前（不抢键盘焦点）。"""
        try:
            self.raise_()
        except RuntimeError:
            pass

    def on_unit_changed(self):
        """切换属性单位：只重算快照，不再访问元素。"""
        if self._info is None:
            return
        try:
            info = reader.reapply_unit(self._info, self.unit_combo.value())
        except Exception as error:
            _log_exception('unit override refresh failed')
            self.set_status('切换单位失败：%s' % error, True)
            return
        self._render(info)
        _log(reader.format_report_text(info))

    def clear_info(self):
        self._element_id = None
        self._info = None
        self.element_label.setText('')
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
        if self._dump_dialog is not None:
            try:
                self._dump_dialog.deleteLater()
            except Exception:
                pass
        try:
            self._dump_dialog = _DumpDialog('\n'.join(lines), self)
            self._dump_dialog.show()
            self._dump_dialog.raise_()
            self._dump_dialog.activateWindow()
        except Exception:
            _log_exception('open dump dialog failed')

    # -- 点取 --------------------------------------------------------------

    def start_pick(self):
        self.set_status('请在模型中点取一个管道 / 管道元件；右键退出点取。')
        self._raise_now()
        try:
            PipeInfoPickTool.InstallNewInstance(0, self, False)
        except Exception as error:
            _log_exception('install pick tool failed')
            self.set_status('点取工具启动失败：%s' % error, True)

    def on_tool_started(self):
        """工具装好后把面板提到最前，免得点取时读不到数。"""
        self._raise_now()

    def on_tool_stopped(self, message=None):
        if message:
            self.set_status(message)

    # -- 窗口 --------------------------------------------------------------

    def close_panel(self):
        self._running = False
        self._allow_close = True
        try:
            if self._dump_dialog is not None:
                self._dump_dialog.close_dump()
                self._dump_dialog = None
        except Exception:
            pass
        try:
            self.close()
        except RuntimeError:
            pass

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
        self.close_panel()

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
            PyCadInputQueue.PythonMainLoop()
            # EC 读取**在工具回调之外**执行：点取工具只把元素 ID 放进队列，
            # 真正读属性发生在 PythonMainLoop 返回之后（与"直接执行脚本"同一
            # 上下文），这是实测唯一稳定的时机。
            pending = self._pending_element_id
            if pending is not None:
                self._pending_element_id = None
                self.inspect_element(pending)
        self._teardown_window()

    def _teardown_window(self):
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
            panel.run_dialog_loop()
        return tool


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

_active_dialog = None


def show_pipe_info_panel():
    """打开管道信息面板；已在运行时只把窗口提到前台，避免重复窗口。"""
    global _active_dialog
    if _active_dialog is not None:
        try:
            if _active_dialog._running:
                _active_dialog.raise_()
                _active_dialog.activateWindow()
                return _active_dialog
        except RuntimeError:
            pass
    dialog = _PipeInfoDialog()
    _active_dialog = dialog
    try:
        dialog.run_dialog_loop()
        return dialog
    finally:
        _active_dialog = None


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
            QMessageBox.critical(None, UI_TITLE, '启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
