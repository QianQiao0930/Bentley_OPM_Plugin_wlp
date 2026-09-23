# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为几何 / 数据逻辑库供 ``K1-[不保温管的限位架].py`` 等插件
# ``import`` 调用，没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中
# 直接加载本文件运行。
# =============================================================================
"""K1 限位架（不保温管的限位架 1/2″~36″）几何 / 数据逻辑（可脱离 Bentley 单测）。

图集要点：

* 两组限位块沿管轴**一前一后**，中间夹着（与管轴垂直的）已有钢结构，间距 =
  用户输入的已有钢构宽度 W。
* 子项 A（DN15~80 / 1/2″~3″）：H100×100×6×8 沿腹板高度中点剖开取半片 **T 形**
  （翼缘 100×8 + 腹板 6×42，总深 50），**竖直放置**；管道焊在其顶端截面，
  剩余的那个翼缘（内侧竖直面）夹住已有钢构；**无底板**。
* 子项 B/C（DN100~250 / DN300~900）：**水平工字钢、长度沿管轴**——腹板水平、
  两翼缘竖直，管道骑在**两翼缘端面**上（截面即「H 上面一个 O」）；底板
  150×150×10 / 200×200×10 焊在朝已有钢构那一端的**截面**上（不是下翼缘底面）。
* 不建：管道本体、已有钢结构/混凝土、弧形垫板、筋板。
* 编号：``K1-子项-管径``（注 5：子项 A 的管径可省略）。
* 注 2：k = 焊缝腰高 = 管壁厚，最大 6（仅用于说明，不建模）。

局部坐标约定（单根限位块，``side`` = +1 在管轴 +方向前侧 / −1 后侧）：

    u = 管轴方向（水平；限位块朝已有钢构的夹紧方向）
    v = 垂直管轴的水平方向
    z = 竖直向上

截面局部坐标：
  * T 形（子项 A）：位于 u-v **水平面**、沿 +z 拉伸；局部原点 = 翼缘外侧面中点，
    x→±u、y→±v；
  * H 型钢（B/C）：位于 v-z **竖直面**、沿 ±u 拉伸；局部原点 = 截面几何中心，
    x→±z（翼缘宽）、y→±v（截面高，即两翼缘净距）。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_hbeam_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 管径（ASME B36.10M 外径，mm）
# ---------------------------------------------------------------------------

DN_OD_TABLE = (
    (15, 21.3), (20, 26.7), (25, 33.4), (32, 42.2), (40, 48.3), (50, 60.3),
    (65, 73.0), (80, 88.9), (90, 101.6), (100, 114.3), (125, 141.3),
    (150, 168.3), (200, 219.1), (250, 273.0), (300, 323.8), (350, 355.6),
    (400, 406.4), (450, 457.0), (500, 508.0), (600, 609.6), (650, 660.4),
    (700, 711.2), (750, 762.0), (800, 812.8), (850, 863.6), (900, 914.4),
)

NPS_BY_DN = {
    15: '1/2"', 20: '3/4"', 25: '1"', 32: '1 1/4"', 40: '1 1/2"', 50: '2"',
    65: '2 1/2"', 80: '3"', 100: '4"', 125: '5"', 150: '6"', 200: '8"',
    250: '10"', 300: '12"', 350: '14"', 400: '16"', 450: '18"', 500: '20"',
    600: '24"', 650: '26"', 700: '28"', 750: '30"', 800: '32"', 850: '34"',
    900: '36"',
}

# 子项定义。
#   kind='t_half'：子项 A 的半片 T 形（竖直）；kind='hbeam'：完整 H 型钢（水平，沿管轴）。
#   t_half: height_mm 立柱竖直长度；footprint_u_mm 截面沿 u 的深度；
#           footprint_v_mm 截面沿 v 的尺寸（翼缘宽 100）。
#   hbeam : length_mm 型钢沿管轴的长度；cross_h_mm 两翼缘净距（H）；
#           cross_b_mm 翼缘宽度（B）。
#   plate : (边长, 边长, 厚) 底板；None 表示无底板。
SUBITEMS = (
    {
        'key': 'A', 'dn_min': 15, 'dn_max': 80, 'nps': '1/2"~3"',
        'kind': 't_half', 'profile': 'H100x100x6x8xr8',
        'height_mm': 100.0, 'footprint_u_mm': 50.0, 'footprint_v_mm': 100.0,
        'plate': None, 'spec': '1/2 H100×100×6×8',
    },
    {
        'key': 'B', 'dn_min': 100, 'dn_max': 250, 'nps': '4"~10"',
        'kind': 'hbeam', 'profile': 'H100x100x6x8xr8',
        'length_mm': 150.0, 'cross_h_mm': 100.0, 'cross_b_mm': 100.0,
        'plate': (150.0, 150.0, 10.0), 'spec': 'H100×100×6×8',
    },
    {
        'key': 'C', 'dn_min': 300, 'dn_max': 900, 'nps': '12"~36"',
        'kind': 'hbeam', 'profile': 'H150x150x7x10xr8',
        'length_mm': 200.0, 'cross_h_mm': 150.0, 'cross_b_mm': 150.0,
        'plate': (200.0, 200.0, 10.0), 'spec': 'H150×150×7×10',
    },
)

SUBITEM_BY_KEY = {item['key']: item for item in SUBITEMS}
DEFAULT_SUBITEM = 'A'

# 几何常量（图注 / 图中未给死处集中在此）。
WELD_LEG_MAX_MM = 6.0          # 注 2：k = 焊缝腰高 = 管壁厚，最大 6
GAP_MM = 3.0                   # 图中「3」（焊接/装配间隙，仅作记录）
DEFAULT_EXISTING_WIDTH_MM = 100.0  # 底部已有钢构宽度的默认值（用户可改）
DEFAULT_MATERIAL = 'Q235B'


def dn_choices():
    return tuple(dn for dn, _od in DN_OD_TABLE)


def od_mm(dn):
    dn = int(dn)
    for key, value in DN_OD_TABLE:
        if key == dn:
            return float(value)
    raise KeyError('未知公称直径：DN%d' % dn)


def nps_text(dn):
    return NPS_BY_DN.get(int(dn), '')


def dn_label(dn):
    dn = int(dn)
    nps = nps_text(dn)
    return 'DN%d（%s）' % (dn, nps) if nps else 'DN%d' % dn


def match_dn(nominal_mm, tolerance=5.0, ratio=0.05):
    """把管道信息里的直径（公称值或外径）匹配到最近 DN；超出容差返回 None。"""
    try:
        value = float(nominal_mm)
    except (TypeError, ValueError):
        return None
    by_dn = min(DN_OD_TABLE, key=lambda row: abs(row[0] - value))
    error_dn = abs(by_dn[0] - value)
    by_od = min(DN_OD_TABLE, key=lambda row: abs(row[1] - value))
    error_od = abs(by_od[1] - value)
    best, error = (by_dn, error_dn) if error_dn <= error_od else (by_od, error_od)
    if error <= max(tolerance, ratio * best[1]):
        return best[0]
    return None


def subitem_choices():
    return tuple(item['key'] for item in SUBITEMS)


def get_subitem(key):
    try:
        return SUBITEM_BY_KEY[str(key).strip().upper()]
    except KeyError:
        raise KeyError('未知子项：%s' % key)


def main_size_mm(item):
    """限位块主尺寸：子项 A = 立柱高；B/C = 型钢沿管轴长度。"""
    return float(item['height_mm'] if item['kind'] == 't_half'
                 else item['length_mm'])


def main_size_label(item):
    return '立柱高 H' if item['kind'] == 't_half' else '型钢沿管轴长 L'


def subitem_label(key):
    item = get_subitem(key)
    plate = ' + 底板 %.0f×%.0f×%.0f' % item['plate'] if item['plate'] else ''
    return '%s：DN%d~%d（%s）· %s（%s %.0f）%s' % (
        item['key'], item['dn_min'], item['dn_max'], item['nps'], item['spec'],
        main_size_label(item).split()[-1], main_size_mm(item), plate)


def subitem_for_dn(dn):
    dn = int(dn)
    for item in SUBITEMS:
        if item['dn_min'] <= dn <= item['dn_max']:
            return item['key']

    def distance(item):
        if dn < item['dn_min']:
            return item['dn_min'] - dn
        return dn - item['dn_max']
    return min(SUBITEMS, key=distance)['key']


def build_number(subitem, dn):
    """管架编号：``K1-子项-管径``（子项 A 省略管径）。"""
    item = get_subitem(subitem)
    if item['kind'] == 't_half':          # 子项 A：管径可省略（注 5）
        return 'K1-%s' % item['key']
    return 'K1-%s-%d' % (item['key'], int(dn))


# ---------------------------------------------------------------------------
# 构件截面（局部 2D）
# ---------------------------------------------------------------------------

_Point2d = namedtuple('_Point2d', 'x y')
_LineSegment = namedtuple('_LineSegment', 'start end')


class TProfileGeometry(object):
    """子项 A 的半片 T 形截面（局部原点 = 翼缘外侧面中点，腹板沿 +x）。

    取自 H100×100×6×8 沿腹板高度中点剖开的一半：翼缘 100×8 + 腹板 6×42，总深 50。
    """

    def __init__(self, flange_width, flange_thickness, web_thickness,
                 web_length, scale=1.0):
        fw = float(flange_width) * scale
        ft = float(flange_thickness) * scale
        wt = float(web_thickness) * scale
        wl = float(web_length) * scale
        self.section = {
            'flange_width': fw, 'flange_thickness': ft,
            'web_thickness': wt, 'web_length': wl, 'depth': ft + wl,
        }
        half_fw = fw / 2.0
        half_wt = wt / 2.0
        points = (
            _Point2d(0.0, -half_fw),
            _Point2d(0.0, half_fw),
            _Point2d(ft, half_fw),
            _Point2d(ft, half_wt),
            _Point2d(ft + wl, half_wt),
            _Point2d(ft + wl, -half_wt),
            _Point2d(ft, -half_wt),
            _Point2d(ft, -half_fw),
        )
        self.segments = tuple(
            _LineSegment(points[index], points[(index + 1) % len(points)])
            for index in range(len(points)))

    @property
    def arc_count(self):
        return 0

    @property
    def line_count(self):
        return len(self.segments)

    def is_closed_and_continuous(self, tolerance=1.0e-9):
        count = len(self.segments)
        return all(
            math.hypot(
                self.segments[(index + 1) % count].start.x - segment.end.x,
                self.segments[(index + 1) % count].start.y - segment.end.y)
            <= tolerance
            for index, segment in enumerate(self.segments))


def member_geometry(subitem, scale=1.0):
    """构建单根限位块的截面轮廓（局部 2D，mm 或按 ``scale`` 缩放到 UOR）。"""
    scale = float(scale)
    item = get_subitem(subitem)
    section = steel_hbeam_data.get_section(item['profile'])
    if item['kind'] == 't_half':
        return TProfileGeometry(
            float(section['B']), float(section['t2']), float(section['t1']),
            float(section['H']) / 2.0 - float(section['t2']), scale)
    scaled = steel_hbeam_geometry.scale_section(section, scale)
    return steel_hbeam_geometry.build_hbeam_geometry(
        scaled, steel_hbeam_geometry.INSERTION_GEOMETRIC,
        steel_hbeam_geometry.Point2d(0.0, 0.0))


def _cross3(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def _section_t2(item):
    return float(steel_hbeam_data.get_section(item['profile'])['t2'])


def flange_seat(subitem, od):
    """返回 ``(contact_offset_mm, gap_mm)``。

    * ``contact_offset_mm``：管道骑在两翼缘端面上时，**管轴 → 翼缘端面（顶面）**
      的高差 = ``sqrt((OD/2)² − (b/2)²)``，其中 ``b = 型钢宽度 − 2×翼缘厚``
      （两翼缘净距）。
    * ``gap_mm``：**钢板顶面与翼缘端面的间距**——按图注算法：以 OD 为两腰、
      ``b`` 为底边作等腰三角形，底边到顶点的高 ``h = sqrt(OD² − (b/2)²)``，
      则 ``gap = 2 × (OD − h)``（≈ 管底到翼缘端面的高度，使钢板顶面落到管底、
      不扎进管子）。
    子项 A（无底板）返回 ``(OD/2, 0)``。
    """
    item = get_subitem(subitem)
    od = float(od)
    if item['kind'] != 'hbeam':
        return (od / 2.0, 0.0)
    base = float(item['cross_h_mm']) - 2.0 * _section_t2(item)
    half = base / 2.0
    radius = od / 2.0
    if half <= 0.0 or half >= radius:
        raise ValueError(
            '管外径 OD=%.1f 与两翼缘净距 b=%.1f 不匹配（管子骑不住）。'
            % (od, base))
    contact = math.sqrt(radius * radius - half * half)
    h_tri = math.sqrt(od * od - half * half)
    return (contact, max(0.0, 2.0 * (od - h_tri)))


def _horizontal(pipe_dir):
    direction = (float(pipe_dir[0]), float(pipe_dir[1]), 0.0)
    length = math.sqrt(direction[0] ** 2 + direction[1] ** 2)
    if length <= 1.0e-9:
        raise ValueError('管道接近竖直，K1 限位架仅适用于水平管道。')
    return (direction[0] / length, direction[1] / length, 0.0)


def _neg(vector):
    return (-vector[0], -vector[1], -vector[2])


def member_frame(subitem, side, center_mm, existing_width_mm, od,
                 pipe_dir=(1.0, 0.0, 0.0)):
    """返回单根限位块 ``(origin, axis_x, axis_y, axis_z, length_mm)``（世界 mm）。

    ``center_mm`` 为放置点在管轴上的投影；``existing_width_mm`` 为两限位块
    内侧面的间距（已有钢构宽）；``od`` 为管外径。管子底面 = 管轴 − OD/2。
    """
    item = get_subitem(subitem)
    pipe = _horizontal(pipe_dir)
    perp = _cross3((0.0, 0.0, 1.0), pipe)
    cx, cy, cz = float(center_mm[0]), float(center_mm[1]), float(center_mm[2])
    pipe_bottom = cz - float(od) / 2.0
    width = float(existing_width_mm)
    s = 1.0 if side >= 0 else -1.0

    if item['kind'] == 't_half':
        # T 形：竖直立柱，截面在水平面、沿 +z 拉伸；局部 x=0 落在内侧面。
        height = float(item['height_mm'])
        u_inner = s * width / 2.0
        origin = (cx + u_inner * pipe[0], cy + u_inner * pipe[1],
                  pipe_bottom - height)
        axis_x = pipe if s > 0 else _neg(pipe)
        axis_y = perp if s > 0 else _neg(perp)
        return (origin, axis_x, axis_y, (0.0, 0.0, 1.0), height)

    # 完整 H：水平、长度沿管轴；腹板水平、两翼缘竖直（管道骑在两翼缘端面上）。
    length = float(item['length_mm'])
    cross_b = float(item['cross_b_mm'])
    plate_t = float(item['plate'][2]) if item['plate'] else 0.0
    contact, _gap = flange_seat(subitem, od)
    flange_top = cz - contact                      # 翼缘端面（= 管轴下方 contact）
    u_inner_beam = s * (width / 2.0 + plate_t)     # 型钢内端（底板外侧）
    origin = (cx + u_inner_beam * pipe[0], cy + u_inner_beam * pipe[1],
              flange_top - cross_b / 2.0)
    if s > 0:
        return (origin, (0.0, 0.0, -1.0), perp, pipe, length)
    return (origin, (0.0, 0.0, 1.0), perp, _neg(pipe), length)


def sample_member(subitem, side, center_mm, existing_width_mm, od,
                  scale=1.0, pipe_dir=(1.0, 0.0, 0.0)):
    """按坐标架把截面采样为世界点（供纯几何测试）。"""
    from steel_sections import steel_sweep_geometry
    geometry = member_geometry(subitem, scale)
    origin, axis_x, axis_y, axis_z, _length = member_frame(
        subitem, side, center_mm, existing_width_mm, od, pipe_dir)
    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    return tuple(
        steel_sweep_geometry.sample_segment(segment, frame)
        for segment in geometry.segments
    )


PlateBox = namedtuple('PlateBox', 'u0 u1 v0 v1 z0 z1')


def plate_box(subitem, side, center_mm, existing_width_mm, od,
              pipe_dir=(1.0, 0.0, 0.0)):
    """底板局部范围 ``PlateBox``（u 沿管轴、v 垂直管轴、z 绝对标高）；无底板返回 None。

    底板焊在型钢朝已有钢构那一端的**截面**上（垂直于管轴的竖直板）。
    """
    item = get_subitem(subitem)
    if not item['plate']:
        return None
    _pipe = _horizontal(pipe_dir)
    _cx, _cy, cz = (float(center_mm[0]), float(center_mm[1]),
                    float(center_mm[2]))
    width = float(existing_width_mm)
    side_len, _side2, thickness = item['plate']
    contact, gap = flange_seat(subitem, od)
    plate_top = (cz - contact) - gap               # 钢板顶面 = 翼缘端面 − 间距
    s = 1.0 if side >= 0 else -1.0
    if s > 0:
        u0, u1 = width / 2.0, width / 2.0 + thickness
    else:
        u0, u1 = -(width / 2.0 + thickness), -width / 2.0
    return PlateBox(u0, u1, -side_len / 2.0, side_len / 2.0,
                    plate_top - side_len, plate_top)


Layout = namedtuple(
    'Layout',
    'subitem dn od nps existing_width_mm size_mm size_label '
    'plate number spec material')


def build_layout(dn, subitem=None, existing_width_mm=DEFAULT_EXISTING_WIDTH_MM,
                 material=DEFAULT_MATERIAL):
    dn = int(dn)
    if subitem is None:
        subitem = subitem_for_dn(dn)
    item = get_subitem(subitem)
    plate = item['plate']
    return Layout(
        subitem=subitem, dn=dn, od=od_mm(dn), nps=nps_text(dn),
        existing_width_mm=float(existing_width_mm),
        size_mm=main_size_mm(item), size_label=main_size_label(item),
        plate=(tuple(float(v) for v in plate) if plate else None),
        number=build_number(subitem, dn), spec=item['spec'],
        material=str(material or DEFAULT_MATERIAL),
    )


def component_items(layout):
    items = [{
        'code': 'Block', 'name': '限位块（型钢）', 'specification': layout.spec,
        'length': layout.size_mm, 'quantity': 2, 'unit': '件',
    }]
    if layout.plate:
        plate = layout.plate
        items.append({
            'code': 'BasePlate', 'name': '底板',
            'specification': '%.0f×%.0f×%.0f' % (plate[0], plate[1], plate[2]),
            'length': plate[2], 'quantity': 2, 'unit': '块',
        })
    return items


def describe(layout):
    text = ('K1 限位架：DN%d（%s，OD %.1f）；子项 %s（%s）；%s %.0f；'
            '两限位块间距 %.0f（已有钢构宽）；编号 %s。'
            % (layout.dn, layout.nps, layout.od, layout.subitem, layout.spec,
               layout.size_label, layout.size_mm, layout.existing_width_mm,
               layout.number))
    if layout.plate:
        _contact, gap = flange_seat(layout.subitem, layout.od)
        text += (' 底板 %.0f×%.0f×%.0f ×2，顶面比翼缘端面低 %.1f。'
                 % (layout.plate[0], layout.plate[1], layout.plate[2], gap))
    return text
