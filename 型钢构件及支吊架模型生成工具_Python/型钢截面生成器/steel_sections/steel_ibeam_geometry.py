"""True-arc geometry for GB/T 706 tapered-flange I-beam sections."""

from __future__ import division

import math
from collections import namedtuple

from .steel_ibeam_data import validate_section


Point2d = namedtuple("Point2d", "x y")
LineSegment = namedtuple("LineSegment", "start end")
ArcSegment = namedtuple("ArcSegment", "start end center radius start_angle sweep")
_Corner = namedtuple("_Corner", "entry exit arc")


INSERTION_CENTROID = "centroid"
INSERTION_GEOMETRIC_CENTER = "geometric_center"
INSERTION_BOTTOM_CENTER = "bottom_center"
INSERTION_LOWER_LEFT = "lower_left"

INSERTION_MODES = (
    (INSERTION_CENTROID, "截面重心（默认）"),
    (INSERTION_GEOMETRIC_CENTER, "几何中心（与重心重合）"),
    (INSERTION_BOTTOM_CENTER, "下翼缘外侧中心"),
    (INSERTION_LOWER_LEFT, "左下外角"),
)


class IBeamGeometry(object):
    """A continuous, closed I-beam path with 1:6 slopes and eight true arcs."""

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


def flange_thicknesses(section):
    """Return ``(root, edge)`` flange thicknesses for the specified 1:6 slope.

    GB/T 706's ``tf`` is the middle/average flange thickness.  Over one half
    of the flange extension the thickness changes by ``extension / 6``.
    """
    validate_section(section)
    extension = (section["B"] - section["tw"]) / 2.0
    return (section["tf"] + extension / 12.0,
            section["tf"] - extension / 12.0)


def scale_section(section, factor):
    """Convert only length dimensions from millimetres to the active DGN UOR."""
    validate_section(section)
    if factor <= 0.0:
        raise ValueError("Scale factor must be positive.")
    scaled = dict(section)
    for key in ("H", "B", "tw", "tf", "r1", "r2"):
        scaled[key] *= factor
    return scaled


def insertion_anchor(section, insertion_mode):
    """Return the selected anchor in the untransformed local coordinate system."""
    validate_section(section)
    half_h, half_b = section["H"] / 2.0, section["B"] / 2.0
    if insertion_mode in (INSERTION_CENTROID, INSERTION_GEOMETRIC_CENTER):
        return Point2d(0.0, 0.0)
    if insertion_mode == INSERTION_BOTTOM_CENTER:
        return Point2d(0.0, -half_h)
    if insertion_mode == INSERTION_LOWER_LEFT:
        return Point2d(-half_b, -half_h)
    raise ValueError("Unsupported insertion mode: {0}".format(insertion_mode))


def build_ibeam_geometry(section, insertion_mode=INSERTION_CENTROID,
                         insertion_point=Point2d(0.0, 0.0)):
    """Create the GB/T 706 I-section outline in the requested placement frame.

    The outline is vertically and horizontally symmetric.  Its flange faces
    have the standard 1:6 taper and use four inner r1 fillets plus four
    flange-end r2 fillets; no arc is approximated by short line segments.
    """
    validate_section(section)
    insertion_point = _as_point2d(insertion_point)
    half_h, half_b, half_web = (section["H"] / 2.0,
                                 section["B"] / 2.0,
                                 section["tw"] / 2.0)
    root_t, edge_t = flange_thicknesses(section)
    y_root = half_h - root_t
    y_edge = half_h - edge_t

    # Counter-clockwise sharp outline.  Radius zero keeps the four external
    # flange corners sharp; r2 is the specified flange-end lower arc.
    vertices = (
        Point2d(half_b, half_h),
        Point2d(-half_b, half_h),
        Point2d(-half_b, y_edge),
        Point2d(-half_web, y_root),
        Point2d(-half_web, -y_root),
        Point2d(-half_b, -y_edge),
        Point2d(-half_b, -half_h),
        Point2d(half_b, -half_h),
        Point2d(half_b, -y_edge),
        Point2d(half_web, -y_root),
        Point2d(half_web, y_root),
        Point2d(half_b, y_edge),
    )
    radii = (0.0, 0.0, section["r2"], section["r1"], section["r1"],
             section["r2"], 0.0, 0.0, section["r2"], section["r1"],
             section["r1"], section["r2"])
    corners = tuple(_make_corner(vertices[index - 1], vertex,
                                 vertices[(index + 1) % len(vertices)], radius)
                    for index, (vertex, radius) in enumerate(zip(vertices, radii)))

    segments = []
    current = corners[0].exit
    for index in range(1, len(corners) + 1):
        corner = corners[index % len(corners)]
        if _distance(current, corner.entry) > 1.0e-10:
            segments.append(LineSegment(current, corner.entry))
        if corner.arc is not None:
            segments.append(corner.arc)
        current = corner.exit

    anchor = insertion_anchor(section, insertion_mode)
    dx, dy = insertion_point.x - anchor.x, insertion_point.y - anchor.y
    geometry = IBeamGeometry(
        tuple(_translate_segment(segment, dx, dy) for segment in segments),
        insertion_point,
        insertion_mode,
        section,
    )
    if not geometry.is_closed_and_continuous():
        raise RuntimeError("Internal error: generated I-beam outline is not closed.")
    if geometry.arc_count != 8:
        raise RuntimeError("Internal error: generated I-beam must contain eight arcs.")
    return geometry


def to_bentley_curve_vector(geometry, z=0.0):
    """Convert the profile to the CurveVector constructor exposed by MSPython."""
    if not geometry.is_closed_and_continuous():
        raise ValueError("Cannot convert an open or discontinuous profile.")

    from MSPyBentleyGeom import (  # pylint: disable=import-error
        CurveVector,
        DEllipse3d,
        DPoint3d,
        DSegment3d,
        ICurvePrimitive,
    )

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
        raise ValueError("Fillet radius is too large for the I-beam section.")

    start = _add(vertex, _scale(incoming, -tangent_length))
    end = _add(vertex, _scale(outgoing, tangent_length))
    normal = _left_normal(incoming) if turn > 0.0 else _right_normal(incoming)
    center = _add(start, _scale(normal, radius))
    start_angle = math.atan2(start.y - center.y, start.x - center.x)
    return _Corner(start, end, ArcSegment(start, end, center, radius, start_angle, turn))


def _translate_segment(segment, dx, dy):
    if isinstance(segment, LineSegment):
        return LineSegment(_translate_point(segment.start, dx, dy),
                           _translate_point(segment.end, dx, dy))
    return ArcSegment(_translate_point(segment.start, dx, dy),
                      _translate_point(segment.end, dx, dy),
                      _translate_point(segment.center, dx, dy),
                      segment.radius, segment.start_angle, segment.sweep)


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
        raise ValueError("Coincident I-beam outline vertices are invalid.")
    return Point2d(vector.x / length, vector.y / length)


def _left_normal(vector):
    return Point2d(-vector.y, vector.x)


def _right_normal(vector):
    return Point2d(vector.y, -vector.x)


def _add(point, vector):
    return Point2d(point.x + vector.x, point.y + vector.y)


def _subtract(point_a, point_b):
    return Point2d(point_a.x - point_b.x, point_a.y - point_b.y)


def _scale(vector, factor):
    return Point2d(vector.x * factor, vector.y * factor)


def _distance(point_a, point_b):
    return math.hypot(point_b.x - point_a.x, point_b.y - point_a.y)
