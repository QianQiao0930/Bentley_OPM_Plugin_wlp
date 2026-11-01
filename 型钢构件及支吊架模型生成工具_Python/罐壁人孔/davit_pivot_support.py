# -*- coding: utf-8 -*-
"""人孔吊杆回转支座，独立 Bentley MSPy 脚本。

运行：Bentley Python Editor 执行；点取下环孔中心（厚度中面）预览，
再次左键确认，右键取消。修改 DEFAULT_OPTIONS 可调整尺寸/朝向。
编程入口：draw_pivot_support(placement_point, options=None)，点坐标为 UOR。
普通 Python：python -B davit_pivot_support.py --self-test。

局部坐标：原点为下支承环孔中心及中面交点；Z 沿轴向上；X 从法兰向外；
Y 沿法兰切向；安装背板在 -X 一侧，heading_deg 绕 Z 旋转。

图纸采用值（mm）：环厚 16，孔径 D+3，黄铜环厚 3，防脱销公称 5。
截图解释/假设：128 按两环净距；25 按轴端低于下环底面；20 按销孔
中心距轴底端。支座采用 C 形板架示意，未还原未标尺寸的弯板圆角。
D 默认 45；环径向壁厚 16、支臂/背板厚 12、背板内面到轴线 100、
上部轴伸 65、轴肩厚 10 和销孔径 5.5 都是可调假设，不是图纸定值。
轴肩放在黄铜环上方表示轴向承托，并非声称图纸明确有此独立零件。
防脱开口销以圆柱包络简化，不画劈开双腿。未做承载或制造校核。

仅生成红框支座、局部轴段、垫环及防脱销；不生成法兰、人孔盖和 R220
完整吊臂。各件分开建模并封装为普通单元；支架连接处有少量实体重合，
未布尔融合，不导出 STEP，不读取/改写同目录其它脚本。
"""

import math
import sys
import traceback


DEFAULT_OPTIONS = {
    "shaft_dia": 45.0,
    "hole_clearance": 3.0,
    "ring_thickness": 16.0,
    "ring_gap": 128.0,
    "ring_wall": 16.0,
    "brass_thickness": 3.0,
    "back_offset": 100.0,
    "plate_thickness": 12.0,
    "shaft_below": 25.0,
    "pin_end_distance": 20.0,
    "pin_dia": 5.0,
    "pin_hole_dia": 5.5,
    "shaft_above": 65.0,
    "collar_thickness": 10.0,
    "heading_deg": 0.0,
    "include_shaft": True,
}
CELL_NAME = "DAVIT_PIVOT_SUPPORT"


def support_layout(options=None):
    p = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(p)
        if unknown:
            raise ValueError("Unknown options: %s" % sorted(unknown))
        p.update(options)
    if not isinstance(p["include_shaft"], bool):
        raise ValueError("include_shaft must be bool")
    for key in p:
        if key == "include_shaft":
            continue
        p[key] = float(p[key])
        if not math.isfinite(p[key]) or (key != "heading_deg" and p[key] <= 0):
            raise ValueError("Invalid dimension: %s" % key)
    t = p["ring_thickness"]
    inner = (p["shaft_dia"] + p["hole_clearance"]) / 2
    outer = inner + p["ring_wall"]
    upper = p["ring_gap"] + t
    bottom = -t / 2 - p["shaft_below"]
    pin_z = bottom + p["pin_end_distance"]
    if p["plate_thickness"] > t:
        raise ValueError("Arm plate thickness must not exceed ring thickness")
    if p["back_offset"] <= outer + p["plate_thickness"]:
        raise ValueError("Back plate is too close to shaft")
    if not p["pin_dia"] < p["pin_hole_dia"] < p["shaft_dia"]:
        raise ValueError("Require pin diameter < pin hole < shaft diameter")
    if pin_z - p["pin_hole_dia"]/2 <= bottom:
        raise ValueError("Pin hole breaks through shaft end")
    if pin_z + p["pin_hole_dia"]/2 >= -t/2:
        raise ValueError("Pin hole must remain below lower ring")
    if p["shaft_above"] <= p["collar_thickness"]:
        raise ValueError("Upper shaft extension must exceed collar thickness")
    p.update(inner_r=inner, outer_r=outer, upper_z=upper,
             lower_bottom=-t/2, upper_top=upper+t/2,
             shaft_bottom=bottom, pin_z=pin_z,
             brass_bottom=upper+t/2,
             brass_top=upper+t/2+p["brass_thickness"],
             shaft_top=upper+t/2+p["brass_thickness"]+p["shaft_above"])
    return p


