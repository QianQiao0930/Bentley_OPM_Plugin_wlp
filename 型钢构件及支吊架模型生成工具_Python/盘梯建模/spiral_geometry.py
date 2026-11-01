# -*- coding: utf-8 -*-
"""盘梯参数与几何布局。尺寸统一 mm；不依赖 Bentley。"""
from dataclasses import dataclass
from math import sin, cos, atan, degrees, ceil, isfinite
from upright_beams import build_u_profiles

@dataclass
class Parameters:
    tank_diameter: float = 20000
    start_z: float = 0
    end_z: float = 20000
    landing_interval: float = 10000
    landing_z: float = None  # 兼容旧调用：指定时只设这个休息平台
    riser: float = 200
    tread_depth: float = 250
    clear_width: float = 700
    wall_gap: float = 0
    landing_length: float = 1000
    top_length: float = 1000
    start_angle: float = 0
    direction: int = 1
    plate_thickness: float = 4
    channel_height: float = 200
    channel_leg: float = 100
    channel_thickness: float = 6
    rail_height: float = 1050
    max_slope: float = 50
    chord_tolerance: float = 0.5

def point(radius, angle, z):
    return (radius*cos(angle), radius*sin(angle), z)

def sample(radius, a, b, z0, z1, tolerance):
    # 弦高误差 <= tolerance；端点保留。
    count = max(1, int(ceil(abs(b-a)/(8*tolerance/radius)**0.5)))
    return [point(radius, a+(b-a)*i/count, z0+(z1-z0)*i/count)
            for i in range(count+1)]

def sector(p, inner, outer, a, b, z):
    if b < a:
        a,b = b,a
    return sample(outer, a, b, z-p.plate_thickness, z-p.plate_thickness, p.chord_tolerance) + list(reversed(sample(inner, a, b, z-p.plate_thickness, z-p.plate_thickness, p.chord_tolerance)))

def build_layout(p=None, auxiliary_only=False):
    p = p or Parameters()
    if any(v is not None and not isfinite(float(v)) for v in vars(p).values()):
        raise ValueError('所有参数必须是有限数字。')
    for name in ('tank_diameter','riser','tread_depth','clear_width','landing_interval','landing_length','top_length','plate_thickness','channel_height','channel_leg','channel_thickness','rail_height','chord_tolerance'):
        if getattr(p, name) <= 0:
            raise ValueError(name+' 必须大于零。')
    if p.wall_gap < 0 or p.direction not in (-1, 1):
        raise ValueError('间隙必须非负，旋转方向必须为 ±1。')
    if p.end_z <= p.start_z:
        raise ValueError('终点标高必须高于起点。')
    if p.landing_z is not None and not p.start_z < p.landing_z < p.end_z:
        raise ValueError('休息平台必须位于起终标高之间。')
    if p.clear_width < 650 or min(p.landing_length, p.top_length) < p.clear_width:
        raise ValueError('净宽不得小于650，平台内缘长度不得小于梯宽。')
    if p.channel_thickness*2 >= min(p.channel_height, p.channel_leg):
        raise ValueError('U形截面尺寸无效。')
    # 间隙量指罐壁到内梁腿尖；腹板外角路径还需让出100mm截面宽。
    r = p.tank_diameter/2 + 100.0 + p.wall_gap
    outer = r+p.clear_width
    delta = p.direction*p.tread_depth/r
    if p.landing_z is not None:
        landing_levels = [p.landing_z]
    else:
        landing_levels = [p.start_z+i*p.landing_interval
                          for i in range(1, int(ceil((p.end_z-p.start_z)/p.landing_interval)))
                          if p.start_z+i*p.landing_interval < p.end_z-1.e-6]
    levels = [p.start_z]+landing_levels+[p.end_z]
    counts = []
    for z0,z1 in zip(levels,levels[1:]):
        rise = z1-z0
        n = round(rise/p.riser)
        if n < 1 or abs(n*p.riser-rise) > 1.e-6:
            raise ValueError('每段高度必须为踏步高度的整数倍。')
        counts.append(n)
    slope = degrees(atan(p.riser/p.tread_depth))
    if slope >= p.max_slope:
        raise ValueError('梯段倾角必须小于最大允许值。')
    flights, platform_specs = [], []
    angle = p.start_angle
    for index,count in enumerate(counts):
        end = angle+count*delta
        flights.append((angle,end,levels[index],levels[index+1]))
        length = p.top_length if index == len(counts)-1 else p.landing_length
        exit_angle = end+p.direction*length/r
        platform_specs.append((end,exit_angle,levels[index+1]))
        angle = exit_angle
    treads, channels, rail = [], [], []
    for index,(count, (a,b,z0,z1)) in enumerate(zip(counts, flights)):
        for n in range(1,count+1):
            angle = a+(n-1)*delta
            treads.append(dict(z=z0+n*p.riser, angle=angle,
                               corners=sector(p,r,outer,angle,angle+delta,z0+n*p.riser)))
        # 两侧U开口径向朝外；内侧腿宽占用局部空间，不能自动判净宽通过。
        for radius in (() if auxiliary_only else (r,outer)):
            sections = []
            path = sample(radius,a,b,z0,z1,p.chord_tolerance)
            for x,y,z in path:
                angle = __import__('math').atan2(y,x)
                h,w,t = p.channel_height,p.channel_leg,p.channel_thickness
                outline = [(0,0),(w,0),(w,t),(t,t),(t,h-t),(w,h-t),(w,h),(0,h)]
                sections.append([(x+u*cos(angle),y+u*sin(angle),z+v) for u,v in outline])
            channels.append(sections)
        rail.extend(sample(outer,a,b,z0,z1,p.chord_tolerance)[bool(rail):])
        pa,pb,pz = platform_specs[index]
        rail.extend(sample(outer,pa,pb,pz,pz,p.chord_tolerance)[1:])
    # 平台规格z仍指梁下缘，平台顶面与200mm高梯梁的上缘平齐。
    platforms = [orient_ccw([point(r,a,z+196),point(outer,a,z+196),point(outer,b,z+196),point(r,b,z+196)]) for a,b,z in platform_specs]
    return dict(parameters=p, inner_radius=r, outer_radius=outer, step_angle=abs(delta),
                counts=counts, slope=slope, flight_angle=sum(counts)*abs(delta),
                treads=treads, channels=channels, platforms=platforms,
                rail=rail, flights=flights,
                landing_levels=landing_levels, platform_specs=platform_specs,
                checks=dict(horizontal_treads=True, risers=True, tread_depth=True, slope=True,
                            minimum_structural_width=p.clear_width-p.channel_leg,
                            structural_width_pass=p.clear_width-p.channel_leg>=650,
                            solid_interference="requires_OPM_verification",
                            grating="simplified_plate", rail_continuity="requires_OPM_verification"))


