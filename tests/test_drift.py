from __future__ import annotations

from pathlib import Path

from healagent.core.trace import TraceLogger
from healagent.core.types import Action
from healagent.faults.drift import (
    DriftEvent,
    apply_drift,
    drift_event_from_config,
    log_drift_event,
)
from healagent.faults.injector import FaultInjector
from healagent.faults.profiles import Persistence, default_profiles
from healagent.faults.types import FaultKind
from healagent.tools.registry import get_tool

O001 = {"order_id": "O001"}
RATE_LIMIT = FaultKind.RATE_LIMIT


def test_before_drift_retry_fixes_order_lookup_rate_limit() -> None:
    injector = FaultInjector(0, 0.0)
    profile = injector.profile_for("order_lookup", RATE_LIMIT)

    assert profile.persistence is Persistence.TRANSIENT
    assert injector.action_succeeds("order_lookup", RATE_LIMIT, Action.RETRY)
    assert not injector.action_succeeds("order_lookup", RATE_LIMIT, Action.SUBSTITUTE)

    tool = get_tool("order_lookup")
    result = injector.apply_action(tool, O001, RATE_LIMIT, Action.RETRY, "T001", 1)
    assert result.fault_injected is None
    assert result.ok


def test_after_drift_retry_fails_and_substitute_works() -> None:
    event = DriftEvent(
        episode=30,
        tool="order_lookup",
        new_profile="order_lookup_rate_limit_persistent",
    )
    profiles = apply_drift(default_profiles(), event)
    injector = FaultInjector(0, 0.0, profiles)
    profile = injector.profile_for("order_lookup", RATE_LIMIT)

    assert profile.persistence is Persistence.PERSISTENT
    assert not injector.action_succeeds("order_lookup", RATE_LIMIT, Action.RETRY)
    assert injector.action_succeeds("order_lookup", RATE_LIMIT, Action.SUBSTITUTE)

    tool = get_tool("order_lookup")
    retried = injector.apply_action(tool, O001, RATE_LIMIT, Action.RETRY, "T001", 1)
    assert retried.fault_injected == RATE_LIMIT.value
    assert not retried.ok

    substituted = injector.apply_action(tool, O001, RATE_LIMIT, Action.SUBSTITUTE, "T001", 1)
    assert substituted.fault_injected is None
    assert substituted.ok


def test_drift_event_from_config() -> None:
    event = drift_event_from_config(
        {"episode": 30, "tool": "order_lookup", "new_profile": "order_lookup_rate_limit_persistent"}
    )
    assert event == DriftEvent(
        episode=30, tool="order_lookup", new_profile="order_lookup_rate_limit_persistent"
    )
    assert drift_event_from_config(None) is None


def test_drift_event_is_logged_to_trace(tmp_path: Path) -> None:
    logger = TraceLogger("drift-run", trace_dir=tmp_path)
    event = DriftEvent(
        episode=30,
        tool="order_lookup",
        new_profile="order_lookup_rate_limit_persistent",
    )
    record = log_drift_event(logger, "drift-run", event, seed=0, episode=30)

    assert record.final_status == "drift"
    assert record.tool == "order_lookup"
    assert record.fault_injected == "order_lookup_rate_limit_persistent"

    stored = logger.read_all()
    assert len(stored) == 1
    assert stored[0].signal == "drift"
