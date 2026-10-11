# -*- coding: utf-8 -*-
"""MicroStation / OpenPlant Modeler 轻便消防水龙柜生成、附加属性及统计工具。

依据国家标准图集 15S202《室内消火栓安装》第 53 页 "轻便消防水龙柜（二）"
（规格 1200×550×160）在活动三维 DGN 内创建模型：

1. 运行本脚本，在窗口中选择规格参数与是否生成内部设备；
2. 在模型中点取柜体底部前侧中心点；
3. 生成钢制柜体、隔板、消防水龙卷盘、灭火器、阀门、直流喷雾喷枪与柜门，
   柜门带观察窗及"轻便消防水龙柜 / 火警电话 119"标识；
4. 下部储物区的灭火器不再使用简化圆柱示意，而是按华海 MF/ABCE 系列手提式
   干粉灭火器的毫米几何配方（内联自 灭火器箱/华海灭火器_OPM，原文件不改）
   生成外观模型：筒身圆角、锥形肩部、黑色底座、阀门、双手柄、销轴、压力表、
   保险拉环、喷嘴/400mm 软管与标签板；每具为嵌套命名单元 HUAHAI_MF_ABCEx，
   随柜体整体移动，也可单独选中。输入型号中的数字视为公称充装量，按就近
   原则映射到 2/4/5/6/8 kg 外观规格（映射结果写入 ItemType）；
5. 通过 ItemType 保存《主要器材表》8 项器材，可统计当前模型器材数量，
   并可导出 JSON / Excel 清单。

坐标约定（单位均为 mm）：X=柜宽（默认 550），Y=进深（默认 160），
Z=柜高（默认 1200）；点取点为柜体底部前侧中心，正面朝 -Y，柜体沿 +Y
向后、沿 +Z 向上。
"""

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

import json
import math
import os
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape


DEBUG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         u'轻便消防水龙柜_debug_log.txt')
USER_SELECTION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'轻便消防水龙柜_上次选型.json')
ITEM_LIBRARY_NAME = 'FireProtectionComponents'
ITEM_TYPE_PREFIX = 'LightHoseCabinet'
CELL_NAME = 'LightHoseCabinet'

STANDARD = '15S202'
DRAWING_PAGE = '53'
CABINET_MODEL = u'15S202-P53 轻便消防水龙柜（二）'

# 默认 MicroStation 色表中 3 为红色、6 为黄色。若项目使用自定义色表，可修改这两个值。
RED_COLOR_INDEX = 3
YELLOW_COLOR_INDEX = 6

# 图集 15S202 第 53 页轻便消防水龙柜（二）默认规格。
DEFAULT_WIDTH = 550.0
DEFAULT_DEPTH = 160.0
DEFAULT_HEIGHT = 1200.0
DEFAULT_LOWER_HEIGHT = 550.0

WALL_THICKNESS = 1.5
DIVIDER_THICKNESS = 1.5
DOOR_THICKNESS = 1.5
WINDOW_MARGIN = 45.0

REEL_DIAMETER = 380.0
REEL_WIDTH = 120.0
REEL_HUB_DIAMETER = 90.0
REEL_FLANGE_THICKNESS = 3.0
REEL_CENTER_FROM_LEFT = 200.0
REEL_CENTER_FROM_TOP = 200.0
REEL_BACK_CLEARANCE = 5.0

DEFAULT_EXTINGUISHER_MODEL = u'MFZ/ABC4'
DEFAULT_EXTINGUISHER_QUANTITY = 2

# 下部储物区灭火器外观模型：内联改编自 灭火器箱/华海灭火器_OPM 的 specs.json
# 与 huahai_geometry.py（MF/ABCE 手提式干粉系列，纯毫米配方，原有文件不改）。
# 输入型号中的数字按就近原则映射到 2/4/5/6/8 kg 外观规格；默认隔板（Z=550）
# 下净高最多容纳 5kg 外观（6/8kg 自动回退到放得下的较小规格）。
EXTINGUISHER_SPECS = {
    '2': {'model': 'MF/ABCE2', 'body_diameter': 110, 'total_height': 360,
          'filled_weight_kg': 3.43, 'hose_diameter': 0, 'hose_length': 0},
    '4': {'model': 'MF/ABCE4', 'body_diameter': 130, 'total_height': 485,
          'filled_weight_kg': 6.26, 'hose_diameter': 18, 'hose_length': 400},
    '5': {'model': 'MF/ABCE5', 'body_diameter': 140, 'total_height': 535,
          'filled_weight_kg': 7.6, 'hose_diameter': 18, 'hose_length': 400},
    '6': {'model': 'MF/ABCE6', 'body_diameter': 150, 'total_height': 575,
          'filled_weight_kg': 9.1, 'hose_diameter': 18, 'hose_length': 400},
    '8': {'model': 'MF/ABCE8', 'body_diameter': 160, 'total_height': 605,
          'filled_weight_kg': 11.68, 'hose_diameter': 18, 'hose_length': 400},
}
RED = (204, 9, 6)
BLACK = (18, 19, 20)
METAL = (166, 168, 173)
WHITE = (237, 240, 227)
LABEL = (245, 242, 224)
EXTINGUISHER_BAY_CLEARANCE = 2.0
EXTINGUISHER_MIN_NEIGHBOR_GAP = 25.0

# 卷盘给水支管：DN25，位于隔板上方 100（图集 I-I 的 100 标注），由柜体左侧
# 穿出并带阀门、管套与螺纹接口。
SUPPLY_PIPE_RADIUS = 17.0
SUPPLY_PIPE_FROM_FRONT = 60.0
SUPPLY_PIPE_OUTSIDE = 120.0
SUPPLY_PIPE_FROM_DIVIDER = 100.0
SUPPLY_PIPE_INNER_FROM_LEFT = 200.0
SLEEVE_RADIUS = 21.0
SLEEVE_LENGTH = 40.0
SUPPLY_THREAD_RADIUS = 19.0
SUPPLY_THREAD_LENGTH = 28.0
VALVE_FROM_LEFT = 100.0
VALVE_BODY_RADIUS = 24.0
VALVE_BODY_LENGTH = 46.0
VALVE_WHEEL_RADIUS = 50.0
VALVE_WHEEL_THICKNESS = 8.0
VALVE_WHEEL_HEIGHT = 60.0

GUN_BARREL_RADIUS = 8.0
GUN_BARREL_LENGTH = 240.0
GUN_HANDLE_RADIUS = 9.0
GUN_HANDLE_LENGTH = 80.0

PRISM_SIDES = 32


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as output:
            output.write(str(message) + '\n')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 纯几何 / 清单计算（不依赖 Bentley 运行时，可被 _geometry_selftest 抽取测试）
# ---------------------------------------------------------------------------

def _cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _normalized(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length <= 0.0:
        raise ValueError('zero-length vector')
    return tuple(component / length for component in vector)


def _perpendicular_basis(axis):
    axis = _normalized(axis)
    reference = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0)
    first = _normalized(_cross(axis, reference))
    second = _cross(axis, first)
    return first, second


def _cylinder_profile_points(center, axis, radius, sides=PRISM_SIDES):
    """Return the side-`sides` polygon vertices of a circular prism cross-section."""
    first, second = _perpendicular_basis(axis)
    points = []
    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        points.append((
            center[0] + radius * (cos_angle * first[0] + sin_angle * second[0]),
            center[1] + radius * (cos_angle * first[1] + sin_angle * second[1]),
            center[2] + radius * (cos_angle * first[2] + sin_angle * second[2]),
        ))
    return points


def _cabinet_layout(width, depth, height, lower_height):
    """Local-mm layout of the cabinet in a frame whose front is at Y=0, front faces -Y."""
    width = float(width)
    depth = float(depth)
    height = float(height)
    return {
        'width': width,
        'depth': depth,
        'height': height,
        'left': -width / 2.0,
        'right': width / 2.0,
        'front': 0.0,
        'rear': depth,
        'bottom': 0.0,
        'top': height,
        'divider_z': float(lower_height),
    }


def _reel_layout(layout, diameter=REEL_DIAMETER, center_from_left=REEL_CENTER_FROM_LEFT,
                 center_from_top=REEL_CENTER_FROM_TOP, reel_width=REEL_WIDTH,
                 hub_diameter=REEL_HUB_DIAMETER, flange_thickness=REEL_FLANGE_THICKNESS,
                 back_clearance=REEL_BACK_CLEARANCE):
    """Axis-along-Y hose reel position; flanges and hub span the drum width along +Y."""
    y_back = layout['rear'] - back_clearance
    y_front = y_back - reel_width
    return {
        'center_x': layout['left'] + center_from_left,
        'center_z': layout['top'] - center_from_top,
        'radius': diameter / 2.0,
        'hub_radius': hub_diameter / 2.0,
        'reel_width': reel_width,
        'flange_thickness': flange_thickness,
        'y_back': y_back,
        'y_front': y_front,
    }


# ---------------------------------------------------------------------------
# 华海灭火器外观模型配方（内联自 灭火器箱/华海灭火器_OPM/huahai_geometry.py，
# 原有文件保持不变；纯毫米几何，不依赖 Bentley 运行时）
# ---------------------------------------------------------------------------

def _ext_capacity_key(value):
    key = str(value).strip().lower()
    for unit in ('公斤', '千克', 'kg'):
        key = key.replace(unit, '')
    key = key.strip()
    if key not in EXTINGUISHER_SPECS:
        raise ValueError('请选择 2、4、5、6 或 8 kg。')
    return key


def _ext_cell_name(capacity):
    return 'HUAHAI_MF_ABCE%s' % _ext_capacity_key(capacity)


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


def _ext_build_recipe(capacity):
    key = _ext_capacity_key(capacity)
    spec = EXTINGUISHER_SPECS[key]
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
    return dict(capacity=key, spec=spec, name=_ext_cell_name(key), parts=parts,
                hose_length=hose_length, scale=scale)


def _ext_point_and_vector(origin, angle, units_per_mm):
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


