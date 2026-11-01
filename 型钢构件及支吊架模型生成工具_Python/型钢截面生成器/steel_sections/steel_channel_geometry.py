"""Geometry construction for a true-arc, parallel-leg channel outline.

This module deliberately has no Bentley imports until conversion to a
``CurveVector`` is requested.  Its mathematical part can therefore be tested
with ordinary CPython as well as from OpenPlant Modeler.
"""

from __future__ import division

import math
from collections import namedtuple

from .steel_channel_data import validate_section


Point2d = namedtuple("Point2d", "x y")
LineSegment = namedtuple("LineSegment", "start end")
ArcSegment = namedtuple("ArcSegment", "start end center radius start_angle sweep")


INSERTION_CENTROID = "centroid"
INSERTION_GEOMETRIC_CENTER = "geometric_center"
INSERTION_WEB_OUTSIDE_CENTER = "web_outside_center"
INSERTION_LOWER_LEFT = "lower_left"

INSERTION_MODES = (
    (INSERTION_CENTROID, "截面重心（默认）"),
    (INSERTION_GEOMETRIC_CENTER, "几何中心"),
    (INSERTION_WEB_OUTSIDE_CENTER, "腹板外侧中心"),
    (INSERTION_LOWER_LEFT, "左下角"),
)


class ChannelGeometry(object):
    """A closed channel outline consisting of lines and genuine arc segments."""

    def __init__(self, segments, insertion_point, anchor_mode, section):
        self.segments = tuple(segments)
        self.insertion_point = insertion_point
        self.anchor_mode = anchor_mode
        self.section = dict(section)

    @property
    def arc_count(self):
        return sum(isinstance(segment, ArcSegment) for segment in self.segments)

    @property
    def line_count(self):
        return sum(isinstance(segment, LineSegment) for segment in self.segments)

    def is_closed_and_continuous(self, tolerance=1.0e-9):
        """Return whether every segment joins the next, including the closure."""
        if not self.segments:
            return False
        for index, segment in enumerate(self.segments):
            next_segment = self.segments[(index + 1) % len(self.segments)]
            if _distance(segment.end, next_segment.start) > tolerance:
                return False
        return True

    def bounding_box(self):
        """Return a conservative bounding box for line/quarter-arc geometry."""
        points = []
        for segment in self.segments:
            points.extend((segment.start, segment.end))
            if isinstance(segment, ArcSegment):
                points.append(segment.center)
        return (
            Point2d(min(point.x for point in points), min(point.y for point in points)),
            Point2d(max(point.x for point in points), max(point.y for point in points)),
        )


def scale_section(section, factor):
    """Scale a millimetre section dictionary into the current DGN UORs."""
    validate_section(section)
    if factor <= 0.0:
        raise ValueError("Scale factor must be positive.")
    return {key: value * factor for key, value in section.items()}


def parallel_leg_area(section):
    """Return the area for the exact nominal geometry constructed here."""
    validate_section(section)
    h, b, tw, tf, r = (section[key] for key in ("H", "B", "tw", "tf", "r"))
    sharp_l_area = tw * h + 2.0 * (b - tw) * tf
    return sharp_l_area + 0.5 * math.pi * r * r


def parallel_leg_centroid(section):
    """Return the centroid measured from the outside web / lower flange faces."""
    validate_section(section)
    h, b, tw, tf, r = (section[key] for key in ("H", "B", "tw", "tf", "r"))

    web_area = tw * h
    flange_area = 2.0 * (b - tw) * tf
    sharp_l_area = web_area + flange_area
    sharp_l_x = (
        web_area * (tw / 2.0) + flange_area * ((b + tw) / 2.0)
    ) / sharp_l_area

    # Two re-entrant inside fillets are two quarter circles.  The shape is
    # symmetric about H/2, so only the x coordinate needs a full calculation.
    fillet_area = 0.5 * math.pi * r * r
    fillet_x = tw + r - (4.0 * r / (3.0 * math.pi))
    area = sharp_l_area + fillet_area
    x = (sharp_l_area * sharp_l_x + fillet_area * fillet_x) / area
    return Point2d(x, h / 2.0)


