# -*- coding: utf-8 -*-
'''
水箱爬梯建模基础库
后续爬梯的立柱、踏步、扶手等构件都在此库中逐步扩展
'''

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

import math
import os

DEBUG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_log.txt')


def _log(msg):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass


def get_uor_per_storage(dgnModel=None):
    if dgnModel is None:
        dgnModel = ISessionMgr.GetActiveDgnModel()
    return dgnModel.GetModelInfo().GetUorPerStorage()


def mm(value, dgnModel=None):
    return value * get_uor_per_storage(dgnModel)


def create_shape(points_mm, dgnModel=None, add2Model=True):
    if dgnModel is None:
        dgnModel = ISessionMgr.GetActiveDgnModel()
    pts = DPoint3dArray()
    for p in points_mm:
        pts.append(DPoint3d(mm(p[0], dgnModel), mm(p[1], dgnModel), mm(p[2], dgnModel)))
    eeh = EditElementHandle()
    if BentleyStatus.eSUCCESS != ShapeHandler.CreateShapeElement(eeh, None, pts, dgnModel.Is3d(), dgnModel):
        return None
    if add2Model:
        if BentleyStatus.eSUCCESS != eeh.AddToModel():
            return None
    return eeh


AXES = {
    'Z': ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    'X': ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    'Y': ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
}

SIGN = {'+': 1.0, '-': -1.0}


def create_angle_steel(width=50.0, thickness=5.0, height=600.0, origin=(0.0, 0.0, 0.0),
                       extrude='Z', legs='+X+Y'):
    '''
    绘制等边角钢实体
    width     : 边宽 (mm)
    thickness : 壁厚 (mm)
    height    : 拉伸长度 (mm)
    origin    : 角钢外角点位置 (mm)
    extrude   : 拉伸方向 'X' / 'Y' / 'Z'
    legs      : 两条腿的朝向，如 '+X+Y'、'-X+Y'、'+Y+Z'，均相对 origin 外角点
    '''
    dgnModel = ISessionMgr.GetActiveDgnModel()
    ox, oy, oz = origin
    ua, vb, ex = AXES[extrude]

    sa = SIGN[legs[0]]
    sb = SIGN[legs[2]]

    def vec(axis, sign, dist):
        return (axis[0] * sign * dist, axis[1] * sign * dist, axis[2] * sign * dist)

    o = (ox, oy, oz)
    p1 = (o[0] + vec(ua, sa, width)[0], o[1] + vec(ua, sa, width)[1], o[2] + vec(ua, sa, width)[2])
    p2 = (p1[0] + vec(vb, sb, thickness)[0], p1[1] + vec(vb, sb, thickness)[1], p1[2] + vec(vb, sb, thickness)[2])
    p3 = (o[0] + vec(ua, sa, thickness)[0] + vec(vb, sb, thickness)[0],
          o[1] + vec(ua, sa, thickness)[1] + vec(vb, sb, thickness)[1],
          o[2] + vec(ua, sa, thickness)[2] + vec(vb, sb, thickness)[2])
    p4 = (p3[0] + vec(vb, sb, width - thickness)[0], p3[1] + vec(vb, sb, width - thickness)[1], p3[2] + vec(vb, sb, width - thickness)[2])
    p5 = (o[0] + vec(vb, sb, width)[0], o[1] + vec(vb, sb, width)[1], o[2] + vec(vb, sb, width)[2])

    profile_pts = [o, p1, p2, p3, p4, p5]

    profile = create_shape(profile_pts, dgnModel, add2Model=True)
    if profile is None:
        return None

    body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if BentleyStatus.eERROR == body[0]:
        return None

    sweepDir = DVec3d(ex[0] * mm(height, dgnModel), ex[1] * mm(height, dgnModel), ex[2] * mm(height, dgnModel))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body[1], sweepDir):
        return None

    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(solid, body[1], profile, dgnModel):
        return None

    if BentleyStatus.eSUCCESS != solid.AddToModel():
        return None

    profile.DeleteFromModel()
    return solid


