from __future__ import annotations

import numpy as np

from healagent.core.seed import SeedManager


def test_same_master_seed_gives_identical_draws() -> None:
    a = SeedManager(1234).rng("faults", "task-1", 1).random(10)
    b = SeedManager(1234).rng("faults", "task-1", 1).random(10)
    np.testing.assert_array_equal(a, b)


def test_same_named_stream_is_stable_across_instances() -> None:
    seed = SeedManager(42).stream_seed("schedule", "task-7", 3)
    assert seed == SeedManager(42).stream_seed("schedule", "task-7", 3)
    draws_a = SeedManager(42).rng("schedule", "task-7", 3).random(5)
    draws_b = SeedManager(42).rng("schedule", "task-7", 3).random(5)
    np.testing.assert_array_equal(draws_a, draws_b)


def test_different_stream_names_give_different_draws() -> None:
    a = SeedManager(7).rng("faults").random(20)
    b = SeedManager(7).rng("schedule").random(20)
    assert not np.array_equal(a, b)


def test_different_parts_give_different_seeds() -> None:
    seed = SeedManager(7)
    assert seed.stream_seed("faults", "t1", 1) != seed.stream_seed("faults", "t1", 2)
    assert seed.stream_seed("faults", "t1") != seed.stream_seed("faults", "t2")


def test_different_master_seeds_give_different_draws() -> None:
    a = SeedManager(1).rng("faults").random(20)
    b = SeedManager(2).rng("faults").random(20)
    assert not np.array_equal(a, b)


def test_seed_is_within_uint64_range() -> None:
    seed = SeedManager(0).stream_seed("any")
    assert 0 <= seed < 2**64


def test_python_rng_is_deterministic() -> None:
    a = [SeedManager(99).python_rng("detector").random() for _ in range(3)]
    b = [SeedManager(99).python_rng("detector").random() for _ in range(3)]
    assert a == b


def test_child_manager_is_deterministic_and_scoped() -> None:
    a = SeedManager(5).child("task-1").rng("faults").random(5)
    b = SeedManager(5).child("task-1").rng("faults").random(5)
    c = SeedManager(5).child("task-2").rng("faults").random(5)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)
