import unittest

from q3_common.public.candidates import build_candidates, estimate_time, score_candidate
from q3_common.public.config import Rules
from q3_common.public.coverage import BeliefTracker
from q3_common.public.models import ActionSpec, Measurement, RobotState


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

    def test_deferred_localization_keeps_global_scan_until_unknown_channels_finish(self):
        belief = BeliefTracker()
        track = belief.tracks[1]
        track.status = "TRACKING"
        track.bearings.append(Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0))
        track.last_point = (0.0, 0.0)
        track.distance_upper_bound_m = 1500.0

        candidates = build_candidates(
            belief,
            RobotState(),
            defer_localization_until_discovery_complete=True,
        )

        self.assertFalse(any(item.action and item.action.kind == "LOCALIZE" for item in candidates))

    def test_localization_can_be_enabled_before_discovery_completes(self):
        belief = BeliefTracker()
        track = belief.tracks[1]
        track.status = "TRACKING"
        track.bearings.append(Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0))
        track.last_point = (0.0, 0.0)
        track.distance_upper_bound_m = 1500.0

        candidates = build_candidates(belief, RobotState(), defer_localization_until_discovery_complete=False)

        self.assertTrue(any(item.action and item.action.kind == "LOCALIZE" for item in candidates))


if __name__ == "__main__":
    unittest.main()
