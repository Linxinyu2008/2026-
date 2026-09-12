"""问题4本地场景批量入口。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .adapters import LocalBackend
from .config import Config
from .run import demo_scenario, run_backend
from .simulator import DirectionalSimulator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="问题4本地批量回放")
    parser.add_argument("--seeds", default="0:4", help="闭区间种子，例如0:4")
    parser.add_argument("--output", type=Path, default=Path("outputs/q4/baseline.csv"))
    parser.add_argument("--global-spacing", type=float, default=950.0)
    parser.add_argument("--global-route", choices=("two_opt", "nearest", "snake"), default="two_opt")
    parser.add_argument("--optical-spacing", type=float, default=30.0)
    parser.add_argument("--max-local-measurements", type=int, default=8)
    parser.add_argument("--no-progress-window", type=int, default=4)
    args = parser.parse_args(argv)
    start, end = (int(item) for item in args.seeds.split(":", 1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = None
        for seed in range(start, end + 1):
            config = Config(
                global_spacing_m=args.global_spacing,
                global_route=args.global_route,
                optical_spacing_m=args.optical_spacing,
                max_local_measurements=args.max_local_measurements,
                no_progress_window=args.no_progress_window,
            )
            result = run_backend(LocalBackend(DirectionalSimulator(demo_scenario(seed))), config)
            row = {
                "seed": seed,
                "global_spacing_m": args.global_spacing,
                "global_route": args.global_route,
                "optical_spacing_m": args.optical_spacing,
                "max_local_measurements": args.max_local_measurements,
                "no_progress_window": args.no_progress_window,
                **result,
            }
            if writer is None:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
