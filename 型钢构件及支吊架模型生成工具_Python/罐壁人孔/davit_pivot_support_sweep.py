# -*- coding: utf-8 -*-
"""矩形截面沿 ] 形路径扫掠的人孔吊杆支架，Bentley MSPy 独立脚本。

一个矩形沿复合路径扫掠成实体，竖直钻通上下板，再做背部外圆角 R20、
内圆角 R10，最后对上下板自由端左右四条竖棱做距离+角度倒角。

全部尺寸 mm，D 是吊杆/圆管外径，默认 45，可改 DEFAULT_OPTIONS。
截面在 YZ 平面：宽 D+30（沿 Y），厚 16（沿 Z），上长边中点为 (0,0,0)。
路径在 XZ 平面：A=(0,0,0)，B=(25+D+20,0,0)，
C=(25+D+20,0,128)，E=(0,0,128)，依次 A→B→C→E。
矩形相对路径向下偏置，绕弯时随路径转向；下板在 Z=-16..0，
上板在 Z=128..144，背板在 X=L..L+16（按直角扫掠的斜接角解释）。
孔轴 X=25+D/2、Y=0，孔径 D+3，一次布尔减法打通上下板。
基础路径转角为 90 度；扫掠后分别对外侧两条横棱倒 R20，内侧两条
横棱倒 R10。两组圆角独立创建，不是等厚同心弯板；直板厚仍为16。
倒角角度30度（相对板长方向 X），沿 X 的距离 c=((D+30-F)/2)*tan60度，
横向退让 b=(D+30-F)/2；F 为法兰边缘厚度，所以前端保留宽度恰好为 F。
F 默认55，仅沿用原24寸人孔脚本的暂定值，尚未规范校核；与 D 分开设置，
修改 DEFAULT_OPTIONS['flange_edge_thickness'] 可指定实际值。
圆角使用原生 BlendEdges，倒角优先使用 ChamferEdges；若版本差异导致
倒角棱定位/验证失败，从倒角前的圆角实体重新用两个三角柱刀具切出
相同的30度平面。后备方案仍严格采用距离+角度公式，不近似圆角。

放置点就是扫掠起点 A / 截面上长边中点。+X 指向背部，+Z 向上；
heading_deg 绕 Z 转动。D=45 时：宽75、厚16、路径边90/128/90、
孔径48、孔距起点47.5；外包络106×75×160；F=55时倒角距离17.320508。

Bentley Python Editor 执行：点取起点预览，再次左键确认，右键取消。
编程入口 draw_pivot_support_sweep(point, options=None)，point 单位为 UOR。
普通 Python 检查：python -B davit_pivot_support_sweep.py --self-test。
不导入或修改目录中的其它脚本，只生成普通单元内的一件钻孔实体。
"""

import math
import sys
import traceback


DEFAULT_OPTIONS = {"shaft_dia": 45.0, "heading_deg": 0.0,
                   "flange_edge_thickness": 55.0}
THICKNESS = 16.0
PATH_HEIGHT = 128.0
OUTER_RADIUS = 20.0
INNER_RADIUS = 10.0
CHAMFER_ANGLE_DEG = 30.0
CELL_NAME = "DAVIT_PIVOT_SUPPORT_SWEEP"


