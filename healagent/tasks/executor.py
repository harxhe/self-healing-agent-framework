"""Plan executor for deterministic no-fault task runs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from healagent.core.interfaces import Tool
from healagent.core.types import Task, ToolResult
from healagent.tools.registry import default_registry, get_tool

from .answers import synthesize_answer


class StepObservation(BaseModel):
    step: int
    tool: str
    args: dict[str, Any]
    result: ToolResult


class ExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    observations: list[StepObservation] = Field(default_factory=list)
    final_answer: Any = None
    ok: bool = False
    errors: list[str] = Field(default_factory=list)
    cost: float = 0.0
    latency_ms: float = 0.0


def run_task(task: Task, registry: Mapping[str, Tool] | None = None) -> ExecutionResult:
    tools = registry or default_registry()
    observations: list[StepObservation] = []
    errors: list[str] = []
    total_latency = 0.0

    for step_index, step in enumerate(task.plan, start=1):
        try:
            tool = get_tool(step.tool, tools)
        except KeyError as exc:
            errors.append(str(exc))
            break

        result = tool.call(step.args)
        total_latency += result.latency_ms
        observations.append(
            StepObservation(
                step=step_index,
                tool=step.tool,
                args=step.args,
                result=result,
            )
        )
        if not result.ok:
            errors.append(result.error or f"{step.tool} failed")
            break

    final_answer = None
    if not errors:
        try:
            final_answer = synthesize_answer(task, _outputs_by_tool(observations))
        except ValueError as exc:
            errors.append(str(exc))

    return ExecutionResult(
        task_id=task.task_id,
        observations=observations,
        final_answer=final_answer,
        ok=not errors,
        errors=errors,
        cost=float(len(observations)),
        latency_ms=total_latency,
    )


def _outputs_by_tool(observations: list[StepObservation]) -> dict[str, list[dict[str, Any]]]:
    outputs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        if observation.result.ok:
            outputs[observation.tool].append(observation.result.output)
    return dict(outputs)
