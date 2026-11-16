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
