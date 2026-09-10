import unittest

from q3_common.public.config import Rules
from q3_common.public.models import Source
from q3_common.public.scenario import SpatialErrorField, make_fixed_scenario
from q3_common.public.simulator import LocalSimulator


class SimulatorTests(unittest.TestCase):
    def test_detection_and_clear_time(self):
        scenario = make_fixed_scenario([Source(1, (100.0, 0.0), 1000.0)])
        sim = LocalSimulator(scenario, Rules())
        measurement = sim.detect_at((0.0, 0.0), 1)
        self.assertEqual(measurement.signal, "BEARING")
        self.assertAlmostEqual(measurement.bearing_deg, 0.0)
        result = sim.clear_at((80.0, 0.0), 1)
        self.assertTrue(result.success)
        self.assertAlmostEqual(sim.virtual_time_s, 26.0)

    def test_same_point_error_is_fixed_and_switch_cost_is_one_second(self):
        scenario = make_fixed_scenario([Source(3, (100.0, 0.0), 1000.0)], error_deg=0.75)
        sim = LocalSimulator(scenario)
        first = sim.detect_at((0.0, 0.0), 3)
        second = sim.detect_at((0.0, 0.0), 3)
        self.assertEqual(first.bearing_deg, second.bearing_deg)
        self.assertAlmostEqual(sim.virtual_time_s, 11.0)
        sim.detect_at((0.0, 0.0), 1)
        self.assertAlmostEqual(sim.virtual_time_s, 17.0)

    def test_near_and_clear_boundaries(self):
        scenario = make_fixed_scenario([Source(1, (20.0, 0.0), 1000.0)])
        sim = LocalSimulator(scenario)
        self.assertEqual(sim.detect_at((15.0, 0.0), 1).signal, "NEAR")
        self.assertTrue(sim.clear_at((0.0, 0.0), 1).success)

    def test_clear_does_not_switch_channel_and_failed_clear_takes_optical_time(self):
        scenario = make_fixed_scenario([Source(2, (100.0, 0.0), 1000.0)])
        sim = LocalSimulator(scenario)
        sim.detect_at((0.0, 0.0), 1)
        before = sim.virtual_time_s
        result = sim.clear_at((0.0, 0.0), 2)
        self.assertFalse(result.success)
        self.assertEqual(sim.current_channel, 1)
        self.assertAlmostEqual(sim.virtual_time_s - before, 3.0)

    def test_spatial_error_is_repeatable_at_one_point_and_can_change_elsewhere(self):
        field = SpatialErrorField((0.0,) * 20, (1.0,) * 20, (0.0,) * 20)
        self.assertEqual(field.value((100.0, 200.0), 1), field.value((100.0, 200.0), 1))
        self.assertNotEqual(field.value((100.0, 200.0), 1), field.value((700.0, 900.0), 1))
        self.assertLessEqual(abs(field.value((700.0, 900.0), 1)), 1.0)


if __name__ == "__main__":
    unittest.main()
