# -*- coding: utf-8 -*-
"""安保围栏大门插件的几何自检。

用桩件模拟 MSPy API，因此**不需要 MicroStation**，任何 Python 3（Tk 可用）都能直接运行：

    python _geometry_selftest.py

覆盖：门柱与门扇定位、45° 斜接切平面、悬臂与刺钢丝位置、菱形网裁剪、
单位换算（毫米 / 英尺主单位）、选项开关、布尔失败降级、参数校验、面板选项解析。
改动 security_fence_gate.py 后建议重跑一遍：全部通过时输出 ALL CHECKS PASSED
并以 0 退出，否则列出失败项并以 1 退出。
"""

import importlib.util
import math
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'security_fence_gate.py')

FAILURES = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    if not condition:
        FAILURES.append(name)
    print('[%s] %s %s' % (status, name, detail))


# --------------------------------------------------------------------------
# MSPy 桩件
# --------------------------------------------------------------------------
BentleyStatus = types.SimpleNamespace(eSUCCESS=0, eERROR=1, eWARN=2)
CREATED = []


class _Any(object):
    def __call__(self, *args, **kwargs):
        return _Any()

    def __getattr__(self, name):
        return _Any()

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


class DPoint3d(object):
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)

    @classmethod
    def From(cls, x, y, z):
        return cls(x, y, z)

    def __repr__(self):
        return 'P(%.4f, %.4f, %.4f)' % (self.x, self.y, self.z)


class DVec3d(DPoint3d):
    pass


class DPoint3dArray(list):
    def append(self, item):
        list.append(self, item)


class DSegment3d(object):
    def __init__(self, start, end):
        self.StartPoint, self.EndPoint = start, end


class DgnConeDetail(object):
    def __init__(self, start, end, r1, r2, capped):
        self.start, self.end, self.radius, self.capped = start, end, r1, capped


class DgnTorusPipeDetail(object):
    def __init__(self, center, vx, vy, major, minor, sweep, capped):
        self.center, self.vector_x, self.vector_y = center, vx, vy
        self.major, self.minor, self.sweep, self.capped = major, minor, sweep, capped


class EditElementHandle(object):
    def __init__(self):
        self.kind = None
        self.color = None
        self.children = []
        self.data = None
        self.is_final = False
        self.added_to_model = False
        self.deleted = False
        CREATED.append(self)

    def AddToModel(self):
        self.added_to_model = True
        return BentleyStatus.eSUCCESS

    def IsValid(self):
        return not self.deleted

    def DeleteFromModel(self):
        self.deleted = True
        return BentleyStatus.eSUCCESS


class ElementPropertiesSetter(object):
    def __init__(self):
        self.color = None
        self.weight = None

    def SetColor(self, color):
        self.color = color

    def SetWeight(self, weight):
        self.weight = weight

    def Apply(self, element):
        element.color = self.color
        element.weight = self.weight


class _ModelInfo(object):
    def __init__(self, uor_per_meter):
        self.uor_per_meter = uor_per_meter

    def GetUorPerMeter(self):
        return self.uor_per_meter


class _DgnModel(object):
    def __init__(self, uor_per_meter=1000.0, is_3d=True):
        self.info = _ModelInfo(uor_per_meter)
        self.is_3d = is_3d

    def Is3d(self):
        return self.is_3d

    def GetModelInfo(self):
        return self.info


class _ModelRef(object):
    def __init__(self, model):
        self.model = model

    def GetDgnModel(self):
        return self.model

    def Is3d(self):
        return self.model.Is3d()


class ISessionMgr(object):
    ActiveDgnModelRef = _ModelRef(_DgnModel())


class _Body(object):
    def __init__(self, element):
        self.element = element
        self.ops = []


class _SolidConvert(object):
    @staticmethod
    def ElementToBody(element, *args):
        return BentleyStatus.eSUCCESS, _Body(element)

    @staticmethod
    def BodyToElement(handle, body, template, model):
        handle.kind = template.kind
        handle.data = template.data
        handle.color = template.color
        handle.is_final = True
        handle.body_ops = list(body.ops)
        return BentleyStatus.eSUCCESS


class _SolidModify(object):
    @staticmethod
    def BooleanSubtract(body, tools):
        for tool in tools:
            tool.element.is_cutter = True
        tool_kinds = [tool.element.kind for tool in tools]
        if _SolidModify.fail_mitre and 'shape' in tool_kinds:
            # 模拟斜接切刀布尔运算失败（内圈掏空不受影响）。
            return BentleyStatus.eERROR
        if _SolidModify.fail_next:
            _SolidModify.fail_next = False
            return BentleyStatus.eERROR
        body.ops.append(('subtract', [tool.element for tool in tools]))
        return BentleyStatus.eSUCCESS

    @staticmethod
    def ThickenSheet(body, distance, chain):
        body.ops.append(('thicken', distance))
        return BentleyStatus.eSUCCESS

    fail_next = False
    fail_mitre = False


