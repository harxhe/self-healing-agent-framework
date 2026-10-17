from __future__ import annotations

import pytest

from healagent.core.types import Action
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.bandit import EpsilonGreedy, ThompsonSampling, UCB1
from toy_env import ToyEnvironment, train


@pytest.mark.parametrize("algorithm", [EpsilonGreedy, UCB1, ThompsonSampling])
@pytest.mark.parametrize("seed", [3, 17, 41])
def test_bandit_learns_best_toy_action(algorithm, seed: int) -> None:
    actions = [Action.RETRY, Action.SUBSTITUTE, Action.REFRESH]
    ledger = RecoveryLedger()
    options = {"epsilon": 0.15, "epsilon_min": 0.04, "epsilon_decay": 0.997} if algorithm is EpsilonGreedy else {}
    policy = algorithm(ledger, actions, seed=seed, **options)
    environment_a = ToyEnvironment(seed + 1, {
        Action.RETRY: 0.2,
        Action.SUBSTITUTE: 0.88,
        Action.REFRESH: 0.45,
    }, tool="toy-a")
    environment_b = ToyEnvironment(seed + 2, {
        Action.RETRY: 0.9,
        Action.SUBSTITUTE: 0.2,
        Action.REFRESH: 0.45,
    }, tool="toy-b")
    counts_a = train(policy, environment_a, 900)
    counts_b = train(policy, environment_b, 900)
    assert counts_a[Action.SUBSTITUTE] > counts_a[Action.RETRY]
    assert counts_a[Action.SUBSTITUTE] > counts_a[Action.REFRESH]
    assert counts_b[Action.RETRY] > counts_b[Action.SUBSTITUTE]
    assert counts_b[Action.RETRY] > counts_b[Action.REFRESH]
    assert policy.select(environment_a.signature, set(actions)) == Action.SUBSTITUTE
    assert policy.select(environment_b.signature, set(actions)) == Action.RETRY

