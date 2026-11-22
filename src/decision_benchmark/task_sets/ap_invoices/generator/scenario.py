"""The clean base case (B1-2): a PO, its receipt and a correct invoice from a domestic supplier, with the facts the
rules read stated in the governing documents.

The generator plants what it expects (decision APPROVE; per line the treatment and basis of the pack's clean line) and
the engine must find it independently (B1 plan section 4). Dates: the invoice falls in the slot's window; the receipt,
and on services the service period, fall on or after the last dated boundary before the invoice, so no rate or scope
change lies between them (a change in between is a family's job, not the clean base's).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from decision_benchmark.core.generator.seeds import rng
from decision_benchmark.core.generator.slots import Slot
from decision_benchmark.core.generator.spec import Generation, SplitSpec

from ..countries import pack
from .entities import (
    APPROVAL, CENT, CompanyWorld, catalog, day_between, invoice_dict, money, price, tax_of,
)
from .statements import Statements

AS_OF_LAG = (3, 21)
AS_OF_CAP = date(2026, 11, 18)
"""as_of_date is the invoice date plus 3-21 days, capped at 18 Nov 2026 (B1 plan section 6)."""
PO_LEAD = (10, 45)


class NoCleanForm(ValueError):
    """The slot can't take a clean case on the drawn date (no supplier has a category the clean base can use)."""


@dataclass
class Planted:
    """Generator truth: what the engine must find (B1 plan section 2.2)."""

    decision: str
    lines: list[tuple[int, str, str]]
    """(line_no, treatment, basis) per line."""
    findings: list[str] = field(default_factory=list)
    buyer_actions: list[str] = field(default_factory=list)


@dataclass
class BuiltCase:
    case_id: str
    company_id: str
    records: dict
    """The company records with the case's own PO and receipt added (JSON-ready)."""
    case: dict
    """The Case payload (JSON-ready)."""
    planted: Planted
    docs: dict[str, dict]
    """The case's documents by doc id, as the statement registry wrote them."""
    attempt: int = 0


def last_boundary(gen: Generation, country: str, day: date) -> date:
    """The latest dated boundary on or before ``day`` (the window start if none)."""
    days = [b.day for b in gen.boundaries if b.country == country and b.day <= day]
    return max(days, default=gen.windows[country][0])


