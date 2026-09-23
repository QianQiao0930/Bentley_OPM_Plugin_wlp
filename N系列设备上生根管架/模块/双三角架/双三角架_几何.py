# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为建模库供入口 ``双三角架.py`` 等插件 ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""N 系列设备上生根管架 —— 设备上生根的双三角架（N4）建模库（无界面）。

用户在模型中绘制一条**水平辅助线**作为整组**中心线**（径向），线长 = L1
（立管中心线 → 端板外表面），据此生成**两套对称的三角架** + 两根构件C：

    * 构件A（横担）×2：中心线两侧 ±L2/2，沿径向从端板 r=L1 伸到
      r = L3 + C宽 + 50；
    * 构件B（斜撑）×2：45°，连接设备上的连接板与横担（复用 N3 的构造）；
    * 构件C（连接横担的横担）×2：内边缘分别在 r=L4、r=L3，垂直于横担；
    * 连接板 + 螺栓：复用 N8 ``连接板_几何``，规格按表 3 自动取；
    * 10mm 筋板：每根横担 3 个（斜撑交点 + 两根构件C 交点），共 6 个。

构件构造全部复用 ``单三角架_几何`` 的低层函数与 ``_build_crossbeam`` /
``_build_brace`` / ``_build_stiffener`` / ``_add_plate_at``。清单写入共享
支吊架库 ``支吊架公共库``（``SupportType='N系列设备上生根管架'``）。
"""

from __future__ import division

import math
import os
import sys
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_SUPPORT_COMMON = os.path.join(_REPO_ROOT, '管道支吊架', '模块', '公共')
_PLATE_DIR = os.path.join(_PLUGIN_ROOT, '模块', '连接板')
_N3_DIR = os.path.join(_PLUGIN_ROOT, '模块', '单三角架')
for _path in (_HERE, _N3_DIR, _PLATE_DIR, _SUPPORT_COMMON):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import 双三角架_数据 as data  # noqa: E402
import 单三角架_几何 as n3  # noqa: E402
import 连接板_数据 as plate_data  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


CELL_NAME = 'EQUIPMENT_DOUBLE_BRACKET'
SUPPORT_TYPE = 'N系列设备上生根管架'
SUPPORT_CODE = 'N4_DOUBLE_BRACKET'

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'
COMPONENT_C_NAME = '构件C（连接横担）'
COMPONENT_PLATE_NAME = '连接板'
COMPONENT_BOLT_NAME = '连接板螺栓'
COMPONENT_STIFFENER_NAME = '筋板'

DEBUG_LOG = os.path.join(
    _PLUGIN_ROOT, '模块', '日志', '双三角架_debug_log.txt')
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


def _succeeded(status):
    return n3._succeeded(status)


def _make_frame(line):
    return n3._make_frame(line['start_mm'], line['heading_deg'])


def _offset_line(line, radial_mm, tangential_mm, length_mm):
    """由中心线偏移出单根横担的“子线”（起点、朝向、长度）。"""
    x_axis, y_axis = n3._frame_vectors(line['heading_deg'])
    start = line['start_mm']
    return {
        'start_mm': (start[0] + x_axis[0] * radial_mm + y_axis[0] * tangential_mm,
                     start[1] + x_axis[1] * radial_mm + y_axis[1] * tangential_mm,
                     start[2]),
        'heading_deg': line['heading_deg'],
        'length_mm': length_mm,
    }


def _connector_body(spec, line, r_mm, span_mm, dgn_model, sign=1.0):
    """构件C 的实体（未转元素）。

    ``r_mm`` 为构件C **内边缘**到中心线的径向距离；``sign`` 为截面宽度方向
    （+1 向外、−1 向内），使两根构件C 分居端板两侧、净距 = L3 + L4。
    """
    x_axis, y_axis = n3._frame_vectors(line['heading_deg'])
    start = line['start_mm']
    width = data.section_dims(spec)['width']
    # 截面轮廓 width ∈ [-B/2, +B/2]（关于轴心对称）。把轴心放到
    # r_mm + sign·B/2，使构件C 的**内边缘**正好落在 r_mm
    # （sign=+1 向外、-1 向内）。顶面在中心线标高；depth 竖向、width 径向。
    # 轮廓放在切向 +span/2 处，再沿 -切向扫掠 span，使构件C 关于中心线对称。
    radial = r_mm + sign * width / 2.0
    origin = (start[0] + x_axis[0] * radial + y_axis[0] * (span_mm / 2.0),
              start[1] + x_axis[1] * radial + y_axis[1] * (span_mm / 2.0),
              start[2])
    points = []
    for depth, w in n3._section_points(spec):
        points.append((origin[0] + sign * w * x_axis[0],
                       origin[1] + sign * w * x_axis[1],
                       origin[2] - depth))
    profile = n3._create_shape(points, dgn_model)
    if profile is None:
        return None
    # 沿切向（-y）从 +span/2 扫到 -span/2。
    return n3._sweep_shape_to_body(
        profile, (-y_axis[0] * span_mm, -y_axis[1] * span_mm, 0.0), dgn_model)


def _build_connector(spec, line, r_mm, span_mm, dgn_model, sign=1.0):
    """构件C：垂直于横担、切向连接两根横担的横担（独立元素，预览用）。"""
    body = _connector_body(spec, line, r_mm, span_mm, dgn_model, sign)
    if body is None:
        return None
    return n3._body_to_element(body, dgn_model, 'connector')


def _build_bom_items(resolved, plate_resolved):
    plate_spec = '%.0f×%.0f×%.0f' % (
        plate_resolved['E'], plate_resolved['E'], plate_resolved['T'])
    bolt_spec = 'M%.0f×%.0f' % (
        plate_resolved['bolt_dia'], plate_resolved['bolt_length'])
    return [
        {'code': 'MemberA', 'name': COMPONENT_A_NAME,
         'specification': resolved['comp_a'],
         'length': round(resolved['beam_length'], 1),
         'quantity': 2, 'unit': '件'},
        {'code': 'MemberB', 'name': COMPONENT_B_NAME,
         'specification': resolved['comp_b'],
         'length': round(resolved['brace_length'], 1),
         'quantity': 2, 'unit': '件'},
        {'code': 'MemberC', 'name': COMPONENT_C_NAME,
         'specification': resolved['comp_c'],
         'length': round(resolved['connector_span'], 1),
         'quantity': 2, 'unit': '件'},
        {'code': 'Plate', 'name': COMPONENT_PLATE_NAME,
         'specification': plate_spec, 'length': plate_resolved['T'],
         'quantity': 4, 'unit': '件'},
        {'code': 'Bolt', 'name': COMPONENT_BOLT_NAME,
         'specification': bolt_spec, 'length': plate_resolved['bolt_length'],
         'quantity': plate_resolved['bolt_count'] * 4, 'unit': '件'},
        {'code': 'Stiffener', 'name': COMPONENT_STIFFENER_NAME,
         'specification': '%.0f 厚' % resolved['stiffener_t'],
         'length': resolved['stiffener_t'], 'quantity': 6, 'unit': '件'},
    ]


def _attach_items(cell, result):
    return psb.attach_components(
        cell,
        support_type=SUPPORT_TYPE,
        support_code=SUPPORT_CODE,
        assembly_tag=result.get('number', ''),
        assembly_spec='%s + %s + %s' % (result.get('comp_a', ''),
                                        result.get('comp_b', ''),
                                        result.get('comp_c', '')),
        components=result.get('bom_items', ()))


def build_double_bracket_cell(line, options=None, number=''):
    """构建双三角架单元但**不写入模型**，返回 ``(builder, 统计字典)``。"""
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('请先打开并激活一个 DGN 模型。')
    dgn_model = model_ref.GetDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    resolved = data.resolve_options(options, line['length_mm'])
    plate_resolved = plate_data.resolve_options({
        'type': resolved['plate_type'], 'mode': 'H',
        'heading_deg': line['heading_deg'], 'mount': 'wall'})

    builder = anchor._AnchorPlateCellBuilder(dgn_model, CELL_NAME)

    offset = resolved['beam_offset']
    beam_length = resolved['beam_length']
    section_a = resolved['section_a']
    # 槽钢横担**背靠背**：两根腹板外表面相对（左根镜像，开口朝外）。
    is_channel = section_a['kind'] == 'C'
    span = resolved['connector_span']
    # 两根构件C 分居端板两侧、方向相反，净距 = L3 + L4：
    #   内侧 C 内边缘在 r = L1 - L4（朝设备），外侧 C 内边缘在 r = L1 + L3（朝外）。
    connector_specs = ((resolved['L1'] - resolved['L4'], -1.0),
                       (resolved['L1'] + resolved['L3'], 1.0))
    # 每根横担 3 个 10mm 筋板：斜撑交点 + 两根构件C 的**腹板**位置
    # （工字钢构件C 腹板在截面中心；槽钢腹板在内边缘）。
    c_section = resolved['section_c']
    c_half = c_section['width'] / 2.0 if c_section['kind'] == 'H' else 0.0
    stiffener_xs = (resolved['attach_x'],
                    resolved['L1'] - resolved['L4'] - c_half,
                    resolved['L1'] + resolved['L3'] + c_half)
    # 构件C 两端伸入腹板一点，保证并集能真正融合（否则只是面接触）；
    # 但只伸到腹板厚度的一半，端头仍落在腹板内、不会突出腹板外表面。
    connector_overlap = max(2.0, section_a['tw'] * 0.5)

    # 两根横担 + 两根构件C + 6 个筋板**全部并进同一个实体**，只输出一个元素，
    # 避免两块元素在连接件处重叠而看起来“没融合”。
    frame_body = None
    for sign in (-1.0, 1.0):
        sub_line = _offset_line(line, resolved['beam_start_r'],
                                sign * offset, beam_length)
        body = n3._crossbeam_body(resolved['comp_a'], sub_line, beam_length,
                                  dgn_model, mirror=(is_channel and sign < 0))
        if body is None:
            raise RuntimeError('横担（构件A）创建失败。')
        if frame_body is None:
            frame_body = body
        elif not n3._union_body(frame_body, body):
            _log('crossbeam union failed')
        # 构件C 与横担**并集融合**（工字钢贴腹板侧面；槽钢贴腹板外表面）。
        for r_mm, csign in connector_specs:
            cb = _connector_body(resolved['comp_c'], line, r_mm,
                                 span + 2.0 * connector_overlap,
                                 dgn_model, csign)
            if cb is None or not n3._union_body(frame_body, cb):
                _log('connector union failed at r=%.1f' % r_mm)
        # 筋板并集；工字钢时只贴腹板的**另一侧**（背离中心线）。
        if is_channel:
            y_min = y_max = None
        else:
            y_min, y_max = 0.0, sign * section_a['width'] / 2.0
        for sx in stiffener_xs:
            sb = n3._stiffener_body(sub_line, resolved, dgn_model, x_mm=sx,
                                    y_min=y_min, y_max=y_max)
            if sb is None or not n3._union_body(frame_body, sb):
                _log('stiffener union failed at x=%.1f' % sx)

        brace = n3._build_brace(resolved['comp_b'], sub_line, resolved,
                                dgn_model)
        if brace is None:
            raise RuntimeError('斜撑（构件B）创建失败。')
        builder.add(brace)

        depth_a = section_a['height']
        n3._add_plate_at(builder, sub_line, (0.0, 0.0, -depth_a / 2.0),
                         plate_resolved, dgn_model)
        brace_z = -resolved['H'] if resolved['type'] == 1 else resolved['H']
        n3._add_plate_at(builder, sub_line, (0.0, 0.0, brace_z),
                         plate_resolved, dgn_model)

    if frame_body is None:
        raise RuntimeError('框架（横担 + 构件C）创建失败。')
    builder.add(n3._body_to_element(frame_body, dgn_model, 'frame'))

    builder.build()
    result = dict(resolved)
    result['child_count'] = builder.child_count
    result['cell_name'] = CELL_NAME
    result['number'] = str(number or '')
    result['plate_resolved'] = dict(plate_resolved)
    result['bom_items'] = _build_bom_items(resolved, plate_resolved)
    _log('double bracket: subtype=%s type=%d H=%.0f L1=%.0f L2=%.0f L3=%.0f '
         'L4=%.0f beam=%.0f cells=%d number=%s'
         % (resolved['subtype'], resolved['type'], resolved['H'],
            resolved['L1'], resolved['L2'], resolved['L3'], resolved['L4'],
            beam_length, builder.child_count, result['number'] or '-'))
    return builder, result


def draw_double_bracket(line, options=None, number=''):
    """创建整组双三角架单元并写入活动模型，返回 ``(cell, 统计字典)``。"""
    builder, result = build_double_bracket_cell(line, options, number)
    cell = builder.commit()
    _attach_items(cell, result)
    return cell, result


def _delete_element(handle):
    return n3._delete_element(handle)


def replace_double_bracket(line, options, previous_handle, number=''):
    """重建双三角架：先建新的一版并写入，成功后再删除上一版预览。"""
    builder, result = build_double_bracket_cell(line, options, number)
    new_handle = builder.commit()
    _attach_items(new_handle, result)
    deleted = _delete_element(previous_handle)
    return new_handle, result, deleted


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(
            _PLUGIN_ROOT, '模块', '输出', '双三角架_bom.json')
    return psb.export_combined_bom(output_path)
