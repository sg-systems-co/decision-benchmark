"""Dated rule elements of MS-7 to MS-10 (rule sheet v0.10 lines 187-281): both sides of every date boundary that the
existing tests (test_my_areas.py, test_my_policies.py, test_my_exemptions.py) don't already cover on the adjacent
days. Each test asserts what the sheet says; the basis is checked so a test can't pass for another rule's reason."""

import datetime as dt
from types import SimpleNamespace

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.my.rules.context import LineCtx
from decision_benchmark.task_sets.ap_invoices.countries.my.rules.scope import NEW_SCOPE_FROM
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import CATALOG
from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_exemptions import imported
from .test_my_policies import fin, mro

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
EXEMPT7, TAXED = (RCI, "SST_SHOULD_BE_EXEMPT", "MS-7"), (OK, "SST_CORRECT", "MS-2")
HO7 = (HO, None, "MS-7")


def svc(category="it_services", rate=None, day=None, supplier=None, company=None, licences=None, **facts):
    rate = rate or ("6" if day is not None and day < "2024-03-01" else "8")
    r, c = one_line(category, rate=rate, day=day, **facts)
    if supplier:
        supplier_facts(r, zone=supplier)
    if company:
        company_facts(r, zone=company)
    if licences is not None:
        supplier_facts(r, area_licences=list(licences))
    return r, c


# == MS-7 areas ===============================================================================================


@pytest.mark.parametrize("day, expected", [("2019-12-31", TAXED), ("2020-01-01", EXEMPT7)])
def test_ms7_pangkor_designated_from_1_jan_2020_adjacent_days(day, expected):
    # Before: Pangkor is principal customs area, so Pangkor -> Labuan is step 2 (taxed); from: step 4 (not taxed).
    assert result(*svc(day=day, supplier="pangkor", company="labuan")) == expected


def test_ms7_pangkor_period_spanning_1_jan_2020_without_a_split():
    r, c = svc(day="2020-01-10", supplier="pangkor", company="labuan", service_period_start="2019-12-15",
               service_period_end="2020-01-09")
    assert result(r, c) == HO7


ROUTES_PULAU_1 = [("pulau_1", "labuan"), ("labuan", "pulau_1"), ("pulau_1", "pulau_1"), ("pulau_1", "free_zone"),
                  ("pulau_1", None)]


@pytest.mark.parametrize("day", ["2024-11-30", "2024-12-01"])
@pytest.mark.parametrize("supplier, company", ROUTES_PULAU_1)
def test_ms7_pulau_1_from_1_dec_2024_taxed_on_both_sides(day, supplier, company):
    # Before 1 Dec 2024 Pulau 1 is principal customs area (steps 1-3: taxed); from 1 Dec 2024 it is a DA and
    # P.U. (A) 370/2024 para 2 taxes every First Schedule service within it and between it and another area.
    assert result(*svc(day=day, supplier=supplier, company=company)) == TAXED


@pytest.mark.parametrize("day", ["2024-11-30", "2024-12-01"])
def test_ms7_pulau_1_site_bound_hotel_and_unlicensed_flight_taxed_on_both_sides(day):
    assert result(*svc("test_hotel", day=day, supplier="pulau_1")) == TAXED
    # Item 1 excludes Pulau 1 from 1 Dec 2024 (371/2024); the Pulau 1 order taxes the flight instead.
    assert result(*svc("test_domestic_flight", day=day, supplier="pulau_1", company="langkawi", licences=[])) == TAXED


@pytest.mark.parametrize("day", ["2025-05-29", "2025-05-30"])
def test_ms7_item5_pulau_1_exclusion_from_30_may_2025_pulau_1_order_still_taxes(day):
    r, c = svc("test_customs_agent", rate="6", day=day, supplier="pulau_1", licences=["customs_agent_s90"],
               international_leg="transshipment")
    assert result(r, c) == TAXED


@pytest.mark.parametrize("day", ["2019-12-31", "2020-01-01"])
def test_ms7_q_a5_supply_base_service_tax_has_no_1_jan_2020_date(day):
    # The 1 Jan 2020 date makes a supply base a special area for sales tax only; for service tax it stays Q-A5.
    assert result(*svc(day=day, supplier="petroleum_supply_base", company="labuan")) == HO7


@pytest.mark.parametrize("day, expected", [("2021-04-30", TAXED), ("2021-05-01", EXEMPT7), ("2022-08-14", EXEMPT7),
                                           ("2022-08-15", TAXED)])
def test_ms7_jda_operator_window_adjacent_days(day, expected):
    # Service Tax Policy 1/2021 from 1 May 2021; refund route (Policy 2/2022, P-20) from 15 Aug 2022.
    r, c = svc(day=day, company="jda")
    company_facts(r, buyer_kinds=["jda_operator"])
    assert result(r, c) == expected


