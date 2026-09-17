# -*- coding: utf-8 -*-
"""管道支吊架统计（只读）。

统计当前活动 DGN 中的**管道支吊架**（端焊三角架、L 型管架，以及今后接入的
其它支吊架）——按类型统计套数，并可导出：

* **Excel**：一张 .xlsx，含「汇总 / 支吊架表 / 材料汇总表」三个工作表；
* **JSON**：统一清单（供程序读取）。

本插件**不生成任何几何**，只读取公共库 ``PipeSupportComponents``。

运行环境：OpenPlant / MicroStation MSPython。
"""

from __future__ import division

import datetime
import importlib
import os
import sys
import traceback

from MSPyBentley import *  # noqa: F401,F403
from MSPyDgnView import *  # noqa: F401,F403
from MSPyMstnPlatform import *  # noqa: F401,F403

# PyQt5 必须放在 MSPy 的 import * 之后。
from PyQt5.QtCore import QEventLoop, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QRegion
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                             QVBoxLayout, QWidget)


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import 端焊三角架_基础 as base  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


DEBUG_LOG = os.path.join(HERE, '支吊架统计_debug_log.txt')
base.DEBUG_LOG = DEBUG_LOG

UI_TITLE = '管道支吊架统计'
DEFAULT_XLSX = os.path.join(HERE, '管道支吊架_bom.xlsx')
DEFAULT_JSON = os.path.join(HERE, '管道支吊架_bom.json')


def _log_exception(title):
    try:
        base._log('%s: %s' % (title, traceback.format_exc()))
    except Exception:
        pass


class _ReportTitleBar(QWidget):
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


class _SupportReportDialog(QWidget):

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

        self.statistics = None
        self._running = True
        self._allow_close = False
        self._event_loop = QEventLoop()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_ReportTitleBar(UI_TITLE, self.close_report))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(6)
        outer.addLayout(body)

        hint = QLabel('读取当前活动 DGN 中的管道支吊架，仅统计、不生成几何。')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        body.addWidget(hint)

        card = base.NeuCard("统计结果")
        self.total_label = self._value('—')
        self._row(card.content, 0, "支吊架总套数：", [self.total_label])
        self.type_label = self._value('—')
        self._row(card.content, 1, "按类型：", [self.type_label])
        self.detail_label = self._value('—')
        self._row(card.content, 2, "记录数：", [self.detail_label])
        body.addWidget(card)

        summary = base.NeuPanel()
        self.status_label = QLabel('点击【刷新】读取当前活动文件。', self)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;' % base.UI_INFO.name())
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        self.refresh_button = base.NeuButton("刷新")
        self.refresh_button.setFixedWidth(96)
        self.refresh_button.clicked.connect(self.refresh)
        self.excel_button = base.NeuButton("导出 Excel 清单", accent=True)
        self.excel_button.setFixedWidth(168)
        self.excel_button.clicked.connect(self.export_excel)
        self.json_button = base.NeuButton("导出 JSON")
        self.json_button.setFixedWidth(120)
        self.json_button.clicked.connect(self.export_json)
        self.close_button = base.NeuButton("关闭")
        self.close_button.setFixedWidth(96)
        self.close_button.clicked.connect(self.close_report)
        button_row.addStretch(1)
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.excel_button)
        button_row.addWidget(self.json_button)
        button_row.addWidget(self.close_button)
        body.addLayout(button_row)

        self.refresh()
        self.setMinimumWidth(560)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))

    # -- 控件 --------------------------------------------------------------

    def _row(self, grid, row, name, widgets):
        label = QLabel(name, self)
        label.setStyleSheet('color: #39435A; font-size: 13px;')
        grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        holder = QWidget(self)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(10)
        for widget in widgets:
            line.addWidget(widget)
        line.addStretch(1)
        grid.addWidget(holder, row, 1)
        grid.setColumnStretch(1, 1)

    def _value(self, text):
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet('color: #39435A; font-size: 13px;'
                            ' font-weight: 600;')
        return label

    def set_status(self, message, is_error=False):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (base.UI_ERROR if is_error else base.UI_INFO).name())
        self.status_label.setText(message)
        QApplication.processEvents()

    # -- 统计 / 导出 -------------------------------------------------------

    def refresh(self):
        try:
            importlib.reload(psb)
        except Exception:
            pass
        try:
            self.statistics = psb.collect_statistics()
        except Exception as error:
            _log_exception('collect statistics failed')
            self.set_status('读取失败：%s' % error, True)
            return
        statistics = self.statistics
        self.total_label.setText('%d 套' % statistics['assemblyCount'])
        if statistics['supportsByType']:
            parts = ['%s %d 套' % (entry['supportType'], entry['assemblyCount'])
                     for entry in statistics['supportsByType']]
            self.type_label.setText('；'.join(parts))
        else:
            self.type_label.setText('（当前活动文件没有管道支吊架）')
        self.detail_label.setText(
            '整组 %d 条，构件 %d 条，材料条目 %d 条。' % (
                len([r for r in statistics['records']
                     if r['recordKind'] == 'Assembly']),
                statistics['componentRecordCount'],
                len(statistics['materials'])))
        if statistics['records']:
            self.set_status('统计完成：共 %d 套管道支吊架。'
                            % statistics['assemblyCount'])
        else:
            self.set_status('当前活动文件没有管道支吊架记录（先用端焊三角架 / '
                            'L 型管架插件放置）。')

    def export_excel(self):
        self.refresh()
        if not self.statistics or not self.statistics['records']:
            self.set_status('没有可导出的管道支吊架。', True)
            return
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        path = psb.export_combined_xlsx(
            DEFAULT_XLSX, self.statistics, timestamp)
        if path:
            self.set_status('Excel 清单已导出：%s' % path)

    def export_json(self):
        self.refresh()
        if not self.statistics or not self.statistics['records']:
            self.set_status('没有可导出的管道支吊架。', True)
            return
        path = psb.export_combined_bom(DEFAULT_JSON)
        if path:
            self.set_status('JSON 清单已导出：%s' % path)

    # -- 窗口 --------------------------------------------------------------

    def close_report(self):
        self._running = False
        self._allow_close = True
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
        self.close_report()

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


def show_support_report():
    dialog = _SupportReportDialog()
    dialog.run_dialog_loop()
    return dialog


def PyMain():
    try:
        show_support_report()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('report tool start failed')
        print('管道支吊架统计启动失败：%s\n%s' % (error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE, '启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
