import unittest

from q3_common.route_c.core import RouteCConfig, RouteCEnv
from q3_common.route_c.features import FeatureSchema, encode_observation


class RouteCFeatureTests(unittest.TestCase):
    def test_feature_dimension_and_finite_values(self):
        env = RouteCEnv(config=RouteCConfig(target_count=10))
        observation, _ = env.reset(seed=123)
        features = encode_observation(observation)
        self.assertEqual(len(features), FeatureSchema().dimension)
        self.assertTrue(all(value == value and abs(value) < float("inf") for value in features))

    def test_encoder_does_not_need_hidden_sources(self):
        env = RouteCEnv(config=RouteCConfig(target_count=10))
        observation, _ = env.reset(seed=456)
        self.assertNotIn("sources", observation)
        self.assertEqual(len(encode_observation(observation)), 757)


if __name__ == "__main__":
    unittest.main()
