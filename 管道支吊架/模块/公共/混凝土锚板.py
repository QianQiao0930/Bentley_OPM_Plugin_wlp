# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为建模库供其它支吊架插件 ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行；
# 对应的可运行放置工具是仓库顶层 ``管道支吊架/G2-[混凝土锚板（膨胀螺栓）].py``。
# =============================================================================
"""混凝土锚板 + 膨胀锚栓建模库（无界面，供其它插件调用）。

数据取自表 1（锚板子项 A~D）：

    子项  锚栓    L    h_ef  拉力  剪力   G    T    MIN.S  MIN.C  MIN.h
     A    M8     80    55     8     8    10   10     75     75     110
     B    M12   120    90    17    23    14   12    100    100     180
     C    M16   140   100    24    40    18   16    125    150     200
     D    M20   180   125    33    68    22   20    150    200     250

几何约定（局部坐标系，原点为**板背面中心**，即贴混凝土面的那一点）：

    +X = 混凝土外法向（锚栓轴线，指向空气侧，混凝土在 -X 一侧）
    +Y = 板面内水平方向（随 heading 绕 Z 旋转）
    +Z = 竖直向上

    * 锚板：正方形 (S+100)×(S+100)、厚 T，板占 x ∈ [0, T]；
      四个 φG 螺栓孔位于 x=0 平面上、间距 S×S、居中（每边 50 边距）。
    * 锚栓：沿 +X，总长 L 不变；螺杆外端**超出螺母外端面 ``BOLT_PROTRUSION``**
      （5 mm，露出的丝头）。因此有效埋深 = L − (板厚 T + 垫圈厚 + 螺母高
      + 5)，仍大于表中要求的最小埋深 h_ef。
    * 每根锚栓由四段**简单拉伸/圆柱**构成，不做布尔融合（允许实体重合）：
      埋入端膨胀套管、螺杆、垫圈、六角螺母（六边形拉伸）。外形可辨认即可。

主要接口::

    import 混凝土锚板 as anchor
    options = {'subtype': 'B', 'spacing': 120.0, 'heading_deg': 0.0}
    cell, result = anchor.draw_anchor_plate(placement_point, options)

``placement_point`` 为模型 UOR 坐标的 DPoint3d；其它尺寸参数一律按 mm。
"""

from __future__ import division

import math

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


CELL_NAME = 'CONCRETE_ANCHOR_PLATE'

# 锚板子项数据表。螺母 / 垫圈尺寸采用对应规格的标准值（近似），仅用于成形。
ANCHOR_TABLE = {
    'A': dict(bolt_dia=8.0, length=80.0, embedment=55.0, tension=8.0, shear=8.0,
              hole_dia=10.0, plate_t=10.0, min_spacing=75.0, min_c=75.0,
              min_h=110.0, nut_af=13.0, nut_h=6.5, washer_od=16.0,
              washer_t=1.6),
    'B': dict(bolt_dia=12.0, length=120.0, embedment=90.0, tension=17.0,
              shear=23.0, hole_dia=14.0, plate_t=12.0, min_spacing=100.0,
              min_c=100.0, min_h=180.0, nut_af=19.0, nut_h=10.0, washer_od=24.0,
              washer_t=2.5),
    'C': dict(bolt_dia=16.0, length=140.0, embedment=100.0, tension=24.0,
              shear=40.0, hole_dia=18.0, plate_t=16.0, min_spacing=125.0,
              min_c=150.0, min_h=200.0, nut_af=24.0, nut_h=13.0, washer_od=30.0,
              washer_t=3.0),
    'D': dict(bolt_dia=20.0, length=180.0, embedment=125.0, tension=33.0,
              shear=68.0, hole_dia=22.0, plate_t=20.0, min_spacing=150.0,
              min_c=200.0, min_h=250.0, nut_af=30.0, nut_h=16.0, washer_od=37.0,
              washer_t=3.0),
}

