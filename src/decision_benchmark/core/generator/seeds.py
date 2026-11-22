"""Derived seeds (step 11 plan §8.1).

Every random draw uses ``random.Random(derive(split_seed, *parts))``. ``derive`` is the first 8 bytes of sha256
over the joined parts, so adding a new purpose never shifts the draws of another. Never used: ``hash()``, set
iteration order, wall-clock time, ``os.urandom``.
"""

from __future__ import annotations

import hashlib
import random

SEPARATOR = "\x1f"
"""Joins the parts before hashing (a byte that never appears in a purpose name)."""


def derive(seed: int | str, *parts: int | str) -> int:
    """A 64-bit seed for one purpose: the first 8 bytes of sha256 over the seed and the parts."""
    text = SEPARATOR.join(str(p) for p in (seed, *parts))
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def rng(seed: int | str, *parts: int | str) -> random.Random:
    """A generator for one purpose, seeded by ``derive``."""
    return random.Random(derive(seed, *parts))
