# -*- coding: utf-8 -*-
"""Bentley / OpenPlant Python 管理器中运行的独立管夹布尔剪切测试。

运行后点取管道中心，即生成一组；可连续点取，右键退出（保留已生成模型）。
固定管轴为全局 X，截面位于 YZ 平面。仅创建管夹，不依赖原插件。
外圆柱 - 内圆柱 = 圆环；圆环 - 45°矩形贯穿体 = 两片管夹。
两处分口各沿轴向均布耳板，组数可设置，首尾中心距管夹端部75mm。
耳板靠近切口的一面距对应承重板切口平面退后10mm。
底座含底板、两道横向弧顶支撑和中央纵向腹板；L>600时加一道中央横向支撑。
支撑通过圆柱布尔剪切形成弧顶，再与下半承重板布尔并；不创建焊缝外形。
每块耳板开一个直径22的通孔，同一分口两孔同轴，适配本次指定的M20螺栓。
C=35：在耳板厚度中面，以管夹外圆接触处沿管轴的切线为基准，向外量到孔心。
尺寸单位均为 mm。T3 是径向板厚，外径因此增加 2*T3。
"""

import math
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# 修改这里的参数后重新加载脚本。
PIPE_OD_MM = 273
INSULATION_MM = 80.0
T3_MM = 12.0
CLAMP_WIDTH_MM = 300.0   # L：管夹及底板沿管轴总长，至少300。
EAR_END_OFFSET_MM = 75.0  # 首尾耳板中心到管夹轴向端部的距离。
EAR_GROUP_COUNT = 0      # 0=自动（L<=600为2组，L>600为3组）；也可手动填2或3。
BASE_WIDTH_W_MM = 150.0
HEIGHT_H_MM = 200.0     # 裸管底部到底板底面。
BASE_T1_MM = 12.0       # 底板厚度，测试暂取12。
SUPPORT_T2_MM = 12.0    # 横向支撑和中央纵向腹板厚度。
SUPPORT_END_OFFSET_MM = 75.0  # 横向支撑中心距轴向端部，暂定。
SUPPORT_SIDE_INSET_MM = 10.0  # 横向支撑两侧距底板边缘。
SUPPORT_OVERLAP_MM = 1.0     # 布尔连接搭接量。
GAP_J_MM = 30.0
CUT_ANGLE_DEG = 45.0  # 截面上从 +Y 向 +Z 旋转。
CUT_EXTRA_LENGTH_MM = 20.0
THROUGH_MARGIN_MM = 5.0
EAR_WIDTH_MM = 60.0       # 沿管轴方向，居中于管夹宽度。
EAR_HEIGHT_MM = 60.0      # 沿切割矩形长边方向向外伸出，含根部搭接。
EAR_THICKNESS_MM = 20.0   # 沿切口法向。
EAR_SETBACK_MM = 10.0    # 耳板内侧面距承重板切口端面的退让距离。
EAR_ROOT_OVERLAP_MM = 1.0  # 保证根部与圆弧实体相交，供布尔并使用。
HOLE_CENTER_C_MM = 35.0  # 从外圆接触切线向外量，非从埋入管夹的耳板底边量。
BOLT_HOLE_DIAMETER_MM = 22.0
# 简化M20外观尺寸，不建螺纹、倒角；垫圈用平圆环表示。
BOLT_DIAMETER_MM = 20.0
HEX_ACROSS_FLATS_MM = 30.0
BOLT_HEAD_HEIGHT_MM = 13.0
NUT_HEIGHT_MM = 16.0
WASHER_OD_MM = 37.0
WASHER_THICKNESS_MM = 3.0
BOLT_TIP_EXTRA_MM = 4.0

_active_tool = None


def _check(status, operation):
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        code = int(status)
    except (TypeError, ValueError):
        raise RuntimeError('%s未返回有效状态码：%r' % (operation, status))
    if code != 0:
        raise RuntimeError('%s失败，状态：%s' % (operation, status))


def _subtract(target, cutter, label):
    cutters = ISolidKernelEntityPtrArray()
    cutters.append(cutter)
    _check(SolidUtil.Modify.BooleanSubtract(target, cutters), label)


