import unittest

from questions.q4.adapters import OfficialBackend
from questions.q4.adapters import LocalBackend
from questions.q4.scenario import Scenario
from questions.q4.simulator import DirectionalSimulator
from questions.q4.models import ClearResult, Measurement


class FakeClient:
    def measure(self, x, y, channel):
        return {"measure_result": "direction", "svd_deg": 12.5, "virtual_time_s": 7.0}

    def clear(self, x, y, channel):
        return {"clear_result": "no_target_in_range", "virtual_time_s": 10.0}


class AdapterTests(unittest.TestCase):
    def test_local_backend_exposes_simulator_virtual_time(self):
        backend = LocalBackend(DirectionalSimulator(Scenario.single(1, (0.0, 0.0), 1000.0, None)))
        backend.measure((0.0, 0.0), 1)
        self.assertEqual(backend.virtual_time_s, 5.0)

    def test_local_backend_accumulates_clear_statistics(self):
        backend = LocalBackend(DirectionalSimulator(Scenario.single(1, (0.0, 0.0), 1000.0, None)))
        backend.clear((10.0, 0.0), 1)
        backend.clear((100.0, 0.0), 1)

        self.assertEqual(backend.clear_count, 2)
        self.assertEqual(backend.clear_count, backend.clear_success_count + backend.clear_failure_count)

    def test_official_measure_response_is_normalized(self):
        backend = OfficialBackend(FakeClient())
        result = backend.measure((1.0, 2.0), 3)
        self.assertIsInstance(result, Measurement)
        self.assertEqual(result.signal, "BEARING")
        self.assertEqual(result.bearing_deg, 12.5)

    def test_failed_clear_is_normalized_without_changing_channel(self):
        backend = OfficialBackend(FakeClient())
        result = backend.clear((1.0, 2.0), 3)
        self.assertIsInstance(result, ClearResult)
        self.assertFalse(result.success)
        self.assertEqual(backend.current_channel, 1)

    def test_official_backend_accumulates_action_statistics(self):
        backend = OfficialBackend(FakeClient())
        backend.measure((3.0, 4.0), 3)
        backend.measure((3.0, 4.0), 4)
        backend.clear((6.0, 8.0), 4)

        self.assertEqual(backend.command_count, 3)
        self.assertEqual(backend.measure_count, 2)
        self.assertEqual(backend.clear_count, 1)
        self.assertEqual(backend.switch_count, 2)
        self.assertAlmostEqual(backend.move_distance_m, 10.0)
        self.assertEqual(backend.clear_success_count, 0)
        self.assertEqual(backend.clear_failure_count, 1)


if __name__ == "__main__":
    unittest.main()