POST_FACE_SPACING = 420.0
DEFAULT_TANK_HEIGHT = 2000.0
LEG_HEIGHT_EXTRA = 480.0
LEG_VERTICAL_HEIGHT = DEFAULT_TANK_HEIGHT + LEG_HEIGHT_EXTRA

REINFORCEMENT_WIDTH = 60.0
REINFORCEMENT_THICKNESS = 10.0
REINFORCEMENT_LENGTH = 250.0
REINFORCEMENT_BOTTOM_CLEARANCE = 100.0
REINFORCEMENT_X_OFFSET = 10.0
REINFORCEMENT_VERTICAL_SPACING = 900.0

RUNG_DIAMETER = 18.0
RUNG_LENGTH = 430.0
RUNG_BOTTOM_CLEARANCE = 300.0
RUNG_VERTICAL_SPACING = 300.0


def get_leg_vertical_height(tank_height):
    '''根据用户输入的水箱高度计算梯腿竖向放样长度。'''
    if tank_height <= 0.0:
        raise ValueError('tank_height must be positive')
    return tank_height + LEG_HEIGHT_EXTRA


def create_line_element(point1_mm, point2_mm, dgnModel):
    eeh = EditElementHandle()
    p1 = DPoint3d(mm(point1_mm[0], dgnModel), mm(point1_mm[1], dgnModel), mm(point1_mm[2], dgnModel))
    p2 = DPoint3d(mm(point2_mm[0], dgnModel), mm(point2_mm[1], dgnModel), mm(point2_mm[2], dgnModel))
    if BentleyStatus.eSUCCESS != LineHandler.CreateLineElement(eeh, None, DSegment3d(p1, p2), dgnModel.Is3d(), dgnModel):
        return None
    return eeh


def create_arc_element(center_mm, radius_mm, rotation, startAngle, sweepAngle, dgnModel):
    eeh = EditElementHandle()
    center = DPoint3d(mm(center_mm[0], dgnModel), mm(center_mm[1], dgnModel), mm(center_mm[2], dgnModel))
    if BentleyStatus.eSUCCESS != ArcHandler.CreateArcElement(eeh, None, center, mm(radius_mm, dgnModel), mm(radius_mm, dgnModel),
                                                             rotation, startAngle, sweepAngle, dgnModel.Is3d(), dgnModel):
        return None
    return eeh


def create_chain(elements, dgnModel):
    chain = EditElementHandle()
    ComplexShapeHandler.CreateChainHeaderElement(chain, None, True, dgnModel.Is3d(), dgnModel)
    if not chain.IsValid():
        return None
    for eeh in elements:
        if eeh is None:
            return None
        if BentleyStatus.eSUCCESS != ComplexShapeHandler.AddComponentElement(chain, eeh):
            return None
    if BentleyStatus.eSUCCESS != chain.AddToModel():
        return None
    return chain


def create_flat_bar(width=60.0, thickness=10.0, length=250.0,
                    origin=(0.0, 0.0, 0.0), extrude='Y'):
    '''
    绘制矩形扁钢实体。

    origin  : 扁钢起始截面中心点 (mm)
    extrude : 长轴方向 'X' / 'Y' / 'Z'，length 为正时沿该轴正方向拉伸
    width   : 扁钢宽面尺寸。长轴为 Y 时，宽面沿 Z，厚度沿 X。
    '''
    if width <= 0.0 or thickness <= 0.0 or length <= 0.0:
        return None
    if extrude not in AXES:
        return None

    dgnModel = ISessionMgr.GetActiveDgnModel()
    ox, oy, oz = origin
    thickness_axis, width_axis, length_axis = AXES[extrude]

    def point(width_offset, thickness_offset):
        return (
            ox + width_axis[0] * width_offset + thickness_axis[0] * thickness_offset,
            oy + width_axis[1] * width_offset + thickness_axis[1] * thickness_offset,
            oz + width_axis[2] * width_offset + thickness_axis[2] * thickness_offset,
        )

    profile = create_shape([
        point(-width / 2.0, -thickness / 2.0),
        point(width / 2.0, -thickness / 2.0),
        point(width / 2.0, thickness / 2.0),
        point(-width / 2.0, thickness / 2.0),
    ], dgnModel, add2Model=True)
    if profile is None:
        return None

    body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if BentleyStatus.eSUCCESS != body[0]:
        profile.DeleteFromModel()
        return None

    sweep_dir = DVec3d(length_axis[0] * mm(length, dgnModel),
                        length_axis[1] * mm(length, dgnModel),
                        length_axis[2] * mm(length, dgnModel))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body[1], sweep_dir):
        profile.DeleteFromModel()
        return None

    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(solid, body[1], profile, dgnModel):
        profile.DeleteFromModel()
        return None
    if BentleyStatus.eSUCCESS != solid.AddToModel():
        profile.DeleteFromModel()
        return None

    profile.DeleteFromModel()
    return solid


