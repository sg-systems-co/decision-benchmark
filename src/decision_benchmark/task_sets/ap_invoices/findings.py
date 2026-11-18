"""Findings, priority sorting and the two ways the engine declines to decide.

Shared by the rules engine and the country packs. The code list and the
priority table are in codes.py; nothing here names a country.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .codes import ORDER, Code
from .models import BuyerAction, Finding

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


class NotSettled(Exception):
    """A rule the documents don't settle for one line: the line's treatment is null (HAND_OVER) with the rule
    as its basis. tax_related False: the open question is not the tax (e.g. a buyer action)."""

    def __init__(self, basis: str, reason: str, tax_related: bool = True) -> None:
        super().__init__(f"{basis}: {reason}")
        self.basis = basis
        self.reason = reason
        self.tax_related = tax_related


@dataclass(frozen=True)
class LineResult:
    """One invoice line's tax result (spec v0.10 tax_lines)."""

    line_no: int
    treatment: str | None
    """None: the documents don't settle the rule named by basis (HAND_OVER)."""
    basis: str
    """The rule ID that decides the line, or that the documents don't settle."""
    buyer_actions: tuple[BuyerAction, ...] = ()
    read: tuple[str, ...] = ()
    """The line facts the rules read that the line records (its gold facts), in reading order."""
    missing: tuple[str, ...] = ()
    """The line facts the rules read that were not recorded or supplied."""


@dataclass(frozen=True)
class TaxResult:
    """A country pack's tax assessment: one LineResult per invoice line. treatment is the worst line,
    None only when unsettled is not empty."""

    treatment: str | None
    findings: list[Finding] = field(default_factory=list)
    unsettled: list[Unsettled] = field(default_factory=list)
    lines: list[LineResult] = field(default_factory=list)
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


def worst_line(lines: Sequence[LineResult], order: Sequence[str]) -> str | None:
    """The worst treatment by order (worst first); None if any line is unsettled or there are no lines."""
    if not lines or any(line.treatment is None for line in lines):
        return None
    rank = {code: i for i, code in enumerate(order)}
    for line in lines:
        if line.treatment not in rank:
            raise ValueError(f"line {line.line_no}: {line.treatment} is not in the severity order")
    return min((line.treatment for line in lines), key=lambda code: rank[code])
