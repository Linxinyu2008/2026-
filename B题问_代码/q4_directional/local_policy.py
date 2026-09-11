"""已发现频道的快速定位、有限局部回退和光学清除队列。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from .config import Config
from .geometry import Region, update_region
from .models import Action, ChannelStatus, LocalMode, Measurement, Point, RobotState
from .triangular_grid import grid_for_region, optical_cover


@dataclass
class Track:
    channel: int
    region: Region
    status: ChannelStatus = ChannelStatus.FOUND
    local_mode: LocalMode = LocalMode.FAST
    local_measure_count: int = 0
    consecutive_none: int = 0
    no_progress_count: int = 0
    previous_radius_m: float | None = None
    measured_points: set[Point] = field(default_factory=set)
    optical_points: tuple[Point, ...] = ()
    optical_index: int = 0


def record_measurement(track: Track | None, measurement: Measurement, region: Region | None = None) -> Track:
    if track is None:
        if region is None:
            raise ValueError("首次记录必须提供初始位置域")
        track = Track(measurement.channel, update_region(region, measurement))
    track.measured_points.add(measurement.point)
    if measurement.signal == "NONE":
        track.consecutive_none += 1
        if track.local_mode == LocalMode.FAST and track.consecutive_none >= 2:
            track.local_mode = LocalMode.REACQUIRE
        return track
    track.consecutive_none = 0
    if measurement.signal == "BEARING":
        old_radius = track.region.radius_m
        track.region = update_region(track.region, measurement)
        track.local_measure_count += 1
        if old_radius is not None and track.region.radius_m is not None:
            if track.region.radius_m >= old_radius * 0.95:
                track.no_progress_count += 1
            else:
                track.no_progress_count = 0
        track.status = ChannelStatus.TRACKING
    elif measurement.signal == "NEAR":
        track.region = update_region(track.region, measurement)
        track.status = ChannelStatus.CLEARABLE
        track.local_mode = LocalMode.OPTICAL
    return track


def _enter_optical(track: Track, config: Config) -> None:
    if track.local_mode != LocalMode.OPTICAL:
        track.local_mode = LocalMode.OPTICAL
    if not track.optical_points:
        track.optical_points = optical_cover(track.region, config.optical_spacing_m)
        track.optical_index = 0


def next_local_action(track: Track, robot: RobotState, config: Config) -> Action:
    if track.region.status != "OK":
        raise RuntimeError("位置域无效，不能生成局部动作")
    if track.region.radius_m is not None and track.region.radius_m <= 20.0:
        _enter_optical(track, config)
    if track.local_measure_count >= config.max_local_measurements or track.no_progress_count >= config.no_progress_window:
        _enter_optical(track, config)
    if track.local_mode == LocalMode.OPTICAL:
        if track.optical_index >= len(track.optical_points):
            raise RuntimeError("光学覆盖点全部执行但仍未清除")
        if len(track.optical_points) - track.optical_index > 1:
            points = list(track.optical_points)
            best_index = min(
                range(track.optical_index, len(points)),
                key=lambda index: hypot(points[index][0] - robot.position[0], points[index][1] - robot.position[1]),
            )
            points[track.optical_index], points[best_index] = points[best_index], points[track.optical_index]
            track.optical_points = tuple(points)
        point = track.optical_points[track.optical_index]
        return Action("CLEAR", point, track.channel, "optical_cover", track.optical_index)
    diameter = max(track.region.diameter_m, 30.0)
    spacing = min(950.0, max(30.0, 0.4 * diameter))
    candidates = grid_for_region(track.region, spacing).points
    available = [point for point in candidates if point not in track.measured_points]
    if not available:
        _enter_optical(track, config)
        return next_local_action(track, robot, config)
    point = min(available, key=lambda candidate: hypot(candidate[0] - robot.position[0], candidate[1] - robot.position[1]))
    return Action("MEASURE", point, track.channel, "local_reacquire")
