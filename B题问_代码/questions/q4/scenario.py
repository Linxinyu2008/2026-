"""仅供本地演练使用的定向/全向场景。控制器不会读取其中的真值。"""

from __future__ import annotations

from dataclasses import dataclass
from math import sin

from .models import Point, Source


@dataclass(frozen=True)
class Scenario:
    sources: tuple[Source, ...]
    seed: int = 0

    def __post_init__(self) -> None:
        channels = [source.channel for source in self.sources]
        if len(set(channels)) != len(channels):
            raise ValueError("每个频道最多允许一个源")
        if any(not 1 <= channel <= 20 for channel in channels):
            raise ValueError("频道必须位于1到20")
        if any(source.reception_radius_m < 1000.0 or source.reception_radius_m > 1500.0 for source in self.sources):
            raise ValueError("接收半径必须位于1000到1500米")

    @classmethod
    def single(
        cls,
        channel: int,
        point: Point,
        reception_radius_m: float,
        orientation_deg: float | None,
    ) -> "Scenario":
        return cls((Source(channel, point, reception_radius_m, orientation_deg),))

    def source_for(self, channel: int) -> Source | None:
        return next((source for source in self.sources if source.channel == channel), None)

    def error_deg(self, point: Point, channel: int) -> float:
        """稳定误差场；默认零误差，测试可通过子类/替换注入对抗误差。"""
        del point, channel
        return 0.0

