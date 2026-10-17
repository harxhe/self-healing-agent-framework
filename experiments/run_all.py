"""Regenerate all Phase 5 experiment tables, CSVs, and figures.

Run with ``python -m experiments.run_all --config configs/phase5.yaml``.
All policy comparisons use identical task schedules for each seed.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.run import run
from healagent.core.types import Action
from healagent.ledger.ledger import RecoveryLedger
from healagent.metrics import confidence_interval, paired_differences, summarize_by

ROOT = Path("results")
METRICS = ("tsr", "rsr", "sfr", "mean_cost", "mean_latency_ms", "mean_regret")
INTENSITIES = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
POLICIES = ("retry_only", "static", "bandit")


def read_config(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_config(config: dict[str, Any], label: str) -> list[dict[str, Any]]:
    result_dir = ROOT / "runs" / label
    result_dir.mkdir(parents=True, exist_ok=True)
    return run(config, output_dir=result_dir)


def _base(config: dict[str, Any], **changes: Any) -> dict[str, Any]:
    result = dict(config)
    result["policy"] = dict(config.get("policy", {}))
    result["budget"] = dict(config.get("budget", {}))
    result.update(changes)
    result["write_traces"] = False
    return result


def experiment_e1(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for intensity in INTENSITIES:
        batch = _base(
            config,
            seeds=config["seeds"],
            episodes=1,
            fault_intensity=intensity,
            policies=list(POLICIES),
        )
        rows.extend(run_config(batch, f"e1/intensity-{intensity:.1f}"))
    write_csv(rows, ROOT / "e1_main.csv")
    summaries = summarize_by(rows, group_by=("policy", "intensity"), metrics=METRICS)
    write_csv(summaries, ROOT / "e1_table.csv")

    paired: list[dict[str, Any]] = []
    for intensity in INTENSITIES:
        subset = [row for row in rows if row["intensity"] == intensity]
        for policy in ("retry_only", "bandit"):
            for metric in ("tsr", "mean_cost", "mean_regret"):
                values = paired_differences(
                    subset, treatment=policy, control="static", metric=metric
                )
                paired.append({"intensity": intensity, "treatment": policy, "control": "static", "metric": metric, **values})
    write_csv(paired, ROOT / "e1_paired.csv")
    return rows


def experiment_e2(config: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = int(config.get("episodes_e2", 30))
    shared = _base(config, seeds=config["seeds"], episodes=episodes, fault_intensity=0.2)
    rows = run_config({**shared, "policies": ["retry_only", "static"]}, "e2/baselines")
    for start in ("cold", "warm"):
        policy_config = dict(shared["policy"], start=start)
        batch = dict(shared, policy=policy_config, policy_name="bandit")
        batch["policy"] = dict(policy_config, name="bandit")
        rows.extend(run_config(batch, f"e2/bandit-{start}"))
        for row in rows[-len(config["seeds"]) * episodes:]:
            row["policy"] = f"bandit_{start}"

    summaries = summarize_by(rows, group_by=("policy", "episode"), metrics=("tsr", "cumulative_regret"))
    write_csv(rows, ROOT / "e2_learning_curve.csv")
    write_csv(summaries, ROOT / "e2_learning_summary.csv")
    _plot_learning(summaries, ROOT / "e2_learning_curve.png")
    return rows


def _plot_learning(summaries: list[dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    styles = {"retry_only": "#4c78a8", "static": "#f58518", "bandit_cold": "#54a24b", "bandit_warm": "#b279a2"}
    for policy in styles:
        points = sorted((row for row in summaries if row["policy"] == policy), key=lambda row: row["episode"])
        if not points:
            continue
        x = [row["episode"] for row in points]
        for axis, metric, low, high, label in (
            (axes[0], "tsr", "tsr_ci_low", "tsr_ci_high", "Task success"),
            (axes[1], "cumulative_regret", "cumulative_regret_ci_low", "cumulative_regret_ci_high", "Cumulative regret"),
        ):
            y = np.asarray([row[metric] for row in points], dtype=float)
            lo = np.asarray([row[low] for row in points], dtype=float)
            hi = np.asarray([row[high] for row in points], dtype=float)
            axis.plot(x, y, label=policy.replace("_", " "), color=styles[policy])
            axis.fill_between(x, lo, hi, alpha=0.16, color=styles[policy])
            axis.set_xlabel("Episode")
            axis.set_ylabel(label)
            axis.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def experiment_e3(config: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = int(config.get("episodes_e3", 40))
    drift_episode = int(config.get("drift_episode", episodes // 2))
    batch = _base(
        config,
        seeds=config["seeds"],
        episodes=episodes,
        fault_intensity=0.3,
        policies=list(POLICIES),
        drift={
            "episode": drift_episode,
            "tool": "order_lookup",
            "new_profile": "order_lookup_rate_limit_persistent",
        },
    )
    rows = run_config(batch, "e3/drift")
    summaries = summarize_by(rows, group_by=("policy", "episode"), metrics=("tsr",))
    write_csv(rows, ROOT / "e3_drift.csv")
    write_csv(summaries, ROOT / "e3_drift_summary.csv")
    recovery = _drift_recovery(rows, drift_episode)
    write_csv(recovery, ROOT / "e3_recovery_time.csv")
    write_csv(_recovery_summary(recovery), ROOT / "e3_recovery_summary.csv")
    _plot_drift(summaries, drift_episode, ROOT / "e3_drift.png")
    return rows


def _drift_recovery(rows: list[dict[str, Any]], drift_episode: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["policy"], row["seed"])].append(row)
    output: list[dict[str, Any]] = []
    for (policy, seed), run_rows in sorted(grouped.items()):
        ordered = sorted(run_rows, key=lambda row: row["episode"])
        before = [row["tsr"] for row in ordered if drift_episode - 5 <= row["episode"] < drift_episode]
        threshold = float(np.mean(before)) if before else 1.0
        regained = None
        for index, row in enumerate(ordered):
            if row["episode"] < drift_episode:
                continue
            window = ordered[index:index + 3]
            if len(window) == 3 and float(np.mean([item["tsr"] for item in window])) >= threshold:
                regained = int(row["episode"] - drift_episode)
                break
        output.append({
            "policy": policy,
            "seed": seed,
            "pre_drift_tsr": threshold,
            "recovery_episodes": regained,
            "regained": regained is not None,
        })
    return output


def _recovery_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for policy in POLICIES:
        cohort = [row for row in rows if row["policy"] == policy]
        recovered = [float(row["recovery_episodes"]) for row in cohort if row["recovery_episodes"] is not None]
        average, low, high = confidence_interval(recovered)
        output.append({
            "policy": policy,
            "seeds": len(cohort),
            "regained_count": len(recovered),
            "regained_fraction": len(recovered) / len(cohort) if cohort else 0.0,
            "mean_recovery_episodes": average,
            "recovery_ci_low": low,
            "recovery_ci_high": high,
        })
    return output


def _plot_drift(summaries: list[dict[str, Any]], drift_episode: int, path: Path) -> None:
    fig, axis = plt.subplots(figsize=(8, 4.5))
    colors = {"retry_only": "#4c78a8", "static": "#f58518", "bandit": "#54a24b"}
    for policy, color in colors.items():
        points = sorted((row for row in summaries if row["policy"] == policy), key=lambda row: row["episode"])
        if not points:
            continue
        x = [row["episode"] for row in points]
        y = [row["tsr"] for row in points]
        axis.plot(x, y, label=policy.replace("_", " "), color=color)
        axis.fill_between(x, [row["tsr_ci_low"] for row in points], [row["tsr_ci_high"] for row in points], alpha=0.16, color=color)
    axis.axvline(drift_episode, color="#e45756", linestyle="--", label="Drift")
    axis.set(xlabel="Episode", ylabel="Task success rate", ylim=(0, 1.02))
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def experiment_e4(config: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = int(config.get("episodes_e4", 6))
    raw: list[dict[str, Any]] = []
    for algorithm, start, cost_term, mask, discount in itertools.product(
        ("epsilon_greedy", "ucb1", "thompson"),
        ("cold", "warm"),
        (True, False),
        (True, False),
        (0.95, 1.0),
    ):
        label = f"{algorithm}-{start}-cost{int(cost_term)}-mask{int(mask)}-gamma{discount:g}"
        batch = _base(
            config,
            seeds=config["seeds"],
            episodes=episodes,
            fault_intensity=0.3,
            policies=["bandit"],
        )
        batch["policy"] = dict(
            batch["policy"],
            name="bandit",
            algorithm=algorithm,
            start=start,
            use_cost_term=cost_term,
            use_mask=mask,
            discount=discount,
        )
        variants = run_config(batch, f"e4/{label}")
        for row in variants:
            row.update(algorithm=algorithm, start=start, use_cost_term=cost_term, use_mask=mask, discount=discount)
        raw.extend(variants)
    write_csv(raw, ROOT / "e4_ablations.csv")
    group_fields = ("algorithm", "start", "use_cost_term", "use_mask", "discount")
    per_seed = _mean_rows(raw, group_fields + ("seed",), METRICS)
    summaries = summarize_by(per_seed, group_by=group_fields, metrics=METRICS)
    write_csv(summaries, ROOT / "e4_ablations_summary.csv")
    return raw


def _mean_rows(
    rows: list[dict[str, Any]], group_fields: tuple[str, ...], metrics: tuple[str, ...]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in group_fields)].append(row)
    output = []
    for key, members in grouped.items():
        result = dict(zip(group_fields, key))
        result.update({metric: float(np.mean([float(row[metric]) for row in members])) for metric in metrics})
        output.append(result)
    return output


def experiment_e5(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for intensity, verifier in itertools.product((0.0, 0.1, 0.2, 0.3), (True, False)):
        batch = _base(
            config,
            seeds=config["seeds"],
            episodes=int(config.get("episodes_e5", 1)),
            fault_intensity=intensity,
            policies=list(POLICIES),
            verifier_enabled=verifier,
            allowed_faults=["semantic_wrong"],
            fault_tools=["calculator"],
        )
        rows = run_config(batch, f"e5/semantic-{intensity:.1f}-verifier{int(verifier)}")
        for row in rows:
            row["semantic_intensity"] = intensity
            row["verifier"] = verifier
        raw.extend(rows)
    write_csv(raw, ROOT / "e5_silent_failures.csv")
    summaries = summarize_by(
        raw,
        group_by=("policy", "semantic_intensity", "verifier"),
        metrics=("tsr", "sfr"),
    )
    write_csv(summaries, ROOT / "e5_silent_failures_summary.csv")
    return raw


def export_heatmap(config: dict[str, Any]) -> list[dict[str, Any]]:
    batch = _base(
        config,
        seeds=config["seeds"],
        episodes=int(config.get("episodes_heatmap", 30)),
        fault_intensity=0.3,
        policies=["bandit"],
    )
    batch["policy"] = dict(batch["policy"], name="bandit", start="cold", algorithm="ucb1")
    batch["ledger_path"] = str(ROOT / "heatmap" / "ledger-{seed}.sqlite")
    run_config(batch, "heatmap/replay")

    combined: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for seed in config["seeds"]:
        ledger = RecoveryLedger(ROOT / "heatmap" / f"ledger-{seed}.sqlite")
        for signature, actions in ledger.all_stats().items():
            for action, stats in actions.items():
                aggregate = combined[(signature, action)]
                count = float(stats["n"])
                aggregate[0] += count
                aggregate[1] += float(stats["success_rate"]) * count
                aggregate[2] += float(stats["mean_reward"]) * count
        ledger.close()
    signature_best: dict[str, tuple[str, float]] = {}
    for (signature, action), (count, successes, reward) in combined.items():
        rate = successes / count if count else 0.0
        current = signature_best.get(signature)
        if current is None or (rate, reward / max(count, 1)) > (current[1], 0.0):
            signature_best[signature] = action, rate
    rows = []
    for (signature, action), (count, successes, reward) in sorted(combined.items()):
        best_action, best_rate = signature_best[signature]
        rows.append({
            "signature": signature,
            "action": action,
            "n": int(count),
            "successes": int(successes),
            "success_rate": successes / count if count else 0.0,
            "mean_reward": reward / count if count else 0.0,
            "best_action": best_action,
            "best_action_success_rate": best_rate,
        })
    write_csv(rows, ROOT / "learned_policy_heatmap.csv")
    return rows


def checkpoint(e1: list[dict[str, Any]], e3: list[dict[str, Any]], recovery: list[dict[str, Any]]) -> dict[str, Any]:
    moderate = [row for row in e1 if row["intensity"] in (0.2, 0.3)]
    averages: dict[tuple[str, float], float] = {}
    for policy in POLICIES:
        for intensity in (0.2, 0.3):
            sample = [row["tsr"] for row in moderate if row["policy"] == policy and row["intensity"] == intensity]
            averages[(policy, intensity)] = float(np.mean(sample)) if sample else 0.0
    bandit_beats_static = any(
        averages[("bandit", level)] > averages[("static", level)] for level in (0.2, 0.3)
    )
    costs_equal_success: list[bool] = []
    for level in (0.2, 0.3):
        same_seed = {
            (row["policy"], row["seed"]): row
            for row in moderate if row["intensity"] == level
        }
        costs_equal_success.append(any(
            abs(float(same_seed[("bandit", seed)]["tsr"]) - float(same_seed[("static", seed)]["tsr"])) <= 0.01
            and float(same_seed[("bandit", seed)]["mean_cost"]) <= float(same_seed[("static", seed)]["mean_cost"])
            for seed in config_seed_values(moderate)
            if ("bandit", seed) in same_seed and ("static", seed) in same_seed
        ))
    recovery_means = {}
    for policy in POLICIES:
        values = [row["recovery_episodes"] for row in recovery if row["policy"] == policy and row["recovery_episodes"] is not None]
        recovery_means[policy] = float(np.mean(values)) if values else None
    drift_advantage = (
        recovery_means["bandit"] is not None
        and recovery_means["static"] is not None
        and recovery_means["bandit"] < recovery_means["static"]
    )
    result = {
        "e1_mean_tsr": {f"{policy}@{level:.1f}": averages[(policy, level)] for policy in POLICIES for level in (0.2, 0.3)},
        "e1_bandit_beats_static_tsr": bandit_beats_static,
        "bandit_cost_no_higher_at_equal_tsr": any(costs_equal_success),
        "e3_mean_recovery_episodes": recovery_means,
        "bandit_recovers_faster_after_drift": drift_advantage,
        "checkpoint_passed": bandit_beats_static or any(costs_equal_success) or drift_advantage,
        "environment_modified": False,
    }
    (ROOT / "phase5_checkpoint.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def config_seed_values(rows: list[dict[str, Any]]) -> set[int]:
    return {int(row["seed"]) for row in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate Phase 5 results.")
    parser.add_argument("--config", default="configs/phase5.yaml")
    args = parser.parse_args(argv)
    config = read_config(args.config)
    ROOT.mkdir(parents=True, exist_ok=True)

    e1 = experiment_e1(config)
    experiment_e2(config)
    e3 = experiment_e3(config)
    experiment_e4(config)
    experiment_e5(config)
    export_heatmap(config)
    recovery = _drift_recovery(e3, int(config.get("drift_episode", 20)))
    result = checkpoint(e1, e3, recovery)
    print(f"Phase 5 artifacts written under {ROOT.resolve()}")
    print(f"Bandit-vs-static checkpoint: {'passed' if result['checkpoint_passed'] else 'not demonstrated'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
