"""Experiment runner: run ``(tasks x policy x seeds)`` and write traces + a CSV.

Usage::

    python experiments/run.py --config configs/template.yaml
    python -m experiments.run --config configs/template.yaml
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from healagent.control.orchestrator import run_episode
from healagent.core.interfaces import Policy
from healagent.core.trace import TraceLogger
from healagent.faults.drift import (
    DriftEvent,
    apply_drift,
    drift_event_from_config,
    initial_profiles,
    log_drift_event,
)
from healagent.faults.injector import FaultInjector
from healagent.tasks.catalog import load_tasks

RESULTS_DIR = Path("results")
TRACE_DIR = RESULTS_DIR / "traces"


def load_config(path: Path | str) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_policy(name: str, config: Mapping[str, Any]) -> Policy:
    if name == "retry_only":
        from healagent.policy import RetryOnly

        return RetryOnly(max_retries=int(config.get("budget", {}).get("attempts", 3)))
    if name == "static":
        from healagent.policy import StaticMapping

        return StaticMapping()
    if name == "bandit":
        from healagent.policy.bandit import build_bandit_policy

        return build_bandit_policy(config)
    raise ValueError(f"unknown policy: {name}")


def policy_names(config: Mapping[str, Any]) -> list[str]:
    if "policies" in config:
        return list(config["policies"])
    return [str(config.get("policy", {}).get("name", "static"))]


def run(
    config: Mapping[str, Any],
    *,
    tasks: Sequence | None = None,
    output_dir: Path | str = RESULTS_DIR,
) -> list[dict[str, Any]]:
    output_dir = Path(output_dir)
    trace_dir = output_dir / "traces"
    task_list = list(tasks) if tasks is not None else load_tasks()

    seeds = list(config.get("seeds", [0]))
    episodes = int(config.get("episodes", 1))
    intensity = float(config.get("fault_intensity", 0.0))
    lam = float(config.get("lambda", 0.05))
    mu = float(config.get("mu", 0.01))
    budget = dict(config.get("budget", {}))
    budget.setdefault("depth", config.get("budget", {}).get("depth", 3))
    drift_event = drift_event_from_config(config.get("drift"))
    names = policy_names(config)

    _snapshot_config(config, output_dir)

    rows: list[dict[str, Any]] = []
    for name in names:
        policy = build_policy(name, config)
        for seed in seeds:
            for episode in range(episodes):
                row = _run_one(
                    policy=policy,
                    name=name,
                    seed=int(seed),
                    episode=episode,
                    intensity=intensity,
                    tasks=task_list,
                    lam=lam,
                    mu=mu,
                    budget=budget,
                    drift_event=drift_event,
                    drift_episode=int(config.get("drift", {}).get("episode", -1)),
                    trace_dir=trace_dir,
                )
                rows.append(row)
    return rows


def _run_one(
    *,
    policy: Policy,
    name: str,
    seed: int,
    episode: int,
    intensity: float,
    tasks: Sequence,
    lam: float,
    mu: float,
    budget: Mapping[str, Any],
    drift_event: DriftEvent | None,
    drift_episode: int,
    trace_dir: Path,
) -> dict[str, Any]:
    profiles = initial_profiles()
    drifted = drift_event is not None and episode >= drift_episode
    if drifted and drift_event is not None:
        profiles = apply_drift(profiles, drift_event)

    trial_seed = seed * 1000 + episode
    injector = FaultInjector(trial_seed, intensity, profiles=profiles)
    run_id = f"{name}-s{seed}-e{episode}-i{intensity:g}"
    logger = TraceLogger(run_id, trace_dir=trace_dir)

    if drifted and drift_event is not None:
        log_drift_event(logger, run_id, drift_event, seed=seed, episode=episode, method=name)

    n_tasks = len(tasks)
    correct = detected = recovered = silent = 0
    total_cost = 0.0
    total_latency = 0.0
    for task in tasks:
        result = run_episode(
            task, policy, injector, logger=logger, run_id=run_id, seed=seed,
            episode=episode, lam=lam, mu=mu, budget_config=budget,
        )
        correct += int(result.answer_correct)
        detected += result.detected_failures
        recovered += result.recovered_failures
        silent += result.silent_failures
        total_cost += result.cost
        total_latency += result.latency_ms

    return {
        "run_id": run_id,
        "policy": name,
        "seed": seed,
        "episode": episode,
        "intensity": intensity,
        "drifted": drifted,
        "n_tasks": n_tasks,
        "tsr": correct / n_tasks if n_tasks else 0.0,
        "rsr": recovered / detected if detected else 1.0,
        "sfr": silent / correct if correct else 0.0,
        "mean_cost": total_cost / n_tasks if n_tasks else 0.0,
        "mean_latency_ms": total_latency / n_tasks if n_tasks else 0.0,
    }


def _snapshot_config(config: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = output_dir / "config_snapshot.yaml"
    snapshot.write_text(yaml.safe_dump(dict(config), sort_keys=False), encoding="utf-8")


def write_summary(rows: list[dict[str, Any]], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HealAgent experiments.")
    parser.add_argument("--config", required=True, help="Path to a YAML config.")
    parser.add_argument("--out", default="results/summary.csv", help="Summary CSV path.")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    rows = run(config)
    path = write_summary(rows, args.out)
    print(f"Wrote {len(rows)} rows to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
