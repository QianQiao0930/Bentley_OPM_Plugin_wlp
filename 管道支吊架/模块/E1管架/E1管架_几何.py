# -*- coding: utf-8 -*-
# =============================================================================
# 【公共模块 · 请勿直接运行】
# 本文件仅作为纯几何 / 数据逻辑库供 ``E1-[不保温管导向架].py`` 等插件 ``import`` 调用，
# 没有独立入口。请勿在 OpenPlant Modeler / MicroStation 中直接加载本文件运行。
# =============================================================================
"""E1 管架（不保温管导向架）纯几何 / 数据逻辑（不依赖 Bentley 运行时，可单测）。

图集要点（表 1 与图注）：

* 子项 A~E 按管径选取：A DN15~65、B DN80~150、C DN200~300、D DN350~600、
  E DN650~900；构件A 分别为 □50×50×10、∠50×6、[10、H100×100×6×8、
  H150×150×7×10；允许荷载 1/4/6/35/60 kN。
* 构件A 为**竖直**构件，自**管底标高**（= 管轴 − OD/2）向上拉伸 **H**：
  H = 50（<3″）/ OD/2 + 50（≥3″，圆整到 mm）；构件顶面高出管轴 50。
* 两根构件A 对称分列管道两侧，内侧面距管壁 **3 mm**；不锈钢薄板（仅不锈钢
  管道，材料 06Cr18Ni9）夹在构件A 与管壁之间，此时薄板距管壁 3 mm。
* 每个型钢都以**最宽的平面竖直朝管道**（该平面法向 ⟂ 管轴），其余部分背离
  管道：角钢用平行管轴那条肢的外表面、槽钢用腹板外表面、工字钢用翼缘面、
  钢板用 50×50 面。朝管面宽 = 50 / 50 / 100 / 100 / 150，正好对应薄板宽度。
* 编号：``E1-子项-H``（不锈钢管道再加 ``-S``）。

局部坐标约定（构件A，``side`` = +1 在管轴 +Y 侧 / −1 在 −Y 侧）：

    X = 管轴方向（水平）
    Y = 垂直管轴的水平方向；构件A 自 Y = side·face 起向背离管道一侧延伸
    Z = 竖直向上（构件A 的拉伸方向）

``face`` = 构件A 朝管面到管轴的距离 = OD/2 + 3 [+ 薄板厚]。
"""

from __future__ import division

import math
import os
import sys
from collections import namedtuple

_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 管道支吊架/模块/E1管架/，插件根目录需上溯两级。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)
_STEEL_DIR = os.path.join(_REPO_ROOT, '型钢截面生成器')
if _STEEL_DIR not in sys.path:
    sys.path.insert(0, _STEEL_DIR)


from steel_sections import steel_channel_data  # noqa: E402
from steel_sections import steel_channel_geometry  # noqa: E402
from steel_sections import steel_equal_angle_data  # noqa: E402
from steel_sections import steel_equal_angle_geometry  # noqa: E402
from steel_sections import steel_hbeam_data  # noqa: E402
from steel_sections import steel_hbeam_geometry  # noqa: E402


# ---------------------------------------------------------------------------
# 管径（ASME B36.10M 外径，mm）与子项
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
    65: '2 1/2"', 80: '3"', 90: '3 1/2"', 100: '4"', 125: '5"', 150: '6"',
    200: '8"', 250: '10"', 300: '12"', 350: '14"', 400: '16"', 450: '18"',
    500: '20"', 600: '24"', 650: '26"', 700: '28"', 750: '30"', 800: '32"',
    850: '34"', 900: '36"',
}

