"""One Bentley placement tool shared by every registered steel family.

Two modes are driven from the selector dialog:

* **Place section** – the click point places the closed 2D section, with a live
  dynamic preview and continuous placement until Reset.
* **Sweep along path** – the user selects one open path element (line, polyline,
  SmartLine, complex chain, arc or spline).  The section is generated at the
  path's start point, oriented normal to the path's start tangent, then swept
  into a SmartSolid with ``SolidUtil.Create.BodyFromSweep``.  The user may ask
  in the dialog for the path element to be deleted once the sweep succeeds.

Every placement / sweep step is written to
``型钢截面生成器_debug_log.txt`` in the plug-in root and reported through the
MicroStation prompt bar so a silent failure can be diagnosed.
"""

from __future__ import division

import datetime
import os
import traceback

from MSPyBentley import *  # noqa: F401,F403
from MSPyBentleyGeom import *  # noqa: F401,F403
from MSPyDgnPlatform import *  # noqa: F401,F403
from MSPyDgnView import *  # noqa: F401,F403
from MSPyMstnPlatform import *  # noqa: F401,F403

from . import steel_registry
from . import steel_sweep_geometry


# The log stays in the plug-in root (one level above this package) so it is
# easy to find next to 型钢截面生成器.py.
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBUG_LOG = os.path.join(SCRIPT_DIR, "型钢截面生成器_debug_log.txt")

# Reference direction used to stop a swept section from twisting about a
# horizontal path.  Vertical paths fall back to another world axis internally.
UP_HINT = steel_sweep_geometry.DEFAULT_UP_HINT

# The tool instance that is currently installed, so the settings dialog can end
# it on demand without resetting MicroStation to the default command (which would
# also tear down the attached selector window).
_ACTIVE_TOOL = None
_STATUS_REVISION = 0
_STATUS_MESSAGE = ""
_STATUS_IS_ERROR = False


def _log(message):
    """Append one timestamped line to the plug-in debug log."""
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DEBUG_LOG, "a", encoding="utf-8") as stream:
            stream.write("[{0}] {1}\n".format(stamp, message))
    except Exception:
        pass


def _log_exception(title):
    _log("{0}\n{1}".format(title, traceback.format_exc()))


def publish_status(message, is_error=False):
    """Queue a status update for the Tk dialog without calling Tcl here."""
    global _STATUS_REVISION, _STATUS_MESSAGE, _STATUS_IS_ERROR
    _STATUS_REVISION += 1
    _STATUS_MESSAGE = str(message)
    _STATUS_IS_ERROR = bool(is_error)


def status_snapshot():
    """Return the latest queued ``(revision, message, is_error)`` tuple."""
    return _STATUS_REVISION, _STATUS_MESSAGE, _STATUS_IS_ERROR


def _has_direction(vector):
    try:
        return (vector.x * vector.x + vector.y * vector.y + vector.z * vector.z) > 1.0e-18
    except AttributeError:
        return False


def _new_point():
    try:
        return DPoint3d()
    except Exception:
        return DPoint3d.From(0.0, 0.0, 0.0)


def _new_vector():
    try:
        return DVec3d()
    except Exception:
        return DVec3d.From(0.0, 0.0, 0.0)


def _curve_start_and_tangent(curve_vector):
    """Read the curve's start point and start tangent in one call when possible."""
    start = _new_point()
    end = _new_point()
    tangent_a = _new_vector()
    tangent_b = _new_vector()
    try:
        curve_vector.GetStartEnd(start, end, tangent_a, tangent_b)
    except Exception:
        _log_exception("CurveVector.GetStartEnd(4) failed")
        return None
    if _has_direction(tangent_a):
        return start, tangent_a
    direction = DVec3d.From(end.x - start.x, end.y - start.y, end.z - start.z)
    if _has_direction(direction):
        return start, direction
    return None


