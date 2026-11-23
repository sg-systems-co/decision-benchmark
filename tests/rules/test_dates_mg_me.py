"""Dated rule elements of rule sheet v0.10 sections 2 (MG-1 to MG-6, G-x) and 3 (ME-1 to ME-4), and the Group K and
Group L ministerial exemptions (K-1 to K-8, L-1 to L-8): both sides of each date boundary that other test files leave
untested or test only on non-adjacent days. Assertions follow the rule sheet; where the engine disagrees the test is
an xfail naming the error.

Where a K-x or L-x date coincides with 1 Jul 2025 (Groups K and L taxable only from then: MS-1 answers first in the
full engine), the day before is tested on the rule's own function, so the test fails if its date check is removed."""

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.my.rules import construction
from decision_benchmark.task_sets.ap_invoices.countries.my.rules import rental as rental_rules
from decision_benchmark.task_sets.ap_invoices.countries.my.rules.context import LineCtx
from decision_benchmark.task_sets.ap_invoices.countries.my.rules.scope import NEW_SCOPE_FROM
from decision_benchmark.task_sets.ap_invoices.models import CompanyRecords, Decision as D
from decision_benchmark.task_sets.ap_invoices.rules import answer_case

from .factory import CATALOG, answer, wrap
from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_areas import GEXEMPT, GNONE, GTAXED, first_line, goods
from .test_my_construction import l_contract, works
from .test_my_rental import contract, msme, rental

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
HO5 = (HO, None, "MG-5")
D_ = dt.date.fromisoformat


# == MG-4: the certificate's period ("for those goods and that period") ======================================


def _certificate(r, **over):
    cert = {"kind": "schedule_a", "number": "A-1", "valid_from": "2026-01-01", "categories": ["test_raw_resin"]} | over
    r["company"]["policy_pack"].setdefault("exemption_certificates", []).append(cert)


@pytest.mark.parametrize("valid_to, expected", [("2026-11-02", (RCI, "SST_SHOULD_BE_EXEMPT", "MG-4")),
                                                ("2026-11-01", (OK, "SST_CORRECT", "MG-2"))])
def test_mg4_certificate_valid_on_its_last_day_only(valid_to, expected):
    r, c = one_line("test_raw_resin", rate="10", price="12.40", qty=100, day="2026-11-02")
    _certificate(r, valid_to=valid_to)
    assert result(r, c) == expected


@pytest.mark.parametrize("valid_from, expected", [("2026-11-02", (RCI, "SST_SHOULD_BE_EXEMPT", "MG-4")),
                                                  ("2026-11-03", (OK, "SST_CORRECT", "MG-2"))])
def test_mg4_certificate_valid_from_its_first_day(valid_from, expected):
    r, c = one_line("test_raw_resin", rate="10", price="12.40", qty=100, day="2026-11-02")
    _certificate(r, valid_from=valid_from)
    assert result(r, c) == expected


# == MG-5: areas from the Act (Pangkor 1 Jan 2020, Pulau 1 1 Dec 2024), supply base (1 Jan 2020) ==============


@pytest.mark.parametrize("day, expected", [("2019-12-31", GTAXED), ("2020-01-01", GEXEMPT)])
def test_mg5_goods_into_pangkor_from_1_january_2020(day, expected):
    assert result(*goods(day=day, company="pangkor")) == expected


@pytest.mark.parametrize("day, expected", [("2024-11-30", GTAXED), ("2024-12-01", HO5)])
def test_mg5_goods_into_pulau_1_from_1_december_2024(day, expected):
    assert result(*goods(day=day, company="pulau_1")) == expected


@pytest.mark.parametrize("day, expected", [("2019-12-31", GTAXED), ("2020-01-01", GEXEMPT)])
def test_mg5_petroleum_supply_base_special_area_from_1_january_2020(day, expected):
    assert result(*goods(day=day, company="petroleum_supply_base")) == expected


# == MG-5: goods the DA order taxes on entry (Q-A1 flag on PCA -> DA; HAND_OVER between two DAs from 2026) =====


