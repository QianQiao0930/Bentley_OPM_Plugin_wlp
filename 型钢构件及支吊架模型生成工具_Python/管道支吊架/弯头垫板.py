# -*- coding: utf-8 -*-
"""弯头弧形垫板放置工具。

运行后**点选一个已有的 OpenPlant 90° 弯头**，在该弯头**背弧（外弯侧 / extrados）**
上生成一块「弯头弧形垫板」：垫板贴附焊接在弯头**外壁**上、居中于弯头弯曲方向的
45° 中点，沿弯曲方向覆盖 **75°**（图左侧），截面周向张角 **120°**（图右侧，与
Y2 弧形垫板同款）。可连续点选，右键退出。

几何做法：

    截面（垂直于弯头中心线）＝ 两段同心圆弧 + 两条径向直线：
        内弧半径 = 弯头外径 / 2（贴弯头外壁，构成环面）
        外弧半径 = 内弧半径 + T（T = 板厚，沿用 Y2 表 1）
        两弧张角 α（缺省 120°，与 Y2 一致）
    截面沿**弯头中心线圆弧**扫掠，覆盖 75°、居中于 45° 中点；
    垫板中央（覆盖中点背弧冠线）开 气孔 Ø6（沿背弧径向贯穿板厚）。

数据来源（全部从所选弯头的 EC 属性与变换矩阵自动读取）：

* ``NOMINAL_DIAMETER`` → 匹配 DN → 按 **ASME B36.10M** 取外径；
* ``DESIGN_LENGTH_CENTER_TO_RUN_END`` / ``..._OUTLET_END``（中心至端面长度）
  → 除以 **NPS 英寸公称直径** 反推**弯头倍率**（1.5D 长半径 / 1.0D 短半径…），
  并吸附到最近标准倍率；面板可用倍率下拉**覆盖**自动值；
* ``TRANSFORMATION_MATRIX`` → 端口 0 原点、入口切线（局部 X）、指向弯曲中心
  方向（局部 Z），据此定位弯头中心线圆弧。

编号：``弯头垫板-管径-弯头倍率``（如 ``弯头垫板-100-1.5``）—— 图集未给编号，
直接按名称编号，故编号中**不含**材料代码与覆盖角。

**HVAC 圆风管弯头**（``OpenPlant_3D.HVAC_ROUND_ELBOW``）同样支持：外径取 EC 的
``MAIN_DIAMETER``（风管实际外径）、弯曲半径取 ``RADIUS``，倍率基准 = 风管外径
（1.0D 即 R = 外径）；**不查任何选型表**——内弧 = 外径/2、外弧 = 内弧 + T，
板厚按外径直接定（≤2000 mm → 6、>2000 mm → 10）；编号按实际外径写，如
``弯头垫板-D1060-1.0``。矩形风管不支持。管道弯头路径与报错文案保持不变。

EC 读取遵循本仓库铁律：**不在工具回调里读 EC**——点选只把「元素 ID」入队，真正的
读取与建模由面板主循环在 ``PyCadInputQueue.PythonMainLoop()`` 返回之后执行；
EC 实例在 ``FindInstances`` 的原始遍历内当场读成纯 Python 数据，绝不外传。

清单写入**管道支吊架公共库**，`SupportType='弯头垫板'`，可统一统计 / 导出。
纯几何 / 数据逻辑在 ``模块/弯头垫板/弯头垫板_几何.py``（可脱离 Bentley 单测）。

运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import importlib
import math
import os
import re
import sys
import time
import traceback

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from MSPyBentley import WString  # noqa: E402,F811
from MSPyMstnPlatform import PythonKeyinManager  # noqa: E402,F811

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '弯头垫板')
# 复用竖直弯头耳轴的纯逻辑库（含 EC 单位标定 ``dimension_scale_to_mm``）。
ELBOW_LOGIC_DIR = os.path.join(HERE, '模块', '竖直弯头的竖直耳轴')
for _path in (COMMON_DIR, GEOM_DIR, ELBOW_LOGIC_DIR, REPO_ROOT):
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

import elbow_selection_logic as _elbow_logic  # noqa: E402
import 弯头垫板_几何 as geom  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


UI_TITLE = '弯头垫板'
SUPPORT_TYPE = '弯头垫板'
SUPPORT_CODE = 'ELBOW_PAD'
CELL_NAME = 'ELBOW_PAD'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', '弯头垫板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 兜底管径：读不到弯头公称直径 / 不在表内时使用。
DEFAULT_DN = 100
DEFAULT_MATERIAL_CODE = geom.DEFAULT_MATERIAL_CODE
DEFAULT_ALPHA_DEG = geom.WRAP_ALPHA_DEG
DEFAULT_COVERAGE_DEG = geom.COVERAGE_DEG
AUTO_MULTIPLIER_LABEL = '自动（按弯头实测）'

# 气孔布尔减时两端各多伸出的余量（mm）。
VENT_HOLE_MARGIN_MM = 1.0

# 只接受标准 90° 圆弧弯头（角度容差 °）。
ELBOW_ANGLE_TOLERANCE_DEG = 0.5

SUCCESS = 0

# EC 属性：只读本工具关心的弯头属性（含 3×4 变换矩阵 M00~M11）。
# HVAC 圆风管弯头的属性名（MAIN_DIAMETER / RADIUS …）由公共模块给出。
ELBOW_NUMBER_PROPERTIES = (
    'ANGLE', 'NOMINAL_DIAMETER', 'NOMINAL_DIAMETER_RUN_END',
    'OUTSIDE_DIAMETER', 'WALL_THICKNESS', 'LENGTH',
    'DESIGN_LENGTH_CENTER_TO_RUN_END',
    'DESIGN_LENGTH_CENTER_TO_OUTLET_END',
    'DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE',
    'DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE',
) + _elbow_logic.HVAC_NUMBER_PROPERTIES + tuple(
    'TRANSFORMATION_MATRIX.M%02d' % index for index in range(12))
ELBOW_TEXT_PROPERTIES = ('UNIT_OF_MEASURE', 'COMPONENT_NAME', 'NAME',
                         'LINENUMBER')


def _log(message):
    try:
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (stamp, message))
            stream.flush()
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _reload_runtime_modules():
    importlib.invalidate_caches()
    for module in (geom, psb, _elbow_logic):
        try:
            importlib.reload(module)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _succeeded(status):
    if isinstance(status, tuple):
        status = status[0] if status else None
    try:
        return int(status) == SUCCESS
    except (TypeError, ValueError):
        return status == SUCCESS


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerMeter() / 1000.0


def _dpoint(point_mm, uor_per_mm):
    return DPoint3d(point_mm[0] * uor_per_mm, point_mm[1] * uor_per_mm,
                    point_mm[2] * uor_per_mm)


# ---------------------------------------------------------------------------
# EC 读取（就地遍历，实例绝不出遍历；不在工具回调内调用）
# ---------------------------------------------------------------------------


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
        for getter in ('GetDouble', 'GetInteger'):
            try:
                number = float(getattr(value, getter)())
                if not math.isnan(number) and not math.isinf(number):
                    return number
            except Exception:
                continue
    except Exception:
        pass
    return None


def _formatted_property_text(instance, access_string, property_value):
    try:
        buffer = WString()
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
    try:
        buffer = WString()
        instance.GetValueAsString(buffer, access_string, False, 0)
        text = str(buffer).strip()
    except Exception:
        return None
    match = re.search(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except (TypeError, ValueError):
        return None


def _number_from_property_value(instance, access_string, property_value):
    """优先直接读枚举到的属性值；嵌套结构体子项用这种方式最稳定。"""
    try:
        value = property_value.GetValue()
        if value is not None and not value.IsNull():
            for getter in ('GetDouble', 'GetInteger'):
                try:
                    number = float(getattr(value, getter)())
                    if not math.isnan(number) and not math.isinf(number):
                        return number
                except Exception:
                    continue
    except Exception:
        pass
    number = _ec_number(instance, access_string)
    if number is not None:
        return number
    text = _formatted_property_text(instance, access_string, property_value)
    if text:
        match = re.search(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',
                          text)
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
            or _formatted_property_text(instance, access_string,
                                        property_value))


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
                instance, access_string, property_value)
        elif access_string in ELBOW_TEXT_PROPERTIES:
            texts[access_string] = _text_from_property_value(
                instance, access_string, property_value)

        # OPM 的结构体属性采用惰性展开：必须先 GetValue()，随后
        # HasChildValues()/GetChildValues() 才能看到 M00～M15。
        try:
            property_value.GetValue()
        except Exception:
            pass
        try:
            has_children = bool(property_value.HasChildValues())
            if has_children or access_string == 'TRANSFORMATION_MATRIX':
                child_values = property_value.GetChildValues()
                if child_values is not None:
                    _read_target_ec_values(
                        instance, child_values, numbers, texts, seen)
        except Exception:
            pass

        # 若当前 MSPy 绑定仍拒绝展开子集合，矩阵根节点已由枚举确认存在，
        # 可以安全地用完整访问路径直接读取标准 M00～M11 字段。
        if access_string == 'TRANSFORMATION_MATRIX':
            for index in range(12):
                child_name = 'TRANSFORMATION_MATRIX.M%02d' % index
                if numbers.get(child_name) is None:
                    numbers[child_name] = _number_from_access_string(
                        instance, child_name)


def _ec_instance_class(instance):
    try:
        ec_class = instance.GetClass()
        return (str(ec_class.GetSchema().GetName()),
                str(ec_class.GetName()))
    except Exception:
        return '', ''


def _collect_elbow_records(element_handle):
    """把元素上的 EC 弯头候选读成纯 Python 字典。"""
    manager = DgnECManager.GetManager()
    query = ECQuery.CreateQuery(_search_all_ec_flag())
    scope = FindInstancesScope.CreateScope(
        element_handle, FindInstancesScopeOption(DgnECHostType.eElement))
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
            _log('EC instance read failed %s.%s: %r'
                 % (schema_name, class_name, error))
            continue
        records.append({
            'schema': schema_name,
            'class': class_name,
            'numbers': numbers,
            'texts': texts,
            'seen': seen,
        })
    return records


def _pick_elbow_record(records):
    candidates = []
    for record in records:
        schema_name = (record.get('schema') or '').upper()
        class_name = (record.get('class') or '').upper()
        if schema_name.startswith('OPENPLANT') and 'ELBOW' in class_name:
            score = 10
            if '90_DEGREE' in class_name:
                score += 3
            if record.get('numbers', {}).get('ANGLE') is not None:
                score += 1
            candidates.append((score, record))
    if not candidates:
        raise ValueError('所选元素不是 OpenPlant 弯头。')
    return max(candidates, key=lambda item: item[0])[1]


def _first_number(numbers, *names):
    for name in names:
        value = numbers.get(name)
        if value is not None:
            return value
    return None


def _element_handle_by_id(element_id):
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('取不到活动 DGN 模型。')
    handle = EditElementHandle(int(element_id), model_ref.GetDgnModel())
    return handle if handle.IsValid() else None


def _read_element_id(element_handle):
    """取元素 ID（只读、不保留句柄）；取不到返回 ``None``。"""
    for getter in ('ElementId', 'GetElementId'):
        try:
            value = getattr(element_handle, getter)
        except Exception:
            continue
        try:
            return int(value() if callable(value) else value)
        except Exception:
            continue
    return None


def read_selected_elbow(element_id):
    """按元素 ID 读取弯头的纯数据（DN / 外径 / 中心至端面 / 局部坐标轴）。

    返回的 ``origin_mm`` / ``axis_x`` / ``axis_z`` 与 ``F5`` 同一套 OPM 解析：
    端口 0 位于矩阵原点，局部 X 是端口 0 进入弯头的切线，局部 Z 由端口 0 指向
    弯曲中心。实际建系由 :func:`弯头垫板_几何.build_frame` 完成。
    """
    handle = _element_handle_by_id(element_id)
    if handle is None:
        raise ValueError('所选元素已经失效，请重新选择。')
    record = _pick_elbow_record(_collect_elbow_records(handle))
    numbers = record['numbers']
    texts = record['texts']

    angle = numbers.get('ANGLE')
    class_name = record.get('class') or ''
    if angle is not None:
        if abs(angle - geom.ELBOW_ANGLE_DEG) > ELBOW_ANGLE_TOLERANCE_DEG:
            raise ValueError('所选弯头角度为 %.2f°，本工具只支持 90° 弯头。'
                             % angle)
    elif '90_DEGREE' not in class_name.upper():
        raise ValueError('无法确认所选弯头为 90° 弯头。')

    is_duct = _elbow_logic.is_hvac_class(class_name)
    if is_duct:
        # HVAC 圆风管弯头：**不查选型表**（护板与表 1 无关）。外径取弯头实测值、
        # 中心至端面取 RADIUS；内弧 = 外径/2，板厚由 geom.duct_thickness_mm 按
        # 外径直接定（≤2000 → 6，>2000 → 10），编号按实际外径写（D1060）。
        dims = _elbow_logic.resolve_elbow_dimensions(
            numbers, texts, class_name, None, ())
        nominal_mm = dims['nominal_diameter_mm']
        outside_mm = dims['outside_diameter_mm']
        center_to_end_mm = dims['center_to_end_mm']
        table_dn = None
        size_label = dims['main_label']
        duct_note = dims['main_dn_note']
    else:
        scale_mm = _elbow_logic.dimension_scale_to_mm(
            texts.get('UNIT_OF_MEASURE'), numbers.get('NOMINAL_DIAMETER'))

        nominal_raw = _first_number(
            numbers, 'NOMINAL_DIAMETER', 'NOMINAL_DIAMETER_RUN_END')
        nominal_mm = (nominal_raw * scale_mm) if nominal_raw is not None else None

        outside_raw = numbers.get('OUTSIDE_DIAMETER')
        outside_mm = (outside_raw * scale_mm) if outside_raw is not None else None

        run_raw = _first_number(
            numbers, 'DESIGN_LENGTH_CENTER_TO_RUN_END',
            'DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE')
        outlet_raw = _first_number(
            numbers, 'DESIGN_LENGTH_CENTER_TO_OUTLET_END',
            'DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE')
        length_raw = numbers.get('LENGTH')
        if run_raw is None and length_raw is not None:
            run_raw = length_raw / 2.0
        if outlet_raw is None and length_raw is not None:
            outlet_raw = length_raw / 2.0
        if run_raw is None or outlet_raw is None:
            raise ValueError('弯头缺少中心至端面长度，无法反推弯曲半径。')
        run_mm = run_raw * scale_mm
        outlet_mm = outlet_raw * scale_mm
        if abs(run_mm - outlet_mm) > max(run_mm, outlet_mm) * 0.02:
            raise ValueError('弯头两端中心距不一致，本工具只支持标准 90° 圆弧弯头。')
        center_to_end_mm = (run_mm + outlet_mm) / 2.0
        table_dn = geom.match_dn(nominal_mm)
        size_label = None
        duct_note = ''

    matrix = [numbers.get('TRANSFORMATION_MATRIX.M%02d' % index)
              for index in range(12)]
    missing = ['M%02d' % index for index, value in enumerate(matrix)
               if value is None]
    if missing:
        raise ValueError('弯头变换矩阵读取不完整，缺少：%s。' % ', '.join(missing))

    def _axis(columns):
        values = tuple(float(matrix[columns[index]]) for index in range(3))
        length = math.sqrt(sum(value * value for value in values))
        if length <= 1.0e-12:
            raise ValueError('弯头变换矩阵局部轴为零向量。')
        return tuple(value / length for value in values)

    uor = _uor_per_mm()
    origin = (matrix[3] / uor, matrix[7] / uor, matrix[11] / uor)
    axis_x = _axis((0, 4, 8))    # 局部 X：端口 0 进入弯头的切线
    axis_z = _axis((2, 6, 10))   # 局部 Z：由端口 0 指向弯曲中心

    _log('selected elbow id=%s class=%s %s nominal=%s OD=%s c2e=%.3f duct=%s '
         'origin=%s' % (
             element_id, class_name,
             size_label or ('DN%s' % table_dn if table_dn else '?'),
             nominal_mm, outside_mm, center_to_end_mm, is_duct,
             tuple(round(value, 2) for value in origin)))
    return {
        'element_id': int(element_id),
        'class': class_name,
        'component_name': texts.get('COMPONENT_NAME') or texts.get('NAME'),
        'pipe_number': (str(texts.get('LINENUMBER')).strip()
                        if texts.get('LINENUMBER') else ''),
        'angle_deg': angle if angle is not None else geom.ELBOW_ANGLE_DEG,
        'nominal_diameter_mm': nominal_mm,
        'outside_diameter_mm': outside_mm,
        'center_to_end_mm': center_to_end_mm,
        'dn': table_dn,
        'is_duct': bool(is_duct),
        'size_label': size_label,
        'od_basis_mm': outside_mm if is_duct else None,
        'duct_dn_note': duct_note,
        'origin_mm': origin,
        'axis_x': axis_x,
        'axis_z': axis_z,
    }


# ---------------------------------------------------------------------------
# 实体构造：闭合截面沿弯头中心线圆弧扫掠
# ---------------------------------------------------------------------------


def _build_profile_curves(layout, origin, ey, ez, uor_per_mm):
    """截面闭合轮廓（「直线 + 真圆弧」）映射到覆盖起点的截面平面内。

    局部 ``(y, z)`` → 世界 ``origin + y·ey + z·ez``（截面平面法向即扫掠切向）。
    圆弧用 ``DEllipse3d.FromPointsOnArc`` 由三点还原精确圆弧，扫掠出的内 / 外表面
    是光滑环面，不会出现折线近似的棱面（「格格」）。
    """
    def world(y, z):
        return (origin[0] + y * ey[0] + z * ez[0],
                origin[1] + y * ey[1] + z * ez[1],
                origin[2] + y * ey[2] + z * ez[2])

    profile = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for kind, points in geom.section_segments(layout):
        mapped = [_dpoint(world(y, z), uor_per_mm) for (y, z) in points]
        if kind == 'arc':
            profile.Add(ICurvePrimitive.CreateArc(
                DEllipse3d.FromPointsOnArc(mapped[0], mapped[1], mapped[2])))
        else:
            profile.Add(ICurvePrimitive.CreateLine(
                DSegment3d(mapped[0], mapped[1])))
    return profile


def _arc_path_curves(frame, layout, uor_per_mm):
    """弯头中心线圆弧的开放路径（三点定弧，覆盖 75°、居中于 45° 中点）。"""
    start, middle, end = geom.path_points(frame, layout)
    path = CurveVector(CurveVector.eBOUNDARY_TYPE_Open)
    path.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromPointsOnArc(
        _dpoint(start, uor_per_mm), _dpoint(middle, uor_per_mm),
        _dpoint(end, uor_per_mm))))
    return path


def _profile_variants(profile):
    """原始闭合轮廓 + 内核更常接受的 ParityRegion 包裹。"""
    variants = [('outer', profile)]
    try:
        region = CurveVector(CurveVector.eBOUNDARY_TYPE_ParityRegion)
        region.Add(profile)
        variants.append(('parity', region))
    except Exception:
        _log_exception('wrap profile as parity region failed')
    return variants


def _body_from_sweep(profile, path, model_ref, path_start_mm, up_axis,
                     uor_per_mm):
    """闭合截面沿圆弧路径扫掠成体，容忍签名 / 区域包裹的差异。"""
    up = DVec3d.From(up_axis[0], up_axis[1], up_axis[2])
    start = _dpoint(path_start_mm, uor_per_mm)

    def call_ten(profile_curve, path_curve, up_vector, scalar):
        if scalar:
            return SolidUtil.Create.BodyFromSweep(
                profile_curve, path_curve, model_ref, False, True, False,
                up_vector, 0.0, 1.0, start)
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False,
            up_vector, None, None, None)

    def call_six(profile_curve, path_curve):
        return SolidUtil.Create.BodyFromSweep(
            profile_curve, path_curve, model_ref, False, True, False)

    last_reason = '没有可用的扫掠调用'
    for profile_label, profile_curve in _profile_variants(profile):
        for up_label, up_vector in (('none', None), ('up', up)):
            plans = [(profile_label + '/10-' + up_label,
                      lambda p=profile_curve, u=up_vector: call_ten(
                          p, path, u, False))]
            if up_vector is not None:
                plans.append((profile_label + '/10s-' + up_label,
                              lambda p=profile_curve, u=up_vector: call_ten(
                                  p, path, u, True)))
            plans.append((profile_label + '/6',
                          lambda p=profile_curve: call_six(p, path)))
            for label, call in plans:
                try:
                    result = call()
                except Exception as error:
                    last_reason = '%s: %r' % (label, error)
                    _log('sweep %s raised: %r' % (label, error))
                    continue
                if (isinstance(result, (tuple, list)) and len(result) >= 2
                        and _succeeded(result[0]) and result[1] is not None):
                    _log('sweep success via %s' % label)
                    return result[1]
                last_reason = '%s: %r' % (label, result)
    _log('sweep failed: %s' % last_reason)
    return None


def _sweep_pad_body(frame, layout, model_ref, uor_per_mm):
    """截面沿弯头中心线圆弧扫掠成垫板实体；失败返回 None。"""
    _ex, ey, ez, origin = geom.sweep_frame(frame, layout)
    profile = _build_profile_curves(layout, origin, ey, ez, uor_per_mm)
    path = _arc_path_curves(frame, layout, uor_per_mm)
    # 锁定方向取截面局部 +Y（即弯曲平面法向）：平面圆弧扫掠时截面不扭转。
    return _body_from_sweep(profile, path, model_ref, origin, ey, uor_per_mm)


def _cone_body(start_mm, end_mm, radius_mm, dgn_model, uor_per_mm):
    """真正的圆柱实体；起点、终点为世界坐标（mm）。失败返回 None。"""
    detail = DgnConeDetail(_dpoint(start_mm, uor_per_mm),
                           _dpoint(end_mm, uor_per_mm),
                           radius_mm * uor_per_mm, radius_mm * uor_per_mm, True)
    primitive = ISolidPrimitive.CreateDgnCone(detail)
    element = EditElementHandle()
    if BentleyStatus.eSUCCESS != DraftingElementSchema.ToElement(
            element, primitive, None, dgn_model):
        return None
    result = SolidUtil.Convert.ElementToBody(element, True, True, False)
    if result is None or not _succeeded(result[0]):
        return None
    return result[1]


def _boolean(target, tools, subtract):
    array = ISolidKernelEntityPtrArray()
    for tool in tools:
        array.append(tool)
    try:
        if subtract:
            status = SolidUtil.Modify.BooleanSubtract(target, array)
        else:
            status = SolidUtil.Modify.BooleanUnion(target, array)
    except Exception as error:
        _log('boolean exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    return BentleyStatus.eSUCCESS == status


def _assembly_element(dgn_model, bodies):
    """把垫板装入 Cell 后一次写入模型。"""
    cell = EditElementHandle()
    NormalCellHeaderHandler.CreateOrphanCellElement(cell, CELL_NAME, True,
                                                    dgn_model)
    for name, body in bodies:
        child = EditElementHandle()
        if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
                child, body, None, dgn_model):
            raise RuntimeError('%s转模型元素失败。' % name)
        if BentleyStatus.eSUCCESS != NormalCellHeaderHandler.AddChildElement(
                cell, child):
            raise RuntimeError('%s加入单元失败。' % name)
    if BentleyStatus.eSUCCESS != NormalCellHeaderHandler.AddChildComplete(cell):
        raise RuntimeError('完成垫板单元失败。')
    if BentleyStatus.eSUCCESS != cell.AddToModel():
        raise RuntimeError('写入垫板单元失败。')
    return cell


def _attach_support_items(cell, layout, elbow):
    """把垫板写入共享支吊架库（整组记录 + 构件记录），供统一统计 / 清单。"""
    size_text = (elbow.get('size_label')
                 or 'DN%d（%s）' % (layout.dn, layout.nps))
    specification = ('%s OD%.1f，T%.0f，弯头倍率 %.1fD（R%.1f），'
                     '覆盖 %.0f°，α%.0f°，%s'
                     % (size_text, layout.od_mm, layout.thickness,
                        layout.multiplier, layout.bend_radius_mm,
                        layout.coverage_deg, layout.alpha_deg,
                        layout.pad_material))
    components = [{
        'code': 'ElbowPad',
        'name': '弯头垫板',
        'specification': specification,
        'length': float(layout.arc_length_mm),
        'quantity': 1,
        'unit': '件',
    }]
    try:
        return psb.attach_components(
            cell, support_type=SUPPORT_TYPE, support_code=SUPPORT_CODE,
            assembly_tag=layout.number, assembly_spec=specification,
            components=components, pipe_number=elbow.get('pipe_number') or '')
    except Exception:
        _log_exception('attach support items failed')
        return 0


def build_pad(elbow, dn, multiplier, material_code=DEFAULT_MATERIAL_CODE,
              alpha_deg=DEFAULT_ALPHA_DEG, coverage_deg=DEFAULT_COVERAGE_DEG,
              base_mm=None, size_label=None):
    """按所选弯头与参数在背弧上生成一块弯头弧形垫板。

    ``base_mm`` / ``size_label`` 仅用于 **HVAC 圆风管弯头**：内弧半径与弯曲半径
    按风管实际外径贴合，板厚按外径直接定（≤2000 → 6，>2000 → 10，不查表），
    编号写 ``D1060``；管道弯头传 ``None``，行为与原来一致（板厚查 Y2 表 1）。

    返回 ``(模型单元, layout)``。
    """
    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise ValueError('请在三维模型中运行。')
    model_ref = ISessionMgr.ActiveDgnModelRef
    if model_ref is None:
        raise RuntimeError('取不到活动 DGN 模型。')

    frame = geom.build_frame(elbow['origin_mm'], elbow['axis_x'],
                             elbow['axis_z'], dn, multiplier, base_mm=base_mm)
    layout = geom.build_layout(dn, multiplier, material_code, alpha_deg,
                               coverage_deg, od_override_mm=base_mm,
                               size_label=size_label)
    uor_per_mm = _uor_per_mm(dgn_model)

    body = _sweep_pad_body(frame, layout, model_ref, uor_per_mm)
    if body is None:
        raise RuntimeError('创建垫板扫掠体失败（截面或圆弧路径无效）。')

    if layout.has_vent_hole:
        outer_end, inner_end = geom.vent_hole_axis(
            frame, layout, VENT_HOLE_MARGIN_MM)
        hole = _cone_body(outer_end, inner_end, layout.vent_hole_dia / 2.0,
                          dgn_model, uor_per_mm)
        if hole is None:
            _log('vent hole cylinder failed; pad generated without hole')
        elif not _boolean(body, [hole], True):
            _log('vent hole boolean failed; pad generated without hole')

    cell = _assembly_element(dgn_model, [('弯头垫板', body)])
    _attach_support_items(cell, layout, elbow)
    return cell, layout


def _compose_message(elbow, layout, dn, dn_from_model, multiplier_auto,
                     multiplier_matched, panel_multiplier):
    parts = []
    if elbow.get('is_duct'):
        parts.append('风管弯头：内弧按实际外径 Ø%.1f mm（R%.1f）贴合，'
                     '板厚 T%.0f mm（直接按外径定，不查表）。'
                     % (elbow['outside_diameter_mm'], layout.inner_radius,
                        layout.thickness))
        if elbow.get('duct_dn_note'):
            parts.append(elbow['duct_dn_note'])
    elif dn_from_model:
        parts.append('弯头公称直径 %s → DN%d。'
                     % ('%.1f mm' % elbow['nominal_diameter_mm']
                        if elbow['nominal_diameter_mm'] is not None
                        else '未知', dn))
    else:
        parts.append('弯头公称直径 %s 未匹配到表，改用面板管径 DN%d。'
                     % ('未知' if elbow['nominal_diameter_mm'] is None
                        else '%.1f mm' % elbow['nominal_diameter_mm'], dn))

    outside = elbow.get('outside_diameter_mm')
    if (not elbow.get('is_duct') and outside is not None
            and abs(outside - layout.od_mm) > 0.5):
        parts.append('注意：弯头外径实测 %.1f mm，与 ASME 表值 %.1f mm 不符，'
                     '垫板内弧按表值贴合，可能需人工复核。'
                     % (outside, layout.od_mm))

    if panel_multiplier is None:
        base_mm = (elbow['outside_diameter_mm'] if elbow.get('is_duct')
                   else geom.nominal_mm(dn))
        base_name = '风管外径' if elbow.get('is_duct') else '公称'
        ratio = elbow['center_to_end_mm'] / base_mm
        parts.append('弯头倍率自动：中心至端面 %.1f mm ÷ %s %.1f mm = %.2fD，'
                     '吸附为 %.1fD%s。'
                     % (elbow['center_to_end_mm'], base_name, base_mm, ratio,
                        multiplier_auto,
                        '' if multiplier_matched else '（非标准弯头，请核对）'))
    else:
        parts.append('弯头倍率取面板值 %.1fD。' % panel_multiplier)

    parts.append('已生成%s：内弧 R%.1f（OD%.1f/2）、外弧 R%.1f（+T%.0f）、'
                 '弯曲 R%.1f、覆盖 %.0f°、周向 %.0f°、气孔 Ø%.0f；垫板材料 %s。'
                 % (layout.number, layout.inner_radius, layout.od_mm,
                    layout.outer_radius, layout.thickness,
                    layout.bend_radius_mm, layout.coverage_deg,
                    layout.alpha_deg, layout.vent_hole_dia,
                    layout.pad_material))
    return ''.join(parts)


# ---------------------------------------------------------------------------
# 面板：显示生成记录与状态（不向控制台打印）
# ---------------------------------------------------------------------------


class _ElbowPadPanel(GlassDialog):
    """点选提示 + 参数输入 + 生成记录 + 状态；同时驱动点选主循环。

    MicroStation 的原生回调里**不做 EC 读取、也不碰 Tk**：只把元素 ID 放进
    ``pending``、把提示放进 ``_pending_status``。真正的读取 EC 与建模都在主循环
    ``PyCadInputQueue.PythonMainLoop()`` 返回之后调用 :meth:`_run_pending` 完成。
    """

    STATE_KEY = 'ElbowPad'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        # 点选到 HVAC 圆风管弯头时记下外径 / 尺寸文字，供面板预览与编号使用。
        self._duct_preview = None

        self._dn = tk.StringVar()
        self._multiplier = tk.StringVar()
        self._coverage = tk.StringVar(value='%.0f' % DEFAULT_COVERAGE_DEG)
        self._alpha = tk.StringVar(value='%.0f' % DEFAULT_ALPHA_DEG)
        self._material = tk.StringVar()
        self._dn_by_label = {}
        self._material_by_label = {}
        self._info_text = tk.StringVar(value='—')

        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.close_panel)
        try:
            self.minsize(440, 720)
        except tk.TclError:
            pass
        self._refresh_info()
        _log('panel built file=%s' % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点选一个 OpenPlant 90° 弯头，在其背弧生成弯头弧形垫板；右键退出')
        form.columnconfigure(0, weight=1)

        hint_frame, hint_text = self._text_field(form, height=3)
        hint_frame.grid(row=0, column=0, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一个 OpenPlant 90° 弯头：垫板将贴附焊接在弯头**背弧'
            '（外弯侧）**外壁上，居中于弯头 45° 中点，沿弯曲方向覆盖 75°。'
            '管径与弯头倍率自动从弯头 EC 属性（公称直径 / 中心至端面长度）读取；'
            '倍率可用下拉覆盖。可连续点选，右键退出。'))

        ttk.Label(form, text='垫板参数', style='Section.TLabel').grid(
            row=1, column=0, sticky='w', pady=(6, 2))

        # 管径（兜底）
        dn_row = tk.Frame(form, bg=CARD)
        dn_row.grid(row=2, column=0, sticky='w')
        tk.Label(dn_row, text='公称直径', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        dn_labels = []
        for key in geom.dn_choices():
            label = geom.dn_label(key)
            dn_labels.append(label)
            self._dn_by_label[label] = key
        self._dn_combo = ttk.Combobox(
            dn_row, textvariable=self._dn, state='readonly', width=22,
            style='Glass.TCombobox', values=dn_labels)
        self._dn_combo.pack(side='left', padx=(10, 0))
        self._dn_combo.bind('<<ComboboxSelected>>', self._on_param_changed)
        tk.Label(dn_row, text='（读不到弯头管径时兜底）', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(8, 0))

        # 弯头倍率
        mul_row = tk.Frame(form, bg=CARD)
        mul_row.grid(row=3, column=0, sticky='w', pady=(6, 0))
        tk.Label(mul_row, text='弯头倍率', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        mul_labels = [AUTO_MULTIPLIER_LABEL]
        for value in geom.multiplier_choices():
            mul_labels.append(geom.multiplier_label(value))
        self._mul_combo = ttk.Combobox(
            mul_row, textvariable=self._multiplier, state='readonly', width=22,
            style='Glass.TCombobox', values=mul_labels)
        self._mul_combo.pack(side='left', padx=(10, 0))
        self._mul_combo.bind('<<ComboboxSelected>>', self._on_param_changed)

        # 覆盖角与截面张角 α
        num_row = tk.Frame(form, bg=CARD)
        num_row.grid(row=4, column=0, sticky='w', pady=(6, 0))
        tk.Label(num_row, text='覆盖角', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        self._coverage_entry = self._entry(num_row, self._coverage, width=7)
        self._coverage_entry.pack(side='left', padx=(10, 4), ipady=3)
        tk.Label(num_row, text='°', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        tk.Label(num_row, text='张角 α', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(16, 0))
        self._alpha_entry = self._entry(num_row, self._alpha, width=7)
        self._alpha_entry.pack(side='left', padx=(10, 4), ipady=3)
        tk.Label(num_row, text='°', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        for var in (self._coverage, self._alpha):
            var.trace_add('write', lambda *_a: self._refresh_info())

        # 材料代码
        mat_row = tk.Frame(form, bg=CARD)
        mat_row.grid(row=5, column=0, sticky='w', pady=(6, 0))
        tk.Label(mat_row, text='材料代码', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        mat_labels = []
        for code, label in geom.material_choices():
            mat_labels.append(label)
            self._material_by_label[label] = code
        self._material_combo = ttk.Combobox(
            mat_row, textvariable=self._material, state='readonly', width=34,
            style='Glass.TCombobox', values=mat_labels)
        self._material_combo.pack(side='left', padx=(10, 0))
        self._material_combo.bind('<<ComboboxSelected>>', self._on_param_changed)

        self._note_label = tk.Label(
            form, text='截面周向张角 α 缺省 120°（与 Y2 弧形垫板一致）；'
                       '沿弯头弯曲方向覆盖 75°、居中于 45° 中点。'
                       '弯头倍率缺省自动（按中心至端面 ÷ 公称直径）。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left', wraplength=400)
        self._note_label.grid(row=6, column=0, sticky='w', pady=(4, 0))

        # 只读信息
        info_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                              highlightthickness=1)
        info_frame.grid(row=7, column=0, sticky='ew', pady=(8, 0))
        tk.Label(info_frame, textvariable=self._info_text, bg=CARD_SOFT, fg=INK,
                 font=UI_FONT_SMALL, justify='left', wraplength=400,
                 anchor='w').pack(fill='x', padx=10, pady=7)

        ttk.Label(form, text='生成记录', style='Section.TLabel').grid(
            row=8, column=0, sticky='w', pady=(8, 2))
        log_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.grid(row=9, column=0, sticky='nsew')
        form.rowconfigure(9, weight=1)
        self._log_view = tk.Text(
            log_frame, height=14, width=38, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=6, cursor='arrow')
        log_bar = SlimScrollbar(log_frame, command=self._log_view.yview,
                                trough=CARD_SOFT)
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side='left', fill='both', expand=True)
        log_bar.pack(side='right', fill='y')
        self._log_view.configure(state='disabled')

        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=10, column=0, sticky='ew', pady=(6, 0))
        self._set_text(self._status_text, '请在模型中点选一个 90° 弯头。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=11, column=0, sticky='ew', pady=(8, 0))
        self.clear_button = RoundButton(
            buttons, '清空记录', self.clear_log, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button = RoundButton(
            buttons, '退出', self.close_panel, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button.pack(side='right')
        self.clear_button.pack(side='right', padx=(0, 8))

    def _entry(self, parent, variable, width=9):
        return tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT,
            fg=INK, bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')

    def _text_field(self, parent, height=3):
        frame = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
        text = tk.Text(
            frame, height=height, width=38, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=5, cursor='arrow', takefocus=0)
        bar = SlimScrollbar(frame, command=text.yview, trough=CARD_SOFT)
        text.configure(yscrollcommand=bar.set)
        text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        text.configure(state='disabled')
        return frame, text

    def _set_text(self, text_widget, value):
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', value or '')
            text_widget.configure(state='disabled')
            text_widget.yview_moveto(0.0)
        except tk.TclError:
            pass

    # -- 面板输入 ----------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = None
        fallback = None
        for label, key in self._dn_by_label.items():
            if fallback is None or key == DEFAULT_DN:
                fallback = label
            if key == state.get('dn'):
                selected = label
        self._dn.set(selected or fallback)

        value = state.get('multiplier')
        if isinstance(value, str) and value.strip():
            self._multiplier.set(value)
        else:
            self._multiplier.set(AUTO_MULTIPLIER_LABEL)

        mat_selected = None
        mat_fallback = None
        for label, code in self._material_by_label.items():
            if mat_fallback is None or code == DEFAULT_MATERIAL_CODE:
                mat_fallback = label
            if code == state.get('material'):
                mat_selected = label
        self._material.set(mat_selected or mat_fallback)

        value = state.get('coverage')
        if isinstance(value, str) and value.strip():
            self._coverage.set(value)
        value = state.get('alpha')
        if isinstance(value, str) and value.strip():
            self._alpha.set(value)

    def persist_state(self, state):
        try:
            state['dn'] = self.current_dn()
            state['multiplier'] = self._multiplier.get()
            state['material'] = self.current_material()
            state['coverage'] = self._coverage.get()
            state['alpha'] = self._alpha.get()
        except Exception:
            pass

    def _on_param_changed(self, _event=None):
        self._refresh_info()

    def current_dn(self):
        return self._dn_by_label.get(self._dn.get(), DEFAULT_DN)

    def current_material(self):
        return self._material_by_label.get(self._material.get(),
                                           DEFAULT_MATERIAL_CODE)

    def current_multiplier(self):
        """返回面板倍率；``None`` 表示自动（按所选弯头实测）。"""
        text = (self._multiplier.get() or '').strip()
        if not text or text == AUTO_MULTIPLIER_LABEL:
            return None
        if text.endswith('D'):
            text = text[:-1]
        try:
            value = float(text)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def current_coverage(self):
        try:
            value = float((self._coverage.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_COVERAGE_DEG
        return value if math.isfinite(value) else DEFAULT_COVERAGE_DEG

    def current_alpha(self):
        try:
            value = float((self._alpha.get() or '').strip())
        except (TypeError, ValueError):
            return DEFAULT_ALPHA_DEG
        return value if math.isfinite(value) else DEFAULT_ALPHA_DEG

    def _refresh_info(self):
        multiplier = self.current_multiplier()
        duct = self._duct_preview
        duct_text = ('风管：按实际外径 %s 贴合，倍率基准 = 风管外径。'
                     % duct['size_label']) if duct else ''
        if multiplier is None:
            text = ('弯头倍率：自动（点选弯头后按「中心至端面 ÷ 公称直径」计算）。\n'
                    '管径：点选弯头后自动读取，读不到时用上面兜底 DN%d。' % DEFAULT_DN)
        else:
            try:
                layout = geom.build_layout(
                    self.current_dn(), multiplier, self.current_material(),
                    self.current_alpha(), self.current_coverage(),
                    od_override_mm=duct['od_mm'] if duct else None,
                    size_label=duct['size_label'] if duct else None)
                text = ('%s\n弯曲 R %.1f · 覆盖 %.0f° · 周向 %.0f° · 板厚 T %.0f · '
                        '气孔 Ø%.0f · 约 %.2f kg'
                        % (layout.number, layout.bend_radius_mm,
                           layout.coverage_deg, layout.alpha_deg,
                           layout.thickness, layout.vent_hole_dia,
                           geom.plate_mass_kg(layout)))
            except Exception as error:
                text = '参数无效：%s' % error
        if duct_text:
            text += '\n' + duct_text
        try:
            self._info_text.set(text)
        except tk.TclError:
            pass

    # -- 输出（只在主循环 / Tk 上下文里调用） ------------------------------

    def _apply_status(self, message, is_error=False):
        self._set_text(getattr(self, '_status_text', None), message)

    def append_log(self, message):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.insert('end', str(message) + '\n\n')
            text_widget.see('end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    def clear_log(self):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    # -- 原生回调入口：只写普通 Python 状态，绝不碰 Tk / EC ---------------

    def set_status(self, message, is_error=False):
        self._pending_status = message
        self._pending_status_is_error = bool(is_error)

    def queue_pick(self, element_id):
        self.pending.append(element_id)

    def close_panel(self):
        self._close_requested = True

    # -- 主循环 ------------------------------------------------------------

    def _run_pending(self):
        """在 ``PythonMainLoop`` 返回之后执行：安全读取 EC 并建模。"""
        self._drain_pending()
        if self._pending_status is not None:
            message = self._pending_status
            is_error = self._pending_status_is_error
            self._pending_status = None
            self._pending_status_is_error = False
            self._apply_status(message, is_error)

    def _drain_pending(self):
        pending, self.pending = self.pending, []
        for element_id in pending:
            self._process(element_id)

    def _process(self, element_id):
        # 这里已不在工具回调内（PythonMainLoop 返回之后），可安全读取 EC。
        try:
            elbow = read_selected_elbow(element_id)
        except Exception as error:
            _log_exception('read elbow failed')
            self.set_status('读取弯头失败：%s' % error, True)
            return

        # 风管不查表：内弧/板厚全部由实际外径定，DN 不参与计算。
        is_duct = bool(elbow.get('is_duct'))
        dn_from_model = elbow['dn'] is not None
        dn = None if is_duct else (elbow['dn'] if dn_from_model
                                   else self.current_dn())
        base_mm = elbow.get('od_basis_mm')          # 风管：实际外径；管道：None
        size_label = elbow.get('size_label')
        self._duct_preview = ({'od_mm': base_mm, 'size_label': size_label}
                              if base_mm else None)
        panel_multiplier = self.current_multiplier()
        multiplier_auto = None
        multiplier_matched = True
        try:
            if panel_multiplier is None:
                multiplier_auto, multiplier_matched = (
                    geom.multiplier_from_center_to_end(
                        dn, elbow['center_to_end_mm'], base_mm=base_mm))
                multiplier = multiplier_auto
            else:
                multiplier = panel_multiplier
            cell, layout = build_pad(
                elbow, dn, multiplier, self.current_material(),
                self.current_alpha(), self.current_coverage(),
                base_mm=base_mm, size_label=size_label)
        except Exception as error:
            _log_exception('build elbow pad failed')
            self.set_status('生成失败：%s' % error, True)
            return

        message = _compose_message(elbow, layout, dn, dn_from_model,
                                   multiplier_auto, multiplier_matched,
                                   panel_multiplier)
        self.append_log(message)
        self.set_status('已生成一块弯头弧形垫板。继续点选 90° 弯头，右键退出。')

    # -- 收尾 --------------------------------------------------------------

    def _finish_tool(self):
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    def run_dialog_loop(self):
        """Tk 主循环：UI 事件 + MicroStation；EC 读取放在 PythonMainLoop 之后。"""
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            if self._close_requested:
                self._close_requested = False
                self._finish_tool()
                break
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception:
                _log_exception('PythonMainLoop failed')
                break
            self._run_pending()


# ---------------------------------------------------------------------------
# 交互工具：点选弯头（只入队，EC 读取在面板循环里）
# ---------------------------------------------------------------------------


class ElbowPadTool(DgnElementSetTool):
    """点选一个 OpenPlant 90° 弯头，在其背弧生成弯头弧形垫板。

    ``_OnPostLocate`` 只记元素 ID；``_OnDataButton`` 只把元素 ID 交给面板排队并
    消费点击——**回调内不做任何 EC 读取**。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('ElbowPadTool')

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
        if self.panel is not None:
            self.panel.set_status('请点选一个 OpenPlant 90° 弯头；右键退出。')

    def _OnPostLocate(self, path, cant_accept_reason):
        """只记下定位到的元素 ID（不保存句柄、不读属性）。"""
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = _read_element_id(handle)
            return self._located_id is not None
        except Exception:
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        """把元素 ID 入队；返回 True 消费本次点击。"""
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            self.panel.set_status(
                '没有定位到元素：请把光标放在弯头上再点击。', True)
            return True
        self.panel.queue_pick(element_id)
        return True

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.close_panel()
        return True

    def _OnRestartTool(self):
        # 保留面板引用重装工具，从而可以连续点取。
        panel = self.panel
        self.panel = None
        ElbowPadTool.InstallNewInstance(self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = ElbowPadTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_pad_panel():
    """打开面板；已在运行时把已有窗口提到前台，避免重复窗口残留。"""
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel.winfo_exists():
                _active_panel.lift()
                return None
        except tk.TclError:
            pass
    panel = _ElbowPadPanel()
    _active_panel = panel
    try:
        return ElbowPadTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


# ---------------------------------------------------------------------------
# 清单导出 / 键入命令
# ---------------------------------------------------------------------------


def export_bom_json(output_path=None):
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '弯头垫板_bom.json')
    return psb.export_combined_bom(output_path)


def export_elbow_pad_bom():
    _reload_runtime_modules()
    return export_bom_json()


_COMMANDS_LOADED = False


def RegisterKeyins():
    """注册键入命令 PYELBOWPAD PLACE / PYELBOWPAD EXPORT。"""
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(GEOM_DIR, '弯头垫板.commands.xml')
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(os.path.abspath(__file__)), WString(command_xml))
    _COMMANDS_LOADED = True


def OpenElbowPad():
    PyMain()


def ExportElbowPadBom():
    export_elbow_pad_bom()


def PyMain():
    _reload_runtime_modules()
    try:
        RegisterKeyins()
    except Exception:
        _log_exception('register keyins failed')
    try:
        _log('PyMain: entry')
        return show_pad_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('elbow pad tool start failed')
        print('弯头垫板启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '弯头垫板启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None


if __name__ == '__main__':
    PyMain()