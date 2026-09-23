# -*- coding: utf-8 -*-
'''
端焊三角架建模脚本

构件 A：H 型钢横担，沿 +X 方向布置。
构件 B：角钢斜撑，位于 XZ 平面内，固定 45°。

用户输入 L1 及端部挑出距离 E 后：
    L1 为焊接端面到斜撑上端中心线的水平距离。
    E 为横担最远端到斜撑上端外侧斜角的距离，最小为 150 mm。
    横担总长 L2 = ceil(L1 + b×sqrt(2)/2 + E)（自动计算，向上取整至 mm）。
    L2 最大为 2500 mm（b 为所选角钢肢宽）。

整组构件（横担 + 斜撑）写成一个普通单元（Normal Cell），可整体选中、
移动、复制或删除；两个构件的清单属性（ItemType）附加在单元上。

面板用 PyQt5 自绘，与 罐壁人孔/tank_wall_manhole.py 同一套视觉风格：
在模型中点取焊接面中心后立即生成预览，改参数自动重建，点【确定】保留，
点【取消】或右键放弃。

运行环境：Bentley Power Platform Python（MSPy）。
'''

from __future__ import division

import json
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

# PyQt5 必须放在 MSPy 的 import * **之后**：MSPy 通配导入会带进同名符号，
# 放在前面会被覆盖，导致面板基本控件类丢失、插件直接起不来。
from PyQt5.QtCore import QEvent, QEventLoop, QPoint, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPalette, QPen, QRegion)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QRadioButton, QSizePolicy, QVBoxLayout, QWidget)


# ---------------------------------------------------------------------------
# 构件规格与几何参数（mm）
# ---------------------------------------------------------------------------

# VARIANTS 以子项代号为键。h_beam = (高, 宽, 腹板厚, 翼缘厚)，
# angle = (肢宽, 肢厚)。插件入口 端焊D5_D6-[三角架].py 会在导入后覆盖本表。
VARIANTS = {
    'A': {
        'h_beam': (125.0, 125.0, 6.5, 9.0),
        'angle': (100.0, 10.0),
        'h_beam_specification': 'H125×125×6.5×9',
        'angle_specification': '∠100×10',
    },
}
DEFAULT_VARIANT = 'A'

MIN_END_OVERHANG = 150.0
MAX_BEAM_LENGTH = 2500.0

H_BEAM_COMPONENT_NAME = '横担'
ANGLE_COMPONENT_NAME = '斜撑'

# 整组构件写入的普通单元名。
CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET'

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 子项选择的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框（L1 / E）的防抖，避免打到一半就重建

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

# 本文件已移至 模块/公共/，插件根目录（管道支吊架/）需上溯两级。
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_OUTPUT_DIR = os.path.join(_PLUGIN_ROOT, '模块', '输出')
try:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
except Exception:
    pass
DEBUG_LOG = os.path.join(
    _PLUGIN_ROOT, '模块', '日志', '端焊三角架_基础_debug_log.txt')


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerStorage()


def mm(value, dgn_model=None):
    return value * _uor_per_mm(dgn_model)


def _succeeded(status):
    '''Bentley 状态码为 0 表示成功；兼容不导出 BentleyStatus 的版本。'''
    try:
        return int(status) == 0
    except (TypeError, ValueError):
        return status == 0


def _point_to_mm(point):
    '''把模型 UOR 坐标点换算成 mm 三元组。'''
    if point is None:
        return None
    uor_per_mm = _uor_per_mm()
    return (point.x / uor_per_mm,
            point.y / uor_per_mm,
            point.z / uor_per_mm)


def _add(point, vector, distance):
    return (
        point[0] + vector[0] * distance,
        point[1] + vector[1] * distance,
        point[2] + vector[2] * distance,
    )


def _variant_spec(variant_key):
    if variant_key not in VARIANTS:
        raise ValueError('未知子项：%s' % variant_key)
    return VARIANTS[variant_key]


def _min_l1(variant_key):
    '''斜撑中心退出量：肢宽在 X 向投影的一半。'''
    return VARIANTS[variant_key]['angle'][0] * math.sqrt(2.0) / 2.0


def calculate_beam_length(l1, end_overhang, variant_key=DEFAULT_VARIANT):
    '''横担总长 L2，向上取整至整毫米。'''
    return float(math.ceil(
        float(l1) + _min_l1(variant_key) + float(end_overhang)))


# ---------------------------------------------------------------------------
# ItemType 构件清单
# ---------------------------------------------------------------------------


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


def _attach_bracket_items(cell, result):
    '''把横担 / 斜撑两个构件的清单属性附加到整组单元上。'''
    attached = 0
    for item in result['bom_items']:
        if _attach_component_item(cell, item['code'], item['name'],
                                  item['specification'], item['length']):
            attached += 1
        else:
            _log('item type: failed to attach %s on cell' % item['code'])
    return attached


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
                _OUTPUT_DIR, 'triangle_bracket_bom.json')
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


# ---------------------------------------------------------------------------
# 实体构造
# ---------------------------------------------------------------------------


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
    '''创建用于端面切割的临时盒状实体。'''
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


def _body_to_element(body, dgn_model, component_name):
    '''把内核实体转成元素句柄；不写入模型，交由单元装配决定。'''
    solid = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(solid, body, None, dgn_model)
    if BentleyStatus.eSUCCESS != status:
        _log('%s: BodyToElement failed: %r' % (component_name, status))
        return None
    return solid


def _create_h_beam_element(length, origin, h_beam_spec):
    '''创建 H 型钢横担元素；origin 为左端焊接面中心。不写入模型。'''
    if length <= 0.0:
        _log('H beam length must be greater than zero')
        return None

    height, width, web_thickness, flange_thickness = h_beam_spec
    dgn_model = ISessionMgr.GetActiveDgnModel()
    half_width = width / 2.0
    half_height = height / 2.0
    half_web = web_thickness / 2.0
    flange_inner_z = half_height - flange_thickness
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
    return _body_to_element(body_result[1], dgn_model, 'H beam')


