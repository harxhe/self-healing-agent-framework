"""Orchestrator: the Monitor -> Detect -> Diagnose -> Recover -> Verify loop.

Follows Algorithm 1 of the paper (``implementation.md`` §0/P3-T6). For each plan
step it observes the tool, detects failures, diagnoses a signature, asks the
policy for an action under the feasibility mask, applies it, verifies the
result against ground truth, updates the policy, and logs a trace record. The
episode ends when every step is resolved or the per-task budget is exhausted
(then the unresolved step is degraded or escalated — never looped forever).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from healagent.core.interfaces import Policy, Tool
from healagent.core.trace import TraceLogger
from healagent.core.types import Action, TraceRecord, ToolResult
from healagent.faults.injector import FaultInjector
from healagent.faults.types import FaultKind
from healagent.policy.reward import recovery_reward
from healagent.tasks.answers import synthesize_answer
from healagent.tools.registry import default_registry, get_tool

from .detector import DetectionContext, Signal, detect
from .diagnoser import diagnose
from .actions import apply_recovery, is_clean
from .budget import Budget
from .mask import feasible_actions
from .verifier import Verifier

SIGNAL_TO_FAULT: dict[Signal, FaultKind] = {
    Signal.TIMEOUT: FaultKind.TIMEOUT,
    Signal.UNAVAILABLE: FaultKind.UNAVAILABLE,
    Signal.RATE_LIMIT: FaultKind.RATE_LIMIT,
    Signal.SCHEMA_VIOLATION: FaultKind.SCHEMA_ERROR,
    Signal.EMPTY_OUTPUT: FaultKind.PARTIAL_RESPONSE,
    Signal.PARTIAL_OUTPUT: FaultKind.PARTIAL_RESPONSE,
    Signal.MALFORMED_OUTPUT: FaultKind.MALFORMED_OUTPUT,
    Signal.STALE_OUTPUT: FaultKind.STALE_CONTEXT,
    Signal.VERIFIER_REJECTION: FaultKind.SEMANTIC_WRONG,
}

DEFAULT_BUDGET: dict[str, float] = {
    "attempts": 6.0,
    "cost": 50.0,
    "latency_ms": 30000.0,
    "depth": 3.0,
}


class StepReport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step: int
    tool: str
    status: str
    detected: bool = False
    attempts: int = 0
    signal: str | None = None
    actions: list[str] = Field(default_factory=list)
    result: ToolResult | None = None
    action_cost: float = 0.0
    action_latency_ms: float = 0.0


class EpisodeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    method: str
    seed: int
    episode: int
    status: str
    ok: bool
    final_answer: Any = None
    answer_correct: bool = False
    detected_failures: int = 0
    recovered_failures: int = 0
    silent_failures: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    verifier_calls: int = 0
    actions: list[str] = Field(default_factory=list)
    steps: list[StepReport] = Field(default_factory=list)


def run_episode(
    task,
    policy: Policy,
    injector: FaultInjector,
    *,
    registry: Mapping[str, Tool] | None = None,
    logger: TraceLogger | None = None,
    run_id: str = "run",
    seed: int = 0,
    episode: int = 0,
    lam: float = 0.05,
    mu: float = 0.01,
    budget_config: Mapping[str, float] | None = None,
) -> EpisodeResult:
    tools = registry or default_registry()
    verifier = Verifier()
    budget = _make_budget(budget_config)

    method = getattr(policy, "name", policy.__class__.__name__)
    records: list[TraceRecord] = []
    steps: list[StepReport] = []
    step_outputs: dict[str, list[dict[str, Any]]] = {}
    detected = recovered = 0
    episode_cost = 0.0
    episode_latency = 0.0
    all_actions: list[str] = []
    any_degraded = False

    for step_index, step in enumerate(task.plan, start=1):
        tool = get_tool(step.tool, tools)
        result = injector.observe(
            tool, step.args, task.task_id, step_index, task.eligible_faults, 0
        )
        episode_cost += 1.0
        episode_latency += result.latency_ms

        report = _resolve_step(
            task=task,
            step=step,
            step_index=step_index,
            tool=tool,
            initial=result,
            policy=policy,
            injector=injector,
            verifier=verifier,
            budget=budget,
            tools=tools,
            method=method,
            run_id=run_id,
            seed=seed,
            episode=episode,
            lam=lam,
            mu=mu,
            records=records,
        )

        steps.append(report)
        episode_cost += report.action_cost
        episode_latency += report.action_latency_ms
        if report.detected:
            detected += 1
            if report.status == "recovered":
                recovered += 1
        all_actions.extend(report.actions)
        if report.status == "degraded":
            any_degraded = True

        final_result = report.result
        if final_result is not None and is_clean(final_result):
            step_outputs.setdefault(step.tool, []).append(final_result.output)

    episode_cost += verifier.calls

    final_answer = _synthesize(task, step_outputs)
    verification = verifier.verify_answer(task, final_answer)
    answer_correct = verification.accepted

    if answer_correct:
        status = "success"
    elif any_degraded:
        status = "degraded"
    else:
        status = "failed"

    silent_failures = 1 if (not answer_correct and detected == 0) else 0

    result = EpisodeResult(
        task_id=task.task_id,
        method=method,
        seed=seed,
        episode=episode,
        status=status,
        ok=answer_correct,
        final_answer=final_answer,
        answer_correct=answer_correct,
        detected_failures=detected,
        recovered_failures=recovered,
        silent_failures=silent_failures,
        cost=round(episode_cost, 4),
        latency_ms=round(episode_latency, 4),
        verifier_calls=verifier.calls,
        actions=all_actions,
        steps=steps,
    )

    if logger is not None:
        records.append(_terminal_record(result, run_id, seed, episode, len(task.plan) + 1, method, budget))
        for record in records:
            logger.log(record)

    return result


def _resolve_step(
    *,
    task,
    step,
    step_index: int,
    tool: Tool,
    initial: ToolResult,
    policy: Policy,
    injector: FaultInjector,
    verifier: Verifier,
    budget: Budget,
    tools: Mapping[str, Tool],
    method: str,
    run_id: str,
    seed: int,
    episode: int,
    lam: float,
    mu: float,
    records: list[TraceRecord],
) -> StepReport:
    result = initial
    recent_actions: list[Action] = []
    attempt = 0
    current_fault: FaultKind | None = None
    actions: list[str] = []
    action_cost = 0.0
    action_latency = 0.0
    detected = False
    signal_value: str | None = None

    while True:
        context = DetectionContext(
            tool=step.tool, attempt=attempt, depth_limit=budget.depth, recent_actions=recent_actions
        )
        signal = detect(result, context)
        if signal is None and not verifier.verify_step(step.tool, step.args, result, tools):
            signal = verifier.step_rejection_signal()
        if signal is None:
            status = "recovered" if detected else "clean"
            return _step_report(
                step_index, step.tool, status, detected, attempt, signal_value, actions,
                result, action_cost, action_latency,
            )

        detected = True
        signal_value = signal.signal.value
        current_fault = SIGNAL_TO_FAULT.get(signal.signal, current_fault)
        signature = diagnose(signal, step.tool, attempt + 1)

        if budget.exhausted() or budget.depth_exceeded(attempt) or current_fault is None:
            fallback = Action.DEGRADE if current_fault is not None else Action.ESCALATE
            outcome = apply_recovery(
                fallback,
                tool=tool,
                args=step.args,
                fault=current_fault or FaultKind.MALFORMED_OUTPUT,
                injector=injector,
                task_id=task.task_id,
                step=step_index,
                eligible_faults=task.eligible_faults,
                recovery_attempt=attempt + 1,
                registry=tools,
                current_result=result,
            )
            budget.consume(outcome.cost, outcome.latency_ms)
            action_cost += outcome.cost
            action_latency += outcome.latency_ms
            actions.append(fallback.value)
            records.append(
                _attempt_record(
                    run_id, task, method, seed, episode, step_index, step.tool, step.args,
                    result.fault_injected or (current_fault.value if current_fault else None),
                    signal, signature, fallback, outcome, budget,
                )
            )
            status = "degraded" if outcome.degraded else "failed"
            return _step_report(
                step_index, step.tool, status, detected, attempt, signal_value, actions,
                outcome.result, action_cost, action_latency,
            )

        mask = feasible_actions(signature, step.tool)
        action = policy.select(signature, mask)
        outcome = apply_recovery(
            action,
            tool=tool,
            args=step.args,
            fault=current_fault,
            injector=injector,
            task_id=task.task_id,
            step=step_index,
            eligible_faults=task.eligible_faults,
            recovery_attempt=attempt + 1,
            registry=tools,
            current_result=result,
        )
        attempt += 1
        budget.consume(outcome.cost, outcome.latency_ms)
        action_cost += outcome.cost
        action_latency += outcome.latency_ms
        actions.append(action.value)
        reward = recovery_reward(outcome.succeeded, outcome.cost, outcome.latency_ms, lam, mu)
        policy.update(signature, action, reward)
        if not outcome.succeeded:
            recent_actions.append(action)
        result = outcome.result

        records.append(
            _attempt_record(
                run_id, task, method, seed, episode, step_index, step.tool, step.args,
                result.fault_injected or current_fault.value, signal, signature, action, outcome, budget,
            )
        )

        if outcome.terminal:
            status = "degraded" if outcome.degraded else "failed"
            return _step_report(
                step_index, step.tool, status, detected, attempt, signal_value, actions,
                result, action_cost, action_latency,
            )


def _step_report(
    step, tool, status, detected, attempts, signal, actions, result, action_cost, action_latency
) -> StepReport:
    return StepReport(
        step=step,
        tool=tool,
        status=status,
        detected=detected,
        attempts=attempts,
        signal=signal,
        actions=actions,
        result=result,
        action_cost=round(action_cost, 4),
        action_latency_ms=round(action_latency, 4),
    )


def _attempt_record(
    run_id, task, method, seed, episode, step_index, tool_name, args, fault_injected,
    signal, signature, action, outcome, budget,
) -> TraceRecord:
    return TraceRecord(
        run_id=run_id,
        task_id=task.task_id,
        method=method,
        seed=seed,
        episode=episode,
        step=step_index,
        tool=tool_name,
        args=args,
        fault_injected=fault_injected,
        signal=signal.signal.value,
        failure_class=signature.failure_class.value,
        signature=signature,
        action=action,
        verifier_outcome="pass" if outcome.succeeded else "fail",
        budget_remaining=budget.remaining(),
        cost=round(outcome.cost, 4),
        latency_ms=round(outcome.latency_ms, 4),
    )


def _terminal_record(result, run_id, seed, episode, step, method, budget) -> TraceRecord:
    return TraceRecord(
        run_id=run_id,
        task_id=result.task_id,
        method=method,
        seed=seed,
        episode=episode,
        step=step,
        verifier_outcome="pass" if result.answer_correct else "fail",
        budget_remaining=budget.remaining(),
        cost=round(result.cost, 4),
        latency_ms=round(result.latency_ms, 4),
        final_status=result.status,
    )


def _make_budget(config: Mapping[str, float] | None) -> Budget:
    merged = dict(DEFAULT_BUDGET)
    if config:
        merged.update({key: float(value) for key, value in config.items() if value is not None})
    return Budget(
        attempts=merged["attempts"],
        cost=merged["cost"],
        latency_ms=merged["latency_ms"],
        depth=int(merged["depth"]),
    )


def _synthesize(task, step_outputs) -> Any:
    try:
        return synthesize_answer(task, step_outputs)
    except (ValueError, KeyError, TypeError):
        return None
