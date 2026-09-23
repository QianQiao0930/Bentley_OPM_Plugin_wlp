# -*- coding: utf-8 -*-
"""Bentley OpenPlant Modeler F5 水平弯头的水平耳轴放置工具。

在 OPM / MicroStation Python Editor 中运行本文件。先在三维模型中选择一个
已有的 OpenPlant 90° 水平弯头，沿 Run 端切线方向拉伸确定长度 L。

* 沿用 F2 自动管径的水平耳轴；
* 用弯头外包络真实布尔切出的耳轴鞍口；
* A 型 6 mm 端板、B 型按表 2 端板或 C 型无端板；
* 耳轴外端附近直径 6 mm 的通气孔。

L 是 Outlet 支管轴线与 Run 轴的交点到耳轴最外端的水平距离。弯头 DN、外径、
两端中心距、端口坐标及水平方向均从 EC 属性与变换矩阵自动读取。
"""

from __future__ import division

import importlib
import ctypes
import faulthandler
import math
import os
import re
import sys
import tkinter as tk
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
COMMON_DIR = os.path.join(SCRIPT_DIR, '模块', '公共')
GEOM_DIR = os.path.join(SCRIPT_DIR, '模块', '竖直弯头的竖直耳轴')
if not os.path.isdir(COMMON_DIR):
    COMMON_DIR = os.path.join(REPO_ROOT, '管道支吊架', '模块', '公共')
for _path in (REPO_ROOT, SCRIPT_DIR, COMMON_DIR, GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    import bentley_ui.glass as _glass_module
    import bentley_ui as _bentley_ui_module
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (
    BORDER,
    CARD,
    CARD_SOFT,
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    SlimScrollbar,
)

import 支吊架公共库 as psb
# OPM 的 Python 进程会跨脚本运行缓存公共库；刷新后才能使用新增参数。
psb = importlib.reload(psb)

import elbow_selection_logic as _elbow_selection_logic

_elbow_selection_logic = importlib.reload(_elbow_selection_logic)
dimension_scale_to_mm = _elbow_selection_logic.dimension_scale_to_mm
horizontal_elbow_frame_from_matrix = _elbow_selection_logic.horizontal_elbow_frame_from_matrix
height_from_view_drag = _elbow_selection_logic.height_from_view_drag
moved_from_selection_view = _elbow_selection_logic.moved_from_selection_view
f5_number = _elbow_selection_logic.f5_number
f5_axis_points = _elbow_selection_logic.f5_axis_points
f5_pipe_axis_origin = _elbow_selection_logic.f5_pipe_axis_origin
f5_placement_direction = _elbow_selection_logic.f5_placement_direction
f5_azimuth_deg = _elbow_selection_logic.f5_azimuth_deg
f4_alignment_offset = _elbow_selection_logic.f4_alignment_offset
f4_end_plate_thickness = _elbow_selection_logic.f4_end_plate_thickness


DEBUG_LOG = os.path.join(SCRIPT_DIR, '模块', '日志',
                         '水平弯头的水平耳轴_debug_log.txt')
FAULT_LOG = os.path.join(SCRIPT_DIR, '模块', '日志',
                         '水平弯头的水平耳轴_fault.log')
_FAULT_STREAM = None
SUPPORT_TYPE = 'F5-[水平弯头的水平耳轴]'
SUPPORT_CODE = 'F5_HORIZONTAL_ELBOW_HORIZONTAL_TRUNNION'
SUCCESS = 0


class AttachmentIncompleteError(RuntimeError):
    """几何已写入模型，但清单 ItemType 未完整附加。"""

# 常用钢管外径及 Sch40 壁厚（mm）。所选弯头外径从 EC 读取；
# 表内壁厚用于自动选型后的空心耳轴。
PIPE_DATA = {
    15: (21.3, 2.77), 20: (26.9, 2.87), 25: (33.7, 3.38),
    32: (42.4, 3.56), 40: (48.3, 3.68), 50: (60.3, 3.91),
    65: (76.1, 5.16), 80: (88.9, 5.49), 100: (114.3, 6.02),
    125: (139.7, 6.55), 150: (168.3, 7.11), 200: (219.1, 8.18),
    250: (273.0, 9.27), 300: (323.9, 9.53), 350: (355.6, 9.53),
    400: (406.4, 9.53), 450: (457.2, 9.53), 500: (508.0, 9.53),
    550: (559.0, 9.53), 600: (610.0, 9.53), 650: (660.0, 18.89),
    700: (711.0, 19.05), 750: (762.0, 19.05), 800: (813.0, 19.05),
    850: (864.0, 19.05), 900: (914.0, 19.05), 950: (965.0, 19.05),
    1000: (1016.0, 19.05), 1050: (1067.0, 19.05),
    1100: (1118.0, 19.05), 1200: (1219.2, 19.05),
}

# 沿用 F2 的自动管径映射：主弯头 DN 上限、耳轴 DN 及保留的 F2 底板参数。
SUPPORT_TABLE = (
    (50, None, 200.0, 10.0),
    (100, 50, 200.0, 10.0),
    (150, 80, 200.0, 10.0),
    (200, 100, 200.0, 12.0),
    (300, 150, 250.0, 12.0),
    (400, 200, 300.0, 12.0),
    (500, 250, 350.0, 16.0),
    (600, 300, 400.0, 16.0),
    (700, 350, 450.0, 20.0),
    (800, 400, 500.0, 20.0),
    (900, 450, 550.0, 20.0),
    (1000, 500, 600.0, 25.0),
    (1200, 600, 700.0, 25.0),
)

# 只开放参考表中明确列出的主弯头规格，避免对表中未出现的 DN65、DN80、
# DN125 等规格静默插值。PIPE_DATA 中仍保留 DN80 等数据供耳轴自动选型使用。
SUPPORTED_MAIN_DNS = (
    15, 20, 25, 32, 40, 50, 100, 150, 200, 250, 300, 350, 400,
    450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000,
    1050, 1100, 1200,
)

DIRECTION_VECTORS = {
    "+X": (1.0, 0.0),
    "-X": (-1.0, 0.0),
    "+Y": (0.0, 1.0),
    "-Y": (0.0, -1.0),
}

# EC 查询与“管道信息查询”插件采用同一安全约束：工具回调里只记录元素 ID，
# 真正的 EC 查询在回调结束后执行；EC 实例必须在 FindInstances 的原始遍历中
# 当场读成纯 Python 数据，绝不把实例对象缓存到回调之外。
MSPY_MODULES = (
    "MSPyBentley", "MSPyBentleyGeom", "MSPyECObjects",
    "MSPyDgnPlatform", "MSPyDgnView", "MSPyMstnPlatform",
)
MSPY_REQUIRED = (
    "AccuSnap", "BentleyStatus", "DgnECManager", "DgnECHostType",
    "DgnElementSetTool", "ECObjectsStatus", "ECQuery",
    "ECQueryProcessFlags", "ECValue", "ECValuesCollection", "EditElementHandle",
    "ElementHandle",
    "FindInstancesScope", "FindInstancesScopeOption", "ISessionMgr",
    "NotificationManager", "PyCadInputQueue", "PyCommandState", "WString",
)


def _fill_mspy_symbols():
    sources = [sys.modules.get(name) for name in MSPY_MODULES]
    try:
        import builtins
        sources.append(builtins)
    except Exception:
        pass
    for name in MSPY_REQUIRED:
        if name in globals():
            continue
        for source in sources:
            if source is None:
                continue
            try:
                value = getattr(source, name)
            except Exception:
                continue
            if value is not None:
                globals()[name] = value
                break


_fill_mspy_symbols()

ELBOW_NUMBER_PROPERTIES = (
    "ANGLE", "NOMINAL_DIAMETER", "NOMINAL_DIAMETER_RUN_END",
    "OUTSIDE_DIAMETER", "WALL_THICKNESS", "LENGTH",
    "DESIGN_LENGTH_CENTER_TO_RUN_END",
    "DESIGN_LENGTH_CENTER_TO_OUTLET_END",
    "DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE",
    "DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE",
) + tuple("TRANSFORMATION_MATRIX.M%02d" % index for index in range(12))
ELBOW_TEXT_PROPERTIES = ("UNIT_OF_MEASURE", "COMPONENT_NAME", "NAME", "LINENUMBER")


def _log(message):
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
        with open(DEBUG_LOG, "a", encoding="utf-8") as stream:
            stream.write(str(message) + "\n")
    except Exception:
        pass


def _enable_fault_logging():
    global _FAULT_STREAM
    try:
        os.makedirs(os.path.dirname(FAULT_LOG), exist_ok=True)
        _FAULT_STREAM = open(FAULT_LOG, 'a', encoding='utf-8')
        _FAULT_STREAM.write('=== F5 session start ===\n')
        _FAULT_STREAM.flush()
        faulthandler.enable(_FAULT_STREAM)
    except Exception as error:
        _log('fault logging setup exception: %r' % error)


def _disable_fault_logging():
    global _FAULT_STREAM
    try:
        faulthandler.cancel_dump_traceback_later()
        faulthandler.disable()
    except Exception:
        pass
    if _FAULT_STREAM is not None:
        try:
            _FAULT_STREAM.close()
        except Exception:
            pass
        _FAULT_STREAM = None


def _watch_direction_change():
    if _FAULT_STREAM is None:
        return
    try:
        faulthandler.cancel_dump_traceback_later()
        faulthandler.dump_traceback_later(8.0, repeat=False,
                                          file=_FAULT_STREAM)
    except Exception as error:
        _log('fault watchdog exception: %r' % error)


def _succeeded(status):
    try:
        return int(status) == SUCCESS
    except (TypeError, ValueError):
        return status == SUCCESS


def _search_all_ec_flag():
    try:
        return ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses
    except Exception:
        return eECQUERY_PROCESS_SearchAllClasses


def _ec_number(instance, access_string):
    try:
        value = ECValue()
        status = instance.GetValue(value, access_string)
        if status != ECObjectsStatus.eECOBJECTS_STATUS_Success or value.IsNull():
            return None
        for getter in ("GetDouble", "GetInteger"):
            try:
                number = float(getattr(value, getter)())
                if not math.isnan(number) and not math.isinf(number):
                    return number
            except Exception:
                continue
    except Exception:
        pass
    return None


def _number_from_property_value(instance, access_string, property_value):
    """优先直接读枚举到的属性值；嵌套结构体子项用这种方式最稳定。"""
    try:
        value = property_value.GetValue()
        if value is not None and not value.IsNull():
            for getter in ("GetDouble", "GetInteger"):
                try:
                    number = float(getattr(value, getter)())
                    if not math.isnan(number) and not math.isinf(number):
                        return number
                except Exception:
                    continue
    except Exception:
        pass

    # 顶层普通属性通常可以从实例按 access string 读取。
    number = _ec_number(instance, access_string)
    if number is not None:
        return number

    # 某些 OPM 版本只允许把结构体子项格式化成字符串，再转成数值。
    text = _formatted_property_text(instance, access_string, property_value)
    if text:
        match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)
        if match:
            try:
                return float(match.group(0))
            except (TypeError, ValueError):
                pass
    return None


