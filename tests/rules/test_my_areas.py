"""Designated and special areas: MS-7 (service tax) and MG-5 (sales tax), rule sheet v0.10 as rewritten 18 Nov 2026
(A12 build PR 4). One test or more per numbered step of MS-7 and MG-5, per row of the P.U. (A) 212/2018 table, per
goods list, and both sides of every date boundary."""

from types import SimpleNamespace

import pytest

from decision_benchmark.task_sets.ap_invoices.countries import pack
from decision_benchmark.task_sets.ap_invoices.countries.my.rules.areas import item_applies, kind
from decision_benchmark.task_sets.ap_invoices.models import CompanyRecords
from decision_benchmark.task_sets.ap_invoices.models import Decision as D
from decision_benchmark.task_sets.ap_invoices.rules import build_case_view

import datetime as dt

from .factory import CATALOG, wrap
from .my_cases import company_facts, one_line, result, supplier_facts

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
EXEMPT, TAXED = (RCI, "SST_SHOULD_BE_EXEMPT", "MS-7"), (OK, "SST_CORRECT", "MS-2")


def zones(r, supplier=None, company=None):
    if supplier:
        supplier_facts(r, zone=supplier)
    if company:
        company_facts(r, zone=company)


def svc(category="it_services", rate="8", day=None, supplier=None, company=None, licences=None, **facts):
    r, c = one_line(category, rate=rate, day=day, **facts)
    zones(r, supplier, company)
    if licences is not None:
        supplier_facts(r, area_licences=list(licences))
    return r, c


def first_line(r, c):
    """The engine's own line result (with open_question, which the answer key doesn't carry)."""
    view = build_case_view(CompanyRecords.model_validate(r), wrap(c))
    return pack("MY").assess_tax(view, CATALOG).lines[0]


# == MS-7 ====================================================================================================


def test_ms7_step1_pca_to_pca_does_not_apply():
    assert result(*svc()) == TAXED


def test_ms7_step2_pca_to_an_area_is_taxed():
    # Formerly UnsupportedCase: a principal customs area supplier charges tax on services to a DA (s50) or SA (s55).
    assert result(*svc(company="labuan")) == TAXED
    assert result(*svc(company="free_zone")) == TAXED


@pytest.mark.parametrize("day, expected", [
    ("2021-04-30", TAXED), ("2021-05-03", EXEMPT),             # Service Tax Policy 1/2021 from 1 May 2021
    ("2022-08-12", EXEMPT), ("2022-08-15", TAXED),             # refund route from 15 Aug 2022 (Policy 2/2022)
])
def test_ms7_step2_jda_operator_window(day, expected):
    rate = "6" if day < "2024-03-01" else "8"
    r, c = svc(rate=rate, day=day, company="jda")
    company_facts(r, buyer_kinds=["jda_operator"])
    assert result(r, c) == ((expected[0], expected[1], expected[2]) if expected == EXEMPT else (OK, "SST_CORRECT", "MS-2"))


def test_ms7_step2_near_miss_jda_buyer_not_an_operator():
    assert result(*svc(rate="6", day="2021-06-01", company="jda")) == TAXED


def test_ms7_step3_area_to_pca_is_taxed():
    assert result(*svc(supplier="labuan")) == TAXED
    assert result(*svc(supplier="licensed_manufacturing_warehouse")) == TAXED


def test_ms7_step4_between_areas_not_taxed():
    assert result(*svc(supplier="labuan", company="langkawi")) == EXEMPT
    assert result(*svc(rate="0", supplier="labuan", company="free_zone")) == (OK, "NO_SST", "MS-7")


def test_ms7_step4_pulau_1_is_taxed_inside_and_between_areas():
    # P.U. (A) 370/2024 para 2, from 1 Dec 2024.
    assert result(*svc(supplier="pulau_1", company="labuan", day="2024-12-02")) == TAXED
    assert result(*svc(supplier="pulau_1", company="pulau_1", day="2024-12-02")) == TAXED


def test_ms7_pulau_1_is_an_area_from_1_december_2024():
    assert kind("pulau_1", dt.date(2024, 11, 30)) == "pca" and kind("pulau_1", dt.date(2024, 12, 1)) == "da"


