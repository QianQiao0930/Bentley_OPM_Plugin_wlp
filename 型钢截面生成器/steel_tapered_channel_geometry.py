"""True-arc geometry for GB/T 706 1:10 tapered-flange channel sections."""

from __future__ import division

import math
from collections import namedtuple

from steel_tapered_channel_data import flange_thicknesses, validate_section


Point2d = namedtuple("Point2d", "x y")
LineSegment = namedtuple("LineSegment", "start end")
ArcSegment = namedtuple("ArcSegment", "start end center radius start_angle sweep")
_Corner = namedtuple("_Corner", "entry exit arc")

INSERTION_CENTROID = "centroid"
INSERTION_GEOMETRIC_CENTER = "geometric_center"
INSERTION_WEB_OUTSIDE_CENTER = "web_outside_center"
INSERTION_LOWER_LEFT = "lower_left"

INSERTION_MODES = (
    (INSERTION_CENTROID, "截面重心（默认）"),
    (INSERTION_GEOMETRIC_CENTER, "几何中心"),
    (INSERTION_WEB_OUTSIDE_CENTER, "腹板外侧中点"),
    (INSERTION_LOWER_LEFT, "左下外角"),
)


class TaperedChannelGeometry(object):
    """Closed channel path with a 1:10 flange slope and four true arcs."""

    def __init__(self, segments, insertion_point, insertion_mode, section):
        self.segments = tuple(segments)
        self.insertion_point = insertion_point
        self.insertion_mode = insertion_mode
        self.section = dict(section)

    @property
    def arc_count(self):
        return sum(isinstance(segment, ArcSegment) for segment in self.segments)

    @property
    def line_count(self):
        return sum(isinstance(segment, LineSegment) for segment in self.segments)

    def is_closed_and_continuous(self, tolerance=1.0e-9):
        if not self.segments:
            return False
        for index, segment in enumerate(self.segments):
            following = self.segments[(index + 1) % len(self.segments)]
            if _distance(segment.end, following.start) > tolerance:
                return False
        return True


def scale_section(section, factor):
    """Convert millimetre dimensions, including the tabulated centroid, to UOR."""
    validate_section(section)
    if factor <= 0.0:
        raise ValueError("Scale factor must be positive.")
    scaled = dict(section)
    for name in ("H", "B", "tw", "tf", "r1", "r2", "Z0"):
        scaled[name] = float(section[name]) * factor
    return scaled


def insertion_anchor(section, insertion_mode):
    """Return the selected local anchor; Z0 is measured from the outer web face."""
    validate_section(section)
    h = float(section["H"])
    b = float(section["B"])
    if insertion_mode == INSERTION_CENTROID:
        return Point2d(float(section["Z0"]), h / 2.0)
    if insertion_mode == INSERTION_GEOMETRIC_CENTER:
        return Point2d(b / 2.0, h / 2.0)
    if insertion_mode == INSERTION_WEB_OUTSIDE_CENTER:
        return Point2d(0.0, h / 2.0)
    if insertion_mode == INSERTION_LOWER_LEFT:
        return Point2d(0.0, 0.0)
    raise ValueError("Unsupported insertion mode: {}".format(insertion_mode))


def build_tapered_channel_geometry(section, insertion_mode=INSERTION_CENTROID,
                                   insertion_point=Point2d(0.0, 0.0)):
    """Build a 1:10 tapered channel that opens towards positive X.

    ``tf`` is the tabulated mean flange thickness.  Across the extension
    ``B - tw`` the root and free-edge thicknesses differ by that extension
    divided by ten, with the specified r1/r2 fillets retained as true arcs.
    """
    validate_section(section)
    insertion_point = _as_point2d(insertion_point)
    h = float(section["H"])
    b = float(section["B"])
    tw = float(section["tw"])
    root_t, edge_t = flange_thicknesses(section)

    # Counter-clockwise sharp outline.  The free flange end has a short outer
    # vertical face; r2 rounds the transition to the 1:10 inner flange slope.
    vertices = (
        Point2d(0.0, 0.0),
        Point2d(b, 0.0),
        Point2d(b, edge_t),
        Point2d(tw, root_t),
        Point2d(tw, h - root_t),
        Point2d(b, h - edge_t),
        Point2d(b, h),
        Point2d(0.0, h),
    )
    radii = (0.0, 0.0, float(section["r2"]), float(section["r1"]),
             float(section["r1"]), float(section["r2"]), 0.0, 0.0)
    corners = tuple(
        _make_corner(vertices[index - 1], vertex, vertices[(index + 1) % len(vertices)], radius)
        for index, (vertex, radius) in enumerate(zip(vertices, radii))
    )

    raw_segments = []
    current = corners[0].exit
    for index in range(1, len(corners) + 1):
        corner = corners[index % len(corners)]
        if _distance(current, corner.entry) > 1.0e-10:
            raw_segments.append(LineSegment(current, corner.entry))
        if corner.arc is not None:
            raw_segments.append(corner.arc)
        current = corner.exit

    anchor = insertion_anchor(section, insertion_mode)
    dx = insertion_point.x - anchor.x
    dy = insertion_point.y - anchor.y
    geometry = TaperedChannelGeometry(
        tuple(_translate_segment(segment, dx, dy) for segment in raw_segments),
        insertion_point,
        insertion_mode,
        section,
    )
    if not geometry.is_closed_and_continuous():
        raise RuntimeError("Internal error: generated tapered channel is not closed.")
    if geometry.arc_count != 4:
        raise RuntimeError("Internal error: generated tapered channel must contain four arcs.")
    return geometry


