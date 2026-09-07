# -*- coding: utf-8 -*-
"""MicroStation 灭火器箱生成、附加属性及统计工具。

运行本脚本后：
1. 依次选择灭火器类型、容量，再由程序限定 XMDDG 箱型；
2. 在模型中点取箱体左下前角的中心定位点；
3. 生成红色钢板灭火器箱及上盖，正面带“灭火器箱”标识；
4. 通过 ItemType 保存构件附加项，可统计箱体数量及灭火器数量，
   并可导出 JSON 清单。

坐标约定（单位均为 mm）：X=长边，Y=短边/进深，Z=高度；箱体正面朝 -Y。
"""

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

import json
import math
import os
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape


DEBUG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         u'灭火器箱_debug_log.txt')
USER_SELECTION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'灭火器箱_上次选型.json')
ITEM_LIBRARY_NAME = 'FireProtectionComponents'
ITEM_TYPE_PREFIX = 'FireExtinguisherBox'
CELL_NAME = 'FireExtinguisherBox'

# 默认 MicroStation 色表中 3 为红色，0 为白色。若项目使用自定义色表，可修改这两个值。
RED_COLOR_INDEX = 3
YELLOW_COLOR_INDEX = 6

WALL_THICKNESS = 2.0
LID_CLEARANCE = 1.0
BODY_LID_FUSE_OVERLAP = 0.5
VERTICAL_CORNER_RADIUS = 20.0
HANDLE_PROJECTION = 12.0
HANDLE_WIDTH = 80.0
HANDLE_HEIGHT = 12.0

# XF 139-2009 / GA 139-2009 表 1：XMDDG 单体类、置地型、翻盖式，2具装。
# 坐标尺寸按 X=宽度 l1、Y=深度 l2、Z=整体高度(l4+l6) 使用。
BOX_PRESETS = {
    'XMDDG12': {
        'display_name': u'XMDDG 12｜单体-置地型-翻盖式（2具）',
        'dimensions': (330.0, 160.0, 530.0),
        'l1': 330.0, 'l2': 160.0, 'l4': 450.0, 'l5': 225.0, 'l6': 80.0,
        'load_n': 80.0, 'test_cylinder_diameter_mm': 120.0,
        'source_dimensions': u'l1×l2×(l4+l6) = 330×160×530 mm',
        'capacity_description': u'2L水基 / 2kg干粉 / 2kg洁净气体（均为2具）',
    },
    'XMDDG22': {
        'display_name': u'XMDDG 22｜单体-置地型-翻盖式（2具）',
        'dimensions': (410.0, 200.0, 680.0),
        'l1': 410.0, 'l2': 200.0, 'l4': 600.0, 'l5': 300.0, 'l6': 80.0,
        'load_n': 140.0, 'test_cylinder_diameter_mm': 140.0,
        'source_dimensions': u'l1×l2×(l4+l6) = 410×200×680 mm',
        'capacity_description': u'2kg二氧化碳 / 3L水基 / 4kg干粉 / 4kg洁净气体（均为2具）',
    },
    'XMDDG32': {
        'display_name': u'XMDDG 32｜单体-置地型-翻盖式（2具）',
        'dimensions': (470.0, 240.0, 830.0),
        'l1': 470.0, 'l2': 240.0, 'l4': 750.0, 'l5': 375.0, 'l6': 80.0,
        'load_n': 200.0, 'test_cylinder_diameter_mm': 170.0,
        'source_dimensions': u'l1×l2×(l4+l6) = 470×240×830 mm',
        'capacity_description': u'3kg二氧化碳 / 6L水基 / 6kg干粉 / 6kg洁净气体（均为2具）',
    },
}

EXTINGUISHER_TYPES = {
    u'干粉灭火器': {'unit': u'kg', 'capacities': (2, 3, 4, 5, 6)},
    u'二氧化碳灭火器': {'unit': u'kg', 'capacities': (2, 3)},
    u'水基型灭火器': {'unit': u'L', 'capacities': (2, 3, 4, 5, 6)},
    u'洁净气体灭火器': {'unit': u'kg', 'capacities': (2, 3, 4, 5, 6)},
}

# 对每一种灭火器记录三种 XMDDG 箱型所允许的最大容量。选择时取最小合格箱型。
BOX_CAPACITY_LIMITS = {
    u'干粉灭火器': ((2, 'XMDDG12'), (4, 'XMDDG22'), (6, 'XMDDG32')),
    u'二氧化碳灭火器': ((2, 'XMDDG22'), (3, 'XMDDG32')),
    u'水基型灭火器': ((2, 'XMDDG12'), (3, 'XMDDG22'), (6, 'XMDDG32')),
    u'洁净气体灭火器': ((2, 'XMDDG12'), (4, 'XMDDG22'), (6, 'XMDDG32')),
}

ITEM_PROPERTIES = (
    ('ComponentName', CustomProperty.Type1.eString),
    ('BoxModel', CustomProperty.Type1.eString),
    ('ExtinguisherModel', CustomProperty.Type1.eString),
    ('ExtinguisherType', CustomProperty.Type1.eString),
    ('ExtinguisherCapacity', CustomProperty.Type1.eInteger),
    ('CapacityUnit', CustomProperty.Type1.eString),
    ('CapacityDescription', CustomProperty.Type1.eString),
    ('WidthMm', CustomProperty.Type1.eDouble),
    ('DepthMm', CustomProperty.Type1.eDouble),
    ('HeightMm', CustomProperty.Type1.eDouble),
    ('L1Mm', CustomProperty.Type1.eDouble),
    ('L2Mm', CustomProperty.Type1.eDouble),
    ('L4Mm', CustomProperty.Type1.eDouble),
    ('L5Mm', CustomProperty.Type1.eDouble),
    ('L6Mm', CustomProperty.Type1.eDouble),
    ('LoadN', CustomProperty.Type1.eDouble),
    ('StiffnessTestCylinderDiameterMm', CustomProperty.Type1.eDouble),
    ('BoxQuantity', CustomProperty.Type1.eInteger),
    ('ExtinguisherQuantity', CustomProperty.Type1.eInteger),
    ('SurfaceColor', CustomProperty.Type1.eString),
    ('TextColor', CustomProperty.Type1.eString),
    ('FrontText', CustomProperty.Type1.eString),
    ('EnglishFrontText', CustomProperty.Type1.eString),
    ('FireAlarmText', CustomProperty.Type1.eString),
    ('TopText', CustomProperty.Type1.eString),
    ('CoordinateConvention', CustomProperty.Type1.eString),
    ('Unit', CustomProperty.Type1.eString),
)


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as output:
            output.write(str(message) + '\n')
    except Exception:
        pass


