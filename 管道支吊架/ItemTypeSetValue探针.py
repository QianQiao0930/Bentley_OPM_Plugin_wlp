# -*- coding: utf-8 -*-
"""ItemType 实例赋值（SetValue）可行性探针 v2。

v1 结果（用户实测，2026-09-28）：本版 MSPy ``ApplyCustomItem`` 原生挂载
成功但 Python 侧拿到 ``None`` —— 实例拿不到就没法 SetValue。本版 v2
按官方 ``ItemTypeAttachDetach.py``（Detach 分支）的范式补一条回取路径：
attach 之后用 ``GetCustomItem(库名, 类型名)`` / ``GetCustomItems`` 把实例
取回来再试 ``SetValue``。若仍不可用，公共库会自动回退旧机制（内容寻址
命名 + 默认值烘焙），无需第三种方案。

在 OPM / MicroStation Python Editor（三维模型）中直接运行本文件。结果
打印到控制台并写入 模块/日志/ItemTypeSetValue探针_log.txt。

判读（看日志最后的 REPORT）：

* ``per-instance set=OK via <path>`` —— 可用；path 指明是哪条取实例的
  路径（return / GetCustomItem / GetCustomItems）， 公共库主路径会
  相应调整；
* ``per-instance set=FAILED`` —— 实例赋值彻底不可用，本版只能走回退
  机制（内容寻址命名，行为与旧版一致）；
* ``reuse no interference: OK`` —— 同一 ItemType 复用到第二个元素、
  各写各值互不串号，通过才算完整通过。

清理：探针库 ``ItemTypeSetValueProbe`` 尝试 ``DeleteLibrary``（本版无
此 API 则退化为 ``DeleteItemType`` 逐类型删除，再不行就留着——在
Item Types 对话框手动删除即可，不影响正式库）。
"""

from __future__ import division

import os
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

try:
    import faulthandler
    _FAULT_LOG = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '模块', '日志', 'ItemTypeSetValue探针_fault.log')
    _FAULT_STREAM = open(_FAULT_LOG, 'w', encoding='utf-8')
    faulthandler.enable(file=_FAULT_STREAM, all_threads=True)
except Exception:
    _FAULT_STREAM = None

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, '模块', '日志', 'ItemTypeSetValue探针_log.txt')
PROBE_LIBRARY = 'ItemTypeSetValueProbe'
PROBE_TYPE = 'ProbeInstanceValue'

# 探针只测三种值形态，属性名与正式契约一致。
PROBE_PROPERTIES = (
    ('AssemblyTag', 'string', 'PROBE-TAG-A'),
    ('DesignLengthMm', 'double', 123.456),
    ('Quantity', 'integer', 7),
)
SECOND_VALUES = (
    ('AssemblyTag', 'string', 'PROBE-TAG-B'),
    ('DesignLengthMm', 'double', 987.5),
    ('Quantity', 'integer', 3),
)
# 默认值一律中性（空串 / 0 / 1），模拟稳定化改造后的类默认值。
NEUTRAL_DEFAULTS = {
    'string': '',
    'double': 0.0,
    'integer': 1,
}


def _log(message):
    line = str(message)
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    except Exception:
        pass


def _new_ec_value(value):
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(int(value))
    return ec_value


def _type_code(value_kind):
    return {
        'string': CustomProperty.Type1.eString,
        'double': CustomProperty.Type1.eDouble,
        'integer': CustomProperty.Type1.eInteger,
    }[value_kind]


