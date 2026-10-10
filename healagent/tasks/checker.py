"""Answer checker for deterministic task success criteria."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from healagent.core.types import Task


class CheckResult(BaseModel):
    ok: bool
    mismatches: list[str] = Field(default_factory=list)


def check_answer(task: Task, answer: Any) -> bool:
    return explain_check(task, answer).ok


def explain_check(task: Task, answer: Any) -> CheckResult:
    check_type = task.success_criteria.get("type", "exact_match")
    if check_type != "exact_match":
        return CheckResult(ok=False, mismatches=[f"unsupported check type: {check_type}"])

    if answer == task.expected_answer:
        return CheckResult(ok=True)

    return CheckResult(
        ok=False,
        mismatches=[
            f"expected {task.expected_answer!r}",
            f"got {answer!r}",
        ],
    )
