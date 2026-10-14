"""Read only the original Python ladder's pure layout, never import MSPy or create a model."""
import ast
import json
import math
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT.parent / '墙面爬梯/wall_ladder.py'
FUNCTIONS = {'select_stile_flat', 'compute_rung_levels', 'compute_bracket_levels',
             'compute_cage_hoop_rungs', 'build_cage_hoop_path', 'build_cage_top_path',
             '_cage_segment_length', 'cage_path_length', 'cage_point_at', 'cage_station_points',
             'build_cage_layout', 'build_ladder_layout'}


def main():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    env = {name: getattr(math, name) for name in ('ceil', 'cos', 'floor', 'hypot', 'pi', 'sin')}
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = value
        elif isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            selected.append(node)
    assert len(selected) == len(FUNCTIONS)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), env)
    cases = []
    for h, w, gap, first, spacing, cage in [
        (300,400,220,400,1500,True), (450,400,220,400,1500,True),
        (699,400,220,400,1500,True), (700,400,220,400,1500,True),
        (751,400,220,400,1500,False), (1000,500,250,0,450,True),
        (2000,400,220,400,1500,True), (3000,400,220,400,1500,True),
        (4500,400,220,400,1500,True), (4500.01,600,300,500,1200,True),
        (5500,400,220,400,1500,True), (5500.01,400,220,400,1500,True),
        (6000,400,220,400,1500,True), (6000,800,200,600,6000,False),
        (1500,121,106,350,600,True), (2100,829,1000,800,2000,True)]:
        layout = env['build_ladder_layout'](h,width_mm=w,standoff_mm=gap,first_rung_mm=first,bracket_spacing_mm=spacing,cage_enabled=cage)
        cases.append({'Height':h,'Width':w,'Standoff':gap,'First':first,'Spacing':spacing,'Cage':cage,'Layout':layout})
    target = PROJECT / 'Development/WallLadderCheck/python_reference.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Generated {len(cases)} original wall-ladder cases.')


if __name__ == '__main__':
    main()
