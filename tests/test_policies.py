from __future__ import annotations

from pathlib import Path

from healagent.control.mask import feasible_actions
from healagent.control.orchestrator import run_episode
from healagent.core.trace import TraceLogger
from healagent.core.types import Action, FailureClass, Signature
from healagent.faults.injector import FaultInjector
from healagent.policy import RetryOnly, StaticMapping
from healagent.tasks.catalog import load_tasks

BUDGET = {"attempts": 8.0, "cost": 60.0, "latency_ms": 40000.0, "depth": 3}
SEEDS = (0, 1, 2)


def _tsr(policy, intensity: float, tasks) -> float:
    correct = 0
    total = 0
    for seed in SEEDS:
        injector = FaultInjector(seed, intensity)
        for task in tasks:
            result = run_episode(task, policy, injector, seed=seed, budget_config=BUDGET)
            correct += int(result.answer_correct)
            total += 1
    return correct / total


def test_zero_intensity_reaches_full_tsr_for_all_policies() -> None:
    tasks = load_tasks()
    assert _tsr(RetryOnly(), 0.0, tasks) == 1.0
    assert _tsr(StaticMapping(), 0.0, tasks) == 1.0


def test_static_mapping_beats_retry_only_at_moderate_intensity() -> None:
    tasks = load_tasks()
    for intensity in (0.2, 0.3):
        retry = _tsr(RetryOnly(), intensity, tasks)
        static = _tsr(StaticMapping(), intensity, tasks)
        assert static > retry, (intensity, static, retry)
        assert static > 0.9
        assert retry < 0.85


def test_traces_exist_for_both_policies(tmp_path: Path) -> None:
    task = load_tasks()[0]
    for name, policy in (("retry", RetryOnly()), ("static", StaticMapping())):
        injector = FaultInjector(0, 0.2)
        logger = TraceLogger(name, trace_dir=tmp_path)
        run_episode(task, policy, injector, logger=logger, run_id=name, seed=0)
        assert logger.path.exists()
        assert logger.read_all()


def test_feasibility_mask_rules() -> None:
    signature = Signature(failure_class=FailureClass.TIMEOUT, tool="shipping_estimator", attempt=1)

    shipping = feasible_actions(signature, "shipping_estimator")
    assert Action.SUBSTITUTE in shipping
    assert Action.REFRESH in shipping

    calculator = feasible_actions(
        Signature(failure_class=FailureClass.SCHEMA_ERROR, tool="calculator", attempt=1), "calculator"
    )
    assert Action.SUBSTITUTE in calculator
    assert Action.REFRESH not in calculator

    evidence = feasible_actions(
        Signature(failure_class=FailureClass.SEMANTIC_WRONG, tool="evidence_checker", attempt=1),
        "evidence_checker",
    )
    assert Action.SUBSTITUTE not in evidence
    assert Action.REFRESH not in evidence
    assert Action.REPAIR in evidence
