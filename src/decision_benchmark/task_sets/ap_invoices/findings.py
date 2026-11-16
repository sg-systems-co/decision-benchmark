"""Findings, priority sorting and the two ways the engine declines to decide.

Shared by the rules engine and the country packs. The code list and the
priority table are in codes.py; nothing here names a country.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .codes import ORDER, Code
from .models import Finding

RANK = {code: i for i, (code, _, _) in enumerate(ORDER)}
TIER = {code: tier for code, tier, _ in ORDER}
DECISION = {code: decision for code, _, decision in ORDER}


class UnsupportedCase(Exception):
    """The case contains a situation the v0.9 rules don't cover. The generator must redraw it.

    The engine raises this instead of guessing.
    """


@dataclass(frozen=True)
class Unsettled:
    """The official rules don't settle the case from the facts available: HAND_OVER by construction."""

    reason: str
    tax_related: bool


@dataclass(frozen=True)
class TaxResult:
    """A country pack's tax assessment. treatment is None only when unsettled is not empty."""

    treatment: str | None
    findings: list[Finding] = field(default_factory=list)
    unsettled: list[Unsettled] = field(default_factory=list)
    extra_reasons: tuple[Code, ...] = ()
    """Reason codes added after the findings (e.g. a disallowed input-tax claim on an approved invoice)."""


def finding(code: Code, **evidence: Any) -> Finding:
    return Finding(code=code, tier=TIER[code], evidence=evidence)


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Stable sort by priority; one finding per code (the first one found)."""
    seen: set[str] = set()
    out = []
    for f in sorted(findings, key=lambda f: RANK[f.code]):
        if f.code not in seen:
            seen.add(f.code)
            out.append(f)
    return out
