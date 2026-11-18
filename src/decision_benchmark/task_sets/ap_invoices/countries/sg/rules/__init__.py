"""Singapore GST rules, line by line (rule sheet v0.10 section 4; A12 plan §4.5).

Invoice-level first: a supplier not entitled to charge GST (SG-4) makes every line that carries GST wrongly
charged. Then each line: GST that shouldn't be there or at a rate the rules don't allow (SG-5, SG-6, SG-3);
an invalid tax invoice (SG-2) for every other line that carries GST; the claim rules (SG-10, SG-1). A line
without GST is right (SG-4, SG-5, SG-6) or undercharged (SG-12). A rule the documents don't settle raises
NotSettled: the line is null with that rule as basis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....codes import Code
from ....fact_reader import FactReader
from ....findings import LineResult, NotSettled, TaxResult, UnsupportedCase, Unsettled, finding, worst_line
from ....models import Catalog, Finding, Invoice, InvoiceLine
from ....models.common import ZERO
from ....models.evidence import LineFacts
from .. import validity
from ..models import PintSg, SgTaxProfile
from ..models import SgTaxTreatment as T
from . import claim, gst
from .context import LineCtx, Outcome

if TYPE_CHECKING:
    from ....rules.view import CaseView


def norm_gst_no(number: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", number).upper()


def gst_charged(inv: Invoice) -> bool:
    assert isinstance(inv.einvoice, PintSg)
    return ((inv.totals.tax or ZERO) > ZERO
            or any(line.tax_amount > ZERO or line.tax_rate > ZERO for line in inv.lines)
            or inv.einvoice.price_includes_gst_statement)


def _line_charged(line: InvoiceLine, tax_category: str | None) -> bool:
    return line.tax_amount > ZERO or line.tax_rate > ZERO or tax_category == "SR"


def _not_entitled(inv: Invoice, reg) -> list[Finding]:
    """SG-4: the supplier is not GST-registered, the number printed doesn't match the record (CHANGELOG
    clarification), or an OVR vendor charges a GST-registered buyer (every Singapore buyer is registered)."""
    e = inv.einvoice
    if reg is None:
        return [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="not_registered")]
    if e.supplier_gst_no and norm_gst_no(e.supplier_gst_no) != norm_gst_no(reg.number):
        return [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="number_does_not_match_record")]
    if reg.type == "ovr":
        return [finding(Code.OVR_GST_CHARGED_TO_REGISTERED_BUYER)]
    return []


def assess(view: CaseView, catalog: Catalog, facts: dict[int, LineFacts] | None = None) -> TaxResult:
    """facts: line facts to use instead of those recorded on the lines (check_rules)."""
    from .. import PACK

    inv = view.invoice
    e = inv.einvoice
    assert isinstance(e, PintSg)
    ext = {x.line_no: x for x in e.lines}
    charged = {line.line_no for line in inv.lines
               if _line_charged(line, ext[line.line_no].tax_category if line.line_no in ext else None)}
    if gst_charged(inv) and not charged:
        charged = {line.line_no for line in inv.lines}  # GST on the invoice, not split by line
    reg = view.supplier.registration("SG_GST", on=inv.issue_date)
    if charged:
        wrong = _not_entitled(inv, reg)
        if wrong:
            lines = [LineResult(line.line_no, T.GST_WRONGLY_CHARGED if line.line_no in charged else T.NO_GST, "SG-4")
                     for line in inv.lines]
            return TaxResult(worst_line(lines, PACK.severity_order), wrong, [], lines)
    invalid = validity.check(inv) if charged else []
    sf, cf = PACK.supplier_facts_of(view.supplier), PACK.company_facts_of(view.company)
    lines: list[LineResult] = []
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        reader = FactReader(PACK, line, (facts or {}).get(line.line_no))
        profile = catalog.get(line.category).tax.get("SG") or SgTaxProfile()
        assert isinstance(profile, SgTaxProfile)
        ctx = LineCtx(line=line, ext=ext.get(line.line_no), reader=reader, profile=profile, invoice=inv,
                      supplier=view.supplier, sf=sf, company=view.company, cf=cf, registration=reg,
                      charged=line.line_no in charged, day=inv.issue_date, processing_date=view.as_of_date,
                      catalog=catalog)
        try:
            out = assess_line(ctx, invalid)
        except NotSettled as ns:
            unsettled.append(Unsettled(ns.reason, tax_related=ns.tax_related))
            lines.append(LineResult(line.line_no, None, ns.basis, read=tuple(reader.recorded_reads()),
                                    missing=tuple(reader.missing())))
            continue
        findings += out.findings
        lines.append(LineResult(line.line_no, out.code, out.basis, out.actions, read=tuple(reader.recorded_reads()),
                                missing=tuple(reader.missing())))
    treatment = worst_line(lines, PACK.severity_order)
    if unsettled:
        return TaxResult(treatment, [], unsettled, lines)
    if any(r.treatment == T.NOT_CLAIMABLE_INVALID_INVOICE for r in lines):
        findings = invalid + findings
    codes = {r.treatment for r in lines}
    if T.NOT_CLAIMABLE_DISALLOWED in codes and T.CLAIMABLE in codes:
        raise UnsupportedCase("claimable and disallowed GST lines on one invoice (plan Q4)")
    extra = (Code.GST_NOT_CLAIMABLE_DISALLOWED,) if T.NOT_CLAIMABLE_DISALLOWED in codes else ()
    return TaxResult(treatment, findings, [], lines, extra_reasons=extra)


def assess_line(ctx: LineCtx, invalid: list[Finding]) -> Outcome:
    if not ctx.charged:
        return gst.uncharged_line(ctx)
    wrong = gst.charged_line(ctx)
    if wrong is not None:
        return wrong
    rate = gst.check_rate(ctx)
    if rate is not None and rate.code != T.CLAIMABLE:
        return rate
    if invalid:
        return Outcome(T.NOT_CLAIMABLE_INVALID_INVOICE, "SG-2")
    out = claim.assess(ctx)
    if rate is not None and out.code == T.CLAIMABLE:
        return Outcome(out.code, rate.basis)
    return out