def _load_last_selection():
    """Return a previously saved UI selection, or an empty dict when unavailable."""
    try:
        with open(USER_SELECTION_FILE, 'r', encoding='utf-8') as source:
            value = json.load(source)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_last_selection(extinguisher_type, capacity, box_key):
    try:
        with open(USER_SELECTION_FILE, 'w', encoding='utf-8') as output:
            json.dump({
                'extinguisherType': extinguisher_type,
                'capacity': int(capacity),
                'boxKey': box_key,
            }, output, ensure_ascii=False, indent=2)
        return True
    except Exception as error:
        _log('selection save exception: %r' % error)
        return False


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerStorage()


def mm(value, dgn_model=None):
    return float(value) * _uor_per_mm(dgn_model)


def _ec_value(value):
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(value)
    return ec_value


def _safe_name(value):
    """Return an ItemType-safe ASCII suffix."""
    return ''.join(ch if ch.isalnum() else '_' for ch in str(value))


def _extinguisher_model_label(extinguisher_type, capacity):
    return u'%s %s%s' % (extinguisher_type, capacity,
                          EXTINGUISHER_TYPES[extinguisher_type]['unit'])


def _recommended_box_key(extinguisher_type, capacity):
    eligible = _eligible_box_keys(extinguisher_type, capacity)
    return eligible[0] if eligible else None


def _eligible_box_keys(extinguisher_type, capacity):
    """Return every standard box whose allowed maximum covers the selection."""
    return tuple(box_key for maximum_capacity, box_key in
                 BOX_CAPACITY_LIMITS[extinguisher_type]
                 if capacity <= maximum_capacity)


def _item_type_name(box_key, extinguisher_type, capacity):
    return '%s_%s_%s' % (ITEM_TYPE_PREFIX, _safe_name(box_key),
                          _safe_name(_extinguisher_model_label(
                              extinguisher_type, capacity)))


def _metadata(box_key, extinguisher_type, capacity):
    preset = BOX_PRESETS[box_key]
    width, depth, height = preset['dimensions']
    return {
        'ComponentName': u'XMDDG单体-置地型-翻盖式灭火器箱',
        'BoxModel': preset['display_name'],
        'ExtinguisherModel': _extinguisher_model_label(extinguisher_type, capacity),
        'ExtinguisherType': extinguisher_type,
        'ExtinguisherCapacity': int(capacity),
        'CapacityUnit': EXTINGUISHER_TYPES[extinguisher_type]['unit'],
        'CapacityDescription': preset['capacity_description'],
        'WidthMm': float(width),
        'DepthMm': float(depth),
        'HeightMm': float(height),
        'L1Mm': float(preset['l1']),
        'L2Mm': float(preset['l2']),
        'L4Mm': float(preset['l4']),
        'L5Mm': float(preset['l5']),
        'L6Mm': float(preset['l6']),
        'LoadN': float(preset['load_n']),
        'StiffnessTestCylinderDiameterMm': float(preset['test_cylinder_diameter_mm']),
        'BoxQuantity': 1,
        'ExtinguisherQuantity': 2,
        'SurfaceColor': u'红色',
        'TextColor': u'黄色',
        'FrontText': u'灭火器箱',
        'EnglishFrontText': 'Fire Extinguisher Cabinet',
        'FireAlarmText': u'火警电话',
        'TopText': u'消防器材，严禁挪用',
        'CoordinateConvention': u'X=长边，Y=短边/进深，Z=高度，正面朝-Y',
        'Unit': u'箱',
    }


def _get_or_create_item_type(box_key, extinguisher_type, capacity):
    """Create a dedicated ItemType whose defaults are this cabinet's metadata."""
    defaults = _metadata(box_key, extinguisher_type, capacity)
    dgn_file = ISessionMgr.GetActiveDgnFile()
    name = _item_type_name(box_key, extinguisher_type, capacity)
    try:
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        changed = False
        if library is None:
            library = ItemTypeLibrary(ITEM_LIBRARY_NAME, dgn_file, False)
            changed = True
        item_type = library.GetItemTypeByName(name)
        if item_type is None:
            item_type = library.AddItemType(name, False)
            changed = True
        if item_type is None:
            _log('cannot create ItemType: %s' % name)
            return None
        for property_name, property_type in ITEM_PROPERTIES:
            item_property = item_type.GetPropertyByName(property_name)
            if item_property is None:
                item_property = item_type.AddProperty(property_name, False)
                if item_property is None or not item_property.SetType(property_type):
                    _log('cannot add ItemType property: %s' % property_name)
                    return None
                if not item_property.SetDefaultValue(_ec_value(defaults[property_name])):
                    _log('cannot set ItemType default: %s' % property_name)
                    return None
                changed = True
        if changed and not library.Write():
            _log('cannot write ItemType library')
            return None
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        return library.GetItemTypeByName(name)
    except Exception as error:
        _log('ItemType setup error: %r' % error)
        return None


def _attach_cabinet_item(element, box_key, extinguisher_type, capacity):
    item_type = _get_or_create_item_type(box_key, extinguisher_type, capacity)
    if item_type is None:
        return False
    try:
        host = CustomItemHost(element, False)
        try:
            item = host.ApplyCustomItem(item_type)
        except TypeError as error:
            # Some MicroStation Python versions complete the native attach but
            # cannot convert the DgnECInstance return object to Python.
            if 'Unable to convert function return value' in str(error):
                return True
            raise
        if item is None:
            return False
        item.WriteChanges()
        return True
    except Exception as error:
        _log('ItemType attach error: %r' % error)
        return False


def _apply_color(element, color_index):
    try:
        setter = ElementPropertiesSetter()
        setter.SetColor(color_index)
        setter.SetWeight(1)
        setter.Apply(element)
        return True
    except Exception as error:
        _log('set color error: %r' % error)
        return False


def _create_box_body(minimum, maximum, dgn_model):
    """Create an un-added rectangular solid body from two mm-coordinate corners."""
    min_x, min_y, min_z = minimum
    max_x, max_y, max_z = maximum
    if max_x <= min_x or max_y <= min_y or max_z <= min_z:
        return None
    points = DPoint3dArray()
    for x, y in ((min_x, min_y), (max_x, min_y),
                 (max_x, max_y), (min_x, max_y)):
        points.append(DPoint3d(mm(x, dgn_model), mm(y, dgn_model),
                               mm(min_z, dgn_model)))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(profile, None, points,
                                             dgn_model.Is3d(), dgn_model)
    if BentleyStatus.eSUCCESS != status:
        return None
    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        return None
    sweep = DVec3d(0.0, 0.0, mm(max_z - min_z, dgn_model))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        return None
    return body_result[1]


