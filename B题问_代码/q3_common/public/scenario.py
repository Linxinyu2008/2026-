"""本地可复现场景和地点相关固定误差场。"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin, sqrt
from random import Random

from .config import Rules
from .models import Point, Source


def _check_point(point: Point, radius: float) -> None:
    if len(point) != 2 or not all(float(v) == float(v) for v in point):
        raise ValueError("点坐标必须是有限数值")
    if hypot(*point) > radius + 1e-9:
        raise ValueError("目标点必须位于目标圆域内")


@dataclass(frozen=True)
class FixedErrorField:
    """首版固定场：每个频道为常量误差，保证同地点重复检测一致。"""

    errors_by_channel: tuple[float, ...]

    def value(self, point: Point, channel: int) -> float:
        del point
        if not 1 <= channel <= len(self.errors_by_channel):
            raise ValueError("频道必须位于误差场范围内")
        return self.errors_by_channel[channel - 1]


@dataclass(frozen=True)
class SpatialErrorField:
    """地点相关且时间固定的误差场，始终限制在题设的±1°内。"""

    offsets_by_channel: tuple[float, ...]
    amplitudes_by_channel: tuple[float, ...]
    phases_by_channel: tuple[float, ...]

    def value(self, point: Point, channel: int) -> float:
        if not 1 <= channel <= len(self.offsets_by_channel):
            raise ValueError("频道必须位于误差场范围内")
        index = channel - 1
        x, y = point
        value = self.offsets_by_channel[index] + self.amplitudes_by_channel[index] * sin(
            0.0013 * x + 0.0007 * y + self.phases_by_channel[index]
        )
        return max(-1.0, min(1.0, value))


@dataclass(frozen=True)
class Scenario:
    sources: tuple[Source, ...]
    error_field: FixedErrorField | SpatialErrorField

    def source_for(self, channel: int) -> Source | None:
        return next((s for s in self.sources if s.channel == channel), None)


def make_fixed_scenario(sources: list[Source] | tuple[Source, ...], error_deg: float = 0.0) -> Scenario:
    if not -1.0 <= error_deg <= 1.0:
        raise ValueError("误差必须位于[-1, 1]度")
    channels = [s.channel for s in sources]
    if len(set(channels)) != len(channels):
        raise ValueError("不同干扰源的频道必须互不相同")
    for source in sources:
        if not 1 <= source.channel <= 20:
            raise ValueError("频道必须位于1到20")
        if not 1000.0 <= source.reception_radius_m <= 1500.0:
            raise ValueError("接收半径必须位于1000到1500米")
        _check_point(source.point, 1800.0)
    errors = tuple(error_deg for _ in range(20))
    return Scenario(tuple(sources), FixedErrorField(errors))


def generate_scenario(
    seed: int,
    rules: Rules = Rules(),
    target_count: int | None = None,
    profile: str = "uniform",
) -> Scenario:
    rng = Random(seed)
    count = target_count if target_count is not None else rng.randint(10, 16)
    if not 10 <= count <= 16:
        raise ValueError("目标数必须位于10到16")
    channels = rng.sample(range(1, 21), count)
    sources: list[Source] = []
    if profile not in {"uniform", "edge", "clustered", "min_radius", "max_error", "mixed"}:
        raise ValueError(f"未知场景profile: {profile}")
    if profile == "mixed":
        profile = rng.choice(("uniform", "edge", "clustered", "min_radius", "max_error"))
    cluster_center = (0.0, 0.0)
    if profile == "clustered":
        center_radius = 700.0 * sqrt(rng.random())
        center_angle = rng.random() * 2.0 * pi
        cluster_center = (center_radius * cos(center_angle), center_radius * sin(center_angle))
    for channel in channels:
        if profile == "edge":
            radius = rng.uniform(1600.0, rules.target_radius_m)
        elif profile == "clustered":
            radius = min(500.0 * sqrt(rng.random()), 1800.0 - hypot(*cluster_center))
        else:
            radius = rules.target_radius_m * sqrt(rng.random())
        angle = rng.random() * 2.0 * pi
        point = (cluster_center[0] + radius * cos(angle), cluster_center[1] + radius * sin(angle))
        if hypot(*point) > rules.target_radius_m:
            point = (radius * cos(angle), radius * sin(angle))
        reception = rules.min_reception_radius_m if profile == "min_radius" else rng.uniform(rules.min_reception_radius_m, rules.max_reception_radius_m)
        sources.append(Source(channel, point, reception))
    offsets = tuple(rng.uniform(-0.5, 0.5) for _ in range(20))
    amplitudes = tuple(rng.uniform(0.0, 0.5) for _ in range(20))
    phases = tuple(rng.random() * 2.0 * pi for _ in range(20))
    if profile == "max_error":
        offsets = tuple(rules.bearing_error_deg if seed % 2 == 0 else -rules.bearing_error_deg for _ in range(20))
        amplitudes = (0.0,) * 20
    return Scenario(tuple(sources), SpatialErrorField(offsets, amplitudes, phases))
