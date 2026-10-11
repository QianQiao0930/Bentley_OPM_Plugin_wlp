"""Generate offline migration fixtures without importing Bentley modules.

Development only; the C# add-in never launches this script.
"""
import ast
import hashlib
import json
import math
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT.parent / "轻便消防水龙柜" / "轻便消防水龙柜.py"
CONSTANTS = {
    "EXTINGUISHER_SPECS", "EXTINGUISHER_BAY_CLEARANCE",
    "EXTINGUISHER_MIN_NEIGHBOR_GAP", "WALL_THICKNESS",
    "DEFAULT_EXTINGUISHER_QUANTITY", "RED", "BLACK", "METAL", "WHITE", "LABEL",
}
FUNCTIONS = {
    "_parse_extinguisher_capacity", "_extinguisher_overhang",
    "_extinguisher_neighbor_gap", "_extinguisher_span", "_extinguisher_variant_key",
    "_extinguisher_max_count", "_extinguisher_fit_error", "distance",
    "_ext_capacity_key", "_ext_cell_name", "_hose_points", "_ext_build_recipe",
}
FIELDS = {
    "kind": "Kind", "name": "Name", "start": "Start", "end": "End",
    "r0": "StartRadiusMm", "r1": "EndRadiusMm", "center": "Center",
    "size": "Size", "tilt": "TiltDegrees", "radius": "RadiusMm",
    "fillet": "FilletMm", "bottom": "BottomMm", "top": "TopMm",
    "major": "MajorRadiusMm", "minor": "MinorRadiusMm", "color": "Color",
    "points": "Points",
}


def main():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
    nodes = [node for node in tree.body if
             isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS or
             isinstance(node, ast.Assign) and any(
                 isinstance(target, ast.Name) and target.id in CONSTANTS
                 for target in node.targets)]
    namespace = {"math": math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    recipes = json.loads((PROJECT / "Resources/fire_extinguisher_recipes.json").read_text(encoding="utf-8"))
    for recipe in recipes:
        original = namespace["_ext_build_recipe"](str(recipe["Capacity"]))
        mapped = [{FIELDS[key]: value for key, value in part.items()} for part in original["parts"]]
        # Reuse only after checking every geometric value, not just recipe names.
        assert json.loads(json.dumps(mapped)) == recipe["Parts"], recipe["Model"]
        assert original["spec"]["body_diameter"] == recipe["BodyDiameterMm"]
        assert original["spec"]["total_height"] == recipe["TotalHeightMm"]
    fixtures = []
    for width in (550, 900):
        for model in ("MFZ/ABC2", "MFZ/ABC4", "MFZ/ABC5", "MFZ/ABC6",
                      "MFZ/ABC8", "未知型号", "型号2026-3"):
            for quantity in range(7):
                error = namespace["_extinguisher_fit_error"](width, 160, 550, model, quantity)
                variant = namespace["_extinguisher_variant_key"](model, width, 160, 550, quantity)
                fixtures.append({"Width": width, "Model": model, "Quantity": quantity,
                                 "Valid": error is None,
                                 "VisualCapacity": int(variant or 0) if quantity else 0})
    (PROJECT / "Development/HoseCabinetCheck/python_reference.json").write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Source SHA256:", hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    print("Five shared visual recipes match; generated", len(fixtures), "reference cases.")


if __name__ == "__main__":
    main()