def to_bentley_curve_vector(geometry, z=0.0):
    """Convert the tapered-channel profile to Bentley native curve primitives."""
    if not geometry.is_closed_and_continuous():
        raise ValueError("Cannot convert an open or discontinuous profile.")
    from MSPyBentleyGeom import CurveVector, DEllipse3d, DPoint3d, DSegment3d, ICurvePrimitive

    curves = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for segment in geometry.segments:
        if isinstance(segment, LineSegment):
            start = DPoint3d(segment.start.x, segment.start.y, z)
            end = DPoint3d(segment.end.x, segment.end.y, z)
            curves.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
        else:
            ellipse = DEllipse3d.FromXYMajorMinor(
                segment.center.x, segment.center.y, z,
                segment.radius, segment.radius, 0.0,
                segment.start_angle, segment.sweep,
            )
            curves.Add(ICurvePrimitive.CreateArc(ellipse))
    return curves


def _make_corner(previous, vertex, following, radius):
    if radius == 0.0:
        return _Corner(vertex, vertex, None)
    incoming = _normalize(_subtract(vertex, previous))
    outgoing = _normalize(_subtract(following, vertex))
    cross = incoming.x * outgoing.y - incoming.y * outgoing.x
    dot = max(-1.0, min(1.0, incoming.x * outgoing.x + incoming.y * outgoing.y))
    turn = math.atan2(cross, dot)
    if abs(turn) < 1.0e-8:
        raise ValueError("A fillet requires a non-collinear corner.")
    tangent_length = radius * abs(math.tan(turn / 2.0))
    if tangent_length >= _distance(previous, vertex) or tangent_length >= _distance(vertex, following):
        raise ValueError("Tapered-channel fillet radius is too large for the profile.")
    start = _add(vertex, _scale(incoming, -tangent_length))
    end = _add(vertex, _scale(outgoing, tangent_length))
    normal = _left_normal(incoming) if turn > 0.0 else _right_normal(incoming)
    center = _add(start, _scale(normal, radius))
    start_angle = math.atan2(start.y - center.y, start.x - center.x)
    return _Corner(start, end, ArcSegment(start, end, center, radius, start_angle, turn))


def _translate_segment(segment, dx, dy):
    if isinstance(segment, LineSegment):
        return LineSegment(_translate_point(segment.start, dx, dy), _translate_point(segment.end, dx, dy))
    return ArcSegment(
        _translate_point(segment.start, dx, dy), _translate_point(segment.end, dx, dy),
        _translate_point(segment.center, dx, dy), segment.radius, segment.start_angle, segment.sweep,
    )


def _translate_point(point, dx, dy):
    return Point2d(point.x + dx, point.y + dy)


def _as_point2d(value):
    if isinstance(value, Point2d):
        return value
    try:
        return Point2d(float(value[0]), float(value[1]))
    except (TypeError, IndexError):
        raise ValueError("Insertion point must supply x and y coordinates.")


def _normalize(vector):
    length = math.hypot(vector.x, vector.y)
    if length == 0.0:
        raise ValueError("Coincident tapered-channel vertices are invalid.")
    return Point2d(vector.x / length, vector.y / length)


def _subtract(left, right):
    return Point2d(left.x - right.x, left.y - right.y)


def _add(point, vector):
    return Point2d(point.x + vector.x, point.y + vector.y)


def _scale(vector, factor):
    return Point2d(vector.x * factor, vector.y * factor)


def _left_normal(vector):
    return Point2d(-vector.y, vector.x)


def _right_normal(vector):
    return Point2d(vector.y, -vector.x)


def _distance(left, right):
    return math.hypot(left.x - right.x, left.y - right.y)
