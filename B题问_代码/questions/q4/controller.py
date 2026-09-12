"""问题4确定性基线控制器：全局三角扫描加已发现频道局部处理。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .geometry import initial_region
from .local_policy import Track, next_local_action, record_measurement
from .models import Action, ChannelStatus, ClearResult, Measurement, RobotState
from .triangular_grid import Grid


@dataclass
class Controller:
    backend: object
    config: Config
    grid: Grid
    tracks: dict[int, Track] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.statuses = {channel: ChannelStatus.UNKNOWN for channel in range(1, 21)}
        self.none_evidence: dict[int, set[int]] = {channel: set() for channel in range(1, 21)}
        self.point_index = 0
        self.channel_index = 0
        self.finished = False

    @property
    def _robot(self) -> RobotState:
        return RobotState(getattr(self.backend, "position", (0.0, 0.0)), getattr(self.backend, "current_channel", 1))

    def _terminal(self, status: ChannelStatus) -> bool:
        return status in (ChannelStatus.CLEARED, ChannelStatus.ABSENT)

    def _mark_absent_after_scan(self) -> None:
        if self.point_index < len(self.grid.points):
            return
        for channel in range(1, 21):
            if self.statuses[channel] == ChannelStatus.UNKNOWN and len(self.none_evidence[channel]) == len(self.grid.points):
                self.statuses[channel] = ChannelStatus.ABSENT

    def _update_finished(self) -> None:
        self._mark_absent_after_scan()
        self.finished = all(self._terminal(status) for status in self.statuses.values())

    def next_action(self) -> Action | None:
        self._update_finished()
        if self.finished:
            return None
        global_scan_complete = self.point_index >= len(self.grid.points)
        for channel, track in self.tracks.items():
            if self.statuses[channel] in (ChannelStatus.CLEARED, ChannelStatus.ABSENT):
                continue
            # 普通BEARING在全局扫描阶段暂存，避免在网格行之间反复往返。
            # NEAR/CLEARABLE仍立即处理，避免错过已经确定的清除机会。
            if global_scan_complete or track.status == ChannelStatus.CLEARABLE:
                return next_local_action(track, self._robot, self.config)
        while self.point_index < len(self.grid.points):
            point = self.grid.points[self.point_index]
            while self.channel_index < 20:
                channel = self.channel_index + 1
                self.channel_index += 1
                if self._terminal(self.statuses[channel]) or channel in self.tracks:
                    continue
                return Action("MEASURE", point, channel, "global_scan", self.point_index)
            self.point_index += 1
            self.channel_index = 0
        self._update_finished()
        if not self.finished:
            for channel, track in self.tracks.items():
                if self.statuses[channel] not in (ChannelStatus.CLEARED, ChannelStatus.ABSENT):
                    return next_local_action(track, self._robot, self.config)
        return None

    def accept(self, action: Action, result: Measurement | ClearResult) -> None:
        channel = action.channel
        if action.kind == "CLEAR":
            if not isinstance(result, ClearResult):
                raise TypeError("CLEAR动作必须接收ClearResult")
            track = self.tracks[channel]
            if result.success:
                self.statuses[channel] = ChannelStatus.CLEARED
                track.status = ChannelStatus.CLEARED
            else:
                track.optical_index += 1
            self._update_finished()
            return
        if not isinstance(result, Measurement):
            raise TypeError("MEASURE动作必须接收Measurement")
        if action.reason == "global_scan":
            point_id = action.coverage_id
            if result.signal == "NONE" and point_id is not None:
                self.none_evidence[channel].add(point_id)
            elif result.signal != "NONE":
                track = record_measurement(None, result, initial_region())
                self.tracks[channel] = track
                self.statuses[channel] = track.status
        else:
            track = self.tracks[channel]
            record_measurement(track, result)
            self.statuses[channel] = track.status
        self._update_finished()