def create_round_bar(diameter=18.0, length=430.0, center=(0.0, 0.0, 0.0),
                     extrude='X'):
    '''
    绘制圆钢实体。center 为圆钢中点，长轴为 extrude；圆钢从中点两侧等长延伸。
    '''
    if diameter <= 0.0 or length <= 0.0 or extrude not in AXES:
        return None

    dgnModel = ISessionMgr.GetActiveDgnModel()
    length_axis = AXES[extrude][2]
    cx, cy, cz = center

    def P(x, y, z):
        return DPoint3d(mm(x, dgnModel), mm(y, dgnModel), mm(z, dgnModel))

    start = (
        cx - length_axis[0] * length / 2.0,
        cy - length_axis[1] * length / 2.0,
        cz - length_axis[2] * length / 2.0,
    )
    end = (
        cx + length_axis[0] * length / 2.0,
        cy + length_axis[1] * length / 2.0,
        cz + length_axis[2] * length / 2.0,
    )

    normal = DVec3d(length_axis[0], length_axis[1], length_axis[2])
    circle = DEllipse3d.FromCenterNormalRadius(P(*start), normal, mm(diameter / 2.0, dgnModel))
    outer_profile = CurveVector.CreateDisk(circle, CurveVector.eBOUNDARY_TYPE_Outer)
    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
    profile.Add(outer_profile)

    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    path.Add(ICurvePrimitive.CreateLine(DSegment3d(P(*start), P(*end))))
    try:
        ret = SolidUtil.Create.BodyFromSweep(profile, path, dgnModel, False, True, False)
    except Exception as e:
        _log("round bar: BodyFromSweep exception: %r" % e)
        return None
    if ret is None or BentleyStatus.eSUCCESS != ret[0]:
        _log("round bar: BodyFromSweep status=%r" % (ret[0] if ret else None,))
        return None

    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(solid, ret[1], None, dgnModel):
        return None
    if BentleyStatus.eSUCCESS != solid.AddToModel():
        return None
    return solid


def union_solid_elements(elements):
    '''
    将已加入模型的一组实体逐个布尔相并，成功后删除原零件，只保留一个实体。
    所有零件必须实体相交或相接；相并失败时不删除任何原零件。
    '''
    solids = [element for element in elements if element is not None and element.IsValid()]
    if not solids:
        return None
    if len(solids) == 1:
        return solids[0]

    dgnModel = ISessionMgr.GetActiveDgnModel()
    target = SolidUtil.Convert.ElementToBody(solids[0], True, True, False)
    if target is None or BentleyStatus.eSUCCESS != target[0]:
        _log('union: failed to convert target element to body')
        return None

    union_functions = []
    for owner_name, owner in (
            ('SolidUtil.Modify', SolidUtil.Modify),
            ('SolidUtil', SolidUtil)):
        for function_name in ('BodyBooleanUnion', 'BooleanUnion'):
            function = getattr(owner, function_name, None)
            if function is not None:
                union_functions.append((owner_name + '.' + function_name, function))
    if not union_functions:
        available = [name for name in dir(SolidUtil.Modify)
                     if 'boolean' in name.lower() or 'union' in name.lower()]
        _log('union: no supported boolean-union API; Modify candidates=%r' % available)
        return None

    for index, tool_element in enumerate(solids[1:], start=2):
        tool = SolidUtil.Convert.ElementToBody(tool_element, True, True, False)
        if tool is None or BentleyStatus.eSUCCESS != tool[0]:
            _log('union: failed to convert element %d to body' % index)
            return None

        status = None
        last_error = None
        for function_name, union_function in union_functions:
            try:
                if function_name.endswith('.BooleanUnion'):
                    tools = ISolidKernelEntityPtrArray()
                    tools.append(tool[1])
                    status = union_function(target[1], tools)
                else:
                    status = union_function(target[1], tool[1])
                if isinstance(status, tuple):
                    status = status[0]
                if BentleyStatus.eSUCCESS == status:
                    break
                last_error = '%s returned %r' % (function_name, status)
            except Exception as e:
                last_error = '%s exception: %r' % (function_name, e)
        if BentleyStatus.eSUCCESS != status:
            _log('union: failed on element %d: %s' % (index, last_error))
            return None

    merged = EditElementHandle()
    try:
        status = SolidUtil.Convert.BodyToElement(merged, target[1], solids[0], dgnModel)
    except Exception as e:
        _log('union: BodyToElement exception: %r' % e)
        return None
    if BentleyStatus.eSUCCESS != status or BentleyStatus.eSUCCESS != merged.AddToModel():
        _log('union: failed to add merged element, status=%r' % (status,))
        return None

    for element in solids:
        try:
            element.DeleteFromModel()
        except Exception as e:
            _log('union: merged successfully, but failed to delete elementId=%d: %r' %
                 (element.GetElementId(), e))
    return merged


