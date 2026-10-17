# HealAgent: Implementation Guide

This file is the implementation plan for the project. The phases are meant to be completed **in order**: finish every task in a phase, and pass its acceptance checks, before starting the next one. Tick the checkbox (`[x]`) when a task is done.

## 0. Project summary

**HealAgent** is an adaptive self-healing agent framework, simulated end to end (no live LLM is required for core results).

- It extends the Monitor → Detect → Diagnose → Recover → Verify loop from *Babu & Agrawal (2026), "Self-Healing Agentic Orchestrators for Reliable Tool-Augmented LLM Systems", arXiv:2606.01416*.
- **New contribution:** a **Recovery Ledger** (`failure signature → recovery action → outcome`) and a **bandit-based policy selector** that learns which recovery action works best for each failure signature, instead of using a fixed mapping.
- **Simulated agent:** an e-commerce customer-support agent (customer, order, inventory, shipping, policy, calculator tools).
- **Compared policies:** `RetryOnly`, `StaticMapping` (the paper's table), `BanditPolicy` (ours).
- **Metrics:** Task Success Rate (TSR), Recovery Success Rate (RSR), Silent Failure Rate (SFR), cost, latency.

### Ground rules

1. **Determinism first.** Every random draw must come from the central seeded RNG (Phase 0). Same seed must produce identical results. Never call `random` or `numpy.random` directly outside the seed manager.
2. **Do not build against the paper's GitHub artifact.** Reimplement everything from this spec.
3. **Do not tune the bandit to hide a flat environment.** If the bandit does not beat Static, change the environment (Phase 5 checkpoint), not the bandit.
4. **The verifier is an oracle** in simulation (it checks against known task success criteria). State this in code docstrings and in the README.
5. **Keep it simple.** Plain Python, no LangChain or LangGraph. No live LLM calls in the core pipeline.
6. **Test as you go.** Every phase ends with passing `pytest` tests listed in its acceptance checks.
7. **Do not modify completed phases' public interfaces** without updating this file and all dependents.

## 1. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Schemas / validation | Pydantic v2 |
| Numerics / learning | NumPy, SciPy |
| Storage | SQLite (ledger), JSONL (traces) |
| Experiments and plots | pandas, matplotlib, seaborn, Jupyter |
| Config | YAML (PyYAML) |
| Tests | pytest |
| Dashboard | Streamlit |
| Env management | `uv` or `venv`, `requirements.txt` |
| Optional live LLM | Ollama or any tool-calling API (Phase 6 only, optional) |

## 2. Repository layout

```
healagent/
├── README.md
├── implementation.md
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
├── experiments/             # runners for E1-E5, plotting scripts
├── dashboard/               # Streamlit app
├── results/                 # generated CSVs, figures, tables (git-ignored except final)
└── tests/
```

## 3. Core definitions (used across all phases)

**Recovery actions** (enum `Action`): `retry`, `repair`, `substitute`, `refresh`, `replan`, `degrade`, `escalate`, `terminate`.

**Failure classes** (enum `FailureClass`): `timeout`, `unavailable`, `rate_limit`, `schema_error` (malformed args), `malformed_output`, `partial_response`, `stale_context`, `contradictory_evidence`, `semantic_wrong` (wrong-but-plausible, verifier-detected), `control_loop` (retry storm, no progress).

**Failure signature:** `Signature(failure_class, tool, attempt)`, where `attempt` is the recovery attempt number for this step (1, 2, 3, capped).

**Reward for a recovery attempt:** `r = success − λ·cost − μ·latency`, where `success ∈ {0,1}`, cost is the call-count proxy for the attempt, latency is simulated latency, and `λ`, `μ` come from config (defaults `λ=0.05`, `μ=0.01`).

**Cost proxy per task:** `N_tool + N_model + N_verify` (call counts).

**Metrics:**
- `TSR = tasks completed correctly / total tasks`
- `RSR = successfully recovered detected failures / detected failures`
- `SFR = incorrect outputs returned without detection / total completed outputs`

**Core interfaces** (define exactly these in `healagent/core/`):

```python
class Tool(Protocol):
    name: str
    def call(self, args: dict) -> "ToolResult": ...

class Policy(Protocol):
    name: str
    def select(self, signature: "Signature", mask: set["Action"]) -> "Action": ...
    def update(self, signature: "Signature", action: "Action", reward: float) -> None: ...
```

`ToolResult` fields: `ok: bool`, `output: Any`, `error: str | None`, `latency_ms: float`, `fault_injected: str | None`.

**Trace record** (one JSONL line per step, Pydantic model `TraceRecord`): `run_id, task_id, method, seed, episode, step, tool, args, fault_injected, signal, failure_class, signature, action, verifier_outcome, budget_remaining, cost, latency_ms, final_status`.

---

## Phase 0: Setup and contracts

**Goal:** Fix the shared interfaces so every later phase fits together. Reproducible runs from one seed.

**Tasks**
- [x] **P0-T1** Create the repository layout from section 2, with `__init__.py` files, `requirements.txt`, `.gitignore`, and a minimal `README.md`.
- [x] **P0-T2** Implement `core/seed.py`: a `SeedManager(master_seed)` that hands out independent, named RNG streams (e.g. `rng("faults", task_id, step)`), derived deterministically from the master seed.
- [x] **P0-T3** Implement `core/types.py`: enums `Action`, `FailureClass`; dataclasses/Pydantic models `Signature`, `ToolResult`, `Task`, `TraceRecord`.
- [x] **P0-T4** Implement `core/interfaces.py`: `Tool` and `Policy` protocols exactly as in section 3.
- [x] **P0-T5** Implement `core/trace.py`: a `TraceLogger` that appends `TraceRecord` as JSONL to `results/traces/<run_id>.jsonl`.
- [x] **P0-T6** Create `configs/template.yaml` with fields: `seeds`, `fault_intensity`, `policy`, `budget` (attempts, cost, latency), `lambda`, `mu`, `episodes`, `drift` (episode, tool, new_profile).
- [x] **P0-T7** Add a dummy tool and dummy policy plus a smoke test that runs them end to end.

**Acceptance checks**
- [x] `pytest tests/test_seed.py`: same master seed gives identical draws; different stream names give different draws.
- [x] `pytest tests/test_smoke.py`: dummy tool + dummy policy run and write exactly one valid JSONL trace line.

---

## Phase 1: Environment (tools, data, tasks)

**Goal:** A trustworthy simulated e-commerce world where all 100 tasks pass with zero faults.

**Tasks**
- [x] **P1-T1** Implement `data/generator.py`: seeded synthetic data, about 50 customers, 50 orders, 50 SKUs, a policy table (refund window, restocking fee, shipping rules). Data must be internally consistent so expected answers are always computable.
- [x] **P1-T2** Implement tools in `tools/`, each with a Pydantic input schema and deterministic output: `customer_lookup(customer_id)`, `order_lookup(order_id)`, `inventory_lookup(sku)`, `shipping_estimator(zip, weight)`, `policy_lookup(topic)`, `calculator(expression)`, `evidence_checker(claim, sources)`.
- [x] **P1-T3** Implement **backup tools** for substitution: `shipping_estimator_backup`, `refund_calculator` (substitute for `calculator`), `order_lookup_backup`. Define a `SUBSTITUTES` map in `tools/registry.py`. Tools without a backup must be absent from the map (this drives the feasibility mask in Phase 4).
- [x] **P1-T4** Implement `tools/registry.py`: lookup by name, schema listing, `SUBSTITUTES`.
- [x] **P1-T5** Define the 100 tasks in `tasks/tasks.json`, 20 per category: (1) order status, (2) refund eligibility, (3) stock and shipping, (4) multi-step workflow, (5) contradiction resolution. Each task has: `task_id, category, request, plan (ordered tool calls with args), expected_answer, success_criteria, eligible_faults`.
- [x] **P1-T6** Implement `tasks/executor.py`: runs a plan step by step through the registry, collects observations, and produces a final answer by a scripted answer function (no LLM).
- [x] **P1-T7** Implement `tasks/checker.py`: compares the final answer to `expected_answer` per `success_criteria`.

**Acceptance checks**
- [x] `pytest tests/test_tasks_nofault.py`: all 100 tasks pass at 100% with zero faults.
- [x] Running the full suite twice with the same seed gives identical outputs.
- [x] Every tool rejects invalid arguments with a schema error.

---

## Phase 2: Fault injector

**Goal:** Deterministic, task-aware faults designed so that a fixed failure → action mapping is sometimes wrong.

**Tasks**
- [x] **P2-T1** Implement fault types in `faults/types.py`, each as a transformation of a `ToolResult`: `timeout`, `unavailable`, `rate_limit`, `schema_drift/malformed_args`, `malformed_output`, `partial_response`, `stale_context`, `semantic_wrong` (syntactically valid but wrong value that violates the success criterion).
- [x] **P2-T2** Implement per-tool **fault profiles** in `faults/profiles.py`. Each profile defines, per `(tool, fault)`: whether it is **transient** or **persistent**, and which actions actually fix it. Required profiles:
  - `shipping_estimator` timeout: persistent (retry fails, substitute works).
  - `customer_lookup` timeout: transient (retry works, cheapest).
  - `policy_lookup` partial_response: fixed by `refresh`, not by retry.
  - `calculator` semantic_wrong: only verifier-driven regenerate/substitute fixes it.
  - `inventory_lookup` stale_context: fixed by `refresh`.
  - `order_lookup` rate_limit: initially fixed by retry-with-backoff (changes under drift).
- [x] **P2-T3** Implement `faults/schedule.py`: whether a fault fires at a step is a deterministic function of `(task_id, step, trial_seed, intensity, recovery_attempt)`. All policies must see identical faults for the same `(task, seed)`.
- [x] **P2-T4** Implement intensity `λ ∈ {0.0, 0.1, 0.2, 0.3, 0.4, 0.5}` applied per eligible tool step. Primary regime: 0.0–0.3. Stress regime: 0.4–0.5.
- [x] **P2-T5** Implement `faults/drift.py`: at episode `N` (from config), swap a tool's profile (default: `order_lookup` starts rate limiting such that retry no longer works and only `substitute` works). Log the drift event to the trace.
- [x] **P2-T6** Implement `faults/injector.py`: wraps any tool, consults the schedule and profile, and returns the faulted `ToolResult` with `fault_injected` set. Must model whether each recovery action succeeds, according to the profile.

**Acceptance checks**
- [x] `pytest tests/test_fault_determinism.py`: fault logs for two different policies are identical for the same `(task, seed, intensity)`.
- [x] `pytest tests/test_drift.py`: before the drift episode, retry fixes `order_lookup` rate limits; after it, retry fails and substitute works.
- [x] A printed fault summary shows all 7 fault types occur and the per-tool transient/persistent behavior matches the profiles.

---

## Phase 3: Control plane and baselines

**Goal:** The paper's Monitor → Detect → Diagnose → Recover → Verify loop, plus the Retry-Only and Static baselines.

**Tasks**
- [x] **P3-T1** Implement `control/detector.py`: converts a `ToolResult` and execution state into a failure signal (exception, timeout, schema violation, empty/partial output, verifier rejection, repeated-action pattern) or `None`.
- [x] **P3-T2** Implement `control/diagnoser.py`: maps a signal and state to a `Signature(failure_class, tool, attempt)`.
- [x] **P3-T3** Implement `control/actions.py`: executable recovery actions, each returning a new observation and its cost and latency:
  - `retry` (with exponential backoff; simulated latency grows per attempt)
  - `repair` (regenerate/fix arguments)
  - `substitute` (use `SUBSTITUTES[tool]`; infeasible if none)
  - `refresh` (re-fetch fresh/complete data)
  - `replan` (restart from the last stable checkpoint; higher cost)
  - `degrade` (return partial result with an uncertainty notice)
  - `escalate`, `terminate`
- [x] **P3-T4** Implement `control/verifier.py`: oracle check against the task `success_criteria` and tool ground truth. On rejection, emit a `semantic_wrong` signal into the loop. Count verifier calls for the cost proxy. Docstring must state it is an oracle.
- [x] **P3-T5** Implement `control/budget.py`: per-task budget for attempts, cost, latency, and recovery depth. Failed recovery still consumes budget. Expose `exhausted()`.
- [x] **P3-T6** Implement `control/orchestrator.py`: the main loop (follow Algorithm 1 of the paper): execute step → detect → (if failure) diagnose → ask `policy.select(signature, mask)` → apply action → verify → `policy.update(...)` → log trace → continue until done or budget exhausted; finish with final verification, degrade, or escalate.
- [x] **P3-T7** Implement `control/mask.py`: `feasible_actions(signature, tool)` returning the set of allowed actions (e.g. `substitute` only if the tool has a backup; no `refresh` for pure computation tools).
- [x] **P3-T8** Implement baselines in `policy/`:
  - `RetryOnly`: always `retry` up to a fixed limit, then terminate.
  - `StaticMapping`: the paper's failure-class → action table (timeout→retry then substitute; schema_error→repair; malformed_output→repair/alt tool; partial_response→repair; stale_context→refresh; contradictory_evidence→cross-check/verifier; semantic_wrong→regenerate with verification; control_loop→replan/degrade).
- [x] **P3-T9** Implement a runner `experiments/run.py` that takes a config, runs `(tasks × policy × seeds)`, and writes traces and a per-run summary CSV.

**Acceptance checks**
- [x] `pytest tests/test_orchestrator.py`: a task with one injected timeout is detected, diagnosed, recovered, verified, and logged.
- [x] With intensity 0.0, all policies reach 100% TSR.
- [x] With intensity 0.2–0.3, `StaticMapping` TSR > `RetryOnly` TSR, and traces exist for both.
- [x] Budget exhaustion ends the task through `degrade`/`escalate`, with no infinite loops.

---

## Phase 4: Ledger and bandit policies (core contribution)

**Goal:** A Recovery Ledger and bandit selector that learns the best recovery action per failure signature.

**Tasks**
- [x] **P4-T1** Implement `ledger/ledger.py` on SQLite. Table `records(id, run_id, episode, failure_class, tool, attempt, action, success, cost, latency, reward, timestamp)`. Methods: `log(...)`, `stats(signature) -> per-action {n, successes, mean_reward}`, `reset()`.
- [x] **P4-T2** Implement arm statistics in `ledger/arms.py`, supporting **discounting** (`gamma`) and an optional **sliding window** so old evidence fades under drift.
- [x] **P4-T3** Implement the reward function in `policy/reward.py`: `r = success − λ·cost − μ·latency`, parameters from config.
- [x] **P4-T4** Implement the tabular bandit base in `policy/bandit.py`: one ledger-backed bandit per signature, feasibility-mask handling, and logged updates.
- [x] **P4-T5** Implement three selection algorithms:
  - `EpsilonGreedy` (with decaying ε)
  - `UCB1`
  - `ThompsonSampling` (Beta posteriors on success; handle reward vs. success consistently and document the choice)
- [x] **P4-T6** Implement **warm start**: optional prior initialization from the `StaticMapping` table (pseudo-counts for the static action), and a **cold start** mode with uniform priors.
- [x] **P4-T7** Wire the configurable bandit factory (algorithm, warm/cold, discount, mask on/off, cost term on/off) into `policy/` and the runner.
- [x] **P4-T8** Build a **toy environment** in `tests/toy_env.py` with known best actions per signature, to verify learning independently of the full simulator.

**Acceptance checks**
- [x] `pytest tests/test_bandit_toy.py`: each algorithm converges to the known best action within 900 episodes across three seeds.
- [x] `pytest tests/test_mask.py`: the bandit never selects an action outside the mask; an empty mask terminates safely.
- [x] `pytest tests/test_discount.py`: after the toy environment's best action flips mid-run, the discounted bandit switches while the non-discounted one lags.
- [x] Ledger persists across runs (re-opening the SQLite file retains statistics) and `reset()` clears it.

---

## Phase 5: Experiments

**Goal:** Produce the evidence for every claim. Use **10–20 seeds**, report **mean with 95% confidence intervals**, and compare **paired** on identical fault schedules.

**Tasks**
- [ ] **P5-T1** Implement `metrics/`: TSR, RSR, SFR, cost proxy, mean latency, cumulative regret relative to the profile-ground-truth best feasible action, t-based confidence intervals, and paired differences.
- [ ] **P5-T2** **E1 Main comparison:** `RetryOnly` vs `StaticMapping` vs `BanditPolicy` at intensities 0.0–0.5. Output `results/e1_main.csv` and a table of TSR, RSR, SFR, cost, latency.
- [ ] **P5-T3** **E2 Learning curve:** TSR and cumulative regret over episodes for the bandit (cold and warm) vs the baselines. Output a figure with confidence bands.
- [ ] **P5-T4** **E3 Drift:** run with the drift event (Phase 2). Plot success over episodes with a vertical line at the drift episode for all three policies. Report recovery time after drift (episodes to regain pre-drift success).
- [ ] **P5-T5** **E4 Ablations:** UCB1 vs Thompson vs ε-greedy; cold vs warm start; cost term on/off; feasibility mask on/off; discounting on/off. Output a table.
- [ ] **P5-T6** **E5 Silent failures:** semantic-fault intensity `λs ∈ {0.0, 0.1, 0.2, 0.3}`; compare SFR and TSR with verifier on vs off, for each policy.
- [ ] **P5-T7** Create a learned-policy heatmap data export: per-signature best action and success rate from the final SQLite ledger.
- [ ] **P5-T8** Add `python -m experiments.run_all --config configs/phase5.yaml` to regenerate the CSVs, figures, and tables.

**Checkpoint (must do before continuing)**
- [ ] After E1 and E3, check whether the bandit beats `StaticMapping` (TSR, or cost at equal TSR, or post-drift recovery). **If it does not,** adjust the *environment* (more varied per-tool behaviors in `faults/profiles.py`, stronger cost differences between actions), rerun, and document the change. Do **not** tune the bandit to hide a flat environment.

**Acceptance checks**
- [ ] One command regenerates all results from scratch.
- [ ] All reported numbers come with 95% CIs and use the same seeds across policies.
- [ ] Results are saved under `results/` with config snapshots for reproducibility.

---

## Phase 6: Dashboard, report, and demo

**Goal:** Package the project for presentation.

**Tasks**
- [ ] **P6-T1** Build the Streamlit app in `dashboard/app.py` with: a **trace viewer** (signal → signature → action → verifier result per step), a **ledger heatmap** (signature × action, colored by success rate), a **policy comparison** view (side-by-side runs on the same fault schedule), and a **drift toggle**.
- [ ] **P6-T2** Make the dashboard **replay recorded seeded runs** (loaded from `results/`) so demos are deterministic. Include a "run N episodes" mode that animates ledger filling from a cold start.
- [ ] **P6-T3** Prepare the scripted demo runs (fixed seed): (D1) setup screen; (D2) refund task with a `policy_lookup` partial-response fault where Retry-Only fails and the bandit uses `refresh`; (D3) ledger heatmap learning over about 50 episodes (shipping → `substitute`, customer → `retry`); (D4) drift toggle on `order_lookup`; (D5) silent failure on `calculator` caught by the verifier.
- [ ] **P6-T4** Write the report (`report/`) with a clear split: **from the paper** (loop architecture, failure classes, metrics, evaluation style) vs **new** (ledger, bandit selector, drift environment, per-tool fault profiles). Include limitations: simulated tools, oracle verifier, synthetic tasks, no real APIs.
- [ ] **P6-T5** Create the slide deck (about 12–14 slides): problem, base paper and its limitation, our idea, architecture (new parts highlighted), bandit design, why simulate, setup, E1 results, learning curve, drift, ablations, limitations, conclusion and future work.
- [ ] **P6-T6** *(Optional)* A 20–30 task live-LLM sanity check with Ollama or an API, run through the same orchestrator; clearly labeled as a sanity check, not a main result.
- [ ] **P6-T7** Finalize the `README.md` with setup, a one-command reproduction of all figures, the repo layout, and the paper citation. Tag the repo (`v1.0`).
- [ ] **P6-T8** Record a backup demo video (about 4 minutes) and export static screenshots of each demo phase.

**Acceptance checks**
- [ ] The dashboard runs with `streamlit run dashboard/app.py` and shows all four views using recorded results.
- [ ] A person who did not write the code can follow the README to reproduce the figures and launch the dashboard.
- [ ] The report and slides clearly credit the paper for the loop architecture and do not present the paper's numbers as ours.

---

## Appendix A: Phase completion log

Update this table as phases finish.

| Phase | Status | Notes |
|---|---|---|
| 0 Setup and contracts | ✅ | contracts fixed; 9 tests passing |
| 1 Environment | ✅ | 100 deterministic no-fault tasks; 22 tests passing |
| 2 Fault injector | ✅ | deterministic profiles, schedule, drift; 39 tests passing |
| 3 Control plane and baselines | ✅ | loop + baselines; Static (0.99) > Retry (0.67) at intensity 0.2; 46 tests passing |
| 4 Ledger and bandit | ✅ | seeded bandits, SQLite ledger, toy convergence/mask/discount coverage; full suite 67 passed |
| 5 Experiments | ☐ | |
| 6 Dashboard, report, demo | ☐ | |

## Appendix B: Reference

Babu, R. S., & Agrawal, A. (2026). *Self-healing agentic orchestrators for reliable tool-augmented large language model systems.* arXiv:2606.01416. https://doi.org/10.48550/arXiv.2606.01416
