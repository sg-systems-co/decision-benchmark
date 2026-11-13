"""Clean base cases as plain dicts, so tests can plant one change and check the answer.

my_base() and sg_base() return fresh (records, case) dicts each call. answer()
validates them through the pydantic models and runs the rules engine.
"""

from __future__ import annotations

import copy
from pathlib import Path

from decision_benchmark.models import Case, CompanyRecords, load_catalog
from decision_benchmark.rules import answer_case

CATALOG = load_catalog(Path(__file__).resolve().parents[1] / "fixtures" / "catalog.yaml")

RULE = {"counts_only_verified": True, "text": "Only verified changes count."}


def _coa(prefix_roles: dict[str, str]) -> list[dict]:
    return [
        {"code": code, "name": role.replace("_", " ").title(), "type": "expense", "role": role}
        for code, role in prefix_roles.items()
    ]


MY_COA = {
    "6150-100": "it_services",
    "6160-000": "professional_fees",
    "6170-000": "security",
    "5300-400": "freight_inward",
    "6210-000": "telecoms",
    "5100-100": "raw_materials",
    "5100-300": "consumables",
    "6300-000": "office_supplies",
    "6220-000": "utilities",
}
SG_COA = {
    "6420-000": "club_subscriptions",
    "6510-000": "staff_welfare_medical",
    "6520-000": "staff_welfare",
    "6610-000": "motor_vehicle_running",
    "6150-000": "it_services",
    "5300-000": "freight_inward",
    "6400-000": "repairs_maintenance",
    "6300-000": "office_supplies",
    "6220-000": "utilities",
}


def _people(cid: str) -> list[dict]:
    return [
        {"person_id": f"{cid}-p1", "name": "Requester One", "role": "requester", "email": f"req@{cid}.example"},
        {"person_id": f"{cid}-p2", "name": "Approver Two", "role": "manager", "email": f"mgr@{cid}.example",
         "approval_role": "ops_manager"},
        {"person_id": f"{cid}-p3", "name": "Director Three", "role": "director", "email": f"dir@{cid}.example",
         "approval_role": "director"},
    ]


def _policy(currency: str, coa: dict[str, str], country: str) -> dict:
    return {
        "tolerance_policy": {"price_tolerance_pct": "2.0", "rounding_tolerance": "0.05", "duplicate_window_days": 90},
        "approval_matrix": [
            {"approval_role": "ops_manager", "limit": "20000.00", "currency": currency},
            {"approval_role": "director", "limit": "200000.00", "currency": currency},
        ],
        "non_po_policy": {"allowed_categories": ["utilities_electricity"], "max_amount": "5000.00"},
        "chart_of_accounts": _coa(coa),
        "tax_registration": {"country": country, "numbers": {"tax": "X"}, "status": "registered"},
        "price_change_rule": RULE,
        "bank_change_rule": RULE,
    }


def _address(country: str) -> dict:
    return {"lines": ["1 Test Road"], "city": "Test City", "country": country}