# 子项定义（表 1）。``profile`` 为 (族, 参数)：
#   ('plate', (朝管面宽, 厚度)) / ('equal_angle', 规格名) /
#   ('channel', 规格名) / ('hbeam', 规格名)
# ``liner`` = 不锈钢薄板 (宽, 长, 厚)，宽沿管轴、长竖直。
# ``face_width`` = 朝管面宽（沿管轴），``depth`` = 背离管道的深度。
SUBITEMS = (
    {
        'key': 'A', 'dn_min': 15, 'dn_max': 65, 'nps': '1/2"~2 1/2"',
        'profile': ('plate', (50.0, 10.0)), 'face_width': 50.0, 'depth': 10.0,
        'spec': '□50×50×10', 'liner': (50.0, 50.0, 1.0), 'load_kn': 1.0,
    },
    {
        'key': 'B', 'dn_min': 80, 'dn_max': 150, 'nps': '3"~6"',
        'profile': ('equal_angle', 'L50x50x6'), 'face_width': 50.0, 'depth': 50.0,
        'spec': '∠50×6', 'liner': (50.0, 60.0, 2.0), 'load_kn': 4.0,
    },
    {
        'key': 'C', 'dn_min': 200, 'dn_max': 300, 'nps': '8"~12"',
        'profile': ('channel', '10'), 'face_width': 100.0, 'depth': 48.0,
        'spec': '[10', 'liner': (100.0, 80.0, 2.0), 'load_kn': 6.0,
    },
    {
        'key': 'D', 'dn_min': 350, 'dn_max': 600, 'nps': '14"~24"',
        'profile': ('hbeam', 'H100x100x6x8xr8'), 'face_width': 100.0, 'depth': 100.0,
        'spec': 'H100×100×6×8', 'liner': (100.0, 90.0, 2.0), 'load_kn': 35.0,
    },
    {
        'key': 'E', 'dn_min': 650, 'dn_max': 900, 'nps': '26"~36"',
        'profile': ('hbeam', 'H150x150x7x10xr8'), 'face_width': 150.0, 'depth': 150.0,
        'spec': 'H150×150×7×10', 'liner': (150.0, 100.0, 2.0), 'load_kn': 60.0,
    },
)

SUBITEM_BY_KEY = {item['key']: item for item in SUBITEMS}
DEFAULT_SUBITEM = 'A'

# 几何常量（图注 / 图中未给死处集中在此，便于修改）。
PIPE_CLEARANCE_MM = 3.0        # 构件A / 薄板内侧面与管壁的间隙（图注 3 / 注 6）
TOP_ABOVE_AXIS_MM = 50.0       # 构件A 顶面高出管轴（注 2）
SMALL_PIPE_H_MM = 50.0         # <3″ 管道固定 H（注 2）
THREE_INCH_MM = 88.9           # 3″ 管外径
STAINLESS_MARK = 'S'           # 不锈钢管道编号后缀（注 3）
STAINLESS_MATERIAL = '06Cr18Ni9'  # 不锈钢薄板材料（注 4）
DEFAULT_MATERIAL = 'Q235B'     # 构件A 材料（图中未注明，取常用碳钢）
LINER_DN_MARK = True           # 是否建不锈钢薄板


def dn_choices():
    """可选的公称直径（升序）。"""
    return tuple(dn for dn, _od in DN_OD_TABLE)


def od_mm(dn):
    """按 ASME B36.10M 返回公称直径对应的管外径（mm）。"""
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
    """把管道信息里的直径匹配到最近 DN；超出容差返回 None。

    读取库给的是**公称直径**（DN 数值，如 DN250 → 250），但也兼容直接给
    **外径**（如 88.9）的情形：两种解释各取误差较小者。
    """
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


def subitem_label(key):
    item = get_subitem(key)
    return '%s：DN%d~%d（%s）· %s · %.0f kN' % (
        item['key'], item['dn_min'], item['dn_max'], item['nps'],
        item['spec'], item['load_kn'])


def subitem_for_dn(dn):
    """按管径选取子项；落在两档之间时取较近的一档。"""
    dn = int(dn)
    for item in SUBITEMS:
        if item['dn_min'] <= dn <= item['dn_max']:
            return item['key']
    # 区间之外：取最近的子项。
    def distance(item):
        if dn < item['dn_min']:
            return item['dn_min'] - dn
        return dn - item['dn_max']
    return min(SUBITEMS, key=distance)['key']


# ---------------------------------------------------------------------------
# H（构件A 高）与编号
# ---------------------------------------------------------------------------


def round_half_up(value):
    return int(math.floor(float(value) + 0.5))


def height_mm(subitem, od):
    """构件A 高度 H（mm）：<3″ 取 50，≥3″ 取 OD/2 + 50（圆整到 mm）。"""
    item = get_subitem(subitem)
    od = float(od)
    if od < THREE_INCH_MM:
        return SMALL_PIPE_H_MM
    return float(round_half_up(od / 2.0 + TOP_ABOVE_AXIS_MM))


