"""Group K rental or leasing: K-1 to K-8 (A12 build PR 2 commit 8)."""

import copy

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_exemptions import group

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
RENTAL = {"service_item": "K", "asset_type": "machinery"}


def rental(rate="6", day=None, **facts):
    return one_line(rate=rate, day=day, **(RENTAL | facts))


def msme(r, **over):
    base = {"mypmk_registered_on": "2026-03-01", "declared_sales_band": "below_1m", "year_of_assessment": 2025,
            "paid_up_capital": "1000000.00"}
    company_facts(r, msme=base | over)


def contract(r, **over):
    base = {"contract_id": "K-001", "company_id": "my-c-001", "supplier_id": "S1", "signed_on": "2025-05-20",
            "stamped_on": "2025-06-05", "has_price_review_clause": False, "states_service": True,
            "states_fixed_value": True, "states_period": True, "start": "2025-06-01", "end": "2027-06-30"}
    r["contracts"] = [base | over]


# -- K-1 SME tenants --------------------------------------------------------------------------------


def test_k1_sme_tenant_is_exempt():
    r, c = rental()
    msme(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-1")


def test_k1_registration_by_end_2026_backdates():
    # Registered 1 Nov 2026 (before the processing date): backdates to 1 Jul 2025 for an invoice of Feb 2026.
    r, c = rental(day="2026-02-10")
    msme(r, mypmk_registered_on="2026-11-01")
    c["as_of_date"] = "2026-11-05"
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-1")


def test_k1_registration_after_2026_counts_from_its_date():
    r, c = rental(day="2027-03-01")
    msme(r, mypmk_registered_on="2027-02-01")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-1")
    r, c = rental(day="2027-01-15")
    msme(r, mypmk_registered_on="2027-02-01")
    c["as_of_date"] = "2027-02-05"
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


@pytest.mark.parametrize("over, day, rate", [
    ({"mypmk_registered_on": "2026-11-20"}, None, "6"),          # registered after the processing date (decision 5)
    ({"declared_sales_band": "1m_to_1_5m"}, "2025-12-10", "8"),  # RM1m-1.5m band only from 1 Jan 2026
    ({"declared_sales_band": "above_1_5m"}, None, "6"),
    ({"paid_up_capital": "3000000.00"}, None, "6"),
    ({"group_holding_pct": "25"}, None, "6"),
    ({"mypmk_registered_on": None}, None, "6"),                  # not registered in MyPMK
])
def test_k1_near_miss_condition_fails(over, day, rate):
    r, c = rental(rate=rate, day=day)
    msme(r, **over)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


@pytest.mark.parametrize("over", [{"declared_sales_band": None}, {"paid_up_capital": None},
                                  {"mypmk_status_known": False}])
def test_k1_unknown_msme_fact_is_a_hand_over(over):
    r, c = rental()
    msme(r, **over)
    assert result(r, c) == (HO, None, "K-1")


# -- K-2 new SMEs -------------------------------------------------------------------------------------


def test_k2_new_sme_in_its_first_year_is_exempt():
    r, c = rental()
    msme(r, declared_sales_band="above_1_5m", ssm_registered_on="2026-02-01", mypmk_registered_on="2026-02-15")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-2")


def test_k2_near_miss_after_its_first_year():
    r, c = rental(day="2027-02-15")
    msme(r, declared_sales_band="above_1_5m", ssm_registered_on="2026-02-01", mypmk_registered_on="2026-02-15")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


# -- K-3 aircraft and vessels ----------------------------------------------------------------------


@pytest.mark.parametrize("asset", ["aircraft", "vessel"])
def test_k3_aircraft_and_vessels_are_exempt(asset):
    assert result(*rental(asset_type=asset)) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-3")


@pytest.mark.parametrize("asset", ["drone", "floating_storage"])
def test_k3_near_miss_drones_and_floating_storage(asset):
    assert result(*rental(asset_type=asset)) == (OK, "SST_CORRECT", "MS-2")


# -- K-4 non-reviewable contracts -------------------------------------------------------------------


def test_k4_non_reviewable_contract_is_exempt_to_30_june_2026():
    r, c = rental(day="2026-03-10")
    contract(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-4")


@pytest.mark.parametrize("over, day", [
    ({}, "2026-07-10"),                                   # after 30 Jun 2026: taxable
    ({"stamped_on": "2025-06-20"}, "2026-03-10"),          # stamped after 9 Jun 2025
    ({"has_price_review_clause": True}, "2026-03-10"),
    ({"states_fixed_value": False}, "2026-03-10"),
    ({"end": "2025-06-30"}, "2025-06-25"),                 # does not run past 1 Jul 2025 (and before the window)
])
def test_k4_near_miss_condition_fails(over, day):
    r, c = rental(day=day)
    contract(r, **over)
    assert result(r, c)[1] in ("SST_CORRECT", "SST_SHOULD_BE_EXEMPT") and result(r, c)[2] != "K-4"


def test_k4_unknown_clause_is_a_hand_over():
    r, c = rental(day="2026-03-10")
    contract(r, has_price_review_clause=None)
    assert result(r, c) == (HO, None, "K-4")
    r, c = rental(day="2026-03-10", contract_stamped=None)
    contract(r)
    assert result(r, c) == (HO, None, "K-4")


# -- K-5 government -----------------------------------------------------------------------------------


def test_k5_government_lessor():
    r, c = rental()
    supplier_facts(r, supplier_kind="federal_state_government")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-5")
    r, c = rental(rate="8", day="2025-08-15")
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-5")


def test_k5_near_miss_local_authority_after_september_2025():
    r, c = rental(rate="8", day="2025-10-15")
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


# -- K-6 group relief ----------------------------------------------------------------------------------


def test_k6_rental_between_group_companies_is_exempt():
    r, c = rental()
    group(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-6")


def test_k6_near_miss_supplies_to_outsiders_above_5pct():
    r, c = rental()
    group(r, within=False)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


# -- K-7 location -------------------------------------------------------------------------------------


def test_k7_asset_outside_malaysia_is_not_taxable():
    assert result(*rental(asset_in_malaysia=False)) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-7")


def test_k7_near_miss_asset_in_malaysia():
    assert result(*rental(asset_in_malaysia=True)) == (OK, "SST_CORRECT", "MS-2")


def test_k7_unknown_location_is_a_hand_over():
    assert result(*rental(asset_in_malaysia=None)) == (HO, None, "K-7")


# -- K-8 joint lessors ---------------------------------------------------------------------------------


def _co_owned(r):
    s2 = copy.deepcopy(r["suppliers"][0]) | {"supplier_id": "S2", "name": "Co-owner Two Sdn Bhd"}
    r["suppliers"].append(s2)
    contract(r, parties=["S2"])


def test_k8_invoice_in_one_co_owners_name_makes_it_the_supplier():
    r, c = rental(supplier=())
    _co_owned(r)
    assert result(r, c) == (RCI, "SST_SUPPLIER_NOT_REGISTERED", "K-8")


def test_k8_near_miss_registered_co_owner():
    r, c = rental()
    _co_owned(r)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_catalog_fact_default_vessel_charter_is_exempt_without_a_line_fact():
    # The category implies asset_type vessel (catalog facts): K-3.
    assert result(*one_line("test_vessel_charter", rate="6")) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-3")
    # A line fact still overrides the category's value.
    assert result(*one_line("test_vessel_charter", rate="6", asset_type="machinery")) == (OK, "SST_CORRECT", "MS-2")