def my_base() -> tuple[dict, dict]:
    cid = "my-c-001"
    records = {
        "company": {
            "company_id": cid, "split": "train", "country": "MY",
            "legal_name": "Teratai Plastik Industri Sdn Bhd", "registration_no": "202001000001",
            "address": _address("MY"), "base_currency": "MYR", "industry": "plastics",
            "tin": "C1000000001", "sst_registration_no": "W10-0000-00000001",
            "is_registered_manufacturer": True, "services_provided": [],
            "people": _people(cid), "policy_pack": _policy("MYR", MY_COA, "MY"),
        },
        "suppliers": [{
            "supplier_id": "S1", "company_id": cid, "name": "Awan Biru Systems Sdn Bhd", "country": "MY",
            "address": _address("MY"), "registration_no": "201901000002", "currency": "MYR",
            "payment_terms_days": 30,
            "bank_account": {"bank_name": "Bank Seri Pertama", "account_name": "Awan Biru Systems",
                             "account_no": "5140 2201 8876"},
            "tin": "C2000000002", "brn": "201901000002", "sst_registration_no": "W10-2403-32000418",
            "sst_type": "service", "turnover_band": "RM5m-25m",
        }],
        "purchase_orders": [{
            "po_number": "PO-1", "company_id": cid, "supplier_id": "S1", "po_date": "2026-09-20",
            "currency": "MYR", "requester_id": f"{cid}-p1", "approver_id": f"{cid}-p2", "status": "open",
            "lines": [{"line_no": 1, "description": "IT support retainer, Oct 2026", "category": "it_services",
                       "qty": 1, "uom": "month", "unit_price": "3200.00", "gl_account": "6150-100"}],
            "total_net": "3200.00",
        }],
        "goods_receipts": [{
            "gr_number": "GR-1", "po_number": "PO-1", "gr_date": "2026-10-31", "kind": "service_confirmation",
            "received_by": f"{cid}-p1", "lines": [{"po_line_no": 1, "qty_received": 1, "uom": "month"}],
        }],
        "ledger": [],
        "emails": [],
    }
    case = {
        "case_id": "ap-my-00001", "split": "train", "country": "MY", "company_id": cid,
        "as_of_date": "2026-11-05", "supplier_id": "S1",
        "invoice": {
            "country": "MY", "invoice_id": "INV-CASE-1", "invoice_number": "ABS-INV-2611-044",
            "issue_date": "2026-11-02", "supplier_block": {"name": "Awan Biru Systems Sdn Bhd", "address": "x"},
            "buyer_block": {"name": "Teratai Plastik Industri Sdn Bhd", "address": "y"},
            "po_reference": "PO-1", "currency": "MYR",
            "totals": {"net": "3200.00", "tax": "256.00", "gross": "3456.00"},
            "bank_block": {"account_no": "5140 2201 8876"},
            "is_einvoice": True, "einvoice_version": "1.0", "einvoice_type_code": "01",
            "supplier_tin": "C2000000002", "supplier_brn": "201901000002", "supplier_sst_no": "W10-2403-32000418",
            "buyer_tin": "C1000000001", "buyer_brn": "202001000001",
            "tax_total_by_type": {"02": "256.00"},
            "lines": [my_line(1, "it_services", 1, "3200.00", rate="8", tax_type="02", po_line_no=1)],
        },
    }
    return records, case


