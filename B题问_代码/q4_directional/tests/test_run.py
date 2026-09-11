import unittest

from q4_directional.run import demo_scenario, run_backend
from q4_directional.adapters import LocalBackend
from q4_directional.config import Config
from q4_directional.geometry import initial_region
from q4_directional.simulator import DirectionalSimulator
from q4_directional.triangular_grid import grid_for_region


class RunScenarioTests(unittest.TestCase):
    def test_demo_seed_changes_valid_mixed_scenario(self):
        first = demo_scenario(0)
        second = demo_scenario(1)
        self.assertNotEqual(first.sources, second.sources)
        self.assertGreaterEqual(len(first.sources), 10)
        self.assertLessEqual(len(first.sources), 16)
        self.assertGreaterEqual(len(second.sources), 10)
        self.assertLessEqual(len(second.sources), 16)

    def test_run_backend_reports_budget_stop_without_throwing(self):
        backend = LocalBackend(DirectionalSimulator(demo_scenario(0)))
        result = run_backend(backend, Config(), max_actions=0)
        self.assertFalse(result["completed"])
        self.assertEqual(result["termination_reason"], "max_actions")


if __name__ == "__main__":
    unittest.main()
