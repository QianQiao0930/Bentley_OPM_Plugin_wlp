# -*- coding: utf-8 -*-
"""不依赖 Bentley 运行时的路径圆角及立柱排布自检。"""

import ast
from math import acos, ceil, cos, floor, hypot, pi, sin, tan
from pathlib import Path


SOURCE = Path(__file__).with_name("steel_handrail.py")
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
    "_offset_kickplate_pieces",
    "_type2_connection_geometry",
    "_type1_connection_geometry",
    "_type1_inner_sections",
    "_type3_connection_geometry",
}
CONSTANTS = {
    "PATH_TOLERANCE_MM",
    "CORNER_RADIUS",
    "CORNER_POST_NOMINAL",
    "POST_SPACING_MAX",
    "MODULE",
    "TOP_RAIL_Z",
    "KNEE_RAIL_Z",
    "STANCHION_OD",
    "STANCHION_WALL",
    "KICKPLATE_THICKNESS",
    "KICKPLATE_BOTTOM_Z",
    "KICKPLATE_CLEARANCE",
    "END_CLOSURE_REACH",
    "TYPE2_BEND_RADIUS",
    "TYPE1_PLATE_CENTER_DROP",
    "TYPE1_FLAT_MAJOR",
    "TYPE1_FLAT_MINOR",
    "TYPE1_TRANSITION_LENGTH",
    "TYPE3_PLATE_LENGTH",
    "TYPE3_PLATE_WIDTH",
    "TYPE3_PLATE_THICKNESS",
    "TYPE2_PLATE_HORIZONTAL",
    "TYPE2_PLATE_VERTICAL",
    "TYPE2_PLATE_THICKNESS",
    "TYPE2_TUBE_PLATE_OVERLAP",
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
    # 底板长宽、居中、水平放置和向上拉伸方向；覆盖反向及坡段。
    for tangent in ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (3.0, 4.0, 2.0), (3.0, 4.0, -2.0)):
        point = (100.0, 200.0, 500.0)
        node = geometry["_type3_connection_geometry"](point, tangent)
        corners = node["corners"]
        assert node["post_bottom"] == (100.0, 200.0, 510.0)
        for i in range(3):
            _near(sum(c[i] for c in corners) / 4.0, point[i])
        assert all(c[2] == point[2] for c in corners)
        along = tuple(corners[1][i] - corners[0][i] for i in range(3))
        across = tuple(corners[2][i] - corners[1][i] for i in range(3))
        _near(hypot(*along[:2]), 145.0)
        _near(hypot(*across[:2]), 75.0)
        _near(sum(along[i] * across[i] for i in range(3)), 0.0)
        _near(along[0] * tangent[1] - along[1] * tangent[0], 0.0)
        assert along[0] * across[1] - along[1] * across[0] > 0.0
    # 左右侧、反向和坡段：放样全程保持靠板侧相切，管底落在板边界上。
    for tangent in ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (3.0, 4.0, 2.0), (3.0, 4.0, -2.0)):
        for side in (1.0, -1.0):
            point = (100.0, 200.0, 500.0)
            node = geometry["_type1_connection_geometry"](point, tangent, side)
            normal = node["normal"]
            center = node["plate_center"]
            _near(center[2], 424.0)
            near_face = tuple(center[i] - normal[i] * 5.0 for i in range(3))
            _near(sum((near_face[i] - point[i]) * normal[i] for i in range(3)), 24.15)
            for axis in (node["plate_long"], node["plate_short"]):
                _near(sum(value * value for value in axis), 1.0)
                _near(sum(axis[i] * normal[i] for i in range(3)), 0.0)
            bottom = node["post_bottom"]
            _near(sum((bottom[i] - point[i]) * normal[i] for i in range(3)), 16.1)
            sections = node["sections"]
            assert sections[0] == (point, 24.15, 24.15)
            _near(sections[1][1], 35.0)
            _near(sections[1][2], 8.05)
            _near(sections[1][0][2], point[2] - 38.5)
            assert sections[0][0][2] > sections[1][0][2] > sections[2][0][2]
            # 直纹插值的每个截面都应贴在同一平面上，无穿板或间隙。
            for start, end in zip(sections, sections[1:]):
                for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
                    section_center = tuple(start[0][i] + fraction * (end[0][i] - start[0][i]) for i in range(3))
                    minor = start[2] + fraction * (end[2] - start[2])
                    _near(sum((section_center[i] - point[i]) * normal[i] for i in range(3)) + minor, 24.15)
            inner = geometry["_type1_inner_sections"](sections)
            assert len(inner) == len(sections) + 2
            assert inner[0][0][2] > sections[0][0][2]
            assert inner[-1][0][2] < sections[-1][0][2]
            for outer_section, inner_section in zip(sections, inner[1:-1]):
                assert outer_section[0] == inner_section[0]
                for outer_axis, inner_axis in zip(outer_section[1:], inner_section[1:]):
                    assert inner_axis > 0.0
                    _near(outer_axis - inner_axis, 3.2)
            dz = bottom[2] - center[2]
            edge_ratios = (
                abs(dz * node["plate_long"][2]) / 73.0,
                abs(dz * node["plate_short"][2]) / 37.5,
            )
            _near(max(edge_ratios), 1.0)
            if tangent[2] == 0.0:
                _near(bottom[2], 386.5)
    for parameter, bad_value in (("TYPE1_FLAT_MINOR", 6.4), ("TYPE1_TRANSITION_LENGTH", 0.0), ("TYPE1_TRANSITION_LENGTH", 200.0)):
        original = geometry[parameter]
        geometry[parameter] = bad_value
        try:
            geometry["_type1_connection_geometry"]((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid type1 parameter accepted: " + parameter)
        finally:
            geometry[parameter] = original
    build = geometry["_build_fillet_path"]
    posts = geometry["_build_post_stations"]
    at = geometry["_point_tangent_at_station"]

    _near(geometry["END_CLOSURE_REACH"] - geometry["CORNER_RADIUS"], 160.0)
    _near(
        geometry["TOP_RAIL_Z"]
        - geometry["KNEE_RAIL_Z"]
        - 2.0 * geometry["CORNER_RADIUS"],
        177.0,
    )
    _near(geometry["KICKPLATE_BOTTOM_Z"], 10.0)
    _near(
        geometry["STANCHION_OD"] / 2.0 + geometry["KICKPLATE_CLEARANCE"],
        34.15,
    )

    pieces, corners, length = build([(0.0, 0.0, 0.0), (5000.0, 0.0, 0.0)])
    _near(length, 5000.0)
    assert len(corners) == 0
    assert posts(length, corners) == [0.0, 1650.0, 3300.0, 5000.0]

    modular = geometry["_build_modular_span_lengths"]
    assert modular(5000.0) == [1650.0, 1650.0, 1700.0]
    assert modular(4950.0) == [1650.0, 1650.0, 1650.0]
    assert modular(5999.0) == [2000.0, 1999.0, 2000.0]
    assert modular(3999.0) == [1999.0, 2000.0]
    assert modular(2000.0) == [2000.0]
    for sample in (2000.1, 5000.0, 5999.0, 9999.0, 12345.67):
        lengths = modular(sample)
        _near(sum(lengths), sample)
        assert max(lengths) <= 2000.0 + 1.0e-6
        non_modular = [
            length for length in lengths
            if abs(length / 50.0 - round(length / 50.0)) > 1.0e-6
        ]
        assert len(non_modular) <= 1

    pieces, corners, length = build([
        (0.0, 0.0, 0.0),
        (3000.0, 0.0, 0.0),
        (3000.0, 3000.0, 0.0),
    ])
    assert len(corners) == 1
    _near(corners[0]["tangent_distance"], 140.0)
    _near(corners[0]["length"], pi * 70.0)
    corner_mid, tangent_mid = at(pieces, corners[0]["start_station"] + corners[0]["length"] / 2.0)
    _near(corner_mid[0], 3000.0 - 140.0 + 140.0 / (2.0 ** 0.5))
    _near(corner_mid[1], 140.0 - 140.0 / (2.0 ** 0.5))
    _near(hypot(tangent_mid[0], tangent_mid[1]), 1.0)
    station_values = posts(length, corners)
    assert max(b - a for a, b in zip(station_values, station_values[1:])) <= 2000.0 + 1.0e-6

    center_offset = 48.3 / 2.0 + 10.0 + 6.0 / 2.0
    inside = geometry["_offset_kickplate_pieces"](pieces, 1.0, center_offset)
    outside = geometry["_offset_kickplate_pieces"](pieces, -1.0, center_offset)
    _near(inside[1]["radius"], 140.0 - center_offset)
    _near(outside[1]["radius"], 140.0 + center_offset)
    for offset_path in (inside, outside):
        for first, second in zip(offset_path, offset_path[1:]):
            _near(first["end"][0], second["start"][0])
            _near(first["end"][1], second["start"][1])

    connection = geometry["_type2_connection_geometry"](
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0, 250.0
    )
    assert connection["normal"] == (0.0, 1.0, 0.0)
    assert connection["plate_long"] == (1.0, 0.0, 0.0)
    assert connection["plate_short"] == (0.0, 0.0, -1.0)
    assert connection["elbow_center"] == (0.0, 76.0, 0.0)
    assert connection["elbow_end"] == (0.0, 76.0, -76.0)
    assert connection["plate_center"] == (0.0, 250.0, -76.0)
    assert connection["tube_end"] == (0.0, 247.0, -76.0)

    # 单一坡段按三维实际路径长度排柱，各构件点保留局部高程。
    pieces, corners, length = build([
        (0.0, 0.0, 0.0),
        (3000.0, 0.0, 1000.0),
    ])
    _near(length, hypot(3000.0, 1000.0))
    assert len(corners) == 0
    slope_stations = posts(length, corners)
    assert max(b - a for a, b in zip(slope_stations, slope_stations[1:])) <= 2000.0 + 1.0e-6
    midpoint, slope_tangent = at(pieces, length / 2.0)
    _near(midpoint[0], 1500.0)
    _near(midpoint[2], 500.0)
    _near(hypot(hypot(*slope_tangent[:2]), slope_tangent[2]), 1.0)
    slope_offset = geometry["_offset_kickplate_pieces"](pieces, 1.0, center_offset)
    _near(slope_offset[0]["start"][2], 0.0)
    _near(slope_offset[0]["end"][2], 1000.0)

    # 纯变坡点保留尖折并强制设柱，其站号等于第一坡段的三维实长。
    pieces, corners, length = build([
        (0.0, 0.0, 0.0),
        (3000.0, 0.0, 1000.0),
        (6000.0, 0.0, 1000.0),
    ])
    assert len(corners) == 1
    assert corners[0]["kind"] == "grade_break"
    grade_station = hypot(3000.0, 1000.0)
    _near(corners[0]["station"], grade_station)
    assert any(abs(value - grade_station) <= 1.0e-6 for value in posts(length, corners))

    # 同一节点既在平面内转向又涉及坡段时，不猜测空间弯头造型。
    try:
        build([
            (0.0, 0.0, 0.0),
            (3000.0, 0.0, 1000.0),
            (3000.0, 3000.0, 1000.0),
        ])
    except ValueError as error:
        assert "空间弯头" in str(error)
    else:
        raise AssertionError("同时转向和变坡的节点应被拒绝")

    elevated_connection = geometry["_type2_connection_geometry"](
        (0.0, 0.0, 500.0), (3.0, 0.0, 1.0), 1.0, 250.0
    )
    assert elevated_connection["elbow_center"] == (0.0, 76.0, 500.0)
    assert elevated_connection["elbow_end"] == (0.0, 76.0, 424.0)
    assert elevated_connection["plate_center"] == (0.0, 250.0, 424.0)
    long_axis = elevated_connection["plate_long"]
    short_axis = elevated_connection["plate_short"]
    normal_axis = elevated_connection["normal"]
    _near(long_axis[2] / long_axis[0], 1.0 / 3.0)
    _near(sum(value * value for value in long_axis), 1.0)
    _near(sum(value * value for value in short_axis), 1.0)
    _near(sum(long_axis[i] * short_axis[i] for i in range(3)), 0.0)
    _near(sum(long_axis[i] * normal_axis[i] for i in range(3)), 0.0)
    _near(sum(short_axis[i] * normal_axis[i] for i in range(3)), 0.0)

    try:
        build([(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0)])
    except ValueError:
        pass
    else:
        raise AssertionError("过短转角路径应被拒绝")

    print("steel_handrail geometry self-test: OK")


if __name__ == "__main__":
    main()
