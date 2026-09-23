# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为建模库供入口 ``连接板.py`` 等插件 ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""N 系列设备上生根管架 —— 设备预焊件用连接板 + 螺栓建模库（无界面）。

按表 1 / 图 1 / 图 2 在设备表面上生成一块**连接板**（预焊件）与其螺栓：

    * 连接板：正方形 E×E×T，在 F×F 方阵上开螺栓孔，孔径 G；
      类型 0~3 四角 4 孔，类型 4、5 四角 + 四边中点 8 孔。
    * 螺栓：一根**贯穿连接板**的六角头螺栓 —— 六角头 + 垫片A + 垫片B + 六角螺母，
      全部由最简单的拉伸 / 圆柱构成，不做布尔融合（允许实体重合），只保证外形
      可辨认。沿 +X（x=0 为连接板背面）装配为
      ``[六角头][垫片A][连接板 T] ← 预留 T（另一片连接板）→ [垫片B][六角螺母]``：
      垫片A 紧贴连接板背面，垫片B 距连接板外表面一个板厚 T（给另一片连接板留位），
      两垫片间距 = 2T；六角头紧贴垫片A、六角螺母紧贴垫片B。螺栓长度 L 自连接板
      背面量起（保温 / 保冷工况不同）。

局部坐标系（原点为**连接板背面中心**，即贴设备面的那一点）：

    +X = 设备外法向（螺栓轴线，指向空气侧，设备在 -X 一侧）
    +Y = 板面内水平方向（随 heading 绕外法向旋转）
    +Z = 竖直向上

几何复用仓库内 ``管道支吊架/模块/公共/混凝土锚板.py`` 的坐标架与
「带孔拉伸板 / 圆柱 / 六角拉伸」基础构件，清单写入共享支吊架库
``支吊架公共库``（``SupportType='N系列设备上生根管架'``）。

主要接口::

    import 连接板_几何 as geom
    cell, result = geom.draw_connection_plate(placement_point, options)
