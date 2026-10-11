"""Retry-Only baseline: always retry, then terminate."""

from __future__ import annotations

from healagent.core.types import Action, Signature


class RetryOnly:
    name = "retry_only"

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def select(self, signature: Signature, mask: set[Action]) -> Action:
        if Action.RETRY in mask:
            return Action.RETRY
        return Action.TERMINATE

    def update(self, signature: Signature, action: Action, reward: float) -> None:
        return None
