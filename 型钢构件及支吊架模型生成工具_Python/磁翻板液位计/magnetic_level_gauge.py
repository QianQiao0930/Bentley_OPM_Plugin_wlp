# -*- coding: utf-8 -*-
"""OPM 磁翻板液位计外观模型。运行本文件，输入 L1，再点取下接口筒体中心。

尺寸单位 mm；局部 Z 向上、接管朝 -X、显示面朝 -Y。
普通 DGN 单元，不注册为 OpenPlant 智能仪表。其余尺寸为展示用近似值。
"""
import math
import os
import sys

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *
from PyQt5.QtCore import QEventLoop, QRectF, QSettings, Qt, QTimer
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPalette, QPen, QRegion)
from PyQt5.QtWidgets import (QAbstractSpinBox, QApplication, QDoubleSpinBox,
                             QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)
import win32gui
import win32process
import win32api

STEEL = (174, 185, 194)
DARK = (48, 57, 65)
RED = (215, 38, 40)
WHITE = (245, 245, 239)
ACTIVE_TOOL = None

# 新拟态界面配色（浅灰白底 + 白色高光 + 冷灰阴影）。
SURFACE = QColor(238, 241, 246)
SURFACE_HOVER = QColor(244, 247, 252)
SURFACE_PRESSED = QColor(229, 233, 241)
WELL = QColor(231, 235, 242)
SHADOW_DARK = QColor(163, 177, 198)
INK = QColor(58, 68, 86)
INK_SOFT = QColor(140, 152, 172)
ACCENT = QColor(79, 110, 230)
# 主按钮的渐变色面：上浅下深，配一枚同色系柔影。
ACCENT_TOP = QColor(116, 148, 248)
ACCENT_BOTTOM = QColor(70, 98, 224)
ACCENT_SHADOW = QColor(76, 106, 208)


def host_window():
    """在创建 Qt 窗口前找出当前 OPM 进程的主窗口。"""
    candidates = []
    def collect(hwnd, _):
        if (win32gui.IsWindowVisible(hwnd)
                and win32process.GetWindowThreadProcessId(hwnd)[1] == os.getpid()
                and not win32gui.GetWindow(hwnd, 4)):
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            candidates.append(((right-left)*(bottom-top), hwnd))
    win32gui.EnumWindows(collect, None)
    return max(candidates)[1] if candidates else None


def clamp_position(x, y, width, height, bounds):
    left, top, right, bottom = bounds
    return (max(left, min(x, right-width)),
            max(top, min(y, bottom-height)))


def check(status, operation):
    if status != BentleyStatus.eSUCCESS:
        raise RuntimeError(operation + "失败：" + str(status))


