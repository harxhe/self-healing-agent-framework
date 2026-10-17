"""Discounted and windowed arm statistics for recovery policies."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class ArmStats:
    n: int = 0
    successes: int = 0
    mean_reward: float = 0.0
    success_rate: float = 0.0

    @property
    def count(self) -> int:
        return self.n

    @property
    def recent_reward(self) -> float:
        return self.mean_reward

    def as_dict(self) -> dict[str, int | float]:
        result = asdict(self)
        result.update(count=self.n, recent_reward=self.mean_reward)
        return result


def aggregate_arm_stats(
    observations: Iterable[tuple[bool, float]],
    *,
    gamma: float = 1.0,
    window: int | None = None,
) -> ArmStats:
    """Aggregate oldest-to-newest observations, weighting newer evidence more."""
    items = list(observations)
    if window is not None:
        items = items[-window:]
    if not items:
        return ArmStats()

    weights = [gamma ** (len(items) - index - 1) for index in range(len(items))]
    weight_sum = sum(weights)
    reward = sum(value * weight for (_, value), weight in zip(items, weights)) / weight_sum
    success = sum(float(ok) * weight for (ok, _), weight in zip(items, weights)) / weight_sum
    return ArmStats(
        n=len(items),
        successes=sum(int(ok) for ok, _ in items),
        mean_reward=reward,
        success_rate=success,
    )
