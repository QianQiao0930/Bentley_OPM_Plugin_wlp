# -*- coding: utf-8 -*-
"""G2 混凝土锚板 + 膨胀锚栓放置工具。

在三维 DGN 模型中点取**混凝土表面**上锚板背面的中心点，生成一块正方形锚板与
四根膨胀锚栓（表 1 子项 A~D）：

    * 锚板：正方形 (S+100)×(S+100)、厚 T，四角四个 φG 螺栓孔（间距 S）。
    * 锚栓：埋入端膨胀套管 + 螺杆 + 垫圈 + 六角螺母，全部由最简单的拉伸 / 圆柱
      构成，不做布尔融合（允许实体重合），只保证外形可辨认。
    * 锚栓朝向沿所选点的混凝土外法向，可用「朝向」绕 Z 旋转。

建模逻辑全部在 ``混凝土锚板.py`` 中，不含任何界面依赖，其它插件可直接
``import 混凝土锚板`` 调用：

    import 混凝土锚板 as anchor
    cell, result = anchor.draw_anchor_plate(placement_point, options)

本文件只负责 PyQt5 面板与交互工具，面板沿用 端焊三角架_基础.py 的自绘风格。
"""

from __future__ import division

import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEvent, QEventLoop, QPoint, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPalette, QPen, QRegion)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QRadioButton, QSizePolicy, QVBoxLayout, QWidget)

HERE = os.path.dirname(os.path.abspath(__file__))
# 建模库 混凝土锚板.py 已移至 模块/公共/。
_COMMON_DIR = os.path.join(HERE, '模块', '公共')
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

import 混凝土锚板 as geometry


DEBUG_LOG = os.path.join(
    HERE, '模块', '日志', 'G2-混凝土锚板_debug_log.txt')

# UI_TITLE / UI_REVISION / UI_RADIUS 由下方 UI 套件定义。

DEFAULT_SUBTYPE = 'A'
DEFAULT_HEADING = 0.0

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


def _subtype_label(subtype):
    table = geometry.ANCHOR_TABLE[subtype]
    return ('%s  |  M%.0f×%.0f  |  板厚 %.0f  |  孔 φ%.0f'
            % (subtype, table['bolt_dia'], table['length'],
               table['plate_t'], table['hole_dia']))


# ---------------------------------------------------------------------------
# 面板外观：浅色柔面（PyQt5 自绘圆角 / 柔影，不依赖任何图片资源）
# ---------------------------------------------------------------------------

UI_BG = QColor(238, 241, 246)         # 面板底色
UI_CARD = QColor(255, 255, 255)       # 卡片底
UI_WELL = QColor(231, 235, 242)       # 凹槽 / 输入框底
UI_TEXT = QColor(57, 67, 90)
UI_MUTED = QColor(125, 138, 160)
UI_RING = QColor(186, 196, 212)       # 未选中指示器描边
UI_SHADOW = QColor(163, 177, 198)
UI_ACCENT = QColor(74, 102, 224)      # 主按钮 / 选中态
UI_ACCENT_TOP = QColor(116, 148, 248)
UI_ACCENT_BOTTOM = QColor(70, 98, 224)
UI_ACCENT_SHADOW = QColor(76, 106, 208)
UI_INFO = QColor(47, 111, 181)        # 状态文字（正常）
UI_ERROR = QColor(180, 35, 24)        # 状态文字（出错）
UI_FONT = "Microsoft YaHei UI"
UI_TITLE = "G2-混凝土锚板（锚板 + 膨胀锚栓）"
UI_RADIUS = 12
# 面板版本标记：写进调试日志，便于确认实际加载的是哪一版脚本。
UI_REVISION = 'anchor-plate-1'

# QApplication 必须由 Python 侧一直持有引用：一旦没有引用，Qt 会把它连同
# 底层对象一起回收，后续建控件就会直接闪退（且没有任何 Python 报错）。
_QT_APP = [None]


def ensure_qt_app():
    """确保存在 QApplication，并把引用留在模块级。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    _QT_APP[0] = app
    return app


def rounded_rect(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    return path


def layer_alpha(color, steps):
    """单层透明度：让 steps 层叠加后正好达到 color 的 alpha。"""
    peak = max(0.0, min(1.0, color.alpha()/255.0))
    if peak <= 0.0:
        return 0
    return max(1, int(round((1.0-(1.0-peak)**(1.0/steps))*255)))


def paint_soft_shadow(painter, rect, radius, color, dx, dy, spread, steps=24):
    """逐层填充叠加出真渐变的外阴影；描边法会在末端留下可见的一圈硬边。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        grow = spread*(1.0-step/float(steps))
        frame = QRectF(rect).translated(dx, dy)
        frame.adjust(-grow, -grow, grow, grow)
        painter.drawRoundedRect(frame, radius+grow, radius+grow)


