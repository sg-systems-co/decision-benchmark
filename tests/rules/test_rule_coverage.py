"""Every rule in the v0.10 rule sheet has registered tests or is not an engine rule with a guard test (A12 plan §12).
The PENDING set used during the build is gone at engine 0.10.0."""

import importlib
import re
from pathlib import Path

from decision_benchmark import __version__

from . import rule_coverage
from .rule_coverage import NOT_ENGINE, NOT_ENGINE_GUARDS, RULE_TESTS, SECTION_5

ROOT = Path(__file__).resolve().parents[2]
SHEET = (ROOT / "docs/tax-rules-v0.10.md").read_text(encoding="utf-8")
RULE_ID = re.compile(r"\b(?:MS|MG|ME|SG|WH|K|L|P|G)-\d+\b")


def sheet_rules() -> set[str]:
    return set(RULE_ID.findall(SHEET)) | set(SECTION_5)


def _exists(name: str) -> bool:
    module, _, function = name.partition("::")
    return callable(getattr(importlib.import_module(f"rules.{module}"), function, None))


def test_the_sheet_has_81_rule_ids_and_two_section_5_rules():
    assert len(sheet_rules()) == 83 and "## 5. Mixed invoices" in SHEET


def test_every_rule_is_in_exactly_one_place():
    guarded = {r for r in NOT_ENGINE if NOT_ENGINE_GUARDS.get(r)}
    places = [set(RULE_TESTS), guarded]
    assert set().union(*places) == sheet_rules()
    assert sum(len(p) for p in places) == len(sheet_rules()), "a rule is in more than one place"
    assert set(NOT_ENGINE) == guarded, "every not-engine rule has its guard test"
    assert set(NOT_ENGINE) == {"P-21", "G-2", "G-6", "G-7"}


def test_registered_tests_exist():
    for rule, tests in RULE_TESTS.items():
        assert tests.get("positive") and tests.get("near_miss"), rule
        for name in tests["positive"] + tests["near_miss"]:
            assert _exists(name), f"{rule}: {name} does not exist"
    for rule, names in NOT_ENGINE_GUARDS.items():
        assert rule in NOT_ENGINE and names, rule
        assert all(_exists(n) for n in names), rule


def test_every_rule_is_built_at_engine_0_10():
    # A12 plan §12: the PENDING set is emptied and removed with engine 0.10.0.
    assert __version__.startswith("0.10.") and not hasattr(rule_coverage, "PENDING")
