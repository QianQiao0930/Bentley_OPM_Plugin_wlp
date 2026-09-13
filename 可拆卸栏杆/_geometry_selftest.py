# -*- coding: utf-8 -*-
"""不依赖 Bentley 运行时的可拆卸栏杆几何自检。

覆盖：路径圆角、按 50 mm 模数与 1800 mm 上限的立柱排布（两端均设柱）、
套管 / 立杆 / 定位环的可拆卸节点几何。
"""

import ast
from math import acos, ceil, cos, floor, hypot, pi, sin, tan
from pathlib import Path


SOURCE = Path(__file__).with_name("removable_handrail.py")
FUNCTIONS = {
    "_cross",
    "_point_on_segment",
    "_segments_intersect",
    "_horizontal_unit",
    "_horizontal_normal",
    "_clean_and_validate_points",
    "_build_fillet_path",
    "_point_tangent_at_station",
    "_merge_stations",
    "_end_first_span_order",
    "_build_modular_span_lengths",
    "_build_post_stations",
    "_socket_geometry",
    "_steel_inventory",
    "_offset_kickplate_pieces",
    "_extend_offset_path",
}
CONSTANTS = {
    "PATH_TOLERANCE_MM",
    "CORNER_RADIUS",
    "CORNER_POST_NOMINAL",
    "POST_SPACING_MAX",
    "MODULE",
    "TOP_RAIL_Z",
    "KNEE_RAIL_Z",
    "TOP_RAIL_OD",
    "TOP_RAIL_WALL",
    "KNEE_RAIL_OD",
    "KNEE_RAIL_WALL",
    "STANCHION_OD",
    "STANCHION_WALL",
    "STANCHION_BORE_CLEARANCE",
    "SLEEVE_OD",
    "SLEEVE_WALL",
    "SLEEVE_LENGTH",
    "STANCHION_INSERT",
    "COLLAR_OD",
    "COLLAR_THICKNESS",
    "KICKPLATE_HEIGHT",
    "KICKPLATE_THICKNESS",
    "KICKPLATE_BOTTOM_Z",
    "KICKPLATE_END_EXTENSION",
}


def _load_geometry_namespace():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCTIONS:
            selected.append(node)
        elif isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & CONSTANTS:
                selected.append(node)
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "acos": acos,
        "ceil": ceil,
        "cos": cos,
        "floor": floor,
        "hypot": hypot,
        "pi": pi,
        "sin": sin,
        "tan": tan,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def _near(actual, expected, tolerance=1.0e-6):
    assert abs(actual - expected) <= tolerance, (actual, expected)


