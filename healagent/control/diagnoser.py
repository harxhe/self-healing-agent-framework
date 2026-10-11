"""Diagnose stage: map a failure signal plus context to a ``Signature``.

The signature is the learning key: ``(failure_class, tool, attempt)``
(``implementation.md`` §3).
"""

from __future__ import annotations

from healagent.core.types import FailureClass, Signature

from .detector import FailureSignal, Signal

SIGNAL_TO_FAILURE_CLASS: dict[Signal, FailureClass] = {
    Signal.TIMEOUT: FailureClass.TIMEOUT,
    Signal.UNAVAILABLE: FailureClass.UNAVAILABLE,
    Signal.RATE_LIMIT: FailureClass.RATE_LIMIT,
    Signal.SCHEMA_VIOLATION: FailureClass.SCHEMA_ERROR,
    Signal.EMPTY_OUTPUT: FailureClass.PARTIAL_RESPONSE,
    Signal.PARTIAL_OUTPUT: FailureClass.PARTIAL_RESPONSE,
    Signal.MALFORMED_OUTPUT: FailureClass.MALFORMED_OUTPUT,
    Signal.STALE_OUTPUT: FailureClass.STALE_CONTEXT,
    Signal.VERIFIER_REJECTION: FailureClass.SEMANTIC_WRONG,
    Signal.REPEATED_ACTION: FailureClass.CONTROL_LOOP,
}


def failure_class_for(signal: Signal) -> FailureClass:
    return SIGNAL_TO_FAILURE_CLASS[signal]


def diagnose(signal: FailureSignal, tool: str, attempt: int) -> Signature:
    return Signature(
        failure_class=failure_class_for(signal.signal),
        tool=tool,
        attempt=max(1, int(attempt)),
    )
