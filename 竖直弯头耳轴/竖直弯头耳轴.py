# -*- coding: utf-8 -*-
"""Bentley OpenPlant Modeler 竖直弯头耳轴参数化建模工具。

在 OPM / MicroStation Python Editor 中运行本文件。用户选择弯头 DN、
中心线弯曲半径和高度 H 后，在三维模型中点取底板中心即可生成：

* 90 度弯头（可选保留）；
* 按标准表选取管径的竖直耳轴；
* 用弯头外包络真实布尔切出的耳轴鞍口；
* A 型方底板、B 型圆底板或 C 型无底板；
* 耳轴下部直径 6 mm 的横向通气孔。

坐标约定：点取点是底板下表面中心；H 是底板上表面至水平管中心线
的竖向距离。弯头位于竖直平面内，界面中的方向是水平管进入弯头的
切线方向。
"""

from __future__ import division

import math
import os
import tempfile

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOG = os.path.join(SCRIPT_DIR, "竖直弯头耳轴_debug_log.txt")
SUCCESS = 0

# 常用钢管外径及 Sch40 壁厚（mm）。壁厚只用于弯头显示和耳轴空心管；
# 用户可在界面中覆盖弯头壁厚。
PIPE_DATA = {
    15: (21.3, 2.77), 20: (26.9, 2.87), 25: (33.7, 3.38),
    32: (42.4, 3.56), 40: (48.3, 3.68), 50: (60.3, 3.91),
    65: (76.1, 5.16), 80: (88.9, 5.49), 100: (114.3, 6.02),
    125: (139.7, 6.55), 150: (168.3, 7.11), 200: (219.1, 8.18),
    250: (273.0, 9.27), 300: (323.9, 10.31), 350: (355.6, 11.13),
    400: (406.4, 12.70), 450: (457.2, 14.27), 500: (508.0, 15.09),
    550: (559.0, 15.88), 600: (610.0, 17.48), 650: (660.0, 18.89),
    700: (711.0, 19.05), 750: (762.0, 19.05), 800: (813.0, 19.05),
    850: (864.0, 19.05), 900: (914.0, 19.05), 950: (965.0, 19.05),
    1000: (1016.0, 19.05), 1050: (1067.0, 19.05),
    1100: (1118.0, 19.05), 1200: (1219.2, 19.05),
}

# 图片表 1 的逐档映射：主弯头 DN 上限、耳轴 DN、A 型方底板边长、底板厚度。
SUPPORT_TABLE = (
    (50, None, 200.0, 10.0),
    (100, 50, 200.0, 10.0),
    (150, 80, 200.0, 10.0),
    (200, 100, 200.0, 12.0),
    (300, 150, 250.0, 12.0),
    (400, 200, 300.0, 12.0),
    (500, 250, 350.0, 16.0),
    (600, 300, 400.0, 16.0),
    (700, 350, 450.0, 20.0),
    (800, 400, 500.0, 20.0),
    (900, 450, 550.0, 20.0),
    (1000, 500, 600.0, 25.0),
    (1200, 600, 700.0, 25.0),
)

# 只开放参考表中明确列出的主弯头规格，避免对表中未出现的 DN65、DN80、
# DN125 等规格静默插值。PIPE_DATA 中仍保留 DN80 等数据供耳轴自动选型使用。
SUPPORTED_MAIN_DNS = (
    15, 20, 25, 32, 40, 50, 100, 150, 200, 250, 300, 350, 400,
    450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000,
    1050, 1100, 1200,
)

DIRECTION_VECTORS = {
    "+X": (1.0, 0.0),
    "-X": (-1.0, 0.0),
    "+Y": (0.0, 1.0),
    "-Y": (0.0, -1.0),
}

def _arrow_icon_path(direction):
    """生成扁平小箭头 PNG，供 QSS 的 down-arrow / up-arrow 引用。"""
    path = os.path.join(
        tempfile.gettempdir(), "trunnion_ui_arrow_%s.png" % direction
    )
    if not os.path.exists(path):
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#6b7280"))
        if direction == "down":
            points = [QPointF(1.5, 3.5), QPointF(8.5, 3.5), QPointF(5.0, 7.5)]
        else:
            points = [QPointF(1.5, 6.5), QPointF(8.5, 6.5), QPointF(5.0, 2.5)]
        painter.drawPolygon(QPolygonF(points))
        painter.end()
        pixmap.save(path, "PNG")
    return path.replace("\\", "/")


