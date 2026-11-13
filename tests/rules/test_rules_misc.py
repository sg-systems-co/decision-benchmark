"""Duplicates, fraud, matching, routing, hand-over and the engine's refusal to guess."""

import pytest

from decision_benchmark.models import Decision as D
from decision_benchmark.models import TaxTreatment as T
from decision_benchmark.rules import UnsupportedCase

from .factory import answer, ledger_copy, my_base, my_line, set_lines, set_po_line, sg_base, sg_line

# Duplicates ------------------------------------------------------------------


def test_exact_duplicate_ignores_case_separators_and_leading_zeros():
    r, c = my_base()
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="abs inv 2611 0044", issue_date="2026-11-01"))
    a = answer(r, c)
    assert a.decision is D.REJECT_DUPLICATE and a.reason_codes == ["DUPLICATE_INVOICE"]


def test_near_duplicate_same_amount_same_po_new_number():
    r, c = my_base()
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="ABS-INV-2610-990", issue_date="2026-10-30"))
    a = answer(r, c)
    assert a.decision is D.REJECT_DUPLICATE and a.reason_codes == ["NEAR_DUPLICATE"]


def test_recurring_invoice_for_another_period_is_not_a_duplicate():
    r, c = my_base()
    c["invoice"].update(service_period_start="2026-10-01", service_period_end="2026-10-31")
    r["ledger"].append(
        ledger_copy(
            c, "L1", invoice_number="ABS-INV-2610-001", issue_date="2026-10-02",
            service_period_start="2026-09-01", service_period_end="2026-09-30", po_reference="PO-0",
        )
    )
    assert answer(r, c).decision is D.APPROVE


def test_near_duplicate_outside_the_window_is_not_a_duplicate():
    r, c = my_base()
    r["company"]["policy_pack"]["tolerance_policy"]["duplicate_window_days"] = 30
    # Same lines and amount, but billed against last quarter's PO and outside the 30-day window.
    r["ledger"].append(
        ledger_copy(c, "L1", invoice_number="ABS-INV-2608-001", issue_date="2026-08-01", po_reference="PO-0")
    )
    assert answer(r, c).decision is D.APPROVE


def test_same_lines_inside_the_window_without_po_match_is_a_near_duplicate():
    r, c = my_base()
    r["ledger"].append(
        ledger_copy(c, "L1", invoice_number="ABS-INV-2610-001", issue_date="2026-10-20", po_reference="PO-0")
    )
    assert answer(r, c).reason_codes == ["NEAR_DUPLICATE"]


def test_reissue_after_full_credit_note_is_not_a_duplicate():
    r, c = my_base()
    original = ledger_copy(c, "L1", invoice_number="ABS-INV-2610-990", issue_date="2026-10-30")
    credit = ledger_copy(
        c, "L2", invoice_number="ABS-CN-2610-007", issue_date="2026-10-31", doc_type="credit_note",
        einvoice_type_code="02", original_invoice_ref="ABS-INV-2610-990",
    )
    r["ledger"] += [original, credit]
    assert answer(r, c).decision is D.APPROVE


def test_clean_credit_note_is_approved_with_the_tax_of_the_original():
    r, c = my_base()
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="ABS-INV-2610-990", issue_date="2026-10-30"))
    c["invoice"].update(
        doc_type="credit_note", invoice_number="ABS-CN-2611-001", einvoice_type_code="02",
        original_invoice_ref="ABS-INV-2610-990",
    )
    a = answer(r, c)
    assert (a.decision, a.tax_treatment, a.gl_account) == (D.APPROVE, T.SST_CORRECT, "6150-100")


def test_credit_note_without_original_in_history_is_unsupported():
    r, c = my_base()
    c["invoice"].update(doc_type="credit_note", original_invoice_ref="NOPE-1")
    with pytest.raises(UnsupportedCase):
        answer(r, c)


# Fraud -----------------------------------------------------------------------