def _create_rounded_box_body(minimum, maximum, radius, dgn_model):
    """Create a solid with four true-radius vertical (Z-axis) corner edges."""
    min_x, min_y, min_z = minimum
    max_x, max_y, max_z = maximum
    if (max_x <= min_x or max_y <= min_y or max_z <= min_z or
            radius <= 0.0 or radius * 2.0 >= min(max_x - min_x, max_y - min_y)):
        return None

    def point(x, y):
        return DPoint3d(mm(x, dgn_model), mm(y, dgn_model), mm(min_z, dgn_model))

    outer = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    outer.Add(ICurvePrimitive.CreateLine(DSegment3d(
        point(min_x + radius, min_y), point(max_x - radius, min_y))))
    outer.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromArcCenterStartEnd(
        point(max_x - radius, min_y + radius), point(max_x - radius, min_y),
        point(max_x, min_y + radius))))
    outer.Add(ICurvePrimitive.CreateLine(DSegment3d(
        point(max_x, min_y + radius), point(max_x, max_y - radius))))
    outer.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromArcCenterStartEnd(
        point(max_x - radius, max_y - radius), point(max_x, max_y - radius),
        point(max_x - radius, max_y))))
    outer.Add(ICurvePrimitive.CreateLine(DSegment3d(
        point(max_x - radius, max_y), point(min_x + radius, max_y))))
    outer.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromArcCenterStartEnd(
        point(min_x + radius, max_y - radius), point(min_x + radius, max_y),
        point(min_x, max_y - radius))))
    outer.Add(ICurvePrimitive.CreateLine(DSegment3d(
        point(min_x, max_y - radius), point(min_x, min_y + radius))))
    outer.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromArcCenterStartEnd(
        point(min_x + radius, min_y + radius), point(min_x, min_y + radius),
        point(min_x + radius, min_y))))

    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
    profile.Add(outer)
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    path.Add(ICurvePrimitive.CreateLine(DSegment3d(
        point(min_x + radius, min_y),
        DPoint3d(mm(min_x + radius, dgn_model), mm(min_y, dgn_model),
                 mm(max_z, dgn_model)))))
    try:
        result = SolidUtil.Create.BodyFromSweep(profile, path, dgn_model,
                                                False, True, False)
    except Exception as error:
        _log('rounded body sweep exception: %r' % error)
        return None
    if result is None or BentleyStatus.eSUCCESS != result[0]:
        _log('rounded body sweep failed: %r' % (result[0] if result else None,))
        return None
    return result[1]


def _subtract_body(target_body, tool_body):
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanSubtract(target_body, tools)
    except Exception as error:
        _log('BooleanSubtract exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if BentleyStatus.eSUCCESS != status:
        _log('BooleanSubtract failed: %r' % status)
        return False
    return True


def _union_body(target_body, tool_body):
    """Fuse two touching/overlapping solid bodies into one body."""
    union_functions = []
    for owner_name, owner in (('SolidUtil.Modify', SolidUtil.Modify),
                              ('SolidUtil', SolidUtil)):
        for function_name in ('BodyBooleanUnion', 'BooleanUnion'):
            function = getattr(owner, function_name, None)
            if function is not None:
                union_functions.append((owner_name + '.' + function_name, function))
    for function_name, union_function in union_functions:
        try:
            if function_name.endswith('.BooleanUnion'):
                tools = ISolidKernelEntityPtrArray()
                tools.append(tool_body)
                status = union_function(target_body, tools)
            else:
                status = union_function(target_body, tool_body)
            if isinstance(status, tuple):
                status = status[0]
            if BentleyStatus.eSUCCESS == status:
                return True
            _log('%s returned %r' % (function_name, status))
        except Exception as error:
            _log('%s exception: %r' % (function_name, error))
    return False


def _add_body_to_model(body, dgn_model, color_index, label):
    element = _body_to_element(body, dgn_model, color_index, label)
    if element is None:
        return None
    if BentleyStatus.eSUCCESS != element.AddToModel():
        _log('%s: AddToModel failed' % label)
        return None
    return element


def _body_to_element(body, dgn_model, color_index, label):
    element = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
            element, body, None, dgn_model):
        _log('%s: BodyToElement failed' % label)
        return None
    _apply_color(element, color_index)
    return element


def _create_solid_box(minimum, maximum, dgn_model, color_index, label,
                      add_to_model=True):
    body = _create_box_body(minimum, maximum, dgn_model)
    if body is None:
        _log('%s: body creation failed' % label)
        return None
    if add_to_model:
        return _add_body_to_model(body, dgn_model, color_index, label)
    return _body_to_element(body, dgn_model, color_index, label)


def _create_text(text, origin, text_height, dgn_model, orientation=None,
                 color_index=YELLOW_COLOR_INDEX, add_to_model=True):
    """Create a text element, optionally with a model-space orientation matrix."""
    try:
        text_props = TextBlockProperties.Create(dgn_model)
        paragraph_props = ParagraphProperties.Create(dgn_model)
        justification = getattr(TextElementJustification, 'CenterBaseline', None)
        if justification is None:
            justification = getattr(TextElementJustification, 'eCenterBaseline', None)
        if justification is None:
            raise RuntimeError('CenterBaseline text justification is unavailable')
        paragraph_props.SetJustification(justification)
        font = DgnFontManager.GetDefaultTrueTypeFont()
        size = DPoint2d(mm(text_height, dgn_model), mm(text_height, dgn_model))
        run_props = RunProperties.Create(font, size, dgn_model)
        text_block = TextBlock(text_props, paragraph_props, run_props, dgn_model)
        text_block.AppendText(text)
        text_block.SetUserOrigin(DPoint3d(mm(origin[0], dgn_model),
                                           mm(origin[1], dgn_model),
                                           mm(origin[2], dgn_model)))
        if orientation is not None:
            text_block.SetOrientation(orientation)
        element = EditElementHandle()
        status = TextElemHandler.CreateElement(element, None, text_block)
        if status != TextBlockToElementResult.eTEXTBLOCK_TO_ELEMENT_RESULT_Success:
            _log('text creation failed: %r' % status)
            return None
        _apply_color(element, color_index)
        if not add_to_model:
            return element
        if BentleyStatus.eSUCCESS != element.AddToModel():
            _log('text AddToModel failed')
            return None
        return element
    except Exception as error:
        _log('text exception: %r' % error)
        return None


