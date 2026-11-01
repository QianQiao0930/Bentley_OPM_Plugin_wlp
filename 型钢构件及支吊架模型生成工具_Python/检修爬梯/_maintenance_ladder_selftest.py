# -*- coding: utf-8 -*-
"""不依赖 Bentley 运行时的检修爬梯几何自检。

覆盖：正交基、踏步数量与级高、45° 斜梯爬升几何、平台/立柱/斜梁/踏步尺寸、
脚轮与底架抬升、平台护栏与斜梯扶手的杆高与立柱间距、斜撑端点、构件轴向完备性。
"""

import ast
from math import ceil, cos, hypot, pi, radians, sin, tan
from pathlib import Path


SOURCE = Path(__file__).with_name("maintenance_ladder.py")
FUNCTIONS = {
    "build_frame",
    "compute_step_count",
    "compute_stair_geometry",
    "_add_box",
    "_add_cylinder",
    "_add_brace",
    "_point_on_frame",
    "build_maintenance_ladder_layout",
}
CONSTANTS = {
    "PLATFORM_HEIGHT",
    "PLATFORM_WIDTH",
    "PLATFORM_DEPTH",
    "STAIR_ANGLE_DEG",
    "STEP_TARGET_RISER",
    "TREAD_THICKNESS",
    "LEG_SIZE",
    "BASE_BEAM_SIZE",
    "STRINGER_WIDTH",
    "STRINGER_DEPTH",
    "PLATFORM_FRAME_SIZE",
    "PLATFORM_PLATE_THICKNESS",
    "TOE_HEIGHT",
    "TOE_THICKNESS",
    "RAIL_DIAMETER",
    "RAIL_HEIGHT",
    "RAIL_MID_HEIGHT",
    "STAIR_RAIL_HEIGHT",
    "STAIR_RAIL_MID_HEIGHT",
    "STAIR_POST_SPACING",
    "GUARD_ENABLED",
    "CASTER_ENABLED",
    "CASTER_WHEEL_DIAMETER",
    "CASTER_WHEEL_WIDTH",
    "CASTER_PLATE_SIZE",
    "CASTER_PLATE_THICKNESS",
    "BRACE_ENABLED",
    "BRACE_DIAMETER",
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
        "ceil": ceil,
        "cos": cos,
        "hypot": hypot,
        "pi": pi,
        "radians": radians,
        "sin": sin,
        "tan": tan,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def _near(actual, expected, tolerance=1.0e-6):
    assert abs(actual - expected) <= tolerance, (actual, expected)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _is_unit(vector):
    return abs(hypot(hypot(vector[0], vector[1]), vector[2]) - 1.0) <= 1.0e-9


def _size_of(item):
    return tuple(round(value, 6) for value in item["size"])


def main():
    geometry = _load_geometry_namespace()
    build_frame = geometry["build_frame"]
    step_count = geometry["compute_step_count"]
    stair_geometry = geometry["compute_stair_geometry"]
    build_layout = geometry["build_maintenance_ladder_layout"]

    # --- 正交基 ------------------------------------------------------------
    for outward in ((1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (-2.0, 1.0)):
        n, t, _z = build_frame(outward)
        assert _is_unit(n) and _is_unit(t)
        cx, cy, cz = _cross(n, t)
        _near(cx, 0.0)
        _near(cy, 0.0)
        _near(cz, 1.0)

    # --- 踏步数量 ----------------------------------------------------------
    assert step_count(1875.0, 220.0) == 9
    assert step_count(2000.0, 220.0) == 9
    assert step_count(100.0, 220.0) == 2      # 最少 2 级。
    try:
        step_count(0.0, 220.0)
    except ValueError:
        pass
    else:
        raise AssertionError("零爬升高度应被拒绝。")

    # --- 45° 斜梯派生几何（带脚轮，底架抬高 125）---------------------------
    geo = stair_geometry(2000.0, 1000.0, 1000.0, 45.0, 220.0, 125.0)
    _near(geo["base_z"], 125.0)
    _near(geo["rise"], 1875.0)
    _near(geo["run"], 1875.0)                 # 45°：水平段 = 爬升段。
    _near(geo["angle_rad"], radians(45.0))
    assert geo["step_count"] == 9
    _near(geo["riser"], 1875.0 / 9.0)
    _near(geo["going"], geo["riser"])         # 45°：级高 = 踏面。
    _near(geo["slope_length"], hypot(1875.0, 1875.0))
    _near(geo["total_depth"], 2875.0)
    _near(geo["half_depth"], 1437.5)
    _near(geo["toe_n"], -1437.5)
    _near(geo["platform_front_n"], 437.5)
    _near(geo["platform_back_n"], 1437.5)
    _near(geo["platform_center_n"], 937.5)

    # --- 默认布局（带脚轮 / 护栏 / 斜撑）-----------------------------------
    layout = build_layout()
    body = layout["primitives"]
    count = layout["body_primitive_count"]
    assert 0 < count < len(body)
    assert layout["caster_enabled"] and layout["guard_enabled"] and layout["brace_enabled"]
    _near(layout["base_z"], 125.0)
    _near(layout["stringer_t"], 480.0)
    _near(layout["leg_t"], 480.0)

    boxes = [item for item in body if item["type"] == "box"]
    cylinders = [item for item in body if item["type"] == "cylinder"]

    # 所有构件尺寸为正、所有轴向为单位向量（斜梁/斜撑不能漏归一化）。
    for item in boxes:
        assert all(value > 0.0 for value in item["size"]), item
        for axis in item["axes"]:
            if not isinstance(axis, str):
                assert _is_unit(axis), (axis, item["size"])
    for item in cylinders:
        assert item["length"] > 0.0 and item["diameter"] > 0.0, item
        if not isinstance(item["axis"], str):
            assert _is_unit(item["axis"]), item

    # 4 根立柱：40×40，从底架顶到平台面（高 1875）。
    legs = [item for item in boxes if _size_of(item) == (40.0, 40.0, 1875.0)]
    assert len(legs) == 4, len(legs)
    for leg in legs:
        _near(leg["center"][2], (125.0 + 2000.0) / 2.0)

    # 9 级踏步：宽 920 = 1000 − 2×40，最上一级踏面标高 = 平台面 2000。
    treads = [item for item in boxes
              if _size_of(item)[1] == 920.0 and _size_of(item)[2] == 30.0]
    assert len(treads) == 9, len(treads)
    tops = sorted(item["center"][2] + 15.0 for item in treads)
    _near(tops[-1], 2000.0)
    _near(tops[0], 125.0 + 1875.0 / 9.0)
    deltas = [b - a for a, b in zip(tops, tops[1:])]
    _near(min(deltas), 1875.0 / 9.0)
    _near(max(deltas), 1875.0 / 9.0)

    # 平台花纹板：1000×1000×4，上表面 = 平台面标高。
    plate = [item for item in boxes if _size_of(item) == (1000.0, 1000.0, 4.0)]
    assert len(plate) == 1
    _near(plate[0]["center"][2], 2000.0 - 2.0)

    # 4 个脚轮：φ125×40，轮心离地 = 半径。
    wheels = [item for item in cylinders if abs(item["diameter"] - 125.0) <= 1.0e-6]
    assert len(wheels) == 4, len(wheels)
    for wheel in wheels:
        _near(wheel["length"], 40.0)
        _near(wheel["center"][2], 62.5)

    # 后侧 X 撑 + 左右侧撑 = 4 根 φ20 斜撑。
    braces = [item for item in cylinders if abs(item["diameter"] - 20.0) <= 1.0e-6]
    assert len(braces) == 4, len(braces)

    # 平台后侧顶杆中心 z = 2000 + 1000 = 3000。
    top_rails = [item for item in cylinders
                 if abs(item["center"][2] - 3000.0) <= 1.0e-6]
    assert top_rails, "缺少平台顶杆"
    back_rail = [item for item in top_rails
                 if abs(item["center"][0] - 1417.5) <= 1.0e-6
                 and abs(item["length"] - 1000.0) <= 1.0e-6]
    assert back_rail, "缺少平台后侧顶杆"

    # 平台护栏立柱：长 1000，自平台面 2000 立到顶杆 3000，中心 z = 2500。
    platform_posts = [item for item in cylinders if isinstance(item["axis"], str)
                      and item["axis"] == "z"
                      and abs(item["length"] - 1000.0) <= 1.0e-6
                      and abs(item["diameter"] - 33.5) <= 1.0e-6]
    assert len(platform_posts) == 7, len(platform_posts)
    for post in platform_posts:
        _near(post["center"][2], 2500.0)

    # 斜梯扶手顶杆到斜面的垂直距离 = 扶手高。
    slope_dir = (cos(radians(45.0)), 0.0, sin(radians(45.0)))
    normal = (-sin(radians(45.0)), 0.0, cos(radians(45.0)))
    incline_anchor = (geo["toe_n"], geo["base_z"])
    stair_rails = []
    for item in cylinders:
        if abs(item["diameter"] - 33.5) > 1.0e-6:
            continue
        center = item["center"]
        distance = ((center[0] - incline_anchor[0]) * normal[0]
                    + (center[2] - incline_anchor[1]) * normal[2])
        if abs(item["axis"][2] if not isinstance(item["axis"], str) else 0.0) > 0.5:
            stair_rails.append(distance)
    assert stair_rails, "缺少斜梯扶手"
    assert any(abs(value - 1000.0) <= 1.0e-6 for value in stair_rails), stair_rails
    assert any(abs(value - 500.0) <= 1.0e-6 for value in stair_rails), stair_rails

    # 斜梯扶立柱：run/750 向上取整 + 1 个站位 × 两侧；柱长 = 扶手高 / cos45。
    post_count = max(2, int(ceil(1875.0 / 750.0)) + 1)
    assert post_count == 4
    post_length = 1000.0 / cos(radians(45.0))
    stair_posts = [item for item in cylinders if isinstance(item["axis"], str)
                   and item["axis"] == "z"
                   and abs(item["length"] - post_length) <= 1.0e-6]
    assert len(stair_posts) == 2 * post_count, len(stair_posts)

    # --- 关脚轮：底架落地，45° 全程 run = 2000 -----------------------------
    layout_plain = build_layout(caster_enabled=False, guard_enabled=False,
                                brace_enabled=False)
    plain_geo = layout_plain["geometry"]
    _near(layout_plain["base_z"], 0.0)
    _near(plain_geo["run"], 2000.0)
    _near(plain_geo["total_depth"], 3000.0)
    _near(plain_geo["toe_n"], -1500.0)
    _near(plain_geo["platform_front_n"], 500.0)
    _near(plain_geo["platform_back_n"], 1500.0)
    assert layout_plain["body_primitive_count"] == len(layout_plain["primitives"])
    assert not any(item["type"] == "cylinder" and abs(item["diameter"] - 125.0) <= 1.0e-6
                   for item in layout_plain["primitives"])
    assert not any(item["type"] == "box" and _size_of(item)[2] == 100.0
                   for item in layout_plain["primitives"])

    # --- 非 45°：级高与踏面不再相等 ---------------------------------------
    geo60 = stair_geometry(2000.0, 1000.0, 1000.0, 60.0, 220.0, 0.0)
    _near(geo60["run"], 2000.0 / tan(radians(60.0)))
    assert abs(geo60["riser"] - geo60["going"]) > 1.0

    # --- 参数校验 ----------------------------------------------------------
    for bad in ({"platform_height_mm": 0.0},
                {"platform_width_mm": -1.0},
                {"platform_depth_mm": 0.0},
                {"stair_angle_deg": 90.0},
                {"step_target_riser_mm": 0.0}):
        try:
            build_layout(**bad)
        except ValueError:
            pass
        else:
            raise AssertionError("非法参数应被拒绝：%r" % bad)

    print("maintenance_ladder geometry self-test: OK")


if __name__ == "__main__":
    main()
