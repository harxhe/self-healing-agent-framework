# AGENTS.md

Guidance for AI agents (and humans) working in this repository.

## Source of truth

- **`docs/implementation.md` is the authoritative plan.** Always follow it. If a
  task in this repository conflicts with `implementation.md`, the implementation
  guide wins.
- The plan is organized in **phases that must be completed in order**. Finish
  every task in a phase (and pass its acceptance checks) before starting the
  next phase.
- `progress.md` (repo root) tracks what is done and what comes next. **Keep it
  up to date** at the end of every work session and on every meaningful change.

## Orientation protocol (do this before you start)

1. Read `docs/implementation.md` end to end.
2. Inspect the git history to see where the project currently is:

   ```bash
   git log --oneline -30
   git status
   ```

3. Read `progress.md` and corroborate it against the code and the latest
   commits. If they disagree, trust the code/commits and fix `progress.md`.
4. Identify the first **unchecked** task in the earliest **incomplete** phase and
   work from there.

## Ground rules (mirror of `implementation.md` §0)

1. **Determinism first.** Every random draw comes from the central seeded RNG
   (`healagent/core/seed.py`). Never call `random` or `numpy.random` directly
   outside the seed manager. Same seed ⇒ identical results.
2. Do **not** build against the paper's reference artifact; reimplement from the
   spec.
3. Do **not** tune the bandit to hide a flat environment. If the bandit does not
   beat Static, change the environment (`faults/profiles.py`), not the bandit.
4. The verifier is an **oracle** in simulation; state this in docstrings and the
   README.
5. Keep it simple: plain Python, no LangChain/LangGraph, no live LLM in the core
   pipeline.
6. Test as you go: every phase ends with passing `pytest` tests from its
   acceptance checks.
7. Do not modify a completed phase's public interfaces without updating
   `implementation.md` and all dependents.

## Coding conventions

- Python 3.11+ (this repo is developed on 3.12). Use type hints.
- Schemas/validation: **Pydantic v2**.
- No comments unless they add real information (docstrings are welcome where the
  spec calls for them, e.g. the oracle verifier).
- Keep modules small and focused; match the layout in `implementation.md` §2.

## Testing

- Tests live in `tests/` and use **pytest**.
- The acceptance checks named in each phase are the definition of done.
- Run the full suite before declaring a phase complete:

  ```bash
  python -m pytest -q
  ```

## Commit conventions

- Use **Conventional Commits**: `feat:`, `fix:`, `test:`, `docs:`, `chore:`,
  `refactor:`, `perf:`, `build:`, `ci:` (optionally with a scope, e.g.
  `feat(core): ...`).
- Commit in **small, logical increments** as work proceeds — one coherent change
  per commit.
- **Do not mention the phase name/number in ordinary commits.** Describe the
  change itself (e.g. `feat(core): add SeedManager for named RNG streams`).
- **Only when a phase is fully complete** (all tasks done and acceptance checks
  passing) make a dedicated milestone commit that says the phase is over, e.g.:

  ```
  chore: phase 0 complete — setup and contracts
  ```

  or

  ```
  docs: phase 2 complete — fault injector
  ```

  Include the phase number in **this milestone commit only**, not in the
  incremental commits leading up to it.
- Update `progress.md` (and tick checkboxes in `docs/implementation.md`) in the
  same milestone commit that closes a phase.

## Definition of done for a phase

1. All phase tasks are implemented.
2. All named acceptance checks pass locally via `pytest`.
3. `progress.md` is updated and `docs/implementation.md` checkboxes are ticked.
4. Ordinary commits along the way used conventional messages **without** the
   phase number; a single milestone commit states the phase is over.