def _create_cabinet_cell(children, dgn_model):
    """Place all coloured parts as one orphan Cell that moves as one element."""
    cell = EditElementHandle()

    def status_is_success(status):
        # Some MicroStation Python bindings expose these C++ void methods as
        # Python calls returning None after they have successfully modified eeh.
        return status is None or status == BentleyStatus.eSUCCESS

    try:
        status = NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, CELL_NAME, dgn_model.Is3d(), dgn_model)
        if not status_is_success(status):
            _log('cell header creation failed: %r' % status)
            return None
        if not cell.IsValid():
            _log('cell header creation returned no valid element')
            return None
        for child in children:
            if child is None:
                continue
            status = NormalCellHeaderHandler.AddChildElement(cell, child)
            if not status_is_success(status):
                _log('cell child add failed: %r' % status)
                return None
        status = NormalCellHeaderHandler.AddChildComplete(cell)
        if not status_is_success(status):
            _log('cell finalization failed: %r' % status)
            return None
        if BentleyStatus.eSUCCESS != cell.AddToModel():
            _log('cell AddToModel failed')
            return None
        return cell
    except Exception as error:
        _log('cell creation exception: %r' % error)
        return None


def _delete_created(elements):
    for element in reversed(elements):
        try:
            element.DeleteFromModel()
        except Exception:
            pass


def create_fire_extinguisher_box(box_key, extinguisher_type, capacity,
                                 origin=(0.0, 0.0, 0.0)):
    """Generate one cabinet Cell and attach its quantity metadata to the Cell.

    ``origin`` is the centre of the cabinet's bottom-front edge. The cabinet
    extends equally along X, backward along +Y, and upward along +Z.
    """
    if box_key not in BOX_PRESETS:
        raise ValueError('unknown box preset: %s' % box_key)
    if extinguisher_type not in EXTINGUISHER_TYPES:
        raise ValueError('unknown extinguisher type: %s' % extinguisher_type)
    if capacity not in EXTINGUISHER_TYPES[extinguisher_type]['capacities']:
        raise ValueError('unsupported extinguisher capacity: %s' % capacity)
    eligible_box_keys = _eligible_box_keys(extinguisher_type, capacity)
    if box_key not in eligible_box_keys:
        raise ValueError('box %s is not a standard match for %s' %
                         (box_key, _extinguisher_model_label(extinguisher_type, capacity)))

    dgn_model = ISessionMgr.GetActiveDgnModel()
    width, depth, height = BOX_PRESETS[box_key]['dimensions']
    if min(width, depth, height) <= 2.0 * WALL_THICKNESS:
        raise ValueError('box dimensions are too small for the selected wall thickness')

    ox, oy, oz = origin
    left, right = ox - width / 2.0, ox + width / 2.0
    front, rear = oy, oy + depth
    bottom, top = oz, oz + height
    lid_height = BOX_PRESETS[box_key]['l6']
    lid_bottom = top - lid_height
    body_top = top - WALL_THICKNESS + BODY_LID_FUSE_OVERLAP
    if lid_bottom <= bottom + WALL_THICKNESS:
        raise ValueError('total height must exceed lid height plus wall thickness')
    parts = []

    # A rounded outer shell, opened at the front by the internal cut. Its four
    # corner edges parallel to Z are true arcs of VERTICAL_CORNER_RADIUS.
    body_outer = _create_rounded_box_body(
        (left, front, bottom), (right, rear, body_top),
        VERTICAL_CORNER_RADIUS, dgn_model)
    body_inner = _create_rounded_box_body(
        (left + WALL_THICKNESS, front + WALL_THICKNESS, bottom + WALL_THICKNESS),
        (right - WALL_THICKNESS, rear - WALL_THICKNESS, body_top + 1.0),
        max(1.0, VERTICAL_CORNER_RADIUS - WALL_THICKNESS), dgn_model)
    if body_outer is None or body_inner is None or not _subtract_body(body_outer, body_inner):
        _log('main shell creation failed')
        return None
    lid_overhang = WALL_THICKNESS + LID_CLEARANCE
    lid_outer = _create_rounded_box_body(
        (left - lid_overhang, front - lid_overhang, lid_bottom),
        (right + lid_overhang, rear + lid_overhang, top),
        VERTICAL_CORNER_RADIUS, dgn_model)
    lid_inner = _create_rounded_box_body(
        (left - LID_CLEARANCE, front - LID_CLEARANCE, lid_bottom - 1.0),
        (right + LID_CLEARANCE, rear + LID_CLEARANCE, top - WALL_THICKNESS),
        max(1.0, VERTICAL_CORNER_RADIUS - WALL_THICKNESS), dgn_model)
    if lid_outer is None or lid_inner is None or not _subtract_body(lid_outer, lid_inner):
        _log('lid shell creation failed')
        return None
    if not _union_body(body_outer, lid_outer):
        _log('main shell and lid cannot be fused')
        return None
    case = _body_to_element(body_outer, dgn_model, RED_COLOR_INDEX, 'integrated cabinet and lid')
    if case is None:
        return None
    parts.append(case)

    # +90° around X maps text XY to XZ and gives it the requested -Y normal.
    front_orientation = RotMatrix.FromVectorAndRotationAngle(
        DVec3d.From(1.0, 0.0, 0.0), math.pi / 2.0)
    text_height = max(18.0, min(height * 0.10, 38.0))
    phone_height = max(12.0, min(text_height * 0.55, 20.0))
    chinese_text_z = bottom + height * 0.62
    english_label = 'Fire Extinguisher Cabinet'
    english_text_height = max(
        10.0,
        min(text_height * 0.55,
            (width * 0.82) / (len(english_label) * 0.65)))
    english_text = _create_text(
        english_label,
        # Keep a full clear text-height gap above the Chinese title so the two
        # baselines cannot overlap with common TrueType font metrics.
        (ox, front - 0.2, chinese_text_z + text_height * 1.65),
        english_text_height, dgn_model, front_orientation, add_to_model=False)
    if english_text is not None:
        parts.append(english_text)
    main_text = _create_text(
        u'灭火器箱',
        (ox, front - 0.2, chinese_text_z),
        text_height, dgn_model, front_orientation, add_to_model=False)
    if main_text is not None:
        parts.append(main_text)

    phone_text = _create_text(
        u'火警电话',
        (ox, front - 0.2, bottom + height * 0.16),
        phone_height, dgn_model, front_orientation, add_to_model=False)
    if phone_text is not None:
        parts.append(phone_text)

    top_text = u'消防器材，严禁挪用'
    top_text_height = max(11.0, min(20.0, width / 12.0))
    top_label = _create_text(
        top_text,
        (ox, front + depth / 2.0, top + 0.2),
        top_text_height, dgn_model, add_to_model=False)
    if top_label is not None:
        parts.append(top_label)
    if english_text is None or main_text is None or phone_text is None or top_label is None:
        _log('cabinet was created but one or more required text elements were not placed')

    # Two red handles are placed on the lid end faces whose outward normals
    # are -X and +X, respectively.
    grip_width = min(HANDLE_WIDTH, depth + 2.0 * lid_overhang - 2.0 * WALL_THICKNESS)
    grip_y_min = front - lid_overhang + (
        depth + 2.0 * lid_overhang - grip_width) / 2.0
    grip_z_min = lid_bottom + (lid_height - HANDLE_HEIGHT) / 2.0
    left_handle = _create_solid_box(
        (left - lid_overhang - HANDLE_PROJECTION, grip_y_min, grip_z_min),
        (left - lid_overhang, grip_y_min + grip_width, grip_z_min + HANDLE_HEIGHT),
        dgn_model, RED_COLOR_INDEX, 'left lid handle', add_to_model=False)
    right_handle = _create_solid_box(
        (right + lid_overhang, grip_y_min, grip_z_min),
        (right + lid_overhang + HANDLE_PROJECTION, grip_y_min + grip_width,
         grip_z_min + HANDLE_HEIGHT),
        dgn_model, RED_COLOR_INDEX, 'right lid handle', add_to_model=False)
    if left_handle is not None:
        parts.append(left_handle)
    if right_handle is not None:
        parts.append(right_handle)

    cell = _create_cabinet_cell(parts, dgn_model)
    if cell is None:
        _log('cabinet Cell creation failed')
        return None
    if not _attach_cabinet_item(cell, box_key, extinguisher_type, capacity):
        _log('cabinet item attach failed; removing incomplete cabinet')
        cell.DeleteFromModel()
        return None
    model_label = _extinguisher_model_label(extinguisher_type, capacity)
    _log('created cabinet Cell: preset=%s, extinguisher=%s, cell=%d' %
         (box_key, model_label, cell.GetElementId()))
    return {'cell': cell, 'parts': tuple(parts), 'boxKey': box_key,
            'extinguisherModel': model_label}