def height_for_dn(subitem, dn):
    return height_mm(subitem, od_mm(dn))


def build_number(subitem, height, stainless=False):
    """管架编号：``E1-子项-H``（不锈钢管道追加 ``-S``）。"""
    text = 'E1-%s-%d' % (str(subitem).strip().upper(), round_half_up(height))
    if stainless:
        text += '-%s' % STAINLESS_MARK
    return text


def is_stainless_marked(number):
    return str(number).strip().upper().endswith('-' + STAINLESS_MARK)


# ---------------------------------------------------------------------------
# 布置参数
# ---------------------------------------------------------------------------


def face_distance_mm(od, stainless=False, subitem=None):
    """构件A 朝管面到管轴的距离（mm）= OD/2 + 3 [+ 薄板厚]。"""
    distance = float(od) / 2.0 + PIPE_CLEARANCE_MM
    if stainless:
        if subitem is None:
            raise ValueError('建薄板时需给出子项以确定薄板厚度。')
        distance += float(get_subitem(subitem)['liner'][2])
    return distance


def liner_spec(subitem):
    """不锈钢薄板 (宽沿管轴, 长竖直, 厚)。"""
    width, length, thickness = get_subitem(subitem)['liner']
    return {'width_mm': float(width), 'length_mm': float(length),
            'thickness_mm': float(thickness)}


def liner_spec_text(subitem):
    width, length, thickness = get_subitem(subitem)['liner']
    return '□%.0f×%.0f×%.0f' % (width, length, thickness)


def member_spec_text(subitem):
    return get_subitem(subitem)['spec']


Layout = namedtuple(
    'Layout',
    'subitem dn od nps stainless material height_mm face_mm liner '
    'allowable_load_kn number spec')


def build_layout(dn, subitem=None, stainless=False, material=DEFAULT_MATERIAL):
    """汇总一次放置所需的全部尺寸 / 数据（纯计算，供面板与建模共用）。"""
    dn = int(dn)
    if subitem is None:
        subitem = subitem_for_dn(dn)
    item = get_subitem(subitem)
    od = od_mm(dn)
    height = height_mm(subitem, od)
    liner = liner_spec(subitem) if stainless else None
    face = face_distance_mm(od, stainless, subitem)
    number = build_number(subitem, height, stainless)
    return Layout(
        subitem=subitem, dn=dn, od=od, nps=nps_text(dn), stainless=bool(stainless),
        material=str(material or DEFAULT_MATERIAL), height_mm=height,
        face_mm=face, liner=liner, allowable_load_kn=item['load_kn'],
        number=number, spec=item['spec'],
    )


# ---------------------------------------------------------------------------
# 构件A 截面（局部 2D）与坐标架
# ---------------------------------------------------------------------------

_Point2d = namedtuple('_Point2d', 'x y')
_LineSegment = namedtuple('_LineSegment', 'start end')


class PlateGeometry(object):
    """子项 A 的钢板截面：矩形 (0,0)-(w,0)-(w,d)-(0,d)。"""

    def __init__(self, width, depth, section=None):
        self.width = float(width)
        self.depth = float(depth)
        self.section = dict(section or {})
        self.segments = (
            _LineSegment(_Point2d(0.0, 0.0), _Point2d(self.width, 0.0)),
            _LineSegment(_Point2d(self.width, 0.0), _Point2d(self.width, self.depth)),
            _LineSegment(_Point2d(self.width, self.depth), _Point2d(0.0, self.depth)),
            _LineSegment(_Point2d(0.0, self.depth), _Point2d(0.0, 0.0)),
        )

    @property
    def arc_count(self):
        return 0

    @property
    def line_count(self):
        return 4

    def is_closed_and_continuous(self, tolerance=1.0e-9):
        return all(
            math.hypot(
                self.segments[(index + 1) % 4].start.x - segment.end.x,
                self.segments[(index + 1) % 4].start.y - segment.end.y)
            <= tolerance
            for index, segment in enumerate(self.segments))


def _profile_family(subitem):
    return get_subitem(subitem)['profile']


