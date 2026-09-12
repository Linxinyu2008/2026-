"""本地模拟器：实现题目观测、清除和虚拟计时规则。"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin

from .config import Rules
from .models import ClearResult, Measurement, Point
from .scenario import Scenario


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _valid_point(point: Point) -> bool:
    return len(point) == 2 and all(float(value) == float(value) for value in point) and all(abs(float(value)) <= 2_000_000.0 for value in point)


@dataclass
class DirectionalSimulator:
    scenario: Scenario
    rules: Rules = Rules()

    def __post_init__(self) -> None:
        self.position: Point = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.cleared_channels: set[int] = set()
        self.move_distance_m = 0.0
        self.measure_count = 0
        self.switch_count = 0
        self.clear_success_count = 0
        self.clear_failure_count = 0

    def _move_to(self, point: Point) -> None:
        if not _valid_point(point):
            raise ValueError("点坐标必须是有限数值且分量绝对值不超过2000000米")
        distance = _distance(self.position, point)
        self.position = point
        self.move_distance_m += distance
        self.virtual_time_s += distance / self.rules.move_speed_mps

    def _switch_to(self, channel: int) -> None:
        if not 1 <= channel <= 20:
            raise ValueError("频道必须位于1到20")
        if channel != self.current_channel:
            self.current_channel = channel
            self.switch_count += 1
            self.virtual_time_s += self.rules.switch_s

    def measure(self, point: Point, channel: int) -> Measurement:
        self._move_to(point)
        self._switch_to(channel)
        self.measure_count += 1
        self.virtual_time_s += self.rules.measure_s
        source = self.scenario.source_for(channel)
        signal = "NONE"
        bearing: float | None = None
        if source is not None and channel not in self.cleared_channels:
            distance = _distance(point, source.point)
            if source.orientation_deg is None:
                visible = True
            else:
                direction = radians(source.orientation_deg)
                dot = (point[0] - source.point[0]) * cos(direction) + (point[1] - source.point[1]) * sin(direction)
                visible = dot >= -self.rules.numeric_margin_m
            if visible and distance <= self.rules.near_distance_m + self.rules.numeric_margin_m:
                signal = "NEAR"
            elif visible and distance <= source.reception_radius_m + self.rules.numeric_margin_m:
                signal = "BEARING"
                true_bearing = degrees(atan2(source.point[1] - point[1], source.point[0] - point[0])) % 360.0
                bearing = (true_bearing + self.scenario.error_deg(point, channel)) % 360.0
        return Measurement(point, channel, signal, bearing, self.virtual_time_s)

    def clear(self, point: Point, channel: int) -> ClearResult:
        self._move_to(point)
        if not 1 <= channel <= 20:
            raise ValueError("频道必须位于1到20")
        source = self.scenario.source_for(channel)
        success = source is not None and channel not in self.cleared_channels and _distance(point, source.point) <= self.rules.clear_distance_m + self.rules.numeric_margin_m
        if success:
            self.cleared_channels.add(channel)
            self.clear_success_count += 1
            self.virtual_time_s += self.rules.clear_success_s
        else:
            self.clear_failure_count += 1
            self.virtual_time_s += self.rules.clear_failure_s
        return ClearResult(point, channel, success, self.virtual_time_s)
