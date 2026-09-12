"""路线C MaskablePPO训练入口。

首版只负责训练闭环和检查点保存，模型效果由独立回测脚本评估。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sb3_contrib import MaskablePPO

from questions.q3.method_c.runtime.core import RouteCConfig
from questions.q3.method_c.runtime.env import GymRouteCEnv


def build_model(env: GymRouteCEnv, seed: int, tensorboard_log: str | None = None) -> MaskablePPO:
    return MaskablePPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=128,
        batch_size=64,
        n_epochs=5,
        gamma=1.0,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=0.02,
        policy_kwargs={"net_arch": {"pi": [128, 128], "vf": [128, 128]}},
        tensorboard_log=tensorboard_log,
        seed=seed,
        device="cpu",
        verbose=1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=10001)
    parser.add_argument("--targets", type=int, default=None)
    parser.add_argument("--profile", default="uniform")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_c"))
    args = parser.parse_args()
    if args.steps <= 0:
        raise SystemExit("steps必须为正整数")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    config = RouteCConfig(target_count=args.targets, profile=args.profile)
    env = GymRouteCEnv(config)
    model = build_model(env, args.seed, str(output_dir / "tensorboard"))
    model.learn(total_timesteps=args.steps, reset_num_timesteps=True)
    model.save(str(output_dir / "model"))
    metadata = {
        "run_id": run_id,
        "seed": args.seed,
        "steps": args.steps,
        "targets": args.targets,
        "profile": args.profile,
        "device": "cpu",
        "observation_dimension": 757,
        "action_dimension": 12,
        "algorithm": "MaskablePPO",
        "reward": {
            "time_scale_s": config.reward_time_scale_s,
            "discovery_reward": config.discovery_reward,
            "clear_reward": config.clear_reward,
            "repeated_scan_penalty": config.repeated_scan_penalty,
            "invalid_action_penalty": config.invalid_action_penalty,
        },
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    env.close()
    print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
