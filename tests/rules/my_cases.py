"""Helpers for the Malaysian rule tests (A12 build PR 2): one-line cases with planted line facts.

``one_line`` builds the MY base case with one line of any catalog category, a chosen rate and tax type,
line facts and an invoice date; the PO and receipt follow, so only the tax question is planted.
``result`` returns what the tests check: the decision, the line's treatment and basis, and the reasons.
"""

from __future__ import annotations

import datetime as dt

from .factory import CATALOG, answer, my_base, my_line, my_supplier_sst, set_lines, tax_facts

ACCOUNT = {
    "it_services": "6150-100", "management_services": "6160-000", "legal_services": "6160-000",
    "guard_services": "6170-000", "recruitment_services": "6160-000", "logistics_haulage": "5300-400",
    "courier_services": "5300-400", "telecoms": "6210-000", "advertising": "6160-000",
    "construction_works": "6160-000", "maintenance_repair": "6160-000", "software_development": "6150-100",
    "test_raw_resin": "5100-100", "test_finished_goods": "5100-300", "office_supplies": "6300-000",
    "utilities_electricity": "6220-000", "test_exempt_goods": "5100-100",
}


def one_line(category: str = "it_services", rate: str = "8", price: str = "3200.00", qty: int = 1,
             tax_type: str | None = None, day: str | None = None, supplier: tuple[str, ...] | None = None,
             **facts):
    """(records, case) with one invoice line. tax_type defaults to the category's kind (01 goods, 02 services).
    day: the invoice date (PO and receipt move before it). supplier: its SST registration types."""
    r, c = my_base()
    kind = CATALOG.get(category).tax["MY"].tax_class
    tax_type = tax_type or ("01" if kind.startswith("sales_") else "02")
    po = r["purchase_orders"][0]
    po["lines"][0].update(category=category, gl_account=ACCOUNT[category], qty=qty, unit_price=price)
    po["total_net"] = f"{qty * float(price):.2f}"
    r["goods_receipts"][0]["lines"][0]["qty_received"] = qty
    if day is not None:
        d = dt.date.fromisoformat(day)
        c["invoice"]["issue_date"] = day
        c["as_of_date"] = str(max(d + dt.timedelta(days=3), dt.date.fromisoformat(c["as_of_date"])))
        po["po_date"] = str(d - dt.timedelta(days=40))
        r["goods_receipts"][0]["gr_date"] = str(d - dt.timedelta(days=2))
    if supplier is not None:
        my_supplier_sst(r, *supplier)
    elif kind.startswith("sales_"):
        my_supplier_sst(r, "sales")
        tax_facts(r["suppliers"][0], is_manufacturer=True)
    set_lines(c, [my_line(1, category, qty, price, rate=rate, tax_type=tax_type, po_line_no=1, **facts)])
    return r, c


def result(r, c) -> tuple:
    """(decision, line treatment, line basis) of the first line."""
    a = answer(r, c)
    t = a.tax_lines[0]
    return a.decision, t.treatment, t.basis


def supplier_facts(r, **changes) -> None:
    tax_facts(r["suppliers"][0], **changes)


def company_facts(r, **changes) -> None:
    tax_facts(r["company"], **changes)


def company_sst(r, *types: str) -> None:
    """The company's registrations: its TIN plus one SST registration per type."""
    regs = [x for x in r["company"]["tax_registrations"] if x["scheme"] != "MY_SST"]
    r["company"]["tax_registrations"] = regs + [
        {"scheme": "MY_SST", "number": f"W10-0000-0000000{i}", "type": t} for i, t in enumerate(types, 1)]
