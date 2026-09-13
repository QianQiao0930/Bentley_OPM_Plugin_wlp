# -*- coding: utf-8 -*-
"""不依赖 Bentley 运行时的轻便消防水龙柜几何 / 器材清单自检。

覆盖：柜体布局、卷盘与灭火器排布、棱柱截面顶点、15S202 第 53 页
《主要器材表》8 项、BomJson 解析与跨柜合计。
"""

import ast
import json
import math
from math import cos, pi, sin, sqrt
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape as _xml_escape


SOURCE = Path(__file__).with_name("轻便消防水龙柜.py")
FUNCTIONS = {
    "_cross",
    "_normalized",
    "_perpendicular_basis",
    "_cylinder_profile_points",
    "_cabinet_layout",
    "_reel_layout",
    "_extinguisher_layout",
    "_max_extinguisher_count",
    "_extinguisher_fit_error",
    "_supply_layout",
    "_build_bom_rows",
    "_parse_bom_rows",
    "_aggregate_bom_materials",
    "_validate_dimensions",
    "_safe_name",
    "_item_type_name",
    "_xlsx_column_name",
    "_xlsx_cell",
    "_xlsx_sheet_xml",
}
CONSTANTS = {
    "DEFAULT_WIDTH",
    "DEFAULT_DEPTH",
    "DEFAULT_HEIGHT",
    "DEFAULT_LOWER_HEIGHT",
    "WALL_THICKNESS",
    "REEL_DIAMETER",
    "REEL_WIDTH",
    "REEL_HUB_DIAMETER",
    "REEL_FLANGE_THICKNESS",
    "REEL_CENTER_FROM_LEFT",
    "REEL_CENTER_FROM_TOP",
    "REEL_BACK_CLEARANCE",
    "DEFAULT_EXTINGUISHER_MODEL",
    "DEFAULT_EXTINGUISHER_QUANTITY",
    "EXTINGUISHER_DIAMETER",
    "EXTINGUISHER_HEIGHT",
    "EXTINGUISHER_BOTTOM_GAP",
    "SUPPLY_PIPE_RADIUS",
    "SUPPLY_PIPE_OUTSIDE",
    "SUPPLY_PIPE_FROM_FRONT",
    "SUPPLY_PIPE_FROM_DIVIDER",
    "SUPPLY_PIPE_INNER_FROM_LEFT",
    "VALVE_FROM_LEFT",
    "PRISM_SIDES",
    "ITEM_TYPE_PREFIX",
    "STANDARD",
}


def _load_geometry_namespace():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            selected.append(node)
        elif isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & CONSTANTS:
                selected.append(node)
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "json": json,
        "math": math,
        "cos": cos,
        "sin": sin,
        "pi": pi,
        "sqrt": sqrt,
        "_xml_escape": _xml_escape,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def _near(actual, expected, tolerance=1.0e-6):
    assert abs(actual - expected) <= tolerance, (actual, expected)


