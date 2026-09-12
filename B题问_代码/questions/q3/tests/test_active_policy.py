import unittest

from questions.q3.shared.models import Source
from questions.q3.shared.scenario import make_fixed_scenario
from questions.q3.shared.simulator import LocalSimulator
from questions.q3.method_b.active_policy import ActiveRouteBPolicy


class ActivePolicyTests(unittest.TestCase):
    def test_active_policy_clears_a_source_and_keeps_history(self):
        simulator = LocalSimulator(make_fixed_scenario([Source(1, (500.0, 0.0), 1500.0)]))
        policy = ActiveRouteBPolicy(simulator)
        belief = policy.run()
        self.assertEqual(belief.cleared_count, 1)
        self.assertGreater(len(policy.candidate_history), 0)


if __name__ == "__main__":
    unittest.main()
