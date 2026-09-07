# -*- coding: utf-8 -*-
"""OPM 可视化实体管口生成器。

在 Bentley OpenPlant Modeler 的 PowerPlatform Python 环境中执行本文件。
操作：选择 DN、PN、长度和放置轴，点击“开始放置”，然后在模型中点击基点。
单位输入为 mm。
"""

import json
import math
import os
import sys

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from PyQt5.QtCore import QEventLoop
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import win32gui


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(PLUGIN_DIR, "flange_data.json")


def load_dimensions():
    """读取可独立替换的 DN/PN 尺寸表。"""
    with open(DATA_FILE, "r", encoding="utf-8") as source:
        return json.load(source)


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


class NozzleDialog(QWidget):
    def __init__(self, dimensions):
        super().__init__()
        self._dimensions = dimensions
        self._running = True
        self._setup_ui()
        self.storedWinId = self.winId()
        self._event_loop = QEventLoop()
        PyCadInputQueue.AttachQtToolSetting(int(self.storedWinId))

    def _setup_ui(self):
        self.setWindowTitle("实体管口生成器")
        self.setMinimumWidth(420)
        self.setStyleSheet("""
            QWidget {
                background: #F6F8FB;
                color: #1E293B;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 13px;
            }
            QFrame#headerCard, QFrame#card {
                background: #FFFFFF;
                border: 1px solid #E5EAF1;
                border-radius: 12px;
            }
            QLabel#appTitle {
                color: #152238;
                font-size: 20px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#appSubtitle, QLabel#hint {
                color: #6B7A90;
                background: transparent;
            }
            QLabel#sectionTitle {
                color: #52637A;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }
            QLabel#previewText {
                color: #2458A6;
                background: #F0F6FF;
                border: 1px solid #D9E8FF;
                border-radius: 8px;
                padding: 10px;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 38px;
                padding: 0 10px;
                background: #FFFFFF;
                border: 1px solid #D8E0EA;
                border-radius: 7px;
                selection-background-color: #DDEBFF;
            }
            QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #8CB5F5;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #4D8FEA;
            }
            QComboBox::drop-down {
                border: 0;
                width: 28px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border: 0;
                background: #F6F8FB;
            }
            QCheckBox {
                color: #40536C;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background: #FFFFFF;
                border: 1px solid #B9C6D5;
                border-radius: 5px;
            }
            QCheckBox::indicator:checked {
                background: #2F7DE1;
                border-color: #2F7DE1;
            }
            QPushButton {
                min-height: 40px;
                border-radius: 8px;
                font-weight: 600;
                padding: 0 14px;
            }
            QPushButton[axisButton="true"] {
                color: #586A82;
                background: #F7F9FC;
                border: 1px solid #DCE4EE;
            }
            QPushButton[axisButton="true"]:hover {
                color: #2669C9;
                background: #EDF5FF;
                border-color: #9EC3F7;
            }
            QPushButton[axisButton="true"]:checked {
                color: #175DBD;
                background: #E7F0FF;
                border: 1px solid #4D8FEA;
            }
            QPushButton#primaryButton {
                color: #FFFFFF;
                background: #2F7DE1;
                border: 1px solid #2F7DE1;
            }
            QPushButton#primaryButton:hover { background: #216CCB; }
            QPushButton#primaryButton:pressed { background: #1859AD; }
            QPushButton#secondaryButton {
                color: #52637A;
                background: #FFFFFF;
                border: 1px solid #D8E0EA;
            }
            QPushButton#secondaryButton:hover {
                color: #334155;
                background: #F3F6FA;
            }
        """)

        self._rating = QComboBox()
        self._rating.addItems(sorted(self._dimensions["ratings"].keys()))
        self._pipe_schedule = QComboBox()
        self._pipe_schedule.addItems(sorted(self._dimensions["pipe_schedules"].keys()))
        self._dn = QComboBox()
        self._wall = QDoubleSpinBox()
        self._wall.setRange(0.1, 100.0)
        self._wall.setDecimals(2)
        self._wall.setSingleStep(0.1)
        self._wall.setSuffix(" mm")
        self._draw_bolt_holes = QCheckBox("绘制螺栓孔")
        self._draw_bolt_holes.setChecked(False)
        self._length = QSpinBox()
        self._length.setRange(10, 10000)
        self._length.setValue(200)
        self._length.setSuffix(" mm")

        # _refresh_dn 会同步刷新预览，因此必须先创建预览控件。
        self._preview = QLabel()
        self._preview.setWordWrap(True)
        self._preview.setObjectName("previewText")
        self._rating.currentTextChanged.connect(self._refresh_dn)
        self._pipe_schedule.currentTextChanged.connect(self._refresh_dn)
        self._dn.currentTextChanged.connect(self._set_wall_from_table)
        self._refresh_dn()

        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(4)
        title = QLabel("实体管口生成器")
        title.setObjectName("appTitle")
        subtitle = QLabel("选择规格与方向，在三维模型中点击基点放置")
        subtitle.setObjectName("appSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        parameter_card = QFrame()
        parameter_card.setObjectName("card")
        parameter_layout = QVBoxLayout(parameter_card)
        parameter_layout.setContentsMargins(18, 16, 18, 18)
        parameter_layout.setSpacing(12)
        section_title = QLabel("规格参数")
        section_title.setObjectName("sectionTitle")

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)
        form.addRow("法兰等级", self._rating)
        form.addRow("钢管系列", self._pipe_schedule)
        form.addRow("公称直径", self._dn)
        form.addRow("钢管壁厚", self._wall)
        form.addRow("管口总长度", self._length)
        form.addRow("法兰螺栓孔", self._draw_bolt_holes)

        axis_label = QLabel("放置方向")
        axis_buttons = QVBoxLayout()
        axis_buttons.setSpacing(8)
        self._axis_group = QButtonGroup(self)
        self._axis_buttons = {}
        for row_axes in (("+X", "-X", "+Y"), ("-Y", "+Z", "-Z")):
            row = QHBoxLayout()
            row.setSpacing(8)
            for axis in row_axes:
                button = QPushButton(axis + " 轴")
                button.setCheckable(True)
                button.setProperty("axisButton", True)
                button.setChecked(axis == "+Z")
                self._axis_group.addButton(button)
                self._axis_buttons[axis] = button
                row.addWidget(button)
            axis_buttons.addLayout(row)
        form.addRow(axis_label, axis_buttons)

        parameter_layout.addWidget(section_title)
        parameter_layout.addLayout(form)

        self._refresh_preview()
        self._rating.currentTextChanged.connect(self._refresh_preview)
        self._dn.currentTextChanged.connect(self._refresh_preview)
        self._wall.valueChanged.connect(self._refresh_preview)
        self._length.valueChanged.connect(self._refresh_preview)
        self._draw_bolt_holes.toggled.connect(self._refresh_preview)

        place_button = QPushButton("开始放置")
        place_button.setObjectName("primaryButton")
        place_button.clicked.connect(self._start_placement)
        close_button = QPushButton("关闭")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(place_button, 2)
        buttons.addWidget(close_button, 1)

        hint = QLabel("提示：开始放置后，在模型中点取基点；实体会沿所选方向生成。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(parameter_card)
        layout.addWidget(self._preview)
        layout.addLayout(buttons)
        layout.addWidget(hint)
        self.setLayout(layout)

    def _selected_axis(self):
        for axis, button in self._axis_buttons.items():
            if button.isChecked():
                return axis
        return "+Z"

    def _refresh_dn(self):
        rating = self._rating.currentText()
        pipe_schedule = self._pipe_schedule.currentText()
        current_dn = self._dn.currentText()
        compatible_dns = set(self._dimensions["ratings"][rating]) & set(
            self._dimensions["pipe_schedules"][pipe_schedule]
        )
        self._dn.blockSignals(True)
        self._dn.clear()
        self._dn.addItems(sorted(compatible_dns, key=lambda item: int(item[2:])))
        index = self._dn.findText(current_dn)
        if index >= 0:
            self._dn.setCurrentIndex(index)
        self._dn.blockSignals(False)
        self._set_wall_from_table()
        self._refresh_preview()

    def _set_wall_from_table(self):
        """切换钢管系列或 DN 时带入表中壁厚；随后用户仍可手动覆盖。"""
        pipe_schedule = self._pipe_schedule.currentText()
        dn = self._dn.currentText()
        if not pipe_schedule or not dn:
            return
        wall = self._dimensions["pipe_schedules"][pipe_schedule][dn]["wall"]
        self._wall.blockSignals(True)
        self._wall.setValue(float(wall))
        self._wall.blockSignals(False)

    def _refresh_preview(self):
        rating = self._rating.currentText()
        pipe_schedule = self._pipe_schedule.currentText()
        dn = self._dn.currentText()
        if not rating or not pipe_schedule or not dn:
            return
        flange = self._dimensions["ratings"][rating][dn]
        pipe = self._dimensions["pipe_schedules"][pipe_schedule][dn]
        pipe_length = self._length.value() - flange["flange_thickness"]
        pipe_length_text = "{0:.1f} mm".format(pipe_length) if pipe_length > 0 else "无效：总长必须大于法兰厚度"
        self._preview.setText(
            "预览：总长 {0:.1f} mm，钢管名义长度 {1}；管外径 {2:.1f} mm，壁厚 {3:.2f} mm；"
            "法兰外径 {4:.1f} mm，厚 {5:.1f} mm；螺栓孔 {6} × Ø{7:.1f} mm（{8}）。".format(
                self._length.value(), pipe_length_text,
                pipe["pipe_od"], self._wall.value(), flange["flange_od"], flange["flange_thickness"],
                flange["bolt_count"], flange["bolt_hole_diameter"],
                "绘制" if self._draw_bolt_holes.isChecked() else "不绘制"
            )
        )

    def _start_placement(self):
        builder = NozzleBuilder(
            self._dimensions,
            self._dn.currentText(),
            self._rating.currentText(),
            self._pipe_schedule.currentText(),
            self._length.value(),
            self._wall.value(),
            self._selected_axis(),
            self._draw_bolt_holes.isChecked(),
        )
        NozzlePlacementTool.install(builder)

    def closeEvent(self, event):
        """QWidget 关闭时显式结束 Python 主循环，避免脚本一直处于执行状态。"""
        self._running = False
        event.accept()

    def ms_main_loop(self):
        while self._running and win32gui.IsWindow(int(self.storedWinId)):
            self._event_loop.processEvents()
            PyCadInputQueue.PythonMainLoop()


def Run():
    """PowerPlatform Python 的入口函数。"""
    dimensions = load_dimensions()
    application = QApplication.instance() or QApplication(sys.argv)
    dialog = NozzleDialog(dimensions)
    dialog.show()
    dialog.ms_main_loop()


if __name__ == "__main__":
    Run()
