"""问题3公共数据结构。单位统一为米、秒和度。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Point = tuple[float, float]
Signal = Literal["NONE", "BEARING", "NEAR"]
Kind = Literal["SCAN", "LOCALIZE", "CLEAR"]


@dataclass(frozen=True)
class Source:
    channel: int
    point: Point
    reception_radius_m: float


@dataclass(frozen=True)
class Measurement:
    point: Point
    channel: int
    signal: Signal
    bearing_deg: float | None
    virtual_time_s: float


@dataclass(frozen=True)
class ClearResult:
    point: Point
    channel: int
    success: bool
    virtual_time_s: float


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    kind: Kind
    point: Point
    channels: tuple[int, ...]
    coverage_id: int | None = None


@dataclass(frozen=True)
class RobotState:
    position: Point = (0.0, 0.0)
    current_channel: int = 1