def _ec_text(instance, access_string):
    try:
        value = ECValue()
        status = instance.GetValue(value, access_string)
        if status != ECObjectsStatus.eECOBJECTS_STATUS_Success or value.IsNull():
            return None
        text = str(value.GetString()).strip()
        return text or None
    except Exception:
        return None


def _formatted_property_text(instance, access_string, property_value):
    """与“管道信息查询/全部属性”相同的 EC 文本读取路径。"""
    try:
        buffer = WString()
        # 不依赖不同 MSPy 版本的状态枚举比较；只要缓冲区实际有内容就采用。
        instance.GetValueAsString(buffer, access_string, False, 0)
        text = str(buffer).strip()
        if text:
            return text
    except Exception:
        pass
    try:
        value = property_value.GetValue()
        if value is not None:
            text = str(value.ToString()).strip()
            if text:
                return text
    except Exception:
        pass
    return None


def _number_from_access_string(instance, access_string):
    """对已经确认存在的结构体，按完整访问路径读取一个数值子项。"""
    try:
        buffer = WString()
        instance.GetValueAsString(buffer, access_string, False, 0)
        text = str(buffer).strip()
    except Exception:
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except (TypeError, ValueError):
        return None


def _text_from_property_value(instance, access_string, property_value):
    try:
        value = property_value.GetValue()
        if value is not None and not value.IsNull():
            text = str(value.GetString()).strip()
            if text:
                return text
    except Exception:
        pass
    return (_ec_text(instance, access_string)
            or _formatted_property_text(instance, access_string, property_value))


def _read_target_ec_values(instance, collection, numbers, texts, seen=None):
    """递归枚举真实存在的属性，并只读取本工具关心的值。"""
    if seen is None:
        seen = set()
    for property_value in collection:
        try:
            accessor = property_value.GetValueAccessor()
            access_string = str(accessor.GetManagedAccessString())
        except Exception:
            continue
        seen.add(access_string)
        if access_string in ELBOW_NUMBER_PROPERTIES:
            numbers[access_string] = _number_from_property_value(
                instance, access_string, property_value
            )
        elif access_string in ELBOW_TEXT_PROPERTIES:
            texts[access_string] = _text_from_property_value(
                instance, access_string, property_value
            )

        # OPM 的结构体属性采用惰性展开：必须先 GetValue()，随后
        # HasChildValues()/GetChildValues() 才能看到 M00～M15。管道信息查询的
        # “全部属性”窗口也是按这个顺序工作，不能直接先问 HasChildValues()。
        try:
            property_value.GetValue()
        except Exception:
            pass
        try:
            has_children = bool(property_value.HasChildValues())
            # 部分版本对结构体根节点错误返回 False，但 GetChildValues() 仍可用。
            if has_children or access_string == "TRANSFORMATION_MATRIX":
                child_values = property_value.GetChildValues()
                if child_values is not None:
                    _read_target_ec_values(
                        instance, child_values, numbers, texts, seen
                    )
        except Exception:
            pass

        # 若当前 MSPy 绑定仍拒绝展开子集合，矩阵根节点已经由枚举确认存在，
        # 可以安全地用完整访问路径直接读取标准 M00～M11 字段。
        if access_string == "TRANSFORMATION_MATRIX":
            for index in range(12):
                child_name = "TRANSFORMATION_MATRIX.M%02d" % index
                if numbers.get(child_name) is None:
                    numbers[child_name] = _number_from_access_string(
                        instance, child_name
                    )


def _ec_instance_class(instance):
    try:
        ec_class = instance.GetClass()
        return (str(ec_class.GetSchema().GetName()), str(ec_class.GetName()))
    except Exception:
        return "", ""


def _collect_elbow_records(element_handle):
    """把元素上的 EC 弯头候选读成纯 Python 字典。"""
    manager = DgnECManager.GetManager()
    query = ECQuery.CreateQuery(_search_all_ec_flag())
    scope = FindInstancesScope.CreateScope(
        element_handle, FindInstancesScopeOption(DgnECHostType.eElement)
    )
    collection = manager.FindInstances(scope, query)
    records = []
    if collection is None:
        return records
    for instance in collection[0]:
        schema_name, class_name = _ec_instance_class(instance)
        numbers = {}
        texts = {}
        seen = set()
        try:
            values = ECValuesCollection.Create(instance)
            _read_target_ec_values(instance, values, numbers, texts, seen)
        except Exception as error:
            _log("EC instance read failed %s.%s: %r" % (
                schema_name, class_name, error
            ))
            continue
        records.append({
            "schema": schema_name,
            "class": class_name,
            "numbers": numbers,
            "texts": texts,
            "seen": seen,
        })
    return records


def _pick_elbow_record(records):
    candidates = []
    for record in records:
        schema_name = (record.get("schema") or "").upper()
        class_name = (record.get("class") or "").upper()
        if schema_name.startswith("OPENPLANT") and "ELBOW" in class_name:
            score = 10
            if "90_DEGREE" in class_name:
                score += 3
            if record.get("numbers", {}).get("ANGLE") is not None:
                score += 1
            candidates.append((score, record))
    if not candidates:
        raise ValueError("所选元素不是 OpenPlant 弯头。")
    return max(candidates, key=lambda item: item[0])[1]


def _first_number(numbers, *names):
    for name in names:
        value = numbers.get(name)
        if value is not None:
            return value
    return None


def _main_dn_from_value(value_mm):
    if value_mm is None:
        raise ValueError("弯头缺少 NOMINAL_DIAMETER。")
    value_mm = float(value_mm)
    nearest = min(SUPPORTED_MAIN_DNS, key=lambda dn: abs(value_mm - dn))
    return nearest if abs(value_mm - nearest) <= 0.5 else None


def _element_handle_by_id(element_id):
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError("取不到活动 DGN 模型。")
    handle = EditElementHandle(int(element_id), model_ref.GetDgnModel())
    return handle if handle.IsValid() else None


