"""Service tax scope by date (engine 0.10.3): Group H item 1 since 2018; the 26 Feb 2024 additions with STP 1/2024
and the old courier item; reg 3A scope changes (MS-3); the Group C wellness exclusions before 1 Jul 2025; MS-8 from
1 Jan 2019; SG-10 vehicle_registered_on. Each date on both sides."""

from decimal import Decimal

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer
from .my_cases import company_facts, one_line, result, sg_one_line, supplier_facts
from .test_my_exemptions import imported

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
EXEMPT, CORRECT = "SST_SHOULD_BE_EXEMPT", "SST_CORRECT"


# -- Group H item 1: credit and charge cards, RM25 per card, taxable since 1 Sep 2018 --------------------------------


def card(day, **kw):
    # 3200.00 x 0.78125% = 25.00: one card.
    return one_line(rate="0.78125", day=day, service_item="H1", financial_charge="card_activation", **kw)


@pytest.mark.parametrize("day, expected", [("2018-08-31", (RCI, EXEMPT, "MS-1")), ("2018-09-01", (OK, CORRECT, "MS-2")),
                                           ("2024-06-14", (OK, CORRECT, "MS-2")), ("2025-06-30", (OK, CORRECT, "MS-2"))])
def test_card_services_taxable_from_1_sep_2018(day, expected):
    assert result(*card(day)) == expected


@pytest.mark.parametrize("day, expected", [("2025-06-30", (OK, CORRECT, "MS-2")), ("2025-07-01", (RCI, EXEMPT, "MS-5"))])
def test_ms5_item6_labuan_from_1_jul_2025_end_to_end(day, expected):
    # Fails if B2B item 6's date check is removed: the card is taxable on 30 Jun 2025, so MS-1 doesn't answer first.
    r, c = card(day)
    company_facts(r, labuan_fsa_regulated=True)
    assert result(r, c) == expected


# -- 26 Feb 2024 additions (P.U. (A) 62/2024) and STP 1/2024 ----------------------------------------------------------


@pytest.mark.parametrize("category, rate", [("karaoke_event_venue", "8"), ("maintenance_repair", "8"),
                                            ("logistics_haulage", "6")])
@pytest.mark.parametrize("day, before, expected", [
    ("2024-02-25", True, (RCI, EXEMPT, "MS-1")),        # not a taxable service yet
    ("2024-02-26", True, (RCI, EXEMPT, "MS-10")),       # STP 1/2024: existing registrant, 26-29 Feb
    ("2024-02-29", True, (RCI, EXEMPT, "MS-10")),
    ("2024-03-01", True, (OK, CORRECT, "MS-2")),
    ("2024-03-31", False, (RCI, EXEMPT, "MS-10")),      # newly liable: to 31 Mar
    ("2024-04-01", False, (OK, CORRECT, "MS-2")),
    ("2024-03-01", None, (HO, None, "MS-10")),
])
def test_26_feb_2024_additions_and_stp_1_2024(category, rate, day, before, expected):
    r, c = one_line(category, rate=rate if day >= "2024-03-01" else "6", day=day)
    supplier_facts(r, registered_before_2024_02_26=before)
    assert result(r, c) == expected


@pytest.mark.parametrize("weight, expected", [("30.00", (OK, CORRECT, "MS-2")), ("30.01", (RCI, EXEMPT, "MS-1")),
                                              (None, (HO, None, "MS-1"))])
def test_courier_before_26_feb_2024_old_item_6_up_to_30_kg(weight, expected):
    r, c = one_line("courier_services", rate="6", day="2024-02-25", parcel_weight_kg=weight)
    assert result(r, c) == expected


@pytest.mark.parametrize("weight, expected", [("30.00", (OK, CORRECT, "MS-2")), ("31.00", (RCI, EXEMPT, "MS-10"))])
def test_courier_from_26_feb_2024_heavier_parcels_are_new_scope_under_stp_1_2024(weight, expected):
    r, c = one_line("courier_services", rate="6", day="2024-02-26", parcel_weight_kg=weight)
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == expected


def test_courier_from_1_apr_2024_needs_no_weight():
    assert result(*one_line("courier_services", rate="6", day="2024-04-01")) == (OK, CORRECT, "MS-2")


# -- MS-3 reg 3A: scope changes (26 Feb 2024 and 1 Jul 2025 additions) -----------------------------------------------


@pytest.mark.parametrize("start, end, rate, expected", [
    ("2024-02-01", "2024-02-25", "8", (RCI, EXEMPT, "MS-3")),      # provided wholly before 26 Feb 2024
    ("2024-04-01", "2024-04-30", "8", (OK, CORRECT, "MS-2")),
    ("2024-02-01", "2024-04-30", "8", (HO, None, "MS-3")),          # spans 26 Feb 2024, no split
])
def test_reg_3a_maintenance_around_26_feb_2024(start, end, rate, expected):
    r, c = one_line("maintenance_repair", rate=rate, day="2024-05-02", service_period_start=start,
                    service_period_end=end)
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == expected