def _primitive_start_and_tangent(primitive):
    """Fallback for bindings that do not expose ``CurveVector.GetStartEnd``."""
    primitive_type = primitive.GetCurvePrimitiveType()
    if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
        segment = primitive.GetLine()
        start = segment.StartPoint
        tangent = DVec3d.From(
            segment.EndPoint.x - start.x,
            segment.EndPoint.y - start.y,
            segment.EndPoint.z - start.z,
        )
        return start, tangent
    if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
        points = primitive.GetLineString()
        if len(points) >= 2:
            start = points[0]
            tangent = DVec3d.From(
                points[1].x - start.x,
                points[1].y - start.y,
                points[1].z - start.z,
            )
            return start, tangent
    if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
        child = primitive.GetChildCurveVector()
        if child is not None:
            return _path_start_and_tangent(child)
    try:
        start = _new_point()
        tangent = _new_vector()
        primitive.FractionToPoint(0.0, start, tangent)
        if _has_direction(tangent):
            return start, tangent
    except Exception:
        _log_exception("primitive.FractionToPoint failed")
    return None


def _path_start_and_tangent(curve_vector):
    """Return ``(DPoint3d start, DVec3d tangent)`` for an open path element."""
    found = _curve_start_and_tangent(curve_vector)
    if found is None:
        for primitive in curve_vector:
            found = _primitive_start_and_tangent(primitive)
            if found is not None:
                break
    if found is None:
        try:
            start = _new_point()
            tangent = _new_vector()
            curve_vector.FractionToPoint(0.0, start, tangent)
            if _has_direction(tangent):
                found = (start, tangent)
        except Exception:
            _log_exception("CurveVector.FractionToPoint failed")
    if found is None:
        raise RuntimeError("无法读取所选路径的起点与切向。")
    return found


def _log_path_endpoints(curve_vector):
    """Record endpoint/chord data that Bentley omits from generic eERROR."""
    start = _new_point()
    end = _new_point()
    tangent_a = _new_vector()
    tangent_b = _new_vector()
    try:
        curve_vector.GetStartEnd(start, end, tangent_a, tangent_b)
        dx = end.x - start.x
        dy = end.y - start.y
        dz = end.z - start.z
        chord = (dx * dx + dy * dy + dz * dz) ** 0.5
        _log(
            "sweep path end=({0:.3f},{1:.3f},{2:.3f}) chord={3:.3f} "
            "end_tangent=({4:.6f},{5:.6f},{6:.6f})".format(
                end.x, end.y, end.z, chord,
                tangent_b.x, tangent_b.y, tangent_b.z,
            )
        )
    except Exception:
        _log_exception("could not describe sweep path endpoints")


def _build_profile_curves(identifier, section_mm, insertion_mode, model_ref, frame):
    """Build the section's closed CurveVector mapped into the path frame."""
    geometry = steel_registry.build_sweep_geometry(
        identifier, section_mm, insertion_mode, model_ref
    )
    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    corners = []
    for segment in geometry.segments:
        points = steel_sweep_geometry.sample_segment(segment, frame)
        corners.extend(points)
        world = [DPoint3d.From(point[0], point[1], point[2]) for point in points]
        if len(world) == 2:
            profile.Add(ICurvePrimitive.CreateLine(DSegment3d(world[0], world[1])))
        else:
            profile.Add(
                ICurvePrimitive.CreateArc(
                    DEllipse3d.FromPointsOnArc(world[0], world[1], world[2])
                )
            )
    _log(
        "profile built: segments={0} x=[{1:.3f},{2:.3f}] y=[{3:.3f},{4:.3f}] "
        "z=[{5:.3f},{6:.3f}]".format(
            len(geometry.segments),
            min(point[0] for point in corners), max(point[0] for point in corners),
            min(point[1] for point in corners), max(point[1] for point in corners),
            min(point[2] for point in corners), max(point[2] for point in corners),
        )
    )
    _log(
        "profile plane vs tangent: axisX.t={0:.3e} axisY.t={1:.3e}".format(
            sum(a * b for a, b in zip(frame.axis_x, frame.axis_z)),
            sum(a * b for a, b in zip(frame.axis_y, frame.axis_z)),
        )
    )
    return profile


def _status_ok(status):
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _profile_variants(profile_curve):
    """Return the profile as-is plus the wrapped region most kernels expect."""
    variants = [("outer", profile_curve)]
    try:
        region = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
        region.Add(profile_curve)
        variants.append(("parity", region))
    except Exception:
        _log_exception("wrap profile as ParityRegion failed")
    return variants


