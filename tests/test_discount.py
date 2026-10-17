from __future__ import annotations

from healagent.core.types import Action, FailureClass, Signature
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.bandit import EpsilonGreedy


def test_discounted_policy_tracks_a_flipped_best_action() -> None:
    signature = Signature(failure_class=FailureClass.TIMEOUT, tool="toy", attempt=1)
    actions = [Action.RETRY, Action.SUBSTITUTE]
    discounted_ledger = RecoveryLedger(discount_factor=0.5)
    stationary_ledger = RecoveryLedger(discount_factor=1.0)
    discounted = EpsilonGreedy(discounted_ledger, actions, epsilon=0, epsilon_min=0, seed=1)
    stationary = EpsilonGreedy(stationary_ledger, actions, epsilon=0, epsilon_min=0, seed=1)

    for _ in range(12):
        for policy in (discounted, stationary):
            policy.update(signature, Action.RETRY, 1.0, success=True)
            policy.update(signature, Action.SUBSTITUTE, 0.0, success=False)
    for _ in range(5):
        for policy in (discounted, stationary):
            policy.update(signature, Action.RETRY, 0.0, success=False)
            policy.update(signature, Action.SUBSTITUTE, 1.0, success=True)

    assert discounted.select(signature, set(actions)) == Action.SUBSTITUTE
    assert stationary.select(signature, set(actions)) == Action.RETRY