"""

from __future__ import division

import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# 本文件位于 N系列设备上生根管架/模块/连接板/，插件根目录需上溯两级；
# 建模库与公共清单库在仓库内 管道支吊架/模块/公共/。
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_SUPPORT_COMMON = os.path.join(_REPO_ROOT, '管道支吊架', '模块', '公共')
for _path in (_HERE, _SUPPORT_COMMON):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 连接板_数据 as data  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# 整组构件写入的普通单元名。
CELL_NAME = 'EQUIPMENT_CONNECTION_PLATE'

# 共享支吊架清单模块所需的类型标识。
SUPPORT_TYPE = 'N系列设备上生根管架'
SUPPORT_CODE = 'N8_CONNECTION_PLATE'

COMPONENT_PLATE_NAME = '连接板'
COMPONENT_BOLT_NAME = '螺栓'

DEBUG_LOG = os.path.join(
    _PLUGIN_ROOT, '模块', '日志', '连接板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


# ---------------------------------------------------------------------------
# 构件几何（复用 混凝土锚板.py 的基础构件）
# ---------------------------------------------------------------------------


def _add_plate(builder, frame, dgn_model, resolved):
    """正方形连接板 E×E×T，一次拉伸 + 全部螺栓孔。"""
    half = resolved['E'] / 2.0
    thickness = resolved['T']
    corners = DPoint3dArray()
    # (y, z) 逆时针 -> 法向 +X，沿 +X 拉伸到 x ∈ [0, T]。
    for y, z in ((-half, -half), (half, -half), (half, half), (-half, half)):
        corners.append(frame.point(0.0, y, z))

    hole_r = frame.uor_of(resolved['G'] / 2.0)
    holes = []
    for hole_y, hole_z in resolved['holes']:
        holes.append((frame.point(-anchor.CUTTER_EXTENSION, hole_y, hole_z),
                      frame.point(thickness + anchor.CUTTER_EXTENSION,
                                  hole_y, hole_z),
                      hole_r))
    builder.add(anchor._prism_with_holes(
        dgn_model, corners, frame.uor_of(thickness), anchor.COLOR_PLATE,
        holes))


def _add_bolt(builder, frame, dgn_model, resolved, hole_y, hole_z):
    """一根贯穿连接板的六角头螺栓：六角头 + 垫片A + 垫片B + 六角螺母。

    装配（沿 +X，x=0 为连接板背面，x=T 为连接板外表面）：

        [六角头] [垫片A] [连接板 T] ← 预留 T（另一片连接板）→ [垫片B] [六角螺母]

    * 垫片A 紧贴连接板背面（与板面平齐）；
    * 垫片B 位于距连接板外表面一个板厚 T 处，正好给**另一片连接板**留出位置，
      故两垫片间距 = 2T；六角螺母紧贴垫片B；
    * 螺杆从垫片A 穿过连接板孔一直伸到末端，末端在螺母外露出丝头。

    ``resolved['bolt_length']`` L 为螺栓长度（自连接板背面量起），螺杆末端取其与
    「螺母外端面 + 丝头」的较大值。
    """
    thickness = resolved['T']
    washer_t = resolved['washer_t']
    nut_h = resolved['nut_h']
    bolt_r = frame.uor_of(resolved['bolt_dia'] / 2.0)
    washer_r = frame.uor_of(resolved['washer_od'] / 2.0)

    # 垫片A 背面在 x = -washer_t（紧贴连接板背面 x=0）；垫片B 背面在 x = 2T。
    washer_a_back = -washer_t
    washer_b_back = 2.0 * thickness
    nut_back = washer_b_back + washer_t
    nut_outer = nut_back + nut_h
    tip = max(nut_outer + data.BOLT_PROTRUSION_MM,
              float(resolved['bolt_length']))

    # 螺杆：从垫片A 背面一直伸到末端（穿过连接板孔与另一片连接板的位置）。
    builder.add(anchor._cylinder(
        dgn_model,
        frame.point(washer_a_back, hole_y, hole_z),
        frame.point(tip, hole_y, hole_z),
        bolt_r, anchor.COLOR_BOLT))

    # 垫片A：紧贴连接板背面（x ∈ [-washer_t, 0]）。
    builder.add(anchor._cylinder(
        dgn_model,
        frame.point(washer_a_back, hole_y, hole_z),
        frame.point(0.0, hole_y, hole_z),
        washer_r, anchor.COLOR_BOLT))

    # 六角头：垫片A 外侧（x ∈ [-washer_t - head_h, -washer_t]）。
    builder.add(anchor._hex_prism(
        dgn_model, frame, hole_y, hole_z, washer_a_back - resolved['head_h'],
        resolved['head_h'], resolved['head_af'], anchor.COLOR_NUT))

    # 垫片B：贴在另一片连接板外表面（x ∈ [2T, 2T + washer_t]）。
    builder.add(anchor._cylinder(
        dgn_model,
        frame.point(washer_b_back, hole_y, hole_z),
        frame.point(washer_b_back + washer_t, hole_y, hole_z),
        washer_r, anchor.COLOR_BOLT))

    # 六角螺母：紧贴垫片B（x ∈ [2T + washer_t, 2T + washer_t + nut_h]）。
    builder.add(anchor._hex_prism(
        dgn_model, frame, hole_y, hole_z, nut_back,
        nut_h, resolved['nut_af'], anchor.COLOR_NUT))


# ---------------------------------------------------------------------------
# 单元装配与清单
# ---------------------------------------------------------------------------


def _build_bom_items(resolved):
    plate_spec = '%.0f×%.0f×%.0f' % (resolved['E'], resolved['E'],
                                     resolved['T'])
    bolt_spec = 'M%.0f×%.0f' % (resolved['bolt_dia'], resolved['bolt_length'])
    return [
        {'code': 'Plate', 'name': COMPONENT_PLATE_NAME,
         'specification': plate_spec, 'length': resolved['T'],
         'quantity': 1, 'unit': '件'},
        {'code': 'Bolt', 'name': COMPONENT_BOLT_NAME,
         'specification': bolt_spec, 'length': resolved['bolt_length'],
         'quantity': resolved['bolt_count'], 'unit': '件'},
    ]


def _attach_items(cell, result):
    """把整组连接板写入共享支吊架库（整组记录 + 各构件记录）。"""
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('plate_number', ''),
        assembly_spec='连接板 %s + 螺栓 %s×%d' % (
            result.get('plate_spec', ''),
            result.get('bolt_spec', ''),
            int(result.get('bolt_count', 0))),
        components=result.get('bom_items', ()),
    )


# ---------------------------------------------------------------------------
# 对外建模接口
# ---------------------------------------------------------------------------


def build_connection_plate_cell(placement_point, options=None,
                                plate_number=''):
    """构建连接板单元但**不写入模型**，返回 ``(builder, 统计字典)``。

    ``placement_point`` 为连接板背面中心（贴设备面）的模型 UOR 坐标；
    ``plate_number`` 为管架编号，写入整组记录的 ``AssemblyTag``。
    """
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('请先打开并激活一个 DGN 模型。')
    dgn_model = model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')
    if placement_point is None:
        raise ValueError('请先在模型中点取设备表面上的放置点。')

    uor_per_mm = dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0
    resolved = data.resolve_options(options)
    frame = anchor._PlateFrame(placement_point, uor_per_mm,
                               resolved['heading_deg'], resolved['mount'])

    builder = anchor._AnchorPlateCellBuilder(dgn_model, CELL_NAME)
    _add_plate(builder, frame, dgn_model, resolved)
    for hole_y, hole_z in resolved['holes']:
        _add_bolt(builder, frame, dgn_model, resolved, hole_y, hole_z)
    builder.build()

    result = dict(resolved)
    result['child_count'] = builder.child_count
    result['cell_name'] = CELL_NAME
    result['plate_number'] = str(plate_number or '')
    result['plate_spec'] = '%.0f×%.0f×%.0f' % (
        resolved['E'], resolved['E'], resolved['T'])
    result['bolt_spec'] = 'M%.0f×%.0f' % (
        resolved['bolt_dia'], resolved['bolt_length'])
    result['bom_items'] = _build_bom_items(resolved)
    _log('connection plate: type=%d mode=%s E=%.0f F=%.0f G=%.0f T=%.0f '
         'bolts=%d M%.0f×%.0f mount=%s heading=%.2f cells=%d number=%s'
         % (resolved['type'], resolved['mode'], resolved['E'], resolved['F'],
            resolved['G'], resolved['T'], resolved['bolt_count'],
            resolved['bolt_dia'], resolved['bolt_length'], resolved['mount'],
            resolved['heading_deg'], builder.child_count,
            result['plate_number'] or '-'))
    return builder, result


def draw_connection_plate(placement_point, options=None, plate_number=''):
    """创建整组连接板单元并写入活动模型，返回 ``(cell, 统计字典)``。"""
    builder, result = build_connection_plate_cell(placement_point, options,
                                                  plate_number)
    cell = builder.commit()
    _attach_items(cell, result)
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


def replace_connection_plate(placement_point, options, previous_handle,
                             plate_number=''):
    """重建连接板：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = build_connection_plate_cell(placement_point, options,
                                                  plate_number)
    new_handle = builder.commit()
    _attach_items(new_handle, result)
    deleted = _delete_element(previous_handle)
    return new_handle, result, deleted


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(
            _PLUGIN_ROOT, '模块', '输出', '连接板_bom.json')
    return psb.export_combined_bom(output_path)
