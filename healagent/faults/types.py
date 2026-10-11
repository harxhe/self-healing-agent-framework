"""Fault kinds and their deterministic transformations of a ``ToolResult``.

Each fault kind represents a different way a tool call can go wrong. Most are
*hard* failures (``ok=False``); ``malformed_output``, ``partial_response``,
``stale_context`` and ``semantic_wrong`` are *silent* failures (``ok=True``)
that only a detector/verifier can catch. Every transformation is seeded so the
same ``(task, step, trial_seed, recovery_attempt, fault)`` always produces the
same faulted result (``implementation.md`` ground rule #1).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from healagent.core.seed import SeedManager
from healagent.core.types import FailureClass, ToolResult


class FaultKind(str, Enum):
    """The eight injectable, tool-result fault types."""

    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMIT = "rate_limit"
    SCHEMA_ERROR = "schema_error"
    MALFORMED_OUTPUT = "malformed_output"
    PARTIAL_RESPONSE = "partial_response"
    STALE_CONTEXT = "stale_context"
    SEMANTIC_WRONG = "semantic_wrong"


HARD_FAULTS: frozenset[FaultKind] = frozenset(
    {FaultKind.TIMEOUT, FaultKind.UNAVAILABLE, FaultKind.RATE_LIMIT, FaultKind.SCHEMA_ERROR}
)
SILENT_FAULTS: frozenset[FaultKind] = frozenset(
    {
        FaultKind.MALFORMED_OUTPUT,
        FaultKind.PARTIAL_RESPONSE,
        FaultKind.STALE_CONTEXT,
        FaultKind.SEMANTIC_WRONG,
    }
)

FAULT_TO_FAILURE_CLASS: dict[FaultKind, FailureClass] = {
    kind: FailureClass(kind.value) for kind in FaultKind
}
FAILURE_CLASS_TO_FAULT: dict[FailureClass, FaultKind] = {
    failure_class: kind for kind, failure_class in FAULT_TO_FAILURE_CLASS.items()
}

FAULT_KIND_VALUES: frozenset[str] = frozenset(kind.value for kind in FaultKind)


class FaultContext(BaseModel):
    """Everything needed to reproduce a single faulted tool call."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    step: int
    trial_seed: int
    recovery_attempt: int = 0
    tool: str
    kind: FaultKind


def to_failure_class(kind: FaultKind) -> FailureClass:
    return FAULT_TO_FAILURE_CLASS[kind]


def eligible_fault_kinds(eligible_faults: list[str] | tuple[str, ...]) -> list[FaultKind]:
    """Keep only eligible entries that name an injectable fault kind."""

    kinds = {FaultKind(value) for value in eligible_faults if value in FAULT_KIND_VALUES}
    return sorted(kinds, key=lambda kind: kind.value)


def apply_fault(base: ToolResult, kind: FaultKind, context: FaultContext) -> ToolResult:
    """Return a faulted copy of ``base`` for ``kind`` (deterministic in context)."""

    rng = SeedManager(context.trial_seed).rng(
        "fault-effect",
        context.task_id,
        context.step,
        context.recovery_attempt,
        context.tool,
        kind.value,
    )

    if kind is FaultKind.TIMEOUT:
        latency = base.latency_ms + 4000.0 + float(rng.integers(0, 500))
        return base.model_copy(
            update={"ok": False, "output": None, "error": "timeout", "latency_ms": latency, "fault_injected": kind.value}
        )
    if kind is FaultKind.UNAVAILABLE:
        return base.model_copy(
            update={"ok": False, "output": None, "error": "service_unavailable", "fault_injected": kind.value}
        )
    if kind is FaultKind.RATE_LIMIT:
        return base.model_copy(
            update={"ok": False, "output": None, "error": "rate_limit_exceeded", "fault_injected": kind.value}
        )
    if kind is FaultKind.SCHEMA_ERROR:
        return base.model_copy(
            update={
                "ok": False,
                "output": None,
                "error": "schema_error: malformed arguments",
                "fault_injected": kind.value,
            }
        )
    if kind is FaultKind.MALFORMED_OUTPUT:
        return base.model_copy(
            update={"ok": True, "output": _malformed(rng), "error": None, "fault_injected": kind.value}
        )
    if kind is FaultKind.PARTIAL_RESPONSE:
        return base.model_copy(
            update={"ok": True, "output": _partial(base.output, rng), "error": None, "fault_injected": kind.value}
        )
    if kind is FaultKind.STALE_CONTEXT:
        return base.model_copy(
            update={"ok": True, "output": _stale(base.output, rng), "error": None, "fault_injected": kind.value}
        )
    if kind is FaultKind.SEMANTIC_WRONG:
        return base.model_copy(
            update={"ok": True, "output": _semantic_wrong(base.output, rng), "error": None, "fault_injected": kind.value}
        )
    raise ValueError(f"unsupported fault kind: {kind}")


def _as_mapping(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        return dict(output)
    return {"value": output}


def _numeric_keys(data: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key, value in data.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def _string_keys(data: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in data.items() if isinstance(value, str))


def _malformed(rng: Any) -> dict[str, Any]:
    payloads = [
        {"raw": "unparseable_payload", "truncated": True},
        {"error_code": 500, "detail": None},
        ["unexpected", "list", "shape"],
    ]
    return payloads[int(rng.integers(0, len(payloads)))]


def _partial(output: Any, rng: Any) -> dict[str, Any]:
    data = _as_mapping(output)
    keys = sorted(data)
    if len(keys) <= 1:
        return {"partial": True}
    drop_count = 1 + int(rng.integers(0, max(1, len(keys) - 1)))
    for key in keys[-drop_count:]:
        data.pop(key, None)
    return data


def _stale(output: Any, rng: Any) -> dict[str, Any]:
    data = _as_mapping(output)
    numeric = _numeric_keys(data)
    if numeric:
        key = numeric[int(rng.integers(0, len(numeric)))]
        data[key] = round(float(data[key]) * 0.5, 2)
    data["stale"] = True
    return data


def _semantic_wrong(output: Any, rng: Any) -> dict[str, Any]:
    data = _as_mapping(output)
    numeric = _numeric_keys(data)
    if numeric:
        key = numeric[int(rng.integers(0, len(numeric)))]
        delta = float(rng.choice([-1.0, 1.0])) * float(1 + int(rng.integers(1, 4)))
        data[key] = round(float(data[key]) + delta, 2)
        return data
    string_keys = _string_keys(data)
    if string_keys:
        key = string_keys[int(rng.integers(0, len(string_keys)))]
        data[key] = "unknown"
        return data
    data["result"] = "unknown"
    return data
