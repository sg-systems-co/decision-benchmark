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
        (dict(my={"tax_class": "service_6", "group_g": True}), "Group G"),
        (dict(my={"tax_class": "service_8", "group_g_excluded": True}), "needs group_g"),
        (dict(my={"tax_class": "service_8", "schedule_c_eligible": True}), "Schedule C"),
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
    assert any(c.tax["MY"].group_g and not c.tax["MY"].group_g_excluded for c in my)
    assert sum(c.tax["MY"].group_g_excluded for c in my) >= 2  # employment and guards
    assert any(c.tax["MY"].schedule_c_eligible for c in my)
    assert set(sg) == {"club_subscription", "staff_medical", "motor_car", "family_benefit",
                       "medical_accident_insurance", "betting"}


@pytest.mark.skipif(not RELEASE.exists(), reason="release catalog not drafted yet")
def test_release_catalog_has_no_unsourced_goods_rate():
    """Q9: no 5% goods in v0.9, and every taxed goods category cites both sales-tax orders."""
    orders = {
        "https://repositori.parlimen.gov.my/bitstream/123456789/3521/83/ST.104.2025%20-%20ST104.2025.pdf",
        "https://repositori.parlimen.gov.my/bitstream/123456789/3521/84/ST.105.2025%20-%20ST105.2025.pdf",
    }
    for c in load_catalog(RELEASE).categories:
        if "MY" not in c.tax or not c.tax["MY"].tax_class.startswith("sales_"):
            continue
        assert c.tax["MY"].tax_class != "sales_5", c.category
        assert orders <= set(c.sources), c.category
        assert c.note.startswith("HS "), c.category