# 板边距：锚板 = (S + 2×PLATE_MARGIN) 见详图 "(S+100)×(S+100)"。
PLATE_MARGIN = 50.0
# 膨胀套管外径系数与占埋深比例。
SLEEVE_DIA_FACTOR = 1.7
SLEEVE_EMBED_FRACTION = 0.55

# 螺杆外端超出螺母外端面的长度（mm）：露出的丝头，总长 L 不变。
BOLT_PROTRUSION = 5.0

COLOR_PLATE = 3
COLOR_BOLT = 7
COLOR_NUT = 2
COLOR_SLEEVE = 4

DEFAULT_OPTIONS = {
    'subtype': 'A',       # A / B / C / D
    'spacing': None,      # 螺栓间距 S（mm）；None 取该子项 MIN.S
    'heading_deg': 0.0,   # 朝向：墙面为绕 Z 的方位角，楼板为绕竖轴的转角
    'mount': 'wall',      # 安装面：wall（竖直墙面）/ floor（楼板顶）/ ceiling（楼板底）
}

# 安装面选项：渲染面板与校验共用。'wall' 为原有行为（锚栓沿水平方向）。
MOUNT_OPTIONS = (
    ('wall', '竖直墙面（螺栓水平）'),
    ('floor', '水平楼板顶面（螺栓朝下）'),
    ('ceiling', '水平楼板底面（螺栓朝上）'),
)
MOUNT_KEYS = tuple(key for key, _label in MOUNT_OPTIONS)

# 切割刀具体伸出锚板两侧的余量（mm），避免共面。
CUTTER_EXTENSION = 2.0


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _succeeded(status):
    """Bentley 状态码为 0 表示成功；兼容不导出 BentleyStatus 的版本。"""
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _apply_color(element, color):
    if element is None or color is None:
        return element
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)
    return element


class _PlateFrame(object):
    """局部坐标（mm）-> 世界坐标（UOR）的映射。

    局部 +X 始终是混凝土外法向（锚栓露出的那一侧）：

    * ``wall``    竖直面：+X 在水平面内，朝向角绕 Z 旋转（原有行为）；
    * ``floor``   水平楼板顶面：+X = 世界 +Z，锚板水平、螺栓向下插入楼板；
    * ``ceiling`` 水平楼板底面：+X = 世界 -Z，锚板水平、螺栓向上。

    朝向角在各自平面内绕外法向旋转锚板。
    """

    def __init__(self, origin, uor_per_mm, heading_deg, mount='wall'):
        self.origin = DPoint3d.From(origin.x, origin.y, origin.z)
        self.uor = uor_per_mm
        angle = math.radians(heading_deg)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        if mount == 'floor':
            self.axis_x = (0.0, 0.0, 1.0)
            self.axis_y = (cos_a, sin_a, 0.0)
            self.axis_z = (-sin_a, cos_a, 0.0)
        elif mount == 'ceiling':
            self.axis_x = (0.0, 0.0, -1.0)
            self.axis_y = (cos_a, sin_a, 0.0)
            self.axis_z = (sin_a, -cos_a, 0.0)
        else:  # wall
            self.axis_x = (cos_a, sin_a, 0.0)
            self.axis_y = (-sin_a, cos_a, 0.0)
            self.axis_z = (0.0, 0.0, 1.0)

    def point(self, x, y, z):
        world_x = (x * self.axis_x[0] + y * self.axis_y[0]
                   + z * self.axis_z[0])
        world_y = (x * self.axis_x[1] + y * self.axis_y[1]
                   + z * self.axis_z[1])
        world_z = (x * self.axis_x[2] + y * self.axis_y[2]
                   + z * self.axis_z[2])
        return DPoint3d.From(self.origin.x + self.uor * world_x,
                             self.origin.y + self.uor * world_y,
                             self.origin.z + self.uor * world_z)

    def uor_of(self, value_mm):
        return value_mm * self.uor


