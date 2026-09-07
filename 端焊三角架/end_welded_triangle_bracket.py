# -*- coding: utf-8 -*-
'''
端焊三角架（类型 1）建模脚本

构件 A：H125x125x6.5x9 横担，沿 +X 方向布置。
构件 B：L100x10 斜撑，位于 XZ 平面内，固定 45°。

用户输入 L1 及端部挑出距离 E 后：
    L1 为焊接端面到斜撑上端中心线的水平距离。
    E 为横担最远端到斜撑上端外侧斜角的距离，最小为 150 mm。
    横担总长 L2 = ceil(L1 + 100×sqrt(2)/2 + E)（自动计算，向上取整至 mm）。
    L2 最大为 2500 mm。
'''

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

import math
import os
import json


DEBUG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'end_welded_triangle_bracket_debug_log.txt')

H_BEAM_HEIGHT = 125.0
H_BEAM_WIDTH = 125.0
H_BEAM_WEB_THICKNESS = 6.5
H_BEAM_FLANGE_THICKNESS = 9.0
ANGLE_WIDTH = 100.0
ANGLE_THICKNESS = 10.0
MIN_END_OVERHANG = 150.0
MAX_BEAM_LENGTH = 2500.0

# 写入当前 DGN 文件的 ItemType 定义。属性名称保持英文，便于 JSON/Excel
# 导出时作为稳定的字段名使用；字段值可使用中文。
ITEM_LIBRARY_NAME = 'TankLadderComponents'
ITEM_TYPE_PREFIX = 'TriangleBracketComponent'
ITEM_PROPERTY_DEFINITIONS = (
    ('ComponentName', CustomProperty.Type1.eString),
    ('Specification', CustomProperty.Type1.eString),
    ('DesignLengthMm', CustomProperty.Type1.eDouble),
    ('Quantity', CustomProperty.Type1.eInteger),
    ('Unit', CustomProperty.Type1.eString),
)


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(message + '\n')
    except Exception:
        pass


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerStorage()


def mm(value, dgn_model=None):
    return value * _uor_per_mm(dgn_model)


def _add(point, vector, distance):
    return (
        point[0] + vector[0] * distance,
        point[1] + vector[1] * distance,
        point[2] + vector[2] * distance,
    )


def _new_ec_value(value):
    '''按 Python 值创建对应类型的 ECValue。'''
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(value)
    return ec_value


def _component_item_type_name(component_code, design_length_mm):
    '''为不同设计长度创建稳定且合法的 ItemType 名称。'''
    length_key = ('%.3f' % design_length_mm).replace('.', '_').replace('-', 'N')
    return '%s_%s_L%s' % (ITEM_TYPE_PREFIX, component_code, length_key)


def _get_or_create_component_item_type(component_code, component_name,
                                       specification, design_length_mm):
    '''
    获取或创建带有本构件默认清单值的 ItemType。

    部分 MicroStation Python 版本无法把 ApplyCustomItem 返回的
    DgnECInstance 转给 Python。将值写为专用 ItemType 的默认值后，附加时
    无需再取得并编辑该实例，规避该绑定问题。
    '''
    dgn_file = ISessionMgr.GetActiveDgnFile()
    item_type_name = _component_item_type_name(component_code, design_length_mm)
    default_values = {
        'ComponentName': component_name,
        'Specification': specification,
        'DesignLengthMm': float(design_length_mm),
        'Quantity': 1,
        'Unit': '件',
    }
    try:
        item_library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        library_changed = False
        if item_library is None:
            item_library = ItemTypeLibrary(ITEM_LIBRARY_NAME, dgn_file, False)
            library_changed = True

        item_type = item_library.GetItemTypeByName(item_type_name)
        if item_type is None:
            item_type = item_library.AddItemType(item_type_name, False)
            library_changed = True
        if item_type is None:
            _log('item type: failed to create %s' % item_type_name)
            return None

        for property_name, property_type in ITEM_PROPERTY_DEFINITIONS:
            item_property = item_type.GetPropertyByName(property_name)
            if item_property is None:
                item_property = item_type.AddProperty(property_name, False)
                if item_property is None or not item_property.SetType(property_type):
                    _log('item type: failed to add property %s' % property_name)
                    return None
                if not item_property.SetDefaultValue(
                        _new_ec_value(default_values[property_name])):
                    _log('item type: failed to set default for %s' % property_name)
                    return None
                library_changed = True

        if library_changed and not item_library.Write():
            _log('item type: failed to write library %s' % ITEM_LIBRARY_NAME)
            return None

        # 与官方示例保持一致：定义写入 DGN 后重新获取持久化 ItemType。
        item_library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        return item_library.GetItemTypeByName(item_type_name)
    except Exception as e:
        _log('item type: setup exception: %r' % e)
        return None


