import random
import math
from typing import List, Dict, Any, Optional
from healagent.ledger.ledger import RecoveryLedger

class BaseBanditPolicy:
    def __init__(self, ledger: RecoveryLedger, actions: List[str], warm_start_table: Optional[Dict[str, str]] = None):
        self.ledger = ledger
        self.actions = actions
        self.warm_start_table = warm_start_table or {}

    def select(self, signature: str, mask: Optional[List[str]] = None) -> str:
        raise NotImplementedError

    def update(self, signature: str, action: str, success: bool, cost: float, latency: float, reward: Optional[float] = None):
        self.ledger.record(signature, action, success, cost, latency, reward)


class EpsilonGreedyPolicy(BaseBanditPolicy):
    def __init__(self, ledger: RecoveryLedger, actions: List[str], epsilon: float = 0.1, warm_start_table: Optional[Dict[str, str]] = None):
        super().__init__(ledger, actions, warm_start_table)
        self.epsilon = epsilon

    def select(self, signature: str, mask: Optional[List[str]] = None) -> str:
        valid_actions = mask if mask is not None else self.actions
        if not valid_actions:
            return self.actions[0]

        if random.random() < self.epsilon:
            return random.choice(valid_actions)

        best_action = valid_actions[0]
        max_reward = -float('inf')

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            if stats["count"] == 0:
                default_action = self.warm_start_table.get(signature, valid_actions[0])
                score = 1.0 if action == default_action else 0.0
            else:
                score = stats["recent_reward"]

            if score > max_reward:
                max_reward = score
                best_action = action

        return best_action


class UCB1Policy(BaseBanditPolicy):
    def __init__(self, ledger: RecoveryLedger, actions: List[str], warm_start_table: Optional[Dict[str, str]] = None):
        super().__init__(ledger, actions, warm_start_table)

    def select(self, signature: str, mask: Optional[List[str]] = None) -> str:
        valid_actions = mask if mask is not None else self.actions
        if not valid_actions:
            return self.actions[0]

        total_pulls = sum(self.ledger.get_arm_stats(signature, a)["count"] for a in valid_actions)

        if total_pulls == 0:
            default_action = self.warm_start_table.get(signature, valid_actions[0])
            if default_action in valid_actions:
                return default_action
            return valid_actions[0]

        best_action = valid_actions[0]
        max_ucb = -float('inf')

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            count = stats["count"]
            if count == 0:
                return action

            mean_reward = stats["recent_reward"]
            confidence = math.sqrt(2.0 * math.log(total_pulls) / count)
            ucb_score = mean_reward + confidence

            if ucb_score > max_ucb:
                max_ucb = ucb_score
                best_action = action

        return best_action


class ThompsonSamplingPolicy(BaseBanditPolicy):
    def __init__(self, ledger: RecoveryLedger, actions: List[str], warm_start_table: Optional[Dict[str, str]] = None):
        super().__init__(ledger, actions, warm_start_table)

    def select(self, signature: str, mask: Optional[List[str]] = None) -> str:
        valid_actions = mask if mask is not None else self.actions
        if not valid_actions:
            return self.actions[0]

        best_action = valid_actions[0]
        max_sample = -float('inf')

        for action in valid_actions:
            stats = self.ledger.get_arm_stats(signature, action)
            count = stats["count"]
            successes = int(stats["success_rate"] * count)
            
            alpha = successes + 1.0
            beta_param = (count - successes) + 1.0
            sample = random.betavariate(alpha, beta_param)

            if sample > max_sample:
                max_sample = sample
                best_action = action

        return best_action