def test_ms7_pangkor_is_an_area_from_1_january_2020():
    assert result(*svc(rate="6", day="2019-12-30", supplier="pangkor", company="labuan")) == TAXED
    assert result(*svc(rate="6", day="2020-01-02", supplier="pangkor", company="labuan")) == EXEMPT


def test_ms7_recipient_zone_names_another_establishment():
    assert result(*svc(company="labuan", recipient_zone="pca")) == TAXED
    assert result(*svc(supplier="labuan", recipient_zone="langkawi")) == EXEMPT
    assert result(*svc(supplier="labuan", recipient_zone=None)) == (HO, None, "MS-7")


def test_ms7_unknown_party_zone_is_a_hand_over():
    r, c = svc(company="labuan")
    supplier_facts(r, zone_known=False)
    assert result(r, c) == (HO, None, "MS-7")


def test_ms7_period_spanning_an_order_date_without_a_split():
    r, c = svc("test_hotel", rate="6", day="2018-09-12", supplier="langkawi", service_period_start="2018-09-01",
               service_period_end="2018-09-10")
    assert result(r, c) == (HO, None, "MS-7")


# -- Site rule ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("company", [None, "labuan", "free_zone"])
def test_ms7_site_rule_langkawi_hotel_not_taxed_whatever_the_buyer_zone(company):
    assert result(*svc("test_hotel", supplier="langkawi", company=company)) == EXEMPT


def test_ms7_site_rule_accommodation_in_a_free_zone_is_taxed():
    assert result(*svc("test_hotel", supplier="free_zone")) == TAXED


def test_ms7_site_rule_named_site_overrides_the_supplier_zone():
    assert result(*svc("test_hotel", service_site_zone="langkawi")) == EXEMPT
    assert result(*svc("test_hotel", service_site_zone=None)) == (HO, None, "MS-7")


# -- The P.U. (A) 212/2018 table -------------------------------------------------------------------------------


def test_ms7_item1_air_transport_between_areas_by_a_licensed_carrier():
    flight = dict(supplier="langkawi", company="labuan")
    assert result(*svc("test_domestic_flight", licences=["mavcom_air_service"], **flight)) == TAXED
    assert result(*svc("test_domestic_flight", licences=[], **flight)) == EXEMPT


def test_ms7_item1_near_miss_within_one_area_and_unknown_licence():
    assert result(*svc("test_domestic_flight", supplier="langkawi", company="langkawi",
                       licences=["mavcom_air_service"])) == EXEMPT
    r, c = svc("test_domestic_flight", supplier="langkawi", company="labuan")
    supplier_facts(r, area_licences_known=False)
    assert result(r, c) == (HO, None, "MS-7")


def test_ms7_item2_telecoms_between_areas_by_a_licensed_provider():
    assert result(*svc("telecoms", rate="6", supplier="labuan", company="tioman", licences=["cma_telecoms"])) == TAXED
    assert result(*svc("telecoms", rate="6", supplier="labuan", company="tioman")) == EXEMPT


@pytest.mark.parametrize("day, rate, expected", [("2018-09-05", "6", TAXED), ("2018-09-06", "6", EXEMPT)])
def test_ms7_item3_in_special_areas_from_6_september_2018(day, rate, expected):
    assert result(*svc("test_hotel", rate=rate, day=day, supplier="langkawi")) == expected


def hotel(day, supplier_kind=None, **facts):
    rate = "6" if day < "2024-03-01" else "8"
    r, c = svc("test_hotel", rate=rate, day=day, supplier="free_zone", **facts)
    if supplier_kind:
        supplier_facts(r, supplier_kind=supplier_kind)
    return r, c


HO7 = (HO, None, "MS-7")
BEFORE, FROM = "2019-12-30", "2020-01-02"


@pytest.mark.parametrize("day", [BEFORE, FROM])
def test_ms7_item3_local_authority_premises_excluded_on_every_date(day):
    assert result(*hotel(day, "local_authority")) == EXEMPT


