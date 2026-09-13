"""Geometry construction for parallel-flange hot-rolled H sections."""

from __future__ import division

import math
from collections import namedtuple

from steel_hbeam_data import validate_section


Point2d = namedtuple("Point2d", "x y")
LineSegment = namedtuple("LineSegment", "start end")
ArcSegment = namedtuple("ArcSegment", "center radius start_angle sweep start end")

INSERTION_CENTROID = "centroid"
INSERTION_GEOMETRIC = "geometric_center"
INSERTION_BOTTOM_CENTER = "bottom_center"
INSERTION_LOWER_LEFT = "lower_left"
INSERTION_MODES = (
    (INSERTION_CENTROID, "截面重心（默认）"),
    (INSERTION_GEOMETRIC, "几何中心"),
    (INSERTION_BOTTOM_CENTER, "下翼缘外边中点"),
    (INSERTION_LOWER_LEFT, "左下外角"),
)

_EPSILON = 1.0e-8


def _point_add(point, vector, factor=1.0):
    return Point2d(point.x + vector.x * factor, point.y + vector.y * factor)


def _point_sub(left, right):
    return Point2d(left.x - right.x, left.y - right.y)


def _length(vector):
    return math.hypot(vector.x, vector.y)


def _unit(vector):
    magnitude = _length(vector)
    if magnitude < _EPSILON:
        raise ValueError("轮廓中存在零长度边。")
    return Point2d(vector.x / magnitude, vector.y / magnitude)


def _cross(left, right):
    return left.x * right.y - left.y * right.x


def _dot(left, right):
    return left.x * right.x + left.y * right.y


def _left_normal(vector):
    return Point2d(-vector.y, vector.x)


def _right_normal(vector):
    return Point2d(vector.y, -vector.x)


def _close(left, right, tolerance=1.0e-6):
    return abs(left.x - right.x) <= tolerance and abs(left.y - right.y) <= tolerance


def _arc_sweep(center, start, end, turn):
    start_angle = math.atan2(start.y - center.y, start.x - center.x)
    end_angle = math.atan2(end.y - center.y, end.x - center.x)
    if turn > 0.0:
        sweep = (end_angle - start_angle) % (2.0 * math.pi)
    else:
        sweep = -((start_angle - end_angle) % (2.0 * math.pi))
    return start_angle, sweep


def _make_corner(previous, vertex, following, radius):
    """Return tangent points and a true circular arc at one profile vertex."""
    incoming = _unit(_point_sub(vertex, previous))
    outgoing = _unit(_point_sub(following, vertex))
    turn = math.atan2(_cross(incoming, outgoing), _dot(incoming, outgoing))

    if radius <= _EPSILON or abs(turn) <= _EPSILON:
        return {"entry": vertex, "exit": vertex, "arc": None}

    tangent_distance = abs(radius * math.tan(turn / 2.0))
    if tangent_distance >= _length(_point_sub(vertex, previous)) - _EPSILON:
        raise ValueError("圆角半径超过相邻边长度。")
    if tangent_distance >= _length(_point_sub(following, vertex)) - _EPSILON:
        raise ValueError("圆角半径超过相邻边长度。")

    entry = _point_add(vertex, incoming, -tangent_distance)
    exit_point = _point_add(vertex, outgoing, tangent_distance)
    normal = _left_normal(incoming) if turn > 0.0 else _right_normal(incoming)
    center = _point_add(entry, normal, radius)
    start_angle, sweep = _arc_sweep(center, entry, exit_point, turn)
    arc = ArcSegment(center, radius, start_angle, sweep, entry, exit_point)
    return {"entry": entry, "exit": exit_point, "arc": arc}


class HBeamGeometry(object):
    def __init__(self, section, segments):
        self.section = dict(section)
        self.segments = tuple(segments)

    @property
    def line_count(self):
        return sum(1 for segment in self.segments if isinstance(segment, LineSegment))

    @property
    def arc_count(self):
        return sum(1 for segment in self.segments if isinstance(segment, ArcSegment))

    def is_closed_and_continuous(self, tolerance=1.0e-6):
        if not self.segments:
            return False
        for index, segment in enumerate(self.segments):
            following = self.segments[(index + 1) % len(self.segments)]
            if not _close(segment.end, following.start, tolerance):
                return False
        return True


def scale_section(section, scale_factor):
    """Scale only the geometric dimensions from millimetres to DGN units."""
    scaled = dict(section)
    for name in ("H", "B", "t1", "t2", "r"):
        scaled[name] = float(section[name]) * scale_factor
    return scaled


