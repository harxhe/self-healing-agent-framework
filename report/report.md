# HealAgent Project Report

## Summary

HealAgent is a deterministic simulation of a self-healing tool-using agent. It
implements a bounded Monitor-Detect-Diagnose-Recover-Verify controller and adds
a persistent recovery ledger with seeded bandit policies. Across the current
synthetic experiments, StaticMapping remains strongest on raw task success at
moderate fault intensities. The bandit's clearest measured advantage is faster
recovery after the configured order-lookup drift: 1.5 episodes on average,
compared with 2.5 for StaticMapping and 7.8 for RetryOnly. These results support
a narrow claim about adaptation in this simulation, not general superiority in
deployed LLM systems.

## Scope and Attribution

The project follows the control-loop framing in Babu and Agrawal (2026):
observe tool execution, infer a failure class from signals, select a bounded
recovery action, verify the result, and retain an observability trace. The
failure vocabulary, recovery loop, oracle-verification framing, call-budget
metrics, and controlled fault-injection evaluation are inherited design
elements. The paper reports its own benchmark and results; none of its success
rates or task counts are reproduced or claimed as HealAgent results.

This repository reimplements the simulation from its implementation
specification. Its new project contributions are the SQLite Recovery Ledger,
per-signature seeded epsilon-greedy/UCB1/Thompson selectors, explicit per-tool
fault profiles, a deterministic drift event, and a synthetic e-commerce task
environment. The StaticMapping policy is a local baseline representation of a
fixed failure-class-to-action table, not a claim that the repository is the
paper's reference artifact.

## System

Tasks are scripted calls over simulated customer, order, inventory, shipping,
policy, calculator, and evidence tools. A deterministic fault schedule injects
timeouts, unavailable tools, rate limits, partial responses, stale context,
malformed output, and semantic errors. A detector uses observable outputs,
not the injector's private fault flag. A diagnoser maps a signal and tool to a
failure signature. Feasibility masks remove unsupported actions. The selected
action is budgeted, verified against known task ground truth, and written to a
JSONL trace. Recovery rewards discount call cost and simulated latency.

The verifier is an oracle in this simulation. It has access to task success
criteria and is intentionally stronger than a production verifier could be.
All reported results are generated without a live LLM or external API.

## Evaluation

Phase 5 evaluates RetryOnly, StaticMapping, and BanditPolicy on the same 100
synthetic tasks, with ten fixed seeds, fault intensities from 0.0 to 0.5, and
paired comparisons. It reports task success rate (TSR), recovery success rate
(RSR), silent failure rate (SFR), call-proxy cost, simulated latency, regret,
and t-based 95% confidence intervals. Additional runs measure cold/warm
learning, profile drift, policy and cost/mask ablations, and verifier behavior
under semantic faults.

At intensity 0.2, mean TSR is 99.5% for StaticMapping, 78.1% for BanditPolicy,
and 69.9% for RetryOnly. At intensity 0.3, the corresponding results are
99.0%, 72.0%, and 57.6%. The bandit does not beat StaticMapping on these main
TSR comparisons. This is an important negative result and is not hidden by the
drift checkpoint.

After order_lookup changes from a transient rate-limit profile to a persistent
one, mean recovery time is 1.5 episodes for BanditPolicy, 2.5 for StaticMapping,
and 7.8 for RetryOnly. All three policies regain the measured pre-drift TSR
threshold in all ten seeds. The recovery-time intervals are wide at this
sample size, so this is evidence for the configured drift scenario rather
than a broad statistical claim.

In the semantic-fault ablation at intensity 0.3, verifier-enabled runs report
zero SFR for all three policies; without verification the SFR is 6% in the
aggregated sample. This validates the oracle's role in the simulator, not a
real-world guarantee.

## Scripted Demonstration

The dashboard bundles fixed-seed traces (seed 2026) for:

- Refund policy lookup with a partial response. RetryOnly exhausts recovery
  attempts; a bandit initialized from explicit prior ledger observations
  chooses `refresh` and succeeds.
- Fifty alternating episodes with persistent shipping-estimator timeouts and
  transient customer-lookup timeouts. The final episodes use `substitute` for
  shipping and `retry` for customer lookup.
- An order-lookup rate-limit profile before and after drift. The static policy
  retries before drift; after drift it moves to `substitute`.
- A plausible but wrong calculator result rejected by the oracle verifier;
  the static policy repairs it.

The dashboard can replay these recorded JSONL files, show the signal/signature/
action/verifier sequence, display phase 5 ledger success rates, compare policies,
and run a fresh N-episode simulation while showing the ledger fill from a cold
start.

## Limitations

- Tools and customer-support tasks are simulated and synthetic.
- The verifier is an oracle with access to ground truth.
- The 100 tasks are compact and scripted; they do not measure open-ended
  language understanding, planning quality, or tool API variability.
- Fault probabilities and recovery profiles are specified by the environment.
- Bandit policies are tabular and signatures are hand-structured.
- Cost is a call-count proxy and latency is simulated.
- No live API or LLM is in the core pipeline; there is no production safety,
  privacy, or reliability evaluation.

## Reproduction

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m experiments.reproduce --config configs/phase5.yaml
streamlit run dashboard/app.py
```

The experiment command regenerates the CSV tables and figures under `results/`
and refreshes the bundled demo tables and traces under `dashboard/data/`.

## Reference

Babu, R. S., & Agrawal, A. (2026). *Self-Healing Agentic Orchestrators for
Reliable Tool-Augmented Large Language Model Systems.* arXiv:2606.01416.
[https://doi.org/10.48550/arXiv.2606.01416](https://doi.org/10.48550/arXiv.2606.01416)
