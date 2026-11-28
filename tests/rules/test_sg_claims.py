"""Singapore customer accounting, reverse charge, partial exemption and Regulations 26/27: SG-7 to SG-10
(A12 build PR 3 commit 14)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer
from .my_cases import result, sg_company_facts, sg_one_line

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER


def phones(rate="0", qty=100, statement=True, **facts):
    # 100 phones at S$150.00 = S$15,000.00 excluding GST: above the S$10,000 customer accounting threshold.
    r, c = sg_one_line(rate=rate, qty=qty, prescribed_goods=facts.pop("goods", "mobile_phone"), **facts)
    c["invoice"]["einvoice"]["customer_accounting_statement"] = statement
    return r, c


def foreign(category="it_services", status="fully_taxable", day=None, **facts):
    r, c = sg_one_line(category, rate="0", day=day, supplier_country="US", **facts)
    r["suppliers"][0]["tax_registrations"] = []
    c["invoice"]["einvoice"]["supplier_gst_no"] = None
    sg_company_facts(r, input_tax_status=status)
    return r, c


# -- SG-7: customer accounting ---------------------------------------------------------------------------


def test_sg7_customer_accounting_invoice_the_buyer_accounts():
    a = answer(*phones())
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (OK, "CUSTOMER_ACCOUNTING", "SG-7")
    assert [x.action for x in a.buyer_actions] == ["ACCOUNT_CUSTOMER_ACCOUNTING_GST"]


def test_sg7_gst_charged_on_prescribed_goods_is_wrongly_charged():
    assert result(*phones(rate="9")) == (RCI, "GST_WRONGLY_CHARGED", "SG-7")


def test_sg7_without_the_statement_it_is_not_a_customer_accounting_invoice():
    assert result(*phones(statement=False)) == (RCI, "NOT_CLAIMABLE_INVALID_INVOICE", "SG-7")


@pytest.mark.parametrize("kw", [{"qty": 10, "rate": "9"}, {"goods": "none", "rate": "9"},
                                {"business_purpose": False, "rate": "9"}])
def test_sg7_near_miss_below_threshold_not_prescribed_or_not_for_business(kw):
    assert result(*phones(**kw))[1] in ("CLAIMABLE", "NOT_CLAIMABLE_DISALLOWED")


def test_sg7_unknown_goods_type_is_a_hand_over():
    assert result(*phones(goods=None)) == (HO, None, "SG-7")


# -- SG-8: reverse charge --------------------------------------------------------------------------------


def test_sg8_partially_exempt_buyer_reverse_charges_an_imported_service():
    a = answer(*foreign(status="partially_exempt"))
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (OK, "REVERSE_CHARGE", "SG-8")
    assert [x.action for x in a.buyer_actions] == ["ACCOUNT_REVERSE_CHARGE_GST"]
    r, c = foreign("machine_parts", status="partially_exempt", low_value_goods=True)
    assert result(r, c) == (OK, "REVERSE_CHARGE", "SG-8")


@pytest.mark.parametrize("category, status, day, facts", [
    ("it_services", "fully_taxable", None, {}),
    ("it_services", "de_minimis_met", None, {}),
    ("machine_parts", "partially_exempt", None, {"low_value_goods": False}),   # GST at import, not on the invoice
    ("it_services", "partially_exempt", "2019-11-10", {}),                      # before 1 Jan 2020
    ("machine_parts", "partially_exempt", "2022-11-10", {"low_value_goods": True}),  # before 1 Jan 2023
])
def test_sg8_near_miss_buyer_does_nothing(category, status, day, facts):
    assert result(*foreign(category, status, day, **facts)) == (OK, "NO_GST", "SG-8")


def test_sg8_unknown_input_tax_status_is_a_hand_over():
    assert result(*foreign(status=None)) == (HO, None, "SG-8")


# -- SG-9: partially exempt buyers -----------------------------------------------------------------------


@pytest.mark.parametrize("attribution, code", [("exempt", "NOT_CLAIMABLE_EXEMPT_USE"),
                                               ("residual", "RESIDUAL_APPORTIONED"), ("taxable", "CLAIMABLE")])
def test_sg9_partially_exempt_buyer_by_attribution(attribution, code):
    r, c = sg_one_line(purchase_attribution=attribution)
    sg_company_facts(r, input_tax_status="partially_exempt")
    assert result(r, c) == (OK, code, "SG-9")


@pytest.mark.parametrize("attribution, basis", [("exempt", "SG-9"), ("residual", "SG-9"), ("taxable", "SG-1")])
def test_sg9_near_miss_de_minimis_met_claims_in_full(attribution, basis):
    # Engine 0.10.5: the de minimis rule is SG-9's exception, so exempt and residual lines are claimable by SG-9.
    r, c = sg_one_line(purchase_attribution=attribution)
    sg_company_facts(r, input_tax_status="de_minimis_met")
    assert result(r, c) == (OK, "CLAIMABLE", basis)


@pytest.mark.parametrize("status, facts", [("partially_exempt", {}), (None, {}), ("de_minimis_met", {})])
def test_sg9_unknown_attribution_or_status_is_a_hand_over(status, facts):
    r, c = sg_one_line(**facts)
    sg_company_facts(r, input_tax_status=status)
    assert result(r, c) == (HO, None, "SG-9")


# -- SG-10: Regulations 26/27 and related IRAS rules -------------------------------------------------------


@pytest.mark.parametrize("category", ["director_only_benefit", "third_party_csr"])
def test_sg10_director_only_benefits_and_csr_are_disallowed(category):
    assert result(*sg_one_line(disallowed_category=category)) == (OK, "NOT_CLAIMABLE_DISALLOWED", "SG-10")


def test_sg10_motor_car_exceptions_from_their_dates():
    car = {"vehicle_is_motor_car": True}
    assert result(*sg_one_line("motor_car_running", chauffeured_pay_per_trip=True, **car)) == (OK, "CLAIMABLE", "SG-10")
    assert result(*sg_one_line("motor_car_running", car_used_by_third_party=True, **car)) == (OK, "CLAIMABLE", "SG-10")


@pytest.mark.parametrize("facts, day, rate", [
    ({"chauffeured_pay_per_trip": True}, "2022-03-10", "7"),        # before 1 Apr 2022
    ({"car_used_by_third_party": True}, "2022-12-10", "7"),         # before 1 Jan 2023
])
def test_sg10_near_miss_motor_car_exception_before_its_date(facts, day, rate):
    r, c = sg_one_line("motor_car_running", rate=rate, day=day, vehicle_is_motor_car=True, **facts)
    assert result(r, c) == (OK, "NOT_CLAIMABLE_DISALLOWED", "SG-10")


def test_sg10_near_miss_no_disallowed_category():
    assert result(*sg_one_line(disallowed_category="none")) == (OK, "CLAIMABLE", "SG-1")



@pytest.mark.parametrize("facts", [
    {"status": "de_minimis_met", "non_business_receipts": True},
    {"status": "fully_taxable", "in_gst_group": True, "gst_group_full_credit": False},
    {"status": "de_minimis_met", "in_gst_group": True, "gst_group_full_credit": False},
])
def test_sg8_non_business_receipts_or_a_group_without_full_credit_reverse_charge(facts):
    status = facts.pop("status")
    r, c = foreign(status=status)
    sg_company_facts(r, **facts)
    assert result(r, c) == (OK, "REVERSE_CHARGE", "SG-8")


def test_sg8_near_miss_group_entitled_to_full_credit():
    r, c = foreign(status="de_minimis_met")
    sg_company_facts(r, in_gst_group=True, gst_group_full_credit=True)
    assert result(r, c) == (OK, "NO_GST", "SG-8")


@pytest.mark.parametrize("facts", [{"in_gst_group": True}, {"non_business_receipts": None}])
def test_sg8_unknown_group_credit_or_non_business_receipts_is_a_hand_over(facts):
    r, c = foreign()
    sg_company_facts(r, **facts)
    assert result(r, c) == (HO, None, "SG-8")