@pytest.mark.parametrize("category, zone, day, flagged", [
    ("test_petroleum", "langkawi", "2019-12-31", False), ("test_petroleum", "langkawi", "2020-01-01", True),   # 391/2019
    ("test_cigarettes", "langkawi", "2020-12-31", False), ("test_cigarettes", "langkawi", "2021-01-01", True),  # 420/2020
    ("test_e_liquid", "langkawi", "2023-03-31", False), ("test_e_liquid", "langkawi", "2023-04-01", True),      # 94/2023
    ("test_motor_vehicle", "pangkor", "2020-01-01", True),                                                    # 391/2019
])
def test_mg5_da_list_dates_exact_day(category, zone, day, flagged):
    line = first_line(*goods(category, rate="0", day=day, company=zone))
    assert (line.treatment, line.basis, line.open_question) == ("NO_SST", "MG-5", "Q-A1" if flagged else None)


def test_mg5_pangkor_motor_vehicles_the_day_before_pangkor_is_an_area():
    line = first_line(*goods("test_motor_vehicle", rate="0", day="2019-12-31", company="pangkor"))
    assert (line.treatment, line.basis) == ("SST_UNDERCHARGED", "MS-9")         # Pangkor still in the PCA


VEHICLE = {"tariff_code": "8703.23.10 00", "motor_vehicle_value": "400000.00", "motor_vehicle_value_basis": "sales_price"}


@pytest.mark.parametrize("day, flagged", [("2025-12-31", False), ("2026-01-01", True)])
def test_mg5_pca_vehicle_above_rm300000_into_labuan_from_1_january_2026(day, flagged):
    line = first_line(*goods("test_motor_vehicle", rate="0", day=day, company="labuan", **VEHICLE))
    assert (line.treatment, line.basis, line.open_question) == ("NO_SST", "MG-5", "Q-A1" if flagged else None)


@pytest.mark.parametrize("category, facts, day, expected", [
    ("test_marble", {}, "2025-12-31", GEXEMPT), ("test_marble", {}, "2026-01-01", HO5),
    ("test_motor_vehicle", VEHICLE, "2025-12-31", GEXEMPT), ("test_motor_vehicle", VEHICLE, "2026-01-01", HO5),
])
def test_mg5_step5_listed_goods_between_two_das_from_1_january_2026(category, facts, day, expected):
    assert result(*goods(category, day=day, supplier="labuan", company="langkawi", **facts)) == expected


# == MG-5: goods the SA order taxes on entry (HAND_OVER under Q-A2) ===========================================


@pytest.mark.parametrize("day, expected", [("2018-12-31", GNONE), ("2019-01-01", HO5)])
def test_mg5_schedule_a_reaches_lmws_on_1_january_2019(day, expected):
    assert result(*goods("test_office_furniture", rate="0", day=day, company="licensed_manufacturing_warehouse")) == expected


@pytest.mark.parametrize("day, expected", [("2018-12-31", GNONE), ("2019-01-01", HO5)])
def test_mg5_not_used_directly_in_lmw_manufacturing_from_1_january_2019(day, expected):
    r, c = goods(rate="0", day=day, company="licensed_manufacturing_warehouse", used_directly_in_approved_activity=False)
    assert result(r, c) == expected


@pytest.mark.parametrize("category, day, expected", [
    ("test_cigarettes", "2021-09-02", GNONE), ("test_cigarettes", "2021-09-03", HO5),   # 349/2021
    ("test_e_liquid", "2023-03-31", GNONE), ("test_e_liquid", "2023-04-01", HO5),       # 100/2023
])
def test_mg5_sa_order_tobacco_into_free_zones_exact_day(category, day, expected):
    assert result(*goods(category, rate="0", day=day, company="free_zone")) == expected


def _run_as(area_goods: list[str], r, c):
    catalog = CATALOG.model_copy(deep=True)
    profile = catalog.get("test_raw_resin").tax["MY"]
    catalog.get("test_raw_resin").tax["MY"] = profile.model_copy(update={"area_goods": area_goods})
    a = answer_case(CompanyRecords.model_validate(r), wrap(c), catalog)
    return a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis


@pytest.mark.parametrize("day, expected", [("2018-12-31", HO5), ("2019-01-01", GNONE)])
def test_mg5_manufacturing_aids_into_a_free_zone_until_31_december_2018(day, expected):
    r, c = goods(rate="0", day=day, company="free_zone")
    assert _run_as(["manufacturing_aid"], r, c) == expected


