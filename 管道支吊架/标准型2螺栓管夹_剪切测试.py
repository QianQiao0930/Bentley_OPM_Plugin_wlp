# -*- coding: utf-8 -*-
"""标准型 2 螺栓管夹（剪切建模）独立测试脚本。

运行后点取管道中心，即按 DN 查表生成一组「管架本体」毛坯；可连续点取，
右键退出（保留已生成模型）。管轴固定为全局 X，截面位于 YZ 平面。尺寸单位 mm。

G 列形如 "t x w"（板厚 x 板宽）：t 取 × 前的厚度值，w 取 × 后的值。

本阶段做管架本体的五步：
  1) 圆柱：以点击点为中心，直径 = A + 2t，轴向长 = w；
  2) 长方体：与圆柱布尔并；厚度 = w（与圆柱一致），
     长度 = A + 2D + 2t（沿 Y），宽度 = C + 2t（沿 Z）；
  3) 剪切截面：直径 A 的圆 + 长度 A + 2t + 2D、宽度 C 的矩形（沿 Y/Z），
     沿轴向贯穿，从本体中减去，得到管夹状；
  4) 上下两对耳板开螺栓孔：孔心距中心 = B（沿 Y），孔径 = F 数字 + 2，
     沿 Z 贯穿两片耳板；
  5) 每个螺栓孔穿一套简化紧固件（螺杆 + 六角头 + 六角螺母，独立实体）；
  6) 整组绕管轴（全局 X）以点击点为中心旋转 ROTATE_ANGLE_DEG（默认 45°）。

DN100 例（表 1：A=117, B=84, C=20, D=50, F=M16, G=8 x 50）：
  圆柱 φ133（=117+2×8）、轴向长 50；长方体 233×36×50；
  剪切截面 = φ117 圆 + 233×20 矩形；螺栓孔 φ18（16+2），孔心 Y=±84；
  M16 螺栓：螺杆 φ16 贯穿，+Z 侧六角头（对边 24、高 10），
  -Z 侧六角螺母（对边 24、高 13），螺杆穿出 4。
"""

import math
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# 测试用管径（表 1）：改这里即可切换 DN。
DN = 100

# 整组构件绕管轴（全局 X）以点击点为中心的旋转角（度）。
ROTATE_ANGLE_DEG = 45.0