def _read_item_value(item, property_name, kind):
    value = ECValue()
    status = item.GetValue(value, property_name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or value.IsNull():
        return None
    if kind == 'integer':
        return value.GetInteger()
    if kind == 'double':
        return value.GetDouble()
    return value.GetString()


def get_fire_extinguisher_box_statistics():
    """Read all cabinet ItemTypes in the active DGN and return detail + totals."""
    dgn_file = ISessionMgr.GetActiveDgnFile()
    library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
    if library is None:
        return {'records': [], 'summary': [], 'totalBoxCount': 0,
                'totalExtinguisherCount': 0}
    scope = FindInstancesScope.CreateScope(
        dgn_file, FindInstancesScopeOption(DgnECHostType.eElement, False))
    query = ECQuery.CreateQuery(ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses)
    schema_name = str(library.GetInternalName())
    records = []
    summary_map = {}
    for item in DgnECManager.GetManager().FindInstances(scope, query)[0]:
        item_class = item.GetClass()
        if (str(item_class.GetSchema().GetName()) != schema_name or
                not str(item_class.GetName()).startswith(ITEM_TYPE_PREFIX + '_')):
            continue
        element_instance = item.GetAsElementInstance()
        if element_instance is None:
            continue
        record = {
            'elementId': int(element_instance.ElementHandle.ElementId),
            'itemType': str(item_class.GetName()),
            'boxModel': _read_item_value(item, 'BoxModel', 'string'),
            'extinguisherModel': _read_item_value(item, 'ExtinguisherModel', 'string'),
            'capacityDescription': _read_item_value(item, 'CapacityDescription', 'string'),
            'widthMm': _read_item_value(item, 'WidthMm', 'double'),
            'depthMm': _read_item_value(item, 'DepthMm', 'double'),
            'heightMm': _read_item_value(item, 'HeightMm', 'double'),
            'boxQuantity': _read_item_value(item, 'BoxQuantity', 'integer'),
            'extinguisherQuantity': _read_item_value(item, 'ExtinguisherQuantity', 'integer'),
        }
        if None in (record['boxModel'], record['extinguisherModel'],
                    record['boxQuantity'], record['extinguisherQuantity']):
            _log('skipped incomplete ItemType on element %s' % record['elementId'])
            continue
        records.append(record)
        key = (record['boxModel'], record['extinguisherModel'])
        if key not in summary_map:
            summary_map[key] = {
                'boxModel': record['boxModel'],
                'extinguisherModel': record['extinguisherModel'],
                'boxCount': 0,
                'extinguisherCount': 0,
            }
        summary_map[key]['boxCount'] += record['boxQuantity']
        summary_map[key]['extinguisherCount'] += record['extinguisherQuantity']
    records.sort(key=lambda record: record['elementId'])
    summary = list(summary_map.values())
    summary.sort(key=lambda record: (record['boxModel'], record['extinguisherModel']))
    return {
        'records': records,
        'summary': summary,
        'totalBoxCount': sum(record['boxQuantity'] for record in records),
        'totalExtinguisherCount': sum(record['extinguisherQuantity'] for record in records),
    }


def export_fire_extinguisher_box_bom_json(output_path=None):
    """Export the active DGN's cabinet detail and box/extinguisher totals to JSON."""
    statistics = get_fire_extinguisher_box_statistics()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'灭火器箱_bom.json')
    with open(output_path, 'w', encoding='utf-8') as output:
        json.dump(statistics, output, ensure_ascii=False, indent=2)
    return output_path, statistics


def _xlsx_column_name(column_number):
    name = ''
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(column_number, row_number, value, style_index=0):
    reference = '%s%d' % (_xlsx_column_name(column_number), row_number)
    style = ' s="%d"' % style_index if style_index else ''
    if value is None:
        return '<c r="%s"%s/>' % (reference, style)
    if isinstance(value, bool):
        return '<c r="%s"%s t="b"><v>%d</v></c>' % (reference, style, int(value))
    if isinstance(value, (int, float)):
        return '<c r="%s"%s><v>%s</v></c>' % (reference, style, value)
    text = _xml_escape(str(value))
    return ('<c r="%s"%s t="inlineStr"><is><t xml:space="preserve">%s'
            '></t></is></c>') % (reference, style, text)


