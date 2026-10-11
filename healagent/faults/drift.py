"""Environment drift: swap a tool's fault profile at a chosen episode.

Drift is what breaks a *static* mapping: the action that used to fix a fault
stops working. The default event flips ``order_lookup`` rate limits so that
retry no longer helps and only ``substitute`` works (``implementation.md``
P2-T5).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from healagent.core.trace import TraceLogger
from healagent.core.types import Action, TraceRecord

from .profiles import FaultProfile, Persistence, default_profiles
from .types import FaultKind


class DriftEvent(BaseModel):
    """A single scheduled profile swap."""

    episode: int
    tool: str
    new_profile: str

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DriftEvent":
        return cls(
            episode=int(config["episode"]),
            tool=str(config["tool"]),
            new_profile=str(config["new_profile"]),
        )


DRIFT_PROFILES: dict[str, FaultProfile] = {
    "order_lookup_rate_limit_persistent": FaultProfile(
        tool="order_lookup",
        fault=FaultKind.RATE_LIMIT,
        persistence=Persistence.PERSISTENT,
        fixed_by=frozenset({Action.SUBSTITUTE}),
        note="post-drift: retry stops working, only substitute works",
    ),
}


def drift_event_from_config(config: dict[str, Any] | None) -> DriftEvent | None:
    if not config:
        return None
    return DriftEvent.from_config(config)


def due_drift_events(episode: int, events: list[DriftEvent]) -> list[DriftEvent]:
    return [event for event in events if event.episode == episode]


def resolve_drift_profile(name: str) -> FaultProfile:
    try:
        return DRIFT_PROFILES[name]
    except KeyError as exc:
        raise KeyError(f"unknown drift profile: {name}") from exc


def apply_drift(
    profiles: dict[tuple[str, FaultKind], FaultProfile],
    event: DriftEvent,
) -> dict[tuple[str, FaultKind], FaultProfile]:
    """Return a new profile registry with ``event`` applied."""

    new_profile = resolve_drift_profile(event.new_profile)
    updated = dict(profiles)
    updated[(event.tool, new_profile.fault)] = new_profile
    return updated


def initial_profiles() -> dict[tuple[str, FaultKind], FaultProfile]:
    return default_profiles()


def build_drift_record(
    run_id: str,
    event: DriftEvent,
    seed: int,
    episode: int,
    step: int = 0,
    method: str = "environment",
    budget_remaining: dict[str, float] | None = None,
) -> TraceRecord:
    """Build a trace record describing a drift event."""

    return TraceRecord(
        run_id=run_id,
        task_id="<drift>",
        method=method,
        seed=seed,
        episode=episode,
        step=step,
        tool=event.tool,
        fault_injected=event.new_profile,
        signal="drift",
        final_status="drift",
        budget_remaining=budget_remaining or {},
    )


def log_drift_event(
    logger: TraceLogger,
    run_id: str,
    event: DriftEvent,
    seed: int,
    episode: int,
    step: int = 0,
    method: str = "environment",
) -> TraceRecord:
    record = build_drift_record(run_id, event, seed, episode, step, method)
    logger.log(record)
    return record
