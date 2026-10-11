"""Verify stage: an **oracle** verifier.

**This verifier is an oracle.** In simulation it knows the ground truth: it can
re-call a tool cleanly (bypassing faults) and compare against the task's
``success_criteria`` / ``expected_answer``. It is intentionally stronger than a
real-world verifier and must never be presented as a deployable component
(``implementation.md`` ground rule #4). Every call is counted for the cost
proxy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from healagent.core.interfaces import Tool
from healagent.core.types import Task, ToolResult
from healagent.tasks.checker import check_answer
from healagent.tools.registry import get_tool

from .detector import EXPECTED_OUTPUT_KEYS, FailureSignal, Signal


class VerificationResult(BaseModel):
    accepted: bool
    signal: FailureSignal | None = None


class Verifier:
    """Oracle verifier. Counts calls for the cost proxy."""

    def __init__(self) -> None:
        self.calls = 0

    def verify_step(
        self,
        tool_name: str,
        args: dict[str, Any],
        actual: ToolResult,
        registry: Mapping[str, Tool] | None = None,
    ) -> bool:
        """True if ``actual`` matches the ground-truth output of ``tool_name``."""

        self.calls += 1
        if not actual.ok:
            return False
        clean = get_tool(tool_name, registry).call(args)
        if not clean.ok:
            return True
        return _semantically_equal(tool_name, actual.output, clean.output)

    def verify_answer(self, task: Task, answer: Any) -> VerificationResult:
        """Oracle check of the final answer against the task's expected answer."""

        self.calls += 1
        if check_answer(task, answer):
            return VerificationResult(accepted=True)
        return VerificationResult(
            accepted=False,
            signal=FailureSignal(
                signal=Signal.VERIFIER_REJECTION,
                detail="final answer does not match success criteria",
            ),
        )

    def step_rejection_signal(self, detail: str = "step output deviates from ground truth") -> FailureSignal:
        return FailureSignal(signal=Signal.VERIFIER_REJECTION, detail=detail)


def _semantically_equal(tool_name: str, actual: Any, clean: Any) -> bool:
    keys = EXPECTED_OUTPUT_KEYS.get(tool_name)
    if not keys:
        return actual == clean
    if not isinstance(actual, dict) or not isinstance(clean, dict):
        return actual == clean
    for key in keys:
        if key not in actual or actual.get(key) != clean.get(key):
            return False
    return True