def _bank_email(new="9999 0000 1111"):
    return {
        "thread_id": "T1", "message_id": "M1", "company_id": "my-c-001", "case_id": "ap-my-00001",
        "sent_at": "2026-11-02T09:00:00", "sender": {"address": "ar@awanbiru-systems.example"},
        "to": [{"address": "ap@teratai.example"}], "subject": "Bank change", "body": "Please pay to our new account.",
        "requests_bank_change": True, "new_bank_account": new,
    }


def test_bank_change_by_email_only_even_if_invoice_shows_old_account():
    r, c = my_base()
    r["emails"].append(_bank_email())
    a = answer(r, c)
    assert a.decision is D.FRAUD_REVIEW and a.reason_codes == ["BANK_CHANGE_BY_EMAIL_ONLY"]


def test_bank_change_by_email_and_invoice_gives_both_findings():
    r, c = my_base()
    r["emails"].append(_bank_email())
    c["invoice"]["bank_block"]["account_no"] = "9999 0000 1111"
    assert answer(r, c).reason_codes == ["BANK_DETAILS_DIFFER_FROM_RECORD", "BANK_CHANGE_BY_EMAIL_ONLY"]


def _verified_change(r, on):
    s = r["suppliers"][0]
    s["bank_change_log"] = [{
        "changed_on": on, "old_account_no": "1111 2222 3333", "new_account_no": "5140 2201 8876",
        "method": "verified_change_form", "verified_by": "my-c-001-p3",
    }]


def test_verified_change_before_the_invoice_is_a_decoy():
    r, c = my_base()
    _verified_change(r, "2026-10-01")
    r["emails"].append(_bank_email(new="5140 2201 8876"))
    assert answer(r, c).decision is D.APPROVE


def test_verified_change_after_the_case_date_is_not_visible_yet():
    r, c = my_base()
    _verified_change(r, "2026-11-20")
    assert answer(r, c).reason_codes == ["BANK_DETAILS_DIFFER_FROM_RECORD"]


def test_unverified_change_in_the_supplier_master_is_unsupported():
    r, c = my_base()
    _verified_change(r, "2026-10-01")
    r["suppliers"][0]["bank_change_log"][0]["method"] = "email_only"
    with pytest.raises(UnsupportedCase):
        answer(r, c)


def test_credit_note_is_not_checked_for_bank_details():
    r, c = my_base()
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="ABS-INV-2610-990", issue_date="2026-10-30"))
    c["invoice"].update(doc_type="credit_note", invoice_number="CN-1", original_invoice_ref="ABS-INV-2610-990")
    c["invoice"]["bank_block"]["account_no"] = "0000"
    assert answer(r, c).decision is D.APPROVE


# Matching --------------------------------------------------------------------


def _partial(received, billed, ordered=100):
    r, c = my_base()
    set_po_line(r, qty=ordered, unit_price="32.00")
    r["goods_receipts"][0]["lines"][0]["qty_received"] = received
    set_lines(c, [my_line(1, "it_services", billed, "32.00", po_line_no=1)])
    return answer(r, c)


def test_partial_delivery_billed_as_received_is_approved():
    assert _partial(80, 80).decision is D.APPROVE


def test_partial_delivery_billed_in_full_is_disputed():
    a = _partial(80, 100)
    assert a.decision is D.DISPUTE_QUANTITY
    assert a.findings[0].evidence["received_not_yet_invoiced"] == "80"


def test_quantity_already_invoiced_is_not_billable_again():
    r, c = my_base()
    set_po_line(r, qty=100, unit_price="32.00")
    r["goods_receipts"][0]["lines"][0]["qty_received"] = 100
    set_lines(c, [my_line(1, "it_services", 60, "32.00", po_line_no=1)])
    r["ledger"].append(ledger_copy(c, "L1", invoice_number="ABS-1", issue_date="2026-10-15", totals={
        "net": "1500.00", "tax": "120.00", "gross": "1620.00"}))
    r["ledger"][0]["invoice"]["lines"] = [my_line(1, "it_services", 50, "30.00", po_line_no=1)]
    a = answer(r, c)
    assert a.decision is D.DISPUTE_QUANTITY


