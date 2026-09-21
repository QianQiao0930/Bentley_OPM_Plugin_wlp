"""Pure geometry helpers for sweeping a steel section along a path.

The module deliberately imports nothing from the Bentley runtime: it only
operates on plain tuples and on the ``LineSegment`` / ``ArcSegment`` records
produced by the ``steel_<family>_geometry`` modules.  The frame maths and the
arc sampling can therefore be unit-tested with ordinary CPython, while
``steel_tool.py`` performs the final conversion to Bentley curve primitives.
"""

from __future__ import division

import math
from collections import namedtuple


# origin / axis_x (local +X) / axis_y (local +Y) / axis_z (path tangent)
Frame = namedtuple("Frame", "origin axis_x axis_y axis_z")

DEFAULT_UP_HINT = (0.0, 0.0, 1.0)

_FALLBACK_UP_HINTS = (
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
)

_PARALLEL_LIMIT = 1.0 - 1.0e-9


def _length(vector):
    return math.sqrt(sum(component * component for component in vector))


def _normalize(vector):
    length = _length(vector)
    if length <= 1.0e-12:
        return None
    return tuple(component / length for component in vector)


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def _cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def sweep_frame(origin, tangent, up_hint=DEFAULT_UP_HINT):
    """Return the section frame whose local ``+Y`` points along *up_hint*.

    The path tangent becomes the frame ``axis_z``; the section's local ``+X``
    and ``+Y`` are mapped into the plane normal to the path.  ``up_hint`` is
    only a reference direction: when it is degenerate or nearly parallel to the
    tangent a perpendicular world axis is substituted so the frame is always
    orthonormal.
    """
    axis_z = _normalize(tuple(float(component) for component in tangent))
    if axis_z is None:
        raise ValueError("路径起点切向为零，无法定位截面。")

    up = _normalize(tuple(float(component) for component in up_hint))
    if up is None or abs(_dot(up, axis_z)) > _PARALLEL_LIMIT:
        up = None
        for candidate in _FALLBACK_UP_HINTS:
            candidate = _normalize(candidate)
            if candidate is not None and abs(_dot(candidate, axis_z)) <= _PARALLEL_LIMIT:
                up = candidate
                break
    if up is None:
        raise ValueError("无法为路径切向确定参考方向。")

    axis_x = _normalize(_cross(up, axis_z))
    if axis_x is None:
        raise ValueError("路径切向与参考方向共线，无法定位截面。")
    axis_y = _normalize(_cross(axis_z, axis_x))
    return Frame(
        tuple(float(component) for component in origin), axis_x, axis_y, axis_z
    )


def map_local_point(frame, x, y):
    """Map a section-local ``(x, y)`` onto the frame in world coordinates."""
    return tuple(
        frame.origin[index]
        + x * frame.axis_x[index]
        + y * frame.axis_y[index]
        for index in range(3)
    )


def rotate_frame(frame, angle_deg):
    """Rotate the section frame about the path tangent (``axis_z``).

    The section keeps its insertion base at ``frame.origin`` and simply spins
    within the plane normal to the path.  A positive angle turns the section
    clockwise when looking along the path direction; ``0`` returns the frame
    unchanged (the default sweep orientation).
    """
    angle = math.radians(float(angle_deg))
    if abs(angle) < 1e-12:
        return frame
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    axis_z = frame.axis_z

    def spin(vector):
        cross = _cross(axis_z, vector)
        return tuple(vector[index] * cos_a + cross[index] * sin_a for index in range(3))

    return Frame(frame.origin, spin(frame.axis_x), spin(frame.axis_y), axis_z)


def segment_kind(segment):
    """Return ``"arc"`` for an arc record, ``"line"`` otherwise."""
    return "arc" if hasattr(segment, "center") else "line"


def arc_midpoint(segment):
    """Return the ``(x, y)`` point at the middle of a section-local arc."""
    angle = segment.start_angle + segment.sweep / 2.0
    return (
        segment.center.x + segment.radius * math.cos(angle),
        segment.center.y + segment.radius * math.sin(angle),
    )


def sample_segment(segment, frame):
    """Return the mapped world points describing one section segment.

    A line yields its two endpoints; an arc yields three points (start, middle
    and end) so the Bentley side can rebuild the true circular arc through
    ``DEllipse3d.FromPointsOnArc`` without any faceting.
    """
    if segment_kind(segment) == "line":
        return (
            map_local_point(frame, segment.start.x, segment.start.y),
            map_local_point(frame, segment.end.x, segment.end.y),
        )
    midpoint = arc_midpoint(segment)
    return (
        map_local_point(frame, segment.start.x, segment.start.y),
        map_local_point(frame, midpoint[0], midpoint[1]),
        map_local_point(frame, segment.end.x, segment.end.y),
    )
