"""Exact counts from shares (step 11 plan §5.1): largest remainder, ties to the earlier key."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from math import floor


class InfeasibleDemand(ValueError):
    """A quota or demand that can't be met exactly. The build stops: nothing is placed approximately."""


def as_fraction(value) -> Fraction:
    """A share or count as an exact fraction: ints, Decimals, "2/3" or "12.5" strings."""
    return Fraction(str(value)) if not isinstance(value, Fraction) else value


def apportion(total: int, weights: Mapping[str, object]) -> dict[str, int]:
    """Split ``total`` over the keys in proportion to their weights, exactly (largest remainder; a tie goes to the
    key listed first). The counts sum to ``total``."""
    if total < 0:
        raise InfeasibleDemand(f"negative total {total}")
    w = {k: as_fraction(v) for k, v in weights.items()}
    whole = sum(w.values(), Fraction(0))
    if total == 0:
        return {k: 0 for k in w}
    if whole <= 0:
        raise InfeasibleDemand(f"no weight to apportion {total} over")
    exact = {k: total * v / whole for k, v in w.items()}
    counts = {k: floor(x) for k, x in exact.items()}
    left = total - sum(counts.values())
    order = sorted(w, key=lambda k: (-(exact[k] - counts[k]), list(w).index(k)))
    for k in order[:left]:
        counts[k] += 1
    return counts


def share_of(total: int, percent) -> int:
    """``percent`` of ``total``, which must come out whole: the plan's quotas are exact, never rounded."""
    exact = total * as_fraction(percent) / 100
    if exact.denominator != 1:
        raise InfeasibleDemand(f"{percent}% of {total} is {exact}, not a whole number of cases")
    return int(exact)


def halves(counts: Mapping[str, int], keys: Sequence[str]) -> dict[str, dict[str, int]]:
    """Split each count evenly over ``keys``. An odd remainder goes to the key with the fewest so far (the earlier key
    on a tie), so the totals per key stay as even as possible."""
    running = {k: 0 for k in keys}
    out: dict[str, dict[str, int]] = {}
    for name, n in counts.items():
        base, extra = divmod(n, len(keys))
        part = {k: base for k in keys}
        for k in sorted(keys, key=lambda k: (running[k], list(keys).index(k)))[:extra]:
            part[k] += 1
        for k in keys:
            running[k] += part[k]
        out[name] = part
    return out