@pytest.mark.parametrize("supplier_kind", ["statutory_body", "private_hei"])
def test_ms7_item3_statutory_body_and_private_hei_premises(supplier_kind):
    assert result(*hotel(FROM, supplier_kind)) == EXEMPT                                    # from 1 Jan 2020: excluded
    assert result(*hotel(BEFORE, supplier_kind, educational_training_welfare_purpose=True)) == EXEMPT
    assert result(*hotel(BEFORE, supplier_kind, educational_training_welfare_purpose=False)) == TAXED
    assert result(*hotel(BEFORE, supplier_kind)) == HO7                                     # purpose not shown


def test_ms7_item3_federal_or_state_government_premises():
    assert result(*hotel(FROM, "federal_state_government")) == EXEMPT                       # State added from 1 Jan 2020
    assert result(*hotel(BEFORE, "federal_state_government", educational_training_welfare_purpose=False)) == TAXED
    # Before 2020, with the purpose: excluded for Federal, not for State; the master doesn't say which.
    assert result(*hotel(BEFORE, "federal_state_government", educational_training_welfare_purpose=True)) == HO7


@pytest.mark.parametrize("day", [BEFORE, FROM])
def test_ms7_item3_religious_or_welfare_body_premises(day):
    assert result(*hotel(day, "religious_welfare_body", non_commercial_religious_welfare=True)) == EXEMPT
    assert result(*hotel(day, "religious_welfare_body", non_commercial_religious_welfare=False)) == TAXED
    assert result(*hotel(day, "religious_welfare_body")) == HO7


def test_ms7_item3_employer_staff_accommodation_from_1_january_2020():
    assert result(*hotel(FROM, employer_staff_accommodation=True)) == EXEMPT
    assert result(*hotel(BEFORE, employer_staff_accommodation=True)) == TAXED
    assert result(*hotel(FROM, employer_staff_accommodation=None)) == HO7


def test_ms7_item3_wording_restated_25_september_2026_no_change():
    for day in ("2026-09-24", "2026-09-25"):
        assert result(*svc("test_hotel", day=day, supplier="free_zone")) == TAXED


def test_ms7_item4_canteens_of_educational_or_religious_institutions_excluded():
    for kind_ in ("educational_institution", "religious_body"):
        assert result(*svc("test_catering", rate="6", supplier="free_zone", canteen_kind=kind_)) == EXEMPT
    assert result(*svc("test_catering", rate="6", supplier="free_zone", canteen_kind="none")) == TAXED
    assert result(*svc("test_catering", rate="6", supplier="free_zone", canteen_kind=None)) == HO7


def test_ms7_item4_food_and_beverages_in_special_areas():
    assert result(*svc("test_catering", rate="6", supplier="free_zone")) == TAXED
    assert result(*svc("test_catering", rate="6", supplier="labuan")) == EXEMPT
    assert result(*svc("test_catering", rate="6", day="2018-09-05", supplier="labuan")) == TAXED


@pytest.mark.parametrize("day, expected", [("2025-05-29", EXEMPT), ("2025-05-30", TAXED)])
def test_ms7_item5_customs_clearance_in_designated_areas_from_30_may_2025(day, expected):
    # transshipment: item 7 does not reach the line, so only item 5 decides.
    r, c = svc("test_customs_agent", rate="6", day=day, supplier="labuan", licences=["customs_agent_s90"],
               international_leg="transshipment")
    assert result(r, c) == ((RCI, "SST_SHOULD_BE_EXEMPT", "MS-7") if expected == EXEMPT else (OK, "SST_CORRECT", "MS-2"))


def test_ms7_item5_customs_clearance_in_special_areas_needs_the_approval():
    assert result(*svc("test_customs_agent", rate="6", supplier="free_zone", licences=["customs_agent_s90"])) == TAXED
    assert result(*svc("test_customs_agent", rate="6", supplier="free_zone", licences=[])) == EXEMPT


def test_ms7_item6_entertainment_premises_food_from_1_september_2019():
    ctx = SimpleNamespace(sf=SimpleNamespace(area_licences_known=True, area_licences=["entertainment_premises"]))
    sa = ("free_zone", "free_zone", "sa", "sa")
    assert not item_applies(ctx, 6, *sa, dt.date(2019, 8, 31))
    assert item_applies(ctx, 6, *sa, dt.date(2019, 9, 1))


@pytest.mark.parametrize("day, expected", [("2024-02-29", EXEMPT), ("2024-03-01", TAXED), ("2025-05-29", TAXED),
                                           ("2025-05-30", EXEMPT)])
