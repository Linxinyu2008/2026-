"""问题4本地策略和题目规则参数。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rules:
    move_speed_mps: float = 5.0
    measure_s: float = 5.0
    switch_s: float = 1.0
    clear_success_s: float = 5.0
    clear_failure_s: float = 3.0
    near_distance_m: float = 5.0
    clear_distance_m: float = 20.0
    numeric_margin_m: float = 1e-7


@dataclass(frozen=True)
class Config:
    rules: Rules = Rules()
    global_spacing_m: float = 950.0
    optical_spacing_m: float = 30.0
    angle_margin_deg: float = 1.005
    max_local_measurements: int = 8
    no_progress_window: int = 4
    progress_ratio: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 < self.global_spacing_m <= 1000.0:
            raise ValueError("global_spacing_m必须位于(0,1000]米")
        if not 0.0 < self.optical_spacing_m <= 20.0 * 3**0.5:
            raise ValueError("optical_spacing_m不满足三角网格20米覆盖条件")
        if self.max_local_measurements <= 0 or self.no_progress_window <= 0:
            raise ValueError("局部尝试上限必须为正整数")
        if not 0.0 <= self.progress_ratio < 1.0:
            raise ValueError("progress_ratio必须位于[0,1)")
