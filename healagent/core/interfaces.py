"""Core structural interfaces every tool and policy must satisfy.

Defined exactly as in ``implementation.md`` §3. These are ``Protocol`` types so
implementations do not need to inherit from them (structural typing).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import Action, Signature, ToolResult


@runtime_checkable
class Tool(Protocol):
    """A callable tool exposed to the agent."""

    name: str

    def call(self, args: dict) -> ToolResult: ...


@runtime_checkable
class Policy(Protocol):
    """A recovery policy mapping failure signatures to actions."""

    name: str

    def select(self, signature: Signature, mask: set[Action]) -> Action: ...

    def update(self, signature: Signature, action: Action, reward: float) -> None: ...
