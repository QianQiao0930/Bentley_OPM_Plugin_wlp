from __future__ import division

import math
import os
import sys
import unittest

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from steel_sections import steel_channel_data  # noqa: E402
from steel_sections import steel_channel_geometry  # noqa: E402
from steel_sections import steel_registry  # noqa: E402
from steel_sections import steel_sweep_geometry  # noqa: E402


class _FakeModelInfo(object):
    def __init__(self, uor_per_meter):
        self._uor_per_meter = uor_per_meter

    def GetUorPerMeter(self):
        return self._uor_per_meter


class _FakeModelRef(object):
    def __init__(self, uor_per_meter):
        self._info = _FakeModelInfo(uor_per_meter)

    def GetModelInfo(self):
        return self._info



def _channel_geometry():
    section = steel_channel_data.get_section(steel_channel_data.DEFAULT_PROFILE)
    return steel_channel_geometry.build_channel_geometry(
        section,
        steel_channel_geometry.INSERTION_GEOMETRIC_CENTER,
        steel_channel_geometry.Point2d(0.0, 0.0),
    )


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def _length(vector):
    return math.sqrt(_dot(vector, vector))


class SweepFrameTests(unittest.TestCase):
    def test_horizontal_path_frame_is_orthonormal_and_up_is_world_z(self):
        frame = steel_sweep_geometry.sweep_frame((1.0, 2.0, 3.0), (1.0, 0.0, 0.0))
        self.assertAlmostEqual(0.0, _dot(frame.axis_x, frame.axis_y))
        self.assertAlmostEqual(0.0, _dot(frame.axis_x, frame.axis_z))
        self.assertAlmostEqual(0.0, _dot(frame.axis_y, frame.axis_z))
        self.assertAlmostEqual(1.0, _length(frame.axis_x))
        self.assertAlmostEqual(1.0, _length(frame.axis_y))
        self.assertAlmostEqual(1.0, _length(frame.axis_z))
        self.assertAlmostEqual(1.0, _dot(frame.axis_y, (0.0, 0.0, 1.0)))
        self.assertEqual((1.0, 2.0, 3.0), frame.origin)

    def test_local_point_maps_into_the_plane_normal_to_the_path(self):
        frame = steel_sweep_geometry.sweep_frame((1.0, 2.0, 3.0), (1.0, 0.0, 0.0))
        point = steel_sweep_geometry.map_local_point(frame, 2.0, 5.0)
        self.assertEqual((1.0, 4.0, 8.0), point)
        self.assertAlmostEqual(0.0, _dot(point, frame.axis_z) - _dot(frame.origin, frame.axis_z))

    def test_vertical_path_substitutes_a_perpendicular_up_hint(self):
        frame = steel_sweep_geometry.sweep_frame((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(0.0, _dot(frame.axis_y, (0.0, 0.0, 1.0)))
        self.assertAlmostEqual(1.0, _length(frame.axis_x))
        self.assertAlmostEqual(1.0, _length(frame.axis_y))

    def test_zero_tangent_is_rejected(self):
        with self.assertRaises(ValueError):
            steel_sweep_geometry.sweep_frame((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


class SegmentSamplingTests(unittest.TestCase):
    def test_arc_midpoint_lies_on_the_circle(self):
        geometry = _channel_geometry()
        arcs = [segment for segment in geometry.segments if hasattr(segment, "center")]
        self.assertEqual(2, len(arcs))
        for arc in arcs:
            midpoint = steel_sweep_geometry.arc_midpoint(arc)
            radius = math.hypot(
                midpoint[0] - arc.center.x, midpoint[1] - arc.center.y
            )
            self.assertAlmostEqual(arc.radius, radius)

    def test_every_segment_maps_onto_the_section_plane(self):
        geometry = _channel_geometry()
        frame = steel_sweep_geometry.sweep_frame((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        for segment in geometry.segments:
            points = steel_sweep_geometry.sample_segment(segment, frame)
            expected = 2 if steel_sweep_geometry.segment_kind(segment) == "line" else 3
            self.assertEqual(expected, len(points))
            for point in points:
                self.assertAlmostEqual(0.0, _dot(point, frame.axis_z))


class RegistrySweepGeometryTests(unittest.TestCase):
    def test_scales_to_uor_and_anchors_at_the_local_origin(self):
        section = steel_channel_data.get_section(steel_channel_data.DEFAULT_PROFILE)
        geometry = steel_registry.build_sweep_geometry(
            "parallel_channel",
            section,
            steel_channel_geometry.INSERTION_LOWER_LEFT,
            _FakeModelRef(1000.0),
        )
        self.assertTrue(geometry.is_closed_and_continuous())
        low, high = geometry.bounding_box()
        self.assertAlmostEqual(0.0, low.x)
        self.assertAlmostEqual(0.0, low.y)
        self.assertAlmostEqual(section["B"], high.x)
        self.assertAlmostEqual(section["H"], high.y)

    def test_uor_scale_is_applied_to_the_section(self):
        section = steel_channel_data.get_section(steel_channel_data.DEFAULT_PROFILE)
        geometry = steel_registry.build_sweep_geometry(
            "parallel_channel",
            section,
            steel_channel_geometry.INSERTION_LOWER_LEFT,
            _FakeModelRef(2000.0),
        )
        _, high = geometry.bounding_box()
        self.assertAlmostEqual(2.0 * section["B"], high.x)
        self.assertAlmostEqual(2.0 * section["H"], high.y)


if __name__ == "__main__":
    unittest.main()
