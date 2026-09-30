"""Generate C# regression fixtures from the original Python's pure geometry; no Bentley import."""
import importlib.util
import json
from pathlib import Path
root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("handrail_test", root / "普通钢结构围栏" / "_geometry_selftest.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
g = module._load_geometry_namespace()
paths = [
    [(0,0,0),(5000,0,0)],
    [(0,0,0),(3000,0,0),(3000,3000,0)],
    [(0,0,0),(3000,0,0),(3000,-3000,0)],
    [(0,0,0),(3000,0,1000)],
    [(100,200,300),(3100,200,1300),(6100,200,1300)],
    [(0,0,0),(2500,0,0),(3500,1000,0),(6000,1000,0)],
    [(0,0,0),(5000,0,-1000)],
]
cases=[]
for path in paths:
    for side in [1,-1]:
        for reverse in [False,True]:
            raw=list(reversed(path)) if reverse else path
            origin=raw[0]
            local=[tuple(q[i]-origin[i] for i in range(3)) for q in raw]
            shifted=g['_offset_path_points'](local,side,-34.2)
            pieces,corners,length=g['_build_fillet_path'](shifted)
            stations=g['_build_post_stations'](length,corners)
            nodes=[]
            for station in stations:
                point,tangent=g['_point_tangent_at_station'](pieces,station)
                node1=g['_type1_connection_geometry'](point,tangent,side)
                node2=g['_type2_connection_geometry'](point,tangent,side,120)
                nodes.append(dict(point=point,tangent=tangent,bottom=node1['post_bottom'],plate1=node1['plate_center'],
                                  plate2=node2['plate_center'],elbow=node2['elbow_end'],tube=node2['tube_end']))
            kick=g['_offset_kickplate_pieces'](pieces,side,37.15)
            cases.append(dict(vertices=path,side=side,reverse=reverse,length=length,stations=stations,nodes=nodes,
                kickStarts=[x['start'] for x in kick],kickEnds=[x['end'] for x in kick],
                kickRadii=[x.get('radius',0) for x in kick]))
Path(__file__).with_name('reference.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(cases)} original Python reference cases generated.')
