"""E-invoices and SST invoice particulars: ME-1, ME-3, ME-4 (rule sheet v0.10 section 3). ME-2 (MyInvois
mandatory fields) is validity.py.

Sources: LHDN e-Invoice Guideline v4.6 (sections 1.5-1.6) and Specific Guideline v4.9 (section 8.3 self-billing,
section 16 interim relaxation); LHDN timeline; Service Tax Regulations 2018 reg 10(1) and 10(1A). The ME-1 dates are
in data/einvoice_timeline.yaml. Open questions here are not about the tax: they leave the line's treatment set and
make the case HAND_OVER (NotSettled with tax_related False).
"""

from __future__ import annotations

from decimal import Decimal

from ....codes import Code
from ....findings import LineResult, NotSettled, finding
from ....models import BuyerAction, Finding, Invoice, Supplier
from .. import einvoice_timeline as tl
from ..models import MyCompanyFacts, MyInvois, MySupplierFacts
from ..models import MyTaxTreatment as T
from .context import HOME, LineCtx

ISSUE_SELF_BILLED = "ISSUE_SELF_BILLED_EINVOICE"


def _validated(inv: Invoice) -> bool:
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    return bool(e.is_einvoice and e.uuid and e.validation_datetime)


def statutory_fees_only_from(inv: Invoice, supplier: Supplier, sf: MySupplierFacts):
    """A statutory body or local authority after its general exemption ended is exempt only for statutory payments,
    fees and charges (e-Invoice Guideline 1.6.1(c)(i)): True when each line must then be checked."""
    row = tl.exempt_person(sf.supplier_kind)
    return (supplier.country == HOME and row is not None and row.statutory_fees and row.to is not None
            and inv.issue_date > row.to and not _validated(inv))


def statutory_fee_line(ctx: LineCtx) -> bool:
    """The whole line is a statutory payment, fee or charge (the line fact MS-4 reads, with its ordinary value)."""
    fee = ctx.fact("statutory_fee_amount", Decimal(0), "ME-1")
    return fee >= ctx.net


def supplier_phase(inv: Invoice, supplier: Supplier, sf: MySupplierFacts,
                   statutory_lines: list[bool] | None = None) -> list[Finding]:
    """ME-1: a supplier in a mandatory phase on the invoice date and outside that phase's interim relaxation period
    issues a validated e-invoice. Inside the relaxation period it may issue a consolidated e-invoice instead, so an
    ordinary invoice raises no finding (Specific Guideline 16.2(a), (d)). statutory_lines: for a statutory body or
    local authority (statutory_fees_only_from), whether each line is a statutory fee."""
    if supplier.country != HOME:
        return []                       # an overseas supplier issues no MyInvois e-invoice (the buyer self-bills, ME-3)
    if _validated(inv):
        return []
    day = inv.issue_date
    if not sf.einvoice_phase_known:
        if day <= tl.earliest_relaxation_end():
            return []                   # no supplier is past its relaxation period yet: the phase doesn't decide
        raise NotSettled("ME-1", "supplier e-invoicing phase not shown", tax_related=False)
    person = tl.exempt_person(sf.supplier_kind)
    if person is not None and (person.to is None or day <= person.to):
        return []
    if person is not None and person.statutory_fees and statutory_lines and all(statutory_lines):
        return []
    status = sf.einvoice
    if status is None or tl.exempt_band(status.turnover_band):
        return []
    start = tl.implementation_date(status)
    if start is None or day < start:
        return []
    end = tl.relaxation_end(start, status.turnover_band)
    if end is None:
        raise NotSettled("ME-1", "no interim relaxation period is published for this implementation date",
                         tax_related=False)
    if day <= end:
        return []
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    missing = [name for name, present in (("validated_einvoice", e.is_einvoice), ("uuid", e.uuid),
                                          ("validation_datetime", e.validation_datetime)) if not present]
    return [finding(Code.MISSING_MANDATORY_FIELD, missing=missing, rule="ME-1")]


def buyer_in_phase(cf: MyCompanyFacts, day) -> bool:
    """ME-3: the buyer is in a mandatory e-invoicing phase on the day, by the ME-1 timeline applied to its own record:
    an exempt person (e-Invoice Guideline 1.6.1) or a turnover below RM3m never is; otherwise from its implementation
    date, relaxation period included (Specific Guideline 16.2(b): it may then issue a consolidated self-billed
    e-invoice, but it still issues one). A phase not shown decides only from the first implementation date."""
    if not cf.einvoice_phase_known:
        if day < tl.earliest_implementation_date():
            return False
        raise NotSettled("ME-3", "company e-invoicing phase not shown", tax_related=False)
    person = tl.exempt_person(cf.person_kind)
    if person is not None and (person.to is None or day <= person.to):
        return False
    status = cf.einvoice
    if status is None or tl.exempt_band(status.turnover_band):
        return False
    start = tl.implementation_date(status)
    return start is not None and day >= start


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
    if not buyer_in_phase(ctx.cf, ctx.day):
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
