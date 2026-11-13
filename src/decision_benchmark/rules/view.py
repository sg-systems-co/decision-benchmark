"""The one case view (step-11 plan §2, §4.11).

``build_case_view`` decides what a case "knows". The rules engine, the
decision-track export and the agent environment all start from it, so both
tracks share one answer key. The view holds exactly the parts the decision track
is given: the invoice, the matching purchase order(s) and their receipts, the
supplier record as of the case date, the supplier's last 10 history items, the
case's own email threads and the policy pack.
"""

from __future__ import annotations

from datetime import date

from ..models import (
    Case,
    Company,
    CompanyRecords,
    Email,
    GoodsReceipt,
    Invoice,
    LedgerInvoice,
    Model,
    PolicyPack,
    PurchaseOrder,
    Supplier,
)
from .findings import UnsupportedCase

HISTORY_SIZE = 10


class CaseView(Model):
    case_id: str
    country: str
    as_of_date: date
    company: Company
    supplier: Supplier
    invoice: Invoice
    purchase_orders: list[PurchaseOrder]
    """The PO the invoice references, or else the supplier's open POs whose lines cover the invoice's categories."""
    goods_receipts: list[GoodsReceipt]
    history: list[LedgerInvoice]
    """The supplier's last 10 ledger items on or before as_of_date, newest first."""
    emails: list[Email]
    """The case's own threads, oldest first."""

    @property
    def policy(self) -> PolicyPack:
        return self.company.policy_pack


def supplier_as_of(supplier: Supplier, day: date) -> Supplier:
    """The supplier record as it stood on ``day``: later bank changes are rolled back and hidden."""
    if any(not change.verified for change in supplier.bank_change_log):
        # Only verified changes may reach the supplier master in v0.9 (policy pack bank_change_rule).
        raise UnsupportedCase("unverified change in the supplier bank log")
    changes = sorted(supplier.bank_change_log, key=lambda c: c.changed_on)
    account_no = supplier.bank_account.account_no
    for change in reversed(changes):
        if change.changed_on > day:
            if change.new_account_no != account_no:
                raise UnsupportedCase("bank change log does not chain")
            account_no = change.old_account_no
    kept = [c for c in changes if c.changed_on <= day]
    bank = supplier.bank_account.model_copy(update={"account_no": account_no})
    return supplier.model_copy(update={"bank_account": bank, "bank_change_log": kept})


def _candidate_pos(records: CompanyRecords, case: Case, visible: list[PurchaseOrder]) -> list[PurchaseOrder]:
    inv = case.invoice
    if inv.po_reference:
        ref = [p for p in visible if p.po_number == inv.po_reference and p.supplier_id == case.supplier_id]
        if ref:
            return ref
    wanted = {line.category for line in inv.lines}
    return [
        p
        for p in visible
        if p.supplier_id == case.supplier_id
        and p.status != "closed"
        and wanted <= {line.category for line in p.lines}
    ]


def build_case_view(records: CompanyRecords, case: Case) -> CaseView:
    if records.company.company_id != case.company_id:
        raise ValueError("case belongs to another company")
    supplier = records.supplier(case.supplier_id)
    if supplier is None:
        raise ValueError(f"unknown supplier {case.supplier_id}")
    day = case.as_of_date
    visible_pos = [p for p in records.purchase_orders if p.po_date <= day]
    pos = _candidate_pos(records, case, visible_pos)
    po_numbers = {p.po_number for p in pos}
    grs = sorted(
        (g for g in records.goods_receipts if g.po_number in po_numbers and g.gr_date <= day),
        key=lambda g: (g.gr_date, g.gr_number),
    )
    history = sorted(
        (
            entry
            for entry in records.ledger
            if entry.supplier_id == case.supplier_id
            and entry.invoice.issue_date <= day
            and entry.invoice.invoice_id != case.invoice.invoice_id
        ),
        key=lambda entry: (entry.invoice.issue_date, entry.ledger_id),
        reverse=True,
    )[:HISTORY_SIZE]
    emails = sorted(
        (e for e in records.emails if e.case_id == case.case_id and e.sent_at.date() <= day),
        key=lambda e: (e.sent_at, e.message_id),
    )
    return CaseView(
        case_id=case.case_id,
        country=case.country.value,
        as_of_date=day,
        company=records.company,
        supplier=supplier_as_of(supplier, day),
        invoice=case.invoice,
        purchase_orders=pos,
        goods_receipts=grs,
        history=history,
        emails=emails,
    )