def read_selected_elbow(element_id):
    """按元素 ID 读取弯头属性和精确放置坐标。"""
    handle = _element_handle_by_id(element_id)
    if handle is None:
        raise ValueError("所选元素已经失效，请重新选择。")
    records = _collect_elbow_records(handle)
    record = _pick_elbow_record(records)
    numbers = record["numbers"]
    texts = record["texts"]

    angle = numbers.get("ANGLE")
    class_name = record.get("class") or ""
    if angle is not None:
        if abs(angle - 90.0) > 0.5:
            raise ValueError("所选弯头角度为 %.2f°，第一版只支持 90° 弯头。" % angle)
    elif "90_DEGREE" not in class_name.upper():
        raise ValueError("无法确认所选弯头为 90° 弯头。")

    scale_mm = dimension_scale_to_mm(
        texts.get("UNIT_OF_MEASURE"),
        numbers.get("NOMINAL_DIAMETER")
    )
    nominal_raw = _first_number(
        numbers, "NOMINAL_DIAMETER", "NOMINAL_DIAMETER_RUN_END"
    )
    nominal_mm = nominal_raw * scale_mm if nominal_raw is not None else None
    main_dn = _main_dn_from_value(nominal_mm)
    if main_dn is None:
        raise ValueError(
            "弯头公称直径 %.1f mm 不在当前参考表支持范围内。" % nominal_mm)

    outside_raw = numbers.get("OUTSIDE_DIAMETER")
    if outside_raw is None or outside_raw <= 0.0:
        raise ValueError("弯头缺少有效的 OUTSIDE_DIAMETER。")
    outside_mm = outside_raw * scale_mm

    run_raw = _first_number(
        numbers, "DESIGN_LENGTH_CENTER_TO_RUN_END",
        "DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE"
    )
    outlet_raw = _first_number(
        numbers, "DESIGN_LENGTH_CENTER_TO_OUTLET_END",
        "DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE"
    )
    length_raw = numbers.get("LENGTH")
    if run_raw is None and length_raw is not None:
        run_raw = length_raw / 2.0
    if outlet_raw is None and length_raw is not None:
        outlet_raw = length_raw / 2.0
    if run_raw is None or outlet_raw is None:
        raise ValueError("弯头缺少中心至端面长度，无法确定两个端口坐标。")

    matrix = [numbers.get(
        "TRANSFORMATION_MATRIX.M%02d" % index
    ) for index in range(12)]
    missing_matrix = [
        "M%02d" % index for index, value in enumerate(matrix)
        if value is None
    ]
    if missing_matrix:
        captured = sorted(
            name for name, value in numbers.items()
            if name.startswith("TRANSFORMATION_MATRIX") and value is not None
        )
        _log("elbow %s matrix missing=%s captured=%s" % (
            element_id, missing_matrix, captured
        ))
        _log("elbow %s matrix access strings=%s" % (
            element_id,
            sorted(name for name in record.get("seen", set())
                   if "TRANSFORMATION" in name.upper() or name.upper().startswith("M"))
        ))
        raise ValueError(
            "弯头变换矩阵读取不完整，缺少：%s。" % ", ".join(missing_matrix)
        )
    model_ref = ISessionMgr.ActiveDgnModelRef
    frame = horizontal_elbow_frame_from_matrix(
        matrix, _uor_per_mm(model_ref), run_raw * scale_mm,
        outlet_raw * scale_mm
    )
    result = {
        "element_id": int(element_id),
        "schema": record.get("schema"),
        "class": class_name,
        "main_dn": main_dn,
        "nominal_diameter_mm": nominal_mm,
        "outside_diameter_mm": outside_mm,
        "wall_thickness_mm": ((numbers.get("WALL_THICKNESS") or 0.0)
                              * scale_mm),
        "frame": frame,
        "component_name": texts.get("COMPONENT_NAME") or texts.get("NAME"),
        "pipe_number": next((str(r.get("texts", {}).get("LINENUMBER")).strip()
                             for r in [record] + records if r.get("texts", {}).get("LINENUMBER")
                             and str(r.get("schema") or "").upper().startswith("OPENPLANT")), ""),
    }
    _log("selected horizontal elbow id=%s class=%s DN=%s OD=%.3f run=%s outlet=%s" % (
        element_id, class_name, main_dn, outside_mm,
        frame["run_port_mm"], frame["outlet_port_mm"]
    ))
    return result


def support_dimensions(main_dn):
    """按 F2 自动选型表返回耳轴 DN、外径和壁厚。"""
    for maximum_dn, trunnion_dn, plate_size, plate_thickness in SUPPORT_TABLE:
        if main_dn <= maximum_dn:
            selected_dn = main_dn if trunnion_dn is None else trunnion_dn
            od, wall = PIPE_DATA[selected_dn]
            return {
                "trunnion_dn": selected_dn,
                "trunnion_od": od,
                "trunnion_wall": wall,
                "plate_size": plate_size,
                "plate_thickness": plate_thickness,
            }
    raise ValueError("主弯头 DN%d 超出表 1 的 DN1200 上限。" % main_dn)


def _uor_per_mm(model_ref):
    return model_ref.GetDgnModel().GetModelInfo().GetUorPerMeter() / 1000.0


def _point(base, local_x_mm, local_y_mm, local_z_mm, direction, scale):
    """把支架局部坐标旋转到选定水平管方向并转换成 UOR。"""
    dx, dy = DIRECTION_VECTORS[direction]
    # 局部 Y 是局部 X 在平面内逆时针旋转 90 度后的方向。
    gx = dx * local_x_mm - dy * local_y_mm
    gy = dy * local_x_mm + dx * local_y_mm
    return DPoint3d(
        base.x + gx * scale,
        base.y + gy * scale,
        base.z + local_z_mm * scale,
    )


def _horizontal_vector(direction):
    dx, dy = DIRECTION_VECTORS[direction]
    return DVec3d(dx, dy, 0.0)


def _dpoint_from_mm(point_mm, scale):
    return DPoint3d(
        point_mm[0] * scale, point_mm[1] * scale, point_mm[2] * scale
    )


def _dvec_from_unit(vector):
    return DVec3d(vector[0], vector[1], vector[2])


def _frame_point(base_mm, local_x_mm, local_y_mm, local_z_mm,
                 horizontal_direction):
    hx, hy = horizontal_direction[0], horizontal_direction[1]
    # 局部 Y 为水平端方向在平面内逆时针旋转 90°。
    return (
        base_mm[0] + hx * local_x_mm - hy * local_y_mm,
        base_mm[1] + hy * local_x_mm + hx * local_y_mm,
        base_mm[2] + local_z_mm,
    )


def _body_from_sweep(profile, path, model_ref, path_start):
    try:
        result = SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False
        )
    except TypeError:
        result = SolidUtil.Create.BodyFromSweep(
            profile, path, model_ref, False, True, False,
            DVec3d.From(0.0, 0.0, 0.0), 0.0, 1.0, path_start
        )
    if result is None or len(result) < 2 or not _succeeded(result[0]):
        raise RuntimeError("沿路径扫掠实体失败。")
    return result[1]


def _arc_path(start, center, end):
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    arc = DEllipse3d.FromArcCenterStartEnd(center, start, end)
    path.Add(ICurvePrimitive.CreateArc(arc))
    return path


def _line_path(start, end):
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    path.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
    return path


def _disk_profile(center, normal, radius):
    ellipse = DEllipse3d.FromCenterNormalRadius(center, normal, radius)
    return CurveVector.CreateDisk(ellipse, CurveVector.eBOUNDARY_TYPE_Outer)


def _cylinder_body(model_ref, start, end, radius):
    axis = DVec3d(end.x - start.x, end.y - start.y, end.z - start.z)
    profile = _disk_profile(start, axis, radius)
    return _body_from_sweep(profile, _line_path(start, end), model_ref, start)


def _elbow_outer_body(model_ref, start, center, end, tangent, radius):
    profile = _disk_profile(start, tangent, radius)
    return _body_from_sweep(profile, _arc_path(start, center, end), model_ref, start)


def _subtract(target, *cutters):
    tools = ISolidKernelEntityPtrArray()
    for cutter in cutters:
        tools.append(cutter)
    status = SolidUtil.Modify.BooleanSubtract(target, tools)
    if not _succeeded(status):
        raise RuntimeError("SmartSolid 布尔差集失败（状态：%s）。" % status)


