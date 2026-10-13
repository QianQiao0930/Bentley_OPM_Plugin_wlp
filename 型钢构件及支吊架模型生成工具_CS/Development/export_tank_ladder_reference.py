"""Generate geometry reference cases from the original ladder's selected, read-only logic.

No MSPy import or model writing. Only inspected layout functions are extracted;
native constructors are replaced by recording stubs for coordinates and dimensions.
"""
import ast
import json
import math
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT.parent / "水箱爬梯/ladder_lib.py"
FUNCTIONS = {"create_ladder_frame", "get_leg_vertical_height", "create_ladder_assembly",
             "_build_ladder_leg_curves", "create_ladder_leg_reinforcement", "create_ladder_rung"}


class Curves:
    eBOUNDARY_TYPE_Open = "open"
    eBOUNDARY_TYPE_Outer = "outer"
    eBOUNDARY_TYPE_ParityRegion = "region"

    def __init__(self, boundary):
        self.items = []

    def Add(self, item):
        self.items.append(item)


class Primitive:
    CreateLine = staticmethod(lambda segment: {"Line": segment})
    CreateArc = staticmethod(lambda arc: arc)


class Ellipse:
    FromArcCenterStartEnd = staticmethod(lambda center, start, end: {"ArcCenter": center, "Start": start, "End": end})


def main():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    environment = {"math": math, "CurveVector": Curves, "ICurvePrimitive": Primitive, "DEllipse3d": Ellipse,
                   "DPoint3d": lambda x, y, z: [x, y, z], "DSegment3d": lambda a, b: [a, b],
                   "mm": lambda value, model: value, "_log": lambda message: None}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if isinstance(value, (float, int)):
                environment[node.targets[0].id] = value
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    assert len(selected) == len(FUNCTIONS)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), environment)
    cases = []
    for height, width, spacing in [(90, 420, 900), (100, 420, 900), (299, 420, 900), (300, 420, 900),
                                   (556, 500, 900), (900, 420, 900), (1000, 640, 450), (1800, 420, 900),
                                   (2000, 420, 900), (2700, 500, 900), (4500, 800, 1000), (5000, 1000, 600)]:
        case = {"TankHeightMm": height, "WidthMm": width, "SpacingMm": spacing,
                "Angles": [], "Legs": [], "Supports": [], "Rungs": []}

        def angle(w, t, length, origin, axis, legs):
            case["Angles"].append({"Width": w, "Thickness": t, "Length": length, "Origin": origin, "Axis": axis})
            return object()

        def leg(w, t, top, vertical, radius, origin):
            path, _ = environment["_build_ladder_leg_curves"](w, t, top, vertical, radius, origin, None)
            case["Legs"].append({"Origin": origin, "VerticalHeight": vertical,
                                 "ShortEnd": path.items[0]["Line"][1], "ArcCenter": path.items[1]["ArcCenter"],
                                 "VerticalStart": path.items[1]["End"], "Bottom": path.items[2]["Line"][1]})
            return object()

        def flat(width=60, thickness=10, length=250, origin=(0, 0, 0), extrude="Y"):
            case["Supports"].append({"Origin": origin, "Width": width, "Thickness": thickness, "Length": length})
            return object()

        def round_bar(diameter=18, length=430, center=(0, 0, 0), extrude="X"):
            case["Rungs"].append({"Center": center, "Diameter": diameter, "Length": length})
            return object()

        environment.update(create_angle_steel=angle, create_ladder_leg=leg,
                           create_flat_bar=flat, create_round_bar=round_bar)
        components = environment["create_ladder_assembly"](tank_height=height, spacing=width,
            reinforcement_spacing=spacing, merge_components=False)
        case["ComponentCount"] = len(components)
        case["Legs"].sort(key=lambda item: item["Origin"][0])
        case["Supports"].sort(key=lambda item: (item["Origin"][2], item["Origin"][0]))
        cases.append(case)
    target = PROJECT / "Development/TankLadderCheck/python_reference.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(cases)} original Python layout reference cases.")


if __name__ == "__main__":
    main()
