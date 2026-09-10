"""路线C的Gymnasium适配层。

环境只负责把独立的RouteCEnv核心转换成Gymnasium接口，动作选择不调用路线B。
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from q3_common.route_c.core import RouteCConfig, RouteCEnv
from q3_common.route_c.features import FeatureSchema, encode_observation


class GymRouteCEnv(gym.Env[np.ndarray, np.int64]):
    metadata = {"render_modes": []}

    def __init__(self, config: RouteCConfig | None = None, schema: FeatureSchema | None = None) -> None:
        super().__init__()
        self.core = RouteCEnv(config=config)
        self.schema = schema or FeatureSchema()
        self.action_space = spaces.Discrete(12)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.schema.dimension,),
            dtype=np.float32,
        )

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        observation, info = self.core.reset(seed=seed, options=options)
        return np.asarray(encode_observation(observation, self.schema), dtype=np.float32), info

    def action_masks(self) -> np.ndarray:
        return np.asarray(self.core.action_masks(), dtype=bool)

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        observation, reward, terminated, truncated, info = self.core.step(int(action))
        encoded = np.asarray(encode_observation(observation, self.schema), dtype=np.float32)
        return encoded, float(reward), bool(terminated), bool(truncated), info

    def close(self) -> None:
        return None

