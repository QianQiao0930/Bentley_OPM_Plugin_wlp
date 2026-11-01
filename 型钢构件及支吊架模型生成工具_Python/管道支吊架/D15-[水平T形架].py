# -*- coding: utf-8 -*-
"""水平 T 形架（D15）放置工具 —— 最小验证版。

在模型中点选一条用户绘制的 **水平直线段**作为辅助线，据此生成一组水平 T 形架：

    辅助线           = 起点 P0、方向 u；线长 = L1 + tb
    构件A（沿 u）    = 自 P0 起、长 L1 = 辅助线长 − tb（tb = 构件B 腹板厚 / 肢厚）
    构件B（沿 v）    = 高度 L2（用户输入），路径 P3 -> P4

五个路径点（局部基 u-v-w，原点取辅助线起点）：

    u = 辅助线方向（世界水平）    w = Z 向上    v = w × u
    P0 = 0                       辅助线起点 = 构件A 起点
    P1 = P0 + (L1+tb)·u          辅助线终点
    P2 = P1 − tb·u               构件A 末端
    P3/P4                        构件B 路径两端

两个类型只在构件B 的偏心方式上不同（``|P3P4|`` 都等于 L2）：

* **类型 1**：``P3 = P2 − (L2/2)·v``、``P4 = P2 + (L2/2)·v``（对称）
* **类型 2**：``P3 = P2 − (wA/2 + 15)·v``、``P4 = P3 + L2·v``（自构件A 下侧偏心）

子项 A~E 的构件A / 构件B 规格查图 表 2；允许荷载查图 表 1；构件B 的 MAX. L2
按类型 1 / 类型 2 分别查表。**接点焊接形式 A~F 只写入管架编号，不影响几何与选型。**

插入基准（= 扫掠起点）：等边角钢取「外接正方形中心」、槽钢与工字钢 / H 型钢取
「几何中心」。

**本版为最小验证版：不生成筋板实体**；编号末段的筋板尺寸 ``h × w`` 由面板上的
输入框**手输纯文字** —— 写了就附加到编号末尾、留空则不附加，**不参与几何与选型**。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import os
import sys
import time
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 通配导入不一定导出这两个符号，显式再导入一次（与其它插件一致）。
from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

# tkinter 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致 tk / ttk 被替换、建控件 / 事件循环时直接崩溃。
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
STEEL_DIR = os.path.join(REPO_ROOT, '型钢截面生成器')
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '水平T形架')
for _path in (COMMON_DIR, GEOM_DIR, STEEL_DIR, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
try:
    import bentley_ui.glass as _glass_module  # noqa: F401
    import bentley_ui as _bentley_ui_module  # noqa: F401
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (  # noqa: E402
    BORDER,
    CARD,
    CARD_SOFT,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    ScrollFrame,
)

import 水平T形架_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


# 支吊架公共清单模块所需的类型标识。
SUPPORT_TYPE = 'D15-[水平T形架]'
SUPPORT_CODE = 'H_T_FRAME'

# 整组构件写入的普通单元名。
CELL_NAME = 'H_T_FRAME'

COMPONENT_A_NAME = '构件A'
COMPONENT_B_NAME = '构件B'

# 构件B 高度 L2 的默认值（mm）。
DEFAULT_ARM_LENGTH_MM = 250.0

# ---------------------------------------------------------------------------
# 清单写库（共享支吊架库 ItemType）策略
# ---------------------------------------------------------------------------
# 本插件本来就只在 ``_PreviewSession.confirm()``（点【确定】）时写库，预览阶段
# 不碰 ItemType —— 与 ``D5_D6_G12_D19`` / ``D8`` 的 ATTACH_ON_CONFIRM 口径一致。
# 这里补一个逃生开关：写库走 MicroStation 原生 EC 调用
# （``ItemTypeLibrary.Write()`` / ``CustomItemHost.ApplyCustomItem``），实测在
# 反复触发的插件里会卡死后 access violation（见 模块/日志/门型架_fault.log）。
# 置 False 后几何照常生成、照常落图，只是这批水平 T 形架不进清单统计。
ITEM_TYPE_ATTACH = True

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '水平T形架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    """强制重新读取本插件的依赖模块，规避 MicroStation 会话的模块缓存。

    仅用 ``importlib.reload`` 不够：若模块在旧会话里已导入过，``import X as Y``
    仍会命中 ``sys.modules`` 的旧对象（典型症状是「新加的函数找不到」）。因此这里
    先从 ``sys.modules`` 摘除、清缓存，再重新导入，并把新的模块对象写回全局名。
    """
    importlib.invalidate_caches()
    # 键为 **sys.modules 中的真实模块名**（注意 steel_sweep_geometry 是以
    # ``steel_sections.`` 为前缀注册的），值为本模块里的全局名。
    local_modules = (
        ('水平T形架_几何', 'geom'),
        ('支吊架公共库', 'psb'),
        ('steel_sections.steel_sweep_geometry', 'steel_sweep_geometry'),
    )
    for module_name, global_name in local_modules:
        current = globals().get(global_name)
        cached = sys.modules.get(module_name)
        if cached is None and current is None:
            # 从未导入过：交给脚本顶部的 import 处理，不在这里报错。
            continue
        try:
            sys.modules.pop(module_name, None)
            module = importlib.import_module(module_name)
        except Exception:
            _log_exception('reload %s failed' % module_name)
            if cached is not None:
                # 重载失败时把原对象放回去，避免全局名变成旧引用以外的东西。
                sys.modules[module_name] = cached
            continue
        globals()[global_name] = module
    # 型钢截面数据 / 几何模块也一并重载，保证规格表是最新的。
    for name in ('steel_sections.steel_equal_angle_data',
                 'steel_sections.steel_equal_angle_geometry',
                 'steel_sections.steel_channel_data',
                 'steel_sections.steel_channel_geometry',
                 'steel_sections.steel_hbeam_data',
                 'steel_sections.steel_hbeam_geometry',
                 'steel_sections.steel_registry'):
        module = sys.modules.get(name)
        if module is not None:
            try:
                importlib.reload(module)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 单位与所选元素提取
# ---------------------------------------------------------------------------


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _point_to_mm(point, uor_per_mm):
    return (point.x / uor_per_mm, point.y / uor_per_mm, point.z / uor_per_mm)


def _to_uor(point_mm, uor_per_mm):
    return tuple(component * uor_per_mm for component in point_mm)


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _collect_linear_pieces(curve_vector, pieces):
    for primitive in curve_vector:
        primitive_type = primitive.GetCurvePrimitiveType()
        if primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line:
            segment = primitive.GetLine()
            pieces.append([_copy_dpoint(segment.StartPoint),
                           _copy_dpoint(segment.EndPoint)])
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_LineString:
            points = [_copy_dpoint(point) for point in primitive.GetLineString()]
            if len(points) >= 2:
                pieces.append(points)
        elif primitive_type == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_CurveVector:
            child = primitive.GetChildCurveVector()
            if child is None:
                raise ValueError('所选元素含无法读取的子路径。')
            _collect_linear_pieces(child, pieces)
        else:
            raise ValueError('所选元素含圆弧或曲线；请选择一条水平的直线段。')


def extract_line(element_handle):
    """从所选元素提取并校验水平辅助线，返回 ``水平T形架_几何.SelectedLine``。"""
    uor_per_mm = _uor_per_mm()
    curve = ICurvePathQuery.ElementToCurveVector(element_handle)
    if curve is None or not curve.IsOpenPath():
        raise ValueError('请选择一条水平直线段作为辅助线。')
    pieces = []
    _collect_linear_pieces(curve, pieces)
    pieces_mm = [[_point_to_mm(point, uor_per_mm) for point in piece]
                 for piece in pieces]
    return geom.parse_selected_line(pieces_mm)


# ---------------------------------------------------------------------------
# 型钢截面 -> Bentley 曲线 -> 扫掠实体
# ---------------------------------------------------------------------------


def _dpoint(point):
    try:
        return DPoint3d.From(point[0], point[1], point[2])
    except Exception:
        return DPoint3d(point[0], point[1], point[2])


def _open_boundary_type():
    for name in ('eBOUNDARY_TYPE_Open', 'eBOUNDARY_TYPE_Outer'):
        value = getattr(CurveVector, name, None)
        if value is not None:
            return value
    return CurveVector.eBOUNDARY_TYPE_Outer


def _profile_curve(geometry, frame):
    """把截面轮廓按坐标架映射到世界，构建闭合 CurveVector（保留真圆弧）。"""
    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for segment in geometry.segments:
        points = steel_sweep_geometry.sample_segment(segment, frame)
        world = [_dpoint(point) for point in points]
        if len(world) == 2:
            profile.Add(ICurvePrimitive.CreateLine(DSegment3d(world[0], world[1])))
        else:
            profile.Add(ICurvePrimitive.CreateArc(
                DEllipse3d.FromPointsOnArc(world[0], world[1], world[2])))
    return profile


def _line_curve(start, end):
    curve = CurveVector(_open_boundary_type())
    curve.Add(ICurvePrimitive.CreateLine(
        DSegment3d(_dpoint(start), _dpoint(end))))
    return curve


def _sweep_body(profile_curve, path_curve, model_ref, origin, up_axis):
    """沿直线路径扫掠截面，兼容 BodyFromSweep 的不同签名。"""
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    start = DPoint3d.From(origin[0], origin[1], origin[2])

    def ten_arg_none():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, None, None, None,
        )

    def ten_arg_scalars():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up, 0.0, 1.0, start,
        )

    def six_arg():
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False
        )

    last_error = None
    for attempt in (ten_arg_none, ten_arg_scalars, six_arg):
        try:
            result = attempt()
        except Exception as error:
            last_error = error
            continue
        if not isinstance(result, (tuple, list)) or len(result) < 2:
            continue
        if result[0] == BentleyStatus.eSUCCESS and result[1] is not None:
            return result[1]
    raise RuntimeError('沿路径扫掠失败：%s' % last_error)


def _body_to_element(body, dgn_model, component_name):
    solid = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
            solid, body, None, dgn_model):
        _log('%s: BodyToElement failed' % component_name)
        return None
    return solid


def _build_member_element(variant_key, member_kind, points, uor_per_mm,
                          dgn_model):
    """构建一个构件（构件A / 构件B）实体元素，不写入模型。"""
    geometry = geom.member_geometry(variant_key, member_kind, uor_per_mm)
    origin, axis_x, axis_y, axis_z, length = geom.member_placement(
        variant_key, member_kind, points, uor_per_mm)

    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    profile = _profile_curve(geometry, frame)
    end = tuple(origin[index] + axis_z[index] * length for index in range(3))
    path = _line_curve(origin, end)
    body = _sweep_body(profile, path, dgn_model, frame.origin, frame.axis_y)
    return _body_to_element(body, dgn_model, member_kind)


# ---------------------------------------------------------------------------
# 整组单元拼装
# ---------------------------------------------------------------------------


def _succeeded(status):
    return status == BentleyStatus.eSUCCESS


class _HFrameCellBuilder(object):
    """把一个整组的子元素装进普通单元（Normal Cell），暂不写入模型。"""

    def __init__(self, dgn_model, cell_name=None):
        self.cell_name = cell_name or CELL_NAME
        self.cell = EditElementHandle()
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model)
        self.child_count = 0

    def add(self, child):
        if child is None:
            return False
        if not _succeeded(NormalCellHeaderHandler.AddChildElement(self.cell,
                                                                  child)):
            return False
        self.child_count += 1
        return True

    def build(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError('构件单元拼装失败。')

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('单元写入模型失败。')
        return self.cell


def _attach_support_items(cell, result):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=result.get('assembly_spec', ''),
        components=result.get('bom_items', ()),
    )


def _write_support_items(handle, result):
    """把一整组写进共享支吊架库（原生 EC 写入），返回写入条目数，失败只记日志。

    先记一条含编号 / 构件的日志：这个原生调用是本插件已知的偶发卡死点，
    崩了也能从日志最后一行看出崩在哪一项。
    """
    if not ITEM_TYPE_ATTACH:
        _log('attach skipped (ITEM_TYPE_ATTACH=False)')
        return 0
    _log('attach on confirm: type=%s tag=%s items=%s'
         % (SUPPORT_TYPE, result.get('pipe_rack_number') or '-',
            [str(item.get('code')) for item in result.get('bom_items', ())]))
    try:
        return _attach_support_items(handle, result)
    except Exception:
        _log_exception('attach failed')
        return 0


def _build_h_frame_cell(line, variant_key, rack_type, arm_length_mm,
                        weld_joint, stiffener=None):
    """按所选水平辅助线构建一组水平 T 形架但**不写入模型**。

    ``stiffener`` 是编号末段的筋板尺寸**文字**（用户手输，可为空）：不建实体、
    不影响几何，只进编号。

    返回 ``(builder, 统计字典)``。
    """
    if rack_type not in geom.ALL_RACK_TYPES:
        raise ValueError('类型只能是 %s。'
                         % '/'.join(str(t) for t in geom.ALL_RACK_TYPES))

    points = geom.path_points(line, variant_key, rack_type, arm_length_mm)
    l1 = points['l1_mm']
    l2 = points['l2_mm']

    max_l1 = geom.max_allowed_l1(variant_key)
    if max_l1 is not None and l1 > max_l1 + geom.LOAD_TOLERANCE_MM:
        raise ValueError(
            '子项 %s 最大允许构件A 长 L1=%d mm，当前 L1=%.0f mm 超限。'
            % (variant_key, max_l1, l1))
    max_l2 = geom.max_allowed_l2(variant_key, rack_type)
    if max_l2 is not None and l2 > max_l2 + geom.LOAD_TOLERANCE_MM:
        raise ValueError(
            '子项 %s 在类型 %d 下最大允许 L2=%d mm，当前 L2=%.0f mm 超限。'
            % (variant_key, rack_type, max_l2, l2))

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    uor_per_mm = _uor_per_mm(dgn_model)

    member_a = _build_member_element(variant_key, 'post', points, uor_per_mm,
                                     dgn_model)
    if member_a is None:
        raise RuntimeError('构件A 实体创建失败。')
    member_b = _build_member_element(variant_key, 'arm', points, uor_per_mm,
                                     dgn_model)
    if member_b is None:
        raise RuntimeError('构件B 实体创建失败。')

    builder = _HFrameCellBuilder(dgn_model)
    builder.add(member_a)
    builder.add(member_b)
    # 最小验证版：不生成筋板（h × w 待补）。
    builder.build()

    spec_a = geom.specification(variant_key, 'post')
    spec_b = geom.specification(variant_key, 'arm')
    stiffener_text = str(stiffener or '').strip()
    rack_number = geom.pipe_rack_number(rack_type, variant_key, weld_joint,
                                       l1, l2, stiffener_text)
    load = geom.allowable_load(variant_key, l1, rack_type)

    bom_items = [
        {'code': 'MemberA', 'name': COMPONENT_A_NAME,
         'specification': spec_a, 'length': l1, 'quantity': 1, 'unit': '根'},
        {'code': 'MemberB', 'name': COMPONENT_B_NAME,
         'specification': spec_b, 'length': l2, 'quantity': 1, 'unit': '根'},
    ]

    result = {
        'variant': variant_key,
        'rack_type': int(rack_type),
        'weld_joint': str(weld_joint).upper(),
        'stiffener': stiffener_text,
        'child_count': builder.child_count,
        'line_length': points['line_length_mm'],
        'tb': points['tb_mm'],
        'l1': l1,
        'l2': l2,
        'w_a': points['w_a_mm'],
        'offset': points['offset_mm'],
        'center_distance': _center_distance(points),
        'specification_a': spec_a,
        'specification_b': spec_b,
        'assembly_spec': geom.assembly_specification(variant_key),
        'allowable_load': load.value,
        'max_l1': max_l1,
        'max_l2': max_l2,
        'pipe_rack_number': rack_number,
        'bom_items': bom_items,
        'points': points,
    }
    _log('h frame built: variant=%s, type=%d, joint=%s, line=%.1f, tb=%.1f, '
         'L1=%.1f, L2=%.1f, offset=%.1f, cells=%d, stiffener=%s, number=%s'
         % (variant_key, int(rack_type), result['weld_joint'],
            points['line_length_mm'], points['tb_mm'], l1, l2,
            points['offset_mm'], builder.child_count,
            stiffener_text or '-', rack_number))
    return builder, result


def _center_distance(points):
    """构件B 中心相对构件A 形心线的偏移量（mm）：类型 2 应为 +15。"""
    p2 = points['p2']
    p3 = points['p3']
    v_dir = points['v_dir']
    delta = tuple(p3[index] - p2[index] for index in range(3))
    along_v = sum(delta[index] * v_dir[index] for index in range(3))
    return along_v + points['l2_mm'] / 2.0


# ---------------------------------------------------------------------------
# 预览所有权
# ---------------------------------------------------------------------------


def _delete_element(element):
    if element is None:
        return
    try:
        if not element.IsValid:
            return
    except Exception:
        return
    status = element.DeleteFromModel()
    if not _succeeded(status):
        raise RuntimeError('删除预览失败：%s' % status)


class _PreviewSession(object):
    """本功能自己创建的预览元素的生命周期。"""

    def __init__(self):
        self.preview = None
        self.result = None

    @property
    def has_preview(self):
        return self.preview is not None

    def regenerate(self, line, variant_key, rack_type, arm_length_mm,
                   weld_joint, stiffener=None):
        """先构建并写入新预览，成功后再删除旧预览。"""
        builder, result = _build_h_frame_cell(
            line, variant_key, rack_type, arm_length_mm, weld_joint, stiffener)
        replacement = builder.commit()
        old = self.preview
        failed_old = None
        try:
            _delete_element(old)
        except Exception:
            failed_old = old
        self.preview = replacement
        self.result = result
        if failed_old is not None:
            # 旧预览删不掉时保留所有权，等 Cancel 再试。
            self.result['stale_preview'] = True
        return result

    def confirm(self, delete_auxiliary_line=False, source_handle=None):
        """确认：写清单并解除所有权（先释放所有权，再写统计）。"""
        if self.preview is None or self.result is None:
            raise ValueError('当前没有可确认的预览。')
        cell = self.preview
        result = self.result
        # 先解除所有权，避免后续统计写入失败时误删已确认的正式元素。
        self.preview = None
        self.result = None
        # 清单写库只在【确定】这一刻做（预览阶段完全不碰 ItemType）。
        _write_support_items(cell, result)
        if delete_auxiliary_line and source_handle is not None:
            _delete_element(source_handle)
        return result

    def cancel(self):
        """放弃：删除本功能创建的预览元素。"""
        element = self.preview
        self.preview = None
        self.result = None
        _delete_element(element)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _HFrameDialog(GlassDialog):
    """子项 / 类型 / 接点焊接形式 / L2 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'HorizontalTFrame'
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title='D15-[水平T形架]')
        self.line = None
        self.line_handle = None
        self.session = _PreviewSession()
        self.confirmed = False

        # 原生回调只写这些纯 Python 状态，Tk 刷新交给 poll 定时器。
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        self._shutdown_requested = False
        self._cancel_requested = False
        self._poll_job = None
        self._regen_deadline = None

        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._weld_joint = tk.StringVar()
        self._arm = tk.StringVar(value='%.0f' % DEFAULT_ARM_LENGTH_MM)
        # 筋板尺寸段（编号末段）：**纯文字**，只进编号、不建模；留空则不附加。
        self._stiffener = tk.StringVar(value='')
        self._keep_line = tk.BooleanVar(value=True)

        self._spec_a = tk.StringVar(value='—')
        self._spec_b = tk.StringVar(value='—')
        self._line_length = tk.StringVar(value='—')
        self._tb = tk.StringVar(value='—')
        self._l1 = tk.StringVar(value='—')
        self._max_l1 = tk.StringVar(value='—')
        self._max_l2 = tk.StringVar(value='—')
        self._offset = tk.StringVar(value='—')
        self._center_distance = tk.StringVar(value='—')
        self._rotation_a = tk.StringVar(value='—')
        self._rotation_b = tk.StringVar(value='—')
        self._fit_offset = tk.StringVar(value='—')
        self._load = tk.StringVar(value='—')
        self._load_note = tk.StringVar(value='')
        self._rack_number = tk.StringVar(value='—')
        self._preview_info = tk.StringVar(value='—')
        self._status = tk.StringVar(value='请选择一条水平辅助线。')

        self._variant_by_label = {}
        self._type_by_label = {}
        self._joint_by_label = {}

        self._build()
        self.protocol('WM_DELETE_WINDOW', self.on_window_close)
        self.restore_state(self.ui_state)
        self.refresh_spec()
        self.after(self.POLL_MS, self._poll_ui)

    # -- 界面 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            'D15-[水平T形架]', '点选水平辅助线生成水平 T 形架 · 改参数自动重建预览')
        form.columnconfigure(0, weight=1)
        form.rowconfigure(0, weight=1)
        self._scroll = ScrollFrame(form, bg=CARD, height=460)
        self._scroll.grid(row=0, column=0, sticky='nsew')
        body = self._scroll.body
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text='点选一条水平直线段作为辅助线：起点即构件A 起点，线长 = L1 + '
                 '构件B 腹板厚（tb）。构件B 垂直于构件A，高度 L2 由下方输入；'
                 '接点焊接形式只影响编号，不改变几何。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=520,
        ).grid(row=0, column=0, sticky='ew')

        ttk.Label(body, text='构件规格（图 表 2）', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(12, 5))

        picks = tk.Frame(body, bg=CARD)
        picks.grid(row=2, column=0, sticky='ew')
        picks.columnconfigure(0, weight=1, uniform='pick')
        picks.columnconfigure(1, weight=1, uniform='pick')

        self._variant_combo = self._labelled_combo(
            picks, 0, 0, '子项', self._variant, geom.variant_choices(),
            self._variant_by_label, self.on_options_changed)
        self._type_combo = self._labelled_combo(
            picks, 0, 1, '类型', self._rack_type, _rack_type_choices(),
            self._type_by_label, self.on_options_changed)
        self._joint_combo = self._labelled_combo(
            picks, 1, 0, '接点焊接形式', self._weld_joint,
            geom.weld_joint_choices(), self._joint_by_label,
            self.on_options_changed)
        self._arm_entry = self._compact_entry(
            picks, 1, 1, '构件B 高度 L2', self._arm, 9,
            unit='mm', note='用户输入；MAX. L2 按类型查图 表 2')

        self._variant.set(self._variant_combo['values'][0])
        self._rack_type.set(self._type_combo['values'][0])
        self._weld_joint.set(self._joint_combo['values'][0])

        ttk.Separator(body, orient='horizontal').grid(
            row=3, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='尺寸与查值', style='Section.TLabel').grid(
            row=4, column=0, sticky='w', pady=(0, 5))

        values = tk.Frame(body, bg=CARD)
        values.grid(row=5, column=0, sticky='ew')
        values.columnconfigure(0, weight=1, uniform='val')
        values.columnconfigure(1, weight=1, uniform='val')

        self._compact_value(values, 0, 0, '构件A', self._spec_a)
        self._compact_value(values, 0, 1, '构件B', self._spec_b)
        self._compact_value(values, 1, 0, '辅助线长', self._line_length,
                            unit='mm', note='= L1 + tb')
        self._compact_value(values, 1, 1, '构件B 腹板厚 tb', self._tb,
                            unit='mm', note='角钢取 t、槽钢取 tw')
        self._compact_value(values, 2, 0, '构件A 长 L1', self._l1,
                            unit='mm', note='= 辅助线长 − tb')
        self._compact_value(values, 2, 1, '最大允许 L1', self._max_l1,
                            unit='mm', note='图 表 1')
        self._compact_value(values, 3, 0, '构件B 偏心量', self._offset,
                            unit='mm', note='类型1 = 0；类型2 = wA/2 + 15')
        self._compact_value(values, 3, 1, '最大允许 L2', self._max_l2,
                            unit='mm', note='图 表 2（按类型）')
        self._compact_value(values, 4, 0, '允许荷载', self._load,
                            unit='kN', notevariable=self._load_note)
        self._compact_value(values, 4, 1, '构件B 中心偏 A 形心', self._center_distance,
                            unit='mm', note='类型2 应为 +15')
        self._compact_value(values, 5, 0, '构件A 截面旋转', self._rotation_a,
                            unit='°', note='绕扫掠轴：角钢 180、槽钢/H 型钢 90')
        self._compact_value(values, 5, 1, '构件B 截面旋转', self._rotation_b,
                            unit='°', note='绕扫掠轴：与构件A 同一规则')
        self._compact_value(values, 6, 0, '构件B 贴合偏移', self._fit_offset,
                            note='u/v/w 三分量；角钢 u−(翼缘/2−10)、w+肢厚；'
                                 '槽钢 u−翼缘/2+腹板厚',
                            columnspan=2)

        ttk.Separator(body, orient='horizontal').grid(
            row=6, column=0, sticky='ew', pady=10)

        ttk.Label(body, text='管架编号', style='Section.TLabel').grid(
            row=7, column=0, sticky='w', pady=(0, 5))
        self._stiffener_entry = self._compact_entry(
            body, 8, 0, '筋板 h×w（可留空）', self._stiffener, 18,
            note='手输纯文字，只附加到编号末段：不建筋板实体、不影响几何与选型。'
                 '例：10×100')
        self._compact_value(
            body, 9, 0, '编号', self._rack_number,
            note='D15-类型-子项-接点焊接形式-L1-L2[-筋板 h×w]')

        preview = tk.Frame(body, bg=CARD_SOFT, highlightbackground=BORDER,
                           highlightthickness=1)
        preview.grid(row=10, column=0, sticky='ew', pady=(10, 0))
        tk.Label(preview, textvariable=self._preview_info, bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=500).pack(fill='x', padx=10, pady=7)

        options = tk.Frame(form, bg=CARD)
        options.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        self._keep_check = tk.Checkbutton(
            options, text='创建后保留所选辅助线', variable=self._keep_line,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT, highlightthickness=0, bd=0)
        self._keep_check.pack(side='left')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        self._pick_button = RoundButton(
            buttons, '点选辅助线', self.pick_line, primary=False, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._pick_button.pack(side='left')
        self._confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._confirm_button.pack(side='right')
        self._cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, primary=False, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._cancel_button.pack(side='right', padx=(0, 8))

        self._arm.trace_add('write', self.on_text_changed)
        # 筋板段只是编号文字：单独一条轻量回调，不触发预览重建。
        self._stiffener.trace_add('write', self.on_stiffener_changed)

        chip = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                        highlightthickness=1)
        chip.grid(row=3, column=0, sticky='ew', pady=(8, 0))
        self._status_label = tk.Label(
            chip, textvariable=self._status, bg=CARD_SOFT, fg='#1f5f99',
            font=UI_FONT_SMALL, wraplength=520, justify='left', anchor='w')
        self._status_label.pack(fill='x', padx=10, pady=7)

    def _labelled_combo(self, parent, row, column, name, variable, choices,
                        label_map, command):
        cell = tk.Frame(parent, bg=CARD)
        cell.grid(row=row, column=column, sticky='nsew',
                  padx=(8 if column else 0, 0), pady=(3, 4))
        ttk.Label(cell, text=name, style='GlassMuted.TLabel').pack(anchor='w')
        labels = []
        for key, label in choices:
            labels.append(label)
            label_map[label] = key
        combo = ttk.Combobox(cell, textvariable=variable, state='readonly',
                             style='Glass.TCombobox', values=labels)
        combo.pack(fill='x', pady=(3, 0))
        combo.bind('<<ComboboxSelected>>', command)
        combo['values'] = labels
        return combo

    def _compact_value(self, parent, row, column, name, textvariable,
                       unit='', note='', notevariable=None, columnspan=1):
        cell = tk.Frame(parent, bg=CARD)
        cell.grid(row=row, column=column, columnspan=columnspan,
                  sticky='nsew', padx=(8 if column else 0, 0), pady=(3, 4))
        ttk.Label(cell, text=name, style='GlassMuted.TLabel').pack(anchor='w')
        value_line = tk.Frame(cell, bg=CARD)
        value_line.pack(fill='x', pady=(1, 0))
        tk.Label(value_line, textvariable=textvariable, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left').pack(side='left')
        if unit:
            tk.Label(value_line, text=unit, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side='left', padx=(5, 0))
        if notevariable is not None:
            tk.Label(cell, textvariable=notevariable, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=500).pack(anchor='w')
        elif note:
            tk.Label(cell, text=note, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL, anchor='w', justify='left',
                     wraplength=500).pack(anchor='w')
        return cell

    def _compact_entry(self, parent, row, column, name, variable, width,
                       unit='', note=''):
        cell = tk.Frame(parent, bg=CARD)
        cell.grid(row=row, column=column, sticky='nsew',
                  padx=(8 if column else 0, 0), pady=(3, 4))
        ttk.Label(cell, text=name, style='GlassMuted.TLabel').pack(anchor='w')
        line = tk.Frame(cell, bg=CARD)
        line.pack(fill='x', pady=(3, 0))
        entry = tk.Entry(line, textvariable=variable, width=width, bg='#FFFFFF',
                         fg=INK, font=UI_FONT, relief='solid', bd=1,
                         highlightthickness=0)
        entry.pack(side='left')
        if unit:
            tk.Label(line, text=unit, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side='left', padx=(5, 0))
        if note:
            tk.Label(cell, text=note, bg=CARD, fg=MUTED, font=UI_FONT_SMALL,
                     anchor='w', justify='left',
                     wraplength=240).pack(anchor='w', pady=(1, 0))
        return entry

    # -- 选项与状态 --------------------------------------------------------

    def current_variant(self):
        return self._variant_by_label.get(self._variant.get(),
                                          geom.DEFAULT_VARIANT)

    def current_rack_type(self):
        return self._type_by_label.get(self._rack_type.get(), 1)

    def current_weld_joint(self):
        return self._joint_by_label.get(self._weld_joint.get(),
                                        geom.DEFAULT_WELD_JOINT)

    def current_arm_length(self):
        try:
            return float((self._arm.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_ARM_LENGTH_MM

    def current_stiffener(self):
        """编号末段的筋板尺寸文字（手输）；留空 = 不附加该段。"""
        return (self._stiffener.get() or '').strip()

    def current_options(self):
        return {
            'variant': self.current_variant(),
            'rack_type': self.current_rack_type(),
            'weld_joint': self.current_weld_joint(),
            'arm_length': self.current_arm_length(),
            'stiffener': self.current_stiffener(),
        }

    # -- 状态存取 ----------------------------------------------------------

    def restore_state(self, state):
        try:
            variant = state.get('variant')
            if variant in geom.VARIANTS:
                for label, key in self._variant_by_label.items():
                    if key == variant:
                        self._variant.set(label)
                        break
            rack_type = state.get('rack_type')
            if rack_type in geom.ALL_RACK_TYPES:
                for label, key in self._type_by_label.items():
                    if key == int(rack_type):
                        self._rack_type.set(label)
                        break
            joint = state.get('weld_joint')
            if joint in geom.WELD_JOINT_CODES:
                for label, key in self._joint_by_label.items():
                    if key == joint:
                        self._weld_joint.set(label)
                        break
            arm = state.get('arm_length')
            if isinstance(arm, str) and arm.strip():
                self._arm.set(arm)
            stiffener = state.get('stiffener')
            if isinstance(stiffener, str):
                self._stiffener.set(stiffener)
            if isinstance(state.get('keep_line'), bool):
                self._keep_line.set(state.get('keep_line'))
        except Exception:
            pass

    def persist_state(self, state):
        try:
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['weld_joint'] = self.current_weld_joint()
            state['arm_length'] = self._arm.get()
            state['stiffener'] = self._stiffener.get()
            state['keep_line'] = bool(self._keep_line.get())
        except Exception:
            pass

    # -- 显示刷新 ----------------------------------------------------------

    def refresh_spec(self):
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        self._spec_a.set(geom.specification(variant_key, 'post'))
        self._spec_b.set(geom.specification(variant_key, 'arm'))
        max_l1 = geom.max_allowed_l1(variant_key)
        max_l2 = geom.max_allowed_l2(variant_key, rack_type)
        self._max_l1.set('—' if max_l1 is None else '%.0f' % max_l1)
        self._max_l2.set('—' if max_l2 is None else '%.0f' % max_l2)
        self._rotation_a.set(
            '%.0f' % geom.member_rotation_deg(variant_key, 'post'))
        self._rotation_b.set(
            '%.0f' % geom.member_rotation_deg(variant_key, 'arm'))
        self.refresh_line_labels()

    def refresh_line_labels(self):
        line = self.line
        if line is None:
            for var in (self._line_length, self._tb, self._l1, self._offset,
                        self._center_distance, self._fit_offset,
                        self._rack_number):
                var.set('—')
            self._load.set('—')
            self._load_note.set('')
            self._preview_info.set('—')
            return
        variant_key = self.current_variant()
        rack_type = self.current_rack_type()
        self._line_length.set('%.1f' % line.length_mm)
        tb = geom.member_web_thickness(variant_key, 'arm')
        self._tb.set('%.1f' % tb)
        try:
            points = geom.path_points(line, variant_key, rack_type,
                                      self.current_arm_length())
        except ValueError as error:
            self._l1.set('—')
            self._offset.set('—')
            self._load.set('—')
            self._load_note.set(str(error))
            self._rack_number.set('—')
            return
        self._l1.set('%.1f' % points['l1_mm'])
        self._offset.set('%.1f' % points['offset_mm'])
        self._center_distance.set('%.1f' % _center_distance(points))
        self._fit_offset.set('u %+.1f / v %+.1f / w %+.1f mm'
                             % (points['fit_u_mm'], points['fit_v_mm'],
                                points['fit_w_mm']))
        load = geom.allowable_load(variant_key, points['l1_mm'], rack_type)
        self._load.set('—' if load.value is None else '%.2f' % load.value)
        self._load_note.set(load.message or '')
        number = self._current_number(points)
        self._rack_number.set(number or '—')

    def _current_number(self, points=None):
        """按当前面板状态（含手输的筋板段）算编号；算不出来返回 None。"""
        line = self.line
        if line is None:
            return None
        if points is None:
            try:
                points = geom.path_points(line, self.current_variant(),
                                          self.current_rack_type(),
                                          self.current_arm_length())
            except ValueError:
                return None
        return geom.pipe_rack_number(
            self.current_rack_type(), self.current_variant(),
            self.current_weld_joint(), points['l1_mm'], points['l2_mm'],
            self.current_stiffener())

    def set_result(self, result):
        points = result.get('points') or {}
        number = result.get('pipe_rack_number') or '—'
        self._preview_info.set(
            '预览：子项 %s，类型 %d，接点 %s；构件A %s 长 %.1f mm，'
            '构件B %s 高 %.1f mm；P3=(%.1f, %.1f, %.1f)，'
            'P4=(%.1f, %.1f, %.1f)；编号 %s。'
            % (result.get('variant'), result.get('rack_type'),
               result.get('weld_joint'),
               result.get('specification_a'), result.get('l1', 0.0),
               result.get('specification_b'), result.get('l2', 0.0),
               points.get('p3', (0, 0, 0))[0], points.get('p3', (0, 0, 0))[1],
               points.get('p3', (0, 0, 0))[2],
               points.get('p4', (0, 0, 0))[0], points.get('p4', (0, 0, 0))[1],
               points.get('p4', (0, 0, 0))[2], number))

    def set_status(self, message, is_error=False):
        try:
            self._status_label.configure(
                fg='#b42318' if is_error else '#1f5f99')
            self._status.set(message)
        except tk.TclError:
            pass

    # -- 选项变化 ----------------------------------------------------------

    def on_options_changed(self, event=None):
        self.refresh_spec()
        if self.line is None:
            self.set_status('请先点选一条水平辅助线。', False)
            return
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        if self.line is None:
            return
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def on_stiffener_changed(self, *_args):
        """筋板段（h×w）只是编号文字：只刷新编号，**不重建预览**。

        几何没变，没必要再扫掠一遍；同时把新编号回写到预览结果里，保证
        「预览显示的编号」与「点确定时写进公共库的编号」一致。
        """
        self.refresh_line_labels()
        result = self.session.result
        if result is None:
            return
        number = self._current_number()
        if not number:
            return
        result['pipe_rack_number'] = number
        result['stiffener'] = self.current_stiffener()
        self.set_result(result)

    def _schedule_regeneration(self, delay_ms):
        self._cancel_pending_regeneration()
        self._regen_deadline = time.time() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    # -- 交互入口 ----------------------------------------------------------

    def pick_line(self):
        try:
            _HFrameByLineTool.InstallNewInstance(0, self, False)
            self.set_status('请点选一条水平直线段作为辅助线；右键取消。', False)
        except Exception as error:
            self.set_status('无法启动点选：%s' % error, True)

    def request_cancel(self):
        """由工具的原生回调调用（只写 Python 状态）。"""
        self._cancel_requested = True

    def note_hover_error(self, message):
        self._pending_message = message
        self._pending_is_error = True

    def regenerate(self, line):
        """由工具在选定辅助线后调用（只写 Python 状态）。"""
        self.line = line
        options = self.current_options()
        try:
            result = self.session.regenerate(
                line, options['variant'], options['rack_type'],
                options['arm_length'], options['weld_joint'],
                options['stiffener'])
        except Exception as error:
            if isinstance(error, ValueError):
                _log('regenerate rejected: %s' % error)
            else:
                _log_exception('regenerate failed')
            self._pending_message = '水平 T 形架生成失败：%s' % error
            self._pending_is_error = True
            self._pending_result = None
            return None
        self._pending_result = result
        self._pending_message = '预览已生成；改参数会自动重建，点【确定】保留。'
        self._pending_is_error = False
        return result

    def discard_preview(self):
        try:
            self.session.cancel()
        except Exception:
            _log_exception('discard preview failed')
        self._pending_result = None

    def request_shutdown(self):
        self._shutdown_requested = True

    def confirm_tool(self):
        """确认当前预览：保留已生成的单元，**但不关闭面板**。

        面板保持打开，方便连续点选下一条辅助线继续生成；已确认的单元在
        ``session.confirm`` 里就已解除所有权，不会再被 Cancel 误删。
        """
        if not self.session.has_preview:
            self.set_status('尚无可确认的预览，请先点选一条水平辅助线。', True)
            return
        try:
            self.session.confirm(
                delete_auxiliary_line=not self._keep_line.get(),
                source_handle=self.line_handle)
        except Exception as error:
            _log_exception('confirm failed')
            self.set_status('确认失败：%s' % error, True)
            return
        self.confirmed = True
        # 清空本轮的辅助线与预览状态，面板留在屏幕上等待下一次点选。
        self.line = None
        self.line_handle = None
        self._cancel_pending_regeneration()
        self.discard_preview()
        self.refresh_line_labels()
        self.set_status('已保留水平 T 形架并写入统计信息；'
                        '可继续点选下一条水平辅助线。', False)

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        """结束原生工具并关闭面板：点【取消】或关闭窗口走这里，退回默认命令。

        **必须调 ``StartDefaultCommand``**：否则 ``DgnElementSetTool`` 仍然处于
        点选状态，面板关闭后下一次鼠标左键会被它吃掉并意外生成一次模型。
        """
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        """关闭面板（可重复调用）。"""
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    def on_window_close(self):
        """窗口标题栏的关闭按钮：清理预览、结束工具、关闭面板。"""
        self.discard_preview()
        self.finish_tool()

    # -- Tk 轮询 -----------------------------------------------------------

    def _poll_ui(self):
        try:
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.discard_preview()
                self.finish_tool()
                return
            if self._cancel_requested:
                self._cancel_requested = False
                self.discard_preview()
                self.set_status('已取消当前点选。', False)
            if self._pending_result is not None:
                result = self._pending_result
                self._pending_result = None
                self.set_result(result)
                self.refresh_line_labels()
            if self._pending_message:
                message = self._pending_message
                is_error = self._pending_is_error
                self._pending_message = None
                self._pending_is_error = False
                self.set_status(message, is_error)
            if (self._regen_deadline is not None
                    and time.time() >= self._regen_deadline):
                self._regen_deadline = None
                if self.line is not None and not self._shutdown_requested:
                    self.regenerate(self.line)
        except tk.TclError:
            return
        except Exception:
            _log_exception('poll failed')
        try:
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            pass


def _rack_type_choices():
    return ((1, '类型1  |  构件B 与构件A 同中心'),
            (2, '类型2  |  构件B 自构件A 下侧偏心'))


# ---------------------------------------------------------------------------
# 点选工具
# ---------------------------------------------------------------------------


class _HFrameByLineTool(DgnElementSetTool):
    """点选一条水平直线并生成水平 T 形架的交互工具。"""

    _active_dialog = None

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('HFrameByLineTool')

    def _DoGroups(self):
        return False

    def _AllowSelection(self):
        return DgnElementSetTool.eUSES_SS_None

    def _NeedAcceptPoint(self):
        return False

    def _WantDynamics(self):
        return False

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnElementSetTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            '请点选一条水平直线段作为辅助线：线长 = L1 + 构件B 腹板厚。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            extract_line(handle)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                try:
                    self.tool_settings.note_hover_error(str(error))
                except Exception:
                    pass
            return False

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = extract_line(eeh)
            self.tool_settings.line_handle = eeh
            result = self.tool_settings.regenerate(line)
            return (BentleyStatus.eSUCCESS if result is not None
                    else BentleyStatus.eERROR)
        except Exception as error:
            if isinstance(error, ValueError):
                _log('element modify rejected: %s' % error)
            else:
                _log_exception('element modify failed')
            try:
                self.tool_settings.note_hover_error(
                    '水平 T 形架生成失败：%s' % error)
            except Exception:
                pass
            return BentleyStatus.eERROR

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        _HFrameByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

    def _OnCleanup(self):
        """工具结束：只解除引用，**不下发关闭面板**。

        ``confirm_tool`` / ``finish_tool`` 会调 ``StartDefaultCommand`` 结束工具，
        若这里再 ``request_shutdown``，点【确定】后刚保留下面板就会被关掉。
        面板的生命周期由 :meth:`_HFrameDialog.finish_tool` 统一负责。
        """
        self.tool_settings = None

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = _HFrameByLineTool._active_dialog
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = tool_settings if tool_settings is not None else _HFrameDialog()
        if owner:
            _HFrameByLineTool._active_dialog = settings
        tool = _HFrameByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                _HFrameByLineTool._active_dialog = None
        return tool


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


_RUNTIME_RELOADED = False


def _ensure_runtime_modules():
    """入口处强制重载一次依赖模块（同一次命令内只做一次）。"""
    global _RUNTIME_RELOADED
    if _RUNTIME_RELOADED:
        return
    _reload_runtime_modules()
    _RUNTIME_RELOADED = True


def show_h_frame_dialog():
    """打开水平 T 形架面板（点选辅助线后生成）。"""
    _ensure_runtime_modules()
    return _HFrameByLineTool.InstallNewInstance(0)


def RegisterKeyins():
    """注册 PYD15 命令（与其它插件一致，可选）。"""
    try:
        PythonKeyinManager.GetInstance().RegisterKeyin(
            'PYD15', 'show_h_frame_dialog')
    except Exception:
        _log_exception('register keyin failed')


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _ensure_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    show_h_frame_dialog()


if __name__ == '__main__':
    show_h_frame_dialog()