def _build_ladder_leg_curves(width, thickness, top_length, vertical_height, radius,
                             origin, dgnModel):
    '''
    建立梯腿扫掠所需的路径与截面，所有输入均为 mm。

    origin 是 310 mm 顶部短边的起点（即扫掠起点），也是扁钢截面的
    中心。路径从 origin 沿 -Y 方向行进，经过 90 度圆角后沿 -Z 方向落到
    竖边底端。
    '''
    if width <= 0.0 or thickness <= 0.0:
        _log("leg: width and thickness must be positive")
        return None
    # 曲线走扁钢截面中心。为使成品外侧总伸出量为 top_length，
    # 中心线在 -Y 方向的长度需扣除半个扁钢宽面。
    centerline_length = top_length - width / 2.0
    if radius <= 0.0 or centerline_length <= radius or vertical_height <= radius:
        _log("leg: require top_length - width/2 > radius > 0 and vertical_height > radius")
        return None

    ox, oy, oz = origin

    def P(x, y, z):
        return DPoint3d(mm(x, dgnModel), mm(y, dgnModel), mm(z, dgnModel))

    short_edge_end = (ox, oy - (centerline_length - radius), oz)
    arc_center = (ox, oy - (centerline_length - radius), oz - radius)
    vertical_start = (ox, oy - centerline_length, oz - radius)
    vertical_end = (ox, oy - centerline_length, oz - vertical_height)

    pathCV = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    pathCV.Add(ICurvePrimitive.CreateLine(DSegment3d(P(ox, oy, oz), P(*short_edge_end))))
    arc = DEllipse3d.FromArcCenterStartEnd(
        P(*arc_center), P(*short_edge_end), P(*vertical_start))
    pathCV.Add(ICurvePrimitive.CreateArc(arc))
    pathCV.Add(ICurvePrimitive.CreateLine(DSegment3d(P(*vertical_start), P(*vertical_end))))

    # BodyFromSweep 要求传入一个区域。单个外环也须置于 ParityRegion 中，
    # 而不是将 Outer 曲线直接作为 profile 参数。
    outerProfileCV = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    # 截面相对于扫掠曲线中心对称：60 mm 宽面沿 Z，10 mm 厚度沿 X。
    corners = [
        P(ox - thickness / 2.0, oy, oz - width / 2.0),
        P(ox + thickness / 2.0, oy, oz - width / 2.0),
        P(ox + thickness / 2.0, oy, oz + width / 2.0),
        P(ox - thickness / 2.0, oy, oz + width / 2.0),
    ]
    for i in range(4):
        outerProfileCV.Add(ICurvePrimitive.CreateLine(DSegment3d(corners[i], corners[(i + 1) % 4])))

    profileCV = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
    profileCV.Add(outerProfileCV)
    return pathCV, profileCV


