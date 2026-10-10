from __future__ import annotations

from collections import Counter

from healagent.tasks.catalog import load_tasks
from healagent.tasks.checker import check_answer
from healagent.tasks.executor import run_task


def test_task_catalog_has_100_tasks_across_five_categories() -> None:
    tasks = load_tasks()

    assert len(tasks) == 100
    assert Counter(task.category for task in tasks) == {
        "order_status": 20,
        "refund_eligibility": 20,
        "stock_and_shipping": 20,
        "multi_step_workflow": 20,
        "contradiction_resolution": 20,
    }
    assert all(task.plan for task in tasks)
    assert all(task.success_criteria["type"] == "exact_match" for task in tasks)
    assert all(task.eligible_faults for task in tasks)


def test_all_tasks_pass_with_zero_faults() -> None:
    for task in load_tasks():
        result = run_task(task)

        assert result.ok, (task.task_id, result.errors)
        assert check_answer(task, result.final_answer), task.task_id


def test_repeated_no_fault_runs_are_identical() -> None:
    tasks = load_tasks()

    first = [run_task(task).model_dump(mode="json") for task in tasks]
    second = [run_task(task).model_dump(mode="json") for task in tasks]

    assert first == second