def _xlsx_sheet_xml(rows, header_rows=()):
    xml_rows = []
    max_columns = 1
    column_widths = {}
    for row_number, row in enumerate(rows, start=1):
        max_columns = max(max_columns, len(row))
        cells = []
        for column_number, value in enumerate(row, start=1):
            style_index = 1 if row_number in header_rows else 0
            if row_number == 1 and len(row) == 1:
                style_index = 2
            cells.append(_xlsx_cell(column_number, row_number, value, style_index))
            visual_length = len(str(value)) if value is not None else 0
            column_widths[column_number] = max(column_widths.get(column_number, 10),
                                                min(42, visual_length + 2))
        xml_rows.append('<row r="%d">%s</row>' % (row_number, ''.join(cells)))
    columns = ''.join('<col min="%d" max="%d" width="%s" customWidth="1"/>' %
                      (column_number, column_number, column_widths.get(column_number, 12))
                      for column_number in range(1, max_columns + 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<cols>%s</cols><sheetData>%s</sheetData>'
            '</worksheet>') % (columns, ''.join(xml_rows))


def _xlsx_styles_xml():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei UI"/>'
            '</font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/>'
            '<name val="Microsoft YaHei UI"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF222222"/>'
            '<bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/>'
            '</border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" '
            'fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" '
            'applyFill="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" '
            'applyFont="1"/></cellXfs></styleSheet>')