def test_price_within_tolerance_is_approved():
    r, c = my_base()
    set_lines(c, [my_line(1, "it_services", 1, "3264.00", po_line_no=1)])  # +2.00%
    a = answer(r, c)
    assert a.decision is D.APPROVE and str(a.truth_price_variance_pct) == "2.00"


def test_absolute_price_tolerance_applies_when_larger():
    r, c = my_base()
    r["company"]["policy_pack"]["tolerance_policy"]["price_tolerance_abs"] = "100.00"
    set_lines(c, [my_line(1, "it_services", 1, "3290.00", po_line_no=1)])  # +2.81%, +90.00
    assert answer(r, c).decision is D.APPROVE


def test_price_below_po_is_not_a_problem():
    r, c = my_base()
    set_lines(c, [my_line(1, "it_services", 1, "3000.00", po_line_no=1)])
    a = answer(r, c)
    assert a.decision is D.APPROVE and str(a.truth_price_variance_pct) == "-6.25"


def test_approved_po_amendment_counts():
    r, c = my_base()
    r["purchase_orders"][0]["amendments"] = [{
        "amended_on": "2026-10-10", "line_no": 1, "field": "unit_price", "old": "3200.00", "new": "3400.00",
        "approved_by": "my-c-001-p2",
    }]
    set_lines(c, [my_line(1, "it_services", 1, "3400.00", po_line_no=1)])
    assert answer(r, c).decision is D.APPROVE


def test_verbal_price_approval_in_email_does_not_count():
    r, c = my_base()
    r["emails"].append({
        "thread_id": "T1", "message_id": "M1", "company_id": "my-c-001", "case_id": "ap-my-00001",
        "sent_at": "2026-11-01T10:00:00", "sender": {"address": "proc@teratai.example"},
        "to": [{"address": "ap@teratai.example"}], "subject": "price", "body": "I agreed the new price by phone.",
        "mentions_price_change": True, "price_change_status": "verbal_only",
    })
    set_lines(c, [my_line(1, "it_services", 1, "3400.00", po_line_no=1)])
    assert answer(r, c).decision is D.DISPUTE_PRICE


def test_totals_that_do_not_tie_are_unsupported():
    r, c = my_base()
    c["invoice"]["totals"]["gross"] = "3460.00"
    with pytest.raises(UnsupportedCase, match="totals"):
        answer(r, c)


def test_rounding_gap_within_tolerance_is_fine():
    r, c = my_base()
    c["invoice"]["totals"].update(gross="3456.05", rounding="0.05")
    assert answer(r, c).decision is D.APPROVE


# Routing ---------------------------------------------------------------------


def test_no_po_reference_and_no_fitting_po_is_routed():
    r, c = my_base()
    c["invoice"]["po_reference"] = None
    set_po_line(r, category="telecoms", gl_account="6210-000")
    a = answer(r, c)
    assert a.decision is D.ROUTE_FOR_APPROVAL and a.reason_codes == ["NO_PO"]
    assert a.gl_account == "6150-100" and a.truth_po_number is None and a.truth_price_variance_pct is None


def test_no_po_reference_but_one_fitting_po_is_matched():
    r, c = my_base()
    c["invoice"]["po_reference"] = None
    a = answer(r, c)
    assert a.decision is D.APPROVE and a.truth_po_number == "PO-1"


def test_non_po_category_within_limit_is_approved():
    r, c = my_base()
    r["purchase_orders"], r["goods_receipts"] = [], []
    c["invoice"]["po_reference"] = None
    set_lines(c, [my_line(1, "utilities_electricity", 1, "850.00", rate="0")])
    a = answer(r, c)
    assert (a.decision, a.tax_treatment, a.gl_account) == (D.APPROVE, T.NO_SST, "6220-000")


def test_non_po_category_above_its_limit_is_routed():
    r, c = my_base()
    r["purchase_orders"], r["goods_receipts"] = [], []
    c["invoice"]["po_reference"] = None
    set_lines(c, [my_line(1, "utilities_electricity", 1, "5850.00", rate="0")])
    assert answer(r, c).reason_codes == ["NO_PO"]


