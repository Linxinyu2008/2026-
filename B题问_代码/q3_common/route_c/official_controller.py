"""路线C官方模拟器控制器。

该模块把公开BeliefTracker、候选动作、PPO推理和附件HTTP客户端串起来。
未成功调用 /enter 时不会发送后续动作；异常时优先安全退出并记录原因。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from q3_common.public.candidates import Candidate, build_candidates
from q3_common.public.config import Rules
from q3_common.public.coverage import BeliefTracker
from q3_common.public.local_search import is_clearable, next_upper_bound
from q3_common.public.models import ClearResult, Measurement, RobotState
from q3_common.public.official_client import OfficialClientError, OfficialSimulatorClient
from q3_common.route_c.core import RouteCConfig
from q3_common.route_c.features import encode_observation
from q3_common.route_c.framework_v2 import build_framework_candidates, choose_framework_v2
from q3_common.route_c.hybrid import choose_hybrid


@dataclass(frozen=True)
class OfficialRunReport:
    requested_mode: str
    actual_mode: str
    fallback_used: bool
    fallback_reason: str | None
    completed: bool
    exit_called: bool
    termination_reason: str
    virtual_time_s: float
    command_count: int
    decision_steps: int
    cleared_count: int
    wall_time_s: float


class OfficialRouteCController:
    def __init__(
        self,
        client: OfficialSimulatorClient,
        *,
        rules: Rules | None = None,
        config: RouteCConfig | None = None,
        model_path: str | Path | None = None,
        mode: str = "ppo",
    ) -> None:
        if mode not in {"ppo", "fixed_scan", "hybrid", "framework_v2"}:
            raise ValueError("mode必须是ppo、fixed_scan、hybrid或framework_v2")
        self.client = client
        self.rules = rules or Rules()
        self.config = config or RouteCConfig()
        self.requested_mode = mode
        self.model = None
        self.model_error: str | None = None
        if mode == "ppo":
            try:
                if model_path is None:
                    raise ValueError("未提供PPO模型路径")
                from sb3_contrib import MaskablePPO

                self.model = MaskablePPO.load(str(model_path), device="cpu")
            except Exception as exc:
                self.model_error = f"PPO模型加载失败: {type(exc).__name__}: {exc}"

        self.belief = BeliefTracker()
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.command_count = 0
        self.decision_steps = 0
        self._hybrid_locked_channel: int | None = None

    def _candidates(self) -> tuple[Candidate, ...]:
        robot = RobotState(self.position, self.current_channel)
        if self.requested_mode == "framework_v2":
            return tuple(build_framework_candidates(self.belief, robot, self.rules))
        return tuple(build_candidates(
            self.belief,
            robot,
            self.rules,
            defer_localization_until_discovery_complete=self.config.defer_localization_until_discovery_complete,
            nearest_scan_point=self.config.nearest_scan_point,
        ))

    def _observation(self, candidates: tuple[Candidate, ...]) -> dict[str, Any]:
        tracks = {}
        for channel, track in self.belief.tracks.items():
            tracks[channel] = {
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
        return {
            "position": self.position,
            "current_channel": self.current_channel,
            "virtual_time_s": self.virtual_time_s,
            "step_count": self.decision_steps,
            "tracks": tracks,
            "candidates": candidates,
            "action_masks": tuple(item.valid for item in candidates),
            "candidate_version": self.command_count,
        }

    @staticmethod
    def _valid(candidates: tuple[Candidate, ...]) -> list[int]:
        valid = [index for index, item in enumerate(candidates) if item.valid]
        if not valid:
            raise OfficialClientError("公开状态没有合法候选动作")
        return valid

    def _fixed_action(self, candidates: tuple[Candidate, ...]) -> int:
        valid = self._valid(candidates)
        scans = [index for index in valid if candidates[index].action and candidates[index].action.kind == "SCAN"]
        return (scans or valid)[0]

    def _ppo_action(self, candidates: tuple[Candidate, ...]) -> int:
        if self.model is None:
            raise OfficialClientError(self.model_error or "PPO模型不可用")
        valid = self._valid(candidates)
        observation = self._observation(candidates)
        encoded = encode_observation(observation)
        action, _ = self.model.predict(encoded, action_masks=[item.valid for item in candidates], deterministic=True)
        action_id = int(action)
        if action_id not in valid:
            raise OfficialClientError(f"PPO输出非法动作: {action_id}")
        return action_id

    def _hybrid_action(self, candidates: tuple[Candidate, ...]) -> int:
        # Reuse the public candidate tuple while keeping the same policy in local and official runs.
        class CandidateView:
            def __init__(self, owner: "OfficialRouteCController", items: tuple[Candidate, ...]):
                self.owner = owner
                self.items = items

            def candidates(self):
                return self.items

            def action_masks(self):
                return [item.valid for item in self.items]

            @property
            def _hybrid_locked_channel(self):
                return self.owner._hybrid_locked_channel

            @_hybrid_locked_channel.setter
            def _hybrid_locked_channel(self, value):
                self.owner._hybrid_locked_channel = value

        return choose_hybrid(CandidateView(self, candidates))

    @staticmethod
    def _framework_action(candidates: tuple[Candidate, ...]) -> int:
        class CandidateView:
            def candidates(self):
                return candidates

            def action_masks(self):
                return [item.valid for item in candidates]

        return choose_framework_v2(CandidateView())

    @staticmethod
    def _measurement(point: tuple[float, float], channel: int, response: dict[str, Any]) -> Measurement:
        mapping = {"no_signal": "NONE", "near": "NEAR", "direction": "BEARING"}
        signal = mapping.get(str(response.get("measure_result")))
        if signal is None:
            raise OfficialClientError(f"未知measure_result: {response}")
        bearing = response.get("svd_deg") if signal == "BEARING" else None
        return Measurement(point, channel, signal, None if bearing is None else float(bearing), float(response["virtual_time_s"]))

    def _measure(self, point: tuple[float, float], channel: int, coverage_id: int | None) -> Measurement:
        response = self.client.measure(point[0], point[1], channel)
        self.command_count += 1
        self.position = point
        self.current_channel = channel
        self.virtual_time_s = float(response["virtual_time_s"])
        measurement = self._measurement(point, channel, response)
        self.belief.observe(measurement, coverage_id)
        return measurement

    def _clear(self, point: tuple[float, float], channel: int) -> ClearResult:
        response = self.client.clear(point[0], point[1], channel)
        self.command_count += 1
        self.position = point
        self.virtual_time_s = float(response["virtual_time_s"])
        result = ClearResult(point, channel, response.get("clear_result") == "success", self.virtual_time_s)
        self.belief.record_clear(result)
        return result

    def _execute(self, candidate: Candidate) -> None:
        assert candidate.action is not None
        self.decision_steps += 1
        action = candidate.action
        if action.kind == "CLEAR":
            self._clear(action.point, action.channels[0])
            return
        for channel in action.channels:
            geometric_localize = action.kind == "LOCALIZE" and action.action_id.startswith("geo-localize-")
            if action.kind == "LOCALIZE" and not geometric_localize:
                track = self.belief.tracks[channel]
                track.distance_upper_bound_m = next_upper_bound(track.distance_upper_bound_m or 1500.0)
            measurement = self._measure(action.point, channel, action.coverage_id if action.kind == "SCAN" else None)
            if measurement.signal == "NEAR":
                self._clear(measurement.point, channel)
                return
            if action.kind == "LOCALIZE" and not geometric_localize and is_clearable(self.belief.tracks[channel].distance_upper_bound_m or 1500.0):
                self._clear(action.point, channel)
                return

    def run(self) -> OfficialRunReport:
        started = time.monotonic()
        actual_mode = (
            self.requested_mode
            if self.requested_mode in {"fixed_scan", "hybrid", "framework_v2"}
            else ("ppo" if self.model is not None else "fixed_scan")
        )
        fallback_used = actual_mode != self.requested_mode
        fallback_reason = self.model_error if fallback_used else None
        completed = False
        exit_called = False
        entered = False
        reason = "not_started"
        try:
            self.client.enter()
            entered = True
            reason = "running"
            while not self.belief.can_finish():
                candidates = self._candidates()
                try:
                    if actual_mode == "ppo":
                        index = self._ppo_action(candidates)
                    elif actual_mode == "hybrid":
                        index = self._hybrid_action(candidates)
                    elif actual_mode == "framework_v2":
                        index = self._framework_action(candidates)
                    else:
                        index = self._fixed_action(candidates)
                except Exception as exc:
                    if actual_mode != "ppo":
                        raise
                    actual_mode = "fixed_scan"
                    fallback_used = True
                    fallback_reason = f"PPO运行时回退: {type(exc).__name__}: {exc}"
                    index = self._fixed_action(candidates)
                self._execute(candidates[index])
            completed = True
            reason = "completed"
            self.client.exit()
            exit_called = True
        except Exception as exc:
            reason = f"error:{type(exc).__name__}:{exc}"
        finally:
            if entered and not exit_called:
                try:
                    self.client.exit()
                    exit_called = True
                except Exception as exc:
                    reason = f"{reason}|exit_error:{type(exc).__name__}:{exc}"
        return OfficialRunReport(
            requested_mode=self.requested_mode,
            actual_mode=actual_mode,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            completed=completed,
            exit_called=exit_called,
            termination_reason=reason,
            virtual_time_s=self.virtual_time_s,
            command_count=self.command_count,
            decision_steps=self.decision_steps,
            cleared_count=self.belief.cleared_count,
            wall_time_s=time.monotonic() - started,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="路线C官方模拟器控制器")
    parser.add_argument("--base-url", default="http://127.0.0.1:2026")
    parser.add_argument("--robot-id", required=True)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--mode", choices=("ppo", "fixed_scan", "hybrid", "framework_v2"), default="ppo")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_c/official"))
    args = parser.parse_args()
    controller = OfficialRouteCController(
        OfficialSimulatorClient(args.base_url, args.robot_id),
        config=RouteCConfig(),
        model_path=args.model,
        mode=args.mode,
    )
    payload = asdict(controller.run())
    output_dir = args.output / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "official_run_report.json"
    client = controller.client
    log_path = output_dir / "behavior_log.jsonl"
    with log_path.open("w", encoding="utf-8") as handle:
        for record in client.request_log:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    payload["behavior_log_path"] = str(log_path)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
