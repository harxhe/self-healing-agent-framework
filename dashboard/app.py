"""HealAgent replay dashboard for deterministic simulation traces."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from prepare_demo import RESULTS, prepare_demo, run_learning_replay

DATA = ROOT / "dashboard" / "data"
PHASE5 = ROOT / "results"
st.set_page_config(page_title="HealAgent Replay", page_icon="HA", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; max-width: 1440px; }
[data-testid="stMetric"] { border-left: 3px solid #287d72; padding-left: 12px; }
h1, h2, h3 { color: #183e3a; }
</style>
""", unsafe_allow_html=True)


def _manifest() -> dict:
    for path in (RESULTS / "manifest.json", DATA / "manifest.json"):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return prepare_demo()


def _trace(run_id: str) -> pd.DataFrame:
    for folder in (RESULTS / "traces", DATA):
        path = folder / f"{run_id}.jsonl"
        if path.exists():
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
            frame = pd.json_normalize(records, sep=".")
            for column in ("signal", "failure_class", "action", "verifier_outcome", "final_status"):
                if column not in frame:
                    frame[column] = None
            frame["signature_label"] = frame.apply(
                lambda row: " | ".join(str(row.get(f"signature.{key}", "")) for key in
                                         ("failure_class", "tool", "attempt"))
                if pd.notna(row.get("signature.failure_class")) else "-", axis=1
            )
            return frame
    return pd.DataFrame()


def _csv(name: str) -> pd.DataFrame:
    for folder in (PHASE5, DATA):
        path = folder / name
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


def _success_heatmap() -> pd.DataFrame:
    ledger_path = RESULTS / "demo" / "learning.sqlite"
    # Demo outcomes are bundled in the manifest; retain phase 5 as the broader learned-policy view.
    phase5 = _csv("learned_policy_heatmap.csv")
    if not phase5.empty:
        columns = {name.lower(): name for name in phase5.columns}
        if {"signature", "action"}.issubset(columns):
            rate = columns.get("success_rate") or columns.get("success")
            if rate:
                return phase5.pivot_table(index=columns["signature"], columns=columns["action"],
                                          values=rate, aggfunc="mean")
    manifest = _manifest()
    stats = manifest.get("ledger", {})
    rows = []
    for signature, arms in stats.items():
        for action, values in arms.items():
            rows.append({"signature": signature, "action": action,
                         "success_rate": values.get("success_rate", 0)})
    return pd.DataFrame(rows).pivot(index="signature", columns="action", values="success_rate")


def _trace_view(manifest: dict) -> None:
    labels = {
        "D2_retry_only": "Refund · RetryOnly",
        "D2_bandit": "Refund · Bandit",
        "D4_before": "Order lookup · Before drift",
        "D4_after": "Order lookup · After drift",
        "D5_verifier": "Calculator · Verifier detection",
    }
    default_trace = st.query_params.get("scenario", "D2_retry_only")
    key = st.selectbox("Recorded trace", list(labels), index=list(labels).index(default_trace)
                       if default_trace in labels else 0, format_func=labels.get)
    run_id = manifest["scenarios"][key]["run_id"]
    frame = _trace(run_id)
    if frame.empty:
        st.warning("No trace records found. Run `python -m dashboard.prepare_demo`.")
        return
    st.caption(f"Run {run_id} · seed {manifest['seed']} · {len(frame)} trace records")
    columns = [col for col in ("step", "task_id", "tool", "signal", "failure_class",
                               "signature_label", "action", "verifier_outcome", "final_status")
               if col in frame]
    st.dataframe(frame[columns], hide_index=True, width="stretch")


def _ledger_view() -> None:
    heatmap = _success_heatmap()
    st.caption("Per-signature success rate · Phase 5 aggregate when available; bundled demo ledger otherwise")
    st.dataframe(heatmap.style.background_gradient(cmap="YlGn", vmin=0, vmax=1).format("{:.0%}"),
                 width="stretch", height=520)
    st.divider()
    st.subheader("Cold-start replay")
    episodes = st.slider("Episodes", min_value=1, max_value=50, value=10)
    if st.button("Run episodes", type="primary"):
        progress = st.progress(0, text="Starting a fresh seeded ledger")
        live = st.empty()
        rows = []

        def update_progress(fraction: float, index: int, row: dict) -> None:
            progress.progress(fraction, text=f"Episode {index} / {episodes}")
            rows.append({"episode": index, "tool": row["target_tool"],
                         "action": " -> ".join(row["actions"]), "success": row["task_success"]})
            live.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            time.sleep(0.025)
        _, stats = run_learning_replay(episodes, progress=update_progress)
        matrix = []
        for signature, arms in stats.items():
            for action, values in arms.items():
                matrix.append({"signature": signature, "action": action,
                               "success_rate": values["success_rate"]})
        if matrix:
            heatmap = pd.DataFrame(matrix).pivot(index="signature", columns="action", values="success_rate")
            st.subheader("Ledger after this replay")
            st.dataframe(heatmap.style.background_gradient(cmap="YlGn", vmin=0, vmax=1).format("{:.0%}"),
                         width="stretch")


def _comparison_view(manifest: dict) -> None:
    retry = manifest["scenarios"]["D2_retry_only"]
    bandit = manifest["scenarios"]["D2_bandit"]
    left, right = st.columns(2)
    for column, title, row in ((left, "RetryOnly", retry), (right, "Bandit", bandit)):
        with column:
            st.subheader(title)
            st.metric("Task result", "Pass" if row["task_success"] else "Fail")
            st.metric("Recovery actions", " -> ".join(row["actions"]) or "none")
            st.metric("Detected failures", row["detected"])
    st.caption("Both runs use the same refund task, seed, fault kind, and fault location. The bandit trace records its seeded ledger history.")
    table = _csv("e1_table.csv")
    if not table.empty:
        st.subheader("Phase 5 policy comparison")
        st.dataframe(table, hide_index=True, width="stretch")
    else:
        st.info("Run `python -m experiments.run_all --config configs/phase5.yaml` for the full policy tables.")


def _drift_view(manifest: dict) -> None:
    after = st.toggle("Show post-drift profile", value=True)
    key = "D4_after" if after else "D4_before"
    scenario = manifest["scenarios"][key]
    frame = _trace(scenario["run_id"])
    a, b, c = st.columns(3)
    a.metric("Profile", "Persistent" if after else "Transient")
    b.metric("Recovery action", " -> ".join(scenario["actions"]) or "none")
    c.metric("Task result", "Pass" if scenario["task_success"] else "Fail")
    st.dataframe(frame[[col for col in ("step", "tool", "signal", "failure_class", "action",
                                        "verifier_outcome", "final_status") if col in frame]],
                 hide_index=True, width="stretch")
    st.caption("Drift changes the order_lookup rate-limit profile; identical seeded forced fault, different recovery outcome.")


manifest = _manifest()
st.title("HealAgent | Recovery replay")
st.caption("Seeded simulation runs · phase 5 evaluation tables · verifier is an oracle")
with st.sidebar:
    st.header("Views")
    views = ["Trace viewer", "Recovery ledger", "Policy comparison", "Drift"]
    requested_view = st.query_params.get("view", views[0])
    view = st.radio("Select a view", views, index=views.index(requested_view) if requested_view in views else 0,
                    label_visibility="collapsed")
    if st.button("Regenerate scripted runs"):
        prepare_demo()
        st.rerun()

if view == "Trace viewer":
    _trace_view(manifest)
elif view == "Recovery ledger":
    _ledger_view()
elif view == "Policy comparison":
    _comparison_view(manifest)
else:
    _drift_view(manifest)
