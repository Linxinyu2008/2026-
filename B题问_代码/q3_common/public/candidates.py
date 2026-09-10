"""问题3统一候选动作生成与路线B评分所需的公开特征。"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .config import Rules
from .coverage import BeliefTracker, coverage_points
from .local_search import next_half_distance_point
from .models import ActionSpec, Point, RobotState


@dataclass(frozen=True)
class Candidate:
    action: ActionSpec | None
    estimated_time_s: float
    search_gain: float
    localization_gain: float
    guaranteed_clear: bool
    valid: bool


def estimate_time(action: ActionSpec, robot: RobotState, rules: Rules = Rules()) -> float:
    if not action.channels:
        raise ValueError("动作至少需要一个频道")
    if action.kind in {"LOCALIZE", "CLEAR"} and len(action.channels) != 1:
        raise ValueError("定位和清除动作必须只有一个频道")
    distance = hypot(action.point[0] - robot.position[0], action.point[1] - robot.position[1])
    switches = 0 if action.kind == "CLEAR" else sum(
        1 for previous, current in zip((robot.current_channel,) + action.channels, action.channels)
        if previous != current
    )
    seconds = distance / rules.move_speed_mps + switches * rules.channel_switch_s
    if action.kind in {"SCAN", "LOCALIZE"}:
        seconds += len(action.channels) * rules.detection_s
    else:
        seconds += rules.clear_operation_s
    return seconds


def _next_coverage_task(belief: BeliefTracker) -> tuple[int, Point, tuple[int, ...]] | None:
    points = coverage_points()
    for point_id, point in enumerate(points):
        channels = tuple(
            channel for channel in range(1, 21)
            if belief.tracks[channel].status == "UNKNOWN"
            and point_id not in belief.tracks[channel].coverage_checked
        )
        if channels:
            return point_id, point, channels
    return None


def build_candidates(
    belief: BeliefTracker,
    robot: RobotState,
    rules: Rules = Rules(),
    *,
    max_candidates: int = 12,
) -> list[Candidate]:
    """按固定槽位生成公开候选，不读取场景真值。

    槽位顺序为：4个SCAN、4个LOCALIZE、3个CLEAR、1个兜底SCAN。
    不足槽位用无效候选补齐，保证路线B和路线C动作索引一致。
    """
    if max_candidates != 12:
        raise ValueError("首版候选接口固定为12个槽位")
    candidates: list[Candidate] = []
    scan_task = _next_coverage_task(belief)
    if scan_task:
        point_id, point, channels = scan_task
        for offset in range(4):
            selected = channels[offset::4]
            if not selected:
                candidates.append(Candidate(None, 0.0, 0.0, 0.0, False, False))
                continue
            action = ActionSpec(f"scan-{offset}-{point[0]:.3f}-{point[1]:.3f}", "SCAN", point, selected, point_id)
            candidates.append(Candidate(action, estimate_time(action, robot, rules), float(len(selected)), 0.0, False, bool(selected)))
    while len(candidates) < 4:
        candidates.append(Candidate(None, 0.0, 0.0, 0.0, False, False))

    local_tracks = [
        (channel, track) for channel, track in belief.tracks.items()
        if track.status == "TRACKING" and track.bearings and track.last_point is not None and track.distance_upper_bound_m
    ]
    local_tracks.sort(key=lambda item: item[0])
    for channel, track in local_tracks[:4]:
        last = track.bearings[-1]
        assert last.bearing_deg is not None
        point = next_half_distance_point(last.point, last.bearing_deg, track.distance_upper_bound_m or 1500.0)
        action = ActionSpec(f"localize-{channel}-{point[0]:.3f}-{point[1]:.3f}", "LOCALIZE", point, (channel,))
        # 局部任务一旦开始，必须连续推进到清除或明确失败，不能被全局扫描收益打断。
        candidates.append(Candidate(action, estimate_time(action, robot, rules), 0.0, track.distance_upper_bound_m, False, True))
    while len(candidates) < 8:
        candidates.append(Candidate(None, 0.0, 0.0, 0.0, False, False))

    clear_tracks = [(channel, track) for channel, track in belief.tracks.items() if track.status == "CLEARABLE" and track.last_point is not None]
    clear_tracks.sort(key=lambda item: item[0])
    for channel, track in clear_tracks[:3]:
        point = track.last_point
        assert point is not None
        action = ActionSpec(f"clear-{channel}-{point[0]:.3f}-{point[1]:.3f}", "CLEAR", point, (channel,))
        candidates.append(Candidate(action, estimate_time(action, robot, rules), 0.0, 0.0, True, True))
    while len(candidates) < 11:
        candidates.append(Candidate(None, 0.0, 0.0, 0.0, False, False))

    fallback = scan_task
    if fallback:
        point_id, point, channels = fallback
        channels = channels[:1]
        action = ActionSpec(f"fallback-{point_id}-{point[0]:.3f}-{point[1]:.3f}", "SCAN", point, channels, point_id)
        candidates.append(Candidate(action, estimate_time(action, robot, rules), float(bool(channels)), 0.0, False, bool(channels)))
    else:
        candidates.append(Candidate(None, 0.0, 0.0, 0.0, False, False))
    return candidates


def score_candidate(
    candidate: Candidate,
    *,
    time_scale_s: float = 100.0,
    search_weight: float = 0.15,
    localization_weight: float = 2.0,
) -> float:
    if not candidate.valid or candidate.action is None:
        return float("-inf")
    gain = (
        search_weight * candidate.search_gain
        + localization_weight * candidate.localization_gain / 1500.0
        + (20.0 if candidate.guaranteed_clear else 0.0)
    )
    return gain / (1.0 + candidate.estimated_time_s / time_scale_s)
