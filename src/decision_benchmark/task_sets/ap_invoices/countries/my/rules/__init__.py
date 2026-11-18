"""Malaysian SST rules, line by line (rule sheet v0.10 sections 1-3; A12 plan §4.1-4.4).

``assess`` builds one LineCtx per invoice line, runs the line's rules and returns one LineResult per
line with the rule ID that decides it. A rule the documents don't settle raises NotSettled: the line's
treatment is then null with that rule as basis, and the case is HAND_OVER. The case-level code is the
worst line by the pack's severity order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....fact_reader import FactReader
from ....findings import LineResult, NotSettled, TaxResult, Unsettled, worst_line
from ....models import Catalog, Finding
from ....models.evidence import LineFacts
from ..models import MyInvois, MyTaxProfile
from . import einvoice, imported, sales_tax, service_tax, withholding
from .context import LineCtx, Outcome

if TYPE_CHECKING:
    from ....rules.view import CaseView


def assess(view: CaseView, catalog: Catalog, facts: dict[int, LineFacts] | None = None) -> TaxResult:
    """facts: line facts to use instead of those recorded on the lines (check_rules)."""
    from .. import PACK

    inv = view.invoice
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    ext = {x.line_no: x for x in e.lines}
    sf, cf = PACK.supplier_facts_of(view.supplier), PACK.company_facts_of(view.company)
    lines: list[LineResult] = []
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        reader = FactReader(PACK, line, (facts or {}).get(line.line_no))
        profile = catalog.get(line.category).tax["MY"]
        assert isinstance(profile, MyTaxProfile)
        ctx = LineCtx(line=line, ext=ext.get(line.line_no), reader=reader, profile=profile, supplier=view.supplier,
                      sf=sf, company=view.company, cf=cf, day=inv.issue_date, processing_date=view.as_of_date,
                      catalog=catalog, contracts=view.contracts, invoice=inv,
                      residence_certificates=view.residence_certificates)
        try:
            out = assess_line(ctx)
        except NotSettled as ns:
            unsettled.append(Unsettled(ns.reason, tax_related=ns.tax_related))
            lines.append(LineResult(line.line_no, None, ns.basis, read=tuple(reader.recorded_reads()),
                                    missing=tuple(reader.missing())))
            continue
        actions = out.actions
        for rule in (einvoice.self_billing, withholding.actions):
            try:
                actions += rule(ctx)
            except NotSettled as ns:
                unsettled.append(Unsettled(ns.reason, tax_related=ns.tax_related))
        findings += out.findings
        lines.append(LineResult(line.line_no, out.code, out.basis, actions, read=tuple(reader.recorded_reads()),
                                missing=tuple(reader.missing())))
    try:
        findings += einvoice.supplier_phase(inv, view.supplier, sf)
    except NotSettled as ns:
        unsettled.append(Unsettled(ns.reason, tax_related=ns.tax_related))
    findings += einvoice.particulars(inv, view.supplier, lines)
    treatment = worst_line(lines, PACK.severity_order)
    if unsettled:
        return TaxResult(treatment, [], unsettled, lines)
    return TaxResult(treatment, findings, [], lines)


def assess_line(ctx: LineCtx) -> Outcome:
    if ctx.is_goods:
        return sales_tax.assess(ctx)
    if ctx.foreign_supplier:
        return imported.assess(ctx)
    return service_tax.assess(ctx)