def test_ms7_item7_logistics_1_march_2024_to_29_may_2025(day, expected):
    rate = "6"
    r, c = svc("logistics_haulage", rate=rate, day=day, supplier="labuan", company="langkawi")
    out = result(r, c)
    assert out == ((RCI, "SST_SHOULD_BE_EXEMPT", "MS-7") if expected == EXEMPT else (OK, "SST_CORRECT", "MS-2"))


def test_ms7_item7_international_legs_are_excepted():
    r, c = svc("logistics_haulage", rate="6", day="2024-06-03", supplier="labuan", company="langkawi",
               international_leg="outside_to_outside")
    assert result(r, c) == EXEMPT
    r, c = svc("logistics_haulage", rate="6", day="2024-06-03", supplier="labuan", company="langkawi",
               international_leg=None)
    assert result(r, c) == (HO, None, "MS-7")


def test_ms7_q_a5_petroleum_supply_base_where_it_decides():
    assert result(*svc(supplier="petroleum_supply_base", company="labuan")) == (HO, None, "MS-7")
    assert result(*svc(supplier="petroleum_supply_base")) == TAXED      # the same answer either way


# == MG-5 ====================================================================================================


def goods(category="test_raw_resin", rate="10", day=None, supplier=None, company=None, **facts):
    r, c = one_line(category, rate=rate, price="12.40", qty=100, day=day, **facts)
    zones(r, supplier, company)
    return r, c


GEXEMPT, GTAXED, GNONE = (RCI, "SST_SHOULD_BE_EXEMPT", "MG-5"), (OK, "SST_CORRECT", "MG-2"), (OK, "NO_SST", "MG-5")


def test_mg5_step1_pca_to_pca_does_not_apply():
    assert result(*goods()) == GTAXED


def test_mg5_step2_pca_manufacturer_into_an_area_no_sales_tax():
    assert result(*goods(company="labuan")) == GEXEMPT
    assert result(*goods(rate="0", company="langkawi")) == GNONE
    assert result(*goods(company="jda")) == GEXEMPT


def test_mg5_step2_lmw_buyer_of_raw_materials_from_a_pca_manufacturer():
    assert result(*goods(rate="0", company="licensed_manufacturing_warehouse")) == GNONE


def test_mg5_step2_lmw_buyer_of_office_furniture_q_a2():
    assert result(*goods("test_office_furniture", rate="0", company="licensed_manufacturing_warehouse")) == (HO, None, "MG-5")


@pytest.mark.parametrize("day, expected", [("2018-12-31", GNONE), ("2019-01-02", (HO, None, "MG-5"))])
def test_mg5_step2_schedule_a_reaches_lmws_from_1_january_2019(day, expected):
    assert result(*goods("test_office_furniture", rate="0", day=day, company="licensed_manufacturing_warehouse")) == expected


def test_mg5_step2_goods_not_used_directly_in_the_approved_activity_q_a2():
    assert result(*goods(rate="0", company="free_zone", used_directly_in_approved_activity=False)) == (HO, None, "MG-5")
    assert result(*goods(rate="0", company="free_zone", used_directly_in_approved_activity=True)) == GNONE


def test_mg5_step2_tasik_kenyir_alcohol_and_tobacco():
    r, c = goods("test_wine", rate="0", company="free_zone")
    company_facts(r, tasik_kenyir=True)
    assert result(r, c) == (HO, None, "MG-5")
    assert result(*goods("test_wine", rate="0", company="free_zone")) == GNONE


@pytest.mark.parametrize("category, day, expected", [
    ("test_cigarettes", "2021-09-02", GNONE), ("test_cigarettes", "2021-09-06", (HO, None, "MG-5")),
    ("test_e_liquid", "2023-03-31", GNONE), ("test_e_liquid", "2023-04-03", (HO, None, "MG-5")),
])
def test_mg5_sa_order_tobacco_into_free_zones(category, day, expected):
    assert result(*goods(category, rate="0", day=day, company="free_zone")) == expected


