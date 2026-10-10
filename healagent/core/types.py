"""Shared enums, models, and dataclasses used across all phases.

These are the stable contracts every later phase depends on (see
``implementation.md`` §3). Keep changes backward compatible.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Action(str, Enum):
    """Recovery actions available to a policy."""

    RETRY = "retry"
    REPAIR = "repair"
    SUBSTITUTE = "substitute"
    REFRESH = "refresh"
    REPLAN = "replan"
    DEGRADE = "degrade"
    ESCALATE = "escalate"
    TERMINATE = "terminate"


class FailureClass(str, Enum):
    """Diagnosed failure classes."""

    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMIT = "rate_limit"
    SCHEMA_ERROR = "schema_error"
    MALFORMED_OUTPUT = "malformed_output"
    PARTIAL_RESPONSE = "partial_response"
    STALE_CONTEXT = "stale_context"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    SEMANTIC_WRONG = "semantic_wrong"
    CONTROL_LOOP = "control_loop"


class Signature(BaseModel):
    """Failure signature: the context key a policy learns over."""

    model_config = ConfigDict(frozen=True)

    failure_class: FailureClass
    tool: str
    attempt: int = 1


class ToolResult(BaseModel):
    """The outcome of a single tool call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ok: bool
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    fault_injected: str | None = None


class PlanStep(BaseModel):
    """One ordered tool call inside a task plan."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """A single simulated customer-support task."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    category: str
    request: str
    plan: list[PlanStep] = Field(default_factory=list)
    expected_answer: Any = None
    success_criteria: dict[str, Any] = Field(default_factory=dict)
    eligible_faults: list[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    """One JSONL trace line per executed step (or terminal event)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    task_id: str
    method: str
    seed: int
    episode: int
    step: int
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    fault_injected: str | None = None
    signal: str | None = None
    failure_class: str | None = None
    signature: Signature | None = None
    action: Action | None = None
    verifier_outcome: str | None = None
    budget_remaining: dict[str, float] = Field(default_factory=dict)
    cost: float = 0.0
    latency_ms: float = 0.0
    final_status: str | None = None
