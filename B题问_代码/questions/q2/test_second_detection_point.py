import unittest

from questions.q2.second_detection_point import (
    candidate_grid,
    fim_loss,
    robust_receive_radius,
    robust_receive_ratio,
    sample_first_feasible_region,
    select_second_detection_point,
    worst_case_diameter,
)


class SecondDetectionPointTests(unittest.TestCase):
    def setUp(self):
        self.particles = sample_first_feasible_region(
            (0.0, 0.0), 0.0, angle_count=9, range_count=5, seed=7
        )

    def test_sampling_respects_first_measurement_constraints(self):
        for particle in self.particles:
            self.assertGreater(particle.first_range, 5.0)
            self.assertLessEqual(particle.first_range, 1500.0)
            self.assertLessEqual((particle.point[0] ** 2 + particle.point[1] ** 2) ** 0.5, 1800.0 + 1e-8)

    def test_first_success_increases_radius_lower_bound(self):
        particle = self.particles[-1]
        self.assertEqual(
            robust_receive_radius(particle), max(1000.0, particle.first_range)
        )

    def test_robust_receive_ratio_is_bounded(self):
        ratio = robust_receive_ratio((0.0, 0.0), self.particles)
        self.assertGreaterEqual(ratio, 0.0)
        self.assertLessEqual(ratio, 1.0)

    def test_fim_is_better_for_nonparallel_geometry(self):
        target = (1000.0, 0.0)
        parallel = fim_loss((0.0, 0.0), (-1000.0, 0.0), target)
        side = fim_loss((0.0, 0.0), (1000.0, 1000.0), target)
        self.assertGreater(parallel, side)

    def test_selection_returns_feasible_point(self):
        result = select_second_detection_point(
            (0.0, 0.0), 0.0,
            particles=self.particles,
            candidates=candidate_grid(radius=1800.0, step=300.0),
            receive_threshold=0.5,
            top_k=4,
        )
        self.assertEqual(result["status"], "OK")
        self.assertIn(result["best_point"], result["candidate_region"])
        self.assertGreaterEqual(result["best"]["receive_ratio"], 0.5)
        self.assertGreater(result["best"]["worst_diameter"], 0.0)

    def test_worst_case_diameter_is_finite_for_side_point(self):
        diameter = worst_case_diameter(
            (0.0, 0.0), 0.0, (0.0, 1000.0), self.particles
        )
        self.assertTrue(diameter < float("inf"))

    def test_outside_first_station_samples_only_inside_target_disk(self):
        particles = sample_first_feasible_region((-2500.0, 0.0), 0.0)
        self.assertTrue(all(p.point[0] ** 2 + p.point[1] ** 2 <= 1800.0 ** 2 + 1e-8 for p in particles))

    def test_selection_rejects_unbounded_repeated_station_geometry(self):
        particles = sample_first_feasible_region((0.0, 0.0), 0.0, angle_count=3, range_count=3)
        with self.assertRaises(ValueError):
            select_second_detection_point((0.0, 0.0), 0.0, particles=particles, candidates=[(0.0, 0.0)])

    def test_receive_screen_includes_the_near_range_boundary(self):
        particles = sample_first_feasible_region((0.0, 0.0), 0.0)
        self.assertLess(robust_receive_ratio((1100.0, 0.0), particles), 1.0)


if __name__ == "__main__":
    unittest.main()
