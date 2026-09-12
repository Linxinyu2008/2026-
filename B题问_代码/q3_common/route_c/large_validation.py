"""Large paired validation for the original Hybrid and Framework V2."""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable

from q3_common.route_c.backtest import run_episode
from q3_common.route_c.core import RouteCConfig, RouteCEnv
from q3_common.route_c.framework_v2 import choose_framework_v2
from q3_common.route_c.hybrid import choose_hybrid


Selector = Callable[[RouteCEnv, Any], int]


def _run(strategy: str, selector: Selector, seed: int, count: int, profile: str) -> dict[str, Any]:
    config = RouteCConfig(
        target_count=count,
        profile=profile,
        framework_v2=strategy == "framework_v2",
    )
    started = time.perf_counter()
    try:
        report = run_episode(RouteCEnv(config=config), seed, selector)
        row = asdict(report)
        row["error"] = None
        row["success"] = int(report.terminated and report.cleared_count == report.target_count)
    except Exception as exc:
        row = {
            "seed": seed,
            "target_count": count,
            "cleared_count": 0,
            "terminated": False,
            "truncated": False,
            "termination_reason": "exception",
            "virtual_time_s": None,
            "move_distance_m": None,
            "detect_count": None,
            "switch_count": None,
            "decision_steps": None,
            "error": f"{type(exc).__name__}: {exc}",
            "success": 0,
        }
    row.update(
        strategy=strategy,
        profile=profile,
        wall_time_s=time.perf_counter() - started,
    )
    row["per_target_time_s"] = (
        float(row["virtual_time_s"]) / count if row["virtual_time_s"] is not None else None
    )
    return row


def _summary(rows: list[dict[str, Any]], strategy: str, profile: str | None = None, count: int | None = None) -> dict[str, Any]:
    selected = [
        row for row in rows
        if row["strategy"] == strategy
        and (profile is None or row["profile"] == profile)
        and (count is None or row["target_count"] == count)
    ]
    successful = [row for row in selected if row["success"] == 1]

    def values(key: str) -> list[float]:
        return [float(row[key]) for row in successful if row[key] is not None]

    times = values("virtual_time_s")
    per_target = values("per_target_time_s")
    return {
        "strategy": strategy,
        "profile": profile or "ALL",
        "target_count": count if count is not None else "ALL",
        "episodes": len(selected),
        "successes": len(successful),
        "success_rate": len(successful) / len(selected) if selected else 0.0,
        "mean_virtual_time_s": mean(times) if times else None,
        "median_virtual_time_s": median(times) if times else None,
        "max_virtual_time_s": max(times) if times else None,
        "mean_per_target_time_s": mean(per_target) if per_target else None,
        "max_per_target_time_s": max(per_target) if per_target else None,
        "mean_move_distance_m": mean(values("move_distance_m")) if successful else None,
        "mean_detect_count": mean(values("detect_count")) if successful else None,
        "mean_switch_count": mean(values("switch_count")) if successful else None,
        "mean_wall_time_s": mean(values("wall_time_s")) if successful else None,
        "max_wall_time_s": max(values("wall_time_s")) if successful else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="第三问Hybrid与Framework V2大样本成对回测")
    parser.add_argument("--seeds-per-cell", type=int, default=100)
    parser.add_argument("--seed", type=int, default=70001)
    parser.add_argument("--profiles", default="uniform,edge,clustered,min_radius,max_error")
    parser.add_argument("--counts", default="10,11,12,13,14,15,16")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_c/framework_v2_large_validation"))
    args = parser.parse_args()
    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    counts = [int(item) for item in args.counts.split(",") if item.strip()]
    if args.seeds_per_cell <= 0 or any(count < 10 or count > 16 for count in counts):
        raise SystemExit("seeds-per-cell必须为正，counts必须位于10到16")

    rows: list[dict[str, Any]] = []
    selectors = (("hybrid", choose_hybrid), ("framework_v2", choose_framework_v2))
    for profile_index, profile in enumerate(profiles):
        for count_index, count in enumerate(counts):
            cell_seed = args.seed + (profile_index * len(counts) + count_index) * args.seeds_per_cell
            for offset in range(args.seeds_per_cell):
                seed = cell_seed + offset
                for strategy, selector in selectors:
                    rows.append(_run(strategy, selector, seed, count, profile))

    summaries = []
    for strategy, _ in selectors:
        summaries.append(_summary(rows, strategy))
        for profile in profiles:
            summaries.append(_summary(rows, strategy, profile=profile))
        for count in counts:
            summaries.append(_summary(rows, strategy, count=count))

    paired = []
    framework_by_key = {
        (row["profile"], row["target_count"], row["seed"]): row
        for row in rows if row["strategy"] == "framework_v2"
    }
    for baseline in (row for row in rows if row["strategy"] == "hybrid"):
        candidate = framework_by_key[(baseline["profile"], baseline["target_count"], baseline["seed"])]
        delta = None
        if baseline["virtual_time_s"] is not None and candidate["virtual_time_s"] is not None:
            delta = float(candidate["virtual_time_s"]) - float(baseline["virtual_time_s"])
        paired.append({
            "profile": baseline["profile"],
            "target_count": baseline["target_count"],
            "seed": baseline["seed"],
            "baseline_success": baseline["success"],
            "candidate_success": candidate["success"],
            "baseline_time_s": baseline["virtual_time_s"],
            "candidate_time_s": candidate["virtual_time_s"],
            "delta_s": delta,
            "candidate_wins": int(delta is not None and delta < -1e-9),
        })

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in (("episodes.csv", rows), ("paired.csv", paired), ("summary.csv", summaries)):
        with (output_dir / filename).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    payload = {
        "run_id": run_id,
        "profiles": profiles,
        "counts": counts,
        "seeds_per_cell": args.seeds_per_cell,
        "scene_count": len(profiles) * len(counts) * args.seeds_per_cell,
        "episode_count": len(rows),
        "summaries": summaries,
        "paired_wins": sum(item["candidate_wins"] for item in paired),
        "paired_comparisons": len(paired),
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
