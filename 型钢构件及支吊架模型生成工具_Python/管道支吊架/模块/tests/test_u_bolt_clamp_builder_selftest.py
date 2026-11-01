# -*- coding: utf-8 -*-
"""U 型管卡建模库（``U型管卡_几何_Bentley.py``）的**桩件自测**（不需要 OPM）。

思路沿用仓库既有的 ``罐壁人孔/_geometry_selftest.py``：把 MSPy 的一小撮类型
换成纯 Python 替身，然后真正**调用**建模库里的几何装配函数，检查它们交给
``BodyFromSweep`` 的**截面与路径数据**是否正确 —— 也就是把"OPM 里才能看出来
的错"尽量提前到纯 CPython 里发现：

* U 型螺栓扫掠路径：两段直腿 + 一段 180° 真圆弧，切点、端点、半径逐点核对；
* 圆截面：圆心在路径起点、法向与路径起始切线一致、半径 = 螺栓直径 / 2；
* 六角螺母截面：对边宽 1.5d（外接圆半径 = 对边 / 2cos30°）、截面落在腿的
  垂直面内、中心在 ``z = ±C/2``；
* 六角棱柱 + 圆柱通孔都交给 ``BodyFromSweep`` / 布尔差集，两者都被调用到；
* 落图顺序：整组写成一个普通单元（先加子元素、再 ``AddChildComplete``、
  最后 ``AddToModel``）。

运行：``python -B 管道支吊架/模块/tests/test_u_bolt_clamp_builder_selftest.py``
"""

from __future__ import division

import math
import os
import sys
import types
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_GEOM_DIR = os.path.join(_MODULE_DIR, 'U型管卡')
if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)


# ---------------------------------------------------------------------------
# MSPy 替身：只实现建模库真正用到的那部分
# ---------------------------------------------------------------------------


