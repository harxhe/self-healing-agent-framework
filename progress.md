# Progress

Tracks what is done and what comes next. Updated at the end of every work
session and on every meaningful change. The authoritative plan lives in
`docs/implementation.md`.

## Current Status

- **Active phase:** None
- **Last completed phase:** Phase 6 - Dashboard, report, and demo
- **Next unchecked task:** None (optional P6-T6 live-LLM sanity check skipped)

## Phase Tracker

| Phase | Status | Notes |
|---|---|---|
| 0 Setup and contracts | complete | contracts fixed; 9 tests passing |
| 1 Environment | complete | 100 deterministic no-fault tasks; 22 tests passing |
| 2 Fault injector | complete | deterministic profiles, schedule, drift; 39 tests passing |
| 3 Control plane and baselines | complete | loop + baselines; 46 tests passing |
| 4 Ledger and bandit | complete | seeded algorithms; SQLite ledger; toy, mask, discount, persistence checks |
| 5 Experiments | complete | E1-E5, ten paired seeds, 95% CIs, post-drift checkpoint passed |
| 6 Dashboard, report, demo | complete | Four-view Streamlit replay app; deterministic D1-D5 traces; report; 14-slide browser deck; five phase captures; four-minute silent backup video |

## Phase 0 Task Log

- [x] P0-T1 repository layout, `__init__.py` files, `requirements.txt`,
      `.gitignore`, minimal `README.md`
- [x] P0-T2 `core/seed.py` - `SeedManager`
- [x] P0-T3 `core/types.py` - enums and models
- [x] P0-T4 `core/interfaces.py` - `Tool` and `Policy` protocols
- [x] P0-T5 `core/trace.py` - `TraceLogger`
- [x] P0-T6 `configs/template.yaml`
- [x] P0-T7 dummy tool + dummy policy + smoke test

## Phase 1 Task Log

- [x] P1-T1 `data/generator.py` seeded synthetic e-commerce world
- [x] P1-T2 deterministic schema-validated primary tools
- [x] P1-T3 backup tools and `SUBSTITUTES`
- [x] P1-T4 `tools/registry.py`
- [x] P1-T5 100 tasks in `tasks/tasks.json`, 20 per category
- [x] P1-T6 `tasks/executor.py` scripted no-LLM execution
- [x] P1-T7 `tasks/checker.py` exact-match success checks

## Phase 2 Task Log

- [x] P2-T1 `faults/types.py` deterministic ToolResult fault transformations
- [x] P2-T2 `faults/profiles.py` per-tool transient/persistent profiles + `fixed_by`
- [x] P2-T3 `faults/schedule.py` policy-independent deterministic fault firing
- [x] P2-T4 intensity levels `{0.0..0.5}`, primary/stress regimes
- [x] P2-T5 `faults/drift.py` profile swap + drift trace logging
- [x] P2-T6 `faults/injector.py` wraps tools, models recovery-action success

## Phase 3 Task Log

- [x] P3-T1 `control/detector.py` structural failure signals (no fault-flag peeking)
- [x] P3-T2 `control/diagnoser.py` signal -> `Signature(failure_class, tool, attempt)`
- [x] P3-T3 `control/actions.py` retry/repair/substitute/refresh/replan/degrade/escalate/terminate
- [x] P3-T4 `control/verifier.py` oracle verifier + verifier-call counting
- [x] P3-T5 `control/budget.py` attempts/cost/latency/depth budget with `exhausted()`
- [x] P3-T6 `control/orchestrator.py` Monitor->Detect->Diagnose->Recover->Verify loop
- [x] P3-T7 `control/mask.py` feasibility mask
- [x] P3-T8 `policy/retry_only.py`, `policy/static.py` baselines + `policy/reward.py`
- [x] P3-T9 `experiments/run.py` runner writing traces + summary CSV + config snapshot
- Additive: `faults/injector.py` gained optional `forced_faults` for scripted tests/demos

## Phase 4 Task Log

- [x] P4-T1 `ledger/ledger.py` - SQLite records, per-signature/action stats, reopen, reset
- [x] P4-T2 `ledger/arms.py` - recency-weighted discounting and sliding window
- [x] P4-T3 `policy/reward.py` - configurable cost and latency reward
- [x] P4-T4-T5 `policy/bandit.py` - seeded epsilon-greedy, UCB1, and Thompson sampling
- [x] P4-T6 warm static-map priors and cold uniform priors
- [x] P4-T7 config-driven bandit selection, masks, reward options, and runner integration
- [x] P4-T8 seeded toy environment and learning tests

## Phase 5 Task Log

- [x] P5-T1 `healagent/metrics/` - task metrics, t-based 95% CIs, paired differences
- [x] P5-T2 E1 main policy comparison at intensities 0.0-0.5
- [x] P5-T3 E2 cold/warm learning curves for TSR and cumulative regret
- [x] P5-T4 E3 drift curves and recovery-time analysis
- [x] P5-T5 E4 algorithm/start/cost/mask/discount ablations
- [x] P5-T6 E5 semantic-fault verifier on/off comparison
- [x] P5-T7 `results/learned_policy_heatmap.csv` exported from final SQLite ledgers
- [x] P5-T8 `python -m experiments.run_all --config configs/phase5.yaml` regenerates artifacts
- [x] Checkpoint: bandit regained pre-drift TSR in 1.5 episodes on average vs. 2.5 for StaticMapping; environment unchanged

## Phase 6 Task Log

