"""Seeded tabular bandit policies backed by the recovery ledger."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from healagent.core.seed import SeedManager
from healagent.core.types import Action, Signature
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.static import STATIC_TABLE


class BaseBanditPolicy:
    name = "bandit"

    def __init__(
        self,
        ledger: RecoveryLedger,
        actions: Sequence[Action | str],
        *,
        seed: int = 0,
        warm_start: bool = False,
        use_mask: bool = True,
        use_cost_term: bool = True,
        prior_count: int = 2,
    ) -> None:
        self.ledger = ledger
        self.actions = tuple(_as_action(action) for action in actions)
        self.seed_manager = SeedManager(seed)
        self.rng = self.seed_manager.rng("policy", self.name)
        self.warm_start = warm_start
        self.use_mask = use_mask
        self.use_cost_term = use_cost_term
        self.prior_count = prior_count
        self.selections = 0

    def _valid_actions(self, mask: set[Action] | set[str]) -> list[Action]:
        if not self.use_mask:
            return list(self.actions)
        allowed = {_as_action(item) for item in mask}
        return [action for action in self.actions if action in allowed]

    def _stats(self, signature: Signature, action: Action) -> dict[str, float | int]:
        stats = self.ledger.get_arm_stats(signature, action.value)
        if self.warm_start and stats["count"] == 0:
            preferred = _static_prior(signature)
            if action == preferred:
                count = self.prior_count
                return {
                    "count": count,
                    "successes": count,
                    "success_rate": 1.0,
                    "mean_reward": 1.0,
                    "recent_reward": 1.0,
                }
        if not self.use_cost_term and stats["count"]:
            success_rate = float(stats["success_rate"])
            stats["mean_reward"] = success_rate
            stats["recent_reward"] = success_rate
        return stats

    def update(
        self,
        signature: Signature | str,
        action: Action | str,
        reward: float,
        *legacy_cost_latency: float,
        success: bool | None = None,
        cost: float = 0.0,
        latency: float = 0.0,
        run_id: str = "",
        episode: int = 0,
    ) -> None:
        if legacy_cost_latency:
            success = bool(reward) if success is None else success
            cost = float(legacy_cost_latency[0])
            latency = float(legacy_cost_latency[1]) if len(legacy_cost_latency) > 1 else 0.0
            reward = float(success) - 0.1 * cost - 0.05 * latency
        self.update_observation(
            signature,
            action,
            reward,
            success=success,
            cost=cost,
            latency=latency,
            run_id=run_id,
            episode=episode,
        )

    def update_observation(
        self,
        signature: Signature | str,
        action: Action | str,
        reward: float,
        *,
        success: bool | None = None,
        cost: float = 0.0,
        latency: float = 0.0,
        run_id: str = "",
        episode: int = 0,
    ) -> None:
        self.ledger.log(
            run_id=run_id,
            episode=episode,
            signature=signature,
            action=_as_action(action).value,
            success=(reward > 0.0 if success is None else success),
            cost=cost,
            latency=latency,
            reward=reward,
        )

    def select(self, signature: Signature | str, mask: set[Action] | set[str] | None = None) -> Action:
        raise NotImplementedError


class EpsilonGreedy(BaseBanditPolicy):
    def __init__(
        self,
        ledger: RecoveryLedger,
        actions: Sequence[Action | str],
        *,
        epsilon: float = 0.1,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
        **kwargs: Any,
    ) -> None:
        super().__init__(ledger, actions, **kwargs)
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

    def select(self, signature: Signature | str, mask: set[Action] | set[str] | None = None) -> Action:
        mask = set(self.actions) if mask is None else mask
        valid = self._valid_actions(mask)
        self.selections += 1
        if not valid:
            return Action.TERMINATE
        epsilon_now = max(self.epsilon_min, self.epsilon * self.epsilon_decay ** (self.selections - 1))
        if self.rng.random() < epsilon_now:
            return valid[int(self.rng.integers(len(valid)))]
        return max(valid, key=lambda action: float(self._stats(signature, action)["recent_reward"]))


class UCB1(BaseBanditPolicy):
    def select(self, signature: Signature | str, mask: set[Action] | set[str] | None = None) -> Action:
        mask = set(self.actions) if mask is None else mask
        valid = self._valid_actions(mask)
        if not valid:
            return Action.TERMINATE
        counts = {action: int(self._stats(signature, action)["count"]) for action in valid}
        untried = [action for action in valid if counts[action] == 0]
        if untried:
            return untried[0]
        total = sum(counts.values())
        return max(
            valid,
            key=lambda action: float(self._stats(signature, action)["recent_reward"])
            + math.sqrt(2.0 * math.log(max(total, 1)) / counts[action]),
        )


class ThompsonSampling(BaseBanditPolicy):
    """Beta posterior over success; cost affects reward-based algorithms only."""

    def select(self, signature: Signature | str, mask: set[Action] | set[str] | None = None) -> Action:
        mask = set(self.actions) if mask is None else mask
        valid = self._valid_actions(mask)
        if not valid:
            return Action.TERMINATE
        samples: dict[Action, float] = {}
        for action in valid:
            stats = self._stats(signature, action)
            successes = int(stats.get("successes", 0))
            count = int(stats["count"])
            failures = max(0, count - successes)
            samples[action] = float(
                self.rng.beta(1.0 + successes, 1.0 + failures)
            )
        return max(valid, key=samples.__getitem__)


def build_bandit_policy(
    config: Mapping[str, Any] | str | None = None,
    ledger: RecoveryLedger | None = None,
    actions: Sequence[Action | str] | None = None,
    **overrides: Any,
) -> BaseBanditPolicy:
    """Build a policy from a runner config or explicit algorithm name."""
    root = dict(config) if isinstance(config, Mapping) else {}
    policy_config = root.get("policy", {})
    if isinstance(policy_config, str):
        policy_config = {"algorithm": policy_config}
    else:
        policy_config = dict(policy_config)
    if isinstance(config, str):
        policy_config["algorithm"] = config
    policy_config.update(overrides)
    algorithm = str(
        policy_config.get("algorithm", policy_config.get("name", "epsilon_greedy"))
    ).lower()
    discount = float(policy_config.get("discount", 1.0))
    window = policy_config.get("window")
    ledger = ledger or RecoveryLedger(
        root.get("ledger_path", ":memory:"),
        discount_factor=discount,
        window=None if window is None else int(window),
    )
    chosen_actions = actions or list(Action)
    common = {
        "seed": int(root.get("seed", 0)),
        "warm_start": str(policy_config.get("start", "cold")).lower() == "warm",
        "use_mask": bool(policy_config.get("use_mask", True)),
        "use_cost_term": bool(policy_config.get("use_cost_term", True)),
        "prior_count": int(policy_config.get("prior_count", 2)),
    }
    if "epsilon" in algorithm or algorithm in {"eps", "epsilon_greedy"}:
        return EpsilonGreedy(
            ledger,
            chosen_actions,
            epsilon=float(policy_config.get("epsilon", 0.1)),
            epsilon_min=float(policy_config.get("epsilon_min", 0.01)),
            epsilon_decay=float(policy_config.get("epsilon_decay", 0.995)),
            **common,
        )
    if "ucb" in algorithm:
        return UCB1(ledger, chosen_actions, **common)
    if "thompson" in algorithm or algorithm in {"ts", "thompson_sampling"}:
        return ThompsonSampling(ledger, chosen_actions, **common)
    raise ValueError(f"unknown bandit algorithm: {algorithm}")


def _as_action(value: Action | str) -> Action:
    if isinstance(value, Action):
        return value
    return Action(value)


def _static_prior(signature: Signature) -> Action | None:
    sequence = STATIC_TABLE.get(signature.failure_class)
    if not sequence:
        return None
    index = min(max(signature.attempt - 1, 0), len(sequence) - 1)
    return sequence[index]


EpsilonGreedyPolicy = EpsilonGreedy
UCB1Policy = UCB1
ThompsonSamplingPolicy = ThompsonSampling