def _check(status, stage, allow_none=False):
    if status is None and allow_none:
        return
    try:
        ok = int(status) == 0
    except (TypeError, ValueError):
        raise RuntimeError("%s: invalid status %r" % (stage, status))
    if not ok:
        raise RuntimeError("%s: status %r" % (stage, status))


def _self_test():
    p = support_layout()
    assert p["inner_r"] * 2 == p["shaft_dia"] + 3
    assert p["upper_z"] - p["ring_thickness"] == 128
    assert p["lower_bottom"] == -8
    assert p["shaft_bottom"] == -33 and p["pin_z"] == -13
    assert p["brass_bottom"] == 152 and p["brass_top"] == 155
    assert p["shaft_top"] == 220
    _check(None, "void API", True)
    _check(0, "success")
    for value in (None, 1, "bad"):
        try:
            _check(value, "expected failure")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Invalid API status accepted")
    for options in ({"shaft_dia": float("nan")}, {"ring_gap": 0},
                    {"pin_end_distance": 24}, {"pin_hole_dia": 4},
                    {"back_offset": 20}, {"plate_thickness": 30}):
        try:
            support_layout(options)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid dimensions accepted")
    print("PASS: dimensions, clearances, axial stack, invalid input and API status")
    print("Origin: lower ring bore centre/mid-plane; ring centres Z=0,144 mm")
    print("Bentley geometry and interactive placement require testing in OPM.")


