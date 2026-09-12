"""路线C独立的无第三方依赖环境核心。

这里先固定 reset/step/action_masks 的执行契约，后续 Gymnasium 适配器和PPO只依赖
这个契约。路线C不调用 route_b 的策略或执行器。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from questions.q3.shared.candidates import Candidate, build_candidates
from questions.q3.shared.config import Rules
from questions.q3.shared.coverage import BeliefTracker
from questions.q3.shared.local_search import is_clearable, next_upper_bound
from questions.q3.shared.models import ActionSpec, RobotState
from questions.q3.shared.scenario import Scenario, generate_scenario
from questions.q3.shared.simulator import LocalSimulator
from questions.q3.method_c.framework_v2.framework_v2 import build_framework_candidates


@dataclass(frozen=True)
class RouteCConfig:
    max_steps: int = 500
    max_virtual_time_s: float = 100.0 * 3600.0
    reward_time_scale_s: float = 100.0
    target_count: int | None = None
    profile: str = "uniform"
    discovery_reward: float = 2.0
    clear_reward: float = 20.0
    repeated_scan_penalty: float = 0.5
    invalid_action_penalty: float = 10.0
    defer_localization_until_discovery_complete: bool = False
    nearest_scan_point: bool = True
    framework_v2: bool = False


@dataclass(frozen=True)
class EpisodeReport:
    seed: int
    target_count: int
    cleared_count: int
    terminated: bool
    truncated: bool
    termination_reason: str
    virtual_time_s: float
    move_distance_m: float
    detect_count: int
    switch_count: int
    decision_steps: int


class RouteCEnv:
    """路线C的环境核心，公开观察不包含Scenario.sources。"""

    def __init__(self, rules: Rules | None = None, config: RouteCConfig | None = None) -> None:
        self.rules = rules or Rules()
        self.config = config or RouteCConfig()
        self._seed = 0
        self._next_seed = 0
        self.scenario: Scenario | None = None
        self.simulator: LocalSimulator | None = None
        self.belief: BeliefTracker | None = None
        self._candidates: tuple[Candidate, ...] = ()
        self._candidate_version = 0
        self._steps = 0
        self._done = True
        self._reason = "not_reset"

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        del options
        if seed is not None:
            self._seed = int(seed)
            self._next_seed = self._seed + 1
        else:
            self._seed = self._next_seed
            self._next_seed += 1
        self.scenario = generate_scenario(self._seed, self.rules, self.config.target_count, self.config.profile)
        self.simulator = LocalSimulator(self.scenario, self.rules)
        self.belief = BeliefTracker()
        self._steps = 0
        self._done = False
        self._reason = "running"
        self._refresh_candidates()
        return self._observation(), {"seed": self._seed, "candidate_version": self._candidate_version}

    def action_masks(self) -> tuple[bool, ...]:
        return tuple(candidate.valid for candidate in self._candidates)

    def candidates(self) -> tuple[Candidate, ...]:
        return self._candidates

    def step(self, action: int) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self._done:
            raise RuntimeError("当前episode已经结束，请先reset")
        if not 0 <= int(action) < len(self._candidates):
            raise IndexError("action索引必须位于0到11")
        candidate = self._candidates[int(action)]
        if not candidate.valid or candidate.action is None:
            self._done = True
            self._reason = "invalid_action"
            return self._observation(), -self.config.invalid_action_penalty, True, False, {"termination_reason": self._reason}
        assert self.simulator is not None and self.belief is not None
        before = self.simulator.virtual_time_s
        before_unknown = sum(track.status == "UNKNOWN" for track in self.belief.tracks.values())
        before_cleared = self.belief.cleared_count
        before_coverage = sum(len(track.coverage_checked) for track in self.belief.tracks.values())
        self._execute(candidate.action)
        self._steps += 1
        delta_time = self.simulator.virtual_time_s - before
        discovered_count = before_unknown - sum(track.status == "UNKNOWN" for track in self.belief.tracks.values())
        cleared_delta = self.belief.cleared_count - before_cleared
        coverage_delta = sum(len(track.coverage_checked) for track in self.belief.tracks.values()) - before_coverage
        terminated = self.belief.can_finish()
        truncated = self._steps >= self.config.max_steps or self.simulator.virtual_time_s >= self.config.max_virtual_time_s
        if terminated:
            self._done = True
            self._reason = "completed"
        elif truncated:
            self._done = True
            self._reason = "step_limit" if self._steps >= self.config.max_steps else "virtual_time_limit"
        else:
            self._refresh_candidates()
        repeated_scan = int(candidate.action.kind == "SCAN" and coverage_delta == 0)
        reward = (
            -delta_time / self.config.reward_time_scale_s
            + self.config.discovery_reward * discovered_count
            + self.config.clear_reward * cleared_delta
            - self.config.repeated_scan_penalty * repeated_scan
        )
        info = {
            "action_id": candidate.action.action_id,
            "action_kind": candidate.action.kind,
            "delta_virtual_time_s": delta_time,
            "newly_cleared": self.belief.cleared_count,
            "discovered_count": discovered_count,
            "cleared_delta": cleared_delta,
            "repeated_scan": repeated_scan,
            "termination_reason": self._reason if self._done else None,
            "candidate_version": self._candidate_version,
        }
        return self._observation(), reward, terminated, truncated, info

    def report(self) -> EpisodeReport:
        assert self.simulator is not None and self.belief is not None
        return EpisodeReport(
            seed=self._seed,
            target_count=len(self.scenario.sources) if self.scenario is not None else 0,
            cleared_count=self.belief.cleared_count,
            terminated=self._done and self._reason == "completed",
            truncated=self._done and self._reason in {"step_limit", "virtual_time_limit"},
            termination_reason=self._reason,
            virtual_time_s=self.simulator.virtual_time_s,
            move_distance_m=self.simulator.move_distance_m,
            detect_count=self.simulator.detect_count,
            switch_count=self.simulator.switch_count,
            decision_steps=self._steps,
        )

    def _refresh_candidates(self) -> None:
        assert self.simulator is not None and self.belief is not None
        robot = RobotState(self.simulator.position, self.simulator.current_channel)
        if self.config.framework_v2:
            self._candidates = tuple(build_framework_candidates(self.belief, robot, self.rules))
        else:
            self._candidates = tuple(build_candidates(
                self.belief,
                robot,
                self.rules,
                defer_localization_until_discovery_complete=self.config.defer_localization_until_discovery_complete,
                nearest_scan_point=self.config.nearest_scan_point,
            ))
        self._candidate_version += 1

    def _execute(self, action: ActionSpec) -> None:
        assert self.simulator is not None and self.belief is not None
        if action.kind == "CLEAR":
            self.belief.record_clear(self.simulator.clear_at(action.point, action.channels[0]))
            return
        for channel in action.channels:
            geometric_localize = action.kind == "LOCALIZE" and action.action_id.startswith("geo-localize-")
            if action.kind == "LOCALIZE" and not geometric_localize:
                track = self.belief.tracks[channel]
                track.distance_upper_bound_m = next_upper_bound(track.distance_upper_bound_m or 1500.0)
            measurement = self.simulator.detect_at(action.point, channel)
            self.belief.observe(measurement, action.coverage_id if action.kind == "SCAN" else None)
            if measurement.signal == "NEAR":
                self.belief.record_clear(self.simulator.clear_at(measurement.point, channel))
                return
            if action.kind == "LOCALIZE" and not geometric_localize and is_clearable(self.belief.tracks[channel].distance_upper_bound_m or 1500.0):
                self.belief.record_clear(self.simulator.clear_at(action.point, channel))
                return

    def _observation(self) -> dict[str, Any]:
        assert self.simulator is not None and self.belief is not None
        tracks = {
            channel: {
                "status": track.status,
                "last_point": track.last_point,
                "distance_upper_bound_m": track.distance_upper_bound_m,
                "region_status": track.region_status,
                "region_center": track.region_center,
                "region_radius_m": track.region_radius_m,
                "region_area_m2": track.region_area_m2,
                "coverage_checked": tuple(sorted(track.coverage_checked)),
                "bearing_count": len(track.bearings),
            }
            for channel, track in self.belief.tracks.items()
        }
        return {
            "position": self.simulator.position,
            "current_channel": self.simulator.current_channel,
            "virtual_time_s": self.simulator.virtual_time_s,
            "step_count": self._steps,
            "tracks": tracks,
            "candidates": self._candidates,
            "action_masks": self.action_masks(),
            "candidate_version": self._candidate_version,
        }
