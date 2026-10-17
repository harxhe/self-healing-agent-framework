import random
import math
from typing import List, Dict, Any, Optional, Union, Set
from healagent.ledger.ledger import RecoveryLedger

class BaseBanditPolicy:
    def __init__(self, ledger: RecoveryLedger, actions: List[str], warm_start_table: Optional[Dict[str, str]] = None):
        self.ledger = ledger
        self.actions = actions
        self.warm_start_table = warm_start_table or {}

    def _get_valid_actions(self, mask: Optional[Union[List[str], Set[str], dict]]) -> List[str]:
        if mask is not None:
            if isinstance(mask, dict):
                valid = [k for k, v in mask.items() if v]
            else:
                valid = list(mask)
            if valid:
                return [a for a in valid if a in self.actions]
        return list(self.actions)

    def select(self, signature: str, mask: Optional[Union[List[str], Set[str], dict]] = None) -> str:
        raise NotImplementedError

    def update(self, signature: Any, action: str, *args, **kwargs):
        """Flexible update supporting both orchestrator (3 args) and unit test (5 args) formats."""
        success = True
        cost = 0.0
        latency = 0.0
        reward = None

        if len(args) == 1:
            val = args[0]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                reward = float(val)
                success = val > 0
            else:
                success = bool(val)
        elif len(args) >= 3:
            success = bool(args[0])
            cost = float(args[1])
            latency = float(args[2])
            if len(args) >= 4:
                reward = float(args[3])

        success = kwargs.get("success", success)
        cost = kwargs.get("cost", cost)
        latency = kwargs.get("latency", latency)
        reward = kwargs.get("reward", reward)

        self.ledger.record(signature, action, success, cost, latency, reward)


class EpsilonGreedyPolicy(BaseBanditPolicy):
    def __init__(self, ledger: RecoveryLedger, actions: List[str], epsilon: float = 0.1, warm_start_table: Optional[Dict[str, str]] = None):
        super().__init__(ledger, actions, warm_start_table)
        self.epsilon = epsilon

    def select(self, signature: str, mask: Optional[Union[List[str], Set[str], dict]] = None) -> str:
        valid_actions = self._get_valid_actions(mask)
        if not valid_actions:
            valid_actions = list(self.actions)

        # Exploration
        if random.random() < self.epsilon:
            return random.choice(valid_actions)

        # Exploitation: check stats
        best_action = valid_actions[0]
        max_reward = float("-inf")

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            score = stats["recent_reward"] if stats["count"] > 0 else 0.0
            
            # Fallback to warm start if no data
            if stats["count"] == 0 and str(signature) in self.warm_start_table:
                if self.warm_start_table[str(signature)] == action:
                    score = 1.0

            if score > max_reward:
                max_reward = score
                best_action = action

        return best_action


class UCB1Policy(BaseBanditPolicy):
    def select(self, signature: str, mask: Optional[Union[List[str], Set[str], dict]] = None) -> str:
        valid_actions = self._get_valid_actions(mask)
        if not valid_actions:
            valid_actions = list(self.actions)

        total_pulls = sum(self.ledger.get_arm_stats(signature, a)["count"] for a in valid_actions)

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            if stats["count"] == 0:
                if str(signature) in self.warm_start_table and self.warm_start_table[str(signature)] == action:
                    return action
                return action

        best_action = valid_actions[0]
        max_ucb = float("-inf")

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            mean_rew = stats["recent_reward"]
            count = stats["count"]
            
            bonus = math.sqrt(2.0 * math.log(max(1, total_pulls)) / count) if count > 0 else 0.0
            ucb_score = mean_rew + bonus

            if ucb_score > max_ucb:
                max_ucb = ucb_score
                best_action = action

        return best_action


class ThompsonSamplingPolicy(BaseBanditPolicy):
    def select(self, signature: str, mask: Optional[Union[List[str], Set[str], dict]] = None) -> str:
        valid_actions = self._get_valid_actions(mask)
        if not valid_actions:
            valid_actions = list(self.actions)

        best_action = valid_actions[0]
        max_sample = float("-inf")

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            success_rate = stats["success_rate"]
            count = stats["count"]

            alpha = 1.0 + (success_rate * count)
            beta_param = 1.0 + ((1.0 - success_rate) * count)
            
            sample = random.betavariate(max(0.1, alpha), max(0.1, beta_param))

            if sample > max_sample:
                max_sample = sample
                best_action = action

        return best_action


def build_bandit_policy(config_or_name, ledger=None, actions=None, **kwargs):
    """Bulletproof factory function supporting dict configs, nested policy definitions, and direct calls."""
    policy_name = "epsilon_greedy"
    params = {}
    
    if isinstance(config_or_name, dict):
        config = config_or_name
        pol = config.get("policy", "epsilon_greedy")
        if isinstance(pol, dict):
            policy_name = pol.get("name", pol.get("type", "epsilon_greedy"))
            params.update(pol)
        elif isinstance(pol, str):
            policy_name = pol
            
        if "name" in config and isinstance(config["name"], str):
            policy_name = config["name"]
            
        ledger = ledger or config.get("ledger") or RecoveryLedger()
        actions = actions or config.get("actions", ["retry", "substitute", "refresh", "escalate"])
        params.update(config.get("params", {}))
        params.update(kwargs)
    else:
        if isinstance(config_or_name, dict):
            pol = config_or_name
            policy_name = pol.get("name", pol.get("type", "epsilon_greedy"))
            params.update(pol)
        elif config_or_name is not None:
            policy_name = str(config_or_name)
            
        ledger = ledger if ledger is not None else RecoveryLedger()
        actions = actions or ["retry", "substitute", "refresh", "escalate"]
        params.update(kwargs)

    name_lower = str(policy_name).lower()
    
    if "epsilon" in name_lower or "eps" in name_lower:
        epsilon = params.get("epsilon", 0.1)
        return EpsilonGreedyPolicy(ledger, actions, epsilon=epsilon, warm_start_table=params.get("warm_start_table"))
    elif "ucb" in name_lower:
        return UCB1Policy(ledger, actions, warm_start_table=params.get("warm_start_table"))
    elif "thompson" in name_lower or "ts" in name_lower:
        return ThompsonSamplingPolicy(ledger, actions, warm_start_table=params.get("warm_start_table"))
    
    return EpsilonGreedyPolicy(ledger, actions, warm_start_table=params.get("warm_start_table"))
