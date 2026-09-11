import unittest

from q4_directional.config import Config
from q4_directional.controller import Controller
from q4_directional.geometry import initial_region
from q4_directional.models import ChannelStatus
from q4_directional.simulator import DirectionalSimulator
from q4_directional.scenario import Scenario
from q4_directional.triangular_grid import grid_for_region


class ControllerTests(unittest.TestCase):
    def test_controller_can_clear_a_source_and_mark_empty_channels_only_after_full_scan(self):
        backend = DirectionalSimulator(Scenario.single(1, (0.0, 0.0), 1000.0, 180.0))
        config = Config(global_spacing_m=1000.0)
        controller = Controller(backend, config, grid_for_region(initial_region(), 1000.0))

        for _ in range(5000):
            action = controller.next_action()
            if action is None:
                break
            result = backend.measure(action.point, action.channel) if action.kind == "MEASURE" else backend.clear(action.point, action.channel)
            controller.accept(action, result)
        else:
            self.fail("controller did not terminate")

        self.assertEqual(controller.statuses[1], ChannelStatus.CLEARED)
        self.assertEqual(controller.statuses[2], ChannelStatus.ABSENT)
        self.assertTrue(controller.finished)

    def test_global_scan_defers_tracking_and_skips_already_found_channels(self):
        backend = DirectionalSimulator(Scenario.single(1, (0.0, 0.0), 1000.0, 0.0))
        config = Config(global_spacing_m=1000.0)
        controller = Controller(backend, config, grid_for_region(initial_region(), 1000.0))

        first = controller.next_action()
        result = backend.measure(first.point, first.channel)
        controller.accept(first, result)
        action = controller.next_action()

        self.assertEqual(action.reason, "global_scan")
        self.assertNotEqual(action.channel, 1)


if __name__ == "__main__":
    unittest.main()
