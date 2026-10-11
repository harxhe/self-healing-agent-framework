"""StaticMapping baseline: the paper's failure-class -> action table.

Reference: Babu & Agrawal (2026), the fixed recovery mapping this project
improves on. Each class maps to an ordered action sequence; the signature's
``attempt`` advances the sequence and the feasibility mask filters infeasible
actions.
"""

from __future__ import annotations

from healagent.core.types import Action, FailureClass, Signature

STATIC_TABLE: dict[FailureClass, tuple[Action, ...]] = {
    FailureClass.TIMEOUT: (Action.RETRY, Action.SUBSTITUTE),
    FailureClass.UNAVAILABLE: (Action.SUBSTITUTE, Action.REPLAN),
    FailureClass.RATE_LIMIT: (Action.RETRY, Action.SUBSTITUTE),
    FailureClass.SCHEMA_ERROR: (Action.REPAIR,),
    FailureClass.MALFORMED_OUTPUT: (Action.REPAIR, Action.SUBSTITUTE),
    FailureClass.PARTIAL_RESPONSE: (Action.REPAIR, Action.REFRESH),
    FailureClass.STALE_CONTEXT: (Action.REFRESH,),
    FailureClass.CONTRADICTORY_EVIDENCE: (Action.REPLAN, Action.REPAIR),
    FailureClass.SEMANTIC_WRONG: (Action.REPAIR, Action.SUBSTITUTE),
    FailureClass.CONTROL_LOOP: (Action.REPLAN,),
}


class StaticMapping:
    name = "static"

    def select(self, signature: Signature, mask: set[Action]) -> Action:
        sequence = STATIC_TABLE.get(signature.failure_class, (Action.RETRY,))
        index = min(max(signature.attempt - 1, 0), len(sequence) - 1)
        ordered = list(sequence[index:]) + list(sequence[:index])
        for action in ordered:
            if action in mask:
                return action
        if mask:
            return sorted(mask, key=lambda action: action.value)[0]
        return Action.TERMINATE

    def update(self, signature: Signature, action: Action, reward: float) -> None:
        return None
