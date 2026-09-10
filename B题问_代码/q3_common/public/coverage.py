"""七点发现覆盖和20频道公开状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, pi, sin

from .models import ClearResult, Measurement
from .geometry import region_summary


def coverage_points() -> tuple[tuple[float, float], ...]:
    return ((0.0, 0.0),) + tuple(
        (1500.0 * cos(k * pi / 3.0), 1500.0 * sin(k * pi / 3.0)) for k in range(6)
    )


@dataclass
class ChannelTrack:
    status: str = "UNKNOWN"
    bearings: list[Measurement] = field(default_factory=list)
    coverage_checked: set[int] = field(default_factory=set)
    last_point: tuple[float, float] | None = None
    distance_upper_bound_m: float | None = None
    region_status: str = "UNBOUNDED_REGION"
    region_center: tuple[float, float] | None = None
    region_radius_m: float | None = None
    region_area_m2: float | None = None


class BeliefTracker:
    def __init__(self) -> None:
        self.tracks = {channel: ChannelTrack() for channel in range(1, 21)}

    def observe(self, measurement: Measurement, coverage_id: int | None = None) -> None:
        track = self.tracks[measurement.channel]
        if coverage_id is not None and measurement.signal == "NONE":
            track.coverage_checked.add(coverage_id)
            if len(track.coverage_checked) == 7 and track.status == "UNKNOWN":
                track.status = "ABSENT"
        if measurement.signal == "BEARING":
            track.status = "TRACKING"
            track.bearings.append(measurement)
            track.last_point = measurement.point
            if track.distance_upper_bound_m is None:
                track.distance_upper_bound_m = 1500.0
            summary = region_summary(track.bearings)
            track.region_status = summary["status"]
            track.region_center = summary["center"]
            track.region_radius_m = summary["radius_m"]
            track.region_area_m2 = summary["area_m2"]
        elif measurement.signal == "NEAR" and track.status != "CLEARED":
            track.status = "CLEARABLE"
            track.last_point = measurement.point

    def record_clear(self, result: ClearResult) -> None:
        if result.success:
            self.tracks[result.channel].status = "CLEARED"

    def can_finish(self) -> bool:
        return all(track.status in {"CLEARED", "ABSENT"} for track in self.tracks.values()) or self.cleared_count >= 16

    @property
    def cleared_count(self) -> int:
        return sum(track.status == "CLEARED" for track in self.tracks.values())
