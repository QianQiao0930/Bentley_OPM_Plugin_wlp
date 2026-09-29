# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为 A1 U 型管卡的 Bentley 建模库供入口插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载运行。
# =============================================================================
"""A1 U 型管卡 —— Bentley（MSPy）建模：扫掠 U 型螺栓 + 每腿 2 颗六角螺母。

调用顺序（由入口插件 ``A1-[U型管卡].py`` 负责）：

1. :func:`build_clamp`：按放置点 / 管轴 / 角度 / 管径生成整组，写入活动模型，
   返回 ``(单元句柄, 提示文本)``；
2. 由入口决定是否调用 :func:`attach_support_items` 写公共支吊架库（ItemType）。

建模口径见 ``U型管卡_几何.py`` 的模块文档。要点：

* **U 型螺栓 = 一条扫掠体**：先建扫掠路径（+Y 侧直腿 → 与直腿相切的 180° 弯弧
  → −Y 侧直腿），再用**螺栓公称直径**做圆截面沿路径扫掠（``BodyFromSweep``），
  于是弯弧段自然是一个圆环面，而不是折线拼出来的假圆弧；
* **螺母 = 6 颗？不，4 颗**：两条腿各 2 颗（背帽），每颗是一个六角棱柱（对边
  1.5d、高 0.8d）沿腿轴拉伸后再布尔减去中心通孔；
* 放置点 = 示意图中心 = **管道中心**；本地 ``X`` = 管轴、``Y`` = 开口方向。

写库策略与 A2 / E1 一致：**调用方（入口插件）决定何时写库**，本模块只出几何。
"""

from __future__ import division

import math
import os
import sys
import time
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 纯数据 / 几何模块与本文件同目录。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import U型管卡_几何 as geom  # noqa: E402


#: 组单元名（普通单元，与其它支吊架一致）。
CELL_NAME = 'A1_U_BOLT_CLAMP'


# ---------------------------------------------------------------------------
# 公共库契约
# ---------------------------------------------------------------------------

SUPPORT_TYPE = 'A1-[U型管卡]'
SUPPORT_CODE = 'A1_U_BOLT_CLAMP'


def _log(message):
    """写调试日志（与入口插件同一份日志文件）。"""
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(_HERE)), '模块', '日志',
                            'U型管卡_debug_log.txt')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'),
                                        message))
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _step(message):
    """建模分步打点。

    原生层崩溃（access violation）不会留 Python 栈，所以每一步**先写日志再干活**：
    崩溃后日志的最后一行就是崩点之前完成到的位置。高频操作（4 颗螺母）只在开始
    与结束各记一条，避免刷爆日志。
    """
    _log(message)


# ---------------------------------------------------------------------------
# 基础原语
# ---------------------------------------------------------------------------


def _check(status, operation):
    """把 MSPy 的状态码（可能是元组）转成「失败即抛中文异常」。"""
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        code = int(status)
    except (TypeError, ValueError):
        raise RuntimeError('%s未返回有效状态码：%r' % (operation, status))
    if code != 0:
        raise RuntimeError('%s失败，状态：%s' % (operation, status))


def _dpoint(point):
    """把 ``DPoint3d`` 或 ``(x, y, z)`` 三元组统一成 ``DPoint3d``。"""
    if point is None:
        return None
    if hasattr(point, 'x') and hasattr(point, 'y') and hasattr(point, 'z'):
        return DPoint3d.From(point.x, point.y, point.z)
    return DPoint3d(point[0], point[1], point[2])


def _dvec(vector):
    """把 ``DVec3d`` 或 ``(x, y, z)`` 三元组统一成 ``DVec3d``。"""
    if vector is None:
        return None
    if hasattr(vector, 'x') and hasattr(vector, 'y') and hasattr(vector, 'z'):
        return DVec3d.From(vector.x, vector.y, vector.z)
    return DVec3d(vector[0], vector[1], vector[2])


def _open_boundary_type():
    for name in ('eBOUNDARY_TYPE_Open', 'eBOUNDARY_TYPE_Outer'):
        value = getattr(CurveVector, name, None)
        if value is not None:
            return value
    return CurveVector.eBOUNDARY_TYPE_Outer


def _uor_per_mm(dgn_model):
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


