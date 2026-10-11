# Progress

Tracks what is done and what comes next. Updated at the end of every work
session and on every meaningful change. The authoritative plan lives in
`docs/implementation.md`.

## Current Status

- **Active phase:** Phase 4 - Ledger and bandit policies
- **Last completed phase:** Phase 3 - Control plane and baselines
- **Next unchecked task:** P4-T1 - implement `ledger/ledger.py`

## Phase Tracker

| Phase | Status | Notes |
|---|---|---|
| 0 Setup and contracts | complete | contracts fixed; 9 tests passing |
| 1 Environment | complete | 100 deterministic no-fault tasks; 22 tests passing |
| 2 Fault injector | complete | deterministic profiles, schedule, drift; 39 tests passing |
| 3 Control plane and baselines | complete | loop + baselines; 46 tests passing |
| 4 Ledger and bandit | in progress | next up |
| 5 Experiments | not started | |
| 6 Dashboard, report, demo | not started | |

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