def _attach_component_item(element, component_code, component_name,
                           specification, design_length_mm):
    '''把构件清单属性作为 ItemType 实例附加到已入模的实体元素。'''
    item_type = _get_or_create_component_item_type(
        component_code, component_name, specification, design_length_mm)
    if item_type is None:
        return False
    try:
        item_host = CustomItemHost(element, False)
        # 官方接口会返回 DgnECInstance；当前环境无法封送该返回值。附加
        # 动作已在 C++ 侧完成，属性则由本 ItemType 的默认值提供。
        try:
            item = item_host.ApplyCustomItem(item_type)
        except TypeError as e:
            if 'Unable to convert function return value' in str(e):
                _log('item type: attached %s with default metadata '
                     '(return conversion unavailable)' % component_name)
                return True
            raise
        if item is None:
            _log('item type: failed to attach item to %s' % component_name)
            return False
        item.WriteChanges()
        return True
    except Exception as e:
        _log('item type: attach exception for %s: %r' % (component_name, e))
        return False


def _get_item_property_value(item, property_name, value_kind):
    '''读取一个 ItemType 属性，并转换为可写入 JSON 的 Python 值。'''
    ec_value = ECValue()
    status = item.GetValue(ec_value, property_name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or ec_value.IsNull():
        return None
    if value_kind == 'double':
        return ec_value.GetDouble()
    if value_kind == 'integer':
        return ec_value.GetInteger()
    return ec_value.GetString()


def export_triangle_bracket_bom_json(output_path=None):
    '''
    导出当前 DGN 中端焊三角架构件的 JSON 清单。

    返回输出文件的绝对路径；未找到构件或导出失败时返回 None。
    输出包含 records（逐件明细）和 summary（按名称、规格、单位汇总）。
    '''
    dgn_file = ISessionMgr.GetActiveDgnFile()
    try:
        item_library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        if item_library is None:
            MessageCenter.ShowErrorMessage(
                '未找到三角架 ItemType 库，尚无可导出的三角架构件。', '', False)
            return None

        scope = FindInstancesScope.CreateScope(
            dgn_file, FindInstancesScopeOption(DgnECHostType.eElement, False))
        query = ECQuery.CreateQuery(ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses)
        records = []
        summary_map = {}
        schema_name = str(item_library.GetInternalName())

        for item in DgnECManager.GetManager().FindInstances(scope, query)[0]:
            item_class = item.GetClass()
            item_schema_name = str(item_class.GetSchema().GetName())
            item_type_name = str(item_class.GetName())
            if (item_schema_name != schema_name or
                    not item_type_name.startswith(ITEM_TYPE_PREFIX + '_')):
                continue

            element_instance = item.GetAsElementInstance()
            if element_instance is None:
                continue
            record = {
                'elementId': int(element_instance.ElementHandle.ElementId),
                'itemType': item_type_name,
                'componentName': _get_item_property_value(
                    item, 'ComponentName', 'string'),
                'specification': _get_item_property_value(
                    item, 'Specification', 'string'),
                'designLengthMm': _get_item_property_value(
                    item, 'DesignLengthMm', 'double'),
                'quantity': _get_item_property_value(item, 'Quantity', 'integer'),
                'unit': _get_item_property_value(item, 'Unit', 'string'),
            }
            if None in (record['componentName'], record['specification'],
                        record['designLengthMm'], record['quantity'], record['unit']):
                _log('bom export: incomplete item on element %s' % record['elementId'])
                continue
            records.append(record)

            key = (record['componentName'], record['specification'], record['unit'])
            if key not in summary_map:
                summary_map[key] = {
                    'componentName': record['componentName'],
                    'specification': record['specification'],
                    'unit': record['unit'],
                    'quantity': 0,
                    'totalDesignLengthMm': 0.0,
                }
            summary_map[key]['quantity'] += record['quantity']
            summary_map[key]['totalDesignLengthMm'] += (
                record['designLengthMm'] * record['quantity'])

        if not records:
            MessageCenter.ShowErrorMessage(
                '未找到带有端焊三角架 ItemType 属性的构件。', '', False)
            return None

        summary = list(summary_map.values())
        for item_summary in summary:
            item_summary['totalDesignLengthMm'] = round(
                item_summary['totalDesignLengthMm'], 3)
        summary.sort(key=lambda value: (value['componentName'], value['specification']))
        records.sort(key=lambda value: value['elementId'])

        payload = {
            'itemTypeLibrary': ITEM_LIBRARY_NAME,
            'recordCount': len(records),
            'records': records,
            'summary': summary,
        }
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'triangle_bracket_bom.json')
        with open(output_path, 'w', encoding='utf-8') as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2)
        MessageCenter.ShowInfoMessage(
            '端焊三角架清单已导出：%s' % output_path, '', False)
        return output_path
    except Exception as e:
        _log('bom export exception: %r' % e)
        MessageCenter.ShowErrorMessage(
            '端焊三角架清单导出失败，请查看调试日志。', '', False)
        return None