# ---------------------------------------------------------------------------
# 实体构件（全部为最简单的拉伸 / 圆柱）
# ---------------------------------------------------------------------------


def _cylinder_element(dgn_model, start, end, radius):
    detail = DgnConeDetail(start, end, radius, radius, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if not _succeeded(
            DraftingElementSchema.ToElement(element, primitive, None, dgn_model)):
        return None
    return element


def _cylinder_body(dgn_model, start, end, radius):
    element = _cylinder_element(dgn_model, start, end, radius)
    if element is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if not _succeeded(status):
        return None
    return body


def _element_from_body(dgn_model, body, template, color):
    finished = EditElementHandle()
    if not _succeeded(
            SolidUtil.Convert.BodyToElement(finished, body, template, dgn_model)):
        return None
    return _apply_color(finished, color)


def _subtract(body, cutters):
    for cutter in cutters:
        if cutter is None:
            continue
        tools = ISolidKernelEntityPtrArray()
        tools.append(cutter)
        SolidUtil.Modify.BooleanSubtract(body, tools)


def _cylinder(dgn_model, start, end, radius, color):
    """实心圆柱：最简单的一种拉伸。"""
    outer = _cylinder_element(dgn_model, start, end, radius)
    if outer is None:
        return None
    status, body = SolidUtil.Convert.ElementToBody(outer, True, True, False)
    if not _succeeded(status):
        return None
    return _element_from_body(dgn_model, body, outer, color)


def _prism_with_holes(dgn_model, corners, thickness, color, holes=()):
    """平面闭合轮廓沿法向拉伸成实体，再一次减掉全部圆柱孔。

    corners 按右手法则逆时针给出（决定拉伸方向）；thickness 为 UOR。
    holes 为 (start, end, radius) 元组，均为 UOR。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    profile = EditElementHandle()
    if not _succeeded(ShapeHandler.CreateShapeElement(
            profile, None, corners, model_ref.Is3d(), model_ref)):
        return None
    status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if not _succeeded(status):
        return None
    if not _succeeded(SolidUtil.Modify.ThickenSheet(body, thickness, 0.0)):
        return None
    _subtract(body, [_cylinder_body(dgn_model, s, e, r) for s, e, r in holes])
    return _element_from_body(dgn_model, body, profile, color)


def _hex_prism(dgn_model, frame, y, z, x_back, height, across_flats, color):
    """正六边形拉伸（螺母外形）。x_back 为螺母内端面局部 X。"""
    radius = across_flats / math.sqrt(3.0)
    corners = DPoint3dArray()
    for index in range(6):
        angle = math.radians(60.0 * index)
        corners.append(frame.point(x_back,
                                   y + radius * math.cos(angle),
                                   z + radius * math.sin(angle)))
    return _prism_with_holes(dgn_model, corners, frame.uor_of(height), color)


# ---------------------------------------------------------------------------
# 单元装配
# ---------------------------------------------------------------------------


class _AnchorPlateCellBuilder(object):
    """收集锚板子元素，全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model, cell_name=CELL_NAME):
        self.dgn_model = dgn_model
        self.cell_name = cell_name
        self.cell = EditElementHandle()
        self.child_count = 0
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('锚板子元素创建失败。')
        if not _succeeded(
                NormalCellHeaderHandler.AddChildElement(self.cell, child)):
            raise RuntimeError('无法将锚板子元素加入普通单元。')
        self.child_count += 1

    def build(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError('无法完成锚板普通单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法将锚板单元写入活动模型。')
        return self.cell


def _add_plate(builder, frame, dgn_model, resolved):
    """正方形锚板 (S+100)×(S+100)×T，一次拉伸 + 四个螺栓孔。"""
    half = resolved['plate_side'] / 2.0
    thickness = resolved['plate_t']
    corners = DPoint3dArray()
    # (y, z) 逆时针 -> 法向 +X，沿 +X 拉伸到 x ∈ [0, T]。
    for y, z in ((-half, -half), (half, -half), (half, half), (-half, half)):
        corners.append(frame.point(0.0, y, z))

    hole_r = frame.uor_of(resolved['hole_dia'] / 2.0)
    hole_half = resolved['spacing'] / 2.0
    holes = []
    for y in (-hole_half, hole_half):
        for z in (-hole_half, hole_half):
            holes.append((frame.point(-CUTTER_EXTENSION, y, z),
                          frame.point(thickness + CUTTER_EXTENSION, y, z),
                          hole_r))
    builder.add(_prism_with_holes(
        dgn_model, corners, frame.uor_of(thickness), COLOR_PLATE, holes))


def _add_bolt(builder, frame, dgn_model, resolved, y, z):
    """一根膨胀锚栓：套管 + 螺杆 + 垫圈 + 六角螺母。"""
    embed = resolved['embedment_actual']
    out_len = resolved['bolt_out_len']
    plate_t = resolved['plate_t']
    bolt_r = frame.uor_of(resolved['bolt_dia'] / 2.0)

    # 埋入端膨胀套管（比螺杆略粗，端部一段）
    builder.add(_cylinder(
        dgn_model,
        frame.point(-embed, y, z),
        frame.point(-embed + resolved['sleeve_len'], y, z),
        frame.uor_of(resolved['sleeve_dia'] / 2.0), COLOR_SLEEVE))

    # 螺杆：从埋入端一直伸到外端（外端超出螺母 BOLT_PROTRUSION）
    builder.add(_cylinder(
        dgn_model,
        frame.point(-embed, y, z),
        frame.point(out_len, y, z),
        bolt_r, COLOR_BOLT))

    # 垫圈：紧贴板正面
    builder.add(_cylinder(
        dgn_model,
        frame.point(plate_t, y, z),
        frame.point(plate_t + resolved['washer_t'], y, z),
        frame.uor_of(resolved['washer_od'] / 2.0), COLOR_BOLT))

    # 六角螺母：垫圈外侧；螺杆再向外露出 BOLT_PROTRUSION
    builder.add(_hex_prism(
        dgn_model, frame, y, z, plate_t + resolved['washer_t'],
        resolved['nut_h'], resolved['nut_af'], COLOR_NUT))


def _add_bolts(builder, frame, dgn_model, resolved):
    half = resolved['spacing'] / 2.0
    for y in (-half, half):
        for z in (-half, half):
            _add_bolt(builder, frame, dgn_model, resolved, y, z)


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


def resolve_options(options=None):
    """合并默认值、校验选项，并算出本次生成用的全部毫米尺寸。"""
    resolved = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(resolved)
        if unknown:
            raise ValueError('未知选项：%s' % '、'.join(sorted(unknown)))
        resolved.update(options)

    subtype = resolved['subtype']
    if subtype not in ANCHOR_TABLE:
        raise ValueError('子项只支持 %s。' % '、'.join(sorted(ANCHOR_TABLE)))
    table = ANCHOR_TABLE[subtype]

    if resolved['spacing'] is None:
        spacing = table['min_spacing']
    else:
        try:
            spacing = float(resolved['spacing'])
        except (TypeError, ValueError):
            raise ValueError('螺栓间距 S 必须是数字（mm）。')
        if not math.isfinite(spacing) or spacing <= 0.0:
            raise ValueError('螺栓间距 S 必须是正数（mm）。')
        if spacing < table['min_spacing']:
            raise ValueError('螺栓间距 S=%.0f mm 小于 MIN.S=%.0f mm。'
                             % (spacing, table['min_spacing']))

    try:
        heading = float(resolved['heading_deg'])
    except (TypeError, ValueError):
        raise ValueError('朝向必须是数字（度）。')
    if not math.isfinite(heading):
        raise ValueError('朝向必须是有限数字。')

    mount = resolved.get('mount') or 'wall'
    if mount not in MOUNT_KEYS:
        raise ValueError('安装面只支持：%s。' % '、'.join(MOUNT_KEYS))

    # 螺杆外端 = 螺母外端面 + 露出的丝头；总长 L 不变，多出的部分全部埋入。
    nut_outer = table['plate_t'] + table['washer_t'] + table['nut_h']
    out_len = nut_outer + BOLT_PROTRUSION
    embed_actual = table['length'] - out_len
    if embed_actual < table['embedment']:
        raise RuntimeError(
            'M%.0f 锚栓有效埋深 %.1f mm 小于要求的 %.1f mm，请核对数据表。'
            % (table['bolt_dia'], embed_actual, table['embedment']))

    return {
        'subtype': subtype,
        'heading_deg': heading,
        'mount': mount,
        'spacing': spacing,
        'plate_side': spacing + 2.0 * PLATE_MARGIN,
        'plate_t': table['plate_t'],
        'hole_dia': table['hole_dia'],
        'bolt_dia': table['bolt_dia'],
        'bolt_length': table['length'],
        'bolt_out_len': out_len,
        'embedment_req': table['embedment'],
        'embedment_actual': embed_actual,
        'sleeve_dia': table['bolt_dia'] * SLEEVE_DIA_FACTOR,
        'sleeve_len': embed_actual * SLEEVE_EMBED_FRACTION,
        'nut_af': table['nut_af'],
        'nut_h': table['nut_h'],
        'washer_od': table['washer_od'],
        'washer_t': table['washer_t'],
        'min_c': table['min_c'],
        'min_h': table['min_h'],
        'tension': table['tension'],
        'shear': table['shear'],
    }


def describe_spec(options=None):
    """面板信息行用的规格说明。"""
    if isinstance(options, dict) and 'plate_side' in options:
        resolved = options
    else:
        resolved = resolve_options(options)
    return ('%s 子项：锚板 %.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f）；'
            'M%.0f×%.0f 膨胀锚栓 ×4，有效埋深 %.0f（≥%.0f）；'
            '混凝土边缘 MIN.C=%.0f、MIN.h=%.0f。'
            % (resolved['subtype'], resolved['plate_side'],
               resolved['plate_side'], resolved['plate_t'],
               resolved['hole_dia'], resolved['spacing'],
               resolved['bolt_dia'], resolved['bolt_length'],
               resolved['embedment_actual'], resolved['embedment_req'],
               resolved['min_c'], resolved['min_h']))


# ---------------------------------------------------------------------------
# 对外建模接口
# ---------------------------------------------------------------------------


def build_anchor_plate_cell(placement_point, options=None):
    """构建锚板单元但**不写入模型**，返回 (builder, 统计字典)。

    placement_point 为板背面中心（贴混凝土面）的模型 UOR 坐标。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('请先打开并激活一个 DGN 模型。')
    dgn_model = model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')
    if placement_point is None:
        raise ValueError('请先在模型中点取混凝土表面上的放置点。')

    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    resolved = resolve_options(options)
    frame = _PlateFrame(placement_point, uor_per_mm, resolved['heading_deg'],
                        resolved['mount'])

    builder = _AnchorPlateCellBuilder(dgn_model, CELL_NAME)
    _add_plate(builder, frame, dgn_model, resolved)
    _add_bolts(builder, frame, dgn_model, resolved)
    builder.build()

    result = dict(resolved)
    result['child_count'] = builder.child_count
    result['bolt_count'] = 4
    result['cell_name'] = CELL_NAME
    return builder, result


def draw_anchor_plate(placement_point, options=None):
    """创建整组锚板单元并写入活动模型，返回 (cell, 统计字典)。"""
    builder, result = build_anchor_plate_cell(placement_point, options)
    cell = builder.commit()
    return cell, result


def _delete_element(handle):
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def replace_anchor_plate(placement_point, options, previous_handle):
    """重建锚板：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = build_anchor_plate_cell(placement_point, options)
    new_handle = builder.commit()
    deleted = _delete_element(previous_handle)
    return new_handle, result, deleted
