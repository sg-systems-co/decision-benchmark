"""Rule branches dated outside the B1 case windows (plan b1-generator-v0.10 section 6.1): MS-5, MS-6, WH-2, SG-6.
Each date is tested on both sides; engine 0.10.3."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.my.rules import b2b
from decision_benchmark.task_sets.ap_invoices.countries.my.rules.context import Exempt
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer
from .my_cases import company_facts, one_line, result, sg_one_line, supplier_facts
from .test_my_exemptions import group, imported
from .test_withholding import my_payee, withheld

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER


# -- MS-5: P.U. (A) 380/2018 from 1 Jan 2019; amendments 1 Jan 2020, 1 Mar 2024, 1 Jul 2025 --------------------


@pytest.mark.parametrize("day, expected", [("2018-12-31", (OK, "SST_CORRECT", "MS-2")),
                                           ("2019-01-01", (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5"))])
def test_ms5_item1_from_1_jan_2019(day, expected):
    r, c = one_line("management_services", rate="6", day=day)
    company_facts(r, services_provided=["G(i)"])
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2019-12-31", (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")),
                                           ("2020-01-01", (OK, "SST_CORRECT", "MS-2"))])
def test_ms5_items_1_and_2_own_use_condition_from_1_jan_2020(day, expected):
    for category, item in (("management_services", "G(i)"), ("advertising", "I8")):
        r, c = one_line(category, rate="6", day=day, personal_use=True)
        company_facts(r, services_provided=[item])
        assert result(r, c) == expected, category


@pytest.mark.parametrize("day, expected", [
    ("2024-02-25", (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")),      # logistics not a taxable service before 26 Feb 2024
    ("2024-02-29", (RCI, "SST_SHOULD_BE_EXEMPT", "P-20")),     # STP 1/2024: no tax 26-29 Feb 2024
    ("2024-03-01", (RCI, "SST_SHOULD_BE_EXEMPT", "MS-5")),
])
def test_ms5_item5_logistics_from_1_mar_2024(day, expected):
    r, c = one_line("logistics_haulage", rate="6", day=day)
    company_facts(r, services_provided=["J1(a)"])
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == expected


def test_ms5_item5_not_reached_without_the_same_service_from_1_mar_2024():
    r, c = one_line("logistics_haulage", rate="6", day="2024-03-01")
    supplier_facts(r, registered_before_2024_02_26=True)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


@pytest.mark.parametrize("day, expected", [("2019-12-31", (OK, "SST_BUYER_ACCOUNTS", "MS-8")),
                                           ("2020-01-01", (OK, "NO_SST", "MS-5"))])
def test_ms5_item4_imported_it_from_1_jan_2020(day, expected):
    r, c = imported("it_services", day=day)
    company_facts(r, services_provided=["G(h)"])
    assert result(r, c) == expected


@pytest.mark.parametrize("day, basis", [("2019-12-31", "MS-8"), ("2020-01-01", "MS-5")])
def test_ms5_item3_frp_digital_from_1_jan_2020(day, basis):
    r, c = imported("it_services", frp=True, day=day)
    assert result(r, c) == (OK, "SST_BUYER_ACCOUNTS", basis)


def _ctx(day, group, item, **facts):
    """A line reaching b2b.check directly. Groups H, K and L are taxable only from 1 Jul 2025 (MS-1 answers first in
    the full engine), so items 6, 8 and 9 are tested here: these tests fail if their date check is removed."""
    import datetime as dt
    cf = SimpleNamespace(labuan_fsa_regulated=True, services_provided=[item])
    return SimpleNamespace(
        foreign_supplier=False, buyer_registered=lambda: True, item=item, group=group, cf=cf,
        day=dt.date.fromisoformat(day), net=Decimal("100"), buyer_provides=lambda prefix: True,
        fact=lambda name, default, basis: facts.get(name, default))


@pytest.mark.parametrize("group_, item, facts", [("H", "H3", {}), ("K", "K", {"same_service_as_buyer": True,
                                                                             "sublet": True}), ("L", "L", {})])
def test_ms5_items_6_8_9_from_1_jul_2025(group_, item, facts):
    assert b2b.check(_ctx("2025-06-30", group_, item, **facts)) is None
    assert b2b.check(_ctx("2025-07-01", group_, item, **facts)) == Exempt("MS-5")


def test_ms5_in_force_dates_match_the_amending_orders():
    days = {n: [d for d in ("2018-12-31", "2019-01-01", "2019-12-31", "2020-01-01", "2024-02-29", "2024-03-01",
                            "2025-06-30", "2025-07-01") if b2b.in_force(n, __import__("datetime").date.fromisoformat(d))][0]
            for n in (1, 2, 3, 4, 5, 6, 8, 9)}
    assert days == {1: "2019-01-01", 2: "2019-01-01", 3: "2020-01-01", 4: "2020-01-01", 5: "2024-03-01",
                    6: "2025-07-01", 8: "2025-07-01", 9: "2025-07-01"}


# -- MS-6: para 8(2) 5% test from 1 Jan 2020 (P.U. (A) 357/2019); before, para 8: no outside supplies at all -------


@pytest.mark.parametrize("day, none, expected", [
    ("2019-12-31", None, (HO, None, "MS-6")),                          # within 5% doesn't show none
    ("2019-12-31", True, (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")),
    ("2019-12-31", False, (OK, "SST_CORRECT", "MS-2")),
    ("2020-01-01", None, (RCI, "SST_SHOULD_BE_EXEMPT", "MS-6")),
])
def test_ms6_outside_supplies_before_and_from_1_jan_2020(day, none, expected):
    r, c = one_line("management_services", rate="6", day=day)
    group(r)
    supplier_facts(r, no_external_supplies=none)
    assert result(r, c) == expected


def test_ms6_before_2020_above_5pct_is_not_relieved():
    r, c = one_line("management_services", rate="6", day="2019-06-14")
    group(r, within=False)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


# -- WH-2: outside Malaysia chargeable only for services performed 17 Jan - 5 Sep 2017 (PR 10/2019 para 5.2, §21) --


def _outside(start, end, day="2026-03-10", **facts):
    return answer(*my_payee("technical_advice", place_of_performance="outside", day=day, service_period_start=start,
                            service_period_end=end, tax_borne_by_payer=False, **facts))


TEN = [(Decimal(10), "WH-2", Decimal("3200.00"))]


@pytest.mark.parametrize("start, end, expected", [
    ("2016-12-01", "2017-01-16", []), ("2017-01-17", "2017-02-10", TEN),
    ("2017-08-01", "2017-09-05", TEN), ("2017-09-06", "2017-09-30", []),
])
def test_wh2_outside_by_period_of_performance(start, end, expected):
    assert withheld(_outside(start, end, day="2017-10-02")) == expected


def test_wh2_the_invoice_date_does_not_decide():
    # Performed before 6 Sep 2017, invoiced after: chargeable (PR 10/2019 §21 table row 2).
    assert withheld(_outside("2017-08-01", "2017-08-31", day="2017-10-02")) == TEN


@pytest.mark.parametrize("start, end", [("2017-01-10", "2017-01-20"), ("2017-09-01", "2017-09-10"), (None, None)])
def test_wh2_outside_period_across_a_date_or_not_shown_is_a_hand_over(start, end):
    a = _outside(start, end)
    assert a.decision == HO and not withheld(a)


@pytest.mark.parametrize("day, due, borne, expected", [
    ("2018-11-01", "2018-12-04", True, [(Decimal(10), "WH-2", Decimal("3555.56"))]),   # 3200 x 100/90
    ("2018-11-01", "2018-12-05", True, [(Decimal(10), "WH-2", Decimal("3200.00"))]),
    ("2018-11-01", "2018-12-04", False, [(Decimal(10), "WH-2", Decimal("3200.00"))]),
    ("2018-12-05", None, None, [(Decimal(10), "WH-2", Decimal("3200.00"))]),
])
def test_wh2_grossing_up_before_5_dec_2018(day, due, borne, expected):
    r, c = my_payee("movable_property_rent", day=day, tax_borne_by_payer=borne)
    c["invoice"]["due_date"] = due
    assert withheld(answer(r, c)) == expected


@pytest.mark.parametrize("due, borne", [("2018-12-04", None), (None, True)])
def test_wh2_grossing_up_not_shown_is_a_hand_over(due, borne):
    r, c = my_payee("movable_property_rent", day="2018-11-01", tax_borne_by_payer=borne)
    c["invoice"]["due_date"] = due
    assert answer(r, c).decision == HO


# -- SG-6: s21(3)(c) and (e) as amended by Act 35 of 2022, from 1 Jan 2023 ---------------------------------------


@pytest.mark.parametrize("day, kind, expected", [
    ("2022-12-31", None, (OK, "NO_GST", "SG-6")),
    ("2022-12-31", "arranging_passenger", (OK, "NO_GST", "SG-6")),
    ("2023-01-01", "arranging_passenger", (RCI, "GST_UNDERCHARGED", "SG-12")),
    ("2023-01-01", "insuring_passenger", (OK, "NO_GST", "SG-6")),
    ("2023-01-01", "goods", (OK, "NO_GST", "SG-6")),
    ("2023-01-01", None, (HO, None, "SG-6")),
])
def test_sg6_c_narrowed_from_1_jan_2023(day, kind, expected):
    r, c = sg_one_line("logistics_haulage", rate="0", day=day, zero_rating_provision="s21(3)(c)",
                       international_transport=True, transport_service_kind=kind)
    assert result(r, c) == expected


@pytest.mark.parametrize("day, booking, expected", [
    ("2022-12-31", None, (OK, "NO_GST", "SG-6")),
    ("2022-12-31", True, (OK, "NO_GST", "SG-6")),
    ("2023-01-01", True, (RCI, "GST_UNDERCHARGED", "SG-12")),
    ("2023-01-01", False, (OK, "NO_GST", "SG-6")),
    ("2023-01-01", None, (HO, None, "SG-6")),
])
def test_sg6_e_accommodation_booking_out_from_1_jan_2023(day, booking, expected):
    r, c = sg_one_line("logistics_haulage", rate="0", day=day, zero_rating_provision="s21(3)(e)",
                       accommodation_booking=booking)
    assert result(r, c) == expected
