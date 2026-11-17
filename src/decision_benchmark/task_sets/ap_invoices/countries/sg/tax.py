"""Singapore GST treatment: can the buyer claim the GST as input tax? (step-11 plan §5.3)"""

from __future__ import annotations

import re

from ...codes import Code
from ...findings import TaxResult, UnsupportedCase, Unsettled, finding
from ...models import Catalog, Invoice, InvoiceLine, Supplier
from ...models.common import ZERO
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


def _value(line: InvoiceLine, name: str) -> bool | None:
    """The value of a recorded line fact; None when it isn't recorded or the documents don't show it."""
    from . import PACK

    fact = PACK.fact(line, name)
    return fact.value if fact is not None else None


def assess(inv: Invoice, supplier: Supplier, catalog: Catalog) -> TaxResult:
    e = inv.einvoice
    assert isinstance(e, PintSg)
    if not gst_charged(inv):
        return TaxResult(T.NO_GST)
    # 1. Supplier not registered, or the number printed doesn't match the record (CHANGELOG clarification).
    reg = supplier.registration("SG_GST", on=inv.issue_date)
    if reg is None:
        return TaxResult(T.GST_WRONGLY_CHARGED, [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="not_registered")])
    if e.supplier_gst_no and norm_gst_no(e.supplier_gst_no) != norm_gst_no(reg.number):
        return TaxResult(
            T.GST_WRONGLY_CHARGED,
            [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, reason="number_does_not_match_record")],
        )
    # 2. Overseas vendor under OVR charging a GST-registered buyer (every SG buyer is registered, plan Q5).
    if reg.type == "ovr":
        return TaxResult(T.GST_WRONGLY_CHARGED, [finding(Code.OVR_GST_CHARGED_TO_REGISTERED_BUYER)])
    # 3. Invalid tax invoice.
    invalid = validity.check(inv)
    if invalid:
        return TaxResult(T.NOT_CLAIMABLE_INVALID_INVOICE, invalid)
    # Standard rate only; other rates are outside the v0.9 rule sheet.
    for line in inv.lines:
        if line.tax_rate > ZERO and line.tax_rate != GST_RATE:
            raise UnsupportedCase(f"GST rate {line.tax_rate}% on line {line.line_no}")
    # 5. Regulations 26 and 27.
    ext = {x.line_no: x.tax_category for x in e.lines}
    disallowed: list[int] = []
    claimable: list[int] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        if not _line_charged(line, ext.get(line.line_no)):
            continue
        profile = catalog.get(line.category).tax.get("SG") or SgTaxProfile()
        assert isinstance(profile, SgTaxProfile)
        cls = profile.disallowed
        if cls == "motor_car":
            fact = _value(line, "vehicle_is_motor_car")
            if fact is None:
                unsettled.append(Unsettled("vehicle_regulation_25_1_unclear", tax_related=True))
            (disallowed if fact else claimable).append(line.line_no)
        elif cls == "staff_medical":
            fact = _value(line, "staff_medical_obligatory")
            if fact is None:
                unsettled.append(Unsettled("staff_medical_obligation_unclear", tax_related=True))
            (claimable if fact else disallowed).append(line.line_no)
        elif cls == "medical_accident_insurance":
            # Claimable when obligatory under the Work Injury Compensation Act or a collective agreement.
            fact = _value(line, "insurance_obligatory")
            if fact is None:
                unsettled.append(Unsettled("insurance_obligation_unclear", tax_related=True))
            (claimable if fact else disallowed).append(line.line_no)
        elif cls is not None:
            disallowed.append(line.line_no)
        else:
            claimable.append(line.line_no)
    if unsettled:
        return TaxResult(None, [], unsettled)
    if disallowed and claimable:
        raise UnsupportedCase("claimable and disallowed GST lines on one invoice (plan Q4)")
    if disallowed:
        return TaxResult(T.NOT_CLAIMABLE_DISALLOWED, extra_reasons=(Code.GST_NOT_CLAIMABLE_DISALLOWED,))
    return TaxResult(T.CLAIMABLE)