def _create_shape(points_mm, dgn_model):
    points = DPoint3dArray()
    for point in points_mm:
        points.append(DPoint3d(mm(point[0], dgn_model),
                               mm(point[1], dgn_model),
                               mm(point[2], dgn_model)))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, points, dgn_model.Is3d(), dgn_model)
    if BentleyStatus.eSUCCESS != status:
        return None
    if BentleyStatus.eSUCCESS != profile.AddToModel():
        return None
    return profile


def _create_box_body(minimum, maximum, dgn_model):
    '''创建用于顶端水平切割的临时盒状实体。'''
    min_x, min_y, min_z = minimum
    max_x, max_y, max_z = maximum
    profile = _create_shape([
        (min_x, min_y, min_z),
        (max_x, min_y, min_z),
        (max_x, max_y, min_z),
        (min_x, max_y, min_z),
    ], dgn_model)
    if profile is None:
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        return None

    sweep = DVec3d(0.0, 0.0, mm(max_z - min_z, dgn_model))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        return None
    return body_result[1]


def _subtract_body(target_body, tool_body):
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanSubtract(target_body, tools)
    except Exception as e:
        _log('BooleanSubtract exception: %r' % e)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if BentleyStatus.eSUCCESS != status:
        _log('BooleanSubtract failed: %r' % (status,))
        return False
    return True


def _body_to_model_element(body, dgn_model, component_name):
    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(solid, body, None, dgn_model)
    if BentleyStatus.eSUCCESS != status:
        _log('%s: BodyToElement failed: %r' % (component_name, status))
        return None
    if BentleyStatus.eSUCCESS != solid.AddToModel():
        _log('%s: AddToModel failed' % component_name)
        return None
    return solid


