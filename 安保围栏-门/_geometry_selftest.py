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
expected_frame = sorted([
    (-558.6, 71.4, 558.6, 71.4), (-558.6, 1778.6, 558.6, 1778.6),
    (-558.6, 71.4, -558.6, 1778.6), (558.6, 71.4, 558.6, 1778.6)])
frame_points = sorted(
    (round(d.start.x, 4), round(d.start.z, 4), round(d.end.x, 4), round(d.end.z, 4))
    for d in frame_members
    if (close(abs(d.start.z - d.end.z), 0.0, 1e-9) or close(abs(d.start.x - d.end.x), 0.0, 1e-9))
    and max(d.start.z, d.end.z) <= 1800.0)
check('single/frame_corners', frame_points == expected_frame, frame_points)
arm_tubes = [detail for detail in frame_members
             if min(detail.start.z, detail.end.z) > 1800.0]
check('single/overhang_arms', len(arm_tubes) == 2, len(arm_tubes))
if arm_tubes:
    detail = arm_tubes[0]
    check('single/arm_tip',
          close(detail.end.y, ELBOW_END_Y + STRAIGHT * math.sin(ANGLE)) and
          close(detail.end.z, ELBOW_END_Z + STRAIGHT * math.cos(ANGLE)) and
          close(detail.start.z, ELBOW_END_Z),
          (detail.end,))

braces = [detail for detail in tube_details() if close(detail.radius, module.GATE_BRACE_OD / 2.0)]
check('single/brace_count', len(braces) == 1, len(braces))
if braces:
    detail = braces[0]
    check('single/brace_hinge_to_latch',
          point_close(detail.start, (-558.6, 0.0, 71.4)) and
          point_close(detail.end, (558.6, 0.0, 1778.6)),
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

# 斜接切刀必须切在门框**外侧**：轮廓绕向决定 ThickenSheet 的拉伸方向，也就是被
# 布尔减掉的一侧；它应当指向该角落的外斜方向，而不是指向门框内部。这一条能抓出
# "斜接法向算反、把整根构件切掉" 这类错误（只校验 45° 角是抓不到的）。
expected_normals = {
    (-558.6, 71.4): (-1.0, -1.0),
    (558.6, 71.4): (1.0, -1.0),
    (-558.6, 1778.6): (-1.0, 1.0),
    (558.6, 1778.6): (1.0, 1.0),
}


def cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


outward_ok = True
normal_details = []
seen_normals = []
for element in cut_box_list:
    corners = element.data[:4]
    centroid_x = sum(p.x for p in corners) / 4.0
    centroid_z = sum(p.z for p in corners) / 4.0
    expected = expected_normals.get((round(centroid_x, 3), round(centroid_z, 3)))
    if expected is None:
        outward_ok = False
        normal_details.append(('unknown corner', round(centroid_x, 3), round(centroid_z, 3)))
        continue
    edge_one = (corners[1].x - corners[0].x, corners[1].y - corners[0].y,
                corners[1].z - corners[0].z)
    edge_two = (corners[2].x - corners[1].x, corners[2].y - corners[1].y,
                corners[2].z - corners[1].z)
    winding = cross(edge_one, edge_two)
    length = math.sqrt(sum(value * value for value in winding))
    winding = tuple(value / length for value in winding)
    expected_unit = (expected[0] / math.sqrt(2.0), 0.0, expected[1] / math.sqrt(2.0))
    seen_normals.append(tuple(round(value, 4) for value in winding))
    if not all(abs(winding[i] - expected_unit[i]) < 1e-6 for i in range(3)):
        outward_ok = False
        normal_details.append(((round(centroid_x, 3), round(centroid_z, 3)),
                               tuple(round(value, 4) for value in winding)))
check('single/mitre_cut_side_outward', outward_ok, normal_details)
check('single/mitre_planes_match_between_members',
      len(set(seen_normals)) == 4, sorted(set(seen_normals)))

wires = horizontal_wires()
check('single/barbed_wires', len(wires) == 3, len(wires))
for index, data in enumerate(sorted(wires, key=lambda item: item[0].z)):
    fraction = (index + 1) / 3.0
    expected_y = ELBOW_END_Y + STRAIGHT * fraction * math.sin(ANGLE)
    expected_z = ELBOW_END_Z + STRAIGHT * fraction * math.cos(ANGLE)
    x_ok = close(data[0].x, -558.6) and close(data[1].x, 558.6)
    check('single/wire_%d_position' % (index + 1),
          x_ok and close(data[0].y, expected_y) and close(data[0].z, expected_z),
          (data[0], round(expected_y, 4), round(expected_z, 4)))
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
left_leaf = [d for d in tube_details() if close(d.radius, HALF) and d.start.x < 0]
right_leaf = [d for d in tube_details() if close(d.radius, HALF) and d.start.x > 0]
check('double/left_leaf_span',
      close(min(d.start.x for d in left_leaf), -2093.6) and
      close(max(d.start.x for d in left_leaf), -31.4),
      (min(d.start.x for d in left_leaf), max(d.start.x for d in left_leaf)))
check('double/right_leaf_span',
      close(min(d.start.x for d in right_leaf), 31.4) and
      close(max(d.start.x for d in right_leaf), 2093.6))
braces = [detail for detail in tube_details()
          if close(detail.radius, module.GATE_BRACE_OD / 2.0)]
check('double/brace_count', len(braces) == 2, len(braces))
check('double/braces_hinge_outside',
      all(close(b.start.x, -2093.6) or close(b.start.x, 2093.6) for b in braces),
      [tuple(round(v, 2) for v in (b.start.x, b.start.z, b.end.x, b.end.z)) for b in braces])
check('double/braces_mirrored',
      {round(b.start.x, 3) for b in braces} == {-2093.6, 2093.6})
wires = horizontal_wires()
check('double/wire_count', len(wires) == 6, len(wires))
check('double/wire_x_span',
      {(round(min(w[0].x, w[1].x), 3), round(max(w[0].x, w[1].x), 3)) for w in wires} ==
      {(-2093.6, -31.4), (31.4, 2093.6)},
      {(round(min(w[0].x, w[1].x), 3), round(max(w[0].x, w[1].x), 3)) for w in wires})

print()
print('=== 选项开关 ===')
builder, result = build(module, {'gate_type': 'double', 'include_posts': False})
check('options/no_posts', result['posts'] == 0 and not post_tubes())
check('options/no_foundation', not foundations())
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
      len(torus_details()) == 4, len(torus_details()))
builder, result = build(module, {'gate_type': 'double'})
check('options/double_elbow_count', len(torus_details()) == 6, len(torus_details()))
builder, result = build(module, {'gate_type': 'single', 'include_posts': False})
check('options/no_posts_elbow_count', len(torus_details()) == 2, len(torus_details()))

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
check('rot90/wire_offset_toward_neg_x', wires and all(w[0].x < 0 for w in wires),
      [round(w[0].x, 2) for w in wires])

builder, result = build(module, {'gate_type': 'single', 'mirrored': True})
check('mirrored/heading', close(result['heading_deg'], 180.0), result['heading_deg'])
wires = horizontal_wires()
check('mirrored/wire_offset_toward_neg_y', wires and all(w[0].y < 0 for w in wires),
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
