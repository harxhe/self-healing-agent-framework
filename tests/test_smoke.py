from __future__ import annotations

from pathlib import Path

from healagent.core.dummy import DummyPolicy, DummyTool
from healagent.core.trace import TraceLogger
from healagent.core.types import Action, FailureClass, Signature, TraceRecord


def _reward(success: int, cost: float, latency_ms: float, lam: float, mu: float) -> float:
    return success - lam * cost - mu * latency_ms


def test_dummy_tool_and_policy_write_one_trace_line(tmp_path: Path) -> None:
    logger = TraceLogger("smoke-run", trace_dir=tmp_path)
    tool = DummyTool()
    policy = DummyPolicy()

    signature = Signature(failure_class=FailureClass.TIMEOUT, tool=tool.name, attempt=1)
    mask = {Action.RETRY, Action.REPAIR}

    action = policy.select(signature, mask)
    assert action in mask

    result = tool.call({"x": 21})
    assert result.ok
    assert result.output == 42

    reward = _reward(1, cost=1.0, latency_ms=result.latency_ms, lam=0.05, mu=0.01)
    policy.update(signature, action, reward)

    logger.log(
        TraceRecord(
            run_id="smoke-run",
            task_id="task-0",
            method=policy.name,
            seed=0,
            episode=0,
            step=0,
            tool=tool.name,
            args={"x": 21},
            signal="timeout",
            failure_class=FailureClass.TIMEOUT.value,
            signature=signature,
            action=action,
            verifier_outcome="pass",
            budget_remaining={"attempts": 2.0, "cost": 24.0, "latency_ms": 3999.0},
            cost=1.0,
            latency_ms=result.latency_ms,
            final_status="success",
        )
    )

    lines = logger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    record = TraceRecord.model_validate_json(lines[0])
    assert record.run_id == "smoke-run"
    assert record.action is Action.RETRY
    assert record.tool == "dummy"

    reloaded = logger.read_all()
    assert len(reloaded) == 1
    assert reloaded[0] == record
