from __future__ import division

import os
import sys
import unittest

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from steel_sections import steel_equal_angle_data  # noqa: E402
from steel_sections import steel_equal_angle_geometry  # noqa: E402


class EqualAngleTests(unittest.TestCase):
    def test_catalogue_contains_all_table_a4_profiles(self):
        profiles = steel_equal_angle_data.profile_names()
        self.assertEqual(144, len(profiles))
        self.assertEqual("L20x20x3", profiles[0])
        self.assertEqual("L360x360x35", profiles[-1])

    def test_representative_dimensions_and_l110_correction(self):
        section = steel_equal_angle_data.get_section("L50x50x5")
        self.assertEqual(50.0, section["B"])
        self.assertEqual(5.0, section["t"])
        self.assertEqual(5.5, section["r1"])
        self.assertAlmostEqual(5.0 / 3.0, section["r2"])

        # The source's five "11" rows show B=100 in one column, while their
        # model and published section properties identify them as L110.
        l110 = steel_equal_angle_data.get_section("L110x110x14")
        self.assertEqual(110.0, l110["B"])
        self.assertEqual(29.06, l110["area"])

    def test_every_profile_generates_a_closed_true_arc_boundary(self):
        for profile_name in steel_equal_angle_data.profile_names():
            section = steel_equal_angle_data.get_section(profile_name)
            geometry = steel_equal_angle_geometry.build_equal_angle_geometry(
                section,
                steel_equal_angle_geometry.INSERTION_CENTROID,
                steel_equal_angle_geometry.Point2d(0.0, 0.0),
            )
            self.assertTrue(geometry.is_closed_and_continuous(), profile_name)
            self.assertEqual(6, geometry.line_count, profile_name)
            self.assertEqual(3, geometry.arc_count, profile_name)

    def test_nominal_area_agrees_with_tabulated_area(self):
        for profile_name in steel_equal_angle_data.profile_names():
            section = steel_equal_angle_data.get_section(profile_name)
            computed_cm2 = steel_equal_angle_data.nominal_area_mm2(section) / 100.0
            self.assertLessEqual(
                abs(computed_cm2 - section["area"]), 0.06, profile_name
            )


if __name__ == "__main__":
    unittest.main()