# == K-1 to K-5 (STP 2/2025 Amendment No. 5) ==================================================================


def _msme_ctx(day, band="below_1m", reg="2026-03-01"):
    m = SimpleNamespace(mypmk_status_known=True, mypmk_registered_on=D_(reg), declared_sales_band=band,
                        paid_up_capital=Decimal("1000000"), group_holding_pct=None)
    return SimpleNamespace(cf=SimpleNamespace(msme=m), day=D_(day), processing_date=D_("2026-11-05"))


def test_k1_below_rm1m_band_starts_1_july_2025():
    assert rental_rules.sme_tenant(_msme_ctx("2025-06-30")) is False
    assert rental_rules.sme_tenant(_msme_ctx("2025-07-01")) is True
    r, c = rental(rate="8", day="2025-07-01")
    msme(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-1")


@pytest.mark.parametrize("day, rate, expected", [("2025-12-31", "8", (OK, "SST_CORRECT", "MS-2")),
                                                 ("2026-01-01", "6", (RCI, "SST_SHOULD_BE_EXEMPT", "K-1"))])
def test_k1_rm1m_to_rm1_5m_band_starts_1_january_2026(day, rate, expected):
    r, c = rental(rate=rate, day=day)
    msme(r, declared_sales_band="1m_to_1_5m")
    assert result(r, c) == expected


@pytest.mark.parametrize("registered, expected", [("2026-12-31", (RCI, "SST_SHOULD_BE_EXEMPT", "K-1")),
                                                  ("2027-01-01", (OK, "SST_CORRECT", "MS-2"))])
def test_k1_mypmk_registration_backdates_only_up_to_31_december_2026(registered, expected):
    r, c = rental(day="2026-02-10")
    msme(r, mypmk_registered_on=registered)
    c["as_of_date"] = "2027-01-05"
    assert result(r, c) == expected


NEW_SME = {"declared_sales_band": "above_1_5m"}


@pytest.mark.parametrize("day, rate, expected", [("2025-12-31", "8", (OK, "SST_CORRECT", "MS-2")),
                                                 ("2026-01-01", "6", (RCI, "SST_SHOULD_BE_EXEMPT", "K-2"))])
def test_k2_new_smes_from_1_january_2026(day, rate, expected):
    r, c = rental(rate=rate, day=day)
    msme(r, ssm_registered_on="2025-10-01", mypmk_registered_on="2025-10-15", **NEW_SME)
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2027-01-31", (RCI, "SST_SHOULD_BE_EXEMPT", "K-2")),
                                           ("2027-02-01", (OK, "SST_CORRECT", "MS-2"))])
def test_k2_one_year_from_ssm_registration(day, expected):
    r, c = rental(day=day)
    msme(r, ssm_registered_on="2026-02-01", mypmk_registered_on="2026-02-15", **NEW_SME)
    assert result(r, c) == expected


def test_k2_one_year_across_a_leap_day():
    r, c = rental(day="2028-02-29")
    msme(r, ssm_registered_on="2027-03-01", mypmk_registered_on="2027-03-15", **NEW_SME)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-2")


def test_k2_near_miss_one_year_across_a_leap_day_ends():
    r, c = rental(day="2028-03-01")
    msme(r, ssm_registered_on="2027-03-01", mypmk_registered_on="2027-03-15", **NEW_SME)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def _k4_ctx(day):
    k = SimpleNamespace(signed_on=D_("2025-05-20"), stamped_on=D_("2025-06-05"), has_price_review_clause=False,
                        states_service=True, states_fixed_value=True, states_period=True, end=D_("2027-06-30"))
    return SimpleNamespace(day=D_(day), contract=lambda basis: k, fact=lambda name, default, basis: default,
                           supplier_registered=lambda *a: True)


def test_k4_window_starts_1_july_2025():
    assert rental_rules.non_reviewable_contract(_k4_ctx("2025-06-30")) is False
    assert rental_rules.non_reviewable_contract(_k4_ctx("2025-07-01")) is True
    r, c = rental(rate="8", day="2025-07-01")
    contract(r)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-4")


