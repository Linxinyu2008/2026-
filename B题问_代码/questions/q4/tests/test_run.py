import unittest

from questions.q4.run import demo_scenario, run_backend
from questions.q4.adapters import LocalBackend
from questions.q4.config import Config
from questions.q4.geometry import initial_region
from questions.q4.simulator import DirectionalSimulator
from questions.q4.triangular_grid import grid_for_region


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

    def test_run_backend_reports_backend_failure_without_throwing(self):
        class FailingBackend:
            position = (0.0, 0.0)
            current_channel = 1

            def measure(self, point, channel):
                raise RuntimeError("simulated transport failure")

        result = run_backend(FailingBackend(), Config(), max_actions=1)

        self.assertFalse(result["completed"])
        self.assertIn("simulated transport failure", result["termination_reason"])


if __name__ == "__main__":
    unittest.main()
