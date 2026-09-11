import unittest

from q4_directional.models import Point, Source
from q4_directional.scenario import Scenario
from q4_directional.simulator import DirectionalSimulator


class DirectionalSimulatorTests(unittest.TestCase):
    def test_directional_source_only_reports_inside_emission_half_plane(self):
        scenario = Scenario.single(
            channel=1,
            point=(0.0, 0.0),
            reception_radius_m=1000.0,
            orientation_deg=0.0,
        )
        simulator = DirectionalSimulator(scenario)

        self.assertEqual(simulator.measure((-100.0, 0.0), 1).signal, "NONE")
        self.assertEqual(simulator.measure((100.0, 0.0), 1).signal, "BEARING")

    def test_boundary_of_closed_half_plane_is_receivable(self):
        scenario = Scenario.single(1, (0.0, 0.0), 1000.0, 0.0)
        simulator = DirectionalSimulator(scenario)

        self.assertEqual(simulator.measure((0.0, 100.0), 1).signal, "BEARING")

    def test_clear_works_inside_twenty_metres_even_when_direction_is_backwards(self):
        scenario = Scenario.single(1, (0.0, 0.0), 1000.0, 0.0)
        simulator = DirectionalSimulator(scenario)

        result = simulator.clear((-10.0, 0.0), 1)

        self.assertTrue(result.success)
        self.assertIn(1, simulator.cleared_channels)

    def test_clear_does_not_change_receiver_channel_and_cost_is_accounted(self):
        scenario = Scenario(
            sources=(
                Source(1, (100.0, 0.0), 1000.0, None),
                Source(2, (200.0, 0.0), 1000.0, None),
            ),
            seed=7,
        )
        simulator = DirectionalSimulator(scenario)
        simulator.measure((0.0, 0.0), 2)
        before = simulator.virtual_time_s

        result = simulator.clear((100.0, 0.0), 1)

        self.assertTrue(result.success)
        self.assertEqual(simulator.current_channel, 2)
        self.assertAlmostEqual(simulator.virtual_time_s - before, 25.0)


if __name__ == "__main__":
    unittest.main()
