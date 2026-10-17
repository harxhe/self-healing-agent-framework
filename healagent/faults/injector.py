"""Fault injector: wraps tools and models recovery-action success.

``observe`` performs a step call and, if the schedule fires, returns a faulted
``ToolResult`` with ``fault_injected`` set. ``apply_action`` models whether a
chosen recovery action clears the fault, according to the tool's profile:
actions listed in ``fixed_by`` clear it (a clean call is returned); anything
else lets the fault persist.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from healagent.core.interfaces import Tool
from healagent.core.types import Action, ToolResult

from .profiles import FaultProfile, default_profiles, get_profile
from .schedule import FaultDecision, FaultSchedule, validate_intensity
from .types import FaultContext, FaultKind, apply_fault


class FaultEvent(BaseModel):
    """A record of what the schedule decided for one step."""

    task_id: str
    step: int
    tool: str
    fires: bool
    fault: FaultKind | None = None


class FaultInjector:
    """Deterministic fault injection for one trial seed and intensity."""

    def __init__(
        self,
        trial_seed: int,
        intensity: float = 0.0,
        profiles: Mapping[tuple[str, FaultKind], FaultProfile] | None = None,
        forced_faults: Mapping[tuple[str, int], FaultKind] | None = None,
        allowed_faults: set[FaultKind] | None = None,
        fault_tools: set[str] | None = None,
    ) -> None:
        self.trial_seed = int(trial_seed)
        self.intensity = validate_intensity(intensity)
        self.schedule = FaultSchedule(self.trial_seed)
        self.profiles: dict[tuple[str, FaultKind], FaultProfile] = (
            dict(profiles) if profiles is not None else default_profiles()
        )
        self.forced_faults: dict[tuple[str, int], FaultKind] = dict(forced_faults or {})
        self.allowed_faults = None if allowed_faults is None else set(allowed_faults)
        self.fault_tools = None if fault_tools is None else set(fault_tools)

    def _decision(self, task_id, step, eligible_faults, recovery_attempt):
        forced = self.forced_faults.get((task_id, step))
        if forced is not None:
            return FaultDecision(fires=True, fault=forced)
        return self.schedule.decision(
            task_id, step, self.intensity, eligible_faults, recovery_attempt
        )

    def profile_for(self, tool: str, fault: FaultKind) -> FaultProfile:
        return get_profile(self.profiles, tool, fault)

    def action_succeeds(self, tool: str, fault: FaultKind, action: Action) -> bool:
        return self.profile_for(tool, fault).is_fixed_by(action)

    def observe(
        self,
        tool: Tool,
        args: dict[str, Any],
        task_id: str,
        step: int,
        eligible_faults: list[str] | tuple[str, ...],
        recovery_attempt: int = 0,
    ) -> ToolResult:
        base = tool.call(args)
        if self.fault_tools is not None and tool.name not in self.fault_tools:
            return base
        if self.allowed_faults is not None:
            eligible_faults = [
                name for name in eligible_faults
                if any(kind.value == name for kind in self.allowed_faults)
            ]
        decision = self._decision(task_id, step, eligible_faults, recovery_attempt)
        if not decision.fires or decision.fault is None:
            return base
        context = FaultContext(
            task_id=task_id,
            step=step,
            trial_seed=self.trial_seed,
            recovery_attempt=recovery_attempt,
            tool=tool.name,
            kind=decision.fault,
        )
        return apply_fault(base, decision.fault, context)

    def apply_action(
        self,
        tool: Tool,
        args: dict[str, Any],
        fault: FaultKind,
        action: Action,
        task_id: str,
        step: int,
        eligible_faults: list[str] | tuple[str, ...] | None = None,
        recovery_attempt: int = 1,
    ) -> ToolResult:
        profile = self.profile_for(tool.name, fault)
        if profile.is_fixed_by(action):
            return tool.call(args)
        context = FaultContext(
            task_id=task_id,
            step=step,
            trial_seed=self.trial_seed,
            recovery_attempt=recovery_attempt,
            tool=tool.name,
            kind=fault,
        )
        return apply_fault(tool.call(args), fault, context)

    def plan(
        self,
        task_id: str,
        steps: list[dict[str, Any]],
        eligible_faults: list[str] | tuple[str, ...],
        recovery_attempt: int = 0,
    ) -> list[FaultEvent]:
        """Return the deterministic fault decisions for every step of a task."""

        events: list[FaultEvent] = []
        for index, step in enumerate(steps, start=1):
            decision = self._decision(task_id, index, eligible_faults, recovery_attempt)
            events.append(
                FaultEvent(
                    task_id=task_id,
                    step=index,
                    tool=str(step.get("tool", "")),
                    fires=decision.fires,
                    fault=decision.fault,
                )
            )
        return events
