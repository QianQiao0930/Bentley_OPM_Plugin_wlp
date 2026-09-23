# -*- coding: utf-8 -*-

import os
import sys
import unittest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_GEOM_DIR = os.path.join(os.path.dirname(_TEST_DIR), '竖直弯头的竖直耳轴')
if os.path.isdir(_GEOM_DIR) and _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)

from elbow_selection_logic import (
    dimension_scale_to_mm,
    elbow_frame_from_matrix,
    horizontal_elbow_frame_from_matrix,
    f2_number,
    height_from_drag_z,
    height_from_view_drag,
    moved_from_selection_view,
    support_base_from_height,
)


class ElbowSelectionLogicTests(unittest.TestCase):
    def test_horizontal_elbow_support_is_at_arc_midpoint(self):
        matrix = (1.0, 0.0, 0.0, 100000.0,
                  0.0, 1.0, 1.0, 200000.0,
                  0.0, 0.0, 0.0, 300000.0)
        frame = horizontal_elbow_frame_from_matrix(matrix, 1000.0, 300.0, 300.0)
        offset = 300.0 / 2.0 ** 0.5
        self.assertTupleAlmostEqual(frame['run_port_mm'], (100.0, 200.0, 300.0))
        self.assertTupleAlmostEqual(frame['outlet_port_mm'], (400.0, 500.0, 300.0))
        self.assertTupleAlmostEqual(frame['support_axis_mm'],
                                    (100.0 + offset, 500.0 - offset, 300.0))
        self.assertTupleAlmostEqual(frame['horizontal_direction'],
                                    (2.0 ** -0.5, 2.0 ** -0.5, 0.0))
        placement = support_base_from_height(frame, 500.0, 12.0)
        self.assertAlmostEqual(placement['base_bottom_mm'][2], -200.0)
        self.assertAlmostEqual(placement['trunnion_bottom_mm'][2], -188.0)
        self.assertTupleAlmostEqual(placement['trunnion_top_mm'],
                                    frame['support_axis_mm'])

    def test_horizontal_elbow_rejects_vertical_and_inclined_axes(self):
        vertical = (1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0)
        inclined = (2.0 ** -0.5, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    2.0 ** -0.5, 0.0, 1.0, 0.0)
        for matrix in (vertical, inclined):
            with self.assertRaisesRegex(ValueError, '不是水平弯头'):
                horizontal_elbow_frame_from_matrix(matrix, 1000.0, 300.0, 300.0)

    def test_horizontal_elbow_number_has_he_suffix(self):
        self.assertEqual('F2-16"-8"-C1-500-A-HE',
                         f2_number(400, 200, 8.18, 8.18, 'C1', 500, 'A',
                                   horizontal_elbow=True))

    def test_user_sample_matrix(self):
        matrix = (
            -1.0, 0.0, 0.0, 13737485.2507,
            0.0, -1.0, 0.0, -7593257.2964,
            0.0, 0.0, 1.0, 0.0,
        )
        frame = elbow_frame_from_matrix(matrix, 1000.0, 381.0, 381.0)
        self.assertTupleAlmostEqual(
            frame["horizontal_port_mm"],
            (13737.4852507, -7593.2572964, 0.0),
        )
        self.assertTupleAlmostEqual(
            frame["vertical_port_mm"],
            (13356.4852507, -7593.2572964, 381.0),
        )
        self.assertTupleAlmostEqual(
            frame["arc_center_mm"],
            (13737.4852507, -7593.2572964, 381.0),
        )
        self.assertTupleAlmostEqual(
            frame["horizontal_direction"], (-1.0, 0.0, 0.0)
        )
        start_radius = tuple(
            frame["horizontal_port_mm"][i] - frame["arc_center_mm"][i]
            for i in range(3)
        )
        self.assertAlmostEqual(sum(
            start_radius[i] * frame["horizontal_direction"][i]
            for i in range(3)
        ), 0.0, places=6)

        placement = support_base_from_height(frame, 1000.0, 12.0)
        self.assertTupleAlmostEqual(
            placement["base_bottom_mm"],
            (13356.4852507, -7593.2572964, -1000.0),
        )
        self.assertTupleAlmostEqual(
            placement["trunnion_bottom_mm"],
            (13356.4852507, -7593.2572964, -988.0),
        )
        self.assertTupleAlmostEqual(
            placement["trunnion_top_mm"], frame["vertical_port_mm"]
        )

        no_plate = support_base_from_height(frame, 1000.0, 0.0)
        self.assertTupleAlmostEqual(no_plate["trunnion_bottom_mm"],
                                    no_plate["base_bottom_mm"])
        with_liner = support_base_from_height(frame, 1000.0, 12.0, 3.0)
        self.assertAlmostEqual(with_liner['liner_bottom_mm'][2], -1000.0)
        self.assertAlmostEqual(with_liner['base_bottom_mm'][2], -997.0)
        self.assertAlmostEqual(with_liner['trunnion_bottom_mm'][2], -985.0)

    def test_vertical_port_can_be_matrix_origin(self):
        matrix = (
            0.0, 0.0, 1.0, 1000.0,
            0.0, 1.0, 0.0, 2000.0,
            -1.0, 0.0, 0.0, 3000.0,
        )
        frame = elbow_frame_from_matrix(matrix, 1000.0, 300.0, 300.0)
        self.assertTupleAlmostEqual(frame["vertical_port_mm"], (1.0, 2.0, 3.0))
        self.assertTupleAlmostEqual(frame["horizontal_port_mm"], (301.0, 2.0, -297.0))
        self.assertTupleAlmostEqual(frame["arc_center_mm"], (301.0, 2.0, 3.0))
        self.assertTupleAlmostEqual(frame["horizontal_direction"], (-1.0, 0.0, 0.0))

    def test_inclined_elbow_is_rejected(self):
        root = 2.0 ** -0.5
        matrix = (
            root, 0.0, -root, 0.0,
            0.0, 1.0, 0.0, 0.0,
            root, 0.0, root, 0.0,
        )
        with self.assertRaisesRegex(ValueError, "不是竖直弯头"):
            elbow_frame_from_matrix(matrix, 1000.0, 300.0, 300.0)

    def test_downward_vertical_end_is_rejected(self):
        matrix = (
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, -1.0, 0.0,
        )
        with self.assertRaisesRegex(ValueError, "竖直端朝下"):
            elbow_frame_from_matrix(matrix, 1000.0, 300.0, 300.0)

    def test_dimension_units(self):
        self.assertEqual(dimension_scale_to_mm("MM", 250.0), 1.0)
        self.assertEqual(dimension_scale_to_mm("M", 0.25), 1000.0)
        self.assertEqual(dimension_scale_to_mm(None, 0.25), 1000.0)

    def test_drag_height_uses_only_world_z_and_model_units(self):
        self.assertAlmostEqual(height_from_drag_z(381.0, -619000.0, 1000.0), 1000.0)
        self.assertAlmostEqual(height_from_drag_z(381.0, 381000.0, 1000.0), 0.0)
        with self.assertRaises(ValueError):
            height_from_drag_z(381.0, -619000.0, 0.0)

    def test_view_drag_projects_to_vertical_axis_without_snap_depth(self):
        self.assertAlmostEqual(
            height_from_view_drag((100.0, 200.0), (140.0, 280.0),
                                  (160.0, 320.0)), 1500.0)
        self.assertAlmostEqual(
            height_from_view_drag((100.0, 200.0), (140.0, 280.0),
                                  (140.0, 280.0)), 1000.0)
        with self.assertRaises(ValueError):
            height_from_view_drag((100.0, 200.0), (100.0, 200.0),
                                  (150.0, 250.0))

    def test_selection_click_cannot_confirm_drag_at_same_view_position(self):
        pick = (2, 100.0, 200.0)
        self.assertFalse(moved_from_selection_view(pick, 2, (100.0, 200.0)))
        self.assertFalse(moved_from_selection_view(pick, 2, (103.0, 204.0)))
        self.assertTrue(moved_from_selection_view(pick, 2, (100.0, 206.0)))

    def test_f2_number_and_applicable_suffixes(self):
        self.assertEqual(
            f2_number(400, 200, 8.18, 8.18, 'C1', 500, 'A'),
            'F2-16"-8"-C1-500-A')
        self.assertEqual(
            f2_number(400, 200, 22.23, 8.18, 'C1', 500, 'A', ptfe=True),
            'F2-16"-8"(22.23)-C1-500-A-F')
        with self.assertRaisesRegex(ValueError, '无底板'):
            f2_number(400, 200, 8.18, 8.18, 'C1', 500, 'C', ptfe=True)

    def assertTupleAlmostEqual(self, actual, expected, places=6):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value, places=places)


if __name__ == "__main__":
    unittest.main()