def create_ladder_leg(width=60.0, thickness=10.0, top_length=340,
                      vertical_height=LEG_VERTICAL_HEIGHT, radius=150.0,
                      origin=None):
    '''
    绘制梯腿实体：60x10 扁钢沿倒 L 形路径扫掠。

    width           : 扁钢宽面宽度 (mm)，在路径起点沿 +Z 方向竖立
    thickness       : 扁钢厚度 (mm)，在路径起点沿 X 方向
    top_length      : 梯腿在 -Y 方向的成品外廓总长 (mm)，默认 310；
                      放样中心线自动扣除半个扁钢宽面
    vertical_height : 从短边起点到竖边底端的总高差 (mm)；默认 2480，
                      对应默认水箱高度 2000 + 480
    radius          : 短边与竖边交接处圆角半径 (mm)
    origin          : 顶部短边起点/扫掠起点 (mm)，也是 60x10 截面中心。
    '''
    dgnModel = ISessionMgr.GetActiveDgnModel()
    if origin is None:
        origin = (0.0, 0.0, 0.0)
    _log("leg: start, origin=%s" % (origin,))

    curves = _build_ladder_leg_curves(width, thickness, top_length, vertical_height,
                                      radius, origin, dgnModel)
    if curves is None:
        return None
    pathCV, profileCV = curves

    try:
        ret = SolidUtil.Create.BodyFromSweep(profileCV, pathCV, dgnModel, False, True, False)
    except Exception as e:
        _log("leg: BodyFromSweep exception: %r" % e)
        return None
    _log("leg: BodyFromSweep status=%r" % (ret[0] if ret else None,))
    if ret is None or BentleyStatus.eSUCCESS != ret[0]:
        return None

    solid = EditElementHandle()
    try:
        status = SolidUtil.Convert.BodyToElement(solid, ret[1], None, dgnModel)
    except Exception as e:
        _log("leg: BodyToElement exception: %r" % e)
        return None
    _log("leg: BodyToElement status=%r" % (status,))
    if BentleyStatus.eSUCCESS != status:
        return None

    status = solid.AddToModel()
    _log("leg: AddToModel status=%r" % (status,))
    if BentleyStatus.eSUCCESS != status:
        return None
    _log("leg: done, elementId=%d" % solid.GetElementId())
    return solid


def create_ladder_frame(width=50.0, thickness=5.0, height=600.0, spacing=POST_FACE_SPACING,
                        origin=(0.0, 0.0, 0.0)):
    '''
    绘制爬梯底部框架：两根立杆 + 底部加固角钢。
    origin 是底部横向角钢直角棱线的中点。
    width     : 角钢边宽 (mm)
    thickness : 角钢壁厚 (mm)
    height    : 立杆高度 (mm)
    spacing   : 两立杆最近面净距 (mm)，将来一键更改此变量即可
    origin    : 底部横向角钢直角棱线的中点 (mm)
    底部角钢 : 沿 X 方向，肢板朝 +Y、+Z；总长为 spacing + 2*width
    两根立杆 : 背面贴底部角钢的 y=0 面，均朝 -Y 开口；左、右立杆的另一肢板
               分别朝 -X、+X，形成相反开口方向。
    '''
    ox, oy, oz = origin
    half_spacing = spacing / 2.0
    bottom_length = spacing + 2.0 * width

    support_post = create_angle_steel(width, thickness, height,
                                      (ox - half_spacing, oy, oz), 'Z', '-X-Y')
    ladder_post = create_angle_steel(width, thickness, height,
                                     (ox + half_spacing, oy, oz), 'Z', '+X-Y')
    bottom = create_angle_steel(width, thickness, bottom_length,
                                (ox - bottom_length / 2.0, oy, oz), 'X', '+Y+Z')
    if ladder_post is None or support_post is None or bottom is None:
        return None
    return (ladder_post, support_post, bottom)


