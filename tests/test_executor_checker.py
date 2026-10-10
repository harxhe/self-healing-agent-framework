from __future__ import annotations

from healagent.core.types import PlanStep, Task
from healagent.tasks.checker import check_answer, explain_check
from healagent.tasks.executor import run_task


def test_executor_runs_order_status_plan() -> None:
    task = Task(
        task_id="inline-order-status",
        category="order_status",
        request="What is the status of order O001?",
        plan=[PlanStep(tool="order_lookup", args={"order_id": "O001"})],
        expected_answer={
            "order_id": "O001",
            "status": "delivered",
            "tracking_number": "TRK00000001",
            "eta_date": None,
            "delivered_date": "2026-01-15",
        },
        success_criteria={"type": "exact_match"},
        eligible_faults=["timeout"],
    )

    result = run_task(task)

    assert result.ok
    assert result.cost == 1.0
    assert check_answer(task, result.final_answer)


def test_checker_reports_exact_mismatch() -> None:
    task = Task(
        task_id="inline-check",
        category="order_status",
        request="Check mismatch",
        expected_answer={"status": "delivered"},
        success_criteria={"type": "exact_match"},
    )

    result = explain_check(task, {"status": "processing"})

    assert not result.ok
    assert result.mismatches
