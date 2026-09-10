"""路线B第一版策略：七点覆盖后，发现即用确定性局部收缩处理。"""

from __future__ import annotations

from q3_common.public.coverage import BeliefTracker, coverage_points
from q3_common.public.local_search import is_clearable, next_half_distance_point, next_upper_bound
from q3_common.public.models import ClearResult, Measurement
from q3_common.public.simulator import LocalSimulator


class RouteBPolicy:
    def __init__(self, simulator: LocalSimulator, belief: BeliefTracker | None = None) -> None:
        self.simulator = simulator
        self.belief = belief or BeliefTracker()

    def scan_unknown_channels(self) -> None:
        for point_id, point in enumerate(coverage_points()):
            for channel in range(1, 21):
                if self.belief.tracks[channel].status != "UNKNOWN":
                    continue
                measurement = self.simulator.detect_at(point, channel)
                self.belief.observe(measurement, point_id)
                if measurement.signal in {"BEARING", "NEAR"}:
                    self.localize_channel(channel, measurement)

    def localize_channel(self, channel: int, first: Measurement) -> None:
        track = self.belief.tracks[channel]
        measurement = first
        for _ in range(8):
            if measurement.signal == "NEAR":
                result = self.simulator.clear_at(measurement.point, channel)
                self.belief.record_clear(result)
                return
            if measurement.signal != "BEARING" or measurement.bearing_deg is None:
                return
            upper = track.distance_upper_bound_m or 1500.0
            point = next_half_distance_point(measurement.point, measurement.bearing_deg, upper)
            upper = next_upper_bound(upper)
            track.distance_upper_bound_m = upper
            if is_clearable(upper):
                result = self.simulator.clear_at(point, channel)
                self.belief.record_clear(result)
                return
            measurement = self.simulator.detect_at(point, channel)
            self.belief.observe(measurement)
            if measurement.signal == "NONE":
                return

    def run(self) -> BeliefTracker:
        self.scan_unknown_channels()
        return self.belief
