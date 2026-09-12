import unittest
from math import cos, hypot, pi, sin

from q3_common.public.coverage import BeliefTracker
from q3_common.public.models import Measurement, RobotState
from q3_common.route_c.framework_v2 import (
    build_framework_candidates,
    choose_framework_v2,
    framework_coverage_points,
)
from q3_common.route_c.official_controller import OfficialRouteCController


class FrameworkV2Tests(unittest.TestCase):
    def test_official_controller_accepts_framework_v2_mode(self):
        controller = OfficialRouteCController(object(), mode="framework_v2")

        self.assertEqual(controller.requested_mode, "framework_v2")
        candidates = controller._candidates()
        self.assertTrue(any(item.action and item.action.action_id.startswith("survey-") for item in candidates))

    def test_compact_coverage_points_cover_target_boundary_at_minimum_radius(self):
        points = framework_coverage_points()
        for degree in range(360):
            target = (1800.0 * cos(degree * pi / 180.0), 1800.0 * sin(degree * pi / 180.0))
            nearest = min(hypot(target[0] - point[0], target[1] - point[1]) for point in points)
            self.assertLessEqual(nearest, 1000.0)

    def test_upper_bound_stops_searching_only_after_sixteen_channels_found(self):
        belief = BeliefTracker()
        for channel in range(1, 17):
            track = belief.tracks[channel]
            track.status = "CLEARABLE"
            track.last_point = (float(channel), 0.0)

        candidates = build_framework_candidates(belief, RobotState())

        self.assertFalse(any(item.action and item.action.kind == "SCAN" for item in candidates))

    def test_ten_discovered_channels_do_not_reveal_unknown_target_count(self):
        belief = BeliefTracker()
        for channel in range(1, 11):
            track = belief.tracks[channel]
            track.status = "CLEARABLE"
            track.last_point = (float(channel), 0.0)

        candidates = build_framework_candidates(belief, RobotState())

        self.assertTrue(any(item.action and item.action.kind == "SCAN" for item in candidates))

    def test_unbounded_track_is_measured_again_at_another_coverage_point(self):
        belief = BeliefTracker()
        for channel, track in belief.tracks.items():
            if channel != 1:
                track.status = "ABSENT"
        belief.observe(Measurement((0.0, 0.0), 1, "BEARING", 0.0, 0.0))

        candidates = build_framework_candidates(belief, RobotState())

        scans = [item for item in candidates if item.action and item.action.kind == "SCAN"]
        self.assertTrue(scans)
        self.assertTrue(any(1 in item.action.channels for item in scans))
        self.assertNotEqual(scans[0].action.point, (0.0, 0.0))

    def test_bounded_region_uses_center_as_next_measurement_point(self):
        belief = BeliefTracker()
        for channel, track in belief.tracks.items():
            if channel != 1:
                track.status = "ABSENT"
        for point, bearing in [
            ((-10000.0, 0.0), 0.0),
            ((10000.0, 0.0), 180.0),
            ((0.0, -10000.0), 90.0),
            ((0.0, 10000.0), 270.0),
        ]:
            belief.observe(Measurement(point, 1, "BEARING", bearing, 0.0))

        candidates = build_framework_candidates(belief, RobotState())

        localize = [item for item in candidates if item.action and item.action.action_id.startswith("geo-localize-")]
        self.assertEqual(len(localize), 1)
        self.assertAlmostEqual(localize[0].action.point[0], 0.0, places=6)
        self.assertAlmostEqual(localize[0].action.point[1], 0.0, places=6)

    def test_policy_finishes_clear_before_scan_and_localize(self):
        belief = BeliefTracker()
        for channel, track in belief.tracks.items():
            track.status = "ABSENT"
        track = belief.tracks[1]
        track.status = "CLEARABLE"
        track.last_point = (0.0, 0.0)
        candidates = build_framework_candidates(belief, RobotState())

        class Env:
            def candidates(self):
                return tuple(candidates)

            def action_masks(self):
                return tuple(item.valid for item in candidates)

        selected = candidates[choose_framework_v2(Env())]
        self.assertEqual(selected.action.kind, "CLEAR")

    def test_policy_keeps_survey_route_when_unknown_channels_remain(self):
        belief = BeliefTracker()
        track = belief.tracks[1]
        track.status = "CLEARABLE"
        track.last_point = (900.0, 0.0)
        candidates = build_framework_candidates(belief, RobotState())

        class Env:
            def candidates(self):
                return tuple(candidates)

            def action_masks(self):
                return tuple(item.valid for item in candidates)

        selected = candidates[choose_framework_v2(Env())]
        self.assertEqual(selected.action.kind, "SCAN")

    def test_policy_uses_nearest_post_survey_task_across_clear_and_localize(self):
        belief = BeliefTracker()
        for track in belief.tracks.values():
            track.status = "ABSENT"
        clear_track = belief.tracks[1]
        clear_track.status = "CLEARABLE"
        clear_track.last_point = (900.0, 0.0)
        for point, bearing in [
            ((-10000.0, 0.0), 0.0),
            ((10000.0, 0.0), 180.0),
            ((0.0, -10000.0), 90.0),
            ((0.0, 10000.0), 270.0),
        ]:
            belief.observe(Measurement(point, 2, "BEARING", bearing, 0.0))
        candidates = build_framework_candidates(belief, RobotState())

        class Env:
            def candidates(self):
                return tuple(candidates)

            def action_masks(self):
                return tuple(item.valid for item in candidates)

        selected = candidates[choose_framework_v2(Env())]
        self.assertTrue(selected.action.action_id.startswith("geo-localize-"))


if __name__ == "__main__":
    unittest.main()
