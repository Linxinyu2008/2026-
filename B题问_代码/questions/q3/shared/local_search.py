"""全向源的确定性局部收缩兜底。"""

from __future__ import annotations

from math import cos, pi, sin, sqrt

from .config import Rules
from .models import Point


RHO = sqrt(1.25 - cos(pi / 180.0))


def next_half_distance_point(point: Point, bearing_deg: float, upper_bound_m: float) -> Point:
    if upper_bound_m <= 0.0:
        raise ValueError("距离上界必须为正")
    angle = bearing_deg * pi / 180.0
    step = upper_bound_m / 2.0
    return point[0] + step * cos(angle), point[1] + step * sin(angle)


def next_upper_bound(upper_bound_m: float) -> float:
    if upper_bound_m <= 0.0:
        raise ValueError("距离上界必须为正")
    return RHO * upper_bound_m


def is_clearable(upper_bound_m: float, rules: Rules = Rules()) -> bool:
    return upper_bound_m + rules.numeric_margin_m <= rules.clear_distance_m