def build_guides(layout):
    """放样辅助线：内外螺旋基准、水平踏步/平台顶面轮廓、中心轴。"""
    p=layout['parameters']
    guides=[]
    for side,radius in (('内',layout['inner_radius']),('外',layout['outer_radius'])):
        points=[]
        platform_segments=[]
        for index,(a,b,z0,z1) in enumerate(layout['flights']):
            flight=sample(radius,a,b,z0,z1,p.chord_tolerance)
            if points and sum((points[-1][i]-flight[0][i])**2 for i in range(3)) > 1.e-12:
                raise ValueError('梯段与平台辅助线端点不连续。')
            points.extend(flight[1:] if points else flight)
            pa,pb,pz=layout['platform_specs'][index]
            # 平台以入口和出口之间的一根水平直线连接，不再采样圆弧。
            platform_segments.append((len(points)-1,len(points)))
            points.append(point(radius,pb,pz))
        guides.append(dict(name=side+'侧完整梯梁路径',points=points,
                           standalone=True,platform_segments=platform_segments))
    guides[1]['return_start']=len(guides[1]['points'])-1
    guides[1]['points'].append(guides[0]['points'][-1])
    for side,path in zip(('inner','outer'),list(guides)):
        # 复用实际梁截面方向，包括顶部横梁的朝外开口和转角斜接。
        # 截面第1点为顶部腿尖外角，正好是栏杆放样基准。
        profiles=build_u_profiles(path['points'],side,p.channel_height,
                                  p.channel_leg,p.channel_thickness,
                                  return_start=path.get('return_start'))
        guides.append(dict(name=path['name'].replace('梯梁','栏杆')+'（梁顶开口外缘）',
                           points=[profile[1] for profile in profiles],
                           standalone=True,platform_segments=list(path['platform_segments']),
                           return_start=path.get('return_start')))
    for index,tread in enumerate(layout['treads']):
        corners=[(x,y,tread['z']) for x,y,z in tread['corners']]
        guides.append(dict(name='踏步%d 顶面轮廓' % (index+1),points=corners+[corners[0]]))
    for index,(boundary,spec) in enumerate(zip(layout['platforms'],layout['platform_specs'])):
        corners=[(x,y,spec[2]+200) for x,y,z in boundary]
        name='顶部平台' if index==len(layout['platforms'])-1 else '休息平台%d' % (index+1)
        guides.append(dict(name=name+' 顶面边界',points=corners+[corners[0]]))
    guides.append(dict(name='罐中心轴',points=[(0,0,p.start_z),(0,0,p.end_z)]))
    return guides


def orient_ccw(points):
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
    return points if area>0 else list(reversed(points))


def build_z_plate_parts(layout,a,b,z,base_corners,back_up=True):
    """横跨两梁的前长边下折、后长边上折，非径向两侧弧边。"""
    p=layout['parameters']
    r0,r1=layout['inner_radius'],layout['outer_radius']
    sign=1 if b>a else -1
    def edge_band(angle,into,base):
        return orient_ccw([point(r0,angle,base),point(r1,angle,base),
                           point(r1,angle+into*4/r1,base),point(r0,angle+into*4/r0,base)])
    parts=[dict(name='水平板向下4mm',corners=base_corners,thickness=4),
           dict(name='前长边下折40mm',corners=edge_band(a,sign,z-40),thickness=40)]
    if back_up:
        parts.append(dict(name='后长边上折40mm',corners=edge_band(b,-sign,z-4),thickness=44))
    return parts


def build_z_tread_parts(layout,tread):
    p=layout['parameters']
    a=tread['angle']
    b=a+p.direction*layout['step_angle']
    return build_z_plate_parts(layout,a,b,tread['z'],tread['corners'])


def build_platform_parts(layout,index):
    """中间及顶部平台均为平板：梁顶平齐，厚度向下4mm，无折边。"""
    return [dict(name='平台平板：梁顶平齐、向下4mm',
                 corners=layout['platforms'][index],thickness=4)]