def _ext_box_frame(part):
    """build123d's centered box followed by Rot(0, tilt, 0)."""
    t = math.radians(part['tilt'])
    x = (math.cos(t), 0, -math.sin(t))
    y = (0,1,0)
    z = (math.sin(t), 0, math.cos(t))
    dx, dy, dz = part['size']
    base = tuple(part['center'][i]-0.5*(dx*x[i]+dy*y[i]+dz*z[i]) for i in range(3))
    top = tuple(base[i]+dz*z[i] for i in range(3))
    return base, top, x, y


def _parse_extinguisher_capacity(model_text, default=4):
    """从型号字符串提取公称充装量：取最后一串数字；无有效数字时用默认 4。"""
    runs = []
    current = ''
    for ch in str(model_text or ''):
        if ch.isdigit():
            current += ch
        elif current:
            runs.append(current)
            current = ''
    if current:
        runs.append(current)
    for run in reversed(runs):
        value = int(run)
        if 0 < value <= 20:
            return value
    return default


def _extinguisher_overhang(spec):
    """外观模型超出筒身投影的外伸长度（沿 +X 的喷射软管/喷嘴侧）。"""
    diameter = float(spec['body_diameter'])
    if spec['hose_length']:
        return 33.0 * (diameter / 130.0) + spec['hose_diameter'] / 2.0
    return max(0.0, 43.0 * (diameter / 130.0) - diameter / 2.0)


