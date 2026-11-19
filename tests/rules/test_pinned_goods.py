"""Release goods categories pinned to one tariff code (G-1, G-3, L-8; review of A12 PR 5): each gives its rate on
both sides of the date it depends on. The engine runs on the fixture goods category with its Malaysian profile
replaced by the release category's, so the release tax class and tariff_code default are what decide."""

from pathlib import Path

import pytest

from decision_benchmark.task_sets.ap_invoices.models import CompanyRecords, Decision as D, load_catalog
from decision_benchmark.task_sets.ap_invoices.rules import answer_case

from .factory import CATALOG, wrap
from .my_cases import one_line

RELEASE = load_catalog(Path(__file__).resolve().parents[2]
                       / "src/decision_benchmark/task_sets/ap_invoices/content/catalog/categories.yaml")
RCI, OK = D.REQUEST_CORRECTED_INVOICE, D.APPROVE
FIXTURE = "test_raw_resin"


def run(release_category: str, rate: str, day: str = "2026-03-02", **kw) -> tuple:
    catalog = CATALOG.model_copy(deep=True)
    catalog.get(FIXTURE).tax["MY"] = RELEASE.get(release_category).tax["MY"]
    r, c = one_line(FIXTURE, rate=rate, price="12.40", qty=100, day=day, **kw)
    a = answer_case(CompanyRecords.model_validate(r), wrap(c), catalog)
    return a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis


@pytest.mark.parametrize("name, code", [
    ("motorcycles_50_150cc", "8711.20.96 00"), ("animal_feed_fishmeal", "2301.20.20 00"),
    ("animal_feed_premix", "2309.90.20 00"), ("construction_cement", "2523.29.90 00"),
    ("construction_rebar_round", "7214.20.31 00"), ("construction_rebar_other_section", "7214.20.41 00"),
    ("construction_ceramic_tiles", "6907"),
])
def test_each_category_is_pinned_to_its_code(name, code):
    assert RELEASE.get(name).tax["MY"].facts["tariff_code"] == code


# -- G-1 motorcycles 8711.20.96 00: exempt before 1 Jul 2025 (2018, 2022 orders) and from it (G-1) -----------


def test_g1_motorcycles_exempt_the_day_before_the_policy_under_the_2022_order():
    # Engine 0.10.1: P.U. (A) 175/2022 Schedule A lists 8711.20.96 00 (MG-3); 0.10.0 had 10% here.
    assert run("motorcycles_50_150cc", "10", day="2025-06-30") == (RCI, "SST_SHOULD_BE_EXEMPT", "MG-3")


@pytest.mark.parametrize("day", ["2025-07-01", "2025-11-01"])   # policy from 1 Jul; Exemption Order from 1 Nov
def test_g1_motorcycles_exempt_from_1_july_2025(day):
    assert run("motorcycles_50_150cc", "10", day=day) == (RCI, "SST_SHOULD_BE_EXEMPT", "G-1")


# -- G-3 feed raw materials: 5% on both sides of 1 Jan 2026 (refund route) --------------------------------------


@pytest.mark.parametrize("name", ["animal_feed_fishmeal", "animal_feed_premix"])
@pytest.mark.parametrize("day, basis", [("2025-12-31", "MG-3"), ("2026-01-01", "G-3")])
def test_g3_feed_raw_materials_stay_at_5_percent(name, day, basis):
    assert run(name, "5", day=day) == (OK, "SST_CORRECT", basis)


@pytest.mark.parametrize("name", ["animal_feed_fishmeal", "animal_feed_premix"])
@pytest.mark.parametrize("day, basis", [("2026-08-31", "G-3"), ("2026-09-01", "MG-2")])
def test_g3_ends_31_august_2026_without_a_certificate_the_5_percent_rate_applies(name, day, basis):
    assert run(name, "5", day=day) == (OK, "SST_CORRECT", basis)


def test_g3_near_miss_feed_raw_materials_at_10_percent_is_the_wrong_rate():
    assert run("animal_feed_fishmeal", "10", day="2026-01-01") == (RCI, "SST_WRONG_RATE", "MG-2")


# -- L-8 construction materials: rate by subheading ------------------------------------------------------------


@pytest.mark.parametrize("name, rate, expected", [
    ("construction_cement", "10", (RCI, "SST_SHOULD_BE_EXEMPT", "MG-2")),
    ("construction_rebar_round", "5", (RCI, "SST_SHOULD_BE_EXEMPT", "MG-2")),
    ("construction_rebar_other_section", "5", (OK, "SST_CORRECT", "MG-2")),
    ("construction_rebar_other_section", "10", (RCI, "SST_WRONG_RATE", "MG-2")),
    ("construction_ceramic_tiles", "10", (OK, "SST_CORRECT", "MG-2")),
])
def test_construction_materials_take_their_subheading_rate(name, rate, expected):
    assert run(name, rate) == expected


def test_l8_separated_materials_on_a_construction_invoice_carry_no_service_tax():
    assert run("construction_rebar_other_section", "6", tax_type="02",
               materials_works_separated=True) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-8")
