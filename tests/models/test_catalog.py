"""The catalog loader and its consistency checks."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.models import Catalog, load_catalog

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalog.yaml"
RELEASE = (
    Path(__file__).resolve().parents[2]
    / "src/decision_benchmark/task_sets/ap_invoices/content/catalog/categories.yaml"
)


def _cat(**kw):
    my = kw.pop("my", {"tax_class": "service_8"})
    base = dict(category="x", kind="service", label="X", countries=["MY"], tax={"MY": my},
                gl_role="r", sources=["https://example.org"])
    return {"version": 1, "categories": [base | kw]}


def test_fixture_catalog_loads():
    cat = load_catalog(FIXTURE)
    assert cat.get("logistics_haulage").tax["MY"].tax_class == "service_6"
    assert cat.get("club_subscription").tax["SG"].disallowed == "club_subscription"
    assert "SG" not in cat.get("machine_parts").tax  # SG profile optional: no disallowed class


@pytest.mark.skipif(not RELEASE.exists(), reason="release catalog not drafted yet")
def test_release_catalog_loads():
    load_catalog(RELEASE)


@pytest.mark.parametrize(
    "kw, msg",
    [
        (dict(tax={}), "need a tax profile"),
        (dict(my={}), "tax_class"),
        (dict(kind="goods"), "service-tax class"),
        (dict(my={"tax_class": "sales_5"}), "sales-tax class"),
        (dict(my={"tax_class": "service_8"}), "needs its service_item"),
        (dict(my={"tax_class": "none", "b2b_exempt": True}), "need a service_item"),
        (dict(my={"tax_class": "none", "group_relief": True}), "need a service_item"),
        (dict(my={"tax_class": "service_8", "service_item": "I8", "group_relief": True}), "only for Group G"),
        (dict(my={"tax_class": "service_6", "service_item": "J1(a)", "group_relief": True}), "only for Group G"),
        (dict(kind="goods", my={"tax_class": "sales_10", "service_item": "G(a)"}), "only for service_6 and service_8"),
        (dict(kind="goods", my={"tax_class": "none", "service_item": "G(a)"}), "only for service_6 and service_8"),
        (dict(my={"tax_class": "service_8", "service_item": "G(j)", "b2b_exempt": True}), "no B2B exemption"),
        (dict(my={"tax_class": "service_8", "service_item": "G(k)", "b2b_exempt": True}), "no B2B exemption"),
        (dict(my={"tax_class": "service_8", "service_item": "Group G"}), "pattern"),
        (dict(my={"tax_class": "service_8", "service_item": "G(a)", "schedule_c_eligible": True}), "Schedule C"),
        (dict(my={"tax_class": "service_8", "disallowed": "betting"}), "Extra inputs"),
        (dict(tax={"MY": {"tax_class": "service_8"}, "SG": {"disallowed": "betting"}}), "where the category is not used"),
        (dict(countries=["TH"], tax={}), "no country pack"),
        (dict(sources=["http://insecure.example"]), "https"),
        (dict(category="Bad-Name"), "pattern"),
    ],
)
def test_inconsistent_entries_fail(kw, msg):
    with pytest.raises(ValidationError, match=msg):
        Catalog.model_validate(_cat(**kw))


@pytest.mark.skipif(not RELEASE.exists(), reason="release catalog not drafted yet")
def test_release_catalog_covers_every_rule_sheet_situation():
    """Every tax situation in the rule-sheet table has at least one category to plant it on."""
    cat = load_catalog(RELEASE)
    my = [c for c in cat.categories if "MY" in c.countries]
    sg = [c.tax["SG"].disallowed for c in cat.categories if "SG" in c.tax]
    six = {c.category for c in my if c.tax["MY"].tax_class == "service_6"}
    assert {"catering", "logistics_haulage", "telecoms", "parking"} <= six
    services = [c.tax["MY"] for c in my if c.tax["MY"].tax_class.startswith("service_")]
    b2b_groups = {p.service_item[0] for p in services if p.b2b_exempt}
    assert b2b_groups == {"G", "J", "I", "L"}  # the four B2B schemes
    assert {p.service_item for p in services if p.b2b_exempt and p.service_item.startswith("I")} == {"I8"}
    assert {"G(j)", "G(k)"} <= {p.service_item for p in services if not p.b2b_exempt}  # employment and guards
    assert any(p.group_relief for p in services)
    assert all(p.service_item[2] in "abcdefghil" for p in services if p.group_relief)
    assert any(c.tax["MY"].schedule_c_eligible for c in my)
    assert set(sg) == {"club_subscription", "staff_medical", "motor_car", "family_benefit",
                       "medical_accident_insurance", "betting"}


@pytest.mark.skipif(not RELEASE.exists(), reason="release catalog not drafted yet")
def test_release_catalog_has_no_unsourced_goods_rate():
    """Q9: every goods category with a sales-tax class cites both gazetted sales-tax orders and names its HS code."""
    r2 = "https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/SST%20Orders/"
    orders = {r2 + "1-PUA%20170_2025.pdf", r2 + "3-PUA%20171%20(2025).pdf"}
    for c in load_catalog(RELEASE).categories:
        if "MY" not in c.tax or not c.tax["MY"].tax_class.startswith("sales_"):
            continue
        assert orders <= set(c.sources), c.category
        assert c.note.startswith("HS "), c.category