def create_h_beam(length, origin=(0.0, 0.0, 0.0)):
    '''创建 H125x125x6.5x9 横担；origin 为左端焊接面中心。'''
    if length <= 0.0:
        _log('H beam length must be greater than zero')
        return None

    dgn_model = ISessionMgr.GetActiveDgnModel()
    half_width = H_BEAM_WIDTH / 2.0
    half_height = H_BEAM_HEIGHT / 2.0
    half_web = H_BEAM_WEB_THICKNESS / 2.0
    flange_inner_z = half_height - H_BEAM_FLANGE_THICKNESS
    x0, y0, z0 = origin

    # YZ 平面内的 H 形截面，从下翼缘外角开始逆时针绘制。
    profile_points = [
        (x0, y0 - half_width, z0 - half_height),
        (x0, y0 + half_width, z0 - half_height),
        (x0, y0 + half_width, z0 - flange_inner_z),
        (x0, y0 + half_web, z0 - flange_inner_z),
        (x0, y0 + half_web, z0 + flange_inner_z),
        (x0, y0 + half_width, z0 + flange_inner_z),
        (x0, y0 + half_width, z0 + half_height),
        (x0, y0 - half_width, z0 + half_height),
        (x0, y0 - half_width, z0 + flange_inner_z),
        (x0, y0 - half_web, z0 + flange_inner_z),
        (x0, y0 - half_web, z0 - flange_inner_z),
        (x0, y0 - half_width, z0 - flange_inner_z),
    ]
    profile = _create_shape(profile_points, dgn_model)
    if profile is None:
        _log('H beam: failed to create profile')
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        _log('H beam: failed to convert profile to body')
        return None

    sweep = DVec3d(mm(length, dgn_model), 0.0, 0.0)
    status = SolidUtil.Modify.SweepBody(body_result[1], sweep)
    if BentleyStatus.eSUCCESS != status:
        _log('H beam: sweep failed: %r' % (status,))
        return None
    beam = _body_to_model_element(body_result[1], dgn_model, 'H beam')
    if beam is not None and not _attach_component_item(
            beam, 'HBeam', '横担', 'H125×125×6.5×9', length):
        _log('H beam: failed to attach component item')
        beam.DeleteFromModel()
        return None
    return beam


