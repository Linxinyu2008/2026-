"""问题3本地二维模拟器：只模拟公开接口可观察到的行为。"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot

from .config import Rules
from .models import ClearResult, Measurement, Point
from .scenario import Scenario


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _validate_point(point: Point) -> None:
    if len(point) != 2 or not all(float(v) == float(v) for v in point):
        raise ValueError("点坐标必须是有限数值")
    if any(abs(float(v)) > 2_000_000.0 for v in point):
        raise ValueError("接口坐标分量绝对值不能超过2000000米")


@dataclass
class LocalSimulator:
    scenario: Scenario
    rules: Rules = Rules()

    def __post_init__(self) -> None:
        self.position: Point = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.cleared_channels: set[int] = set()
        self.move_distance_m = 0.0
        self.detect_count = 0
        self.switch_count = 0

    def _move_to(self, point: Point) -> None:
        _validate_point(point)
        distance = _distance(self.position, point)
        self.move_distance_m += distance
        self.virtual_time_s += distance / self.rules.move_speed_mps
        self.position = point

    def _switch_to(self, channel: int) -> None:
        if not 1 <= channel <= 20:
            raise ValueError("频道必须位于1到20")
        if channel != self.current_channel:
            self.virtual_time_s += self.rules.channel_switch_s
            self.switch_count += 1
            self.current_channel = channel

    def detect_at(self, point: Point, channel: int) -> Measurement:
        self._move_to(point)
        self._switch_to(channel)
        self.virtual_time_s += self.rules.detection_s
        self.detect_count += 1
        source = self.scenario.source_for(channel)
        if source is None or channel in self.cleared_channels:
            signal = "NONE"
            bearing = None
        else:
            distance = _distance(point, source.point)
            if distance > source.reception_radius_m:
                signal = "NONE"
                bearing = None
            elif distance <= self.rules.near_distance_m:
                signal = "NEAR"
                bearing = None
            else:
                true_bearing = degrees(atan2(source.point[1] - point[1], source.point[0] - point[0])) % 360.0
                bearing = (true_bearing + self.scenario.error_field.value(point, channel)) % 360.0
                signal = "BEARING"
        return Measurement(point, channel, signal, bearing, self.virtual_time_s)

    def clear_at(self, point: Point, channel: int) -> ClearResult:
        self._move_to(point)
        # 按题目接口规则，/clear 的 channel 只指定待清除目标，
        # 不改变测向机当前频道，也不产生频道切换耗时。
        if not 1 <= channel <= 20:
            raise ValueError("频道必须位于1到20")
        source = self.scenario.source_for(channel)
        success = source is not None and channel not in self.cleared_channels and _distance(point, source.point) <= self.rules.clear_distance_m + self.rules.numeric_margin_m
        self.virtual_time_s += self.rules.clear_operation_s if success else self.rules.optical_s
        if success:
            self.cleared_channels.add(channel)
        return ClearResult(point, channel, success, self.virtual_time_s)