class _Frame(object):
    """把局部 ``(x, y, z)`` 映射到世界 UOR 的坐标架。

    ``x`` = 管轴、``y`` = 开口方向、``z`` = 第三轴（三者右手正交）。
    映射为 ``O + x·ex + y·ey + z·ez``（**每个局部分量乘自己那根轴**）。
    """

    def __init__(self, center_mm, axes, scale):
        self.center = tuple(float(value) for value in center_mm)
        self.ex = tuple(axes[0])
        self.ey = tuple(axes[1])
        self.ez = tuple(axes[2])
        self.scale = float(scale)

    def point(self, x=0.0, y=0.0, z=0.0):
        return DPoint3d(
            (self.center[0] + x * self.ex[0] + y * self.ey[0]
             + z * self.ez[0]) * self.scale,
            (self.center[1] + x * self.ex[1] + y * self.ey[1]
             + z * self.ez[1]) * self.scale,
            (self.center[2] + x * self.ex[2] + y * self.ey[2]
             + z * self.ez[2]) * self.scale)

    def vector(self, x=0.0, y=0.0, z=0.0):
        return DVec3d((x * self.ex[0] + y * self.ey[0] + z * self.ez[0])
                      * self.scale,
                      (x * self.ex[1] + y * self.ey[1] + z * self.ez[1])
                      * self.scale,
                      (x * self.ex[2] + y * self.ey[2] + z * self.ez[2])
                      * self.scale)

    def world(self, x=0.0, y=0.0, z=0.0):
        return (self.center[0] + x * self.ex[0] + y * self.ey[0]
                + z * self.ez[0],
                self.center[1] + x * self.ex[1] + y * self.ey[1]
                + z * self.ez[1],
                self.center[2] + x * self.ex[2] + y * self.ey[2]
                + z * self.ez[2])


# ---------------------------------------------------------------------------
# 扫掠 U 型螺栓
# ---------------------------------------------------------------------------


def _circle_profile(center, normal, radius, uor):
    """垂直于 ``normal`` 的整圆截面（``CreateDisk`` 是真圆，不是多边形近似）。

    与 ``水平弯头耳轴/水平弯头耳轴.py`` 的 ``_disk_profile`` 同一写法（该写法已在
    OPM 实测通过）：**整圆盘直接作为 profile**，不要再包一层 ParityRegion。
    """
    ellipse = DEllipse3d.FromCenterNormalRadius(_dpoint(center), normal,
                                                radius * uor)
    return CurveVector.CreateDisk(ellipse, CurveVector.eBOUNDARY_TYPE_Outer)


def _u_bolt_path(frame, geometry, uor):
    """构造 U 型螺栓的扫掠路径：直腿 → 与直腿相切的 180° 弯弧 → 直腿。"""
    a = geometry.r_leg
    tip = geometry.leg_tip_y
    bend = geometry.bend_start_y
    path = CurveVector(_open_boundary_type())
    # 起点 = +Y 侧腿端；切线沿 −Y（先朝弯弧走）。
    path.Add(ICurvePrimitive.CreateLine(
        DSegment3d(frame.point(0.0, tip, a), frame.point(0.0, bend, a))))
    # 弯弧：圆心在管轴高度 (y=bend, z=0)、半径 a，自 +Z 侧切点经 −Y 侧扫 180° 到
    # −Z 侧切点。
    #
    # ⚠️ **180° 半圆必须用三点式**（``FromPointsOnArc(起点, 弧上中点, 终点)``），
    # **不能**用 ``FromArcCenterStartEnd(圆心, 起点, 终点)``：后者靠"圆心→起点"与
    # "圆心→终点"两个向量反推圆弧所在平面，而 180° 时这两向量**正对**（和 / 叉积
    # 退化），平面定不出来 → 返回无效椭圆 → 扫掠直接 eERROR（实测）。
    # 全仓库用圆心形式的弧都是 90°（弯头耳轴 / 水箱爬梯圆角 / 灭火器箱圆角），
    # 这里 180° 是唯一例外，故用三点式；中点取弯弧最低点，方向唯一、无歧义。
    arc = DEllipse3d.FromPointsOnArc(frame.point(0.0, bend, a),
                                     frame.point(0.0, bend - a, 0.0),
                                     frame.point(0.0, bend, -a))
    path.Add(ICurvePrimitive.CreateArc(arc))
    path.Add(ICurvePrimitive.CreateLine(
        DSegment3d(frame.point(0.0, bend, -a), frame.point(0.0, tip, -a))))
    return path