def member_geometry(subitem, scale=1.0):
    """构建构件A 截面轮廓（局部 2D，mm 或按 ``scale`` 缩放到 UOR）。

    截面局部原点与朝向：
      * 钢板：外角 (0,0)，宽沿 +x、厚沿 +y；
      * 角钢：两腿外侧交点 (0,0)，两腿沿 +x / +y；
      * 槽钢：腹板外表面 / 下翼缘面交线 (0,0)，开口朝 +x、高沿 +y；
      * 工字钢：几何中心 (0,0)，翼缘宽沿 x、截面高沿 y。
    """
    scale = float(scale)
    kind, argument = _profile_family(subitem)
    if kind == 'plate':
        width, depth = argument
        return PlateGeometry(width * scale, depth * scale)
    if kind == 'equal_angle':
        section = steel_equal_angle_data.get_section(argument)
        scaled = steel_equal_angle_geometry.scale_section(section, scale)
        return steel_equal_angle_geometry.build_equal_angle_geometry(
            scaled, steel_equal_angle_geometry.INSERTION_OUTER_CORNER,
            steel_equal_angle_geometry.Point2d(0.0, 0.0))
    if kind == 'channel':
        section = steel_channel_data.get_section(argument)
        scaled = steel_channel_geometry.scale_section(section, scale)
        return steel_channel_geometry.build_channel_geometry(
            scaled, steel_channel_geometry.INSERTION_LOWER_LEFT,
            steel_channel_geometry.Point2d(0.0, 0.0))
    if kind == 'hbeam':
        section = steel_hbeam_data.get_section(argument)
        scaled = steel_hbeam_geometry.scale_section(section, scale)
        return steel_hbeam_geometry.build_hbeam_geometry(
            scaled, steel_hbeam_geometry.INSERTION_GEOMETRIC,
            steel_hbeam_geometry.Point2d(0.0, 0.0))
    raise ValueError('未知截面族：%s' % kind)


