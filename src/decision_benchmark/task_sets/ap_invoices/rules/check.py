"""check_rules (A12 plan §8; spec v0.10, agent variant (b)): the engine's per-line tax results for facts a caller
supplies, by the same code path as the answer keys.

The caller supplies the spec's facts.lines (evidence optional). Party facts come from the records, as for any case.
Only the supplied line facts count: nothing recorded on the invoice is read. A fact the rules read and the caller did
not supply takes the ordinary value (or the category's, from the catalog), exactly as for a line that doesn't record
it; it is listed in ``missing``. A rule the supplied facts don't settle gives a null treatment with that rule as basis.
It returns per-line results only, never the decision, the GL account or the other checks.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..envelope import ApCaseEnvelope
from ..models import BuyerAction, Catalog, CompanyRecords, Model
from ..models.evidence import EVIDENCE_OPTIONAL, LineFacts
from ..versions import ENGINE_VERSION, RULES_VERSION
from .view import build_case_view


class LineCheck(Model):
    line_no: int
    treatment: str | None
    basis: str
    buyer_actions: list[BuyerAction] = []
    missing: list[str] = []
    """Facts the rules read that the caller did not supply."""


class CheckRulesResult(Model):
    engine_version: str = Field(default_factory=lambda: ENGINE_VERSION)
    rules_version: str = Field(default_factory=lambda: RULES_VERSION)
    lines: list[LineCheck]


def parse_lines(pack, invoice_line_nos: set[int], lines: list[dict[str, Any]]) -> dict[int, LineFacts]:
    """The supplied facts.lines, validated with the country pack's line-facts model (evidence optional)."""
    out: dict[int, LineFacts] = {}
    for entry in lines:
        data = dict(entry)
        line_no = data.pop("line_no", None)
        if line_no not in invoice_line_nos:
            raise ValueError(f"facts for line {line_no!r}, which is not on the invoice")
        if line_no in out:
            raise ValueError(f"facts for line {line_no} given twice")
        out[line_no] = pack.line_facts_model.model_validate(data, context={EVIDENCE_OPTIONAL: True})
    return out


def check_rules(records: CompanyRecords, case: ApCaseEnvelope, lines: list[dict[str, Any]], catalog: Catalog) -> CheckRulesResult:
    view = build_case_view(records, case)
    pack = view.pack
    facts = parse_lines(pack, {x.line_no for x in view.invoice.lines}, lines)
    result = pack.assess_tax(view, catalog, facts)
    return CheckRulesResult(lines=[
        LineCheck(line_no=r.line_no, treatment=r.treatment, basis=r.basis, buyer_actions=list(r.buyer_actions),
                  missing=list(r.missing))
        for r in result.lines])
