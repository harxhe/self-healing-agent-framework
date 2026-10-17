import sqlite3
import time
from typing import Dict, Any, List, Optional

class RecoveryLedger:
    def __init__(self, db_path: str = ":memory:", discount_factor: float = 0.95):
        self.db_path = db_path
        self.discount_factor = discount_factor
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signature TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    cost REAL NOT NULL,
                    latency REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.commit()

    def record(self, signature: str, action: str, success: bool, cost: float, latency: float, reward: Optional[float] = None):
        if reward is None:
            # Cost-aware reward: success - lambda * cost - mu * latency
            reward = float(success) - 0.1 * cost - 0.05 * latency
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ledger (signature, action, success, cost, latency, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (signature, action, int(success), cost, latency, time.time()))
            conn.commit()

    def get_arm_stats(self, signature: str, action: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT success, cost, latency, timestamp FROM ledger
                WHERE signature = ? AND action = ?
                ORDER BY timestamp ASC
            """, (signature, action))
            rows = cursor.fetchall()
        
        if not rows:
            return {"count": 0, "mean_reward": 0.0, "success_rate": 0.0, "recent_reward": 0.0}

        count = len(rows)
        total_reward = 0.0
        successes = 0
        weighted_reward = 0.0
        weight_sum = 0.0
        current_weight = 1.0

        for row in rows:
            succ, cost, lat, _ = row
            rew = float(succ) - 0.1 * cost - 0.05 * lat
            successes += succ
            total_reward += rew
            
            weighted_reward += rew * current_weight
            weight_sum += current_weight
            current_weight *= self.discount_factor

        mean_reward = total_reward / count
        success_rate = successes / count
        recent_reward = weighted_reward / weight_sum if weight_sum > 0 else mean_reward

        return {
            "count": count,
            "mean_reward": mean_reward,
            "success_rate": success_rate,
            "recent_reward": recent_reward
        }
