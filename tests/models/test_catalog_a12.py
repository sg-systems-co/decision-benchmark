"""Release catalog for rule sheet v0.10 (A12 build PR 5, plan §6): fact defaults, regressions C1 and C2."""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries import PACKS
from decision_benchmark.task_sets.ap_invoices.countries.my.constants import GROUP_RELIEF_ITEMS
from decision_benchmark.task_sets.ap_invoices.models import Catalog, load_catalog

ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "src/decision_benchmark/task_sets/ap_invoices/content/catalog"
RELEASE = load_catalog(RELEASE_DIR / "categories.yaml")


def test_c1_group_relief_covers_maintenance():
    # C1: First Schedule para 3 as amended by P.U. (A) 354/2024: items (a)-(i), (l) and (n).
    assert "G(n)" in GROUP_RELIEF_ITEMS
    assert RELEASE.get("maintenance_repair").tax["MY"].group_relief


def test_c2_courier_has_no_30_kg_limit_from_26_feb_2024():
    # C2: courier is Group J item 1(d) with no weight limit; the 30 kg limit of the old Group I item 6 appears only as
    # the rule before 26 Feb 2024 (rule sheet MS-10, "26 Feb 2024 additions"; engine 0.10.3).
    assert "30 kg" not in (RELEASE_DIR / "categories.yaml").read_text(encoding="utf-8")
    readme = (RELEASE_DIR / "README.md").read_text(encoding="utf-8")
    for m in re.finditer("30 kg", readme):
        assert "26 February 2024" in readme[max(0, m.start() - 120):m.start()], readme[m.start() - 120:m.end()]


def test_every_fact_default_is_a_line_fact_of_its_country():
    seen = 0
    for c in RELEASE.categories:
        for country, profile in c.tax.items():
            seen += len(PACKS[country].fact_defaults(profile))
    assert seen >= 30


@pytest.mark.parametrize("facts, msg", [({"no_such_fact": True}, "not MY line facts"), ({"asset_type": "spaceship"}, "facts")])
def test_bad_fact_default_is_rejected(facts, msg):
    with pytest.raises((ValidationError, ValueError), match=msg):
        Catalog.model_validate({"version": 1, "categories": [{
            "category": "x", "kind": "service", "label": "x", "countries": ["MY"],
            "tax": {"MY": {"tax_class": "service_6", "service_item": "K", "facts": facts}},
            "gl_role": "rent", "sources": ["https://mysst.customs.gov.my/faq-services-tax/"]}]})


def test_categories_the_plan_adds():
    names = {c.category for c in RELEASE.categories}
    assert {"equipment_rental", "commercial_premises_rental", "aircraft_vessel_charter", "residential_housing_rental",
            "healthcare_consultation", "staff_education_fees", "imported_it_services", "software_royalty",
            "loan_interest_non_resident", "card_activation", "customs_agent", "mobile_phones", "residential_lease_sg",
            "international_freight_sg", "director_benefits", "chauffeured_private_hire"} <= names