def support_layout(options=None):
    p = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(p)
        if unknown:
            raise ValueError("Unknown options: %s" % sorted(unknown))
        p.update(options)
    for key in p:
        p[key] = float(p[key])
        if not math.isfinite(p[key]):
            raise ValueError("Non-finite value: %s" % key)
    d = p["shaft_dia"]
    if d <= 0:
        raise ValueError("D must be positive")
    width = d + 30.0
    length = 25.0 + d + 20.0
    hole_x = 25.0 + d/2.0
    flange_t = p["flange_edge_thickness"]
    if not 0 < flange_t < width:
        raise ValueError("Require 0 < flange edge thickness < D+30")
    inset = (width-flange_t)/2.0
    chamfer_distance = inset*math.tan(math.radians(60.0))
    if chamfer_distance >= length-INNER_RADIUS:
        raise ValueError("End chamfer reaches the rear bend")
    # 圆孔必须与倒角斜边保持距离；检查到有限线段的最短距离。
    sx, sy = 0., flange_t/2.
    vx, vy = chamfer_distance, inset
    fraction = max(0., min(1., ((hole_x-sx)*vx-sy*vy)/(vx*vx+vy*vy)))
    clearance = math.hypot(hole_x-sx-fraction*vx, -sy-fraction*vy)-(d+3.)/2.
    if clearance <= 0:
        raise ValueError("End chamfer intersects the shaft hole")
    p.update(width=width, thickness=THICKNESS, length=length, height=PATH_HEIGHT,
             hole_x=hole_x, hole_dia=d+3.0,
             outer_radius=OUTER_RADIUS, inner_radius=INNER_RADIUS,
             chamfer_angle=math.radians(CHAMFER_ANGLE_DEG),
             chamfer_distance=chamfer_distance, chamfer_inset=inset,
             chamfer_hole_clearance=clearance,
             path=((0.,0.,0.), (length,0.,0.),
                   (length,0.,PATH_HEIGHT), (0.,0.,PATH_HEIGHT)),
             # 右手法向 +X；矩形上边中点严格位于路径起点。
             profile=((0.,-width/2.,-THICKNESS), (0.,width/2.,-THICKNESS),
                      (0.,width/2.,0.), (0.,-width/2.,0.),
                      (0.,-width/2.,-THICKNESS)),
             cutter_start=(hole_x,0.,-THICKNESS-2.),
             cutter_end=(hole_x,0.,PATH_HEIGHT+THICKNESS+2.))
    return p


def _blend_targets(p):
    """以局部坐标描述要圆角的四条横向棱，避免依赖内核边编号。"""
    w, l, t, h = p["width"], p["length"], p["thickness"], p["height"]
    return [((x,-w/2,z), (x,w/2,z), radius)
            for x,z,radius in ((l+t,-t,OUTER_RADIUS), (l+t,h+t,OUTER_RADIUS),
                               (l,0.,INNER_RADIUS), (l,h,INNER_RADIUS))]


def _blend_tangent_edges(p):
    """圆角后八条切线边的位置；用于核对实际圆角半径/单位。"""
    l,t,h,w = p["length"],p["thickness"],p["height"],p["width"]
    ro,ri = OUTER_RADIUS,INNER_RADIUS
    positions = ((l+t-ro,-t), (l+t,-t+ro), (l+t-ro,h+t), (l+t,h+t-ro),
                 (l-ri,0.), (l,ri), (l-ri,h), (l,h-ri))
    return [((x,-w/2,z),(x,w/2,z)) for x,z in positions]


