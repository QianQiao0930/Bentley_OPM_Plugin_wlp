from __future__ import division

import unittest

from steel_tapered_channel_data import (
    flange_thicknesses, get_section, nominal_area_mm2, profile_names,
)
from steel_tapered_channel_geometry import (
    INSERTION_CENTROID, Point2d, build_tapered_channel_geometry,
)


class TaperedChannelTests(unittest.TestCase):
    def test_catalogue_has_all_supplied_table_rows(self):
        self.assertEqual(41, len(profile_names()))

    def test_20a_has_a_one_to_ten_flange_slope(self):
        section = get_section("20a")
        root_t, edge_t = flange_thicknesses(section)
        self.assertAlmostEqual((section["B"] - section["tw"]) / 10.0, root_t - edge_t)
        self.assertAlmostEqual(section["tf"], (root_t + edge_t) / 2.0)

    def test_every_profile_is_closed_with_four_true_arcs(self):
        for name in profile_names():
            geometry = build_tapered_channel_geometry(
                get_section(name), INSERTION_CENTROID, Point2d(0.0, 0.0)
            )
            self.assertTrue(geometry.is_closed_and_continuous(), name)
            self.assertEqual(8, geometry.line_count, name)
            self.assertEqual(4, geometry.arc_count, name)

    def test_table_areas_match_the_tapered_channel_formula(self):
        for name in profile_names():
            section = get_section(name)
            self.assertAlmostEqual(
                section["area"], nominal_area_mm2(section) / 100.0, delta=0.04, msg=name
            )


if __name__ == "__main__":
    unittest.main()
