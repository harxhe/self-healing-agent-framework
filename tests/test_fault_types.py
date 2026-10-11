from __future__ import annotations

from healagent.faults.profiles import default_profiles
from healagent.faults.schedule import INTENSITY_LEVELS, validate_intensity
from healagent.faults.types import (
    HARD_FAULTS,
    SILENT_FAULTS,
    FaultContext,
    FaultKind,
    apply_fault,
)
from healagent.core.types import Action, ToolResult


def _base() -> ToolResult:
    return ToolResult(
        ok=True,
        output={"result": 10.0, "expression": "1+1", "customer_id": "C001"},
        latency_ms=5.0,
    )


def _context(kind: FaultKind, step: int = 1) -> FaultContext:
    return FaultContext(
        task_id="T001",
        step=step,
        trial_seed=0,
        recovery_attempt=0,
        tool="calculator",
        kind=kind,
    )


def test_hard_faults_fail_with_an_error() -> None:
    for kind in HARD_FAULTS:
        result = apply_fault(_base(), kind, _context(kind))
        assert result.ok is False
        assert result.error
        assert result.fault_injected == kind.value


def test_silent_faults_stay_ok_but_change_the_output() -> None:
    for kind in SILENT_FAULTS:
        result = apply_fault(_base(), kind, _context(kind))
        assert result.ok is True
        assert result.error is None
        assert result.fault_injected == kind.value
        assert result.output != _base().output


def test_timeout_inflates_latency() -> None:
    result = apply_fault(_base(), FaultKind.TIMEOUT, _context(FaultKind.TIMEOUT))
    assert result.latency_ms > _base().latency_ms + 1000


def test_fault_effect_is_deterministic() -> None:
    kind = FaultKind.SEMANTIC_WRONG
    first = apply_fault(_base(), kind, _context(kind))
    second = apply_fault(_base(), kind, _context(kind))
    assert first == second


def test_all_eight_fault_kinds_are_covered() -> None:
    assert len(FaultKind) == 8
    assert HARD_FAULTS | SILENT_FAULTS == set(FaultKind)


def test_validate_intensity_accepts_levels_and_rejects_others() -> None:
    for level in INTENSITY_LEVELS:
        assert validate_intensity(level) == level
    try:
        validate_intensity(0.25)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unsupported intensity")


def test_required_profiles_match_the_spec() -> None:
    profiles = default_profiles()
    assert profiles[("shipping_estimator", FaultKind.TIMEOUT)].persistence.value == "persistent"
    assert profiles[("customer_lookup", FaultKind.TIMEOUT)].persistence.value == "transient"
    assert profiles[("order_lookup", FaultKind.RATE_LIMIT)].persistence.value == "transient"
    assert profiles[("inventory_lookup", FaultKind.STALE_CONTEXT)].is_fixed_by(Action.REFRESH)
    assert profiles[("policy_lookup", FaultKind.PARTIAL_RESPONSE)].is_fixed_by(Action.REFRESH)
    assert not profiles[("policy_lookup", FaultKind.PARTIAL_RESPONSE)].is_fixed_by(Action.RETRY)
    assert profiles[("calculator", FaultKind.SEMANTIC_WRONG)].is_fixed_by(Action.REPAIR)