def _append_open_path_primitives(source, target, primitive_types):
    """Flatten nested path CurveVectors into one explicit open path."""
    for primitive in source:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
            child = primitive.GetChildCurveVector()
            if child is not None:
                _append_open_path_primitives(child, target, primitive_types)
            continue
        target.Add(primitive)
        try:
            primitive_types.append(int(primitive_type))
        except (TypeError, ValueError):
            primitive_types.append(str(primitive_type))


def _distance_3d(first, second):
    dx = second.x - first.x
    dy = second.y - first.y
    dz = second.z - first.z
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _sample_primitive(primitive, fraction):
    point = _new_point()
    tangent = _new_vector()
    primitive.FractionToPoint(fraction, point, tangent)
    return point, tangent


def _tangent_cosine(first, second):
    first_length = (
        first.x * first.x + first.y * first.y + first.z * first.z
    ) ** 0.5
    second_length = (
        second.x * second.x + second.y * second.y + second.z * second.z
    ) ** 0.5
    if first_length <= 1.0e-12 or second_length <= 1.0e-12:
        return None
    return (
        first.x * second.x + first.y * second.y + first.z * second.z
    ) / (first_length * second_length)


def _three_point_radius(first, middle, last):
    """Estimate a circular arc radius from three sampled 3D points."""
    side_a = _distance_3d(first, middle)
    side_b = _distance_3d(middle, last)
    side_c = _distance_3d(first, last)
    ux = middle.x - first.x
    uy = middle.y - first.y
    uz = middle.z - first.z
    vx = last.x - first.x
    vy = last.y - first.y
    vz = last.z - first.z
    cross_x = uy * vz - uz * vy
    cross_y = uz * vx - ux * vz
    cross_z = ux * vy - uy * vx
    double_area = (
        cross_x * cross_x + cross_y * cross_y + cross_z * cross_z
    ) ** 0.5
    if double_area <= 1.0e-12:
        return None
    return side_a * side_b * side_c / (2.0 * double_area)


def _log_path_primitive_geometry(path_curve, model_ref):
    """Log segment size, arc radius, join gap and tangent continuity."""
    primitives = []

    def collect(source):
        for primitive in source:
            primitive_type = primitive.GetCurvePrimitiveType()
            if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
                child = primitive.GetChildCurveVector()
                if child is not None:
                    collect(child)
            else:
                primitives.append((primitive_type, primitive))

    try:
        collect(path_curve)
        uor_per_mm = model_ref.GetModelInfo().GetUorPerMeter() / 1000.0
        previous_end = None
        previous_tangent = None
        for index, (primitive_type, primitive) in enumerate(primitives, 1):
            start, start_tangent = _sample_primitive(primitive, 0.0)
            middle, unused_tangent = _sample_primitive(primitive, 0.5)
            end, end_tangent = _sample_primitive(primitive, 1.0)
            del unused_tangent
            chord_mm = _distance_3d(start, end) / uor_per_mm
            gap_mm = (
                0.0 if previous_end is None
                else _distance_3d(previous_end, start) / uor_per_mm
            )
            tangent_cos = (
                None if previous_tangent is None
                else _tangent_cosine(previous_tangent, start_tangent)
            )
            radius = _three_point_radius(start, middle, end)
            radius_text = (
                "-" if radius is None else "{0:.3f}mm".format(radius / uor_per_mm)
            )
            cosine_text = (
                "-" if tangent_cos is None else "{0:.9f}".format(tangent_cos)
            )
            _log(
                "path segment {0}: type={1} chord={2:.3f}mm radius={3} "
                "join_gap={4:.6f}mm tangent_cos={5}".format(
                    index, int(primitive_type), chord_mm, radius_text,
                    gap_mm, cosine_text,
                )
            )
            previous_end = end
            previous_tangent = end_tangent
    except Exception:
        _log_exception("could not describe individual sweep path segments")


