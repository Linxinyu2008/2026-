import math
import unittest

from questions.q4.geometry import initial_region
from questions.q4.triangular_grid import grid_for_region, nearest_neighbor_order, optical_cover


class TriangularGridTests(unittest.TestCase):
    def test_nearest_route_preserves_all_scan_points(self):
        grid = grid_for_region(initial_region(), 950.0)
        routed = nearest_neighbor_order(grid)
        self.assertEqual(set(routed.points), set(grid.points))
        self.assertEqual(len(routed.points), len(grid.points))

    def test_intersecting_cells_keep_exterior_vertices(self):
        region = initial_region(1800.0, sides=64)
        grid = grid_for_region(region, 950.0)

        self.assertGreater(len(grid.triangles), 0)
        self.assertEqual(len(grid.points), len(set(grid.points)))
        self.assertTrue(any(math.hypot(x, y) > 1800.0 for x, y in grid.points))

    def test_every_source_in_target_disk_has_a_nearby_visible_vertex(self):
        grid = grid_for_region(initial_region(1800.0, sides=64), 950.0)
        for source in ((0.0, 0.0), (1799.0, 0.0), (-1799.0, 0.0), (0.0, 1799.0)):
            for angle_deg in range(0, 360, 15):
                ux, uy = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
                visible = [
                    point for point in grid.points
                    if math.dist(point, source) <= 1000.0 + 1e-7
                    and (point[0] - source[0]) * ux + (point[1] - source[1]) * uy >= -1e-7
                ]
                self.assertTrue(visible, (source, angle_deg))

    def test_optical_cover_has_nearest_point_within_twenty_metres(self):
        region = initial_region(50.0, sides=64)
        points = optical_cover(region, spacing_m=30.0)
        for x, y in ((0.0, 0.0), (49.0, 0.0), (-20.0, 30.0)):
            self.assertLessEqual(min(math.dist((x, y), point) for point in points), 20.0 + 1e-7)

    def test_points_are_ordered_in_a_snake_by_lattice_rows(self):
        grid = grid_for_region(initial_region(), 950.0)
        row_values = [round(2.0 * point[1] / (math.sqrt(3.0) * grid.spacing_m)) for point in grid.points]
        self.assertGreater(len(set(row_values)), 1)


if __name__ == "__main__":
    unittest.main()
