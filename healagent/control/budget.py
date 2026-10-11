"""Per-task recovery budget.

Tracks attempts, cost-proxy units, latency, and a recovery *depth* cap. Failed
recovery attempts still consume budget so a policy cannot loop forever
(``implementation.md`` P3-T5).
"""

from __future__ import annotations

from pydantic import BaseModel


class Budget(BaseModel):
    attempts: float
    cost: float
    latency_ms: float
    depth: int = 3

    max_attempts: float = 0.0
    max_cost: float = 0.0
    max_latency_ms: float = 0.0

    def model_post_init(self, __context: object) -> None:
        self.max_attempts = self.attempts
        self.max_cost = self.cost
        self.max_latency_ms = self.latency_ms

    def consume(self, cost: float, latency_ms: float, attempts: int = 1) -> None:
        self.attempts -= attempts
        self.cost -= cost
        self.latency_ms -= latency_ms

    def exhausted(self) -> bool:
        return self.attempts <= 0 or self.cost <= 0 or self.latency_ms <= 0

    def depth_exceeded(self, attempt: int) -> bool:
        return attempt >= self.depth

    def remaining(self) -> dict[str, float]:
        return {
            "attempts": round(self.attempts, 4),
            "cost": round(self.cost, 4),
            "latency_ms": round(self.latency_ms, 4),
        }

    def spent(self) -> dict[str, float]:
        return {
            "cost": round(self.max_cost - self.cost, 4),
            "latency_ms": round(self.max_latency_ms - self.latency_ms, 4),
        }
