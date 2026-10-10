# Progress

Tracks what is done and what comes next. Updated at the end of every work
session and on every meaningful change. The authoritative plan lives in
`docs/implementation.md`.

## Current status

- **Active phase:** Phase 1 — Environment (tools, data, tasks)
- **Last completed phase:** Phase 0 — Setup and contracts
- **Next unchecked task:** P1-T1 — implement `data/generator.py`

## Phase tracker

| Phase | Status | Notes |
|---|---|---|
| 0 Setup and contracts | ✅ complete | contracts fixed; 9 tests passing |
| 1 Environment | 🚧 in progress | next up |
| 2 Fault injector | ☐ not started | |
| 3 Control plane and baselines | ☐ not started | |
| 4 Ledger and bandit | ☐ not started | |
| 5 Experiments | ☐ not started | |
| 6 Dashboard, report, demo | ☐ not started | |

## Phase 0 task log

- [x] P0-T1 repository layout, `__init__.py` files, `requirements.txt`,
      `.gitignore`, minimal `README.md`
- [x] P0-T2 `core/seed.py` — `SeedManager`
- [x] P0-T3 `core/types.py` — enums and models
- [x] P0-T4 `core/interfaces.py` — `Tool` and `Policy` protocols
- [x] P0-T5 `core/trace.py` — `TraceLogger`
- [x] P0-T6 `configs/template.yaml`
- [x] P0-T7 dummy tool + dummy policy + smoke test

## Acceptance checks

- [x] `pytest tests/test_seed.py` — determinism of named RNG streams
- [x] `pytest tests/test_smoke.py` — dummy tool + policy write one valid JSONL line

## Session notes

- 2026-10-10: Repository scaffolded; `AGENTS.md` and `progress.md` added.
- 2026-10-10: Phase 0 complete — all contracts implemented, full suite green
  (9 tests). Next: Phase 1 environment (`data/generator.py`, tools, tasks).
