"""Monitor/Detect stage: turn a :class:`ToolResult` plus execution state into a
failure signal (or ``None`` when the call looks healthy).

The detector works only from what a real monitor would see — ``ok``, ``error``,
the shape of ``output`` and the recent action history — never from the injected
``fault_injected`` field. ``semantic_wrong`` is invisible here and is caught
later by the oracle verifier.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from healagent.core.types import Action, ToolResult


class Signal(str, Enum):
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMIT = "rate_limit"
    SCHEMA_VIOLATION = "schema_violation"
    EMPTY_OUTPUT = "empty_output"
    PARTIAL_OUTPUT = "partial_output"
    MALFORMED_OUTPUT = "malformed_output"
    STALE_OUTPUT = "stale_output"
    VERIFIER_REJECTION = "verifier_rejection"
    REPEATED_ACTION = "repeated_action"


class FailureSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal: Signal
    detail: str = ""


EXPECTED_OUTPUT_KEYS: dict[str, frozenset[str]] = {
    "customer_lookup": frozenset({"customer_id", "name", "email", "zip", "tier"}),
    "order_lookup": frozenset(
        {"order_id", "customer_id", "items", "status", "order_date", "tracking_number", "shipping_zip", "subtotal"}
    ),
    "order_lookup_backup": frozenset(
        {"order_id", "customer_id", "items", "status", "order_date", "tracking_number", "shipping_zip", "subtotal"}
    ),
    "inventory_lookup": frozenset(
        {"sku", "name", "category", "weight", "price", "stock", "warehouse_zip"}
    ),
    "shipping_estimator": frozenset({"zip", "weight", "service", "estimated_days", "shipping_cost"}),
    "shipping_estimator_backup": frozenset(
        {"zip", "weight", "service", "estimated_days", "shipping_cost"}
    ),
    "policy_lookup": frozenset({"topic", "policy", "as_of"}),
    "calculator": frozenset({"expression", "result"}),
    "refund_calculator": frozenset({"expression", "result"}),
    "evidence_checker": frozenset({"claim", "supported", "resolved_value", "best_source", "confidence"}),
}


class DetectionContext(BaseModel):
    tool: str
    attempt: int = 0
    depth_limit: int = 3
    recent_actions: list[Action] = Field(default_factory=list)


def detect(result: ToolResult, context: DetectionContext) -> FailureSignal | None:
    """Return the first failure signal for ``result``, or ``None`` if healthy."""

    error_signal = _from_error(result.error)
    if error_signal is not None:
        return error_signal

    if not result.ok and result.error is None:
        return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail="ok=False without an error")

    output_signal = _from_output(result.output, context.tool)
    if output_signal is not None:
        return output_signal

    if _is_repeat_storm(context):
        return FailureSignal(signal=Signal.REPEATED_ACTION, detail="same action repeated without progress")

    return None


def _from_error(error: str | None) -> FailureSignal | None:
    if not error:
        return None
    lowered = error.lower()
    if lowered.startswith("timeout"):
        return FailureSignal(signal=Signal.TIMEOUT, detail=error)
    if "unavailable" in lowered:
        return FailureSignal(signal=Signal.UNAVAILABLE, detail=error)
    if "rate_limit" in lowered:
        return FailureSignal(signal=Signal.RATE_LIMIT, detail=error)
    if lowered.startswith("schema_error"):
        return FailureSignal(signal=Signal.SCHEMA_VIOLATION, detail=error)
    if lowered.startswith(("not_found", "invalid_request")):
        return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail=error)
    return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail=error)


def _from_output(output: object, tool: str) -> FailureSignal | None:
    if output is None:
        return FailureSignal(signal=Signal.EMPTY_OUTPUT, detail="empty output")
    if isinstance(output, (list, tuple, str)):
        if not output:
            return FailureSignal(signal=Signal.EMPTY_OUTPUT, detail="empty output")
        return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail="unexpected output shape")
    if not isinstance(output, dict):
        return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail="unexpected output type")
    if not output:
        return FailureSignal(signal=Signal.EMPTY_OUTPUT, detail="empty output")
    if output.get("stale") is True:
        return FailureSignal(signal=Signal.STALE_OUTPUT, detail="output flagged stale")
    expected = EXPECTED_OUTPUT_KEYS.get(tool)
    if expected:
        present = expected & set(output)
        if not present:
            return FailureSignal(signal=Signal.MALFORMED_OUTPUT, detail="missing all expected fields")
        if expected - set(output):
            missing = ", ".join(sorted(expected - set(output)))
            return FailureSignal(signal=Signal.PARTIAL_OUTPUT, detail=f"missing fields: {missing}")
    return None


def _is_repeat_storm(context: DetectionContext) -> bool:
    if context.depth_limit <= 0 or len(context.recent_actions) < context.depth_limit:
        return False
    window = context.recent_actions[-context.depth_limit :]
    return len(set(window)) == 1
