"""正三角网格生成和有限光学覆盖点。"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, sqrt

from .geometry import Region
from .models import Point


Triangle = tuple[Point, Point, Point]


@dataclass(frozen=True)
class Grid:
    spacing_m: float
    triangles: tuple[Triangle, ...]
    points: tuple[Point, ...]


def _point(m: int, n: int, spacing: float) -> Point:
    return (spacing * (m + n / 2.0), spacing * sqrt(3.0) * n / 2.0)


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point, tol: float = 1e-7) -> bool:
    return min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol and abs(_cross(a, b, p)) <= tol


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    values = (_cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b))
    if values[0] * values[1] < -1e-12 and values[2] * values[3] < -1e-12:
        return True
    return _on_segment(a, b, c) or _on_segment(a, b, d) or _on_segment(c, d, a) or _on_segment(c, d, b)


def _point_in_triangle(point: Point, triangle: Triangle, tol: float = 1e-7) -> bool:
    values = [_cross(triangle[i], triangle[(i + 1) % 3], point) for i in range(3)]
    return min(values) >= -tol or max(values) <= tol


def _intersects_region(triangle: Triangle, region: Region) -> bool:
    if any(region.contains(point) for point in triangle):
        return True
    if any(_point_in_triangle(point, triangle) for point in region.vertices):
        return True
    triangle_edges = [(triangle[i], triangle[(i + 1) % 3]) for i in range(3)]
    region_edges = [(region.vertices[i], region.vertices[(i + 1) % len(region.vertices)]) for i in range(len(region.vertices))]
    return any(_segments_intersect(a, b, c, d) for a, b in triangle_edges for c, d in region_edges)


def _build(region: Region, spacing_m: float) -> Grid:
    if spacing_m <= 0:
        raise ValueError("网格边长必须为正")
    if region.status != "OK" or not region.vertices:
        return Grid(spacing_m, (), ())
    min_x = min(point[0] for point in region.vertices)
    max_x = max(point[0] for point in region.vertices)
    min_y = min(point[1] for point in region.vertices)
    max_y = max(point[1] for point in region.vertices)
    n_min = int(min_y / (sqrt(3.0) * spacing_m / 2.0)) - 3
    n_max = int(max_y / (sqrt(3.0) * spacing_m / 2.0)) + 3
    triangles: list[Triangle] = []
    points: list[Point] = []
    seen: set[Point] = set()
    for n in range(n_min, n_max + 1):
        m_min = int(min_x / spacing_m - n / 2.0) - 3
        m_max = int(max_x / spacing_m - n / 2.0) + 3
        for m in range(m_min, m_max + 1):
            p00 = _point(m, n, spacing_m)
            p10 = _point(m + 1, n, spacing_m)
            p01 = _point(m, n + 1, spacing_m)
            p11 = _point(m + 1, n + 1, spacing_m)
            for triangle in ((p00, p10, p01), (p10, p11, p01)):
                if _intersects_region(triangle, region):
                    triangles.append(triangle)
                    for point in triangle:
                        if point not in seen:
                            seen.add(point)
                            points.append(point)
    def lattice_key(point: Point) -> tuple[int, float]:
        row = round(2.0 * point[1] / (sqrt(3.0) * spacing_m))
        column = point[0] / spacing_m - row / 2.0
        return row, column

    rows: dict[int, list[Point]] = {}
    for point in points:
        row, _ = lattice_key(point)
        rows.setdefault(row, []).append(point)
    ordered_points: list[Point] = []
    for row_index, row in enumerate(sorted(rows)):
        row_points = sorted(rows[row], key=lambda point: lattice_key(point)[1], reverse=row_index % 2 == 1)
        ordered_points.extend(row_points)
    return Grid(spacing_m, tuple(triangles), tuple(ordered_points))


def grid_for_region(region: Region, spacing_m: float) -> Grid:
    return _build(region, spacing_m)


def nearest_neighbor_order(grid: Grid, start: Point = (0.0, 0.0)) -> Grid:
    """保留全部三角网格点，只改变访问顺序以减少移动距离。

    全局扫描的覆盖集合不变，因此不会改变可证明的覆盖范围；从机器狗
    初始位置开始，每一步选择最近的未访问点，作为比逐行蛇形更短的确定性路线。
    """
    remaining = list(grid.points)
    ordered: list[Point] = []
    position = start
    while remaining:
        point = min(
            remaining,
            key=lambda candidate: (
                hypot(candidate[0] - position[0], candidate[1] - position[1]),
                candidate[1],
                candidate[0],
            ),
        )
        ordered.append(point)
        remaining.remove(point)
        position = point
    return Grid(grid.spacing_m, grid.triangles, tuple(ordered))


def two_opt_order(grid: Grid, start: Point = (0.0, 0.0), max_passes: int = 4) -> Grid:
    """在最近邻路线基础上做有限次 2-opt，保持点集不变并缩短开放路径。"""
    if max_passes < 0:
        raise ValueError("max_passes必须非负")
    route = list(nearest_neighbor_order(grid, start).points)

    def distance(a: Point, b: Point) -> float:
        return hypot(a[0] - b[0], a[1] - b[1])

    for _ in range(max_passes):
        improved = False
        for i in range(len(route) - 2):
            left = start if i == 0 else route[i - 1]
            a = route[i]
            for j in range(i + 1, len(route) - 1):
                b = route[j]
                right = route[j + 1]
                old = distance(left, a) + distance(b, right)
                new = distance(left, b) + distance(a, right)
                if new + 1e-9 < old:
                    route[i : j + 1] = reversed(route[i : j + 1])
                    improved = True
        if not improved:
            break
    return Grid(grid.spacing_m, grid.triangles, tuple(route))


def optical_cover(region: Region, spacing_m: float = 30.0) -> tuple[Point, ...]:
    """返回相交细网格的全部顶点，满足 h/sqrt(3) <= 20 米的覆盖构造。"""
    return _build(region, spacing_m).points
