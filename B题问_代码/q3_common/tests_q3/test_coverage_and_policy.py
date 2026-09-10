import unittest

from q3_common.public.coverage import BeliefTracker, coverage_points
from q3_common.public.models import Measurement, Source
from q3_common.public.scenario import make_fixed_scenario
from q3_common.public.simulator import LocalSimulator
from q3_common.route_b.policy import RouteBPolicy


class CoverageAndPolicyTests(unittest.TestCase):
    def test_unknown_channel_needs_all_seven_points(self):
        tracker = BeliefTracker()
        for index, point in enumerate(coverage_points()):
            tracker.observe(
                Measurement(point, 20, "NONE", None, 5.0),
                index,
            )
            if index < 6:
                self.assertEqual(tracker.tracks[20].status, "UNKNOWN")
        self.assertEqual(tracker.tracks[20].status, "ABSENT")

    def test_route_b_clears_one_source(self):
        source = Source(1, (500.0, 0.0), 1500.0)
        sim = LocalSimulator(make_fixed_scenario([source]))
        belief = RouteBPolicy(sim).run()
        self.assertEqual(belief.tracks[1].status, "CLEARED")


if __name__ == "__main__":
    unittest.main()
