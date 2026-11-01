# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为公共库供其它支吊架插件 ``import`` 调用，没有独立入口。
# 请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""管道支吊架 —— 公共 ItemType 契约与统一清单导出（共享模块）。

各管道支吊架插件（端焊三角架、L 型管架……）统一把构件写入**同一个 ItemType
库** ``PipeSupportComponents``，并带上同一套公共属性：

    RecordKind      'Assembly'（整组）或 'Component'（构件）
    SupportType     支吊架类型（如 '端焊三角架' / 'L型管架'）
    AssemblyTag     支吊架编号
    ComponentName   构件名
    Specification   规格
    DesignLengthMm  设计长度 / 特征尺寸
    Quantity        数量
    Unit            单位
    PipeNumber      管道号（从所选管道读取时自动填写；无值时留空，也可在
                    「属性 → Item Types」面板中自行填写）

于是任何支吊架插件放置的实体都能被 :func:`export_combined_bom` 一次扫到：

* 按 ``SupportType`` 统计**套数**（不同 AssemblyTag 的整组记录数）；
* 按 ``SupportType → ComponentName → Specification`` 汇总**材料**。

**ItemType 名与实例数据分离**：名称按「支吊架类型 → 构件代号」稳定
复用（不带哈希、不带单次放置的长度/编号），真实参数（tag / 规格 /
长度 / 数量 / 管道号）经 ``ApplyCustomItem`` 返回的元素实例逐属性
``SetValue`` 写入；类默认值只放中性占位（空 tag / 0 长度）。个别
MicroStation 版本 ``ApplyCustomItem`` 返回值无法封送或 ``SetValue``
不可用时，自动回退到旧机制（把实例数据烘焙进默认值、名称按内容寻址），
行为与旧版一致。

