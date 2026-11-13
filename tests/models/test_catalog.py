"""The catalog loader and its consistency checks."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_benchmark.models import Catalog, load_catalog

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalog.yaml"
RELEASE = (
    Path(__file__).resolve().parents[2]
    / "src/decision_benchmark/content/ap-invoices-my-sg/catalog/categories.yaml"
)


def _cat(**kw):
    base = dict(category="x", kind="service", label="X", countries=["MY"], my_tax_class="service_8",
                gl_role="r", sources=["https://example.org"])
    return {"version": 1, "categories": [base | kw]}


def test_fixture_catalog_loads():
    cat = load_catalog(FIXTURE)
    assert cat.get("logistics_haulage").my_tax_class == "service_6"


@pytest.mark.skipif(not RELEASE.exists(), reason="release catalog not drafted yet")
def test_release_catalog_loads():
    load_catalog(RELEASE)


@pytest.mark.parametrize(
    "kw, msg",
    [
        (dict(my_tax_class=None), "need my_tax_class"),
        (dict(kind="goods"), "service-tax class"),
        (dict(my_tax_class="sales_5"), "sales-tax class"),
        (dict(group_g=True, my_tax_class="service_6"), "Group G"),
        (dict(group_g_excluded=True), "needs group_g"),
        (dict(schedule_c_eligible=True), "Schedule C"),
        (dict(sg_disallowed="betting"), "not used in Singapore"),
        (dict(sources=["http://insecure.example"]), "https"),
        (dict(category="Bad-Name"), "pattern"),
    ],
)
def test_inconsistent_entries_fail(kw, msg):
    with pytest.raises(ValidationError, match=msg):
        Catalog.model_validate(_cat(**kw))
