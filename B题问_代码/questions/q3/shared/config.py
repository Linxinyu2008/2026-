"""题目规则和算法参数。未从附件确认的协议细节不在这里猜测。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rules:
    target_radius_m: float = 1800.0
    min_reception_radius_m: float = 1000.0
    max_reception_radius_m: float = 1500.0
    bearing_error_deg: float = 1.0
    near_distance_m: float = 5.0
    clear_distance_m: float = 20.0
    move_speed_mps: float = 5.0
    channel_switch_s: float = 1.0
    detection_s: float = 5.0
    optical_s: float = 3.0
    laser_s: float = 2.0
    numeric_margin_m: float = 1e-6

    @property
    def clear_operation_s(self) -> float:
        return self.optical_s + self.laser_s
