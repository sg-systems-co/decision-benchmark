"""Dated rule elements of rule sheet v0.10 sections 4 (SG-1 to SG-12) and 4A (WH-1 to WH-5), each tested on the day
before and on the day of its boundary. Boundaries already tested in test_out_of_window_branches.py (SG-6 (c)/(e),
WH-2 grossing-up) are not repeated; the WH-2 outside-Malaysia sides that only checked an empty withholding list are
checked here against a HAND_OVER too."""

from decimal import Decimal

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer
from .my_cases import result, sg_one_line
from .test_sg_claims import foreign
from .test_withholding import my_payee, sg_payee, withheld

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER


# -- SG-3: 8% from 1 Jan 2023, 9% from 1 Jan 2024 (7% before); supply wholly on one side ---------------------------


@pytest.mark.parametrize("day, rate, expected", [
    ("2022-12-31", "7", (OK, "CLAIMABLE", "SG-1")),
    ("2022-12-31", "8", (RCI, "GST_WRONGLY_CHARGED", "SG-3")),
    ("2023-01-01", "8", (OK, "CLAIMABLE", "SG-1")),
    ("2023-01-01", "7", (RCI, "GST_UNDERCHARGED", "SG-3")),
    ("2023-12-31", "8", (OK, "CLAIMABLE", "SG-1")),
    ("2023-12-31", "9", (RCI, "GST_WRONGLY_CHARGED", "SG-3")),
    ("2024-01-01", "9", (OK, "CLAIMABLE", "SG-1")),
    ("2024-01-01", "8", (RCI, "GST_UNDERCHARGED", "SG-3")),
])
def test_sg3_rate_on_each_side_of_the_changes(day, rate, expected):
    assert result(*sg_one_line(rate=rate, day=day)) == expected


# -- SG-3: transitional rules, same for the 2023 change as for 2024 ------------------------------------------------


@pytest.mark.parametrize("change, old, new", [("2023-01-01", "7", "8"), ("2024-01-01", "8", "9")])
def test_sg3_invoice_on_the_change_day_delivered_the_day_before_either_rate(change, old, new):
    # Invoice on or after the change, not fully paid before: the supplier may elect the old rate.
    eve = {"2023-01-01": "2022-12-31", "2024-01-01": "2023-12-31"}[change]
    for rate in (old, new):
        assert result(*sg_one_line(rate=rate, day=change, delivery_date=eve)) == (OK, "CLAIMABLE", "SG-3")


@pytest.mark.parametrize("change, old, new", [("2023-01-01", "7", "8"), ("2024-01-01", "8", "9")])
def test_sg3_invoice_after_the_change_fully_paid_before_takes_the_old_rate(change, old, new):
    # 10 x S$150.00 = S$1,500.00 paid before the change.
    assert result(*sg_one_line(rate=old, day=change, amount_paid_before_change="1500.00")) == (OK, "CLAIMABLE", "SG-3")
    assert result(*sg_one_line(rate=new, day=change, amount_paid_before_change="1500.00")) == (
        RCI, "GST_WRONGLY_CHARGED", "SG-3")


@pytest.mark.parametrize("eve, change, old, new", [("2022-12-31", "2023-01-01", "7", "8"),
                                                   ("2023-12-31", "2024-01-01", "8", "9")])
def test_sg3_invoice_the_day_before_the_change_delivered_on_it_shows_the_old_rate(eve, change, old, new):
    assert result(*sg_one_line(rate=old, day=eve, delivery_date=change)) == (OK, "CLAIMABLE", "SG-3")
    assert result(*sg_one_line(rate=new, day=eve, delivery_date=change)) == (RCI, "GST_WRONGLY_CHARGED", "SG-3")


# -- SG-4 / SG-12: supplier GST registration on the invoice date -------------------------------------------------


def _registered(r, valid_from=None, valid_to=None):
    reg = r["suppliers"][0]["tax_registrations"][0]
    reg["valid_from"] = valid_from or reg["valid_from"]
    reg["valid_to"] = valid_to


@pytest.mark.parametrize("day, rate, expected", [
    ("2026-05-31", "0", (OK, "NO_GST", "SG-4")),
    ("2026-05-31", "9", (RCI, "GST_WRONGLY_CHARGED", "SG-4")),
    ("2026-06-01", "0", (RCI, "GST_UNDERCHARGED", "SG-12")),
    ("2026-06-01", "9", (OK, "CLAIMABLE", "SG-1")),
])
def test_sg4_sg12_registration_starting_on_a_date(day, rate, expected):
    r, c = sg_one_line(rate=rate, day=day)
    _registered(r, valid_from="2026-06-01")
    assert result(r, c) == expected


