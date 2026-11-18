"""E-invoices and SST invoice particulars: ME-1, ME-3, ME-4 (rule sheet v0.10 section 3). ME-2 (MyInvois
mandatory fields) is validity.py.

Sources: LHDN e-Invoice Guideline and Specific Guideline v4.9 (section 8.3 self-billing); LHDN timeline;
Service Tax Regulations 2018 reg 10(1) and 10(1A). Open questions here are not about the tax: they leave the
line's treatment set and make the case HAND_OVER (NotSettled with tax_related False).
"""

from __future__ import annotations

from ....codes import Code
from ....findings import LineResult, NotSettled, finding
from ....models import BuyerAction, Finding, Invoice, Supplier
from ..models import MyCompanyFacts, MyInvois, MySupplierFacts
from ..models import MyTaxTreatment as T
from .context import HOME, LineCtx

ISSUE_SELF_BILLED = "ISSUE_SELF_BILLED_EINVOICE"


def supplier_phase(inv: Invoice, supplier: Supplier, sf: MySupplierFacts) -> list[Finding]:
    """ME-1: a supplier in a mandatory phase on the invoice date issues a validated e-invoice."""
    if supplier.country != HOME:
        return []                       # an overseas supplier issues no MyInvois e-invoice (the buyer self-bills, ME-3)
    if not sf.einvoice_phase_known:
        raise NotSettled("ME-1", "supplier e-invoicing phase not shown", tax_related=False)
    start = sf.einvoice_phase_start
    if start is None or inv.issue_date < start:
        return []
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    missing = [name for name, present in (("validated_einvoice", e.is_einvoice), ("uuid", e.uuid),
                                          ("validation_datetime", e.validation_datetime)) if not present]
    return [finding(Code.MISSING_MANDATORY_FIELD, missing=missing, rule="ME-1")] if missing else []


def self_billing(ctx: LineCtx) -> tuple[BuyerAction, ...]:
    """ME-3: the buyer issues the e-invoice itself for a section 8.3 transaction type, when it is in a mandatory
    phase on the transaction date. Interest (item (g)) under one of its exceptions: the supplier issues it."""
    kind = ctx.fact("self_billing_type", "foreign_supplier" if ctx.foreign_supplier else "none", "ME-3")
    if kind == "none":
        return ()
    if kind == "interest_payment":
        try:
            exception = ctx.need("interest_exception", "ME-3")
        except NotSettled as ns:
            raise NotSettled("ME-3", ns.reason, tax_related=False) from None
        if exception != "none":
            return ()
    cf: MyCompanyFacts = ctx.cf
    if not cf.einvoice_phase_known:
        raise NotSettled("ME-3", "company e-invoicing phase not shown", tax_related=False)
    start = cf.einvoice_phase_start
    if start is None or ctx.day < start:
        return ()
    return (BuyerAction(action=ISSUE_SELF_BILLED),)


def particulars(inv: Invoice, supplier: Supplier, lines: list[LineResult]) -> list[Finding]:
    """ME-4: what an SST invoice must show (reg 10(1)), and for a buyer exempt under the B2B order (reg 10(1A))."""
    if supplier.country != HOME:
        return []
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    missing: list[str] = []
    registered = supplier.registration("MY_SST", on=inv.issue_date) is not None
    if registered and any(line.tax_amount > 0 for line in inv.lines):
        # Reg 10(1) binds a registered person; tax charged by an unregistered supplier is MS-1 / MG-1.
        if not inv.supplier_block.name:
            missing.append("supplier_name")
        if not inv.supplier_block.address:
            missing.append("supplier_address")
        if not e.supplier_sst_no:
            missing.append("supplier_sst_no")
        missing += [f"line{x.line_no}.description" for x in inv.lines if not x.description]
        if inv.currency != "MYR" and inv.exchange_rate is None:
            missing.append("ringgit_amounts")
    b2b = [r.line_no for r in lines if r.basis == "MS-5" and r.treatment == T.NO_SST]
    if b2b:
        if not inv.buyer_block.name:
            missing.append("buyer_name")
        if not inv.buyer_block.address:
            missing.append("buyer_address")
        if not e.buyer_sst_no:
            missing.append("buyer_sst_no")
        ext = {x.line_no: x for x in e.lines}
        missing += [f"line{n}.tax_exemption_reason" for n in b2b if not (ext.get(n) and ext[n].tax_exemption_reason)]
    return [finding(Code.MISSING_MANDATORY_FIELD, missing=missing, rule="ME-4")] if missing else []
