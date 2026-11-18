"""Rule registry (A12 plan §3, §9): every rule a country pack applies, with its validity dates.

A pack lists one RuleSpec per rule ID of its schema part. Rule IDs are opaque strings here; only
the packs know them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    valid_from: date | None = None
    """First day the rule applies; None: no start date in the rule sheet."""
    valid_to: date | None = None
    """Last day the rule applies; None: open-ended."""

    def __post_init__(self) -> None:
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError(f"{self.rule_id}: valid_to is before valid_from")

    def applies_on(self, day: date) -> bool:
        return (self.valid_from is None or self.valid_from <= day) and (self.valid_to is None or day <= self.valid_to)


def registry(*specs: RuleSpec) -> dict[str, RuleSpec]:
    out: dict[str, RuleSpec] = {}
    for spec in specs:
        if spec.rule_id in out:
            raise ValueError(f"rule {spec.rule_id} registered twice")
        out[spec.rule_id] = spec
    return out
