# -*- coding: utf-8 -*-

import unittest

from elbow_selection_logic import (
    dimension_scale_to_mm,
    elbow_frame_from_matrix,
    support_base_from_height,
)


class ElbowSelectionLogicTests(unittest.TestCase):
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
            (13356.4852507, -7593.2572964, -1012.0),
        )
        self.assertTupleAlmostEqual(
            placement["trunnion_top_mm"], frame["vertical_port_mm"]
        )

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

    def assertTupleAlmostEqual(self, actual, expected, places=6):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value, places=places)


if __name__ == "__main__":
    unittest.main()