def _extinguisher_neighbor_gap(spec, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """相邻两具灭火器筒壁间的净距：软管外伸 + 间隙，且不小于最小视觉间距。"""
    return max(_extinguisher_overhang(spec) + clearance, EXTINGUISHER_MIN_NEIGHBOR_GAP)


def _extinguisher_span(spec, count, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """count 具等距成组布置占用的总宽度（相邻留净距，含软管外伸）。"""
    if count <= 0:
        return 0.0
    diameter = float(spec['body_diameter'])
    return (count * diameter
            + (count - 1) * _extinguisher_neighbor_gap(spec, clearance)
            + _extinguisher_overhang(spec))


def _extinguisher_variant_key(model_text, width, depth, divider_z,
                              count=DEFAULT_EXTINGUISHER_QUANTITY,
                              wall=WALL_THICKNESS, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """按输入型号就近选择华海外观规格，并要求能连数量一起放进下部储物区。

    就近顺序：容量差最小者优先，并列取大规格。进深、隔板下净高、成组总宽
    任一放不下则尝试下一规格；全部放不下返回 None（数量为 0 时仅查单具）。
    """
    capacity = _parse_extinguisher_capacity(model_text)
    interior_width = float(width) - 2.0 * wall
    half_depth = (float(depth) - 2.0 * wall) / 2.0
    available_height = float(divider_z) - wall - clearance
    ordered = sorted(EXTINGUISHER_SPECS,
                     key=lambda key: (abs(int(key) - capacity), -int(key)))
    for key in ordered:
        spec = EXTINGUISHER_SPECS[key]
        diameter = float(spec['body_diameter'])
        if diameter / 2.0 + clearance > half_depth:
            continue
        if float(spec['total_height']) > available_height:
            continue
        if count <= 0 or _extinguisher_span(spec, count, clearance) <= interior_width - 2.0 * clearance:
            return key
    return None


def _extinguisher_max_count(model_text, width, depth, divider_z,
                            wall=WALL_THICKNESS, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """该型号外观模型在下部储物区按宽度可容纳的最大具数。"""
    variant_key = _extinguisher_variant_key(model_text, width, depth, divider_z,
                                            1, wall, clearance)
    if variant_key is None:
        return 0
    spec = EXTINGUISHER_SPECS[variant_key]
    interior_width = float(width) - 2.0 * wall
    count = 1
    while (_extinguisher_span(spec, count + 1, clearance)
           <= interior_width - 2.0 * clearance):
        count += 1
    return count


def _extinguisher_fit_error(width, depth, divider_z, model_text, count,
                            wall=WALL_THICKNESS, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """型号或数量放不进下部储物区时报错，否则返回 None。"""
    try:
        count = int(count)
    except (TypeError, ValueError):
        return u'灭火器数量必须为整数。'
    if count < 0:
        return u'灭火器数量不能为负数。'
    if count == 0:
        return None
    maximum = _extinguisher_max_count(model_text, width, depth, divider_z,
                                      wall, clearance)
    if maximum <= 0:
        return u'所选型号 %s 的灭火器外观模型放不进下部储物区，请改选较小规格或加大柜体。' % (
            model_text,)
    if count > maximum:
        return u'下部储物区最多可容纳 %d 具 %s（外观模型按华海规格就近映射），请减少数量或加大柜体。' % (
            maximum, model_text)
    return None


def _extinguisher_visual_spec_text(variant_key):
    """ItemType / 清单使用的外观模型说明文字。"""
    if variant_key is None:
        return u'（无）'
    spec = EXTINGUISHER_SPECS[variant_key]
    return u'Ø%.0f×%.0f mm（华海 %s 外观简化模型）' % (
        spec['body_diameter'], spec['total_height'], spec['model'])


def _extinguisher_layout(layout, count, variant_key,
                         wall=WALL_THICKNESS, clearance=EXTINGUISHER_BAY_CLEARANCE):
    """将 count 具选定规格的灭火器等距成组、整体居中布置在下部储物区。

    相邻筒壁净距取软管外伸与最小视觉间距的较大值；灭火器落在柜体底板上，
    瓶顶不得越过隔板；瓶体标识与压力表朝 -Y（柜门方向）。
    """
    if count <= 0 or variant_key is None:
        return []
    spec = EXTINGUISHER_SPECS[variant_key]
    diameter = float(spec['body_diameter'])
    total_height = float(spec['total_height'])
    overhang = _extinguisher_overhang(spec)
    gap = _extinguisher_neighbor_gap(spec, clearance)
    interior_left = layout['left'] + wall
    interior_width = layout['right'] - layout['left'] - 2.0 * wall
    span = _extinguisher_span(spec, count, clearance)
    start = interior_left + (interior_width - span) / 2.0 + diameter / 2.0
    bottom_z = layout['bottom'] + wall
    bottles = []
    for index in range(count):
        bottles.append({
            'center_x': start + index * (diameter + gap),
            'center_y': (layout['front'] + layout['rear']) / 2.0,
            'bottom_z': bottom_z,
            'top_z': bottom_z + total_height,
            'radius': diameter / 2.0,
            'diameter': diameter,
            'total_height': total_height,
            'overhang': overhang,
            'variant': variant_key,
        })
    return bottles


def _supply_layout(layout, pipe_radius=SUPPLY_PIPE_RADIUS,
                   outside=SUPPLY_PIPE_OUTSIDE, from_front=SUPPLY_PIPE_FROM_FRONT,
                   from_divider=SUPPLY_PIPE_FROM_DIVIDER,
                   inner_from_left=SUPPLY_PIPE_INNER_FROM_LEFT,
                   valve_from_left=VALVE_FROM_LEFT):
    """DN25 卷盘给水支管：隔板上方 100 处水平向左穿出柜体（图集 I-I 尺寸）。"""
    outer_x = layout['left'] - outside
    inner_x = layout['left'] + inner_from_left
    return {
        'y': layout['front'] + from_front,
        'z': layout['divider_z'] + from_divider,
        'radius': pipe_radius,
        'outer_x': outer_x,
        'inner_x': inner_x,
        'length': inner_x - outer_x,
        'valve_x': layout['left'] + valve_from_left,
    }


def _build_bom_rows(width=DEFAULT_WIDTH, depth=DEFAULT_DEPTH, height=DEFAULT_HEIGHT,
                    extinguisher_model=DEFAULT_EXTINGUISHER_MODEL,
                    extinguisher_quantity=DEFAULT_EXTINGUISHER_QUANTITY):
    """图集《主要器材表》8 项 + 用户输入的箱内灭火器；单柜数量按输入值。"""
    rows = [
        {'no': 1, 'code': 'Cabinet', 'name': u'轻便消防水龙柜', 'material': u'钢',
         'spec': u'%.0f×%.0f×%.0f' % (width, depth, height), 'unit': u'个', 'qty': 1},
        {'no': 2, 'code': 'HoseReel', 'name': u'轻便消防水龙卷盘', 'material': u'钢喷塑',
         'spec': u'P380', 'unit': u'个', 'qty': 1},
        {'no': 3, 'code': 'Hose', 'name': u'轻便消防水龙', 'material': u'衬胶',
         'spec': u'LQG16-30', 'unit': u'条', 'qty': 1},
        {'no': 4, 'code': 'SprayGun', 'name': u'直流喷雾喷枪', 'material': u'全铜',
         'spec': u'当量喷嘴直径 φ6', 'unit': u'支', 'qty': 1},
        {'no': 5, 'code': 'QuickCoupling', 'name': u'快速接口', 'material': u'全铜',
         'spec': u'成品', 'unit': u'个', 'qty': 1},
        {'no': 6, 'code': 'QuickConnector', 'name': u'快速接头', 'material': u'钢或铜',
         'spec': u'DN25', 'unit': u'个', 'qty': 1},
        {'no': 7, 'code': 'Valve', 'name': u'阀门', 'material': u'全铜',
         'spec': u'DN25', 'unit': u'个', 'qty': 1},
        {'no': 8, 'code': 'PipeSleeve', 'name': u'管套', 'material': u'钢（扣压成型）',
         'spec': u'成品', 'unit': u'个', 'qty': 1},
    ]
    quantity = int(extinguisher_quantity)
    if quantity > 0:
        rows.append({
            'no': 9, 'code': 'Extinguisher', 'name': u'手提式灭火器',
            'material': u'用户配套', 'spec': extinguisher_model,
            'unit': u'具', 'qty': quantity})
    return rows


def _parse_bom_rows(text):
    """Parse a BomJson string back into rows; an empty or malformed string yields []."""
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    rows = []
    for entry in data:
        if not isinstance(entry, dict):
            return []
        try:
            rows.append({
                'no': int(entry['no']),
                'code': str(entry.get('code', '')),
                'name': str(entry['name']),
                'material': str(entry['material']),
                'spec': str(entry['spec']),
                'unit': str(entry['unit']),
                'qty': int(entry['qty']),
            })
        except (KeyError, TypeError, ValueError):
            return []
    return rows


def _aggregate_bom_materials(row_groups):
    """Aggregate per-set BOM rows across (rows, multiplier) groups into one material table."""
    aggregate = {}
    for rows, multiplier in row_groups:
        for row in rows:
            key = (row['no'], row['name'], row['material'], row['spec'], row['unit'])
            entry = aggregate.get(key)
            if entry is None:
                entry = {
                    'no': row['no'],
                    'name': row['name'],
                    'material': row['material'],
                    'spec': row['spec'],
                    'unit': row['unit'],
                    'qtyPerSet': row['qty'],
                    'totalQty': 0,
                }
                aggregate[key] = entry
            entry['totalQty'] += row['qty'] * multiplier
    return sorted(aggregate.values(), key=lambda item: item['no'])


def _editable_fields():
    return (DEFAULT_WIDTH, DEFAULT_DEPTH, DEFAULT_HEIGHT, DEFAULT_LOWER_HEIGHT)


def _validate_dimensions(width, depth, height, lower_height):
    """Return an error string, or None when the four dimensions describe a buildable cabinet."""
    try:
        width = float(width)
        depth = float(depth)
        height = float(height)
        lower_height = float(lower_height)
    except (TypeError, ValueError):
        return u'尺寸必须为数字。'
    if min(width, depth, height, lower_height) <= 0.0:
        return u'尺寸必须为正数。'
    if min(width, depth) <= 2.0 * WALL_THICKNESS:
        return u'柜宽或进深过小，无法生成壁厚。'
    if not (WALL_THICKNESS * 2.0 < lower_height < height - WALL_THICKNESS * 2.0):
        return u'下部储物区高度必须位于柜高内部。'
    if REEL_DIAMETER > min(width, height - lower_height):
        return u'卷盘直径超出柜体可用空间。'
    return None


def _load_last_selection():
    try:
        with open(USER_SELECTION_FILE, 'r', encoding='utf-8') as source:
            value = json.load(source)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_last_selection(selection):
    try:
        with open(USER_SELECTION_FILE, 'w', encoding='utf-8') as output:
            json.dump(selection, output, ensure_ascii=False, indent=2)
        return True
    except Exception as error:
        _log('selection save exception: %r' % error)
        return False


def _uor_per_mm(dgn_model=None):
    if dgn_model is None:
        dgn_model = ISessionMgr.GetActiveDgnModel()
    return dgn_model.GetModelInfo().GetUorPerStorage()


def mm(value, dgn_model=None):
    return float(value) * _uor_per_mm(dgn_model)


def _ec_value(value):
    ec_value = ECValue()
    if isinstance(value, str):
        ec_value.SetString(value)
    elif isinstance(value, float):
        ec_value.SetDouble(value)
    else:
        ec_value.SetInteger(value)
    return ec_value


def _safe_name(value):
    """ItemType 名称只保留字母数字，其余字符（含中文）以 '_' 代替。"""
    cleaned = ''.join(ch if ch.isalnum() else '_' for ch in str(value))
    return cleaned or 'None'


def _item_type_name(width, depth, height, extinguisher_model, extinguisher_quantity):
    return '%s_%s_%dx%dx%d_%sx%d' % (
        ITEM_TYPE_PREFIX, STANDARD, int(round(width)), int(round(depth)),
        int(round(height)), _safe_name(extinguisher_model),
        int(extinguisher_quantity))


ITEM_PROPERTIES = (
    ('ComponentName', CustomProperty.Type1.eString),
    ('CabinetModel', CustomProperty.Type1.eString),
    ('Standard', CustomProperty.Type1.eString),
    ('DrawingPage', CustomProperty.Type1.eString),
    ('WidthMm', CustomProperty.Type1.eDouble),
    ('DepthMm', CustomProperty.Type1.eDouble),
    ('HeightMm', CustomProperty.Type1.eDouble),
    ('LowerCompartmentHeightMm', CustomProperty.Type1.eDouble),
    ('ReelModel', CustomProperty.Type1.eString),
    ('ReelDiameterMm', CustomProperty.Type1.eDouble),
    ('HoseModel', CustomProperty.Type1.eString),
    ('GunModel', CustomProperty.Type1.eString),
    ('GunNozzleDiameterMm', CustomProperty.Type1.eDouble),
    ('ValveSize', CustomProperty.Type1.eString),
    ('ExtinguisherModel', CustomProperty.Type1.eString),
    ('ExtinguisherQuantity', CustomProperty.Type1.eInteger),
    ('ExtinguisherUnit', CustomProperty.Type1.eString),
    ('ExtinguisherVisualCell', CustomProperty.Type1.eString),
    ('ExtinguisherVisualSpec', CustomProperty.Type1.eString),
    ('ExtinguisherVisualDiameterMm', CustomProperty.Type1.eDouble),
    ('ExtinguisherVisualHeightMm', CustomProperty.Type1.eDouble),
    ('CabinetQuantity', CustomProperty.Type1.eInteger),
    ('ComponentKinds', CustomProperty.Type1.eInteger),
    ('BomJson', CustomProperty.Type1.eString),
    ('SurfaceFinish', CustomProperty.Type1.eString),
    ('FrontText', CustomProperty.Type1.eString),
    ('FirePhoneText', CustomProperty.Type1.eString),
    ('CoordinateConvention', CustomProperty.Type1.eString),
    ('Unit', CustomProperty.Type1.eString),
)


def _metadata(width, depth, height, lower_height,
              extinguisher_model=DEFAULT_EXTINGUISHER_MODEL,
              extinguisher_quantity=DEFAULT_EXTINGUISHER_QUANTITY):
    rows = _build_bom_rows(width, depth, height,
                           extinguisher_model, extinguisher_quantity)
    variant_key = _extinguisher_variant_key(extinguisher_model, width, depth,
                                            lower_height, extinguisher_quantity)
    if variant_key is not None:
        visual_spec = EXTINGUISHER_SPECS[variant_key]
        visual = {
            'ExtinguisherVisualCell': _ext_cell_name(variant_key),
            'ExtinguisherVisualSpec': _extinguisher_visual_spec_text(variant_key),
            'ExtinguisherVisualDiameterMm': float(visual_spec['body_diameter']),
            'ExtinguisherVisualHeightMm': float(visual_spec['total_height']),
        }
    else:
        visual = {
            'ExtinguisherVisualCell': u'（无）',
            'ExtinguisherVisualSpec': u'储物区放不下外观模型',
            'ExtinguisherVisualDiameterMm': 0.0,
            'ExtinguisherVisualHeightMm': 0.0,
        }
    return {
        'ComponentName': u'轻便消防水龙柜',
        'CabinetModel': CABINET_MODEL,
        'Standard': STANDARD,
        'DrawingPage': DRAWING_PAGE,
        'WidthMm': float(width),
        'DepthMm': float(depth),
        'HeightMm': float(height),
        'LowerCompartmentHeightMm': float(lower_height),
        'ReelModel': u'P380',
        'ReelDiameterMm': float(REEL_DIAMETER),
        'HoseModel': u'LQG16-30',
        'GunModel': u'直流喷雾喷枪',
        'GunNozzleDiameterMm': 6.0,
        'ValveSize': u'DN25',
        'ExtinguisherModel': extinguisher_model,
        'ExtinguisherQuantity': int(extinguisher_quantity),
        'ExtinguisherUnit': u'具',
        'ExtinguisherVisualCell': visual['ExtinguisherVisualCell'],
        'ExtinguisherVisualSpec': visual['ExtinguisherVisualSpec'],
        'ExtinguisherVisualDiameterMm': visual['ExtinguisherVisualDiameterMm'],
        'ExtinguisherVisualHeightMm': visual['ExtinguisherVisualHeightMm'],
        'CabinetQuantity': 1,
        'ComponentKinds': len(rows),
        'BomJson': json.dumps(rows, ensure_ascii=False),
        'SurfaceFinish': u'钢制柜体，门面喷塑',
        'FrontText': u'轻便消防水龙柜',
        'FirePhoneText': u'火警电话 119',
        'CoordinateConvention': u'X=宽，Y=进深，Z=高，正面朝-Y',
        'Unit': u'套',
    }


def _get_or_create_item_type(width, depth, height, lower_height,
                             extinguisher_model, extinguisher_quantity):
    defaults = _metadata(width, depth, height, lower_height,
                         extinguisher_model, extinguisher_quantity)
    dgn_file = ISessionMgr.GetActiveDgnFile()
    name = _item_type_name(width, depth, height,
                           extinguisher_model, extinguisher_quantity)
    try:
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        changed = False
        if library is None:
            library = ItemTypeLibrary(ITEM_LIBRARY_NAME, dgn_file, False)
            changed = True
        item_type = library.GetItemTypeByName(name)
        if item_type is None:
            item_type = library.AddItemType(name, False)
            changed = True
        if item_type is None:
            _log('cannot create ItemType: %s' % name)
            return None
        for property_name, property_type in ITEM_PROPERTIES:
            item_property = item_type.GetPropertyByName(property_name)
            if item_property is None:
                item_property = item_type.AddProperty(property_name, False)
                if item_property is None or not item_property.SetType(property_type):
                    _log('cannot add ItemType property: %s' % property_name)
                    return None
                if not item_property.SetDefaultValue(_ec_value(defaults[property_name])):
                    _log('cannot set ItemType default: %s' % property_name)
                    return None
                changed = True
        if changed and not library.Write():
            _log('cannot write ItemType library')
            return None
        library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
        return library.GetItemTypeByName(name)
    except Exception as error:
        _log('ItemType setup error: %r' % error)
        return None


def _attach_cabinet_item(element, width, depth, height, lower_height,
                         extinguisher_model, extinguisher_quantity):
    item_type = _get_or_create_item_type(
        width, depth, height, lower_height,
        extinguisher_model, extinguisher_quantity)
    if item_type is None:
        return False
    try:
        host = CustomItemHost(element, False)
        try:
            item = host.ApplyCustomItem(item_type)
        except TypeError as error:
            # 部分 MicroStation Python 版本完成原生挂接后无法转换返回对象。
            if 'Unable to convert function return value' in str(error):
                return True
            raise
        if item is None:
            return False
        item.WriteChanges()
        return True
    except Exception as error:
        _log('ItemType attach error: %r' % error)
        return False


def _apply_color(element, color_index):
    try:
        setter = ElementPropertiesSetter()
        setter.SetColor(color_index)
        setter.SetWeight(1)
        setter.Apply(element)
        return True
    except Exception as error:
        _log('set color error: %r' % error)
        return False


def _create_box_body(minimum, maximum, dgn_model):
    min_x, min_y, min_z = minimum
    max_x, max_y, max_z = maximum
    if max_x <= min_x or max_y <= min_y or max_z <= min_z:
        return None
    points = DPoint3dArray()
    for x, y in ((min_x, min_y), (max_x, min_y),
                 (max_x, max_y), (min_x, max_y)):
        points.append(DPoint3d(mm(x, dgn_model), mm(y, dgn_model),
                               mm(min_z, dgn_model)))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(profile, None, points,
                                             dgn_model.Is3d(), dgn_model)
    if BentleyStatus.eSUCCESS != status:
        return None
    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        return None
    sweep = DVec3d(0.0, 0.0, mm(max_z - min_z, dgn_model))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        return None
    return body_result[1]


def _subtract_body(target_body, tool_body):
    tools = ISolidKernelEntityPtrArray()
    tools.append(tool_body)
    try:
        status = SolidUtil.Modify.BooleanSubtract(target_body, tools)
    except Exception as error:
        _log('BooleanSubtract exception: %r' % error)
        return False
    if isinstance(status, tuple):
        status = status[0]
    if BentleyStatus.eSUCCESS != status:
        _log('BooleanSubtract failed: %r' % status)
        return False
    return True


def _body_to_element(body, dgn_model, color_index, label):
    element = EditElementHandle()
    if BentleyStatus.eSUCCESS != SolidUtil.Convert.BodyToElement(
            element, body, None, dgn_model):
        _log('%s: BodyToElement failed' % label)
        return None
    _apply_color(element, color_index)
    return element


def _create_solid_box(minimum, maximum, dgn_model, color_index, label,
                      add_to_model=True):
    body = _create_box_body(minimum, maximum, dgn_model)
    if body is None:
        _log('%s: body creation failed' % label)
        return None
    element = _body_to_element(body, dgn_model, color_index, label)
    if element is None:
        return None
    if add_to_model and BentleyStatus.eSUCCESS != element.AddToModel():
        _log('%s: AddToModel failed' % label)
        return None
    return element


def _create_prism_body(center, axis, radius, length, dgn_model, sides=PRISM_SIDES):
    """Extrude a `sides`-gon circular profile from `center` along `axis` by `length` (mm)."""
    if radius <= 0.0 or length <= 0.0 or sides < 3:
        return None
    points = DPoint3dArray()
    for x, y, z in _cylinder_profile_points(center, axis, radius, sides):
        points.append(DPoint3d(mm(x, dgn_model), mm(y, dgn_model), mm(z, dgn_model)))
    profile = EditElementHandle()
    status = ShapeHandler.CreateShapeElement(profile, None, points,
                                             dgn_model.Is3d(), dgn_model)
    if BentleyStatus.eSUCCESS != status:
        return None
    body_result = SolidUtil.Convert.ElementToBody(profile, True, True, False)
    if body_result is None or BentleyStatus.eSUCCESS != body_result[0]:
        return None
    direction = _normalized(axis)
    sweep = DVec3d(mm(direction[0] * length, dgn_model),
                   mm(direction[1] * length, dgn_model),
                   mm(direction[2] * length, dgn_model))
    if BentleyStatus.eSUCCESS != SolidUtil.Modify.SweepBody(body_result[1], sweep):
        return None
    return body_result[1]


def _create_prism_element(center, axis, radius, length, dgn_model, color_index, label):
    body = _create_prism_body(center, axis, radius, length, dgn_model)
    if body is None:
        _log('%s: prism body creation failed' % label)
        return None
    return _body_to_element(body, dgn_model, color_index, label)


def _create_text(text, origin, text_height, dgn_model, orientation=None,
                 color_index=YELLOW_COLOR_INDEX, add_to_model=True):
    try:
        text_props = TextBlockProperties.Create(dgn_model)
        paragraph_props = ParagraphProperties.Create(dgn_model)
        justification = getattr(TextElementJustification, 'CenterBaseline', None)
        if justification is None:
            justification = getattr(TextElementJustification, 'eCenterBaseline', None)
        if justification is None:
            raise RuntimeError('CenterBaseline text justification is unavailable')
        paragraph_props.SetJustification(justification)
        font = DgnFontManager.GetDefaultTrueTypeFont()
        size = DPoint2d(mm(text_height, dgn_model), mm(text_height, dgn_model))
        run_props = RunProperties.Create(font, size, dgn_model)
        text_block = TextBlock(text_props, paragraph_props, run_props, dgn_model)
        text_block.AppendText(text)
        text_block.SetUserOrigin(DPoint3d(mm(origin[0], dgn_model),
                                          mm(origin[1], dgn_model),
                                          mm(origin[2], dgn_model)))
        if orientation is not None:
            text_block.SetOrientation(orientation)
        element = EditElementHandle()
        status = TextElemHandler.CreateElement(element, None, text_block)
        if status != TextBlockToElementResult.eTEXTBLOCK_TO_ELEMENT_RESULT_Success:
            _log('text creation failed: %r' % status)
            return None
        _apply_color(element, color_index)
        if not add_to_model:
            return element
        if BentleyStatus.eSUCCESS != element.AddToModel():
            _log('text AddToModel failed')
            return None
        return element
    except Exception as error:
        _log('text exception: %r' % error)
        return None


def _extinguisher_check(status, operation, allow_void=False):
    if status is None and allow_void:
        return
    if status != BentleyStatus.eSUCCESS:
        raise RuntimeError('%s失败，Bentley 状态：%r' % (operation, status))


def _build_extinguisher_cell(recipe, origin, angle, dgn_model):
    """按毫米配方创建一具灭火器命名单元（内存中，未写入模型）。

    改编自 华海灭火器_OPM/huahai_bentley.py 的 build_cell：配方由外部传入，
    且不调用 AddToModel——单元将作为嵌套子单元加入柜体 Cell。
    ``origin`` 为灭火器底部中心（UOR 坐标）。
    """
    units_per_mm = _uor_per_mm(dgn_model)
    point_tuple, vector_tuple = _ext_point_and_vector(
        (origin.x, origin.y, origin.z), angle, units_per_mm)

    def p(v):
        return DPoint3d(*point_tuple(v))

    def v(vec):
        return DVec3d(*vector_tuple(vec))

    def direction(vec):
        return DVec3d(*(a/units_per_mm for a in vector_tuple(vec)))

    cell = EditElementHandle()
    # 用命名单元接口指定底部中心为原点，避免匿名单元自动取范围中心。
    _extinguisher_check(NormalCellHeaderHandler.CreateCellElement(
        cell, recipe['name'], origin,
        RotMatrix.FromAxisAndRotationAngle(2, math.radians(angle)),
        True, dgn_model), '创建命名单元', allow_void=True)
    if not cell.IsValid():
        raise RuntimeError('Bentley 未创建有效的命名单元句柄。')
    _extinguisher_check(NormalCellHeaderHandler.SetDescription(cell,
        'Huahai %s kg / %s / diameter %s mm / height %s mm' %
        (recipe['capacity'], recipe['spec']['model'], recipe['spec']['body_diameter'],
         recipe['spec']['total_height'])), '设置单元说明')
    colors = {}

    def lathe(part):
        # 圆柱上下边缘保留原脚本的 9*scale mm 真圆弧圆角。
        r, f = part['radius'], part['fillet']
        lo, hi = part['bottom'], part['top']
        curve = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)

        def line(a, b):
            curve.Add(ICurvePrimitive.CreateLine(DSegment3d(p(a), p(b))))

        line((0,0,lo), (r-f,0,lo))
        curve.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
            p((r-f,0,lo+f)), v((f,0,0)), v((0,0,f)), -math.pi/2, math.pi/2)))
        line((r,0,lo+f), (r,0,hi-f))
        curve.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
            p((r-f,0,hi-f)), v((f,0,0)), v((0,0,f)), 0, math.pi/2)))
        line((r-f,0,hi), (0,0,hi))
        line((0,0,hi), (0,0,lo))
        return ISolidPrimitive.CreateDgnRotationalSweep(DgnRotationalSweepDetail(
            curve, p((0,0,0)), direction((0,0,1)), 2*math.pi, True))

    def hose(part):
        # 沿平滑中心线以圆截面生成一个封闭放样实体。截面一致朝向避免扭转。
        points = part['points']
        sections = CurveVectorPtrArray()
        radius = part['radius']
        for i, center in enumerate(points):
            before, after = points[max(0,i-1)], points[min(len(points)-1,i+1)]
            dx, dz = after[0]-before[0], after[2]-before[2]
            length = math.hypot(dx, dz)
            if length <= 1e-9:
                raise RuntimeError('软管中心线有重复点。')
            section = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
            section.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
                p(center), v((0,radius,0)), v((-dz/length*radius,0,dx/length*radius)),
                0, 2*math.pi)))
            sections.append(section)
        return ISolidPrimitive.CreateDgnRuledSweep(DgnRuledSweepDetail(sections, True))

    for part in recipe['parts']:
        kind = part['kind']
        if kind == 'cone':
            primitive = ISolidPrimitive.CreateDgnCone(DgnConeDetail(
                p(part['start']), p(part['end']), part['r0']*units_per_mm,
                part['r1']*units_per_mm, True))
        elif kind == 'box':
            base, top, x, y = _ext_box_frame(part)
            dx, dy, dz = part['size']
            primitive = ISolidPrimitive.CreateDgnBox(DgnBoxDetail(
                p(base), p(top), direction(x), direction(y),
                dx*units_per_mm, dy*units_per_mm, dx*units_per_mm, dy*units_per_mm, True))
        elif kind == 'torus':
            primitive = ISolidPrimitive.CreateDgnTorusPipe(DgnTorusPipeDetail(
                p(part['center']), direction((1,0,0)), direction((0,0,1)),
                part['major']*units_per_mm, part['minor']*units_per_mm, 2*math.pi, True))
        elif kind == 'rounded_bottle':
            primitive = lathe(part)
        elif kind == 'hose':
            primitive = hose(part)
        else:
            raise RuntimeError('未知几何：%s' % kind)
        if primitive is None:
            raise RuntimeError('生成实体失败：%s' % part['name'])
        element = EditElementHandle()
        _extinguisher_check(DraftingElementSchema.ToElement(element, primitive,
                                                            None, dgn_model),
                            part['name'])
        if not element.IsValid():
            raise RuntimeError('实体句柄无效：%s' % part['name'])
        rgb = tuple(part['color'])
        if rgb not in colors:
            colors[rgb] = DgnColorMap.CreateElementColor(
                IntColorDef(*rgb), None, None, ISessionMgr.GetActiveDgnFile())
        props = ElementPropertiesSetter()
        props.SetColor(colors[rgb])
        props.SetWeight(1)
        props.Apply(element)
        _extinguisher_check(NormalCellHeaderHandler.AddChildElement(cell, element),
                            '加入 '+part['name'])
    _extinguisher_check(NormalCellHeaderHandler.AddChildComplete(cell), '完成灭火器单元')
    return cell