def _path_variants(path_curve):
    """Return the selected path plus a flattened explicit-Open equivalent."""
    variants = [("selected", path_curve)]
    try:
        rebuilt = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
        primitive_types = []
        _append_open_path_primitives(path_curve, rebuilt, primitive_types)
        if primitive_types:
            variants.append(("rebuilt-open", rebuilt))
        _log(
            "path primitives: count={0} types={1}".format(
                len(primitive_types), primitive_types
            )
        )
    except Exception:
        _log_exception("rebuild path as explicit Open CurveVector failed")
    return variants


def _sweep_body(profile_curve, path_curve, model_ref, origin, up_axis):
    """Sweep the profile along the path, tolerating signature/region variants."""
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    world_up = DVec3d.From(0.0, 0.0, 1.0)
    start = DPoint3d.From(origin[0], origin[1], origin[2])

    def call_ten(profile, path, up_vector, scalar):
        if scalar:
            return SolidUtil.Create.BodyFromSweep(
                profile, path, model_ref, False, True, False,
                up_vector, 0.0, 1.0, start,
            )
        return SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False,
            up_vector, None, None, None,
        )

    def call_six(profile, path):
        return SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False
        )

    last_reason = "没有可用的扫掠调用"
    for path_label, path in _path_variants(path_curve):
        for profile_label, profile in _profile_variants(profile_curve):
            # Bentley's documented extended call commonly uses a null lock
            # direction.  It is not equivalent to the short overload in every
            # MSPython/OpenPlant build, so keep it as an explicit first choice.
            up_vectors = [("none", None), ("up", up)]
            if not (up.x == world_up.x and up.y == world_up.y and up.z == world_up.z):
                up_vectors.append(("worldZ", world_up))
            plans = []
            for up_label, up_vector in up_vectors:
                plans.append((path_label + "/" + profile_label + "/10-" + up_label, (
                    lambda p=profile, c=path, u=up_vector: call_ten(
                        p, c, u, False))))
                if up_vector is not None:
                    plans.append((path_label + "/" + profile_label + "/10s-" + up_label, (
                        lambda p=profile, c=path, u=up_vector: call_ten(
                            p, c, u, True))))
            plans.append((path_label + "/" + profile_label + "/6", (
                lambda p=profile, c=path: call_six(p, c))))

            for label, call in plans:
                try:
                    result = call()
                except Exception as error:
                    last_reason = "{0}: {1!r}".format(label, error)
                    _log("sweep {0} raised: {1!r}".format(label, error))
                    continue
                _log("sweep {0} returned: {1!r}".format(label, result))
                if (isinstance(result, (tuple, list)) and len(result) >= 2
                        and _status_ok(result[0]) and result[1] is not None):
                    _log("sweep success via {0}".format(label))
                    return result[1]
                last_reason = "{0}: {1!r}".format(label, result)
    raise RuntimeError("沿路径扫掠失败（{0}）".format(last_reason))


def _delete_element(element):
    try:
        if element is not None and element.IsValid():
            element.DeleteFromModel()
            return True
    except Exception:
        _log_exception("delete path element failed")
    return False


