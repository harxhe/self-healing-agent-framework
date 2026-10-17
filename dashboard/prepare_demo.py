"""Build fixed-seed traces used by the dashboard and scripted presentation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from healagent.control.orchestrator import run_episode
from healagent.core.trace import TraceLogger
from healagent.core.types import Action, FailureClass, Signature, Task
from healagent.faults.drift import DriftEvent, apply_drift, initial_profiles
from healagent.faults.injector import FaultInjector
from healagent.faults.types import FaultKind
from healagent.ledger.ledger import RecoveryLedger
from healagent.policy.bandit import EpsilonGreedy
from healagent.policy.retry_only import RetryOnly
from healagent.policy.static import StaticMapping
from healagent.tasks.catalog import load_tasks

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "demo"
TRACES = RESULTS / "traces"
BUNDLED = ROOT / "dashboard" / "data"
SEED = 2026
BUDGET = {"attempts": 6, "cost": 50, "latency_ms": 30000, "depth": 3}


def _task(task_id: str) -> Task:
    return next(task for task in load_tasks() if task.task_id == task_id)


def _record(task: Task, policy, label: str, fault: FaultKind, step: int, episode: int = 0,
            profiles=None) -> dict:
    run_id = f"{label}-s{SEED}-e{episode}"
    logger = TraceLogger(run_id, TRACES)
    injector = FaultInjector(
        trial_seed=SEED + episode,
        intensity=0.0,
        profiles=profiles,
        forced_faults={(task.task_id, step): fault},
    )
    result = run_episode(
        task, policy, injector, logger=logger, run_id=run_id, seed=SEED,
        episode=episode, budget_config=BUDGET,
    )
    return {
        "run_id": run_id,
        "task_id": task.task_id,
        "policy": label,
        "episode": episode,
        "task_success": result.answer_correct,
        "actions": result.actions,
        "detected": result.detected_failures,
        "recovered": result.recovered_failures,
        "silent": result.silent_failures,
        "cost": result.cost,
        "drifted": bool(profiles and profiles.get(("order_lookup", FaultKind.RATE_LIMIT))
                         and profiles[("order_lookup", FaultKind.RATE_LIMIT)].persistence.value == "persistent"),
    }


def run_learning_replay(episodes: int, progress=None, label: str = "demo-interactive-learning") -> tuple[list[dict], dict]:
    ledger = RecoveryLedger(":memory:")
    policy = EpsilonGreedy(ledger, list(Action), seed=SEED, epsilon=0.15, epsilon_min=0.02)
    tasks = {task.task_id: task for task in load_tasks()}
    rows = []
    for episode in range(episodes):
        shipping = episode % 2 == 0
        task = tasks["T041"] if shipping else tasks["T061"]
        tool = "shipping_estimator" if shipping else "customer_lookup"
        step = 2 if shipping else 1
        row = _record(task, policy, label, FaultKind.TIMEOUT, step, episode)
        row["target_tool"] = tool
        rows.append(row)
        if progress is not None:
            progress((episode + 1) / episodes, episode + 1, row)
    stats = ledger.all_stats()
    ledger.close()
    return rows, stats


def prepare_demo() -> dict:
    for path in (TRACES, BUNDLED):
        path.mkdir(parents=True, exist_ok=True)
    for path in TRACES.glob("demo-*.jsonl"):
        path.unlink()

    tasks = {task.task_id: task for task in load_tasks()}
    refund = tasks["T021"]
    retry = _record(refund, RetryOnly(max_retries=2), "demo-retry-only", FaultKind.PARTIAL_RESPONSE, 2)

    # Seed the learned policy with prior observations from the same signature.
    ledger = RecoveryLedger(":memory:")
    signature = Signature(failure_class=FailureClass.PARTIAL_RESPONSE, tool="policy_lookup", attempt=1)
    for action in (Action.RETRY, Action.REPAIR, Action.SUBSTITUTE):
        for _ in range(3):
            ledger.record(signature, action.value, False, 1, 10, -0.1, run_id="demo-prior")
    for _ in range(3):
        ledger.record(signature, Action.REFRESH.value, True, 1, 10, 0.9, run_id="demo-prior")
    bandit = EpsilonGreedy(ledger, list(Action), seed=SEED, epsilon=0.0, epsilon_min=0.0)
    learned = _record(refund, bandit, "demo-bandit", FaultKind.PARTIAL_RESPONSE, 2)
    ledger.close()

    # Fifty episodes teach two intentionally different timeout profiles.
    learning, learned_stats = run_learning_replay(50, label="demo-learning")

    # Compare order lookup before and after the profile changes from transient to persistent.
    drift_task = tasks["T001"]
    pre = _record(drift_task, StaticMapping(), "demo-drift-before", FaultKind.RATE_LIMIT, 1)
    profiles = apply_drift(
        initial_profiles(),
        DriftEvent(episode=0, tool="order_lookup", new_profile="order_lookup_rate_limit_persistent"),
    )
    post = _record(drift_task, StaticMapping(), "demo-drift-after", FaultKind.RATE_LIMIT, 1, profiles=profiles)

    # The verifier sees plausible but wrong calculator output and triggers repair.
    silent = _record(tasks["T021"], StaticMapping(), "demo-verifier", FaultKind.SEMANTIC_WRONG, 3)

    manifest = {
        "seed": SEED,
        "scenarios": {"D2_retry_only": retry, "D2_bandit": learned,
                      "D3_learning": learning, "D4_before": pre, "D4_after": post,
                      "D5_verifier": silent},
        "ledger": learned_stats,
        "notes": {
            "D2": "The bandit is initialized from prior outcomes for this signature; its chosen action is then recorded in the trace.",
            "D3": "A fixed schedule alternates the persistent shipping timeout and transient customer timeout profiles.",
            "D5": "The oracle verifier compares tool output with the known task answer in simulation.",
        },
    }
    output = RESULTS / "manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for source in TRACES.glob("demo-*.jsonl"):
        shutil.copy2(source, BUNDLED / source.name)
    shutil.copy2(output, BUNDLED / output.name)
    return manifest


if __name__ == "__main__":
    data = prepare_demo()
    print(f"Prepared {len(data['scenarios']['D3_learning'])} learning episodes at {RESULTS}")