def test_ms7_jda_period_spanning_1_may_2021_without_a_split():
    r, c = svc(day="2021-05-12", company="jda", service_period_start="2021-04-20", service_period_end="2021-05-10")
    company_facts(r, buyer_kinds=["jda_operator"])
    assert result(r, c) == HO7


@pytest.mark.parametrize("day, expected", [("2018-09-05", TAXED), ("2018-09-06", EXEMPT7)])
def test_ms7_item4_food_in_special_areas_only_from_6_sep_2018(day, expected):
    # Labuan is a DA: before 6 Sep 2018 item 4 reached all areas, from then only special areas.
    assert result(*svc("test_catering", rate="6", day=day, supplier="labuan")) == expected


def hotel(day, supplier_kind=None, **facts):
    r, c = svc("test_hotel", day=day, supplier="free_zone", **facts)
    if supplier_kind:
        supplier_facts(r, supplier_kind=supplier_kind)
    return r, c


@pytest.mark.parametrize("day, expected", [("2019-12-31", TAXED), ("2020-01-01", EXEMPT7)])
def test_ms7_item3_exclusions_from_1_jan_2020_adjacent_days(day, expected):
    assert result(*hotel(day, employer_staff_accommodation=True)) == expected
    for kind in ("federal_state_government", "statutory_body", "private_hei"):
        # No educational, training or welfare purpose: excluded only from 1 Jan 2020.
        assert result(*hotel(day, kind, educational_training_welfare_purpose=False)) == expected, kind


@pytest.mark.parametrize("day, expected", [("2019-08-30", EXEMPT7), ("2019-09-02", TAXED)])
def test_ms7_item6_entertainment_premises_food_from_1_sep_2019_full_engine(monkeypatch, day, expected):
    # No catalog category carries item 6; give catering items 4 and 6. A religious-body canteen is excluded from item 4,
    # so only item 6 (night-club or public-house operator, no canteen exclusion, from 1 Sep 2019) can tax the line.
    category = CATALOG.get("test_catering")
    monkeypatch.setitem(category.tax, "MY", category.tax["MY"].model_copy(update={"area_items": [4, 6]}))
    r, c = svc("test_catering", rate="6", day=day, supplier="free_zone", licences=["entertainment_premises"],
               canteen_kind="religious_body")
    assert result(r, c) == expected


# == MS-8 imported services ===================================================================================


@pytest.mark.parametrize("day, expected", [("2025-06-30", (OK, "NO_SST", "MS-1")), ("2025-07-01", (OK, "NO_SST", "MS-8"))])
def test_ms8_stp_1_2025_item6_from_group_h_start(day, expected):
    # Before 1 Jul 2025 Group H is not a taxable service (MS-1); from then STP 1/2025 item 6 exempts the import.
    r, c = imported("it_services", day=day, service_item="H3", financial_charge="fee_or_commission",
                    financial_use="offshore_financial_services")
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2025-06-30", (OK, "NO_SST", "MS-1")),
                                           ("2025-07-01", (OK, "SST_BUYER_ACCOUNTS", "MS-8"))])
def test_ms8_near_miss_imported_financial_service_other_use(day, expected):
    r, c = imported("it_services", day=day, service_item="H3", financial_charge="fee_or_commission",
                    financial_use="other")
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == expected


# == MS-10 Service Tax Policies ===============================================================================


@pytest.mark.parametrize("day, expected", [("2026-05-31", TAXED), ("2026-06-01", (RCI, "SST_SHOULD_BE_EXEMPT", "P-7"))])
def test_p7_tia_i_from_1_jun_2026_adjacent_days(day, expected):
    assert result(*fin("tia_i_account_fee", day=day)) == expected


def _gov(kind, day):
    ctx = SimpleNamespace(sf=SimpleNamespace(supplier_kind=kind), day=dt.date.fromisoformat(day))
    return LineCtx.government_supplier(ctx, "P-8", NEW_SCOPE_FROM)


@pytest.mark.parametrize("kind, day, exempt", [
    ("federal_state_government", "2025-06-30", False), ("federal_state_government", "2025-07-01", True),
    ("local_authority", "2025-06-30", False), ("local_authority", "2025-07-01", True),
    ("local_authority", "2025-09-30", True), ("local_authority", "2025-10-01", False),
])
def test_p8_government_dates_direct(kind, day, exempt):
    # Before 1 Jul 2025 MS-1 answers first in the full engine, so the date check itself is tested here.
    assert _gov(kind, day) is exempt


