"""Decision priority: fraud > duplicate > invalid invoice > mismatch > routing (spec), and the order inside the
mismatch tier (plan Q7)."""

import itertools

import pytest

from decision_benchmark.models import Decision as D

from .factory import answer, ledger_copy, my_base, my_line, set_lines


def plant_fraud(r, c):
    c["invoice"]["bank_block"]["account_no"] = "8800 1234 5678"


def plant_duplicate(r, c):
    r["ledger"].append(ledger_copy(c, "L-DUP", issue_date="2026-11-01"))


def plant_invalid(r, c):
    c["invoice"]["buyer_tin"] = None


def plant_mismatch(r, c):
    set_lines(c, [my_line(1, "it_services", 1, "3400.00", po_line_no=1)])


def plant_routing(r, c):
    r["company"]["policy_pack"]["approval_matrix"][0]["limit"] = "1000.00"


TIERS = [
    ("fraud", plant_fraud, D.FRAUD_REVIEW, "BANK_DETAILS_DIFFER_FROM_RECORD"),
    ("duplicate", plant_duplicate, D.REJECT_DUPLICATE, "DUPLICATE_INVOICE"),
    ("invalid", plant_invalid, D.REQUEST_CORRECTED_INVOICE, "MISSING_MANDATORY_FIELD"),
    ("mismatch", plant_mismatch, D.DISPUTE_PRICE, "PRICE_ABOVE_PO"),
    ("routing", plant_routing, D.ROUTE_FOR_APPROVAL, "ABOVE_APPROVAL_LIMIT"),
]


@pytest.mark.parametrize("tier", TIERS, ids=[t[0] for t in TIERS])
def test_each_tier_alone(tier):
    _, plant, decision, code = tier
    r, c = my_base()
    plant(r, c)
    a = answer(r, c)
    assert a.decision is decision
    assert a.reason_codes == [code]


@pytest.mark.parametrize(
    "high, low", list(itertools.combinations(TIERS, 2)), ids=lambda t: t[0]
)
def test_higher_tier_wins(high, low):
    r, c = my_base()
    # Plant the price mismatch first: set_lines rewrites the invoice lines and totals.
    for _, plant, _, _ in sorted([high, low], key=lambda t: t[0] != "mismatch"):
        plant(r, c)
    a = answer(r, c)
    assert a.decision is high[2]
    assert a.reason_codes.index(high[3]) < a.reason_codes.index(low[3])


def test_not_received_beats_quantity_and_price():
    r, c = my_base()
    r["goods_receipts"] = []
    set_lines(c, [my_line(1, "it_services", 1, "3400.00", po_line_no=1)])
    a = answer(r, c)
    assert a.decision is D.HOLD_NOT_RECEIVED
    assert a.reason_codes == ["NOT_RECEIVED", "PRICE_ABOVE_PO"]


def test_quantity_beats_price():
    r, c = my_base()
    set_lines(c, [my_line(1, "it_services", 2, "3400.00", po_line_no=1)])
    a = answer(r, c)
    assert a.decision is D.DISPUTE_QUANTITY
    assert a.reason_codes == ["QUANTITY_ABOVE_RECEIVED", "PRICE_ABOVE_PO"]
