"""Square manhole generator for Bentley OpenPlant Modeler / MicroStation.

Run this file from the MicroStation Python Editor while a 3D OPM model is active.
The dialog accepts user-defined barrel and cover specifications in millimetres,
plus an X/Y/Z placement point for the barrel-bottom centre.

Geometry specification
----------------------
* Barrel: user-entered clear width, depth, and height; walls are formed outward.
* Cover : user-entered outside width, depth, and height; bottom face is open.
* Fit   : the dialog validates that the cover clear inside exceeds the barrel
          outside. The cover top is one wall thickness above the barrel.

The four barrel walls are boolean-united into one SmartSolid; the four cover
walls and top plate are boolean-united into another. This is the reliable Python
equivalent of shelling a box and deleting faces while keeping the lid and barrel
as separate OpenPlant/MicroStation entities.
"""

from __future__ import annotations

# OPM packages selected MicroStation classes in either DgnPlatform or
# MstnPlatform depending on the release.  This is the import pattern used by
# Bentley's shipped Python examples and works in OpenPlant Modeler 2024.
from MSPyBentley import WString
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QApplication,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
    )
except ImportError as exc:
    raise RuntimeError(
        "PyQt5 is required. Please run this script from the OpenPlant/MicroStation Python Editor."
    ) from exc


DEFAULT_WALL_MM = 4.0
HANDLE_PIPE_DIAMETER_MM = 16.0
HANDLE_WIDTH_MM = 140.0
HANDLE_HEIGHT_MM = 60.0
HANDLE_BEND_RADIUS_MM = 32.0
HANDLE_CENTER_OFFSET_MM = 150.0
SUCCESS = 0
BY_LEVEL_COLOR = 0xFFFFFFFF


def _succeeded(status) -> bool:
    """Bentley API success status is zero in all supported OPM releases.

    OpenPlant Modeler 2024 does not export ``BentleyStatus`` from
    ``MSPyBentley`` (unlike some MicroStation Python examples), so comparing the
    underlying status code keeps this script compatible with both bindings.
    """
    try:
        return int(status) == SUCCESS
    except (TypeError, ValueError):
        return status == SUCCESS


def _apply_bylevel_color(element) -> None:
    """Make an element inherit its display color from its assigned level."""
    properties = ElementPropertiesSetter()
    properties.SetColor(BY_LEVEL_COLOR)
    properties.Apply(element)


class ManholeDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("方形人孔")
        self.setModal(True)
        self.resize(390, 300)

        layout = QFormLayout(self)
        self.barrel_width_edit = QLineEdit("600")
        self.barrel_depth_edit = QLineEdit("600")
        self.barrel_height_edit = QLineEdit("100")
        self.cover_width_edit = QLineEdit("620")
        self.cover_depth_edit = QLineEdit("620")
        self.cover_height_edit = QLineEdit("40")
        self.wall_edit = QLineEdit(str(DEFAULT_WALL_MM))
        self.note = QLabel(
            "规格单位为 mm。确认后请在图面单击放置点；\n"
            "该点为筒体下口中心。盖板内腔必须大于筒体外形。"
        )
        self.note.setWordWrap(True)

        layout.addRow("筒体净长（mm）", self.barrel_width_edit)
        layout.addRow("筒体净宽（mm）", self.barrel_depth_edit)
        layout.addRow("筒体高度（mm）", self.barrel_height_edit)
        layout.addRow("盖板外形长（mm）", self.cover_width_edit)
        layout.addRow("盖板外形宽（mm）", self.cover_depth_edit)
        layout.addRow("盖板外形高（mm）", self.cover_height_edit)
        layout.addRow("壁厚（mm）", self.wall_edit)
        layout.addRow("", self.note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate_and_accept(self) -> None:
        try:
            barrel_width = float(self.barrel_width_edit.text())
            barrel_depth = float(self.barrel_depth_edit.text())
            barrel_height = float(self.barrel_height_edit.text())
            cover_width = float(self.cover_width_edit.text())
            cover_depth = float(self.cover_depth_edit.text())
            cover_height = float(self.cover_height_edit.text())
            wall = float(self.wall_edit.text())
            if min(barrel_width, barrel_depth, barrel_height, cover_width, cover_depth, cover_height) <= 0:
                raise ValueError("所有长、宽、高尺寸必须为正数。")
            if wall <= 0:
                raise ValueError("壁厚必须为正数。")
            if cover_height < wall:
                raise ValueError("盖板高度必须不小于壁厚。")
            if barrel_height < max(50.0, cover_height - wall):
                raise ValueError("筒体高度不足，无法容纳盖板裙边和距底 50 mm 的筒体把手。")
            if cover_width - 2.0 * wall <= barrel_width + 2.0 * wall:
                raise ValueError("盖板宽度不足：盖板内腔必须大于筒体外形。")
            if cover_depth - 2.0 * wall <= barrel_depth + 2.0 * wall:
                raise ValueError("盖板深度不足：盖板内腔必须大于筒体外形。")
        except ValueError as exc:
            QMessageBox.warning(self, "输入有误", str(exc))
            return
        self.accept()

    def values_mm(self) -> tuple[float, ...]:
        return (
            float(self.barrel_width_edit.text()),
            float(self.barrel_depth_edit.text()),
            float(self.barrel_height_edit.text()),
            float(self.cover_width_edit.text()),
            float(self.cover_depth_edit.text()),
            float(self.cover_height_edit.text()),
            float(self.wall_edit.text()),
        )


def _mm_to_uor() -> float:
    """Return the active model conversion factor, using millimetres as input."""
    model = ISessionMgr.ActiveDgnModelRef.GetDgnModel()
    return model.GetModelInfo().GetUorPerMeter() / 1000.0


def _create_box(
    model_ref, x, y, z, dx, dy, dz, color: int, name: str, add_to_model: bool = True
):
    """Create one rectangular SmartSolid; optionally defer writing it to DGN."""
    points = DPoint3dArray()
    points.append(DPoint3d(x, y, z))
    points.append(DPoint3d(x + dx, y, z))
    points.append(DPoint3d(x + dx, y + dy, z))
    points.append(DPoint3d(x, y + dy, z))
    points.append(DPoint3d(x, y, z))

    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, points, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的矩形轮廓（状态：{status}）。")

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if len(body_result) < 2 or not _succeeded(body_result[0]):
        raise RuntimeError(f"无法将 {name} 的轮廓转换为实体。")

    status = SolidUtil.Modify.ThickenSheet(body_result[1], dz, 0.0)
    if not _succeeded(status):
        raise RuntimeError(f"无法拉伸 {name}（状态：{status}）。")

    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        solid, body_result[1], profile, model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法生成 {name} 实体（状态：{status}）。")

    _apply_bylevel_color(solid)
    if add_to_model and not _succeeded(solid.AddToModel()):
        raise RuntimeError(f"无法将 {name} 写入当前模型。")
    return solid


def _unite_parts(model_ref, elements, color: int, name: str) -> None:
    """Boolean-unite in-memory SmartSolid elements and write one final element."""
    bodies = []
    for element in elements:
        result = SolidUtil.Convert.ElementToBody(element, True, True, False)
        if len(result) < 2 or not _succeeded(result[0]):
            raise RuntimeError(f"无法读取 {name} 的待合并实体。")
        bodies.append(result[1])

    if len(bodies) < 2:
        raise RuntimeError(f"{name} 至少需要两个实体才能相并。")

    # OpenPlant Modeler 2024: BooleanUnion modifies the first body in place and
    # accepts every remaining body through ISolidKernelEntityPtrArray.
    target_body = bodies[0]
    tool_bodies = ISolidKernelEntityPtrArray()
    for body in bodies[1:]:
        tool_bodies.append(body)
    status = SolidUtil.Modify.BooleanUnion(target_body, tool_bodies)
    if not _succeeded(status):
        raise RuntimeError(f"{name} 实体并集失败。")

    united = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        united, target_body, elements[0], model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法生成合并后的 {name} 实体。")
    _apply_bylevel_color(united)
    if not _succeeded(united.AddToModel()):
        raise RuntimeError(f"无法将合并后的 {name} 写入当前模型。")


def _create_open_square_shell(
    model_ref,
    center_x: float,
    center_y: float,
    clear_width: float,
    clear_depth: float,
    wall: float,
    bottom_z: float,
    height: float,
    color: int,
    prefix: str,
    add_to_model: bool = True,
):
    """Create four connected walls; there are deliberately no top/bottom faces."""
    outer_width = clear_width + 2.0 * wall
    outer_depth = clear_depth + 2.0 * wall
    x0 = center_x - outer_width / 2.0
    y0 = center_y - outer_depth / 2.0

    # Front/back overlap the two side walls at the four corners. This preserves
    # the specified clear opening while giving the boolean operation a real
    # shared volume instead of only a coincident face.
    parts = []
    parts.append(_create_box(
        model_ref, x0, y0, bottom_z, wall, outer_depth, height, color,
        prefix + "-左壁", add_to_model
    ))
    parts.append(_create_box(
        model_ref, x0 + outer_width - wall, y0, bottom_z,
        wall, outer_depth, height, color, prefix + "-右壁", add_to_model
    ))
    parts.append(_create_box(
        model_ref, x0, y0, bottom_z,
        outer_width, wall, height, color, prefix + "-前壁", add_to_model
    ))
    parts.append(_create_box(
        model_ref, x0, y0 + outer_depth - wall, bottom_z,
        outer_width, wall, height, color, prefix + "-后壁", add_to_model
    ))
    return parts


def _create_line_component(model_ref, start, end, name: str):
    """Create an in-memory line component for a sweep path."""
    component = EditElementHandle()
    status = LineHandler.CreateLineElement(
        component, None, DSegment3d(start, end), model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的直线路径。")
    return component


def _create_arc_component(model_ref, start, middle, end, name: str):
    """Create an in-memory circular arc component for a sweep path."""
    component = EditElementHandle()
    arc = DEllipse3d.FromPointsOnArc(start, middle, end)
    status = ArcHandler.CreateArcElement(
        component, None, arc, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的 R32 弯曲路径。")
    return component


def _body_from_sweep(profile_vector, path_vector, model_ref, path_start):
    """Sweep a closed profile along an open path across OPM Python variants."""
    try:
        # Newer bindings expose the optional sweep controls with their defaults.
        result = SolidUtil.Create.BodyFromSweep(
            profile_vector, path_vector, model_ref, False, True, False
        )
    except TypeError:
        # OPM 2024 installations can expose the full C++ signature instead.
        result = SolidUtil.Create.BodyFromSweep(
            profile_vector,
            path_vector,
            model_ref,
            False,  # alignParallel: keep the profile normal to the path
            True,   # selfRepair
            False,  # createSheet: create a solid
            DVec3d.From(0.0, 0.0, 0.0),
            0.0,    # twist angle
            1.0,    # scale
            path_start,
        )

    if len(result) < 2 or not _succeeded(result[0]):
        raise RuntimeError("钢管沿把手曲线扫掠失败。")
    return result[1]


def _create_handle(model_ref, center_x, center_y, cover_top_z, scale, name: str) -> None:
    """Create one Ø16 inverted-U steel-pipe handle as a swept SmartSolid.

    All route dimensions are centre-line dimensions.  The two endpoint faces lie
    on the cover top surface, so the handle is seated on the cover rather than
    floating above it.
    """
    radius = HANDLE_PIPE_DIAMETER_MM * scale / 2.0
    width = HANDLE_WIDTH_MM * scale
    height = HANDLE_HEIGHT_MM * scale
    bend_radius = HANDLE_BEND_RADIUS_MM * scale
    straight_leg = height - bend_radius
    top_straight = width - 2.0 * bend_radius
    if min(straight_leg, top_straight, bend_radius) <= 0.0:
        raise RuntimeError("把手尺寸不成立：请检查 140、60 与 R32 的关系。")

    half_width = width / 2.0
    p0 = DPoint3d(center_x - half_width, center_y, cover_top_z)
    p1 = DPoint3d(center_x - half_width, center_y, cover_top_z + straight_leg)
    p2 = DPoint3d(center_x - half_width + bend_radius, center_y, cover_top_z + height)
    p3 = DPoint3d(center_x + half_width - bend_radius, center_y, cover_top_z + height)
    p4 = DPoint3d(center_x + half_width, center_y, cover_top_z + straight_leg)
    p5 = DPoint3d(center_x + half_width, center_y, cover_top_z)

    # Points on the two 90-degree bends at 45 degrees.  They retain true R32
    # arcs rather than approximating the bends with segmented straight pipes.
    root2_over_2 = 0.7071067811865476
    left_mid = DPoint3d(
        center_x - half_width + bend_radius * (1.0 - root2_over_2),
        center_y,
        cover_top_z + straight_leg + bend_radius * root2_over_2,
    )
    right_mid = DPoint3d(
        center_x + half_width - bend_radius * (1.0 - root2_over_2),
        center_y,
        cover_top_z + straight_leg + bend_radius * root2_over_2,
    )

    components = [
        _create_line_component(model_ref, p0, p1, name + "-左直段"),
        _create_arc_component(model_ref, p1, left_mid, p2, name + "-左弯"),
        _create_line_component(model_ref, p2, p3, name + "-顶部直段"),
        _create_arc_component(model_ref, p3, right_mid, p4, name + "-右弯"),
        _create_line_component(model_ref, p4, p5, name + "-右直段"),
    ]

    path_element = EditElementHandle()
    status = ChainHeaderHandler.CreateChainHeaderElement(
        path_element, None, False, model_ref.Is3d(), model_ref
    )
    # Some OPM 2024 builds return None here after filling the output handle;
    # other builds return the usual Bentley status code.
    if status is not None and not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的复合扫掠路径。")
    for component in components:
        ChainHeaderHandler.AddComponentElement(path_element, component)
    ChainHeaderHandler.AddComponentComplete(path_element)

    # The start tangent is vertical, so a circle in the XY plane is normal to
    # it and makes a solid Ø16 steel pipe after sweeping.
    profile_element = EditElementHandle()
    status = EllipseHandler.CreateEllipseElement(
        profile_element, None, p0, radius, radius, 0.0, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的 Ø16 圆形放样截面。")

    path_vector = ICurvePathQuery.ElementToCurveVector(path_element)
    profile_vector = ICurvePathQuery.ElementToCurveVector(profile_element)
    if path_vector is None or profile_vector is None:
        raise RuntimeError(f"无法读取 {name} 的放样曲线。")
    body = _body_from_sweep(profile_vector, path_vector, model_ref, p0)

    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        solid, body, profile_element, model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法生成 {name} 的钢管实体。")
    _apply_bylevel_color(solid)
    if not _succeeded(solid.AddToModel()):
        raise RuntimeError(f"无法将 {name} 写入当前模型。")


def _create_horizontal_barrel_handle(
    model_ref, center_x, wall_y, center_z, outward_sign, scale, name: str
) -> None:
    """Create one horizontal, outward-facing Ø16 sweep handle on the barrel.

    The route lies in a horizontal plane.  Its 140 mm grip runs along X; its
    60 mm U-depth projects outward from the barrel along Y.  Both pipe end faces
    lie on the external barrel wall and the route centreline is ``center_z``.
    """
    radius = HANDLE_PIPE_DIAMETER_MM * scale / 2.0
    width = HANDLE_WIDTH_MM * scale
    depth = HANDLE_HEIGHT_MM * scale  # confirmed 60 mm U-depth
    bend_radius = HANDLE_BEND_RADIUS_MM * scale
    straight_leg = depth - bend_radius
    top_straight = width - 2.0 * bend_radius
    if min(straight_leg, top_straight, bend_radius) <= 0.0:
        raise RuntimeError("筒体把手尺寸不成立：请检查 140、60 与 R32 的关系。")

    half_width = width / 2.0

    def point(x, outward):
        return DPoint3d(center_x + x, wall_y + outward_sign * outward, center_z)

    p0 = point(-half_width, 0.0)
    p1 = point(-half_width, straight_leg)
    p2 = point(-half_width + bend_radius, depth)
    p3 = point(half_width - bend_radius, depth)
    p4 = point(half_width, straight_leg)
    p5 = point(half_width, 0.0)

    root2_over_2 = 0.7071067811865476
    left_mid = point(
        -half_width + bend_radius * (1.0 - root2_over_2),
        straight_leg + bend_radius * root2_over_2,
    )
    right_mid = point(
        half_width - bend_radius * (1.0 - root2_over_2),
        straight_leg + bend_radius * root2_over_2,
    )

    components = [
        _create_line_component(model_ref, p0, p1, name + "-左直段"),
        _create_arc_component(model_ref, p1, left_mid, p2, name + "-左弯"),
        _create_line_component(model_ref, p2, p3, name + "-主握杆"),
        _create_arc_component(model_ref, p3, right_mid, p4, name + "-右弯"),
        _create_line_component(model_ref, p4, p5, name + "-右直段"),
    ]
    path_element = EditElementHandle()
    status = ChainHeaderHandler.CreateChainHeaderElement(
        path_element, None, False, model_ref.Is3d(), model_ref
    )
    if status is not None and not _succeeded(status):
        raise RuntimeError(f"无法创建 {name} 的复合扫掠路径。")
    for component in components:
        ChainHeaderHandler.AddComponentElement(path_element, component)
    ChainHeaderHandler.AddComponentComplete(path_element)

    # The path starts normal to Y, so the circular profile is constructed in
    # the XZ plane. CreateDisk preserves a true circular (not polygonal) profile.
    profile_ellipse = DEllipse3d.FromCenterNormalRadius(
        p0, DVec3d.From(0.0, outward_sign, 0.0), radius
    )
    profile_vector = CurveVector.CreateDisk(
        profile_ellipse, CurveVector.eBOUNDARY_TYPE_Outer
    )
    path_vector = ICurvePathQuery.ElementToCurveVector(path_element)
    if path_vector is None:
        raise RuntimeError(f"无法读取 {name} 的放样曲线。")
    body = _body_from_sweep(profile_vector, path_vector, model_ref, p0)

    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        solid, body, path_element, model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError(f"无法生成 {name} 的钢管实体。")
    _apply_bylevel_color(solid)
    if not _succeeded(solid.AddToModel()):
        raise RuntimeError(f"无法将 {name} 写入当前模型。")


def create_square_manhole(
    barrel_width_mm: float,
    barrel_depth_mm: float,
    barrel_height_mm: float,
    cover_width_mm: float,
    cover_depth_mm: float,
    cover_height_mm: float,
    wall_mm: float,
    placement_x_mm: float,
    placement_y_mm: float,
    placement_z_mm: float,
) -> None:
    """Create the assembled manhole at the specified barrel-bottom centre point."""
    model_ref = ISessionMgr.ActiveDgnModelRef
    if not model_ref.Is3d():
        raise RuntimeError("请在三维 DGN/OPM 模型中运行此脚本。")

    scale = _mm_to_uor()
    wall = wall_mm * scale
    base_x = placement_x_mm * scale
    base_y = placement_y_mm * scale
    base_z = placement_z_mm * scale
    cover_top = wall
    barrel_height = barrel_height_mm * scale
    clear_width = barrel_width_mm * scale
    clear_depth = barrel_depth_mm * scale
    cover_outer_width = cover_width_mm * scale
    cover_outer_depth = cover_depth_mm * scale
    cover_height = cover_height_mm * scale

    # The barrel is an outward shell with top and bottom faces removed.
    barrel_parts = _create_open_square_shell(
        model_ref, base_x, base_y, clear_width, clear_depth, wall, base_z, barrel_height,
        color=3, prefix="筒体", add_to_model=False
    )
    _unite_parts(model_ref, barrel_parts, color=3, name="筒体")

    # The user-defined cover is bottom-open. Its top surface is one wall
    # thickness above the barrel, while its skirt extends down around the barrel.
    cover_clear_width = cover_outer_width - 2.0 * wall
    cover_clear_depth = cover_outer_depth - 2.0 * wall
    cover_wall_bottom = base_z + barrel_height - (cover_height - cover_top)
    cover_parts = _create_open_square_shell(
        model_ref, base_x, base_y, cover_clear_width, cover_clear_depth, wall,
        cover_wall_bottom, cover_height, color=6, prefix="盖板裙边", add_to_model=False
    )
    cover_parts.append(_create_box(
        model_ref, base_x - cover_outer_width / 2.0, base_y - cover_outer_depth / 2.0,
        base_z + barrel_height, cover_outer_width, cover_outer_depth, cover_top,
        color=6, name="盖板顶面", add_to_model=False
    ))
    _unite_parts(model_ref, cover_parts, color=6, name="盖板")

    # Two identical swept-steel-pipe handles. Their centres are respectively
    # 150 mm above and below the cover centre along the Y axis.
    cover_top_z = base_z + barrel_height + cover_top
    handle_offset = HANDLE_CENTER_OFFSET_MM * scale
    _create_handle(model_ref, base_x, base_y + handle_offset, cover_top_z, scale, "把手+150")
    _create_handle(model_ref, base_x, base_y - handle_offset, cover_top_z, scale, "把手-150")

    # A second pair is fitted horizontally to opposite barrel walls. Their
    # centreline is 50 mm above the barrel bottom, as shown in the supplied
    # section drawing. The U-depth projects away from the barrel exterior.
    barrel_center_z = base_z + 50.0 * scale
    barrel_outer_depth = clear_depth + 2.0 * wall
    _create_horizontal_barrel_handle(
        model_ref, base_x, base_y + barrel_outer_depth / 2.0,
        barrel_center_z, 1.0, scale, "筒体把手+Y"
    )
    _create_horizontal_barrel_handle(
        model_ref, base_x, base_y - barrel_outer_depth / 2.0,
        barrel_center_z, -1.0, scale, "筒体把手-Y"
    )


_active_place_tool = None


class PlaceSquareManholeTool(DgnPrimitiveTool):
    """Single-shot tool: the next data point becomes the barrel-bottom centre."""

    def __init__(self, specifications_mm) -> None:
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.specifications_mm = specifications_mm
        self.m_self = self  # Keep the Python wrapper alive while the tool is active.

    def _GetToolName(self, name):
        return WString("PlaceSquareManhole")

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt("请选择方形人孔的放置点（筒体下口中心）；右键取消。")
        DgnPrimitiveTool._OnPostInstall(self)

    def _OnDataButton(self, ev):
        point_uor = ev.GetPoint()
        scale = _mm_to_uor()
        try:
            create_square_manhole(
                *self.specifications_mm,
                point_uor.x / scale,
                point_uor.y / scale,
                point_uor.z / scale,
            )
            NotificationManager.OutputPrompt("方形人孔已放置。")
        except Exception as exc:
            QMessageBox.critical(None, "方形人孔生成失败", str(exc))
        self._ExitTool()
        return True

    def _OnResetButton(self, ev):
        self._ExitTool()
        return True

    @staticmethod
    def InstallNewInstance(specifications_mm) -> None:
        global _active_place_tool
        _active_place_tool = PlaceSquareManholeTool(specifications_mm)
        _active_place_tool.InstallTool()


def main() -> None:
    """Entry point shown by the MicroStation Python Editor."""
    # MicroStation already owns the QApplication. Creating one only when absent
    # makes this file work in releases where Python Editor starts without one.
    app = QApplication.instance() or QApplication([])
    dialog = ManholeDialog()
    if dialog.exec_() != QDialog.Accepted:
        return

    PlaceSquareManholeTool.InstallNewInstance(dialog.values_mm())


if __name__ == "__main__":
    main()