def create_angle_brace(horizontal_distance, vertical_distance, origin):
    '''创建 L100x10 斜撑，下端为 YZ 切面、上端为 XY 水平切面。'''
    if horizontal_distance <= 0.0 or vertical_distance <= 0.0:
        _log('brace projections must be greater than zero')
        return None

    dgn_model = ISessionMgr.GetActiveDgnModel()
    length = math.hypot(horizontal_distance, vertical_distance)
    axis = (horizontal_distance / length, 0.0, vertical_distance / length)

    # 截面必须垂直于扫掠轴线。+Y 与斜撑轴线天然垂直；另一肢在 XZ
    # 平面内取法向，使两肢实际长度均为 ANGLE_WIDTH，而不是其投影长度。
    # 对 45° 斜撑，该方向为 (+sqrt(2)/2, 0, -sqrt(2)/2)。
    # 为形成完整的 YZ 底端切面，扫掠起点需沿 -axis 预留一段余量，
    # 再以 x=origin.x 的平面切除余料。
    start_overrun = ((ANGLE_WIDTH + ANGLE_THICKNESS) * axis[2] / axis[0])
    outer_corner = _add(origin, axis, -start_overrun)
    leg_y_axis = (0.0, 1.0, 0.0)
    face_axis = (axis[2], 0.0, -axis[0])
    p1 = _add(outer_corner, leg_y_axis, ANGLE_WIDTH)
    p2 = _add(p1, face_axis, ANGLE_THICKNESS)
    p3 = _add(_add(outer_corner, leg_y_axis, ANGLE_THICKNESS),
              face_axis, ANGLE_THICKNESS)
    p4 = _add(_add(outer_corner, leg_y_axis, ANGLE_THICKNESS),
              face_axis, ANGLE_WIDTH)
    p5 = _add(outer_corner, face_axis, ANGLE_WIDTH)
    profile = _create_shape([outer_corner, p1, p2, p3, p4, p5], dgn_model)
    if profile is None:
        _log('brace: failed to create L100x10 profile')
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        _log('brace: failed to convert profile to body')
        return None

    # 多扫掠一段后削平，保证上端与横担下翼缘为 XY 水平焊接面。
    overrun = ((ANGLE_WIDTH + ANGLE_THICKNESS) * axis[0] / axis[2])
    raw_length = start_overrun + length + overrun
    sweep = DVec3d(mm(axis[0] * raw_length, dgn_model),
                   0.0,
                   mm(axis[2] * raw_length, dgn_model))
    status = SolidUtil.Modify.SweepBody(body_result[1], sweep)
    if BentleyStatus.eSUCCESS != status:
        _log('brace: sweep failed: %r' % (status,))
        return None

    # 角钢的起始局部截面垂直于斜撑轴线，不能直接作为安装端面。
    # 以 x=origin.x 的 YZ 平面切除左侧余料，得到底端竖直切面。
    raw_end_x = outer_corner[0] + axis[0] * raw_length
    margin = ANGLE_WIDTH + ANGLE_THICKNESS
    bottom_cutter = _create_box_body(
        (outer_corner[0] - margin,
         origin[1] - margin,
         outer_corner[2] - ANGLE_WIDTH - margin),
        (origin[0],
         origin[1] + ANGLE_WIDTH + margin,
         origin[2] + vertical_distance + margin),
        dgn_model)
    if bottom_cutter is None or not _subtract_body(body_result[1], bottom_cutter):
        _log('brace: failed to create YZ bottom cut')
        return None

    top_cut_z = origin[2] + vertical_distance
    cutter = _create_box_body(
        (min(outer_corner[0], raw_end_x) - margin,
         origin[1] - margin,
         top_cut_z),
        (max(origin[0], raw_end_x) + margin,
         origin[1] + ANGLE_WIDTH + margin,
         top_cut_z + raw_length * axis[2] + margin),
        dgn_model)
    if cutter is None or not _subtract_body(body_result[1], cutter):
        _log('brace: failed to create horizontal top cut')
        return None
    brace = _body_to_model_element(body_result[1], dgn_model, 'angle brace')
    # raw_length 仅是为顶部水平切割预留的加工余量；清单长度记录设计轴线长度。
    if brace is not None and not _attach_component_item(
            brace, 'AngleBrace', '斜撑', 'L100×10', length):
        _log('brace: failed to attach component item')
        brace.DeleteFromModel()
        return None
    return brace