def layout(l1):
    """纯几何描述，方便在没有 OPM 的环境检查尺寸。"""
    l1 = float(l1)
    if not math.isfinite(l1) or not 350 <= l1 <= 6000:
        raise ValueError("L1 必须在 350～6000 mm 之间。")
    parts = []

    def cyl(a, b, r, color=STEEL):
        parts.append(('cylinder', a, b, r, color))

    def box(a, size, color=STEEL):
        parts.append(('box', a, size, color))

    def wheel(x, z, radius):
        # 真正的环形手轮，保留中间镂空和两根轮辐。
        parts.append(('torus', (x, 0, z), radius, 3.5, DARK))
        cyl((x-radius, 0, z), (x+radius, 0, z), 2.5, DARK)
        cyl((x, -radius, z), (x, radius, z), 2.5, DARK)

    cyl((0, 0, -85), (0, 0, l1+85), 30)
    for z in (-105, l1+85):
        cyl((0, 0, z), (0, 0, z+10), 55)
        cyl((0, 0, z+10), (0, 0, z+12), 50, DARK)
        cyl((0, 0, z+12), (0, 0, z+20), 55)
        for i in range(6):
            angle = 2*math.pi*i/6
            x, y = 44*math.cos(angle), 44*math.sin(angle)
            cyl((x, y, z-4), (x, y, z+25), 4, DARK)
            cyl((x, y, z+20), (x, y, z+26), 6)

    for z in (0, l1):
        cyl((-260, 0, z), (-22, 0, z), 13.5)
        # 截止阀位于两组配对法兰之间。
        for x in (-224, -108):
            cyl((x, 0, z), (x+10, 0, z), 46)
            cyl((x+10, 0, z), (x+12, 0, z), 43, DARK)
            cyl((x+12, 0, z), (x+22, 0, z), 46)
            for i in range(4):
                a = math.pi/4+i*math.pi/2
                y, dz = 35*math.cos(a), 35*math.sin(a)
                cyl((x-4, y, z+dz), (x+26, y, z+dz), 4, DARK)
                cyl((x+22, y, z+dz), (x+28, y, z+dz), 6)
        cyl((-202, 0, z), (-108, 0, z), 24)
        cyl((-155, 0, z), (-155, 0, z+37), 18)
        cyl((-155, 0, z+37), (-155, 0, z+45), 23)
        cyl((-155, 0, z+45), (-155, 0, z+77), 5, DARK)
        wheel(-155, z+80, 30)

    # 显示框安在筒体前方，并通过两个支架固定。
    for z in (30, l1-30):
        cyl((0, 0, z-5), (0, 0, z+5), 32, DARK)
        box((-22, -39, z-5), (44, 18, 10))
    box((-25, -44, -12), (65, 8, l1+24), DARK)
    box((-25, -49, -12), (4, 5, l1+24))
    box((21, -49, -12), (4, 5, l1+24))
    box((-21, -49, -12), (42, 5, 12))
    box((-21, -49, l1), (42, 5, 12))
    # 偶数片确保红白交界恰好位于量程的 50%，仅为静态示意。
    count = 2*max(10, int(math.ceil(l1/24)))
    pitch = l1/count
    for i in range(count):
        box((-20, -49, i*pitch+0.4), (40, 5, pitch-0.8),
            RED if i < count//2 else WHITE)
    box((26, -45, 0), (13, 1, l1), WHITE)
    for i in range(int(l1//10)+1):
        width = 11 if i % 5 == 0 else 6
        box((27, -46, min(i*10, l1-0.8)), (width, 1, 0.8), DARK)

    cyl((0, 0, -128), (0, 0, -105), 9)
    box((-13, -13, -155), (26, 26, 27))
    cyl((0, 0, -180), (0, 0, -155), 7)
    cyl((13, 0, -142), (38, 0, -142), 4, DARK)
    cyl((38, -18, -142), (38, 18, -142), 3, DARK)
    return parts


def create_gauge(origin, l1, rotation_degrees=0):
    parts = layout(l1)
    if not math.isfinite(rotation_degrees):
        raise ValueError("旋转角必须为有限数值。")
    ref = ISessionMgr.ActiveDgnModelRef
    if ref is None or not ref.Is3d():
        raise RuntimeError("请先打开可编辑的三维 DGN 模型。")
    model = ref.GetDgnModel()
    scale = model.GetModelInfo().GetUorPerMeter()/1000.0
    a = math.radians(rotation_degrees)
    c, s = math.cos(a), math.sin(a)

    def point(v):
        x, y, z = v
        return DPoint3d(origin.x+(c*x-s*y)*scale,
                        origin.y+(s*x+c*y)*scale, origin.z+z*scale)

    colors = {}
    for rgb in (STEEL, DARK, RED, WHITE):
        colors[rgb] = DgnColorMap.CreateElementColor(
            IntColorDef(*rgb), None, None, ISessionMgr.GetActiveDgnFile())
    cell = EditElementHandle()
    # 此 MSPy 接口返回 None（void），不能作为 BentleyStatus 检查。
    # 检查输出句柄；后续加入构件、完成单元和写入仍严格检查状态码。
    NormalCellHeaderHandler.CreateOrphanCellElement(
        cell, 'MAGNETIC_LEVEL_GAUGE_L1_%g' % l1, True, model)
    if not cell.IsValid():
        raise RuntimeError('创建单元失败：未生成有效的单元句柄。')
    for part in parts:
        kind = part[0]
        element = EditElementHandle()
        if kind == 'cylinder':
            _, start, end, radius, rgb = part
            primitive = ISolidPrimitive.CreateDgnCone(DgnConeDetail(
                point(start), point(end), radius*scale, radius*scale, True))
            check(DraftingElementSchema.ToElement(element, primitive, None, model), '创建圆柱')
        elif kind == 'torus':
            _, center, major, minor, rgb = part
            primitive = ISolidPrimitive.CreateDgnTorusPipe(DgnTorusPipeDetail(
                point(center), DVec3d(c, s, 0), DVec3d(-s, c, 0),
                major*scale, minor*scale, 2*math.pi, True))
            check(DraftingElementSchema.ToElement(element, primitive, None, model), '创建手轮')
        else:
            _, start, size, rgb = part
            x, y, z = start
            dx, dy, dz = size
            vertices = DPoint3dArray()
            for v in ((x,y,z), (x+dx,y,z), (x+dx,y+dy,z),
                      (x,y+dy,z), (x,y,z)):
                vertices.append(point(v))
            profile = EditElementHandle()
            check(ShapeHandler.CreateShapeElement(profile, None, vertices, True, ref), '创建矩形')
            status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
            check(status, '转换矩形')
            check(SolidUtil.Modify.SweepBody(body, DVec3d(0, 0, dz*scale)), '拉伸矩形')
            check(SolidUtil.Convert.BodyToElement(element, body, profile, model), '生成板件')
        properties = ElementPropertiesSetter()
        properties.SetColor(colors[rgb])
        properties.Apply(element)
        check(NormalCellHeaderHandler.AddChildElement(cell, element), '加入构件')
    check(NormalCellHeaderHandler.AddChildComplete(cell), '完成单元')
    # 所有几何成功后才一次性写入，避免失败时留下零散构件。
    check(cell.AddToModel(), '写入模型')
    return cell


class GaugePlacementTool(DgnPrimitiveTool):
    def __init__(self, l1, angle):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.l1, self.angle = l1, angle
        self.m_self = self
        self.stopping = False
        self.cleaned = False

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt('点取下接口对应的筒体中心；Z 向上。右键结束。')

    def _OnDataButton(self, event):
        try:
            create_gauge(event.GetPoint(), self.l1, self.angle)
            NotificationManager.OutputPrompt('已创建 L1=%g mm 液位计；可继续点取，右键结束。' % self.l1)
        except Exception as error:
            QMessageBox.critical(None, '液位计创建失败', str(error))
        return True

    def _OnResetButton(self, event):
        self.stop()
        return True

    def _OnRestartTool(self):
        if not self.stopping and not self.cleaned:
            install_tool(self.l1, self.angle)

    def stop(self):
        if not self.cleaned and not self.stopping:
            self.stopping = True
            self._ExitTool()

    def _OnCleanup(self):
        global ACTIVE_TOOL
        self.cleaned = True
        self.stopping = True
        if ACTIVE_TOOL is self:
            ACTIVE_TOOL = None
        self.m_self = None


def install_tool(l1, angle):
    global ACTIVE_TOOL
    ACTIVE_TOOL = GaugePlacementTool(l1, angle)
    ACTIVE_TOOL.InstallTool()


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
                 light=205, gradient=None, shadow=SHADOW_DARK):
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
        # 极轻微的纵向渐变，让凸面更像柔和的实体而不是贴片。
        ramp = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        ramp.setColorAt(0.0, gradient[0])
        ramp.setColorAt(1.0, gradient[1])
        painter.setBrush(ramp)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.restore()


def paint_inset(painter, rect, radius, surface=WELL, depth=10.0, steps=24):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(surface)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.setClipPath(rounded_rect(rect, radius))
    paint_inner_shadow(painter, rect, radius,
                       QColor(SHADOW_DARK.red(), SHADOW_DARK.green(),
                              SHADOW_DARK.blue(), 150),
                       depth, depth, depth, steps)
    paint_inner_shadow(painter, rect, radius, QColor(255, 255, 255, 230),
                       -depth, -depth, depth, steps)
    painter.restore()


class NeuButton(QPushButton):
    """新拟态按钮：静止凸起，按下转为凹槽。留白需容下阴影，否则会被裁硬。"""

    def __init__(self, text, parent=None, accent=False, radius=None,
                 margin_x=18, margin_y=18):
        super().__init__(text, parent)
        self.accent = accent
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(46+2*margin_y)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet('QPushButton {border: none; background: transparent;'
                           ' font-size: 15px;}')

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
        hovered = self.underMouse()
        if self.accent:
            # 主按钮：上浅下深的蓝色渐变胶囊，悬停提亮、按下压深。
            if self.isDown():
                top, bottom, spread = ACCENT_BOTTOM, ACCENT_BOTTOM.darker(107), 8.0
            elif hovered:
                top = ACCENT_TOP.lighter(105)
                bottom = ACCENT_BOTTOM.lighter(105)
                spread = 13.0
            else:
                top, bottom, spread = ACCENT_TOP, ACCENT_BOTTOM, 12.0
            paint_raised(painter, rect, radius, SURFACE, spread=spread, dark=110,
                         light=95, gradient=(top, bottom), shadow=ACCENT_SHADOW)
            painter.setPen(QColor(255, 255, 255))
        elif self.isDown():
            paint_inset(painter, rect, radius, SURFACE_PRESSED, depth=7.0)
            painter.setPen(INK)
        else:
            surface = SURFACE_HOVER if hovered else SURFACE
            paint_raised(painter, rect, radius, surface,
                         gradient=(surface.lighter(102), surface.darker(103)))
            painter.setPen(INK)
        font = self.font()
        font.setBold(self.accent)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text())


class NeuField(QWidget):
    """独立成框的新拟态输入行：左侧名称，右侧数值与加减钮。"""

    def __init__(self, name, parent=None, radius=18, margin_x=18, margin_y=6,
                 padding_x=18, padding_y=8):
        super().__init__(parent)
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        row = QHBoxLayout(self)
        row.setContentsMargins(margin_x+padding_x, margin_y+padding_y,
                               margin_x+10, margin_y+padding_y)
        row.setSpacing(12)
        self.label = QLabel(name, self)
        self.label.setStyleSheet('font-size: 14px; color: #6B7A93;')
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(self.label)
        row.addStretch(1)
        self.spin = NeuSpin(self)
        row.addWidget(self.spin)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin_x, self.margin_y,
                                            -self.margin_x, -self.margin_y)
        paint_inset(painter, rect, self.radius, WELL, depth=9.0)


