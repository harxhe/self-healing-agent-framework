from __future__ import annotations

from healagent.metrics import confidence_interval, paired_differences, task_metrics


def test_confidence_interval_contains_sample_mean() -> None:
    mean, low, high = confidence_interval([0.2, 0.4, 0.6, 0.8])
    assert low <= mean <= high
    assert mean == 0.5


def test_paired_differences_match_by_seed() -> None:
    rows = [
        {"seed": 1, "policy": "static", "tsr": 0.7},
        {"seed": 1, "policy": "bandit", "tsr": 0.8},
        {"seed": 2, "policy": "static", "tsr": 0.6},
        {"seed": 2, "policy": "bandit", "tsr": 0.6},
    ]
    result = paired_differences(rows, treatment="bandit", control="static", metric="tsr")
    assert result["n"] == 2
    assert abs(result["mean_difference"] - 0.05) < 1e-12


def test_silent_failure_rate_uses_all_completed_tasks() -> None:
    metrics = task_metrics(
        correct=90,
        total=100,
        detected=10,
        recovered=8,
        silent=10,
        total_cost=120,
        total_latency_ms=400,
        cumulative_regret=2,
    )
    assert metrics["sfr"] == 0.1
