"""Feasibility mask: which recovery actions are allowed for a signature.

Keeps policies from choosing impossible actions, e.g. ``substitute`` for a tool
with no backup, or ``refresh`` for a pure-computation tool
(``implementation.md`` P3-T7).
"""

from __future__ import annotations

from collections.abc import Mapping

from healagent.core.types import Action, FailureClass, Signature
from healagent.tools.registry import SUBSTITUTES

REFRESHABLE_TOOLS: frozenset[str] = frozenset(
    {
        "customer_lookup",
        "order_lookup",
        "order_lookup_backup",
        "inventory_lookup",
        "shipping_estimator",
        "shipping_estimator_backup",
        "policy_lookup",
    }
)

COMPUTATION_TOOLS: frozenset[str] = frozenset(
    {"calculator", "refund_calculator", "evidence_checker"}
)

TERMINAL_ACTIONS: frozenset[Action] = frozenset({Action.DEGRADE, Action.ESCALATE, Action.TERMINATE})


def feasible_actions(
    signature: Signature,
    tool: str,
    substitutes: Mapping[str, str] | None = None,
) -> set[Action]:
    sub_map = substitutes if substitutes is not None else SUBSTITUTES

    if signature.failure_class is FailureClass.CONTROL_LOOP:
        actions: set[Action] = {Action.REPLAN}
        if tool in sub_map:
            actions.add(Action.SUBSTITUTE)
        return actions

    actions = {Action.RETRY, Action.REPAIR, Action.REPLAN}
    if tool in sub_map:
        actions.add(Action.SUBSTITUTE)
    if tool in REFRESHABLE_TOOLS and tool not in COMPUTATION_TOOLS:
        actions.add(Action.REFRESH)
    return actions


def has_substitute(tool: str, substitutes: Mapping[str, str] | None = None) -> bool:
    sub_map = substitutes if substitutes is not None else SUBSTITUTES
    return tool in sub_map
