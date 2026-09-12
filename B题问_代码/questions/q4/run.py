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
from .triangular_grid import grid_for_region, nearest_neighbor_order, two_opt_order


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
    if config.global_route == "nearest":
        grid = nearest_neighbor_order(grid)
    elif config.global_route == "two_opt":
        grid = two_opt_order(grid)
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
        try:
            result = backend.measure(action.point, action.channel) if action.kind == "MEASURE" else backend.clear(action.point, action.channel)
            controller.accept(action, result)
        except Exception as exc:
            termination_reason = f"error:{type(exc).__name__}:{exc}"
            break
        action_count += 1
    if action_count >= max_actions and not controller.finished:
        termination_reason = "max_actions"
    return {
        "completed": controller.finished,
        "termination_reason": termination_reason,
        "action_count": action_count,
        "command_count": int(getattr(backend, "command_count", action_count)),
        "virtual_time_s": float(getattr(backend, "virtual_time_s", 0.0)),
        "move_distance_m": float(getattr(backend, "move_distance_m", 0.0)),
        "measure_count": int(getattr(backend, "measure_count", 0)),
        "clear_count": int(getattr(backend, "clear_count", 0)),
        "switch_count": int(getattr(backend, "switch_count", 0)),
        "clear_success_count": int(getattr(backend, "clear_success_count", 0)),
        "clear_failure_count": int(getattr(backend, "clear_failure_count", 0)),
        "cleared_channels": sorted(channel for channel, status in controller.statuses.items() if status.value == "cleared"),
        "absent_channels": sorted(channel for channel, status in controller.statuses.items() if status.value == "absent"),
        "unresolved_channels": sorted(channel for channel, status in controller.statuses.items() if status.value not in {"cleared", "absent"}),
        "global_grid_points": len(grid.points),
        "http_request_count": int(getattr(getattr(backend, "client", None), "http_request_count", 0)),
        "retry_count": int(getattr(getattr(backend, "client", None), "retry_count", 0)),
    }


def _failure_result(exc: Exception) -> dict:
    return {
        "completed": False,
        "termination_reason": f"error:{type(exc).__name__}:{exc}",
        "action_count": 0,
        "command_count": 0,
        "virtual_time_s": 0.0,
        "move_distance_m": 0.0,
        "measure_count": 0,
        "clear_count": 0,
        "switch_count": 0,
        "clear_success_count": 0,
        "clear_failure_count": 0,
        "cleared_channels": [],
        "absent_channels": [],
        "unresolved_channels": [],
        "global_grid_points": 0,
        "http_request_count": 0,
        "retry_count": 0,
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
    client = None
    entered = False
    backend = None
    result: dict | None = None
    exit_error: Exception | None = None
    try:
        if args.backend == "local":
            backend = LocalBackend(DirectionalSimulator(demo_scenario(args.seed)))
        else:
            if not args.robot_id:
                parser.error("官方后端必须提供--robot-id")
            from questions.q3.shared.official_client import OfficialSimulatorClient
            client = OfficialSimulatorClient(args.base_url, args.robot_id)
            client.enter()
            entered = True
            backend = OfficialBackend(client)
        result = run_backend(backend, config)
    except Exception as exc:
        result = _failure_result(exc)
    finally:
        if client is not None and entered:
            try:
                client.exit()
                if result is not None:
                    result["exit_called"] = True
            except Exception as exc:
                exit_error = exc
                if result is not None:
                    result["exit_called"] = False
                    result["exit_error"] = f"{type(exc).__name__}:{exc}"
    assert result is not None
    if backend is not None and result.get("action_count", 0) == 0 and result.get("termination_reason", "").startswith("error:"):
        for name in ("virtual_time_s", "move_distance_m", "measure_count", "switch_count", "clear_success_count", "clear_failure_count"):
            if hasattr(backend, name):
                result[name] = getattr(backend, name)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        if client is not None:
            log_path = args.output.with_suffix(args.output.suffix + ".commands.jsonl")
            with log_path.open("w", encoding="utf-8") as handle:
                for record in client.request_log:
                    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            result["behavior_log_path"] = str(log_path)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