def _create_angle_brace_element(horizontal_distance, vertical_distance, origin,
                                angle_spec):
    '''创建角钢斜撑元素；下端为 YZ 切面、上端为 XY 水平切面。不写入模型。'''
    if horizontal_distance <= 0.0 or vertical_distance <= 0.0:
        _log('brace projections must be greater than zero')
        return None

    angle_width, angle_thickness = angle_spec
    dgn_model = ISessionMgr.GetActiveDgnModel()
    length = math.hypot(horizontal_distance, vertical_distance)
    axis = (horizontal_distance / length, 0.0, vertical_distance / length)

    # 截面必须垂直于扫掠轴线。+Y 与斜撑轴线天然垂直；另一肢在 XZ
    # 平面内取法向，使两肢实际长度均为 angle_width，而不是其投影长度。
    # 对 45° 斜撑，该方向为 (+sqrt(2)/2, 0, -sqrt(2)/2)。
    # 为形成完整的 YZ 底端切面，扫掠起点需沿 -axis 预留一段余量，
    # 再以 x=origin.x 的平面切除余料。
    start_overrun = ((angle_width + angle_thickness) * axis[2] / axis[0])
    outer_corner = _add(origin, axis, -start_overrun)
    leg_y_axis = (0.0, 1.0, 0.0)
    face_axis = (axis[2], 0.0, -axis[0])
    p1 = _add(outer_corner, leg_y_axis, angle_width)
    p2 = _add(p1, face_axis, angle_thickness)
    p3 = _add(_add(outer_corner, leg_y_axis, angle_thickness),
              face_axis, angle_thickness)
    p4 = _add(_add(outer_corner, leg_y_axis, angle_thickness),
              face_axis, angle_width)
    p5 = _add(outer_corner, face_axis, angle_width)
    profile = _create_shape([outer_corner, p1, p2, p3, p4, p5], dgn_model)
    if profile is None:
        _log('brace: failed to create angle profile')
        return None

    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    profile.DeleteFromModel()
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        _log('brace: failed to convert profile to body')
        return None

    # 多扫掠一段后削平，保证上端与横担下翼缘为 XY 水平焊接面。
    overrun = ((angle_width + angle_thickness) * axis[0] / axis[2])
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
    margin = angle_width + angle_thickness
    bottom_cutter = _create_box_body(
        (outer_corner[0] - margin,
         origin[1] - margin,
         outer_corner[2] - angle_width - margin),
        (origin[0],
         origin[1] + angle_width + margin,
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
         origin[1] + angle_width + margin,
         top_cut_z + raw_length * axis[2] + margin),
        dgn_model)
    if cutter is None or not _subtract_body(body_result[1], cutter):
        _log('brace: failed to create horizontal top cut')
        return None
    return _body_to_element(body_result[1], dgn_model, 'angle brace')


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _TriangleBracketCellBuilder(object):
    '''收集端焊三角架子元素，全部成功后一次性写入一个普通单元。'''

    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell_name = cell_name or CELL_NAME
        self.cell = EditElementHandle()
        self.child_count = 0
        self.warnings = []
        # Bentley 此创建函数返回 None；后续 AddChildElement/AddChildComplete
        # 的状态值用于判断单元构造是否成功。
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model
        )

    def add(self, child):
        if child is None:
            raise RuntimeError('三角架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法将三角架子元素加入普通单元。')
        self.child_count += 1

    def note(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def build(self):
        status = NormalCellHeaderHandler.AddChildComplete(self.cell)
        if not _succeeded(status):
            raise RuntimeError('无法完成端焊三角架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法将端焊三角架单元写入活动模型。')
        return self.cell


def _delete_preview(handle):
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def _build_triangle_bracket_cell(l1, end_overhang, origin=(0.0, 0.0, 0.0),
                                 variant=None):
    '''
    构建端焊三角架单元但**不写入模型**，返回 (builder, 统计字典)。

    origin 为横担左端焊接面中心的 mm 坐标。
    '''
    variant_key = variant or DEFAULT_VARIANT
    spec = _variant_spec(variant_key)
    angle_width = spec['angle'][0]
    h_beam_height = spec['h_beam'][0]

    if l1 <= 0.0:
        raise ValueError('L1 必须大于零。')
    if end_overhang < MIN_END_OVERHANG:
        raise ValueError('E 不得小于 %.0f mm。' % MIN_END_OVERHANG)

    brace_corner_offset = angle_width * math.sqrt(2.0) / 2.0
    # E 的量取端点是斜撑顶面外侧末端，而非其中心。对于 45° 角钢，
    # 该末端相对顶面中心沿 +X 的偏移为半个肢宽的投影：b*sqrt(2)/2。
    brace_top_center_x = origin[0] + l1
    brace_top_outer_end_x = brace_top_center_x + brace_corner_offset
    theoretical_beam_length = brace_top_outer_end_x + end_overhang - origin[0]
    beam_length = float(math.ceil(theoretical_beam_length))
    if beam_length > MAX_BEAM_LENGTH:
        raise ValueError('计算得到 L2=%.0f mm，不能大于 %.0f mm。'
                         % (beam_length, MAX_BEAM_LENGTH))

    # 斜撑端面垂直于 45° 轴线。顶面与 XY 平面相交时，角钢肢在 X 向的
    # 投影为 b*sqrt(2)，其中心距外角为 b*sqrt(2)/2。因此扫掠基准需回退
    # 该距离，保证图纸 L1 的量取中心仍准确。
    brace_sweep_projection = l1 - brace_corner_offset
    if brace_sweep_projection <= 0.0:
        raise ValueError('L1 必须大于 %.3f mm。' % brace_corner_offset)

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    # 横担中心标高为 origin.z；斜撑上端贴其下翼缘。角钢轮廓在 Y 向从其
    # 基准外角向 +Y 展开一个肢宽，因此将基准外角后移半个肢宽，使角钢外
    # 轮廓关于横担中心面 Y=origin.y 居中。
    brace_top_z = origin[2] - h_beam_height / 2.0
    brace_origin = (origin[0], origin[1] - angle_width / 2.0,
                    brace_top_z - brace_sweep_projection)

    builder = _TriangleBracketCellBuilder(dgn_model)
    brace = _create_angle_brace_element(
        brace_sweep_projection, brace_sweep_projection, brace_origin,
        spec['angle'])
    if brace is None:
        raise RuntimeError('斜撑实体创建失败。')
    builder.add(brace)

    beam = _create_h_beam_element(beam_length, origin, spec['h_beam'])
    if beam is None:
        raise RuntimeError('横担实体创建失败。')
    builder.add(beam)

    builder.build()
    brace_length = math.hypot(brace_sweep_projection, brace_sweep_projection)
    result = {
        'variant': variant_key,
        'child_count': builder.child_count,
        'l1': float(l1),
        'end_overhang': float(end_overhang),
        'beam_length': beam_length,
        'brace_length': brace_length,
        'beam_end_x': origin[0] + beam_length,
        'h_beam_specification': spec['h_beam_specification'],
        'angle_specification': spec['angle_specification'],
        'bom_items': [
            {'code': 'HBeam', 'name': H_BEAM_COMPONENT_NAME,
             'specification': spec['h_beam_specification'],
             'length': beam_length},
            {'code': 'AngleBrace', 'name': ANGLE_COMPONENT_NAME,
             'specification': spec['angle_specification'],
             'length': brace_length},
        ],
        'warnings': list(builder.warnings),
    }
    _log('triangle bracket created: variant=%s, L1=%.1f, E=%.1f, '
         'braceProjection=%.3f, L2=%.0f, beamEndX=%.3f, cells=%d' %
         (variant_key, l1, end_overhang, brace_sweep_projection,
          beam_length, origin[0] + beam_length, builder.child_count))
    return builder, result


def draw_end_welded_triangle_bracket(l1, end_overhang,
                                     origin=(0.0, 0.0, 0.0), variant=None):
    '''创建整组端焊三角架单元并写入活动模型，返回 (cell, 统计字典)。'''
    builder, result = _build_triangle_bracket_cell(
        l1, end_overhang, origin, variant)
    cell = builder.commit()
    _attach_bracket_items(cell, result)
    return cell, result


def replace_end_welded_triangle_bracket(l1, end_overhang, origin,
                                        previous_handle, variant=None):
    '''重建三角架：先建新的一版并写入，成功后再删除上一版预览。'''
    builder, result = _build_triangle_bracket_cell(
        l1, end_overhang, origin, variant)
    new_handle = builder.commit()
    _attach_bracket_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def create_end_welded_triangle_bracket(l1, end_overhang,
                                       origin=(0.0, 0.0, 0.0), variant=None):
    '''兼容旧接口：直接创建并写入模型，返回 (cell, 统计字典)。'''
    return draw_end_welded_triangle_bracket(l1, end_overhang, origin, variant)


# ---------------------------------------------------------------------------
# 面板外观：浅色柔面（PyQt5 自绘圆角 / 柔影，不依赖任何图片资源）
# ---------------------------------------------------------------------------

UI_BG = QColor(238, 241, 246)         # 面板底色
UI_CARD = QColor(255, 255, 255)       # 卡片底
UI_WELL = QColor(231, 235, 242)       # 凹槽 / 输入框底
UI_TEXT = QColor(57, 67, 90)
UI_MUTED = QColor(125, 138, 160)
UI_RING = QColor(186, 196, 212)       # 未选中指示器描边
UI_SHADOW = QColor(163, 177, 198)
UI_ACCENT = QColor(74, 102, 224)      # 主按钮 / 选中态
UI_ACCENT_TOP = QColor(116, 148, 248)
UI_ACCENT_BOTTOM = QColor(70, 98, 224)
UI_ACCENT_SHADOW = QColor(76, 106, 208)
UI_INFO = QColor(47, 111, 181)        # 状态文字（正常）
UI_ERROR = QColor(180, 35, 24)        # 状态文字（出错）
UI_FONT = "Microsoft YaHei UI"
UI_TITLE = "端焊三角架"
UI_RADIUS = 12
# 面板版本标记：写进调试日志，便于确认实际加载的是哪一版脚本。
UI_REVISION = 'pyqt5-combo-1'

# QApplication 必须由 Python 侧一直持有引用：一旦没有引用，Qt 会把它连同
# 底层对象一起回收，后续建控件就会直接闪退（且没有任何 Python 报错）。
_QT_APP = [None]


def ensure_qt_app():
    """确保存在 QApplication，并把引用留在模块级。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    _QT_APP[0] = app
    return app


# pywin32 只用于"面板保持在 OPM 之上"这一条：缺了也不影响建模功能。
try:
    import win32gui
    import win32process
except Exception:  # pragma: no cover - 仅在无 pywin32 时触发
    win32gui = None
    win32process = None


def _host_window_hwnd():
    """找出当前进程的主窗口（OPM 主窗），用于"面板始终在软件之上"。"""
    if win32gui is None or win32process is None:
        return None
    candidates = []

    def collect(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            if win32process.GetWindowThreadProcessId(hwnd)[1] != os.getpid():
                return
            if win32gui.GetWindow(hwnd, 4):  # GW_OWNER：跳过被拥有的窗口
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            candidates.append(((right - left) * (bottom - top), hwnd))
        except Exception:
            return

    try:
        win32gui.EnumWindows(collect, None)
    except Exception:
        return None
    return max(candidates)[1] if candidates else None


def keep_above_host(panel, interval_ms=1200):
    """把面板挂成 OPM 的工具设置窗，并周期性地避免被主窗遮挡。

    ``AttachQtToolSetting`` 让面板被 OPM 主窗"拥有"：始终位于主窗之上，
    且 OPM 整体最小化时随主窗一起收起——正是所需的行为。个别机器上仅靠
    它仍会被主窗遮住，所以再加一个只在"OPM 在前台"时才把面板提到最前的
    定时器；OPM 被最小化或切到别的程序时不动，不打扰其它程序。
    """
    try:
        panel.hwnd = int(panel.winId())
        PyCadInputQueue.AttachQtToolSetting(panel.hwnd)
    except Exception:
        _log('attach qt tool setting failed: %s' % traceback.format_exc())

    host = _host_window_hwnd()
    timer = QTimer(panel)
    timer.setInterval(interval_ms)

    def _keep_above():
        if host is None or win32gui is None or not panel.isVisible():
            return
        try:
            if not win32gui.IsWindow(host):
                return
            if win32gui.GetForegroundWindow() != host:
                return
        except Exception:
            return
        try:
            panel.raise_()
        except RuntimeError:
            pass

    timer.timeout.connect(_keep_above)
    timer.start()
    panel._keep_above_timer = timer
    return timer


def rounded_rect(rect, radius):
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    return path


def layer_alpha(color, steps):
    """单层透明度：让 steps 层叠加后正好达到 color 的 alpha。"""
    peak = max(0.0, min(1.0, color.alpha()/255.0))
    if peak <= 0.0:
        return 0
    return max(1, int(round((1.0-(1.0-peak)**(1.0/steps))*255)))


def paint_soft_shadow(painter, rect, radius, color, dx, dy, spread, steps=24):
    """逐层填充叠加出真渐变的外阴影；描边法会在末端留下可见的一圈硬边。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        grow = spread*(1.0-step/float(steps))
        frame = QRectF(rect).translated(dx, dy)
        frame.adjust(-grow, -grow, grow, grow)
        painter.drawRoundedRect(frame, radius+grow, radius+grow)


def paint_inner_shadow(painter, rect, radius, color, dx, dy, depth, steps=24):
    """凹槽内影：把同一形状朝 (dx,dy) 平移后叠填，越靠边越深。"""
    alpha = layer_alpha(color, steps)
    if not alpha:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
    for step in range(steps):
        shift = 1.0-step/float(steps)
        painter.drawRoundedRect(QRectF(rect).translated(dx*shift, dy*shift),
                                radius, radius)


def paint_raised(painter, rect, radius, surface, spread=12.0, dark=118,
                 light=205, gradient=None, shadow=UI_SHADOW):
    """gradient 传 (顶色, 底色) 时改用纵向渐变填充，否则用纯色 surface。"""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    paint_soft_shadow(painter, rect, radius, QColor(255, 255, 255, light),
                      -2.5, -2.5, spread)
    paint_soft_shadow(painter, rect, radius,
                      QColor(shadow.red(), shadow.green(), shadow.blue(), dark),
                      3.0, 4.0, spread)
    painter.setPen(Qt.NoPen)
    if gradient is None:
        painter.setBrush(surface)
    else:
        ramp = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        ramp.setColorAt(0.0, gradient[0])
        ramp.setColorAt(1.0, gradient[1])
        painter.setBrush(ramp)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.restore()


def paint_inset(painter, rect, radius, surface=UI_WELL, depth=10.0, steps=24):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(surface)
    painter.drawRoundedRect(QRectF(rect), radius, radius)
    painter.setClipPath(rounded_rect(rect, radius))
    paint_inner_shadow(painter, rect, radius,
                       QColor(UI_SHADOW.red(), UI_SHADOW.green(),
                              UI_SHADOW.blue(), 150),
                       depth, depth, depth, steps)
    paint_inner_shadow(painter, rect, radius, QColor(255, 255, 255, 230),
                       -depth, -depth, depth, steps)
    painter.restore()


class NeuButton(QPushButton):
    """新拟态按钮：静止凸起，按下转为凹槽；accent 为主操作。"""

    def __init__(self, text, parent=None, accent=False, radius=None,
                 margin_x=15, margin_y=13):
        super().__init__(text, parent)
        self.accent = accent
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumHeight(44+2*margin_y)
        self.setStyleSheet('QPushButton {border: none; background: transparent;'
                           ' font-size: 14px;}')

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin_x, self.margin_y,
                                            -self.margin_x, -self.margin_y)
        radius = self.radius if self.radius else rect.height()/2.0
        hovered = self.underMouse() and self.isEnabled()
        if self.accent:
            if self.isDown():
                top, bottom, spread = (UI_ACCENT_BOTTOM,
                                       UI_ACCENT_BOTTOM.darker(107), 7.0)
            elif hovered:
                top = UI_ACCENT_TOP.lighter(105)
                bottom = UI_ACCENT_BOTTOM.lighter(105)
                spread = 10.0
            else:
                top, bottom, spread = UI_ACCENT_TOP, UI_ACCENT_BOTTOM, 9.0
            paint_raised(painter, rect, radius, UI_CARD, spread=spread, dark=100,
                         light=95, gradient=(top, bottom),
                         shadow=UI_ACCENT_SHADOW)
            painter.setPen(QColor(255, 255, 255))
        elif self.isDown():
            paint_inset(painter, rect, radius, UI_WELL, depth=7.0)
            painter.setPen(UI_TEXT)
        else:
            surface = QColor(247, 249, 253) if hovered else UI_CARD
            paint_raised(painter, rect, radius, surface, spread=9.0, dark=100,
                         gradient=(surface, surface.darker(103)))
            painter.setPen(UI_TEXT)
        font = self.font()
        font.setBold(self.accent)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text())