def _body_from_sweep(profile, path, dgn_model, center, up_axis, label):
    """``BodyFromSweep`` 的兼容封装，返回**已校验有效**的内核实体。

    签名按仓库两份已实测代码的共同形式优先
    （``(profile, path, model, False, True, False)``：``水平弯头耳轴`` /
    ``水箱爬梯/ladder_lib`` / ``罐壁人孔``），失败再退到带参考向量的十参形式
    （``水平弯头耳轴`` 的 TypeError 回退分支，**全部给实参，不塞 None**）。

    校验照 ``D15-[水平T形架]`` 的"状态码 + 非空"双重检查，并额外要求实体
    ``IsValid``（若该属性存在）：退化路径 / 截面会让内核返回一个"成功但非法"的
    实体，若照单全收就会把非法 SmartSolid 写进模型，多次放置后在原生层炸。
    """
    start = _dpoint(center)
    up = _dvec(up_axis)

    def six_arg():
        return SolidUtil.Create.BodyFromSweep(
            profile, path, dgn_model, False, True, False)

    def ten_arg():
        # 参考向量 / 起止参数 / 路径起点全部给实参（对齐 水平弯头耳轴 的回退分支）。
        return SolidUtil.Create.BodyFromSweep(
            profile, path, dgn_model, False, True, False,
            up, 0.0, 1.0, start)

    last_error = None
    for attempt in (six_arg, ten_arg):
        try:
            result = attempt()
        except Exception as error:
            last_error = error
            continue
        status, body = _sweep_result(result)
        try:
            _check(status, label + '扫掠')
        except RuntimeError as error:
            last_error = error
            continue
        if body is None:
            last_error = RuntimeError('%s：扫掠未返回实体。' % label)
            continue
        return _validate_body(body, label)
    raise RuntimeError('%s扫掠失败（路径 / 截面可能退化）：%s'
                       % (label, last_error))


def _sweep_result(result):
    """从 ``BodyFromSweep`` 的返回值里取出 ``(status, body)``。"""
    if isinstance(result, (tuple, list)):
        if not result:
            return None, None
        if len(result) < 2:
            return result[0], None
        return result[0], result[1]
    # 个别版本直接返回裸实体。
    return 0, result


def _validate_body(body, label):
    """确认扫掠出来的实体有效；无效则抛中文异常（附几何控制点便于排查）。"""
    if body is None:
        raise RuntimeError('%s：扫掠未返回实体（路径 / 截面可能退化）。' % label)
    try:
        valid = bool(body.IsValid)
    except AttributeError:
        return body
    except Exception:
        return body
    if not valid:
        raise RuntimeError('%s：扫掠得到的实体无效（路径 / 截面退化），'
                           '已拒绝写入模型。' % label)
    return body


def build_u_bolt_body(frame, geometry, dgn_model, uor):
    """用**螺栓公称直径**做圆截面、沿 U 型路径扫掠出一个 U 型螺栓实体。"""
    path = _u_bolt_path(frame, geometry, uor)
    # 截面圆心取路径起点（+Y 侧腿端），法向取该点切线（−Y），与路径起点一致。
    profile = _circle_profile(frame.point(0.0, geometry.leg_tip_y,
                                          geometry.r_leg),
                              frame.vector(0.0, -1.0, 0.0),
                              geometry.d / 2.0, uor)
    return _body_from_sweep(profile, path, dgn_model,
                            frame.world(0.0, geometry.leg_tip_y,
                                        geometry.r_leg),
                            frame.vector(0.0, 0.0, 1.0), 'U型螺栓')


# ---------------------------------------------------------------------------
# 六角螺母
# ---------------------------------------------------------------------------


def _build_hex_body(dgn_model, frame, x, y_low, y_high, z_center,
                    across_flats, uor, label='六角螺母'):
    """沿腿轴（本地 ``Y``）拉伸的六角棱柱：对边宽 ``across_flats``。"""
    radius = across_flats / (2.0 * math.cos(math.pi / 6.0))
    outer = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    corners = []
    for index in range(6):
        theta = math.pi / 6.0 + index * math.pi / 3.0
        corners.append(frame.point(x + radius * math.cos(theta), y_low,
                                   z_center + radius * math.sin(theta)))
    for index in range(6):
        outer.Add(ICurvePrimitive.CreateLine(
            DSegment3d(corners[index], corners[(index + 1) % 6])))
    # 手绘多边形截面**必须**包一层 ParityRegion（与 水箱爬梯/ladder_lib 同写法），
    # 而整圆盘则直接作为 profile（见 _circle_profile）。
    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
    profile.Add(outer)
    return _body_from_sweep(profile,
                            _line_path(frame.point(x, y_low, z_center),
                                       frame.point(x, y_high, z_center)),
                            dgn_model, frame.world(x, y_low, z_center),
                            frame.vector(0.0, 0.0, 1.0), label)