@pytest.mark.parametrize("category, day, flagged", [
    ("test_cigarettes", "2019-03-26", True), ("test_cigarettes", "2019-03-27", False),   # deleted by 92/2019
    ("test_cigarettes", "2020-12-31", False), ("test_cigarettes", "2021-01-04", True),   # 420/2020
    ("test_petroleum", "2019-12-31", False), ("test_petroleum", "2020-01-02", True),     # 391/2019
    ("test_e_liquid", "2023-03-31", False), ("test_e_liquid", "2023-04-03", True),       # 94/2023
    ("test_marble", "2026-01-02", True),
])
def test_mg5_q_a1_da_listed_goods_carry_no_tax_and_the_open_question(category, day, flagged):
    zone = "langkawi"
    r, c = goods(category, rate="0", day=day, company=zone)
    line = first_line(r, c)
    assert (line.treatment, line.basis) == ("NO_SST", "MG-5")
    assert line.open_question == ("Q-A1" if flagged else None)


def test_mg5_pangkor_motor_vehicles_from_1_january_2020():
    assert first_line(*goods("test_motor_vehicle", rate="0", day="2020-01-02", company="pangkor")).open_question == "Q-A1"
    assert first_line(*goods("test_motor_vehicle", rate="0", day="2019-12-30", company="pangkor")).basis == "MS-9"


def test_mg5_step3_from_a_designated_area():
    assert result(*goods(supplier="labuan")) == GEXEMPT
    assert result(*goods(supplier="labuan", company="free_zone")) == GEXEMPT
    assert result(*goods("test_petroleum", supplier="labuan")) == GTAXED       # petroleum: ordinary MG rules


def test_mg5_step4_from_a_special_area():
    assert result(*goods(rate="0", supplier="licensed_manufacturing_warehouse")) == GNONE
    assert result(*goods(supplier="licensed_manufacturing_warehouse")) == (HO, None, "MG-5")    # Q-A3
    assert result(*goods(supplier="jda")) == GEXEMPT
    assert result(*goods(supplier="free_zone", company="labuan")) == GEXEMPT


@pytest.mark.parametrize("category, day, facts, expected", [
    ("test_raw_resin", "2026-01-02", {}, GEXEMPT),
    ("test_marble", "2025-12-31", {}, GEXEMPT),
    ("test_marble", "2026-01-02", {}, (HO, None, "MG-5")),
    ("test_motor_vehicle", "2026-01-02", {"tariff_code": "8703.23.10 00", "motor_vehicle_value": "400000.00",
                                          "motor_vehicle_value_basis": "sales_price"}, (HO, None, "MG-5")),
    ("test_motor_vehicle", "2026-01-02", {"tariff_code": "8703.23.10 00", "motor_vehicle_value": "200000.00",
                                          "motor_vehicle_value_basis": "sales_price"}, GEXEMPT),
])
def test_mg5_step5_between_designated_areas(category, day, facts, expected):
    r, c = goods(category, day=day, supplier="labuan", company="langkawi", **facts)
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2024-11-29", GTAXED), ("2024-12-02", (HO, None, "MG-5"))])
def test_mg5_step6_goods_into_pulau_1_q_a4(day, expected):
    assert result(*goods(day=day, company="pulau_1")) == expected


def test_mg5_step6_goods_made_and_delivered_in_pulau_1():
    assert result(*goods(day="2024-12-02", supplier="pulau_1", company="pulau_1")) == GTAXED
    assert result(*goods("test_wine", day="2024-12-02", supplier="pulau_1", company="pulau_1")) == (HO, None, "MG-5")


@pytest.mark.parametrize("day, expected", [("2019-12-31", GTAXED), ("2020-01-02", GEXEMPT)])
def test_mg5_petroleum_supply_base_is_a_special_area_from_1_january_2020(day, expected):
    assert result(*goods(day=day, company="petroleum_supply_base")) == expected


def test_mg5_delivery_zone_overrides_the_company_zone():
    assert result(*goods(delivery_zone="labuan")) == GEXEMPT
    assert result(*goods(company="labuan", delivery_zone="pca")) == GTAXED
    assert result(*goods(delivery_zone=None)) == (HO, None, "MG-5")


def test_mg5_unknown_zone_is_a_hand_over():
    r, c = goods()
    company_facts(r, zone="labuan", zone_known=False)
    assert result(r, c) == (HO, None, "MG-5")