@pytest.mark.parametrize("day, expected", [("2026-06-30", (RCI, "SST_SHOULD_BE_EXEMPT", "K-4")),
                                           ("2026-07-01", (OK, "SST_CORRECT", "MS-2"))])
def test_k4_window_ends_30_june_2026(day, expected):
    r, c = rental(day=day)
    contract(r)
    assert result(r, c) == expected


@pytest.mark.parametrize("signed", ["2025-06-01", None])   # None: signed on the stamping day (stamping follows signing)
@pytest.mark.parametrize("on, expected", [("2025-06-09", (RCI, "SST_SHOULD_BE_EXEMPT", "K-4")),
                                          ("2025-06-10", (OK, "SST_CORRECT", "MS-2"))])
def test_k4_signed_and_stamped_on_or_before_9_june_2025(signed, on, expected):
    r, c = rental(day="2026-03-10")
    contract(r, signed_on=signed or on, stamped_on=on)
    assert result(r, c) == expected


@pytest.mark.parametrize("end, expected", [("2025-07-01", (OK, "SST_CORRECT", "MS-2")),
                                           ("2025-07-02", (RCI, "SST_SHOULD_BE_EXEMPT", "K-4"))])
def test_k4_contract_runs_past_1_july_2025(end, expected):
    r, c = rental(rate="8", day="2025-07-01")
    contract(r, end=end)
    assert result(r, c) == expected


def test_k5_l7_federal_and_state_from_1_july_2025():
    gov = SimpleNamespace(sf=SimpleNamespace(supplier_kind="federal_state_government"))
    for basis in ("K-5", "L-7"):
        assert LineCtx.government_supplier(SimpleNamespace(**vars(gov), day=D_("2025-06-30")), basis, NEW_SCOPE_FROM) is False
        assert LineCtx.government_supplier(SimpleNamespace(**vars(gov), day=D_("2025-07-01")), basis, NEW_SCOPE_FROM) is True
    r, c = rental(rate="8", day="2025-07-01")
    supplier_facts(r, supplier_kind="federal_state_government")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "K-5")


def test_k5_l7_local_authorities_from_1_july_2025():
    la = SimpleNamespace(sf=SimpleNamespace(supplier_kind="local_authority"))
    assert LineCtx.government_supplier(SimpleNamespace(**vars(la), day=D_("2025-06-30")), "K-5", NEW_SCOPE_FROM) is False
    assert LineCtx.government_supplier(SimpleNamespace(**vars(la), day=D_("2025-07-01")), "K-5", NEW_SCOPE_FROM) is True


@pytest.mark.parametrize("day, expected", [("2025-09-30", (RCI, "SST_SHOULD_BE_EXEMPT", "K-5")),
                                           ("2025-10-01", (OK, "SST_CORRECT", "MS-2"))])
def test_k5_local_authority_lessor_to_30_september_2025(day, expected):
    r, c = rental(rate="8", day=day)
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == expected


# == L-1, L-5, L-7 (STP 3/2025 Amendment No. 3, STP 2/2026) ==================================================


