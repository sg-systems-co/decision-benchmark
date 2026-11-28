"""Conflicting documents (B1-6, H2) that every country plants the same way: the price row.

The invoice bills a price above the PO and a supplier email says the new price was agreed. Emails don't count: only
an approved ERP amendment changes a PO price (the policy pack), so the key follows the PO. The patch puts the invoiced
price on the PO line, which would make the invoice match.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from . import phrases
from .country import CannotPlant


def price_conflict(d, country: str) -> None:
    """Run after the families' ops (Draft.final): the price family has raised the invoice price over the PO."""
    if d.po is None:
        raise CannotPlant("the price conflict needs the PO")
    pos = d.built.records["purchase_orders"]
    k = pos.index(d.po)
    raised = [(i, x) for i, x in enumerate(d.invoice["lines"])
              if i < len(d.po["lines"]) and Decimal(x["unit_price"]) > Decimal(d.po["lines"][i]["unit_price"])]
    if not raised:
        raise CannotPlant("the price conflict needs a line billed above the PO")
    i, line = raised[0]
    says = phrases.conflict(country, "price", d.r, price=f"{d.invoice['currency']} {line['unit_price']}")
    contact = d.supplier["contacts"][0]
    domain = d.cw.company["people"][0]["email"].split("@")[1]
    sent = d.day - timedelta(days=d.r.randint(2, 12))
    d.built.records.setdefault("emails_add", []).append({
        "thread_id": f"T-{d.built.case_id}-price", "message_id": f"M-{d.built.case_id}-price",
        "company_id": d.cw.company_id, "case_id": d.built.case_id, "sent_at": f"{sent}T{d.r.randrange(8, 18):02d}:40:00",
        "sender": {"name": contact["name"], "address": contact["email"]}, "to": [{"address": f"ap@{domain}"}],
        "subject": "Revised unit price", "body": says, "intent": "other", "signals": []})
    d.conflict = {"row": "price", "says": says, "patches": [
        {"target": "records", "path": f"purchase_orders[{k}].lines[{j}].unit_price", "value": x["unit_price"]}
        for j, x in raised]}


__all__ = ["price_conflict"]