class SteelSectionPlaceTool(DgnPrimitiveTool):
    """Dynamic-preview tool that places any available registered family."""

    def __init__(self, family_id, profile_name, insertion_mode):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.family_id = family_id
        self.profile_name = profile_name
        self.insertion_mode = insertion_mode
        self.family = steel_registry.require_available(family_id)
        self.section_mm = steel_registry.get_section(family_id, profile_name)
        self._dynamic_logged = False
        self.m_self = self
        _log(
            "place tool created: family={0} profile={1} insertion={2}".format(
                family_id, profile_name, insertion_mode
            )
        )

    def _GetToolName(self, name):
        return WString("Steel Section Generator")

    def _OnPostInstall(self):
        try:
            AccuSnap.GetInstance().EnableSnap(True)
            self._BeginDynamics()
            DgnPrimitiveTool._OnPostInstall(self)
        except Exception:
            _log_exception("_OnPostInstall failed")
            self._error("放置工具初始化失败：\n{0}".format(traceback.format_exc()))
            return
        model_ref = ISessionMgr.ActiveDgnModelRef
        try:
            _log(
                "tool installed: is3d={0} uor_per_meter={1}".format(
                    model_ref.Is3d(), model_ref.GetModelInfo().GetUorPerMeter()
                )
            )
        except Exception:
            _log_exception("could not describe active model")
        NotificationManager.OutputPrompt(
            "请选择 {0} {1} 的插入点（右键 Reset 退出）".format(
                self.family.label, self.profile_name
            )
        )

    def _OnRestartTool(self):
        _log("restart place tool")
        SteelSectionPlaceTool.InstallNewInstance(
            self.family_id, self.profile_name, self.insertion_mode
        )

    def _OnDataButton(self, ev):
        point = ev.GetPoint()
        _log(
            "place data button: x={0:.4f} y={1:.4f} z={2:.4f}".format(
                point.x, point.y, point.z
            )
        )
        try:
            if not self._commit_section(point):
                return False
        except Exception:
            _log_exception("data button failed")
            self._error(
                "放置失败：\n{0}\n\n详见日志：{1}".format(
                    traceback.format_exc(), DEBUG_LOG
                )
            )
            return False
        return True

    def _OnResetButton(self, ev):
        _log("place reset button: exiting tool")
        self._EndDynamics()
        self._ExitTool()
        return True

    def _OnCleanup(self):
        global _ACTIVE_TOOL
        if _ACTIVE_TOOL is self:
            _ACTIVE_TOOL = None
        self.m_self = None

    def _OnDynamicFrame(self, ev):
        eeh = EditElementHandle()
        try:
            if not self._create_element(eeh, ev.GetPoint()):
                return
        except Exception:
            if not self._dynamic_logged:
                self._dynamic_logged = True
                _log_exception("dynamic preview failed")
            return
        if not self._dynamic_logged:
            self._dynamic_logged = True
            _log("dynamic preview first frame ok")
        redraw = RedrawElems()
        redraw.SetDynamicsViews(IViewManager.GetActiveViewSet(), ev.GetViewport())
        redraw.SetDrawMode(eDRAW_MODE_TempDraw)
        redraw.SetDrawPurpose(DrawPurpose.eDynamics)
        redraw.DoRedraw(eeh)

    def _commit_section(self, point):
        eeh = EditElementHandle()
        try:
            if not self._create_element(eeh, point):
                _log("commit section: _create_element returned False")
                self._error("无法生成截面元素。")
                return False
            if BentleyStatus.eSUCCESS != eeh.AddToModel():
                _log("commit section: AddToModel failed")
                self._error("截面没有写入当前 DGN 模型。")
                return False
        except Exception:
            _log_exception("commit section raised")
            self._error(
                "放置失败：\n{0}\n\n详见日志：{1}".format(
                    traceback.format_exc(), DEBUG_LOG
                )
            )
            return False
        _log("commit section: placed ok")
        NotificationManager.OutputPrompt(
            "已放置 {0} {1}。".format(self.family.label, self.profile_name)
        )
        return True

    def _create_element(self, eeh, base_point):
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None:
            raise RuntimeError("没有活动 DGN 模型。")
        geometry = steel_registry.build_geometry(
            self.family_id, self.section_mm, self.insertion_mode, model_ref, base_point
        )
        curves = steel_registry.to_bentley_curve_vector(
            self.family_id, geometry, base_point
        )
        if BentleyStatus.eSUCCESS != DraftingElementSchema.ToElement(
                eeh, curves, None, model_ref.Is3d(), model_ref):
            return False
        ElementPropertyUtils.ApplyActiveSettings(eeh)
        return True

    @staticmethod
    def _error(message):
        _log("ERROR: {0}".format(message))
        try:
            MessageCenter.ShowErrorMessage("型钢截面生成器", message, False)
        except Exception:
            _log_exception("ShowErrorMessage failed")

    @staticmethod
    def InstallNewInstance(family_id, profile_name, insertion_mode):
        global _ACTIVE_TOOL
        _log("InstallNewInstance(place): family={0} profile={1}".format(family_id, profile_name))
        tool = SteelSectionPlaceTool(family_id, profile_name, insertion_mode)
        status = tool.InstallTool()
        _log("InstallNewInstance(place): InstallTool status={0}".format(status))
        if BentleyStatus.eSUCCESS != status:
            raise RuntimeError("无法启动型钢截面放置工具，状态码：{0}".format(status))
        _ACTIVE_TOOL = tool
        return tool


