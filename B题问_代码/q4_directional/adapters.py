"""本地和官方协议后端的统一适配层。

OfficialBackend只转换已知附件协议字段，不在异常时伪造NONE或清除失败。
"""

from __future__ import annotations

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

    def measure(self, point: Point, channel: int) -> Measurement:
        response = self.client.measure(point[0], point[1], channel)
        mapping = {"no_signal": "NONE", "near": "NEAR", "direction": "BEARING"}
        signal = mapping.get(str(response.get("measure_result")))
        if signal is None:
            raise ValueError(f"未知measure_result: {response}")
        bearing = response.get("svd_deg") if signal == "BEARING" else None
        self.position = point
        self.current_channel = channel
        self.virtual_time_s = float(response["virtual_time_s"])
        return Measurement(point, channel, signal, None if bearing is None else float(bearing), self.virtual_time_s)

    def clear(self, point: Point, channel: int) -> ClearResult:
        response = self.client.clear(point[0], point[1], channel)
        self.position = point
        self.virtual_time_s = float(response["virtual_time_s"])
        return ClearResult(point, channel, response.get("clear_result") == "success", self.virtual_time_s)
