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

Phases 0-6 are complete. The project includes the deterministic dashboard,
report, 14-slide presentation, and seeded demo assets. See
`docs/implementation.md` for the plan and `progress.md` for the phase record.

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

## Reproduce Results and Demo Data

```bash
python -m experiments.reproduce --config configs/phase5.yaml
streamlit run dashboard/app.py
```

The first command regenerates the E1-E5 tables, confidence intervals, paired
comparisons, learning and drift figures, recovery-time summary, learned-policy
heatmap, and fixed-seed dashboard traces. Phase 5 outputs go under `results/`;
the compact dashboard data snapshot is also refreshed under `dashboard/data/`.
The configuration fixes the same ten seeds across policies. The second command
launches four views: trace replay, ledger heatmap and cold-start replay, policy
comparison, and an order-lookup drift toggle. Traces can be regenerated with
`python -m dashboard.prepare_demo` alone.

## Report and Demo

- Project report: [`report/report.md`](report/report.md)
- 14-slide presentation: [`report/slides.html`](report/slides.html)
- Scripted trace scenarios and replay data: `dashboard/data/`
- D1-D5 phase captures and silent four-minute walkthrough: `report/demo/`

The slide deck is a self-contained browser presentation. Use the arrow keys to
advance, or the Print control to export it from a browser.

The demo uses seed `2026`. The bandit refund scenario starts with explicit
prior ledger observations, then records its `refresh` choice. The 50-episode
learning sequence and each trace are reproducible. This is a synthetic
simulation: the verifier is an oracle and no external APIs or live LLM are used.

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
├── dashboard/               # Streamlit app, seeded demo builder and snapshots
├── report/                  # report, presentation and demo media
├── results/                 # generated CSVs, figures, tables (git-ignored)
└── tests/
```

## Citation

Babu, R. S., & Agrawal, A. (2026). *Self-healing agentic orchestrators for
reliable tool-augmented large language model systems.* arXiv:2606.01416.
https://doi.org/10.48550/arXiv.2606.01416