class DPoint3d(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    @staticmethod
    def From(x, y, z):
        return DPoint3d(x, y, z)

    def as_tuple(self):
        return (self.x, self.y, self.z)


class DVec3d(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    @staticmethod
    def From(x, y, z):
        return DVec3d(x, y, z)

    def as_tuple(self):
        return (self.x, self.y, self.z)


class DSegment3d(object):
    def __init__(self, start, end):
        self.StartPoint = start
        self.EndPoint = end


class DEllipse3d(object):
    """只记住构造方式与关键参数，供断言检查。"""

    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.data = kwargs

    @staticmethod
    def FromCenterNormalRadius(center, normal, radius):
        return DEllipse3d('circle', center=center, normal=normal,
                          radius=radius)

    @staticmethod
    def FromPointsOnArc(start, middle, end):
        return DEllipse3d('arc', start=start, middle=middle, end=end)

    @staticmethod
    def FromArcCenterStartEnd(center, start, end):
        return DEllipse3d('arc', center=center, start=start, end=end)


class _Primitive(object):
    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload


class ICurvePrimitive(object):
    eCURVE_PRIMITIVE_TYPE_Line = 1

    @staticmethod
    def CreateLine(segment):
        return _Primitive('line', segment)

    @staticmethod
    def CreateArc(ellipse):
        return _Primitive('arc', ellipse)


class CurveVector(list):
    eBOUNDARY_TYPE_Open = 'open'
    eBOUNDARY_TYPE_Outer = 'outer'
    eBOUNDARY_TYPE_ParityRegion = 'parity'

    def __init__(self, boundary_type='outer'):
        list.__init__(self)
        self.boundary_type = boundary_type

    @staticmethod
    def CreateDisk(ellipse, boundary_type='outer'):
        disk = CurveVector(boundary_type)
        disk.disk_ellipse = ellipse
        return disk

    def Add(self, item):
        self.append(item)


class DgnConeDetail(object):
    def __init__(self, start, end, radius1, radius2, capped):
        self.start, self.end = start, end
        self.radius1, self.radius2 = radius1, radius2
        self.capped = capped


class _SolidPrimitive(object):
    @staticmethod
    def CreateDgnCone(detail):
        return ('cone', detail)


class DraftingElementSchema(object):
    @staticmethod
    def ToElement(element, primitive, template, model):
        element.created = primitive
        return 0


class EditElementHandle(object):
    #: 本次测试内被创建出来的所有句柄（可按序检查"临时元素有没有被删"）。
    created_handles = []

    def __init__(self):
        self.created = None
        self.children = []
        self.added = False
        self.deleted = False
        EditElementHandle.created_handles.append(self)

    def AddToModel(self):
        self.added = True
        return 0

    def DeleteFromModel(self):
        self.deleted = True
        return 0


class SolidUtil(object):
    """记录每次 BodyFromSweep / BooleanSubtract 的调用参数。"""

    calls = []

    class Create(object):
        @staticmethod
        def BodyFromSweep(profile, path, model, *args):
            SolidUtil.calls.append(('sweep', profile, path))
            return (0, ('body', profile, path))

    class Modify(object):
        @staticmethod
        def BooleanSubtract(target, tools):
            SolidUtil.calls.append(('subtract', target, list(tools)))
            return 0

    class Convert(object):
        @staticmethod
        def BodyToElement(element, body, template, model):
            element.body = body
            return 0

        @staticmethod
        def ElementToBody(element, *args):
            SolidUtil.calls.append(('element_to_body', element))
            return (0, ('cylinder_body', element.created))


class ISolidKernelEntityPtrArray(list):
    pass


class NormalCellHeaderHandler(object):
    cells = []

    @staticmethod
    def CreateOrphanCellElement(cell, name, is_3d, model):
        cell.name = name
        NormalCellHeaderHandler.cells.append(cell)
        return None

    @staticmethod
    def AddChildElement(cell, child):
        cell.children.append(child)
        return 0

    @staticmethod
    def AddChildComplete(cell):
        cell.completed = True
        return 0


class _ModelInfo(object):
    @staticmethod
    def GetUorPerMeter():
        return 1000.0


class _FakeModel(object):
    def __init__(self, is_3d=True):
        self._is_3d = is_3d

    def Is3d(self):
        return self._is_3d

    @staticmethod
    def GetModelInfo():
        return _ModelInfo()


_MODEL = _FakeModel()


class ISessionMgr(object):
    @staticmethod
    def GetActiveDgnModel():
        return _MODEL


def _install_fake_mspy():
    """把替身装进 ``sys.modules``，供建模库的 ``from MSPyX import *`` 取用。"""
    common = {
        'DPoint3d': DPoint3d,
        'DVec3d': DVec3d,
        'DSegment3d': DSegment3d,
        'DEllipse3d': DEllipse3d,
        'ICurvePrimitive': ICurvePrimitive,
        'CurveVector': CurveVector,
        'DgnConeDetail': DgnConeDetail,
        'ISolidPrimitive': _SolidPrimitive,
        'DraftingElementSchema': DraftingElementSchema,
        'EditElementHandle': EditElementHandle,
        'SolidUtil': SolidUtil,
        'ISolidKernelEntityPtrArray': ISolidKernelEntityPtrArray,
        'NormalCellHeaderHandler': NormalCellHeaderHandler,
        'ISessionMgr': ISessionMgr,
    }
    for name in ('MSPyBentley', 'MSPyBentleyGeom', 'MSPyDgnPlatform',
                 'MSPyDgnView', 'MSPyMstnPlatform'):
        module = types.ModuleType(name)
        for key, value in common.items():
            setattr(module, key, value)
        sys.modules[name] = module


_install_fake_mspy()

import U型管卡_几何 as geom  # noqa: E402
import U型管卡_几何_Bentley as builder  # noqa: E402


def _points_of(primitive):
    if primitive.kind == 'line':
        return [primitive.payload.StartPoint, primitive.payload.EndPoint]
    return None


class PathTests(unittest.TestCase):
    """U 型螺栓扫掠路径（两直腿 + 180° 真圆弧）。"""

    @classmethod
    def setUpClass(cls):
        cls.geometry = geom.build_geometry(100)
        cls.frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        cls.frame = builder._Frame((0.0, 0.0, 0.0), cls.frame_axes, 1.0)
        cls.path = builder._u_bolt_path(cls.frame, cls.geometry, 1.0)

    def test_path_has_line_arc_line(self):
        kinds = [item.kind for item in self.path]
        self.assertEqual(kinds, ['line', 'arc', 'line'])

    def test_path_endpoints_are_leg_tips(self):
        """水平管（管轴 +X）开口朝上：腿端在 ``z = D``、两腿分列 ``y = ±C/2``。

        世界 z 是"开口方向"，世界 y 是"第三个轴"——两腿沿世界 y 分开、朝 +Z
        伸出管外，弯弧兜在管下（``z`` 为负）。
        """
        g = self.geometry
        first = _points_of(self.path[0])[0]
        last = _points_of(self.path[2])[1]
        self.assertAlmostEqual(first.x, 0.0)
        self.assertAlmostEqual(first.y, -g.r_leg)
        self.assertAlmostEqual(first.z, g.leg_tip_y)
        self.assertAlmostEqual(last.y, g.r_leg)
        self.assertAlmostEqual(last.z, g.leg_tip_y)

    def test_path_start_tangent_points_toward_arc(self):
        """起始切线沿 −Y（朝弯弧走），两段直腿互相平行且等长 = 直腿段长。"""
        first = _points_of(self.path[0])
        last = _points_of(self.path[2])
        self.assertAlmostEqual(first[1].y - first[0].y, 0.0)
        self.assertAlmostEqual(first[1].z - first[0].z,
                               -self.geometry.straight_mm)
        self.assertLess(first[1].z, first[0].z)
        for index in (0, 2):
            start, end = _points_of(self.path[index])
            length = math.dist(start.as_tuple(), end.as_tuple())
            self.assertAlmostEqual(length, self.geometry.straight_mm, places=9)

    def test_arc_is_three_point_half_circle(self):
        """**180° 半圆必须用三点式**（``FromPointsOnArc``）。

        为什么不能用圆心式 ``FromArcCenterStartEnd``：它靠"圆心→起点"与
        "圆心→终点"反推圆弧平面，而 180° 时这两向量正对、平面退化 → 无效椭圆 →
        扫掠 eERROR（实机已复现）。全仓库用圆心式的弧都是 90°。

        这里核对：弧上中点在弯弧最低点、三点共圆（半径 = C/2）、且中点**不在
        弧心上**（防回退：把弧心当弧上中点会让三点共线、构造退化）。
        """
        g = self.geometry
        arc = self.path[1].payload
        self.assertEqual(arc.kind, 'arc')
        data = arc.data
        start, middle, end = data['start'], data['middle'], data['end']
        # 起点 / 终点：与两条直腿相切，位于 ±C/2、管轴高度。
        for point in (start, end):
            self.assertAlmostEqual(point.z, g.bend_start_y)
        self.assertAlmostEqual(g.bend_start_y, 0.0)
        self.assertAlmostEqual(start.y, -g.r_leg)
        self.assertAlmostEqual(end.y, g.r_leg)
        # 弧上中点 = 弯弧最低点（世界坐标：开口方向是 z）。
        self.assertAlmostEqual(middle.y, 0.0)
        self.assertAlmostEqual(middle.z, g.bend_start_y - g.r_leg, places=9)
        # 三点共圆：到弧心 (y=0, z=bend_start_y) 的距离都等于 R = C/2。
        center = (0.0, g.bend_start_y)
        distances = [math.hypot(point.y - center[0], point.z - center[1])
                     for point in (start, middle, end)]
        for distance in distances:
            self.assertAlmostEqual(distance, g.r_leg, places=9)
        # **防回退**：三点必须互不重合、且中点绝不能等于弧心。
        self.assertGreater(min(distances), 1.0)
        self.assertGreater(math.dist(middle.as_tuple(), start.as_tuple()), 1.0)
        self.assertGreater(math.dist(middle.as_tuple(), end.as_tuple()), 1.0)
        # 弯弧最低点（螺栓内表面）必须在管外。
        self.assertGreater(g.inner_face_radius, g.pipe_od_mm / 2.0)

    def test_arc_points_define_a_plane(self):
        """三点必须**不共线**——否则圆弧所在平面退化（这正是 eERROR 的根因）。"""
        g = self.geometry
        data = self.path[1].payload.data
        start, middle, end = data['start'], data['middle'], data['end']

        def sub(a, b):
            return (a.x - b.x, a.y - b.y, a.z - b.z)

        def cross(a, b):
            return (a[1] * b[2] - a[2] * b[1],
                    a[2] * b[0] - a[0] * b[2],
                    a[0] * b[1] - a[1] * b[0])

        v1 = sub(middle, start)
        v2 = sub(end, middle)
        normal = cross(v1, v2)
        magnitude = math.sqrt(sum(component * component
                                  for component in normal))
        self.assertGreater(magnitude, 1.0, '三点共线，圆弧平面退化')
        # 平面法向必须垂直于管轴方向（本用例管轴 = 世界 X），即 U 型卡平面含管轴。
        self.assertAlmostEqual(normal[0] / magnitude, 1.0, places=6)

    def test_arc_radius_is_consistent(self):
        """圆弧三点必须落在同一个以（管轴, y=0, z=bend_start_y）为圆心的圆上。"""
        g = self.geometry
        arc = self.path[1].payload
        center = (0.0, g.bend_start_y)
        for key in ('start', 'middle', 'end'):
            point = arc.data[key]
            radius = math.hypot(point.y - center[0], point.z - center[1])
            self.assertAlmostEqual(radius, g.r_leg, places=9, msg=key)

    def test_arc_center_is_on_pipe_axis(self):
        """弧心必须落在管轴上（本项目 2026-09-28 修正的核心口径）。

        三点式不直接给圆心，故由"弧上中点 + 半径"反推（中点即最低点）。
        """
        g = self.geometry
        self.assertAlmostEqual(g.arc_center_y, 0.0)
        data = self.path[1].payload.data
        center_z = data['middle'].z + g.r_leg
        self.assertAlmostEqual(center_z, 0.0, places=9)

    def test_legs_and_arc_lie_in_plane_through_pipe_axis(self):
        """整条路径的 x 恒为 0：U 型螺栓所在平面**包含管轴**（= 节点平面）。"""
        for primitive in self.path:
            points = _points_of(primitive)
            if points is None:
                arc = primitive.payload
                points = [arc.data['start'], arc.data['middle'],
                          arc.data['end']]
            for point in points:
                self.assertAlmostEqual(point.x, 0.0)


class ProfileTests(unittest.TestCase):
    def test_circle_profile_center_normal_radius(self):
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((10.0, 20.0, 30.0), frame_axes, 1.0)
        profile = builder._circle_profile(
            frame.point(0.0, geometry.leg_tip_y, geometry.r_leg),
            frame.vector(0.0, -1.0, 0.0), geometry.d / 2.0, 1.0)
        # CreateDisk 的椭圆：圆心 = 腿端，法向 = 路径起始切线，半径 = d/2。
        ellipse = profile.disk_ellipse
        self.assertEqual(ellipse.kind, 'circle')
        self.assertAlmostEqual(ellipse.data['radius'], geometry.d / 2.0)
        # 放置中心 (10, 20, 30) + 腿端（世界 z=115、世界 y=−66）。
        center = ellipse.data['center']
        self.assertAlmostEqual(center.x, 10.0)
        self.assertAlmostEqual(center.y, 20.0 - geometry.r_leg)
        self.assertAlmostEqual(center.z, 30.0 + geometry.leg_tip_y)
        # 局部 −Y（开口方向的反向 = 路径起始切线）= 世界 −Z。
        normal = ellipse.data['normal']
        self.assertAlmostEqual(normal.y, 0.0)
        self.assertAlmostEqual(normal.z, -1.0)
        # 整圆盘直接作为 profile，不再包 ParityRegion。
        self.assertEqual(profile.boundary_type, CurveVector.eBOUNDARY_TYPE_Outer)

    def test_sweep_receives_profile_and_path(self):
        SolidUtil.calls = []
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 90.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        body = builder.build_u_bolt_body(frame, geometry, _MODEL, 1.0)
        self.assertIsNotNone(body)
        sweeps = [call for call in SolidUtil.calls if call[0] == 'sweep']
        self.assertEqual(len(sweeps), 1)
        kinds = [item.kind for item in sweeps[0][2]]
        self.assertEqual(kinds, ['line', 'arc', 'line'])

    def test_vertical_angle_rotates_path(self):
        """竖直管（管轴 +Z）+ 90°：开口方向 = 世界 +Y。

        竖直管时**世界 z 是管轴**，基准方向退回世界 +X，故 90° 对应开口朝
        世界 +Y：两腿分列 ``x = ∓C/2``，整条路径落在 **y = D 平面**内（垂直于
        管轴的那个平面；U 型螺栓的两条腿沿开口方向伸出，本身就与管轴垂直）。
        """
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((0.0, 0.0, 1.0), 90.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        path = builder._u_bolt_path(frame, geometry, 1.0)
        first = _points_of(path[0])[0]
        self.assertAlmostEqual(abs(first.x), geometry.r_leg)
        self.assertAlmostEqual(first.y, geometry.leg_tip_y)
        self.assertAlmostEqual(first.z, 0.0)
        # 沿开口方向的投影只出现在 [弯弧最低点, 腿端] 区间内（竖直管时即为世界 y）。
        normal = frame.ey
        for primitive in path:
            points = _points_of(primitive)
            if points is None:
                arc = primitive.payload
                points = [arc.data['start'], arc.data['middle'],
                          arc.data['end']]
            for point in points:
                projection = (point.x * normal[0] + point.y * normal[1]
                              + point.z * normal[2])
                self.assertGreaterEqual(projection, geometry.arc_bottom_y - 1e-9)
                self.assertLessEqual(projection, geometry.leg_tip_y + 1e-9)


class NutTests(unittest.TestCase):
    def test_hex_corners(self):
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        SolidUtil.calls = []
        body = builder.build_nut_body(frame, geometry, 1.0,
                                      geometry.nuts[0][1],
                                      geometry.nuts[0][2], _MODEL, 1.0)
        self.assertIsNotNone(body)
        sweeps = [call for call in SolidUtil.calls if call[0] == 'sweep']
        self.assertEqual(len(sweeps), 1)
        hexagon = sweeps[0][1][0]
        corners = [item.payload.StartPoint for item in hexagon]
        self.assertEqual(len(corners), 6)
        # 外接圆半径 = 对边 / (2 cos30°)。
        circumradius = geometry.nut_across_flats / (2.0 * math.cos(math.pi / 6.0))
        # 螺母中心 = 放置中心 + 本地 (0, 0, ±C/2)；水平管（管轴 +X、开口 +Z）时
        # 就是世界 (0, ∓C/2, 下底面标高)。
        center = (0.0, -geometry.r_leg, geometry.nuts[0][1])
        for point in corners:
            # 六个顶点都落在螺母下底面（世界 z = 下底面标高）。
            self.assertAlmostEqual(point.z, geometry.nuts[0][1], places=9)
            # 六个顶点到螺母中心的距离都等于外接圆半径。
            offset = (point.x - center[0], point.y - center[1],
                      point.z - center[2])
            self.assertAlmostEqual(
                math.sqrt(sum(component * component for component in offset)),
                circumradius, places=9)
        # 对边宽：正六边形的相邻顶点间距 = 外接圆半径，而对边距 = 2×外接圆半径
        # × cos30°（即 1.5d）。
        sides = [math.dist(corners[index].as_tuple(),
                           corners[(index + 1) % 6].as_tuple())
                 for index in range(6)]
        self.assertAlmostEqual(sides[0], circumradius, places=6)
        self.assertAlmostEqual(
            max(math.dist(corners[index].as_tuple(),
                          corners[(index + 3) % 6].as_tuple())
                for index in range(6)),
            2.0 * circumradius, places=6)
        self.assertAlmostEqual(2.0 * circumradius * math.cos(math.pi / 6.0),
                               geometry.nut_across_flats, places=6)

    def test_nut_bore_subtracted(self):
        """螺母必须布尔减去中心通孔，孔径 = d + 2×间隙。"""
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        SolidUtil.calls = []
        builder.build_nut_body(frame, geometry, -1.0, geometry.nuts[1][1],
                               geometry.nuts[1][2], _MODEL, 1.0)
        cutters = [call for call in SolidUtil.calls if call[0] == 'subtract']
        self.assertEqual(len(cutters), 1)
        cutter = cutters[0][2][0][1]
        detail = cutter[1]
        self.assertAlmostEqual(detail.radius1, geometry.hole_radius)
        # 通孔沿腿轴贯穿螺母上下两端，各留贯穿余量。水平管时"腿轴方向"是世界
        # z、螺母所在腿的横向位置是世界 y = +C/2（sign = −1 那条腿）。
        self.assertAlmostEqual(detail.start.y, geometry.r_leg)
        self.assertAlmostEqual(detail.end.y, geometry.r_leg)
        low = geometry.nuts[1][1] - geom.THROUGH_MARGIN_MM
        high = geometry.nuts[1][2] + geom.THROUGH_MARGIN_MM
        self.assertAlmostEqual(detail.start.z, low)
        self.assertAlmostEqual(detail.end.z, high)

    def test_temp_cylinder_is_cleaned_up(self):
        """**回归测试**：螺母通孔的临时圆柱元素必须"入库 → 取体 → 删除"。

        早期版本只 ``ToElement`` 就再没管过它——每建一颗螺母泄漏一个原生元素，
        每放置一副管卡泄漏 4 个，多次放置后会在原生层崩（access violation）。
        """
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        SolidUtil.calls = []
        EditElementHandle.created_handles = []
        builder.build_nut_body(frame, geometry, 1.0, geometry.nuts[0][1],
                               geometry.nuts[0][2], _MODEL, 1.0)
        handles = EditElementHandle.created_handles
        self.assertEqual(len(handles), 1, '每颗螺母应只造 1 个临时圆柱元素')
        temp = handles[0]
        self.assertTrue(temp.added, '临时元素必须先入库')
        self.assertTrue(temp.deleted, '临时元素必须被删除（否则泄漏原生元素）')

    def test_four_nuts_build_and_clean_four_temp_cylinders(self):
        """4 颗螺母 = 4 个临时圆柱，全部建完即删，不留残留。"""
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        EditElementHandle.created_handles = []
        for _index, low, high in geometry.nuts:
            for sign in (1.0, -1.0):
                builder.build_nut_body(frame, geometry, sign, low, high,
                                       _MODEL, 1.0)
        handles = EditElementHandle.created_handles
        self.assertEqual(len(handles), 4)
        for handle in handles:
            self.assertTrue(handle.added)
            self.assertTrue(handle.deleted)

    def test_four_nuts_built(self):
        """整组应产生 1 个 U 型螺栓 + 4 颗螺母 = 5 个零件、5 次扫掠。"""
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        SolidUtil.calls = []
        parts = [builder.build_u_bolt_body(frame, geometry, _MODEL, 1.0)]
        for _index, low, high in geometry.nuts:
            for sign in (1.0, -1.0):
                parts.append(builder.build_nut_body(frame, geometry, sign,
                                                    low, high, _MODEL, 1.0))
        self.assertEqual(len(parts), 5)
        sweeps = [call for call in SolidUtil.calls if call[0] == 'sweep']
        self.assertEqual(len(sweeps), 5)
        subtracts = [call for call in SolidUtil.calls if call[0] == 'subtract']
        self.assertEqual(len(subtracts), 4)


class SweepValidationTests(unittest.TestCase):
    """``_body_from_sweep`` 必须拒绝"退化 / 无效实体"，不能静默接受。"""

    class _Body(object):
        def __init__(self, valid=True):
            self.IsValid = valid

    class _Model(object):
        pass

    def setUp(self):
        self._real = SolidUtil.Create.BodyFromSweep

    def tearDown(self):
        SolidUtil.Create.BodyFromSweep = self._real

    def _profile_and_path(self):
        geometry = geom.build_geometry(100)
        frame_axes = geom.placement_frame((1.0, 0.0, 0.0), 0.0)
        frame = builder._Frame((0.0, 0.0, 0.0), frame_axes, 1.0)
        path = builder._u_bolt_path(frame, geometry, 1.0)
        profile = builder._circle_profile(frame.point(0.0, geometry.leg_tip_y,
                                                      geometry.r_leg),
                                          frame.vector(0.0, -1.0, 0.0),
                                          geometry.d / 2.0, 1.0)
        return profile, path

    def test_accepts_valid_body(self):
        body = self._Body(True)
        SolidUtil.Create.BodyFromSweep = staticmethod(lambda *a: (0, body))
        profile, path = self._profile_and_path()
        self.assertIs(builder._body_from_sweep(
            profile, path, self._Model(), (0, 0, 0), (0, 0, 1), 'U型螺栓'), body)

    def test_rejects_invalid_body(self):
        """实体自称 IsValid=False（退化几何）时必须抛错，不能写进模型。"""
        body = self._Body(False)
        SolidUtil.Create.BodyFromSweep = staticmethod(lambda *a: (0, body))
        profile, path = self._profile_and_path()
        with self.assertRaises(RuntimeError) as context:
            builder._body_from_sweep(profile, path, self._Model(), (0, 0, 0),
                                     (0, 0, 1), 'U型螺栓')
        self.assertIn('无效', str(context.exception))

    def test_rejects_failing_status(self):
        """状态码非 0 时不能接受（哪怕实体非空）。"""
        body = self._Body(True)
        SolidUtil.Create.BodyFromSweep = staticmethod(lambda *a: (1, body))
        profile, path = self._profile_and_path()
        with self.assertRaises(RuntimeError):
            builder._body_from_sweep(profile, path, self._Model(), (0, 0, 0),
                                     (0, 0, 1), 'U型螺栓')

    def test_rejects_missing_body(self):
        SolidUtil.Create.BodyFromSweep = staticmethod(lambda *a: (0, None))
        profile, path = self._profile_and_path()
        with self.assertRaises(RuntimeError):
            builder._body_from_sweep(profile, path, self._Model(), (0, 0, 0),
                                     (0, 0, 1), 'U型螺栓')

    def test_ten_arg_fallback_uses_real_arguments(self):
        """六参抛 TypeError 时回退十参，且十参必须给实参（不塞 None）。"""
        calls = []

        def fake(profile, path, model, *rest):
            calls.append(rest)
            if len(rest) == 3:
                raise TypeError('six-arg form unsupported')
            return (0, self._Body(True))

        SolidUtil.Create.BodyFromSweep = staticmethod(fake)
        profile, path = self._profile_and_path()
        body = builder._body_from_sweep(profile, path, self._Model(),
                                        (0, 0, 0), (0, 0, 1), 'U型螺栓')
        self.assertTrue(body.IsValid)
        self.assertEqual(len(calls), 2)
        fallback = calls[1]
        self.assertEqual(len(fallback), 7)          # up, 0.0, 1.0, start
        self.assertNotIn(None, fallback, '十参回退不允许塞 None')
        for value in fallback:
            self.assertIsNotNone(value)


class BuildClampTests(unittest.TestCase):
    def test_cell_assembly_order(self):
        """落图顺序：建组单元 → 逐个加子元素 → AddChildComplete → AddToModel。"""
        NormalCellHeaderHandler.cells = []
        SolidUtil.calls = []
        cell, message = builder.build_clamp((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                            dn=100, angle_deg=0.0)
        self.assertTrue(cell.added)
        self.assertTrue(cell.completed)
        self.assertEqual(len(cell.children), 5)
        self.assertEqual(cell.name, builder.CELL_NAME)
        self.assertIn('DN100', message)
        self.assertIn('开口朝上', message)

    def test_rejects_2d_model(self):
        global _MODEL
        original = _MODEL
        _MODEL = _FakeModel(is_3d=False)
        try:
            with self.assertRaises(ValueError):
                builder.build_clamp((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), dn=100)
        finally:
            _MODEL = original

    def test_rejects_zero_axis(self):
        with self.assertRaises(ValueError):
            builder.build_clamp((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), dn=100)

    def test_insulation_note(self):
        _cell, message = builder.build_clamp((0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                                             dn=100, insulation_mm=50.0)
        self.assertIn('保温', message)


if __name__ == '__main__':
    unittest.main(verbosity=2)
