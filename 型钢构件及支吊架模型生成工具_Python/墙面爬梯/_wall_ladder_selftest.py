# -*- coding: utf-8 -*-
"""不依赖 Bentley 运行时的墙面爬梯几何自检。

覆盖：立柱扁钢按支架跨距选型、横担分层（最低 400、间距 250～300）、
支架分层、正交基与构件布局（横担外伸 10、立柱中心距墙 220）。
"""

import ast
from math import ceil, cos, floor, hypot, pi, sin
from pathlib import Path


SOURCE = Path(__file__).with_name("wall_ladder.py")
FUNCTIONS = {
    "select_stile_flat",
    "compute_rung_levels",
    "compute_bracket_levels",
    "compute_cage_hoop_rungs",
    "build_cage_hoop_path",
    "build_cage_top_path",
    "_cage_segment_length",
    "cage_path_length",
    "cage_point_at",
    "cage_station_points",
    "build_cage_layout",
    "build_frame",
    "build_ladder_layout",
}
CONSTANTS = {
    "RUNG_DIAMETER",
    "STANDOFF_FROM_WALL",
    "LADDER_WIDTH",
    "RUNG_PROTRUSION",
    "FIRST_RUNG_HEIGHT",
    "RUNG_MIN_SPACING",
    "RUNG_MAX_SPACING",
    "TOP_RUNG_CLEARANCE",
    "TOP_EXTENSION",
    "BRACKET_SPACING",
    "BRACKET_ANGLE_LEG",
    "BRACKET_ANGLE_THICKNESS",
    "WALL_PLATE_WIDTH",
    "WALL_PLATE_HEIGHT",
    "WALL_PLATE_THICKNESS",
    "STILE_FLAT_TABLE",
    "CAGE_ENABLED",
    "CAGE_HALF_WIDTH",
    "CAGE_HOOK_N_INWARD",
    "CAGE_STRAIGHT_END_OFFSET",
    "CAGE_TAB_INWARD",
    "CAGE_HOOP_FIRST_Z",
    "CAGE_HOOP_SPACING",
    "CAGE_HOOP_FLAT_WIDTH",
    "CAGE_HOOP_FLAT_THICKNESS",
    "CAGE_BAR_COUNT",
    "CAGE_BAR_FLAT_WIDTH",
    "CAGE_BAR_FLAT_THICKNESS",
    "CAGE_TOP_HOOK",
    "CAGE_TOP_HOOK_N",
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
        "floor": floor,
        "hypot": hypot,
        "pi": pi,
        "sin": sin,
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


def main():
    geometry = _load_geometry_namespace()
    select = geometry["select_stile_flat"]
    rung_levels = geometry["compute_rung_levels"]
    bracket_levels = geometry["compute_bracket_levels"]
    build_frame = geometry["build_frame"]
    build_layout = geometry["build_ladder_layout"]

    # --- 立柱扁钢选型 ------------------------------------------------------
    assert select(4400.0) == (75.0, 12.0)
    assert select(4500.0) == (75.0, 12.0)
    assert select(4500.5) == (75.0, 16.0)
    assert select(5500.0) == (75.0, 16.0)
    assert select(5500.5) == (75.0, 20.0)
    assert select(6000.0) == (75.0, 20.0)
    try:
        select(6000.5)
    except ValueError:
        pass
    else:
        raise AssertionError("超过 6000 应被拒绝")

    # --- 横担分层（顶节低于立柱顶端 TOP_RUNG_CLEARANCE）---------------------
    clearance = geometry["TOP_RUNG_CLEARANCE"]
    _near(clearance, 50.0)
    assert rung_levels(400.0) == []           # 顶端以下放不下最低横担
    assert rung_levels(450.0) == [400.0]      # 最低横担恰好 50 低于顶端
    levels = rung_levels(1000.0)
    _near(levels[0], 400.0)
    _near(levels[-1], 1000.0 - clearance)     # 顶节 = 顶端 - 50
    assert len(levels) == 3
    assert all(b > a for a, b in zip(levels, levels[1:]))

    minimum = geometry["RUNG_MIN_SPACING"]
    maximum = geometry["RUNG_MAX_SPACING"]
    for height in range(400, 8001, 25):
        levels = rung_levels(float(height))
        if not levels:
            continue
        assert levels[0] == 400.0
        assert levels[-1] <= height - clearance + 1.0e-6
        if len(levels) >= 2:
            assert abs(levels[-1] - (height - clearance)) <= 1.0e-6, (height, levels[-1])
        assert all(b > a for a, b in zip(levels, levels[1:]))
        for spacing in (b - a for a, b in zip(levels, levels[1:])):
            # 首选 ≥250；短爬梯存在无解区间时允许越界，但越界已被最小化。
            assert minimum - 70.0 <= spacing <= maximum + 70.0, (height, spacing)

    # 绝大多数高度应严格落在 [250, 300] 内。
    in_range = 0
    total = 0
    for height in range(900, 8001, 50):
        levels = rung_levels(float(height))
        for spacing in (b - a for a, b in zip(levels, levels[1:])):
            total += 1
            if minimum - 1.0e-6 <= spacing <= maximum + 1.0e-6:
                in_range += 1
    assert in_range >= int(total * 0.9), (in_range, total)

    # --- 支架分层（两端不设中间支架）---------------------------------------
    assert bracket_levels(0.0, 1500.0) == []
    assert bracket_levels(1000.0, 1500.0) == []
    assert bracket_levels(1500.0, 1500.0) == []
    assert bracket_levels(3000.0, 1500.0) == [1500.0]
    assert bracket_levels(3200.0, 1500.0) == [1500.0, 3000.0]
    assert bracket_levels(4000.0, 1500.0) == [1500.0, 3000.0]

    # --- 正交基 ------------------------------------------------------------
    n, t, _z = build_frame((1.0, 0.0))
    _near(n[0], 1.0)
    _near(n[1], 0.0)
    _near(t[0], 0.0)
    _near(t[1], 1.0)
    # n × t 必须等于 +z。
    cx, cy, cz = _cross(n, t)
    _near(cx, 0.0)
    _near(cy, 0.0)
    _near(cz, 1.0)

    n45, t45, _ = build_frame((1.0, 1.0))
    _near(hypot(n45[0], n45[1]), 1.0)
    cx, cy, cz = _cross(n45, t45)
    _near(cx, 0.0)
    _near(cy, 0.0)
    _near(cz, 1.0)

    # --- 布局：立柱、横担、支架、外伸（先关护笼，单看爬梯）-----------------
    layout = build_layout(4000.0, cage_enabled=False)
    assert layout["cage"] is None
    assert layout["stile_flat"] == (75.0, 12.0)
    _near(layout["width"], 400.0)
    _near(layout["standoff"], 220.0)
    # 横担长度 = 中心距 + 立柱厚 + 2×外伸 = 400 + 12 + 20
    _near(layout["rung_length"], 432.0)

    boxes = [item for item in layout["primitives"] if item["type"] == "box"]
    rungs = [item for item in layout["primitives"] if item["type"] == "cylinder"]

    # 立柱比攀爬高度（4000）高出 TOP_EXTENSION（1200），即 5200。
    stiles = [item for item in boxes if item["size"][2] == 5200.0]
    assert len(stiles) == 2
    for stile in stiles:
        _near(stile["center"][0], 220.0)
        assert abs(abs(stile["center"][1]) - 200.0) <= 1.0e-6
        _near(stile["center"][2], 2600.0)
        _near(stile["size"][0], 75.0)
        _near(stile["size"][1], 12.0)
    # 立柱延长段没有踏步：最顶踏步仍低于平台（height）。
    assert max(layout["rung_levels"]) < 4000.0

    assert len(rungs) == len(layout["rung_levels"]) == 13
    for rung in rungs:
        assert rung["axis"] == "t"
        _near(rung["center"][0], 220.0)
        _near(rung["center"][1], 0.0)
        _near(rung["length"], 432.0)
        _near(rung["diameter"], 24.0)
    # 外伸量 = 横担半长 − (中心距/2 + 立柱厚/2) = 10
    protrusion = layout["rung_length"] / 2.0 - (400.0 / 2.0 + 12.0 / 2.0)
    _near(protrusion, 10.0)

    # 支架：中间 2 层（1500、3000），每层每立柱 1 个角钢（2 段）+ 1 块贴板。
    assert layout["bracket_levels"] == [1500.0, 3000.0]
    angle_leg = geometry["BRACKET_ANGLE_LEG"]
    angle_thickness = geometry["BRACKET_ANGLE_THICKNESS"]
    _near(angle_leg, 75.0)
    _near(angle_thickness, 10.0)
    assert len(boxes) == 2 + 2 * 2 * 3

    # 竖肢背靠背贴立柱外侧面：其内侧面 t = 立柱外侧面。
    stile_t = 12.0
    stile_out_edge = 200.0 + stile_t / 2.0
    back_to_back = [
        item for item in boxes
        if abs(item["size"][1] - angle_thickness) <= 1.0e-6
        and abs(item["size"][2] - angle_leg) <= 1.0e-6
    ]
    assert len(back_to_back) == 4  # 2 层 × 2 立柱
    for item in back_to_back:
        _near(abs(item["center"][1]), stile_out_edge + angle_thickness / 2.0)
    # 角钢长度到立柱前缘：墙面 → 立柱中心 + 半个立柱宽。
    angle_length = 220.0 + 75.0 / 2.0
    for item in back_to_back:
        _near(item["size"][0], angle_length)
        _near(item["center"][0], angle_length / 2.0)

    # 贴墙钢板：100x100，位于墙面处，中心与 75 角钢截面中心对齐。
    plates = [
        item for item in boxes
        if abs(item["size"][0] - geometry["WALL_PLATE_THICKNESS"]) <= 1.0e-6
    ]
    assert len(plates) == 4
    for plate in plates:
        _near(plate["center"][0], geometry["WALL_PLATE_THICKNESS"] / 2.0)
        _near(plate["size"][1], geometry["WALL_PLATE_WIDTH"])
        _near(plate["size"][2], geometry["WALL_PLATE_HEIGHT"])
        _near(abs(plate["center"][1]), stile_out_edge + angle_leg / 2.0)

    # 高爬梯自动换更厚的扁钢。
    assert build_layout(5000.0, cage_enabled=False)["stile_flat"] == (75.0, 16.0)
    assert build_layout(5800.0, cage_enabled=False)["stile_flat"] == (75.0, 20.0)
    # 显式覆盖。
    assert build_layout(4000.0, cage_enabled=False,
                        stile_flat=(75.0, 20.0))["stile_flat"] == (75.0, 20.0)

    # --- 防护围栏（护笼）---------------------------------------------------
    compute_cage = geometry["compute_cage_hoop_rungs"]
    cage_path = geometry["build_cage_hoop_path"]
    cage_stations = geometry["cage_station_points"]
    cage_layout = geometry["build_cage_layout"]
    cage_length = geometry["cage_path_length"]

    # 环吸附到最近的踏步；相邻环间距不超过最大值；取更远的踏步以减少环数。
    rungs = [500.0, 800.0, 1100.0, 1400.0, 1700.0, 2000.0,
             2300.0, 2600.0, 2900.0, 3200.0, 3500.0]
    assert compute_cage([], 2000.0, 1500.0) == []
    assert compute_cage(rungs, 2000.0, 1500.0) == [2000.0, 3500.0]
    # 最近踏步略低于 2000 时，应吸附到它。
    assert compute_cage(rungs, 1950.0, 1500.0)[0] == 2000.0
    assert compute_cage(rungs, 2050.0, 1500.0)[0] == 2000.0
    assert compute_cage(rungs, 2400.0, 1500.0)[0] == 2300.0
    for spacing in (b - a for a, b in zip(
            compute_cage(rungs, 2000.0, 1500.0),
            compute_cage(rungs, 2000.0, 1500.0)[1:])):
        assert spacing <= 1500.0 + 1.0e-6

    # 11 点路径：默认 (220,200)→(220,140)→(115,140)→(115,355)→(630,355)
    # →圆头(985,0)→对称回位。
    path = cage_path(400.0)
    _near(path["half_width"], 355.0)
    _near(path["near_n"], 220.0)
    _near(path["n_hook"], 115.0)       # 220 - 105
    _near(path["curve_n"], 630.0)      # 220 + 410
    _near(path["t_tab"], 140.0)        # 200 - 60

    segments = path["segments"]
    assert len(segments) == 10
    expected_points = [
        ((220.0, 200.0), (220.0, 140.0)),
        ((220.0, 140.0), (115.0, 140.0)),
        ((115.0, 140.0), (115.0, 355.0)),
        ((115.0, 355.0), (630.0, 355.0)),
    ]
    for segment, (start, end) in zip(segments[:4], expected_points):
        _near(segment["start"][0], start[0])
        _near(segment["start"][1], start[1])
        _near(segment["end"][0], end[0])
        _near(segment["end"][1], end[1])

    arcs = [segment for segment in segments if segment["type"] == "arc"]
    assert len(arcs) == 2
    _near(arcs[0]["center"][0], 630.0)
    _near(arcs[0]["center"][1], 0.0)
    _near(arcs[0]["radius"], 355.0)
    _near(arcs[0]["start_angle"], 90.0)
    _near(arcs[1]["end_angle"], -90.0)
    # 圆头顶点 = 弧心 + 半径。
    _near(arcs[1]["center"][0] + arcs[1]["radius"], 985.0)
    _near(arcs[1]["center"][1], 0.0)
    _near(segments[-1]["end"][0], 220.0)
    _near(segments[-1]["end"][1], -200.0)

    # 路径长度：6 条直线 + 半圆（半径 355）。
    straight = 60.0 + 105.0 + 215.0 + 515.0 + 515.0 + 215.0 + 105.0 + 60.0
    expected_length = straight + pi * 355.0
    _near(cage_length(segments), expected_length)

    stations = cage_stations(segments, 11)
    assert len(stations) == 11
    station_t = sorted(station[1] for station in stations)
    for value in station_t:
        assert -355.0 - 1.0e-6 <= value <= 355.0 + 1.0e-6
    for index in range(5):   # 关于 t=0 对称
        _near(station_t[index], -station_t[10 - index])

    # 不带延长段：只有吸附踏步的环。
    cage = cage_layout(400.0, rungs, 24.0, 4000.0, top_extension_mm=0.0)
    assert cage["hoop_rungs"] == [2000.0, 3500.0]
    # 环中心 = 踏步 − 踏步半径 − 半个环宽；环顶贴踏步底面。
    _near(cage["hoop_levels"][0], 2000.0 - 12.0 - 25.0)
    _near(cage["hoop_levels"][1], 3500.0 - 12.0 - 25.0)
    sweeps = [item for item in cage["primitives"] if item["type"] == "sweep"]
    cage_bars = [item for item in cage["primitives"] if item["type"] == "box"]
    assert len(sweeps) == 2       # 每环一个扫掠体
    assert len(cage_bars) == 11   # 1 段 × 11 竖杆（无延长段 → 无倒 L）

    for sweep in sweeps:
        _near(sweep["flat_width"], 50.0)
        _near(sweep["flat_thickness"], 5.0)
    for bar in cage_bars:
        _near(bar["size"][0], 5.0)     # 径向厚
        _near(bar["size"][1], 30.0)    # 沿路径宽
        _near(bar["size"][2], 1500.0)  # 竖向跨两环

    # 带 1.2 m 延长段：最顶环并入 9 点路径（倒 L + 顶环一根扁钢）。
    extended = cage_layout(400.0, rungs, 24.0, 4000.0, top_extension_mm=1200.0)
    assert extended["hoop_levels"][-1] == 4000.0 + 1200.0 - 25.0
    for a, b in zip(extended["hoop_levels"], extended["hoop_levels"][1:]):
        assert b - a <= 1500.0 + 1.0e-6
    assert len(extended["hoop_levels"]) == 4   # 1963 / 3463 / 4963 / 5175
    ext_sweeps = [item for item in extended["primitives"] if item["type"] == "sweep"]
    ext_3d = [item for item in extended["primitives"] if item["type"] == "sweep3d"]
    ext_bars = [item for item in extended["primitives"] if item["type"] == "box"]
    assert len(ext_sweeps) == 3      # 顶环已并入 9 点路径
    assert len(ext_3d) == 1
    assert len(ext_bars) == 33       # 3 段 × 11 竖杆
    for sweep in ext_sweeps + ext_3d:
        _near(sweep["flat_width"], 50.0)
        _near(sweep["flat_thickness"], 5.0)

    # 9 点路径（倒 L + 顶环）：8 段 = 6 直线 + 2 圆弧，坐标逐点校验。
    top_path = geometry["build_cage_top_path"](400.0, 4000.0)
    top_segments = top_path["segments"]
    assert len(top_segments) == 8
    top_lines = [seg for seg in top_segments if seg["type"] == "line"]
    assert len(top_lines) == 6
    expected_top = [
        ((-700.0, -355.0, 4000.0), (-700.0, -355.0, 5200.0)),
        ((-700.0, -355.0, 5200.0), (115.0, -355.0, 5175.0)),
        ((115.0, -355.0, 5175.0), (630.0, -355.0, 5175.0)),
        ((630.0, 355.0, 5175.0), (115.0, 355.0, 5175.0)),
        ((115.0, 355.0, 5175.0), (-700.0, 355.0, 5200.0)),
        ((-700.0, 355.0, 5200.0), (-700.0, 355.0, 4000.0)),
    ]
    for segment, (start, end) in zip(top_lines, expected_top):
        for index in range(3):
            _near(segment["start"][index], start[index])
            _near(segment["end"][index], end[index])
    top_arcs = [seg for seg in top_segments if seg["type"] == "arc"]
    assert len(top_arcs) == 2
    _near(top_arcs[0]["center"][0], 630.0)
    _near(top_arcs[0]["center"][2], 5175.0)
    _near(top_arcs[0]["radius"], 355.0)
    _near(top_arcs[1]["center"][0] + top_arcs[1]["radius"], 985.0)   # 圆头顶点
    _near(top_arcs[1]["center"][2], 5175.0)

    # 开护笼后，布局里应同时包含普通扫掠与 3D 扫掠；且分界两侧分别是爬梯/护笼构件。
    full = build_layout(4000.0)
    assert full["cage"] is not None
    assert any(item["type"] == "sweep" for item in full["primitives"])
    assert any(item["type"] == "sweep3d" for item in full["primitives"])
    split = full["ladder_primitive_count"]
    assert 0 < split < len(full["primitives"])
    assert all(item["type"] in ("box", "cylinder")
               for item in full["primitives"][:split])          # 分界前＝爬梯
    assert any(item["type"] in ("sweep", "sweep3d")
               for item in full["primitives"][split:])          # 分界后＝护笼

    print("wall_ladder geometry self-test: OK")


if __name__ == "__main__":
    main()
