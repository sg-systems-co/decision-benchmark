"""Withholding tax on payments to non-residents: WH-1 to WH-5 and the treaty-rate loaders (A12 build PR 3 commit 15)."""

from decimal import Decimal

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.my import treaties as my_treaties
from decision_benchmark.task_sets.ap_invoices.countries.sg import treaties as sg_treaties
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer
from .my_cases import company_facts, one_line, sg_one_line, sg_supplier_facts, supplier_facts
from .test_my_exemptions import imported

HO = D.HAND_OVER


def withheld(a) -> list[tuple]:
    return [(x.rate, x.basis, x.base_amount) for x in a.buyer_actions if x.action == "WITHHOLD_TAX"]


def cert(r, country):
    r["residence_certificates"] = [{"certificate_id": "COR-1", "supplier_id": "S1", "country": country,
                                    "valid_from": "2026-01-01"}]


def my_payee(nature, country="SG", certificate=False, **facts):
    r, c = imported("it_services", payment_nature=nature, **facts)
    r["suppliers"][0]["country"] = country
    if certificate:
        cert(r, country)
    return r, c


# -- Loaders -----------------------------------------------------------------------------------------------


def test_treaty_tables_load_and_every_country_maps():
    assert len(my_treaties.table().rows) == 78 and my_treaties.row("SG").royalties.general == Decimal(8)
    assert my_treaties.row("BE").interest.for_payer(industrial_undertaking=True) == Decimal(10)
    rows = sg_treaties.sg_table().rows
    assert len(rows) == 107 and all(r.country in sg_treaties.IRAS_COUNTRIES for r in rows)
    confirmed = [a for r in rows for a in (r.interest, r.royalties, r.technical_fees) if a.confirmed]
    assert len(confirmed) == 62 and all(a.status == "single rate in the article" for a in confirmed)
    assert sg_treaties.treaty("BH").agreement == "DTA"       # the comprehensive DTA, not the limited one


# -- WH-1 interest and royalties ----------------------------------------------------------------------------


@pytest.mark.parametrize("nature, certificate, rate", [
    ("interest", False, "15"), ("interest", True, "10"), ("royalty", False, "10"), ("royalty", True, "8"),
])
def test_wh1_interest_and_royalties(nature, certificate, rate):
    a = answer(*my_payee(nature, certificate=certificate))
    assert withheld(a) == [(Decimal(rate), "WH-1", Decimal("3200.00"))]
    assert a.tax_treatment == "SST_BUYER_ACCOUNTS"          # withholding doesn't change the treatment


def test_wh1_industrial_undertaking_row_15_10():
    r, c = my_payee("interest", country="BE", certificate=True)
    company_facts(r, industrial_undertaking=True)
    assert withheld(answer(r, c))[0][0] == Decimal(10)
    r, c = my_payee("interest", country="BE", certificate=True)
    assert withheld(answer(r, c))[0][0] == Decimal(15)


def test_wh1_near_miss_resident_supplier_or_no_nature():
    assert withheld(answer(*one_line(payment_nature="interest"))) == []
    assert withheld(answer(*my_payee("none"))) == []


# -- WH-2 special classes of income --------------------------------------------------------------------------


def test_wh2_technical_services_in_malaysia():
    a = answer(*my_payee("technical_advice", place_of_performance="in_country"))
    assert withheld(a) == [(Decimal(10), "WH-2", Decimal("3200.00"))]
    a = answer(*my_payee("technical_advice", certificate=True, place_of_performance="in_country"))
    assert withheld(a) == [(Decimal(5), "WH-2", Decimal("3200.00"))]      # Malaysia-Singapore technical fees 5%


def test_wh2_mixed_contract_on_the_malaysian_part_without_hotels():
    a = answer(*my_payee("technical_advice", place_of_performance="mixed", in_country_share="0.4",
                         hotel_reimbursement="200.00"))
    assert withheld(a) == [(Decimal(10), "WH-2", Decimal("1200.00"))]      # (3200 - 200) x 40%


def test_wh2_movable_property_rent_wherever_used():
    assert withheld(answer(*my_payee("movable_property_rent"))) == [(Decimal(10), "WH-2", Decimal("3200.00"))]


@pytest.mark.parametrize("nature, facts", [("technical_advice", {"place_of_performance": "outside"}),
                                           ("freight", {})])
def test_wh2_near_miss_services_outside_malaysia_or_freight_alone(nature, facts):
    assert withheld(answer(*my_payee(nature, **facts))) == []


def test_wh2_unknown_place_is_a_hand_over_with_the_tax_set():
    a = answer(*my_payee("technical_advice", place_of_performance=None))
    assert (a.decision, a.tax_treatment) == (HO, "SST_BUYER_ACCOUNTS")