class SolidUtil(object):
    Convert = _SolidConvert
    Modify = _SolidModify


class ISolidKernelEntityPtrArray(list):
    pass


class _ShapeHandler(object):
    @staticmethod
    def CreateShapeElement(handle, template, points, is_3d, model):
        handle.kind = 'shape'
        handle.data = list(points)
        return BentleyStatus.eSUCCESS


class _LineHandler(object):
    @staticmethod
    def CreateLineElement(handle, template, segment, is_3d, model):
        handle.kind = 'line'
        handle.data = (segment.StartPoint, segment.EndPoint)
        handle.is_final = True
        return BentleyStatus.eSUCCESS


class _Primitive(object):
    @staticmethod
    def CreateDgnCone(detail):
        return {'type': 'cone', 'detail': detail}

    @staticmethod
    def CreateDgnTorusPipe(detail):
        return {'type': 'torus', 'detail': detail}


class _DraftingElementSchema(object):
    @staticmethod
    def ToElement(handle, primitive, template, model):
        handle.kind = primitive['type']
        handle.data = primitive['detail']
        return BentleyStatus.eSUCCESS


class _CellHandler(object):
    @staticmethod
    def CreateOrphanCellElement(cell, name, is_3d, model):
        cell.kind = 'cell'
        cell.data = name

    @staticmethod
    def AddChildElement(cell, child):
        cell.children.append(child)
        return BentleyStatus.eSUCCESS

    @staticmethod
    def AddChildComplete(cell):
        return BentleyStatus.eSUCCESS


class DgnPrimitiveTool(object):
    def __init__(self, tool_id=0, arg=0):
        self.tool_id = tool_id

    def InstallTool(self):
        return BentleyStatus.eSUCCESS

    def _OnPostInstall(self):
        pass


def _install_stub_modules():
    def make(name, attributes):
        module = types.ModuleType(name)
        # 只导出本模块显式提供的名字：几个 MSPy 桩件都会参与 import *，
        # 若共用一份全量名字表，后导入的模块会把前面已就位的桩件覆盖成 _Any。
        module.__all__ = sorted(attributes)
        for key, value in attributes.items():
            setattr(module, key, value)
        sys.modules[name] = module
        return module

    runtime = {'AccuSnap': _Any(), 'PyCadInputQueue': _Any(),
               'PyCommandState': _Any(), 'NotificationManager': _Any(),
               'MessageCenter': _Any()}
    common = {'BentleyStatus': BentleyStatus, 'EditElementHandle': EditElementHandle,
              'ElementPropertiesSetter': ElementPropertiesSetter, 'DPoint3d': DPoint3d,
              'DVec3d': DVec3d, 'DPoint3dArray': DPoint3dArray, 'ISessionMgr': ISessionMgr,
              'WString': lambda value: value}
    geometry = {'DSegment3d': DSegment3d, 'DgnConeDetail': DgnConeDetail,
                'DgnTorusPipeDetail': DgnTorusPipeDetail, 'ISolidPrimitive': _Primitive,
                'SolidUtil': SolidUtil, 'ShapeHandler': _ShapeHandler,
                'ISolidKernelEntityPtrArray': ISolidKernelEntityPtrArray}
    platform = {'LineHandler': _LineHandler,
                'NormalCellHeaderHandler': _CellHandler,
                'DraftingElementSchema': _DraftingElementSchema}
    make('MSPyBentley', common)
    make('MSPyBentleyGeom', dict(common, **geometry))
    make('MSPyDgnPlatform', dict(common, **geometry, **platform))
    make('MSPyDgnView', dict(common, **geometry, **platform))
    make('MSPyMstnPlatform',
         dict(common, **platform, **runtime, DgnPrimitiveTool=DgnPrimitiveTool))
    make('win32gui', {})