def paint_inner_shadow(painter, rect, radius, color, dx, dy, depth, steps=24):
    """凹槽内影：把同一形状朝 (dx,dy) 平移后叠填，越靠边越深。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        shift = 1.0-step/float(steps)
        painter.drawRoundedRect(QRectF(rect).translated(dx*shift, dy*shift),
                                radius, radius)


def paint_raised(painter, rect, radius, surface, spread=12.0, dark=118,
                 light=205, gradient=None, shadow=UI_SHADOW):
    """gradient 传 (顶色, 底色) 时改用纵向渐变填充，否则用纯色 surface。"""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    paint_soft_shadow(painter, rect, radius, QColor(255, 255, 255, light),
                      -2.5, -2.5, spread)
    paint_soft_shadow(painter, rect, radius,
                      QColor(shadow.red(), shadow.green(), shadow.blue(), dark),
                      3.0, 4.0, spread)
    painter.setPen(Qt.NoPen)
    if gradient is None:
        painter.setBrush(surface)
    else:
        ramp = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        ramp.setColorAt(0.0, gradient[0])
        ramp.setColorAt(1.0, gradient[1])
        painter.setBrush(ramp)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.restore()


def paint_inset(painter, rect, radius, surface=UI_WELL, depth=10.0, steps=24):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(surface)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.setClipPath(rounded_rect(rect, radius))
    paint_inner_shadow(painter, rect, radius,
                       QColor(UI_SHADOW.red(), UI_SHADOW.green(),
                              UI_SHADOW.blue(), 150),
                       depth, depth, depth, steps)
    paint_inner_shadow(painter, rect, radius, QColor(255, 255, 255, 230),
                       -depth, -depth, depth, steps)
    painter.restore()


class NeuButton(QPushButton):
    """新拟态按钮：静止凸起，按下转为凹槽；accent 为主操作。"""

    def __init__(self, text, parent=None, accent=False, radius=None,
                 margin_x=15, margin_y=13):
        super().__init__(text, parent)
        self.accent = accent
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumHeight(44+2*margin_y)
        self.setStyleSheet('QPushButton {border: none; background: transparent;'
                           ' font-size: 14px;}')

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin_x, self.margin_y,
                                            -self.margin_x, -self.margin_y)
        radius = self.radius if self.radius else rect.height()/2.0
        hovered = self.underMouse() and self.isEnabled()
        if self.accent:
            if self.isDown():
                top, bottom, spread = (UI_ACCENT_BOTTOM,
                                       UI_ACCENT_BOTTOM.darker(107), 7.0)
            elif hovered:
                top = UI_ACCENT_TOP.lighter(105)
                bottom = UI_ACCENT_BOTTOM.lighter(105)
                spread = 10.0
            else:
                top, bottom, spread = UI_ACCENT_TOP, UI_ACCENT_BOTTOM, 9.0
            paint_raised(painter, rect, radius, UI_CARD, spread=spread, dark=100,
                         light=95, gradient=(top, bottom),
                         shadow=UI_ACCENT_SHADOW)
            painter.setPen(QColor(255, 255, 255))
        elif self.isDown():
            paint_inset(painter, rect, radius, UI_WELL, depth=7.0)
            painter.setPen(UI_TEXT)
        else:
            surface = QColor(247, 249, 253) if hovered else UI_CARD
            paint_raised(painter, rect, radius, surface, spread=9.0, dark=100,
                         gradient=(surface, surface.darker(103)))
            painter.setPen(UI_TEXT)
        font = self.font()
        font.setBold(self.accent)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text())


class NeuIconButton(QWidget):
    """标题栏小图标钮：悬停浮出圆形底，关闭钮悬停为红色。"""

    def __init__(self, parent, kind, callback, danger=False):
        super().__init__(parent)
        self.kind = kind
        self.danger = danger
        self._callback = callback
        self._pressed = False
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        released = self._pressed and self.rect().contains(event.pos())
        self._pressed = False
        self.update()
        if event.button() == Qt.LeftButton and released:
            self._callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        active = self.underMouse() or self._pressed
        if active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ERROR if self.danger else QColor(255, 255, 255, 235))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1.0, 1.0,
                                                             -1.0, -1.0))
        if self.danger:
            color = QColor(255, 255, 255) if active else QColor(122, 134, 154)
        else:
            color = UI_MUTED
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        center = self.rect().center()
        cx, cy = center.x(), center.y()
        if self.kind == 'close':
            painter.drawLine(cx-4, cy-4, cx+4, cy+4)
            painter.drawLine(cx-4, cy+4, cx+4, cy-4)
        else:
            painter.drawLine(cx-5, cy, cx+5, cy)


class NeuTitleBar(QWidget):
    """无边框窗口的自绘标题栏，空白处按住可拖动整个窗口。"""

    def __init__(self, title, on_minimize, on_close, parent=None):
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
        row.addWidget(NeuIconButton(self, 'minimize', on_minimize))
        row.addWidget(NeuIconButton(self, 'close', on_close, danger=True))

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


class NeuCard(QWidget):
    """白色圆角卡片：柔和外影 + 分组标题，content 为内部栅格。"""

    def __init__(self, title, parent=None, radius=15, margin_x=15, margin_y=5,
                 padding=8):
        super().__init__(parent)
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        outer = QVBoxLayout(self)
        outer.setContentsMargins(margin_x+padding, margin_y+padding,
                                 margin_x+padding, margin_y+padding)
        outer.setSpacing(5)
        caption = QLabel(title, self)
        caption.setStyleSheet('color: #7D8AA0; font-size: 12px;'
                              ' font-weight: 600;')
        outer.addWidget(caption)
        self.content = QGridLayout()
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setHorizontalSpacing(10)
        self.content.setVerticalSpacing(6)
        outer.addLayout(self.content)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin_x, self.margin_y,
                                            -self.margin_x, -self.margin_y)
        paint_raised(painter, rect, self.radius, UI_CARD, spread=7.0,
                     dark=92, light=225)


class NeuPanel(QWidget):
    """凹槽信息面板（规格 / 预览 / 状态）。"""

    def __init__(self, parent=None, radius=14, margin=3, padding=9):
        super().__init__(parent)
        self.radius = radius
        self.margin = margin
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(margin+padding, margin+padding,
                                        margin+padding, margin+padding)
        self.content.setSpacing(3)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin, self.margin,
                                            -self.margin, -self.margin)
        paint_inset(painter, rect, self.radius, UI_WELL, depth=8.0)


class NeuEdit(QWidget):
    """凹槽输入框：内嵌无边框 QLineEdit，凹槽与留白由自绘完成。"""

    def __init__(self, text='', parent=None, width=84, radius=13, margin=2):
        super().__init__(parent)
        self.radius = radius
        self.margin = margin
        self.edit = QLineEdit(text, self)
        self.edit.setFrame(False)
        self.edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.edit.setFixedWidth(width)
        self.edit.setStyleSheet(
            'QLineEdit {border: none; background: transparent;'
            ' color: #39435A; font-size: 15px; font-weight: 600;'
            ' selection-background-color: #4A66E0; selection-color: #FFFFFF;}')
        row = QHBoxLayout(self)
        row.setContentsMargins(margin+11, margin+4, margin+11, margin+4)
        row.addWidget(self.edit)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def value(self):
        return self.edit.text()

    def set_value(self, text):
        self.edit.setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin, self.margin,
                                            -self.margin, -self.margin)
        paint_inset(painter, rect, self.radius, UI_WELL, depth=8.0)


class NeuChoice(QRadioButton):
    """自绘单选项：圆环指示器 + 文字，选中为实心主色。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.text())+30, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height()-size)/2.0
        circle = QRectF(4.0, top, size, size)
        if checked:
            painter.setPen(QPen(UI_ACCENT if enabled else UI_MUTED, 2.0))
            painter.setBrush(QColor(255, 255, 255))
        else:
            pen = QPen(UI_ACCENT if (enabled and self.underMouse()) else UI_RING,
                       2.0)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255) if enabled else UI_WELL)
        painter.drawEllipse(circle)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT if enabled else UI_MUTED)
            painter.drawEllipse(circle.adjusted(4.6, 4.6, -4.6, -4.6))
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(4.0+size+8.0, 0.0, self.width()-(12.0+size),
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())