def insertion_anchor(section, mode):
    h = float(section["H"])
    b = float(section["B"])
    if mode in (INSERTION_CENTROID, INSERTION_GEOMETRIC):
        return Point2d(0.0, 0.0)
    if mode == INSERTION_BOTTOM_CENTER:
        return Point2d(0.0, -h / 2.0)
    if mode == INSERTION_LOWER_LEFT:
        return Point2d(-b / 2.0, -h / 2.0)
    raise ValueError("未知插入方式：{}".format(mode))


def build_hbeam_geometry(section, insertion_mode=INSERTION_CENTROID, insertion_point=None):
    """Build one closed H-beam boundary in the local X/Y plane."""
    validate_section(section)
    h = float(section["H"])
    b = float(section["B"])
    t1 = float(section["t1"])
    t2 = float(section["t2"])
    radius = float(section["r"])
    half_h = h / 2.0
    half_b = b / 2.0
    half_web = t1 / 2.0
    flange_inner_y = half_h - t2

    # Counter-clockwise boundary.  Vertices 3, 4, 9 and 10 are web-root fillets.
    vertices = (
        Point2d(half_b, half_h),
        Point2d(-half_b, half_h),
        Point2d(-half_b, flange_inner_y),
        Point2d(-half_web, flange_inner_y),
        Point2d(-half_web, -flange_inner_y),
        Point2d(-half_b, -flange_inner_y),
        Point2d(-half_b, -half_h),
        Point2d(half_b, -half_h),
        Point2d(half_b, -flange_inner_y),
        Point2d(half_web, -flange_inner_y),
        Point2d(half_web, flange_inner_y),
        Point2d(half_b, flange_inner_y),
    )
    rounded_indices = (3, 4, 9, 10)
    corners = []
    for index, vertex in enumerate(vertices):
        if index in rounded_indices:
            corners.append(_make_corner(vertices[index - 1], vertex, vertices[(index + 1) % len(vertices)], radius))
        else:
            corners.append({"entry": vertex, "exit": vertex, "arc": None})

    segments = []
    for index, corner in enumerate(corners):
        next_index = (index + 1) % len(corners)
        next_corner = corners[next_index]
        if not _close(corner["exit"], next_corner["entry"]):
            segments.append(LineSegment(corner["exit"], next_corner["entry"]))
        if next_corner["arc"] is not None:
            segments.append(next_corner["arc"])

    if insertion_point is not None:
        anchor = insertion_anchor(section, insertion_mode)
        offset = Point2d(insertion_point.x - anchor.x, insertion_point.y - anchor.y)
        translated = []
        for segment in segments:
            if isinstance(segment, LineSegment):
                translated.append(LineSegment(_point_add(segment.start, offset), _point_add(segment.end, offset)))
            else:
                translated.append(ArcSegment(
                    _point_add(segment.center, offset), segment.radius, segment.start_angle,
                    segment.sweep, _point_add(segment.start, offset), _point_add(segment.end, offset)
                ))
        segments = translated

    geometry = HBeamGeometry(section, segments)
    if not geometry.is_closed_and_continuous():
        raise ValueError("生成的 H 型钢截面没有闭合。")
    if geometry.arc_count != 4:
        raise ValueError("生成的 H 型钢截面圆角数量异常。")
    return geometry


def to_bentley_curve_vector(geometry, z=0.0, point_type=None):
    """Convert pure-Python geometry into a Bentley CurveVector boundary.

    ``point_type`` is normally the class of the DPoint3d delivered by the
    active tool event.  Using it avoids relying on a version-specific module
    export for DPoint3d in OpenPlant's embedded Python runtime.
    """
    from MSPyBentleyGeom import CurveVector, DEllipse3d, DSegment3d, ICurvePrimitive

    if point_type is None:
        raise ValueError("需要传入 OpenPlant 事件点的类型来创建 DPoint3d。")

    def make_point(x, y, point_z):
        try:
            return point_type(x, y, point_z)
        except TypeError:
            point = point_type()
            point.x = x
            point.y = y
            point.z = point_z
            return point

    curves = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for segment in geometry.segments:
        if isinstance(segment, LineSegment):
            start = make_point(segment.start.x, segment.start.y, z)
            end = make_point(segment.end.x, segment.end.y, z)
            curves.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
        else:
            # OpenPlant 2024 exposes the same eight-scalar overload used by
            # the working channel and I-beam generators.
            ellipse = DEllipse3d.FromXYMajorMinor(
                segment.center.x,
                segment.center.y,
                z,
                segment.radius,
                segment.radius,
                0.0,
                segment.start_angle,
                segment.sweep,
            )
            curves.Add(ICurvePrimitive.CreateArc(ellipse))
    return curves