# 白色毛玻璃 + 扁平化风格的全局样式表。__ARROW_UP__ / __ARROW_DOWN__
# 在应用样式时替换为运行时生成的箭头图标路径。
GLASS_STYLESHEET = """
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #fbfdff, stop:0.55 #f4f7fb, stop:1 #edf1f7);
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 9pt;
    color: #1f2937;
}
QLabel {
    background: transparent;
    color: #374151;
}
QLabel#titleLabel {
    font-size: 13pt;
    font-weight: 600;
    color: #111827;
}
QLabel#noteLabel {
    color: #6b7280;
    font-size: 8.5pt;
}
QGroupBox {
    background: rgba(255, 255, 255, 78%);
    border: 1px solid #e3e8f0;
    border-radius: 10px;
    margin-top: 14px;
    padding: 8px 12px 12px 12px;
    font-weight: 600;
    color: #111827;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    top: 0px;
    padding: 0 4px;
    background: transparent;
    color: #2f6fed;
}
QComboBox, QDoubleSpinBox {
    background: rgba(255, 255, 255, 92%);
    border: 1px solid #dfe5ee;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 18px;
    color: #1f2937;
    selection-background-color: #2f6fed;
    selection-color: white;
}
QComboBox:hover, QDoubleSpinBox:hover {
    border-color: #b9c6da;
    background: white;
}
QComboBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2f6fed;
    background: white;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox::down-arrow {
    image: url(__ARROW_DOWN__);
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: white;
    border: 1px solid #e3e8f0;
    border-radius: 6px;
    selection-background-color: #e8f0fe;
    selection-color: #1f2937;
    outline: none;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: transparent;
    border: none;
    width: 16px;
}
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {
    background: #eef3fb;
    border-radius: 3px;
}
QDoubleSpinBox::up-arrow {
    image: url(__ARROW_UP__);
    width: 8px;
    height: 8px;
}
QDoubleSpinBox::down-arrow {
    image: url(__ARROW_DOWN__);
    width: 8px;
    height: 8px;
}
QCheckBox {
    spacing: 7px;
    background: transparent;
    color: #374151;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #c6cfdd;
    border-radius: 4px;
    background: white;
}
QCheckBox::indicator:hover {
    border-color: #2f6fed;
}
QCheckBox::indicator:checked {
    background: #2f6fed;
    border-color: #2f6fed;
}
QLabel#previewCard {
    background: rgba(232, 240, 254, 78%);
    border: 1px solid #d3e2fb;
    border-radius: 8px;
    color: #1d4ed8;
    padding: 9px 11px;
    font-weight: 500;
}
QFrame#headerLine {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(47, 111, 237, 0),
                stop:0.5 rgba(47, 111, 237, 55%),
                stop:1 rgba(47, 111, 237, 0));
    max-height: 1px;
    border: none;
}
QPushButton {
    background: white;
    border: 1px solid #d8dfe9;
    border-radius: 7px;
    padding: 6px 20px;
    color: #374151;
    font-weight: 500;
}
QPushButton:hover {
    background: #f3f6fb;
    border-color: #b9c6da;
}
QPushButton:pressed {
    background: #e8edf5;
}
QPushButton:default {
    background: #2f6fed;
    border: 1px solid #2f6fed;
    color: white;
    font-weight: 600;
}
QPushButton:default:hover {
    background: #2a63d4;
    border-color: #2a63d4;
}
QPushButton:default:pressed {
    background: #2558ba;
    border-color: #2558ba;
}
"""


def _log(message):
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as stream:
            stream.write(str(message) + "\n")
    except Exception:
        pass


def _succeeded(status):
    try:
        return int(status) == SUCCESS
    except (TypeError, ValueError):
        return status == SUCCESS


def support_dimensions(main_dn):
    """按表 1 返回耳轴 DN、外径、壁厚、方底板边长和板厚。"""
    for maximum_dn, trunnion_dn, plate_size, plate_thickness in SUPPORT_TABLE:
        if main_dn <= maximum_dn:
            selected_dn = main_dn if trunnion_dn is None else trunnion_dn
            od, wall = PIPE_DATA[selected_dn]
            return {
                "trunnion_dn": selected_dn,
                "trunnion_od": od,
                "trunnion_wall": wall,
                "plate_size": plate_size,
                "plate_thickness": plate_thickness,
            }
    raise ValueError("主弯头 DN%d 超出表 1 的 DN1200 上限。" % main_dn)


def _uor_per_mm(model_ref):
    return model_ref.GetDgnModel().GetModelInfo().GetUorPerMeter() / 1000.0


