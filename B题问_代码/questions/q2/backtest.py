"""第二问第二检测点选择器的可复现回测。"""

from __future__ import annotations

import argparse
import json
from math import atan2, degrees
from random import Random
from statistics import mean

from questions.q2.second_detection_point import (
    candidate_grid,
    sample_first_feasible_region,
    select_second_detection_point,
)


def run_backtest(episodes: int = 20, seed: int = 42001) -> dict:
    rng = Random(seed)
    successes = 0
    receive_ratios: list[float] = []
    worst_diameters: list[float] = []
    for _ in range(episodes):
        station = (rng.uniform(-400.0, 400.0), rng.uniform(-400.0, 400.0))
        target = (rng.uniform(-600.0, 600.0), rng.uniform(-600.0, 600.0))
        bearing = degrees(atan2(target[1] - station[1], target[0] - station[0])) % 360.0
        particles = sample_first_feasible_region(
            station, bearing, angle_count=9, range_count=8, seed=rng.randrange(1_000_000)
        )
        result = select_second_detection_point(
            station,
            bearing,
            particles=particles,
            candidates=candidate_grid(step=300.0),
            top_k=5,
        )
        successes += int(result["status"] == "OK")
        receive_ratios.append(float(result["best"]["receive_ratio"]))
        worst_diameters.append(float(result["best"]["worst_diameter"]))
    return {
        "episodes": episodes,
        "seed": seed,
        "success_rate": successes / episodes,
        "mean_receive_ratio": mean(receive_ratios),
        "min_receive_ratio": min(receive_ratios),
        "mean_worst_diameter_m": mean(worst_diameters),
        "max_worst_diameter_m": max(worst_diameters),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42001)
    args = parser.parse_args()
    if args.episodes <= 0:
        raise SystemExit("episodes必须为正数")
    print(json.dumps(run_backtest(args.episodes, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
