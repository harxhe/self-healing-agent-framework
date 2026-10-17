import pytest
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.bandit import EpsilonGreedyPolicy, UCB1Policy, ThompsonSamplingPolicy

def tf_actions():
    return ["retry", "substitute", "refresh", "escalate"]

def test_ledger_recording():
    ledger = RecoveryLedger(db_path=":memory:")
    ledger.record("sig_timeout", "retry", True, 1.0, 0.5)
    stats = ledger.get_arm_stats("sig_timeout", "retry")
    assert stats["count"] == 1
    assert stats["success_rate"] == 1.0

def test_ucb1_convergence():
    ledger = RecoveryLedger(db_path=":memory:")
    policy = UCB1Policy(ledger, tf_actions())
    sig = "sig_rate_limit"
    
    for _ in range(10):
        policy.update(sig, "substitute", True, 1.0, 0.2)
    for _ in range(10):
        policy.update(sig, "retry", False, 1.0, 0.5)

    selected = policy.select(sig, mask=["retry", "substitute"])
    assert selected == "substitute"

def test_thompson_sampling():
    ledger = RecoveryLedger(db_path=":memory:")
    policy = ThompsonSamplingPolicy(ledger, tf_actions())
    action = policy.select("sig_error")
    assert action in tf_actions()
