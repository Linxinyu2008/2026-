import unittest

from q3_common.public.candidates import build_candidates, estimate_time, score_candidate
from q3_common.public.config import Rules
from q3_common.public.coverage import BeliefTracker
from q3_common.public.models import ActionSpec, RobotState


class CandidateTests(unittest.TestCase):
    def test_scan_cost_counts_each_channel_and_switch(self):
        action = ActionSpec("scan", "SCAN", (0.0, 0.0), (1, 3, 5))
        self.assertAlmostEqual(estimate_time(action, RobotState(), Rules()), 17.0)

    def test_clear_cost_does_not_include_channel_switch(self):
        action = ActionSpec("clear", "CLEAR", (0.0, 0.0), (2,))
        self.assertAlmostEqual(estimate_time(action, RobotState((0.0, 0.0), 1)), 5.0)

    def test_candidate_schema_has_twelve_stable_slots(self):
        candidates = build_candidates(BeliefTracker(), RobotState())
        self.assertEqual(len(candidates), 12)
        self.assertTrue(candidates[0].valid)
        self.assertEqual(candidates[-1].action.kind, "SCAN")

    def test_invalid_candidate_is_never_selected(self):
        candidates = build_candidates(BeliefTracker(), RobotState())
        self.assertEqual(score_candidate(candidates[4]), float("-inf"))


if __name__ == "__main__":
    unittest.main()