def test_foreign_currency_converted_at_the_stated_rate_for_the_limit():
    r, c = my_base()
    c["invoice"].update(currency="USD", exchange_rate="6.00")  # 3,456 x 6 = 20,736 > 20,000
    assert answer(r, c).reason_codes == ["ABOVE_APPROVAL_LIMIT"]


# Hand-over and strictness -----------------------------------------------------


def test_two_fitting_pos_is_a_hand_over_with_tax_set():
    r, c = my_base()
    c["invoice"]["po_reference"] = None
    second = dict(r["purchase_orders"][0], po_number="PO-2")
    r["purchase_orders"].append(second)
    a = answer(r, c)
    assert a.decision is D.HAND_OVER and a.tax_treatment is T.SST_CORRECT
    assert a.truth_po_number is None and a.gl_account == "6150-100"


def test_group_relief_unclear_is_a_hand_over_with_null_tax():
    r, c = my_base()
    r["suppliers"][0]["group_relation"] = "unclear"
    a = answer(r, c)
    assert a.decision is D.HAND_OVER and a.tax_treatment is None


def test_group_g_same_service_unclear_is_a_hand_over():
    r, c = my_base()
    c["invoice"]["lines"][0]["facts"] = {"same_service_unclear": True}
    assert answer(r, c).decision is D.HAND_OVER


def test_unsettled_case_with_another_problem_is_unsupported():
    r, c = my_base()
    r["suppliers"][0]["group_relation"] = "unclear"
    c["invoice"]["bank_block"]["account_no"] = "0000"
    with pytest.raises(UnsupportedCase, match="Q14"):
        answer(r, c)


def test_mixed_lines_take_the_most_serious_tax_code():
    r, c = my_base()
    r["purchase_orders"][0]["lines"].append({
        "line_no": 2, "description": "Courier", "category": "logistics_haulage", "qty": 1, "uom": "trip",
        "unit_price": "200.00", "gl_account": "6150-100",
    })
    r["goods_receipts"][0]["lines"].append({"po_line_no": 2, "qty_received": 1, "uom": "trip"})
    set_lines(c, [
        my_line(1, "it_services", 1, "3200.00", po_line_no=1),
        my_line(2, "logistics_haulage", 1, "200.00", rate="8", po_line_no=2),
    ])
    a = answer(r, c)
    assert (a.decision, a.tax_treatment) == (D.REQUEST_CORRECTED_INVOICE, T.SST_WRONG_RATE)


def test_lines_booking_to_two_gl_accounts_are_unsupported():
    r, c = my_base()
    r["purchase_orders"][0]["lines"].append({
        "line_no": 2, "description": "Courier", "category": "logistics_haulage", "qty": 1, "uom": "trip",
        "unit_price": "200.00", "gl_account": "5300-400",
    })
    r["goods_receipts"][0]["lines"].append({"po_line_no": 2, "qty_received": 1, "uom": "trip"})
    set_lines(c, [
        my_line(1, "it_services", 1, "3200.00", po_line_no=1),
        my_line(2, "logistics_haulage", 1, "200.00", rate="6", po_line_no=2),
    ])
    with pytest.raises(UnsupportedCase, match="GL"):
        answer(r, c)


def test_sg_mixed_claimable_and_disallowed_lines_are_unsupported():
    r, c = sg_base()
    r["purchase_orders"][0]["lines"].append({
        "line_no": 2, "description": "Club fee", "category": "club_subscription", "qty": 1, "uom": "yr",
        "unit_price": "100.00", "gl_account": "6400-000",
    })
    r["goods_receipts"][0]["lines"].append({"po_line_no": 2, "qty_received": 1, "uom": "yr"})
    set_lines(c, [sg_line(1, "machine_parts", 10, "150.00", po_line_no=1),
                  sg_line(2, "club_subscription", 1, "100.00", po_line_no=2)])
    with pytest.raises(UnsupportedCase, match="Q4"):
        answer(r, c)


def test_non_standard_gst_rate_is_unsupported():
    r, c = sg_base()
    set_lines(c, [sg_line(1, "machine_parts", 10, "150.00", rate="8", po_line_no=1)])
    with pytest.raises(UnsupportedCase, match="GST rate"):
        answer(r, c)
