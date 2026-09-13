"""Unified registry for every steel-section family handled by this plug-in.

To add a future family, add its data module and geometry module, then add one
``FamilyDefinition`` below.  The selector and placement tool obtain all their
behaviour through this registry.
"""

from __future__ import division

from collections import OrderedDict, namedtuple

import steel_channel_data
import steel_channel_geometry
import steel_equal_angle_data
import steel_equal_angle_geometry
import steel_hbeam_data
import steel_hbeam_geometry
import steel_hk_data
import steel_ibeam_data
import steel_ibeam_geometry
import steel_tapered_channel_data
import steel_tapered_channel_geometry
import steel_unequal_angle_data
import steel_unequal_angle_geometry


FamilyDefinition = namedtuple(
    "FamilyDefinition",
    "identifier label description available data geometry builder converter_mode fields",
)


_FAMILIES = OrderedDict((
    (
        "parallel_channel",
        FamilyDefinition(
            "parallel_channel",
            "平行腿槽钢",
            "现有槽钢数据；腹板与翼缘平行，包含两处根部圆角。",
            True,
            steel_channel_data,
            steel_channel_geometry,
            "build_channel_geometry",
            "standard",
            (
                ("H", "高度 H", "mm"), ("B", "宽度 B", "mm"),
                ("tw", "腹板厚度 tw", "mm"), ("tf", "翼缘厚度 tf", "mm"),
                ("r", "根部圆角 r", "mm"), ("Z0", "重心距 Z0", "mm"),
            ),
        ),
    ),
    (
        "ordinary_ibeam",
        FamilyDefinition(
            "ordinary_ibeam",
            "普通热轧工字钢",
            "GB/T 706 普通工字钢；翼缘坡度 1:6，包含 r1/r2 真圆弧。",
            True,
            steel_ibeam_data,
            steel_ibeam_geometry,
            "build_ibeam_geometry",
            "standard",
            (
                ("H", "高度 H", "mm"), ("B", "宽度 B", "mm"),
                ("tw", "腹板厚度 tw", "mm"), ("tf", "翼缘平均厚度 tf", "mm"),
                ("r1", "腹板圆角 r1", "mm"), ("r2", "翼缘端圆角 r2", "mm"),
                ("A", "截面面积 A", "cm²"), ("mass", "理论重量", "kg/m"),
            ),
        ),
    ),
    (
        "hot_rolled_h",
        FamilyDefinition(
            "hot_rolled_h",
            "热轧 H 型钢",
            "平行等厚翼缘 H 型钢；t1 为腹板厚度，t2 为翼缘厚度。",
            True,
            steel_hbeam_data,
            steel_hbeam_geometry,
            "build_hbeam_geometry",
            "event_point_type",
            (
                ("H", "高度 H", "mm"), ("B", "宽度 B", "mm"),
                ("t1", "腹板厚度 t1", "mm"), ("t2", "翼缘厚度 t2", "mm"),
                ("r", "根部圆角 r", "mm"), ("area", "截面面积", "cm²"),
                ("mass", "理论重量", "kg/m"),
            ),
        ),
    ),
    (
        "tapered_channel",
        FamilyDefinition(
            "tapered_channel",
            "斜腿槽钢",
            "GB/T 706 斜腿槽钢；翼缘坡度 1:10，包含 r1/r2 真圆弧。",
            True,
            steel_tapered_channel_data,
            steel_tapered_channel_geometry,
            "build_tapered_channel_geometry",
            "standard",
            (
                ("H", "高度 H", "mm"), ("B", "宽度 B", "mm"),
                ("tw", "腹板厚度 tw", "mm"), ("tf", "翼缘平均厚度 tf", "mm"),
                ("r1", "腹板圆角 r1", "mm"), ("r2", "翼缘端圆角 r2", "mm"),
                ("area", "截面面积", "cm²"), ("mass", "理论重量", "kg/m"),
                ("Z0_cm", "重心距 Z0", "cm"),
            ),
        ),
    ),
    (
        "equal_angle",
        FamilyDefinition(
            "equal_angle",
            "等边角钢",
            "GB/T 等边角钢；r2=t/3，包含一个内圆角 r1 和两个端部圆角 r2。",
            True,
            steel_equal_angle_data,
            steel_equal_angle_geometry,
            "build_equal_angle_geometry",
            "standard",
            (
                ("B", "边长 B", "mm"), ("t", "厚度 t", "mm"),
                ("r1", "内圆角 r1", "mm"), ("r2", "端部圆角 r2", "mm"),
                ("area", "截面面积", "cm²"), ("mass", "理论重量", "kg/m"),
                ("Z0_cm", "重心距 Z′0", "cm"),
            ),
        ),
    ),
    (
        "unequal_angle",
        FamilyDefinition(
            "unequal_angle",
            "不等边角钢",
            "GB/T 不等边角钢；长边 BL 竖向、短边 BS 横向，r2=t/3。",
            True,
            steel_unequal_angle_data,
            steel_unequal_angle_geometry,
            "build_unequal_angle_geometry",
            "standard",
            (
                ("BL", "长边 BL", "mm"), ("BS", "短边 BS", "mm"),
                ("t", "厚度 t", "mm"), ("r1", "内圆角 r1", "mm"),
                ("r2", "端部圆角 r2", "mm"), ("area", "截面面积", "cm²"),
                ("mass", "理论重量", "kg/m"), ("X0_cm", "重心距 X0", "cm"),
                ("Y0_cm", "重心距 Y0", "cm"),
            ),
        ),
    ),
    (
        "hk_section",
        FamilyDefinition(
            "hk_section",
            "HK 系列 H 型钢",
            "HK 平行翼缘型钢；复用热轧 H 型钢的四处根部真圆弧几何。",
            True,
            steel_hk_data,
            steel_hbeam_geometry,
            "build_hbeam_geometry",
            "event_point_type",
            (
                ("H", "高度 H", "mm"), ("B", "宽度 B", "mm"),
                ("t1", "腹板厚度 t1", "mm"), ("t2", "翼缘厚度 t2", "mm"),
                ("r", "根部圆角 r", "mm"), ("area", "截面面积", "cm²"),
                ("mass", "理论重量", "kg/m"),
            ),
        ),
    ),
))