def _line_path(start, end):
    path = CurveVector(_open_boundary_type())
    path.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
    return path


def _cylinder_between(model, start, end, radius_mm, uor):
    """临时圆柱元素 → 内核实体，**用完立刻删掉临时元素**。

    原生层元素不会自己回收：``ToElement`` 出来的临时圆柱若不删除，每建一颗螺母
    就泄漏一个原生元素（每放置一副管卡泄漏 4 个），多次放置后容易在模型重绘 /
    内存整理时崩在原生层（access violation）——A1 早期版本就是这么写的。

    清理顺序照 A2 / F10 的 ``_box_body``：**入库 → 取体 → 删除**。只读模型
    （参考文件）里入不了库，此时退回"不入库直接取体"（``ElementToBody`` 的第一
    个 ``True`` 是带拷贝，取出的体与临时元素无关，故不删也不影响几何）。
    """
    detail = DgnConeDetail(start, end, radius_mm * uor, radius_mm * uor, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    _check(DraftingElementSchema.ToElement(element, primitive, None, model),
           '创建圆柱')
    in_model = False
    try:
        in_model = int(element.AddToModel()) == 0
    except Exception:
        in_model = False
    try:
        status, body = SolidUtil.Convert.ElementToBody(element, True, True, False)
        _check(status, '圆柱转内核体')
    finally:
        if in_model:
            try:
                _check(element.DeleteFromModel(), '删除临时圆柱')
            except Exception:
                _log('临时圆柱删除失败（忽略，不影响已取出的实体）')
    return body


def build_nut_body(frame, geometry, sign, y_low, y_high, dgn_model, uor):
    """一颗六角螺母：六角棱柱 − 中心通孔（孔径 = 螺栓直径 + 2×间隙）。"""
    body = _build_hex_body(dgn_model, frame, 0.0, y_low, y_high,
                           sign * geometry.r_leg, geometry.nut_across_flats,
                           uor)
    margin = geom.THROUGH_MARGIN_MM
    bore = _cylinder_between(
        dgn_model,
        frame.point(0.0, y_low - margin, sign * geometry.r_leg),
        frame.point(0.0, y_high + margin, sign * geometry.r_leg),
        geometry.hole_radius, uor)
    cutters = ISolidKernelEntityPtrArray()
    cutters.append(bore)
    _check(SolidUtil.Modify.BooleanSubtract(body, cutters), '螺母中心孔')
    return body


# ---------------------------------------------------------------------------
# 单元拼装
# ---------------------------------------------------------------------------


def _body_to_element(body, dgn_model, label):
    element = EditElementHandle()
    _check(SolidUtil.Convert.BodyToElement(element, body, None, dgn_model),
           label + '转模型元素')
    return element


def _assembly_element(dgn_model, parts, cell_name=None):
    """把整组子实体写成一个普通单元（Cell）后落图，返回单元句柄。"""
    cell = EditElementHandle()
    # 该 API 返回 None，不是状态码；后续加入子元素、完成、落图均检查状态码。
    NormalCellHeaderHandler.CreateOrphanCellElement(
        cell, cell_name or CELL_NAME, True, dgn_model)
    for label, body in parts:
        child = _body_to_element(body, dgn_model, label)
        _check(NormalCellHeaderHandler.AddChildElement(cell, child),
               label + '加入单元')
    _check(NormalCellHeaderHandler.AddChildComplete(cell), '完成 U 型管卡单元')
    _check(cell.AddToModel(), '写入 U 型管卡单元')
    return cell


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------


def build_clamp(center_mm, axis, dn=None, angle_deg=None, insulation_mm=0.0,
                note=''):
    """在 ``center_mm``（= **管道中心**）处、绕管轴 ``axis`` 生成一副 A1 U 型管卡。

    ``dn``            表 1 的 DN 键（None 时用 :data:`U型管卡_几何.DEFAULT_DN`）；
    ``angle_deg``     绕管轴的角度（0° = 开口朝上），None 时用默认 0°；
    ``insulation_mm`` 保温厚度：只用于提示，**不放大管卡**（U 型管卡按裸管管径
                      选型，保温管另有加长腿的型式）。
    返回 ``(模型单元, 提示文本)``；提示文本由面板的「生成记录」显示。

    写公共库（ItemType）**不在这里做**，由入口在合适的时机调用
    :func:`attach_support_items`（A2 / E1 的既有策略）。
    """
    model = ISessionMgr.GetActiveDgnModel()
    if not model.Is3d():
        raise ValueError('请在三维模型中运行。')
    dn = geom.DEFAULT_DN if dn is None else dn
    angle = geom.DEFAULT_ANGLE_DEG if angle_deg is None else angle_deg
    angle = geom.normalize_angle(angle)
    geometry = geom.build_geometry(dn)

    frame_axes = geom.placement_frame(axis, angle)
    if frame_axes is None:
        raise ValueError('管轴方向无效（长度为零），无法定位 U 型管卡。')
    uor = _uor_per_mm(model)
    frame = _Frame(center_mm, frame_axes, uor)
    _step('build DN%d @(%.1f, %.1f, %.1f) angle=%g uor=%.6g 内表面半径=%.2f '
          '净空=%s 直腿段=%.1f'
          % (dn, center_mm[0], center_mm[1], center_mm[2], angle, uor,
             geometry.inner_face_radius,
             ('%.2f' % geometry.pipe_clearance_mm()
              if geometry.pipe_clearance_mm() is not None else 'n/a'),
             geometry.straight_mm))

    _step('  step1/4 扫掠 U 型螺栓…（路径 直腿-圆弧-直腿，截面 φ%.1f）'
          % geometry.d)
    parts = []
    try:
        parts.append(('U型螺栓',
                      build_u_bolt_body(frame, geometry, model, uor)))
        _step('  step1/4 完成')
        _step('  step2/4 逐颗建螺母（共 %d 颗：每腿 2 颗 × 2 腿）…'
              % (len(geometry.nuts) * 2))
        for _index, y_low, y_high in geometry.nuts:
            for sign in (1.0, -1.0):
                label = '六角螺母(%s%.0f~%.0f)' % (
                    '+' if sign > 0 else '-', y_low, y_high)
                _step('    - %s …' % label)
                parts.append((label, build_nut_body(
                    frame, geometry, sign, y_low, y_high, model, uor)))
        _step('  step2/4 完成（%d 个零件）' % len(parts))

        _step('  step3/4 整组写入普通单元 %s…' % CELL_NAME)
        cell = _assembly_element(model, parts)
        _step('  step3/4 完成（已落图）')
    except Exception:
        # 中途失败时已建好的内核实体必须丢掉引用，否则滞留内存（本插件是
        # "点一次放一个"，连点十几次就是累积型原生层崩溃的温床）。
        _log('build_clamp 中途失败，丢弃已建的 %d 个实体' % len(parts))
        del parts
        raise

    message = geom.describe(geometry, angle)
    if float(insulation_mm or 0.0) > 0.0:
        message += ('\n注意：该管道有保温 %.1f mm，本插件按**裸管管径**选型、'
                    '不放大内孔；保温管请改用加长腿的 U 型管卡型式。'
                    % float(insulation_mm))
    if note:
        message += '\n' + note
    return cell, message


def attach_support_items(cell, dn, geometry, angle_deg, pipe_number='',
                         nut_count=4):
    """把整组写进共享支吊架库（整组记录 + 构件记录），失败只记日志并返回 0。"""
    try:
        import 支吊架公共库 as psb
    except Exception:
        _log_exception('import 支吊架公共库 failed')
        return 0
    tag = geom.assembly_tag(dn, geometry.bolt, angle_deg)
    try:
        return psb.attach_components(
            cell,
            support_type=SUPPORT_TYPE,
            support_code=SUPPORT_CODE,
            assembly_tag=tag,
            assembly_spec=geom.assembly_spec(dn, geometry),
            components=geom.bom_items(geometry, nut_count=nut_count),
            pipe_number=pipe_number or '')
    except Exception:
        _log_exception('attach support items failed')
        return 0
