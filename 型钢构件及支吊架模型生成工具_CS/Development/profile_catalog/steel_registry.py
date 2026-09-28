"""Local, development-only registry for the C# profile resource exporter."""

from collections import OrderedDict, namedtuple

from . import steel_channel_data, steel_channel_geometry
from . import steel_ibeam_data, steel_ibeam_geometry
from . import steel_hbeam_data, steel_hbeam_geometry
from . import steel_tapered_channel_data, steel_tapered_channel_geometry
from . import steel_equal_angle_data, steel_equal_angle_geometry
from . import steel_unequal_angle_data, steel_unequal_angle_geometry
from . import steel_hk_data

Family = namedtuple("Family", "identifier label data geometry builder")
_FAMILIES = OrderedDict((
    ("parallel_channel", Family("parallel_channel", "平行腿槽钢",
        steel_channel_data, steel_channel_geometry, "build_channel_geometry")),
    ("ordinary_ibeam", Family("ordinary_ibeam", "普通热轧工字钢",
        steel_ibeam_data, steel_ibeam_geometry, "build_ibeam_geometry")),
    ("hot_rolled_h", Family("hot_rolled_h", "热轧 H 型钢",
        steel_hbeam_data, steel_hbeam_geometry, "build_hbeam_geometry")),
    ("tapered_channel", Family("tapered_channel", "斜腿槽钢",
        steel_tapered_channel_data, steel_tapered_channel_geometry, "build_tapered_channel_geometry")),
    ("equal_angle", Family("equal_angle", "等边角钢",
        steel_equal_angle_data, steel_equal_angle_geometry, "build_equal_angle_geometry")),
    ("unequal_angle", Family("unequal_angle", "不等边角钢",
        steel_unequal_angle_data, steel_unequal_angle_geometry, "build_unequal_angle_geometry")),
    ("hk_section", Family("hk_section", "HK 系列 H 型钢",
        steel_hk_data, steel_hbeam_geometry, "build_hbeam_geometry")),
))


def family_ids():
    return tuple(_FAMILIES)


def get_family(identifier):
    return _FAMILIES[identifier]


def profile_names(identifier):
    return tuple(get_family(identifier).data.profile_names())


def get_section(identifier, profile_name):
    return get_family(identifier).data.get_section(profile_name)


def insertion_modes(identifier):
    return tuple(get_family(identifier).geometry.INSERTION_MODES)
