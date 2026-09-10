import unittest

from q3_common.public.config import Rules
from q3_common.route_c.core import RouteCConfig, RouteCEnv


class RouteCCoreTests(unittest.TestCase):
    def test_reset_creates_twelve_cached_candidates_without_hidden_truth(self):
        env = RouteCEnv(Rules(), RouteCConfig(target_count=10))
        observation, info = env.reset(seed=123)
        self.assertEqual(len(env.candidates()), 12)
        self.assertEqual(len(env.action_masks()), 12)
        self.assertNotIn("sources", observation)
        self.assertEqual(info["candidate_version"], 1)

    def test_step_uses_cached_index_and_returns_contract(self):
        env = RouteCEnv(Rules(), RouteCConfig(target_count=10))
        observation, _ = env.reset(seed=7)
        valid = next(index for index, allowed in enumerate(env.action_masks()) if allowed)
        old_version = observation["candidate_version"]
        next_observation, reward, terminated, truncated, info = env.step(valid)
        self.assertIsInstance(reward, float)
        self.assertFalse(terminated and truncated)
        self.assertIn("action_id", info)
        if not (terminated or truncated):
            self.assertGreater(next_observation["candidate_version"], old_version)

    def test_step_after_end_is_rejected(self):
        env = RouteCEnv(Rules(), RouteCConfig(target_count=10, max_steps=1))
        env.reset(seed=7)
        valid = next(index for index, allowed in enumerate(env.action_masks()) if allowed)
        env.step(valid)
        with self.assertRaises(RuntimeError):
            env.step(valid)

    def test_reset_without_seed_generates_a_new_training_scenario(self):
        env = RouteCEnv(Rules(), RouteCConfig(target_count=10, profile="mixed"))
        env.reset(seed=10001)
        first = env.scenario
        env.reset()
        self.assertNotEqual(env.scenario, first)

    def test_report_uses_actual_random_target_count(self):
        env = RouteCEnv(Rules(), RouteCConfig(target_count=None, max_steps=1))
        env.reset(seed=7)
        valid = next(index for index, allowed in enumerate(env.action_masks()) if allowed)
        env.step(valid)
        self.assertGreaterEqual(env.report().target_count, 10)
        self.assertLessEqual(env.report().target_count, 16)


if __name__ == "__main__":
    unittest.main()
