"""路线B主动候选评分策略。"""

from __future__ import annotations

from questions.q3.shared.candidates import Candidate, build_candidates, score_candidate
from questions.q3.shared.coverage import BeliefTracker
from questions.q3.shared.local_search import is_clearable, next_upper_bound
from questions.q3.shared.models import RobotState
from questions.q3.shared.simulator import LocalSimulator


class ActiveRouteBPolicy:
    def __init__(self, simulator: LocalSimulator, belief: BeliefTracker | None = None) -> None:
        self.simulator = simulator
        self.belief = belief or BeliefTracker()
        self.candidate_history: list[list[Candidate]] = []

    def _execute(self, candidate: Candidate) -> None:
        if not candidate.valid or candidate.action is None:
            return
        action = candidate.action
        if action.kind == "CLEAR":
            result = self.simulator.clear_at(action.point, action.channels[0])
            self.belief.record_clear(result)
            return
        for channel in action.channels:
            if action.kind == "LOCALIZE":
                track = self.belief.tracks[channel]
                track.distance_upper_bound_m = next_upper_bound(track.distance_upper_bound_m or 1500.0)
            measurement = self.simulator.detect_at(action.point, channel)
            self.belief.observe(measurement, action.coverage_id if action.kind == "SCAN" else None)
            if measurement.signal == "NEAR":
                result = self.simulator.clear_at(measurement.point, channel)
                self.belief.record_clear(result)
                return
            if action.kind == "LOCALIZE" and is_clearable(self.belief.tracks[channel].distance_upper_bound_m or 1500.0):
                result = self.simulator.clear_at(action.point, channel)
                self.belief.record_clear(result)
                return

    def choose(self) -> Candidate:
        robot = RobotState(self.simulator.position, self.simulator.current_channel)
        candidates = build_candidates(self.belief, robot)
        self.candidate_history.append(candidates)
        # 已发现但未清除的目标必须连续定位，避免扫描收益中断几何收缩。
        active_tracks = [track for track in self.belief.tracks.values() if track.status == "TRACKING"]
        if active_tracks:
            local = [candidate for candidate in candidates if candidate.valid and candidate.action and candidate.action.kind == "LOCALIZE"]
            if local:
                return min(local, key=lambda candidate: (candidate.estimated_time_s, candidate.action.action_id))
        return max(candidates, key=score_candidate)

    def run(self, max_steps: int = 500) -> BeliefTracker:
        for _ in range(max_steps):
            if self.belief.can_finish():
                break
            candidate = self.choose()
            if not candidate.valid:
                break
            self._execute(candidate)
        return self.belief
