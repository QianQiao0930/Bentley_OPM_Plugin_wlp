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


def _sweep_body(profile_curve, path_curve, model_ref, origin, up_axis):
    """Sweep the profile along the path, tolerating signature/region variants."""
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    world_up = DVec3d.From(0.0, 0.0, 1.0)
    start = DPoint3d.From(origin[0], origin[1], origin[2])

    def call_ten(profile, up_vector, scalar):
        if scalar:
            return SolidUtil.Create.BodyFromSweep(
                profile, path_curve, model_ref, False, True, False,
                up_vector, 0.0, 1.0, start,
            )
        return SolidUtil.Create.BodyFromSweep(
            profile, path_curve, model_ref, False, True, False,
            up_vector, None, None, None,
        )

    def call_six(profile):
        return SolidUtil.Create.BodyFromSweep(
            profile, path_curve, model_ref, False, True, False
        )

    last_reason = "没有可用的扫掠调用"
    for profile_label, profile in _profile_variants(profile_curve):
        up_vectors = [("up", up)]
        if not (up.x == world_up.x and up.y == world_up.y and up.z == world_up.z):
            up_vectors.append(("worldZ", world_up))
        plans = []
        for up_label, up_vector in up_vectors:
            plans.append((profile_label + "/10-" + up_label, (
                lambda p=profile, u=up_vector: call_ten(p, u, False))))
            plans.append((profile_label + "/10s-" + up_label, (
                lambda p=profile, u=up_vector: call_ten(p, u, True))))
        plans.append((profile_label + "/6", (
            lambda p=profile: call_six(p))))

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
        print("PySteel: operation failed - see debug log")

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
                 rotation_deg=0.0):
        DgnElementSetTool.__init__(self, 0)
        self.m_self = self
        self.family_id = family_id
        self.profile_name = profile_name
        self.insertion_mode = insertion_mode
        self.delete_path = bool(delete_path)
        self.rotation_deg = float(rotation_deg)
        self.family = steel_registry.require_available(family_id)
        self.section_mm = steel_registry.get_section(family_id, profile_name)
        _log(
            "sweep tool created: family={0} profile={1} insertion={2} "
            "delete_path={3} rotation={4}".format(
                family_id, profile_name, insertion_mode, self.delete_path,
                self.rotation_deg,
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
        except Exception:
            _log_exception("sweep failed")
            self._error(
                "扫掠失败：\n{0}\n\n详见日志：{1}".format(
                    traceback.format_exc(), DEBUG_LOG
                )
            )
            return BentleyStatus.eERROR
        message = "已生成 {0} {1} 沿路径扫掠实体。".format(
            self.family.label, self.profile_name
        )
        if self.delete_path:
            message += " 已删除路径线。"
        _log("sweep ok: " + message)
        NotificationManager.OutputPrompt(message)
        return BentleyStatus.eSUCCESS

    def _OnRestartTool(self):
        SteelSectionSweepTool.InstallNewInstance(
            self.family_id, self.profile_name, self.insertion_mode,
            self.delete_path, self.rotation_deg,
        )

    def _OnCleanup(self):
        global _ACTIVE_TOOL
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
        print("PySteel: operation failed - see debug log")

    @staticmethod
    def InstallNewInstance(family_id, profile_name, insertion_mode, delete_path=False,
                           rotation_deg=0.0):
        global _ACTIVE_TOOL
        _log(
            "InstallNewInstance(sweep): family={0} profile={1} delete_path={2} "
            "rotation={3}".format(
                family_id, profile_name, delete_path, rotation_deg
            )
        )
        tool = SteelSectionSweepTool(
            family_id, profile_name, insertion_mode, delete_path, rotation_deg
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
                rotation_deg=0.0):
    return SteelSectionSweepTool.InstallNewInstance(
        family_id, profile_name, insertion_mode, delete_path, rotation_deg
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
