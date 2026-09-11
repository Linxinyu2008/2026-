import unittest

from q4_directional.adapters import OfficialBackend
from q4_directional.adapters import LocalBackend
from q4_directional.scenario import Scenario
from q4_directional.simulator import DirectionalSimulator
from q4_directional.models import ClearResult, Measurement


class FakeClient:
    def measure(self, x, y, channel):
        return {"measure_result": "direction", "svd_deg": 12.5, "virtual_time_s": 7.0}

    def clear(self, x, y, channel):
        return {"clear_result": "failed", "virtual_time_s": 10.0}


class AdapterTests(unittest.TestCase):
    def test_local_backend_exposes_simulator_virtual_time(self):
        backend = LocalBackend(DirectionalSimulator(Scenario.single(1, (0.0, 0.0), 1000.0, None)))
        backend.measure((0.0, 0.0), 1)
        self.assertEqual(backend.virtual_time_s, 5.0)

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


if __name__ == "__main__":
    unittest.main()
