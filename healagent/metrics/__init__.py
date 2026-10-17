"""Experiment metrics and paired confidence intervals."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from math import sqrt
from statistics import mean, stdev
from typing import Any

from scipy.stats import t


def task_metrics(
    *,
    correct: int,
    total: int,
    detected: int,
    recovered: int,
    silent: int,
    total_cost: float,
    total_latency_ms: float,
    cumulative_regret: float,
) -> dict[str, float]:
    """Calculate task success, recovery, silent-failure, and efficiency measures."""
    return {
        "tsr": correct / total if total else 0.0,
        "rsr": recovered / detected if detected else 1.0,
        "sfr": silent / total if total else 0.0,
        "mean_cost": total_cost / total if total else 0.0,
        "mean_latency_ms": total_latency_ms / total if total else 0.0,
        "cumulative_regret": cumulative_regret,
        "mean_regret": cumulative_regret / total if total else 0.0,
    }


def confidence_interval(values: Sequence[float], confidence: float = 0.95) -> tuple[float, float, float]:
    """Return mean and two-sided Student-t confidence bounds."""
    if not values:
        return 0.0, 0.0, 0.0
    center = mean(values)
    if len(values) == 1:
        return center, center, center
    margin = float(t.ppf((1.0 + confidence) / 2.0, len(values) - 1)) * stdev(values) / sqrt(len(values))
    return center, center - margin, center + margin


def summarize_by(
    rows: Sequence[Mapping[str, Any]],
    *,
    group_by: Sequence[str],
    metrics: Sequence[str],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(row[key] for key in group_by), []).append(row)
    summaries: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        summary: dict[str, Any] = dict(zip(group_by, key))
        summary["n"] = len(group)
        for metric in metrics:
            center, low, high = confidence_interval([float(row[metric]) for row in group])
            summary[metric] = center
            summary[f"{metric}_ci_low"] = low
            summary[f"{metric}_ci_high"] = high
        summaries.append(summary)
    return summaries


def paired_differences(
    rows: Sequence[Mapping[str, Any]],
    *,
    treatment: str,
    control: str,
    metric: str,
    pair_by: Sequence[str] = ("seed",),
) -> dict[str, float | int]:
    """Summarize treatment-minus-control differences for matched seeds/configs."""
    lookup = {
        tuple(row[key] for key in (*pair_by, "policy")): float(row[metric])
        for row in rows
    }
    differences = [
        lookup[(*key, treatment)] - lookup[(*key, control)]
        for key in sorted({tuple(row[key] for key in pair_by) for row in rows}, key=str)
        if (*key, treatment) in lookup and (*key, control) in lookup
    ]
    center, low, high = confidence_interval(differences)
    return {"n": len(differences), "mean_difference": center, "ci_low": low, "ci_high": high}


__all__ = ["confidence_interval", "paired_differences", "summarize_by", "task_metrics"]