def create_end_welded_triangle_bracket(l1, end_overhang,
                                       origin=(0.0, 0.0, 0.0)):
    '''
    创建类型 1 端焊三角架。

    origin       ：横担左端与既有钢结构焊接面的中心，横担沿 +X，支架向 -Z 下方展开。
    l1           ：焊接端面至斜撑上端中心线的水平距离。
    end_overhang ：横担最远端至斜撑上端外侧斜角的距离 E，最小为 150 mm。

    对 L100x10、45° 斜撑，横担总长为：
    L2 = ceil(L1 + 100×sqrt(2)/2 + E)，向上取整至 mm。
    '''
    if l1 <= 0.0:
        _log('L1 must be greater than zero')
        return None
    if end_overhang < MIN_END_OVERHANG:
        _log('end overhang %.1f is below minimum %.1f' %
             (end_overhang, MIN_END_OVERHANG))
        return None
    brace_corner_offset = ANGLE_WIDTH * math.sqrt(2.0) / 2.0
    # E 的量取端点是斜撑顶面外侧末端，而非其中心。对于 45° L100 角钢，
    # 该末端相对顶面中心沿 +X 的偏移为半个肢宽的投影：100*sqrt(2)/2。
    brace_top_center_x = origin[0] + l1
    brace_top_outer_end_x = brace_top_center_x + brace_corner_offset
    theoretical_beam_length = (
        brace_top_outer_end_x + end_overhang - origin[0])
    beam_length = float(math.ceil(theoretical_beam_length))
    beam_end_x = origin[0] + beam_length
    if beam_length > MAX_BEAM_LENGTH:
        _log('L2 %.1f exceeds maximum %.1f' % (beam_length, MAX_BEAM_LENGTH))
        return None

    # 斜撑端面已改为垂直于 45° 轴线。顶面与 XY 平面相交时，100 mm
    # 角钢肢在 X 向的投影为 100*sqrt(2)，其中心距外角为 100/sqrt(2)。
    # 因此扫掠基准需回退该距离，保证图纸 L1 的量取中心仍准确。
    brace_center_offset = ANGLE_WIDTH * math.sqrt(2.0) / 2.0
    brace_sweep_projection = l1 - brace_center_offset
    if brace_sweep_projection <= 0.0:
        _log('L1 must exceed the brace center offset (%.3f)' %
             brace_center_offset)
        return None

    # 横担中心标高为 origin.z；斜撑上端贴其下翼缘。
    # L100 角钢轮廓在 Y 向从其基准外角向 +Y 展开 100 mm，
    # 因此将基准外角后移半个肢宽，使角钢外轮廓关于横担中心面 Y=origin.y 居中。
    brace_top_z = origin[2] - H_BEAM_HEIGHT / 2.0
    brace_origin = (origin[0], origin[1] - ANGLE_WIDTH / 2.0,
                    brace_top_z - brace_sweep_projection)
    brace = create_angle_brace(brace_sweep_projection,
                               brace_sweep_projection, brace_origin)
    if brace is None:
        return None

    beam = create_h_beam(beam_length, origin)
    if beam is None:
        try:
            brace.DeleteFromModel()
        except Exception:
            pass
        return None

    _log('triangle bracket created: L1=%.1f, braceProjection=%.3f, '
         'topCenterX=%.3f, topOuterEndX=%.3f, beamEndX=%.3f, '
         'offset=%.3f, E=%.1f, EActual=%.3f, L2Theory=%.3f, L2=%.0f, '
         'beamId=%d, braceId=%d' %
         (l1, brace_sweep_projection, brace_top_center_x, brace_top_outer_end_x,
          beam_end_x, brace_corner_offset, end_overhang,
          beam_end_x - brace_top_outer_end_x, theoretical_beam_length, beam_length,
          beam.GetElementId(), brace.GetElementId()))
    return (beam, brace)


ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL = None


