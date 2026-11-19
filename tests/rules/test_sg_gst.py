"""Singapore GST: SG-1, SG-3 to SG-6, SG-11, SG-12 (A12 build PR 3 commit 13). SG-2 and SG-4 keep their v0.9
tests (rows 2 to 5 of tests/rules/test_table_rows.py)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.sg.models import SgLineFacts, SgSupplierFacts
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer, ledger_copy
from .my_cases import result, sg_one_line

RCI, OK, HO, DUP = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER, D.REJECT_DUPLICATE


# -- SG-1 --------------------------------------------------------------------------------------------


def test_sg1_not_for_the_purpose_of_the_business_is_disallowed():
    a = answer(*sg_one_line(business_purpose=False))
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (OK, "NOT_CLAIMABLE_DISALLOWED", "SG-1")
    assert "GST_NOT_CLAIMABLE_DISALLOWED" in a.reason_codes


def test_sg1_near_miss_business_purchase_is_claimable():
    assert result(*sg_one_line(business_purpose=True)) == (OK, "CLAIMABLE", "SG-1")


def test_sg1_unknown_purpose_is_a_hand_over():
    assert result(*sg_one_line(business_purpose=None)) == (HO, None, "SG-1")


def test_sg1_condition_8_guard_missing_trader_fraud_is_not_modelled():
    # A12 decision 6: SG-1 condition 8 stays unplanted; no fact can carry it, and a clean case is claimable.
    fields = set(SgLineFacts.model_fields) | set(SgSupplierFacts.model_fields)
    assert not {f for f in fields if "fraud" in f or "trader" in f or "reasonable" in f}
    assert result(*sg_one_line()) == (OK, "CLAIMABLE", "SG-1")


# -- SG-3: rate by time of supply ------------------------------------------------------------------------


def test_sg3_invoice_after_the_change_either_rate_by_election():
    # Invoice 10 Jan 2024, delivered Dec 2023: the supplier may elect 8%; 9% is also allowed.
    for rate in ("8", "9"):
        assert result(*sg_one_line(rate=rate, day="2024-01-10", delivery_date="2023-12-15")) == (OK, "CLAIMABLE", "SG-3")


@pytest.mark.parametrize("rate, facts, expected", [
    ("7", {"delivery_date": "2023-12-15"}, (RCI, "GST_UNDERCHARGED", "SG-3")),        # below both allowed rates
    ("10", {"delivery_date": "2023-12-15"}, (RCI, "GST_WRONGLY_CHARGED", "SG-3")),
    ("9", {"amount_paid_before_change": "1500.00"}, (RCI, "GST_WRONGLY_CHARGED", "SG-3")),  # paid in full before: 8%
])
def test_sg3_rate_the_rules_dont_allow(rate, facts, expected):
    assert result(*sg_one_line(rate=rate, day="2024-01-10", **facts)) == expected


def test_sg3_invoice_before_the_change_takes_the_old_rate():
    assert result(*sg_one_line(rate="9", day="2023-12-20", delivery_date="2024-01-05")) == (
        RCI, "GST_WRONGLY_CHARGED", "SG-3")
    assert result(*sg_one_line(rate="8", day="2023-12-20", delivery_date="2024-01-05")) == (OK, "CLAIMABLE", "SG-3")


def test_sg3_near_miss_supply_wholly_on_one_side():
    assert result(*sg_one_line(rate="7", day="2022-12-20")) == (OK, "CLAIMABLE", "SG-1")
    assert result(*sg_one_line(rate="8", day="2024-01-10", amount_paid_before_change="1500.00")) == (
        OK, "CLAIMABLE", "SG-3")


def test_sg3_unknown_delivery_date_is_a_hand_over():
    assert result(*sg_one_line(rate="9", day="2024-01-10", delivery_date=None)) == (HO, None, "SG-3")


# -- SG-5: exempt supplies -------------------------------------------------------------------------------


def test_sg5_gst_on_an_exempt_supply_is_wrongly_charged():
    a = answer(*sg_one_line(exempt_supply="financial"))
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (RCI, "GST_WRONGLY_CHARGED", "SG-5")


def test_sg5_near_miss_advisory_fee_is_not_exempt_and_exempt_line_without_gst():
    assert result(*sg_one_line(exempt_supply="none")) == (OK, "CLAIMABLE", "SG-1")
    assert result(*sg_one_line(rate="0", exempt_supply="residential_property")) == (OK, "NO_GST", "SG-5")


def test_sg5_unknown_supply_category_is_a_hand_over():
    assert result(*sg_one_line(rate="0", exempt_supply=None)) == (HO, None, "SG-5")


# -- SG-6: zero-rated supplies ---------------------------------------------------------------------------


def test_sg6_gst_on_a_zero_rated_service_is_wrongly_charged():
    r, c = sg_one_line("logistics_haulage", zero_rating_provision="s21(3)(a)", international_transport=True)
    assert result(r, c) == (RCI, "GST_WRONGLY_CHARGED", "SG-6")


@pytest.mark.parametrize("facts, day", [
    ({"zero_rating_provision": "s21(3)(a)", "international_transport": True}, None),
    ({"zero_rating_provision": "s21(6)", "export_evidence": True}, None),
    ({"zero_rating_provision": "s21(3)(u)"}, "2021-11-10"),
    ({"zero_rating_provision": "s21(3)(e)"}, None),
])
def test_sg6_zero_rated_line_shows_0_percent(facts, day):
    assert result(*sg_one_line("logistics_haulage", rate="0", day=day, **facts)) == (OK, "NO_GST", "SG-6")


@pytest.mark.parametrize("facts, day", [
    ({"zero_rating_provision": "s21(3)(a)", "international_transport": False}, None),
    ({"zero_rating_provision": "s21(3)(u)"}, "2022-02-10"),             # advertising: only before 1 Jan 2022
])
def test_sg6_near_miss_provision_doesnt_apply_so_gst_was_left_off(facts, day):
    assert result(*sg_one_line("logistics_haulage", rate="0", day=day, **facts)) == (RCI, "GST_UNDERCHARGED", "SG-12")


def test_sg6_unknown_overseas_beneficiary_is_a_hand_over():
    r, c = sg_one_line("it_services", rate="0", zero_rating_provision="s21(3)(j)", beneficiary_outside_singapore=None)
    assert result(r, c) == (HO, None, "SG-6")


# -- SG-11: duplicate claims ----------------------------------------------------------------------------


def test_sg11_duplicate_claim_is_caught_by_the_duplicate_check():
    r, c = sg_one_line()
    r["ledger"].append(ledger_copy(c, "L1"))
    assert answer(r, c).decision is DUP


def test_sg11_near_miss_another_invoice_is_not_a_duplicate():
    r, c = sg_one_line()
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="KMP-26-0700", issue_date="2026-06-15", po_reference="4500009999"))
    assert answer(r, c).decision is OK


# -- SG-12: GST left off ---------------------------------------------------------------------------------


def test_sg12_registered_supplier_leaves_gst_off_a_standard_rated_supply():
    a = answer(*sg_one_line(rate="0"))
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (RCI, "GST_UNDERCHARGED", "SG-12")
    assert a.reason_codes == ["TAX_UNDERCHARGED"]


def test_sg12_near_miss_unregistered_supplier_charges_none():
    r, c = sg_one_line(rate="0")
    r["suppliers"][0]["tax_registrations"] = []
    c["invoice"]["einvoice"]["supplier_gst_no"] = None
    assert result(r, c) == (OK, "NO_GST", "SG-4")


def test_catalog_fact_default_residential_lease_is_exempt_without_a_line_fact():
    assert result(*sg_one_line("test_residential_lease_sg", rate="0")) == (OK, "NO_GST", "SG-5")
    assert result(*sg_one_line("test_residential_lease_sg", rate="9")) == (RCI, "GST_WRONGLY_CHARGED", "SG-5")
