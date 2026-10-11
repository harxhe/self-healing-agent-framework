"""Reward for a recovery attempt.

``r = success - lambda * cost - mu * latency`` (``implementation.md`` §3), with
``cost`` the call-count proxy and ``latency`` the simulated latency in seconds
so the two terms stay comparable for the configured defaults.
"""

from __future__ import annotations


def recovery_reward(
    success: bool,
    cost: float,
    latency_ms: float,
    lam: float = 0.05,
    mu: float = 0.01,
) -> float:
    return float(bool(success)) - lam * float(cost) - mu * (float(latency_ms) / 1000.0)
