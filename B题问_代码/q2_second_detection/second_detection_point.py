"""B题第二问：鲁棒第二检测点选择。

本模块复用 ``localization_region.solve_localization_region``，实现：

1. 根据第一次示向度生成集合先验粒子；
2. 用第一次成功接收推出的接收半径下界筛选第二检测点；
3. 用 FIM 几何指标快速筛选；
4. 用第一问的定位区域直径进行确定性几何精修。

误差只有上下界而没有概率分布，因此粒子均值、95%分位数等只作为
辅助指标；最终选点采用离散粒子和误差网格近似的最坏定位直径。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, inf, nextafter, pi, sin, sqrt
from random import Random
from typing import Iterable, Sequence

from q1_localization.localization_region import Point, solve_localization_region


@dataclass(frozen=True)
class TargetParticle:
    point: Point
    first_range: float
    weight: float = 1.0


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _angle_diff_deg(a: float, b: float) -> float:
    """圆周意义下的最小角差，结果位于 [-180, 180)。"""
    return (a - b + 180.0) % 360.0 - 180.0


def _ray_disk_interval(origin: Point, angle: float, radius: float) -> tuple[float, float] | None:
    """从 origin 沿射线与目标圆域相交的非负距离区间。"""
    ux, uy = cos(angle), sin(angle)
    projection = origin[0] * ux + origin[1] * uy
    discriminant = projection * projection + radius * radius - _distance(origin, (0.0, 0.0)) ** 2
    if discriminant < 0.0:
        return None
    root = sqrt(max(0.0, discriminant))
    lower, upper = -projection - root, -projection + root
    if upper < 0.0:
        return None
    return max(0.0, lower), upper


def sample_first_feasible_region(
    station: Point,
    bearing_deg: float,
    *,
    epsilon_deg: float = 1.0,
    target_radius: float = 1800.0,
    min_range: float = 5.0,
    max_range: float = 1500.0,
    angle_count: int = 41,
    range_count: int = 25,
    seed: int = 0,
) -> list[TargetParticle]:
    """在第一次可行域内生成粒子。

    每个方向按面积均匀的径向变量采样，即使用 r² 均匀而不是 r 均匀。
    目标圆域以原点为中心，第一次正常检测带来 ``min_range < r <= max_range``。
    """
    if angle_count < 1 or range_count < 1:
        raise ValueError("angle_count 和 range_count 必须为正整数")
    if not (0.0 < epsilon_deg < 90.0):
        raise ValueError("epsilon_deg 应满足 0 < epsilon_deg < 90")
    if not (0.0 < min_range < max_range):
        raise ValueError("必须满足 0 < min_range < max_range")

    rng = Random(seed)
    particles: list[TargetParticle] = []
    center_angle = bearing_deg * pi / 180.0
    for i in range(angle_count):
        fraction = (i + 0.5) / angle_count
        angle = center_angle + (-epsilon_deg + 2.0 * epsilon_deg * fraction) * pi / 180.0
        disk_interval = _ray_disk_interval(station, angle, target_radius)
        if disk_interval is None:
            continue
        # 正常示向要求距离严格大于min_range；保留最接近的可表示边界点。
        rmin = max(nextafter(min_range, inf), disk_interval[0])
        rmax = min(max_range, disk_interval[1])
        if rmax <= rmin:
            continue
        fractions = [0.0] + [(j + 0.5) / range_count for j in range(range_count)] + [1.0]
        for index, u in enumerate(fractions):
            # 保留两端边界；中间点轻微抖动以避免规则格点，同时保持可复现。
            jitter = 0.0 if index in {0, len(fractions) - 1} else (rng.random() - 0.5) / (10.0 * range_count)
            r2 = rmin * rmin + max(0.0, min(1.0, u + jitter)) * (rmax * rmax - rmin * rmin)
            r = sqrt(r2)
            point = (station[0] + r * cos(angle), station[1] + r * sin(angle))
            particles.append(TargetParticle(point, r))
    if not particles:
        raise ValueError("第一次可行域为空，请检查检测点、示向度和目标圆域")
    weight = 1.0 / len(particles)
    return [TargetParticle(p.point, p.first_range, weight) for p in particles]


def robust_receive_radius(particle: TargetParticle, lower_radius: float = 1000.0) -> float:
    """第一次成功接收后，对该粒子对应目标的有效半径下界。"""
    if lower_radius <= 0:
        raise ValueError("lower_radius 必须为正")
    return max(lower_radius, particle.first_range)


def robust_receive_ratio(
    candidate: Point,
    particles: Sequence[TargetParticle],
    *,
    lower_radius: float = 1000.0,
) -> float:
    """候选点对粒子集合的鲁棒接收覆盖率。1 表示全体粒子均有保证。"""
    if not particles:
        return 0.0
    covered = sum(
        p.weight
        for p in particles
        if _distance(candidate, p.point) <= robust_receive_radius(p, lower_radius) + 1e-9
    )
    total = sum(p.weight for p in particles)
    return covered / total if total > 0.0 else 0.0


def _intersection_angle_deg(station1: Point, target: Point, station2: Point) -> float:
    a = degrees(atan2(station1[1] - target[1], station1[0] - target[0]))
    b = degrees(atan2(station2[1] - target[1], station2[0] - target[0]))
    d = abs(_angle_diff_deg(a, b))
    return min(d, 360.0 - d)


def fim_loss(
    station1: Point,
    station2: Point,
    target: Point,
    *,
    epsilon: float = 1e-9,
) -> float:
    """两次 bearing 观测的 CRLB 等价几何损失（角度噪声方差相同）。"""
    r1 = _distance(target, station1)
    r2 = _distance(target, station2)
    phi = _intersection_angle_deg(station1, target, station2) * pi / 180.0
    return (r1 * r1 + r2 * r2) / (sin(phi) ** 2 + epsilon)


def candidate_grid(
    *,
    center: Point = (0.0, 0.0),
    radius: float = 1800.0,
    step: float = 100.0,
) -> list[Point]:
    """在圆域内生成规则候选网格。"""
    if radius <= 0.0 or step <= 0.0:
        raise ValueError("radius 和 step 必须为正")
    n = int(radius / step) + 1
    points: list[Point] = []
    for ix in range(-n, n + 1):
        for iy in range(-n, n + 1):
            point = (center[0] + ix * step, center[1] + iy * step)
            if _distance(point, center) <= radius + 1e-9:
                points.append(point)
    return points


def _mean_and_quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def worst_case_diameter(
    station1: Point,
    bearing1_deg: float,
    station2: Point,
    particles: Sequence[TargetParticle],
    *,
    epsilon_deg: float = 1.0,
    error_samples: Iterable[float] = (-1.0, -0.5, 0.0, 0.5, 1.0),
) -> float:
    """用粒子和误差网格近似第二次观测后的最坏定位区域直径。"""
    diameters: list[float] = []
    for particle in particles:
        true_bearing = degrees(atan2(particle.point[1] - station2[1], particle.point[0] - station2[0])) % 360.0
        for error in error_samples:
            observed = (true_bearing + error) % 360.0
            result = solve_localization_region(
                [station1, station2], [bearing1_deg, observed], epsilon_deg
            )
            if result["status"] == "OK":
                diameters.append(float(result["diameter"]))
            else:
                # 退化或无界代表不可接受的观测几何。
                diameters.append(float("inf"))
    return max(diameters) if diameters else float("inf")


def select_second_detection_point(
    station1: Point,
    bearing1_deg: float,
    *,
    particles: Sequence[TargetParticle] | None = None,
    candidates: Sequence[Point] | None = None,
    epsilon_deg: float = 1.0,
    lower_radius: float = 1000.0,
    receive_threshold: float = 1.0,
    top_k: int = 20,
    priority_angle: tuple[float, float] = (60.0, 120.0),
) -> dict:
    """返回第二检测点、候选区域和快速/精修指标。"""
    if particles is None:
        particles = sample_first_feasible_region(station1, bearing1_deg, epsilon_deg=epsilon_deg)
    if candidates is None:
        candidates = candidate_grid()
    if not particles or not candidates:
        raise ValueError("particles 和 candidates 不能为空")
    if not (0.0 < receive_threshold <= 1.0):
        raise ValueError("receive_threshold 必须位于 (0, 1]")

    feasible: list[tuple[Point, float, float]] = []
    for candidate in candidates:
        receive = robust_receive_ratio(candidate, particles, lower_radius=lower_radius)
        if receive + 1e-12 < receive_threshold:
            continue
        score = sum(p.weight * fim_loss(station1, candidate, p.point) for p in particles)
        feasible.append((candidate, score, receive))
    if not feasible:
        raise ValueError("候选区域中没有满足鲁棒接收约束的第二检测点")

    feasible.sort(key=lambda item: item[1])
    shortlist = feasible[: max(1, min(top_k, len(feasible)))]
    refined: list[dict] = []
    for candidate, score, receive in shortlist:
        angle_values = [
            _intersection_angle_deg(station1, p.point, candidate)
            for p in particles
        ]
        priority = sum(
            p.weight * (priority_angle[0] <= angle <= priority_angle[1])
            for p, angle in zip(particles, angle_values)
        )
        diameter = worst_case_diameter(
            station1, bearing1_deg, candidate, particles, epsilon_deg=epsilon_deg
        )
        refined.append({
            "point": candidate,
            "fim_loss": score,
            "receive_ratio": receive,
            "priority_angle_ratio": priority,
            "worst_diameter": diameter,
        })
    refined = [item for item in refined if item["worst_diameter"] < float("inf")]
    if not refined:
        raise ValueError("候选点无法形成有限定位区域，请扩大或调整候选区域")
    refined.sort(key=lambda item: item["worst_diameter"])
    best = refined[0]
    return {
        "status": "OK",
        "best_point": best["point"],
        "best": best,
        "particles": list(particles),
        "feasible_candidates": feasible,
        "shortlist": refined,
        "candidate_region": [item[0] for item in feasible],
    }
