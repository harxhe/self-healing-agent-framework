"""Executable recovery actions (Recover stage).

Each action returns a new observation plus its cost-proxy and simulated
latency. ``retry`` uses exponential backoff; ``substitute`` routes to the
tool's backup; ``refresh`` re-fetches; ``replan`` restarts from a stable
checkpoint; ``degrade``/``escalate``/``terminate`` end the attempt
(``implementation.md`` P3-T3).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from healagent.core.interfaces import Tool
from healagent.core.types import Action, ToolResult
from healagent.faults.injector import FaultInjector
from healagent.faults.types import FaultKind
from healagent.tools.registry import SUBSTITUTES, get_tool

REPLAN_COST = 3.0
SUBSTITUTE_COST = 2.0
RETRY_COST = 1.0
REPAIR_COST = 1.0
REFRESH_COST = 1.2
DEGRADE_COST = 0.5


class ActionOutcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    action: Action
    result: ToolResult
    cost: float
    latency_ms: float
    succeeded: bool
    terminal: bool = False
    degraded: bool = False
    detail: str = ""


def is_clean(result: ToolResult) -> bool:
    return bool(result.ok) and result.fault_injected is None


def apply_recovery(
    action: Action,
    *,
    tool: Tool,
    args: dict,
    fault: FaultKind,
    injector: FaultInjector,
    task_id: str,
    step: int,
    eligible_faults: list[str] | tuple[str, ...] | None,
    recovery_attempt: int,
    registry: Mapping[str, Tool] | None = None,
    current_result: ToolResult | None = None,
) -> ActionOutcome:
    if action is Action.RETRY:
        latency = tool.latency_ms * (2 ** recovery_attempt)
        result = injector.apply_action(
            tool, args, fault, Action.RETRY, task_id, step, eligible_faults, recovery_attempt
        )
        result = result.model_copy(update={"latency_ms": latency})
        return ActionOutcome(
            action=action,
            result=result,
            cost=RETRY_COST,
            latency_ms=latency,
            succeeded=is_clean(result),
            detail="retry with exponential backoff",
        )

    if action is Action.REPAIR:
        latency = tool.latency_ms * 1.5
        result = injector.apply_action(
            tool, args, fault, Action.REPAIR, task_id, step, eligible_faults, recovery_attempt
        ).model_copy(update={"latency_ms": latency})
        return ActionOutcome(
            action=action,
            result=result,
            cost=REPAIR_COST,
            latency_ms=latency,
            succeeded=is_clean(result),
            detail="regenerate/fix arguments",
        )

    if action is Action.REFRESH:
        latency = tool.latency_ms * 1.1
        result = injector.apply_action(
            tool, args, fault, Action.REFRESH, task_id, step, eligible_faults, recovery_attempt
        ).model_copy(update={"latency_ms": latency})
        return ActionOutcome(
            action=action,
            result=result,
            cost=REFRESH_COST,
            latency_ms=latency,
            succeeded=is_clean(result),
            detail="re-fetch fresh/complete data",
        )

    if action is Action.REPLAN:
        latency = tool.latency_ms * 3.0
        result = injector.apply_action(
            tool, args, fault, Action.REPLAN, task_id, step, eligible_faults, recovery_attempt
        ).model_copy(update={"latency_ms": latency})
        return ActionOutcome(
            action=action,
            result=result,
            cost=REPLAN_COST,
            latency_ms=latency,
            succeeded=is_clean(result),
            detail="restart from last stable checkpoint",
        )

    if action is Action.SUBSTITUTE:
        return _substitute(tool, args, fault, injector, registry)

    if action is Action.DEGRADE:
        payload = {"degraded": True, "note": "partial result returned with uncertainty", "raw": None}
        if current_result is not None:
            payload["raw"] = current_result.output
        result = ToolResult(ok=True, output=payload, error=None, latency_ms=tool.latency_ms, fault_injected=None)
        return ActionOutcome(
            action=action,
            result=result,
            cost=DEGRADE_COST,
            latency_ms=tool.latency_ms,
            succeeded=False,
            terminal=True,
            degraded=True,
            detail="degrade with uncertainty notice",
        )

    if action is Action.ESCALATE:
        result = ToolResult(ok=False, error="escalated_to_human", latency_ms=0.0, fault_injected=None)
        return ActionOutcome(
            action=action, result=result, cost=0.0, latency_ms=0.0, succeeded=False, terminal=True
        )

    if action is Action.TERMINATE:
        result = ToolResult(ok=False, error="terminated", latency_ms=0.0, fault_injected=None)
        return ActionOutcome(
            action=action, result=result, cost=0.0, latency_ms=0.0, succeeded=False, terminal=True
        )

    raise ValueError(f"unsupported recovery action: {action}")


def _substitute(
    tool: Tool,
    args: dict,
    fault: FaultKind,
    injector: FaultInjector,
    registry: Mapping[str, Tool] | None,
) -> ActionOutcome:
    sub_name = SUBSTITUTES.get(tool.name)
    base_latency = tool.latency_ms * 1.6
    if sub_name is None:
        result = ToolResult(
            ok=False, error="no_substitute_available", latency_ms=base_latency, fault_injected=fault.value
        )
        return ActionOutcome(
            action=Action.SUBSTITUTE,
            result=result,
            cost=SUBSTITUTE_COST,
            latency_ms=base_latency,
            succeeded=False,
            detail="no backup tool registered",
        )

    substitute_tool = get_tool(sub_name, registry)
    raw = substitute_tool.call(args)
    result = ToolResult(
        ok=raw.ok,
        output=raw.output,
        error=raw.error,
        latency_ms=base_latency,
        fault_injected=None,
    )
    succeeded = injector.action_succeeds(tool.name, fault, Action.SUBSTITUTE) and raw.ok
    return ActionOutcome(
        action=Action.SUBSTITUTE,
        result=result,
        cost=SUBSTITUTE_COST,
        latency_ms=base_latency,
        succeeded=succeeded,
        detail=f"use {sub_name}",
    )
