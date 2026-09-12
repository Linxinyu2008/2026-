"""第一问几何求解器的可复现回测。"""

from __future__ import annotations

import argparse
import json
from math import atan2, degrees
from random import Random
from statistics import mean

from questions.q1.localization_region import solve_localization_region


def run_backtest(episodes: int = 50, seed: int = 41001) -> dict:
    rng = Random(seed)
    statuses: dict[str, int] = {}
    diameters: list[float] = []
    for _ in range(episodes):
        target = (rng.uniform(-600.0, 600.0), rng.uniform(-600.0, 600.0))
        stations = [(0.0, -1400.0), (1400.0, 0.0), (0.0, 1400.0), (-1400.0, 0.0)]
        errors = [rng.uniform(-1.0, 1.0) for _ in stations]
        bearings = [
            (degrees(atan2(target[1] - station[1], target[0] - station[0])) + error) % 360.0
            for station, error in zip(stations, errors)
        ]
        result = solve_localization_region(stations, bearings, epsilon_deg=1.0)
        status = str(result["status"])
        statuses[status] = statuses.get(status, 0) + 1
        if status == "OK":
            diameters.append(float(result["diameter"]))
    return {
        "episodes": episodes,
        "seed": seed,
        "status_counts": statuses,
        "ok_rate": statuses.get("OK", 0) / episodes,
        "mean_diameter_m": mean(diameters) if diameters else None,
        "max_diameter_m": max(diameters) if diameters else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed", type=int, default=41001)
    args = parser.parse_args()
    if args.episodes <= 0:
        raise SystemExit("episodes必须为正数")
    print(json.dumps(run_backtest(args.episodes, args.seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
