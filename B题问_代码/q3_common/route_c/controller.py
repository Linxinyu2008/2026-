"""路线C主控制器。

控制器把环境、PPO推理和固定扫描回退串成一个可执行入口。
它只依赖 public 和 route_c，不调用 route_b 的策略实现。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from q3_common.route_c.core import EpisodeReport, RouteCConfig
from q3_common.route_c.env import GymRouteCEnv


@dataclass(frozen=True)
class ControllerReport:
    seed: int
    requested_mode: str
    actual_mode: str
    fallback_used: bool
    fallback_reason: str | None
    episode: EpisodeReport


class RouteCController:
    """路线C运行时控制器，默认优先使用 PPO，异常时回退固定扫描。"""

    def __init__(
        self,
        config: RouteCConfig | None = None,
        model_path: str | Path | None = None,
        mode: str = "ppo",
    ) -> None:
        if mode not in {"ppo", "fixed_scan"}:
            raise ValueError("mode必须是ppo或fixed_scan")
        self.config = config or RouteCConfig()
        self.requested_mode = mode
        self.model_path = Path(model_path) if model_path else None
        self.model: Any | None = None
        self.model_error: str | None = None
        self._load_model_if_needed()

    def _load_model_if_needed(self) -> None:
        if self.requested_mode == "fixed_scan":
            return
        if self.model_path is None:
            self.model_error = "未提供PPO模型路径"
            return
        try:
            from sb3_contrib import MaskablePPO

            self.model = MaskablePPO.load(str(self.model_path), device="cpu")
        except Exception as exc:  # 运行时必须保留固定扫描回退
            self.model = None
            self.model_error = f"PPO模型加载失败: {type(exc).__name__}: {exc}"

    @staticmethod
    def _valid_actions(env: GymRouteCEnv) -> list[int]:
        masks = env.action_masks()
        if masks.shape != (12,):
            raise RuntimeError(f"动作掩码维度异常: {masks.shape}")
        valid = [index for index, flag in enumerate(masks.tolist()) if bool(flag)]
        if not valid:
            raise RuntimeError("当前状态没有合法动作")
        return valid

    def _fixed_scan_action(self, env: GymRouteCEnv) -> int:
        valid = self._valid_actions(env)
        candidates = env.core.candidates()
        scan = [
            index for index in valid
            if candidates[index].action is not None and candidates[index].action.kind == "SCAN"
        ]
        return (scan or valid)[0]

    def _ppo_action(self, env: GymRouteCEnv, observation: Any) -> int:
        if self.model is None:
            raise RuntimeError(self.model_error or "PPO模型不可用")
        valid = self._valid_actions(env)
        action, _ = self.model.predict(observation, action_masks=env.action_masks(), deterministic=True)
        action_id = int(action)
        if action_id not in valid:
            raise RuntimeError(f"PPO输出非法动作: {action_id}, 合法动作: {valid}")
        return action_id

    def run_episode(self, seed: int) -> ControllerReport:
        env = GymRouteCEnv(config=self.config)
        observation, _ = env.reset(seed=seed)
        actual_mode = "ppo" if self.requested_mode == "ppo" and self.model is not None else "fixed_scan"
        fallback_used = actual_mode != self.requested_mode
        fallback_reason = self.model_error if fallback_used else None
        try:
            while True:
                try:
                    action = self._ppo_action(env, observation) if actual_mode == "ppo" else self._fixed_scan_action(env)
                except Exception as exc:
                    if actual_mode != "ppo":
                        raise
                    actual_mode = "fixed_scan"
                    fallback_used = True
                    fallback_reason = f"PPO运行时回退: {type(exc).__name__}: {exc}"
                    action = self._fixed_scan_action(env)
                observation, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break
            return ControllerReport(
                seed=seed,
                requested_mode=self.requested_mode,
                actual_mode=actual_mode,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                episode=env.core.report(),
            )
        finally:
            env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="路线C主控制器")
    parser.add_argument("--model", type=Path, default=None, help="混合训练PPO模型zip路径")
    parser.add_argument("--mode", choices=("ppo", "fixed_scan"), default="ppo")
    parser.add_argument("--seed", type=int, default=30001)
    parser.add_argument("--targets", type=int, default=16)
    parser.add_argument("--profile", default="uniform")
    parser.add_argument("--output", type=Path, default=Path("outputs/route_c/controller"))
    args = parser.parse_args()
    controller = RouteCController(
        config=RouteCConfig(target_count=args.targets, profile=args.profile),
        model_path=args.model,
        mode=args.mode,
    )
    report = controller.run_episode(args.seed)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, **asdict(report)}
    (output_dir / "controller_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
