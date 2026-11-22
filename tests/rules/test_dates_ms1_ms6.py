"""Dated rule elements in rule sheet v0.10 section 1, MS-1 to MS-6 (incl. the K-x and L-x rules): each date boundary
tested on the day before and on the day itself, asserting what the sheet says. MS-5 item dates and the MS-6 5% test
are in test_out_of_window_branches.py."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .my_cases import one_line, result, supplier_facts
from .test_my_construction import l_contract, works
from .test_my_exemptions import group
from .test_my_rental import contract, msme, rental

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
CORRECT, EXEMPT, WRONG = "SST_CORRECT", "SST_SHOULD_BE_EXEMPT", "SST_WRONG_RATE"


# -- MS-2 / MS-3: the general 8% rate from 1 Mar 2024 (Rate of Tax (Amendment) Order 2024, P.U. (A) 64/2024) ---------
# Before 1 Mar 2024 every taxable service is at 6%; from then 8% except the 6% list (F&B, telecoms, parking, logistics).


@pytest.mark.parametrize("item, facts, before, after", [
    ("G(h)", {}, "6", "8"),                                 # IT services
    ("A", {}, "6", "8"),                                    # accommodation
    ("C", {"fb_content": "alcohol_alone"}, "6", "8"),       # Group C operator, alcohol sold alone (STP 3/2024)
    ("I2", {}, "6", "6"),                                   # telecoms: 6% on both sides
])
@pytest.mark.parametrize("day", ["2024-02-29", "2024-03-01"])
def test_ms2_general_rate_8pct_from_1_mar_2024(item, facts, before, after, day):
    right = before if day < "2024-03-01" else after
    r, c = one_line(rate=right, day=day, service_item=item, **facts)
    assert result(r, c) == (OK, CORRECT, "MS-2")
    if before != after:
        wrong = after if day < "2024-03-01" else before
        r, c = one_line(rate=wrong, day=day, service_item=item, **facts)
        assert result(r, c) == (RCI, WRONG, "MS-2")


# -- MS-1 / MS-4: Groups H, K, L, M and items I14-I16 are taxable services from 1 Jul 2025 ---------------------------


NEW_SCOPE = [
    ("it_services", "8", {"service_item": "H3", "financial_charge": "fee_or_commission"}),
    ("it_services", "8", {"service_item": "H2", "financial_charge": "insurance_premium", "insurance_cover": "other"}),
    ("it_services", "8", {"service_item": "K", "asset_type": "machinery"}),
    ("construction_works", "6", {}),
    ("it_services", "6", {"service_item": "M", "education_provider_kind": "higher_education",
                          "student_category": "non_citizen"}),
    ("it_services", "6", {"service_item": "I14", "patient_category": "non_citizen"}),
    ("it_services", "6", {"service_item": "I15", "patient_category": "non_citizen"}),
    ("it_services", "6", {"service_item": "I16", "patient_category": "non_citizen"}),
]


@pytest.mark.parametrize("category, rate, facts", NEW_SCOPE)
def test_ms1_new_scope_not_taxable_on_30_jun_2025(category, rate, facts):
    r, c = one_line(category, rate=rate, day="2025-06-30", **facts)
    assert result(r, c) == (RCI, EXEMPT, "MS-1")


@pytest.mark.parametrize("category, rate, facts", NEW_SCOPE)
def test_ms1_new_scope_taxable_from_1_jul_2025(category, rate, facts):
    r, c = one_line(category, rate=rate, day="2025-07-01", **facts)
    assert result(r, c) == (OK, CORRECT, "MS-2")


# -- MS-2 / MS-3 / Group K: rental 8% from 1 Jul 2025 to 31 Dec 2025, 6% from 1 Jan 2026 [P.U. (A) 125/2026] ---------


@pytest.mark.parametrize("day, right, wrong, at_wrong", [
    ("2025-12-31", "8", "6", (RCI, WRONG, "MS-2")),
    # 8% on rental from 1 Jan 2026 is a wrong rate whether invoiced before or after the 13 Mar 2026 gazette date
    # (STP 2/2025 Amendment No. 5, Appendix B: the correction comes as a credit note).
    ("2026-01-01", "6", "8", (RCI, WRONG, "MS-2")),
    ("2026-03-13", "6", "8", (RCI, WRONG, "MS-2")),
    ("2026-03-14", "6", "8", (RCI, WRONG, "MS-2")),
])
def test_ms2_rental_6pct_from_1_jan_2026(day, right, wrong, at_wrong):
    assert result(*rental(rate=right, day=day)) == (OK, CORRECT, "MS-2")
    assert result(*rental(rate=wrong, day=day)) == at_wrong


@pytest.mark.parametrize("start, end, day, rate, expected", [
    ("2025-12-01", "2025-12-31", "2026-02-02", "8", (OK, CORRECT, "MS-3")),   # December rental, invoiced in the gap: 8%
    ("2026-01-01", "2026-01-31", "2026-02-02", "8", (RCI, WRONG, "MS-2")),    # January rental: 6%, invoiced before 13 Mar
    ("2026-01-01", "2026-01-31", "2026-03-16", "8", (RCI, WRONG, "MS-2")),    # ... and after
])
def test_ms2_rental_8pct_by_the_period_provided_around_1_jan_2026(start, end, day, rate, expected):
    assert result(*rental(rate=rate, day=day, service_period_start=start, service_period_end=end)) == expected


# MS-3: "Services spanning a rate change are taxed by the part provided on each side of the date; payments received
# before the change keep the old rate ... Rental: 8% from 1 Jul 2025". Rental provided before 1 Jul 2025 bears no tax,
# even when invoiced later (Service Tax Regulations 2018 reg 3A; Guide on Rental or Leasing Services paras 40-41,
# FAQ 7: "provided prior to the effective date of 1 July 2025" is not subject to service tax).

_JUNE = {"service_period_start": "2025-06-01", "service_period_end": "2025-06-30"}
_JULY = {"service_period_start": "2025-07-01", "service_period_end": "2025-07-31"}
_SPAN = {"service_period_start": "2025-06-16", "service_period_end": "2025-07-15"}
_NO_TAX_BEFORE_1_JUL_2025 = ("ENGINE ERROR: MS-3 is applied only between two rates; rental provided before 1 Jul 2025 "
                             "(or paid before it) is taxed at 8% because the invoice date is after 1 Jul 2025")


def test_ms3_rental_provided_in_june_2025_invoiced_in_july_bears_no_tax():
    decision, treatment, basis = result(*rental(rate="8", day="2025-07-10", **_JUNE))
    assert (decision, treatment) == (RCI, EXEMPT) and basis in ("MS-1", "MS-3")


def test_ms3_rental_provided_from_1_jul_2025_is_taxed():
    assert result(*rental(rate="8", day="2025-08-05", **_JULY)) == (OK, CORRECT, "MS-2")


def test_ms3_rental_spanning_1_jul_2025_without_the_split_is_a_hand_over():
    assert result(*rental(rate="8", day="2025-07-20", **_SPAN)) == (HO, None, "MS-3")


def test_ms3_rental_spanning_1_jul_2025_is_taxed_on_the_july_part_only():
    # 3200.00, of which 1600.00 provided before 1 Jul 2025: tax 1600.00 x 8% = 128.00 = 4% of the line.
    r, c = rental(rate="4", day="2025-07-20", value_provided_before_change="1600.00", **_SPAN)
    assert result(r, c) == (OK, CORRECT, "MS-3")


def test_ms3_rental_paid_before_1_jul_2025_bears_no_tax():
    decision, treatment, _ = result(*rental(rate="8", day="2025-07-05", amount_paid_before_change="3200.00", **_JULY))
    assert (decision, treatment) == (RCI, EXEMPT)


def test_ms3_rental_paid_from_1_jul_2025_is_taxed():
    assert result(*rental(rate="8", day="2025-07-05", amount_paid_before_change="0.00", **_JULY)) == (OK, CORRECT, "MS-2")


# K-x and L-x dates: tests/rules/test_dates_mg_me.py.


# -- MS-6 / C1: G(n) maintenance or repair in group relief from 1 May 2024 [P.U. (A) 354/2024] ------------------------


@pytest.mark.parametrize("day, expected", [("2024-04-30", (OK, CORRECT, "MS-2")), ("2024-05-01", (RCI, EXEMPT, "MS-6"))])
def test_ms6_maintenance_group_relief_from_1_may_2024(day, expected):
    r, c = one_line("maintenance_repair", rate="8", day=day)
    group(r)
    assert result(r, c) == expected