def _point(base, local_x_mm, local_y_mm, local_z_mm, direction, scale):
    """把支架局部坐标旋转到选定水平管方向并转换成 UOR。"""
    dx, dy = DIRECTION_VECTORS[direction]
    # 局部 Y 是局部 X 在平面内逆时针旋转 90 度后的方向。
    gx = dx * local_x_mm - dy * local_y_mm
    gy = dy * local_x_mm + dx * local_y_mm
    return DPoint3d(
        base.x + gx * scale,
        base.y + gy * scale,
        base.z + local_z_mm * scale,
    )


def _horizontal_vector(direction):
    dx, dy = DIRECTION_VECTORS[direction]
    return DVec3d(dx, dy, 0.0)


def _body_from_sweep(profile, path, model_ref, path_start):
    try:
        result = SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False
        )
    except TypeError:
        result = SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False,
            DVec3d.From(0.0, 0.0, 0.0), 0.0, 1.0, path_start
        )
    if result is None or len(result) < 2 or not _succeeded(result[0]):
        raise RuntimeError("沿路径扫掠实体失败。")
    return result[1]


def _arc_path(start, center, end):
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    arc = DEllipse3d.FromArcCenterStartEnd(center, start, end)
    path.Add(ICurvePrimitive.CreateArc(arc))
    return path


def _line_path(start, end):
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    path.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
    return path


def _disk_profile(center, normal, radius):
    ellipse = DEllipse3d.FromCenterNormalRadius(center, normal, radius)
    return CurveVector.CreateDisk(ellipse, CurveVector.eBOUNDARY_TYPE_Outer)


def _cylinder_body(model_ref, start, end, radius):
    axis = DVec3d(end.x - start.x, end.y - start.y, end.z - start.z)
    profile = _disk_profile(start, axis, radius)
    return _body_from_sweep(profile, _line_path(start, end), model_ref, start)


def _elbow_outer_body(model_ref, start, center, end, tangent, radius):
    profile = _disk_profile(start, tangent, radius)
    return _body_from_sweep(profile, _arc_path(start, center, end), model_ref, start)


def _subtract(target, *cutters):
    tools = ISolidKernelEntityPtrArray()
    for cutter in cutters:
        tools.append(cutter)
    status = SolidUtil.Modify.BooleanSubtract(target, tools)
    if not _succeeded(status):
        raise RuntimeError("SmartSolid 布尔差集失败（状态：%s）。" % status)


def _box_body(model_ref, base, half_size, thickness, direction, scale):
    corners = DPoint3dArray()
    corners.append(_point(base, -half_size, -half_size, 0.0, direction, scale))
    corners.append(_point(base, half_size, -half_size, 0.0, direction, scale))
    corners.append(_point(base, half_size, half_size, 0.0, direction, scale))
    corners.append(_point(base, -half_size, half_size, 0.0, direction, scale))
    corners.append(_point(base, -half_size, -half_size, 0.0, direction, scale))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, corners, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError("创建方底板轮廓失败。")
    converted = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if converted is None or len(converted) < 2 or not _succeeded(converted[0]):
        raise RuntimeError("方底板轮廓转换失败。")
    status = SolidUtil.Modify.SweepBody(
        converted[1], DVec3d(0.0, 0.0, thickness * scale)
    )
    if not _succeeded(status):
        raise RuntimeError("方底板拉伸失败。")
    return converted[1]


def _element_from_body(model_ref, body, color, label):
    element = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        element, body, None, model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError("%s 转换为 SmartSolid 失败。" % label)
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)
    return element


