"""Malaysian B2B exemptions, group relief, areas and imported services: MS-5 to MS-8 (A12 build PR 2 commit 7)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D
from decision_benchmark.task_sets.ap_invoices.rules import UnsupportedCase

from .factory import answer
from .my_cases import company_facts, company_sst, one_line, result, supplier_facts

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
RENTAL = {"service_item": "K", "asset_type": "machinery"}


# -- MS-5: B2B exemptions -------------------------------------------------------------------------


def test_ms5_rental_sublet_in_full_is_exempt():
    r, c = one_line(rate="6", sublet=True, **RENTAL)
    company_facts(r, services_provided=["K"])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")


def test_ms5_rental_sublet_in_part_exempts_the_sublet_part():
    # 40% sublet: tax on 60% of 3200.00 at 6% = 115.20 = 3.6% of the line.
    r, c = one_line(rate="3.6", sublet=True, sublet_share="0.4", **RENTAL)
    company_facts(r, services_provided=["K"])
    assert result(r, c) == (OK, "SST_CORRECT", "MS-5")
    r, c = one_line(rate="6", sublet=True, sublet_share="0.4", **RENTAL)
    company_facts(r, services_provided=["K"])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")


def test_ms5_construction_and_finance_items():
    r, c = one_line("construction_works", rate="6")
    company_facts(r, services_provided=["L"])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")
    r, c = one_line(rate="8", service_item="H3", financial_charge="fee_or_commission")
    company_facts(r, labuan_fsa_regulated=True)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")


@pytest.mark.parametrize("facts, provides, labuan", [
    (RENTAL | {"sublet": False}, ["K"], False),                       # rented for own use, not to sublet
    (RENTAL | {"sublet": True}, ["G(h)"], False),                     # not a Group K provider
    ({"own_use": True}, ["L"], False),                                # construction for own use
    ({"service_item": "H3", "financial_charge": "fee_or_commission"}, [], False),  # not Labuan-regulated
])
def test_ms5_near_miss_condition_fails(facts, provides, labuan):
    category = "construction_works" if provides == ["L"] else "it_services"
    rate = "6" if facts.get("service_item") == "K" or category == "construction_works" else "8"
    r, c = one_line(category, rate=rate, **facts)
    company_facts(r, services_provided=provides, labuan_fsa_regulated=labuan)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


@pytest.mark.parametrize("fact", ["personal_use", "same_service_as_buyer"])
def test_ms5_unknown_purpose_or_same_service_is_a_hand_over(fact):
    r, c = one_line("management_services", rate="8", **{fact: None})
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == (HO, None, "MS-5")


def test_ms5_unknown_sublet_is_a_hand_over():
    r, c = one_line(rate="6", sublet=None, **RENTAL)
    company_facts(r, services_provided=["K"])
    assert result(r, c) == (HO, None, "MS-5")


# -- MS-6: group relief -----------------------------------------------------------------------------


def group(r, pct="60", board=None, nominee=False, reverse=False, within=True):
    holder, held = ("S1", "my-c-001") if reverse else ("my-c-001", "S1")
    company_facts(r, group={"shareholdings": [
        {"holder_id": holder, "held_id": held, "pct": pct, "board_control": board, "nominee": nominee}]})
    supplier_facts(r, group_company_id="S1", external_share_within_5pct=within)


@pytest.mark.parametrize("kw", [{}, {"reverse": True}, {"pct": "30", "board": True}])
def test_ms6_group_company_supply_is_relieved(kw):
    r, c = one_line("management_services", rate="8")
    group(r, **kw)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")


def test_ms6_relieved_supply_without_tax_is_no_sst():
    r, c = one_line("management_services", rate="0")
    group(r)
    assert result(r, c) == (OK, "NO_SST", "MS-6")


@pytest.mark.parametrize("kw", [{"pct": "30", "board": False}, {"pct": "60", "nominee": True}, {"within": False},
                                {"pct": "15", "board": True}])
def test_ms6_near_miss_no_control_or_above_5pct(kw):
    r, c = one_line("management_services", rate="8")
    group(r, **kw)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms6_near_miss_item_outside_group_relief():
    r, c = one_line("advertising", rate="8")
    group(r)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms6_maintenance_is_relieved_from_1_may_2024():
    r, c = one_line("maintenance_repair", rate="8", day="2024-04-15")
    group(r)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")
    r, c = one_line("maintenance_repair", rate="8", day="2024-05-02")
    group(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")


@pytest.mark.parametrize("kw", [{"pct": "30", "board": None}, {"within": None}])
def test_ms6_unknown_control_or_5pct_is_a_hand_over(kw):
    r, c = one_line("management_services", rate="8")
    group(r, **kw)
    assert result(r, c) == (HO, None, "MS-6")


def test_ms6_group_company_without_a_group_structure_is_a_hand_over():
    r, c = one_line("management_services", rate="8")
    supplier_facts(r, group_company_id="S1")
    assert result(r, c) == (HO, None, "MS-6")


# -- MS-7: designated and special areas ----------------------------------------------------------


def test_ms7_service_within_a_designated_area_is_not_taxed():
    r, c = one_line(rate="8")
    company_facts(r, zone="labuan")
    supplier_facts(r, zone="labuan")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-7")
    r, c = one_line(rate="0")
    company_facts(r, zone="langkawi")
    supplier_facts(r, zone="free_zone")
    assert result(r, c) == (OK, "NO_SST", "MS-7")


def test_ms7_near_miss_principal_customs_area_and_jda():
    r, c = one_line(rate="8")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")
    r, c = one_line(rate="8")
    company_facts(r, zone="jda")
    supplier_facts(r, zone="jda")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")      # refund route since 15 Aug 2022 (P-20)


def test_ms7_unknown_zone_status_is_a_hand_over():
    r, c = one_line(rate="8")
    supplier_facts(r, zone="labuan", zone_known=False)
    assert result(r, c) == (HO, None, "MS-7")


def test_ms7_principal_customs_area_to_a_zone_is_not_in_the_sheet():
    r, c = one_line(rate="8")
    company_facts(r, zone="labuan")
    with pytest.raises(UnsupportedCase, match="DA/SA orders"):
        answer(r, c)


# -- MS-8: imported taxable services ----------------------------------------------------------------


def imported(category="management_services", rate="0", frp=False, supplier=(), **facts):
    r, c = one_line(category, rate=rate, supplier=supplier, **facts)
    r["suppliers"][0]["country"] = "SG"
    if frp:
        supplier_facts(r, is_foreign_registered_person=True)
    return r, c


def test_ms8_buyer_accounts_for_imported_service_tax():
    r, c = imported()
    a = answer(r, c)
    assert (a.decision, a.tax_treatment, a.tax_lines[0].basis) == (OK, "SST_BUYER_ACCOUNTS", "MS-8")
    assert [x.action for x in a.buyer_actions] == ["ACCOUNT_IMPORTED_SERVICE_TAX"]


def test_ms8_exceptions_buyer_accounts_for_nothing():
    r, c = imported()
    group(r)
    assert result(r, c) == (OK, "NO_SST", "MS-6")                 # para 3A: group company abroad
    r, c = imported("it_services")
    company_facts(r, services_provided=["G(h)"])
    assert result(r, c) == (OK, "NO_SST", "MS-5")                 # B2B item 4: reselling the IT service
    r, c = imported(supplier_paid=True)
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == (OK, "NO_SST", "MS-8")                 # STP 2/2020
    r, c = imported("it_services", service_item="H3", financial_charge="fee_or_commission",
                    financial_use="offshore_financial_services")
    company_facts(r, services_provided=["H3"])
    assert result(r, c) == (OK, "NO_SST", "MS-8")                 # STP 1/2025 item 6


def test_ms8_near_miss_supplier_not_yet_paid():
    r, c = imported(supplier_paid=False)
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == (OK, "SST_BUYER_ACCOUNTS", "MS-8")


def test_ms8_near_miss_excluded_service_is_not_imported_taxable():
    r, c = imported("legal_services", subject_outside_malaysia=True)
    assert result(r, c) == (OK, "NO_SST", "MS-4")


def test_ms8_foreign_registered_person():
    r, c = imported("it_services", rate="8", frp=True, supplier=("service",), service_item="G(l)")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-8")            # STP 3/2020: the FRP's invoice carries SST
    r, c = imported("it_services", frp=True, service_item="G(l)")
    assert result(r, c) == (OK, "SST_BUYER_ACCOUNTS", "MS-5")     # B2B item 3
    r, c = imported("it_services", frp=True, service_item="G(l)")
    company_sst(r)
    assert result(r, c) == (RCI, "SST_UNDERCHARGED", "MS-9")


def test_ms8_foreign_supplier_charging_sst_is_not_registered():
    r, c = imported(rate="8")
    assert result(r, c) == (RCI, "SST_SUPPLIER_NOT_REGISTERED", "MS-1")


def test_ms8_unregistered_buyer_is_a_hand_over():
    r, c = imported()
    company_sst(r)
    assert result(r, c) == (HO, None, "MS-8")


def holdings(r, *rows, within=True):
    """Shareholdings as (holder, held, pct, extra) rows; the supplier is S1 and the buyer my-c-001."""
    company_facts(r, group={"shareholdings": [
        {"holder_id": h, "held_id": d, "pct": p} | (x or {}) for h, d, p, x in rows]})
    supplier_facts(r, group_company_id="S1", external_share_within_5pct=within)


def test_ms6_sisters_under_a_common_parent_company_are_relieved():
    # Para 4: one company (the parent P) controls each of the other companies.
    r, c = one_line("management_services", rate="8")
    holdings(r, ("P", "my-c-001", "60", None), ("P", "S1", "70", None))
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")


def test_ms6_near_miss_sisters_under_a_common_individual_are_not_a_group():
    r, c = one_line("management_services", rate="8")
    ind = {"holder_kind": "individual"}
    holdings(r, ("Mr X", "my-c-001", "60", ind), ("Mr X", "S1", "70", ind))
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms6_indirect_control_through_a_subsidiary_is_relieved():
    # Para 5: P controls SUB, SUB controls S1, so P controls S1 indirectly; P also controls the buyer.
    r, c = one_line("management_services", rate="8")
    holdings(r, ("P", "my-c-001", "55", None), ("P", "SUB", "60", None), ("SUB", "S1", "80", None))
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")
    # Direct and indirect holdings add up: 30% by P and 25% by its subsidiary SUB is 55%.
    r, c = one_line("management_services", rate="8")
    holdings(r, ("P", "my-c-001", "55", None), ("P", "SUB", "60", None), ("P", "S1", "30", None),
             ("SUB", "S1", "25", None))
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")


def test_ms6_near_miss_parent_controls_only_one_sister():
    r, c = one_line("management_services", rate="8")
    holdings(r, ("P", "my-c-001", "60", None), ("P", "S1", "40", {"board_control": False}))
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms6_unknown_board_control_on_the_common_parent_path_is_a_hand_over():
    r, c = one_line("management_services", rate="8")
    holdings(r, ("P", "my-c-001", "60", None), ("P", "S1", "40", {"board_control": None}))
    assert result(r, c) == (HO, None, "MS-6")


def test_ms5_near_miss_buyer_registered_for_sales_tax_only():
    # The B2B order is made under the Service Tax Act 2018: a sales-tax registration doesn't make a registered person.
    r, c = one_line("management_services", rate="8")
    company_facts(r, services_provided=["G(i)"])
    company_sst(r, "sales")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")
    r, c = one_line("management_services", rate="8")
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")