def insertion_anchor(section, insertion_mode):
    """Return the local point that must coincide with the user data point."""
    validate_section(section)
    h, b = section["H"], section["B"]
    if insertion_mode == INSERTION_CENTROID:
        return parallel_leg_centroid(section)
    if insertion_mode == INSERTION_GEOMETRIC_CENTER:
        return Point2d(b / 2.0, h / 2.0)
    if insertion_mode == INSERTION_WEB_OUTSIDE_CENTER:
        return Point2d(0.0, h / 2.0)
    if insertion_mode == INSERTION_LOWER_LEFT:
        return Point2d(0.0, 0.0)
    raise ValueError("Unsupported insertion mode: {0}".format(insertion_mode))


def build_channel_geometry(section, insertion_mode=INSERTION_CENTROID,
                           insertion_point=Point2d(0.0, 0.0)):
    """Build a closed 2D channel profile placed at *insertion_point*.

    The local profile opens toward +X.  It uses eight line segments and two
    clockwise quarter-circle arcs at the web/flange inside corners.  All input
    values must already be in the same coordinate units as ``insertion_point``.
    """
    validate_section(section)
    insertion_point = _as_point2d(insertion_point)
    h, b, tw, tf, r = (section[key] for key in ("H", "B", "tw", "tf", "r"))

    # Canonical profile origin: outside web face / lower flange face.
    p0 = Point2d(0.0, 0.0)
    p1 = Point2d(b, 0.0)
    p2 = Point2d(b, tf)
    p3 = Point2d(tw + r, tf)
    p4 = Point2d(tw, tf + r)
    p5 = Point2d(tw, h - tf - r)
    p6 = Point2d(tw + r, h - tf)
    p7 = Point2d(b, h - tf)
    p8 = Point2d(b, h)
    p9 = Point2d(0.0, h)

    bottom_center = Point2d(tw + r, tf + r)
    top_center = Point2d(tw + r, h - tf - r)
    raw_segments = (
        LineSegment(p0, p1),
        LineSegment(p1, p2),
        LineSegment(p2, p3),
        ArcSegment(p3, p4, bottom_center, r, -math.pi / 2.0, -math.pi / 2.0),
        LineSegment(p4, p5),
        ArcSegment(p5, p6, top_center, r, math.pi, -math.pi / 2.0),
        LineSegment(p6, p7),
        LineSegment(p7, p8),
        LineSegment(p8, p9),
        LineSegment(p9, p0),
    )

    anchor = insertion_anchor(section, insertion_mode)
    dx = insertion_point.x - anchor.x
    dy = insertion_point.y - anchor.y
    segments = tuple(_translate_segment(segment, dx, dy) for segment in raw_segments)
    geometry = ChannelGeometry(segments, insertion_point, insertion_mode, section)
    if not geometry.is_closed_and_continuous():
        raise RuntimeError("Internal error: generated channel profile is not closed.")
    if geometry.arc_count != 2:
        raise RuntimeError("Internal error: generated channel profile must contain two arcs.")
    return geometry


def to_bentley_curve_vector(geometry, z=0.0):
    """Convert :class:`ChannelGeometry` into an MSPython ``CurveVector``.

    Imports are intentionally local: this module remains unit-testable outside
    a Bentley-hosted Python process.  ``DEllipse3d`` retains the two true arc
    primitives; it is not stroked into a polyline.
    """
    if not geometry.is_closed_and_continuous():
        raise ValueError("Cannot convert an open or discontinuous profile.")

    from MSPyBentleyGeom import (  # pylint: disable=import-error
        CurveVector,
        DEllipse3d,
        DPoint3d,
        DSegment3d,
        ICurvePrimitive,
    )

    # MSPython exposes CurveVector's native constructor (rather than the
    # C++/.NET ``CurveVector.Create`` factory) in the OpenPlant runtime.
    curves = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
    for segment in geometry.segments:
        if isinstance(segment, LineSegment):
            start = DPoint3d(segment.start.x, segment.start.y, z)
            end = DPoint3d(segment.end.x, segment.end.y, z)
            curves.Add(ICurvePrimitive.CreateLine(DSegment3d(start, end)))
        else:
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


def _translate_segment(segment, dx, dy):
    if isinstance(segment, LineSegment):
        return LineSegment(_translate_point(segment.start, dx, dy),
                           _translate_point(segment.end, dx, dy))
    return ArcSegment(
        _translate_point(segment.start, dx, dy),
        _translate_point(segment.end, dx, dy),
        _translate_point(segment.center, dx, dy),
        segment.radius,
        segment.start_angle,
        segment.sweep,
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


def _distance(point_a, point_b):
    return math.hypot(point_b.x - point_a.x, point_b.y - point_a.y)
