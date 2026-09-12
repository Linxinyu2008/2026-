"""确定性混合调度器：优先清除，短期锁定定位，并按时间收益选择扫描。"""

from __future__ import annotations

from typing import Any


def _valid(env: Any) -> list[int]:
    return [i for i, ok in enumerate(env.action_masks()) if ok]


def _kind(env: Any, i: int) -> str | None:
    action = env.candidates()[i].action
    return action.kind if action is not None else None


def choose_hybrid(env: Any, rng: Any = None) -> int:
    del rng
    valid = _valid(env)
    candidates = env.candidates()

    clear = [i for i in valid if _kind(env, i) == "CLEAR"]
    if clear:
        return min(clear, key=lambda i: candidates[i].estimated_time_s)

    locked = getattr(env, "_hybrid_locked_channel", None)
    if locked is not None:
        locked_localize = [
            i for i in valid
            if _kind(env, i) == "LOCALIZE" and candidates[i].action.channels == (locked,)
        ]
        if locked_localize:
            return min(locked_localize, key=lambda i: candidates[i].estimated_time_s)
        env._hybrid_locked_channel = None

    localize = [i for i in valid if _kind(env, i) == "LOCALIZE"]
    scans = [i for i in valid if _kind(env, i) == "SCAN"]
    best_scan_time = min((candidates[i].estimated_time_s for i in scans), default=float("inf"))
    if localize:
        best_localize = max(
            localize,
            key=lambda i: candidates[i].localization_gain / (1.0 + candidates[i].estimated_time_s),
        )
        # Continue a nearby localization task; otherwise keep moving toward the scan route.
        if candidates[best_localize].estimated_time_s <= 1.25 * best_scan_time:
            env._hybrid_locked_channel = candidates[best_localize].action.channels[0]
            return best_localize

    if scans:
        return max(
            scans,
            key=lambda i: len(candidates[i].action.channels) / (1.0 + candidates[i].estimated_time_s),
        )
    if localize:
        env._hybrid_locked_channel = localize[0].action.channels[0]
        return min(localize, key=lambda i: candidates[i].estimated_time_s)
    return valid[0]