def my_line(n, category, qty, price, rate="8", tax_type="02", po_line_no=None, **facts) -> dict:
    from decimal import ROUND_HALF_UP, Decimal

    net = (Decimal(str(qty)) * Decimal(price)).quantize(Decimal("0.01"))
    tax = (net * Decimal(rate) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    line = {
        "line_no": n, "description": f"{category} line {n}", "qty": qty, "uom": "unit", "unit_price": price,
        "net_amount": str(net), "tax_rate": rate, "tax_amount": str(tax),
        "classification_code": "022", "tax_type": tax_type if Decimal(rate) > 0 else "06",
        "po_line_no": po_line_no, "category": category,
    }
    if facts:
        line["facts"] = facts
    return line


def sg_line(n, category, qty, price, rate="9", po_line_no=None, **facts) -> dict:
    line = my_line(n, category, qty, price, rate=rate, po_line_no=po_line_no, **facts)
    del line["classification_code"], line["tax_type"]
    line["tax_category"] = "SR" if rate != "0" else "OS"
    return line


def sg_base() -> tuple[dict, dict]:
    cid = "sg-c-001"
    records = {
        "company": {
            "company_id": cid, "split": "train", "country": "SG",
            "legal_name": "Larkspur Precision Engineering Pte Ltd", "registration_no": "201800001A",
            "address": _address("SG"), "base_currency": "SGD", "industry": "engineering",
            "gst_reg_no": "M2-0098761-K", "gst_registered_since": "2018-04-01",
            "people": _people(cid), "policy_pack": _policy("SGD", SG_COA, "SG"),
        },
        "suppliers": [{
            "supplier_id": "S1", "company_id": cid, "name": "Kestrel Machine Parts Pte Ltd", "country": "SG",
            "address": _address("SG"), "registration_no": "201500002B", "currency": "SGD",
            "payment_terms_days": 30,
            "bank_account": {"bank_name": "Harbourfront Bank", "account_name": "Kestrel", "account_no": "771-20034-1"},
            "gst_reg_no": "20-0412377-W", "gst_status": "registered", "gst_status_date": "2015-06-01",
        }],
        "purchase_orders": [{
            "po_number": "4500010001", "company_id": cid, "supplier_id": "S1", "po_date": "2026-09-20",
            "currency": "SGD", "requester_id": f"{cid}-p1", "approver_id": f"{cid}-p2", "status": "open",
            "lines": [{"line_no": 1, "description": "Spindle bearing", "category": "machine_parts",
                       "qty": 10, "uom": "pc", "unit_price": "150.00", "gl_account": "6400-000"}],
            "total_net": "1500.00",
        }],
        "goods_receipts": [{
            "gr_number": "GR-1", "po_number": "4500010001", "gr_date": "2026-10-20", "kind": "goods",
            "received_by": f"{cid}-p1", "lines": [{"po_line_no": 1, "qty_received": 10, "uom": "pc"}],
        }],
        "ledger": [],
        "emails": [],
    }
    case = {
        "case_id": "ap-sg-00001", "split": "train", "country": "SG", "company_id": cid,
        "as_of_date": "2026-11-05", "supplier_id": "S1",
        "invoice": {
            "country": "SG", "invoice_id": "INV-CASE-1", "invoice_number": "KMP-26-0981",
            "issue_date": "2026-10-28", "supplier_block": {"name": "Kestrel Machine Parts Pte Ltd", "address": "x"},
            "buyer_block": {"name": "Larkspur Precision Engineering Pte Ltd", "address": "y"},
            "po_reference": "4500010001", "currency": "SGD", "document_title": "Tax Invoice",
            "supplier_gst_no": "20-0412377-W",
            "totals": {"net": "1500.00", "tax": "135.00", "gross": "1635.00"},
            "bank_block": {"account_no": "771-20034-1"},
            "lines": [sg_line(1, "machine_parts", 10, "150.00", po_line_no=1)],
        },
    }
    return records, case


def set_lines(case: dict, lines: list[dict]) -> None:
    """Replace the invoice lines and recompute the printed totals."""
    from decimal import Decimal

    inv = case["invoice"]
    inv["lines"] = lines
    net = sum(Decimal(line["net_amount"]) for line in lines)
    tax = sum(Decimal(line["tax_amount"]) for line in lines)
    inv["totals"] = {"net": f"{net:.2f}", "tax": f"{tax:.2f}", "gross": f"{net + tax:.2f}"}
    if inv["country"] == "MY":
        by_type: dict[str, Decimal] = {}
        for line in lines:
            if Decimal(line["tax_amount"]) > 0:
                by_type[line["tax_type"]] = by_type.get(line["tax_type"], Decimal(0)) + Decimal(line["tax_amount"])
        inv["tax_total_by_type"] = {k: f"{v:.2f}" for k, v in by_type.items()} or {"06": "0.00"}


def set_po_line(records: dict, **changes) -> None:
    records["purchase_orders"][0]["lines"][0].update(changes)


def ledger_copy(case: dict, ledger_id: str, **invoice_changes) -> dict:
    """A history entry that copies the case invoice, with changes."""
    inv = copy.deepcopy(case["invoice"]) | {"invoice_id": f"HIST-{ledger_id}"}
    inv.update(invoice_changes)
    return {"ledger_id": ledger_id, "supplier_id": case["supplier_id"], "status": "paid",
            "posted_on": str(inv["issue_date"]), "invoice": inv}


def answer(records: dict, case: dict):
    return answer_case(CompanyRecords.model_validate(records), Case.model_validate(case), CATALOG)
