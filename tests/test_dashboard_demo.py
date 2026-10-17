import json
from pathlib import Path

from dashboard.prepare_demo import BUNDLED, prepare_demo


def test_scripted_demo_scenarios_and_traces_are_deterministic():
    first = prepare_demo()
    first_json = json.dumps(first, sort_keys=True)
    second = prepare_demo()

    assert json.dumps(second, sort_keys=True) == first_json
    scenarios = second["scenarios"]
    assert not scenarios["D2_retry_only"]["task_success"]
    assert scenarios["D2_bandit"]["task_success"]
    assert scenarios["D2_bandit"]["actions"] == ["refresh"]
    assert len(scenarios["D3_learning"]) == 50
    assert scenarios["D3_learning"][-1]["actions"] == ["retry"]
    assert scenarios["D4_before"]["actions"] == ["retry"]
    assert scenarios["D4_after"]["actions"] == ["retry", "substitute"]
    assert scenarios["D5_verifier"]["actions"] == ["repair"]

    trace = BUNDLED / f"{scenarios['D5_verifier']['run_id']}.jsonl"
    records = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    calculator = [row for row in records if row.get("tool") == "calculator"]
    assert calculator[0]["signal"] == "verifier_rejection"
    assert calculator[0]["action"] == "repair"
    assert calculator[0]["verifier_outcome"] == "pass"