def test_reg_3a_split_shown_taxes_only_the_part_from_the_start_date():
    # 3200.00, 1000.00 provided before 26 Feb 2024: 2200.00 x 8% = 176.00 = 5.5% of the line.
    r, c = one_line("maintenance_repair", rate="5.5", day="2024-05-02", service_period_start="2024-02-01",
                    service_period_end="2024-04-30", value_provided_before_change="1000.00")
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == (OK, CORRECT, "MS-3")


@pytest.mark.parametrize("category, rate, facts", [
    ("construction_works", "6", {}),
    ("it_services", "8", {"service_item": "H3", "financial_charge": "fee_or_commission"}),
])
def test_reg_3a_other_1_jul_2025_additions_provided_before_it(category, rate, facts):
    period = {"service_period_start": "2025-06-01", "service_period_end": "2025-06-30"}
    assert result(*one_line(category, rate=rate, day="2025-07-10", **period, **facts)) == (RCI, EXEMPT, "MS-3")
    period = {"service_period_start": "2025-07-01", "service_period_end": "2025-07-31"}
    assert result(*one_line(category, rate=rate, day="2025-08-04", **period, **facts))[:2] == (OK, CORRECT)


# -- Group C item 2: wellness exclusions before 1 Jul 2025 ------------------------------------------------------------


@pytest.mark.parametrize("kind, day, expected", [
    ("private_healthcare_facility", "2025-06-30", (RCI, EXEMPT, "MS-4")),
    ("private_healthcare_facility", "2025-07-01", (OK, CORRECT, "MS-2")),
    ("government_healthcare_facility", "2025-06-30", (RCI, EXEMPT, "MS-4")),
    ("university_healthcare_facility", "2025-07-01", (OK, CORRECT, "MS-2")),
    ("tcm_practitioner_premises", "2024-11-26", (OK, CORRECT, "MS-2")),
    ("tcm_practitioner_premises", "2024-11-27", (RCI, EXEMPT, "MS-4")),
    ("none", "2025-06-30", (OK, CORRECT, "MS-2")),
])
def test_wellness_centre_exclusions(kind, day, expected):
    assert result(*one_line("wellness_centre_services", rate="8", day=day, wellness_facility_kind=kind)) == expected


# -- MS-8: imported services from 1 Jan 2019 ---------------------------------------------------------------------------


@pytest.mark.parametrize("day, actions", [("2018-12-31", []), ("2019-01-01", ["ACCOUNT_IMPORTED_SERVICE_TAX"])])
def test_ms8_imported_services_from_1_jan_2019(day, actions):
    a = answer(*imported(day=day))
    assert (a.decision, a.tax_lines[0].basis) == (OK, "MS-8")
    assert [x.action for x in a.buyer_actions] == actions


# -- SG-10: business service passenger vehicles registered before 1 Apr 1998 -----------------------------------------


@pytest.mark.parametrize("registered, expected", [("1998-03-31", "CLAIMABLE"), ("1998-04-01", "NOT_CLAIMABLE_DISALLOWED")])
def test_sg10_vehicle_registered_before_1_apr_1998(registered, expected):
    r, c = sg_one_line("motor_car_running", vehicle_registered_on=registered)
    assert result(r, c) == (OK, expected, "SG-10")


# -- Treaty rows that take effect on or after 1 Jan 2023 (treaty_effective_dates.yaml): domestic rate before -------


def _long_certificate(r, country):
    r["residence_certificates"] = [{"certificate_id": "COR-1", "supplier_id": "S1", "country": country,
                                    "valid_from": "2020-01-01"}]


@pytest.mark.parametrize("country, eve, day", [("PL", "2023-12-29", "2024-01-02"), ("RU", "2025-12-31", "2026-01-02")])
def test_my_treaty_interest_from_its_effective_date(country, eve, day):
    from .test_withholding import my_payee, withheld
    for when, rate in ((eve, Decimal(15)), (day, Decimal(10))):
        r, c = my_payee("interest", country=country, day=when)
        _long_certificate(r, country)
        assert [x[:2] for x in withheld(answer(r, c))] == [(rate, "WH-1")], (country, when)


@pytest.mark.parametrize("country", ["KE", "TW"])
def test_sg_treaty_interest_from_1_jan_2027(country):
    from .test_withholding import sg_payee, withheld
    for when, rate in (("2026-12-31", Decimal(15)), ("2027-01-04", Decimal(10))):
        r, c = sg_payee("interest", country=country, day=when)
        _long_certificate(r, country)
        assert [x[:2] for x in withheld(answer(r, c))] == [(rate, "WH-5")], (country, when)


@pytest.mark.parametrize("day, expected", [("2019-12-31", (OK, "SST_BUYER_ACCOUNTS", "MS-8")),
                                           ("2020-01-01", (OK, "NO_SST", "MS-8"))])
def test_ms8_stp_2_2020_from_1_jan_2020(day, expected):
    r, c = imported(day=day, supplier_paid=True)
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == expected