class NeuIconButton(QWidget):
    """标题栏小图标钮：悬停浮出圆形底，关闭钮悬停为红色。"""

    def __init__(self, parent, kind, callback, danger=False):
        super().__init__(parent)
        self.kind = kind
        self.danger = danger
        self._callback = callback
        self._pressed = False
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        released = self._pressed and self.rect().contains(event.pos())
        self._pressed = False
        self.update()
        if event.button() == Qt.LeftButton and released:
            self._callback()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        active = self.underMouse() or self._pressed
        if active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ERROR if self.danger else QColor(255, 255, 255, 235))
            painter.drawEllipse(QRectF(self.rect()).adjusted(1.0, 1.0,
                                                             -1.0, -1.0))
        if self.danger:
            color = QColor(255, 255, 255) if active else QColor(122, 134, 154)
        else:
            color = UI_MUTED
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        center = self.rect().center()
        cx, cy = center.x(), center.y()
        if self.kind == 'close':
            painter.drawLine(cx-4, cy-4, cx+4, cy+4)
            painter.drawLine(cx-4, cy+4, cx+4, cy-4)
        else:
            painter.drawLine(cx-5, cy, cx+5, cy)


class NeuTitleBar(QWidget):
    """无边框窗口的自绘标题栏，空白处按住可拖动整个窗口。

    只有关闭钮：面板是 OPM 主窗的 owned window，没有任务栏入口，最小化后
    无法再唤回，故不提供最小化。``on_minimize`` 仅为兼容旧调用而保留。
    """

    def __init__(self, title, on_minimize=None, on_close=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._drag_offset = None
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 0, 10, 0)
        row.setSpacing(9)
        dot = QLabel(self)
        dot.setFixedSize(9, 9)
        dot.setStyleSheet('background: #4A66E0; border-radius: 4px;')
        dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        caption = QLabel(title, self)
        caption.setStyleSheet('font-size: 14px; font-weight: 600;'
                              ' color: #39435A;')
        caption.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(dot)
        row.addWidget(caption)
        row.addStretch(1)
        row.addWidget(NeuIconButton(self, 'close', on_close, danger=True))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (event.globalPos()
                                 - self.window().frameGeometry().topLeft())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class NeuCard(QWidget):
    """白色圆角卡片：柔和外影 + 分组标题，content 为内部栅格。"""

    def __init__(self, title, parent=None, radius=15, margin_x=15, margin_y=5,
                 padding=8):
        super().__init__(parent)
        self.radius = radius
        self.margin_x = margin_x
        self.margin_y = margin_y
        outer = QVBoxLayout(self)
        outer.setContentsMargins(margin_x+padding, margin_y+padding,
                                 margin_x+padding, margin_y+padding)
        outer.setSpacing(5)
        caption = QLabel(title, self)
        caption.setStyleSheet('color: #7D8AA0; font-size: 12px;'
                              ' font-weight: 600;')
        outer.addWidget(caption)
        self.content = QGridLayout()
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setHorizontalSpacing(10)
        self.content.setVerticalSpacing(6)
        outer.addLayout(self.content)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin_x, self.margin_y,
                                            -self.margin_x, -self.margin_y)
        paint_raised(painter, rect, self.radius, UI_CARD, spread=7.0,
                     dark=92, light=225)


