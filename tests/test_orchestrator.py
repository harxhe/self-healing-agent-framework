from __future__ import annotations

from pathlib import Path

from healagent.control.orchestrator import run_episode
from healagent.core.trace import TraceLogger
from healagent.core.types import Action
from healagent.faults.injector import FaultInjector
from healagent.faults.types import FaultKind
from healagent.policy import RetryOnly, StaticMapping
from healagent.tasks.catalog import load_tasks


def test_timeout_is_detected_diagnosed_recovered_verified_and_logged(tmp_path: Path) -> None:
    task = load_tasks()[0]
    injector = FaultInjector(0, 0.0, forced_faults={("T001", 1): FaultKind.TIMEOUT})
    logger = TraceLogger("orch-run", trace_dir=tmp_path)

    result = run_episode(task, StaticMapping(), injector, logger=logger, run_id="orch-run", seed=0)

    assert result.answer_correct
    assert result.detected_failures == 1
    assert result.recovered_failures == 1

    records = logger.read_all()
    recovery_records = [record for record in records if record.action is not None]
    assert recovery_records, "expected at least one recovery trace record"

    record = recovery_records[0]
    assert record.signal == "timeout"
    assert record.failure_class == "timeout"
    assert record.signature is not None
    assert record.action is Action.RETRY
    assert record.verifier_outcome == "pass"
    assert any(record.final_status == "success" for record in records)


def test_persistent_fault_recovers_via_substitute_and_verifies(tmp_path: Path) -> None:
    tasks = load_tasks()
    task = next(task for task in tasks if any(step.tool == "shipping_estimator" for step in task.plan))
    step_index = next(
        index for index, step in enumerate(task.plan, start=1) if step.tool == "shipping_estimator"
    )
    injector = FaultInjector(
        0, 0.0, forced_faults={(task.task_id, step_index): FaultKind.TIMEOUT}
    )
    logger = TraceLogger("sub-run", trace_dir=tmp_path)

    result = run_episode(task, StaticMapping(), injector, logger=logger, run_id="sub-run", seed=0)

    assert result.answer_correct
    actions = [record.action for record in logger.read_all() if record.action is not None]
    assert Action.RETRY in actions
    assert Action.SUBSTITUTE in actions


def test_budget_exhaustion_degrades_without_infinite_loop() -> None:
    tasks = load_tasks()
    task = next(task for task in tasks if any(step.tool == "shipping_estimator" for step in task.plan))
    step_index = next(
        index for index, step in enumerate(task.plan, start=1) if step.tool == "shipping_estimator"
    )
    injector = FaultInjector(
        0, 0.0, forced_faults={(task.task_id, step_index): FaultKind.TIMEOUT}
    )
    budget = {"attempts": 3.0, "cost": 50.0, "latency_ms": 30000.0, "depth": 2}

    result = run_episode(task, RetryOnly(), injector, seed=0, budget_config=budget)

    assert result.status in {"degraded", "failed"}
    assert result.answer_correct is False
    assert len(result.actions) <= 3
