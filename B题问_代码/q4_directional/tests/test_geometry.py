import math
import unittest

from q4_directional.geometry import initial_region, update_region
from q4_directional.models import Measurement


class ConservativeGeometryTests(unittest.TestCase):
    def test_initial_region_contains_boundary_points(self):
        region = initial_region(1800.0, sides=128)
        self.assertTrue(region.contains((1800.0, 0.0), tol=1e-5))
        self.assertTrue(region.contains((0.0, -1800.0), tol=1e-5))

    def test_bearing_region_keeps_a_valid_source_near_zero_degrees(self):
        region = initial_region(1800.0, sides=128)
        measurement = Measurement((0.0, 0.0), 1, "BEARING", 359.0, 5.0)

        updated = update_region(region, measurement, angle_margin_deg=1.005, max_range_m=1500.0)

        self.assertEqual(updated.status, "OK")
        self.assertTrue(updated.contains((1000.0, -17.45), tol=1e-4))
        self.assertLess(updated.radius_m, region.radius_m)

    def test_near_observation_intersects_a_five_metre_outer_disk(self):
        region = initial_region(1800.0, sides=128)
        measurement = Measurement((100.0, 100.0), 1, "NEAR", None, 5.0)

        updated = update_region(region, measurement, angle_margin_deg=1.005, max_range_m=1500.0)

        self.assertEqual(updated.status, "OK")
        self.assertTrue(updated.contains((103.0, 101.0), tol=1e-4))
        self.assertFalse(updated.contains((120.0, 100.0), tol=1e-4))

    def test_disjoint_near_observations_report_inconsistent(self):
        region = initial_region(1800.0, sides=128)
        region = update_region(region, Measurement((0.0, 0.0), 1, "NEAR", None, 5.0), 1.005, 1500.0)

        updated = update_region(region, Measurement((100.0, 0.0), 1, "NEAR", None, 5.0), 1.005, 1500.0)

        self.assertEqual(updated.status, "INCONSISTENT")


if __name__ == "__main__":
    unittest.main()