def _box_body(model_ref, base, half_size, thickness, direction, scale):
    corners = DPoint3dArray()
    corners.append(_point(base, -half_size, -half_size, 0.0, direction, scale))
    corners.append(_point(base, half_size, -half_size, 0.0, direction, scale))
    corners.append(_point(base, half_size, half_size, 0.0, direction, scale))
    corners.append(_point(base, -half_size, half_size, 0.0, direction, scale))
    corners.append(_point(base, -half_size, -half_size, 0.0, direction, scale))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, corners, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError("创建方底板轮廓失败。")
    converted = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if converted is None or len(converted) < 2 or not _succeeded(converted[0]):
        raise RuntimeError("方底板轮廓转换失败。")
    status = SolidUtil.Modify.SweepBody(
        converted[1], DVec3d(0.0, 0.0, thickness * scale)
    )
    if not _succeeded(status):
        raise RuntimeError("方底板拉伸失败。")
    return converted[1]


def _box_body_in_frame(model_ref, base_mm, half_size, thickness,
                       horizontal_direction, scale):
    corners = DPoint3dArray()
    for local_x, local_y in (
            (-half_size, -half_size), (half_size, -half_size),
            (half_size, half_size), (-half_size, half_size),
            (-half_size, -half_size)):
        corners.append(_dpoint_from_mm(_frame_point(
            base_mm, local_x, local_y, 0.0, horizontal_direction
        ), scale))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(
        profile, None, corners, model_ref.Is3d(), model_ref
    )
    if not _succeeded(status):
        raise RuntimeError("创建方底板轮廓失败。")
    converted = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if converted is None or len(converted) < 2 or not _succeeded(converted[0]):
        raise RuntimeError("方底板轮廓转换失败。")
    status = SolidUtil.Modify.SweepBody(
        converted[1], DVec3d(0.0, 0.0, thickness * scale)
    )
    if not _succeeded(status):
        raise RuntimeError("方底板拉伸失败。")
    return converted[1]


def _element_from_body(model_ref, body, color, label):
    element = EditElementHandle()
    status = SolidUtil.Convert.BodyToElement(
        element, body, None, model_ref.GetDgnModel()
    )
    if not _succeeded(status):
        raise RuntimeError("%s 转换为 SmartSolid 失败。" % label)
    properties = ElementPropertiesSetter()
    properties.SetColor(color)
    properties.Apply(element)
    return element


class HorizontalTrunnionBuilder(object):
    """F5：水平弯头的水平耳轴；同中心线或底平。"""

    def __init__(self, length_l_mm, end_plate_type, alignment_type,
                 direction_side='RUN',
                 hollow_trunnion=True, material_code='C1',
                 wall_override_mm=None):
        self.length_l_mm = float(length_l_mm)
        self.end_plate_type = str(end_plate_type)[0]
        self.alignment_type = alignment_type
        self.direction_side = direction_side
        self.hollow_trunnion = bool(hollow_trunnion)
        self.material_code = str(material_code).upper()
        self.wall_override_mm = (None if wall_override_mm is None
                                 else float(wall_override_mm))
        self.number = ''

    def _validate(self):
        if self.length_l_mm <= 0.0 or self.length_l_mm > 20000.0:
            raise ValueError('长度 L 必须在 0～20000 mm 之间。')
        if self.end_plate_type not in ('A', 'B', 'C'):
            raise ValueError('未知端板类型。')
        if self.alignment_type not in ALIGNMENT_TYPES:
            raise ValueError('未知耳轴对齐类型。')
        if self.direction_side not in ('RUN', 'OUTLET'):
            raise ValueError('未知的水平耳轴伸出方向。')
        if self.material_code not in _elbow_selection_logic.MATERIAL_CODES:
            raise ValueError('未知材料代码。')
        if self.wall_override_mm is not None and self.wall_override_mm <= 0.0:
            raise ValueError('指定的耳轴壁厚必须大于 0。')

    def create_from_elbow(self, elbow_info):
        self._validate()
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None or not model_ref.Is3d():
            raise RuntimeError('请在 OPM 三维模型中运行本工具。')

        scale = _uor_per_mm(model_ref)
        main_dn = elbow_info['main_dn']
        main_od = elbow_info['outside_diameter_mm']
        dims = support_dimensions(main_dn)  # 按用户要求沿用 F2 自动管径
        trunnion_od = dims['trunnion_od']
        wall = dims['trunnion_wall'] if self.wall_override_mm is None else self.wall_override_mm
        if wall >= trunnion_od / 2.0:
            raise ValueError('耳轴壁厚必须小于耳轴半径。')
        plate_t = f4_end_plate_thickness(dims['trunnion_dn'], self.end_plate_type)
        if self.length_l_mm <= main_od / 2.0 + trunnion_od + plate_t + 20.0:
            raise ValueError('长度 L 过短，必须容纳鞍口、通气孔和端板。')

        frame = elbow_info['frame']
        alignment = ('CENTER' if self.alignment_type == ALIGNMENT_TYPES[0]
                     else 'BOTTOM')
        offset = f4_alignment_offset(main_od, trunnion_od, alignment)
        points = f5_axis_points(frame, self.length_l_mm, plate_t, offset,
                                self.direction_side)
        direction = f5_placement_direction(frame, self.direction_side)
        self.number = f5_number(main_dn, dims['trunnion_dn'], wall,
                                dims['trunnion_wall'], self.material_code,
                                self.length_l_mm, self.end_plate_type,
                                f5_azimuth_deg(direction), alignment == 'BOTTOM')
        _log('F5 build: elbow=%s side=%s alignment=%s offset=%.3f origin=%s '
             'tube_start=%s tube_end=%s L=%.3f' % (
                 elbow_info['element_id'], self.direction_side, alignment, offset,
                 points['origin_mm'], points['tube_start_mm'],
                 points['tube_end_mm'], self.length_l_mm))

        # 重建选中弯头的实心外包络作为鞍口刀具，保持主管原件不变。
        _log('F5 kernel: create elbow cutter')
        cutter = _elbow_outer_body(
            model_ref,
            _dpoint_from_mm(frame['run_port_mm'], scale),
            _dpoint_from_mm(frame['arc_center_mm'], scale),
            _dpoint_from_mm(frame['outlet_port_mm'], scale),
            _dvec_from_unit(frame['axis_x']), main_od * scale / 2.0)

        _log('F5 kernel: create tube')
        tube_start = _dpoint_from_mm(points['tube_start_mm'], scale)
        tube_end = _dpoint_from_mm(points['tube_end_mm'], scale)
        tube = _cylinder_body(model_ref, tube_start, tube_end,
                              trunnion_od * scale / 2.0)
        _log('F5 kernel: subtract elbow cutter')
        _subtract(tube, cutter)
        if self.hollow_trunnion:
            inner_radius = (trunnion_od / 2.0 - wall) * scale
            bore_start = _dpoint_from_mm(_frame_point(
                points['tube_start_mm'], -1.0, 0.0, 0.0, direction), scale)
            bore_end = _dpoint_from_mm(_frame_point(
                points['tube_end_mm'], 1.0, 0.0, 0.0, direction), scale)
            _log('F5 kernel: subtract bore')
            _subtract(tube, _cylinder_body(model_ref, bore_start, bore_end,
                                           inner_radius))

        # Ø6 通气孔，靠近耳轴外端，孔轴沿世界 Z。
        hole_x = max(main_od / 2.0 + trunnion_od / 2.0,
                     self.length_l_mm - plate_t - 20.0)
        hole_center = _frame_point(points['origin_mm'], hole_x, 0.0, 0.0, direction)
        hole_start = _dpoint_from_mm((hole_center[0], hole_center[1],
                                      hole_center[2] - trunnion_od), scale)
        hole_end = _dpoint_from_mm((hole_center[0], hole_center[1],
                                    hole_center[2] + trunnion_od), scale)
        _log('F5 kernel: subtract vent hole')
        _subtract(tube, _cylinder_body(model_ref, hole_start, hole_end,
                                       3.0 * scale))

        bodies = [(tube, 3, '水平耳轴')]
        if plate_t > 0.0:
            plate = _cylinder_body(
                model_ref, tube_end,
                _dpoint_from_mm(points['outer_end_mm'], scale),
                (trunnion_od + 25.0) * scale / 2.0)
            bodies.append((plate, 4, self.end_plate_type + ' 型端板'))

        elements = [_element_from_body(model_ref, body, color, label)
                    for body, color, label in bodies]
        cell = EditElementHandle()
        NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, SUPPORT_CODE, True, model_ref.GetDgnModel())
        for element in elements:
            status = NormalCellHeaderHandler.AddChildElement(cell, element)
            if not _succeeded(status):
                raise RuntimeError('耳轴构件加入单元失败（状态：%s）。' % status)
        status = NormalCellHeaderHandler.AddChildComplete(cell)
        if not _succeeded(status):
            raise RuntimeError('耳轴单元完成失败（状态：%s）。' % status)
        status = cell.AddToModel()
        if not _succeeded(status):
            raise RuntimeError('耳轴单元写入当前模型失败（状态：%s）。' % status)

        components = [{
            'code': 'F5_PIPE_DN%d_W%s_%s' % (
                dims['trunnion_dn'], str(wall).replace('.', '_'), self.material_code),
            'name': '水平耳轴钢管' if self.hollow_trunnion else '水平耳轴圆钢',
            'specification': 'DN%d Ø%g × %g mm，%s' % (
                dims['trunnion_dn'], trunnion_od, wall, self.material_code),
            'length': points['tube_length_mm'],
            'quantity': 1, 'unit': '件',
        }]
        if plate_t > 0.0:
            components.append({
                'code': 'F5_END_%s_DN%d_T%g' % (
                    self.end_plate_type, dims['trunnion_dn'], plate_t),
                'name': self.end_plate_type + ' 型端板',
                'specification': 'Ø%g × %g mm' % (trunnion_od + 25.0, plate_t),
                'length': plate_t, 'quantity': 1, 'unit': '件',
            })
        try:
            attached = psb.attach_components(
                cell, support_type=SUPPORT_TYPE, support_code=SUPPORT_CODE,
                assembly_tag=self.number,
                assembly_spec='%s；DN%d；L %g mm；端板 %s' % (
                    self.number, main_dn, self.length_l_mm, self.end_plate_type),
                components=components,
                pipe_number=elbow_info.get('pipe_number') or '')
        except Exception as error:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项写入失败：%s。请勿重复建模。'
                % (cell.GetElementId(), error))
        if attached < len(components) + 1:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项仅写入 %d/%d。请勿重复建模。'
                % (cell.GetElementId(), attached, len(components) + 1))
        _log('created F5 from elbow %s: %s, cell=%s' % (
            elbow_info['element_id'], self.number, cell.GetElementId()))
        return [cell]