def _read_instance_value(item, name, kind):
    ec_value = ECValue()
    status = item.GetValue(ec_value, name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or ec_value.IsNull():
        return None
    if kind == 'double':
        return ec_value.GetDouble()
    if kind == 'integer':
        return ec_value.GetInteger()
    return ec_value.GetString()


def _make_probe_library(dgn_file):
    item_library = ItemTypeLibrary.FindByName(PROBE_LIBRARY, dgn_file)
    if item_library is None:
        item_library = ItemTypeLibrary(PROBE_LIBRARY, dgn_file, False)
    item_type = item_library.GetItemTypeByName(PROBE_TYPE)
    if item_type is None:
        item_type = item_library.AddItemType(PROBE_TYPE, False)
    for name, kind, _value in PROBE_PROPERTIES:
        item_property = item_type.GetPropertyByName(name)
        if item_property is None:
            item_property = item_type.AddProperty(name, False)
            item_property.SetType(_type_code(kind))
            item_property.SetDefaultValue(
                _new_ec_value(NEUTRAL_DEFAULTS[kind]))
    if not item_library.Write():
        raise RuntimeError('探针库写入失败。')
    item_library = ItemTypeLibrary.FindByName(PROBE_LIBRARY, dgn_file)
    return item_library.GetItemTypeByName(PROBE_TYPE)


def _make_shape_element(model, uor_per_mm, index):
    """10 mm 见方小面，作为挂 ItemType 的宿主元素。"""
    base_x = 100.0 * uor_per_mm
    base_y = index * 40.0 * uor_per_mm
    size = 10.0 * uor_per_mm
    points = DPoint3dArray()
    for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1)):
        points.append(DPoint3d(base_x + dx * size, base_y + dy * size, 0))
    element = EditElementHandle()
    ShapeHandler.CreateShapeElement(element, None, points, True, model)
    element.AddToModel()
    return element


def _fresh_handle(element):
    """AddToModel 后按元素 ID 重取句柄（与正式库同一防失效做法）。"""
    try:
        element_id = int(element.GetElementId())
        if element_id:
            model_ref = ISessionMgr.ActiveDgnModelRef
            if model_ref is not None:
                return EditElementHandle(element_id, model_ref.GetDgnModel())
    except Exception:
        pass
    return element


def _apply_and_get_instance(element, item_type):
    """attach 并尽量拿到实例；返回 (实例 or None, 取到实例的路径名)。

    三条路径依次尝试：

    1. ``ApplyCustomItem`` 返回值直接封送（v1 已确认本版返回 None）；
    2. 官方 Detach 范式：attach 后 ``GetCustomItem(库名, 类型名)``；
    3. ``GetCustomItems`` 遍历取第一个。
    """
    host = CustomItemHost(_fresh_handle(element), False)
    instance = None
    try:
        instance = host.ApplyCustomItem(item_type)
    except TypeError as error:
        if 'Unable to convert function return value' not in str(error):
            raise
    if instance is not None:
        return instance, 'return'
    try:
        instance = host.GetCustomItem(PROBE_LIBRARY, PROBE_TYPE)
    except Exception as error:
        _log('GetCustomItem failed: %r' % (error,))
    if instance is not None:
        return instance, 'GetCustomItem'
    try:
        count = host.GetCustomItemsCount()
        if count:
            from MSPyBentley import WString  # noqa: F401
            host.GetCustomItems(count)
            # GetCustomItems 需要预置容器；pythonnet 下不易构造，
            # 这条路径大概率走不通，标记即可。
            return None, 'GetCustomItems(unavailable)'
    except Exception as error:
        _log('GetCustomItems failed: %r' % (error,))
    return None, 'none'


def _set_instance_values(item, values):
    """按官方形态 ``SetValue(name, ECValue)`` 写值并提交。"""
    for name, _kind, want in values:
        item.SetValue(name, _new_ec_value(want))
    item.WriteChanges()


def _probe_set_value(item):
    """依次试 ECValue 包装 / 裸值；返回 (ok, 失败说明)。"""
    for form in ('ECValue', 'raw'):
        try:
            for name, _kind, want in PROBE_PROPERTIES:
                if form == 'ECValue':
                    item.SetValue(name, _new_ec_value(want))
                else:
                    item.SetValue(name, want)
            item.WriteChanges()
            readback = {}
            for name, kind, _want in PROBE_PROPERTIES:
                readback[name] = _read_instance_value(item, name, kind)
            failed = [
                name for name, _kind, want in PROBE_PROPERTIES
                if readback.get(name) != want
            ]
            if failed:
                return False, ('read-back mismatch on %s: %r'
                               % (failed, readback))
            return True, form
        except Exception as error:
            _log('form %s failed: %r' % (form, error))
            continue
    return False, 'both forms failed'