class SteelSectionSweepTool(DgnElementSetTool):
    """Select one open path and sweep the chosen section along it."""

    def __init__(self, family_id, profile_name, insertion_mode, delete_path=False,
                 rotation_deg=0.0, continuous=False):
        DgnElementSetTool.__init__(self, 0)
        self.m_self = self
        self.family_id = family_id
        self.profile_name = profile_name
        self.insertion_mode = insertion_mode
        self.delete_path = bool(delete_path)
        self.rotation_deg = float(rotation_deg)
        self.continuous = bool(continuous)
        self.stopping = False
        self.cleaned = False
        self.family = steel_registry.require_available(family_id)
        self.section_mm = steel_registry.get_section(family_id, profile_name)
        _log(
            "sweep tool created: family={0} profile={1} insertion={2} "
            "delete_path={3} rotation={4} continuous={5}".format(
                family_id, profile_name, insertion_mode, self.delete_path,
                self.rotation_deg, self.continuous,
            )
        )

    def _GetToolName(self, name):
        return WString("Steel Section Sweep Tool")

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
            "请选择 {0} {1} 要沿其扫掠的路径线（右键 Reset 退出）".format(
                self.family.label, self.profile_name
            )
        )

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            element_handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            curve = ICurvePathQuery.ElementToCurveVector(element_handle)
            if curve is None or not curve.IsOpenPath():
                return False
            return True
        except Exception:
            return False

    def _OnElementModify(self, eeh):
        try:
            NotificationManager.OutputPrompt(
                "正在沿路径扫掠 {0} {1} ……".format(
                    self.family.label, self.profile_name
                )
            )
            self._perform_sweep(eeh)
        except Exception as error:
            _log_exception("sweep failed")
            if str(error).startswith("沿路径扫掠失败"):
                message = (
                    "扫掠失败：所选路径不符合要求。\n"
                    "可能原因：圆角半径过小、路径断开/自交、存在过短线段，"
                    "或直线与圆弧不相切。\n"
                    "请增大圆角半径、清理路径，或改用简单连续的开放折线。"
                )
            else:
                message = (
                    "扫掠失败：发生内部错误。请检查所选路径后重试。\n"
                    "详细原因已写入调试日志。"
                )
            publish_status(message, True)
            try:
                NotificationManager.OutputPrompt(
                    "扫掠失败，请查看型钢截面生成器窗口中的提示。"
                )
            except Exception:
                pass
            return BentleyStatus.eERROR
        message = "已生成 {0} {1} 沿路径扫掠实体。".format(
            self.family.label, self.profile_name
        )
        if self.delete_path:
            message += " 已删除路径线。"
        if not self.continuous:
            message += " 扫掠工具已结束。"
        _log("sweep ok: " + message)
        publish_status(message, False)
        NotificationManager.OutputPrompt(message)
        return BentleyStatus.eSUCCESS

    def _OnResetButton(self, ev):
        """Right-click Reset always means stop; never restart the sweep tool."""
        _log("sweep reset button: exiting tool")
        publish_status("已结束扫掠工具。可调整参数后重新选取路径。", False)
        self.stop()
        return True

    def _OnRestartTool(self):
        if self.continuous and not self.stopping and not self.cleaned:
            SteelSectionSweepTool.InstallNewInstance(
                self.family_id, self.profile_name, self.insertion_mode,
                self.delete_path, self.rotation_deg, self.continuous,
            )
        else:
            self.stopping = True
            _log("sweep restart skipped: one-shot or stopping")

    def stop(self):
        if self.cleaned or self.stopping:
            return
        self.stopping = True
        self._ExitTool()

    def _OnCleanup(self):
        global _ACTIVE_TOOL
        self.cleaned = True
        self.stopping = True
        if _ACTIVE_TOOL is self:
            _ACTIVE_TOOL = None
        self.m_self = None

    def _perform_sweep(self, path_element):
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None:
            raise RuntimeError("没有活动 DGN 模型。")
        if not model_ref.Is3d():
            raise RuntimeError("沿路径扫掠需要三维模型。")

        path_curve = ICurvePathQuery.ElementToCurveVector(path_element)
        if path_curve is None or not path_curve.IsOpenPath():
            raise RuntimeError("请选择一条非闭合的路径线。")

        start, tangent = _path_start_and_tangent(path_curve)
        _log(
            "sweep path: isOpen={0} start=({1:.3f},{2:.3f},{3:.3f}) "
            "tangent=({4:.6f},{5:.6f},{6:.6f})".format(
                path_curve.IsOpenPath(), start.x, start.y, start.z,
                tangent.x, tangent.y, tangent.z,
            )
        )
        _log_path_endpoints(path_curve)
        _log_path_primitive_geometry(path_curve, model_ref)
        frame = steel_sweep_geometry.sweep_frame(
            (start.x, start.y, start.z),
            (tangent.x, tangent.y, tangent.z),
            UP_HINT,
        )
        frame = steel_sweep_geometry.rotate_frame(frame, self.rotation_deg)
        profile_curve = _build_profile_curves(
            self.family_id, self.section_mm, self.insertion_mode, model_ref, frame
        )
        body = _sweep_body(
            profile_curve, path_curve, model_ref, frame.origin, frame.axis_y
        )

        result = EditElementHandle()
        if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
                result, body, path_element, model_ref.GetDgnModel()):
            raise RuntimeError("无法把扫掠实体写入元素。")
        ElementPropertyUtils.ApplyActiveSettings(result)
        if BentleyStatus.eSUCCESS != result.AddToModel():
            raise RuntimeError("扫掠实体没有写入当前 DGN 模型。")

        if self.delete_path:
            _delete_element(path_element)

    @staticmethod
    def _error(message):
        _log("ERROR: {0}".format(message))
        try:
            MessageCenter.ShowErrorMessage("型钢截面生成器", message, False)
        except Exception:
            _log_exception("ShowErrorMessage failed")

    @staticmethod
    def InstallNewInstance(family_id, profile_name, insertion_mode, delete_path=False,
                           rotation_deg=0.0, continuous=False):
        global _ACTIVE_TOOL
        _log(
            "InstallNewInstance(sweep): family={0} profile={1} delete_path={2} "
            "rotation={3} continuous={4}".format(
                family_id, profile_name, delete_path, rotation_deg, continuous
            )
        )
        tool = SteelSectionSweepTool(
            family_id, profile_name, insertion_mode, delete_path, rotation_deg,
            continuous,
        )
        status = tool.InstallTool()
        _log("InstallNewInstance(sweep): InstallTool status={0}".format(status))
        if BentleyStatus.eSUCCESS != status:
            raise RuntimeError("无法启动型钢扫掠工具，状态码：{0}".format(status))
        _ACTIVE_TOOL = tool
        return tool


