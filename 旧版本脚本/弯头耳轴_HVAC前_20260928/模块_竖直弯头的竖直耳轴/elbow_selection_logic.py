# -*- coding: utf-8 -*-
"""所选 90° 弯头的纯几何解析逻辑（不依赖 Bentley 运行时）。"""

from __future__ import division

import math


NPS_BY_DN = {
    15: '1/2"', 20: '3/4"', 25: '1"', 32: '1-1/4"',
    40: '1-1/2"', 50: '2"', 65: '2-1/2"', 80: '3"',
    100: '4"', 125: '5"', 150: '6"', 200: '8"',
    250: '10"', 300: '12"', 350: '14"', 400: '16"',
    450: '18"', 500: '20"', 550: '22"', 600: '24"',
    650: '26"', 700: '28"', 750: '30"', 800: '32"',
    850: '34"', 900: '36"', 950: '38"', 1000: '40"',
    1050: '42"', 1100: '44"', 1200: '48"',
}
MATERIAL_CODES = ('L', 'C1', 'C2', 'A1', 'A2', 'S')


def _dimension_text(value):
    return ('%g' % float(value))


def f2_number(main_dn, trunnion_dn, wall_mm, default_wall_mm,
              material_code, height_mm, base_code, ptfe=False,
              upward=False, horizontal_elbow=False):
    """按图示 F2-主管-耳轴(壁厚)-材料-H-底板[-F][-UP][-HE] 编号。"""
    try:
        main_nps = NPS_BY_DN[int(main_dn)]
        trunnion_nps = NPS_BY_DN[int(trunnion_dn)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('主管或耳轴管径缺少 NPS 对照。')
    material = str(material_code).upper()
    base = str(base_code).upper()
    if material not in MATERIAL_CODES:
        raise ValueError('未知材料代码：%s。' % material_code)
    if base not in ('A', 'B', 'C'):
        raise ValueError('未知底板类型：%s。' % base_code)
    if ptfe and base == 'C':
        raise ValueError('无底板时不能标注 PTFE 滑板 F。')
    wall = _finite(wall_mm, '耳轴壁厚')
    default_wall = _finite(default_wall_mm, '默认壁厚')
    height = _finite(height_mm, '高度 H')
    if wall <= 0.0 or default_wall <= 0.0 or height <= 0.0:
        raise ValueError('耳轴壁厚及高度 H 必须大于 0。')
    wall_suffix = '' if abs(wall - default_wall) < 1.0e-6 else '(%s)' % _dimension_text(wall)
    parts = ['F2', main_nps, trunnion_nps + wall_suffix, material,
             str(int(math.floor(height + 0.5))), base]
    if ptfe:
        parts.append('F')
    if upward:
        parts.append('UP')
    if horizontal_elbow:
        parts.append('HE')
    return '-'.join(parts)


def f4_number(main_dn, trunnion_dn, wall_mm, default_wall_mm,
              material_code, length_mm, end_plate_type, flat_bend_code=''):
    """同中心线省略 FB；底平时按弯头朝向追加 FB1 或 FB2。"""
    try:
        main_nps = NPS_BY_DN[int(main_dn)]
        trunnion_nps = NPS_BY_DN[int(trunnion_dn)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('主管或耳轴管径缺少 NPS 对照。')
    material = str(material_code).upper()
    plate = str(end_plate_type).upper()
    bend = str(flat_bend_code).upper()
    if material not in MATERIAL_CODES or plate not in ('A', 'B', 'C'):
        raise ValueError('未知材料代码或端板类型。')
    if bend not in ('', 'FB1', 'FB2'):
        raise ValueError('底平标记必须为 FB1 或 FB2。')
    wall = _finite(wall_mm, '耳轴壁厚')
    default_wall = _finite(default_wall_mm, '默认壁厚')
    length = _finite(length_mm, '长度 L')
    if min(wall, default_wall, length) <= 0:
        raise ValueError('耳轴壁厚及长度 L 必须大于 0。')
    suffix = '' if abs(wall - default_wall) < 1.0e-6 else '(%s)' % _dimension_text(wall)
    parts = ['F4', main_nps, trunnion_nps + suffix, material,
             str(int(math.floor(length + 0.5))), plate]
    if bend:
        parts.append(bend)
    return '-'.join(parts)


def f5_azimuth_deg(direction):
    """耳轴平面方向：正北 0°，顺时针为正。"""
    dx, dy, dz = (_finite(value, '耳轴方向') for value in direction)
    if abs(dz) > ORIENTATION_TOLERANCE:
        raise ValueError('耳轴方向必须水平。')
    if math.hypot(dx, dy) <= 1.0e-9:
        raise ValueError('耳轴方向为零向量。')
    return math.degrees(math.atan2(dx, dy)) % 360.0


def f5_number(main_dn, trunnion_dn, wall_mm, default_wall_mm,
              material_code, length_mm, end_plate_type, azimuth_deg,
              bottom_flat=False):
    """F5-主管-耳轴(壁厚)-材料-L-端板-方位角[-FB]。"""
    main_diameter = _finite(main_dn, '主管 DN')
    trunnion_diameter = _finite(trunnion_dn, '耳轴 DN')
    if (main_diameter <= 0 or trunnion_diameter <= 0
            or not main_diameter.is_integer()
            or not trunnion_diameter.is_integer()):
        raise ValueError('主管和耳轴公称直径必须为正整数 DN。')
    material = str(material_code).upper()
    plate = str(end_plate_type).upper()
    if material not in MATERIAL_CODES or plate not in ('A', 'B', 'C'):
        raise ValueError('未知材料代码或端板类型。')
    wall = _finite(wall_mm, '耳轴壁厚')
    default_wall = _finite(default_wall_mm, '默认壁厚')
    length = _finite(length_mm, '长度 L')
    azimuth = _finite(azimuth_deg, '方位角')
    if min(wall, default_wall, length) <= 0:
        raise ValueError('耳轴壁厚及长度 L 必须大于 0。')
    suffix = '' if abs(wall - default_wall) < 1.0e-6 else '(%s)' % _dimension_text(wall)
    rounded_azimuth = int(math.floor(azimuth % 360.0 + 0.5)) % 360
    parts = ['F5', 'DN%d' % int(main_diameter),
             'DN%d%s' % (int(trunnion_diameter), suffix), material,
             str(int(math.floor(length + 0.5))), plate,
             str(rounded_azimuth)]
    if bottom_flat:
        parts.append('FB')
    return '-'.join(parts)


def f5_pipe_axis_origin(frame):
    """L 的起点为 Outlet 支管轴线与 Run 端切线的理论交点。"""
    return _add(frame['run_port_mm'], frame['axis_x'],
                frame['run_length_mm'])


def f5_placement_direction(frame, side):
    """水平弯头可沿 Run 端切线或 Outlet 端反向切线伸出。"""
    if side == 'RUN':
        return frame['axis_x']
    if side == 'OUTLET':
        return _negate(frame['axis_z'])
    raise ValueError('未知的水平耳轴伸出方向。')


def f5_axis_points(frame, length_mm, plate_thickness_mm,
                   downward_offset_mm=0.0, side='RUN'):
    length = _finite(length_mm, '长度 L')
    plate = _finite(plate_thickness_mm, '端板厚度')
    offset = _finite(downward_offset_mm, '耳轴轴线偏移')
    if length <= plate or plate < 0 or offset < 0:
        raise ValueError('长度、端板厚度或耳轴偏移无效。')
    pipe_origin = f5_pipe_axis_origin(frame)
    origin = (pipe_origin[0], pipe_origin[1], pipe_origin[2] - offset)
    direction = f5_placement_direction(frame, side)
    # 从所选端口内侧穿过弯头，布尔切除弯头包络后留下实际鞍口。
    port = frame['run_port_mm'] if side == 'RUN' else frame['outlet_port_mm']
    tube_start = _add((port[0], port[1], port[2] - offset),
                      direction, 1.0)
    tube_end = _add(origin, direction, length - plate)
    outer_end = _add(origin, direction, length)
    tube_length = sum((tube_end[i] - tube_start[i]) * direction[i]
                      for i in range(3))
    if tube_length <= 0:
        raise ValueError('长度 L 不足以容纳耳轴管坯。')
    return {'origin_mm': origin, 'tube_start_mm': tube_start,
            'tube_length_mm': tube_length, 'tube_end_mm': tube_end,
            'outer_end_mm': outer_end}


def f4_alignment_offset(main_od_mm, trunnion_od_mm, alignment):
    """返回耳轴轴线相对主管轴线向下的偏移；底平时两管外底面齐平。"""
    main_od = _finite(main_od_mm, '主管外径')
    trunnion_od = _finite(trunnion_od_mm, '耳轴外径')
    if main_od <= 0 or trunnion_od <= 0:
        raise ValueError('主管及耳轴外径必须大于 0。')
    if alignment == 'CENTER':
        return 0.0
    if alignment != 'BOTTOM':
        raise ValueError('未知耳轴对齐类型。')
    if main_od < trunnion_od:
        raise ValueError('耳轴外径大于主管外径，无法底平。')
    return (main_od - trunnion_od) / 2.0


def f4_end_plate_thickness(trunnion_dn, end_plate_type):
    """端板 A=6 mm，B 按图表 2，C 不设端板。"""
    plate = str(end_plate_type).upper()
    dn = int(trunnion_dn)
    if plate == 'A':
        return 6.0
    if plate == 'C':
        return 0.0
    if plate != 'B':
        raise ValueError('未知端板类型。')
    for maximum_dn, thickness in ((80, 10), (200, 12), (300, 16),
                                  (450, 20), (600, 25)):
        if dn <= maximum_dn:
            return float(thickness)
    return 30.0


def f4_pipe_axis_origin(frame):
    """F4 起点：竖直段的平面中心，水平主管的中心线标高。"""
    vertical = frame['vertical_port_mm']
    horizontal = frame['horizontal_port_mm']
    return (vertical[0], vertical[1], horizontal[2])


def f4_axis_points(frame, length_mm, plate_thickness_mm,
                   downward_offset_mm=0.0):
    """L 从竖直段中心线量；管坯从水平端内侧进入弯头，再由鞍口切除。"""
    length = _finite(length_mm, '长度 L')
    plate = _finite(plate_thickness_mm, '端板厚度')
    if length <= plate or plate < 0:
        raise ValueError('长度 L 必须大于端板厚度。')
    offset = _finite(downward_offset_mm, '耳轴轴线偏移')
    if offset < 0:
        raise ValueError('耳轴轴线偏移不能为负。')
    pipe_origin = f4_pipe_axis_origin(frame)
    origin = (pipe_origin[0], pipe_origin[1], pipe_origin[2] - offset)
    direction = frame['horizontal_direction']
    horizontal_port = frame['horizontal_port_mm']
    # 向弯内 1 mm，避开与弯头端面完全共面的布尔输入。
    tube_start = _add((horizontal_port[0], horizontal_port[1],
                       horizontal_port[2] - offset), direction, 1.0)
    tube_end = _add(origin, direction, length - plate)
    outer_end = _add(origin, direction, length)
    tube_length = sum((tube_end[i] - tube_start[i]) * direction[i]
                      for i in range(3))
    if tube_length <= 0:
        raise ValueError('长度 L 不足以容纳耳轴管坯。')
    return {'origin_mm': origin, 'tube_start_mm': tube_start,
            'tube_length_mm': tube_length, 'tube_end_mm': tube_end,
            'outer_end_mm': outer_end}


ORIENTATION_TOLERANCE = 0.02


def _finite(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError("缺少或无法读取 %s。" % name)
    if math.isnan(result) or math.isinf(result):
        raise ValueError("%s 不是有效数值。" % name)
    return result


def _normalize(vector, name):
    values = tuple(_finite(value, name) for value in vector)
    length = math.sqrt(sum(value * value for value in values))
    if length <= 1.0e-9:
        raise ValueError("%s 为零向量。" % name)
    return tuple(value / length for value in values)


def _add(point, vector, distance):
    return tuple(point[index] + vector[index] * distance for index in range(3))


def _negate(vector):
    return tuple(-value for value in vector)


def dimension_scale_to_mm(unit_of_measure, nominal_diameter_raw=None):
    """按 EC 单位标记返回毫米换算系数；缺标记时用公称直径量级兜底。"""
    unit = str(unit_of_measure or "").strip().upper()
    if unit in ("MM", "MILLIMETER", "MILLIMETRE", "毫米"):
        return 1.0
    if unit in ("M", "METER", "METRE", "米"):
        return 1000.0
    if unit in ("IN", "INCH", "INCHES"):
        return 25.4
    try:
        nominal = abs(float(nominal_diameter_raw))
    except (TypeError, ValueError):
        nominal = 0.0
    # OPM 公称直径若以米保存通常小于 2；常见 DN 的毫米值则大于 10。
    return 1000.0 if 0.0 < nominal < 2.0 else 1.0


def elbow_frame_from_matrix(matrix, uor_per_mm, run_length_mm,
                            outlet_length_mm,
                            tolerance=ORIENTATION_TOLERANCE,
                            allow_downward=False):
    """由 OPM 3x4 变换矩阵解析两个端口、圆心与水平端方向。

    OPM 标准弯头局部坐标约定为：端口 0 位于矩阵原点，局部 X 是端口 0
    进入弯头的切线方向，局部 Z 是端口 1 的出弯方向。圆弧中心位于
    ``原点 + 局部 Z × Outlet 中心距``。
    """
    if matrix is None or len(matrix) < 12:
        raise ValueError("弯头缺少完整的 TRANSFORMATION_MATRIX。")
    uor_per_mm = _finite(uor_per_mm, "模型 UOR/mm")
    if uor_per_mm <= 0.0:
        raise ValueError("模型 UOR/mm 必须大于 0。")
    run_length_mm = _finite(run_length_mm, "中心至 Run 端距离")
    outlet_length_mm = _finite(outlet_length_mm, "中心至 Outlet 端距离")
    if run_length_mm <= 0.0 or outlet_length_mm <= 0.0:
        raise ValueError("弯头两端中心距必须大于 0。")
    if abs(run_length_mm - outlet_length_mm) > max(
            run_length_mm, outlet_length_mm) * 0.02:
        raise ValueError("弯头两端中心距不一致，第一版只支持标准 90° 圆弧弯头。")

    values = [_finite(value, "变换矩阵") for value in matrix[:12]]
    axis_x = _normalize((values[0], values[4], values[8]), "局部 X 轴")
    axis_z = _normalize((values[2], values[6], values[10]), "局部 Z 轴")
    if abs(sum(axis_x[i] * axis_z[i] for i in range(3))) > tolerance:
        raise ValueError("弯头变换矩阵的 X/Z 轴不正交。")

    origin = (values[3] / uor_per_mm,
              values[7] / uor_per_mm,
              values[11] / uor_per_mm)
    arc_center = _add(origin, axis_z, outlet_length_mm)
    port0 = origin
    port1 = _add(_add(origin, axis_x, run_length_mm),
                 axis_z, outlet_length_mm)

    x_is_horizontal = abs(axis_x[2]) <= tolerance
    x_is_vertical = abs(axis_x[2]) >= 1.0 - tolerance
    z_is_horizontal = abs(axis_z[2]) <= tolerance
    z_is_vertical = abs(axis_z[2]) >= 1.0 - tolerance

    if x_is_horizontal and z_is_vertical:
        horizontal_port = port0
        vertical_port = port1
        horizontal_direction = axis_x
        vertical_outward = axis_z
    elif x_is_vertical and z_is_horizontal:
        horizontal_port = port1
        vertical_port = port0
        horizontal_direction = _negate(axis_z)
        vertical_outward = _negate(axis_x)
    else:
        raise ValueError(
            "所选弯头不是竖直弯头：两个端口必须一端水平、另一端竖直。")

    if vertical_outward[2] < 1.0 - tolerance and not allow_downward:
        raise ValueError("所选弯头的竖直端朝下；第一版仅支持竖直端朝上的弯头。")

    horizontal_direction = _normalize(
        (horizontal_direction[0], horizontal_direction[1], 0.0),
        "水平端方向")
    return {
        "origin_mm": origin,
        "axis_x": axis_x,
        "axis_z": axis_z,
        "horizontal_port_mm": horizontal_port,
        "vertical_port_mm": vertical_port,
        "arc_center_mm": arc_center,
        "horizontal_direction": horizontal_direction,
        "vertical_outward_direction": vertical_outward,
        "flat_bend_code": "FB1" if vertical_outward[2] > 0 else "FB2",
        "run_length_mm": run_length_mm,
        "outlet_length_mm": outlet_length_mm,
    }


def horizontal_elbow_frame_from_matrix(matrix, uor_per_mm, run_length_mm,
                                       outlet_length_mm,
                                       tolerance=ORIENTATION_TOLERANCE):
    """解析水平 90° 弯头，把竖直耳轴放在弯曲中心线的 45° 中点下方。"""
    if matrix is None or len(matrix) < 12:
        raise ValueError("弯头缺少完整的 TRANSFORMATION_MATRIX。")
    scale = _finite(uor_per_mm, "模型 UOR/mm")
    run = _finite(run_length_mm, "中心至 Run 端距离")
    outlet = _finite(outlet_length_mm, "中心至 Outlet 端距离")
    if scale <= 0.0 or run <= 0.0 or outlet <= 0.0:
        raise ValueError("模型单位和弯头中心距必须大于 0。")
    if abs(run - outlet) > max(run, outlet) * 0.02:
        raise ValueError("弯头两端中心距不一致，只支持标准 90° 圆弧弯头。")

    values = [_finite(value, "变换矩阵") for value in matrix[:12]]
    axis_x = _normalize((values[0], values[4], values[8]), "局部 X 轴")
    axis_z = _normalize((values[2], values[6], values[10]), "局部 Z 轴")
    if abs(axis_x[2]) > tolerance or abs(axis_z[2]) > tolerance:
        raise ValueError("所选弯头不是水平弯头：两端轴线必须都在水平面内。")
    if abs(sum(axis_x[i] * axis_z[i] for i in range(3))) > tolerance:
        raise ValueError("弯头变换矩阵的 X/Z 轴不正交。")

    origin = (values[3] / scale, values[7] / scale, values[11] / scale)
    center = _add(origin, axis_z, outlet)
    end = _add(_add(origin, axis_x, run), axis_z, outlet)
    radius = (run + outlet) / 2.0
    # 起点相对圆心为 -Z，终点为 +X；45° 半径方向为 (X-Z)/sqrt(2)。
    middle = tuple(center[i] + (axis_x[i] - axis_z[i])
                   * radius / math.sqrt(2.0) for i in range(3))
    tangent = _normalize(tuple(axis_x[i] + axis_z[i] for i in range(3)),
                         "弯头中点切线")
    return {
        "origin_mm": origin,
        "axis_x": axis_x,
        "axis_z": axis_z,
        "run_port_mm": origin,
        "outlet_port_mm": end,
        "arc_center_mm": center,
        "support_axis_mm": middle,
        # 沿用 F2 的 H 和拉伸预览接口：两点均为耳轴所在的主管中心线点。
        "horizontal_port_mm": middle,
        "vertical_port_mm": middle,
        "horizontal_direction": tangent,
        "run_length_mm": run,
        "outlet_length_mm": outlet,
    }


def support_base_from_height(frame, height_h_mm, plate_thickness_mm,
                             liner_thickness_mm=0.0):
    """H 定位构件最低点；可选覆面在结构底板下方。"""
    height_h_mm = _finite(height_h_mm, "高度 H")
    plate_thickness_mm = _finite(plate_thickness_mm, "底板厚度")
    liner_thickness_mm = _finite(liner_thickness_mm, "覆面厚度")
    if (height_h_mm <= 0.0 or plate_thickness_mm < 0.0
            or liner_thickness_mm < 0.0):
        raise ValueError("高度 H 必须大于 0，底板和覆面厚度不能为负。")
    horizontal = frame["horizontal_port_mm"]
    vertical = frame["vertical_port_mm"]
    liner_bottom_z = horizontal[2] - height_h_mm
    base_bottom_z = liner_bottom_z + liner_thickness_mm
    plate_top_z = base_bottom_z + plate_thickness_mm
    if vertical[2] <= plate_top_z:
        raise ValueError("高度 H 使耳轴上端不高于底端，无法建模。")
    return {
        "plate_top_z_mm": plate_top_z,
        "base_bottom_mm": (vertical[0], vertical[1], base_bottom_z),
        "liner_bottom_mm": (vertical[0], vertical[1], liner_bottom_z),
        "trunnion_bottom_mm": (vertical[0], vertical[1], plate_top_z),
        "trunnion_top_mm": vertical,
    }


def height_from_drag_z(horizontal_port_z_mm, cursor_z_uor, uor_per_mm):
    """将拖动点的 Z 标高换算为弯头水平中心线到构件最低点的 H。"""
    scale = _finite(uor_per_mm, "模型 UOR/mm")
    if scale <= 0.0:
        raise ValueError("模型 UOR/mm 必须大于 0。")
    return (_finite(horizontal_port_z_mm, "水平端标高")
            - _finite(cursor_z_uor, "光标 Z 坐标") / scale)


def height_from_view_drag(anchor_xy, one_meter_down_xy, cursor_xy):
    """沿视图中的世界竖直轴投影光标，返回毫米高度。"""
    ax, ay = (_finite(value, "拉伸起点") for value in anchor_xy)
    bx, by = (_finite(value, "竖直轴") for value in one_meter_down_xy)
    cx, cy = (_finite(value, "光标位置") for value in cursor_xy)
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-6:
        raise ValueError("当前视图无法显示竖直方向，请切换到侧视图或轴测视图。")
    return 1000.0 * ((cx - ax) * dx + (cy - ay) * dy) / length_sq


def moved_from_selection_view(pick_position, view_number, view_xy,
                              minimum_view_distance=5.0):
    """防止同一次点选事件在新工具中被误当成拉伸确认。"""
    pick_view, pick_x, pick_y = pick_position
    if int(view_number) != int(pick_view):
        return True
    x, y = view_xy
    dx = _finite(x, "光标 X") - _finite(pick_x, "选取 X")
    dy = _finite(y, "光标 Y") - _finite(pick_y, "选取 Y")
    distance = _finite(minimum_view_distance, "最小移动距离")
    return dx * dx + dy * dy > distance * distance