def _cross3(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


def member_frame(subitem, side, center_mm, face_mm, base_z_mm, height_mm,
                 pipe_dir=(1.0, 0.0, 0.0), away_dir=(0.0, 1.0, 0.0)):
    """返回构件A 的扫掠坐标架 ``(origin, axis_x, axis_y, axis_z)``（世界 mm）。

    ``center_mm`` 为放置点在管轴上的投影；``face_mm`` 为朝管面到管轴的距离；
    ``base_z_mm`` / ``height_mm`` 为管底标高与拉伸长度。``pipe_dir`` /
    ``away_dir`` 为管轴与「背离管道」两个水平单位方向。

    ``side`` = +1 / −1 的两根构件A 互为**镜像**（轴对称于管轴竖直面）：两者
    的**沿管轴特征朝向一致**（角钢同一端面同向），仅背离方向相反。为保证
    右手系，``axis_z`` 取 ``axis_x × axis_y``（可能为 −Z）；``origin`` 的 z
    已按扫掠方向取在起点（``axis_z`` 为 −Z 时取构件顶面）。
    """
    s = 1.0 if side >= 0 else -1.0
    kind, argument = _profile_family(subitem)
    cx, cy = float(center_mm[0]), float(center_mm[1])
    base_z = float(base_z_mm)
    height = float(height_mm)
    face = float(face_mm)
    px, py = float(pipe_dir[0]), float(pipe_dir[1])
    ax_, ay_ = float(away_dir[0]), float(away_dir[1])
    pipe = (px, py, 0.0)
    mirrored_away = (s * ax_, s * ay_, 0.0)
    if kind == 'channel':
        # 腹板外表面朝管道；型钢高度（局部 y）沿管轴、两侧同向。
        section_height = float(steel_channel_data.get_section(argument)['H'])
        axis_x = mirrored_away
        axis_y = pipe
        ox = cx - section_height / 2.0 * px + s * face * ax_
        oy = cy - section_height / 2.0 * py + s * face * ay_
    elif kind == 'hbeam':
        section_height = float(steel_hbeam_data.get_section(argument)['H'])
        axis_x = pipe
        axis_y = mirrored_away
        ox = cx + s * (face + section_height / 2.0) * ax_
        oy = cy + s * (face + section_height / 2.0) * ay_
    else:
        if kind == 'equal_angle':
            width = float(steel_equal_angle_data.get_section(argument)['B'])
        elif kind == 'plate':
            width = float(argument[0])
        else:
            raise ValueError('未知截面族：%s' % kind)
        axis_x = pipe
        axis_y = mirrored_away
        ox = cx - width / 2.0 * px + s * face * ax_
        oy = cy - width / 2.0 * py + s * face * ay_
    axis_z = _cross3(axis_x, axis_y)
    origin_z = base_z if axis_z[2] >= 0.0 else base_z + height
    return ((ox, oy, origin_z), axis_x, axis_y, axis_z)


def sample_member(subitem, side, center_mm, face_mm, base_z_mm, height_mm=100.0,
                  scale=1.0, pipe_dir=(1.0, 0.0, 0.0), away_dir=(0.0, 1.0, 0.0)):
    """按坐标架把构件A 截面采样为世界点（供纯几何测试）。"""
    from steel_sections import steel_sweep_geometry
    geometry = member_geometry(subitem, scale)
    origin, axis_x, axis_y, axis_z = member_frame(
        subitem, side, center_mm, face_mm, base_z_mm, height_mm, pipe_dir,
        away_dir)
    frame = steel_sweep_geometry.Frame(origin, axis_x, axis_y, axis_z)
    return tuple(
        steel_sweep_geometry.sample_segment(segment, frame)
        for segment in geometry.segments
    )


LinerBox = namedtuple('LinerBox', 'u0 u1 v0 v1 z0 z1')


def liner_box(subitem, side, od, pipe_axis_z_mm, base_z_mm, height_mm_value):
    """不锈钢薄板的局部范围 ``LinerBox``（``u`` 沿管轴、``v`` 沿背离方向）。

    ``u`` 以放置点（管轴上的投影）为原点、``v`` 以管轴为原点（构件在
    ``v > 0`` 或 ``v < 0`` 一侧）、``z`` 为绝对标高。薄板内侧面距管壁
    3 mm、外侧面贴构件A 朝管面，竖直方向以管轴为中心并夹在构件A 高度内。
    """
    spec = liner_spec(subitem)
    s = 1.0 if side >= 0 else -1.0
    half_width = spec['width_mm'] / 2.0
    inner_v = float(od) / 2.0 + PIPE_CLEARANCE_MM
    outer_v = inner_v + spec['thickness_mm']
    z_center = float(pipe_axis_z_mm)
    half_length = spec['length_mm'] / 2.0
    z0 = z_center - half_length
    z1 = z_center + half_length
    base_z = float(base_z_mm)
    top_z = base_z + float(height_mm_value)
    if z0 < base_z:
        z1 += base_z - z0
        z0 = base_z
    if z1 > top_z:
        z0 -= z1 - top_z
        z1 = top_z
    if s >= 0:
        v0, v1 = inner_v, outer_v
    else:
        v0, v1 = -outer_v, -inner_v
    return LinerBox(-half_width, half_width, v0, v1, z0, z1)


def component_items(layout):
    """供公共库 ``attach_components`` 使用的构件清单。"""
    items = [{
        'code': 'MEMBER_A',
        'name': '构件A',
        'specification': layout.spec,
        'length': layout.height_mm,
        'quantity': 2,
        'unit': '件',
    }]
    if layout.stainless and layout.liner is not None:
        items.append({
            'code': 'LINER',
            'name': '不锈钢薄板',
            'specification': liner_spec_text(layout.subitem),
            'length': layout.liner['length_mm'],
            'quantity': 2,
            'unit': '件',
        })
    return items


def describe(layout):
    """面板预览用的一段说明文字。"""
    text = ('E1 管架：DN%d（%s，OD %.1f）；子项 %s（%s）；H=%.0f；'
            '构件A 高 %.0f；允许荷载 %.0f kN；编号 %s。'
            % (layout.dn, layout.nps, layout.od, layout.subitem, layout.spec,
               layout.height_mm, layout.height_mm, layout.allowable_load_kn,
               layout.number))
    if layout.stainless:
        text += ' 不锈钢管道：加 2 块 %s（%s）。' % (
            liner_spec_text(layout.subitem), STAINLESS_MATERIAL)
    return text
