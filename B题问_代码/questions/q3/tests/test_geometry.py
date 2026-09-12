import unittest

from questions.q1.localization_region import solve_localization_region
from questions.q3.shared.geometry import region_summary
from questions.q3.shared.models import Measurement


class GeometryTests(unittest.TestCase):
    def test_summary_keeps_unbounded_region_unbounded(self):
        stations = [(-35.24933083584688, 2.400589704310894), (-98.30400010208645, 9.657155745444513), (64.4317012379502, 9.98039576400349)]
        bearings = [-0.6061595771781894, -1.1047994366983005, -1.5017171251752286]
        measurements = [Measurement(p, 1, "BEARING", b, 0.0) for p, b in zip(stations, bearings)]
        self.assertEqual(solve_localization_region(stations, bearings)["status"], "UNBOUNDED_REGION")
        self.assertEqual(region_summary(measurements)["status"], "UNBOUNDED_REGION")