def _delete_library(dgn_file):
    """探针库清理：本版无 ``DeleteLibrary`` 时退化为逐类型删除。"""
    try:
        ItemTypeLibrary.DeleteLibrary(PROBE_LIBRARY, dgn_file, False)
        return 'deleted library'
    except AttributeError:
        pass
    except Exception as error:
        _log('DeleteLibrary other error: %r' % (error,))
    try:
        item_library = ItemTypeLibrary.FindByName(PROBE_LIBRARY, dgn_file)
        if item_library is not None:
            item_type = item_library.GetItemTypeByName(PROBE_TYPE)
            if item_type is not None:
                item_library.DeleteItemType(item_type, False)
                item_library.Write()
                return 'deleted item type'
    except Exception as error:
        _log('delete item type failed: %r' % (error,))
    return 'left in place (manual cleanup ok)'


def run():
    _log('=== ItemType SetValue probe v2 start ===')
    model = ISessionMgr.GetActiveDgnModel()
    if model is None or not model.Is3d():
        _log('SKIP: 探针需要在三维模型中运行。')
        return
    dgn_file = ISessionMgr.GetActiveDgnFile()
    uor_per_mm = model.GetModelInfo().GetUorPerMeter() / 1000.0

    try:
        item_type = _make_probe_library(dgn_file)
        _log('probe library ready: %s / %s' % (PROBE_LIBRARY, PROBE_TYPE))
    except Exception:
        _log('probe library init failed:\n%s' % traceback.format_exc())
        return

    first = second = None
    ok = False
    form = ''
    path = ''
    try:
        first = _make_shape_element(model, uor_per_mm, 0)
        _log('host element 1 created')

        instance1, path = _apply_and_get_instance(first, item_type)
        if instance1 is None:
            _log('RESULT: per-instance set=FAILED —— attach 成功但三条路径'
                 '均取不到实例（%s）。公共库将走回退机制（行为与旧版一致）。'
                 % (path or 'unknown'))
            return
        _log('instance 1 obtained via %s; testing SetValue...' % path)

        ok, form = _probe_set_value(instance1)
        if not ok:
            _log('RESULT: per-instance set=FAILED (%s)——稳定化方案走回退。'
                 % (form,))
            return

        # 复用同一 ItemType 挂第二个元素，写不同值，验证互不串号。
        second = _make_shape_element(model, uor_per_mm, 1)
        instance2, path2 = _apply_and_get_instance(second, item_type)
        if instance2 is None:
            _log('reuse apply failed to get instance (%s)' % (path2,))
            _log('reuse no interference: FAILED (no second instance)')
        else:
            _set_instance_values(instance2, SECOND_VALUES)
            tag1 = _read_instance_value(instance1, 'AssemblyTag', 'string')
            tag2 = _read_instance_value(instance2, 'AssemblyTag', 'string')
            len2 = _read_instance_value(instance2, 'DesignLengthMm', 'double')
            if (tag1 == 'PROBE-TAG-A' and tag2 == 'PROBE-TAG-B'
                    and len2 == 987.5):
                _log('reuse no interference: OK (%r / %r / %r)'
                     % (tag1, tag2, len2))
            else:
                _log('reuse no interference: FAILED (%r / %r / %r)'
                     % (tag1, tag2, len2))
    except Exception:
        _log('probe exception:\n%s' % traceback.format_exc())
    finally:
        for element in (first, second):
            if element is not None:
                try:
                    element.DeleteFromModel()
                except Exception as error:
                    _log('cleanup element failed: %r' % (error,))
        result = _delete_library(dgn_file)
        _log('cleanup: %s' % result)

    _log('REPORT: per-instance set=%s form=%s via=%s —— %s'
         % ('OK' if ok else 'FAILED', form, path,
            '公共库可启用实例赋值主路径。' if ok
            else '本版实例赋值不可用，公共库走回退机制（行为与旧版一致）。'))
    _log('=== ItemType SetValue probe v2 end ===')


run()
