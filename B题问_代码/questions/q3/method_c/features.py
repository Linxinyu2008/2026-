"""路线C首版757维公开观察编码。

编码器只读取 RouteCEnv 返回的公开观察，不读取 Scenario 或目标真值。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Any


@dataclass(frozen=True)
class FeatureSchema:
    version: str = "route_c_features_v1"
    dimension: int = 757
    target_radius_m: float = 1800.0
    max_virtual_time_s: float = 360000.0
    max_action_time_s: float = 1000.0


def _one_hot(index: int | None, size: int) -> list[float]:
    values = [0.0] * size
    if index is not None and 0 <= index < size:
        values[index] = 1.0
    return values


def _kind_index(kind: str | None) -> int | None:
    return {"SCAN": 0, "LOCALIZE": 1, "CLEAR": 2}.get(kind)


def encode_observation(observation: dict[str, Any], schema: FeatureSchema = FeatureSchema()) -> list[float]:
    """把公开观察编码为固定顺序的757维Python float列表。"""
    values: list[float] = []
    position = observation["position"]
    values.extend((float(position[0]) / schema.target_radius_m, float(position[1]) / schema.target_radius_m))
    current_channel = int(observation["current_channel"])
    values.extend(_one_hot(current_channel - 1, 20))
    values.append(float(observation["virtual_time_s"]) / schema.max_virtual_time_s)
    values.append(1.0)  # 本地训练没有真实程序时钟，固定为“预算充足”
    values.append(min(1.0, float(observation["step_count"]) / 500.0))
    if len(values) != 25:
        raise AssertionError("全局特征应为25维")

    tracks = observation["tracks"]
    status_index = {"UNKNOWN": 0, "TRACKING": 1, "CLEARABLE": 2, "CLEARED": 3, "ABSENT": 4}
    for channel in range(1, 21):
        track = tracks[channel]
        values.extend(_one_hot(status_index.get(track["status"]), 5))
        point = track.get("region_center")
        if point is None:
            values.extend((0.0, 0.0))
            has_estimate = 0.0
        else:
            values.extend((float(point[0]) / schema.target_radius_m, float(point[1]) / schema.target_radius_m))
            has_estimate = float(track.get("region_status") == "OK")
        upper = track["distance_upper_bound_m"]
        values.append(0.0 if upper is None else min(2.0, float(upper) / 1500.0))
        area = track.get("region_area_m2")
        values.append(0.0 if area is None else min(1.0, float(area) / (3.141592653589793 * schema.target_radius_m ** 2)))
        values.append(has_estimate)
        checked = tuple(track["coverage_checked"])
        values.append(1.0 - len(checked) / 7.0)
        values.extend(float(index in checked) for index in range(7))
    if len(values) != 385:
        raise AssertionError("频道特征应为20*18=360维并与全局25维合计385维")

    candidates = observation["candidates"]
    if len(candidates) != 12:
        raise ValueError("候选数量必须为12")
    for candidate in candidates:
        action = candidate.action
        if action is None:
            values.extend([0.0] * 31)
            continue
        robot = position
        values.extend(((action.point[0] - robot[0]) / schema.target_radius_m, (action.point[1] - robot[1]) / schema.target_radius_m))
        values.append(min(10.0, hypot(action.point[0] - robot[0], action.point[1] - robot[1]) / schema.target_radius_m))
        values.append(min(10.0, float(candidate.estimated_time_s) / schema.max_action_time_s))
        values.extend(_one_hot(_kind_index(action.kind), 3))
        channel_bits = [0.0] * 20
        for channel in action.channels:
            if 1 <= channel <= 20:
                channel_bits[channel - 1] = 1.0
        values.extend(channel_bits)
        values.append(float(candidate.search_gain) / 20.0)
        values.append(float(candidate.localization_gain) / 1500.0)
        values.append(float(candidate.guaranteed_clear))
        values.append(float(candidate.valid))
    if len(values) != schema.dimension:
        raise AssertionError(f"特征维度错误：{len(values)} != {schema.dimension}")
    if not all(isfinite(value) for value in values):
        raise ValueError("特征中出现非有限数")
    return values