@pytest.mark.parametrize("kind, day, expected", [
    ("federal_state_government", "2025-06-30", (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")),
    ("federal_state_government", "2025-07-01", (RCI, "SST_SHOULD_BE_EXEMPT", "P-8")),
    ("local_authority", "2025-07-01", (RCI, "SST_SHOULD_BE_EXEMPT", "P-8")),
    ("local_authority", "2025-09-30", (RCI, "SST_SHOULD_BE_EXEMPT", "P-8")),
    ("local_authority", "2025-10-01", TAXED),
])
def test_p8_government_supplier_full_engine(kind, day, expected):
    r, c = fin("fee_or_commission", day=day)
    supplier_facts(r, supplier_kind=kind)
    assert result(r, c) == expected


P9 = (RCI, "SST_SHOULD_BE_EXEMPT", "P-9")


@pytest.mark.parametrize("day, expected", [("2025-08-31", TAXED), ("2025-09-01", P9)])
def test_p9_foreign_company_buyer_from_1_sep_2025(day, expected):
    assert result(*mro(buyer=("foreign_company",), day=day)) == expected


@pytest.mark.parametrize("day, expected", [("2026-09-21", TAXED), ("2026-09-22", P9)])
def test_p9_dgta_amo_from_22_sep_2026(day, expected):
    assert result(*mro(approvals=("dgta_amo",), day=day)) == expected


@pytest.mark.parametrize("day, expected", [("2027-12-31", P9), ("2028-01-01", TAXED)])
def test_p9_until_31_dec_2027(day, expected):
    assert result(*mro(day=day)) == expected


def test_p9_mida_shipyard_from_1_mar_2024():
    r, c = one_line("maintenance_repair", rate="6", day="2024-02-29", mro_aircraft_ship=True)
    company_facts(r, buyer_kinds=["registered_ship_owner"])
    supplier_facts(r, approvals=["mida_shipyard"])
    assert result(r, c)[2] != "P-9"
    assert result(*mro(buyer=("registered_ship_owner",), approvals=("mida_shipyard",), day="2024-03-01")) == P9


@pytest.mark.parametrize("day, expected", [("2026-06-30", TAXED), ("2026-07-01", (RCI, "SST_SHOULD_BE_EXEMPT", "P-10"))])
def test_p10_non_residential_charges_from_1_jul_2026(day, expected):
    r, c = one_line("maintenance_repair", rate="8", day=day, building_charge="maintenance", residential=False)
    supplier_facts(r, supplier_kind="developer_jmb_mc")
    assert result(r, c) == expected


HEALTH_EXAM = {"excluded_management_kind": "health_examination_management"}


@pytest.mark.parametrize("day, expected", [("2026-04-30", (RCI, "SST_SHOULD_BE_EXEMPT", "P-15")),
                                           ("2026-05-01", (OK, "SST_CORRECT", "P-15"))])
def test_p15_health_examination_management_taxable_from_1_may_2026(day, expected):
    assert result(*one_line("management_services", rate="8", day=day, **HEALTH_EXAM)) == expected


P20 = (RCI, "SST_SHOULD_BE_EXEMPT", "P-20")


@pytest.mark.parametrize("provider, day, expected", [
    ("bank", "2025-07-31", P20), ("bank", "2025-08-01", TAXED),
    ("non_bank", "2022-07-31", TAXED), ("non_bank", "2022-08-01", P20),
    ("non_bank", "2025-07-31", P20), ("non_bank", "2025-08-01", TAXED),
])
def test_p20_digital_payment_windows_adjacent_days(provider, day, expected):
    r, c = svc(day=day, service_item="G(l)", digital_payment_provider=provider)
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2021-12-31", (OK, "NO_SST", "P-20")),
                                           ("2022-01-01", (OK, "SST_BUYER_ACCOUNTS", "MS-8"))])
def test_p20_labuan_imported_services_to_31_dec_2021_adjacent_days(day, expected):
    r, c = imported(day=day)
    company_facts(r, zone="labuan")
    assert result(r, c) == expected


# == Transitional new-scope exemptions (sheet line 278; STP 1/2024 para 5) =====================================


@pytest.mark.parametrize("rate", ["6", "8"])
@pytest.mark.parametrize("day", ["2024-02-26", "2024-02-29"])
def test_transitional_new_scope_2024_existing_registrant_window(day, rate):
    decision, treatment, _ = result(*one_line("maintenance_repair", rate=rate, day=day))
    assert (decision, treatment) == (RCI, "SST_SHOULD_BE_EXEMPT")


def test_transitional_new_scope_2024_existing_registrant_taxed_from_1_mar_2024():
    r, c = one_line("maintenance_repair", rate="8", day="2024-03-01")
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == TAXED


@pytest.mark.parametrize("day, before, expected", [
    ("2024-02-25", None, (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")),     # G(n) not taxable before 26 Feb 2024
    ("2024-03-31", False, (RCI, "SST_SHOULD_BE_EXEMPT", "MS-10")),   # newly liable: no tax to 31 Mar 2024
    ("2024-04-01", False, TAXED),
    ("2024-03-15", None, (HO, None, "MS-10")),                        # registration before 26 Feb not shown
])
def test_transitional_new_scope_2024_new_registrant_window(day, before, expected):
    r, c = one_line("maintenance_repair", rate="8", day=day)
    supplier_facts(r, registered_before_2024_02_26=before)
    assert result(r, c) == expected