def start_placement(family_id, profile_name, insertion_mode):
    return SteelSectionPlaceTool.InstallNewInstance(
        family_id, profile_name, insertion_mode
    )


def start_sweep(family_id, profile_name, insertion_mode, delete_path=False,
                rotation_deg=0.0, continuous=False):
    return SteelSectionSweepTool.InstallNewInstance(
        family_id, profile_name, insertion_mode, delete_path, rotation_deg,
        continuous,
    )


def has_active_tool():
    return _ACTIVE_TOOL is not None


def end_active_tool():
    """End the installed tool while leaving the selector dialog open.

    ``PyCommandState.StartDefaultCommand`` is deliberately avoided: it also
    unloads the attached Tk tool-settings window.  Exiting the tool itself
    returns control to MicroStation without touching the dialog.
    """
    tool = _ACTIVE_TOOL
    if tool is None:
        _log("end_active_tool: no active tool")
        return False
    try:
        stop = getattr(tool, "stop", None)
        if callable(stop):
            stop()
            _log("end_active_tool: tool ended")
            return True
        dynamics = getattr(tool, "_EndDynamics", None)
        if callable(dynamics):
            try:
                dynamics()
            except Exception:
                _log_exception("end_active_tool: _EndDynamics failed")
        tool._ExitTool()
    except Exception:
        _log_exception("end_active_tool failed")
        return False
    _log("end_active_tool: tool ended")
    return True