@pytest.mark.parametrize("day, expected", [("2026-05-31", (OK, "CLAIMABLE", "SG-1")),
                                           ("2026-06-01", (RCI, "GST_WRONGLY_CHARGED", "SG-4"))])
def test_sg4_registration_expired_after_its_last_day(day, expected):
    r, c = sg_one_line(day=day)
    _registered(r, valid_to="2026-05-31")
    assert result(r, c) == expected


# -- SG-6 (u): advertising substantially outside Singapore, zero-rated only before 1 Jan 2022 ----------------------


@pytest.mark.parametrize("day, rate, expected", [
    ("2021-12-31", "0", (OK, "NO_GST", "SG-6")),
    ("2021-12-31", "7", (RCI, "GST_WRONGLY_CHARGED", "SG-6")),
    ("2022-01-01", "0", (RCI, "GST_UNDERCHARGED", "SG-12")),
    ("2022-01-01", "7", (OK, "CLAIMABLE", "SG-1")),
])
def test_sg6_u_advertising_up_to_31_dec_2021(day, rate, expected):
    assert result(*sg_one_line("it_services", rate=rate, day=day, zero_rating_provision="s21(3)(u)")) == expected


# -- SG-8: reverse charge on imported services from 1 Jan 2020, low-value goods from 1 Jan 2023 --------------------


@pytest.mark.parametrize("category, facts, eve, day", [
    ("it_services", {}, "2019-12-31", "2020-01-01"),
    ("machine_parts", {"low_value_goods": True}, "2022-12-31", "2023-01-01"),
])
def test_sg8_reverse_charge_from_its_dates(category, facts, eve, day):
    assert result(*foreign(category, "partially_exempt", eve, **facts)) == (OK, "NO_GST", "SG-8")
    a = answer(*foreign(category, "partially_exempt", day, **facts))
    assert (a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis) == (OK, "REVERSE_CHARGE", "SG-8")
    assert [x.action for x in a.buyer_actions] == ["ACCOUNT_REVERSE_CHARGE_GST"]


# -- SG-10: chauffeured private hire from 1 Apr 2022; car used by a third party from 1 Jan 2023 ---------------------


@pytest.mark.parametrize("fact, eve, eve_rate, day, day_rate", [
    ("chauffeured_pay_per_trip", "2022-03-31", "7", "2022-04-01", "7"),
    ("car_used_by_third_party", "2022-12-31", "7", "2023-01-01", "8"),
])
def test_sg10_motor_car_exceptions_on_each_side_of_their_dates(fact, eve, eve_rate, day, day_rate):
    car = {"vehicle_is_motor_car": True, fact: True}
    assert result(*sg_one_line("motor_car_running", rate=eve_rate, day=eve, **car)) == (
        OK, "NOT_CLAIMABLE_DISALLOWED", "SG-10")
    assert result(*sg_one_line("motor_car_running", rate=day_rate, day=day, **car)) == (OK, "CLAIMABLE", "SG-10")


# -- WH-2: services outside Malaysia, the sides with no withholding are not a HAND_OVER ----------------------------


def _outside(start, end):
    return answer(*my_payee("technical_advice", place_of_performance="outside", day="2017-10-02",
                            service_period_start=start, service_period_end=end, tax_borne_by_payer=False))


@pytest.mark.parametrize("start, end, expected", [
    ("2017-01-01", "2017-01-16", []),                                          # not chargeable before 17 Jan 2017
    ("2017-01-17", "2017-01-31", [(Decimal(10), "WH-2", Decimal("3200.00"))]),
    ("2017-09-01", "2017-09-05", [(Decimal(10), "WH-2", Decimal("3200.00"))]),
    ("2017-09-06", "2017-09-20", []),                                          # exempt from 6 Sep 2017
])
def test_wh2_outside_malaysia_on_each_side_of_17_jan_and_6_sep_2017(start, end, expected):
    a = _outside(start, end)
    assert a.decision != HO and withheld(a) == expected


# -- WH-1 / WH-5: a treaty rate needs a certificate of residence valid on the invoice date --------------------------


CERT_FROM = "2026-01-01"   # test_withholding.cert: valid_from 2026-01-01


@pytest.mark.parametrize("day, rate", [("2025-12-31", "10"), (CERT_FROM, "8")])
def test_wh1_treaty_royalty_rate_from_the_certificate_date(day, rate):
    a = answer(*my_payee("royalty", certificate=True, day=day))
    assert withheld(a) == [(Decimal(rate), "WH-1", Decimal("3200.00"))]


@pytest.mark.parametrize("day, rate", [("2025-12-31", "10"), (CERT_FROM, "8")])
def test_wh5_treaty_royalty_rate_from_the_certificate_date(day, rate):
    a = answer(*sg_payee("royalty", certificate=True, day=day))
    assert withheld(a) == [(Decimal(rate), "WH-5", Decimal("1500.00"))]
