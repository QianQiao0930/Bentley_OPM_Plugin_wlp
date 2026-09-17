# -*- coding: utf-8 -*-
"""OPM 可视化实体管口生成器。

在 Bentley OpenPlant Modeler 的 PowerPlatform Python 环境中执行本文件。
操作：选择法兰等级、钢管系列、DN、壁厚、长度和放置轴，点击“开始放置”，
然后在模型中点取基点。单位输入为 mm。

面板沿用 端焊三角架/end_welded_triangle_bracket.py 的 PyQt5 自绘风格：
浅色柔面（圆角、柔影、凹槽输入框），不依赖任何图片资源。
"""

from __future__ import division

import json
import math
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
from PyQt5.QtCore import QEventLoop, QPoint, QRectF, QSize, Qt
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPalette, QPen, QRegion)
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QRadioButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

import win32gui


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(PLUGIN_DIR, "flange_data.json")


def load_dimensions():
    """读取可独立替换的 DN/PN 尺寸表。"""
    with open(DATA_FILE, "r", encoding="utf-8") as source:
        return json.load(source)


def _format_number(value):
    """把表里的数字格式化成简洁文本，供输入框与预览使用。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(number - round(number)) < 1e-6:
        return str(int(round(number)))
    return ("%.2f" % number).rstrip("0").rstrip(".")


class NozzleBuilder:
    """利用拉伸、壳体、相并生成一个 SmartSolid 管口。"""

    def __init__(self, dimensions, dn, rating, pipe_schedule, pipe_length_mm, wall_mm, axis, draw_bolt_holes):
        self._dimensions = dimensions
        self._dn = dn
        self._rating = rating
        self._pipe_schedule = pipe_schedule
        self._pipe_length_mm = float(pipe_length_mm)
        self._wall_mm = float(wall_mm)
        self._axis = axis
        self._draw_bolt_holes = bool(draw_bolt_holes)

    def _parameters(self):
        try:
            flange = self._dimensions["ratings"][self._rating][self._dn]
            pipe = self._dimensions["pipe_schedules"][self._pipe_schedule][self._dn]
        except KeyError:
            raise ValueError("尺寸表中没有 {0} / {1} / {2}".format(self._rating, self._pipe_schedule, self._dn))
        if abs(float(flange["pipe_od"]) - float(pipe["pipe_od"])) > 0.01:
            raise ValueError("法兰与钢管的外径数据不一致")
        values = dict(flange)
        values.update(pipe)
        return values

    @staticmethod
    def _visual_wall_thickness(pipe_od_mm):
        """未提供壁厚时使用的纯显示默认值，不代表任何管表或制造要求。"""
        return max(2.0, min(12.0, float(pipe_od_mm) * 0.04))

    @staticmethod
    def _mm_to_uor(model_ref, value_mm):
        """输入总是 mm，按当前 DGN 的工作单位换算成 UOR。"""
        return float(value_mm) * model_ref.GetDgnModel().GetModelInfo().GetUorPerMeter() / 1000.0

    @staticmethod
    def _axis_geometry(axis):
        """返回指定正/负轴的拉伸方向和垂直于该轴的圆轮廓旋转矩阵。"""
        if axis == "+X":
            return DVec3d(1.0, 0.0, 0.0), RotMatrix.FromRowValues(0, 0, 1, 1, 0, 0, 0, 1, 0)
        if axis == "-X":
            return DVec3d(-1.0, 0.0, 0.0), RotMatrix.FromRowValues(0, 0, -1, 1, 0, 0, 0, -1, 0)
        if axis == "+Y":
            return DVec3d(0.0, 1.0, 0.0), RotMatrix.FromRowValues(0, 1, 0, 0, 0, 1, 1, 0, 0)
        if axis == "-Y":
            return DVec3d(0.0, -1.0, 0.0), RotMatrix.FromRowValues(0, -1, 0, 0, 0, -1, 1, 0, 0)
        if axis == "+Z":
            return DVec3d(0.0, 0.0, 1.0), RotMatrix.FromRowValues(1, 0, 0, 0, 1, 0, 0, 0, 1)
        if axis == "-Z":
            return DVec3d(0.0, 0.0, -1.0), RotMatrix.FromRowValues(1, 0, 0, 0, -1, 0, 0, 0, -1)
        raise ValueError("不支持的放置轴：{0}".format(axis))

    @staticmethod
    def _point_along(point, direction, distance):
        return DPoint3d(
            point.x + direction.x * distance,
            point.y + direction.y * distance,
            point.z + direction.z * distance,
        )

    @staticmethod
    def _body_from_circle(model_ref, center, radius_uor, sweep_uor, direction, rotation):
        """由闭合圆轮廓拉伸得到圆柱 SmartSolid；不把中间轮廓写入模型。"""
        profile = EditElementHandle()
        model = model_ref.GetDgnModel()
        status = EllipseHandler.CreateEllipseElement(
            profile, None, center, radius_uor, radius_uor, rotation, model_ref.Is3d(), model
        )
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法创建圆形拉伸轮廓")

        body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        if body_result[0] != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法把拉伸轮廓转换为实体")

        sweep = DVec3d(direction.x * sweep_uor, direction.y * sweep_uor, direction.z * sweep_uor)
        status = SolidUtil.Modify.SweepBody(body_result[1], sweep)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("拉伸操作失败")
        return body_result[1], profile

    @staticmethod
    def _hollow_pipe(pipe_body, wall_uor, direction):
        """对圆柱执行壳体：端面清除，侧壁向内偏移，保留两端开口。"""
        all_faces = ISubEntityPtrArray()
        SolidUtil.GetBodyFaces(all_faces, pipe_body)

        end_faces = ISubEntityPtrArray()
        end_distances = DoubleArray()
        for face in all_faces:
            face_point = DPoint3d()
            face_normal = DVec3d()
            status = SolidUtil.GetPlanarFaceData(face_point, face_normal, face)
            normal_dot_axis = (
                face_normal.x * direction.x + face_normal.y * direction.y + face_normal.z * direction.z
            )
            if status == BentleyStatus.eSUCCESS and abs(normal_dot_axis) > 0.999:
                end_faces.append(face)
                end_distances.append(0.0)  # 0 表示移除该端面，形成开口。

        if len(end_faces) != 2:
            raise RuntimeError("未能识别管道的两个端面，壳体操作已取消")

        status = SolidUtil.Modify.HollowFaces(
            pipe_body,
            -wall_uor,
            end_faces,
            end_distances,
            SolidUtil.Modify.StepFacesOption.eADD_STEP_NonCoincident,
        )
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("壳体操作失败")

    @staticmethod
    def _union(target, *tools_to_union):
        tools = ISolidKernelEntityPtrArray()
        for tool in tools_to_union:
            tools.append(tool)
        status = SolidUtil.Modify.BooleanUnion(target, tools)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("相并操作失败")

    @staticmethod
    def _subtract(target, *tools_to_subtract):
        tools = ISolidKernelEntityPtrArray()
        for tool in tools_to_subtract:
            tools.append(tool)
        status = SolidUtil.Modify.BooleanSubtract(target, tools)
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("布尔差切除失败")

    @staticmethod
    def _bolt_center(center, axis, radius, angle):
        """在垂直于放置轴的平面上计算一个螺栓孔圆心。"""
        u = radius * math.cos(angle)
        v = radius * math.sin(angle)
        axis_name = axis[-1]
        if axis_name == "X":
            return DPoint3d(center.x, center.y + u, center.z + v)
        if axis_name == "Y":
            return DPoint3d(center.x + v, center.y, center.z + u)
        return DPoint3d(center.x + u, center.y + v, center.z)

    def create_at(self, base_point):
        """在 base_point 处创建一个完整的可视化实体管口。"""
        values = self._parameters()
        wall_mm = self._wall_mm
        if wall_mm * 2 >= values["pipe_od"]:
            raise ValueError("壁厚必须小于管外径的一半")

        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None or not model_ref.Is3d():
            raise RuntimeError("请在三维设计模型中运行此工具")

        pipe_radius = self._mm_to_uor(model_ref, values["pipe_od"] / 2.0)
        bore_radius = self._mm_to_uor(model_ref, (values["pipe_od"] - 2.0 * wall_mm) / 2.0)
        wall = self._mm_to_uor(model_ref, wall_mm)
        flange_radius = self._mm_to_uor(model_ref, values["flange_od"] / 2.0)
        flange_thickness = self._mm_to_uor(model_ref, values["flange_thickness"])
        pipe_length_mm = self._pipe_length_mm - float(values["flange_thickness"])
        if pipe_length_mm <= 0.0:
            raise ValueError("管口总长度必须大于法兰厚度 {0:.1f} mm".format(values["flange_thickness"]))
        pipe_length = self._mm_to_uor(model_ref, pipe_length_mm)
        raised_face_od = values.get("raised_face_od")
        raised_face_height = float(values.get("raised_face_height", 0.0))
        raised_radius = None if raised_face_od is None else self._mm_to_uor(model_ref, raised_face_od / 2.0)
        raised_height = self._mm_to_uor(model_ref, raised_face_height)
        overlap = self._mm_to_uor(model_ref, 1.0)
        direction, rotation = self._axis_geometry(self._axis)

        # 1) 总长度 = 钢管名义长度 + 法兰厚度。相交余量只隐藏在法兰内部，
        #    不增加法兰外形厚度，也不改变管口总外形长度。
        pipe_body, template_profile = self._body_from_circle(
            model_ref, base_point, pipe_radius, pipe_length + overlap, direction, rotation
        )
        self._hollow_pipe(pipe_body, wall, direction)

        # 2) 法兰从钢管名义端部开始拉伸，厚度严格等于数据表 C。
        flange_start = self._point_along(base_point, direction, pipe_length)
        flange_body, _ = self._body_from_circle(
            model_ref, flange_start, flange_radius, flange_thickness, direction, rotation
        )
        # 3) 相并为一个实体；当前 CL150 数据未提供密封面尺寸，因此不虚构凸台。
        #    若后续数据表补充 raised_face_od / raised_face_height，会自动生成并相并凸台。
        if raised_radius is not None and raised_height > 0.0:
            face_start = self._point_along(flange_start, direction, flange_thickness - overlap)
            raised_body, _ = self._body_from_circle(
                model_ref, face_start, raised_radius, raised_height + overlap, direction, rotation
            )
            self._union(pipe_body, flange_body, raised_body)
        else:
            self._union(pipe_body, flange_body)

        # 4) 仅切除中心通孔，不生成螺栓孔。
        bore_start = self._point_along(base_point, direction, -overlap)
        bore_height = pipe_length + flange_thickness + raised_height + 3.0 * overlap
        bore_body, _ = self._body_from_circle(
            model_ref, bore_start, bore_radius, bore_height, direction, rotation
        )
        self._subtract(pipe_body, bore_body)

        # 5) 依据 CL150 的 K、L、n 数据切除螺栓孔。
        bolt_count = int(values.get("bolt_count", 0))
        bolt_hole_diameter = float(values.get("bolt_hole_diameter", 0.0))
        bolt_circle = float(values.get("bolt_circle_diameter", 0.0))
        if self._draw_bolt_holes and bolt_count > 0 and bolt_hole_diameter > 0.0 and bolt_circle > 0.0:
            hole_start = self._point_along(flange_start, direction, -overlap)
            hole_depth = flange_thickness + 2.0 * overlap
            hole_radius = self._mm_to_uor(model_ref, bolt_hole_diameter / 2.0)
            bolt_radius = self._mm_to_uor(model_ref, bolt_circle / 2.0)
            hole_bodies = []
            for index in range(bolt_count):
                angle = 2.0 * math.pi * index / bolt_count
                hole_center = self._bolt_center(hole_start, self._axis, bolt_radius, angle)
                hole_body, _ = self._body_from_circle(
                    model_ref, hole_center, hole_radius, hole_depth, direction, rotation
                )
                hole_bodies.append(hole_body)
            self._subtract(pipe_body, *hole_bodies)

        result = EditElementHandle()
        status = SolidUtil.Convert.BodyToElement(
            result, pipe_body, template_profile, model_ref.GetDgnModel()
        )
        if status != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法把生成的实体写入模型")

        properties = ElementPropertiesSetter()
        properties.SetColor(6)
        properties.Apply(result)
        if result.AddToModel() != BentleyStatus.eSUCCESS:
            raise RuntimeError("无法把实体加入当前模型")


class NozzlePlacementTool(DgnPrimitiveTool):
    """一次数据点即创建实体，连续点击可连续放置相同规格的管口。"""

    def __init__(self, builder):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self._builder = builder
        self._self_reference = self

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)

    def _OnDataButton(self, event):
        try:
            self._builder.create_at(event.GetPoint())
        except Exception as error:
            QMessageBox.critical(None, "管口生成失败", str(error))
        return False

    def _OnResetButton(self, event):
        """DgnPrimitiveTool 的必需回调：右键取消当前动作并重置放置工具。"""
        self._OnRestartTool()
        return True

    def _OnRestartTool(self):
        NozzlePlacementTool.install(self._builder)

    @staticmethod
    def install(builder):
        tool = NozzlePlacementTool(builder)
        tool.InstallTool()


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
UI_TITLE = "实体管口生成器"
UI_RADIUS = 12

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
    peak = max(0.0, min(1.0, color.alpha() / 255.0))
    if peak <= 0.0:
        return 0
    return max(1, int(round((1.0 - (1.0 - peak) ** (1.0 / steps)) * 255)))


def paint_soft_shadow(painter, rect, radius, color, dx, dy, spread, steps=24):
    """逐层填充叠加出真渐变的外阴影；描边法会在末端留下可见的一圈硬边。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        grow = spread * (1.0 - step / float(steps))
        frame = QRectF(rect).translated(dx, dy)
        frame.adjust(-grow, -grow, grow, grow)
        painter.drawRoundedRect(frame, radius + grow, radius + grow)


