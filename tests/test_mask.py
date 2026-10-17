from __future__ import annotations

import pytest

from healagent.core.types import Action, FailureClass, Signature
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.bandit import EpsilonGreedy, ThompsonSampling, UCB1


@pytest.mark.parametrize("algorithm", [EpsilonGreedy, UCB1, ThompsonSampling])
def test_bandit_never_selects_outside_mask(algorithm) -> None:
    policy = algorithm(
        RecoveryLedger(),
        [Action.RETRY, Action.SUBSTITUTE, Action.REFRESH],
        seed=5,
        **({"epsilon": 1.0} if algorithm is EpsilonGreedy else {}),
    )
    signature = Signature(failure_class=FailureClass.TIMEOUT, tool="shipping_estimator", attempt=1)
    mask = {Action.SUBSTITUTE}
    assert {policy.select(signature, mask) for _ in range(50)} == mask


def test_empty_mask_returns_terminal_action() -> None:
    policy = UCB1(RecoveryLedger(), [Action.RETRY], seed=5)
    signature = Signature(failure_class=FailureClass.TIMEOUT, tool="calculator", attempt=1)
    assert policy.select(signature, set()) == Action.TERMINATE
