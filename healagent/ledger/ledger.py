"""Persistent SQLite recovery ledger."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from healagent.core.types import Signature
from healagent.ledger.arms import ArmStats, aggregate_arm_stats


class RecoveryLedger:
    """Store recovery outcomes and compute per-signature, per-action statistics."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        discount_factor: float = 1.0,
        window: int | None = None,
    ) -> None:
        if not 0.0 < discount_factor <= 1.0:
            raise ValueError("discount_factor must be in (0, 1]")
        if window is not None and window < 1:
            raise ValueError("window must be positive")
        self.db_path = str(db_path)
        self.discount_factor = discount_factor
        self.window = window
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._initialize()

    def _connect(self) -> tuple[sqlite3.Connection, bool]:
        if self._connection is not None:
            return self._connection, False
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        return self._connection, False

    def _initialize(self) -> None:
        connection, close = self._connect()
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL DEFAULT '',
                    episode INTEGER NOT NULL DEFAULT 0,
                    failure_class TEXT NOT NULL DEFAULT '',
                    tool TEXT NOT NULL DEFAULT '',
                    attempt INTEGER NOT NULL DEFAULT 1,
                    signature TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    cost REAL NOT NULL,
                    latency REAL NOT NULL,
                    reward REAL NOT NULL,
                    timestamp REAL NOT NULL
                )"""
            )
            connection.commit()
        finally:
            if close:
                connection.close()

    def log(
        self,
        run_id: str,
        episode: int,
        signature: Signature | str,
        action: str,
        success: bool,
        cost: float,
        latency: float,
        reward: float,
    ) -> None:
        self.record(
            signature,
            action,
            success,
            cost,
            latency,
            reward,
            run_id=run_id,
            episode=episode,
        )

    def record(
        self,
        signature: Signature | str,
        action: str,
        success: bool,
        cost: float,
        latency: float,
        reward: float | None = None,
        *,
        run_id: str = "",
        episode: int = 0,
    ) -> None:
        signature_key, failure_class, tool, attempt = _signature_parts(signature)
        if reward is None:
            reward = float(bool(success)) - 0.05 * float(cost) - 0.01 * float(latency) / 1000.0
        connection, close = self._connect()
        try:
            connection.execute(
                """INSERT INTO records
                   (run_id, episode, failure_class, tool, attempt, signature,
                    action, success, cost, latency, reward, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    int(episode),
                    failure_class,
                    tool,
                    attempt,
                    signature_key,
                    _action_value(action),
                    int(bool(success)),
                    float(cost),
                    float(latency),
                    float(reward),
                    time.time(),
                ),
            )
            connection.commit()
        finally:
            if close:
                connection.close()

    def stats(self, signature: Signature | str) -> dict[str, dict[str, float | int]]:
        signature_key, _, _, _ = _signature_parts(signature)
        connection, close = self._connect()
        try:
            rows = connection.execute(
                "SELECT action, success, reward FROM records WHERE signature = ? ORDER BY id",
                (signature_key,),
            ).fetchall()
        finally:
            if close:
                connection.close()
        by_action: dict[str, list[tuple[bool, float]]] = {}
        for action, success, reward in rows:
            by_action.setdefault(action, []).append((bool(success), float(reward)))
        return {
            action: aggregate_arm_stats(
                observations,
                gamma=self.discount_factor,
                window=self.window,
            ).as_dict()
            for action, observations in by_action.items()
        }

    def all_stats(self) -> dict[str, dict[str, dict[str, float | int]]]:
        connection, close = self._connect()
        try:
            signatures = [row[0] for row in connection.execute(
                "SELECT DISTINCT signature FROM records ORDER BY signature"
            )]
        finally:
            if close:
                connection.close()
        return {signature: self.stats(signature) for signature in signatures}

    def get_arm_stats(self, signature: Signature | str, action: str) -> dict[str, Any]:
        stats = self.stats(signature).get(_action_value(action))
        if stats is None:
            return ArmStats().as_dict()
        return stats

    def reset(self) -> None:
        connection, close = self._connect()
        try:
            connection.execute("DELETE FROM records")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'records'")
            connection.commit()
        finally:
            if close:
                connection.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def _signature_parts(signature: Signature | str) -> tuple[str, str, str, int]:
    if isinstance(signature, Signature):
        failure_class = signature.failure_class.value
        tool = signature.tool
        attempt = signature.attempt
        return f"{failure_class}|{tool}|{attempt}", failure_class, tool, attempt
    value = str(signature)
    pieces = value.split("|")
    if len(pieces) == 3 and pieces[2].isdigit():
        return value, pieces[0], pieces[1], int(pieces[2])
    return value, "", value, 1


def _action_value(action: Any) -> str:
    return str(getattr(action, "value", action))