def paint_inner_shadow(painter, rect, radius, color, dx, dy, depth, steps=24):
    """凹槽内影：把同一形状朝 (dx,dy) 平移后叠填，越靠边越深。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        shift = 1.0 - step / float(steps)
        painter.drawRoundedRect(QRectF(rect).translated(dx * shift, dy * shift),
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
        self.setMinimumHeight(44 + 2 * margin_y)
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
        radius = self.radius if self.radius else rect.height() / 2.0
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
            painter.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
            painter.drawLine(cx - 4, cy + 4, cx + 4, cy - 4)
        else:
            painter.drawLine(cx - 5, cy, cx + 5, cy)


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
        outer.setContentsMargins(margin_x + padding, margin_y + padding,
                                 margin_x + padding, margin_y + padding)
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
        self.content.setContentsMargins(margin + padding, margin + padding,
                                        margin + padding, margin + padding)
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
        row.setContentsMargins(margin + 11, margin + 4, margin + 11, margin + 4)
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
        return QSize(metrics.horizontalAdvance(self.text()) + 30, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height() - size) / 2.0
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
        painter.drawText(QRectF(4.0 + size + 8.0, 0.0, self.width() - (12.0 + size),
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
        return QSize(metrics.horizontalAdvance(self.text()) + 32, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height() - size) / 2.0
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
            mark.moveTo(box.left() + 4.0, box.center().y())
            mark.lineTo(box.center().x() - 0.6, box.bottom() - 4.2)
            mark.lineTo(box.right() - 3.4, box.top() + 4.0)
            painter.drawPath(mark)
        else:
            pen = QPen(UI_ACCENT if (enabled and self.underMouse()) else UI_RING,
                       2.0)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255) if enabled else UI_WELL)
            painter.drawRoundedRect(box, 5.0, 5.0)
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(4.0 + size + 9.0, 0.0, self.width() - (13.0 + size),
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
        self.setMinimumWidth(metrics.horizontalAdvance(label) + 48)

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
            painter.drawEllipse(QRectF(9.0, self.height() / 2.0 - 3.5, 7.0, 7.0))
        font = self.font()
        font.setBold(self._selected)
        painter.setFont(font)
        painter.setPen(UI_TEXT)
        painter.drawText(QRectF(26.0, 0.0, self.width() - 32.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label)


class _NeuComboPopup(QWidget):
    """下拉列表弹层：圆角白卡 + 柔影，选项过多时在内部滚动，点击外部自动收起。"""

    MARGIN = 12
    ITEM_HEIGHT = 30
    VISIBLE_ITEMS = 8
    SCROLLBAR_WIDTH = 8

    def __init__(self, combo, entries, on_pick):
        super().__init__(combo, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.items = []
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setStyleSheet(
            'QScrollArea {background: transparent; border: none;}'
            'QScrollArea > QWidget > QWidget {background: transparent;}'
            'QScrollBar:vertical {background: transparent; width: %dpx;'
            ' margin: 1px 0;}' % self.SCROLLBAR_WIDTH +
            'QScrollBar::handle:vertical {background: #C3CDDD;'
            ' border-radius: 4px; min-height: 24px;}'
            'QScrollBar::handle:vertical:hover {background: #A9B6CC;}'
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical'
            ' {height: 0; background: transparent;}'
            'QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical'
            ' {background: transparent;}')

        content = QWidget()
        content.setAttribute(Qt.WA_TranslucentBackground, True)
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)
        for value, label in entries:
            item = _ComboItem(label, value, on_pick, content)
            self.items.append(item)
            column.addWidget(item)
        self._scroll.setWidget(content)
        self._content = content

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.MARGIN, self.MARGIN,
                                 self.MARGIN, self.MARGIN)
        outer.setSpacing(0)
        outer.addWidget(self._scroll)

    def sync(self, current, combo_width):
        for item in self.items:
            item.set_selected(item.value == current)
        count = len(self.items)
        inner_width = max([int(combo_width)]
                          + [item.minimumWidth() for item in self.items] or [0])
        visible = min(count, self.VISIBLE_ITEMS) if count else 1
        view_height = visible * self.ITEM_HEIGHT + max(0, visible - 1)
        total_height = count * self.ITEM_HEIGHT + max(0, count - 1)
        needs_scroll = count > self.VISIBLE_ITEMS
        bar = self.SCROLLBAR_WIDTH if needs_scroll else 0
        self._content.setFixedSize(inner_width, max(total_height, 1))
        self._scroll.setFixedSize(inner_width + bar, max(view_height, 1))
        self.setFixedSize(inner_width + bar + 2 * self.MARGIN,
                          view_height + 2 * self.MARGIN)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        edge = self.MARGIN - 4.0
        rect = QRectF(self.rect()).adjusted(edge, edge, -edge, -edge)
        paint_raised(painter, rect, 12, UI_CARD, spread=6.0, dark=92, light=225)


class NeuCombo(QWidget):
    """凹槽下拉选择框：闭合时显示当前项，点开后弹出 NeuComboPopup。"""

    def __init__(self, entries, current=None, parent=None, on_change=None,
                 width=None):
        super().__init__(parent)
        self.entries = [(value, label) for value, label in entries]
        self._fixed_width = width
        self._value = (current if current is not None
                       else (self.entries[0][0] if self.entries else None))
        self._on_change = on_change
        self._popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(40)
        self._apply_width()

    def _apply_width(self):
        metrics = self.fontMetrics()
        labels = [label for _, label in self.entries]
        natural = max([metrics.horizontalAdvance(label) for label in labels]
                      or [0]) + 76
        if self._fixed_width is None:
            self.setFixedWidth(natural)

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

    def set_entries(self, entries, current=None):
        """重建选项（公称直径会随法兰等级 / 钢管系列变化）。"""
        self.entries = [(value, label) for value, label in entries]
        values = [value for value, _ in self.entries]
        target = current if current in values else (values[0] if values else None)
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None
        self._value = target
        self._apply_width()
        self.update()

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
        self._popup.sync(self._value, self.width())
        self._popup.move(self.mapToGlobal(
            QPoint(-_NeuComboPopup.MARGIN, self.height() - 8)))
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
        painter.drawText(QRectF(15.0, 0.0, self.width() - 46.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label())
        # 右侧下拉箭头：悬停或展开时变主色。
        active = enabled and (self.underMouse() or self.popup_visible())
        pen = QPen(UI_ACCENT if active else UI_MUTED, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = self.width() - 19.0
        cy = self.height() / 2.0 - 1.0
        chevron = QPainterPath()
        chevron.moveTo(cx - 5.0, cy - 2.5)
        chevron.lineTo(cx, cy + 2.5)
        chevron.lineTo(cx + 5.0, cy - 2.5)
        painter.drawPath(chevron)


# ---------------------------------------------------------------------------
# 工具设置面板
# ---------------------------------------------------------------------------

AXIS_ORDER = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")


class NozzleDialog(QWidget):
    """规格 / 长度 / 方向选择，以及“开始放置”入口。"""

    RADIUS = UI_RADIUS

    def __init__(self, dimensions):
        self._app = ensure_qt_app()
        super().__init__()
        self._dimensions = dimensions
        self._running = True
        self._allow_close = False
        self._event_loop = QEventLoop()
        self._axis_buttons = {}

        self.setWindowTitle(UI_TITLE)
        # 无边框：标题栏与最小化/关闭钮自绘，便于与卡片风格统一。
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self._build_ui()

        self._refresh_dn()
        self.refresh_preview()

        self.setMinimumWidth(520)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        self.hwnd = int(self.winId())
        PyCadInputQueue.AttachQtToolSetting(self.hwnd)

    # -- 控件构造 ----------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(NeuTitleBar(UI_TITLE, self._minimize, self.close))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("选择规格与方向，点击【开始放置】，再在三维模型中点取基点；"
                      "实体会沿所选方向生成，可连续放置，右键结束。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = NeuCard("规格参数")
        self._rating = self._combo_row(
            card.content, 0, "法兰等级：",
            [(key, key) for key in sorted(self._dimensions["ratings"].keys())],
            None, self._on_rating_changed)
        self._pipe_schedule = self._combo_row(
            card.content, 1, "钢管系列：",
            [(key, key) for key in sorted(self._dimensions["pipe_schedules"].keys())],
            None, self._on_pipe_schedule_changed)
        self._dn = self._combo_row(
            card.content, 2, "公称直径：", [], None, self._on_dn_changed)
        self._wall = self._edit_row(
            card.content, 3, "钢管壁厚：", "",
            "mm　默认取表中值，可手动覆盖")
        self._length = self._edit_row(
            card.content, 4, "管口总长度：", "200",
            "mm　含法兰厚度 C")
        self._draw_bolt_holes = NeuToggle("绘制螺栓孔")
        self._draw_bolt_holes.toggled.connect(self.refresh_preview)
        self._row(card.content, 5, "法兰螺栓孔：", [self._draw_bolt_holes], 8)
        body.addWidget(card)

        axis_card = NeuCard("放置方向")
        self._axis_group = QButtonGroup(self)
        row = 0
        column = 0
        for axis in AXIS_ORDER:
            button = NeuChoice("%s 轴" % axis)
            button.setChecked(axis == "+Z")
            self._axis_group.addButton(button)
            self._axis_buttons[axis] = button
            axis_card.content.addWidget(
                button, row, column, Qt.AlignLeft | Qt.AlignVCenter)
            column += 1
            if column == 3:
                column = 0
                row += 1
        axis_card.content.setColumnStretch(3, 1)
        body.addWidget(axis_card)

        summary = NeuPanel()
        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setStyleSheet('color: %s; font-size: 11px;'
                                    % UI_TEXT.name())
        summary.content.addWidget(self._preview)
        self._status = QLabel("请在三维模型中点取基点。")
        self._status.setWordWrap(True)
        self._status.setStyleSheet('color: %s; font-size: 11px;'
                                   % UI_INFO.name())
        summary.content.addWidget(self._status)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self._close_button = NeuButton("关闭")
        self._close_button.setFixedWidth(126)
        self._close_button.clicked.connect(self.close)
        self._place_button = NeuButton("开始放置", accent=True)
        self._place_button.setFixedWidth(160)
        self._place_button.clicked.connect(self._start_placement)
        button_row.addStretch(1)
        button_row.addWidget(self._close_button)
        button_row.addWidget(self._place_button)
        body.addLayout(button_row)

    def _row(self, grid, row, name, widgets, spacing=18):
        """卡片内一行：左标签 +（横向排列的）控件。"""
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

    def _combo_row(self, grid, row, name, entries, current, on_change):
        combo = NeuCombo(entries, current=current, on_change=on_change)
        self._row(grid, row, name, [combo], 16)
        return combo

    def _edit_row(self, grid, row, name, value, note):
        field = NeuEdit(value, width=96)
        field.edit.textChanged.connect(self.refresh_preview)
        self._row(grid, row, name, [field, self._note(note)], 8)
        return field

    def _note(self, text):
        label = QLabel(text, self)
        label.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        return label

    # -- 选项联动 ----------------------------------------------------------

    def _on_rating_changed(self):
        self._refresh_dn()

    def _on_pipe_schedule_changed(self):
        self._refresh_dn()

    def _on_dn_changed(self):
        self._set_wall_from_table()
        self.refresh_preview()

    def _refresh_dn(self):
        rating = self._rating.value()
        pipe_schedule = self._pipe_schedule.value()
        if not rating or not pipe_schedule:
            return
        current_dn = self._dn.value()
        compatible_dns = set(self._dimensions["ratings"][rating]) & set(
            self._dimensions["pipe_schedules"][pipe_schedule]
        )
        ordered = sorted(compatible_dns, key=lambda item: int(item[2:]))
        self._dn.set_entries([(dn, dn) for dn in ordered], current_dn)
        self._on_dn_changed()

    def _set_wall_from_table(self):
        """切换钢管系列或 DN 时带入表中壁厚；随后用户仍可手动覆盖。"""
        pipe_schedule = self._pipe_schedule.value()
        dn = self._dn.value()
        if not pipe_schedule or not dn:
            return
        try:
            wall = self._dimensions["pipe_schedules"][pipe_schedule][dn]["wall"]
        except KeyError:
            return
        self._wall.set_value(_format_number(wall))

    def _wall_value(self):
        text = self._wall.value().strip()
        value = float(text)
        return value

    def _length_value(self):
        text = self._length.value().strip()
        value = float(text)
        return value

    def _selected_axis(self):
        for axis, button in self._axis_buttons.items():
            if button.isChecked():
                return axis
        return "+Z"

    def _set_status(self, message, is_error=False):
        self._status.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (UI_ERROR if is_error else UI_INFO).name())
        self._status.setText(message)

    def refresh_preview(self, *_unused):
        rating = self._rating.value()
        pipe_schedule = self._pipe_schedule.value()
        dn = self._dn.value()
        if not rating or not pipe_schedule or not dn:
            return
        try:
            flange = self._dimensions["ratings"][rating][dn]
            pipe = self._dimensions["pipe_schedules"][pipe_schedule][dn]
        except KeyError:
            self._preview.setText("预览：尺寸表中缺少该组合。")
            return
        try:
            length = self._length_value()
            pipe_length = length - float(flange["flange_thickness"])
            pipe_length_text = ("{0:.1f} mm".format(pipe_length)
                                if pipe_length > 0
                                else "无效：总长必须大于法兰厚度")
        except (TypeError, ValueError):
            pipe_length_text = "—"
        try:
            wall_text = "%.2f mm" % self._wall_value()
        except (TypeError, ValueError):
            wall_text = "—"
        self._preview.setText(
            "预览：{rating} / {schedule} / {dn}；管外径 {od:.1f} mm，壁厚 {wall}；"
            "法兰外径 {fod:.1f} mm，厚 {ft:.1f} mm；钢管名义长度 {pipe_len}；"
            "螺栓孔 {count} × Ø{dia:.1f} mm（{draw}）。".format(
                rating=rating, schedule=pipe_schedule, dn=dn,
                od=float(pipe["pipe_od"]), wall=wall_text,
                fod=float(flange["flange_od"]),
                ft=float(flange["flange_thickness"]),
                pipe_len=pipe_length_text,
                count=int(flange["bolt_count"]),
                dia=float(flange["bolt_hole_diameter"]),
                draw="绘制" if self._draw_bolt_holes.isChecked() else "不绘制",
            )
        )

    def _start_placement(self):
        try:
            wall = self._wall_value()
        except (TypeError, ValueError):
            self._set_status("钢管壁厚必须是数字（mm）。", True)
            return
        try:
            length = self._length_value()
        except (TypeError, ValueError):
            self._set_status("管口总长度必须是数字（mm）。", True)
            return
        try:
            builder = NozzleBuilder(
                self._dimensions,
                self._dn.value(),
                self._rating.value(),
                self._pipe_schedule.value(),
                length,
                wall,
                self._selected_axis(),
                self._draw_bolt_holes.isChecked(),
            )
            builder._parameters()
        except ValueError as error:
            self._set_status("参数有误：%s" % error, True)
            return
        NozzlePlacementTool.install(builder)
        self._set_status("已进入放置模式：在模型中点取基点，可连续放置；右键结束。")

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
        """QWidget 关闭时显式结束 Python 主循环，避免脚本一直处于执行状态。"""
        self._running = False
        self._allow_close = True
        event.accept()

    def run_dialog_loop(self):
        """Qt 事件泵与 Bentley 主循环交替，直到面板收起。"""
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2,
                      area.center().y() - self.height() // 2)
        self.show()
        # 无边框/无父窗口不会自动抢焦点，显式提到最前，避免被 OPM 主窗遮住。
        self.raise_()
        self.activateWindow()
        while self._running and win32gui.IsWindow(int(self.hwnd)):
            self._event_loop.processEvents()
            PyCadInputQueue.PythonMainLoop()


def Run():
    """PowerPlatform Python 的入口函数。"""
    try:
        dimensions = load_dimensions()
        dialog = NozzleDialog(dimensions)
        dialog.run_dialog_loop()
    except Exception as error:
        detail = traceback.format_exc()
        print("实体管口生成器启动失败：{0}\n{1}".format(error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE,
                                 "启动失败：{0}".format(error))
        except Exception:
            pass


if __name__ == "__main__":
    Run()
