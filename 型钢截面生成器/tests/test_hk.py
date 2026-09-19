from __future__ import division

import os
import sys
import unittest

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from steel_sections import steel_hbeam_geometry  # noqa: E402
from steel_sections import steel_hk_data  # noqa: E402


class HKSectionTests(unittest.TestCase):
    def test_catalogue_contains_all_supplied_hk_profiles(self):
        profiles = steel_hk_data.profile_names()
        self.assertEqual(378, len(profiles))
        self.assertEqual("HK100x100 [106x103x7.1x8.8]", profiles[0])
        self.assertEqual("HK1200x400 [1210x422x40x48]", profiles[-1])
        self.assertIn(steel_hk_data.DEFAULT_PROFILE, profiles)

    def test_profile_name_distinguishes_duplicate_nominal_models(self):
        names = [name for name in steel_hk_data.profile_names() if name.startswith("HK100x100")]
        self.assertEqual(2, len(names))
        self.assertNotEqual(names[0], names[1])

    def test_representative_dimensions_and_properties(self):
        section = steel_hk_data.get_section("HK100x100 [106x103x7.1x8.8]")
        self.assertEqual(106.0, section["H"])
        self.assertEqual(103.0, section["B"])
        self.assertEqual(7.1, section["t1"])
        self.assertEqual(8.8, section["t2"])
        self.assertEqual(6.0, section["r"])
        self.assertEqual(24.71, section["area"])

    def test_every_profile_reuses_closed_hbeam_geometry(self):
        for profile_name in steel_hk_data.profile_names():
            section = steel_hk_data.get_section(profile_name)
            geometry = steel_hbeam_geometry.build_hbeam_geometry(
                section,
                steel_hbeam_geometry.INSERTION_CENTROID,
                steel_hbeam_geometry.Point2d(0.0, 0.0),
            )
            self.assertTrue(geometry.is_closed_and_continuous(), profile_name)
            self.assertEqual(12, geometry.line_count, profile_name)
            self.assertEqual(4, geometry.arc_count, profile_name)

    def test_nominal_area_agrees_with_tabulated_area(self):
        for profile_name in steel_hk_data.profile_names():
            section = steel_hk_data.get_section(profile_name)
            computed_cm2 = steel_hk_data.nominal_area_mm2(section) / 100.0
            self.assertLessEqual(
                abs(computed_cm2 - section["area"]), 0.5, profile_name
            )


if __name__ == "__main__":
    unittest.main()