def _create_cabinet_cell(children, dgn_model):
    """Place all coloured parts as one orphan Cell that moves as one element."""
    cell = EditElementHandle()

    def status_is_success(status):
        return status is None or status == BentleyStatus.eSUCCESS

    try:
        status = NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, CELL_NAME, dgn_model.Is3d(), dgn_model)
        if not status_is_success(status):
            _log('cell header creation failed: %r' % status)
            return None
        if not cell.IsValid():
            _log('cell header creation returned no valid element')
            return None
        for child in children:
            if child is None:
                continue
            status = NormalCellHeaderHandler.AddChildElement(cell, child)
            if not status_is_success(status):
                _log('cell child add failed: %r' % status)
                return None
        status = NormalCellHeaderHandler.AddChildComplete(cell)
        if not status_is_success(status):
            _log('cell finalization failed: %r' % status)
            return None
        if BentleyStatus.eSUCCESS != cell.AddToModel():
            _log('cell AddToModel failed')
            return None
        return cell
    except Exception as error:
        _log('cell creation exception: %r' % error)
        return None


def create_light_hose_cabinet(origin=(0.0, 0.0, 0.0), width=DEFAULT_WIDTH,
                              depth=DEFAULT_DEPTH, height=DEFAULT_HEIGHT,
                              lower_height=DEFAULT_LOWER_HEIGHT, with_equipment=True,
                              extinguisher_model=DEFAULT_EXTINGUISHER_MODEL,
                              extinguisher_quantity=DEFAULT_EXTINGUISHER_QUANTITY):
    """Generate one 15S202-P53 cabinet Cell and attach its material metadata.

    ``origin`` is the centre of the cabinet's bottom-front edge. The cabinet
    extends equally along X, backward along +Y and upward along +Z.
    """
    error = _validate_dimensions(width, depth, height, lower_height)
    if error is not None:
        raise ValueError(error)
    error = _extinguisher_fit_error(width, depth, lower_height,
                                    extinguisher_model, extinguisher_quantity)
    if error is not None:
        raise ValueError(error)

    width = float(width)
    depth = float(depth)
    height = float(height)
    lower_height = float(lower_height)
    extinguisher_quantity = int(extinguisher_quantity)
    dgn_model = ISessionMgr.GetActiveDgnModel()
    ox, oy, oz = origin
    local = _cabinet_layout(width, depth, height, lower_height)
    left, right = local['left'], local['right']
    front, rear = local['front'], local['rear']
    bottom, top = local['bottom'], local['top']
    divider_z = local['divider_z']

    def place(x, y, z):
        return (ox + x, oy + y, oz + z)

    parts = []

    # 1) 开放式钢制柜体：直角外壳扣除内腔，前端不封板。
    shell_outer = _create_box_body(
        place(left, front, bottom), place(right, rear, top), dgn_model)
    shell_inner = _create_box_body(
        place(left + WALL_THICKNESS, front - 1.0, bottom + WALL_THICKNESS),
        place(right - WALL_THICKNESS, rear - WALL_THICKNESS, top - WALL_THICKNESS),
        dgn_model)
    if shell_outer is None or shell_inner is None or not _subtract_body(shell_outer, shell_inner):
        _log('cabinet shell creation failed')
        return None
    shell = _body_to_element(shell_outer, dgn_model, RED_COLOR_INDEX, 'cabinet shell')
    if shell is None:
        return None
    parts.append(shell)

    # 2) 上下分隔隔板。
    shelf = _create_solid_box(
        place(left + WALL_THICKNESS, front, divider_z),
        place(right - WALL_THICKNESS, rear - WALL_THICKNESS, divider_z + DIVIDER_THICKNESS),
        dgn_model, RED_COLOR_INDEX, 'divider shelf', add_to_model=False)
    if shelf is not None:
        parts.append(shelf)

    extinguisher_variant = None
    extinguishers_placed = 0
    extinguisher_fallback = False
    if with_equipment:
        # 3) 下部储物区的灭火器外观模型（华海 MF/ABCE 配方，嵌套命名单元）。
        #    生成失败时回退为简化圆柱示意，不拖垮整个柜体放置。
        if extinguisher_quantity > 0:
            extinguisher_variant = _extinguisher_variant_key(
                extinguisher_model, width, depth, lower_height,
                extinguisher_quantity)
            if extinguisher_variant is None:
                _log('no fitting extinguisher visual model for %s x%d; skipping'
                     % (extinguisher_model, extinguisher_quantity))
            else:
                recipe = _ext_build_recipe(extinguisher_variant)
                try:
                    for bottle in _extinguisher_layout(
                            local, extinguisher_quantity, extinguisher_variant):
                        world_x, world_y, world_z = place(
                            bottle['center_x'], bottle['center_y'],
                            bottle['bottom_z'])
                        extinguisher_origin = DPoint3d(
                            mm(world_x, dgn_model), mm(world_y, dgn_model),
                            mm(world_z, dgn_model))
                        extinguisher_cell = _build_extinguisher_cell(
                            recipe, extinguisher_origin, 0.0, dgn_model)
                        parts.append(extinguisher_cell)
                        extinguishers_placed += 1
                except Exception as error:
                    _log('extinguisher visual model exception: %r' % error)
                if extinguishers_placed < extinguisher_quantity:
                    extinguisher_fallback = True
                    for index in range(extinguishers_placed, extinguisher_quantity):
                        bottle = _extinguisher_layout(
                            local, extinguisher_quantity, extinguisher_variant)[index]
                        body = _create_prism_element(
                            place(bottle['center_x'], bottle['center_y'],
                                  bottle['bottom_z']),
                            (0.0, 0.0, 1.0), bottle['radius'],
                            bottle['total_height'], dgn_model,
                            RED_COLOR_INDEX, 'extinguisher_%d' % (index + 1))
                        if body is not None:
                            parts.append(body)

        # 4) 上部卷盘：轮毂 + 两片侧板，轴线沿 Y。
        reel = _reel_layout(local)
        hub = _create_prism_element(
            place(reel['center_x'], reel['y_front'], reel['center_z']),
            (0.0, 1.0, 0.0), reel['hub_radius'], reel['reel_width'],
            dgn_model, RED_COLOR_INDEX, 'reel hub')
        if hub is not None:
            parts.append(hub)
        flange_positions = (
            ('reel flange back', reel['y_back'] - reel['flange_thickness']),
            ('reel flange front', reel['y_front']),
        )
        for label, flange_y in flange_positions:
            flange = _create_prism_element(
                place(reel['center_x'], flange_y, reel['center_z']),
                (0.0, 1.0, 0.0), reel['radius'], reel['flange_thickness'],
                dgn_model, RED_COLOR_INDEX, label)
            if flange is not None:
                parts.append(flange)

        # 5) 卷盘给水管 DN25：隔板上方 100，由柜体左侧穿出，经阀门、管套与螺纹接口。
        supply = _supply_layout(local)
        supply_y = supply['y']
        supply_z = supply['z']
        pipe = _create_prism_element(
            place(supply['outer_x'], supply_y, supply_z), (1.0, 0.0, 0.0),
            supply['radius'], supply['length'], dgn_model,
            YELLOW_COLOR_INDEX, 'reel supply pipe')
        if pipe is not None:
            parts.append(pipe)
        # 穿墙管套（器材表第 8 项）。
        sleeve = _create_prism_element(
            place(left - SLEEVE_LENGTH / 2.0, supply_y, supply_z), (1.0, 0.0, 0.0),
            SLEEVE_RADIUS, SLEEVE_LENGTH, dgn_model, RED_COLOR_INDEX, 'pipe sleeve')
        if sleeve is not None:
            parts.append(sleeve)
        # 接出端螺纹接口（DN25 外螺纹短节，不做法兰片）。
        nipple = _create_prism_element(
            place(supply['outer_x'], supply_y, supply_z), (1.0, 0.0, 0.0),
            SUPPLY_THREAD_RADIUS, SUPPLY_THREAD_LENGTH, dgn_model,
            YELLOW_COLOR_INDEX, 'threaded nipple')
        if nipple is not None:
            parts.append(nipple)
        valve = _create_prism_element(
            place(supply['valve_x'] - VALVE_BODY_LENGTH / 2.0, supply_y, supply_z),
            (1.0, 0.0, 0.0), VALVE_BODY_RADIUS, VALVE_BODY_LENGTH, dgn_model,
            YELLOW_COLOR_INDEX, 'valve body')
        if valve is not None:
            parts.append(valve)
        wheel = _create_prism_element(
            place(supply['valve_x'], supply_y, supply_z + VALVE_WHEEL_HEIGHT),
            (0.0, 0.0, 1.0), VALVE_WHEEL_RADIUS, VALVE_WHEEL_THICKNESS, dgn_model,
            YELLOW_COLOR_INDEX, 'valve wheel')
        if wheel is not None:
            parts.append(wheel)

        # 6) 直流喷雾喷枪（枪管沿 X + 下挂手柄）。
        gun_x = left + 70.0
        gun_y = front + 60.0
        gun_z = divider_z + 70.0
        barrel = _create_prism_element(
            place(gun_x, gun_y, gun_z), (1.0, 0.0, 0.0),
            GUN_BARREL_RADIUS, GUN_BARREL_LENGTH, dgn_model,
            YELLOW_COLOR_INDEX, 'spray gun barrel')
        if barrel is not None:
            parts.append(barrel)
        handle = _create_prism_element(
            place(gun_x + 40.0, gun_y, gun_z - GUN_HANDLE_LENGTH),
            (0.0, 0.0, 1.0), GUN_HANDLE_RADIUS, GUN_HANDLE_LENGTH,
            dgn_model, YELLOW_COLOR_INDEX, 'spray gun handle')
        if handle is not None:
            parts.append(handle)

    # 7) 柜门（上、下两处观察窗）+ 门把手。
    door = _create_box_body(
        place(left, front - DOOR_THICKNESS, bottom),
        place(right, front, top), dgn_model)
    if door is not None:
        window_bands = (
            (max(divider_z + 150.0,
                 _reel_center_z(local) - REEL_DIAMETER / 2.0 - 10.0), top - 20.0),
            (bottom + 60.0, divider_z - 15.0),
        )
        for window_z0, window_z1 in window_bands:
            if window_z1 <= window_z0:
                continue
            window = _create_box_body(
                place(left + WINDOW_MARGIN, front - DOOR_THICKNESS - 1.0, window_z0),
                place(right - WINDOW_MARGIN, front + 1.0, window_z1), dgn_model)
            if window is not None:
                _subtract_body(door, window)
        door_element = _body_to_element(door, dgn_model, RED_COLOR_INDEX, 'cabinet door')
        if door_element is not None:
            parts.append(door_element)
        handle_element = _create_solid_box(
            place(right - 70.0, front - DOOR_THICKNESS - 14.0, divider_z + 30.0),
            place(right - 54.0, front - DOOR_THICKNESS, divider_z + 130.0),
            dgn_model, YELLOW_COLOR_INDEX, 'door handle', add_to_model=False)
        if handle_element is not None:
            parts.append(handle_element)

    # 8) 柜门标识文字，朝 -Y。
    front_orientation = RotMatrix.FromVectorAndRotationAngle(
        DVec3d.From(1.0, 0.0, 0.0), math.pi / 2.0)
    title_height = max(18.0, min(height * 0.05, 34.0))
    text_y = front - DOOR_THICKNESS - 0.3
    title = _create_text(
        u'轻便消防水龙柜', place(0.0, text_y, divider_z + 95.0),
        title_height, dgn_model, front_orientation, add_to_model=False)
    if title is not None:
        parts.append(title)
    phone = _create_text(
        u'火警电话 119', place(0.0, text_y, divider_z + 50.0),
        max(12.0, title_height * 0.6), dgn_model, front_orientation,
        add_to_model=False)
    if phone is not None:
        parts.append(phone)

    cell = _create_cabinet_cell(parts, dgn_model)
    if cell is None:
        _log('cabinet Cell creation failed')
        return None
    if not _attach_cabinet_item(cell, width, depth, height, lower_height,
                                extinguisher_model, extinguisher_quantity):
        _log('cabinet item attach failed; removing incomplete cabinet')
        cell.DeleteFromModel()
        return None
    _log('created cabinet Cell: %s, cell=%d' % (CABINET_MODEL, cell.GetElementId()))
    return {'cell': cell, 'parts': tuple(parts), 'width': width,
            'depth': depth, 'height': height, 'lowerHeight': lower_height,
            'extinguisherModel': extinguisher_model,
            'extinguisherQuantity': extinguisher_quantity,
            'extinguisherVariant': extinguisher_variant,
            'extinguishersPlaced': extinguishers_placed,
            'extinguisherFallback': extinguisher_fallback}


