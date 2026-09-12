import unittest

from questions.q3.shared.models import ActionSpec
from questions.q3.shared.candidates import Candidate
from questions.q3.method_c.hybrid import choose_hybrid


class FakeEnv:
    def __init__(self, candidates):
        self._candidates = tuple(candidates)
        self._hybrid_locked_channel = None

    def candidates(self):
        return self._candidates

    def action_masks(self):
        return [candidate.valid for candidate in self._candidates]


class HybridPolicyTests(unittest.TestCase):
    def test_clear_is_selected_before_scan(self):
        env = FakeEnv([
            Candidate(ActionSpec("scan", "SCAN", (100.0, 0.0), (1,), 0), 100.0, 1.0, 0.0, False, True),
            Candidate(ActionSpec("clear", "CLEAR", (2.0, 0.0), (2,)), 10.0, 0.0, 0.0, True, True),
        ])
        self.assertEqual(choose_hybrid(env, None), 1)

    def test_localization_is_locked_until_its_channel_is_finished(self):
        env = FakeEnv([
            Candidate(ActionSpec("localize-3", "LOCALIZE", (10.0, 0.0), (3,)), 10.0, 0.0, 1500.0, False, True),
            Candidate(ActionSpec("scan", "SCAN", (100.0, 0.0), (1,), 0), 100.0, 1.0, 0.0, False, True),
        ])
        self.assertEqual(choose_hybrid(env, None), 0)
        self.assertEqual(env._hybrid_locked_channel, 3)
        self.assertEqual(choose_hybrid(env, None), 0)


if __name__ == "__main__":
    unittest.main()
