"""Regenerate experiment outputs and the bundled deterministic dashboard demo."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dashboard.prepare_demo import BUNDLED, prepare_demo
from experiments.run_all import main as run_experiments

SNAPSHOTS = (
    "e1_table.csv",
    "e2_learning_summary.csv",
    "e3_drift_summary.csv",
    "e3_recovery_summary.csv",
    "e4_ablations_summary.csv",
    "e5_silent_failures_summary.csv",
    "learned_policy_heatmap.csv",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reproduce experiments and dashboard demo data.")
    parser.add_argument("--config", default="configs/phase5.yaml")
    args = parser.parse_args(argv)
    run_experiments(["--config", args.config])
    prepare_demo()
    root = Path(__file__).resolve().parents[1] / "results"
    BUNDLED.mkdir(parents=True, exist_ok=True)
    for name in SNAPSHOTS:
        shutil.copy2(root / name, BUNDLED / name)
    print("Experiment tables and seeded dashboard demo are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