def create_ladder_leg_path(top_length=340, vertical_height=LEG_VERTICAL_HEIGHT,
                           radius=150.0, origin=None):
    '''
    绘制梯腿放样路径曲线（不拉伸）：倒 L 形，直线 + 圆弧 + 直线
    top_length      : 梯腿在 -Y 方向的成品外廓总长 310 (mm)
    vertical_height : 从短边起点到竖边底端的总高差 (mm)，默认 2480
    radius          : 交接处圆角半径 150 (mm)
    origin          : 顶部短边起点/路径起点 (mm)，曲线位于 XZ 平面 (y=0)
    '''
    dgnModel = ISessionMgr.GetActiveDgnModel()
    if origin is None:
        origin = (0.0, 0.0, 0.0)

    _log("leg path: start, origin=%s" % (origin,))

    curves = _build_ladder_leg_curves(60.0, 10.0, top_length, vertical_height,
                                      radius, origin, dgnModel)
    if curves is None:
        return None
    pathCV, _ = curves
    _log("leg path: curveVector built")

    eeh = EditElementHandle()
    try:
        status = DraftingElementSchema.ToElement(eeh, pathCV, None, dgnModel.Is3d(), dgnModel)
    except Exception as e:
        _log("leg path: ToElement exception: %r" % e)
        return None
    _log("leg path: ToElement status=%r" % (status,))
    if BentleyStatus.eSUCCESS != status:
        return None

    status = eeh.AddToModel()
    _log("leg path: AddToModel status=%r" % (status,))
    if BentleyStatus.eSUCCESS != status:
        return None
    _log("leg path: done, elementId=%d" % eeh.GetElementId())
    return eeh


def create_ladder_leg_reinforcement(width=REINFORCEMENT_WIDTH,
                                    thickness=REINFORCEMENT_THICKNESS,
                                    length=REINFORCEMENT_LENGTH,
                                    origin=(0.0, 0.0, 0.0)):
    '''
    绘制梯腿加固支撑：60x10 扁钢，长轴沿 +Y 方向，默认长度 250 mm。
    origin 为靠近梯腿一端的截面中心点。
    '''
    return create_flat_bar(width, thickness, length, origin, 'Y')


def create_ladder_rung(diameter=RUNG_DIAMETER, length=RUNG_LENGTH,
                       center=(0.0, 0.0, 0.0)):
    '''绘制一根梯步：φ18 圆钢，长轴沿 X，圆钢中点位于 Y 轴对称面。'''
    return create_round_bar(diameter, length, center, 'X')


