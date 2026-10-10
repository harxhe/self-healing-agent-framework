"""Minimal dummy tool and policy used by the Phase 0 end-to-end smoke test.

These are placeholders only; the real environment and policies arrive in later
phases. They exist to prove the interfaces, seed manager, and trace logger fit
together.
"""

from __future__ import annotations

from .types import Action, Signature, ToolResult


class DummyTool:
    """Doubles its integer input; always succeeds."""

    name = "dummy"

    def call(self, args: dict) -> ToolResult:
        value = args.get("x", 0)
        return ToolResult(ok=True, output=value * 2, latency_ms=1.0)


class DummyPolicy:
    """Always prefers ``retry`` when feasible, otherwise the first masked action."""

    name = "dummy"

    def select(self, signature: Signature, mask: set[Action]) -> Action:
        if Action.RETRY in mask:
            return Action.RETRY
        return sorted(mask, key=lambda a: a.value)[0]

    def update(self, signature: Signature, action: Action, reward: float) -> None:
        return None