class NeuToggle(QCheckBox):
    """自绘复选项：圆角方格指示器，选中时画白色对勾。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.text())+32, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height()-size)/2.0
        box = QRectF(4.0, top, size, size)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT if enabled else UI_MUTED)
            painter.drawRoundedRect(box, 5.0, 5.0)
            pen = QPen(QColor(255, 255, 255), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            mark = QPainterPath()
            mark.moveTo(box.left()+4.0, box.center().y())
            mark.lineTo(box.center().x()-0.6, box.bottom()-4.2)
            mark.lineTo(box.right()-3.4, box.top()+4.0)
            painter.drawPath(mark)
        else:
            pen = QPen(UI_ACCENT if (enabled and self.underMouse()) else UI_RING,
                       2.0)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255) if enabled else UI_WELL)
            painter.drawRoundedRect(box, 5.0, 5.0)
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(4.0+size+9.0, 0.0, self.width()-(13.0+size),
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())


class _ComboItem(QWidget):
    """下拉列表中的一行：悬停高亮，当前项带主色圆点并加粗。"""

    def __init__(self, label, value, on_pick, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = value
        self._on_pick = on_pick
        self._selected = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(30)
        metrics = self.fontMetrics()
        self.setMinimumWidth(metrics.horizontalAdvance(label)+48)

    def set_selected(self, selected):
        if self._selected != selected:
            self._selected = selected
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self._on_pick(self.value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(UI_ACCENT.red(), UI_ACCENT.green(),
                                   UI_ACCENT.blue(), 28))
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(2.0, 1.0, -2.0, -1.0), 7.0, 7.0)
        if self._selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT)
            painter.drawEllipse(QRectF(9.0, self.height()/2.0-3.5, 7.0, 7.0))
        font = self.font()
        font.setBold(self._selected)
        painter.setFont(font)
        painter.setPen(UI_TEXT)
        painter.drawText(QRectF(26.0, 0.0, self.width()-32.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label)


class _NeuComboPopup(QWidget):
    """下拉列表弹层：圆角白卡 + 柔影，点击外部自动收起。"""

    MARGIN = 12

    def __init__(self, combo, entries, on_pick):
        super().__init__(combo, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.items = []
        column = QVBoxLayout(self)
        column.setContentsMargins(self.MARGIN, self.MARGIN,
                                  self.MARGIN, self.MARGIN)
        column.setSpacing(1)
        for value, label in entries:
            item = _ComboItem(label, value, on_pick, self)
            self.items.append(item)
            column.addWidget(item)

    def sync(self, current, minimum_width):
        for item in self.items:
            item.set_selected(item.value == current)
        self.setFixedWidth(max(minimum_width, self.sizeHint().width()))
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        edge = self.MARGIN-4.0
        rect = QRectF(self.rect()).adjusted(edge, edge, -edge, -edge)
        paint_raised(painter, rect, 12, UI_CARD, spread=6.0, dark=92, light=225)


class NeuCombo(QWidget):
    """凹槽下拉选择框：闭合时显示当前项，点开后弹出 NeuComboPopup。"""

    def __init__(self, entries, current=None, parent=None, on_change=None,
                 width=None):
        super().__init__(parent)
        self.entries = [(value, label) for value, label in entries]
        self._value = (current if current is not None
                       else (self.entries[0][0] if self.entries else None))
        self._on_change = on_change
        self._popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(40)
        if width is None:
            metrics = self.fontMetrics()
            width = max([metrics.horizontalAdvance(label)
                         for _, label in self.entries] or [0]) + 76
        self.setFixedWidth(width)

    def value(self):
        return self._value

    def label(self):
        for value, label in self.entries:
            if value == self._value:
                return label
        return ''

    def set_value(self, value):
        if value == self._value:
            return
        self._value = value
        self.update()
        if self._on_change is not None:
            self._on_change()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.open_popup()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def popup_visible(self):
        return self._popup is not None and self._popup.isVisible()

    def open_popup(self):
        # 弹层只建一次，之后复用；hide() 收起但保留，避免每次选择漏一个窗口。
        if self._popup is None:
            self._popup = _NeuComboPopup(self, self.entries, self._pick)
        # 弹层左/上各留 MARGIN 的柔影边距，使白卡与下拉框左沿对齐。
        self._popup.sync(self._value, self.width()+2*_NeuComboPopup.MARGIN)
        self._popup.move(self.mapToGlobal(
            QPoint(-_NeuComboPopup.MARGIN, self.height()-8)))
        self._popup.show()
        self._popup.raise_()

    def _pick(self, value):
        if self._popup is not None:
            self._popup.hide()
        self.set_value(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        rect = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
        paint_inset(painter, rect, 13, UI_WELL, depth=8.0)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(15.0, 0.0, self.width()-46.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label())
        # 右侧下拉箭头：悬停或展开时变主色。
        active = enabled and (self.underMouse() or self.popup_visible())
        pen = QPen(UI_ACCENT if active else UI_MUTED, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = self.width()-19.0
        cy = self.height()/2.0 - 1.0
        chevron = QPainterPath()
        chevron.moveTo(cx-5.0, cy-2.5)
        chevron.lineTo(cx, cy+2.5)
        chevron.lineTo(cx+5.0, cy-2.5)
        painter.drawPath(chevron)


class _AnchorPlateSettingsDialog(QWidget):
    """子项 / 间距 / 朝向选择，预览 / 确定 / 取消面板。"""

    RADIUS = UI_RADIUS

    def __init__(self):
        self._app = ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self.placement_point = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self.subtype_combo = None
        self.option_widgets = []
        self._running = True
        self._allow_close = False
        self._finish_requested = False
        self._event_loop = QEventLoop()

        # 防抖定时器：选择框用短间隔求跟手，文本框用长间隔避免半途重建。
        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(REGENERATE_DELAY_MS)
        self._regen_timer.timeout.connect(self._run_pending_regeneration)
        self._text_timer = QTimer(self)
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(TEXT_REGENERATE_DELAY_MS)
        self._text_timer.timeout.connect(self._run_pending_regeneration)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(NeuTitleBar(UI_TITLE, self._minimize, self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点取混凝土表面上锚板背面的中心点；锚栓沿该点的"
                      "混凝土外法向（+X）伸入，斜撑侧为空气侧。点取后可改子项 / "
                      "间距 S / 朝向，预览会自动重建；点【确定】保留，"
                      "点【取消】或右键放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = NeuCard("锚栓规格")
        self.subtype_combo = self._register(NeuCombo(
            [(key, _subtype_label(key))
             for key in sorted(geometry.ANCHOR_TABLE)],
            current=DEFAULT_SUBTYPE, on_change=self.on_subtype_changed))
        self._row(card.content, 0, "子项：", [self.subtype_combo], 16)
        self.plate_label = self._value()
        self._row(card.content, 1, "锚板：", [self.plate_label])
        self.bolt_label = self._value()
        self._row(card.content, 2, "锚栓：", [self.bolt_label])
        body.addWidget(card)

        card = NeuCard("布置参数")
        self.spacing_edit = self._edit_row(
            card.content, 0, "间距 S：", '75',
            "mm　孔中心距，不得小于该子项 MIN.S")
        self.heading_edit = self._edit_row(
            card.content, 1, "朝向：", '%.0f' % DEFAULT_HEADING,
            "°　0° 时锚栓轴线沿模型 +X，逆时针为正")
        body.addWidget(card)

        summary = NeuPanel()
        self.spec_label = self._info("", UI_TEXT)
        summary.content.addWidget(self.spec_label)
        self.preview_info_label = self._info("预览：—", UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点取混凝土表面上锚板背面的中心点；改参数会自动重建预览。",
            UI_INFO)
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.cancel_button = NeuButton("取消")
        self.cancel_button.setFixedWidth(126)
        self.cancel_button.clicked.connect(self.cancel_tool)
        self.confirm_button = NeuButton("确定", accent=True)
        self.confirm_button.setFixedWidth(126)
        self.confirm_button.clicked.connect(self.confirm_tool)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.confirm_button)
        body.addLayout(button_row)
        self.action_widgets = [self.confirm_button, self.cancel_button]

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
        field = NeuEdit(value, width=96)
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

    def current_subtype(self):
        if self.subtype_combo is None:
            return DEFAULT_SUBTYPE
        return self.subtype_combo.value() or DEFAULT_SUBTYPE

    def current_options(self):
        subtype = self.current_subtype()
        if subtype not in geometry.ANCHOR_TABLE:
            raise ValueError('未知子项：%s。' % subtype)
        try:
            spacing = float(self.spacing_edit.value())
        except (TypeError, ValueError):
            raise ValueError('间距 S 必须是数字（mm）。')
        try:
            heading = float(self.heading_edit.value())
        except (TypeError, ValueError):
            raise ValueError('朝向必须是数字（度）。')
        return {'subtype': subtype, 'spacing': spacing,
                'heading_deg': heading}

    def set_status(self, message, is_error=False):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (UI_ERROR if is_error else UI_INFO).name())
        self.status_label.setText(message)
        QApplication.processEvents()

    def set_result(self, result):
        self.preview_info_label.setText(
            "预览：%s 子项，锚板 %.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f），"
            "M%.0f×%.0f 锚栓 ×%d，有效埋深 %.0f mm，单元含 %d 个子元素。" % (
                result['subtype'], result['plate_side'], result['plate_side'],
                result['plate_t'], result['hole_dia'], result['spacing'],
                result['bolt_dia'], result['bolt_length'], result['bolt_count'],
                result['embedment_actual'], result['child_count'],
            )
        )

    def refresh_spec(self):
        subtype = self.current_subtype()
        table = geometry.ANCHOR_TABLE.get(subtype)
        if table is None:
            self.spec_label.setText('子项有误。')
            return
        self.plate_label.setText('%.0f×%.0f×%.0f（板厚 T=%.0f）' % (
            table['min_spacing'] + 2.0 * geometry.PLATE_MARGIN,
            table['min_spacing'] + 2.0 * geometry.PLATE_MARGIN,
            table['plate_t'], table['plate_t']))
        self.bolt_label.setText('M%.0f×%.0f 膨胀锚栓，孔径 φ%.0f' % (
            table['bolt_dia'], table['length'], table['hole_dia']))
        try:
            self.spec_label.setText(
                geometry.describe_spec(self.current_options()))
        except (ValueError, RuntimeError) as error:
            self.spec_label.setText('参数有误：%s' % error)

    def _set_busy(self, busy):
        for widget in self.option_widgets + self.action_widgets:
            widget.setEnabled(not busy)
        QApplication.processEvents()

    def on_subtype_changed(self, *_unused):
        """切换子项时把间距 S 重置为该子项 MIN.S，保证默认参数合法。"""
        table = geometry.ANCHOR_TABLE.get(self.current_subtype())
        if table is not None:
            self.spacing_edit.set_value('%.0f' % table['min_spacing'])
        self.on_options_changed()

    def on_options_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._regen_timer)

    def on_text_changed(self, *_unused):
        self.refresh_spec()
        self._schedule_regeneration(self._text_timer)

    def _schedule_regeneration(self, timer):
        self._cancel_pending_regeneration()
        if self.placement_point is None:
            return
        timer.start()

    def _cancel_pending_regeneration(self):
        self._regen_timer.stop()
        self._text_timer.stop()

    def _run_pending_regeneration(self):
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
            geometry.resolve_options(options)
        except (ValueError, RuntimeError) as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成锚板预览，请稍候……')
        try:
            handle, result, deleted = geometry.replace_anchor_plate(
                self.placement_point, options, self.preview_handle)
        except Exception as error:
            message = '锚板生成失败：%s' % error
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
        message = (
            "预览已更新：%s 子项，锚板 %.0f×%.0f×%.0f，M%.0f×%.0f 锚栓 ×4，"
            "单元含 %d 个子元素。%s改参数会自动重建；点【确定】保留，"
            "点【取消】放弃。"
            % (result['subtype'], result['plate_side'], result['plate_side'],
               result['plate_t'], result['bolt_dia'], result['bolt_length'],
               result['child_count'], '已替换上一版预览。' if deleted else '')
        )
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return geometry._delete_element(handle)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
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
        painter.setBrush(UI_BG)
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


# ---------------------------------------------------------------------------
# 交互工具
# ---------------------------------------------------------------------------


class AnchorPlatePlacementTool(DgnPrimitiveTool):
    """点取混凝土表面上的锚板中心并放置锚板的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('ConcreteAnchorPlatePlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            '请点取混凝土表面上锚板背面的中心点；点取后可改子项 / 间距 S / '
            '朝向，预览会自动重建，点【确定】保留，点【取消】或右键放弃。')

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            QTimer.singleShot(0, settings.cancel_tool)
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
            active = getattr(AnchorPlatePlacementTool, '_active_settings', None)
            if active is not None:
                try:
                    if active._running:
                        active.raise_()
                        active.activateWindow()
                        return None
                except RuntimeError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _AnchorPlateSettingsDialog())
        if owner:
            AnchorPlatePlacementTool._active_settings = settings
        tool = AnchorPlatePlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_dialog_loop()
        finally:
            if owner:
                AnchorPlatePlacementTool._active_settings = None
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    try:
        AnchorPlatePlacementTool.InstallNewInstance(0)
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('G2-混凝土锚板工具启动失败：%s\n%s' % (error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE, '工具启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


show_anchor_plate_dialog = PyMain


if __name__ == '__main__':
    PyMain()