def create_ladder_assembly(frame_width=50.0, frame_thickness=5.0, frame_height=600.0,
                           spacing=POST_FACE_SPACING, leg_width=60.0,
                           leg_thickness=10.0, top_length=340,
                           tank_height=DEFAULT_TANK_HEIGHT, radius=150.0, leg_drop=50.0,
                           reinforcement_spacing=REINFORCEMENT_VERTICAL_SPACING,
                           reinforcement_x_offset=REINFORCEMENT_X_OFFSET,
                           rung_diameter=RUNG_DIAMETER,
                           rung_bottom_clearance=RUNG_BOTTOM_CLEARANCE,
                           rung_spacing=RUNG_VERTICAL_SPACING,
                           mirror_about_y=True,
                           merge_components=True,
                           origin=(0.0, 0.0, 0.0)):
    '''
    绘制完整的爬梯框架与梯腿。梯腿贴合在右侧立杆 -Y 肢板的外侧面，
    即两根立杆之间一侧的直角边。梯腿起始截面的右上角与该肢板顶端
    外侧边的中点对齐后，整体再向下偏移 leg_drop（默认 50 mm）。

    tank_height 为用户输入的水箱高度；梯腿竖向长度自动计算为
    tank_height + 480 mm。加固支撑首根位于水箱底部上方 100 mm，
    从梯腿竖边沿 +Y 方向伸出 250 mm，并沿 +X 偏移 10 mm 贴边。
    支撑总数量为 floor((tank_height - 100) / reinforcement_spacing) + 1，
    默认每 900 mm 向上复制一根。mirror_about_y 为 True 时，梯腿和
    全部加固支撑均关于整体原点所在的 Y 轴平面镜像一份。

    梯步为 φ18 圆钢，长度自动取“爬梯宽度 + 10 mm”，长轴沿 X，圆钢中点位于 Y 轴对称面；
    首根中心距水箱底部 rung_bottom_clearance（默认 300 mm），每隔
    rung_spacing（默认 300 mm）向上复制，总数量为 floor(tank_height / rung_spacing)。
    merge_components 为 True 时，所有构件将布尔相并为一个整体实体。
    '''
    frame = create_ladder_frame(frame_width, frame_thickness, frame_height, spacing, origin)
    if frame is None:
        return None

    ox, oy, oz = origin
    ladder_post_x = ox + spacing / 2.0
    # 右侧立杆为 +X-Y 角钢：-Y 肢板顶端外侧边的中点。
    # 该边位于两根立杆之间的内侧位置。
    post_outer_edge_mid = (ladder_post_x,
                           oy - frame_width / 2.0,
                           oz + frame_height)

    # 梯腿起点截面的右上角为
    # (origin.x + leg_thickness / 2, origin.y, origin.z + leg_width / 2)。
    # 反算起点，令该角点与 post_outer_edge_mid 对齐后整体下移 leg_drop。
    leg_origin = (post_outer_edge_mid[0] - leg_thickness / 2.0,
                  post_outer_edge_mid[1],
                  post_outer_edge_mid[2] - leg_width / 2.0 - leg_drop)
    leg_vertical_height = get_leg_vertical_height(tank_height)
    leg = create_ladder_leg(leg_width, leg_thickness, top_length,
                            leg_vertical_height, radius, leg_origin)
    if leg is None:
        return None

    legs = [leg]
    mirrored_leg_origin = None
    if mirror_about_y:
        mirrored_leg_origin = (2.0 * ox - leg_origin[0],
                               leg_origin[1],
                               leg_origin[2])
        mirrored_leg = create_ladder_leg(leg_width, leg_thickness, top_length,
                                         leg_vertical_height, radius, mirrored_leg_origin)
        if mirrored_leg is None:
            return None
        legs.append(mirrored_leg)

    if reinforcement_spacing <= 0.0:
        return None

    # 首根支撑：水箱底部（origin.z - tank_height）上方 100 mm，
    # 起点沿 +X 偏移 10 mm 后贴住梯腿边，向 +Y 方向伸至水箱侧。
    leg_centerline_length = top_length - leg_width / 2.0
    reinforcement_count = max(0, int(
        (tank_height - REINFORCEMENT_BOTTOM_CLEARANCE) // reinforcement_spacing
    ) + 1)
    reinforcements = []
    for index in range(reinforcement_count):
        reinforcement_origin = (
            leg_origin[0] + reinforcement_x_offset,
            leg_origin[1] - leg_centerline_length,
            oz - tank_height + REINFORCEMENT_BOTTOM_CLEARANCE + index * reinforcement_spacing,
        )
        reinforcement = create_ladder_leg_reinforcement(origin=reinforcement_origin)
        if reinforcement is None:
            return None
        reinforcements.append(reinforcement)

        if mirror_about_y:
            mirrored_reinforcement_origin = (
                2.0 * ox - reinforcement_origin[0],
                reinforcement_origin[1],
                reinforcement_origin[2],
            )
            mirrored_reinforcement = create_ladder_leg_reinforcement(
                origin=mirrored_reinforcement_origin)
            if mirrored_reinforcement is None:
                return None
            reinforcements.append(mirrored_reinforcement)

    if rung_spacing <= 0.0:
        return None

    # 梯步长度随两立杆净距联动，两端各搭接 5 mm。
    rung_length = spacing + 10.0

    # 梯步从水箱底部上方 300 mm 起，每隔 300 mm 向上复制；最高不超过水箱顶。
    rung_count = int(tank_height // rung_spacing)
    rungs = []
    for index in range(rung_count):
        rung_center = (
            ox,
            leg_origin[1] - leg_centerline_length,
            oz - tank_height + rung_bottom_clearance + index * rung_spacing,
        )
        rung = create_ladder_rung(rung_diameter, rung_length, rung_center)
        if rung is None:
            return None
        rungs.append(rung)
    components = frame + tuple(legs) + tuple(reinforcements) + tuple(rungs)
    if not merge_components:
        return components
    return union_solid_elements(components)


ACTIVE_LADDER_PLACEMENT_TOOL = None


class LadderPlacementTool(DgnPrimitiveTool):
    '''在模型中单击一点，将该点作为整套爬梯的整体原点。'''

    def __init__(self, parameters):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.parameters = parameters
        self.m_self = self

    def _GetToolName(self, name):
        return WString('LadderPlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt('请在模型中单击爬梯整体原点。')

    def _OnDataButton(self, ev):
        dgnModel = ISessionMgr.GetActiveDgnModel()
        uor_per_mm = get_uor_per_storage(dgnModel)
        point = ev.GetPoint()
        origin = (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)

        element = create_ladder_assembly(origin=origin, **self.parameters)
        if element is None:
            MessageCenter.ShowErrorMessage('爬梯生成或相并失败，请查看 debug_log.txt。', '', False)
        else:
            MessageCenter.ShowInfoMessage('爬梯已在选定位置生成并相并为整体。', '', False)
        return True

    def _OnResetButton(self, ev):
        NotificationManager.OutputPrompt('已取消爬梯定位。')
        return True

    @staticmethod
    def InstallNewInstance(parameters):
        global ACTIVE_LADDER_PLACEMENT_TOOL
        ACTIVE_LADDER_PLACEMENT_TOOL = LadderPlacementTool(parameters)
        ACTIVE_LADDER_PLACEMENT_TOOL.InstallTool()


def show_ladder_dialog():
    '''显示参数输入界面；确认后在模型中点取整体原点。'''
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as e:
        _log('ui: tkinter unavailable: %r' % e)
        return None

    root = tk.Tk()
    root.title('水箱爬梯生成')
    root.resizable(False, False)

    form = ttk.Frame(root, padding=16)
    form.grid(row=0, column=0, sticky='nsew')

    values = {
        'tank_height': tk.StringVar(value=str(DEFAULT_TANK_HEIGHT)),
        'ladder_width': tk.StringVar(value=str(POST_FACE_SPACING)),
        'reinforcement_spacing': tk.StringVar(value=str(REINFORCEMENT_VERTICAL_SPACING)),
    }
    fields = [
        ('水箱高度', 'tank_height', 'mm'),
        ('爬梯宽度（两立杆净距）', 'ladder_width', 'mm'),
        ('加强撑间隙', 'reinforcement_spacing', 'mm'),
    ]
    for row, (label, key, unit) in enumerate(fields):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=5)
        ttk.Entry(form, textvariable=values[key], width=18).grid(
            row=row, column=1, sticky='ew', padx=(12, 6), pady=5)
        ttk.Label(form, text=unit).grid(row=row, column=2, sticky='w', pady=5)

    status_text = tk.StringVar(value='输入参数后，进入模型点取爬梯整体原点。')
    ttk.Label(form, textvariable=status_text, foreground='#505050').grid(
        row=len(fields), column=0, columnspan=3, sticky='w', pady=(10, 6))

    result = {'element': None}

    def generate():
        try:
            tank_height = float(values['tank_height'].get())
            ladder_width = float(values['ladder_width'].get())
            reinforcement_spacing = float(values['reinforcement_spacing'].get())
            if tank_height <= 0.0 or ladder_width <= 0.0 or reinforcement_spacing <= 0.0:
                raise ValueError('所有输入值必须大于 0')
        except ValueError as e:
            messagebox.showerror('输入有误', str(e), parent=root)
            return

        parameters = {
            'tank_height': tank_height,
            'spacing': ladder_width,
            'reinforcement_spacing': reinforcement_spacing,
            'merge_components': True,
        }
        root.destroy()
        LadderPlacementTool.InstallNewInstance(parameters)

    buttons = ttk.Frame(form)
    buttons.grid(row=len(fields) + 1, column=0, columnspan=3, sticky='e', pady=(8, 0))
    ttk.Button(buttons, text='取消', command=root.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text='下一步：点取原点', command=generate).grid(row=0, column=1)

    root.mainloop()
    return result['element']


if __name__ == "__main__":
    show_ladder_dialog()
