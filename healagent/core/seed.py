"""Central, deterministic RNG management.

Every random draw in HealAgent must originate from a stream handed out by
:class:`SeedManager`. Calling :mod:`random` or :mod:`numpy.random` directly
elsewhere is forbidden so that a single master seed reproduces a run exactly.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

_SEP = "\x1f"


def _canonical(*parts: Any) -> str:
    return _SEP.join(str(p) for p in parts)


@dataclass
class SeedManager:
    """Hands out independent, named RNG streams derived from a master seed.

    A stream is identified by an ordered tuple of *parts* (e.g. ``("faults",
    task_id, step)``). The same parts always yield the same stream for a given
    master seed, and unrelated parts yield unrelated streams.
    """

    master_seed: int
    _cache: dict[str, np.random.Generator] = field(default_factory=dict, repr=False)

    def stream_seed(self, *parts: Any) -> int:
        """Return a deterministic 64-bit seed for the named stream."""
        digest = hashlib.blake2b(
            _canonical(self.master_seed, *parts).encode("utf-8"),
            digest_size=8,
        ).digest()
        return int.from_bytes(digest, "little", signed=False)

    def rng(self, *parts: Any) -> np.random.Generator:
        """Return the NumPy generator for the named stream (cached per instance)."""
        key = _canonical(*parts)
        gen = self._cache.get(key)
        if gen is None:
            gen = np.random.default_rng(self.stream_seed(*parts))
            self._cache[key] = gen
        return gen

    def python_rng(self, *parts: Any) -> random.Random:
        """Return a fresh :class:`random.Random` seeded for the named stream."""
        return random.Random(self.stream_seed(*parts))

    def child(self, *parts: Any) -> "SeedManager":
        """Derive a nested :class:`SeedManager` for a sub-scope."""
        return SeedManager(self.stream_seed(*parts))