def load_plugin():
    _install_stub_modules()
    spec = importlib.util.spec_from_file_location('security_fence_gate', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules['security_fence_gate'] = module
    spec.loader.exec_module(module)
    return module


def set_model(uor_per_meter=1000.0, is_3d=True):
    ISessionMgr.ActiveDgnModelRef = _ModelRef(_DgnModel(uor_per_meter, is_3d))


def build(module, options, origin=(0.0, 0.0, 0.0), uor_per_meter=1000.0):
    set_model(uor_per_meter)
    del CREATED[:]
    _SolidModify.fail_next = False
    _SolidModify.fail_mitre = False
    builder, result = module._build_security_gate_cell(DPoint3d(*origin), options)
    return builder, result


def finals(kind=None):
    """返回真正写进单元的元素（BodyToElement 的模板 / 线元素）。"""
    return [element for element in CREATED
            if element.is_final and (kind is None or element.kind == kind)]


def tube_details():
    return [element.data for element in finals('cone')]


def torus_details():
    return [element.data for element in finals('torus')]


def cutters():
    """斜接切刀：只被当成布尔切刀用过、且没有写入单元的方块。"""
    return [element for element in CREATED
            if element.kind == 'shape' and getattr(element, 'is_cutter', False)]


def foundations():
    return [element for element in finals('shape') if element.color == 3]


def hinge_pins():
    """活页销轴：半径等于 HINGE_PIN_DIAMETER/2 的实心圆柱（未转实体的原始锥元素）。"""
    return [element.data for element in CREATED
            if element.kind == 'cone' and
            close(getattr(element.data, 'radius', -1.0),
                  module.HINGE_PIN_DIAMETER / 2.0)]


def hinge_plates():
    """活页连接板：颜色为 COLOR_HINGE 的最终 shape。"""
    return [element for element in finals('shape')
            if element.color == module.COLOR_HINGE]


def line_data(color=None):
    return [element.data for element in finals('line')
            if color is None or element.color == color]


def horizontal_wires():
    return [data for data in line_data(2)
            if close(abs(data[0].z - data[1].z), 0.0, 1e-9)]


def barbs():
    return [data for data in line_data(2)
            if not close(abs(data[0].z - data[1].z), 0.0, 1e-9)]


def close(a, b, tolerance=1.0e-6):
    return abs(a - b) <= tolerance


def point_close(point, expected, tolerance=1.0e-6):
    return (close(point.x, expected[0], tolerance) and
            close(point.y, expected[1], tolerance) and
            close(point.z, expected[2], tolerance))


def z_range(detail):
    return (min(detail.start.z, detail.end.z), max(detail.start.z, detail.end.z))


def local_point(point, heading_deg, origin=(0.0, 0.0, 0.0)):
    """把模型点反算成本地 (x, y, z) 毫米（uor_per_mm = 1 时）。"""
    angle = math.radians(heading_deg)
    u = (math.cos(angle), math.sin(angle))
    v = (-math.sin(angle), math.cos(angle))
    dx = point.x - origin[0]
    dy = point.y - origin[1]
    return (u[0] * dx + u[1] * dy, v[0] * dx + v[1] * dy, point.z - origin[2])


# --------------------------------------------------------------------------
module = load_plugin()
GATE_HEIGHT = module.GATE_HEIGHT
R = module.ELBOW_CENTERLINE_RADIUS
ANGLE = math.radians(module.OVERHANG_ANGLE_DEG)
ELBOW_LEN = R * ANGLE
STRAIGHT = module.OVERHANG_LENGTH - ELBOW_LEN
HALF = module.GATE_FRAME_OD / 2.0
ELBOW_END_Y = R * (1.0 - math.cos(ANGLE))
ELBOW_END_Z = GATE_HEIGHT + R * math.sin(ANGLE)


def post_tubes(scale=1.0):
    """门柱本体：φ100 且管长为 2600（用来把悬臂直段等同半径钢管排除掉）。"""
    return [detail for detail in tube_details()
            if close(detail.radius, module.GATE_POST_OD / 2.0 * scale, 1e-6 * scale)
            and close(z_range(detail)[1] - z_range(detail)[0],
                      module.GATE_POST_LENGTH * scale, 1e-6 * scale)]


print('=== 单扇门（默认 1200，0°）===')
builder, result = build(module, {'gate_type': 'single'})
check('single/leaf_width', close(result['leaf_width'], 1160.0), result['leaf_width'])
check('single/leaf_count', result['leaf_count'] == 1)
check('single/posts', result['posts'] == 2)
check('single/no_warnings', result['warnings'] == [], result['warnings'])

posts = post_tubes()
check('single/post_count', len(posts) == 2, len(posts))
check('single/post_offsets', sorted(round(d.start.x, 3) for d in posts) == [-650.0, 650.0],
      sorted(round(d.start.x, 3) for d in posts))
check('single/post_embedment',
      all(close(d.start.z, -800.0) and close(d.end.z, 1800.0) for d in posts))

frame_members = [detail for detail in tube_details() if close(detail.radius, HALF)]
# 门框构件两端各沿轴线外伸 MITRE_END_EXTENSION 再切，端点在角点外侧半个管径以上。
frame_ext = module.MITRE_END_EXTENSION
expected_frame = sorted([
    (round(-558.6 - frame_ext, 4), 71.4, round(558.6 + frame_ext, 4), 71.4),
    (round(-558.6 - frame_ext, 4), 1778.6, round(558.6 + frame_ext, 4), 1778.6),
    (-558.6, round(71.4 - frame_ext, 4), -558.6, round(1778.6 + frame_ext, 4)),
    (558.6, round(71.4 - frame_ext, 4), 558.6, round(1778.6 + frame_ext, 4))])
frame_points = sorted(
    (round(d.start.x, 4), round(d.start.z, 4), round(d.end.x, 4), round(d.end.z, 4))
    for d in frame_members
    if (close(abs(d.start.z - d.end.z), 0.0, 1e-9) or close(abs(d.start.x - d.end.x), 0.0, 1e-9))
    and max(d.start.z, d.end.z) <= GATE_HEIGHT + frame_ext + 1e-6)
check('single/frame_corners', frame_points == expected_frame, frame_points)
# 外伸量至少要达到半个管径，切平面才能在角点处切出完整端面（否则会留缺口）。
check('single/mitre_end_extension_covers_outer_corner',
      module.MITRE_END_EXTENSION >= module.GATE_FRAME_OD / 2.0,
      module.MITRE_END_EXTENSION)
arm_tubes = [detail for detail in frame_members
             if min(detail.start.z, detail.end.z) >= GATE_HEIGHT - 1e-6]
check('single/overhang_arms', len(arm_tubes) == 2, len(arm_tubes))
if arm_tubes:
    detail = arm_tubes[0]
    # 门扇悬臂为竖直段：x/y 不变，从 GATE_HEIGHT 直上 OVERHANG_LENGTH。
    check('single/arm_tip',
          close(detail.start.x, detail.end.x) and
          close(detail.start.y, detail.end.y) and
          close(detail.start.z, GATE_HEIGHT) and
          close(detail.end.z, GATE_HEIGHT + module.OVERHANG_LENGTH),
          (detail.start, detail.end))

braces = [detail for detail in tube_details() if close(detail.radius, module.GATE_BRACE_OD / 2.0)]
check('single/brace_count', len(braces) == 1, len(braces))
if braces:
    detail = braces[0]
    corner_start = (-558.6, 0.0, 71.4)
    corner_end = (558.6, 0.0, 1778.6)
    span_dx = corner_end[0] - corner_start[0]
    span_dz = corner_end[2] - corner_start[2]
    span = math.hypot(span_dx, span_dz)
    ux = span_dx / span
    uz = span_dz / span
    recess = module.BRACE_END_RECESS
    check('single/brace_hinge_to_latch',
          point_close(detail.start,
                      (corner_start[0] + ux * recess, 0.0, corner_start[2] + uz * recess)) and
          point_close(detail.end,
                      (corner_end[0] - ux * recess, 0.0, corner_end[2] - uz * recess)),
          (detail.start, detail.end))

cut_box_list = cutters()
check('single/mitre_cutters', len(cut_box_list) == 8, len(cut_box_list))
corners_found = []
for element in cut_box_list:
    points = element.data
    center = (sum(p.x for p in points[:4]) / 4.0,
              sum(p.y for p in points[:4]) / 4.0,
              sum(p.z for p in points[:4]) / 4.0)
    corners_found.append((round(center[0], 4), round(center[2], 4)))
check('single/mitre_plane_points',
      sorted(corners_found) == sorted([(-558.6, 71.4), (-558.6, 71.4), (558.6, 71.4),
                                       (558.6, 71.4), (-558.6, 1778.6), (-558.6, 1778.6),
                                       (558.6, 1778.6), (558.6, 1778.6)]),
      sorted(corners_found))
if cut_box_list:
    points = [p for p in cut_box_list[0].data[:4]]
    # 切平面必须与门扇平面成 45°：轮廓在面内的两个方向是 ±y 与 45° 斜方向，
    # 因此四点到 45° 对角线的距离轴 |dx| - |dz| 应当处处相同。
    span_y = max(p.y for p in points) - min(p.y for p in points)
    span_plane = max(abs((p.x - points[0].x) - (p.z - points[0].z)) for p in points)
    span_plane_other = max(abs((p.x - points[0].x) + (p.z - points[0].z)) for p in points)
    check('single/mitre_cutter_square_300',
          close(span_y, 300.0, 1e-4) and
          close(max(span_plane, span_plane_other), 300.0 * math.sqrt(2.0), 1e-4),
          (span_y, span_plane, span_plane_other))
    deltas = sorted(round(abs(p.x - points[0].x) - abs(p.z - points[0].z), 6) for p in points)
    check('single/mitre_plane_45deg', close(deltas[0], deltas[-1], 1e-6), deltas)

# 斜接切刀必须切在**朝向另一根构件**的一侧：同一角落两根构件各保留自身一侧，
# 切刀法向应当相反，两个 45° 端面才能拼合。若两者同向（都指向角落外侧），就是
# 切反了：两根构件被切在同一侧，角点会出现缺口、内侧反而重叠。
def cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def cutter_normal(element):
    corners = element.data[:4]
    edge_one = (corners[1].x - corners[0].x, corners[1].y - corners[0].y,
                corners[1].z - corners[0].z)
    edge_two = (corners[2].x - corners[1].x, corners[2].y - corners[1].y,
                corners[2].z - corners[1].z)
    winding = cross(edge_one, edge_two)
    length = math.sqrt(sum(value * value for value in winding))
    return tuple(value / length for value in winding)


corner_normals = {}
for element in cut_box_list:
    corners = element.data[:4]
    centroid_x = sum(p.x for p in corners) / 4.0
    centroid_z = sum(p.z for p in corners) / 4.0
    key = (round(centroid_x, 3), round(centroid_z, 3))
    corner_normals.setdefault(key, []).append(cutter_normal(element))

opposite_ok = True
diagonal_ok = True
normal_details = []
for key, normals in sorted(corner_normals.items()):
    if len(normals) != 2:
        opposite_ok = False
        normal_details.append((key, normals))
        continue
    if not all(abs(normals[0][i] + normals[1][i]) < 1e-6 for i in range(3)):
        opposite_ok = False
        normal_details.append((key, normals))
    for normal in normals:
        if not (close(abs(normal[0]), math.sqrt(0.5), 1e-6) and
                close(normal[1], 0.0, 1e-6) and
                close(abs(normal[2]), math.sqrt(0.5), 1e-6)):
            diagonal_ok = False
check('single/mitre_cut_side_opposite', opposite_ok, normal_details)
check('single/mitre_cut_normals_diagonal', diagonal_ok)

wires = horizontal_wires()
check('single/barbed_wires', len(wires) == 3, len(wires))
for index, data in enumerate(sorted(wires, key=lambda item: item[0].z)):
    fraction = (index + 1) / 3.0
    expected_z = GATE_HEIGHT + module.OVERHANG_LENGTH * fraction
    x_ok = close(data[0].x, -558.6) and close(data[1].x, 558.6)
    check('single/wire_%d_position' % (index + 1),
          x_ok and close(data[0].y, 0.0) and close(data[0].z, expected_z),
          (data[0], round(expected_z, 4)))
check('single/barb_count', len(barbs()) == 12, len(barbs()))

mesh = line_data(9)
check('single/mesh_count', 80 <= len(mesh) <= 100, len(mesh))
inside = True
diagonal = True
for start, end in mesh:
    if not (-558.6 - 1e-6 <= start.x <= 558.6 + 1e-6 and
            -558.6 - 1e-6 <= end.x <= 558.6 + 1e-6):
        inside = False
    if not (71.4 - 1e-6 <= start.z <= 1778.6 + 1e-6 and
            71.4 - 1e-6 <= end.z <= 1778.6 + 1e-6):
        inside = False
    if not close(abs(end.x - start.x), abs(end.z - start.z), 1e-6):
        diagonal = False
check('single/mesh_inside_frame', inside)
check('single/mesh_45deg', diagonal)

# 活页：单扇门 3 个，竖直销轴 + 上下两块连接板；位于合页侧立柱与门柱之间的缝隙。
pins = hinge_pins()
check('single/hinge_pin_count', len(pins) == 3, len(pins))
check('single/hinge_plate_count', len(hinge_plates()) == 6, len(hinge_plates()))
if pins:
    bottom, top = 71.4, 1778.6
    expected_z = sorted(
        round(bottom + (top - bottom) * f, 4) - module.HINGE_PIN_LENGTH / 2.0
        for f in module.HINGE_HEIGHT_FRACTIONS)
    check('single/hinge_pin_heights',
          sorted(round(p.start.z, 4) for p in pins) == expected_z,
          sorted(round(p.start.z, 4) for p in pins))
    check('single/hinge_pin_in_gap',
          all(-600.0 - 1e-6 < p.start.x < -580.0 + 1e-6 for p in pins),
          [round(p.start.x, 3) for p in pins])
plates = hinge_plates()
if plates:
    plate_xs = sorted(set(round(p.x, 4) for p in plates[0].data))
    check('single/hinge_plate_span',
          close(plate_xs[0], -650.0) and close(plate_xs[-1], -558.6), plate_xs)

check('single/child_count_matches', builder.child_count == len(builder.cell.children),
      builder.child_count)
check('single/element_total', len(CREATED) > 0)

print()
print('=== 双扇门（默认 4270）===')
builder, result = build(module, {'gate_type': 'double'})
check('double/leaf_width', close(result['leaf_width'], 2105.0), result['leaf_width'])
check('double/leaf_count', result['leaf_count'] == 2)
posts = post_tubes()
check('double/post_offsets', sorted(round(d.start.x, 3) for d in posts) == [-2185.0, 2185.0],
      sorted(round(d.start.x, 3) for d in posts))
# 门框构件两端外伸后再切，端点会越过角点；用立柱中心线（竖直构件）判断两扇位置。
leaf_stile_xs = sorted({round(d.start.x, 3) for d in tube_details()
                        if close(d.radius, HALF) and close(d.start.x, d.end.x)})
check('double/leaf_stile_xs', leaf_stile_xs == [-2093.6, -31.4, 31.4, 2093.6], leaf_stile_xs)
braces = [detail for detail in tube_details()
          if close(detail.radius, module.GATE_BRACE_OD / 2.0)]
check('double/brace_count', len(braces) == 2, len(braces))


def brace_corner_start(brace):
    """把斜撑起点沿管轴外推 BRACE_END_RECESS，还原到门框角点。"""
    dx = brace.end.x - brace.start.x
    dz = brace.end.z - brace.start.z
    span = math.hypot(dx, dz)
    return (brace.start.x - dx / span * module.BRACE_END_RECESS,
            brace.start.z - dz / span * module.BRACE_END_RECESS)


check('double/braces_hinge_outside',
      all(close(brace_corner_start(b)[0], -2093.6) or close(brace_corner_start(b)[0], 2093.6)
          for b in braces),
      [tuple(round(v, 2) for v in (b.start.x, b.start.z, b.end.x, b.end.z)) for b in braces])
check('double/braces_mirrored',
      {round(brace_corner_start(b)[0], 3) for b in braces} == {-2093.6, 2093.6})
wires = horizontal_wires()
check('double/wire_count', len(wires) == 6, len(wires))
check('double/wire_x_span',
      {(round(min(w[0].x, w[1].x), 3), round(max(w[0].x, w[1].x), 3)) for w in wires} ==
      {(-2093.6, -31.4), (31.4, 2093.6)},
      {(round(min(w[0].x, w[1].x), 3), round(max(w[0].x, w[1].x), 3)) for w in wires})
# 双扇门：每扇 3 个活页，共 6 销轴 / 12 连接板。
check('double/hinge_pin_count', len(hinge_pins()) == 6, len(hinge_pins()))
check('double/hinge_plate_count', len(hinge_plates()) == 12, len(hinge_plates()))

print()
print('=== 选项开关 ===')
builder, result = build(module, {'gate_type': 'double', 'include_posts': False})
check('options/no_posts', result['posts'] == 0 and not post_tubes())
check('options/no_foundation', not foundations())
# 不建门柱时活页仍要生成（连接门扇与预埋柱位置）。
check('options/no_posts_hinges',
      len(hinge_pins()) == 6 and len(hinge_plates()) == 12,
      (len(hinge_pins()), len(hinge_plates())))
builder, result = build(module, {'gate_type': 'single', 'include_overhang': False})
check('options/no_overhang_wires', not line_data(2))
check('options/no_overhang_elbows', not torus_details())
builder, result = build(module, {'gate_type': 'single', 'include_foundation': False})
check('options/foundation_flag', result['foundation'] is False and not foundations())
builder, result = build(module, {'gate_type': 'single', 'include_foundation': True})
blocks = foundations()
check('options/foundation_blocks', len(blocks) == 2, len(blocks))
if blocks:
    points = blocks[0].data
    xs = sorted(set(round(p.x, 4) for p in points))
    ys = sorted(set(round(p.y, 4) for p in points))
    zs = sorted(set(round(p.z, 4) for p in points))
    check('options/foundation_size',
          close(xs[0], -850.0) and close(xs[-1], -450.0) and
          close(ys[0], -200.0) and close(ys[-1], 200.0) and zs == [-600.0],
          (xs, ys, zs))
    # 基础轮廓画在 -600，必须沿 +Z 拉伸 600 才能顶面与地面齐平：轮廓绕向
    # （右手方向）决定了 ThickenSheet 的拉伸方向，这里直接校验绕向。
    edge_one = (points[1].x - points[0].x, points[1].y - points[0].y, 0.0)
    edge_two = (points[2].x - points[1].x, points[2].y - points[1].y, 0.0)
    winding = (edge_one[1] * edge_two[2] - edge_one[2] * edge_two[1],
               edge_one[2] * edge_two[0] - edge_one[0] * edge_two[2],
               edge_one[0] * edge_two[1] - edge_one[1] * edge_two[0])
    check('options/foundation_extrudes_up', winding[2] > 0.0, winding)
check('options/elbow_count_leaf_and_posts',
      len(torus_details()) == 2, len(torus_details()))  # 门扇悬臂竖直无弯头，仅两根门柱各 1
builder, result = build(module, {'gate_type': 'double'})
check('options/double_elbow_count', len(torus_details()) == 2, len(torus_details()))
builder, result = build(module, {'gate_type': 'single', 'include_posts': False})
check('options/no_posts_elbow_count', len(torus_details()) == 0, len(torus_details()))

print()
print('=== 单位换算（英尺主单位 uor_per_meter=304800）===')
builder, result = build(module, {'gate_type': 'single'}, uor_per_meter=304800.0)
posts = post_tubes(304.8)
check('feet/post_count', len(posts) == 2, len(posts))
if posts:
    detail = posts[0]
    check('feet/post_offset_uor', close(abs(detail.start.x), 650.0 * 304.8, 1e-6),
          detail.start.x)
    check('feet/post_z_uor', close(detail.start.z, -800.0 * 304.8, 1e-6) and
          close(detail.end.z, 1800.0 * 304.8, 1e-6))
    check('feet/radius_uor', close(detail.radius, 50.0 * 304.8, 1e-6), detail.radius)
mesh = line_data(9)
check('feet/mesh_present', len(mesh) > 80, len(mesh))
if mesh:
    start, end = mesh[0]
    check('feet/mesh_45deg_uor', close(abs(end.x - start.x), abs(end.z - start.z), 1e-6))

print()
print('=== 转角与反向 ===')
builder, result = build(module, {'gate_type': 'single', 'heading_deg': 90.0})
posts = post_tubes()
check('rot90/posts_on_y', sorted(round(d.start.y, 3) for d in posts) == [-650.0, 650.0],
      sorted(round(d.start.y, 3) for d in posts))
check('rot90/posts_x_zero', all(close(d.start.x, 0.0) for d in posts))
wires = horizontal_wires()
check('rot90/wires_along_y', wires and all(close(w[0].x, w[1].x) for w in wires) and
      all(close(abs(w[0].y - w[1].y), 1117.2, 1e-6) for w in wires),
      [(round(w[0].x, 2), round(w[0].y, 2)) for w in wires])
check('rot90/wire_vertical_no_lean', wires and all(close(w[0].x, 0.0) for w in wires),
      [round(w[0].x, 2) for w in wires])

builder, result = build(module, {'gate_type': 'single', 'mirrored': True})
check('mirrored/heading', close(result['heading_deg'], 180.0), result['heading_deg'])
wires = horizontal_wires()
check('mirrored/wire_vertical_no_lean', wires and all(close(w[0].y, 0.0) for w in wires),
      [round(w[0].y, 2) for w in wires])
builder, result = build(module, {'gate_type': 'single', 'heading_deg': 30.0})
wires = horizontal_wires()
local_wires = [(local_point(w[0], 30.0), local_point(w[1], 30.0)) for w in wires]
check('rot30/wire_local_width',
      wires and all(close(abs(l[1][0] - l[0][0]), 1117.2, 1e-6) and
                    close(l[0][1], l[1][1], 1e-6) and close(l[0][2], l[1][2], 1e-6)
                    for l in local_wires),
      [(round(l[0][0], 3), round(l[1][0], 3)) for l in local_wires])
check('rot30/post_local_positions',
      sorted(round(local_point(d.start, 30.0)[0], 3) for d in post_tubes()) == [-650.0, 650.0],
      sorted(round(local_point(d.start, 30.0)[0], 3) for d in post_tubes()))

print()
print('=== 原点平移 ===')
builder, result = build(module, {'gate_type': 'single'}, origin=(1234.5, -678.9, 250.0))
posts = post_tubes()
check('origin/post_positions',
      sorted((round(d.start.x, 4), round(d.start.y, 4), round(d.start.z, 4))
             for d in posts) == sorted([(584.5, -678.9, -550.0), (1884.5, -678.9, -550.0)]),
      [(d.start.x, d.start.y, d.start.z) for d in posts])

print()
print('=== 布尔失败降级 ===')
set_model(1000.0)
del CREATED[:]
_SolidModify.fail_mitre = True
builder, result = module._build_security_gate_cell(
    DPoint3d(0.0, 0.0, 0.0), {'gate_type': 'single'})
_SolidModify.fail_mitre = False
check('fallback/mitre_warning', any(u'\u659c\u63a5' in w for w in result['warnings']),
      result['warnings'])
check('fallback/still_builds', result['child_count'] > 100, result['child_count'])
check('fallback/frame_members_kept',
      len([d for d in tube_details() if close(d.radius, HALF)]) >= 4)

print()
print('=== 参数校验 ===')
def expect_error(name, options, message):
    try:
        build(module, options)
    except Exception as error:
        check(name, message in str(error), str(error))
        return
    check(name, False, 'no exception raised')


expect_error('validate/bad_type', {'gate_type': 'triple'}, u'\u95e8\u578b')
expect_error('validate/width_too_small', {'gate_type': 'single', 'opening_width': 100.0},
             u'\u95e8\u6d1e\u51c0\u5bbd')
expect_error('validate/width_too_large', {'gate_type': 'double', 'opening_width': 99000.0},
             u'\u95e8\u6d1e\u51c0\u5bbd')
expect_error('validate/unknown_option', {'gate_type': 'single', 'bogus': 1}, u'\u672a\u77e5\u9009\u9879')
expect_error('validate/bad_heading', {'gate_type': 'single', 'heading_deg': 'x'},
             u'\u8f6c\u89d2')

set_model(1000.0, is_3d=False)
try:
    module._build_security_gate_cell(DPoint3d(0.0, 0.0, 0.0), {'gate_type': 'single'})
    check('validate/needs_3d', False, 'no exception')
except Exception as error:
    check('validate/needs_3d', u'3D' in str(error), str(error))
set_model(1000.0)

try:
    module._build_security_gate_cell(None, {'gate_type': 'single'})
    check('validate/needs_point', False, 'no exception')
except Exception as error:
    check('validate/needs_point', u'\u70b9\u53d6' in str(error), str(error))

print()
print('=== 自定义门宽 ===')
builder, result = build(module, {'gate_type': 'double', 'opening_width': 5000.0})
check('custom/leaf_width', close(result['leaf_width'], (5000.0 - 40.0 - 20.0) / 2.0),
      result['leaf_width'])
check('custom/still_valid', result['warnings'] == [])
check('custom/post_offsets',
      sorted(round(d.start.x, 3) for d in post_tubes()) == [-2550.0, 2550.0])
builder, result = build(module, {'gate_type': 'single', 'opening_width': 3000.0})
check('custom/wide_single', close(result['leaf_width'], 2960.0) and not result['warnings'])

print()
print('=== 单元封装 ===')
builder, result = build(module, {'gate_type': 'double'})
check('cell/name', builder.cell.data == 'SECURITY_GATE', builder.cell.data)
check('cell/children', len(builder.cell.children) == builder.child_count)
check('cell/not_written_yet', not builder.cell.added_to_model)
handle = builder.commit()
check('cell/committed', handle.added_to_model)
set_model(1000.0)
del CREATED[:]
builder, result = module._build_security_gate_cell(DPoint3d(0, 0, 0), {'gate_type': 'single'})
old = builder.commit()
check('cell/delete_preview', module._delete_preview(old) and old.deleted)

print()
print('=== 面板交互（真实 Tk，不进入主循环）===')
try:
    dialog = module._GateSettingsDialog()
    dialog.withdraw()
    defaults = dialog.current_options()
    check('ui/defaults', defaults['gate_type'] == 'single' and
          close(defaults['opening_width'], 1200.0) and defaults['include_posts'] and
          defaults['include_foundation'] and defaults['include_overhang'] and
          not defaults['mirrored'], defaults)
    dialog.gate_type_var.set('double')
    dialog.on_gate_type_changed()
    check('ui/type_switch_resets_width',
          close(dialog.current_options()['opening_width'], 4270.0),
          dialog.current_options()['opening_width'])
    dialog.width_var.set('3000')
    check('ui/custom_width', close(dialog.current_options()['opening_width'], 3000.0))
    dialog.width_var.set(u'\u4e09')
    try:
        dialog.current_options()
        check('ui/bad_width', False, 'no exception')
    except ValueError as error:
        check('ui/bad_width', True, str(error))
    dialog.width_var.set('1200')
    dialog.heading_var.set('45')
    check('ui/heading', close(dialog.current_options()['heading_deg'], 45.0))
    dialog.on_options_changed()
    check('ui/no_regen_before_placement', dialog._pending_regeneration is None)
    check('ui/option_widgets', len(dialog.option_widgets) == 8,
          len(dialog.option_widgets))
    check('ui/no_preview_to_discard', dialog.discard_preview() is False)
    dialog.destroy()
except Exception as error:
    check('ui/dialog_constructs', False, repr(error))

print()
if FAILURES:
    print('FAILED %d: %s' % (len(FAILURES), FAILURES))
    sys.exit(1)
print('ALL CHECKS PASSED')
