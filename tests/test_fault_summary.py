from __future__ import annotations

from collections import Counter

from healagent.core.types import Action
from healagent.faults.injector import FaultInjector
from healagent.faults.profiles import default_profiles
from healagent.faults.types import FaultKind
from healagent.tasks.catalog import load_tasks

TRIAL_SEEDS = tuple(range(8))
INTENSITY = 0.5


def _fault_counts(seeds=TRIAL_SEEDS, intensity: float = INTENSITY) -> Counter:
    tasks = load_tasks()
    counts: Counter = Counter()
    for seed in seeds:
        injector = FaultInjector(seed, intensity)
        for task in tasks:
            steps = [{"tool": step.tool} for step in task.plan]
            for event in injector.plan(task.task_id, steps, task.eligible_faults):
                if event.fault is not None:
                    counts[event.fault.value] += 1
    return counts


def test_printed_fault_summary_covers_every_fault_kind(capsys) -> None:
    counts = _fault_counts()
    expected = {kind.value for kind in FaultKind}

    print("\nFault summary (intensity 0.5, seeds 0-7):")
    for kind in sorted(expected):
        print(f"  {kind:<18} {counts.get(kind, 0)}")
    print("Profile summary (tool / fault -> persistence, fixed_by):")
    for (tool, fault), profile in sorted(
        default_profiles().items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        fixed = ", ".join(sorted(action.value for action in profile.fixed_by))
        print(f"  {tool:<20} {fault.value:<18} {profile.persistence.value:<11} [{fixed}]")

    assert set(counts) == expected, f"missing fault kinds: {expected - set(counts)}"


def test_required_transient_and_persistent_behaviour() -> None:
    profiles = default_profiles()
    expected = {
        ("shipping_estimator", FaultKind.TIMEOUT): ("persistent", Action.SUBSTITUTE),
        ("customer_lookup", FaultKind.TIMEOUT): ("transient", Action.RETRY),
        ("order_lookup", FaultKind.RATE_LIMIT): ("transient", Action.RETRY),
        ("policy_lookup", FaultKind.PARTIAL_RESPONSE): ("persistent", Action.REFRESH),
        ("inventory_lookup", FaultKind.STALE_CONTEXT): ("persistent", Action.REFRESH),
        ("calculator", FaultKind.SEMANTIC_WRONG): ("persistent", Action.REPAIR),
    }
    for key, (persistence, fixing_action) in expected.items():
        profile = profiles[key]
        assert profile.persistence.value == persistence
        assert profile.is_fixed_by(fixing_action)
