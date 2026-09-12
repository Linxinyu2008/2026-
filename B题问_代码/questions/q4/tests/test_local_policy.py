import unittest

from questions.q4.config import Config
from questions.q4.geometry import initial_region
from questions.q4.local_policy import next_local_action, record_measurement
from questions.q4.models import ChannelStatus, LocalMode, Measurement, RobotState


class LocalPolicyTests(unittest.TestCase):
    def test_local_measurement_budget_cannot_be_reset_by_bearing(self):
        track = record_measurement(None, Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0), initial_region(1800.0, 64))
        config = Config(max_local_measurements=2, no_progress_window=4)
        track.local_measure_count = 1

        record_measurement(track, Measurement((10.0, 0.0), 1, "BEARING", 0.0, 10.0), track.region)

        self.assertEqual(track.local_measure_count, 2)

    def test_exhausted_local_budget_enters_optical_mode_and_returns_clear(self):
        track = record_measurement(None, Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0), initial_region(20.0, 64))
        track.local_measure_count = 12
        config = Config(max_local_measurements=12)

        action = next_local_action(track, RobotState(), config)

        self.assertEqual(track.local_mode, LocalMode.OPTICAL)
        self.assertEqual(action.kind, "CLEAR")

    def test_none_does_not_make_found_channel_absent(self):
        track = record_measurement(None, Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0), initial_region(1800.0, 64))
        record_measurement(track, Measurement((100.0, 100.0), 1, "NONE", None, 10.0), track.region)

        self.assertNotEqual(track.status, ChannelStatus.ABSENT)

    def test_optical_queue_does_not_skip_a_point_that_was_measured(self):
        track = record_measurement(None, Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0), initial_region(20.0, 64))
        track.local_measure_count = 12
        config = Config(max_local_measurements=12)
        first = next_local_action(track, RobotState(), config)
        track.measured_points.add(first.point)

        second = next_local_action(track, RobotState(), config)

        self.assertEqual(second.kind, "CLEAR")
        self.assertEqual(second.point, first.point)

    def test_optical_queue_starts_from_the_nearest_point_to_robot(self):
        track = record_measurement(None, Measurement((0.0, 0.0), 1, "BEARING", 0.0, 5.0), initial_region(20.0, 64))
        track.local_measure_count = 12
        config = Config(max_local_measurements=12)

        action = next_local_action(track, RobotState((100.0, 100.0), 1), config)

        distances = [((point[0] - 100.0) ** 2 + (point[1] - 100.0) ** 2, point) for point in track.optical_points]
        self.assertEqual(action.point, min(distances)[1])


if __name__ == "__main__":
    unittest.main()
