from __future__ import annotations

from collections.abc import Callable

from healagent.core.types import Action, PlanStep
from healagent.faults.injector import FaultInjector
from healagent.faults.types import FaultKind
from healagent.tasks.catalog import load_tasks
from healagent.tools.registry import default_registry, get_tool

TRIAL_SEED = 1234
INTENSITY = 0.4


def _plan(tasks, injector: FaultInjector):
    events = []
    for task in tasks:
        steps = [{"tool": step.tool} for step in task.plan]
        events.extend(injector.plan(task.task_id, steps, task.eligible_faults))
    return [(event.task_id, event.step, event.fault) for event in events]


def test_fault_plan_is_deterministic_across_instances() -> None:
    tasks = load_tasks()
    first = _plan(tasks, FaultInjector(TRIAL_SEED, INTENSITY))
    second = _plan(tasks, FaultInjector(TRIAL_SEED, INTENSITY))
    assert first == second
    assert any(fault is not None for _, _, fault in first)


def test_different_seeds_change_the_plan() -> None:
    tasks = load_tasks()
    a = _plan(tasks, FaultInjector(1, INTENSITY))
    b = _plan(tasks, FaultInjector(2, INTENSITY))
    assert a != b


def test_zero_intensity_injects_nothing() -> None:
    tasks = load_tasks()
    events = _plan(tasks, FaultInjector(TRIAL_SEED, 0.0))
    assert all(fault is None for _, _, fault in events)


def _initial_faults(
    tasks,
    choose_action: Callable[[PlanStep, FaultKind, int], Action],
):
    injector = FaultInjector(TRIAL_SEED, INTENSITY)
    registry = default_registry()
    seen = []
    for task in tasks:
        for step_index, step in enumerate(task.plan, start=1):
            tool = get_tool(step.tool, registry)
            result = injector.observe(
                tool, step.args, task.task_id, step_index, task.eligible_faults, 0
            )
            seen.append((task.task_id, step_index, result.fault_injected))
            if result.fault_injected is None:
                continue
            fault = FaultKind(result.fault_injected)
            attempt = 1
            while result.fault_injected is not None and attempt <= 3:
                action = choose_action(step, fault, attempt)
                result = injector.apply_action(
                    tool,
                    step.args,
                    fault,
                    action,
                    task.task_id,
                    step_index,
                    task.eligible_faults,
                    attempt,
                )
                if result.fault_injected is None:
                    break
                attempt += 1
    return seen


def test_two_different_policies_see_identical_faults() -> None:
    tasks = load_tasks()

    def retry_only(step: PlanStep, fault: FaultKind, attempt: int) -> Action:
        return Action.RETRY

    def substitute_only(step: PlanStep, fault: FaultKind, attempt: int) -> Action:
        return Action.SUBSTITUTE

    def mixed(step: PlanStep, fault: FaultKind, attempt: int) -> Action:
        return [Action.REFRESH, Action.REPLAN, Action.RETRY][attempt - 1]

    a = _initial_faults(tasks, retry_only)
    b = _initial_faults(tasks, substitute_only)
    c = _initial_faults(tasks, mixed)

    assert a == b == c
    assert any(fault is not None for _, _, fault in a)
