"""路线B本地单局入口。"""

from __future__ import annotations

import argparse

from q3_common.public.config import Rules
from q3_common.public.scenario import generate_scenario
from q3_common.public.simulator import LocalSimulator

from .policy import RouteBPolicy
from .active_policy import ActiveRouteBPolicy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--targets", type=int, default=None)
    parser.add_argument("--policy", choices=("fixed", "active"), default="active")
    args = parser.parse_args()
    rules = Rules()
    scenario = generate_scenario(args.seed, rules, args.targets)
    simulator = LocalSimulator(scenario, rules)
    policy = ActiveRouteBPolicy(simulator) if args.policy == "active" else RouteBPolicy(simulator)
    belief = policy.run()
    print({
        "seed": args.seed,
        "targets": len(scenario.sources),
        "cleared": belief.cleared_count,
        "virtual_time_s": round(simulator.virtual_time_s, 3),
        "move_distance_m": round(simulator.move_distance_m, 3),
        "detect_count": simulator.detect_count,
        "switch_count": simulator.switch_count,
        "statuses": {status: sum(t.status == status for t in belief.tracks.values()) for status in {"UNKNOWN", "TRACKING", "CLEARABLE", "CLEARED", "ABSENT"}},
    })


if __name__ == "__main__":
    main()