class NeuStep(QWidget):
    """数值框右端的圆形加减钮，按住可连续步进。"""

    def __init__(self, parent, plus, callback):
        super().__init__(parent)
        self.plus = plus
        self._callback = callback
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(380)
        self._delay.timeout.connect(self._begin_repeat)
        self._repeat = QTimer(self)
        self._repeat.setInterval(70)
        self._repeat.timeout.connect(self._callback)

    def _begin_repeat(self):
        self._callback()
        self._repeat.start()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._callback()
            self._delay.start()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._delay.stop()
        self._repeat.stop()
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        active = self.underMouse() or self._repeat.isActive()
        if active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawRoundedRect(QRectF(self.rect()), 10, 10)
        pen = QPen(ACCENT if active else INK_SOFT, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        center = self.rect().center()
        cx, cy = center.x(), center.y()
        painter.drawLine(cx-5, cy, cx+5, cy)
        if self.plus:
            painter.drawLine(cx, cy-5, cx, cy+5)


class NeuSpin(QDoubleSpinBox):
    """透明数值框，右侧自带新拟态加减按钮，API 与 QDoubleSpinBox 一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setMinimumHeight(46)
        self.setMinimumWidth(180)
        self.setStyleSheet('QDoubleSpinBox {border: none; background: transparent;}')
        editor = self.lineEdit()
        if editor is not None:
            editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            editor.setStyleSheet('background: transparent; border: none;'
                                 ' color: #3A4456; font-size: 17px;'
                                 ' font-weight: 600;')
            editor.setTextMargins(0, 0, 42, 0)
        self.up = NeuStep(self, True, self.stepUp)
        self.down = NeuStep(self, False, self.stepDown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width, gap, pad = 28, 5, 6
        each = (self.height()-2*pad-gap)//2
        self.up.setGeometry(self.width()-width-pad, pad, width, each)
        self.down.setGeometry(self.width()-width-pad, pad+each+gap, width, each)
        self.up.raise_()
        self.down.raise_()


class NeuIconButton(QWidget):
    """标题栏小图标钮：悬停时浮出圆形底，关闭钮悬停为红色。"""

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
            painter.setBrush(QColor(229, 72, 77) if self.danger
                             else QColor(255, 255, 255, 235))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1.0, 1.0,
                                                             -1.0, -1.0))
        if self.danger:
            color = QColor(255, 255, 255) if active else QColor(122, 134, 154)
        else:
            color = INK_SOFT
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
        dot.setStyleSheet('background: #4F6EE6; border-radius: 4px;')
        dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        caption = QLabel(title, self)
        caption.setStyleSheet('font-size: 14px; font-weight: 600;'
                              ' color: #3A4456;')
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


class GaugeDialog(QWidget):
    RADIUS = 12

    def __init__(self, owner_hwnd=None):
        super().__init__()
        self.running = True
        self.close_requested = False
        self.allow_close = False
        self.owner_hwnd = owner_hwnd
        self.settings = QSettings('BentleyOPMPlugins', 'MagneticLevelGauge')
        self.setWindowTitle('磁翻板液位计')
        # 无边框：标题栏与最小化/关闭钮全部自绘，才能与新拟态风格统一。
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, SURFACE)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(NeuTitleBar('磁翻板液位计', self._minimize,
                                    self.request_close))

        heading = QVBoxLayout()
        heading.setContentsMargins(18, 2, 18, 0)
        heading.setSpacing(4)
        heading.addWidget(self._label('侧—侧式磁翻板液位计',
                                      'font-size: 20px; font-weight: 700;'
                                      ' color: #3A4456;'))
        heading.addWidget(self._label('外观模型 · 尺寸示意',
                                      'font-size: 12px; color: #8C98AC;'))
        outer.addLayout(heading)
        outer.addSpacing(18)

        l1_field = NeuField('测量范围 L1')
        self.l1 = l1_field.spin
        self.l1.setRange(350, 6000)
        self.l1.setDecimals(1)
        self.l1.setSingleStep(50)
        self.l1.setValue(1400)
        self.l1.setSuffix(' mm')
        outer.addWidget(l1_field)

        angle_field = NeuField('绕 Z 轴旋转')
        self.angle = angle_field.spin
        self.angle.setRange(-180, 180)
        self.angle.setDecimals(1)
        self.angle.setSingleStep(90)
        self.angle.setSuffix(' °')
        outer.addWidget(angle_field)

        note = self._label('L1 可输入 350～6000 mm，放置点取下半部筒体轴心。\n'
                           '0° 时接管朝 −X、显示面朝 −Y；红白分界固定在 50% 量程。',
                           'font-size: 12px; color: #94A0B4;')
        note.setWordWrap(True)
        note_box = QVBoxLayout()
        note_box.setContentsMargins(18, 14, 18, 0)
        note_box.addWidget(note)
        outer.addLayout(note_box)

        row = QHBoxLayout()
        row.setContentsMargins(0, 16, 0, 18)
        row.setSpacing(0)
        start_button = NeuButton('开始放置', accent=True)
        start_button.clicked.connect(self.start)
        cancel_button = NeuButton('取消')
        cancel_button.clicked.connect(self.request_close)
        row.addWidget(start_button, 3)
        row.addWidget(cancel_button, 2)
        outer.addLayout(row)

        self.hwnd = int(self.winId())
        self.loop = QEventLoop()
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)
        self.setMinimumWidth(480)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))

    def _label(self, text, style):
        label = QLabel(text)
        label.setStyleSheet(style)
        return label

    def _minimize(self):
        self.showMinimized()

    def paintEvent(self, event):
        # 无边框窗口自己画底与描边，圆角由 setMask 裁出。
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(210, 218, 231), 1.0))
        painter.setBrush(SURFACE)
        painter.drawRoundedRect(frame, self.RADIUS, self.RADIUS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def restore_position(self):
        screens = QApplication.screens()
        screen = QApplication.primaryScreen()
        center = None
        if self.owner_hwnd and win32gui.IsWindow(self.owner_hwnd):
            # Win32 使用物理坐标；Qt 使用逻辑坐标，按所属屏幕换算。
            monitor = win32api.GetMonitorInfo(
                win32api.MonitorFromWindow(self.owner_hwnd, 2))
            screen = next((item for item in screens
                           if item.name() == monitor['Device']), screen)
            left, top, right, bottom = win32gui.GetWindowRect(self.owner_hwnd)
            ml, mt, mr, mb = monitor['Monitor']
            geo = screen.geometry()
            center = (geo.x()+((left+right)/2-ml)*geo.width()/(mr-ml),
                      geo.y()+((top+bottom)/2-mt)*geo.height()/(mb-mt))
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        try:
            x = int(self.settings.value('window/x'))
            y = int(self.settings.value('window/y'))
            target = next((item for item in screens
                           if item.availableGeometry().contains(x, y)), None)
            if target is not None:
                available = target.availableGeometry()
            else:
                raise ValueError('Saved screen is unavailable')
        except (TypeError, ValueError):
            cx, cy = center or (available.center().x(), available.center().y())
            x, y = int(cx-frame.width()/2), int(cy-frame.height()/2)
        x, y = clamp_position(x, y, frame.width(), frame.height(),
                              (available.x(), available.y(),
                               available.x()+available.width(),
                               available.y()+available.height()))
        self.move(x, y)

    def start(self):
        ref = ISessionMgr.ActiveDgnModelRef
        if ref is None or not ref.Is3d():
            QMessageBox.warning(self, '需要三维模型', '请打开三维 DGN 模型后再放置。')
            return
        install_tool(self.l1.value(), self.angle.value())

    def request_close(self):
        # 与标题栏 × 完全同路：只登记请求，交由主循环安全收尾。
        self.close_requested = True

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
            return
        # 这里只记录请求。在 Qt 回调外退出原生工具，避免命令切换重入。
        self.close_requested = True
        event.ignore()

    def finish_close(self):
        tool = ACTIVE_TOOL  # 保持引用，直到原生退出调用返回。
        if tool is not None:
            tool.stop()
            if not tool.cleaned:
                return False
        frame = self.frameGeometry()
        self.settings.setValue('window/x', frame.x())
        self.settings.setValue('window/y', frame.y())
        self.settings.sync()
        self.allow_close = True
        self.running = False
        self.close()
        return True

    def main_loop(self):
        while self.running and win32gui.IsWindow(self.hwnd):
            self.loop.processEvents()
            if self.close_requested and self.finish_close():
                break
            if not self.running or not win32gui.IsWindow(self.hwnd):
                break
            PyCadInputQueue.PythonMainLoop()


def Run():
    owner_hwnd = host_window()
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = GaugeDialog(owner_hwnd)
    dialog.show()
    dialog.restore_position()
    # 无边框窗口不会自动抢焦点，显式提到最前，避免被 OPM 主窗遮住。
    dialog.raise_()
    dialog.activateWindow()
    dialog.main_loop()


if __name__ == '__main__':
    Run()
