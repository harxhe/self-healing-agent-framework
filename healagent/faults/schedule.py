"""Deterministic fault schedule.

Whether a fault fires at a step is a pure function of
``(task_id, step, trial_seed, intensity, recovery_attempt)``; which eligible
fault fires is a pure function of ``(task_id, step, trial_seed,
recovery_attempt, eligible_faults)``. Because nothing here depends on the
policy, **every policy sees exactly the same faults** for a given
``(task, seed, intensity)`` (``implementation.md`` P2-T3).
"""

from __future__ import annotations

from pydantic import BaseModel

from healagent.core.seed import SeedManager

from .types import FaultKind, eligible_fault_kinds

INTENSITY_LEVELS: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
PRIMARY_REGIME: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3)
STRESS_REGIME: tuple[float, ...] = (0.4, 0.5)


class FaultDecision(BaseModel):
    fires: bool
    fault: FaultKind | None = None


def validate_intensity(intensity: float) -> float:
    """Clamp-free validation: intensity must be one of the supported levels."""

    for level in INTENSITY_LEVELS:
        if abs(intensity - level) < 1e-9:
            return level
    raise ValueError(f"intensity {intensity} not in {INTENSITY_LEVELS}")


class FaultSchedule:
    """Deterministic, policy-independent fault schedule for one trial seed."""

    def __init__(self, trial_seed: int) -> None:
        self.trial_seed = int(trial_seed)

    def fires(
        self,
        task_id: str,
        step: int,
        intensity: float,
        recovery_attempt: int = 0,
    ) -> bool:
        if intensity <= 0.0:
            return False
        rng = SeedManager(self.trial_seed).rng("fault-schedule", task_id, step, recovery_attempt)
        return float(rng.random()) < intensity

    def choose_fault(
        self,
        task_id: str,
        step: int,
        eligible_faults: list[str] | tuple[str, ...],
        recovery_attempt: int = 0,
    ) -> FaultKind | None:
        kinds = eligible_fault_kinds(eligible_faults)
        if not kinds:
            return None
        rng = SeedManager(self.trial_seed).rng("fault-choice", task_id, step, recovery_attempt)
        return kinds[int(rng.integers(0, len(kinds)))]

    def decision(
        self,
        task_id: str,
        step: int,
        intensity: float,
        eligible_faults: list[str] | tuple[str, ...],
        recovery_attempt: int = 0,
    ) -> FaultDecision:
        if not self.fires(task_id, step, intensity, recovery_attempt):
            return FaultDecision(fires=False)
        fault = self.choose_fault(task_id, step, eligible_faults, recovery_attempt)
        if fault is None:
            return FaultDecision(fires=False)
        return FaultDecision(fires=True, fault=fault)
