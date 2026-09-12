"""问题4的基础数据结构。单位为米、秒和度。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Point = tuple[float, float]
Signal = Literal["NONE", "BEARING", "NEAR"]


@dataclass(frozen=True)
class Source:
    channel: int
    point: Point
    reception_radius_m: float
    orientation_deg: float | None = None


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


class ChannelStatus(Enum):
    UNKNOWN = "unknown"
    FOUND = "found"
    TRACKING = "tracking"
    CLEARABLE = "clearable"
    CLEARED = "cleared"
    ABSENT = "absent"


class LocalMode(Enum):
    FAST = "fast"
    REACQUIRE = "reacquire"
    OPTICAL = "optical"


@dataclass(frozen=True)
class RobotState:
    position: Point = (0.0, 0.0)
    current_channel: int = 1


@dataclass(frozen=True)
class Action:
    kind: Literal["MEASURE", "CLEAR"]
    point: Point
    channel: int
    reason: str
    coverage_id: int | None = None

