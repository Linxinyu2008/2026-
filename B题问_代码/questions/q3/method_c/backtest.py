"""路线C策略回测入口。

回测只通过 RouteCEnv 的公开观察和动作掩码选择动作，不读取场景真值，
用于比较随机、固定扫描、主动评分和 PPO 四类策略。
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable

from questions.q3.shared.candidates import score_candidate
from questions.q3.method_c.core import EpisodeReport, RouteCConfig, RouteCEnv
from questions.q3.method_c.hybrid import choose_hybrid
from questions.q3.method_c.framework_v2 import choose_framework_v2


ActionSelector = Callable[[RouteCEnv, random.Random], int]


def _valid_indices(env: RouteCEnv) -> list[int]:
    return [index for index, valid in enumerate(env.action_masks()) if valid]


def choose_random(env: RouteCEnv, rng: random.Random) -> int:
    valid = _valid_indices(env)
    if not valid:
        raise RuntimeError("环境没有可执行动作")
    return rng.choice(valid)


def choose_fixed_scan(env: RouteCEnv, rng: random.Random) -> int:
    del rng
    valid = _valid_indices(env)
    scan = [index for index in valid if env.candidates()[index].action and env.candidates()[index].action.kind == "SCAN"]
    return (scan or valid)[0]


def choose_active(env: RouteCEnv, rng: random.Random) -> int:
    del rng
    valid = _valid_indices(env)
    return max(valid, key=lambda index: score_candidate(env.candidates()[index]))


def run_episode(env: RouteCEnv, seed: int, selector: ActionSelector) -> EpisodeReport:
    env.reset(seed=seed)
    rng = random.Random(seed + 7919)
    while True:
        action = selector(env, rng)
        _, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            return env.report()


def run_ppo_episode(model: Any, config: RouteCConfig, seed: int) -> EpisodeReport:
    """用训练好的 MaskablePPO 在同一环境核心上回放一个 episode。"""
    from questions.q3.method_c.env import GymRouteCEnv

    env = GymRouteCEnv(config=config)
    observation, _ = env.reset(seed=seed)
    while True:
        action, _ = model.predict(observation, action_masks=env.action_masks(), deterministic=True)
        observation, _, terminated, truncated, _ = env.step(int(action))
        if terminated or truncated:
            report = env.core.report()
            env.close()
            return report


def _record(report: EpisodeReport, strategy: str) -> dict[str, Any]:
    row = asdict(report)
    row.update(
        strategy=strategy,
        cleared_rate=report.cleared_count / report.target_count,
        average_localization_clear_time_s=report.virtual_time_s / report.cleared_count if report.cleared_count else None,
        success=int(report.terminated and report.cleared_count >= report.target_count),
    )
    return row


def _aggregate(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    selected = [row for row in rows if row["strategy"] == strategy]
    def avg(key: str) -> float:
        values = [float(row[key]) for row in selected if row[key] is not None]
        return mean(values) if values else 0.0
    def sd(key: str) -> float:
        values = [float(row[key]) for row in selected]
        return pstdev(values) if len(values) > 1 else 0.0
    return {
        "strategy": strategy,
        "episodes": len(selected),
        "success_rate": avg("success"),
        "mean_cleared_rate": avg("cleared_rate"),
        "mean_localization_clear_time_s": avg("average_localization_clear_time_s"),
        "mean_virtual_time_s": avg("virtual_time_s"),
        "std_virtual_time_s": sd("virtual_time_s"),
        "mean_decision_steps": avg("decision_steps"),
        "mean_detect_count": avg("detect_count"),
        "mean_switch_count": avg("switch_count"),
    }


def run_backtest(seeds: list[int], config: RouteCConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selectors: list[tuple[str, ActionSelector]] = [
        ("random", choose_random),
        ("fixed_scan", choose_fixed_scan),
        ("active", choose_active),
        ("hybrid", choose_hybrid),
    ]
    if config.framework_v2:
        selectors.append(("framework_v2", choose_framework_v2))
    rows: list[dict[str, Any]] = []
    for strategy, selector in selectors:
        for seed in seeds:
            report = run_episode(RouteCEnv(config=config), seed, selector)
            rows.append(_record(report, strategy))
    summary = [_aggregate(rows, strategy) for strategy, _ in selectors]
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="路线C多策略回测")
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20001)
    parser.add_argument("--targets", type=int, default=16)
    parser.add_argument("--profile", default="uniform")
    parser.add_argument("--framework-v2", action="store_true", help="实验：全局多站测向与几何区域定位框架")
    parser.add_argument("--model", type=Path, default=None, help="可选：MaskablePPO模型zip路径")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_c/backtest"))
    args = parser.parse_args()
    if args.episodes <= 0 or args.targets <= 0:
        raise SystemExit("episodes 和 targets 必须为正数")
    seeds = [args.seed + index for index in range(args.episodes)]
    config = RouteCConfig(target_count=args.targets, profile=args.profile, framework_v2=args.framework_v2)
    rows, summary = run_backtest(seeds, config)
    if args.model is not None:
        from sb3_contrib import MaskablePPO

        model = MaskablePPO.load(str(args.model), device="cpu")
        for seed in seeds:
            report = run_ppo_episode(model, config, seed)
            rows.append(_record(report, "ppo"))
        summary.append(_aggregate(rows, "ppo"))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "episodes.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "run_id": run_id,
        "episodes": args.episodes,
        "seed_start": args.seed,
        "targets": args.targets,
        "profile": args.profile,
        "strategies": [item["strategy"] for item in summary],
        "summary": summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
