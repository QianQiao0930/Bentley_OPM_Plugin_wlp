from __future__ import division

import unittest

import steel_unequal_angle_data
import steel_unequal_angle_geometry


class UnequalAngleTests(unittest.TestCase):
    def test_catalogue_contains_all_table_a5_profiles(self):
        profiles = steel_unequal_angle_data.profile_names()
        self.assertEqual(71, len(profiles))
        self.assertEqual("L25x16x3", profiles[0])
        self.assertEqual("L200x125x18", profiles[-1])
        self.assertEqual("L63x40x5", steel_unequal_angle_data.DEFAULT_PROFILE)

    def test_representative_dimensions_and_centroid_offsets(self):
        section = steel_unequal_angle_data.get_section("L63x40x5")
        self.assertEqual(63.0, section["BL"])
        self.assertEqual(40.0, section["BS"])
        self.assertEqual(5.0, section["t"])
        self.assertEqual(7.0, section["r1"])
        self.assertAlmostEqual(5.0 / 3.0, section["r2"])
        self.assertEqual(9.5, section["X0"])
        self.assertEqual(20.8, section["Y0"])

    def test_every_profile_generates_a_closed_true_arc_boundary(self):
        for profile_name in steel_unequal_angle_data.profile_names():
            section = steel_unequal_angle_data.get_section(profile_name)
            geometry = steel_unequal_angle_geometry.build_unequal_angle_geometry(
                section,
                steel_unequal_angle_geometry.INSERTION_CENTROID,
                steel_unequal_angle_geometry.Point2d(0.0, 0.0),
            )
            self.assertTrue(geometry.is_closed_and_continuous(), profile_name)
            self.assertEqual(6, geometry.line_count, profile_name)
            self.assertEqual(3, geometry.arc_count, profile_name)

    def test_nominal_area_agrees_with_tabulated_area(self):
        for profile_name in steel_unequal_angle_data.profile_names():
            section = steel_unequal_angle_data.get_section(profile_name)
            computed_cm2 = steel_unequal_angle_data.nominal_area_mm2(section) / 100.0
            self.assertLessEqual(
                abs(computed_cm2 - section["area"]), 0.01, profile_name
            )


if __name__ == "__main__":
    unittest.main()
