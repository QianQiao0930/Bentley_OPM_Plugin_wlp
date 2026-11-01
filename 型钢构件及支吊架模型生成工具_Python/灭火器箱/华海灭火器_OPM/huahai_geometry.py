# -*- coding: utf-8 -*-
"""华海灭火器的毫米几何配方；不依赖 build123d 或 Bentley，可离线校验。"""
import json
import math
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('specs.json').read_text(encoding='utf-8'))
SPECS = CATALOG['variants']
RED = (204, 9, 6)
BLACK = (18, 19, 20)
METAL = (166, 168, 173)
WHITE = (237, 240, 227)
LABEL = (245, 242, 224)


def normalize_capacity(value):
    key = str(value).strip().lower()
    for unit in ('公斤', '千克', 'kg'):
        key = key.replace(unit, '')
    key = key.strip()
    if key not in SPECS:
        raise ValueError('请选择 2、4、5、6 或 8 kg。')
    return key


def cell_name(capacity):
    return 'HUAHAI_MF_ABCE%s' % normalize_capacity(capacity)


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def _hose_points(anchors, steps=16):
    """Cubic Hermite interpolation, sampled for native circular-section lofting."""
    tangents = []
    for i in range(len(anchors)):
        a, b = anchors[max(0, i-1)], anchors[min(len(anchors)-1, i+1)]
        divisor = 1.0 if i in (0, len(anchors)-1) else 2.0
        tangents.append(tuple((y-x)/divisor for x, y in zip(a, b)))
    result = []
    for i in range(len(anchors)-1):
        for j in range(steps):
            t = j/float(steps)
            h = (2*t**3-3*t*t+1, t**3-2*t*t+t,
                 -2*t**3+3*t*t, t**3-t*t)
            result.append(tuple(h[0]*anchors[i][k]+h[1]*tangents[i][k]
                                +h[2]*anchors[i+1][k]+h[3]*tangents[i+1][k]
                                for k in range(3)))
    result.append(anchors[-1])
    return result


def build_recipe(capacity=4):
    key = normalize_capacity(capacity)
    spec = SPECS[key]
    radius = spec['body_diameter']/2.0
    scale = spec['body_diameter']/130.0
    reference_top = 402+52.5*math.sin(math.radians(8))+2.5*math.cos(math.radians(8))
    shoulder_z = spec['total_height']-(reference_top-299)*scale
    offset = shoulder_z-299*scale
    bottom, top = 8*scale, shoulder_z+9*scale
    parts = []

    def head(point):
        x, y, z = point
        return (x*scale, y*scale, z*scale+offset)

    def cone(name, start, end, r0, r1, color):
        parts.append(dict(kind='cone', name=name, start=start, end=end,
                          r0=r0, r1=r1, color=color))

    def box(name, center, size, color, tilt=0):
        parts.append(dict(kind='box', name=name, center=center, size=size,
                          tilt=tilt, color=color))

    def head_box(name, center, size, color, tilt=0):
        box(name, head(center), tuple(v*scale for v in size), color, tilt)

    parts.append(dict(kind='rounded_bottle', name='red_cylinder', radius=radius,
                      bottom=bottom, top=top, fillet=9*scale, color=RED))
    cone('tapered_shoulder', (0,0,shoulder_z), (0,0,shoulder_z+49*scale),
         radius, 19*scale, RED)
    cone('black_base_foot', (0,0,0), (0,0,12*scale), radius, radius, BLACK)
    cone('neck_collar', head((0,0,346)), head((0,0,361)), 19*scale, 19*scale, METAL)
    head_box('valve_block', (0,0,370), (34,28,25), METAL)
    head_box('fixed_carry_handle', (-38,0,386), (105,18,6), BLACK)
    head_box('upper_squeeze_lever', (-35,0,402), (105,18,5), RED, 8)
    cone('lever_pivot', head((4,13,390)), head((4,-13,390)), 5*scale, 5*scale, METAL)
    cone('pressure_gauge_rim', head((0,-18,374)), head((0,-30,374)),
         17*scale, 17*scale, BLACK)
    cone('pressure_gauge_face', head((0,-30,374)), head((0,-32,374)),
         14*scale, 14*scale, WHITE)
    head_box('pressure_gauge_needle', (0,-32.5,378), (1.7,1,16), BLACK, 25)
    parts.append(dict(kind='torus', name='safety_pull_ring',
                      center=head((21,-18,388)), major=11*scale,
                      minor=2*scale, color=METAL))
    hose_length = 0.0
    if spec['hose_length']:
        y, start_z, hose_x = 8*scale, head((0,0,373))[2], radius+29*scale

        def path(drop):
            return _hose_points([(16*scale,y,start_z), (55*scale,y,start_z+3*scale),
                                 (hose_x,y,start_z-22*scale),
                                 (hose_x+4*scale,y,start_z-80*scale),
                                 (hose_x+2*scale,y,start_z-drop*0.65),
                                 (hose_x,y,start_z-drop)])

        low, high = 100.0, 500.0
        for _ in range(45):
            drop = (low+high)/2
            points = path(drop)
            length = sum(distance(a,b) for a,b in zip(points, points[1:]))
            if length < spec['hose_length']:
                low = drop
            else:
                high = drop
        drop = (low+high)/2
        points = path(drop)
        hose_length = sum(distance(a,b) for a,b in zip(points, points[1:]))
        parts.append(dict(kind='hose', name='curved_black_discharge_hose',
                          points=points, radius=spec['hose_diameter']/2.0, color=BLACK))
        nozzle_bottom = start_z-drop-28*scale
        cone('flared_discharge_nozzle', (hose_x,y,nozzle_bottom),
             (hose_x,y,nozzle_bottom+30*scale), 13*scale, 9, BLACK)
        box('hose_retaining_clip', (radius+14*scale,y,start_z-drop*0.6),
            (30*scale,22*scale,12*scale), BLACK)
    else:
        cone('direct_discharge_nozzle_2kg', head((15,8,373)), head((43,8,373)),
             7*scale, 12*scale, BLACK)
    box('front_instruction_label', (0,-radius+0.5*scale,bottom+(top-bottom)*0.60),
        (54*scale,3*scale,95*scale), LABEL)
    return dict(capacity=key, spec=spec, name=cell_name(key), parts=parts,
                hose_length=hose_length, scale=scale)


def point_and_vector(origin, angle, units_per_mm):
    """Return mm-to-UOR transforms; vectors exclude translation."""
    if not math.isfinite(angle) or not math.isfinite(units_per_mm) or units_per_mm <= 0:
        raise ValueError('角度或模型单位无效。')
    if not all(math.isfinite(v) for v in origin):
        raise ValueError('放置点无效。')
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def vector(v):
        x, y, z = v
        return ((c*x-s*y)*units_per_mm, (s*x+c*y)*units_per_mm, z*units_per_mm)

    def point(v):
        return tuple(a+b for a,b in zip(origin, vector(v)))
    return point, vector


def box_frame(part):
    """build123d's centered box followed by Rot(0, tilt, 0)."""
    t = math.radians(part['tilt'])
    x = (math.cos(t), 0, -math.sin(t))
    y = (0,1,0)
    z = (math.sin(t), 0, math.cos(t))
    dx, dy, dz = part['size']
    base = tuple(part['center'][i]-0.5*(dx*x[i]+dy*y[i]+dz*z[i]) for i in range(3))
    top = tuple(base[i]+dz*z[i] for i in range(3))
    return base, top, x, y