class NeuPanel(QWidget):
    """凹槽信息面板（规格 / 预览 / 状态）。"""

    def __init__(self, parent=None, radius=14, margin=3, padding=9):
        super().__init__(parent)
        self.radius = radius
        self.margin = margin
        self.content = QVBoxLayout(self)
        self.content.setContentsMargins(margin+padding, margin+padding,
                                        margin+padding, margin+padding)
        self.content.setSpacing(3)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin, self.margin,
                                            -self.margin, -self.margin)
        paint_inset(painter, rect, self.radius, UI_WELL, depth=8.0)


class NeuEdit(QWidget):
    """凹槽输入框：内嵌无边框 QLineEdit，凹槽与留白由自绘完成。"""

    def __init__(self, text='', parent=None, width=84, radius=13, margin=2):
        super().__init__(parent)
        self.radius = radius
        self.margin = margin
        self.edit = QLineEdit(text, self)
        self.edit.setFrame(False)
        self.edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.edit.setFixedWidth(width)
        self.edit.setStyleSheet(
            'QLineEdit {border: none; background: transparent;'
            ' color: #39435A; font-size: 15px; font-weight: 600;'
            ' selection-background-color: #4A66E0; selection-color: #FFFFFF;}')
        row = QHBoxLayout(self)
        row.setContentsMargins(margin+11, margin+4, margin+11, margin+4)
        row.addWidget(self.edit)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def value(self):
        return self.edit.text()

    def set_value(self, text):
        self.edit.setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(self.margin, self.margin,
                                            -self.margin, -self.margin)
        paint_inset(painter, rect, self.radius, UI_WELL, depth=8.0)