if "--self-test" not in sys.argv:
    from MSPyBentley import *
    from MSPyBentleyGeom import *
    from MSPyDgnPlatform import *
    from MSPyDgnView import *
    from MSPyMstnPlatform import *


    def _build_support(origin, options=None):
        p = support_layout(options)
        ref = ISessionMgr.ActiveDgnModelRef
        if ref is None or origin is None:
            raise RuntimeError("An active model and placement point are required")
        model = ref.GetDgnModel()
        if not model.Is3d():
            raise RuntimeError("Please activate a 3D DGN model")
        scale = model.GetModelInfo().GetUorPerMeter()/1000.0
        if not math.isfinite(scale) or scale <= 0:
            raise RuntimeError("Invalid model unit scale")
        angle = math.radians(p["heading_deg"])
        c, s = math.cos(angle), math.sin(angle)

        def pt(x, y, z):
            return DPoint3d.From(origin.x+scale*(c*x-s*y),
                                origin.y+scale*(s*x+c*y), origin.z+scale*z)

        def cylinder(start, end, radius):
            primitive = ISolidPrimitive.CreateDgnCone(DgnConeDetail(
                pt(*start), pt(*end), radius*scale, radius*scale, True))
            element = EditElementHandle()
            _check(DraftingElementSchema.ToElement(element, primitive, None, model),
                   "Cylinder creation")
            return element

        def body(element):
            status, result = SolidUtil.Convert.ElementToBody(element, True, True, False)
            _check(status, "ElementToBody")
            if result is None:
                raise RuntimeError("ElementToBody returned empty body")
            return result

        def finish(solid, template):
            element = EditElementHandle()
            _check(SolidUtil.Convert.BodyToElement(element, solid, template, model),
                   "BodyToElement")
            return element

        def subtract(element, cutter):
            solid = body(element)
            cutters = ISolidKernelEntityPtrArray()
            cutters.append(body(cutter))
            _check(SolidUtil.Modify.BooleanSubtract(solid, cutters), "BooleanSubtract")
            return finish(solid, element)

        def ring(z0, z1):
            return subtract(cylinder((0,0,z0), (0,0,z1), p["outer_r"]),
                            cylinder((0,0,z0-2), (0,0,z1+2), p["inner_r"]))

        def box(x0, x1, y0, y1, z0, z1):
            points = DPoint3dArray()
            for x, y in ((x0,y0), (x1,y0), (x1,y1), (x0,y1), (x0,y0)):
                points.append(pt(x,y,z0))
            profile = EditElementHandle()
            _check(ShapeHandler.CreateShapeElement(profile, None, points, True, ref),
                   "Plate profile")
            solid = body(profile)
            _check(SolidUtil.Modify.ThickenSheet(solid, (z1-z0)*scale, 0.0),
                   "Plate thickness")
            return finish(solid, profile)

        cell = EditElementHandle()
        _check(NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, CELL_NAME, True, model), "Cell header", allow_none=True)
        if not cell.IsValid():
            raise RuntimeError("Invalid cell header")

        def add(element, color):
            props = ElementPropertiesSetter()
            props.SetColor(color)
            props.Apply(element)
            _check(NormalCellHeaderHandler.AddChildElement(cell, element), "Cell child")

        t = p["ring_thickness"]
        plate = p["plate_thickness"]
        # 支臂在圆孔之外终止，仅与环外侧重合，绝不填塞中心孔。
        arm_end = -p["inner_r"] - p["ring_wall"]/2
        width = 2*p["outer_r"]
        for z in (0, p["upper_z"]):
            add(ring(z-t/2, z+t/2), 3)
            add(box(-p["back_offset"]-plate/2, arm_end,
                    -width/2, width/2, z-plate/2, z+plate/2), 3)
        add(box(-p["back_offset"]-plate, -p["back_offset"],
                -width/2, width/2, -t/2, p["upper_top"]), 3)
        add(ring(p["brass_bottom"], p["brass_top"]), 6)

        if p["include_shaft"]:
            shaft_r = p["shaft_dia"]/2
            pin_z = p["pin_z"]
            shaft = cylinder((0,0,p["shaft_bottom"]), (0,0,p["shaft_top"]), shaft_r)
            add(subtract(shaft, cylinder((0,-shaft_r-2,pin_z),
                                        (0,shaft_r+2,pin_z), p["pin_hole_dia"]/2)), 2)
            # 转动轴肩与轴独立保留，底面接触黄铜垫环顶面。
            collar = cylinder((0,0,p["brass_top"]),
                              (0,0,p["brass_top"]+p["collar_thickness"]), p["outer_r"])
            collar_hole = cylinder((0,0,p["brass_top"]-2),
                                  (0,0,p["brass_top"]+p["collar_thickness"]+2), shaft_r)
            add(subtract(collar, collar_hole), 2)
            add(cylinder((0,-shaft_r-12,pin_z), (0,shaft_r+12,pin_z), p["pin_dia"]/2), 4)
        _check(NormalCellHeaderHandler.AddChildComplete(cell), "Complete cell")
        return cell


    def draw_pivot_support(placement_point, options=None):
        """构建完成后才写模型，返回可整体选择的普通单元句柄。"""
        cell = _build_support(placement_point, options)
        _check(cell.AddToModel(), "AddToModel")
        return cell


    class PivotSupportPlacementTool(DgnPrimitiveTool):
        def __init__(self):
            DgnPrimitiveTool.__init__(self, 0, 0)
            self.m_self = self
            self.preview = None

        def _GetToolName(self, name):
            return WString("PivotSupportPlacementTool")

        def _OnPostInstall(self):
            DgnPrimitiveTool._OnPostInstall(self)
            AccuSnap.GetInstance().EnableSnap(True)
            NotificationManager.OutputPrompt(
                "Pick lower ring centre; next left click accepts; right click cancels.")

        def _OnDataButton(self, event):
            if self.preview is not None:
                self.preview = None
                PyCommandState.StartDefaultCommand()
                return True
            try:
                self.preview = draw_pivot_support(event.GetPoint())
                NotificationManager.OutputPrompt("Preview ready. Left: accept. Right: cancel.")
            except Exception as error:
                traceback.print_exc()
                NotificationManager.OutputPrompt("Pivot support failed: %s" % error)
            return True

        def _discard(self):
            if self.preview is not None:
                _check(self.preview.DeleteFromModel(), "Delete preview", allow_none=True)
                self.preview = None

        def _OnResetButton(self, event):
            try:
                self._discard()
            except Exception as error:
                NotificationManager.OutputPrompt(str(error))
                return True
            PyCommandState.StartDefaultCommand()
            return True

        def _OnCleanup(self):
            try:
                self._discard()
            except Exception:
                traceback.print_exc()


    _ACTIVE_TOOL = None


    def PyMain():
        global _ACTIVE_TOOL
        _ACTIVE_TOOL = PivotSupportPlacementTool()
        _ACTIVE_TOOL.InstallTool()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        PyMain()
