import unittest

import numpy as np

from questions.q3.method_c.runtime.core import RouteCConfig
from questions.q3.method_c.runtime.env import GymRouteCEnv


class RouteCGymTests(unittest.TestCase):
    def test_reset_matches_declared_spaces(self):
        env = GymRouteCEnv(RouteCConfig(target_count=10))
        observation, _ = env.reset(seed=321)
        self.assertEqual(observation.shape, (757,))
        self.assertEqual(observation.dtype, np.float32)
        self.assertTrue(env.observation_space.contains(observation))
        self.assertEqual(env.action_masks().shape, (12,))
        self.assertTrue(env.action_masks().any())

    def test_random_valid_action_replay(self):
        env = GymRouteCEnv(RouteCConfig(target_count=10, max_steps=5))
        env.reset(seed=99)
        for _ in range(5):
            valid = np.flatnonzero(env.action_masks())
            self.assertGreater(len(valid), 0)
            action = int(valid[0])
            _, reward, terminated, truncated, info = env.step(action)
            self.assertIsInstance(reward, float)
            self.assertIn("action_id", info)
            if terminated or truncated:
                break


if __name__ == "__main__":
    unittest.main()
