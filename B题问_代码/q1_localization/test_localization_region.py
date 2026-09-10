import unittest

from q1_localization.localization_region import solve_localization_region


class LocalizationRegionTests(unittest.TestCase):
    def test_incompatible_bearings_form_an_empty_region(self):
        result = solve_localization_region([(0.0, 1.0), (0.0, -1.0)], [1.0, -1.0])
        self.assertEqual(result["status"], "EMPTY_REGION")