UI_TITLE = 'F5-[水平弯头的水平耳轴]'
BASE_TYPES = ("A 6 mm 端板", "B 表 2 端板", "C 无端板")
ALIGNMENT_TYPES = ("相同中心线", "底平（FB）")
_ACTIVE_PLACEMENT_TOOL = None
_ACTIVE_PANEL = None


def _read_element_id(element_handle):
    for name in ("ElementId", "GetElementId"):
        try:
            value = getattr(element_handle, name)
            return int(value() if callable(value) else value)
        except Exception:
            continue
    return None


class TrunnionPanel(GlassDialog):
    """与支吊架插件一致的常驻参数面板和 Bentley 点选主循环。"""

    STATE_KEY = "HorizontalElbowHorizontalTrunnion"

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._live_height = None
        self.processing = False
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        self._height = tk.StringVar(value="1000.0")
        self._base_type = tk.StringVar(value=BASE_TYPES[0])
        self._alignment = tk.StringVar(value=ALIGNMENT_TYPES[0])
        self._direction_side = tk.StringVar(value='RUN')
        self._direction_text = tk.StringVar(value='伸出方向：Run 端')
        self._hollow = tk.BooleanVar(value=True)
        self._material = tk.StringVar(value='C1')
        self._wall_override = tk.StringVar(value='')
        self._number = tk.StringVar(value='F5 编号：选弯头后显示')
        self._selected_elbow_info = None
        self._status = tk.StringVar(value="请在模型中点选一个水平 90° 弯头。")
        self._selection = tk.StringVar(
            value="等待点选｜将自动读取 EC 规格、端口坐标和水平方向。"
        )
        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol("WM_DELETE_WINDOW", self.close_panel)
        try:
            self.minsize(480, 610)
        except tk.TclError:
            pass

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            "点选弯头后自动进入拉伸和 AccuDraw；移动预览，左键确认",
        )
        form.columnconfigure(0, weight=1)

        hint = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                        highlightthickness=1)
        hint.grid(row=0, column=0, sticky="ew")
        tk.Label(
            hint,
            text=("点选弯头后可点击换向，沿两条水平切线之一拉伸。"
                  "L 从两支管轴线的理论交点量到最外端；底平标 FB。"),
            bg=CARD_SOFT, fg=INK, font=UI_FONT_SMALL, justify="left",
            wraplength=410,
        ).pack(anchor="w", padx=12, pady=9)

        ttk.Label(form, text="1. 放置参数", style="Section.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 3)
        )
        height_entry = self._entry_row(form, 2, "实时长度 L", self._height, "mm")
        height_entry.configure(state="readonly")
        self._combo_row(form, 3, "端板类型", self._base_type, BASE_TYPES)

        check_row = tk.Frame(form, bg=CARD)
        check_row.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        alignment_row = tk.Frame(check_row, bg=CARD)
        alignment_row.pack(anchor='w', pady=(0, 7))
        tk.Label(alignment_row, text='耳轴位置', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        alignment_combo = ttk.Combobox(
            alignment_row, textvariable=self._alignment,
            values=ALIGNMENT_TYPES, state='readonly', width=20,
            style='Glass.TCombobox')
        alignment_combo.pack(side='left', padx=(12, 0))
        alignment_combo.bind('<<ComboboxSelected>>',
                             lambda _event: self._update_number_from_current())
        direction_row = tk.Frame(check_row, bg=CARD)
        direction_row.pack(anchor='w', pady=(0, 7))
        tk.Label(direction_row, textvariable=self._direction_text,
                 bg=CARD, fg=INK, font=UI_FONT_BOLD).pack(side='left')
        # 拉伸期间点击的按钮不能使用 Canvas 悬停动画；Tk 的 after 重绘会与
        # Bentley 动态绘图循环交错，曾在 tkinter.update 中触发访问冲突。
        tk.Button(
            direction_row, text='换向', command=self.change_direction,
            bg=CARD_SOFT, fg=INK, activebackground=FIELD,
            activeforeground=INK, font=UI_FONT, relief='flat',
            bd=0, highlightthickness=0, padx=12, pady=6,
        ).pack(side='left', padx=(12, 0))
        tk.Checkbutton(
            check_row, text="耳轴按钢管建模（取消则为实心圆钢）",
            variable=self._hollow, bg=CARD, fg=INK, activebackground=CARD,
            activeforeground=INK, selectcolor=FIELD, font=UI_FONT,
            highlightthickness=0, bd=0,
        ).pack(anchor="w")
        material_row = tk.Frame(check_row, bg=CARD)
        material_row.pack(anchor='w', pady=(7, 0))
        tk.Label(material_row, text='材料代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        ttk.Combobox(
            material_row, textvariable=self._material,
            values=_elbow_selection_logic.MATERIAL_CODES,
            state='readonly', width=7, style='Glass.TCombobox').pack(
                side='left', padx=(10, 12))
        tk.Label(material_row, text='耳轴壁厚', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        tk.Entry(material_row, textvariable=self._wall_override, width=8,
                 font=UI_FONT, fg=INK, bg=FIELD, relief='flat',
                 highlightthickness=1, highlightbackground=BORDER,
                 insertbackground=INK, justify='center').pack(
                     side='left', padx=(8, 5), ipady=3)
        tk.Label(material_row, text='mm（空 = STD）', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        ttk.Separator(form, orient="horizontal").grid(
            row=5, column=0, sticky="ew", pady=12
        )
        ttk.Label(form, text="2. 弯头识别 / 自动选型", style="Section.TLabel").grid(
            row=6, column=0, sticky="w", pady=(0, 3)
        )
        selection_card = tk.Frame(
            form, bg=CARD_SOFT, highlightbackground=BORDER, highlightthickness=1
        )
        selection_card.grid(row=7, column=0, sticky="ew")
        tk.Label(
            selection_card, textvariable=self._selection, bg=CARD_SOFT,
            fg="#1F5F99", font=UI_FONT_SMALL, justify="left",
            wraplength=410,
        ).pack(anchor="w", padx=12, pady=9)
        tk.Label(selection_card, textvariable=self._number, bg=CARD_SOFT,
                 fg=INK, font=UI_FONT_BOLD, justify='left',
                 wraplength=410).pack(anchor='w', padx=12, pady=(0, 9))

        ttk.Label(form, text="生成记录", style="Section.TLabel").grid(
            row=8, column=0, sticky="w", pady=(12, 3)
        )
        log_frame = tk.Frame(
            form, bg=CARD_SOFT, highlightbackground=BORDER, highlightthickness=1
        )
        log_frame.grid(row=9, column=0, sticky="nsew")
        form.rowconfigure(9, weight=1)
        self._log_view = tk.Text(
            log_frame, height=6, width=46, wrap="word", font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief="flat", highlightthickness=0,
            bd=0, padx=9, pady=7, cursor="arrow", takefocus=0,
        )
        log_bar = SlimScrollbar(
            log_frame, command=self._log_view.yview, trough=CARD_SOFT
        )
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side="left", fill="both", expand=True)
        log_bar.pack(side="right", fill="y")
        self._log_view.configure(state="disabled")

        self._status_chip = self.make_status_chip(
            form, self._status, wraplength=410
        )
        self._status_chip.grid(row=10, column=0, sticky="ew", pady=(10, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=11, column=0, sticky="ew", pady=(10, 0))
        self.clear_button = RoundButton(
            buttons, "清空记录", self.clear_log, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD,
        )
        self.close_button = RoundButton(
            buttons, "退出", self.close_panel, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD,
        )
        self.close_button.pack(side="right")
        self.clear_button.pack(side="right", padx=(0, 8))

    def _entry_row(self, form, row, label, variable, hint=""):
        frame = tk.Frame(form, bg=CARD)
        frame.grid(row=row, column=0, sticky="w", pady=(7, 0))
        tk.Label(frame, text=label, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side="left")
        entry = tk.Entry(
            frame, textvariable=variable, width=11, font=UI_FONT, fg=INK,
            bg=FIELD, relief="flat", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor="#9FB4CC",
            insertbackground=INK, justify="center",
        )
        entry.pack(side="left", padx=(12, 0), ipady=4)
        if hint:
            tk.Label(frame, text=hint, bg=CARD, fg=MUTED,
                     font=UI_FONT_SMALL).pack(side="left", padx=(7, 0))
        return entry

    def _combo_row(self, form, row, label, variable, values):
        frame = tk.Frame(form, bg=CARD)
        frame.grid(row=row, column=0, sticky="w", pady=(7, 0))
        tk.Label(frame, text=label, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side="left")
        combo = ttk.Combobox(
            frame, textvariable=variable, values=values, state="readonly",
            width=20, style="Glass.TCombobox",
        )
        combo.pack(side="left", padx=(12, 0))
        return combo

    def restore_state(self):
        height = self.ui_state.get("length_l")
        if isinstance(height, (int, float)) and 0.0 < height <= 20000.0:
            self._height.set("%.1f" % height)
        base_type = self.ui_state.get("end_plate_type")
        if base_type in BASE_TYPES:
            self._base_type.set(base_type)
        alignment = self.ui_state.get('alignment_type')
        if alignment in ALIGNMENT_TYPES:
            self._alignment.set(alignment)
        direction_side = self.ui_state.get('direction_side')
        if direction_side in ('RUN', 'OUTLET'):
            self._direction_side.set(direction_side)
        self._update_direction_text()
        hollow = self.ui_state.get("hollow_trunnion")
        if isinstance(hollow, bool):
            self._hollow.set(hollow)
        material = self.ui_state.get('material_code')
        if material in _elbow_selection_logic.MATERIAL_CODES:
            self._material.set(material)
        self._wall_override.set(str(self.ui_state.get('wall_override_mm') or ''))

    def persist_state(self, state):
        try:
            state["length_l"] = float(self._height.get().strip())
        except (TypeError, ValueError):
            state["length_l"] = 1000.0
        state["end_plate_type"] = self._base_type.get()
        state['alignment_type'] = self._alignment.get()
        state['direction_side'] = self._direction_side.get()
        state["hollow_trunnion"] = bool(self._hollow.get())
        state['material_code'] = self._material.get()
        state['wall_override_mm'] = self._wall_override.get().strip()

    def builder(self, length):
        if not 50.0 <= length <= 20000.0:
            raise ValueError('长度 L 必须在 50～20000 mm 之间。')
        wall_text = self._wall_override.get().strip().replace(',', '')
        try:
            wall = None if not wall_text else float(wall_text)
        except (TypeError, ValueError):
            raise ValueError('耳轴壁厚必须是有效数字，或留空采用 STD。')
        builder = HorizontalTrunnionBuilder(
            length, self._base_type.get(), self._alignment.get(),
            self._direction_side.get(),
            bool(self._hollow.get()),
            self._material.get(), wall)
        builder._validate()
        return builder

    def _update_direction_text(self):
        side = self._direction_side.get()
        label = 'Run 端' if side == 'RUN' else 'Outlet 端反向'
        if self._selected_elbow_info is None:
            self._direction_text.set('伸出方向：' + label)
            return
        direction = f5_placement_direction(
            self._selected_elbow_info['frame'], side)
        azimuth = int(f5_azimuth_deg(direction) + 0.5) % 360
        self._direction_text.set('伸出方向：%s｜方位角 %d°' % (label, azimuth))

    def change_direction(self):
        """按钮回调只入队；不在 Tk 回调里操作正在动态绘图的原生工具。"""
        if self.processing or self._close_requested:
            return
        self.pending = [item for item in self.pending
                        if item[0] not in ('height', 'cancel_height',
                                           'change_direction')]
        self._live_height = None
        self.pending.append(('change_direction',))

    def _process_change_direction(self):
        """只重置本次拉伸；Bentley 动态工具保持运行。"""
        _watch_direction_change()
        self._direction_side.set(
            'OUTLET' if self._direction_side.get() == 'RUN' else 'RUN')
        self._update_direction_text()
        if self._selected_elbow_info is not None:
            self._selection.set(self._selection_text(self._selected_elbow_info))
        self._update_number_from_current()
        tool = _ACTIVE_PLACEMENT_TOOL
        if isinstance(tool, TrunnionHeightTool) and tool.panel is self:
            tool._has_preview = False
            tool._accept_armed = False
            tool._first_frame_logged = False
            self.set_status('已换向；旧拉伸已放弃，移动光标预览新方向后左键确认。')
        else:
            self.set_status('已换向；选择水平弯头后开始拉伸。')
        _log('F5 direction changed to %s; preview reset' %
             self._direction_side.get())

    def queue_pick(self, element_id, pick_view_position):
        """原生工具回调只入队；不在回调内访问 EC 或 Tk 控件。"""
        if self.processing or self.pending:
            return
        self.pending.append(("pick", element_id, pick_view_position))

    def queue_height(self, elbow_info, height):
        """数据点回调只提交纯 Python 数据，实体创建留给主循环。"""
        self.pending.append(("height", elbow_info, height))

    def queue_cancel_height(self):
        self.pending.append(("cancel_height",))

    def show_live_height(self, height):
        self._live_height = height

    def _update_number(self, length):
        info = self._selected_elbow_info
        if info is None:
            return
        try:
            dims = support_dimensions(info['main_dn'])
            wall_text = self._wall_override.get().strip().replace(',', '')
            wall = dims['trunnion_wall'] if not wall_text else float(wall_text)
            bend_code = (self._alignment.get() == ALIGNMENT_TYPES[1])
            number = f5_number(
                info['main_dn'], dims['trunnion_dn'], wall,
                dims['trunnion_wall'], self._material.get(), length,
                self._base_type.get()[0],
                f5_azimuth_deg(f5_placement_direction(
                    info['frame'], self._direction_side.get())), bend_code)
            self._number.set('F5 编号：' + number)
        except (ValueError, TypeError, IndexError) as error:
            self._number.set('F5 编号：' + str(error))

    def _update_number_from_current(self):
        try:
            self._update_number(float(self._height.get()))
        except (TypeError, ValueError, tk.TclError):
            pass

    def set_status(self, message, is_error=False):
        self._pending_status = message
        self._pending_status_is_error = bool(is_error)

    def _apply_status(self, message, is_error=False):
        prefix = "错误｜" if is_error else "状态｜"
        try:
            self._status.set(prefix + message)
        except tk.TclError:
            return
        try:
            NotificationManager.OutputPrompt(message)
        except Exception:
            pass

    def _append_log(self, text):
        try:
            self._log_view.configure(state="normal")
            if self._log_view.index("end-1c") != "1.0":
                self._log_view.insert("end", "\n")
            self._log_view.insert("end", text)
            self._log_view.see("end")
            self._log_view.configure(state="disabled")
        except tk.TclError:
            pass

    def clear_log(self):
        try:
            self._log_view.configure(state="normal")
            self._log_view.delete("1.0", "end")
            self._log_view.configure(state="disabled")
        except tk.TclError:
            pass

    def _selection_text(self, elbow_info):
        dims = support_dimensions(elbow_info["main_dn"])
        frame = elbow_info["frame"]
        run_port = frame["run_port_mm"]
        outlet_port = frame["outlet_port_mm"]
        return (
            "元素 %s｜%s\nDN%d · 外径 %.1f mm → 耳轴 DN%d（Ø%.1f）\n"
            "Run 端 (%.1f, %.1f, %.1f)｜Outlet 端 (%.1f, %.1f, %.1f) mm｜方位角 %s°"
            % ((elbow_info["element_id"], elbow_info["class"],
                elbow_info["main_dn"], elbow_info["outside_diameter_mm"],
                dims["trunnion_dn"], dims["trunnion_od"])
               + tuple(run_port) + tuple(outlet_port)
               + (str(int(f5_azimuth_deg(f5_placement_direction(
                   frame, self._direction_side.get())) + 0.5) % 360),))
        )

    def _process_pick(self, element_id, pick_view_position):
        self.processing = True
        try:
            elbow_info = read_selected_elbow(element_id)
            self._selected_elbow_info = elbow_info
            self._selection.set(self._selection_text(elbow_info))
            self._update_direction_text()
            TrunnionHeightTool.InstallNewInstance(
                0, self, elbow_info, pick_view_position)
            self.set_status("已进入水平拉伸：移动光标预览，左键确认生成；右键取消。")
        except Exception as error:
            _log("selection exception for %s: %r" % (element_id, error))
            self.set_status("%s；请重新点选有效的水平弯头。" % error, True)
            if not isinstance(_ACTIVE_PLACEMENT_TOOL, TrunnionPlacementTool):
                self.restart_selection(False)
        finally:
            self.processing = False

    def _process_height(self, elbow_info, height):
        self.processing = True
        try:
            builder = self.builder(height)
            elements = builder.create_from_elbow(elbow_info)
            self._height.set("%.1f" % height)
            self._number.set('F5 编号：' + builder.number)
            self._append_log(
                "已生成｜%s｜元素 %s｜DN%d｜L %.1f mm｜端板 %s｜单元 %s"
                % (builder.number, elbow_info["element_id"], elbow_info["main_dn"], builder.length_l_mm,
                   builder.end_plate_type,
                   ", ".join(str(item.GetElementId()) for item in elements))
            )
            self.set_status("生成完成；可继续点选另一个水平弯头。")
        except AttachmentIncompleteError as error:
            _log("height/attachment exception for %s: %r" % (elbow_info["element_id"], error))
            self.set_status(str(error), True)
        except Exception as error:
            _log("height/create exception for %s: %r" % (elbow_info["element_id"], error))
            self.set_status("%s；请重新点选弯头后拉伸。" % error, True)
        finally:
            self.processing = False
            self.restart_selection(False)

    def _run_pending(self):
        pending, self.pending = self.pending, []
        for item in pending:
            if item[0] == "pick":
                self._process_pick(item[1], item[2])
            elif item[0] == "height":
                self._process_height(item[1], item[2])
            elif item[0] == "cancel_height":
                self.restart_selection()
            elif item[0] == "change_direction":
                self._process_change_direction()
        if self._live_height is not None:
            self._height.set("%.1f" % self._live_height)
            self._update_number(self._live_height)
            self._live_height = None
        if self._pending_status is not None:
            message = self._pending_status
            is_error = self._pending_status_is_error
            self._pending_status = None
            self._pending_status_is_error = False
            self._apply_status(message, is_error)

    def restart_selection(self, announce=True):
        try:
            TrunnionPlacementTool.InstallNewInstance(0, self, False)
            if announce:
                self.set_status("请在模型中点选一个 OpenPlant 90° 水平弯头。")
        except Exception as error:
            self.set_status("点选工具启动失败：%s" % error, True)

    def close_panel(self):
        self._close_requested = True

    def _finish(self):
        _disable_fault_logging()
        try:
            PyCommandState.StartDefaultCommand()
        except Exception as error:
            _log("StartDefaultCommand exception: %r" % error)
        try:
            self.destroy()
        except tk.TclError:
            pass

    def run_dialog_loop(self):
        """Tk/Bentley 联合循环；每次 PythonMainLoop 返回后再读 EC 和建模。"""
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            if self._close_requested:
                self._finish()
                break
            # Tk 按钮提交的换向只改 Python 状态，动态工具继续运行。
            if any(item[0] == 'change_direction' for item in self.pending):
                self._run_pending()
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception as error:
                _log("PythonMainLoop exception: %r" % error)
                self._apply_status("Bentley 输入循环失败：%s" % error, True)
                break
            self._run_pending()


class TrunnionPlacementTool(DgnElementSetTool):
    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.panel = panel
        self.m_self = self
        self._located_id = None

    def _GetToolName(self, name):
        return WString("SelectVerticalElbowForHorizontalTrunnion")

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

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = _read_element_id(handle)
            return self._located_id is not None
        except Exception as error:
            _log("post locate exception: %r" % error)
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        if self.panel is None:
            return True
        if self._located_id is None:
            self.panel.set_status(
                "没有定位到元素，请把光标放在弯头主单元上再点击。", True
            )
            return True
        element_id = self._located_id
        self._located_id = None
        pick_point = event.GetViewPoint()
        self.panel.queue_pick(element_id, (
            int(event.GetViewNum()), float(pick_point.x), float(pick_point.y)))
        return True

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.close_panel()
        return True

    def _OnRestartTool(self):
        panel = self.panel
        self.panel = None
        if panel is not None and not panel._close_requested:
            TrunnionPlacementTool.InstallNewInstance(
                self.GetToolId(), panel, False
            )

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        global _ACTIVE_PLACEMENT_TOOL
        _ACTIVE_PLACEMENT_TOOL = TrunnionPlacementTool(tool_id, panel)
        _ACTIVE_PLACEMENT_TOOL.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return _ACTIVE_PLACEMENT_TOOL


def _left_mouse_button_is_down():
    """只用物理按键状态判断选取点击是否已释放，不使用时间阈值。"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


class TrunnionHeightTool(DgnPrimitiveTool):
    """选中弯头后立即动态预览；下一个数据点确认建模。"""

    def __init__(self, tool_id, panel, elbow_info, pick_view_position):
        DgnPrimitiveTool.__init__(self, tool_id, tool_id)
        self.panel = panel
        self.elbow_info = elbow_info
        self.m_self = self
        self._has_preview = False
        self._pick_view_position = pick_view_position
        self._pick_button_released = False
        self._accept_armed = False
        self._accudraw_direction_side = panel._direction_side.get()
        self._first_frame_logged = False
        self._preview_frames = []

    def _moved_from_pick(self, event):
        point = event.GetViewPoint()
        return moved_from_selection_view(
            self._pick_view_position, event.GetViewNum(),
            (point.x, point.y))

    def _GetToolName(self, name):
        return WString("DragHorizontalTrunnionLength")

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)

    def _start_drag(self, focus_accudraw=True):
        """选取数据点结束后启动水平拉伸及 AccuDraw。"""
        self._BeginDynamics()
        if not self.GetDynamicsStarted():
            raise RuntimeError('Bentley 动态绘图未启动。')
        if not self.update_accudraw_context(focus_accudraw):
            raise RuntimeError('AccuDraw 拉伸方向设置失败。')

    def update_accudraw_context(self, focus_accudraw=True):
        """新拉伸工具安装完成后设置精确绘图原点和方向轴。"""
        try:
            frame = self.elbow_info['frame']
            scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
            anchor = _dpoint_from_mm(f5_pipe_axis_origin(frame), scale)
            direction = f5_placement_direction(
                frame, self.panel._direction_side.get())
            accu_draw = AccuDraw.GetInstance()
            accu_draw.Activate()
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetOrigin, anchor)
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetXAxis, None,
                                 _dvec_from_unit(direction))
            if focus_accudraw:
                accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetFocus)
            return True
        except Exception as error:
            _log('AccuDraw horizontal context exception: %r' % error)
            return False

    def _height_from_event(self, event):
        scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
        frame = self.elbow_info['frame']
        origin = f5_pipe_axis_origin(frame)
        direction = f5_placement_direction(
            frame, self.panel._direction_side.get())
        if event.GetCoordSource() == DgnButtonEvent.eFROM_Precision:
            # AccuDraw 保持选中弯头时的轴向；换向后沿原轴读取精确数值。
            precision_direction = f5_placement_direction(
                frame, self._accudraw_direction_side)
            point = event.GetPoint()
            return ((point.x / scale - origin[0]) * precision_direction[0]
                    + (point.y / scale - origin[1]) * precision_direction[1])
        if event.GetCoordSource() in (
                DgnButtonEvent.eFROM_ElemSnap,
                DgnButtonEvent.eFROM_TentativePoint):
            point = event.GetPoint()
            return ((point.x / scale - origin[0]) * direction[0]
                    + (point.y / scale - origin[1]) * direction[1])
        anchor = _dpoint_from_mm(origin, scale)
        one_meter = _dpoint_from_mm(_frame_point(
            origin, 1000.0, 0.0, 0.0, direction), scale)
        viewport = event.GetViewport()
        anchor_view, meter_view, cursor_view = DPoint3d(), DPoint3d(), DPoint3d()
        viewport.ActiveToView(anchor_view, anchor)
        viewport.ActiveToView(meter_view, one_meter)
        viewport.ActiveToView(cursor_view, event.GetRawPoint())
        return height_from_view_drag(
            (anchor_view.x, anchor_view.y),
            (meter_view.x, meter_view.y),
            (cursor_view.x, cursor_view.y))

    def _plate_thickness(self):
        dn = support_dimensions(self.elbow_info['main_dn'])['trunnion_dn']
        return f4_end_plate_thickness(dn, self.panel._base_type.get()[0])

    def _minimum_height(self):
        dims = support_dimensions(self.elbow_info['main_dn'])
        return (self.elbow_info['outside_diameter_mm'] / 2.0
                + dims['trunnion_od'] + self._plate_thickness() + 20.0)

    def _OnDynamicFrame(self, event):
        first_frame = not self._first_frame_logged
        if first_frame:
            self._first_frame_logged = True
            _log('F5 dynamic frame begin: side=%s' %
                 self.panel._direction_side.get())
        try:
            length = max(self._minimum_height(),
                         min(20000.0, self._height_from_event(event)))
            frame = self.elbow_info['frame']
            side = self.panel._direction_side.get()
            direction = f5_placement_direction(frame, side)
            plate_t = self._plate_thickness()
            scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
            dims = support_dimensions(self.elbow_info['main_dn'])
            alignment = ('CENTER' if self.panel._alignment.get() == ALIGNMENT_TYPES[0]
                         else 'BOTTOM')
            offset = f4_alignment_offset(
                self.elbow_info['outside_diameter_mm'],
                dims['trunnion_od'], alignment)
            points = f5_axis_points(frame, length, plate_t, offset, side)
            radius = dims['trunnion_od'] / 2.0
            origin = points['origin_mm']
            tube_start = points['tube_start_mm']
            tube_end = points['tube_end_mm']
            outer_end = points['outer_end_mm']
            # 必须在临时重绘前读取事件；DoRedraw 后不再访问 event。
            moved = self._moved_from_pick(event)
            pick_released = not _left_mouse_button_is_down()
            self.panel.show_live_height(length)
            if pick_released:
                self._pick_button_released = True
            if self._pick_button_released and moved:
                self._accept_armed = True
            if first_frame:
                _log('F5 dynamic input ready: side=%s moved=%s' % (side, moved))
            lines = [(_dpoint_from_mm(origin, scale),
                      _dpoint_from_mm(outer_end, scale)),
                     (_dpoint_from_mm(tube_start, scale),
                      _dpoint_from_mm(tube_end, scale))]
            for sign in (-1.0, 1.0):
                side_start = _frame_point(tube_start, 0.0, sign * radius, 0.0,
                                          direction)
                side_end = _frame_point(tube_end, 0.0, sign * radius, 0.0,
                                        direction)
                lines.append((_dpoint_from_mm(side_start, scale),
                              _dpoint_from_mm(side_end, scale)))
                vertical_start = (tube_start[0], tube_start[1],
                                  tube_start[2] + sign * radius)
                vertical_end = (tube_end[0], tube_end[1],
                                tube_end[2] + sign * radius)
                lines.append((_dpoint_from_mm(vertical_start, scale),
                              _dpoint_from_mm(vertical_end, scale)))
            if plate_t > 0.0:
                plate_radius = (dims['trunnion_od'] + 25.0) / 2.0
                for sign in (-1.0, 1.0):
                    a = _frame_point(tube_end, 0.0, sign * plate_radius,
                                     0.0, direction)
                    b = _frame_point(outer_end, 0.0, sign * plate_radius,
                                     0.0, direction)
                    lines.append((_dpoint_from_mm(a, scale),
                                  _dpoint_from_mm(b, scale)))
                    vertical_a = (tube_end[0], tube_end[1],
                                  tube_end[2] + sign * plate_radius)
                    vertical_b = (outer_end[0], outer_end[1],
                                  outer_end[2] + sign * plate_radius)
                    lines.append((_dpoint_from_mm(vertical_a, scale),
                                  _dpoint_from_mm(vertical_b, scale)))
            redraw = RedrawElems()
            redraw.SetDynamicsViews(IViewManager.GetActiveViewSet(), event.GetViewport())
            redraw.SetDrawMode(eDRAW_MODE_TempDraw)
            redraw.SetDrawPurpose(DrawPurpose.eDynamics)
            drawn = 0
            frame_elements = []
            for start, end in lines:
                element = EditElementHandle()
                curve = ICurvePrimitive.CreateLine(DSegment3d(start, end))
                status = DraftingElementSchema.ToElement(
                    element, curve, None, ISessionMgr.ActiveDgnModelRef.Is3d(),
                    ISessionMgr.ActiveDgnModelRef)
                if _succeeded(status):
                    # DoRedraw 可能在回调返回后才消费句柄，不能让前几条线提前析构。
                    frame_elements.append(element)
                    redraw.DoRedraw(element)
                    drawn += 1
            if drawn == 0:
                raise RuntimeError('动态轮廓无法绘制。')
            if first_frame:
                _log('F5 dynamic frame drawn: side=%s lines=%d' % (
                    side, drawn))
            self._preview_frames.append(frame_elements)
            if len(self._preview_frames) > 3:
                self._preview_frames.pop(0)
            self._has_preview = True
        except Exception as error:
            self._has_preview = False
            self._accept_armed = False
            _log('length dynamics exception: %r' % error)
            self.panel.set_status('拉伸预览失败：%s' % error, True)

    def _OnDataButton(self, event):
        moved = self._moved_from_pick(event)
        if (not self._has_preview or not self._pick_button_released
                or not self._accept_armed or not moved):
            _log("height accept suppressed: preview=%s released=%s armed=%s "
                 "moved=%s source=%s" % (
                     self._has_preview, self._pick_button_released,
                     self._accept_armed, moved, event.GetButtonSource()))
            self.panel.set_status(
                "请先松开选取弯头的左键，移动光标预览长度，然后再左键确认。", True)
            return False
        try:
            height = self._height_from_event(event)
            height = max(self._minimum_height(), min(20000.0, height))
            _log("height accepted: H=%.3f source=%s" % (
                height, event.GetButtonSource()))
            self.panel.queue_height(self.elbow_info, height)
            return True
        except Exception as error:
            _log("height accept exception: %r" % error)
            self.panel.set_status("无法读取拉伸长度：%s" % error, True)
            return False

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.queue_cancel_height()
        return True

    def _OnRestartTool(self):
        if self.panel is not None and not self.panel._close_requested:
            self.panel.restart_selection()

    @staticmethod
    def InstallNewInstance(tool_id, panel, elbow_info, pick_view_position,
                           focus_accudraw=True):
        global _ACTIVE_PLACEMENT_TOOL
        _ACTIVE_PLACEMENT_TOOL = TrunnionHeightTool(
            tool_id, panel, elbow_info, pick_view_position)
        status = _ACTIVE_PLACEMENT_TOOL.InstallTool()
        if not _succeeded(status):
            raise RuntimeError("耳轴拉伸工具安装失败（状态：%s）。" % status)
        _ACTIVE_PLACEMENT_TOOL._start_drag(focus_accudraw)
        return _ACTIVE_PLACEMENT_TOOL


def main():
    global _ACTIVE_PANEL
    _enable_fault_logging()
    try:
        _ACTIVE_PANEL = TrunnionPanel()
        TrunnionPlacementTool.InstallNewInstance(0, _ACTIVE_PANEL, True)
    finally:
        _disable_fault_logging()


if __name__ == "__main__":
    main()
