"""Singapore GST treatment: can the buyer claim the GST as input tax? (step-11 plan §5.3)"""

from __future__ import annotations

import re
from decimal import Decimal

from ..models import Catalog, Finding, InvoiceSG, Supplier, TaxTreatment
from . import validity_sg
from .constants import SG_GST_RATE
from .findings import UnsupportedCase, Unsettled, finding

ZERO = Decimal("0")


def norm_gst_no(number: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", number).upper()


def gst_charged(inv: InvoiceSG) -> bool:
    return (
        (inv.totals.tax or ZERO) > ZERO
        or any(line.tax_amount > ZERO or line.tax_rate > ZERO for line in inv.lines)
        or inv.price_includes_gst_statement
    )


def _line_charged(line) -> bool:
    return line.tax_amount > ZERO or line.tax_rate > ZERO or line.tax_category == "SR"


def assess(
    inv: InvoiceSG, supplier: Supplier, catalog: Catalog
) -> tuple[TaxTreatment | None, list[Finding], list[Unsettled]]:
    if not gst_charged(inv):
        return TaxTreatment.NO_GST, [], []

    # 1. Supplier not registered, or the number printed doesn't match the record (CHANGELOG clarification).
    if not supplier.gst_registered_on(inv.issue_date) or not supplier.gst_reg_no:
        return TaxTreatment.GST_WRONGLY_CHARGED, [finding("SUPPLIER_NOT_TAX_REGISTERED", reason="not_registered")], []
    if inv.supplier_gst_no and norm_gst_no(inv.supplier_gst_no) != norm_gst_no(supplier.gst_reg_no):
        return (
            TaxTreatment.GST_WRONGLY_CHARGED,
            [finding("SUPPLIER_NOT_TAX_REGISTERED", reason="number_does_not_match_record")],
            [],
        )

    # 2. Overseas vendor under OVR charging a GST-registered buyer (every SG buyer is registered, plan Q5).
    if supplier.gst_regime == "ovr":
        return TaxTreatment.GST_WRONGLY_CHARGED, [finding("OVR_GST_CHARGED_TO_REGISTERED_BUYER")], []

    # 3. Invalid tax invoice.
    invalid = validity_sg.check(inv)
    if invalid:
        return TaxTreatment.NOT_CLAIMABLE_INVALID_INVOICE, invalid, []

    # Standard rate only; other rates are outside the v0.9 rule sheet.
    for line in inv.lines:
        if line.tax_rate > ZERO and line.tax_rate != SG_GST_RATE:
            raise UnsupportedCase(f"GST rate {line.tax_rate}% on line {line.line_no}")

    # 5. Regulations 26 and 27.
    disallowed, claimable, unsettled = [], [], []
    for line in inv.lines:
        if not _line_charged(line):
            continue
        cls = catalog.get(line.category).sg_disallowed
        if cls == "motor_car":
            fact = line.facts.vehicle_is_motor_car
            if fact is None:
                unsettled.append(Unsettled("vehicle_regulation_25_1_unclear", tax_related=True))
            (disallowed if fact else claimable).append(line.line_no)
        elif cls == "staff_medical":
            fact = line.facts.staff_medical_obligatory
            if fact is None:
                unsettled.append(Unsettled("staff_medical_obligation_unclear", tax_related=True))
            (claimable if fact else disallowed).append(line.line_no)
        elif cls is not None:
            disallowed.append(line.line_no)
        else:
            claimable.append(line.line_no)
    if unsettled:
        return None, [], unsettled
    if disallowed and claimable:
        raise UnsupportedCase("claimable and disallowed GST lines on one invoice (plan Q4)")
    if disallowed:
        return TaxTreatment.NOT_CLAIMABLE_DISALLOWED, [], []
    return TaxTreatment.CLAIMABLE, [], []