def _reel_center_z(layout):
    return _reel_layout(layout)['center_z']


def _read_item_value(item, property_name, kind):
    value = ECValue()
    status = item.GetValue(value, property_name)
    if ECObjectsStatus.eECOBJECTS_STATUS_Success != status or value.IsNull():
        return None
    if kind == 'integer':
        return value.GetInteger()
    if kind == 'double':
        return value.GetDouble()
    return value.GetString()


def _record_bom_rows(item):
    rows = _parse_bom_rows(_read_item_value(item, 'BomJson', 'string') or '')
    if rows:
        return rows
    width = _read_item_value(item, 'WidthMm', 'double') or DEFAULT_WIDTH
    depth = _read_item_value(item, 'DepthMm', 'double') or DEFAULT_DEPTH
    height = _read_item_value(item, 'HeightMm', 'double') or DEFAULT_HEIGHT
    model = _read_item_value(item, 'ExtinguisherModel', 'string') or ''
    quantity = _read_item_value(item, 'ExtinguisherQuantity', 'integer') or 0
    return _build_bom_rows(width, depth, height, model, quantity)


def get_light_hose_cabinet_statistics():
    """扫描当前 DGN，返回明细、柜型汇总、《主要器材表》合计与灭火器合计。"""
    dgn_file = ISessionMgr.GetActiveDgnFile()
    library = ItemTypeLibrary.FindByName(ITEM_LIBRARY_NAME, dgn_file)
    if library is None:
        return {'records': [], 'summary': [], 'materialSummary': [],
                'totalCabinetCount': 0, 'totalComponentCount': 0,
                'totalExtinguisherCount': 0}
    scope = FindInstancesScope.CreateScope(
        dgn_file, FindInstancesScopeOption(DgnECHostType.eElement, False))
    query = ECQuery.CreateQuery(ECQueryProcessFlags.eECQUERY_PROCESS_SearchAllClasses)
    schema_name = str(library.GetInternalName())
    records = []
    summary_map = {}
    material_groups = []
    for item in DgnECManager.GetManager().FindInstances(scope, query)[0]:
        item_class = item.GetClass()
        if (str(item_class.GetSchema().GetName()) != schema_name or
                not str(item_class.GetName()).startswith(ITEM_TYPE_PREFIX + '_')):
            continue
        element_instance = item.GetAsElementInstance()
        if element_instance is None:
            continue
        cabinet_quantity = _read_item_value(item, 'CabinetQuantity', 'integer') or 1
        rows = _record_bom_rows(item)
        extinguisher_quantity = _read_item_value(item, 'ExtinguisherQuantity', 'integer')
        if extinguisher_quantity is None:
            extinguisher_quantity = sum(
                row['qty'] for row in rows if row.get('code') == 'Extinguisher')
        record = {
            'elementId': int(element_instance.ElementHandle.ElementId),
            'itemType': str(item_class.GetName()),
            'cabinetModel': _read_item_value(item, 'CabinetModel', 'string') or CABINET_MODEL,
            'widthMm': _read_item_value(item, 'WidthMm', 'double'),
            'depthMm': _read_item_value(item, 'DepthMm', 'double'),
            'heightMm': _read_item_value(item, 'HeightMm', 'double'),
            'cabinetQuantity': cabinet_quantity,
            'componentKinds': int(_read_item_value(item, 'ComponentKinds', 'integer') or len(rows)),
            'extinguisherModel': _read_item_value(item, 'ExtinguisherModel', 'string'),
            'extinguisherQuantity': int(extinguisher_quantity),
            'extinguisherVisualCell': _read_item_value(item, 'ExtinguisherVisualCell', 'string'),
            'extinguisherVisualSpec': _read_item_value(item, 'ExtinguisherVisualSpec', 'string'),
        }
        records.append(record)
        key = record['cabinetModel']
        summary_map[key] = summary_map.get(key, 0) + cabinet_quantity
        material_groups.append((rows, cabinet_quantity))
    records.sort(key=lambda record: record['elementId'])
    summary = [{'cabinetModel': key, 'cabinetCount': summary_map[key]}
               for key in sorted(summary_map)]
    material_summary = _aggregate_bom_materials(material_groups)
    return {
        'records': records,
        'summary': summary,
        'materialSummary': material_summary,
        'totalCabinetCount': sum(record['cabinetQuantity'] for record in records),
        'totalComponentCount': sum(item['totalQty'] for item in material_summary),
        'totalExtinguisherCount': sum(
            record['extinguisherQuantity'] * record['cabinetQuantity']
            for record in records),
    }


