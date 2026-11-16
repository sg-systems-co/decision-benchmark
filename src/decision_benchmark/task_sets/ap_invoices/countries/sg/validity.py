"""IRAS tax-invoice checks (rule sheet rows 2 and 3). Run only when GST is charged (see tax.py)."""

from __future__ import annotations

from decimal import Decimal

from ...codes import Code
from ...findings import finding
from ...models import Finding, Invoice
from .constants import FULL_TAX_INVOICE_THRESHOLD
from .models import PintSg


def gross_sgd(inv: Invoice) -> Decimal | None:
    assert isinstance(inv.einvoice, PintSg)
    if inv.currency == "SGD":
        return inv.totals.gross
    return inv.einvoice.gross_sgd


def check(inv: Invoice) -> list[Finding]:
    """Findings for an invoice on which GST is charged. Credit notes are not checked in v0.9."""
    e = inv.einvoice
    assert isinstance(e, PintSg)
    if inv.doc_type != "invoice":
        return []
    out: list[Finding] = []
    if inv.currency != "SGD" and (e.gross_sgd is None or e.tax_total_sgd is None):
        out.append(finding(Code.FOREIGN_CURRENCY_NO_SGD_AMOUNTS, currency=inv.currency))
    missing = []
    if not inv.supplier_block.name:
        missing.append("supplier_name")
    if not inv.supplier_block.address:
        missing.append("supplier_address")
    if not e.supplier_gst_no:
        missing.append("supplier_gst_no")
    amount = gross_sgd(inv)
    if amount is not None:
        if amount > FULL_TAX_INVOICE_THRESHOLD:
            if not e.document_title or "tax invoice" not in e.document_title.lower():
                missing.append("tax_invoice_wording")
            if not inv.buyer_block.name:
                missing.append("customer_name")
            if inv.totals.tax is None:
                missing.append("gst_amount")
        elif inv.totals.tax is None and not e.price_includes_gst_statement:
            missing.append("gst_amount_or_price_includes_gst_statement")
    if missing:
        out.append(finding(Code.INVALID_TAX_INVOICE, missing=missing))
    return out