# 表 1：DN -> 尺寸。t = G 列 × 前的板厚，w = G 列 × 后的板宽。
TABLE = {
    15:  {'nps': '1/2"',   'A': 25,  'B': 28,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    20:  {'nps': '3/4"',   'A': 30,  'B': 30,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    25:  {'nps': '1"',     'A': 37,  'B': 34,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    32:  {'nps': '1 1/4"', 'A': 45,  'B': 38,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    40:  {'nps': '1 1/2"', 'A': 51,  'B': 41,  'C': 12, 'D': 30,  'F': 'M10', 't': 5,  'w': 30},
    50:  {'nps': '2"',     'A': 63,  'B': 52,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    65:  {'nps': '2 1/2"', 'A': 79,  'B': 60,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    80:  {'nps': '3"',     'A': 92,  'B': 66,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    90:  {'nps': '3 1/2"', 'A': 105, 'B': 73,  'C': 15, 'D': 40,  'F': 'M12', 't': 6,  'w': 40},
    100: {'nps': '4"',     'A': 117, 'B': 84,  'C': 20, 'D': 50,  'F': 'M16', 't': 8,  'w': 50},
    125: {'nps': '5"',     'A': 143, 'B': 97,  'C': 20, 'D': 50,  'F': 'M16', 't': 8,  'w': 50},
    150: {'nps': '6"',     'A': 171, 'B': 116, 'C': 25, 'D': 60,  'F': 'M20', 't': 10, 'w': 60},
    200: {'nps': '8"',     'A': 222, 'B': 141, 'C': 25, 'D': 60,  'F': 'M20', 't': 10, 'w': 60},
    250: {'nps': '10"',    'A': 276, 'B': 176, 'C': 25, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    300: {'nps': '12"',    'A': 328, 'B': 202, 'C': 25, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    350: {'nps': '14"',    'A': 359, 'B': 217, 'C': 30, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    400: {'nps': '16"',    'A': 409, 'B': 242, 'C': 30, 'D': 75,  'F': 'M24', 't': 12, 'w': 75},
    450: {'nps': '18"',    'A': 460, 'B': 268, 'C': 35, 'D': 75,  'F': 'M24', 't': 16, 'w': 75},
    500: {'nps': '20"',    'A': 511, 'B': 301, 'C': 35, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    550: {'nps': '22"',    'A': 563, 'B': 327, 'C': 35, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    600: {'nps': '24"',    'A': 613, 'B': 352, 'C': 40, 'D': 90,  'F': 'M30', 't': 16, 'w': 90},
    650: {'nps': '26"',    'A': 663, 'B': 387, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
    700: {'nps': '28"',    'A': 714, 'B': 412, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
    750: {'nps': '30"',    'A': 765, 'B': 438, 'C': 50, 'D': 110, 'F': 'M36', 't': 20, 'w': 110},
}

_THROUGH_MARGIN_MM = 5.0
_CELL_NAME = 'STD_2BOLT_CLAMP_TEST'

# 简化紧固件比例（精度不要求细致，能看出螺栓/螺母即可）。
_HEX_ACROSS_FLATS_RATIO = 1.5   # 六角对边 ≈ 1.5 d（M16→24）。
_BOLT_HEAD_HEIGHT_RATIO = 0.625  # 头高 ≈ 0.625 d（M16→10）。
_NUT_HEIGHT_RATIO = 0.8          # 螺母高 ≈ 0.8 d（M16→13）。
_BOLT_TIP_EXTRA_MM = 4.0         # 螺杆穿出螺母的长度。

_active_tool = None


def _row(dn):
    if dn not in TABLE:
        raise ValueError('表 1 中无 DN%d。' % dn)
    return TABLE[dn]


def _check(status, operation):
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        code = int(status)
    except (TypeError, ValueError):
        raise RuntimeError('%s未返回有效状态码：%r' % (operation, status))
    if code != 0:
        raise RuntimeError('%s失败，状态：%s' % (operation, status))


def _cylinder_between(model, start, end, radius, uor):
    # 使用真正的圆柱曲面，不用多边形近似圆。
    detail = DgnConeDetail(start, end, radius * uor, radius * uor, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    _check(DraftingElementSchema.ToElement(element, primitive, None, model),
           '创建圆柱')
    status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
    _check(status, '圆柱转内核体')
    return body


def _box_body(model, point, direction, x0, x1, y0, y1, z0, z1):
    points = DPoint3dArray()
    for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
        points.append(point(x0, y, z))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建长方体截面')
    _check(profile.AddToModel(), '创建长方体临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '长方体截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除长方体临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(x1 - x0, 0.0, 0.0)),
           '拉伸长方体')
    return body


def _cutter_section(model, point, direction, uor, row):
    """管夹状剪切截面：直径 A 的圆 + 长度 A+2t+2D、宽度 C 的矩形（沿 Y/Z）。

    整体沿管轴（本地 X）贯穿，比本体两端各多出余量以保证布尔干净。
    """
    a = float(row['A'])
    c = float(row['C'])
    d = float(row['D'])
    thickness = float(row['t'])
    width = float(row['w'])
    half = width / 2.0 + _THROUGH_MARGIN_MM
    bore = _cylinder_between(model, point(-half, 0.0, 0.0),
                             point(half, 0.0, 0.0), a / 2.0, uor)
    length = a + 2.0 * thickness + 2.0 * d + 2.0 * _THROUGH_MARGIN_MM
    box = _box_body(model, point, direction, -half, half,
                    -length / 2.0, length / 2.0, -c / 2.0, c / 2.0)
    return [bore, box]


def _hex_body(model, point, direction, x, y, z0, z1, across_flats):
    """沿本地 Z 拉伸的六角棱柱（六角头 / 螺母），对边尺寸为 across_flats。"""
    radius = across_flats / (2.0 * math.cos(math.pi / 6.0))
    points = DPoint3dArray()
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        points.append(point(x + radius * math.cos(theta),
                            y + radius * math.sin(theta), z0))
    profile = EditElementHandle()
    _check(ShapeHandler.CreateShapeElement(profile, None, points, True, model),
           '创建六角截面')
    _check(profile.AddToModel(), '创建六角临时截面')
    try:
        status, body = SolidUtil.Convert.ElementToBody(profile, True, True, False)
        _check(status, '六角截面转内核体')
    finally:
        _check(profile.DeleteFromModel(), '删除六角临时截面')
    _check(SolidUtil.Modify.SweepBody(body, direction(0.0, 0.0, z1 - z0)),
           '拉伸六角头 / 螺母')
    return body


def _fastener_bodies(model, point, direction, uor, x, y, seat, bolt_dia,
                     hole_radius):
    """一套简化紧固件：贯穿的螺杆 + 一侧六角螺栓头 + 另一侧六角螺母。

    ``seat`` 为耳板外侧面的本地 Z 坐标；螺栓头在 +Z 侧、螺母在 -Z 侧。
    """
    head_height = bolt_dia * _BOLT_HEAD_HEIGHT_RATIO
    nut_height = bolt_dia * _NUT_HEIGHT_RATIO
    across = bolt_dia * _HEX_ACROSS_FLATS_RATIO
    shank = _cylinder_between(
        model, point(x, y, -seat - nut_height - _BOLT_TIP_EXTRA_MM),
        point(x, y, seat), bolt_dia / 2.0, uor)
    head = _hex_body(model, point, direction, x, y, seat,
                     seat + head_height, across)
    nut = _hex_body(model, point, direction, x, y, -seat - nut_height,
                    -seat, across)
    bits = ISolidKernelEntityPtrArray()
    bits.append(_cylinder_between(
        model, point(x, y, -seat - nut_height - _THROUGH_MARGIN_MM),
        point(x, y, -seat + _THROUGH_MARGIN_MM), hole_radius, uor))
    _check(SolidUtil.Modify.BooleanSubtract(nut, bits), '螺母中心孔')
    return [('螺杆', shank), ('六角螺栓头', head), ('六角螺母', nut)]


def _assembly_element(model, bodies):
    """把管架本体装入 Cell 后一次写入模型。"""
    cell = EditElementHandle()
    # 此API返回None，不是状态码；后续加入子元素、完成及写入均检查状态。
    NormalCellHeaderHandler.CreateOrphanCellElement(
        cell, _CELL_NAME, True, model)
    for name, body in bodies:
        child = EditElementHandle()
        _check(SolidUtil.Convert.BodyToElement(child, body, None, model),
               name + '转模型元素')
        _check(NormalCellHeaderHandler.AddChildElement(cell, child),
               name + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成管架单元')
    _check(cell.AddToModel(), '写入管架单元')
    return cell


def build_at_center(center):
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    row = _row(DN)
    a = float(row['A'])
    c = float(row['C'])
    d = float(row['D'])
    thickness = float(row['t'])
    width = float(row['w'])

    cylinder_dia = a + 2.0 * thickness
    cylinder_radius = cylinder_dia / 2.0
    box_length = a + 2.0 * d + 2.0 * thickness
    box_width = c + 2.0 * thickness
    values = (a, c, d, thickness, width, cylinder_dia, box_length, box_width)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('尺寸参数必须是有限的正数。')

    uor = model.GetModelInfo().GetUorPerMeter() / 1000.0

    # 绕管轴（全局 X）以点击点为中心旋转：本地 (x, y, z) → 世界。
    angle = math.radians(ROTATE_ANGLE_DEG)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def point(x, y, z):
        ry = y * cos_a - z * sin_a
        rz = y * sin_a + z * cos_a
        return DPoint3d(center.x + x * uor, center.y + ry * uor,
                        center.z + rz * uor)

    def direction(x, y, z):
        ry = y * cos_a - z * sin_a
        rz = y * sin_a + z * cos_a
        return DVec3d(x * uor, ry * uor, rz * uor)

    # 1) 圆柱：轴向沿全局 X，长 = w（即长方体厚度）。
    half_w = width / 2.0
    ring = _cylinder_between(model, point(-half_w, 0.0, 0.0),
                             point(half_w, 0.0, 0.0), cylinder_radius, uor)
    # 2) 长方体：与圆柱同厚 w（沿 X），长 box_length（沿 Y），宽 box_width（沿 Z）。
    box = _box_body(model, point, direction, -half_w, half_w,
                    -box_length / 2.0, box_length / 2.0,
                    -box_width / 2.0, box_width / 2.0)

    parts = ISolidKernelEntityPtrArray()
    parts.append(box)
    _check(SolidUtil.Modify.BooleanUnion(ring, parts), '长方体与圆柱布尔并')

    # 3) 剪切截面（φA 圆 + 长度 A+2t+2D、宽度 C 的矩形）贯穿减去，成管夹状。
    cutters = ISolidKernelEntityPtrArray()
    for body in _cutter_section(model, point, direction, uor, row):
        cutters.append(body)
    _check(SolidUtil.Modify.BooleanSubtract(ring, cutters), '剪切截面裁切管架本体')

    # 4) 上下两对耳板开螺栓孔：孔心距中心 B（沿 Y），孔径 = F 数字 + 2，沿 Z 贯穿。
    f_number = int(''.join(ch for ch in row['F'] if ch.isdigit()))
    hole_radius = (f_number + 2.0) / 2.0
    hole_half = box_width / 2.0 + _THROUGH_MARGIN_MM
    holes = ISolidKernelEntityPtrArray()
    for sign in (1.0, -1.0):
        y = sign * float(row['B'])
        holes.append(_cylinder_between(model, point(0.0, y, -hole_half),
                                       point(0.0, y, hole_half),
                                       hole_radius, uor))
    _check(SolidUtil.Modify.BooleanSubtract(ring, holes), '耳板开螺栓孔')

    bodies = [('管架本体', ring)]
    # 5) 每个螺栓孔穿一套简化紧固件（独立实体，与本体分开）。
    for sign in (1.0, -1.0):
        y = sign * float(row['B'])
        bodies.extend(_fastener_bodies(model, point, direction, uor, 0.0, y,
                                       box_width / 2.0, f_number, hole_radius))
    result = _assembly_element(model, bodies)

    message = ('已生成标准型2螺栓管夹（DN%d，%s，%s）：'
               '圆柱 φ%.1f（A+2t=%.0f+2×%.0f）、轴向长 %.0f；'
               '长方体 长%.1f（A+2D+2t）×宽%.1f（C+2t）×厚%.0f；'
               '剪切截面 φ%.0f（A） + 长%.1f×宽%.0f（C）矩形；'
               '螺栓孔 φ%.0f（%s+2），孔心距中心 %.0f（B）；'
               '每孔配 1 套简化螺栓（%s：螺杆 φ%.0f + 六角头 + 六角螺母）；'
               '整组绕管轴旋转 %.0f°。'
               % (DN, row['nps'], row['F'], cylinder_dia, a, thickness, width,
                  box_length, box_width, width, a, box_length, c,
                  f_number + 2.0, row['F'], float(row['B']),
                  row['F'], float(f_number), ROTATE_ANGLE_DEG))
    print(message)
    NotificationManager.OutputPrompt(message + '继续点取中心，右键退出。')
    return result


class Std2BoltClampCutTestTool(DgnPrimitiveTool):
    def __init__(self):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.m_self = self

    def _GetToolName(self, name):
        return WString('Std2BoltClampBooleanCutTest')

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt(
            '标准型2螺栓管夹剪切测试：点取管道中心（管轴固定为全局 X，'
            '当前 DN%d）；右键退出。' % DN)

    def _OnDataButton(self, event):
        try:
            build_at_center(event.GetPoint())
        except Exception as error:
            print(traceback.format_exc())
            NotificationManager.OutputPrompt('生成失败：%s' % error)
        return True

    def _OnResetButton(self, event):
        PyCommandState.StartDefaultCommand()
        return True

    def _OnRestartTool(self):
        PyMain()


def PyMain():
    global _active_tool
    _active_tool = Std2BoltClampCutTestTool()
    _active_tool.InstallTool()


if __name__ == '__main__':
    PyMain()