class TriangleBracketPlacementTool(DgnPrimitiveTool):
    '''在模型中点取横担根部的焊接面中心。'''

    def __init__(self, l1, end_overhang):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.l1 = l1
        self.end_overhang = end_overhang
        self.m_self = self

    def _GetToolName(self, name):
        return WString('TriangleBracketPlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt('请点取横担左端与已有钢结构焊接面的中心。')

    def _OnDataButton(self, ev):
        point = ev.GetPoint()
        uor_per_mm = _uor_per_mm()
        origin = (point.x / uor_per_mm,
                  point.y / uor_per_mm,
                  point.z / uor_per_mm)
        components = create_end_welded_triangle_bracket(
            self.l1, self.end_overhang, origin)
        if components is None:
            MessageCenter.ShowErrorMessage(
                '端焊三角架生成失败，请查看 end_welded_triangle_bracket_debug_log.txt。',
                '', False)
        else:
            MessageCenter.ShowInfoMessage(
                '端焊三角架已生成：H125×125×6.5×9 横担 + L100×10 斜撑。',
                '', False)
        return True

    def _OnResetButton(self, ev):
        NotificationManager.OutputPrompt('已取消端焊三角架定位。')
        return True

    @staticmethod
    def InstallNewInstance(l1, end_overhang):
        global ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL
        ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL = TriangleBracketPlacementTool(
            l1, end_overhang)
        ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL.InstallTool()


def show_triangle_bracket_dialog():
    '''显示端焊三角架的尺寸输入窗口。'''
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as e:
        _log('ui: tkinter unavailable: %r' % e)
        return None

    root = tk.Tk()
    root.title('端焊三角架生成（类型 1）')
    root.resizable(False, False)
    form = ttk.Frame(root, padding=16)
    form.grid(row=0, column=0, sticky='nsew')

    l1_value = tk.StringVar(value='1000')
    end_overhang_value = tk.StringVar(value='150')
    calculated_l2_value = tk.StringVar(value='1221')

    ttk.Label(form, text='L1（焊接端面至斜撑上端中心）').grid(
        row=0, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=l1_value, width=18).grid(
        row=0, column=1, sticky='ew', padx=(12, 6), pady=5)
    ttk.Label(form, text='mm').grid(row=0, column=2, sticky='w', pady=5)

    ttk.Label(form, text='E（最远端至斜撑上端外侧斜角）').grid(
        row=1, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=end_overhang_value, width=18).grid(
        row=1, column=1, sticky='ew', padx=(12, 6), pady=5)
    ttk.Label(form, text='mm（≥150）').grid(row=1, column=2, sticky='w', pady=5)

    ttk.Label(form, text='计算横担总长 L2').grid(
        row=2, column=0, sticky='w', pady=5)
    ttk.Label(form, textvariable=calculated_l2_value).grid(
        row=2, column=1, sticky='w', padx=(12, 6), pady=5)
    ttk.Label(form, text='mm').grid(row=2, column=2, sticky='w', pady=5)

    note = ('横担：H125×125×6.5×9；斜撑：L100×10（45°）。\n'
            'L2 = L1 + 100×√2/2 + E，结果向上取整至 mm；L2 不得大于 2500 mm。')
    ttk.Label(form, text=note, foreground='#505050', justify='left').grid(
        row=3, column=0, columnspan=3, sticky='w', pady=(10, 6))

    def update_calculated_l2(*unused):
        try:
            l2 = math.ceil(float(l1_value.get()) +
                           ANGLE_WIDTH * math.sqrt(2.0) / 2.0 +
                           float(end_overhang_value.get()))
            calculated_l2_value.set('%d' % l2)
        except ValueError:
            calculated_l2_value.set('—')

    l1_value.trace_add('write', update_calculated_l2)
    end_overhang_value.trace_add('write', update_calculated_l2)

    def generate():
        try:
            l1 = float(l1_value.get())
            end_overhang = float(end_overhang_value.get())
            minimum_l1 = ANGLE_WIDTH * math.sqrt(2.0) / 2.0
            if l1 <= minimum_l1:
                raise ValueError('L1 必须大于 %.3f mm。' % minimum_l1)
            if end_overhang < MIN_END_OVERHANG:
                raise ValueError('E 不得小于 %.0f mm。' % MIN_END_OVERHANG)
            beam_length = math.ceil(
                l1 + ANGLE_WIDTH * math.sqrt(2.0) / 2.0 + end_overhang)
            if beam_length > MAX_BEAM_LENGTH:
                raise ValueError('计算得到 L2=%d mm，不能大于 %.0f mm。' %
                                 (beam_length, MAX_BEAM_LENGTH))
        except ValueError as e:
            messagebox.showerror('输入有误', str(e), parent=root)
            return
        root.destroy()
        TriangleBracketPlacementTool.InstallNewInstance(l1, end_overhang)

    def export_bom():
        output_path = export_triangle_bracket_bom_json()
        if output_path is not None:
            messagebox.showinfo('导出完成',
                                '端焊三角架清单已导出：\n%s' % output_path,
                                parent=root)

    buttons = ttk.Frame(form)
    buttons.grid(row=4, column=0, columnspan=3, sticky='e', pady=(8, 0))
    ttk.Button(buttons, text='取消', command=root.destroy).grid(
        row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text='导出 JSON 清单', command=export_bom).grid(
        row=0, column=1, padx=(0, 8))
    ttk.Button(buttons, text='下一步：点取焊接面', command=generate).grid(row=0, column=2)
    root.mainloop()


if __name__ == '__main__':
    show_triangle_bracket_dialog()
