"""Geometry-first route framework built only from public measurements."""

from __future__ import annotations

from functools import lru_cache
from math import cos, hypot, isfinite, pi, sin
from typing import Any

from q3_common.public.candidates import Candidate, estimate_time
from q3_common.public.config import Rules
from q3_common.public.coverage import BeliefTracker, ChannelTrack
from q3_common.public.local_search import next_half_distance_point
from q3_common.public.models import ActionSpec, Point, RobotState


CERTIFICATION_MARGIN_M = 0.1
FRAMEWORK_COVERAGE_RADIUS_M = 1130.0
MAX_TARGET_COUNT = 16


@lru_cache(maxsize=1)
def framework_coverage_points() -> tuple[Point, ...]:
    return ((0.0, 0.0),) + tuple(
        (
            FRAMEWORK_COVERAGE_RADIUS_M * cos(index * pi / 3.0),
            FRAMEWORK_COVERAGE_RADIUS_M * sin(index * pi / 3.0),
        )
        for index in range(6)
    )


def _invalid() -> Candidate:
    return Candidate(None, 0.0, 0.0, 0.0, False, False)


def _seen_at(track: ChannelTrack, point_id: int, point: Point) -> bool:
    if point_id in track.coverage_checked:
        return True
    return any(hypot(item.point[0] - point[0], item.point[1] - point[1]) <= 1e-7 for item in track.bearings)


def _region_values(track: ChannelTrack) -> tuple[Point, float] | None:
    if track.region_status != "OK" or track.region_center is None or track.region_radius_m is None:
        return None
    center = track.region_center
    radius = track.region_radius_m
    if not all(isfinite(float(value)) for value in (*center, radius)):
        return None
    return (float(center[0]), float(center[1])), float(radius)


def build_framework_candidates(
    belief: BeliefTracker,
    robot: RobotState,
    rules: Rules = Rules(),
) -> list[Candidate]:
    """Build 12 stable slots for global survey, region refinement, and clear."""
    scan_tasks = []
    discovered = sum(
        track.status in {"TRACKING", "CLEARABLE", "CLEARED"}
        for track in belief.tracks.values()
    )
    search_unknown = discovered < MAX_TARGET_COUNT
    for point_id, point in enumerate(framework_coverage_points()):
        channels = tuple(
            channel
            for channel, track in belief.tracks.items()
            if (
                (search_unknown and track.status == "UNKNOWN")
                or (track.status == "TRACKING" and track.region_status != "OK")
            )
            and not _seen_at(track, point_id, point)
        )
        if channels:
            distance = hypot(point[0] - robot.position[0], point[1] - robot.position[1])
            scan_tasks.append((distance, point_id, point, channels))
    scan_tasks.sort(key=lambda item: (item[0], item[1]))

    candidates: list[Candidate] = []
    if scan_tasks:
        _, point_id, point, channels = scan_tasks[0]
        chunk_size = max(1, (len(channels) + 3) // 4)
        for offset in range(4):
            selected = channels[offset * chunk_size : (offset + 1) * chunk_size]
            if not selected:
                candidates.append(_invalid())
                continue
            action = ActionSpec(f"survey-{offset}-{point_id}", "SCAN", point, selected, point_id)
            candidates.append(Candidate(action, estimate_time(action, robot, rules), float(len(selected)), 0.0, False, True))
    while len(candidates) < 4:
        candidates.append(_invalid())

    localize = []
    clear = []
    for channel, track in belief.tracks.items():
        if track.status == "CLEARABLE" and track.last_point is not None:
            clear.append((channel, track.last_point))
            continue
        if track.status != "TRACKING" or not track.bearings or track.last_point is None:
            continue
        region = _region_values(track)
        if region is not None:
            center, radius = region
            if radius <= rules.clear_distance_m - CERTIFICATION_MARGIN_M:
                clear.append((channel, center))
                continue
            if radius <= rules.min_reception_radius_m - CERTIFICATION_MARGIN_M:
                action = ActionSpec(f"geo-localize-{channel}", "LOCALIZE", center, (channel,))
                localize.append(Candidate(action, estimate_time(action, robot, rules), 0.0, radius, False, True))
                continue
        last = track.bearings[-1]
        assert last.bearing_deg is not None
        upper = track.distance_upper_bound_m or rules.max_reception_radius_m
        point = next_half_distance_point(last.point, last.bearing_deg, upper)
        action = ActionSpec(f"half-localize-{channel}", "LOCALIZE", point, (channel,))
        localize.append(Candidate(action, estimate_time(action, robot, rules), 0.0, upper, False, True))

    localize.sort(key=lambda item: (item.estimated_time_s, item.action.channels[0] if item.action else 0))
    candidates.extend(localize[:4])
    while len(candidates) < 8:
        candidates.append(_invalid())

    clear_candidates = []
    for channel, point in clear:
        action = ActionSpec(f"region-clear-{channel}", "CLEAR", point, (channel,))
        clear_candidates.append(Candidate(action, estimate_time(action, robot, rules), 0.0, 0.0, True, True))
    clear_candidates.sort(key=lambda item: (item.estimated_time_s, item.action.channels[0] if item.action else 0))
    candidates.extend(clear_candidates[:3])
    while len(candidates) < 11:
        candidates.append(_invalid())

    fallback = next(
        (
            item for item in candidates[:4]
            if item.valid and item.action is not None and item.action.kind == "SCAN"
        ),
        None,
    )
    candidates.append(fallback if fallback is not None else _invalid())
    return candidates


def choose_framework_v2(env: Any, rng: Any = None) -> int:
    del rng
    candidates = env.candidates()
    valid = [index for index, ok in enumerate(env.action_masks()) if ok]
    if not valid:
        raise RuntimeError("framework_v2没有可执行动作")
    scan = [index for index in valid if candidates[index].action and candidates[index].action.kind == "SCAN"]
    if scan:
        return max(scan, key=lambda index: len(candidates[index].action.channels) / (1.0 + candidates[index].estimated_time_s))
    post_survey = [
        index for index in valid
        if candidates[index].action and candidates[index].action.kind in {"CLEAR", "LOCALIZE"}
    ]
    if post_survey:
        return min(post_survey, key=lambda index: candidates[index].estimated_time_s)
    return valid[0]