def export_fire_extinguisher_box_bom_xlsx(output_path=None):
    """Export the active DGN's statistics as a self-contained Excel .xlsx file."""
    statistics = get_fire_extinguisher_box_statistics()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'灭火器箱_bom.xlsx')
    summary_rows = [
        [u'灭火器箱统计清单'],
        [u'导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        [u'灭火器箱总数', statistics['totalBoxCount']],
        [u'灭火器总数', statistics['totalExtinguisherCount']],
        [],
        [u'灭火器箱型号', u'灭火器型号', u'箱体数量', u'灭火器数量'],
    ]
    for item in statistics['summary']:
        summary_rows.append([item['boxModel'], item['extinguisherModel'],
                             item['boxCount'], item['extinguisherCount']])
    detail_rows = [[u'元素 ID', u'ItemType', u'灭火器箱型号', u'灭火器型号',
                    u'适用范围', u'宽度 mm', u'深度 mm', u'高度 mm',
                    u'箱体数量', u'灭火器数量']]
    for record in statistics['records']:
        detail_rows.append([
            record['elementId'], record['itemType'], record['boxModel'],
            record['extinguisherModel'], record['capacityDescription'],
            record['widthMm'], record['depthMm'], record['heightMm'],
            record['boxQuantity'], record['extinguisherQuantity'],
        ])

    workbook_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets><sheet name="汇总" sheetId="1" r:id="rId1"/>'
                    '<sheet name="明细" sheetId="2" r:id="rId2"/></sheets></workbook>')
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                         '</Types>')
        archive.writestr('_rels/.rels',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                         '</Relationships>')
        archive.writestr('xl/workbook.xml', workbook_xml)
        archive.writestr('xl/_rels/workbook.xml.rels',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                         '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
                         '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                         '</Relationships>')
        archive.writestr('xl/styles.xml', _xlsx_styles_xml())
        archive.writestr('xl/worksheets/sheet1.xml', _xlsx_sheet_xml(summary_rows, (6,)))
        archive.writestr('xl/worksheets/sheet2.xml', _xlsx_sheet_xml(detail_rows, (1,)))
    return output_path, statistics


ACTIVE_FIRE_EXTINGUISHER_BOX_TOOL = None


class FireExtinguisherBoxPlacementTool(DgnPrimitiveTool):
    def __init__(self, box_key, extinguisher_type, capacity):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.box_key = box_key
        self.extinguisher_type = extinguisher_type
        self.capacity = capacity
        self.m_self = self

    def _GetToolName(self, name):
        return WString('FireExtinguisherBoxPlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            u'请点取灭火器箱底部前侧中心点；X为长边、Y为进深、Z向上为高度，正面朝-Y。')

    def _OnDataButton(self, event):
        point = event.GetPoint()
        uor_per_mm = _uor_per_mm()
        origin = (point.x / uor_per_mm, point.y / uor_per_mm,
                  point.z / uor_per_mm)
        try:
            result = create_fire_extinguisher_box(
                self.box_key, self.extinguisher_type, self.capacity, origin)
        except Exception as error:
            _log('placement exception: %r' % error)
            result = None
        if result is None:
            MessageCenter.ShowErrorMessage(
                u'灭火器箱生成或附加项写入失败，请查看灭火器箱_debug_log.txt。', '', False)
        else:
            MessageCenter.ShowInfoMessage(
                u'已生成红色灭火器箱：1个箱体，2具%s灭火器。' %
                _extinguisher_model_label(self.extinguisher_type, self.capacity), '', False)
        return True

    def _OnResetButton(self, event):
        NotificationManager.OutputPrompt(u'已取消灭火器箱定位。')
        return True

    @staticmethod
    def InstallNewInstance(box_key, extinguisher_type, capacity):
        global ACTIVE_FIRE_EXTINGUISHER_BOX_TOOL
        ACTIVE_FIRE_EXTINGUISHER_BOX_TOOL = FireExtinguisherBoxPlacementTool(
            box_key, extinguisher_type, capacity)
        ACTIVE_FIRE_EXTINGUISHER_BOX_TOOL.InstallTool()


def _mix_color(source, target, ratio):
    """Linearly blend two '#RRGGBB' colours; ratio 0 -> source, 1 -> target."""
    source = source.lstrip('#')
    target = target.lstrip('#')
    blended = []
    for offset in (0, 2, 4):
        first = int(source[offset:offset + 2], 16)
        second = int(target[offset:offset + 2], 16)
        blended.append(max(0, min(255, int(round(first + (second - first) * ratio)))))
    return '#%02X%02X%02X' % tuple(blended)


def _apply_window_backdrop(root):
    """Best-effort Windows 11 rounded window corners (silently ignored elsewhere)."""
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            return
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33,
                                                   ctypes.byref(preference), 4)
    except Exception:
        pass


def show_fire_extinguisher_box_dialog():
    """Show the model selector, current-DGN statistics, and JSON export controls."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as error:
        _log('tkinter unavailable: %r' % error)
        return None

    BG = '#EEF2F7'        # 冷白毛玻璃底
    CARD = '#FFFFFF'      # 玻璃卡片
    CARD_SOFT = '#F4F7FB' # 卡片内浅色衬底
    BORDER = '#E3E9F1'
    INK = '#1F2A3D'
    MUTED = '#8C97A8'
    ACCENT = '#D93025'    # 消防红点缀

    root = tk.Tk()
    root.title(u'XMDDG 灭火器箱')
    root.resizable(False, False)
    root.configure(bg=BG)
    _apply_window_backdrop(root)

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    ui_font = ('Microsoft YaHei UI', 10)
    ui_font_small = ('Microsoft YaHei UI', 9)
    ui_font_bold = ('Microsoft YaHei UI', 10, 'bold')
    style.configure('Card.TFrame', background=CARD)
    style.configure('Glass.TLabel', background=CARD, foreground=INK, font=ui_font)
    style.configure('GlassMuted.TLabel', background=CARD, foreground=MUTED,
                    font=ui_font)
    style.configure('TSeparator', background=BORDER)
    style.configure('TCombobox', font=ui_font, padding=(10, 7),
                    fieldbackground='#FBFCFE', background='#FFFFFF',
                    foreground=INK, bordercolor=BORDER, lightcolor='#FBFCFE',
                    darkcolor='#CBD5E1', arrowsize=15)
    style.map('TCombobox',
              fieldbackground=[('readonly', '#FBFCFE'), ('active', '#FFFFFF')],
              bordercolor=[('active', '#9FB4CC'), ('focus', '#9FB4CC')],
              lightcolor=[('active', '#9FB4CC')],
              arrowcolor=[('active', INK), ('!active', '#93A1B5')],
              selectbackground=[('readonly', '#F0F5FA')],
              selectforeground=[('readonly', INK)])

    def make_button(parent, text, command, primary=False):
        """Rounded Canvas button with an animated hover transition."""
        font = ui_font_bold if primary else ui_font
        text_width = sum(14 if ord(ch) > 127 else 7 for ch in text)
        width = text_width + 44
        height = 36
        radius = 10
        idle_fill = '#2A3644' if primary else CARD
        hover_fill = '#3D4C5E' if primary else '#F0F5FA'
        idle_edge = '#2A3644' if primary else '#D8E0EA'
        hover_edge = '#3D4C5E' if primary else '#B9C6D6'
        text_fill = '#FFFFFF' if primary else '#33415C'
        canvas = tk.Canvas(parent, width=width, height=height, bg=CARD,
                           highlightthickness=0, bd=0, cursor='hand2')

        def paint(ratio):
            canvas.delete('all')
            fill = _mix_color(idle_fill, hover_fill, ratio)
            edge = _mix_color(idle_edge, hover_edge, ratio)
            x1, y1, x2, y2 = 1, 1, width - 1, height - 1
            points = (x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                      x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                      x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1)
            canvas.create_polygon(points, smooth=True, fill=fill, outline=edge)
            canvas.create_text(width / 2.0, height / 2.0, text=text,
                               fill=text_fill, font=font)

        animator = {'ratio': 0.0, 'target': 0.0, 'job': None}

        def step():
            ratio = animator['ratio']
            target = animator['target']
            if abs(target - ratio) < 0.04:
                animator['ratio'] = target
                animator['job'] = None
                paint(target)
                return
            animator['ratio'] = ratio + (target - ratio) * 0.32
            paint(animator['ratio'])
            animator['job'] = canvas.after(16, step)

        def set_target(target):
            animator['target'] = target
            if animator['job'] is None:
                step()

        canvas.bind('<Enter>', lambda event: set_target(1.0))
        canvas.bind('<Leave>', lambda event: set_target(0.0))
        canvas.bind('<Button-1>', lambda event: command())
        paint(0.0)
        return canvas

    shell = tk.Frame(root, bg=BG, padx=24, pady=22)
    shell.pack(fill='both', expand=True)

    header = tk.Frame(shell, bg=BG)
    header.pack(fill='x', pady=(0, 16))
    title_row = tk.Frame(header, bg=BG)
    title_row.pack(anchor='w')
    dot = tk.Canvas(title_row, width=10, height=10, bg=BG,
                    highlightthickness=0, bd=0)
    dot.create_oval(1, 1, 9, 9, fill=ACCENT, outline='')
    dot.pack(side='left', pady=(9, 0), padx=(0, 8))
    tk.Label(title_row, text=u'XMDDG 灭火器箱', bg=BG, fg=INK,
             font=('Microsoft YaHei UI', 18, 'bold')).pack(side='left')
    tk.Label(header, text=u'单体 · 置地型 · 翻盖式    |    GA 139-2009 表 1',
             bg=BG, fg=MUTED, font=ui_font_small).pack(
                 anchor='w', pady=(4, 0), padx=(18, 0))

    card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER,
                    highlightthickness=1)
    card.pack(fill='both', expand=True)
    form = ttk.Frame(card, style='Card.TFrame', padding=22)
    form.pack(fill='both', expand=True)

    last_selection = _load_last_selection()
    initial_type = last_selection.get('extinguisherType', u'干粉灭火器')
    if initial_type not in EXTINGUISHER_TYPES:
        initial_type = u'干粉灭火器'
    initial_capacity = last_selection.get('capacity', 2)
    if initial_capacity not in EXTINGUISHER_TYPES[initial_type]['capacities']:
        initial_capacity = EXTINGUISHER_TYPES[initial_type]['capacities'][0]
    initial_box_key = last_selection.get('boxKey', _recommended_box_key(
        initial_type, initial_capacity))
    if initial_box_key not in _eligible_box_keys(initial_type, initial_capacity):
        initial_box_key = _recommended_box_key(initial_type, initial_capacity)

    extinguisher_type = tk.StringVar(value=initial_type)
    capacity_value = tk.StringVar(value=str(initial_capacity))
    box_key = tk.StringVar(value=initial_box_key)
    capacity_unit = tk.StringVar()
    model_display = tk.StringVar()
    dimension_display = tk.StringVar()
    capacity_display = tk.StringVar()
    note = tk.StringVar()

    ttk.Label(form, text=u'选择参数', style='GlassMuted.TLabel',
              font=ui_font_small).grid(row=0, column=0, columnspan=2, sticky='w')
    ttk.Label(form, text=u'灭火器类型', style='GlassMuted.TLabel').grid(
        row=1, column=0, sticky='w', pady=6)
    type_combo = ttk.Combobox(form, textvariable=extinguisher_type,
                              values=tuple(EXTINGUISHER_TYPES.keys()),
                              state='readonly', width=22)
    type_combo.grid(row=1, column=1, sticky='ew', padx=(12, 0), pady=6)
    ttk.Label(form, text=u'规格容量', style='GlassMuted.TLabel').grid(
        row=2, column=0, sticky='w', pady=6)
    capacity_combo = ttk.Combobox(form, textvariable=capacity_value,
                                  state='readonly', width=12)
    capacity_combo.grid(row=2, column=1, sticky='w', padx=(12, 0), pady=6)
    ttk.Label(form, textvariable=capacity_unit, style='GlassMuted.TLabel').grid(
        row=2, column=1, sticky='w', padx=(158, 0), pady=6)
    ttk.Label(form, text=u'受限箱型', style='GlassMuted.TLabel').grid(
        row=3, column=0, sticky='w', pady=6)
    box_combo = ttk.Combobox(form, textvariable=box_key,
                             state='readonly', width=18)
    box_combo.grid(row=3, column=1, sticky='ew', padx=(12, 0), pady=6)

    ttk.Separator(form, orient='horizontal').grid(
        row=4, column=0, columnspan=2, sticky='ew', pady=12)
    ttk.Label(form, text=u'规格说明', style='GlassMuted.TLabel').grid(
        row=5, column=0, sticky='nw', pady=3)
    ttk.Label(form, textvariable=model_display, style='Glass.TLabel',
              justify='left', wraplength=400).grid(
        row=5, column=1, sticky='w', padx=(12, 0), pady=3)
    ttk.Label(form, text=u'生成尺寸', style='GlassMuted.TLabel').grid(
        row=6, column=0, sticky='w', pady=3)
    ttk.Label(form, textvariable=dimension_display, style='Glass.TLabel',
              justify='left', wraplength=400).grid(
        row=6, column=1, sticky='w', padx=(12, 0), pady=3)
    ttk.Label(form, text=u'标准适用范围', style='GlassMuted.TLabel').grid(
        row=7, column=0, sticky='nw', pady=3)
    ttk.Label(form, textvariable=capacity_display, style='Glass.TLabel',
              justify='left', wraplength=400).grid(
        row=7, column=1, sticky='w', padx=(12, 0), pady=3)

    note_chip = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
    note_chip.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(14, 0))
    tk.Label(note_chip, textvariable=note, bg=CARD_SOFT, fg='#5B6B82',
             font=ui_font_small, wraplength=440, justify='left').pack(
                 anchor='w', padx=12, pady=8)

    def refresh_preset(*unused):
        preset = BOX_PRESETS[box_key.get()]
        width, depth, height = preset['dimensions']
        model_display.set(preset['display_name'])
        dimension_display.set(u'X×Y×Z = %.0f×%.0f×%.0f mm（%s）' %
                              (width, depth, height, preset['source_dimensions']))
        capacity_display.set(preset['capacity_description'])
        note.set(u'%s 可使用当前选择的 %s；默认推荐最小合格箱型，也可改选更大规格。' %
                 (preset['display_name'].split('｜')[0],
                  _extinguisher_model_label(extinguisher_type.get(),
                                             int(capacity_value.get()))))

    def refresh_selection(*unused):
        selected_type = extinguisher_type.get()
        type_data = EXTINGUISHER_TYPES[selected_type]
        capacity_options = tuple(str(value) for value in type_data['capacities'])
        capacity_combo['values'] = capacity_options
        if capacity_value.get() not in capacity_options:
            capacity_value.set(capacity_options[0])
        capacity_unit.set(type_data['unit'])
        selected_capacity = int(capacity_value.get())
        eligible_box_keys = _eligible_box_keys(selected_type, selected_capacity)
        box_combo['values'] = eligible_box_keys
        if box_key.get() not in eligible_box_keys:
            box_key.set(eligible_box_keys[0])
        refresh_preset()

    def persist_selection(*unused):
        try:
            selected_type = extinguisher_type.get()
            selected_capacity = int(capacity_value.get())
            if box_key.get() in _eligible_box_keys(selected_type, selected_capacity):
                _save_last_selection(selected_type, selected_capacity, box_key.get())
        except (KeyError, ValueError):
            pass

    extinguisher_type.trace_add('write', refresh_selection)
    capacity_value.trace_add('write', refresh_selection)
    box_key.trace_add('write', refresh_preset)
    extinguisher_type.trace_add('write', persist_selection)
    capacity_value.trace_add('write', persist_selection)
    box_key.trace_add('write', persist_selection)
    refresh_selection()

    def show_statistics():
        statistics = get_fire_extinguisher_box_statistics()
        details = [u'灭火器箱：%d 个' % statistics['totalBoxCount'],
                   u'灭火器：%d 具' % statistics['totalExtinguisherCount']]
        for summary in statistics['summary']:
            details.append(u'%s / %s：%d 箱，%d 具' % (
                summary['boxModel'], summary['extinguisherModel'],
                summary['boxCount'], summary['extinguisherCount']))
        messagebox.showinfo(u'当前模型统计', '\n'.join(details), parent=root)

    def export_bom():
        try:
            output_path, statistics = export_fire_extinguisher_box_bom_json()
            messagebox.showinfo(
                u'导出完成', u'已导出 JSON 清单：\n%s\n\n灭火器箱：%d 个\n灭火器：%d 具' % (
                    output_path, statistics['totalBoxCount'],
                    statistics['totalExtinguisherCount']), parent=root)
        except Exception as error:
            _log('JSON export exception: %r' % error)
            messagebox.showerror(u'导出失败', u'请查看灭火器箱_debug_log.txt。', parent=root)

    def export_excel():
        try:
            output_path, statistics = export_fire_extinguisher_box_bom_xlsx()
            messagebox.showinfo(
                u'导出完成', u'已导出 Excel 清单：\n%s\n\n灭火器箱：%d 个\n灭火器：%d 具' % (
                    output_path, statistics['totalBoxCount'],
                    statistics['totalExtinguisherCount']), parent=root)
        except Exception as error:
            _log('Excel export exception: %r' % error)
            messagebox.showerror(u'导出失败', u'Excel 导出失败，请查看灭火器箱_debug_log.txt。', parent=root)

    def start_placement():
        selected_key = box_key.get()
        selected_type = extinguisher_type.get()
        selected_capacity = int(capacity_value.get())
        _save_last_selection(selected_type, selected_capacity, selected_key)
        root.destroy()
        FireExtinguisherBoxPlacementTool.InstallNewInstance(selected_key,
                                                            selected_type,
                                                            selected_capacity)

    button_bar = tk.Frame(form, bg=CARD)
    button_bar.grid(row=9, column=0, columnspan=2, sticky='ew', pady=(16, 0))
    make_button(button_bar, u'统计当前模型', show_statistics).pack(
        side='left', padx=(0, 8))
    make_button(button_bar, u'导出 JSON 清单', export_bom).pack(
        side='left', padx=(0, 8))
    make_button(button_bar, u'导出 Excel 清单', export_excel).pack(side='left')
    make_button(button_bar, u'下一步：点取位置', start_placement,
                primary=True).pack(side='right')
    root.mainloop()


if __name__ == '__main__':
    show_fire_extinguisher_box_dialog()