@pytest.mark.parametrize("day, expected", [("2027-06-30", (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")),
                                           ("2027-07-01", (OK, "SST_CORRECT", "MS-2"))])
def test_l1_exempt_to_30_june_2027(day, expected):
    r, c = works(day=day)
    l_contract(r)
    assert result(r, c) == expected


@pytest.mark.parametrize("over, expected", [
    ({"signed_on": "2025-06-30"}, (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")),
    ({"signed_on": "2025-07-01"}, (OK, "SST_CORRECT", "MS-2")),
    ({"stamped_on": "2025-12-30"}, (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")),
    ({"stamped_on": "2025-12-31"}, (OK, "SST_CORRECT", "MS-2")),
])
def test_l1_signed_before_1_july_2025_and_stamped_before_31_december_2025(over, expected):
    r, c = works()
    l_contract(r, **over)
    assert result(r, c) == expected


@pytest.mark.parametrize("signed, stamped, expected", [
    ("2025-06-30", "2025-12-30", (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")),
    ("2025-07-01", "2025-12-30", (OK, "SST_CORRECT", "MS-2")),
    ("2025-06-30", "2025-12-31", (OK, "SST_CORRECT", "MS-2")),
])
def test_l1_variation_order_signed_and_stamped_by_the_same_dates(signed, stamped, expected):
    r, c = works(variation_signed=signed, variation_stamped=stamped, variation_changes_value=False)
    l_contract(r)
    assert result(r, c) == expected


@pytest.mark.parametrize("signed, stamped, expected", [
    ("2025-06-30", "2025-12-30", (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")),
    ("2025-07-01", "2025-12-30", (OK, "SST_CORRECT", "MS-2")),
    ("2025-06-30", "2025-12-31", (OK, "SST_CORRECT", "MS-2")),
])
def test_l1_extension_of_time_signed_and_stamped_by_the_same_dates(signed, stamped, expected):
    # Appendix A (g)(iii): an extension of time on an original contract that expired before 1 Jul 2025.
    eot = {"signed_on": signed, "stamped_on": stamped, "changes_value": False}
    r, c = works()
    l_contract(r, end="2025-06-30", extensions_of_time=[eot])
    assert result(r, c) == expected


def test_l1_near_miss_extension_of_time_on_a_contract_in_force_after_1_july_2025():
    # (g) covers only originals that expired before 1 Jul 2025; work after a 2026 end has no qualifying extension.
    eot = {"signed_on": "2025-06-15", "stamped_on": "2025-10-01", "changes_value": False}
    r, c = works(day="2026-08-03")
    l_contract(r, end="2026-06-30", extensions_of_time=[eot])
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l1_contract_ending_on_1_july_2025_is_not_in_force_after_it():
    r, c = works(day="2025-07-01")
    l_contract(r, end="2025-07-01")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_l1_near_miss_contract_ending_2_july_2025_is_in_force_after_1_july():
    r, c = works(day="2025-07-01")
    l_contract(r, end="2025-07-02")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")


def test_l1_extension_of_time_on_a_contract_that_ended_30_june_2025():
    eot = {"signed_on": "2025-06-15", "stamped_on": "2025-10-01", "changes_value": False}
    r, c = works()
    l_contract(r, end="2025-06-30", extensions_of_time=[eot])
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-1")


def test_l1_near_miss_contract_ended_30_june_2025_without_an_extension():
    r, c = works()
    l_contract(r, end="2025-06-30")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def _home_ctx(day):
    facts = {"residential": True, "completed_building": True}
    return SimpleNamespace(day=D_(day), fact=lambda name, default, basis: facts.get(name, default),
                           invoice=SimpleNamespace(buyer_block=SimpleNamespace(name="Tan", address="1 Jalan Mawar")))


def test_l5_completed_homes_from_1_july_2025():
    assert construction.completed_home(_home_ctx("2025-06-30")) is None
    assert construction.completed_home(_home_ctx("2025-07-01")) is not None
    assert result(*works(day="2025-07-01", residential=True, completed_building=True)) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-5")


@pytest.mark.parametrize("day, expected", [("2025-09-30", (RCI, "SST_SHOULD_BE_EXEMPT", "L-7")),
                                           ("2025-10-01", (OK, "SST_CORRECT", "MS-2"))])
def test_l7_local_authority_contractor_to_30_september_2025(day, expected):
    r, c = works(day=day)
    supplier_facts(r, supplier_kind="local_authority")
    assert result(r, c) == expected


# == ME-3: the buyer's phase start, and its relaxation period does not lift self-billing ======================


@pytest.mark.parametrize("day, actions", [("2025-12-31", []), ("2026-01-01", ["ISSUE_SELF_BILLED_EINVOICE"]),
                                          ("2027-12-31", ["ISSUE_SELF_BILLED_EINVOICE"])])
def test_me3_from_the_buyers_phase_start_including_its_relaxation_period(day, actions):
    r, c = one_line(day=day, rate="8" if day >= "2024-03-01" else "6", self_billing_type="agents_dealers_distributors")
    company_facts(r, einvoice={"turnover_band": "3m_to_5m", "turnover_basis": "fy2022_audited"})
    assert [x.action for x in answer(r, c).buyer_actions] == actions
