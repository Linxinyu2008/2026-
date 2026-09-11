"""问题4本地运行入口；官方后端必须显式指定。"""

from __future__ import annotations

import argparse
import json
import random
from math import cos, pi, sin
from pathlib import Path

from .adapters import LocalBackend, OfficialBackend
from .config import Config
from .controller import Controller
from .geometry import initial_region
from .models import Source
from .scenario import Scenario
from .simulator import DirectionalSimulator
from .triangular_grid import grid_for_region


def demo_scenario(seed: int = 0) -> Scenario:
    rng = random.Random(seed)
    count = 10 + seed % 7
    sources = []
    for channel in range(1, count + 1):
        angle = rng.uniform(0.0, 2.0 * pi)
        distance = 1800.0 * (rng.random() ** 0.5)
        point = (distance * cos(angle), distance * sin(angle))
        radius = float(rng.choice((1000, 1100, 1200, 1300, 1400, 1500)))
        orientation = None if rng.random() < 0.35 else rng.uniform(0.0, 360.0)
        sources.append(Source(channel, point, radius, orientation))
    return Scenario(sources, seed=seed)


def run_backend(backend: object, config: Config, *, max_actions: int = 200000) -> dict:
    grid = grid_for_region(initial_region(), config.global_spacing_m)
    controller = Controller(backend, config, grid)
    action_count = 0
    termination_reason = "completed"
    while action_count < max_actions:
        try:
            action = controller.next_action()
        except Exception as exc:
            termination_reason = f"error:{type(exc).__name__}:{exc}"
            break
        if action is None:
            if not controller.finished:
                termination_reason = "stopped_unresolved"
            break
        result = backend.measure(action.point, action.channel) if action.kind == "MEASURE" else backend.clear(action.point, action.channel)
        controller.accept(action, result)
        action_count += 1
    if action_count >= max_actions and not controller.finished:
        termination_reason = "max_actions"
    return {
        "completed": controller.finished,
        "termination_reason": termination_reason,
        "action_count": action_count,
        "virtual_time_s": float(getattr(backend, "virtual_time_s", 0.0)),
        "move_distance_m": float(getattr(backend, "move_distance_m", 0.0)),
        "measure_count": int(getattr(backend, "measure_count", 0)),
        "switch_count": int(getattr(backend, "switch_count", 0)),
        "clear_success_count": int(getattr(backend, "clear_success_count", 0)),
        "clear_failure_count": int(getattr(backend, "clear_failure_count", 0)),
        "cleared_channels": sorted(channel for channel, status in controller.statuses.items() if status.value == "cleared"),
        "absent_channels": sorted(channel for channel, status in controller.statuses.items() if status.value == "absent"),
        "unresolved_channels": sorted(channel for channel, status in controller.statuses.items() if status.value not in {"cleared", "absent"}),
        "global_grid_points": len(grid.points),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="问题4三角网格基线")
    parser.add_argument("--backend", choices=("local", "official"), default="local")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:2026")
    parser.add_argument("--robot-id", default=None)
    args = parser.parse_args(argv)
    config = Config()
    if args.backend == "local":
        backend = LocalBackend(DirectionalSimulator(demo_scenario(args.seed)))
    else:
        if not args.robot_id:
            parser.error("官方后端必须提供--robot-id")
        from q3_common.public.official_client import OfficialSimulatorClient
        client = OfficialSimulatorClient(args.base_url, args.robot_id)
        client.enter()
        backend = OfficialBackend(client)
    result = run_backend(backend, config)
    if args.backend == "official":
        client.exit()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0 if result["completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