class NeuChoice(QRadioButton):
    """自绘单选项：圆环指示器 + 文字，选中为实心主色。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.text())+30, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height()-size)/2.0
        circle = QRectF(4.0, top, size, size)
        if checked:
            painter.setPen(QPen(UI_ACCENT if enabled else UI_MUTED, 2.0))
            painter.setBrush(QColor(255, 255, 255))
        else:
            pen = QPen(UI_ACCENT if (enabled and self.underMouse()) else UI_RING,
                       2.0)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255) if enabled else UI_WELL)
        painter.drawEllipse(circle)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT if enabled else UI_MUTED)
            painter.drawEllipse(circle.adjusted(4.6, 4.6, -4.6, -4.6))
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(4.0+size+8.0, 0.0, self.width()-(12.0+size),
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())


class NeuToggle(QCheckBox):
    """自绘复选项：圆角方格指示器，选中时画白色对勾。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def sizeHint(self):
        metrics = self.fontMetrics()
        return QSize(metrics.horizontalAdvance(self.text())+32, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        checked = self.isChecked()
        size = 16.0
        top = (self.height()-size)/2.0
        box = QRectF(4.0, top, size, size)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT if enabled else UI_MUTED)
            painter.drawRoundedRect(box, 5.0, 5.0)
            pen = QPen(QColor(255, 255, 255), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            mark = QPainterPath()
            mark.moveTo(box.left()+4.0, box.center().y())
            mark.lineTo(box.center().x()-0.6, box.bottom()-4.2)
            mark.lineTo(box.right()-3.4, box.top()+4.0)
            painter.drawPath(mark)
        else:
            pen = QPen(UI_ACCENT if (enabled and self.underMouse()) else UI_RING,
                       2.0)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255) if enabled else UI_WELL)
            painter.drawRoundedRect(box, 5.0, 5.0)
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(4.0+size+9.0, 0.0, self.width()-(13.0+size),
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())