def main():
    geometry = _load_geometry_namespace()
    socket = geometry["_socket_geometry"]
    stations = geometry["_build_post_stations"]
    modular = geometry["_build_modular_span_lengths"]
    build = geometry["_build_fillet_path"]
    offset = geometry["_offset_kickplate_pieces"]
    extend = geometry["_extend_offset_path"]
    steel = geometry["_steel_inventory"]

    # 立杆外径必须能插入套管，定位环外径大于立杆、厚度为正。
    _near(
        geometry["SLEEVE_OD"] - 2.0 * geometry["SLEEVE_WALL"] - geometry["STANCHION_OD"],
        3.0,
    )
    _near(geometry["STANCHION_BORE_CLEARANCE"], 1.5)
    assert geometry["COLLAR_OD"] > geometry["STANCHION_OD"]
    assert geometry["STANCHION_INSERT"] <= geometry["SLEEVE_LENGTH"] + 1.0e-6
    _near(geometry["COLLAR_THICKNESS"], 10.0)

    # 模数分配：总额闭合、跨距不超上限、最多一个非模数尾数。
    assert modular(5000.0, 1800.0) == [1650.0, 1650.0, 1700.0]
    assert modular(1800.0, 1800.0) == [1800.0]
    assert modular(5400.0, 1800.0) == [1800.0, 1800.0, 1800.0]
    for sample in (1800.1, 3600.0, 5000.0, 7000.0, 12345.67):
        lengths = modular(sample, 1800.0)
        _near(sum(lengths), sample)
        assert max(lengths) <= 1800.0 + 1.0e-6
        non_modular = [
            length for length in lengths
            if abs(length / 50.0 - round(length / 50.0)) > 1.0e-6
        ]
        assert len(non_modular) <= 1, lengths

    # 端部退让为 0：立柱落在路径两端，跨距合规。
    post_values = stations(6000.0, [], 1800.0)
    _near(post_values[0], 0.0)
    _near(post_values[-1], 6000.0)
    assert max(b - a for a, b in zip(post_values, post_values[1:])) <= 1800.0 + 1.0e-6

    # 转角路径仍能正常排柱。
    pieces, corners, length = build([
        (0.0, 0.0, 0.0),
        (3000.0, 0.0, 0.0),
        (3000.0, 3000.0, 0.0),
    ])
    assert len(corners) == 1
    _near(corners[0]["tangent_distance"], 140.0)
    corner_stations = stations(length, corners, 1800.0)
    assert corner_stations
    assert max(b - a for a, b in zip(corner_stations, corner_stations[1:])) <= 1800.0 + 1.0e-6

    # 可拆卸节点：定位环 10 mm 厚、上边缘与线段平齐；套管 150 长、顶面比
    # 线段低 10（让定位环坐在套管口，避免相碰）；立杆自线段向上为栏杆高度、
    # 向下插入套管。
    point = (100.0, 200.0, 500.0)
    tangent = (1.0, 0.0, 0.0)
    node = socket(point, tangent)
    _near(node["line_z"], 500.0)
    _near(node["sleeve_end"][2], 490.0)
    _near(node["sleeve_start"][2], 340.0)
    _near(node["sleeve_end"][2] - node["sleeve_start"][2], geometry["SLEEVE_LENGTH"])
    _near(node["sleeve_end"][2], node["collar_start"][2])
    _near(node["collar_end"][2], point[2])
    _near(node["collar_end"][2] - node["collar_start"][2], geometry["COLLAR_THICKNESS"])
    _near(node["stanchion_start"][2], 350.0)
    _near(node["stanchion_end"][2], 500.0 + geometry["TOP_RAIL_Z"])
    for key in ("sleeve_start", "sleeve_end", "stanchion_start", "stanchion_end",
                "collar_start", "collar_end"):
        _near(node[key][0], point[0])
        _near(node[key][1], point[1])

    # 坡段仍保持竖直立杆与水平套管。
    slope = socket((100.0, 200.0, 500.0), (3.0, 4.0, 2.0))
    _near(slope["sleeve_end"][2], 490.0)
    _near(slope["collar_end"][2], 500.0)
    _near(slope["stanchion_end"][2], 500.0 + geometry["TOP_RAIL_Z"])

    # 插入深度超过套管长度时拒绝。
    original = geometry["STANCHION_INSERT"]
    geometry["STANCHION_INSERT"] = geometry["SLEEVE_LENGTH"] + 10.0
    try:
        socket(point, tangent)
    except ValueError:
        pass
    else:
        raise AssertionError("插入深度超过套管长度应被拒绝")
    finally:
        geometry["STANCHION_INSERT"] = original

    # 挡板：内侧面与立杆外圆相切（偏移 = 立杆半径 + 板厚/2），底边高于线段 10，
    # 首末各外伸 25，总长比线段长 50。
    _near(geometry["KICKPLATE_HEIGHT"], 130.0)
    _near(geometry["KICKPLATE_BOTTOM_Z"], 10.0)
    straight = build([(0.0, 0.0, 0.0), (5000.0, 0.0, 0.0)])[0]
    center_offset = (
        geometry["STANCHION_OD"] / 2.0 + geometry["KICKPLATE_THICKNESS"] / 2.0
    )
    _near(
        center_offset - geometry["KICKPLATE_THICKNESS"] / 2.0,
        geometry["STANCHION_OD"] / 2.0,
    )
    inside = offset(straight, 1.0, center_offset)
    assert len(inside) == 1
    _near(inside[0]["start"][1], center_offset)
    _near(inside[0]["end"][1], center_offset)
    outside = offset(straight, -1.0, center_offset)
    _near(outside[0]["start"][1], -center_offset)
    extended = extend(inside, geometry["KICKPLATE_END_EXTENSION"])
    _near(extended[0]["start"][0], -geometry["KICKPLATE_END_EXTENSION"])
    _near(extended[0]["end"][0], 5000.0 + geometry["KICKPLATE_END_EXTENSION"])
    _near(
        extended[0]["end"][0] - extended[0]["start"][0],
        5000.0 + 2.0 * geometry["KICKPLATE_END_EXTENSION"],
    )

    # 钢材清单：管类按中心线实长、挡板按路径+50，按单元分组。
    post_values = stations(5000.0, [], 1800.0)
    inventory = steel(straight, len(post_values), 5000.0)
    assert all(item["host"] in ("socket", "panel") for item in inventory)
    sleeve = [item for item in inventory if item["code"] == "Sleeve"]
    assert len(sleeve) == 1
    assert sleeve[0]["host"] == "socket"
    _near(sleeve[0]["length"], geometry["SLEEVE_LENGTH"])
    assert sleeve[0]["quantity"] == len(post_values)
    stanchion = [item for item in inventory if item["code"] == "Stanchion"][0]
    _near(stanchion["length"], geometry["STANCHION_INSERT"] + geometry["TOP_RAIL_Z"])
    rails = [item for item in inventory if item["code"] in ("TopRail", "KneeRail")]
    assert len(rails) == 2
    for rail in rails:
        _near(rail["length"], 5000.0)
    kickplate = [item for item in inventory if item["code"] == "Kickplate"][0]
    _near(kickplate["length"], 5000.0 + 2.0 * geometry["KICKPLATE_END_EXTENSION"])

    print("removable_handrail geometry self-test: OK")


if __name__ == "__main__":
    main()