def main():
    geometry = _load_geometry_namespace()
    layout = geometry["_cabinet_layout"]
    reel = geometry["_reel_layout"]
    bottles = geometry["_extinguisher_layout"]
    supply = geometry["_supply_layout"]
    profile = geometry["_cylinder_profile_points"]
    rows_fn = geometry["_build_bom_rows"]
    parse = geometry["_parse_bom_rows"]
    aggregate = geometry["_aggregate_bom_materials"]
    validate = geometry["_validate_dimensions"]
    item_type_name = geometry["_item_type_name"]

    width = geometry["DEFAULT_WIDTH"]
    depth = geometry["DEFAULT_DEPTH"]
    height = geometry["DEFAULT_HEIGHT"]
    lower = geometry["DEFAULT_LOWER_HEIGHT"]
    assert (width, depth, height, lower) == (550.0, 160.0, 1200.0, 550.0)

    # 柜体布局：对称、正进深、正高度。
    local = layout(width, depth, height, lower)
    _near(local["left"], -275.0)
    _near(local["right"], 275.0)
    _near(local["front"], 0.0)
    _near(local["rear"], 160.0)
    _near(local["top"], 1200.0)
    _near(local["divider_z"], 550.0)

    # 卷盘：P380 位于距左 200、距顶 200，宽 120，不越出柜体。
    reel_layout = reel(local)
    _near(reel_layout["radius"], 190.0)
    _near(reel_layout["hub_radius"], 45.0)
    _near(reel_layout["center_x"], local["left"] + 200.0)
    _near(reel_layout["center_z"], local["top"] - 200.0)
    _near(reel_layout["y_back"] - reel_layout["y_front"], geometry["REEL_WIDTH"])
    assert reel_layout["center_x"] - reel_layout["radius"] >= local["left"]
    assert reel_layout["center_x"] + reel_layout["radius"] <= local["right"]
    assert reel_layout["center_z"] + reel_layout["radius"] <= local["top"]
    assert reel_layout["y_back"] <= local["rear"]
    assert reel_layout["y_front"] > local["front"]

    # 灭火器：数量由输入决定，默认 2 具，均布且不越界、不重叠。
    bottle_list = bottles(local)
    assert len(bottle_list) == geometry["DEFAULT_EXTINGUISHER_QUANTITY"] == 2
    for bottle in bottle_list:
        _near(bottle["radius"], geometry["EXTINGUISHER_DIAMETER"] / 2.0)
        assert bottle["bottom_z"] >= local["bottom"]
        assert bottle["top_z"] <= local["divider_z"], "瓶体不得穿出隔板"
        assert bottle["center_x"] - bottle["radius"] >= local["left"]
        assert bottle["center_x"] + bottle["radius"] <= local["right"]
    centers = [bottle["center_x"] for bottle in bottle_list]
    assert centers == sorted(centers)
    for first, second in zip(centers, centers[1:]):
        assert second - first >= geometry["EXTINGUISHER_DIAMETER"], "相邻灭火器应留有间隙"
    assert len(bottles(local, count=1)) == 1
    assert bottles(local, count=0) == []

    # 灭火器数量校验：默认柜宽最多 3 具，超出报错。
    max_count = geometry["_max_extinguisher_count"]
    fit_error = geometry["_extinguisher_fit_error"]
    assert max_count(550.0) == 3
    assert fit_error(550.0, 3) is None
    assert fit_error(550.0, 4) is not None
    assert fit_error(550.0, -1) is not None
    assert fit_error(550.0, "abc") is not None

    # 卷盘给水管：DN25，位于隔板上方 100（图集 I-I），自柜体左侧伸出。
    supply_layout = supply(local)
    _near(supply_layout["z"],
          local["divider_z"] + geometry["SUPPLY_PIPE_FROM_DIVIDER"])
    _near(supply_layout["z"] - local["divider_z"], 100.0)
    _near(supply_layout["y"], local["front"] + geometry["SUPPLY_PIPE_FROM_FRONT"])
    _near(supply_layout["outer_x"],
          local["left"] - geometry["SUPPLY_PIPE_OUTSIDE"])
    _near(supply_layout["inner_x"],
          local["left"] + geometry["SUPPLY_PIPE_INNER_FROM_LEFT"])
    _near(supply_layout["length"],
          geometry["SUPPLY_PIPE_INNER_FROM_LEFT"] + geometry["SUPPLY_PIPE_OUTSIDE"])
    _near(supply_layout["valve_x"], local["left"] + geometry["VALVE_FROM_LEFT"])
    _near(supply_layout["radius"], 17.0)
    assert supply_layout["z"] < reel_layout["center_z"], "给水管应低于卷盘中心"
    assert supply_layout["outer_x"] < local["left"], "给水管应伸出柜体外"

    # 棱柱截面：圆度、顶点数、各点位于同一平面且与轴线垂直。
    radius = 25.0
    points = profile((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), radius, 16)
    assert len(points) == 16
    first_basis, second_basis = geometry["_perpendicular_basis"]((0.0, 0.0, 1.0))
    for x, y, z in points:
        _near(z, 0.0, 1.0e-9)
        _near(sqrt(x * x + y * y), radius, 1.0e-9)
    dot_first = sum(points[0][axis] * first_basis[axis] for axis in range(3))
    dot_second = sum(points[0][axis] * second_basis[axis] for axis in range(3))
    _near(dot_first, radius)
    _near(dot_second, 0.0)
    axis_points = profile((5.0, 7.0, 9.0), (0.0, 1.0, 0.0), radius, 8)
    for x, y, z in axis_points:
        _near(y, 7.0, 1.0e-9)
        _near(sqrt((x - 5.0) ** 2 + (z - 9.0) ** 2), radius, 1.0e-9)

    # 《主要器材表》8 项 + 用户灭火器：编号连续、规格随尺寸/型号生成。
    rows = rows_fn(1200.0, 550.0, 160.0)
    assert len(rows) == 9
    assert [row["no"] for row in rows] == list(range(1, 10))
    assert all(row["qty"] == 1 for row in rows[:8])
    assert rows[0]["spec"] == u"1200×550×160"
    assert rows[0]["unit"] == u"个"
    assert rows[1]["spec"] == u"P380"
    assert rows[2]["spec"] == u"LQG16-30"
    assert rows[6]["spec"] == u"DN25"
    assert rows[8]["code"] == "Extinguisher"
    assert rows[8]["spec"] == geometry["DEFAULT_EXTINGUISHER_MODEL"]
    assert rows[8]["qty"] == geometry["DEFAULT_EXTINGUISHER_QUANTITY"] == 2
    assert rows[8]["unit"] == u"具"
    codes = [row["code"] for row in rows]
    assert len(set(codes)) == 9
    # 数量为 0 时不生成灭火器行。
    assert len(rows_fn(1200.0, 550.0, 160.0, u"MFZ/ABC4", 0)) == 8
    # 自定义型号与数量进入器材表。
    custom = rows_fn(1200.0, 550.0, 160.0, u"MT7", 3)
    assert custom[8]["spec"] == u"MT7" and custom[8]["qty"] == 3

    # BomJson 往返解析（保留 code，供灭火器回退统计识别）。
    assert parse("") == []
    assert parse("not json") == []
    round_trip = parse(json.dumps(rows, ensure_ascii=False))
    assert round_trip == [{key: row[key] for key in
                           ("no", "code", "name", "material", "spec", "unit", "qty")}
                          for row in rows]
    assert round_trip[8]["code"] == "Extinguisher"
    legacy = parse(json.dumps([{"no": 1, "name": u"轻便消防水龙柜", "material": u"钢",
                                "spec": u"550×160×1200", "unit": u"个", "qty": 1}],
                              ensure_ascii=False))
    assert legacy[0]["code"] == ""

    # 跨柜合计：2 套时每项数量为 2 × 单柜数量。
    summary = aggregate([(rows, 2), (rows_fn(1200.0, 550.0, 160.0), 1)])
    assert len(summary) == 9
    assert [item["no"] for item in summary] == list(range(1, 10))
    for item in summary:
        per_set = 1 if item["no"] != 9 else 2
        assert item["qtyPerSet"] == per_set
        assert item["totalQty"] == per_set * 3

    # 尺寸校验：默认合格；越界与过小应被拒绝。
    assert validate(550.0, 160.0, 1200.0, 550.0) is None
    assert validate(0.0, 160.0, 1200.0, 550.0) is not None
    assert validate(550.0, 2.0, 1200.0, 550.0) is not None
    assert validate(550.0, 160.0, 1200.0, 2.0) is not None
    assert validate("abc", 160.0, 1200.0, 550.0) is not None

    # ItemType 名称：ASCII、含灭火器型号与数量、可稳定复现。
    assert geometry["_safe_name"]("MFZ/ABC4") == "MFZ_ABC4"
    assert item_type_name(550.0, 160.0, 1200.0, "MFZ/ABC4", 2) == \
        "LightHoseCabinet_15S202_550x160x1200_MFZ_ABC4x2"

    # Excel 工作表：列名进位正确，内联字符串不夹带多余字符、可被 XML 解析。
    column_name = geometry["_xlsx_column_name"]
    assert column_name(1) == "A"
    assert column_name(26) == "Z"
    assert column_name(27) == "AA"
    sheet_xml = geometry["_xlsx_sheet_xml"](
        [["标题"], ["轻便消防水龙柜", 8, 1.5], ["<A&B>", None]], {2})
    root = ElementTree.fromstring(sheet_xml)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    cells = root.findall(".//%sc" % namespace)
    texts = [element.text for element in root.iter("%st" % namespace)]
    assert texts == ["标题", "轻便消防水龙柜", "<A&B>"]
    assert all(text is not None for text in texts)
    assert any(cell.get("s") == "2" for cell in cells)

    print("light_hose_cabinet geometry self-test: OK")


if __name__ == "__main__":
    main()
