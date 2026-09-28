# -*- coding: utf-8 -*-
"""Bentley OpenPlant Modeler 弯头耳轴合并工具（原 F2 / F2-HE / F4 / F5）。

在 OPM / MicroStation Python Editor 中直接运行本文件。面板最上面先选
「弯头方向 × 耳轴方向」得到四种型式之一，再在三维模型里点选一个已有的
OpenPlant 90° 弯头，沿对应方向拉伸确定高度 H 或长度 L，即可生成：

* 按表 1 自动选型的耳轴（竖直耳轴 / 水平耳轴）；
* 用弯头外包络真实布尔切出的耳轴鞍口；
* A 型底板（端板）、B 型底板（端板）或 C 型无板；
* 耳轴上的通气孔，以及可选的 PTFE 滑板覆面；
* 可勾选「附带弯头弧板（护板）」：同一个弯头上再生成一块弯头弧形垫板。

四种型式（顶层「弯头方向 + 耳轴方向」组合）分别对应原脚本：

* 竖直弯头 + 竖直耳轴 → ``F2-[竖直弯头的竖直耳轴].py``
* 水平弯头 + 竖直耳轴 → ``F2-[水平弯头的竖直耳轴].py``（F2-HE）
* 竖直弯头 + 水平耳轴 → ``F4-[竖直弯头的水平耳轴].py``
* 水平弯头 + 水平耳轴 → ``F5-[水平弯头的水平耳轴].py``

四种型式共用 EC 读取、几何原语、鞍口布尔与拉伸框架，只在弯头坐标系解析、
Builder、编号和拉伸工具上分型式；行为与四个原脚本逐项一致（含报错文案），
原脚本仍然保留、可单独运行。管道弯头与 **HVAC 圆风管弯头**
（``OpenPlant_3D.HVAC_ROUND_ELBOW``）同样都支持，编号按风管实际外径写
（如 ``F2-D450-10"-C1-500-A``）；矩形风管不支持。

勾选「附带弯头弧板（护板）」时，直接复用 ``弯头垫板.py``（贴弯头背弧的
弧形护板，覆盖 75°、周向 120°）：管径与弯头倍率按弯头实测自动反推，材料
沿用耳轴材料，清单自成一条 ``弯头垫板`` Assembly，与单独运行该插件一致。
"""

from __future__ import division

import ctypes
import faulthandler
import importlib
import math
import os
import re
import sys
import time
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
# 弯头坐标系与编号的纯逻辑库（原四个脚本共用的那个模块）。
GEOM_DIR = os.path.join(SCRIPT_DIR, '模块', '竖直弯头的竖直耳轴')
if not os.path.isdir(COMMON_DIR):
    COMMON_DIR = os.path.join(REPO_ROOT, '管道支吊架', '模块', '公共')
