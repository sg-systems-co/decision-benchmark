"""Ministerial exemptions: MS-10, P-1 to P-14, P-16 to P-20, and the P-21 guard (A12 build PR 2 commit 10).
P-15 stays pending (no line fact identifies a health-examination management service)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_exemptions import imported

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
EXEMPT, CORRECT = (RCI, "SST_SHOULD_BE_EXEMPT"), (OK, "SST_CORRECT")


def fin(charge, rate="8", day=None, **facts):
    return one_line(rate=rate, day=day, service_item="H3", financial_charge=charge, **facts)


# -- P-1 to P-7: financial services -----------------------------------------------------------------


def test_p1_financial_services_bought_by_a_group_h_provider():
    r, c = fin("fee_or_commission", financial_use="taxable_financial_services")
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == (*EXEMPT, "P-1")


def test_p1_near_miss_other_use():
    r, c = fin("fee_or_commission", financial_use="other")
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == (*CORRECT, "MS-2")


def test_p1_unknown_use_is_a_hand_over():
    r, c = fin("fee_or_commission", financial_use=None)
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == (HO, None, "P-1")


@pytest.mark.parametrize("charge, rule", [
    ("bursa_clearing_trading_fee", "P-2"), ("listing_perusal_fee", "P-2"), ("shariah_structure_fee", "P-3"),
    ("asnb_fund_management", "P-4"), ("government_securities_fee", "P-5"), ("bursa_share_brokerage", "P-7"),
    ("commodity_platform_fee", "P-7"),
])
def test_p2_to_p7_exempt_financial_charges(charge, rule):
    assert result(*fin(charge)) == (*EXEMPT, rule)


def test_p2_to_p7_near_miss_ordinary_fee():
    assert result(*fin("fee_or_commission")) == (*CORRECT, "MS-2")


def test_p6_reinsurance_for_medical_life_or_family_cover():
    assert result(*fin("reinsurance", financial_use="medical_life_family_cover")) == (*EXEMPT, "P-6")
    assert result(*fin("reinsurance", financial_use="other")) == (*CORRECT, "MS-2")


def test_p7_tia_i_account_fees_from_june_2026():
    assert result(*fin("tia_i_account_fee", day="2026-06-02")) == (*EXEMPT, "P-7")
    assert result(*fin("tia_i_account_fee", day="2026-05-20")) == (*CORRECT, "MS-2")


# -- P-8: government ---------------------------------------------------------------------------------


def test_p8_government_supplier_of_new_scope_services():
    r, c = fin("fee_or_commission")
    supplier_facts(r, supplier_kind="federal_state_government")
    assert result(r, c) == (*EXEMPT, "P-8")


def test_p8_near_miss_local_authority_after_september_2025():
    r, c = fin("fee_or_commission", day="2025-10-15")
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == (*CORRECT, "MS-2")


# -- P-9: MRO of aircraft and ships ------------------------------------------------------------------


def mro(day=None, buyer=("aoc_airline",), approvals=("caam_amo",), **facts):
    r, c = one_line("maintenance_repair", rate="8", day=day, mro_aircraft_ship=facts.pop("mro", True), **facts)
    company_facts(r, buyer_kinds=list(buyer))
    supplier_facts(r, approvals=list(approvals))
    return r, c


def test_p9_mro_by_an_approved_amo_for_an_airline():
    assert result(*mro()) == (*EXEMPT, "P-9")
    assert result(*mro(approvals=("dgta_amo",), day="2026-10-01")) == (*EXEMPT, "P-9")


@pytest.mark.parametrize("kw", [
    {"buyer": ("foreign_company",), "day": "2025-08-10"},   # foreign companies only from 1 Sep 2025
    {"approvals": ("dgta_amo",), "day": "2026-09-01"},       # DGTA AMOs only from 22 Sep 2026
    {"day": "2028-01-10"},                                  # until 31 Dec 2027
    {"approvals": ()},
])
def test_p9_near_miss_condition_fails(kw):
    assert result(*mro(**kw)) == (*CORRECT, "MS-2")


def test_p9_unknown_mro_is_a_hand_over():
    assert result(*mro(mro=None)) == (HO, None, "P-9")


# -- P-10, P-11: building charges ------------------------------------------------------------------


def test_p10_non_residential_maintenance_charges_by_a_jmb():
    r, c = one_line("maintenance_repair", rate="8", day="2026-08-01", building_charge="maintenance", residential=False)
    supplier_facts(r, supplier_kind="developer_jmb_mc")
    assert result(r, c) == (*EXEMPT, "P-10")


@pytest.mark.parametrize("day, kind", [("2026-06-20", "developer_jmb_mc"), ("2026-08-01", "company")])
def test_p10_near_miss_before_july_2026_or_not_a_jmb(day, kind):
    r, c = one_line("maintenance_repair", rate="8", day=day, building_charge="maintenance", residential=False)
    supplier_facts(r, supplier_kind=kind)
    assert result(r, c) == (*CORRECT, "MS-2")


def test_p11_residential_sinking_fund_and_warranty():
    for charge in ("sinking_fund", "warranty_repair"):
        r, c = one_line("maintenance_repair", rate="8", building_charge=charge, residential=True)
        assert result(r, c) == (*EXEMPT, "P-11")


def test_p11_near_miss_non_residential_warranty_repair():
    r, c = one_line("maintenance_repair", rate="8", building_charge="warranty_repair", residential=False)
    assert result(r, c) == (*CORRECT, "MS-2")


# -- P-12 to P-14: private healthcare ------------------------------------------------------------------


def care(**facts):
    return one_line(rate="6", service_item="I14", **({"patient_category": "non_citizen"} | facts))


def test_p12_itemised_consultation_fee_is_exempt():
    assert result(*care(itemised_consultation_fee=True)) == (*EXEMPT, "P-12")


def test_p12_near_miss_not_itemised_the_whole_invoice_is_taxed():
    assert result(*care(itemised_consultation_fee=False)) == (*CORRECT, "P-12")


@pytest.mark.parametrize("category", ["foreign_worker_screening", "diplomat_with_mofa_letter",
                                      "newborn_with_citizen_parent"])
def test_p13_screening_diplomats_and_newborns(category):
    assert result(*care(patient_category=category)) == (*EXEMPT, "P-13")


def test_p13_near_miss_non_citizen_patient():
    assert result(*care()) == (*CORRECT, "MS-2")


def test_p14_referral_not_walked_in_is_not_taxed():
    assert result(*care(referral_walk_in=False)) == (*EXEMPT, "P-14")


def test_p14_near_miss_walk_in_or_medical_aids_are_taxed():
    assert result(*care(referral_walk_in=True)) == (*CORRECT, "P-14")
    assert result(*care(medical_aid=True)) == (*CORRECT, "P-14")
    assert result(*care(medical_aid=True, patient_category="citizen")) == (*EXEMPT, "MS-4")


# -- P-16, P-17: education and training ----------------------------------------------------------------


@pytest.mark.parametrize("facts", [{"education_fee_item": "books"}, {"fully_sponsored": True},
                                   {"student_category": "diplomat_child"}])
def test_p16_education_fee_items_sponsored_and_diplomats(facts):
    assert result(*one_line(rate="6", service_item="M", **facts)) == (*EXEMPT, "P-16")


def test_p16_near_miss_tuition_for_a_non_citizen():
    r, c = one_line(rate="6", service_item="M", education_fee_item="tuition", student_category="non_citizen")
    assert result(r, c) == (*CORRECT, "MS-2")


def test_p17_training_for_oku_holders_by_a_recognised_centre():
    r, c = one_line(rate="6", service_item="M", oku_holder=True)
    supplier_facts(r, recognised_training_centre=True)
    assert result(r, c) == (*EXEMPT, "P-17")


def test_p17_near_miss_centre_not_recognised():
    r, c = one_line(rate="6", service_item="M", oku_holder=True, student_category="non_citizen")
    assert result(r, c) == (*CORRECT, "MS-2")


# -- P-18, P-19: logistics and digital content ----------------------------------------------------------


@pytest.mark.parametrize("carriage", ["door_to_door_international", "ocean_peninsula_east_malaysia"])
def test_p18_international_door_to_door_and_east_malaysia_freight(carriage):
    assert result(*one_line("logistics_haulage", rate="6", carriage=carriage)) == (*EXEMPT, "P-18")


def test_p18_near_miss_domestic_carriage():
    assert result(*one_line("logistics_haulage", rate="6", carriage="domestic")) == (*CORRECT, "MS-2")


def test_p19_distance_learning_and_e_newspapers_are_not_digital_services():
    for kind in ("online_distance_learning", "e_newspaper_journal_periodical"):
        assert result(*one_line(rate="8", service_item="G(l)", digital_content_type=kind)) == (*EXEMPT, "P-19")


def test_p19_near_miss_other_digital_content():
    assert result(*one_line(rate="8", service_item="G(l)", digital_content_type="other")) == (*CORRECT, "MS-2")


# -- P-20: expired exemptions kept as dated rules ------------------------------------------------------


def test_p20_labuan_imported_services_to_2021():
    r, c = imported(day="2021-11-10")
    company_facts(r, zone="labuan")
    assert result(r, c) == (OK, "NO_SST", "P-20")


def test_p20_near_miss_labuan_imported_services_from_2022():
    r, c = imported(day="2022-01-10")
    company_facts(r, zone="labuan")
    assert result(r, c) == (OK, "SST_BUYER_ACCOUNTS", "MS-8")


# -- MS-10 and P-21 ------------------------------------------------------------------------------------


def test_ms10_a_policy_exemption_with_tax_charged_is_should_be_exempt():
    a = result(*fin("asnb_fund_management"))
    assert a == (*EXEMPT, "P-4")


def test_ms10_near_miss_a_policy_exemption_without_tax_is_no_sst():
    assert result(*fin("asnb_fund_management", rate="0")) == (OK, "NO_SST", "P-4")


def test_p21_guard_domestic_electricity_is_not_a_company_purchase_rule():
    # P-21 is not an engine rule: an electricity line is treated as any line outside the First Schedule.
    assert result(*one_line("utilities_electricity", rate="8", tax_type="02")) == (*EXEMPT, "MS-1")
    assert result(*one_line("utilities_electricity", rate="0")) == (OK, "NO_SST", "MS-1")
