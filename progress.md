# Progress

Tracks what is done and what comes next. Updated at the end of every work
session and on every meaningful change. The authoritative plan lives in
`docs/implementation.md`.

## Current Status

- **Active phase:** Phase 2 - Fault injector
- **Last completed phase:** Phase 1 - Environment (tools, data, tasks)
- **Next unchecked task:** P2-T1 - implement `faults/types.py`

## Phase Tracker

| Phase | Status | Notes |
|---|---|---|
| 0 Setup and contracts | complete | contracts fixed; 9 tests passing |
| 1 Environment | complete | 100 deterministic no-fault tasks; 22 tests passing |
| 2 Fault injector | in progress | next up |
| 3 Control plane and baselines | not started | |
| 4 Ledger and bandit | not started | |
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

## Acceptance Checks

- [x] `pytest tests/test_seed.py` - determinism of named RNG streams
- [x] `pytest tests/test_smoke.py` - dummy tool + policy write one valid JSONL line
- [x] `pytest tests/test_tasks_nofault.py` - all 100 tasks pass with zero faults
- [x] Full suite repeated deterministically for the no-fault executor outputs
- [x] `pytest tests/test_tools.py` - all tools reject invalid arguments with schema errors

## Session Notes

- 2026-10-10: Repository scaffolded; `AGENTS.md` and `progress.md` added.
- 2026-10-10: Phase 0 complete - all contracts implemented, full suite green
  (9 tests). Next: Phase 1 environment (`data/generator.py`, tools, tasks).
- 2026-10-10: Phase 1 complete - deterministic data, tools, backups,
  registry, task catalog, executor, and checker implemented; full suite green
  (22 tests). Next: Phase 2 fault injector (`faults/types.py`).