def export_light_hose_cabinet_bom_json(output_path=None):
    """导出当前 DGN 的水龙柜明细与器材合计为 JSON 清单。"""
    statistics = get_light_hose_cabinet_statistics()
    payload = {
        'standard': STANDARD,
        'drawingPage': DRAWING_PAGE,
        'cabinetModel': CABINET_MODEL,
        'exportedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'totalCabinetCount': statistics['totalCabinetCount'],
        'totalComponentCount': statistics['totalComponentCount'],
        'totalExtinguisherCount': statistics['totalExtinguisherCount'],
        'materialSummary': statistics['materialSummary'],
        'summary': statistics['summary'],
        'records': statistics['records'],
    }
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'轻便消防水龙柜_bom.json')
    with open(output_path, 'w', encoding='utf-8') as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
    return output_path, payload


def _xlsx_column_name(column_number):
    name = ''
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(column_number, row_number, value, style_index=0):
    reference = '%s%d' % (_xlsx_column_name(column_number), row_number)
    style = ' s="%d"' % style_index if style_index else ''
    if value is None:
        return '<c r="%s"%s/>' % (reference, style)
    if isinstance(value, bool):
        return '<c r="%s"%s t="b"><v>%d</v></c>' % (reference, style, int(value))
    if isinstance(value, (int, float)):
        return '<c r="%s"%s><v>%s</v></c>' % (reference, style, value)
    text = _xml_escape(str(value))
    return ('<c r="%s"%s t="inlineStr"><is><t xml:space="preserve">%s'
            '</t></is></c>') % (reference, style, text)


