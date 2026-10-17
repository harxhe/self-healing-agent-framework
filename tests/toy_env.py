"""Small seeded recovery environment for bandit acceptance tests."""

from __future__ import annotations

from healagent.core.seed import SeedManager
from healagent.core.types import Action, FailureClass, Signature


class ToyEnvironment:
    def __init__(self, seed: int, rates: dict[Action, float], tool: str = "toy") -> None:
        self.rng = SeedManager(seed).rng("toy_environment")
        self.rates = rates
        self.signature = Signature(failure_class=FailureClass.TIMEOUT, tool=tool, attempt=1)

    def step(self, action: Action) -> tuple[bool, float]:
        success = bool(self.rng.random() < self.rates[action])
        return success, float(success)


def train(policy, environment: ToyEnvironment, episodes: int) -> dict[Action, int]:
    counts = {action: 0 for action in policy.actions}
    for _ in range(episodes):
        action = policy.select(environment.signature, set(policy.actions))
        success, reward = environment.step(action)
        policy.update(environment.signature, action, reward, success=success)
        counts[action] += 1
    return counts