class VerticalElbowTrunnionBuilder(object):
    """在一个点位构造弯头、鞍口耳轴及底板。"""

    def __init__(self, main_dn, bend_radius_mm, height_h_mm,
                 elbow_wall_mm, base_type, direction, keep_elbow,
                 hollow_trunnion=True):
        self.main_dn = int(main_dn)
        self.bend_radius_mm = float(bend_radius_mm)
        self.height_h_mm = float(height_h_mm)
        self.elbow_wall_mm = float(elbow_wall_mm)
        self.base_type = base_type
        self.direction = direction
        self.keep_elbow = bool(keep_elbow)
        self.hollow_trunnion = bool(hollow_trunnion)

    def _validate(self):
        if self.main_dn not in SUPPORTED_MAIN_DNS:
            raise ValueError("参考表 1 没有 DN%d 的主弯头选型数据。" % self.main_dn)
        main_od = PIPE_DATA[self.main_dn][0]
        if self.bend_radius_mm <= main_od / 2.0:
            raise ValueError("弯曲半径必须大于弯头外半径 %.1f mm。" % (main_od / 2.0))
        if self.elbow_wall_mm <= 0.0 or self.elbow_wall_mm * 2.0 >= main_od:
            raise ValueError("弯头壁厚必须大于 0 且小于外径的一半。")
        if self.height_h_mm <= main_od / 2.0:
            raise ValueError("高度 H 过小，应大于弯头外半径 %.1f mm。" % (main_od / 2.0))
        if self.base_type not in ("A 方形底板", "B 圆形底板", "C 无底板"):
            raise ValueError("未知底板类型。")
        if self.direction not in DIRECTION_VECTORS:
            raise ValueError("未知水平管方向。")

    def create_at(self, base_point):
        self._validate()
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None or not model_ref.Is3d():
            raise RuntimeError("请在 OPM 三维模型中运行本工具。")

        scale = _uor_per_mm(model_ref)
        main_od, _default_wall = PIPE_DATA[self.main_dn]
        dims = support_dimensions(self.main_dn)
        trunnion_od = dims["trunnion_od"]
        trunnion_wall = dims["trunnion_wall"]
        plate_t = 0.0 if self.base_type == "C 无底板" else dims["plate_thickness"]
        radius = self.bend_radius_mm

        # 耳轴中心轴与弯头竖直段（立管）中心线对齐：弯头竖直端落在
        # 点取点正上方，弯头起点（水平端）后退一个弯曲半径 R。
        horizontal_cl_z = plate_t + self.height_h_mm
        start = _point(base_point, -radius, 0.0,
                       horizontal_cl_z, self.direction, scale)
        center = _point(base_point, -radius, 0.0,
                        horizontal_cl_z + radius, self.direction, scale)
        end = _point(base_point, 0.0, 0.0,
                     horizontal_cl_z + radius, self.direction, scale)
        contact_cl_z = horizontal_cl_z + radius
        tangent = _horizontal_vector(self.direction)

        # 1. 独立生成实心弯头外包络，专门作为耳轴鞍口的切削刀具体。
        elbow_cutter = _elbow_outer_body(
            model_ref, start, center, end, tangent, main_od * scale / 2.0
        )

        # 2. 耳轴先延伸到弯头中心线，再由外包络切除，留下吻合的凹形鞍口。
        trunnion_bottom = _point(base_point, 0.0, 0.0, plate_t,
                                 self.direction, scale)
        trunnion_top = _point(base_point, 0.0, 0.0, contact_cl_z,
                              self.direction, scale)
        trunnion_body = _cylinder_body(
            model_ref, trunnion_bottom, trunnion_top,
            trunnion_od * scale / 2.0
        )
        _subtract(trunnion_body, elbow_cutter)

        if self.hollow_trunnion:
            inner_radius = (trunnion_od / 2.0 - trunnion_wall) * scale
            if inner_radius <= 0.0:
                raise ValueError("耳轴壁厚数据无效。")
            inner_start = _point(base_point, 0.0, 0.0,
                                 plate_t - 1.0, self.direction, scale)
            inner_end = _point(base_point, 0.0, 0.0,
                               contact_cl_z + 1.0, self.direction, scale)
            _subtract(trunnion_body, _cylinder_body(
                model_ref, inner_start, inner_end, inner_radius
            ))

        # 3. 图示 Ø6 横向通气孔，孔中心位于耳轴底端上方 20 mm。
        hole_z = plate_t + min(20.0, max(8.0, self.height_h_mm * 0.08))
        hole_start = _point(base_point, 0.0, -trunnion_od, hole_z,
                            self.direction, scale)
        hole_end = _point(base_point, 0.0, trunnion_od, hole_z,
                          self.direction, scale)
        _subtract(trunnion_body, _cylinder_body(
            model_ref, hole_start, hole_end, 3.0 * scale
        ))

        bodies = [(trunnion_body, 3, "竖直耳轴")]

        # 4. 底板类型。B 型直径按图为耳轴外径 + 25 mm。
        if self.base_type == "A 方形底板":
            bodies.append((_box_body(
                model_ref, base_point, dims["plate_size"] / 2.0,
                plate_t, self.direction, scale
            ), 4, "A 型方形底板"))
        elif self.base_type == "B 圆形底板":
            plate_start = _point(base_point, 0.0, 0.0, 0.0,
                                 self.direction, scale)
            plate_end = _point(base_point, 0.0, 0.0, plate_t,
                               self.direction, scale)
            bodies.append((_cylinder_body(
                model_ref, plate_start, plate_end,
                (trunnion_od + 25.0) * scale / 2.0
            ), 4, "B 型圆形底板"))

        # 5. 需要时把真实空心弯头写入模型；切削始终使用实心外包络。
        if self.keep_elbow:
            elbow_body = _elbow_outer_body(
                model_ref, start, center, end, tangent, main_od * scale / 2.0
            )
            inner_body = _elbow_outer_body(
                model_ref, start, center, end, tangent,
                (main_od / 2.0 - self.elbow_wall_mm) * scale
            )
            _subtract(elbow_body, inner_body)
            bodies.append((elbow_body, 2, "90 度弯头"))

        # 所有内存几何都成功后再写 DGN，避免前面失败留下半套模型。
        elements = []
        for body, color, label in bodies:
            elements.append(_element_from_body(model_ref, body, color, label))
        for element in elements:
            status = element.AddToModel()
            if not _succeeded(status):
                raise RuntimeError("实体写入当前模型失败（状态：%s）。" % status)

        _log("created DN%d R%.1f H%.1f, trunnion DN%d, base=%s, ids=%s" % (
            self.main_dn, self.bend_radius_mm, self.height_h_mm,
            dims["trunnion_dn"], self.base_type,
            tuple(item.GetElementId() for item in elements)
        ))
        return elements


class TrunnionDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setWindowTitle("竖直弯头耳轴生成器")
        self.setMinimumWidth(480)
        self.setStyleSheet(GLASS_STYLESHEET
                           .replace("__ARROW_UP__", _arrow_icon_path("up"))
                           .replace("__ARROW_DOWN__", _arrow_icon_path("down")))
        self.setFont(QFont("Microsoft YaHei UI", 9))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("竖直弯头耳轴生成器")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        note = QLabel(
            "选择参数后点“确定”，再在三维模型中点取底板下表面中心。\n"
            "H = 底板上表面至水平管中心线；所有尺寸单位均为 mm。"
        )
        note.setObjectName("noteLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        header_line = QFrame()
        header_line.setObjectName("headerLine")
        header_line.setFrameShape(QFrame.NoFrame)
        layout.addWidget(header_line)

        group = QGroupBox("建模参数")
        form = QFormLayout(group)
        form.setContentsMargins(14, 8, 14, 12)
        form.setSpacing(9)
        form.setHorizontalSpacing(14)

        self.dn = QComboBox()
        self.dn.addItems(["DN%d" % dn for dn in SUPPORTED_MAIN_DNS])
        self.dn.setCurrentText("DN200")

        self.radius_mode = QComboBox()
        self.radius_mode.addItems(("长半径 1.5D", "短半径 1.0D", "自定义"))
        self.radius = QDoubleSpinBox()
        self.radius.setRange(20.0, 10000.0)
        self.radius.setDecimals(1)
        self.radius.setSuffix(" mm")

        self.wall = QDoubleSpinBox()
        self.wall.setRange(0.5, 100.0)
        self.wall.setDecimals(2)
        self.wall.setSuffix(" mm")
        self.height_h = QDoubleSpinBox()
        self.height_h.setRange(50.0, 20000.0)
        self.height_h.setValue(1000.0)
        self.height_h.setDecimals(1)
        self.height_h.setSuffix(" mm")

        self.base_type = QComboBox()
        self.base_type.addItems(("A 方形底板", "B 圆形底板", "C 无底板"))
        self.direction = QComboBox()
        self.direction.addItems(("+X", "-X", "+Y", "-Y"))
        self.keep_elbow = QCheckBox("保留生成的空心弯头")
        self.keep_elbow.setChecked(True)
        self.hollow_trunnion = QCheckBox("耳轴按钢管建模（取消则为实心圆钢）")
        self.hollow_trunnion.setChecked(True)

        self.preview = QLabel()
        self.preview.setObjectName("previewCard")
        self.preview.setWordWrap(True)

        form.addRow("弯头规格", self.dn)
        form.addRow("弯曲半径模式", self.radius_mode)
        form.addRow("中心线弯曲半径", self.radius)
        form.addRow("弯头壁厚", self.wall)
        form.addRow("高度 H", self.height_h)
        form.addRow("底板类型", self.base_type)
        form.addRow("水平管方向", self.direction)
        form.addRow("", self.keep_elbow)
        form.addRow("", self.hollow_trunnion)
        layout.addWidget(group)
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setDefault(True)
        ok_button.setText("确定")
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        cancel_button.setText("取消")
        # 按钮必须保留在按钮盒内，否则重新设置父对象后会失去 accepted/rejected 信号。
        layout.addWidget(buttons)

        self.dn.currentTextChanged.connect(self._dn_changed)
        self.radius_mode.currentTextChanged.connect(self._radius_mode_changed)
        self.radius.valueChanged.connect(self._refresh_preview)
        self.wall.valueChanged.connect(self._refresh_preview)
        self.height_h.valueChanged.connect(self._refresh_preview)
        self.base_type.currentTextChanged.connect(self._refresh_preview)
        self._dn_changed()
        self._radius_mode_changed()

    def selected_dn(self):
        return int(self.dn.currentText()[2:])

    def _standard_radius(self):
        factor = 1.0 if self.radius_mode.currentText().startswith("短") else 1.5
        return self.selected_dn() * factor

    def _dn_changed(self):
        _od, default_wall = PIPE_DATA[self.selected_dn()]
        self.wall.blockSignals(True)
        self.wall.setValue(default_wall)
        self.wall.blockSignals(False)
        if self.radius_mode.currentText() != "自定义":
            self.radius.blockSignals(True)
            self.radius.setValue(self._standard_radius())
            self.radius.blockSignals(False)
        self._refresh_preview()

    def _radius_mode_changed(self):
        custom = self.radius_mode.currentText() == "自定义"
        self.radius.setReadOnly(not custom)
        if not custom:
            self.radius.setValue(self._standard_radius())
        self._refresh_preview()

    def _refresh_preview(self):
        dims = support_dimensions(self.selected_dn())
        if self.base_type.currentText() == "A 方形底板":
            plate = "A 型 %.0f×%.0f×%.0f" % (
                dims["plate_size"], dims["plate_size"], dims["plate_thickness"]
            )
        elif self.base_type.currentText() == "B 圆形底板":
            plate = "B 型 Ø%.1f×%.0f" % (
                dims["trunnion_od"] + 25.0, dims["plate_thickness"]
            )
        else:
            plate = "C 型无底板"
        self.preview.setText(
            "自动选型：耳轴 DN%d（外径 %.1f、壁厚 %.2f）；%s；通气孔 Ø6。" % (
                dims["trunnion_dn"], dims["trunnion_od"],
                dims["trunnion_wall"], plate
            )
        )

    def _accept_if_valid(self):
        try:
            self.builder()._validate()
        except Exception as error:
            QMessageBox.warning(self, "参数有误", str(error))
            return
        self.accept()

    def builder(self):
        return VerticalElbowTrunnionBuilder(
            self.selected_dn(), self.radius.value(), self.height_h.value(),
            self.wall.value(), self.base_type.currentText(),
            self.direction.currentText(), self.keep_elbow.isChecked(),
            self.hollow_trunnion.isChecked()
        )


_ACTIVE_PLACEMENT_TOOL = None


class TrunnionPlacementTool(DgnPrimitiveTool):
    def __init__(self, builder):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.builder = builder
        self.m_self = self

    def _GetToolName(self, name):
        return WString("VerticalElbowTrunnionPlacement")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt(
            "请点取竖直弯头耳轴底板下表面中心；右键取消。"
        )
        DgnPrimitiveTool._OnPostInstall(self)

    def _OnDataButton(self, event):
        try:
            self.builder.create_at(event.GetPoint())
            NotificationManager.OutputPrompt("竖直弯头耳轴已生成。")
        except Exception as error:
            _log("create exception: %r" % error)
            QMessageBox.critical(None, "生成失败", "%s\n\n详见：%s" % (error, DEBUG_LOG))
        self._ExitTool()
        return True

    def _OnResetButton(self, event):
        self._ExitTool()
        return True

    @staticmethod
    def InstallNewInstance(builder):
        global _ACTIVE_PLACEMENT_TOOL
        _ACTIVE_PLACEMENT_TOOL = TrunnionPlacementTool(builder)
        _ACTIVE_PLACEMENT_TOOL.InstallTool()


_QT_APPLICATION = None


def main():
    global _QT_APPLICATION
    _QT_APPLICATION = QApplication.instance() or QApplication([])
    dialog = TrunnionDialog()
    if dialog.exec_() != QDialog.Accepted:
        return
    TrunnionPlacementTool.InstallNewInstance(dialog.builder())


if __name__ == "__main__":
    main()
