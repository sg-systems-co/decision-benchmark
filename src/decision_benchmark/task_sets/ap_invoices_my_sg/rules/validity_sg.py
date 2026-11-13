"""IRAS tax-invoice checks (tax-rule sheet, "Valid tax invoice")."""

from __future__ import annotations

from decimal import Decimal

from ..models import Finding, InvoiceSG
from .constants import SG_FULL_TAX_INVOICE_THRESHOLD
from .findings import finding


def gross_sgd(inv: InvoiceSG) -> Decimal | None:
    if inv.currency == "SGD":
        return inv.totals.gross
    return inv.gross_sgd


def check(inv: InvoiceSG) -> list[Finding]:
    """Findings for an invoice on which GST is charged. Credit notes are not checked in v0.9."""
    if inv.doc_type != "invoice":
        return []
    out: list[Finding] = []
    if inv.currency != "SGD" and (inv.gross_sgd is None or inv.tax_total_sgd is None):
        out.append(finding("FOREIGN_CURRENCY_NO_SGD_AMOUNTS", currency=inv.currency))
    missing = []
    if not inv.supplier_block.name:
        missing.append("supplier_name")
    if not inv.supplier_block.address:
        missing.append("supplier_address")
    if not inv.supplier_gst_no:
        missing.append("supplier_gst_no")
    amount = gross_sgd(inv)
    if amount is not None:
        if amount > SG_FULL_TAX_INVOICE_THRESHOLD:
            if not inv.document_title or "tax invoice" not in inv.document_title.lower():
                missing.append("tax_invoice_wording")
            if not inv.buyer_block.name:
                missing.append("customer_name")
            if inv.totals.tax is None:
                missing.append("gst_amount")
        elif inv.totals.tax is None and not inv.price_includes_gst_statement:
            missing.append("gst_amount_or_price_includes_gst_statement")
    if missing:
        out.append(finding("INVALID_TAX_INVOICE", missing=missing))
    return out