def _xlsx_sheet_xml(rows, header_rows=()):
    xml_rows = []
    max_columns = 1
    column_widths = {}
    for row_number, row in enumerate(rows, start=1):
        max_columns = max(max_columns, len(row))
        cells = []
        for column_number, value in enumerate(row, start=1):
            style_index = 1 if row_number in header_rows else 0
            if row_number == 1 and len(row) == 1:
                style_index = 2
            cells.append(_xlsx_cell(column_number, row_number, value, style_index))
            visual_length = len(str(value)) if value is not None else 0
            column_widths[column_number] = max(column_widths.get(column_number, 10),
                                               min(46, visual_length + 2))
        xml_rows.append('<row r="%d">%s</row>' % (row_number, ''.join(cells)))
    columns = ''.join('<col min="%d" max="%d" width="%s" customWidth="1"/>' %
                      (column_number, column_number,
                       column_widths.get(column_number, 12))
                      for column_number in range(1, max_columns + 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<cols>%s</cols><sheetData>%s</sheetData>'
            '</worksheet>') % (columns, ''.join(xml_rows))


def _xlsx_styles_xml():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei UI"/>'
            '</font><font><b/><color rgb="FFFFFFFF"/><sz val="10"/>'
            '<name val="Microsoft YaHei UI"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF222222"/>'
            '<bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/>'
            '</border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" '
            'fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" '
            'applyFill="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" '
            'applyFont="1"/></cellXfs></styleSheet>')