for _path in (REPO_ROOT, SCRIPT_DIR, COMMON_DIR, GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _boot_log(message):
    """启动阶段的面包屑（此时 _log 还没定义）：每次覆盖写，用来定位启动期崩溃。

    正常启动后本文件会留下「import: 完成」一行；若停在前面的某一步，就说明
    崩在那一步（面板与拉伸工具的日志分别在 弯头耳轴_debug_log / _fault.log）。
    """
    try:
        log_dir = os.path.join(SCRIPT_DIR, '模块', '日志')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, '弯头耳轴_启动.txt'),
                  'w', encoding='utf-8') as stream:
            stream.write('%s %s\n'
                         % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
    except Exception:
        pass


_boot_log('import: MSPy 与路径就绪')

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
_boot_log('import: 支吊架公共库就绪')

import elbow_selection_logic as _elbow_selection_logic

_elbow_selection_logic = importlib.reload(_elbow_selection_logic)
_boot_log('import: 纯逻辑库 elbow_selection_logic 就绪')
dimension_scale_to_mm = _elbow_selection_logic.dimension_scale_to_mm
elbow_frame_from_matrix = _elbow_selection_logic.elbow_frame_from_matrix
support_base_from_height = _elbow_selection_logic.support_base_from_height
height_from_view_drag = _elbow_selection_logic.height_from_view_drag
height_from_drag_z = _elbow_selection_logic.height_from_drag_z
moved_from_selection_view = _elbow_selection_logic.moved_from_selection_view
f2_number = _elbow_selection_logic.f2_number
resolve_elbow_dimensions = _elbow_selection_logic.resolve_elbow_dimensions
HVAC_NUMBER_PROPERTIES = _elbow_selection_logic.HVAC_NUMBER_PROPERTIES
horizontal_elbow_frame_from_matrix = _elbow_selection_logic.horizontal_elbow_frame_from_matrix
f4_number = _elbow_selection_logic.f4_number
f4_axis_points = _elbow_selection_logic.f4_axis_points
f4_pipe_axis_origin = _elbow_selection_logic.f4_pipe_axis_origin
f4_alignment_offset = _elbow_selection_logic.f4_alignment_offset
f4_end_plate_thickness = _elbow_selection_logic.f4_end_plate_thickness
f5_number = _elbow_selection_logic.f5_number
f5_axis_points = _elbow_selection_logic.f5_axis_points
f5_pipe_axis_origin = _elbow_selection_logic.f5_pipe_axis_origin
f5_placement_direction = _elbow_selection_logic.f5_placement_direction
f5_azimuth_deg = _elbow_selection_logic.f5_azimuth_deg


def _elbow_pad_module():
    """导入并返回 弯头垫板.py 模块（**首次真正要用时**才导入）。

    弯头垫板.py 是另一个入口脚本（自己会再刷一遍 bentley_ui、重排 sys.path）；
    放在启动阶段整份拉进本进程会让启动直接崩掉，因此改为延迟导入，并且把它
    的失败限制成「弧板不可用」——耳轴本体照旧。
    """
    global _pad
    if _pad is None:
        try:
            import 弯头垫板 as module
        except Exception as error:
            _log('import 弯头垫板 failed: %r' % (error,))
            raise ValueError(
                '弯头弧板插件（弯头垫板.py）无法载入：%s。可先只生成耳轴，'
                '或单独运行一次 弯头垫板.py 确认它能启动。' % (error,))
        _pad = module
    return _pad


# 弯头弧板（护板）复用既有插件的读弯头 / 反推倍率 / build_pad（见上）。
_pad = None
_boot_log('import: 弧板插件改为延迟导入')

# 四种型式共用一个调试日志，条目里带型式代号。
DEBUG_LOG = os.path.join(SCRIPT_DIR, '模块', '日志', '弯头耳轴_debug_log.txt')
# F5 型式的诊断日志（拉伸 / 换向期间看门狗）；与 F5 原脚本一致。
FAULT_LOG = os.path.join(SCRIPT_DIR, '模块', '日志', '弯头耳轴_fault.log')
_FAULT_STREAM = None

# F2 / F2-HE 的 PTFE 滑板覆面厚度（mm）。
PTFE_LINER_THICKNESS_MM = 3.0

# 逃生开关：CustomItemHost.ApplyCustomItem 在本机 MicroStation/OPM 版本上
# 偶发卡死 → access violation（与几何、清单数据无关，同参数可能这次成功、
# 下次卡死）。置 False 后几何照常生成、照常落图，只是这批耳轴不进公共清单。
# 遇到持续崩溃时把它改成 False 即可继续建模，之后可单独运行 支吊架清单导出。
ITEM_TYPE_ATTACH = True

# 各型式的清单口径（中文类型名 + ASCII 代号，只用于 ItemType 命名）。
# 四个 Builder 在写公共清单时引用自己那一组；型式表也用这同一组常量。
F2V_SUPPORT_TYPE = 'F2-[竖直弯头的竖直耳轴]'
F2V_SUPPORT_CODE = 'F2_VERTICAL_ELBOW_TRUNNION'
F2HE_SUPPORT_TYPE = 'F2-[水平弯头的竖直耳轴]'
F2HE_SUPPORT_CODE = 'F2_HORIZONTAL_ELBOW_TRUNNION'
F4_SUPPORT_TYPE = 'F4-[竖直弯头的水平耳轴]'
F4_SUPPORT_CODE = 'F4_VERTICAL_ELBOW_HORIZONTAL_TRUNNION'
F5_SUPPORT_TYPE = 'F5-[水平弯头的水平耳轴]'
F5_SUPPORT_CODE = 'F5_HORIZONTAL_ELBOW_HORIZONTAL_TRUNNION'

# 耳轴位置（对齐）选项。F4 与 F5 的「底平」后缀文字不同（FB1/FB2 vs FB），
# 两组标签各自保留原脚本文字，Builder 的校验与自己那一组比较。
ALIGNMENT_TYPES = ("相同中心线", "底平（FB1/FB2）")
F5_ALIGNMENT_TYPES = ("相同中心线", "底平（FB）")

# 当前在装的 Bentley 工具（点选 / 拉伸），四种型式共用一份。
_ACTIVE_PLACEMENT_TOOL = None
_ACTIVE_PANEL = None


# ---------------------------------------------------------------------------
# 共享区：四种型式逐字一致的常量与纯逻辑（原四份重复代码合为一份）
# ---------------------------------------------------------------------------

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

# 图片表 1 的逐档映射：主弯头 DN 上限、耳轴 DN、A 型方底板边长、底板厚度。
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

ELBOW_NUMBER_PROPERTIES = (
    "ANGLE", "NOMINAL_DIAMETER", "NOMINAL_DIAMETER_RUN_END",
    "OUTSIDE_DIAMETER", "WALL_THICKNESS", "LENGTH",
    "DESIGN_LENGTH_CENTER_TO_RUN_END",
    "DESIGN_LENGTH_CENTER_TO_OUTLET_END",
    "DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE",
    "DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE",
) + HVAC_NUMBER_PROPERTIES + tuple(
    "TRANSFORMATION_MATRIX.M%02d" % index for index in range(12)
)

ELBOW_TEXT_PROPERTIES = ("UNIT_OF_MEASURE", "COMPONENT_NAME", "NAME", "LINENUMBER")

def _log(message):
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
        with open(DEBUG_LOG, "a", encoding="utf-8") as stream:
            stream.write(str(message) + "\n")
    except Exception:
        pass

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

def _element_handle_by_id(element_id):
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError("取不到活动 DGN 模型。")
    handle = EditElementHandle(int(element_id), model_ref.GetDgnModel())
    return handle if handle.IsValid() else None

def support_dimensions(main_dn):
    """按表 1 返回耳轴 DN、外径、壁厚、方底板边长和板厚。"""
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

def _read_element_id(element_handle):
    for name in ("ElementId", "GetElementId"):
        try:
            value = getattr(element_handle, name)
            return int(value() if callable(value) else value)
        except Exception:
            continue
    return None

def _left_mouse_button_is_down():
    """只用物理按键状态判断选取点击是否已释放，不使用时间阈值。"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


# ---------------------------------------------------------------------------
# 型式专属：四种 Builder（鞍口、通气孔、板件与清单写入各按型式）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# F2：竖直弯头的竖直耳轴
# ---------------------------------------------------------------------------

class VerticalElbowTrunnionBuilder(object):
    """根据一个已存在的 OpenPlant 竖直弯头构造耳轴及底板。"""

    def __init__(self, height_h_mm, base_type, hollow_trunnion=True,
                 material_code='C1', wall_override_mm=None, ptfe=False):
        self.height_h_mm = float(height_h_mm)
        self.base_type = base_type
        self.hollow_trunnion = bool(hollow_trunnion)
        self.material_code = str(material_code).upper()
        self.wall_override_mm = (None if wall_override_mm is None
                                 else float(wall_override_mm))
        self.ptfe = bool(ptfe)
        self.number = ''

    def _validate(self):
        if self.height_h_mm <= 0.0:
            raise ValueError("高度 H 必须大于 0。")
        if self.base_type not in ("A 方形底板", "B 圆形底板", "C 无底板"):
            raise ValueError("未知底板类型。")
        if self.material_code not in _elbow_selection_logic.MATERIAL_CODES:
            raise ValueError("未知材料代码。")
        if self.ptfe and self.base_type == "C 无底板":
            raise ValueError("无底板时不能使用 PTFE 滑板附加项 F。")
        if self.wall_override_mm is not None and self.wall_override_mm <= 0.0:
            raise ValueError("指定的耳轴壁厚必须大于 0。")

    def create_from_elbow(self, elbow_info):
        self._validate()
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None or not model_ref.Is3d():
            raise RuntimeError("请在 OPM 三维模型中运行本工具。")

        scale = _uor_per_mm(model_ref)
        main_dn = elbow_info["main_dn"]
        main_od = elbow_info["outside_diameter_mm"]
        dims = support_dimensions(main_dn)
        trunnion_od = dims["trunnion_od"]
        trunnion_wall = (dims["trunnion_wall"] if self.wall_override_mm is None
                         else self.wall_override_mm)
        if trunnion_wall >= trunnion_od / 2.0:
            raise ValueError("耳轴壁厚必须小于耳轴半径。")
        plate_t = 0.0 if self.base_type == "C 无底板" else dims["plate_thickness"]
        liner_t = PTFE_LINER_THICKNESS_MM if self.ptfe else 0.0
        minimum_h = main_od / 2.0 + plate_t + liner_t
        if self.height_h_mm <= minimum_h:
            raise ValueError("高度 H 过小，应大于弯头外半径加底板厚度 %.1f mm。" % minimum_h)
        frame = elbow_info["frame"]
        placement = support_base_from_height(
            frame, self.height_h_mm, plate_t, liner_t
        )
        self.number = f2_number(
            main_dn, dims['trunnion_dn'], trunnion_wall,
            dims['trunnion_wall'], self.material_code,
            self.height_h_mm, self.base_type[0], ptfe=self.ptfe,
            main_label=elbow_info["main_label"])
        horizontal_direction = frame["horizontal_direction"]

        start = _dpoint_from_mm(frame["horizontal_port_mm"], scale)
        center = _dpoint_from_mm(frame["arc_center_mm"], scale)
        end = _dpoint_from_mm(frame["vertical_port_mm"], scale)
        tangent = _dvec_from_unit(horizontal_direction)

        # 1. 按所选弯头的真实端口坐标重建实心外包络，只作为鞍口刀具体。
        elbow_cutter = _elbow_outer_body(
            model_ref, start, center, end, tangent, main_od * scale / 2.0
        )

        # 2. 耳轴轴线通过竖直端中心，毛坯延伸至该中心，再由外包络切出鞍口。
        trunnion_bottom = _dpoint_from_mm(
            placement["trunnion_bottom_mm"], scale
        )
        trunnion_top = _dpoint_from_mm(placement["trunnion_top_mm"], scale)
        trunnion_body = _cylinder_body(
            model_ref, trunnion_bottom, trunnion_top,
            trunnion_od * scale / 2.0
        )
        _subtract(trunnion_body, elbow_cutter)

        if self.hollow_trunnion:
            inner_radius = (trunnion_od / 2.0 - trunnion_wall) * scale
            if inner_radius <= 0.0:
                raise ValueError("耳轴壁厚数据无效。")
            bottom_mm = placement["trunnion_bottom_mm"]
            top_mm = placement["trunnion_top_mm"]
            inner_start = _dpoint_from_mm(
                (bottom_mm[0], bottom_mm[1], bottom_mm[2] - 1.0), scale
            )
            inner_end = _dpoint_from_mm(
                (top_mm[0], top_mm[1], top_mm[2] + 1.0), scale
            )
            _subtract(trunnion_body, _cylinder_body(
                model_ref, inner_start, inner_end, inner_radius
            ))

        # 3. 图示 Ø6 横向通气孔，孔中心位于耳轴底端上方 20 mm。
        hole_z = (placement["plate_top_z_mm"]
                  + min(20.0, max(8.0, (self.height_h_mm - plate_t - liner_t) * 0.08)))
        hole_center = (placement["trunnion_bottom_mm"][0],
                       placement["trunnion_bottom_mm"][1], hole_z)
        hole_start = _dpoint_from_mm(_frame_point(
            hole_center, 0.0, -trunnion_od, 0.0, horizontal_direction
        ), scale)
        hole_end = _dpoint_from_mm(_frame_point(
            hole_center, 0.0, trunnion_od, 0.0, horizontal_direction
        ), scale)
        _subtract(trunnion_body, _cylinder_body(
            model_ref, hole_start, hole_end, 3.0 * scale
        ))

        bodies = [(trunnion_body, 3, "竖直耳轴")]

        # 4. 底板类型。B 型直径按图为耳轴外径 + 25 mm。
        if self.base_type == "A 方形底板":
            bodies.append((_box_body_in_frame(
                model_ref, placement["base_bottom_mm"],
                dims["plate_size"] / 2.0, plate_t,
                horizontal_direction, scale
            ), 4, "A 型方形底板"))
        elif self.base_type == "B 圆形底板":
            base_mm = placement["base_bottom_mm"]
            plate_start = _dpoint_from_mm(base_mm, scale)
            plate_end = _dpoint_from_mm(
                (base_mm[0], base_mm[1], base_mm[2] + plate_t), scale
            )
            bodies.append((_cylinder_body(
                model_ref, plate_start, plate_end,
                (trunnion_od + 25.0) * scale / 2.0
            ), 4, "B 型圆形底板"))

        if self.ptfe:
            liner_base = placement['liner_bottom_mm']
            if self.base_type == 'A 方形底板':
                liner_body = _box_body_in_frame(
                    model_ref, liner_base, dims['plate_size'] / 2.0,
                    liner_t, horizontal_direction, scale)
            else:
                liner_start = _dpoint_from_mm(liner_base, scale)
                liner_end = _dpoint_from_mm((
                    liner_base[0], liner_base[1], liner_base[2] + liner_t), scale)
                liner_body = _cylinder_body(
                    model_ref, liner_start, liner_end,
                    (trunnion_od + 25.0) * scale / 2.0)
            bodies.append((liner_body, 7, '3 mm 镜面不锈钢覆面'))

        # 所选弯头本身保持不变；新几何组成一个单元，附加公共支吊架 ItemType。
        elements = []
        for body, color, label in bodies:
            elements.append(_element_from_body(model_ref, body, color, label))
        cell = EditElementHandle()
        NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, F2V_SUPPORT_CODE, True, model_ref.GetDgnModel())
        for element in elements:
            status = NormalCellHeaderHandler.AddChildElement(cell, element)
            if not _succeeded(status):
                raise RuntimeError("耳轴构件加入单元失败（状态：%s）。" % status)
        status = NormalCellHeaderHandler.AddChildComplete(cell)
        if not _succeeded(status):
            raise RuntimeError("耳轴单元完成失败（状态：%s）。" % status)
        status = cell.AddToModel()
        if not _succeeded(status):
            raise RuntimeError("耳轴单元写入当前模型失败（状态：%s）。" % status)

        tube_length = placement['trunnion_top_mm'][2] - placement['trunnion_bottom_mm'][2]
        components = [{
            'code': 'TRUNNION_DN%d_W%s_%s_%s' % (
                dims['trunnion_dn'], str(trunnion_wall).replace('.', '_'),
                self.material_code, 'PIPE' if self.hollow_trunnion else 'SOLID'),
            'name': '竖直耳轴钢管' if self.hollow_trunnion else '竖直耳轴圆钢',
            'specification': 'DN%d Ø%g × %g mm，%s' % (
                dims['trunnion_dn'], trunnion_od, trunnion_wall,
                self.material_code),
            'length': tube_length, 'quantity': 1, 'unit': '件',
        }]
        if plate_t > 0.0:
            components.append({
                'code': 'BASE_%s_%s_T%s' % (
                    self.base_type[0],
                    str(dims['plate_size'] if self.base_type.startswith('A')
                        else trunnion_od + 25.0).replace('.', '_'),
                    str(plate_t).replace('.', '_')),
                'name': self.base_type,
                'specification': ('%g × %g × %g mm' % (
                    dims['plate_size'], dims['plate_size'], plate_t)
                    if self.base_type.startswith('A') else
                    'Ø%g × %g mm' % (trunnion_od + 25.0, plate_t)),
                'length': plate_t, 'quantity': 1, 'unit': '件',
            })
        if self.ptfe:
            liner_size = (dims['plate_size'] if self.base_type.startswith('A')
                          else trunnion_od + 25.0)
            components.append({
                'code': 'SS_LINER_%s_%s' % (
                    self.base_type[0], str(liner_size).replace('.', '_')),
                'name': '镜面不锈钢覆面',
                'specification': ('%g × %g × 3 mm' % (liner_size, liner_size)
                                  if self.base_type.startswith('A') else
                                  'Ø%g × 3 mm' % liner_size),
                'length': liner_t, 'quantity': 1, 'unit': '件',
            })
        try:
            if ITEM_TYPE_ATTACH:
                attached = psb.attach_components(
                    cell, support_type=F2V_SUPPORT_TYPE, support_code=F2V_SUPPORT_CODE,
                    assembly_tag=self.number,
                    assembly_spec='%s；%s；H %g mm；%s' % (
                        self.number, elbow_info["main_size_text"],
                        self.height_h_mm, self.base_type),
                    components=components,
                    pipe_number=elbow_info.get("pipe_number") or "")
            else:
                attached = len(components) + 1
                _log('attach skipped (ITEM_TYPE_ATTACH=False): %s' % self.number)
        except Exception as error:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项写入失败：%s。请勿重复建模。'
                % (cell.GetElementId(), error))
        if attached < len(components) + 1:
            _log('ItemType attach incomplete: %d/%d for %s' % (
                attached, len(components) + 1, self.number))
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项仅写入 %d/%d。请勿重复建模。'
                % (cell.GetElementId(), attached, len(components) + 1))

        _log("created from elbow %s %s H%.1f, trunnion DN%d, base=%s, number=%s, cell=%s" % (
            elbow_info["element_id"], elbow_info["main_size_text"],
            self.height_h_mm,
            dims["trunnion_dn"], self.base_type, self.number,
            cell.GetElementId()
        ))
        return [cell]

# ---------------------------------------------------------------------------
# F2-HE：水平弯头的竖直耳轴
# ---------------------------------------------------------------------------

class HorizontalElbowTrunnionBuilder(object):
    """根据一个已存在的 OpenPlant 水平弯头构造竖直耳轴及底板。"""

    def __init__(self, height_h_mm, base_type, hollow_trunnion=True,
                 material_code='C1', wall_override_mm=None, ptfe=False):
        self.height_h_mm = float(height_h_mm)
        self.base_type = base_type
        self.hollow_trunnion = bool(hollow_trunnion)
        self.material_code = str(material_code).upper()
        self.wall_override_mm = (None if wall_override_mm is None
                                 else float(wall_override_mm))
        self.ptfe = bool(ptfe)
        self.number = ''

    def _validate(self):
        if self.height_h_mm <= 0.0:
            raise ValueError("高度 H 必须大于 0。")
        if self.base_type not in ("A 方形底板", "B 圆形底板", "C 无底板"):
            raise ValueError("未知底板类型。")
        if self.material_code not in _elbow_selection_logic.MATERIAL_CODES:
            raise ValueError("未知材料代码。")
        if self.ptfe and self.base_type == "C 无底板":
            raise ValueError("无底板时不能使用 PTFE 滑板附加项 F。")
        if self.wall_override_mm is not None and self.wall_override_mm <= 0.0:
            raise ValueError("指定的耳轴壁厚必须大于 0。")

    def create_from_elbow(self, elbow_info):
        self._validate()
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None or not model_ref.Is3d():
            raise RuntimeError("请在 OPM 三维模型中运行本工具。")

        scale = _uor_per_mm(model_ref)
        main_dn = elbow_info["main_dn"]
        main_od = elbow_info["outside_diameter_mm"]
        dims = support_dimensions(main_dn)
        trunnion_od = dims["trunnion_od"]
        trunnion_wall = (dims["trunnion_wall"] if self.wall_override_mm is None
                         else self.wall_override_mm)
        if trunnion_wall >= trunnion_od / 2.0:
            raise ValueError("耳轴壁厚必须小于耳轴半径。")
        plate_t = 0.0 if self.base_type == "C 无底板" else dims["plate_thickness"]
        liner_t = PTFE_LINER_THICKNESS_MM if self.ptfe else 0.0
        minimum_h = main_od / 2.0 + plate_t + liner_t
        if self.height_h_mm <= minimum_h:
            raise ValueError("高度 H 过小，应大于弯头外半径加底板厚度 %.1f mm。" % minimum_h)
        frame = elbow_info["frame"]
        placement = support_base_from_height(
            frame, self.height_h_mm, plate_t, liner_t
        )
        self.number = f2_number(
            main_dn, dims['trunnion_dn'], trunnion_wall,
            dims['trunnion_wall'], self.material_code,
            self.height_h_mm, self.base_type[0], ptfe=self.ptfe,
            horizontal_elbow=True, main_label=elbow_info["main_label"])
        horizontal_direction = frame["horizontal_direction"]

        start = _dpoint_from_mm(frame["run_port_mm"], scale)
        center = _dpoint_from_mm(frame["arc_center_mm"], scale)
        end = _dpoint_from_mm(frame["outlet_port_mm"], scale)
        tangent = _dvec_from_unit(frame["axis_x"])

        # 1. 按所选弯头的真实端口坐标重建实心外包络，只作为鞍口刀具体。
        elbow_cutter = _elbow_outer_body(
            model_ref, start, center, end, tangent, main_od * scale / 2.0
        )

        # 2. 耳轴轴线通过水平弯头弧线中点，毛坯延伸至主管中心线，再切出鞍口。
        trunnion_bottom = _dpoint_from_mm(
            placement["trunnion_bottom_mm"], scale
        )
        trunnion_top = _dpoint_from_mm(placement["trunnion_top_mm"], scale)
        trunnion_body = _cylinder_body(
            model_ref, trunnion_bottom, trunnion_top,
            trunnion_od * scale / 2.0
        )
        _subtract(trunnion_body, elbow_cutter)

        if self.hollow_trunnion:
            inner_radius = (trunnion_od / 2.0 - trunnion_wall) * scale
            if inner_radius <= 0.0:
                raise ValueError("耳轴壁厚数据无效。")
            bottom_mm = placement["trunnion_bottom_mm"]
            top_mm = placement["trunnion_top_mm"]
            inner_start = _dpoint_from_mm(
                (bottom_mm[0], bottom_mm[1], bottom_mm[2] - 1.0), scale
            )
            inner_end = _dpoint_from_mm(
                (top_mm[0], top_mm[1], top_mm[2] + 1.0), scale
            )
            _subtract(trunnion_body, _cylinder_body(
                model_ref, inner_start, inner_end, inner_radius
            ))

        # 3. 图示 Ø6 横向通气孔，孔中心位于耳轴底端上方 20 mm。
        hole_z = (placement["plate_top_z_mm"]
                  + min(20.0, max(8.0, (self.height_h_mm - plate_t - liner_t) * 0.08)))
        hole_center = (placement["trunnion_bottom_mm"][0],
                       placement["trunnion_bottom_mm"][1], hole_z)
        hole_start = _dpoint_from_mm(_frame_point(
            hole_center, 0.0, -trunnion_od, 0.0, horizontal_direction
        ), scale)
        hole_end = _dpoint_from_mm(_frame_point(
            hole_center, 0.0, trunnion_od, 0.0, horizontal_direction
        ), scale)
        _subtract(trunnion_body, _cylinder_body(
            model_ref, hole_start, hole_end, 3.0 * scale
        ))

        bodies = [(trunnion_body, 3, "竖直耳轴")]

        # 4. 底板类型。B 型直径按图为耳轴外径 + 25 mm。
        if self.base_type == "A 方形底板":
            bodies.append((_box_body_in_frame(
                model_ref, placement["base_bottom_mm"],
                dims["plate_size"] / 2.0, plate_t,
                horizontal_direction, scale
            ), 4, "A 型方形底板"))
        elif self.base_type == "B 圆形底板":
            base_mm = placement["base_bottom_mm"]
            plate_start = _dpoint_from_mm(base_mm, scale)
            plate_end = _dpoint_from_mm(
                (base_mm[0], base_mm[1], base_mm[2] + plate_t), scale
            )
            bodies.append((_cylinder_body(
                model_ref, plate_start, plate_end,
                (trunnion_od + 25.0) * scale / 2.0
            ), 4, "B 型圆形底板"))

        if self.ptfe:
            liner_base = placement['liner_bottom_mm']
            if self.base_type == 'A 方形底板':
                liner_body = _box_body_in_frame(
                    model_ref, liner_base, dims['plate_size'] / 2.0,
                    liner_t, horizontal_direction, scale)
            else:
                liner_start = _dpoint_from_mm(liner_base, scale)
                liner_end = _dpoint_from_mm((
                    liner_base[0], liner_base[1], liner_base[2] + liner_t), scale)
                liner_body = _cylinder_body(
                    model_ref, liner_start, liner_end,
                    (trunnion_od + 25.0) * scale / 2.0)
            bodies.append((liner_body, 7, '3 mm 镜面不锈钢覆面'))

        # 所选弯头本身保持不变；新几何组成一个单元，附加公共支吊架 ItemType。
        elements = []
        for body, color, label in bodies:
            elements.append(_element_from_body(model_ref, body, color, label))
        cell = EditElementHandle()
        NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, F2HE_SUPPORT_CODE, True, model_ref.GetDgnModel())
        for element in elements:
            status = NormalCellHeaderHandler.AddChildElement(cell, element)
            if not _succeeded(status):
                raise RuntimeError("耳轴构件加入单元失败（状态：%s）。" % status)
        status = NormalCellHeaderHandler.AddChildComplete(cell)
        if not _succeeded(status):
            raise RuntimeError("耳轴单元完成失败（状态：%s）。" % status)
        status = cell.AddToModel()
        if not _succeeded(status):
            raise RuntimeError("耳轴单元写入当前模型失败（状态：%s）。" % status)

        tube_length = placement['trunnion_top_mm'][2] - placement['trunnion_bottom_mm'][2]
        components = [{
            'code': 'TRUNNION_DN%d_W%s_%s_%s' % (
                dims['trunnion_dn'], str(trunnion_wall).replace('.', '_'),
                self.material_code, 'PIPE' if self.hollow_trunnion else 'SOLID'),
            'name': '竖直耳轴钢管' if self.hollow_trunnion else '竖直耳轴圆钢',
            'specification': 'DN%d Ø%g × %g mm，%s' % (
                dims['trunnion_dn'], trunnion_od, trunnion_wall,
                self.material_code),
            'length': tube_length, 'quantity': 1, 'unit': '件',
        }]
        if plate_t > 0.0:
            components.append({
                'code': 'BASE_%s_%s_T%s' % (
                    self.base_type[0],
                    str(dims['plate_size'] if self.base_type.startswith('A')
                        else trunnion_od + 25.0).replace('.', '_'),
                    str(plate_t).replace('.', '_')),
                'name': self.base_type,
                'specification': ('%g × %g × %g mm' % (
                    dims['plate_size'], dims['plate_size'], plate_t)
                    if self.base_type.startswith('A') else
                    'Ø%g × %g mm' % (trunnion_od + 25.0, plate_t)),
                'length': plate_t, 'quantity': 1, 'unit': '件',
            })
        if self.ptfe:
            liner_size = (dims['plate_size'] if self.base_type.startswith('A')
                          else trunnion_od + 25.0)
            components.append({
                'code': 'SS_LINER_%s_%s' % (
                    self.base_type[0], str(liner_size).replace('.', '_')),
                'name': '镜面不锈钢覆面',
                'specification': ('%g × %g × 3 mm' % (liner_size, liner_size)
                                  if self.base_type.startswith('A') else
                                  'Ø%g × 3 mm' % liner_size),
                'length': liner_t, 'quantity': 1, 'unit': '件',
            })
        try:
            if ITEM_TYPE_ATTACH:
                attached = psb.attach_components(
                    cell, support_type=F2HE_SUPPORT_TYPE, support_code=F2HE_SUPPORT_CODE,
                    assembly_tag=self.number,
                    assembly_spec='%s；%s；H %g mm；%s' % (
                        self.number, elbow_info["main_size_text"],
                        self.height_h_mm, self.base_type),
                    components=components,
                    pipe_number=elbow_info.get("pipe_number") or "")
            else:
                attached = len(components) + 1
                _log('attach skipped (ITEM_TYPE_ATTACH=False): %s' % self.number)
        except Exception as error:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项写入失败：%s。请勿重复建模。'
                % (cell.GetElementId(), error))
        if attached < len(components) + 1:
            _log('ItemType attach incomplete: %d/%d for %s' % (
                attached, len(components) + 1, self.number))
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项仅写入 %d/%d。请勿重复建模。'
                % (cell.GetElementId(), attached, len(components) + 1))

        _log("created from elbow %s %s H%.1f, trunnion DN%d, base=%s, number=%s, cell=%s" % (
            elbow_info["element_id"], elbow_info["main_size_text"],
            self.height_h_mm,
            dims["trunnion_dn"], self.base_type, self.number,
            cell.GetElementId()
        ))
        return [cell]

# ---------------------------------------------------------------------------
# F4：竖直弯头的水平耳轴
# ---------------------------------------------------------------------------

class F4HorizontalTrunnionBuilder(object):
    """F4：可选同中心线或底平；底平标 FB1/FB2。"""

    def __init__(self, length_l_mm, end_plate_type, alignment_type,
                 hollow_trunnion=True, material_code='C1',
                 wall_override_mm=None):
        self.length_l_mm = float(length_l_mm)
        self.end_plate_type = str(end_plate_type)[0]
        self.alignment_type = alignment_type
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
        points = f4_axis_points(frame, self.length_l_mm, plate_t, offset)
        direction = frame['horizontal_direction']
        self.number = f4_number(main_dn, dims['trunnion_dn'], wall,
                                dims['trunnion_wall'], self.material_code,
                                self.length_l_mm, self.end_plate_type,
                                frame['flat_bend_code'] if alignment == 'BOTTOM'
                                else '', main_label=elbow_info['main_label'])
        _log('F4 build: elbow=%s alignment=%s offset=%.3f origin=%s '
             'tube_start=%s tube_end=%s L=%.3f' % (
                 elbow_info['element_id'], alignment, offset,
                 points['origin_mm'], points['tube_start_mm'],
                 points['tube_end_mm'], self.length_l_mm))

        # 重建选中弯头的实心外包络作为鞍口刀具，保持主管原件不变。
        _log('F4 kernel: create elbow cutter')
        cutter = _elbow_outer_body(
            model_ref,
            _dpoint_from_mm(frame['horizontal_port_mm'], scale),
            _dpoint_from_mm(frame['arc_center_mm'], scale),
            _dpoint_from_mm(frame['vertical_port_mm'], scale),
            _dvec_from_unit(direction), main_od * scale / 2.0)

        _log('F4 kernel: create tube')
        tube_start = _dpoint_from_mm(points['tube_start_mm'], scale)
        tube_end = _dpoint_from_mm(points['tube_end_mm'], scale)
        tube = _cylinder_body(model_ref, tube_start, tube_end,
                              trunnion_od * scale / 2.0)
        _log('F4 kernel: subtract elbow cutter')
        _subtract(tube, cutter)
        if self.hollow_trunnion:
            inner_radius = (trunnion_od / 2.0 - wall) * scale
            bore_start = _dpoint_from_mm(_frame_point(
                points['tube_start_mm'], -1.0, 0.0, 0.0, direction), scale)
            bore_end = _dpoint_from_mm(_frame_point(
                points['tube_end_mm'], 1.0, 0.0, 0.0, direction), scale)
            _log('F4 kernel: subtract bore')
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
        _log('F4 kernel: subtract vent hole')
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
            cell, F4_SUPPORT_CODE, True, model_ref.GetDgnModel())
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
            'code': 'F4_PIPE_DN%d_W%s_%s' % (
                dims['trunnion_dn'], str(wall).replace('.', '_'), self.material_code),
            'name': '水平耳轴钢管' if self.hollow_trunnion else '水平耳轴圆钢',
            'specification': 'DN%d Ø%g × %g mm，%s' % (
                dims['trunnion_dn'], trunnion_od, wall, self.material_code),
            'length': points['tube_length_mm'],
            'quantity': 1, 'unit': '件',
        }]
        if plate_t > 0.0:
            components.append({
                'code': 'F4_END_%s_DN%d_T%g' % (
                    self.end_plate_type, dims['trunnion_dn'], plate_t),
                'name': self.end_plate_type + ' 型端板',
                'specification': 'Ø%g × %g mm' % (trunnion_od + 25.0, plate_t),
                'length': plate_t, 'quantity': 1, 'unit': '件',
            })
        try:
            if ITEM_TYPE_ATTACH:
                attached = psb.attach_components(
                    cell, support_type=F4_SUPPORT_TYPE, support_code=F4_SUPPORT_CODE,
                    assembly_tag=self.number,
                    assembly_spec='%s；%s；L %g mm；端板 %s' % (
                        self.number, elbow_info["main_size_text"],
                        self.length_l_mm, self.end_plate_type),
                    components=components,
                    pipe_number=elbow_info.get('pipe_number') or '')
            else:
                attached = len(components) + 1
                _log('attach skipped (ITEM_TYPE_ATTACH=False): %s' % self.number)
        except Exception as error:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项写入失败：%s。请勿重复建模。'
                % (cell.GetElementId(), error))
        if attached < len(components) + 1:
            raise AttachmentIncompleteError(
                '耳轴单元 %s 已生成，但附加项仅写入 %d/%d。请勿重复建模。'
                % (cell.GetElementId(), attached, len(components) + 1))
        _log('created F4 from elbow %s: %s, cell=%s' % (
            elbow_info['element_id'], self.number, cell.GetElementId()))
        return [cell]

# ---------------------------------------------------------------------------
# F5：水平弯头的水平耳轴
# ---------------------------------------------------------------------------

class F5HorizontalTrunnionBuilder(object):
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
        if self.alignment_type not in F5_ALIGNMENT_TYPES:
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
        alignment = ('CENTER' if self.alignment_type == F5_ALIGNMENT_TYPES[0]
                     else 'BOTTOM')
        offset = f4_alignment_offset(main_od, trunnion_od, alignment)
        points = f5_axis_points(frame, self.length_l_mm, plate_t, offset,
                                self.direction_side)
        direction = f5_placement_direction(frame, self.direction_side)
        self.number = f5_number(main_dn, dims['trunnion_dn'], wall,
                                dims['trunnion_wall'], self.material_code,
                                self.length_l_mm, self.end_plate_type,
                                f5_azimuth_deg(direction), alignment == 'BOTTOM',
                                main_label=elbow_info['main_label'])
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
            cell, F5_SUPPORT_CODE, True, model_ref.GetDgnModel())
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
            if ITEM_TYPE_ATTACH:
                attached = psb.attach_components(
                    cell, support_type=F5_SUPPORT_TYPE, support_code=F5_SUPPORT_CODE,
                    assembly_tag=self.number,
                    assembly_spec='%s；%s；L %g mm；端板 %s' % (
                        self.number, elbow_info["main_size_text"],
                        self.length_l_mm, self.end_plate_type),
                    components=components,
                    pipe_number=elbow_info.get('pipe_number') or '')
            else:
                attached = len(components) + 1
                _log('attach skipped (ITEM_TYPE_ATTACH=False): %s' % self.number)
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


# ---------------------------------------------------------------------------
# F5 型式专用：拉伸 / 换向期间的诊断日志看门狗
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 型式专属：三种拉伸工具
#
# F2 与 F2-HE 共用同一个（原脚本里两者逐字一致），F4、F5 各自一份。
# ---------------------------------------------------------------------------

class F2FamilyHeightTool(DgnPrimitiveTool):
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

    def _moved_from_pick(self, event):
        point = event.GetViewPoint()
        return moved_from_selection_view(
            self._pick_view_position, event.GetViewNum(),
            (point.x, point.y))

    def _GetToolName(self, name):
        return WString("DragVerticalTrunnionHeight")

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)

    def _start_drag(self):
        """在 InstallTool 返回后启动；此时原选取事件已经消费完毕。"""
        self._BeginDynamics()
        if not self.GetDynamicsStarted():
            raise RuntimeError("Bentley 动态绘图未启动。")
        try:
            model_ref = ISessionMgr.ActiveDgnModelRef
            frame = self.elbow_info["frame"]
            horizontal = frame["horizontal_port_mm"]
            vertical = frame["vertical_port_mm"]
            anchor = _dpoint_from_mm(
                (vertical[0], vertical[1], horizontal[2]),
                _uor_per_mm(model_ref))
            # 显示 AccuDraw 罗盘并把 X 轴设为向下的世界 Z 方向。
            # 未捕捉时按视图投影拉伸；捕捉或精确输入时按调整后的 Z 标高计算。
            accu_draw = AccuDraw.GetInstance()
            accu_draw.Activate()
            origin_status = accu_draw.SetContext(
                AccuDrawFlags.eACCUDRAW_SetOrigin, anchor)
            axis_status = accu_draw.SetContext(
                AccuDrawFlags.eACCUDRAW_SetXAxis, None,
                DVec3d.From(0.0, 0.0, -1.0))
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetFocus)
            if not _succeeded(origin_status) or not _succeeded(axis_status):
                _log("AccuDraw context status: origin=%s axis=%s" % (
                    origin_status, axis_status))
        except Exception as error:
            _log("AccuDraw vertical context exception: %r" % error)

    def _height_from_event(self, event):
        model_ref = ISessionMgr.ActiveDgnModelRef
        scale = _uor_per_mm(model_ref)
        frame = self.elbow_info["frame"]
        horizontal_z = frame["horizontal_port_mm"][2]
        if event.GetCoordSource() in (
                DgnButtonEvent.eFROM_Precision,
                DgnButtonEvent.eFROM_ElemSnap,
                DgnButtonEvent.eFROM_TentativePoint):
            return height_from_drag_z(horizontal_z, event.GetPoint().z, scale)
        vertical = frame["vertical_port_mm"]
        anchor = _dpoint_from_mm(
            (vertical[0], vertical[1], horizontal_z), scale)
        down = _dpoint_from_mm(
            (vertical[0], vertical[1], horizontal_z - 1000.0), scale)
        viewport = event.GetViewport()
        anchor_view, down_view, cursor_view = DPoint3d(), DPoint3d(), DPoint3d()
        viewport.ActiveToView(anchor_view, anchor)
        viewport.ActiveToView(down_view, down)
        viewport.ActiveToView(cursor_view, event.GetRawPoint())
        return height_from_view_drag(
            (anchor_view.x, anchor_view.y),
            (down_view.x, down_view.y),
            (cursor_view.x, cursor_view.y))

    def _plate_thickness(self):
        if self.panel._base_type.get() == "C 无底板":
            return 0.0
        return support_dimensions(self.elbow_info["main_dn"])["plate_thickness"]

    def _liner_thickness(self):
        if self.panel._ptfe.get() and self.panel._base_type.get() != 'C 无底板':
            return PTFE_LINER_THICKNESS_MM
        return 0.0

    def _minimum_height(self):
        return max(50.0, self.elbow_info["outside_diameter_mm"] / 2.0
                   + self._plate_thickness() + self._liner_thickness() + 1.0)

    def _OnDynamicFrame(self, event):
        try:
            height = self._height_from_event(event)
            height = max(self._minimum_height(), min(20000.0, height))
            model_ref = ISessionMgr.ActiveDgnModelRef
            scale = _uor_per_mm(model_ref)
            frame = self.elbow_info["frame"]
            horizontal = frame["horizontal_port_mm"]
            vertical = frame["vertical_port_mm"]
            plate_t = self._plate_thickness()
            liner_t = self._liner_thickness()
            placement = support_base_from_height(frame, height, plate_t, liner_t)
            top = _dpoint_from_mm(vertical, scale)
            tube_bottom_mm = placement["trunnion_bottom_mm"]
            bottom = _dpoint_from_mm(tube_bottom_mm, scale)
            # 动态阶段画耳轴轮廓与 H 尺寸线，避免每帧执行实体布尔运算。
            dims = support_dimensions(self.elbow_info["main_dn"])
            radius = dims["trunnion_od"] / 2.0
            direction = frame["horizontal_direction"]
            normal_xy = (-direction[1], direction[0])
            shaft_top_z = vertical[2] - self.elbow_info["outside_diameter_mm"] / 2.0
            side_lines = []
            for sign in (-1.0, 1.0):
                side_x = vertical[0] + sign * normal_xy[0] * radius
                side_y = vertical[1] + sign * normal_xy[1] * radius
                side_lines.append((
                    _dpoint_from_mm((side_x, side_y, shaft_top_z), scale),
                    _dpoint_from_mm((side_x, side_y, tube_bottom_mm[2]), scale)))
            base_edge = (side_lines[0][1], side_lines[1][1])
            preview_lines = [(top, bottom), base_edge]
            preview_lines.extend(side_lines)
            if plate_t > 0.0:
                base_type = self.panel._base_type.get()
                plate_radius = (dims["plate_size"] / 2.0 if base_type == "A 方形底板"
                                else (dims["trunnion_od"] + 25.0) / 2.0)
                plate_corners = []
                for z in (placement["base_bottom_mm"][2],
                          placement["plate_top_z_mm"]):
                    plate_corners.append(tuple(_dpoint_from_mm((
                        vertical[0] + sign * normal_xy[0] * plate_radius,
                        vertical[1] + sign * normal_xy[1] * plate_radius,
                        z), scale) for sign in (-1.0, 1.0)))
                preview_lines.extend((plate_corners[0], plate_corners[1],
                                      (plate_corners[0][0], plate_corners[1][0]),
                                      (plate_corners[0][1], plate_corners[1][1])))
                if liner_t > 0.0:
                    liner_bottom = tuple(_dpoint_from_mm((
                        vertical[0] + sign * normal_xy[0] * plate_radius,
                        vertical[1] + sign * normal_xy[1] * plate_radius,
                        placement['liner_bottom_mm'][2]), scale)
                        for sign in (-1.0, 1.0))
                    preview_lines.extend((liner_bottom,
                                          (liner_bottom[0], plate_corners[0][0]),
                                          (liner_bottom[1], plate_corners[0][1])))
            dimension_top = _dpoint_from_mm(
                (horizontal[0], horizontal[1], horizontal[2]), scale)
            dimension_bottom = _dpoint_from_mm(
                (horizontal[0], horizontal[1], horizontal[2] - height), scale)
            preview_lines.append((dimension_top, dimension_bottom))
            redraw = RedrawElems()
            redraw.SetDynamicsViews(IViewManager.GetActiveViewSet(), event.GetViewport())
            redraw.SetDrawMode(eDRAW_MODE_TempDraw)
            redraw.SetDrawPurpose(DrawPurpose.eDynamics)
            drawn = 0
            for start, end in preview_lines:
                element = EditElementHandle()
                curve = ICurvePrimitive.CreateLine(DSegment3d(start, end))
                status = DraftingElementSchema.ToElement(
                    element, curve, None, model_ref.Is3d(), model_ref)
                if _succeeded(status):
                    redraw.DoRedraw(element)
                    drawn += 1
            if drawn == 0:
                raise RuntimeError("动态轮廓无法绘制。")
            self._has_preview = True
            self.panel.show_live_height(height)
            pick_released = not _left_mouse_button_is_down()
            if pick_released:
                self._pick_button_released = True
            if self._pick_button_released and self._moved_from_pick(event):
                self._accept_armed = True
        except Exception as error:
            _log("height dynamics exception: %r" % error)
            self.panel.set_status("拉伸预览失败：%s" % error, True)

    def _OnDataButton(self, event):
        moved = self._moved_from_pick(event)
        if (not self._has_preview or not self._pick_button_released
                or not self._accept_armed or not moved):
            _log("height accept suppressed: preview=%s released=%s armed=%s "
                 "moved=%s source=%s" % (
                     self._has_preview, self._pick_button_released,
                     self._accept_armed, moved, event.GetButtonSource()))
            self.panel.set_status(
                "请先松开选取弯头的左键，移动光标预览高度，然后再左键确认。", True)
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
            self.panel.set_status("无法读取拉伸高度：%s" % error, True)
            return False

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.queue_cancel_height()
        return True

    def _OnRestartTool(self):
        if self.panel is not None and not self.panel._close_requested:
            self.panel.restart_selection()

    @staticmethod
    def InstallNewInstance(tool_id, panel, elbow_info, pick_view_position):
        global _ACTIVE_PLACEMENT_TOOL
        _ACTIVE_PLACEMENT_TOOL = F2FamilyHeightTool(
            tool_id, panel, elbow_info, pick_view_position)
        status = _ACTIVE_PLACEMENT_TOOL.InstallTool()
        if not _succeeded(status):
            raise RuntimeError("耳轴拉伸工具安装失败（状态：%s）。" % status)
        _ACTIVE_PLACEMENT_TOOL._start_drag()
        return _ACTIVE_PLACEMENT_TOOL

class F4HeightTool(DgnPrimitiveTool):
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

    def _start_drag(self):
        """选取数据点结束后启动水平拉伸及 AccuDraw。"""
        self._BeginDynamics()
        if not self.GetDynamicsStarted():
            raise RuntimeError('Bentley 动态绘图未启动。')
        try:
            frame = self.elbow_info['frame']
            scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
            anchor = _dpoint_from_mm(f4_pipe_axis_origin(frame), scale)
            direction = frame['horizontal_direction']
            accu_draw = AccuDraw.GetInstance()
            accu_draw.Activate()
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetOrigin, anchor)
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetXAxis, None,
                                 _dvec_from_unit(direction))
            accu_draw.SetContext(AccuDrawFlags.eACCUDRAW_SetFocus)
        except Exception as error:
            _log('AccuDraw horizontal context exception: %r' % error)

    def _height_from_event(self, event):
        scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
        frame = self.elbow_info['frame']
        origin = f4_pipe_axis_origin(frame)
        direction = frame['horizontal_direction']
        if event.GetCoordSource() in (
                DgnButtonEvent.eFROM_Precision,
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
        try:
            length = max(self._minimum_height(),
                         min(20000.0, self._height_from_event(event)))
            frame = self.elbow_info['frame']
            direction = frame['horizontal_direction']
            plate_t = self._plate_thickness()
            scale = _uor_per_mm(ISessionMgr.ActiveDgnModelRef)
            dims = support_dimensions(self.elbow_info['main_dn'])
            alignment = ('CENTER' if self.panel._alignment.get() == ALIGNMENT_TYPES[0]
                         else 'BOTTOM')
            offset = f4_alignment_offset(
                self.elbow_info['outside_diameter_mm'],
                dims['trunnion_od'], alignment)
            points = f4_axis_points(frame, length, plate_t, offset)
            radius = dims['trunnion_od'] / 2.0
            origin = points['origin_mm']
            tube_start = points['tube_start_mm']
            tube_end = points['tube_end_mm']
            outer_end = points['outer_end_mm']
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
            for start, end in lines:
                element = EditElementHandle()
                curve = ICurvePrimitive.CreateLine(DSegment3d(start, end))
                status = DraftingElementSchema.ToElement(
                    element, curve, None, ISessionMgr.ActiveDgnModelRef.Is3d(),
                    ISessionMgr.ActiveDgnModelRef)
                if _succeeded(status):
                    redraw.DoRedraw(element)
                    drawn += 1
            if drawn == 0:
                raise RuntimeError('动态轮廓无法绘制。')
            self._has_preview = True
            self.panel.show_live_height(length)
            if not _left_mouse_button_is_down():
                self._pick_button_released = True
            if self._pick_button_released and self._moved_from_pick(event):
                self._accept_armed = True
        except Exception as error:
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
    def InstallNewInstance(tool_id, panel, elbow_info, pick_view_position):
        global _ACTIVE_PLACEMENT_TOOL
        _ACTIVE_PLACEMENT_TOOL = F4HeightTool(
            tool_id, panel, elbow_info, pick_view_position)
        status = _ACTIVE_PLACEMENT_TOOL.InstallTool()
        if not _succeeded(status):
            raise RuntimeError("耳轴拉伸工具安装失败（状态：%s）。" % status)
        _ACTIVE_PLACEMENT_TOOL._start_drag()
        return _ACTIVE_PLACEMENT_TOOL

class F5HeightTool(DgnPrimitiveTool):
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
        _ACTIVE_PLACEMENT_TOOL = F5HeightTool(
            tool_id, panel, elbow_info, pick_view_position)
        status = _ACTIVE_PLACEMENT_TOOL.InstallTool()
        if not _succeeded(status):
            raise RuntimeError("耳轴拉伸工具安装失败（状态：%s）。" % status)
        _ACTIVE_PLACEMENT_TOOL._start_drag(focus_accudraw)
        return _ACTIVE_PLACEMENT_TOOL


# ---------------------------------------------------------------------------
# 共享：点选弯头的原生工具（工具名由面板按型式提供）
# ---------------------------------------------------------------------------

class TrunnionPlacementTool(DgnElementSetTool):
    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.panel = panel
        self.m_self = self
        self._located_id = None

    def _GetToolName(self, name):
        # 工具名随型式变化，由面板提供，避免一个工具类写死四种名字。
        label = getattr(self.panel, 'tool_name', None)
        return WString(label or "SelectElbowTrunnion")

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


# ---------------------------------------------------------------------------
# 型式表、统一的弯头读取、统一面板、弯头弧板接入与入口
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 型式配置：四种弯头耳轴组合（原 F2 / F2-HE / F4 / F5 四个独立脚本）
#
# 顶层「弯头方向 × 耳轴方向」两个下拉组合出以下四种型式；参数区按型式切换
# 可见性与标签，点选 / 拉伸 / 建模各自走型式的读取器、Builder 与拉伸工具，
# 四者共用本文件前半部分的 EC 读取、几何原语与鞍口布尔逻辑。
# ---------------------------------------------------------------------------


class _Variant(object):
    """一种弯头耳轴型式的全部差异点（其余实现四型式共用）。"""

    def __init__(self, key, elbow_label, trunnion_label, support_type,
                 support_code, title, hint, tool_name, number_prefix,
                 number_family, frame_kind, allow_downward, base_types,
                 alignment_types, extent_label, extent_name, plate_label,
                 drag_status, done_status):
        self.key = key
        self.elbow_label = elbow_label
        self.trunnion_label = trunnion_label
        self.support_type = support_type
        self.support_code = support_code
        self.title = title
        self.hint = hint
        self.tool_name = tool_name
        self.number_prefix = number_prefix
        self.number_family = number_family
        self.frame_kind = frame_kind
        self.allow_downward = allow_downward
        self.base_types = base_types
        self.alignment_types = alignment_types
        self.extent_label = extent_label
        self.extent_name = extent_name
        self.plate_label = plate_label
        self.drag_status = drag_status
        self.done_status = done_status
        # 下方装配：Builder 与拉伸工具类按型式回填。
        self.builder_cls = None
        self.height_tool = None

    @property
    def uses_ptfe(self):
        return self.number_family == 'f2'

    @property
    def uses_alignment(self):
        return self.alignment_types is not None

    @property
    def uses_direction(self):
        return self.number_family == 'f5'


ELBOW_LABELS = ("竖直弯头", "水平弯头")
TRUNNION_LABELS = ("竖直耳轴", "水平耳轴")

# 耳轴位置选项见文件开头：ALIGNMENT_TYPES（F4）与 F5_ALIGNMENT_TYPES（F5）；
# 复制过来的拉伸工具只比较 [0]（相同中心线），两组下标语义一致。

VARIANTS = (
    _Variant(
        key='f2v', elbow_label=ELBOW_LABELS[0], trunnion_label=TRUNNION_LABELS[0],
        support_type=F2V_SUPPORT_TYPE,
        support_code=F2V_SUPPORT_CODE,
        title='F2 · 竖直弯头的竖直耳轴',
        hint=("点选竖直弯头主单元后自动进入拉伸，移动光标预览耳轴。"
              "H 从弯头水平端中心线量到最低点：有底板取板底，F 取覆面底，无底板取管底。"),
        tool_name='SelectVerticalElbowForTrunnion',
        number_prefix='F2', number_family='f2',
        frame_kind='vertical_elbow', allow_downward=False,
        base_types=("A 方形底板", "B 圆形底板", "C 无底板"),
        alignment_types=None,
        extent_label='实时高度 H', extent_name='高度 H', plate_label='底板类型',
        drag_status='已进入竖直拉伸：移动光标预览，左键确认生成；右键取消。',
        done_status='生成完成；可继续点选另一个竖直弯头。',
    ),
    _Variant(
        key='f2he', elbow_label=ELBOW_LABELS[1], trunnion_label=TRUNNION_LABELS[0],
        support_type=F2HE_SUPPORT_TYPE,
        support_code=F2HE_SUPPORT_CODE,
        title='F2-HE · 水平弯头的竖直耳轴',
        hint=("点选水平弯头主单元后自动进入拉伸，移动光标预览耳轴。"
              "H 从弯头弧线中点的主管中心线量到最低点：有底板取板底，F 取覆面底，无底板取管底。"),
        tool_name='SelectHorizontalElbowForTrunnion',
        number_prefix='F2', number_family='f2',
        frame_kind='horizontal_elbow', allow_downward=False,
        base_types=("A 方形底板", "B 圆形底板", "C 无底板"),
        alignment_types=None,
        extent_label='实时高度 H', extent_name='高度 H', plate_label='底板类型',
        drag_status='已进入竖直拉伸：移动光标预览，左键确认生成；右键取消。',
        done_status='生成完成；可继续点选另一个水平弯头。',
    ),
    _Variant(
        key='f4', elbow_label=ELBOW_LABELS[0], trunnion_label=TRUNNION_LABELS[1],
        support_type=F4_SUPPORT_TYPE,
        support_code=F4_SUPPORT_CODE,
        title='F4 · 竖直弯头的水平耳轴',
        hint=("点选弯头后沿水平管延长方向拉伸，移动光标预览耳轴。"
              "L 从竖直段中心线量到耳轴最外端；底平时按朝向标 FB1/FB2。"),
        tool_name='SelectVerticalElbowForHorizontalTrunnion',
        number_prefix='F4', number_family='f4',
        frame_kind='vertical_elbow', allow_downward=True,
        base_types=("A 6 mm 端板", "B 表 2 端板", "C 无端板"),
        alignment_types=ALIGNMENT_TYPES,
        extent_label='实时长度 L', extent_name='长度 L', plate_label='端板类型',
        drag_status='已进入水平拉伸：移动光标预览，左键确认生成；右键取消。',
        done_status='生成完成；可继续点选另一个竖直弯头。',
    ),
    _Variant(
        key='f5', elbow_label=ELBOW_LABELS[1], trunnion_label=TRUNNION_LABELS[1],
        support_type=F5_SUPPORT_TYPE,
        support_code=F5_SUPPORT_CODE,
        title='F5 · 水平弯头的水平耳轴',
        hint=("点选水平弯头后可点击换向，沿两条水平切线之一拉伸。"
              "L 从两支管轴线的理论交点量到最外端；底平标 FB。"),
        tool_name='SelectVerticalElbowForHorizontalTrunnion',
        number_prefix='F5', number_family='f5',
        frame_kind='horizontal_elbow', allow_downward=False,
        base_types=("A 6 mm 端板", "B 表 2 端板", "C 无端板"),
        alignment_types=F5_ALIGNMENT_TYPES,
        extent_label='实时长度 L', extent_name='长度 L', plate_label='端板类型',
        drag_status='已进入水平拉伸：移动光标预览，左键确认生成；右键取消。',
        done_status='生成完成；可继续点选另一个水平弯头。',
    ),
)

VARIANTS_BY_KEY = dict((item.key, item) for item in VARIANTS)

_VARIANT_TABLE = (
    (ELBOW_LABELS[0], TRUNNION_LABELS[0], 'f2v'),
    (ELBOW_LABELS[1], TRUNNION_LABELS[0], 'f2he'),
    (ELBOW_LABELS[0], TRUNNION_LABELS[1], 'f4'),
    (ELBOW_LABELS[1], TRUNNION_LABELS[1], 'f5'),
)


def variant_key(elbow_label, trunnion_label):
    """由顶层两个下拉的显示文字得到型式代号。"""
    for elbow, trunnion, key in _VARIANT_TABLE:
        if elbow == elbow_label and trunnion == trunnion_label:
            return key
    raise ValueError('未知的弯头 / 耳轴方向组合：%s / %s。'
                     % (elbow_label, trunnion_label))


def _bind_variant_implementations():
    """把各型式的 Builder 与拉伸工具绑定到型式表上。"""
    VARIANTS_BY_KEY['f2v'].builder_cls = VerticalElbowTrunnionBuilder
    VARIANTS_BY_KEY['f2v'].height_tool = F2FamilyHeightTool
    VARIANTS_BY_KEY['f2he'].builder_cls = HorizontalElbowTrunnionBuilder
    VARIANTS_BY_KEY['f2he'].height_tool = F2FamilyHeightTool
    VARIANTS_BY_KEY['f4'].builder_cls = F4HorizontalTrunnionBuilder
    VARIANTS_BY_KEY['f4'].height_tool = F4HeightTool
    VARIANTS_BY_KEY['f5'].builder_cls = F5HorizontalTrunnionBuilder
    VARIANTS_BY_KEY['f5'].height_tool = F5HeightTool


def read_selected_elbow(element_id, key):
    """按元素 ID 读取弯头属性与精确放置坐标；四种型式共用本函数。

    与改造前的四个脚本逐字一致：管道弯头与 HVAC 圆风管弯头走同一套尺寸解析，
    差别只在按型式选择弯头坐标系解析函数（竖直弯头 / 水平弯头、是否允许向下弯）。
    """
    variant = VARIANTS_BY_KEY[key]
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

    # 管道弯头与 HVAC 圆风管弯头走同一套解析（属性名不同，输出一致）：风管取
    # MAIN_DIAMETER 作外径、RADIUS 作中心至端面，表 1 档位按外径就近匹配。
    dims = resolve_elbow_dimensions(
        numbers, texts, class_name, PIPE_DATA, SUPPORTED_MAIN_DNS)
    main_dn = dims["main_dn"]
    nominal_mm = dims["nominal_diameter_mm"]
    outside_mm = dims["outside_diameter_mm"]

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
    if variant.frame_kind == 'horizontal_elbow':
        frame = horizontal_elbow_frame_from_matrix(
            matrix, _uor_per_mm(model_ref), dims["run_length_mm"],
            dims["outlet_length_mm"]
        )
    elif variant.allow_downward:
        frame = elbow_frame_from_matrix(
            matrix, _uor_per_mm(model_ref), dims["run_length_mm"],
            dims["outlet_length_mm"], allow_downward=True
        )
    else:
        frame = elbow_frame_from_matrix(
            matrix, _uor_per_mm(model_ref), dims["run_length_mm"],
            dims["outlet_length_mm"]
        )
    result = {
        "element_id": int(element_id),
        "schema": record.get("schema"),
        "class": class_name,
        "variant": variant.key,
        "main_dn": main_dn,
        "nominal_diameter_mm": nominal_mm,
        "outside_diameter_mm": outside_mm,
        "wall_thickness_mm": dims["wall_thickness_mm"],
        "is_duct": dims["is_duct"],
        "main_label": dims["main_label"],
        "main_size_text": dims["main_size_text"],
        "duct_dn_note": dims["main_dn_note"],
        "center_to_end_mm": dims["center_to_end_mm"],
        "frame": frame,
        "component_name": texts.get("COMPONENT_NAME") or texts.get("NAME"),
        "pipe_number": next((str(r.get("texts", {}).get("LINENUMBER")).strip()
                             for r in [record] + records if r.get("texts", {}).get("LINENUMBER")
                             and str(r.get("schema") or "").upper().startswith("OPENPLANT")), ""),
    }
    _log("selected elbow id=%s variant=%s class=%s %s DN=%s OD=%.3f "
         "c2e=%s/%s duct=%s%s" % (
             element_id, variant.key, class_name, dims["main_size_text"], main_dn,
             outside_mm, dims["run_length_mm"], dims["outlet_length_mm"],
             dims["is_duct"],
             (" note=%s" % dims["main_dn_note"]) if dims["main_dn_note"] else ""
         ))
    return result


# ---------------------------------------------------------------------------
# 弯头弧板（护板）：勾选后复用既有「弯头垫板」插件再生成一块弧形护板
# ---------------------------------------------------------------------------


def build_elbow_pad_for(element_id, material_code):
    """按既有弯头垫板插件在同一个弯头上再生成一块弧形护板。

    管径与弯头倍率按弯头实测自动反推（与弯头垫板面板的「自动」一致），材料
    代码沿用耳轴材料，张角与覆盖角取弯头垫板的默认值；清单自成一条 Assembly
    （``弯头垫板``），与单独运行 ``弯头垫板.py`` 的结果完全一致。HVAC 风管
    不查选型表：内弧 = 实际外径/2、板厚按外径定（≤2000 → 6，>2000 → 10）。
    """
    pad = _elbow_pad_module()
    elbow = pad.read_selected_elbow(int(element_id))
    is_duct = bool(elbow.get("is_duct"))
    base_mm = elbow.get("od_basis_mm")      # 风管：实际外径；管道：None
    size_label = elbow.get("size_label")
    # 风管不查选型表：内弧 / 板厚全部由实际外径定，DN 传 None。
    dn = None if is_duct else (elbow["dn"] if elbow["dn"] is not None
                               else pad.DEFAULT_DN)
    multiplier, matched = pad.geom.multiplier_from_center_to_end(
        dn, elbow["center_to_end_mm"], base_mm=base_mm)
    material = str(material_code or '').upper()
    if material not in _elbow_selection_logic.MATERIAL_CODES:
        material = pad.DEFAULT_MATERIAL_CODE
    cell, layout = pad.build_pad(
        elbow, dn, multiplier, material,
        pad.DEFAULT_ALPHA_DEG, pad.DEFAULT_COVERAGE_DEG,
        base_mm=base_mm, size_label=size_label)
    return {
        "cell": cell,
        "layout": layout,
        "matched": matched,
        "dn_from_model": is_duct or elbow["dn"] is not None,
    }


def _pad_log_text(elbow_info, pad_result):
    """弧板的生成记录文字（与弯头垫板插件的口径一致）。"""
    layout = pad_result["layout"]
    parts = ['%s（内弧 R%.1f，外弧 R%.1f，覆盖 %.0f°，%s）' % (
        layout.number, layout.inner_radius, layout.outer_radius,
        layout.coverage_deg, layout.pad_material)]
    if not pad_result["matched"]:
        parts.append('弯头倍率非标准，请核对')
    if not pad_result["dn_from_model"]:
        parts.append('弯头公称直径未匹配到表，管径按兜底 DN%d 取' % layout.dn)
    if elbow_info.get("is_duct"):
        parts.append('风管：内弧按实际外径 Ø%.1f mm 贴合，板厚 T%.0f mm'
                     '（按外径定，不查表）'
                     % (layout.od_mm, layout.thickness))
    if elbow_info.get("duct_dn_note"):
        parts.append(elbow_info["duct_dn_note"])
    return '；'.join(parts)


# ---------------------------------------------------------------------------
# 面板：顶层选型式 + 参数区按型式切换 + 可选附带弯头弧板
# ---------------------------------------------------------------------------


UI_TITLE = '弯头耳轴（F2 / F2-HE / F4 / F5）'


class ElbowTrunnionPanel(GlassDialog):
    """四种弯头耳轴共用一块常驻参数面板和 Bentley 点选主循环。"""

    STATE_KEY = "ElbowTrunnionMerged"

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._live_height = None
        self.processing = False
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        self._elbow_label = tk.StringVar(value=ELBOW_LABELS[0])
        self._trunnion_label = tk.StringVar(value=TRUNNION_LABELS[0])
        self._variant = VARIANTS_BY_KEY[variant_key(
            ELBOW_LABELS[0], TRUNNION_LABELS[0])]
        self.tool_name = self._variant.tool_name
        self._variant_text = tk.StringVar(value='当前型式：' + self._variant.title)
        self._height = tk.StringVar(value="1000.0")
        self._base_type = tk.StringVar(value=self._variant.base_types[0])
        self._alignment = tk.StringVar(value=ALIGNMENT_TYPES[0])
        self._direction_side = tk.StringVar(value='RUN')
        self._direction_text = tk.StringVar(value='伸出方向：Run 端')
        self._hollow = tk.BooleanVar(value=True)
        self._material = tk.StringVar(value='C1')
        self._wall_override = tk.StringVar(value='')
        self._ptfe = tk.BooleanVar(value=False)
        self._with_pad = tk.BooleanVar(value=False)
        self._number = tk.StringVar(value='编号：选弯头后显示')
        self._selected_elbow_info = None
        self._status = tk.StringVar(
            value="先在顶部选择弯头 / 耳轴方向，再到模型中点选 90° 弯头。")
        self._selection = tk.StringVar(
            value="等待点选｜将自动读取 EC 规格、端口坐标和方向。")
        self._build()
        self._apply_variant()
        self.restore_state()
        self.restore_position()
        self.protocol("WM_DELETE_WINDOW", self.close_panel)
        try:
            self.minsize(520, 680)
        except tk.TclError:
            pass

    # -- 界面 ---------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            "顶层选型式 → 点选弯头 → 拉伸确认；可勾选附带弯头弧板",
        )
        form.columnconfigure(0, weight=1)

        variant_card = tk.Frame(form, bg=CARD_SOFT,
                                highlightbackground=BORDER, highlightthickness=1)
        variant_card.grid(row=0, column=0, sticky="ew")

        pick_row = tk.Frame(variant_card, bg=CARD_SOFT)
        pick_row.pack(anchor="w", padx=12, pady=(9, 0))
        tk.Label(pick_row, text='弯头方向', bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        elbow_combo = ttk.Combobox(
            pick_row, textvariable=self._elbow_label, values=ELBOW_LABELS,
            state='readonly', width=12, style='Glass.TCombobox')
        elbow_combo.pack(side='left', padx=(10, 14))
        tk.Label(pick_row, text='耳轴方向', bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        trunnion_combo = ttk.Combobox(
            pick_row, textvariable=self._trunnion_label, values=TRUNNION_LABELS,
            state='readonly', width=12, style='Glass.TCombobox')
        trunnion_combo.pack(side='left', padx=(10, 0))
        elbow_combo.bind('<<ComboboxSelected>>',
                         lambda _event: self.change_variant())
        trunnion_combo.bind('<<ComboboxSelected>>',
                            lambda _event: self.change_variant())

        tk.Label(variant_card, textvariable=self._variant_text, bg=CARD_SOFT,
                 fg="#1F5F99", font=UI_FONT_BOLD).pack(
                     anchor='w', padx=12, pady=(7, 2))
        self._hint_label = tk.Label(
            variant_card, text=self._variant.hint, bg=CARD_SOFT, fg=INK,
            font=UI_FONT_SMALL, justify="left", wraplength=440)
        self._hint_label.pack(anchor='w', padx=12, pady=(0, 9))

        ttk.Label(form, text="1. 放置参数", style="Section.TLabel").grid(
            row=1, column=0, sticky="w", pady=(12, 3)
        )
        height_entry = self._entry_row(
            form, 2, self._variant.extent_label, self._height, "mm")
        height_entry.configure(state="readonly")

        plate_frame = tk.Frame(form, bg=CARD)
        plate_frame.grid(row=3, column=0, sticky="w", pady=(7, 0))
        self._plate_label = tk.Label(plate_frame, text=self._variant.plate_label,
                                     bg=CARD, fg=INK, font=UI_FONT_BOLD)
        self._plate_label.pack(side='left')
        self._plate_combo = ttk.Combobox(
            plate_frame, textvariable=self._base_type,
            values=self._variant.base_types, state="readonly", width=20,
            style="Glass.TCombobox")
        self._plate_combo.pack(side="left", padx=(12, 0))

        check_row = tk.Frame(form, bg=CARD)
        check_row.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        self._alignment_row = tk.Frame(check_row, bg=CARD)
        self._alignment_row.pack(anchor='w', pady=(0, 7))
        tk.Label(self._alignment_row, text='耳轴位置', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        self._alignment_combo = ttk.Combobox(
            self._alignment_row, textvariable=self._alignment,
            values=ALIGNMENT_TYPES, state='readonly', width=20,
            style='Glass.TCombobox')
        self._alignment_combo.pack(side='left', padx=(12, 0))
        self._alignment_combo.bind('<<ComboboxSelected>>',
                                   lambda _event: self._update_number_from_current())

        self._direction_row = tk.Frame(check_row, bg=CARD)
        self._direction_row.pack(anchor='w', pady=(0, 7))
        tk.Label(self._direction_row, textvariable=self._direction_text,
                 bg=CARD, fg=INK, font=UI_FONT_BOLD).pack(side='left')
        # 拉伸期间点击的按钮不能使用 Canvas 悬停动画；Tk 的 after 重绘会与
        # Bentley 动态绘图循环交错，曾在 tkinter.update 中触发访问冲突。
        self._direction_button = tk.Button(
            self._direction_row, text='换向', command=self.change_direction,
            bg=CARD_SOFT, fg=INK, activebackground=FIELD,
            activeforeground=INK, font=UI_FONT, relief='flat',
            bd=0, highlightthickness=0, padx=12, pady=6)
        self._direction_button.pack(side='left', padx=(12, 0))

        # 下面这几行是型式切换时的插入锚点：对齐行 / 换向行插到钢管勾选之前，
        # PTFE 插到弧板勾选之前，避免 pack_forget 后再 pack 把行挤到参数区末尾。
        self._hollow_check = tk.Checkbutton(
            check_row, text="耳轴按钢管建模（取消则为实心圆钢）",
            variable=self._hollow, bg=CARD, fg=INK, activebackground=CARD,
            activeforeground=INK, selectcolor=FIELD, font=UI_FONT,
            highlightthickness=0, bd=0,
        )
        self._hollow_check.pack(anchor="w")
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

        self._ptfe_check = tk.Checkbutton(
            check_row, text='F：与 PTFE 滑板组合（仅 A/B 底板）',
            variable=self._ptfe, bg=CARD, fg=INK, activebackground=CARD,
            activeforeground=INK, selectcolor=FIELD, font=UI_FONT,
            highlightthickness=0, bd=0)

        self._pad_check = tk.Checkbutton(
            check_row, text='附带弯头弧板（护板）（暂不可用）',
            variable=self._with_pad, bg=CARD, fg=INK, activebackground=CARD,
            activeforeground=INK, selectcolor=FIELD, font=UI_FONT,
            highlightthickness=0, bd=0, state='disabled',
        )
        self._pad_check.pack(anchor='w', pady=(6, 0))
        tk.Label(
            check_row,
            text="附带弯头垫板功能已在本面板中禁用。",
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=440,
        ).pack(anchor='w', pady=(1, 0))

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
            wraplength=440,
        ).pack(anchor="w", padx=12, pady=9)
        tk.Label(selection_card, textvariable=self._number, bg=CARD_SOFT,
                 fg=INK, font=UI_FONT_BOLD, justify='left',
                 wraplength=440).pack(anchor='w', padx=12, pady=(0, 9))

        ttk.Label(form, text="生成记录", style="Section.TLabel").grid(
            row=8, column=0, sticky="w", pady=(12, 3)
        )
        log_frame = tk.Frame(
            form, bg=CARD_SOFT, highlightbackground=BORDER, highlightthickness=1
        )
        log_frame.grid(row=9, column=0, sticky="nsew")
        form.rowconfigure(9, weight=1)
        self._log_view = tk.Text(
            log_frame, height=6, width=50, wrap="word", font=UI_FONT_SMALL,
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
            form, self._status, wraplength=440
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
        self._extent_label = tk.Label(frame, text=label, bg=CARD, fg=INK,
                                      font=UI_FONT_BOLD)
        self._extent_label.pack(side="left")
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

    # -- 型式切换 -----------------------------------------------------------

    def change_variant(self):
        """顶层下拉只入队；由主循环取消旧拉伸并重新安装点选工具。"""
        if self.processing or self._close_requested:
            return
        try:
            key = variant_key(self._elbow_label.get(), self._trunnion_label.get())
        except ValueError as error:
            self.set_status(str(error), True)
            return
        self.pending = [('change_variant', key)]
        self._live_height = None

    def _process_change_variant(self, key):
        self._variant = VARIANTS_BY_KEY[key]
        self.tool_name = self._variant.tool_name
        self._selected_elbow_info = None
        self._number.set('编号：选弯头后显示')
        self._selection.set(
            '等待点选｜将自动读取 EC 规格、端口坐标和方向。（当前型式：%s）'
            % self._variant.title)
        self._apply_variant()
        self.restart_selection(False)
        self.set_status('已切换到 %s；请在模型中点选对应的 90° 弯头。'
                        % self._variant.title)

    def _apply_variant(self):
        """按当前型式刷新参数区的标签、取值范围与控件可见性。"""
        variant = self._variant
        self._variant_text.set('当前型式：' + variant.title)
        try:
            self._hint_label.configure(text=variant.hint)
        except tk.TclError:
            pass
        self._extent_label.configure(text=variant.extent_label)
        self._plate_label.configure(text=variant.plate_label)
        self._plate_combo.configure(values=variant.base_types)
        self._base_type.set(variant.base_types[0])
        if variant.uses_alignment:
            self._alignment_combo.configure(values=variant.alignment_types)
            self._alignment.set(variant.alignment_types[0])
            self._alignment_row.pack(anchor='w', pady=(0, 7),
                                     before=self._hollow_check)
        else:
            self._alignment_row.pack_forget()
        if variant.uses_direction:
            self._direction_row.pack(anchor='w', pady=(0, 7),
                                     before=self._hollow_check)
        else:
            self._direction_row.pack_forget()
        if variant.uses_ptfe:
            self._ptfe_check.pack(anchor='w', pady=(5, 0),
                                  before=self._pad_check)
        else:
            self._ptfe_check.pack_forget()
        self._update_direction_text()

    # -- 队列：原生工具回调只入队，实体创建留给主循环 ------------------------

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
        try:
            self._height.set("%.1f" % height)
            self._update_number(height)
        except tk.TclError:
            pass

    # -- 输出（只在主循环 / Tk 上下文里调用） --------------------------------

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

    # -- 编号与选择信息 -----------------------------------------------------

    def _wall_override_value(self):
        text = self._wall_override.get().strip().replace(',', '')
        return None if not text else float(text)

    def _update_number(self, extent):
        info = self._selected_elbow_info
        if info is None:
            return
        try:
            number = self._number_for(info, extent)
            self._number.set('%s 编号：%s' % (self._variant.number_prefix, number))
        except (ValueError, TypeError, IndexError) as error:
            self._number.set('%s 编号：%s' % (self._variant.number_prefix, error))

    def _update_number_from_current(self):
        try:
            self._update_number(float(self._height.get()))
        except (TypeError, ValueError, tk.TclError):
            pass

    def _number_for(self, info, extent):
        variant = self._variant
        dims = support_dimensions(info['main_dn'])
        wall_override = self._wall_override_value()
        wall = dims['trunnion_wall'] if wall_override is None else wall_override
        base = self._base_type.get()[0]
        if variant.number_family == 'f2':
            return f2_number(
                info['main_dn'], dims['trunnion_dn'], wall,
                dims['trunnion_wall'], self._material.get(), extent, base,
                ptfe=bool(self._ptfe.get()),
                horizontal_elbow=(variant.key == 'f2he'),
                main_label=info['main_label'])
        if variant.number_family == 'f4':
            flat = (self._alignment.get() == variant.alignment_types[1])
            bend_code = info['frame']['flat_bend_code'] if flat else ''
            return f4_number(
                info['main_dn'], dims['trunnion_dn'], wall,
                dims['trunnion_wall'], self._material.get(), extent, base,
                bend_code, main_label=info['main_label'])
        flat = (self._alignment.get() == variant.alignment_types[1])
        return f5_number(
            info['main_dn'], dims['trunnion_dn'], wall,
            dims['trunnion_wall'], self._material.get(), extent, base,
            f5_azimuth_deg(f5_placement_direction(
                info['frame'], self._direction_side.get())), flat,
            main_label=info['main_label'])

    def _update_direction_text(self):
        side = self._direction_side.get()
        label = 'Run 端' if side == 'RUN' else 'Outlet 端反向'
        info = self._selected_elbow_info
        if info is None or not self._variant.uses_direction:
            try:
                self._direction_text.set('伸出方向：' + label)
            except tk.TclError:
                pass
            return
        direction = f5_placement_direction(info['frame'], side)
        azimuth = int(f5_azimuth_deg(direction) + 0.5) % 360
        try:
            self._direction_text.set('伸出方向：%s｜方位角 %d°' % (label, azimuth))
        except tk.TclError:
            pass

    def _selection_text(self, elbow_info):
        """选择信息：各型式沿用原面板的端口 / 方位角口径。"""
        variant = self._variant
        dims = support_dimensions(elbow_info["main_dn"])
        frame = elbow_info["frame"]
        if variant.key == 'f2v':
            first, second = frame["horizontal_port_mm"], frame["vertical_port_mm"]
            first_name, second_name, tail = "水平端", "竖直端", ""
        elif variant.key == 'f2he':
            first, second = frame["run_port_mm"], frame["support_axis_mm"]
            first_name, second_name, tail = "Run 端", "弧线中点", ""
        elif variant.key == 'f4':
            first, second = frame["horizontal_port_mm"], frame["vertical_port_mm"]
            first_name, second_name = "水平端", "竖直端"
            tail = "｜底平标记 %s" % frame['flat_bend_code']
        else:
            first, second = frame["run_port_mm"], frame["outlet_port_mm"]
            first_name, second_name = "Run 端", "Outlet 端"
            tail = "｜方位角 %s°" % str(int(f5_azimuth_deg(f5_placement_direction(
                frame, self._direction_side.get())) + 0.5) % 360)
        text = (
            "元素 %s｜%s\n%s · 外径 %.1f mm → 耳轴 DN%d（Ø%.1f）\n"
            "%s (%.1f, %.1f, %.1f)｜%s (%.1f, %.1f, %.1f) mm%s"
            % ((elbow_info["element_id"], elbow_info["class"],
                elbow_info["main_size_text"],
                elbow_info["outside_diameter_mm"],
                dims["trunnion_dn"], dims["trunnion_od"])
               + (first_name,) + tuple(first)
               + (second_name,) + tuple(second) + (tail,))
        )
        if elbow_info.get("is_duct"):
            text += ("\n风管弯头：中心至端面按 RADIUS 取 %.1f mm。"
                     % elbow_info["center_to_end_mm"])
        if elbow_info.get("duct_dn_note"):
            text += "\n" + elbow_info["duct_dn_note"]
        return text

    # -- 主循环内的处理 -----------------------------------------------------

    def _process_pick(self, element_id, pick_view_position):
        self.processing = True
        try:
            elbow_info = read_selected_elbow(element_id, self._variant.key)
            self._selected_elbow_info = elbow_info
            self._selection.set(self._selection_text(elbow_info))
            self._update_direction_text()
            self._variant.height_tool.InstallNewInstance(
                0, self, elbow_info, pick_view_position)
            self.set_status(self._variant.drag_status)
        except Exception as error:
            _log("selection exception for %s: %r" % (element_id, error))
            self.set_status("%s；请重新点选有效的 90° 弯头。" % error, True)
            if not isinstance(_ACTIVE_PLACEMENT_TOOL, TrunnionPlacementTool):
                self.restart_selection(False)
        finally:
            self.processing = False

    def builder(self, extent):
        """按当前型式构造 Builder；高度 / 长度范围与原件一致。"""
        variant = self._variant
        if not 50.0 <= extent <= 20000.0:
            raise ValueError("%s 必须在 50～20000 mm 之间。" % variant.extent_name)
        wall = self._wall_override_value()
        hollow = bool(self._hollow.get())
        material = self._material.get()
        base = self._base_type.get()
        if variant.number_family == 'f2':
            builder = variant.builder_cls(
                extent, base, hollow, material, wall, bool(self._ptfe.get()))
        elif variant.number_family == 'f4':
            builder = variant.builder_cls(
                extent, base, self._alignment.get(), hollow, material, wall)
        else:
            builder = variant.builder_cls(
                extent, base, self._alignment.get(),
                self._direction_side.get(), hollow, material, wall)
        builder._validate()
        return builder

    def _process_height(self, elbow_info, extent):
        self.processing = True
        try:
            builder = self.builder(extent)
            elements = builder.create_from_elbow(elbow_info)
            self._height.set("%.1f" % extent)
            self._number.set('%s 编号：%s' % (
                self._variant.number_prefix, builder.number))
            if self._variant.number_family == 'f2':
                extent_text = 'H %.1f mm' % builder.height_h_mm
                plate = builder.base_type
            else:
                extent_text = 'L %.1f mm' % builder.length_l_mm
                plate = builder.end_plate_type
            self._append_log(
                "已生成｜%s｜元素 %s｜%s｜%s｜%s｜单元 %s"
                % (builder.number, elbow_info["element_id"],
                   elbow_info["main_size_text"], extent_text, plate,
                   ", ".join(str(item.GetElementId()) for item in elements))
            )
            pad_error = None
            if bool(self._with_pad.get()):
                try:
                    pad_result = build_elbow_pad_for(
                        elbow_info["element_id"], self._material.get())
                    self._append_log(
                        "附带弧板｜%s" % _pad_log_text(elbow_info, pad_result))
                except Exception as error:
                    pad_error = error
                    _log("pad generation exception for %s: %r" % (
                        elbow_info["element_id"], error))
            if pad_error is not None:
                self.set_status(
                    "耳轴已生成；但附带弯头弧板失败：%s。（可单独运行 弯头垫板.py）"
                    % pad_error, True)
            else:
                self.set_status(self._variant.done_status)
        except AttachmentIncompleteError as error:
            _log("height/attachment exception for %s: %r" % (
                elbow_info["element_id"], error))
            self.set_status(str(error), True)
        except Exception as error:
            _log("height/create exception for %s: %r" % (
                elbow_info["element_id"], error))
            self.set_status("%s；请重新点选弯头后拉伸。" % error, True)
        finally:
            self.processing = False
            self.restart_selection(False)

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
        """只重置本次拉伸；Bentley 动态工具保持运行（仅 F5 型式可见）。"""
        _watch_direction_change()
        self._direction_side.set(
            'OUTLET' if self._direction_side.get() == 'RUN' else 'RUN')
        self._update_direction_text()
        if self._selected_elbow_info is not None:
            self._selection.set(self._selection_text(self._selected_elbow_info))
        self._update_number_from_current()
        tool = _ACTIVE_PLACEMENT_TOOL
        if isinstance(tool, F5HeightTool) and tool.panel is self:
            tool._has_preview = False
            tool._accept_armed = False
            tool._first_frame_logged = False
            self.set_status('已换向；旧拉伸已放弃，移动光标预览新方向后左键确认。')
        else:
            self.set_status('已换向；选择水平弯头后开始拉伸。')
        _log('direction changed to %s; preview reset' %
             self._direction_side.get())

    def _run_pending(self):
        pending, self.pending = self.pending, []
        changes = [item for item in pending if item[0] == 'change_variant']
        if changes:
            # 切换前的点选、确认、换向和动态高度均已失效。
            pending = changes[-1:]
            self._live_height = None
        for item in pending:
            if item[0] == 'change_variant':
                self._process_change_variant(item[1])
            elif item[0] == "pick":
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
                self.set_status(
                    "请在模型中点选一个 OpenPlant 90° 弯头（当前型式：%s）。"
                    % self._variant.title)
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
            # 在 Tk 回调结束后、下一次 Bentley 输入前处理型式切换。
            if any(item[0] in ('change_direction', 'change_variant')
                   for item in self.pending):
                self._run_pending()
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception as error:
                _log("PythonMainLoop exception: %r" % error)
                self._apply_status("Bentley 输入循环失败：%s" % error, True)
                break
            self._run_pending()

    # -- 状态记忆 -----------------------------------------------------------

    def restore_state(self):
        key = self.ui_state.get('variant_key')
        if key in VARIANTS_BY_KEY:
            self._variant = VARIANTS_BY_KEY[key]
            self._elbow_label.set(self._variant.elbow_label)
            self._trunnion_label.set(self._variant.trunnion_label)
            self.tool_name = self._variant.tool_name
            self._apply_variant()
        height = self.ui_state.get("height_h")
        if isinstance(height, (int, float)) and 0.0 < height <= 20000.0:
            self._height.set("%.1f" % height)
        base_type = self.ui_state.get("base_type")
        if base_type in self._variant.base_types:
            self._base_type.set(base_type)
        alignment = self.ui_state.get('alignment')
        if self._variant.uses_alignment and alignment in self._variant.alignment_types:
            self._alignment.set(alignment)
        side = self.ui_state.get('direction_side')
        if side in ('RUN', 'OUTLET'):
            self._direction_side.set(side)
        hollow = self.ui_state.get("hollow_trunnion")
        if isinstance(hollow, bool):
            self._hollow.set(hollow)
        material = self.ui_state.get('material_code')
        if material in _elbow_selection_logic.MATERIAL_CODES:
            self._material.set(material)
        self._wall_override.set(str(self.ui_state.get('wall_override_mm') or ''))
        self._ptfe.set(bool(self.ui_state.get('ptfe', False)))
        # 面板暂时禁用附带弧板，旧配置中的勾选状态也不恢复。
        self._with_pad.set(False)
        self._update_direction_text()

    def persist_state(self, state):
        state['variant_key'] = self._variant.key
        try:
            state["height_h"] = float(self._height.get().strip())
        except (TypeError, ValueError):
            state["height_h"] = 1000.0
        state["base_type"] = self._base_type.get()
        state['alignment'] = self._alignment.get()
        state['direction_side'] = self._direction_side.get()
        state["hollow_trunnion"] = bool(self._hollow.get())
        state['material_code'] = self._material.get()
        state['wall_override_mm'] = self._wall_override.get().strip()
        state['ptfe'] = bool(self._ptfe.get())
        state['with_pad'] = False


def main():
    global _ACTIVE_PANEL
    _enable_fault_logging()
    try:
        _ACTIVE_PANEL = ElbowTrunnionPanel()
        TrunnionPlacementTool.InstallNewInstance(0, _ACTIVE_PANEL, True)
    finally:
        _disable_fault_logging()


# 四种型式的 Builder / 拉伸工具在这里绑定到型式表上（幂等）。
_bind_variant_implementations()
_boot_log('import: 完成（型式表已装配，可创建面板）')


if __name__ == "__main__":
    main()
