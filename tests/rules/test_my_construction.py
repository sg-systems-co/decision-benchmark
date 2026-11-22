"""Group L construction works: L-1 to L-8 (A12 build PR 2 commit 9; L-5 from the review of PR #14)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_rental import contract

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER


def works(rate="6", day=None, supplier=None, **facts):
    return one_line("construction_works", rate=rate, day=day, supplier=supplier, **facts)


def l_contract(r, **over):
    contract(r, **({"signed_on": "2025-05-01", "stamped_on": "2025-11-01", "start": "2025-06-01",
                    "end": "2027-12-31"} | over))


# -- L-1 non-reviewable contracts ------------------------------------------------------------------


def test_l1_non_reviewable_contract_is_exempt_to_june_2027():
    r, c = works()
    l_contract(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")


@pytest.mark.parametrize("over, day", [
    ({}, "2027-07-10"),                               # after 30 Jun 2027
    ({"signed_on": "2025-07-05"}, None),              # signed on or after 1 Jul 2025
    ({"stamped_on": "2026-01-05"}, None),             # stamped on or after 31 Dec 2025
    ({"has_price_review_clause": True}, None),
])
def test_l1_near_miss_condition_fails(over, day):
    r, c = works(day=day)
    l_contract(r, **over)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l1_variation_order_qualifies_on_its_own_terms():
    vo = {"variation_signed": "2025-06-01", "variation_stamped": "2025-11-01"}
    r, c = works(variation_changes_value=False, **vo)
    l_contract(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")
    r, c = works(variation_changes_value=True, **vo)
    l_contract(r)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")
    r, c = works(variation_changes_value=False, variation_signed="2025-06-01", variation_stamped=None)
    l_contract(r)
    assert result(r, c) == (HO, None, "L-1")


def test_l1_work_after_the_end_needs_qualifying_extensions_of_time():
    # STP 3/2025 Amdt 3 Appendix A (g): the original contract expired before 1 Jul 2025.
    eot = {"signed_on": "2025-06-15", "stamped_on": "2025-10-01", "changes_value": False}
    r, c = works()
    l_contract(r, end="2025-06-30", extensions_of_time=[eot])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")
    r, c = works()
    l_contract(r, end="2025-06-30", extensions_of_time=[eot | {"stamped_on": "2026-02-01"}])
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l1_unknown_clause_is_a_hand_over():
    r, c = works()
    l_contract(r, has_price_review_clause=None)
    assert result(r, c) == (HO, None, "L-1")


# -- L-2 mixed development -------------------------------------------------------------------------


MIXED = {"residential": True, "residential_share": "0.3"}


def test_l2_residential_part_of_a_mixed_development_is_exempt():
    # 30% residential: tax on 70% of 3200.00 at 6% = 134.40 = 4.2% of the line.
    r, c = works(rate="4.2", mixed_development_stated=True, **MIXED)
    assert result(r, c) == (OK, "SST_CORRECT", "L-2")
    r, c = works(rate="6", mixed_development_stated=True, **MIXED)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-2")


def test_l2_the_stated_contract_can_show_it():
    r, c = works(rate="4.2", **MIXED)
    l_contract(r, signed_on="2025-08-01", tax_facts={"country": "MY", "mixed_development_stated": True})
    assert result(r, c) == (OK, "SST_CORRECT", "L-2")


def test_l2_near_miss_contract_does_not_state_mixed_development():
    r, c = works(mixed_development_stated=False, **MIXED)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l2_unknown_statement_is_a_hand_over():
    r, c = works(mixed_development_stated=None, **MIXED)
    assert result(r, c) == (HO, None, "L-2")


# -- L-3 design-and-build ---------------------------------------------------------------------------


def dnb(statement=True, provides=("L",), **facts):
    r, c = one_line(rate="8", service_item="G(e)", design_and_build=True, exemption_statement_on_invoice=statement,
                    **facts)
    company_facts(r, services_provided=list(provides))
    return r, c


def test_l3_consultant_to_a_main_contractor_on_design_and_build_is_exempt():
    assert result(*dnb()) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-3")


@pytest.mark.parametrize("kw", [{"statement": False}, {"provides": ()}])
def test_l3_near_miss_no_statement_or_not_a_main_contractor(kw):
    assert result(*dnb(**kw)) == (OK, "SST_CORRECT", "MS-2")


def test_l3_unknown_design_and_build_is_a_hand_over():
    r, c = one_line(rate="8", service_item="G(e)", design_and_build=None)
    assert result(r, c) == (HO, None, "L-3")


# -- L-4 places of worship ----------------------------------------------------------------------------


def test_l4_place_of_worship_is_exempt():
    assert result(*works(place_of_worship=True)) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-4")


def test_l4_near_miss_commercial_building():
    assert result(*works(place_of_worship=False)) == (OK, "SST_CORRECT", "MS-2")


# -- L-6 facilities for foreign clients ----------------------------------------------------------------


def test_l6_facility_for_a_foreign_client_with_the_statement_is_exempt():
    r, c = works(client_established_in_malaysia=False, exemption_statement_on_invoice=True)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-6")


def test_l6_near_miss_no_statement_on_the_invoice():
    r, c = works(client_established_in_malaysia=False, exemption_statement_on_invoice=False)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l6_unknown_client_is_a_hand_over():
    assert result(*works(client_established_in_malaysia=None)) == (HO, None, "L-6")


# -- L-7 government -----------------------------------------------------------------------------------


def test_l7_government_contractor():
    r, c = works()
    supplier_facts(r, supplier_kind="federal_state_government")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-7")


def test_l7_near_miss_local_authority_after_september_2025():
    r, c = works(day="2025-10-20")
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


# -- L-8 materials, installation, ships and platforms -------------------------------------------------


def _manufacturer(r):
    supplier_facts(r, is_manufacturer=True)


def test_l8_materials_not_separated_tax_the_whole_invoice():
    assert result(*works(materials_works_separated=False)) == (OK, "SST_CORRECT", "L-8")


def test_l8_installation_not_separated_by_a_manufacturer_bears_sales_tax():
    r, c = works(rate="10", tax_type="01", supplier=("service", "sales"), installation_separated=False)
    _manufacturer(r)
    assert result(r, c) == (OK, "SST_CORRECT", "L-8")
    r, c = works(rate="6", supplier=("service", "sales"), installation_separated=False)
    _manufacturer(r)
    assert result(r, c) == (RCI, "SST_WRONG_RATE", "L-8")


def test_l8_near_miss_installation_by_a_non_manufacturer_bears_service_tax():
    assert result(*works(installation_separated=False)) == (OK, "SST_CORRECT", "MS-2")
    assert result(*works(installation_separated=True)) == (OK, "SST_CORRECT", "MS-2")


def test_l8_ship_or_platform_follows_the_election():
    r, c = works(rate="6", ship_platform_election="manufacturing")
    assert result(r, c) == (RCI, "SST_WRONG_RATE", "L-8")
    assert result(*works(ship_platform_election="construction")) == (OK, "SST_CORRECT", "MS-2")
    assert result(*works(ship_platform_election=None)) == (HO, None, "L-8")


# -- L-5 completed residential buildings (review of PR #14) --------------------------------------------------


HOME = {"residential": True, "completed_building": True}


def test_l5_work_on_a_completed_home_with_recipient_and_address_is_exempt():
    assert result(*works(**HOME)) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-5")


def test_l5_near_miss_invoice_without_the_residential_address_is_taxed():
    r, c = works(**HOME)
    c["invoice"]["buyer_block"]["address"] = None
    assert result(r, c) == (OK, "SST_CORRECT", "L-5")


def test_l5_near_miss_building_not_completed_falls_under_the_regulations():
    assert result(*works(residential=True, completed_building=False)) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-4")


def test_l5_unknown_completion_is_a_hand_over():
    assert result(*works(residential=True, completed_building=None)) == (HO, None, "L-5")
