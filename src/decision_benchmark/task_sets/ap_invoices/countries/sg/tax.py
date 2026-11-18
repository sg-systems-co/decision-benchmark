"""Singapore GST treatment: can the buyer claim the GST as input tax? (step-11 plan §5.3, A12 plan §4)

Each line is assessed on its own into a LineResult with the rule ID that decides it; the case-level
code is the worst line (spec v0.10). Invoice-level findings (supplier not entitled to charge,
invalid tax invoice) apply to every line that carries GST. Until the v0.10 Singapore rules land
(A12 build PR 3) the v0.9 logic below names its closest v0.10 rule; a line without GST is NO_GST
under SG-12 (or SG-4 when the supplier is not registered).
"""

from __future__ import annotations

import re

from ...codes import Code
from ...fact_reader import FactReader
from ...findings import LineResult, TaxResult, UnsupportedCase, Unsettled, finding, worst_line
from ...models import Catalog, Invoice, InvoiceLine, Supplier
from ...models.common import ZERO
from ...models.evidence import LineFacts
from . import validity
from .constants import GST_RATE
from .models import PintSg, SgTaxProfile
from .models import SgTaxTreatment as T


def norm_gst_no(number: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", number).upper()


def gst_charged(inv: Invoice) -> bool:
    assert isinstance(inv.einvoice, PintSg)
    return (
        (inv.totals.tax or ZERO) > ZERO
        or any(line.tax_amount > ZERO or line.tax_rate > ZERO for line in inv.lines)
        or inv.einvoice.price_includes_gst_statement
    )


def _line_charged(line: InvoiceLine, tax_category: str | None) -> bool:
    return line.tax_amount > ZERO or line.tax_rate > ZERO or tax_category == "SR"


def assess(inv: Invoice, supplier: Supplier, catalog: Catalog, facts: dict[int, LineFacts] | None = None) -> TaxResult:
    """facts: line facts to use instead of those recorded on the lines (check_rules)."""
    from . import PACK

    e = inv.einvoice
    assert isinstance(e, PintSg)
    ext = {x.line_no: x.tax_category for x in e.lines}
    charged = {line.line_no for line in inv.lines if _line_charged(line, ext.get(line.line_no))}
    if gst_charged(inv) and not charged:
        charged = {line.line_no for line in inv.lines}  # GST on the invoice, not split by line
    reg = supplier.registration("SG_GST", on=inv.issue_date)

    def whole_invoice(code: str, basis: str, findings: list, other_basis: str) -> TaxResult:
        lines = [LineResult(line.line_no, code if line.line_no in charged else T.NO_GST,
                            basis if line.line_no in charged else other_basis) for line in inv.lines]
        return TaxResult(worst_line(lines, PACK.severity_order), findings, [], lines)

    if not gst_charged(inv):
        basis = "SG-4" if reg is None else "SG-12"
        return whole_invoice(T.NO_GST, basis, [], basis)
    # Supplier not registered, or the number printed doesn't match the record (SG-4; CHANGELOG clarification).
    if reg is None:
        return whole_invoice(T.GST_WRONGLY_CHARGED, "SG-4",
                             [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="not_registered")], "SG-4")
    if e.supplier_gst_no and norm_gst_no(e.supplier_gst_no) != norm_gst_no(reg.number):
        return whole_invoice(T.GST_WRONGLY_CHARGED, "SG-4",
                             [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="number_does_not_match_record")], "SG-4")
    # Overseas vendor under OVR charging a GST-registered buyer (SG-4; every SG buyer is registered, plan Q5).
    if reg.type == "ovr":
        return whole_invoice(T.GST_WRONGLY_CHARGED, "SG-4", [finding(Code.OVR_GST_CHARGED_TO_REGISTERED_BUYER)], "SG-4")
    # Invalid tax invoice (SG-2): every line that carries GST.
    invalid = validity.check(inv)
    if invalid:
        return whole_invoice(T.NOT_CLAIMABLE_INVALID_INVOICE, "SG-2", invalid, "SG-12")
    # Standard rate only; other rates are outside the v0.9 rule sheet.
    for line in inv.lines:
        if line.tax_rate > ZERO and line.tax_rate != GST_RATE:
            raise UnsupportedCase(f"GST rate {line.tax_rate}% on line {line.line_no}")
    # Regulations 26 and 27 (SG-10), else claimable (SG-1).
    lines: list[LineResult] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        if line.line_no not in charged:
            lines.append(LineResult(line.line_no, T.NO_GST, "SG-12"))
            continue
        reader = FactReader(PACK, line, (facts or {}).get(line.line_no))
        code, basis, why = _claim(line, reader, catalog)
        if why:
            unsettled.append(Unsettled(why, tax_related=True))
        lines.append(LineResult(line.line_no, code, basis, read=tuple(reader.recorded_reads()),
                                missing=tuple(reader.missing())))
    if unsettled:
        return TaxResult(None, [], unsettled, lines)
    codes = {line.treatment for line in lines}
    if T.NOT_CLAIMABLE_DISALLOWED in codes and T.CLAIMABLE in codes:
        raise UnsupportedCase("claimable and disallowed GST lines on one invoice (plan Q4)")
    extra = (Code.GST_NOT_CLAIMABLE_DISALLOWED,) if T.NOT_CLAIMABLE_DISALLOWED in codes else ()
    return TaxResult(worst_line(lines, PACK.severity_order), [], [], lines, extra_reasons=extra)


def _claim(line: InvoiceLine, reader: FactReader, catalog: Catalog) -> tuple[str | None, str, str | None]:
    """(code, basis, unsettled reason) for one line that carries GST."""
    profile = catalog.get(line.category).tax.get("SG") or SgTaxProfile()
    assert isinstance(profile, SgTaxProfile)
    cls = profile.disallowed
    if cls == "motor_car":
        fact = reader.value("vehicle_is_motor_car")
        if fact is None:
            return None, "SG-10", "vehicle_regulation_25_1_unclear"
        return (T.NOT_CLAIMABLE_DISALLOWED if fact else T.CLAIMABLE), "SG-10", None
    if cls == "staff_medical":
        fact = reader.value("staff_medical_obligatory")
        if fact is None:
            return None, "SG-10", "staff_medical_obligation_unclear"
        return (T.CLAIMABLE if fact else T.NOT_CLAIMABLE_DISALLOWED), "SG-10", None
    if cls == "medical_accident_insurance":
        # Claimable when obligatory under the Work Injury Compensation Act or a collective agreement.
        fact = reader.value("insurance_obligatory")
        if fact is None:
            return None, "SG-10", "insurance_obligation_unclear"
        return (T.CLAIMABLE if fact else T.NOT_CLAIMABLE_DISALLOWED), "SG-10", None
    if cls is not None:
        return T.NOT_CLAIMABLE_DISALLOWED, "SG-10", None
    return T.CLAIMABLE, "SG-1", None