# -- WH-3 contract payments, WH-4 other gains ---------------------------------------------------------------


def test_wh3_contract_payment_with_a_pe_two_withholdings():
    r, c = my_payee("contract_payment")
    supplier_facts(r, pe_in_country=True)
    assert withheld(answer(r, c)) == [(Decimal(10), "WH-3", Decimal("3200.00")), (Decimal(3), "WH-3", Decimal("3200.00"))]


def test_wh3_near_miss_unknown_pe_is_a_hand_over():
    r, c = my_payee("contract_payment")
    assert answer(r, c).decision is HO


@pytest.mark.parametrize("nature, rate", [("other_gain", "10"), ("public_entertainer", "15")])
def test_wh4_other_gains_and_entertainers(nature, rate):
    assert withheld(answer(*my_payee(nature))) == [(Decimal(rate), "WH-4", Decimal("3200.00"))]


def test_wh4_near_miss_resident_entertainer():
    assert withheld(answer(*one_line(payment_nature="public_entertainer"))) == []


# -- WH-5 Singapore -----------------------------------------------------------------------------------------------


def sg_payee(nature, country="MY", certificate=False, branch=False, **facts):
    r, c = sg_one_line("it_services", rate="0", supplier_country=country, payment_nature=nature, **facts)
    r["suppliers"][0]["tax_registrations"] = []
    c["invoice"]["einvoice"]["supplier_gst_no"] = None
    sg_supplier_facts(r, has_branch_receiving=branch)
    if certificate:
        cert(r, country)
    return r, c


@pytest.mark.parametrize("nature, certificate, facts, rate", [
    ("interest", False, {}, "15"),
    ("royalty", True, {}, "8"),                                                 # Malaysia royalties: confirmed 8%
    ("technical_or_management_fee", False, {"place_of_performance": "in_country"}, "17"),
    ("technical_or_management_fee", True, {"place_of_performance": "in_country"}, "5"),  # confirmed article 13
    ("director_fee", False, {}, "24"),
    ("professional_fee", False, {}, "15"),
])
def test_wh5_withholding_rates(nature, certificate, facts, rate):
    a = answer(*sg_payee(nature, certificate=certificate, **facts))
    assert withheld(a) == [(Decimal(rate), "WH-5", Decimal("1500.00"))]


@pytest.mark.parametrize("nature, kw", [
    ("technical_or_management_fee", {"place_of_performance": "outside"}),
    ("electronic_service", {}), ("ship_charter", {}), ("copyrighted_article", {}),
    ("interest", {"branch": True}),
])
def test_wh5_near_miss_not_subject(nature, kw):
    assert withheld(answer(*sg_payee(nature, **kw))) == []


@pytest.mark.parametrize("nature, kw", [
    ("interest", {"certificate": True}),                                         # Malaysia interest row needs review
    ("technical_or_management_fee", {"certificate": True, "country": "US", "place_of_performance": "in_country"}),
    ("interest", {"branch": None}),
])
def test_wh5_unconfirmed_treaty_row_or_unknown_branch_is_a_hand_over(nature, kw):
    a = answer(*sg_payee(nature, **kw))
    assert (a.decision, a.tax_treatment) == (HO, "NO_GST")


def test_wh5_work_partly_in_singapore_withholds_on_the_singapore_part():
    a = answer(*sg_payee("technical_or_management_fee", place_of_performance="mixed",
                         value_performed_in_singapore="600.00"))
    assert withheld(a) == [(Decimal(17), "WH-5", Decimal("600.00"))]


def test_wh5_near_miss_work_partly_in_singapore_without_the_split_is_a_hand_over():
    a = answer(*sg_payee("technical_or_management_fee", place_of_performance="mixed"))
    assert (a.decision, a.tax_treatment) == (HO, "NO_GST")



def test_wh2_rent_of_movable_property_with_a_certificate_is_a_hand_over():
    # LHDN note (v): many treaties put equipment rental inside royalties (e.g. Singapore 8%); not read yet.
    a = answer(*my_payee("movable_property_rent", certificate=True))
    assert (a.decision, a.tax_treatment) == (HO, "SST_BUYER_ACCOUNTS")


def test_wh3_contract_payment_without_a_pe_falls_back_to_wh2():
    r, c = my_payee("contract_payment", place_of_performance="in_country")
    supplier_facts(r, pe_in_country=False)
    assert withheld(answer(r, c)) == [(Decimal(10), "WH-2", Decimal("3200.00"))]


def test_wh3_near_miss_contract_payment_without_a_pe_for_work_outside_malaysia():
    r, c = my_payee("contract_payment", place_of_performance="outside")
    supplier_facts(r, pe_in_country=False)
    assert withheld(answer(r, c)) == []
