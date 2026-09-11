"""问题4的保守凸多边形位置域。

圆约束使用外接正多边形，因此数值近似只会保留额外候选，不会排除真实源。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, radians, sin, hypot

from .models import Measurement, Point


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _clip_ge(vertices: list[Point], a: float, b: float, c: float, tol: float = 1e-9) -> list[Point]:
    if not vertices:
        return []
    result: list[Point] = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        fs = a * start[0] + b * start[1] - c
        fe = a * end[0] + b * end[1] - c
        inside_s = fs >= -tol
        inside_e = fe >= -tol
        if inside_s:
            result.append(start)
        if inside_s != inside_e:
            denominator = fs - fe
            if abs(denominator) > tol:
                ratio = fs / denominator
                result.append((start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1])))
    return _deduplicate(result)


def _clip_le(vertices: list[Point], a: float, b: float, c: float, tol: float = 1e-9) -> list[Point]:
    return _clip_ge(vertices, -a, -b, -c, tol)


def _deduplicate(vertices: list[Point], tol: float = 1e-8) -> list[Point]:
    result: list[Point] = []
    for point in vertices:
        if not result or _distance(point, result[-1]) > tol:
            result.append(point)
    if len(result) > 1 and _distance(result[0], result[-1]) <= tol:
        result.pop()
    return result


def _outer_disk(center: Point, radius: float, sides: int) -> list[Point]:
    # Vertices of the circumscribed regular polygon. The normal offset is R.
    return [
        (center[0] + radius / cos(pi / sides) * cos(2 * pi * k / sides),
         center[1] + radius / cos(pi / sides) * sin(2 * pi * k / sides))
        for k in range(sides)
    ]


@dataclass(frozen=True)
class Region:
    vertices: tuple[Point, ...]
    status: str = "OK"
    center: Point | None = None
    radius_m: float | None = None
    area_m2: float | None = None

    def contains(self, point: Point, tol: float = 1e-7) -> bool:
        if self.status != "OK" or not self.vertices:
            return False
        signs = []
        for a, b in zip(self.vertices, self.vertices[1:] + self.vertices[:1]):
            signs.append(_cross((b[0] - a[0], b[1] - a[1]), (point[0] - a[0], point[1] - a[1])))
        return min(signs) >= -tol or max(signs) <= tol

    @property
    def diameter_m(self) -> float:
        return max((_distance(a, b) for i, a in enumerate(self.vertices) for b in self.vertices[i + 1:]), default=0.0)


def _make_region(vertices: list[Point]) -> Region:
    vertices = _deduplicate(vertices)
    if not vertices:
        return Region((), status="INCONSISTENT")
    if len(vertices) == 1:
        center, radius = vertices[0], 0.0
    else:
        min_x = min(point[0] for point in vertices)
        max_x = max(point[0] for point in vertices)
        min_y = min(point[1] for point in vertices)
        max_y = max(point[1] for point in vertices)
        center = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
        radius = max(_distance(center, point) for point in vertices)
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(vertices, vertices[1:] + vertices[:1]))) / 2.0 if len(vertices) >= 3 else 0.0
    return Region(tuple(vertices), center=center, radius_m=radius, area_m2=area)


def initial_region(target_radius_m: float = 1800.0, sides: int = 256) -> Region:
    if target_radius_m <= 0 or sides < 8:
        raise ValueError("目标半径必须为正且外包多边形边数不少于8")
    return _make_region(_outer_disk((0.0, 0.0), target_radius_m, sides))


def update_region(region: Region, measurement: Measurement, angle_margin_deg: float = 1.005, max_range_m: float = 1500.0) -> Region:
    if region.status != "OK":
        return region
    vertices = list(region.vertices)
    x, y = measurement.point
    if measurement.signal == "NEAR":
        for k in range(64):
            angle = 2 * pi * k / 64
            nx, ny = cos(angle), sin(angle)
            vertices = _clip_le(vertices, nx, ny, nx * x + ny * y + 5.0 / cos(pi / 64))
    elif measurement.signal == "BEARING" and measurement.bearing_deg is not None:
        theta = radians(measurement.bearing_deg)
        left = (cos(theta - radians(angle_margin_deg)), sin(theta - radians(angle_margin_deg)))
        right = (cos(theta + radians(angle_margin_deg)), sin(theta + radians(angle_margin_deg)))
        vertices = _clip_ge(vertices, -left[1], left[0], -left[1] * x + left[0] * y)
        vertices = _clip_ge(vertices, right[1], -right[0], right[1] * x - right[0] * y)
        for k in range(128):
            angle = 2 * pi * k / 128
            nx, ny = cos(angle), sin(angle)
            vertices = _clip_le(vertices, nx, ny, nx * x + ny * y + max_range_m / cos(pi / 128))
    return _make_region(vertices)
