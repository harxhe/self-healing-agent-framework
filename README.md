# HealAgent

An adaptive **self-healing agent framework**, simulated end to end (no live LLM
is required for the core results).

HealAgent extends the Monitor → Detect → Diagnose → Recover → Verify loop from
Babu & Agrawal (2026), *"Self-Healing Agentic Orchestrators for Reliable
Tool-Augmented LLM Systems"* (arXiv:2606.01416).

**New contribution:** a **Recovery Ledger** (`failure signature → recovery
action → outcome`) and a **bandit-based policy selector** that learns which
recovery action works best for each failure signature, instead of relying on a
fixed mapping.

- **Simulated agent:** an e-commerce customer-support agent (customer, order,
  inventory, shipping, policy, calculator tools).
- **Compared policies:** `RetryOnly`, `StaticMapping` (the paper's table),
  `BanditPolicy` (ours).
- **Metrics:** Task Success Rate (TSR), Recovery Success Rate (RSR), Silent
  Failure Rate (SFR), cost, latency.

> **Note:** The verifier is an **oracle** in simulation: it checks outputs
> against known task success criteria. Live LLM tooling is optional and limited
> to a sanity check; it is never part of the core, deterministic pipeline.

## Status

Phases 0-5 are complete. Phase 6 contains the dashboard, report, and demo work.
See `docs/implementation.md` for the full plan and `progress.md` for current
progress.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
pip install -r requirements.txt
```

## Tests

```bash
python -m pytest -q
```

## Reproduce Phase 5 Results

```bash
python -m experiments.run_all --config configs/phase5.yaml
```

This regenerates the E1-E5 CSV tables, confidence intervals, paired comparisons,
learning and drift figures, recovery-time summary, and learned-policy heatmap
under `results/`. The configuration fixes the same ten seeds across policies.

## Repository layout

```
healagent/
├── README.md
├── docs/implementation.md
├── requirements.txt
├── configs/                 # experiment YAML files
├── healagent/
│   ├── core/                # seed manager, types, trace schema, interfaces
│   ├── data/                # synthetic data generator
│   ├── tools/               # simulated tools + backups
│   ├── tasks/               # task records + executor
│   ├── faults/              # fault types, profiles, schedule, drift
│   ├── control/             # detector, diagnoser, actions, verifier, budget
│   ├── policy/              # retry_only, static, bandit (eps-greedy, UCB1, Thompson)
│   ├── ledger/              # SQLite ledger + arm statistics
│   └── metrics/             # TSR, RSR, SFR, cost, latency, regret
├── experiments/             # experiment runner and E1-E5 reproduction
├── dashboard/               # Streamlit app
├── results/                 # generated CSVs, figures, tables (git-ignored)
└── tests/
```

## Citation

Babu, R. S., & Agrawal, A. (2026). *Self-healing agentic orchestrators for
reliable tool-augmented large language model systems.* arXiv:2606.01416.
https://doi.org/10.48550/arXiv.2606.01416