class _ComboItem(QWidget):
    """下拉列表中的一行：悬停高亮，当前项带主色圆点并加粗。"""

    def __init__(self, label, value, on_pick, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = value
        self._on_pick = on_pick
        self._selected = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(30)
        metrics = self.fontMetrics()
        self.setMinimumWidth(metrics.horizontalAdvance(label)+48)

    def set_selected(self, selected):
        if self._selected != selected:
            self._selected = selected
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self._on_pick(self.value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(UI_ACCENT.red(), UI_ACCENT.green(),
                                   UI_ACCENT.blue(), 28))
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(2.0, 1.0, -2.0, -1.0), 7.0, 7.0)
        if self._selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(UI_ACCENT)
            painter.drawEllipse(QRectF(9.0, self.height()/2.0-3.5, 7.0, 7.0))
        font = self.font()
        font.setBold(self._selected)
        painter.setFont(font)
        painter.setPen(UI_TEXT)
        painter.drawText(QRectF(26.0, 0.0, self.width()-32.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label)


class _NeuComboPopup(QWidget):
    """下拉列表弹层：圆角白卡 + 柔影，点击外部自动收起。"""

    MARGIN = 12

    def __init__(self, combo, entries, on_pick):
        super().__init__(combo, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.items = []
        column = QVBoxLayout(self)
        column.setContentsMargins(self.MARGIN, self.MARGIN,
                                  self.MARGIN, self.MARGIN)
        column.setSpacing(1)
        for value, label in entries:
            item = _ComboItem(label, value, on_pick, self)
            self.items.append(item)
            column.addWidget(item)

    def sync(self, current, minimum_width):
        for item in self.items:
            item.set_selected(item.value == current)
        self.setFixedWidth(max(minimum_width, self.sizeHint().width()))
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        edge = self.MARGIN-4.0
        rect = QRectF(self.rect()).adjusted(edge, edge, -edge, -edge)
        paint_raised(painter, rect, 12, UI_CARD, spread=6.0, dark=92, light=225)


class NeuCombo(QWidget):
    """凹槽下拉选择框：闭合时显示当前项，点开后弹出 NeuComboPopup。"""

    def __init__(self, entries, current=None, parent=None, on_change=None,
                 width=None):
        super().__init__(parent)
        self.entries = [(value, label) for value, label in entries]
        self._value = (current if current is not None
                       else (self.entries[0][0] if self.entries else None))
        self._on_change = on_change
        self._popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(40)
        if width is None:
            metrics = self.fontMetrics()
            width = max([metrics.horizontalAdvance(label)
                         for _, label in self.entries] or [0]) + 76
        self.setFixedWidth(width)

    def value(self):
        return self._value

    def label(self):
        for value, label in self.entries:
            if value == self._value:
                return label
        return ''

    def set_value(self, value):
        if value == self._value:
            return
        self._value = value
        self.update()
        if self._on_change is not None:
            self._on_change()

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.open_popup()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def popup_visible(self):
        return self._popup is not None and self._popup.isVisible()

    def open_popup(self):
        # 弹层只建一次，之后复用；hide() 收起但保留，避免每次选择漏一个窗口。
        if self._popup is None:
            self._popup = _NeuComboPopup(self, self.entries, self._pick)
        # 弹层左/上各留 MARGIN 的柔影边距，使白卡与下拉框左沿对齐。
        self._popup.sync(self._value, self.width()+2*_NeuComboPopup.MARGIN)
        self._popup.move(self.mapToGlobal(
            QPoint(-_NeuComboPopup.MARGIN, self.height()-8)))
        self._popup.show()
        self._popup.raise_()

    def _pick(self, value):
        if self._popup is not None:
            self._popup.hide()
        self.set_value(value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        rect = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
        paint_inset(painter, rect, 13, UI_WELL, depth=8.0)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(UI_TEXT if enabled else UI_MUTED)
        painter.drawText(QRectF(15.0, 0.0, self.width()-46.0,
                                float(self.height())),
                         Qt.AlignLeft | Qt.AlignVCenter, self.label())
        # 右侧下拉箭头：悬停或展开时变主色。
        active = enabled and (self.underMouse() or self.popup_visible())
        pen = QPen(UI_ACCENT if active else UI_MUTED, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = self.width()-19.0
        cy = self.height()/2.0 - 1.0
        chevron = QPainterPath()
        chevron.moveTo(cx-5.0, cy-2.5)
        chevron.lineTo(cx, cy+2.5)
        chevron.lineTo(cx+5.0, cy-2.5)
        painter.drawPath(chevron)


# ---------------------------------------------------------------------------
# 工具设置面板
# ---------------------------------------------------------------------------


def _variant_label(variant_key):
    variant = VARIANTS[variant_key]
    return '%s  |  %s  |  %s' % (variant_key, variant['h_beam_specification'],
                                 variant['angle_specification'])


class TriangleBracketSettingsDialog(QWidget):
    """子项 / 尺寸参数选择、预览 / 确定 / 取消面板。"""

    RADIUS = UI_RADIUS

    def __init__(self):
        self._app = ensure_qt_app()
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        # 无边框：标题栏与最小化/关闭钮自绘，便于与卡片风格统一。
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowSystemMenuHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, UI_BG)
        self.setPalette(palette)
        self.setStyleSheet('QWidget {font-family: "Microsoft YaHei UI";}')

        self.placement_origin = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self.variant_combo = None
        # 选项控件按创建顺序登记，供 _set_busy 统一切换可用状态。
        self.option_widgets = []
        self._running = True
        self._allow_close = False
        self._finish_requested = False
        self._event_loop = QEventLoop()

        # 两个防抖定时器：子项选择用短间隔求跟手，文本框用长间隔避免半途重建。
        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(REGENERATE_DELAY_MS)
        self._regen_timer.timeout.connect(self._run_pending_regeneration)
        self._text_timer = QTimer(self)
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(TEXT_REGENERATE_DELAY_MS)
        self._text_timer.timeout.connect(self._run_pending_regeneration)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(NeuTitleBar(UI_TITLE, self._minimize,
                                    self.cancel_tool))

        body = QVBoxLayout()
        body.setContentsMargins(3, 0, 3, 3)
        body.setSpacing(0)
        outer.addLayout(body)

        hint_row = QVBoxLayout()
        hint_row.setContentsMargins(15, 0, 15, 0)
        hint = QLabel("在模型中点取横担左端与既有钢结构焊接面的中心；"
                      "点取后可改 L1 / E，预览会自动重建，点【确定】保留，"
                      "点【取消】或右键放弃。")
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        hint_row.addWidget(hint)
        body.addLayout(hint_row)
        body.addSpacing(6)

        card = NeuCard("构件规格")
        row = 0
        if len(VARIANTS) > 1:
            self.variant_combo = self._combo_row(
                card.content, row, "子项：",
                [(key, _variant_label(key)) for key in sorted(VARIANTS)],
                DEFAULT_VARIANT)
            row += 1
        self.beam_label = self._value()
        self._row(card.content, row, "构件A（横担）：", [self.beam_label])
        row += 1
        self.angle_label = self._value()
        self._row(card.content, row, "构件B（斜撑）：", [self.angle_label])
        body.addWidget(card)

        card = NeuCard("尺寸参数")
        self.l1_edit = self._edit_row(
            card.content, 0, "L1：", "1000", "mm　焊接端面至斜撑上端中心线")
        self.overhang_edit = self._edit_row(
            card.content, 1, "E：", "150", "mm　最远端至斜撑上端外侧斜角（≥150）")
        self.l2_label = self._value()
        self._row(card.content, 2, "横担总长 L2：",
                  [self.l2_label, self._note("mm　自动向上取整，≤2500")], 8)
        body.addWidget(card)

        summary = NeuPanel()
        self.spec_label = self._info("", UI_TEXT)
        summary.content.addWidget(self.spec_label)
        self.preview_info_label = self._info("预览：—", UI_TEXT)
        summary.content.addWidget(self.preview_info_label)
        self.status_label = self._info(
            "请在模型中点取焊接面中心；改参数会自动重建预览。", UI_INFO)
        summary.content.addWidget(self.status_label)
        body.addWidget(summary)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(3, 0, 3, 0)
        button_row.setSpacing(0)
        self.cancel_button = NeuButton("取消")
        self.cancel_button.setFixedWidth(126)
        self.cancel_button.clicked.connect(self.cancel_tool)
        self.export_button = NeuButton("导出 JSON 清单")
        self.export_button.setFixedWidth(150)
        self.export_button.clicked.connect(self.export_bom)
        self.confirm_button = NeuButton("确定", accent=True)
        self.confirm_button.setFixedWidth(126)
        self.confirm_button.clicked.connect(self.confirm_tool)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.confirm_button)
        body.addLayout(button_row)
        self.action_widgets = [
            self.confirm_button, self.cancel_button, self.export_button]

        self.refresh_spec()
        self.setMinimumWidth(520)
        self.adjustSize()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))
        try:
            _stamp = int(os.path.getmtime(os.path.abspath(__file__)))
        except Exception:
            _stamp = 0
        _log('panel built %dx%d rev=%s file=%s mtime=%d'
             % (self.width(), self.height(), UI_REVISION,
                os.path.abspath(__file__), _stamp))
        keep_above_host(self)
        _log('panel attached to host, hwnd=%s' % getattr(self, 'hwnd', None))

    # -- 控件构造 ----------------------------------------------------------

    def _register(self, widget):
        self.option_widgets.append(widget)
        return widget

    def _row(self, grid, row, name, widgets, spacing=18):
        """卡片内一行：左标签 +（横向排列的）控件。"""
        label = QLabel(name, self)
        label.setStyleSheet('color: #39435A; font-size: 13px;')
        grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
        holder = QWidget(self)
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(spacing)
        for widget in widgets:
            line.addWidget(widget)
        line.addStretch(1)
        grid.addWidget(holder, row, 1)
        grid.setColumnStretch(1, 1)
        return holder

    def _combo_row(self, grid, row, name, entries, default):
        combo = self._register(NeuCombo(entries, current=default,
                                        on_change=self.on_options_changed))
        self._row(grid, row, name, [combo], 16)
        return combo

    def _edit_row(self, grid, row, name, value, note):
        field = NeuEdit(value, width=96)
        self._register(field.edit)
        # 文本框用更长的防抖，避免"输入 1000 时刚敲 1 就重建"。
        field.edit.textChanged.connect(self.on_text_changed)
        self._row(grid, row, name, [field, self._note(note)], 8)
        return field

    def _value(self):
        label = QLabel('', self)
        label.setStyleSheet('color: #39435A; font-size: 13px;'
                            ' font-weight: 600;')
        return label

    def _note(self, text):
        label = QLabel(text, self)
        label.setStyleSheet('color: #7D8AA0; font-size: 12px;')
        return label

    def _info(self, text, color):
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setStyleSheet('color: %s; font-size: 11px;' % color.name())
        return label

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        if self.variant_combo is None:
            return DEFAULT_VARIANT
        return self.variant_combo.value() or DEFAULT_VARIANT

    def current_options(self):
        variant_key = self.current_variant()
        if variant_key not in VARIANTS:
            raise ValueError("未知子项：%s。" % variant_key)
        try:
            l1 = float(self.l1_edit.value())
        except (TypeError, ValueError):
            raise ValueError("L1 必须是数字（mm）。")
        try:
            end_overhang = float(self.overhang_edit.value())
        except (TypeError, ValueError):
            raise ValueError("E 必须是数字（mm）。")
        minimum_l1 = _min_l1(variant_key)
        if l1 <= minimum_l1:
            raise ValueError("L1 必须大于 %.3f mm。" % minimum_l1)
        if end_overhang < MIN_END_OVERHANG:
            raise ValueError("E 不得小于 %.0f mm。" % MIN_END_OVERHANG)
        beam_length = calculate_beam_length(l1, end_overhang, variant_key)
        if beam_length > MAX_BEAM_LENGTH:
            raise ValueError("计算得到 L2=%.0f mm，不能大于 %.0f mm。"
                             % (beam_length, MAX_BEAM_LENGTH))
        return {'variant': variant_key, 'l1': l1,
                'end_overhang': end_overhang}

    def set_status(self, message, is_error=False):
        self.status_label.setStyleSheet(
            'color: %s; font-size: 11px;'
            % (UI_ERROR if is_error else UI_INFO).name())
        self.status_label.setText(message)
        QApplication.processEvents()

    def set_result(self, result):
        self.preview_info_label.setText(
            "预览：子项 %s，横担 %s，L2=%.0f mm，斜撑轴长 %.0f mm，"
            "单元含 %d 个子元素。" % (
                result["variant"], result["h_beam_specification"],
                result["beam_length"], result["brace_length"],
                result["child_count"],
            )
        )

    def refresh_spec(self):
        variant_key = self.current_variant()
        variant = VARIANTS.get(variant_key, VARIANTS[DEFAULT_VARIANT])
        angle_width = variant['angle'][0]
        self.beam_label.setText(variant['h_beam_specification'])
        self.angle_label.setText('%s（45°）' % variant['angle_specification'])
        try:
            l1 = float(self.l1_edit.value())
            end_overhang = float(self.overhang_edit.value())
            self.l2_label.setText(
                '%d' % calculate_beam_length(l1, end_overhang, variant_key))
        except (TypeError, ValueError):
            self.l2_label.setText('—')
        self.spec_label.setText(
            "横担 %s + 斜撑 %s；L2 = ceil(L1 + %.0f×√2/2 + E)，≤%.0f mm。"
            % (variant['h_beam_specification'], variant['angle_specification'],
               angle_width, MAX_BEAM_LENGTH))

    def _set_busy(self, busy):
        for widget in self.option_widgets + self.action_widgets:
            widget.setEnabled(not busy)
        QApplication.processEvents()

    def on_options_changed(self, *_unused):
        """子项变化：刷新摘要，并按短防抖重建预览。"""
        self.refresh_spec()
        self._schedule_regeneration(self._regen_timer)

    def on_text_changed(self, *_unused):
        """文本框输入：刷新摘要，按长防抖重建，避免数字只打了一半。"""
        self.refresh_spec()
        self._schedule_regeneration(self._text_timer)

    def _schedule_regeneration(self, timer):
        self._cancel_pending_regeneration()
        if self.placement_origin is None:
            return
        timer.start()

    def _cancel_pending_regeneration(self):
        self._regen_timer.stop()
        self._text_timer.stop()

    def _run_pending_regeneration(self):
        self.regenerate()

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, placement_point=None):
        """按当前选项重建预览：先建新的一版，成功后再删掉旧的。"""
        self._cancel_pending_regeneration()
        if placement_point is not None:
            self.placement_origin = _point_to_mm(placement_point)
        if self.placement_origin is None:
            return None

        try:
            options = self.current_options()
        except ValueError as error:
            self.set_status("参数有误：%s" % error, True)
            return None

        self._set_busy(True)
        self.set_status("正在生成端焊三角架预览，请稍候……")
        try:
            handle, result, deleted = replace_end_welded_triangle_bracket(
                options['l1'], options['end_overhang'], self.placement_origin,
                self.preview_handle, options['variant']
            )
        except Exception as error:
            message = "端焊三角架生成失败：%s" % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log('preview failed: %s\n%s' % (error, traceback.format_exc()))
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        self.set_result(result)
        message = (
            "预览已更新：子项 %s，横担 %s，L2=%.0f mm，单元含 %d 个子元素。%s"
            "改参数会自动重建；点【确定】保留，点【取消】放弃。"
            % (result["variant"], result["h_beam_specification"],
               result["beam_length"], result["child_count"],
               "已替换上一版预览。" if deleted else "")
        )
        if result["warnings"]:
            message += "注意：%s" % "；".join(result["warnings"])
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return _delete_preview(handle)

    def export_bom(self):
        output_path = export_triangle_bracket_bom_json()
        if output_path is not None:
            self.set_status("清单已导出：%s" % output_path)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        self._finish_requested = True

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self._finish_requested = True

    def finish_tool(self):
        """结束原生工具并收起面板：点【确定】/【取消】/关闭都走这里，退回默认命令。"""
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log('StartDefaultCommand failed: %s' % traceback.format_exc())
        self.shutdown()

    def shutdown(self):
        """由工具的 _OnCleanup 调用：收起窗口并结束事件泵。"""
        _log('panel shutdown')
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            pass

    # -- 窗口 --------------------------------------------------------------

    def _minimize(self):
        self.showMinimized()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(210, 218, 231), 1.0))
        painter.setBrush(UI_BG)
        painter.drawRoundedRect(frame, self.RADIUS, self.RADIUS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        # 关窗口等同于取消：先撤掉预览，再由主循环退出原生工具。
        event.ignore()
        self.cancel_tool()

    def run_dialog_loop(self):
        """Qt 事件泵与 Bentley 主循环交替，直到面板收起。"""
        screen = QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.center().x()-self.width()//2,
                      area.center().y()-self.height()//2)
        self.show()
        self.raise_()
        self.activateWindow()
        _log('panel shown, entering event pump')
        while self._running:
            self._event_loop.processEvents()
            if self._finish_requested:
                self._finish_requested = False
                self.finish_tool()
                continue
            PyCadInputQueue.PythonMainLoop()
        self._teardown_window()

    def _teardown_window(self):
        """退出事件泵后收尾：关闭窗口、冲刷重绘并延迟销毁，避免 UI 残留。

        无边框 + setMask 的自绘窗口若只 ``close()`` 不重绘，容易在屏幕上留下
        残影；顶层窗口不 ``deleteLater()`` 会一直驻留。这里显式处理。
        """
        try:
            self._running = False
            self._allow_close = True
            self.close()
        except RuntimeError:
            return
        QApplication.processEvents()
        try:
            self.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        except (RuntimeError, TypeError):
            pass
        QApplication.processEvents()


class TriangleBracketPlacementTool(DgnPrimitiveTool):
    """点取横担左端焊接面中心并放置端焊三角架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('TriangleBracketPlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            '请点取横担左端与既有钢结构焊接面的中心；点取后可改 L1 / E，'
            '预览会自动重建，点【确定】保留，点【取消】或右键放弃。'
        )

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            QTimer.singleShot(0, settings.cancel_tool)
        return True

    def _OnCleanup(self):
        settings = self.tool_settings
        if settings is None:
            return
        self.tool_settings = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(TriangleBracketPlacementTool, '_active_settings', None)
            if active is not None:
                try:
                    if active._running:
                        active.raise_()
                        active.activateWindow()
                        return None
                except RuntimeError:
                    pass
        settings = (
            tool_settings if tool_settings is not None
            else TriangleBracketSettingsDialog()
        )
        if owner:
            TriangleBracketPlacementTool._active_settings = settings
        tool = TriangleBracketPlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_dialog_loop()
        finally:
            if owner:
                TriangleBracketPlacementTool._active_settings = None
        return tool


def show_triangle_bracket_dialog():
    """显示端焊三角架的 PyQt5 工具设置面板并安装放置工具。"""
    try:
        TriangleBracketPlacementTool.InstallNewInstance(0)
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('端焊三角架工具启动失败：%s\n%s' % (error, detail))
        try:
            QMessageBox.critical(None, UI_TITLE,
                                 '工具启动失败：%s' % error)
        except Exception:
            pass
        return None
    return None


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    return show_triangle_bracket_dialog()


if __name__ == '__main__':
    PyMain()