def family_ids(include_future=True):
    if include_future:
        return tuple(_FAMILIES.keys())
    return tuple(identifier for identifier, family in _FAMILIES.items() if family.available)


def family_choices():
    """Return ``(identifier, label, available)`` in selector display order."""
    return tuple((identifier, family.label, family.available) for identifier, family in _FAMILIES.items())


def get_family(identifier):
    try:
        return _FAMILIES[identifier]
    except KeyError:
        raise KeyError("未知型钢型式：{}".format(identifier))


def require_available(identifier):
    family = get_family(identifier)
    if not family.available:
        raise ValueError("{}：{}".format(family.label, family.description))
    return family


def profile_names(identifier):
    return tuple(require_available(identifier).data.profile_names())


def default_profile(identifier):
    return require_available(identifier).data.DEFAULT_PROFILE


def get_section(identifier, profile_name):
    return require_available(identifier).data.get_section(profile_name)


def insertion_modes(identifier):
    return tuple(require_available(identifier).geometry.INSERTION_MODES)


def default_insertion_mode(identifier):
    return insertion_modes(identifier)[0][0]


def detail_rows(identifier, profile_name):
    family = require_available(identifier)
    section = get_section(identifier, profile_name)
    rows = []
    for field, label, unit in family.fields:
        value = section[field]
        rows.append((label, "{:g} {}".format(value, unit)))
    return tuple(rows)


def build_geometry(identifier, section_mm, insertion_mode, model_ref, point):
    """Scale a selected section and build it at the Bentley event point."""
    family = require_available(identifier)
    model_scale = model_ref.GetModelInfo().GetUorPerMeter() / 1000.0
    geometry_module = family.geometry
    section_uor = geometry_module.scale_section(section_mm, model_scale)
    local_point = geometry_module.Point2d(point.x, point.y)
    builder = getattr(geometry_module, family.builder)
    return builder(section_uor, insertion_mode, local_point)


def build_sweep_geometry(identifier, section_mm, insertion_mode, model_ref):
    """Scale a selected section and build it anchored at the local origin.

    Used by the sweep tool, which then maps the flat profile into the frame of
    the selected path before handing it to the solid sweep.
    """
    family = require_available(identifier)
    model_scale = model_ref.GetModelInfo().GetUorPerMeter() / 1000.0
    geometry_module = family.geometry
    section_uor = geometry_module.scale_section(section_mm, model_scale)
    origin = geometry_module.Point2d(0.0, 0.0)
    builder = getattr(geometry_module, family.builder)
    return builder(section_uor, insertion_mode, origin)


def to_bentley_curve_vector(identifier, geometry, point):
    """Convert family geometry into a closed Bentley CurveVector."""
    family = require_available(identifier)
    converter = family.geometry.to_bentley_curve_vector
    if family.converter_mode == "event_point_type":
        return converter(geometry, point.z, point.__class__)
    return converter(geometry, point.z)


def describe(identifier):
    family = get_family(identifier)
    status = "可用" if family.available else "待导入数据"
    return "{}｜{}\n{}".format(family.label, status, family.description)