def _chamfer_triangles(p):
    """两个端角的 XY 刀具轮廓；斜边严格落在所需30度平面上。

    向模型外延长2mm，避免刀具的其它面与板端/板侧共面。
    +Y斜边为 y=F/2+x*tan30；-Y关于 XZ 平面对称。
    """
    extension = 2.0
    slope = math.tan(p["chamfer_angle"])
    nose,half = p["flange_edge_thickness"]/2,p["width"]/2
    result = []
    for sign in (-1.,1.):
        vertices = [(-extension,sign*(nose-extension*slope)),
                    (p["chamfer_distance"]+extension/slope,sign*(half+extension)),
                    (-extension,sign*(half+extension))]
        if sign < 0:
            vertices.reverse()
        result.append(tuple(vertices+[vertices[0]]))
    return result


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
    for d in (35., 40., 45., 50., 55., 60., 65.):
        p = support_layout({"shaft_dia": d})
        a, b, c, e = p["path"]
        assert math.dist(a,b) == 25+d+20
        assert math.dist(b,c) == 128 and math.dist(c,e) == math.dist(a,b)
        assert p["profile"][0] == p["profile"][-1]
        upper1, upper2 = p["profile"][2:4]
        assert tuple((u+v)/2 for u,v in zip(upper1,upper2)) == a
        assert math.dist(upper1,upper2) == d+30
        assert math.dist(p["profile"][1],upper1) == 16
        assert p["hole_x"] == 25+d/2 and p["hole_dia"] == d+3
        radius = p["hole_dia"]/2
        assert math.isclose(p["hole_x"]-radius, 23.5)
        assert math.isclose(p["length"]-p["hole_x"]-radius, 18.5)
        assert math.isclose(p["width"]/2-radius, 13.5)
        assert p["cutter_start"][2] < -16
        assert p["cutter_end"][2] > 128+16
        assert math.isclose(p["chamfer_distance"],
                            ((d+30-p["flange_edge_thickness"])/2)*math.tan(math.pi/3))
        assert math.isclose(p["chamfer_distance"]*math.tan(p["chamfer_angle"]),
                            p["chamfer_inset"])
        assert math.isclose(p["width"]-2*p["chamfer_inset"],p["flange_edge_thickness"])
        assert p["chamfer_hole_clearance"] > 0
        assert [entry[2] for entry in _blend_targets(p)] == [20.,20.,10.,10.]
        assert len(_blend_tangent_edges(p)) == 8
    assert math.isclose(support_layout()["chamfer_distance"], 17.32050807568877)
    for flange_t in (45.,50.,55.):
        p = support_layout({"flange_edge_thickness":flange_t})
        assert math.isclose(p["chamfer_inset"], (75-flange_t)/2)
        for triangle in _chamfer_triangles(p):
            assert triangle[0] == triangle[-1]
            area2 = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(triangle,triangle[1:]))
            assert area2 > 0  # +Z法向，沿+Z拉伸。
            diagonal = [v for v in triangle[:-1] if math.isclose(
                abs(v[1]),flange_t/2+v[0]*math.tan(math.pi/6))]
            assert len(diagonal) == 2
    _check(None, "void API", True)
    _check(0, "success")
    for invalid in ({"shaft_dia":0}, {"shaft_dia":float("nan")},
                    {"heading_deg":float("inf")}, {"unknown":1},
                    {"flange_edge_thickness":0}, {"flange_edge_thickness":75}):
        try:
            support_layout(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid option accepted")
    print("PASS: profile, upper-edge anchor, three path lengths and through-hole")
    print("PASS: seven diameters, constant edge clearances and invalid input")
    print("PASS: R20/R10 edge targets; 30-degree chamfer formula; retained nose width")
    print("PASS: equivalent chamfer cutters, exact slope and outward extension")
    print("Bentley sweep topology and appearance still require OPM verification.")


if "--self-test" not in sys.argv:
    from MSPyBentley import *
    from MSPyBentleyGeom import *
    from MSPyDgnPlatform import *
    from MSPyDgnView import *
    from MSPyMstnPlatform import *


    def _edge_at(solid, start, end, tolerance):
        """按端点匹配棱；兼容查询坐标为 UOR 或实体内核坐标的绑定。"""
        edges = ISubEntityPtrArray()
        SolidUtil.GetBodyEdges(edges,solid)
        matches = []

        def close(a,b):
            return math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2) <= tolerance

        def pair_matches(a,b):
            return (close(a,start) and close(b,end)) or (close(a,end) and close(b,start))

        for edge in edges:
            vertices = ISubEntityPtrArray()
            _check(SolidUtil.GetEdgeVertices(vertices,edge), "Get edge vertices")
            if len(vertices) != 2:
                continue
            a,b = DPoint3d.From(0.,0.,0.),DPoint3d.From(0.,0.,0.)
            _check(SolidUtil.EvaluateVertex(vertices[0],a), "Evaluate edge vertex")
            _check(SolidUtil.EvaluateVertex(vertices[1],b), "Evaluate edge vertex")
            matched = pair_matches(a,b)
            if not matched:
                transform = solid.GetEntityTransform()
                transform.Multiply(a)
                transform.Multiply(b)
                matched = pair_matches(a,b)
            if matched:
                matches.append(edge)
        if len(matches) != 1:
            raise RuntimeError("Expected one edge at requested endpoints, found %d" % len(matches))
        return matches[0]


    def _planar_chamfer(solid,p,pt,scale,ref):
        """原生倒角接口失败时，按同一距离/角度精确切削四个板端角。"""
        cutters = ISolidKernelEntityPtrArray()
        z0 = -p["thickness"]-2.
        z1 = p["height"]+p["thickness"]+2.
        for polygon in _chamfer_triangles(p):
            points = DPoint3dArray()
            for x,y in polygon:
                points.append(pt((x,y,z0)))
            profile = EditElementHandle()
            _check(ShapeHandler.CreateShapeElement(profile,None,points,True,ref),
                   "Chamfer cutter profile")
            status,cutter = SolidUtil.Convert.ElementToBody(profile,True,True,False)
            _check(status,"Chamfer cutter sheet")
            if cutter is None:
                raise RuntimeError("Empty chamfer cutter sheet")
            _check(SolidUtil.Modify.ThickenSheet(cutter,(z1-z0)*scale,0.),
                   "Chamfer cutter extrusion")
            cutters.append(cutter)
        _check(SolidUtil.Modify.BooleanSubtract(solid,cutters), "Planar 30-degree chamfers")
        # 检查上下四角各自斜面的两侧，一侧应保留材料，另一侧应为空。
        x = p["chamfer_distance"]/2.
        boundary = p["flange_edge_thickness"]/2.+x*math.tan(p["chamfer_angle"])
        delta = min(0.5,p["chamfer_inset"]/8.)
        for z in (-p["thickness"]/2.,p["height"]+p["thickness"]/2.):
            for sign in (-1.,1.):
                keep = pt((x,sign*(boundary-delta),z))
                remove = pt((x,sign*(boundary+delta),z))
                if not SolidUtil.IsPointInsideBody(solid,keep):
                    raise RuntimeError("Planar chamfer validation: retained side is empty")
                if SolidUtil.IsPointInsideBody(solid,remove):
                    raise RuntimeError("Planar chamfer validation: cut side still contains material")
        return solid


    def _round_and_chamfer(solid,p,pt,scale,ref):
        tolerance = max(scale*1.e-4,1.e-7)
        edges,radii = ISubEntityPtrArray(),DoubleArray()
        for start,end,radius in _blend_targets(p):
            edges.append(_edge_at(solid,pt(start),pt(end),tolerance))
            radii.append(radius*scale)
        _check(SolidUtil.Modify.BlendEdges(solid,edges,radii,False), "Outer R20 / inner R10")
        # 真正查询修改后的边，确认半径对应的切点，防止单位或目标棱选错。
        for start,end in _blend_tangent_edges(p):
            _edge_at(solid,pt(start),pt(end),tolerance)

        # Native chamfer trials only modify copies; preserve the rounded body
        # so a failed later corner can restart the complete cut consistently.
        rounded_body = solid

        w,t,h = p["width"],p["thickness"],p["height"]
        distance,angle = p["chamfer_distance"],p["chamfer_angle"]
        nose = p["flange_edge_thickness"]/2
        modes = ((SolidUtil.Modify.ChamferMode.eDistanceAngle,distance*scale,angle),
                 (SolidUtil.Modify.ChamferMode.eAngleDistance,angle,distance*scale))
        # 每次重新找边。内核的相邻面次序不保证左右对称，需验证距离落在 X。
        for z0,z1 in ((-t,0.),(h,h+t)):
            for sign in (-1.,1.):
                attempts = []
                accepted = None
                for mode,value1,value2 in modes:
                    status,trial = SolidUtil.CopyEntity(solid)
                    _check(status,"Copy body before chamfer")
                    if trial is None:
                        raise RuntimeError("CopyEntity returned empty body")
                    stage = "locate original end edge"
                    try:
                        selected = ISubEntityPtrArray()
                        selected.append(_edge_at(trial,pt((0.,sign*w/2,z0)),
                                                 pt((0.,sign*w/2,z1)),tolerance))
                        first,second = DoubleArray(),DoubleArray()
                        first.append(value1)
                        second.append(value2)
                        stage = "native chamfer operation"
                        _check(SolidUtil.Modify.ChamferEdges(
                            trial,selected,first,second,mode,False), "30-degree end chamfer")
                        # 长度 c 在板长方向，横向退让 b，前端实际保留宽度 F。
                        stage = "verify native chamfer endpoints"
                        for x,y in ((0.,sign*nose),(distance,sign*w/2)):
                            _edge_at(trial,pt((x,y,z0)),pt((x,y,z1)),tolerance)
                        accepted = trial
                        break
                    except RuntimeError as error:
                        attempts.append("%s: %s" % (stage,error))
                if accepted is None:
                    print("Native chamfer fallback (z=%g, side=%g): %s"
                          % (z0,sign," | ".join(attempts)))
                    return _planar_chamfer(rounded_body,p,pt,scale,ref)
                solid = accepted
        return solid


    def _build_support(origin, options=None):
        p = support_layout(options)
        ref = ISessionMgr.ActiveDgnModelRef
        if ref is None or origin is None:
            raise RuntimeError("An active model and sweep start point are required")
        model = ref.GetDgnModel()
        if not model.Is3d():
            raise RuntimeError("Please activate a 3D DGN model")
        scale = model.GetModelInfo().GetUorPerMeter()/1000.0
        if not math.isfinite(scale) or scale <= 0:
            raise RuntimeError("Invalid model units")
        angle = math.radians(p["heading_deg"])
        co, si = math.cos(angle), math.sin(angle)

        def pt(local):
            x,y,z = local
            return DPoint3d.From(origin.x+scale*(co*x-si*y),
                                origin.y+scale*(si*x+co*y), origin.z+scale*z)

        # 1. 真正的闭合矩形截面；只在内存创建，不写模型。
        points = DPoint3dArray()
        for local in p["profile"]:
            points.append(pt(local))
        profile = EditElementHandle()
        _check(ShapeHandler.CreateShapeElement(profile, None, points, True, ref),
               "Rectangle profile")
        profile_vector = ICurvePathQuery.ElementToCurveVector(profile)
        if profile_vector is None:
            raise RuntimeError("Cannot extract rectangle CurveVector")

        # 2. 三段线组成一条开放复合路径，不拆成三块板。
        path = EditElementHandle()
        _check(ChainHeaderHandler.CreateChainHeaderElement(path, None, False, True, ref),
               "Path header", allow_none=True)
        for start,end in zip(p["path"],p["path"][1:]):
            line = EditElementHandle()
            _check(LineHandler.CreateLineElement(
                line, None, DSegment3d(pt(start),pt(end)), True, ref), "Path segment")
            _check(ChainHeaderHandler.AddComponentElement(path,line),
                   "Add path segment", allow_none=True)
        _check(ChainHeaderHandler.AddComponentComplete(path),
               "Complete path", allow_none=True)
        path_vector = ICurvePathQuery.ElementToCurveVector(path)
        if path_vector is None:
            raise RuntimeError("Cannot extract sweep path CurveVector")

        # 3. 矩形上边中点作为路径起点，截面随路径转向，生成实体。
        try:
            result = SolidUtil.Create.BodyFromSweep(
                profile_vector, path_vector, ref, False, True, False)
        except TypeError:
            # 与目录已有 MSPy 脚本保持相同的扩展签名兼容方式。
            result = SolidUtil.Create.BodyFromSweep(
                profile_vector, path_vector, ref, False, True, False,
                DVec3d.From(0.,0.,0.), 0., 1., pt(p["path"][0]))
        if not isinstance(result,(tuple,list)) or len(result) < 2:
            raise RuntimeError("BodyFromSweep returned no status/body pair")
        _check(result[0], "Rectangle sweep along right-angle path")
        solid = result[1]
        if solid is None:
            raise RuntimeError("Rectangle sweep returned an empty body")

        # 4. 一根圆柱刀具，穿过上下两层板，保证两孔同轴。
        radius = p["hole_dia"]/2*scale
        primitive = ISolidPrimitive.CreateDgnCone(DgnConeDetail(
            pt(p["cutter_start"]), pt(p["cutter_end"]), radius, radius, True))
        cutter_element = EditElementHandle()
        _check(DraftingElementSchema.ToElement(cutter_element, primitive, None, model),
               "Hole cylinder")
        status,cutter = SolidUtil.Convert.ElementToBody(cutter_element, True, True, False)
        _check(status, "Hole cylinder body")
        if cutter is None:
            raise RuntimeError("Empty hole cutter")
        cutters = ISolidKernelEntityPtrArray()
        cutters.append(cutter)
        _check(SolidUtil.Modify.BooleanSubtract(solid,cutters), "Drill both plates")
        # 5. R20/R10 真圆角，再做30度端部倒角，仍然保持一件实体。
        solid = _round_and_chamfer(solid,p,pt,scale,ref)
        finished = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(finished,solid,profile,model),
               "Finished swept support")
        if not finished.IsValid():
            raise RuntimeError("Invalid finished support")
        props = ElementPropertiesSetter()
        props.SetColor(3)
        props.Apply(finished)

        # 一个普通单元里只有一个最终实体；截面、路径、刀具均不入模型。
        cell = EditElementHandle()
        _check(NormalCellHeaderHandler.CreateOrphanCellElement(
            cell,CELL_NAME,True,model), "Cell header", allow_none=True)
        if not cell.IsValid():
            raise RuntimeError("Invalid cell header")
        _check(NormalCellHeaderHandler.AddChildElement(cell,finished), "Cell solid")
        _check(NormalCellHeaderHandler.AddChildComplete(cell), "Complete cell")
        return cell


    def draw_pivot_support_sweep(placement_point, options=None):
        cell = _build_support(placement_point,options)
        _check(cell.AddToModel(), "AddToModel")
        return cell


    class PivotSupportSweepTool(DgnPrimitiveTool):
        def __init__(self):
            DgnPrimitiveTool.__init__(self,0,0)
            self.m_self = self
            self.preview = None

        def _GetToolName(self,name):
            return WString("PivotSupportSweepTool")

        def _OnPostInstall(self):
            DgnPrimitiveTool._OnPostInstall(self)
            AccuSnap.GetInstance().EnableSnap(True)
            NotificationManager.OutputPrompt(
                "Pick sweep START (rectangle upper-edge midpoint). Left: accept; right: cancel.")

        def _OnDataButton(self,event):
            if self.preview is not None:
                self.preview = None
                PyCommandState.StartDefaultCommand()
                return True
            try:
                self.preview = draw_pivot_support_sweep(event.GetPoint())
                NotificationManager.OutputPrompt("Swept support ready. Left: accept; right: cancel.")
            except Exception as error:
                traceback.print_exc()
                NotificationManager.OutputPrompt("Support sweep failed: %s" % error)
            return True

        def _discard(self):
            if self.preview is not None:
                _check(self.preview.DeleteFromModel(), "Delete preview", allow_none=True)
                self.preview = None

        def _OnResetButton(self,event):
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
        _ACTIVE_TOOL = PivotSupportSweepTool()
        _ACTIVE_TOOL.InstallTool()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        PyMain()
