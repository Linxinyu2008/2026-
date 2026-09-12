"""本地和官方协议后端的统一适配层。

OfficialBackend只转换已知附件协议字段，不在异常时伪造NONE或清除失败。
"""

from __future__ import annotations

from math import hypot
from typing import Any

from .models import ClearResult, Measurement, Point


class LocalBackend:
    def __init__(self, simulator: Any) -> None:
        self.simulator = simulator

    @property
    def position(self) -> Point:
        return self.simulator.position

    @property
    def current_channel(self) -> int:
        return self.simulator.current_channel

    @property
    def virtual_time_s(self) -> float:
        return float(self.simulator.virtual_time_s)

    @property
    def move_distance_m(self) -> float:
        return float(self.simulator.move_distance_m)

    @property
    def measure_count(self) -> int:
        return int(self.simulator.measure_count)

    @property
    def switch_count(self) -> int:
        return int(self.simulator.switch_count)

    @property
    def clear_count(self) -> int:
        return int(self.simulator.clear_success_count + self.simulator.clear_failure_count)

    @property
    def clear_success_count(self) -> int:
        return int(self.simulator.clear_success_count)

    @property
    def clear_failure_count(self) -> int:
        return int(self.simulator.clear_failure_count)

    def measure(self, point: Point, channel: int) -> Measurement:
        return self.simulator.measure(point, channel)

    def clear(self, point: Point, channel: int) -> ClearResult:
        return self.simulator.clear(point, channel)


class OfficialBackend:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.position: Point = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.command_count = 0
        self.measure_count = 0
        self.clear_count = 0
        self.switch_count = 0
        self.move_distance_m = 0.0
        self.clear_success_count = 0
        self.clear_failure_count = 0

    def _record_position(self, point: Point) -> None:
        self.move_distance_m += hypot(point[0] - self.position[0], point[1] - self.position[1])
        self.position = point

    def measure(self, point: Point, channel: int) -> Measurement:
        response = self.client.measure(point[0], point[1], channel)
        mapping = {"no_signal": "NONE", "near": "NEAR", "direction": "BEARING"}
        signal = mapping.get(str(response.get("measure_result")))
        if signal is None:
            raise ValueError(f"未知measure_result: {response}")
        bearing = response.get("svd_deg") if signal == "BEARING" else None
        if channel != self.current_channel:
            self.switch_count += 1
        self._record_position(point)
        self.current_channel = channel
        self.virtual_time_s = float(response["virtual_time_s"])
        self.command_count += 1
        self.measure_count += 1
        return Measurement(point, channel, signal, None if bearing is None else float(bearing), self.virtual_time_s)

    def clear(self, point: Point, channel: int) -> ClearResult:
        response = self.client.clear(point[0], point[1], channel)
        self._record_position(point)
        self.virtual_time_s = float(response["virtual_time_s"])
        self.command_count += 1
        self.clear_count += 1
        success = response.get("clear_result") == "success"
        if success:
            self.clear_success_count += 1
        else:
            self.clear_failure_count += 1
        return ClearResult(point, channel, success, self.virtual_time_s)