def clean_case(gen: Generation, split: SplitSpec, cw: CompanyWorld, slot: Slot, attempt: int = 0,
               need_taxed: bool = False) -> BuiltCase:
    """need_taxed: line 1 must carry tax (a family will plant a tax problem on it)."""
    r = rng(split.seed, "case", slot.case_index, "clean", attempt)
    g = pack(cw.country).generation
    lo, hi = slot.window or gen.windows[cw.country]
    day = day_between(r, lo, hi)
    covered = cw.certificate_categories(day)
    options = []
    for s in cw.domestic_suppliers():
        cats = [c for c in cw.categories[s["supplier_id"]] if c not in covered
                and g.clean_line(catalog().get(c), day) is not None]
        taxed = [c for c in cats if g.clean_line(catalog().get(c), day).rate > 0]
        if cats and (taxed or not need_taxed):
            options.append((s, cats, taxed))
    if not options:
        raise NoCleanForm(f"{cw.company_id} on {day}: no supplier with a clean category")
    supplier, cats, taxed = r.choice(options)
    sid = supplier["supplier_id"]
    anchor = max(last_boundary(gen, cw.country, day), day - timedelta(days=60))
    po_date = day - timedelta(days=r.randint(*PO_LEAD))
    gr_date = day_between(r, max(anchor, po_date + timedelta(days=1)), day) if po_date < day else day
    cc = cw.country.lower()
    po_number = f"PO-{cc.upper()}-{slot.case_index:06d}"
    gr_number = f"GR-{cc.upper()}-{slot.case_index:06d}"
    invoice_id = f"INV-{cc.upper()}-{slot.case_index:06d}"
    number = f"{supplier['name'][:3].upper()}-{day:%y%m}-{slot.case_index:05d}"

    lines, po_lines, gr_lines, planted = [], [], [], []
    for n in range(1, slot.lines + 1):
        cat = catalog().get(r.choice(taxed if need_taxed and n == 1 else cats))
        clean = g.clean_line(cat, day)
        assert clean is not None
        qty = r.randint(1, 40) if cat.kind == "goods" else r.randint(1, 2)
        uom = "unit" if cat.kind == "goods" else ("month" if qty == 1 else "job")
        unit = price(r, cat.kind)
        net = (Decimal(qty) * unit).quantize(CENT)
        description = f"{cat.label}" if cat.kind == "goods" else f"{cat.label}, {day:%B %Y}"
        lines.append({"line_no": n, "description": description, "qty": qty, "uom": uom, "unit_price": money(unit),
                      "net_amount": money(net), "tax_rate": str(clean.rate), "tax_amount": money(tax_of(net, clean.rate)),
                      "po_line_no": n, "category": cat.category, "ext": clean.ext})
        po_lines.append({"line_no": n, "description": description, "category": cat.category, "qty": qty, "uom": uom,
                         "unit_price": money(unit), "gl_account": cw.account_for_role[cat.gl_role]})
        gr_lines.append({"po_line_no": n, "qty_received": qty, "uom": uom})
        planted.append((n, clean.treatment, clean.basis))

    gross = sum(Decimal(x["net_amount"]) + Decimal(x["tax_amount"]) for x in lines)
    role = next(role for role, limit in APPROVAL if gross <= limit)
    approver = next(p for p in cw.company["people"] if p.get("approval_role") == role)
    requester = next(p for p in cw.company["people"] if p["role"] == "requester")
    po = {"po_number": po_number, "company_id": cw.company_id, "supplier_id": sid, "po_date": str(po_date),
          "currency": supplier["currency"], "requester_id": requester["person_id"], "approver_id": approver["person_id"],
          "status": "open", "lines": po_lines, "total_net": money(sum(Decimal(x["net_amount"]) for x in lines))}
    has_goods = any(catalog().get(x["category"]).kind == "goods" for x in lines)
    gr = {"gr_number": gr_number, "po_number": po_number, "gr_date": str(gr_date),
          "kind": "goods" if has_goods else "service_confirmation", "received_by": requester["person_id"],
          "lines": gr_lines}
    invoice = invoice_dict(cw, supplier, lines, day, number, invoice_id, po_number)

    st = Statements()
    st.document(po_number, po)
    st.document(gr_number, gr)
    st.document(f"supplier:{sid}", supplier)
    st.document(f"company:{cw.company_id}", cw.company)
    fields = pack(cw.country).line_facts_model.model_fields
    services = [x for x in invoice["lines"] if catalog().get(x["category"]).kind == "service"]
    if services and "service_period_start" in fields:
        start = max(anchor, day - timedelta(days=r.randint(20, 40)))
        end = day - timedelta(days=1)
        if start <= end:
            invoice["service_period_start"], invoice["service_period_end"] = str(start), str(end)
    st.document(invoice_id, invoice)
    for line in invoice["lines"]:
        kind = catalog().get(line["category"]).kind
        if kind == "service" and invoice.get("service_period_start"):
            st.state(line, "service_period_start", invoice_id, "service_period_start")
            st.state(line, "service_period_end", invoice_id, "service_period_end")
        if kind == "goods" and "delivery_date" in fields:
            st.state(line, "delivery_date", gr_number, "gr_date")

    as_of = min(day + timedelta(days=r.randint(*AS_OF_LAG)), max(AS_OF_CAP, day))
    case = {"company_id": cw.company_id, "as_of_date": str(as_of), "supplier_id": sid, "invoice": invoice,
            "exception_types": [], "families": ["clean_base"], "two_problems": False}
    records = cw.records() | {"purchase_orders": [po], "goods_receipts": [gr]}
    return BuiltCase(case_id=f"ap-{cc}-{slot.case_index:05d}", company_id=cw.company_id, records=records, case=case,
                     planted=Planted(decision="APPROVE", lines=planted), docs=st.docs, attempt=attempt)
