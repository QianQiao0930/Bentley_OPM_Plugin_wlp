"""Read only the original gauge's pure layout; no MSPy/Qt import or model write."""
import ast
import json
import math
from pathlib import Path

project = Path(__file__).resolve().parents[1]
source = project.parent / '磁翻板液位计/magnetic_level_gauge.py'
tree = ast.parse(source.read_text(encoding='utf-8-sig'))
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'layout']
assert len(selected) == 1
env = {'math': math}
for n in tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in {'STEEL','DARK','RED','WHITE'}:
        env[n.targets[0].id] = ast.literal_eval(n.value)
exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), env)
cases = [{'L1': l1, 'Parts': env['layout'](l1)} for l1 in (350, 360, 359.999, 360.001, 999, 1000, 1400, 1400.125, 3000, 5999.999, 6000)]
target = project / 'Development/MagneticGaugeCheck/python_reference.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(cases,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
print(f'Generated {len(cases)} original gauge layout cases; default parts: {len(env["layout"](1400))}.')
