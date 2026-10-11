"""Per-tool fault profiles.

A profile describes, for one ``(tool, fault)`` pair, whether the fault is
**transient** (retrying tends to clear it) or **persistent** (retrying does not
help), and exactly which recovery actions actually fix it. The profiles are the
*environment*: they are deliberately non-flat so that a fixed failure→action
mapping (the paper's ``StaticMapping``) is sometimes wrong and a learned policy
can do better (``implementation.md`` ground rule #3).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from healagent.core.types import Action

from .types import FaultKind


class Persistence(str, Enum):
    TRANSIENT = "transient"
    PERSISTENT = "persistent"


class FaultProfile(BaseModel):
    """Behaviour of a single ``(tool, fault)`` pair."""

    model_config = ConfigDict(frozen=True)

    tool: str
    fault: FaultKind
    persistence: Persistence
    fixed_by: frozenset[Action]
    note: str = ""

    def is_fixed_by(self, action: Action) -> bool:
        return action in self.fixed_by


_DEFAULTS: dict[FaultKind, tuple[Persistence, frozenset[Action]]] = {
    FaultKind.TIMEOUT: (Persistence.TRANSIENT, frozenset({Action.RETRY, Action.SUBSTITUTE})),
    FaultKind.UNAVAILABLE: (Persistence.PERSISTENT, frozenset({Action.SUBSTITUTE, Action.REPLAN})),
    FaultKind.RATE_LIMIT: (Persistence.TRANSIENT, frozenset({Action.RETRY})),
    FaultKind.SCHEMA_ERROR: (Persistence.TRANSIENT, frozenset({Action.REPAIR})),
    FaultKind.MALFORMED_OUTPUT: (Persistence.TRANSIENT, frozenset({Action.REPAIR, Action.REPLAN})),
    FaultKind.PARTIAL_RESPONSE: (Persistence.TRANSIENT, frozenset({Action.REFRESH, Action.REPAIR})),
    FaultKind.STALE_CONTEXT: (Persistence.TRANSIENT, frozenset({Action.REFRESH})),
    FaultKind.SEMANTIC_WRONG: (Persistence.PERSISTENT, frozenset({Action.REPAIR})),
}

_REQUIRED: tuple[FaultProfile, ...] = (
    FaultProfile(
        tool="shipping_estimator",
        fault=FaultKind.TIMEOUT,
        persistence=Persistence.PERSISTENT,
        fixed_by=frozenset({Action.SUBSTITUTE}),
        note="retry never clears it; the backup estimator does",
    ),
    FaultProfile(
        tool="customer_lookup",
        fault=FaultKind.TIMEOUT,
        persistence=Persistence.TRANSIENT,
        fixed_by=frozenset({Action.RETRY}),
        note="retry is enough and cheapest",
    ),
    FaultProfile(
        tool="policy_lookup",
        fault=FaultKind.PARTIAL_RESPONSE,
        persistence=Persistence.PERSISTENT,
        fixed_by=frozenset({Action.REFRESH}),
        note="needs a fresh/complete fetch, not a retry",
    ),
    FaultProfile(
        tool="calculator",
        fault=FaultKind.SEMANTIC_WRONG,
        persistence=Persistence.PERSISTENT,
        fixed_by=frozenset({Action.REPAIR, Action.SUBSTITUTE}),
        note="verifier-driven regenerate or substitute only",
    ),
    FaultProfile(
        tool="inventory_lookup",
        fault=FaultKind.STALE_CONTEXT,
        persistence=Persistence.PERSISTENT,
        fixed_by=frozenset({Action.REFRESH}),
        note="refresh clears stale stock data",
    ),
    FaultProfile(
        tool="order_lookup",
        fault=FaultKind.RATE_LIMIT,
        persistence=Persistence.TRANSIENT,
        fixed_by=frozenset({Action.RETRY}),
        note="retry-with-backoff works until drift",
    ),
)


def default_profile_for(tool: str, fault: FaultKind) -> FaultProfile:
    persistence, fixed_by = _DEFAULTS[fault]
    return FaultProfile(tool=tool, fault=fault, persistence=persistence, fixed_by=fixed_by)


def default_profiles() -> dict[tuple[str, FaultKind], FaultProfile]:
    profiles: dict[tuple[str, FaultKind], FaultProfile] = {}
    for profile in _REQUIRED:
        profiles[(profile.tool, profile.fault)] = profile
    return profiles


def get_profile(
    profiles: dict[tuple[str, FaultKind], FaultProfile] | None,
    tool: str,
    fault: FaultKind,
) -> FaultProfile:
    if profiles is not None:
        found = profiles.get((tool, fault))
        if found is not None:
            return found
    return default_profile_for(tool, fault)


def action_fixes(profile: FaultProfile, action: Action) -> bool:
    return profile.is_fixed_by(action)