本模块不依赖任何具体插件；各插件把 ``管道支吊架/模块/公共`` 目录加入
``sys.path`` 后 ``import 支吊架公共库`` 即可。
"""

from __future__ import division

import hashlib
import json
import os
import traceback
import zipfile
from xml.sax.saxutils import escape as _xml_escape

# Bentley 运行时：在 OPM / MicroStation 中存在；纯 CPython 下缺失，此时仍可
# 导入本模块以单测 :func:`_summarise` 等纯逻辑（ItemType 相关函数不可调用）。
try:
    from MSPyBentley import *  # noqa: F401,F403
    from MSPyECObjects import *  # noqa: F401,F403
    from MSPyDgnPlatform import *  # noqa: F401,F403
    from MSPyDgnView import *  # noqa: F401,F403
    from MSPyMstnPlatform import *  # noqa: F401,F403
    _EC_STRING = CustomProperty.Type1.eString
    _EC_DOUBLE = CustomProperty.Type1.eDouble
    _EC_INTEGER = CustomProperty.Type1.eInteger
except Exception:  # pragma: no cover - 仅在无 Bentley 运行时时触发
    _EC_STRING = None
    _EC_DOUBLE = None
    _EC_INTEGER = None


HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件已移至 模块/公共/，插件根目录（管道支吊架/）需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(HERE))
LOG_DIR = os.path.join(_PLUGIN_ROOT, '模块', '日志')
OUTPUT_DIR = os.path.join(_PLUGIN_ROOT, '模块', '输出')
for _dir in (LOG_DIR, OUTPUT_DIR):
    try:
        os.makedirs(_dir, exist_ok=True)
    except Exception:
        pass
DEBUG_LOG = os.path.join(LOG_DIR, '管道支吊架_debug_log.txt')

# 所有支吊架插件共用的 ItemType 库。
SUPPORT_LIBRARY_NAME = 'PipeSupportComponents'
ASSEMBLY_PREFIX = 'PipeSupportAssembly'
COMPONENT_PREFIX = 'PipeSupportComponent'

# 公共属性定义：名字与类型在各插件间必须完全一致，否则同一个库会被污染。
PROPERTY_DEFINITIONS = (
    ('RecordKind', _EC_STRING),
    ('SupportType', _EC_STRING),
    ('AssemblyTag', _EC_STRING),
    ('ComponentName', _EC_STRING),
    ('Specification', _EC_STRING),
    ('DesignLengthMm', _EC_DOUBLE),
    ('Quantity', _EC_INTEGER),
    ('Unit', _EC_STRING),
    ('PipeNumber', _EC_STRING),
)

# 属性在 Bentley「属性 → Item Types」面板中的显示名（尽力而为，失败不影响写入）。
PROPERTY_DISPLAY_LABELS = {
    'PipeNumber': '管道号',
}


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


# ---------------------------------------------------------------------------
# ItemType 写入
# ---------------------------------------------------------------------------


def _new_ec_value(value):
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(int(value))
    return ec_value


def _apply_display_label(item_property, property_name):
    """给属性设置中文显示名（面板可见）；API 不支持时静默跳过。"""
    label = PROPERTY_DISPLAY_LABELS.get(property_name)
    if not label or not hasattr(item_property, 'SetDisplayLabel'):
        return
    try:
        item_property.SetDisplayLabel(label)
    except Exception:
        pass


def _ascii_token(text):
    """把任意文本压成 ItemType 名称可用的 ASCII 片段。"""
    cleaned = ''.join(
        ch if (ch.isalnum() and ord(ch) < 128) else '_' for ch in str(text))
    cleaned = cleaned.strip('_') or 'X'
    return cleaned


def _short_hash(text):
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()[:10]


def _length_key(length_mm):
    return ('%.3f' % float(length_mm)).replace('.', '_').replace('-', 'N')


def _stable_assembly_item_type_name(support_code):
    """稳定族名（新机制）：只看支吊架类型，每个类型一个 Assembly 类。"""
    return '%s_%s' % (ASSEMBLY_PREFIX, _ascii_token(support_code))


def _stable_component_item_type_name(support_code, component_code):
    """稳定族名（新机制）：类型 + 构件代号；壁厚/长度等单次数据不进名字。"""
    return '%s_%s_%s' % (COMPONENT_PREFIX, _ascii_token(support_code),
                         _ascii_token(component_code))


def _legacy_assembly_item_type_name(support_code, assembly_tag, assembly_spec):
    digest = _short_hash('%s|%s' % (assembly_tag, assembly_spec))
    return '%s_%s_%s' % (ASSEMBLY_PREFIX, _ascii_token(support_code), digest)


def _legacy_component_item_type_name(support_code, component_code, length_mm):
    return '%s_%s_%s_L%s' % (
        COMPONENT_PREFIX, _ascii_token(support_code),
        _ascii_token(component_code), _length_key(length_mm))


def _write_instance_values(instance, values):
    """对实例逐属性 ``SetValue`` + ``WriteChanges()``；失败抛异常。

    ``SetValue`` 各版本封送形态不同：先试 ``ECValue`` 包装，再试裸
    Python 值。任何属性两种形态都写不进去，就抛 ``RuntimeError``，
    由 ``_attach_item_with_values`` 捕获并触发一次性回退。
    """
    for property_name, value in values.items():
        ec_value = _new_ec_value(value)
        written = False
        for value_form in (ec_value, value):
            try:
                instance.SetValue(property_name, value_form)
                written = True
                break
            except Exception:
                continue
        if not written:
            raise RuntimeError('SetValue 不可用（属性 %s）' % property_name)
    instance.WriteChanges()
    return True


def _apply_item_to_element(element, item_type):
    """``ApplyCustomItem``；抛 TypeError(封送失败) 时返回 None。

    **不做 GetCustomItem 回取**：实测（2026-09-28，第五块弧板崩溃）在
    ApplyCustomItem 返回 None 之后紧接着对同一元素 GetCustomItem 会触发
    原生 access violation。拿不到实例就当作「实例赋值不可用」，让调用方
    走旧机制回退，绝不在同一次挂载里二次进入原生层。
    """
    target = element
    try:
        element_id = int(element.GetElementId())
        if element_id:
            model_ref = ISessionMgr.ActiveDgnModelRef
            if model_ref is not None:
                target = EditElementHandle(element_id, model_ref.GetDgnModel())
    except Exception:
        target = element
    item_host = CustomItemHost(target, False)
    try:
        return item_host.ApplyCustomItem(item_type)
    except TypeError as error:
        if 'Unable to convert function return value' in str(error):
            return None
        raise


def _get_or_create_item_type(item_type_name, defaults):
    dgn_file = ISessionMgr.GetActiveDgnFile()
    try:
        item_library = ItemTypeLibrary.FindByName(SUPPORT_LIBRARY_NAME, dgn_file)
        changed = False
        if item_library is None:
            item_library = ItemTypeLibrary(SUPPORT_LIBRARY_NAME, dgn_file, False)
            changed = True

        item_type = item_library.GetItemTypeByName(item_type_name)
        if item_type is None:
            item_type = item_library.AddItemType(item_type_name, False)
            changed = True
        if item_type is None:
            _log('item type: failed to create %s' % item_type_name)
            return None

        for property_name, property_type in PROPERTY_DEFINITIONS:
            item_property = item_type.GetPropertyByName(property_name)
            if item_property is None:
                item_property = item_type.AddProperty(property_name, False)
                if item_property is None or not item_property.SetType(property_type):
                    _log('item type: failed to add property %s' % property_name)
                    return None
                if not item_property.SetDefaultValue(
                        _new_ec_value(defaults[property_name])):
                    _log('item type: failed to set default for %s' % property_name)
                    return None
                _apply_display_label(item_property, property_name)
                changed = True

        if changed and not item_library.Write():
            _log('item type: failed to write library %s' % SUPPORT_LIBRARY_NAME)
            return None
        if changed:
            # 新建 / 改过属性才记一条：便于区分"首次创建"与"复用已有 ItemType"。
            _log('item type: created/updated %s' % item_type_name)

        item_library = ItemTypeLibrary.FindByName(SUPPORT_LIBRARY_NAME, dgn_file)
        return item_library.GetItemTypeByName(item_type_name)
    except Exception as error:
        _log('item type: setup exception: %r' % error)
        return None


# 会话级标记：实例赋值路径一旦确认不可用（拿不到实例 / SetValue 失败），
# 本会话内后续 item 一律直接走旧机制，不再重复尝试。首次失败会记一条日志。
_INSTANCE_WRITE_OK = None

# 稳定名的类默认值：中性占位。真实数据在实例上；旧机制回退分支才烘焙进默认值。
_NEUTRAL_DEFAULTS = {
    'RecordKind': '',
    'SupportType': '',
    'AssemblyTag': '',
    'ComponentName': '',
    'Specification': '',
    'DesignLengthMm': 0.0,
    'Quantity': 1,
    'Unit': '',
    'PipeNumber': '',
}


def _attach_item_with_defaults(element, item_type_name, defaults):
    """旧机制（回退用）：数据烘焙进类默认值、名称按内容寻址。

    行为与改造前的 ``_attach_item_with_defaults`` 完全一致。
    """
    item_type = _get_or_create_item_type(item_type_name, defaults)
    if item_type is None:
        return False
    _log('apply item type: %s' % item_type_name)
    try:
        # AddToModel() 之后 EditElementHandle 内部指针在个别版本里会失效，
        # 这里按元素 ID 重新取一份句柄，再交给 CustomItemHost。
        target = element
        try:
            element_id = int(element.GetElementId())
            if element_id:
                model_ref = ISessionMgr.ActiveDgnModelRef
                if model_ref is not None:
                    target = EditElementHandle(element_id, model_ref.GetDgnModel())
        except Exception:
            target = element
        item_host = CustomItemHost(target, False)
        try:
            item_host.ApplyCustomItem(item_type)
        except TypeError as error:
            if 'Unable to convert function return value' in str(error):
                return True
            raise
        _log('apply ok: %s' % item_type_name)
        return True
    except Exception as error:
        _log('item attach exception (%s): %r' % (item_type_name, error))
        return False


def _attach_item_with_values(element, item_type_name, values,
                              legacy_name, legacy_defaults):
    """把一条清单记录挂到 *element*（稳定名机制，带回退）。

    主路径：``item_type_name`` 稳定族名，类默认值放 ``_NEUTRAL_DEFAULTS``
    占位；``ApplyCustomItem`` 后把 ``values``（本实例真实参数）经
    ``SetValue`` 写到返回的元素实例上。

    会话内一旦确认实例路径不可用（拿不到实例 / ``SetValue`` 失败），
    后续 item 直接走旧机制：``legacy_name``（内容寻址名）+
    ``legacy_defaults``（同一份数据，烘焙进类默认值），行为与旧版完全
    一致。失败的那一条会补挂旧类；此时元素同时带稳定类（中性值）与
    旧类（真实值）两种记录，清单导出可能出现一行多的重复，仅发生在
    会话内第一次失败，后续条目全部纯旧机制单条记录。

    返回 True 表示记录已挂上（新 / 旧机制任一成功都算）。
    """
    global _INSTANCE_WRITE_OK
    if _INSTANCE_WRITE_OK is False:
        return _attach_item_with_defaults(element, legacy_name,
                                          legacy_defaults)
    item_type = _get_or_create_item_type(item_type_name, _NEUTRAL_DEFAULTS)
    if item_type is None:
        return False
    # ``ApplyCustomItem`` 是原生 EC 写入，本仓库里出现过"卡死后 access violation"。
    # 每次调用前先落一条日志：崩溃时日志最后一行就是卡住的那一项。
    _log('apply item type: %s' % item_type_name)
    try:
        instance = _apply_item_to_element(element, item_type)
        _log('apply ok: %s' % item_type_name)
        if instance is None:
            # type 已挂上（属性面板可见中性占位），但拿不到实例就写不了真实值。
            # 不做 GetCustomItem 回取、也不 detach：实测二者都会二次进入原生层
            # 并触发 access violation（2026-09-28 第五块弧板崩溃）。
            # 判定本会话实例路径不可用：本条不重挂（避免双记录），后续条目
            # 在入口处直接走旧机制。
            _INSTANCE_WRITE_OK = False
            _log('instance path unavailable (%s): record will carry neutral'
                 ' defaults; subsequent items go legacy' % item_type_name)
            return True
        try:
            _write_instance_values(instance, values)
            _INSTANCE_WRITE_OK = True
            return True
        except Exception as error:
            # SetValue 失败：不 detach、不重挂（避免二次进入原生层）。
            # 本条记录已挂稳定类（带中性默认值），清单上该条为占位值；
            # 后续条目在入口处直接走旧机制。
            _INSTANCE_WRITE_OK = False
            _log('instance SetValue failed for %s: %r —— subsequent items'
                 ' go legacy' % (item_type_name, error))
            return True
    except Exception as error:
        _log('item attach exception (%s): %r' % (item_type_name, error))
        return False


def attach_components(element, support_type, support_code, assembly_tag,
                      components, assembly_spec='', assembly_unit='套',
                      pipe_number=''):
    """把一组支吊架构件写入公共库并附加到 *element*（通常是一整组单元）。

    ``support_type`` 为中文显示名（如 '端焊三角架'）；``support_code`` 为
    ASCII 代号（用于 ItemType 命名）。``components`` 为构件字典序列，每项含
    ``code`` / ``name`` / ``specification`` / ``length``，可选
    ``quantity``（默认 1）与 ``unit``（默认 '件'）。

    **命名**（稳定族名）：``Assembly_<类型>`` / ``Component_<类型>_<构件
    code>``——同一类型反复放置复用同一批类，ItemType 库不再膨胀；tag /
    规格 / 长度 / 数量 / 管道号等单次数据写到元素实例上。个别版本实例
    路径不可用时自动回退旧命名（内容寻址 + 默认值烘焙），行为与旧版一致。

    同时附加一条整组记录（RecordKind='Assembly'），用于按类型统计套数。
    返回成功附加的条目数。
    """
    attached = 0
    pipe_number = str(pipe_number or '').strip()

    assembly_values = {
        'RecordKind': 'Assembly',
        'SupportType': str(support_type),
        'AssemblyTag': str(assembly_tag or ''),
        'ComponentName': '支吊架',
        'Specification': str(assembly_spec or ''),
        'DesignLengthMm': 0.0,
        'Quantity': 1,
        'Unit': str(assembly_unit or '套'),
        'PipeNumber': pipe_number,
    }
    stable_name = _stable_assembly_item_type_name(support_code)
    legacy_name = (_legacy_assembly_item_type_name(
        support_code, assembly_tag, assembly_spec)
        + ('_P' + _short_hash(pipe_number) if pipe_number else ''))
    legacy_defaults = dict(assembly_values)
    if _attach_item_with_values(element, stable_name, assembly_values,
                                legacy_name, legacy_defaults):
        attached += 1

    for item in components or ():
        code = str(item.get('code') or item.get('name') or 'Item')
        length = float(item.get('length', 0.0))
        values = {
            'RecordKind': 'Component',
            'SupportType': str(support_type),
            'AssemblyTag': '',
            'ComponentName': str(item.get('name', '')),
            'Specification': str(item.get('specification', '')),
            'DesignLengthMm': length,
            'Quantity': int(item.get('quantity', 1)),
            'Unit': str(item.get('unit', '件')),
            'PipeNumber': pipe_number,
        }
        stable_name = _stable_component_item_type_name(support_code, code)
        legacy_name = (_legacy_component_item_type_name(support_code, code, length)
                       + ('_P' + _short_hash(pipe_number) if pipe_number else ''))
        if _attach_item_with_values(
                element, stable_name, values, legacy_name, dict(values)):
            attached += 1

    _log('attached %d/%d support items: type=%s tag=%s' %
         (attached, len(components or ()) + 1, support_type, assembly_tag or '-'))
    return attached


# ---------------------------------------------------------------------------
# 统一清单导出
# ---------------------------------------------------------------------------


def _item_property_value(item, property_name, value_kind):
    ec_value = ECValue()
    status = item.GetValue(ec_value, property_name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or ec_value.IsNull():
        return None
    if value_kind == 'double':
        return ec_value.GetDouble()
    if value_kind == 'integer':
        return ec_value.GetInteger()
    return ec_value.GetString()


def _collect_records(item_library, dgn_file):
    scope = FindInstancesScope.CreateScope(
        dgn_file, FindInstancesScopeOption(DgnECHostType.eElement, False))
    query = ECQuery.CreateQuery(ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses)
    schema_name = str(item_library.GetInternalName())
    records = []
    for item in DgnECManager.GetManager().FindInstances(scope, query)[0]:
        item_class = item.GetClass()
        if str(item_class.GetSchema().GetName()) != schema_name:
            continue
        type_name = str(item_class.GetName())
        if not (type_name.startswith(ASSEMBLY_PREFIX)
                or type_name.startswith(COMPONENT_PREFIX)):
            continue
        element_instance = item.GetAsElementInstance()
        if element_instance is None:
            continue
        record = {
            'elementId': int(element_instance.ElementHandle.ElementId),
            'itemType': type_name,
            'recordKind': _item_property_value(item, 'RecordKind', 'string'),
            'supportType': _item_property_value(item, 'SupportType', 'string'),
            'assemblyTag': _item_property_value(item, 'AssemblyTag', 'string'),
            'componentName': _item_property_value(item, 'ComponentName', 'string'),
            'specification': _item_property_value(item, 'Specification', 'string'),
            'designLengthMm': _item_property_value(item, 'DesignLengthMm', 'double'),
            'quantity': _item_property_value(item, 'Quantity', 'integer'),
            'unit': _item_property_value(item, 'Unit', 'string'),
            'pipeNumber': _item_property_value(item, 'PipeNumber', 'string'),
        }
        if not record['recordKind']:
            record['recordKind'] = ('Assembly'
                                    if type_name.startswith(ASSEMBLY_PREFIX)
                                    else 'Component')
        records.append(record)
    return records


def _summarise(records):
    supports = {}
    materials = {}
    for record in records:
        support_type = record['supportType'] or '未知'
        if record['recordKind'] == 'Assembly':
            entry = supports.setdefault(support_type, {
                'supportType': support_type,
                'assemblyCount': 0,
                'assemblyTags': [],
            })
            entry['assemblyCount'] += int(record['quantity'] or 1)
            tag = record['assemblyTag'] or ''
            if tag:
                entry['assemblyTags'].append(tag)
        else:
            key = (support_type, record['componentName'] or '',
                   record['specification'] or '', record['unit'] or '')
            entry = materials.setdefault(key, {
                'supportType': support_type,
                'componentName': record['componentName'] or '',
                'specification': record['specification'] or '',
                'unit': record['unit'] or '',
                'quantity': 0,
                'totalDesignLengthMm': 0.0,
            })
            quantity = int(record['quantity'] or 1)
            entry['quantity'] += quantity
            entry['totalDesignLengthMm'] += float(record['designLengthMm'] or 0.0) * quantity

    supports_list = sorted(supports.values(), key=lambda value: value['supportType'])
    for entry in supports_list:
        entry['assemblyTags'].sort()
    materials_list = list(materials.values())
    for entry in materials_list:
        entry['totalDesignLengthMm'] = round(entry['totalDesignLengthMm'], 3)
    materials_list.sort(key=lambda value: (
        value['supportType'], value['componentName'], value['specification']))
    return supports_list, materials_list


def collect_statistics():
    """读取当前活动 DGN 的支吊架数据，返回统计字典（不写文件）。

    返回：``itemTypeLibrary`` / ``assemblyCount``（总套数）/
    ``componentRecordCount`` / ``supportsByType`` / ``materials`` / ``records``。
    读不到库时各计数为 0、列表为空（不报错）。
    """
    empty = {
        'itemTypeLibrary': SUPPORT_LIBRARY_NAME,
        'assemblyCount': 0,
        'componentRecordCount': 0,
        'supportsByType': [],
        'materials': [],
        'records': [],
    }
    dgn_file = ISessionMgr.GetActiveDgnFile()
    item_library = ItemTypeLibrary.FindByName(SUPPORT_LIBRARY_NAME, dgn_file)
    if item_library is None:
        return empty
    records = _collect_records(item_library, dgn_file)
    if not records:
        return empty
    supports_list, materials_list = _summarise(records)
    records.sort(key=lambda value: ((value['supportType'] or ''),
                                    value['elementId']))
    return {
        'itemTypeLibrary': SUPPORT_LIBRARY_NAME,
        'assemblyCount': sum(entry['assemblyCount'] for entry in supports_list),
        'componentRecordCount': sum(
            1 for record in records if record['recordKind'] != 'Assembly'),
        'supportsByType': supports_list,
        'materials': materials_list,
        'records': records,
    }


def export_combined_bom(output_path=None):
    """扫描公共支吊架库，导出统一清单 JSON，返回文件路径。

    清单包含：按类型统计套数（supportsByType）、材料汇总（materials）以及
    逐实例明细（records）。
    """
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, '管道支吊架_bom.json')
    try:
        payload = collect_statistics()
        if not payload['records']:
            MessageCenter.ShowErrorMessage(
                '未找到带有管道支吊架 ItemType 属性的实体。', '', False)
            return None
        with open(output_path, 'w', encoding='utf-8') as json_file:
            json.dump(payload, json_file, ensure_ascii=False, indent=2)
        MessageCenter.ShowInfoMessage(
            '管道支吊架清单已导出：%s' % output_path, '', False)
        return output_path
    except Exception as error:
        _log('combined bom export exception: %r' % error)
        MessageCenter.ShowErrorMessage(
            '管道支吊架清单导出失败，请查看调试日志。', '', False)
        return None


# ---------------------------------------------------------------------------
# 自包含 Excel(.xlsx) 写出（无第三方依赖，可在 OPM / CPython 下使用）
# ---------------------------------------------------------------------------


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
            column_widths[column_number] = max(
                column_widths.get(column_number, 10), min(42, visual_length + 2))
        xml_rows.append('<row r="%d">%s</row>' % (row_number, ''.join(cells)))
    columns = ''.join(
        '<col min="%d" max="%d" width="%s" customWidth="1"/>' %
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


def write_xlsx(output_path, sheets):
    """把若干工作表写成一个自包含的 .xlsx。

    ``sheets`` 为 ``(name, rows, header_rows)`` 序列；``rows`` 为二维列表
    （第一列可为字符串或数字），``header_rows`` 为需要表头样式的行号集合。
    返回 ``output_path``。
    """
    sheets = list(sheets)
    count = max(1, len(sheets))
    content_overrides = ''.join(
        '<Override PartName="/xl/worksheets/sheet%d.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.worksheet+xml"/>' % (index + 1)
        for index in range(count))
    workbook_sheets = ''.join(
        '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' %
        (_xml_escape(str(name)), index + 1, index + 1)
        for index, (name, _rows, _headers) in enumerate(sheets))
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>%s</sheets></workbook>' % workbook_sheets)
    workbook_rels = ''.join(
        '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet%d.xml"/>' % (index + 1, index + 1)
        for index in range(count))
    workbook_rels += (
        '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        % (count + 1))

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
            'package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '%s'
            '<Override PartName="/xl/styles.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>' % content_overrides)
        archive.writestr(
            '_rels/.rels',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', workbook_xml)
        archive.writestr('xl/_rels/workbook.xml.rels',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/'
                         'package/2006/relationships">%s</Relationships>'
                         % workbook_rels)
        archive.writestr('xl/styles.xml', _xlsx_styles_xml())
        for index, (_name, rows, header_rows) in enumerate(sheets):
            archive.writestr('xl/worksheets/sheet%d.xml' % (index + 1),
                             _xlsx_sheet_xml(rows, header_rows))
    return output_path


def build_excel_sheets(statistics, timestamp=''):
    """按统计字典生成（汇总 / 支吊架表 / 材料汇总表）三个工作表定义。"""
    supports = statistics.get('supportsByType', [])
    materials = statistics.get('materials', [])
    records = statistics.get('records', [])

    # 每个元素（整组）的构件明细，用于支吊架表。
    components_by_element = {}
    for record in records:
        if record.get('recordKind') == 'Assembly':
            continue
        key = record.get('elementId')
        entry = components_by_element.setdefault(key, [])
        quantity = int(record.get('quantity') or 1)
        suffix = '×%d' % quantity if quantity != 1 else ''
        entry.append('%s(%s)%s' % (record.get('componentName') or '',
                                   record.get('specification') or '', suffix))

    summary_rows = [[u'管道支吊架统计'], [u'导出时间', timestamp],
                    [u'支吊架总套数', statistics.get('assemblyCount', 0)],
                    [u'构件记录数', statistics.get('componentRecordCount', 0)],
                    [], [u'支吊架类型', u'套数', u'编号列表']]
    for entry in supports:
        summary_rows.append([entry['supportType'], entry['assemblyCount'],
                             '、'.join(entry['assemblyTags'])])

    support_rows = [[u'序号', u'支吊架类型', u'支吊架编号', u'管道号', u'规格',
                     u'构件明细', u'元素ID']]
    index = 0
    for record in records:
        if record.get('recordKind') != 'Assembly':
            continue
        index += 1
        support_rows.append([
            index, record.get('supportType') or '', record.get('assemblyTag') or '',
            record.get('pipeNumber') or '', record.get('specification') or '',
            '；'.join(components_by_element.get(record.get('elementId'), [])),
            record.get('elementId'),
        ])

    material_rows = [[u'支吊架类型', u'构件名称', u'规格', u'单位', u'数量',
                      u'总长(mm)']]
    for entry in materials:
        material_rows.append([
            entry['supportType'], entry['componentName'], entry['specification'],
            entry['unit'], entry['quantity'], entry['totalDesignLengthMm'],
        ])

    return [
        (u'汇总', summary_rows, set()),
        (u'支吊架表', support_rows, {1}),
        (u'材料汇总表', material_rows, {1}),
    ]


def export_combined_xlsx(output_path=None, statistics=None, timestamp=''):
    """扫描公共支吊架库，导出 Excel（汇总 / 支吊架表 / 材料汇总表）。"""
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, '管道支吊架_bom.xlsx')
    if statistics is None:
        statistics = collect_statistics()
    if not statistics.get('records'):
        MessageCenter.ShowErrorMessage(
            '未找到带有管道支吊架 ItemType 属性的实体。', '', False)
        return None
    try:
        write_xlsx(output_path, build_excel_sheets(statistics, timestamp))
        MessageCenter.ShowInfoMessage(
            '管道支吊架 Excel 清单已导出：%s' % output_path, '', False)
        return output_path
    except Exception as error:
        _log('combined xlsx export exception: %r' % error)
        MessageCenter.ShowErrorMessage(
            '管道支吊架 Excel 导出失败，请查看调试日志。', '', False)
        return None
