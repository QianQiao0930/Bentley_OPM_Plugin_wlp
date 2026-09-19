from __future__ import division

import os
import sys
import unittest

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from steel_sections import steel_registry  # noqa: E402


class UnifiedRegistryTests(unittest.TestCase):
    def test_expected_family_order_and_future_interfaces(self):
        self.assertEqual(
            (
                "parallel_channel", "ordinary_ibeam", "hot_rolled_h",
                "tapered_channel", "equal_angle", "unequal_angle", "hk_section",
            ),
            steel_registry.family_ids(),
        )
        self.assertEqual(
            (
                "parallel_channel", "ordinary_ibeam", "hot_rolled_h",
                "tapered_channel", "equal_angle", "unequal_angle", "hk_section",
            ),
            steel_registry.family_ids(include_future=False),
        )
        for identifier in steel_registry.family_ids(include_future=False):
            self.assertTrue(steel_registry.get_family(identifier).available)

    def test_all_existing_data_and_geometry_adapters_work_together(self):
        expected_counts = {
            "parallel_channel": 34,
            "ordinary_ibeam": 45,
            "hot_rolled_h": 431,
            "tapered_channel": 41,
            "equal_angle": 144,
            "unequal_angle": 71,
            "hk_section": 378,
        }
        for family_id, expected_count in expected_counts.items():
            family = steel_registry.get_family(family_id)
            profiles = steel_registry.profile_names(family_id)
            self.assertEqual(expected_count, len(profiles), family_id)
            self.assertIn(steel_registry.default_profile(family_id), profiles)
            self.assertTrue(steel_registry.detail_rows(family_id, profiles[0]))
            builder = getattr(family.geometry, family.builder)
            insertion_mode = steel_registry.default_insertion_mode(family_id)
            for profile_name in profiles:
                section = steel_registry.get_section(family_id, profile_name)
                origin = family.geometry.Point2d(0.0, 0.0)
                geometry = builder(section, insertion_mode, origin)
                self.assertTrue(geometry.is_closed_and_continuous(), "{} {}".format(family_id, profile_name))

    def test_unknown_family_cannot_request_profiles(self):
        with self.assertRaises(KeyError):
            steel_registry.profile_names("not_a_steel_family")


if __name__ == "__main__":
    unittest.main()