- [x] P6-T1 `dashboard/app.py` - trace viewer, success-rate heatmap, paired policy comparison, drift toggle
- [x] P6-T2 replay fixed-seed traces from `results/` with bundled `dashboard/data/` fallback; cold-start N-episode replay executes the orchestrator
- [x] P6-T3 deterministic D1-D5 scenarios, including refund refresh, 50-episode learning, order-lookup drift, and oracle-detected calculator error
- [x] P6-T4 `report/report.md` separates paper-derived architecture from project contributions and states simulation limits
- [x] P6-T5 14-slide browser presentation with project results and paper attribution; no paper numbers presented as project results
- [ ] P6-T6 optional live-LLM sanity check skipped; main pipeline remains offline and deterministic
- [x] P6-T7 README setup/reproduction/layout/citation updated; local `v1.0` tag created after milestone commit
- [x] P6-T8 D1-D5 still captures and four-minute silent slideshow backup at `report/demo/`

## Acceptance Checks

- [x] `pytest tests/test_seed.py` - determinism of named RNG streams
- [x] `pytest tests/test_smoke.py` - dummy tool + policy write one valid JSONL line
- [x] `pytest tests/test_tasks_nofault.py` - all 100 tasks pass with zero faults
- [x] Full suite repeated deterministically for the no-fault executor outputs
- [x] `pytest tests/test_tools.py` - all tools reject invalid arguments with schema errors
- [x] `pytest tests/test_fault_determinism.py` - identical faults for same `(task, seed, intensity)` across policies
- [x] `pytest tests/test_drift.py` - retry fixes `order_lookup` rate limits before drift, fails after (substitute works)
- [x] `pytest tests/test_fault_summary.py` - all fault kinds occur; transient/persistent matches profiles
- [x] `pytest tests/test_orchestrator.py` - injected timeout detected/diagnosed/recovered/verified/logged
- [x] intensity 0.0 -> 100% TSR for both baselines
- [x] intensity 0.2-0.3 -> StaticMapping TSR > RetryOnly TSR (0.99 vs 0.67 at 0.2), traces for both
- [x] budget exhaustion degrades/escalates with no infinite loops
- [x] `pytest tests/test_bandit_toy.py`, `tests/test_mask.py`, `tests/test_discount.py` - seeded algorithms learn; mask and drift-discount behavior hold
- [x] Ledger reopen/reset persistence check
- [x] `python -m experiments.run_all --config configs/phase5.yaml` - all E1-E5 artifacts and heatmap regenerated
- [x] `python -m pytest -q` - 67 tests passed
- [x] `streamlit run dashboard/app.py` - four dashboard views render from recorded or bundled results
- [x] Dashboard AppTest - all four view paths and cold-start episode replay complete without exceptions
- [x] `python -m pytest -q` - 68 tests passed after Phase 6 additions
- [x] Demo manifest and traces reproduce identically at seed 2026
- [x] Backup MP4 validated at 240 seconds; 14-slide presentation and D1-D5 captures rendered

## Session Notes

- 2026-10-10: Repository scaffolded; `AGENTS.md` and `progress.md` added.
- 2026-10-10: Phase 0 complete - all contracts implemented, full suite green
  (9 tests). Next: Phase 1 environment (`data/generator.py`, tools, tasks).
- 2026-10-10: Phase 1 complete - deterministic data, tools, backups,
  registry, task catalog, executor, and checker implemented; full suite green
  (22 tests). Next: Phase 2 fault injector (`faults/types.py`).
- 2026-10-10: Phase 2 complete - fault types, per-tool profiles, deterministic
  schedule, drift, and injector implemented; full suite green (39 tests).
  Note: P2-T1 lists 8 injectable fault kinds (not 7); `faults/types.py`
  implements all 8 and the summary test asserts every kind occurs.
  Next: Phase 3 control plane and baselines.
- 2026-10-10: Phase 3 complete - detector, diagnoser, feasibility mask, budget,
  oracle verifier, recovery actions, orchestrator loop, RetryOnly/StaticMapping
  baselines, and `experiments/run.py` implemented; full suite green (46 tests).
  Static > Retry at intensity 0.2/0.3 (0.99 vs 0.67). Verifier is an oracle;
  it is deliberately strong and documented as such. `policy/reward.py` landed
  early (needed by the loop; formally P4-T3). Next: Phase 4 ledger + bandits.
- 2026-10-18: Phase 4 complete - persistent ledger, recency-weighted arm stats,
  seeded epsilon-greedy/UCB1/Thompson policies, warm/cold starts, and toy
  acceptance tests. Full suite: 67 passed.
- 2026-10-18: Phase 5 complete - E1-E5, paired ten-seed comparisons, 95% CIs,
  drift recovery, verifier ablation, and SQLite-derived heatmap regenerated by
  one command. Bandit post-drift recovery averaged 1.5 episodes vs. 2.5 for
  StaticMapping; the environment required no adjustment. SFR uses all completed
  tasks as its denominator. Next: Phase 6.
- 2026-10-18: Phase 6 complete - Streamlit replay dashboard, fixed-seed D1-D5
  scenarios, bundled result snapshots, report, 14-slide browser presentation,
  phase captures, and four-minute silent backup walkthrough. Full suite: 68
  passed. Optional live-LLM sanity check not run. The combined full E1-E5
  reproduction wrapper was started but interrupted during ablations; Phase 5's
  existing `experiments.run_all` acceptance run remains the verified baseline.
