"""Export the cabinet migration fixtures without importing Bentley Python modules.

Development only. The C# runtime reads its own embedded JSON resource.
Usage: python -B Development/export_fire_recipes.py [source.py]
"""
import ast
import hashlib
import json
import math
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT.parent / "灭火器箱" / "灭火器箱（带灭火器模型）.py"
CONSTANTS = {"EXTINGUISHER_SPECS", "RED", "BLACK", "METAL", "WHITE", "LABEL", "BOX_PRESETS",
             "EXTINGUISHER_TYPES", "BOX_CAPACITY_LIMITS", "WALL_THICKNESS", "INTERIOR_GAP", "INTERIOR_WALL_CLEARANCE"}
FUNCTIONS = {"distance", "_ext_capacity_key", "_ext_cell_name", "_hose_points", "_ext_build_recipe", "_interior_recipe_key", "_eligible_box_keys"}
FIELDS = {"kind": "Kind", "name": "Name", "start": "Start", "end": "End", "r0": "StartRadiusMm", "r1": "EndRadiusMm",
          "center": "Center", "size": "Size", "tilt": "TiltDegrees", "radius": "RadiusMm", "fillet": "FilletMm",
          "bottom": "BottomMm", "top": "TopMm", "major": "MajorRadiusMm", "minor": "MinorRadiusMm", "color": "Color", "points": "Points"}
source = SOURCE.read_text(encoding="utf-8-sig")
nodes = [node for node in ast.parse(source).body
         if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS or
         isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in CONSTANTS for target in node.targets)]
namespace = {"math": math}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
recipes = []
for capacity in ("2", "4", "5", "6", "8"):
    recipe = namespace["_ext_build_recipe"](capacity)
    spec = recipe["spec"]
    recipes.append({"Capacity": int(capacity), "Model": spec["model"], "CellName": recipe["name"],
                    "BodyDiameterMm": spec["body_diameter"], "TotalHeightMm": spec["total_height"],
                    "HoseLengthMm": recipe["hose_length"],
                    "Parts": [{FIELDS[key]: value for key, value in part.items()} for part in recipe["parts"]]})
fixtures = []
for kind, options in namespace["EXTINGUISHER_TYPES"].items():
    for capacity in options["capacities"]:
        for box in namespace["_eligible_box_keys"](kind, capacity):
            visual = namespace["_interior_recipe_key"](kind, capacity, box)
            fixtures.append({"Type": kind, "Capacity": capacity, "Box": box, "VisualCapacity": int(visual) if visual else 0})
(PROJECT / "Resources/fire_extinguisher_recipes.json").write_text(json.dumps(recipes, ensure_ascii=False, indent=2), encoding="utf-8")
(PROJECT / "Development/FireCabinetCheck/python_reference.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
print("Source SHA256:", hashlib.sha256(SOURCE.read_bytes()).hexdigest())
print("Exported", len(recipes), "recipes and", len(fixtures), "reference cases.")