def _cylinder(model, point, x0, x1, radius, uor):
    # 使用真正的圆柱曲面，不用多边形近似圆。
    return _cylinder_between(model, point(x0, 0, 0), point(x1, 0, 0), radius, uor)


def _cylinder_between(model, start, end, radius, uor):
    detail = DgnConeDetail(start, end, radius * uor, radius * uor, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    _check(DraftingElementSchema.ToElement(element, primitive, None, model),
           '创建圆柱')
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    _check(status, '圆柱转内核体')
    return body


def _ear_body(model, point, uor, a0, a1, b0, b1, width, center_x):
    """在切口坐标系中创建耳板：X 为轴向，a 为径向，b 为切口法向。"""
    angle = math.radians(CUT_ANGLE_DEG)
    c, s = math.cos(angle), math.sin(angle)
    points = DPoint3dArray()
    for a, b in ((a0, b0), (a1, b0), (a1, b1), (a0, b1)):
        points.append(point(center_x - width / 2.0, a * c - b * s, a * s + b * c))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建耳板截面')
    _check(profile.AddToModel(), '创建耳板临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '耳板截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除耳板临时截面')
    _check(SolidUtil.Modify.SweepBody(body, DVec3d(width * uor, 0, 0)),
           '拉伸耳板')
    return body


def _ear_bounds(inner_radius, outer_radius):
    """四块耳板的切口坐标范围；先验证根部不会穿入保温层。"""
    b_near = GAP_J_MM / 2.0 + EAR_SETBACK_MM
    b_far = b_near + EAR_THICKNESS_MM
    if b_far >= outer_radius:
        raise ValueError('耳板位置超出管夹外圆，请减小间隙、退让或耳板厚度。')
    a_root = math.sqrt(outer_radius ** 2 - b_far ** 2) - EAR_ROOT_OVERLAP_MM
    if a_root <= 0 or math.hypot(a_root, b_near) <= inner_radius:
        raise ValueError('耳板根部会穿入保温层，请调整耳板位置或搭接量。')
    if EAR_WIDTH_MM > CLAMP_WIDTH_MM:
        raise ValueError('本测试要求耳板轴向宽度不超过管夹宽度。')
    if a_root + EAR_HEIGHT_MM <= math.sqrt(outer_radius ** 2 - b_near ** 2):
        raise ValueError('耳板高度不足以伸出管夹外圆。')
    bounds = []
    for radial_side in (-1, 1):
        a0, a1 = sorted((radial_side * a_root,
                         radial_side * (a_root + EAR_HEIGHT_MM)))
        for plate_side in (-1, 1):
            b0, b1 = sorted((plate_side * b_near, plate_side * b_far))
            bounds.append((a0, a1, b0, b1))
    return bounds


def _ear_hole_center(a0, a1, b0, b1, outer_radius):
    """返回孔心的有符号a坐标；对称耳板取相同a，保证两孔同轴。"""
    b_mid = (b0 + b1) / 2.0
    contact_a = math.sqrt(outer_radius ** 2 - b_mid ** 2)
    side = 1.0 if a0 + a1 > 0 else -1.0
    hole_a = side * (contact_a + HOLE_CENTER_C_MM)
    radius = BOLT_HOLE_DIAMETER_MM / 2.0
    if EAR_WIDTH_MM / 2.0 <= radius or not (a0 < hole_a - radius and
                                                           hole_a + radius < a1):
        raise ValueError('孔超出耳板边界，请调整C、孔径或耳板尺寸。')
    # 孔底应高于整段耳板根部外圆，避免孔侵入管夹本体。
    nearest_b = min(abs(b0), abs(b1))
    surface_a = math.sqrt(outer_radius ** 2 - nearest_b ** 2)
    if abs(hole_a) - radius <= surface_a:
        raise ValueError('孔与管夹本体相交，请增大C或减小孔径。')
    return hole_a


def _weld_ears(ring, model, point, uor, bounds, hole_centers, center_x):
    angle = math.radians(CUT_ANGLE_DEG)
    c, s = math.cos(angle), math.sin(angle)
    for index, (a0, a1, b0, b1) in enumerate(bounds, 1):
        ear = _ear_body(model, point, uor, a0, a1, b0, b1, EAR_WIDTH_MM, center_x)
        a = hole_centers[index - 1]
        # 圆柱沿b方向贯穿20mm板厚，并在两面额外延伸，避免共面布尔失败。
        start_b, end_b = b0 - THROUGH_MARGIN_MM, b1 + THROUGH_MARGIN_MM
        start = point(center_x, a * c - start_b * s, a * s + start_b * c)
        end = point(center_x, a * c - end_b * s, a * s + end_b * c)
        bore = _cylinder_between(model, start, end, BOLT_HOLE_DIAMETER_MM / 2.0, uor)
        _subtract(ear, bore, '耳板%d开螺栓通孔' % index)
        parts = ISolidKernelEntityPtrArray()
        parts.append(ear)
        _check(SolidUtil.Modify.BooleanUnion(ring, parts),
               '耳板%d与承重板布尔并' % index)


def _rectangle_cutter(model, point, uor, outer_diameter):
    angle = math.radians(CUT_ANGLE_DEG)
    c, s = math.cos(angle), math.sin(angle)
    half_length = (outer_diameter + CUT_EXTRA_LENGTH_MM) / 2.0
    half_gap = GAP_J_MM / 2.0
    x0 = -CLAMP_WIDTH_MM / 2.0 - THROUGH_MARGIN_MM
    # a 沿矩形长边，b 沿其法向。J 是两条切口平行面之间的垂直距离。
    corners = [(-half_length, -half_gap), (half_length, -half_gap),
               (half_length, half_gap), (-half_length, half_gap)]
    points = DPoint3dArray()
    for a, b in corners:
        points.append(point(x0, a * c - b * s, a * s + b * c))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建45度矩形截面')
    _check(profile.AddToModel(), '创建临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '矩形截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除临时截面')
    distance = (CLAMP_WIDTH_MM + 2.0 * THROUGH_MARGIN_MM) * uor
    _check(SolidUtil.Modify.SweepBody(body, DVec3d(distance, 0, 0)),
           '拉伸矩形贯穿切割体')
    return body


def _support_layout(outer_radius):
    """在生成实体前校验底座净高、支撑数量及耳板排列。"""
    length = CLAMP_WIDTH_MM
    if length < 300.0:
        raise ValueError('管夹长度L必须至少300mm。')
    if EAR_GROUP_COUNT not in (0, 2, 3):
        raise ValueError('EAR_GROUP_COUNT只能取0（自动）、2或3。')
    count = EAR_GROUP_COUNT or (3 if length > 600.0 else 2)
    span = length - 2.0 * EAR_END_OFFSET_MM
    if EAR_END_OFFSET_MM < EAR_WIDTH_MM / 2.0 or span / (count - 1) <= EAR_WIDTH_MM:
        raise ValueError('耳板重叠或超出管夹端部，请增大L或调整端距及组数。')
    ear_x = [-span / 2.0 + i * span / (count - 1) for i in range(count)]
    offset = SUPPORT_END_OFFSET_MM
    if not SUPPORT_T2_MM / 2.0 < offset < length / 2.0 - SUPPORT_T2_MM:
        raise ValueError('横向支撑端距不合理。')
    support_x = [-length / 2.0 + offset, length / 2.0 - offset]
    if length > 600.0:
        support_x.insert(1, 0.0)
    bottom_z = -PIPE_OD_MM / 2.0 - HEIGHT_H_MM
    base_top_z = bottom_z + BASE_T1_MM
    if base_top_z >= -outer_radius:
        raise ValueError('H不足，底板与管夹相交或没有支撑净高。')
    if SUPPORT_OVERLAP_MM >= min(T3_MM, BASE_T1_MM):
        raise ValueError('搭接量必须小于承重板及底板厚度。')
    half_span = BASE_WIDTH_W_MM / 2.0 - SUPPORT_SIDE_INSET_MM
    trim_radius = outer_radius - SUPPORT_OVERLAP_MM
    if not SUPPORT_T2_MM / 2.0 < half_span < trim_radius:
        raise ValueError('横向支撑宽度不适合当前管夹直径。')
    # 顶面取弧顶两侧最高点，减去圆柱后仅剩下方支撑。
    top_z = -math.sqrt(trim_radius ** 2 - half_span ** 2)
    # 支撑毛坯不得到达上半承重板；保留原来的45度对开间隙。
    angle = math.radians(CUT_ANGLE_DEG)
    max_b = abs(math.sin(angle)) * half_span + math.cos(angle) * top_z
    if math.cos(angle) <= 0 or max_b >= GAP_J_MM / 2.0:
        raise ValueError('当前切口角度或支撑宽度会使支撑接触上半承重板。')
    return ear_x, support_x, bottom_z, base_top_z, half_span, top_z, trim_radius


def _box_body(model, point, uor, x0, x1, y0, y1, z0, z1):
    points = DPoint3dArray()
    for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
        points.append(point(x0, y, z))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建支撑板截面')
    _check(profile.AddToModel(), '创建支撑板临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '支撑板截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除支撑板临时截面')
    _check(SolidUtil.Modify.SweepBody(body, DVec3d((x1 - x0) * uor, 0, 0)),
           '拉伸支撑板')
    return body


def _union(target, body, label):
    parts = ISolidKernelEntityPtrArray()
    parts.append(body)
    _check(SolidUtil.Modify.BooleanUnion(target, parts), label)


def _build_support(ring, model, point, uor, layout, outer_radius):
    _, support_x, bottom, base_top, half_span, top, trim_radius = layout
    half_l = CLAMP_WIDTH_MM / 2.0
    half_w = BASE_WIDTH_W_MM / 2.0
    base = _box_body(model, point, uor, -half_l, half_l,
                     -half_w, half_w, bottom, base_top)
    half_t = SUPPORT_T2_MM / 2.0
    plates = [(x - half_t, x + half_t, -half_span, half_span) for x in support_x]
    # 俯视图中的中央纵向腹板，连接两端横向支撑。
    plates.append((support_x[0], support_x[-1], -half_t, half_t))
    for index, (x0, x1, y0, y1) in enumerate(plates, 1):
        plate = _box_body(model, point, uor, x0, x1, y0, y1,
                          base_top - SUPPORT_OVERLAP_MM, top)
        cutter = _cylinder(model, point, x0 - THROUGH_MARGIN_MM,
                           x1 + THROUGH_MARGIN_MM, trim_radius, uor)
        _subtract(plate, cutter, '支撑%d剪切贴合圆弧' % index)
        # 宽支撑边角可能到达对开切口，裁去该部分以免填补J间隙。
        max_b = max(-math.sin(math.radians(CUT_ANGLE_DEG)) * y +
                    math.cos(math.radians(CUT_ANGLE_DEG)) * top for y in (y0, y1))
        if max_b > -GAP_J_MM / 2.0:
            slit = _rectangle_cutter(model, point, uor, 2.0 * outer_radius)
            _subtract(plate, slit, '支撑%d避让管夹对开间隙' % index)
        _union(base, plate, '支撑%d连接底板' % index)
    _union(ring, base, '支腿与下半承重板连接')


def _hex_body(model, point, uor, center_x, a, b0, b1):
    """六角截面沿孔轴b拉伸，参数30为对边尺寸而非半径。"""
    angle = math.radians(CUT_ANGLE_DEG)
    c, s = math.cos(angle), math.sin(angle)
    radius = HEX_ACROSS_FLATS_MM / (2.0 * math.cos(math.pi / 6.0))
    points = DPoint3dArray()
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        x = center_x + radius * math.cos(theta)
        radial = a + radius * math.sin(theta)
        points.append(point(x, radial * c - b0 * s, radial * s + b0 * c))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建六角截面')
    _check(profile.AddToModel(), '创建六角临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '六角截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除六角临时截面')
    distance = (b1 - b0) * uor
    _check(SolidUtil.Modify.SweepBody(body, DVec3d(0, -s * distance, c * distance)),
           '拉伸六角头或螺母')
    return body


def _fastener_bodies(model, point, uor, center_x, a):
    """一套：贯穿两板的光杆、六角头、六角螺母、两只圆环垫圈。"""
    angle = math.radians(CUT_ANGLE_DEG)
    c, s = math.cos(angle), math.sin(angle)

    def cylinder(b0, b1, radius):
        start = point(center_x, a * c - b0 * s, a * s + b0 * c)
        end = point(center_x, a * c - b1 * s, a * s + b1 * c)
        return _cylinder_between(model, start, end, radius, uor)

    far = GAP_J_MM / 2.0 + EAR_SETBACK_MM + EAR_THICKNESS_MM
    seat = far + WASHER_THICKNESS_MM
    shank = cylinder(-seat, seat + NUT_HEIGHT_MM + BOLT_TIP_EXTRA_MM,
                     BOLT_DIAMETER_MM / 2.0)
    head = _hex_body(model, point, uor, center_x, a,
                     -seat - BOLT_HEAD_HEIGHT_MM, -seat)
    nut = _hex_body(model, point, uor, center_x, a, seat, seat + NUT_HEIGHT_MM)
    _subtract(nut, cylinder(seat - THROUGH_MARGIN_MM,
                            seat + NUT_HEIGHT_MM + THROUGH_MARGIN_MM,
                            BOLT_HOLE_DIAMETER_MM / 2.0), '螺母中心孔')
    bodies = [('M20螺杆', shank), ('六角螺栓头', head), ('六角螺母', nut)]
    for b0, b1 in ((-seat, -far), (far, seat)):
        washer = cylinder(b0, b1, WASHER_OD_MM / 2.0)
        _subtract(washer, cylinder(b0 - THROUGH_MARGIN_MM, b1 + THROUGH_MARGIN_MM,
                                   BOLT_HOLE_DIAMETER_MM / 2.0), '垫圈中心孔')
        bodies.append(('垫圈', washer))
    return bodies


def _assembly_element(model, bodies):
    """保持紧固件为独立实体，整组装入Cell后一次写入模型。"""
    cell = EditElementHandle()
    # 此API返回None，不是状态码；后续加入子元素、完成及写入均检查状态。
    NormalCellHeaderHandler.CreateOrphanCellElement(
        cell, 'CLAMP_CUT_TEST', True, model)
    for name, body in bodies:
        child = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(child, body, None, model), name + '转模型元素')
        _check(NormalCellHeaderHandler.AddChildElement(cell, child), name + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成管夹单元')
    _check(cell.AddToModel(), '写入管夹单元')
    return cell


def build_at_center(center):
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    values = (PIPE_OD_MM, INSULATION_MM, T3_MM, CLAMP_WIDTH_MM,
              GAP_J_MM, CUT_EXTRA_LENGTH_MM, THROUGH_MARGIN_MM,
              EAR_WIDTH_MM, EAR_HEIGHT_MM, EAR_THICKNESS_MM, EAR_ROOT_OVERLAP_MM,
              HOLE_CENTER_C_MM, BOLT_HOLE_DIAMETER_MM,
              EAR_END_OFFSET_MM, BASE_WIDTH_W_MM, HEIGHT_H_MM, BASE_T1_MM,
              SUPPORT_T2_MM, SUPPORT_END_OFFSET_MM, SUPPORT_SIDE_INSET_MM,
              SUPPORT_OVERLAP_MM, BOLT_DIAMETER_MM, HEX_ACROSS_FLATS_MM,
              BOLT_HEAD_HEIGHT_MM, NUT_HEIGHT_MM, WASHER_OD_MM,
              WASHER_THICKNESS_MM, BOLT_TIP_EXTRA_MM)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('尺寸参数必须是有限的正数。')
    if not math.isfinite(CUT_ANGLE_DEG):
        raise ValueError('切割角度必须是有限数值。')
    if not BOLT_DIAMETER_MM < BOLT_HOLE_DIAMETER_MM < min(WASHER_OD_MM, HEX_ACROSS_FLATS_MM):
        raise ValueError('螺杆、通孔、垫圈及螺母尺寸不匹配。')
    if not math.isfinite(EAR_SETBACK_MM) or EAR_SETBACK_MM < 0:
        raise ValueError('耳板退让距离必须是有限的非负数。')
    inner_radius = PIPE_OD_MM / 2.0 + INSULATION_MM
    outer_radius = inner_radius + T3_MM
    support_layout = _support_layout(outer_radius)
    if GAP_J_MM >= 2.0 * inner_radius:
        raise ValueError('J 必须小于管夹内径。')
    bounds = _ear_bounds(inner_radius, outer_radius)
    hole_centers = [_ear_hole_center(*bound, outer_radius) for bound in bounds]
    uor = model.GetModelInfo().GetUorPerMeter() / 1000.0

    def point(x, y, z):
        return DPoint3d(center.x + x * uor, center.y + y * uor,
                        center.z + z * uor)

    half_width = CLAMP_WIDTH_MM / 2.0
    ring = _cylinder(model, point, -half_width, half_width, outer_radius, uor)
    bore = _cylinder(model, point, -half_width - THROUGH_MARGIN_MM,
                     half_width + THROUGH_MARGIN_MM, inner_radius, uor)
    _subtract(ring, bore, '外圆柱减去管道及保温层圆柱')
    cutter = _rectangle_cutter(model, point, uor, 2.0 * outer_radius)
    _subtract(ring, cutter, '圆环减去45度矩形贯穿体')
    for center_x in support_layout[0]:
        _weld_ears(ring, model, point, uor, bounds, hole_centers, center_x)
    _build_support(ring, model, point, uor, support_layout, outer_radius)

    bodies = [('管夹和支腿', ring)]
    for center_x in support_layout[0]:
        # 每个轴向位置有两处分口，各穿一套紧固件。
        for a in (hole_centers[0], hole_centers[2]):
            bodies.extend(_fastener_bodies(model, point, uor, center_x, a))
    result = _assembly_element(model, bodies)
    group_count = len(support_layout[0])
    message = ('已生成剪切管夹：内径 %.1f，外径 %.1f，板厚 %.1f，'
               '轴向宽 %.1f，切口 J=%.1f，角度 %.1f°；'
               '耳板%d块 %.1f×%.1f×%.1f，端面退让 %.1f，耳板净距 %.1f；'
               '每板1孔，孔径 %.1f（M20），切线至孔心 C=%.1f。'
               % (2 * inner_radius, 2 * outer_radius, T3_MM,
                  CLAMP_WIDTH_MM, GAP_J_MM, CUT_ANGLE_DEG,
                  4 * group_count, EAR_WIDTH_MM, EAR_HEIGHT_MM, EAR_THICKNESS_MM,
                  EAR_SETBACK_MM, GAP_J_MM + 2.0 * EAR_SETBACK_MM,
                  BOLT_HOLE_DIAMETER_MM, HOLE_CENTER_C_MM))
    message += (' 底座W=%.1f，H=%.1f，T1=%.1f，T2=%.1f，横向支撑%d道；'
                '耳板轴向中心=%s，支撑轴向中心=%s（相对管夹中心）。'
                % (BASE_WIDTH_W_MM, HEIGHT_H_MM, BASE_T1_MM, SUPPORT_T2_MM,
                   len(support_layout[1]), support_layout[0], support_layout[1]))
    message += ' M20紧固件%d套（各含螺杆、六角头、螺母和两只垫圈）。' % (2 * group_count)
    print(message)
    NotificationManager.OutputPrompt(message + '继续点取中心，右键退出。')
    return result


class ClampCutTestTool(DgnPrimitiveTool):
    def __init__(self):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.m_self = self

    def _GetToolName(self, name):
        return WString('ClampBooleanCutTest')

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt(
            '管夹剪切测试：点取管道中心（轴向固定为全局X）；右键退出。')

    def _OnDataButton(self, event):
        try:
            build_at_center(event.GetPoint())
        except Exception as error:
            print(traceback.format_exc())
            NotificationManager.OutputPrompt('剪切测试失败：%s' % error)
        return True

    def _OnResetButton(self, event):
        PyCommandState.StartDefaultCommand()
        return True

    def _OnRestartTool(self):
        PyMain()


def PyMain():
    global _active_tool
    _active_tool = ClampCutTestTool()
    _active_tool.InstallTool()


if __name__ == '__main__':
    PyMain()
