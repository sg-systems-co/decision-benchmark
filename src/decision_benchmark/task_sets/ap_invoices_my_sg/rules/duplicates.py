"""Exact and near duplicates against the supplier's history (step-11 plan §5.3)."""

from __future__ import annotations

import re

from ..models import Finding, LedgerInvoice
from .findings import finding
from .view import CaseView


def norm_number(number: str) -> str:
    """Upper case, separators dropped, leading zeros of each digit run dropped: "inv-0042" == "INV42"."""
    parts = re.findall(r"[A-Za-z]+|\d+", number)
    return "".join(str(int(p)) if p.isdigit() else p.upper() for p in parts)


def _credited_in_full(history: list[LedgerInvoice]) -> set[str]:
    """Ledger ids of invoices that a credit note in the history cancels in full."""
    out = set()
    credits = [h.invoice for h in history if h.invoice.doc_type == "credit_note" and h.invoice.original_invoice_ref]
    for h in history:
        inv = h.invoice
        if inv.doc_type != "invoice":
            continue
        for cn in credits:
            assert cn.original_invoice_ref is not None
            if norm_number(cn.original_invoice_ref) == norm_number(inv.invoice_number) and (
                cn.totals.gross == inv.totals.gross
            ):
                out.add(h.ledger_id)
    return out


def _lines_key(inv) -> list[tuple]:
    return sorted((line.description or "", str(line.qty), str(line.unit_price)) for line in inv.lines)


def check(view: CaseView) -> list[Finding]:
    inv = view.invoice
    window = view.policy.tolerance_policy.duplicate_window_days
    cancelled = _credited_in_full(view.history)
    out: list[Finding] = []
    for h in view.history:
        old = h.invoice
        if old.doc_type != inv.doc_type or h.ledger_id in cancelled:
            continue
        if norm_number(old.invoice_number) == norm_number(inv.invoice_number):
            out.append(finding("DUPLICATE_INVOICE", ledger_id=h.ledger_id, invoice_number=old.invoice_number))
            continue
        if old.totals.gross != inv.totals.gross:
            continue
        if abs((inv.issue_date - old.issue_date).days) > window:
            continue
        same_period = (old.service_period_start, old.service_period_end) == (
            inv.service_period_start,
            inv.service_period_end,
        )
        same_basis = (inv.po_reference is not None and old.po_reference == inv.po_reference) or (
            _lines_key(old) == _lines_key(inv)
        )
        if same_period and same_basis:
            out.append(finding("NEAR_DUPLICATE", ledger_id=h.ledger_id, invoice_number=old.invoice_number))
    return out
