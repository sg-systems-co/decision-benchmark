"""Goods rates before 1 Jul 2025 (MG-3, engine 0.10.1): the release categories' classes under the Sales Tax
(Rates of Tax) and (Goods Exempted from Tax) Orders 2018 (from 1 Sep 2018) and 2022 (from 1 Jun 2022), which the
2025 orders revoked. P.U. (A) 199/2025 para 3(2): goods no longer exempt from 1 Jul 2025 bear no sales tax when
invoiced before that date."""

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries.my.models import MyTaxProfile
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .test_pinned_goods import RELEASE, run

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
START, END = "2018-09-01", "2025-06-30"
EXEMPT_BEFORE = {   # category: its rate under the 2025 orders
    "hdpe_resin": "5", "polypropylene_resin": "5", "pvc_resin": "5", "copper_wire": "5", "electric_forklifts": "5",
    "power_tools": "5", "centrifugal_pumps": "5", "animal_feed_fishmeal": "5", "animal_feed_premix": "5",
    "construction_rebar_other_section": "5", "motorcycles_50_150cc": "10",
}
NOT_SETTLED_BEFORE = {"process_gauges", "control_instruments", "tool_bits"}


def goods_categories():
    cats = RELEASE.categories if isinstance(RELEASE.categories, list) else list(RELEASE.categories.values())
    return [c for c in cats if "MY" in c.tax and c.tax["MY"].tax_class.startswith("sales_")]


def test_every_goods_category_has_one_earlier_period_or_none():
    unsettled = set()
    for c in goods_categories():
        earlier = c.tax["MY"].earlier_classes
        if not earlier:
            unsettled.add(c.category)
            continue
        assert [(str(e.valid_from), str(e.valid_to)) for e in earlier] == [(START, END)], c.category
        changed = earlier[0].tax_class != c.tax["MY"].tax_class
        assert changed == (c.category in EXEMPT_BEFORE), c.category
    assert unsettled == NOT_SETTLED_BEFORE


@pytest.mark.parametrize("name, rate", EXEMPT_BEFORE.items())
@pytest.mark.parametrize("day", [START, "2022-05-31", "2022-06-01", END])
def test_goods_exempt_before_1_july_2025_carry_no_tax_invoiced_before_then(name, rate, day):
    assert run(name, rate, day=day) == (RCI, "SST_SHOULD_BE_EXEMPT", "MG-3")


@pytest.mark.parametrize("name, rate", [(n, r) for n, r in EXEMPT_BEFORE.items() if n != "motorcycles_50_150cc"])
def test_near_miss_from_1_july_2025_the_2025_rate_applies(name, rate):
    basis = "MG-3" if name.startswith("animal_feed") else "MG-2"   # G-3 codes, before the policy's 1 Jan 2026
    assert run(name, rate, day="2025-07-01") == (OK, "SST_CORRECT", basis)


def test_goods_exempt_before_1_july_2025_invoiced_without_tax_are_correct():
    assert run("hdpe_resin", "0", day=END) == (OK, "NO_SST", "MG-3")
    assert run("hdpe_resin", "0", day="2025-07-01")[1] == "SST_UNDERCHARGED"


@pytest.mark.parametrize("name, rate, expected", [
    ("laptops_desktops", "5", (OK, "SST_CORRECT", "MG-2")),
    ("printers_copiers", "10", (RCI, "SST_WRONG_RATE", "MG-2")),
    ("construction_ceramic_tiles", "10", (OK, "SST_CORRECT", "MG-2")),
    ("construction_cement", "10", (RCI, "SST_SHOULD_BE_EXEMPT", "MG-2")),
])
@pytest.mark.parametrize("day", ["2019-03-01", END])
def test_categories_whose_class_did_not_change_keep_it(name, rate, expected, day):
    assert run(name, rate, day=day) == expected


@pytest.mark.parametrize("name", sorted(NOT_SETTLED_BEFORE))
def test_partly_exempt_headings_are_not_settled_before_1_july_2025(name):
    assert run(name, "10", day=END) == (HO, None, "MG-3")
    assert run(name, "10", day="2025-07-01") == (OK, "SST_CORRECT", "MG-2")


def test_goods_invoiced_before_sales_tax_began_are_not_settled():
    assert run("laptops_desktops", "5", day="2018-08-31") == (HO, None, "MG-3")


@pytest.mark.parametrize("earlier, error", [
    ([{"valid_from": "2018-09-01", "valid_to": "2025-07-01", "tax_class": "sales_10"}], "end before 1 Jul 2025"),
    ([{"valid_from": "2018-09-01", "valid_to": "2022-06-01", "tax_class": "sales_10"},
      {"valid_from": "2022-06-01", "valid_to": "2025-06-30", "tax_class": "sales_5"}], "overlap"),
    ([{"valid_from": "2022-06-01", "valid_to": "2018-09-01", "tax_class": "sales_10"}], "before valid_from"),
])
def test_earlier_classes_are_checked(earlier, error):
    with pytest.raises(ValidationError, match=error):
        MyTaxProfile(tax_class="sales_10", earlier_classes=earlier)


def test_earlier_classes_are_for_goods_only():
    with pytest.raises(ValidationError, match="goods"):
        MyTaxProfile(tax_class="service_8", service_item="G(h)",
                     earlier_classes=[{"valid_from": "2018-09-01", "valid_to": "2025-06-30", "tax_class": "sales_10"}])
