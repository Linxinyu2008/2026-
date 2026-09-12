"""第一、第二、第三部分统一本地回测入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from questions.q1.backtest import run_backtest as run_q1
from questions.q2.backtest import run_backtest as run_q2
from questions.q3.method_c.backtest import run_backtest as run_q3
from questions.q3.method_c.core import RouteCConfig
from questions.q3.method_c.backtest import _aggregate, _record, run_ppo_episode


def main() -> None:
    parser = argparse.ArgumentParser(description="Part 1/2/3统一本地回测")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--targets", type=int, default=16)
    parser.add_argument("--profile", default="mixed")
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("outputs/part123"))
    args = parser.parse_args()
    if args.episodes <= 0 or not 10 <= args.targets <= 16:
        raise SystemExit("episodes必须为正数，targets必须位于10到16")
    q3_rows, q3_summary = run_q3(
        [50001 + index for index in range(args.episodes)],
        RouteCConfig(target_count=args.targets, profile=args.profile),
    )
    if args.model is not None:
        from sb3_contrib import MaskablePPO

        q3_config = RouteCConfig(target_count=args.targets, profile=args.profile)
        model = MaskablePPO.load(str(args.model), device="cpu")
        for seed in [50001 + index for index in range(args.episodes)]:
            report = run_ppo_episode(model, q3_config, seed)
            q3_rows.append(_record(report, "ppo"))
        q3_summary.append(_aggregate(q3_rows, "ppo"))
    payload = {
        "questions.q1": run_q1(args.episodes, 51001),
        "questions.q2": run_q2(args.episodes, 52001),
        "q3_route_c": {
            "episodes": args.episodes,
            "targets": args.targets,
            "profile": args.profile,
            "model": str(args.model) if args.model else None,
            "summary": q3_summary,
        },
        "note": "这是本地规则仿真回测，不替代真实模拟器演练。",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    output_file = args.output / "part123_backtest.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"saved_to={output_file}")


if __name__ == "__main__":
    main()
