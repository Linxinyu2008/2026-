"""路线B固定策略与主动策略的配对本地实验。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from questions.q3.shared.config import Rules
from questions.q3.shared.scenario import generate_scenario
from questions.q3.shared.simulator import LocalSimulator

from .active_policy import ActiveRouteBPolicy
from .policy import RouteBPolicy


def run_one(seed: int, target_count: int | None, policy_name: str, profile: str = "uniform") -> dict[str, object]:
    rules = Rules()
    scenario = generate_scenario(seed, rules, target_count, profile)
    simulator = LocalSimulator(scenario, rules)
    if policy_name == "active":
        policy = ActiveRouteBPolicy(simulator)
    else:
        policy = RouteBPolicy(simulator)
    belief = policy.run()
    return {
        "seed": seed,
        "policy": policy_name,
        "profile": profile,
        "targets": len(scenario.sources),
        "cleared": belief.cleared_count,
        "all_cleared": belief.cleared_count == len(scenario.sources),
        "virtual_time_s": simulator.virtual_time_s,
        "move_distance_m": simulator.move_distance_m,
        "detect_count": simulator.detect_count,
        "switch_count": simulator.switch_count,
        "decision_steps": len(getattr(policy, "candidate_history", [])),
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {"episodes": len(rows)}
    for policy in ("fixed", "active"):
        group = [row for row in rows if row["policy"] == policy]
        times = [float(row["virtual_time_s"]) for row in group]
        summary[policy] = {
            "episodes": len(group),
            "all_clear_rate": sum(bool(row["all_cleared"]) for row in group) / len(group) if group else 0.0,
            "mean_cleared": sum(int(row["cleared"]) for row in group) / len(group) if group else 0.0,
            "mean_virtual_time_s": sum(times) / len(times) if times else None,
            "median_virtual_time_s": sorted(times)[len(times) // 2] if times else None,
            "mean_move_distance_m": sum(float(row["move_distance_m"]) for row in group) / len(group) if group else None,
            "mean_detect_count": sum(int(row["detect_count"]) for row in group) / len(group) if group else None,
            "mean_switch_count": sum(int(row["switch_count"]) for row in group) / len(group) if group else None,
            "mean_decision_steps": sum(int(row["decision_steps"]) for row in group) / len(group) if group else None,
        }
    paired = {}
    for seed in sorted({int(row["seed"]) for row in rows}):
        for profile in sorted({str(row["profile"]) for row in rows if int(row["seed"]) == seed}):
            fixed = next(row for row in rows if row["seed"] == seed and row["profile"] == profile and row["policy"] == "fixed")
            active = next(row for row in rows if row["seed"] == seed and row["profile"] == profile and row["policy"] == "active")
            paired[f"{profile}:{seed}"] = {
            "active_minus_fixed_time_s": float(active["virtual_time_s"]) - float(fixed["virtual_time_s"]),
            "active_minus_fixed_move_m": float(active["move_distance_m"]) - float(fixed["move_distance_m"]),
            "same_clear_result": active["cleared"] == fixed["cleared"],
        }
    summary["paired"] = paired
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--targets", type=int, default=None)
    parser.add_argument("--profiles", default="uniform")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_b"))
    args = parser.parse_args()
    if args.episodes <= 0:
        raise SystemExit("episodes必须为正整数")
    profiles = tuple(profile.strip() for profile in args.profiles.split(",") if profile.strip())
    rows = [
        run_one(seed, args.targets, policy, profile)
        for profile in profiles
        for seed in range(args.seed_start, args.seed_start + args.episodes)
        for policy in ("fixed", "active")
    ]
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "episodes.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **{k: v for k, v in summary.items() if k in {"fixed", "active"}}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