def export_light_hose_cabinet_bom_xlsx(output_path=None):
    """导出当前 DGN 统计为自带样式的 Excel .xlsx 文件（汇总 + 明细两页）。"""
    statistics = get_light_hose_cabinet_statistics()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   u'轻便消防水龙柜_bom.xlsx')

    summary_rows = [
        [u'轻便消防水龙柜统计清单'],
        [u'图集', STANDARD, u'第 %s 页' % DRAWING_PAGE],
        [u'导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        [u'水龙柜总数', statistics['totalCabinetCount']],
        [u'器材总件数', statistics['totalComponentCount']],
        [u'灭火器总数', statistics['totalExtinguisherCount']],
        [],
        [u'柜型', u'数量'],
    ]
    summary_header_rows = {8}
    for item in statistics['summary']:
        summary_rows.append([item['cabinetModel'], item['cabinetCount']])
    summary_rows.append([])
    summary_rows.append([u'主要器材表'])
    summary_rows.append([u'编号', u'名称', u'材质', u'规格', u'单位',
                         u'单柜数量', u'合计数量'])
    summary_header_rows.add(len(summary_rows))
    for item in statistics['materialSummary']:
        summary_rows.append([item['no'], item['name'], item['material'], item['spec'],
                             item['unit'], item['qtyPerSet'], item['totalQty']])

    detail_rows = [[u'元素 ID', u'ItemType', u'柜型', u'宽度 mm', u'进深 mm',
                    u'高度 mm', u'柜数量', u'器材种类',
                    u'灭火器型号', u'灭火器数量', u'灭火器外观模型', u'外观模型规格']]
    for record in statistics['records']:
        detail_rows.append([
            record['elementId'], record['itemType'], record['cabinetModel'],
            record['widthMm'], record['depthMm'], record['heightMm'],
            record['cabinetQuantity'], record['componentKinds'],
            record['extinguisherModel'], record['extinguisherQuantity'],
            record['extinguisherVisualCell'], record['extinguisherVisualSpec'],
        ])

    workbook_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets><sheet name="汇总" sheetId="1" r:id="rId1"/>'
                    '<sheet name="明细" sheetId="2" r:id="rId2"/></sheets></workbook>')
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                         '</Types>')
        archive.writestr('_rels/.rels',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                         '</Relationships>')
        archive.writestr('xl/workbook.xml', workbook_xml)
        archive.writestr('xl/_rels/workbook.xml.rels',
                         '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                         '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
                         '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                         '</Relationships>')
        archive.writestr('xl/styles.xml', _xlsx_styles_xml())
        archive.writestr('xl/worksheets/sheet1.xml',
                         _xlsx_sheet_xml(summary_rows, summary_header_rows))
        archive.writestr('xl/worksheets/sheet2.xml',
                         _xlsx_sheet_xml(detail_rows, {1}))
    return output_path, statistics


ACTIVE_LIGHT_HOSE_CABINET_TOOL = None


class LightHoseCabinetPlacementTool(DgnPrimitiveTool):
    def __init__(self, width, depth, height, lower_height, with_equipment,
                 extinguisher_model, extinguisher_quantity):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.width = width
        self.depth = depth
        self.height = height
        self.lower_height = lower_height
        self.with_equipment = with_equipment
        self.extinguisher_model = extinguisher_model
        self.extinguisher_quantity = extinguisher_quantity
        self.m_self = self

    def _GetToolName(self, name):
        return WString('LightHoseCabinetPlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            u'请点取轻便消防水龙柜底部前侧中心点；X为柜宽、Y为进深、Z向上为高度，正面朝-Y。')

    def _OnDataButton(self, event):
        point = event.GetPoint()
        uor_per_mm = _uor_per_mm()
        origin = (point.x / uor_per_mm, point.y / uor_per_mm,
                  point.z / uor_per_mm)
        try:
            result = create_light_hose_cabinet(
                origin, self.width, self.depth, self.height,
                self.lower_height, self.with_equipment,
                self.extinguisher_model, self.extinguisher_quantity)
        except Exception as error:
            _log('placement exception: %r' % error)
            result = None
        if result is None:
            MessageCenter.ShowErrorMessage(
                u'轻便消防水龙柜生成或附加项写入失败，请查看轻便消防水龙柜_debug_log.txt。',
                '', False)
        else:
            if not self.with_equipment or self.extinguisher_quantity <= 0:
                detail = u''
            elif result.get('extinguishersPlaced') == self.extinguisher_quantity:
                detail = u'灭火器外观模型采用华海 %s。' % _ext_cell_name(
                    result['extinguisherVariant'])
            elif result.get('extinguisherFallback'):
                detail = u'注意：灭火器外观模型生成失败，已用简化圆柱示意，详见调试日志。'
            else:
                detail = u'注意：灭火器外观模型未能生成，详见调试日志。'
            MessageCenter.ShowInfoMessage(
                u'已生成轻便消防水龙柜：%.0f×%.0f×%.0f mm，内含 %s 灭火器 %d 具。%s' %
                (self.width, self.depth, self.height,
                 self.extinguisher_model, self.extinguisher_quantity, detail),
                '', False)
        return True

    def _OnResetButton(self, event):
        NotificationManager.OutputPrompt(u'已取消轻便消防水龙柜定位。')
        return True

    @staticmethod
    def InstallNewInstance(width, depth, height, lower_height, with_equipment,
                           extinguisher_model, extinguisher_quantity):
        global ACTIVE_LIGHT_HOSE_CABINET_TOOL
        ACTIVE_LIGHT_HOSE_CABINET_TOOL = LightHoseCabinetPlacementTool(
            width, depth, height, lower_height, with_equipment,
            extinguisher_model, extinguisher_quantity)
        ACTIVE_LIGHT_HOSE_CABINET_TOOL.InstallTool()


def _mix_color(source, target, ratio):
    source = source.lstrip('#')
    target = target.lstrip('#')
    blended = []
    for offset in (0, 2, 4):
        first = int(source[offset:offset + 2], 16)
        second = int(target[offset:offset + 2], 16)
        blended.append(max(0, min(255, int(round(first + (second - first) * ratio)))))
    return '#%02X%02X%02X' % tuple(blended)


def _apply_window_backdrop(root):
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            return
        preference = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33,
                                                   ctypes.byref(preference), 4)
    except Exception:
        pass


def show_light_hose_cabinet_dialog():
    """显示规格选择、当前模型统计与清单导出窗口。"""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as error:
        _log('tkinter unavailable: %r' % error)
        return None

    BG = '#EEF2F7'
    CARD = '#FFFFFF'
    CARD_SOFT = '#F4F7FB'
    BORDER = '#E3E9F1'
    INK = '#1F2A3D'
    MUTED = '#8C97A8'
    ACCENT = '#D93025'

    root = tk.Tk()
    root.title(u'15S202 轻便消防水龙柜')
    root.resizable(False, False)
    root.configure(bg=BG)
    _apply_window_backdrop(root)

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    ui_font = ('Microsoft YaHei UI', 10)
    ui_font_small = ('Microsoft YaHei UI', 9)
    ui_font_bold = ('Microsoft YaHei UI', 10, 'bold')
    style.configure('Card.TFrame', background=CARD)
    style.configure('Glass.TLabel', background=CARD, foreground=INK, font=ui_font)
    style.configure('GlassMuted.TLabel', background=CARD, foreground=MUTED,
                    font=ui_font)
    style.configure('TSeparator', background=BORDER)
    style.configure('TEntry', font=ui_font, padding=(8, 6),
                    fieldbackground='#FBFCFE', bordercolor=BORDER)

    def make_button(parent, text, command, primary=False):
        font = ui_font_bold if primary else ui_font
        text_width = sum(14 if ord(ch) > 127 else 7 for ch in text)
        width = text_width + 44
        height = 36
        radius = 10
        idle_fill = '#2A3644' if primary else CARD
        hover_fill = '#3D4C5E' if primary else '#F0F5FA'
        idle_edge = '#2A3644' if primary else '#D8E0EA'
        hover_edge = '#3D4C5E' if primary else '#B9C6D6'
        text_fill = '#FFFFFF' if primary else '#33415C'
        canvas = tk.Canvas(parent, width=width, height=height, bg=CARD,
                           highlightthickness=0, bd=0, cursor='hand2')

        def paint(ratio):
            canvas.delete('all')
            fill = _mix_color(idle_fill, hover_fill, ratio)
            edge = _mix_color(idle_edge, hover_edge, ratio)
            x1, y1, x2, y2 = 1, 1, width - 1, height - 1
            points = (x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                      x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                      x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1)
            canvas.create_polygon(points, smooth=True, fill=fill, outline=edge)
            canvas.create_text(width / 2.0, height / 2.0, text=text,
                               fill=text_fill, font=font)

        animator = {'ratio': 0.0, 'target': 0.0, 'job': None}

        def step():
            ratio = animator['ratio']
            target = animator['target']
            if abs(target - ratio) < 0.04:
                animator['ratio'] = target
                animator['job'] = None
                paint(target)
                return
            animator['ratio'] = ratio + (target - ratio) * 0.32
            paint(animator['ratio'])
            animator['job'] = canvas.after(16, step)

        def set_target(target):
            animator['target'] = target
            if animator['job'] is None:
                step()

        canvas.bind('<Enter>', lambda event: set_target(1.0))
        canvas.bind('<Leave>', lambda event: set_target(0.0))
        canvas.bind('<Button-1>', lambda event: command())
        paint(0.0)
        return canvas

    shell = tk.Frame(root, bg=BG, padx=24, pady=22)
    shell.pack(fill='both', expand=True)

    header = tk.Frame(shell, bg=BG)
    header.pack(fill='x', pady=(0, 16))
    title_row = tk.Frame(header, bg=BG)
    title_row.pack(anchor='w')
    dot = tk.Canvas(title_row, width=10, height=10, bg=BG,
                    highlightthickness=0, bd=0)
    dot.create_oval(1, 1, 9, 9, fill=ACCENT, outline='')
    dot.pack(side='left', pady=(9, 0), padx=(0, 8))
    tk.Label(title_row, text=u'轻便消防水龙柜', bg=BG, fg=INK,
             font=('Microsoft YaHei UI', 18, 'bold')).pack(side='left')
    tk.Label(header, text=u'15S202 第 53 页    |    默认规格 1200×550×160',
             bg=BG, fg=MUTED, font=ui_font_small).pack(
                 anchor='w', pady=(4, 0), padx=(18, 0))

    card = tk.Frame(shell, bg=CARD, highlightbackground=BORDER,
                    highlightthickness=1)
    card.pack(fill='both', expand=True)
    form = ttk.Frame(card, style='Card.TFrame', padding=22)
    form.pack(fill='both', expand=True)
    form.columnconfigure(1, weight=1)

    last = _load_last_selection()
    defaults = _editable_fields()
    width_value = tk.StringVar(value=str(last.get('width', defaults[0])))
    depth_value = tk.StringVar(value=str(last.get('depth', defaults[1])))
    height_value = tk.StringVar(value=str(last.get('height', defaults[2])))
    lower_value = tk.StringVar(value=str(last.get('lowerHeight', defaults[3])))
    extinguisher_model = tk.StringVar(
        value=str(last.get('extinguisherModel', DEFAULT_EXTINGUISHER_MODEL)))
    extinguisher_quantity = tk.StringVar(
        value=str(last.get('extinguisherQuantity', DEFAULT_EXTINGUISHER_QUANTITY)))
    with_equipment = tk.BooleanVar(value=bool(last.get('withEquipment', True)))
    note = tk.StringVar()

    ttk.Label(form, text=u'规格参数（mm）', style='GlassMuted.TLabel',
              font=ui_font_small).grid(row=0, column=0, columnspan=2, sticky='w')
    rows = (
        (u'柜体宽度 X', width_value),
        (u'柜体进深 Y', depth_value),
        (u'柜体高度 Z', height_value),
        (u'下部储物区高度', lower_value),
    )
    for index, (label_text, variable) in enumerate(rows, start=1):
        ttk.Label(form, text=label_text, style='GlassMuted.TLabel').grid(
            row=index, column=0, sticky='w', pady=5)
        ttk.Entry(form, textvariable=variable, width=14).grid(
            row=index, column=1, sticky='w', padx=(12, 0), pady=5)

    ttk.Label(form, text=u'灭火器型号', style='GlassMuted.TLabel').grid(
        row=5, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=extinguisher_model, width=24).grid(
        row=5, column=1, sticky='w', padx=(12, 0), pady=5)
    ttk.Label(form, text=u'灭火器数量（具）', style='GlassMuted.TLabel').grid(
        row=6, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=extinguisher_quantity, width=10).grid(
        row=6, column=1, sticky='w', padx=(12, 0), pady=5)

    equipment_check = tk.Checkbutton(
        form, text=u'生成内部设备（卷盘 / 灭火器 / 阀门 / 喷枪）',
        variable=with_equipment, bg=CARD, fg=INK, activebackground=CARD,
        selectcolor=CARD_SOFT, font=ui_font, anchor='w')
    equipment_check.grid(row=7, column=0, columnspan=2, sticky='w', pady=(8, 0))

    note_chip = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
    note_chip.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(14, 0))
    tk.Label(note_chip, textvariable=note, bg=CARD_SOFT, fg='#5B6B82',
             font=ui_font_small, wraplength=460, justify='left').pack(
                 anchor='w', padx=12, pady=8)
    note.set(u'点取点为柜体底部前侧中心。灭火器采用华海 MF/ABCE 外观模型（内含筒身'
             u'圆角、阀门、手柄、压力表、软管等细节）：型号中的数字为公称充装量，'
             u'按就近原则映射 2/4/5/6/8 kg 规格，映射结果写入 ItemType。'
             u'型号与数量计入统计与导出。')

    def read_dimensions():
        return (float(width_value.get()), float(depth_value.get()),
                float(height_value.get()), float(lower_value.get()))

    def read_extinguisher():
        model = extinguisher_model.get().strip() or DEFAULT_EXTINGUISHER_MODEL
        return model, int(extinguisher_quantity.get())

    def show_statistics():
        statistics = get_light_hose_cabinet_statistics()
        details = [u'轻便消防水龙柜：%d 个' % statistics['totalCabinetCount'],
                   u'器材合计：%d 件' % statistics['totalComponentCount'],
                   u'灭火器合计：%d 具' % statistics['totalExtinguisherCount']]
        for item in statistics['materialSummary']:
            details.append(u'%s %s（%s）：%d %s' % (
                item['name'], item['spec'], item['material'],
                item['totalQty'], item['unit']))
        messagebox.showinfo(u'当前模型统计', '\n'.join(details), parent=root)

    def export_json():
        try:
            output_path, payload = export_light_hose_cabinet_bom_json()
            messagebox.showinfo(
                u'导出完成', u'已导出 JSON 清单：\n%s\n\n水龙柜：%d 个\n器材：%d 件\n灭火器：%d 具' % (
                    output_path, payload['totalCabinetCount'],
                    payload['totalComponentCount'],
                    payload['totalExtinguisherCount']), parent=root)
        except Exception as error:
            _log('JSON export exception: %r' % error)
            messagebox.showerror(u'导出失败', u'请查看轻便消防水龙柜_debug_log.txt。',
                                 parent=root)

    def export_excel():
        try:
            output_path, statistics = export_light_hose_cabinet_bom_xlsx()
            messagebox.showinfo(
                u'导出完成', u'已导出 Excel 清单：\n%s\n\n水龙柜：%d 个\n器材：%d 件\n灭火器：%d 具' % (
                    output_path, statistics['totalCabinetCount'],
                    statistics['totalComponentCount'],
                    statistics['totalExtinguisherCount']), parent=root)
        except Exception as error:
            _log('Excel export exception: %r' % error)
            messagebox.showerror(
                u'导出失败', u'Excel 导出失败，请查看轻便消防水龙柜_debug_log.txt。',
                parent=root)

    def start_placement():
        try:
            width, depth, height, lower_height = read_dimensions()
            model, quantity = read_extinguisher()
        except ValueError:
            messagebox.showerror(u'参数错误', u'尺寸与灭火器数量必须为数字。', parent=root)
            return
        error = _validate_dimensions(width, depth, height, lower_height)
        if error is not None:
            messagebox.showerror(u'参数错误', error, parent=root)
            return
        error = _extinguisher_fit_error(width, depth, lower_height, model, quantity)
        if error is not None:
            messagebox.showerror(u'参数错误', error, parent=root)
            return
        _save_last_selection({
            'width': width, 'depth': depth, 'height': height,
            'lowerHeight': lower_height, 'withEquipment': bool(with_equipment.get()),
            'extinguisherModel': model, 'extinguisherQuantity': quantity,
        })
        root.destroy()
        LightHoseCabinetPlacementTool.InstallNewInstance(
            width, depth, height, lower_height, bool(with_equipment.get()),
            model, quantity)

    button_bar = tk.Frame(form, bg=CARD)
    button_bar.grid(row=9, column=0, columnspan=2, sticky='ew', pady=(16, 0))
    make_button(button_bar, u'统计当前模型', show_statistics).pack(
        side='left', padx=(0, 8))
    make_button(button_bar, u'导出 JSON 清单', export_json).pack(
        side='left', padx=(0, 8))
    make_button(button_bar, u'导出 Excel 清单', export_excel).pack(side='left')
    make_button(button_bar, u'下一步：点取位置', start_placement,
                primary=True).pack(side='right')
    root.mainloop()


if __name__ == '__main__':
    show_light_hose_cabinet_dialog()
