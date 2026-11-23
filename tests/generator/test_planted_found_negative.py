"""Planted = found must bite (B1 plan section 4): a family whose expectation is wrong redraws until its slot reaches 20
attempts and stops the build with a clear error, and an expectation wrong in any one compared field (decision, finding
codes, a line's treatment, a line's basis, a buyer action, a gold fact) redraws the case with that cause in
report/planting.json."""

import json
from decimal import Decimal

import pytest

from decision_benchmark.core.generator.cli import main
from decision_benchmark.core.generator.spec import SplitSpec
from decision_benchmark.task_sets.ap_invoices.generator import build as build_mod
from decision_benchmark.task_sets.ap_invoices.generator.build import (
    MAX_ATTEMPTS, Build, PlantingFailed, build_split, compare, planted_truth,
)
from decision_benchmark.task_sets.ap_invoices.generator.hardcases import Expect, templates
from decision_benchmark.task_sets.ap_invoices.models import BuyerAction
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

GEN, QUOTAS = SPEC.generation, dict(SPEC.quotas)
TEST = SplitSpec(name="test", n_cases=500, seed=2026112202)
PRIMARY = "tax_problem"             # its family plants a finding, a line basis, and facts the engine reads


# -- (1) a family with a wrong expected decision stops the build ---------------------------------------------------


@pytest.fixture
def wrong_decision_family(monkeypatch):
    """price_above_po's ops with APPROVE expected: the engine disputes the price on every draw."""
    good = next(t for t in templates()["price_mismatch"] if t.family == "price_above_po")
    bad = good.model_copy(update={"family": "wrong_decision", "expect": Expect(decision="APPROVE")})
    fams = {k: list(v) for k, v in templates().items()} | {"price_mismatch": [bad]}
    monkeypatch.setattr(build_mod, "templates", lambda: fams)
    captured: list[Build] = []

    class Capturing(Build):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.append(self)

    monkeypatch.setattr(build_mod, "Build", Capturing)
    return captured


def test_wrong_expected_decision_redraws_to_20_attempts_and_stops_the_build(wrong_decision_family):
    with pytest.raises(PlantingFailed) as err:
        build_split(GEN, QUOTAS, TEST, primaries={"price_mismatch"}, limit=1)
    message = str(err.value)
    assert f"{MAX_ATTEMPTS} attempts, planted != found on every one" in message
    assert "price_mismatch" in message and "wrong_decision" in message
    assert "decision DISPUTE_PRICE != APPROVE" in message

    b = wrong_decision_family[0]
    assert b.max_slot_attempts == MAX_ATTEMPTS and b.cases == []
    tally = b.families["wrong_decision"]
    assert (tally.attempts, tally.redraws, dict(tally.causes)) == (MAX_ATTEMPTS, MAX_ATTEMPTS,
                                                                    {"decision differs": MAX_ATTEMPTS})
    report = err.value.report
    assert report["attempts"] == report["redraws"] == MAX_ATTEMPTS
    assert report["families"]["wrong_decision"]["causes"] == {"decision differs": MAX_ATTEMPTS}


def test_db_generate_stops_with_the_error_and_still_writes_planting_json(wrong_decision_family, tmp_path):
    with pytest.raises(PlantingFailed, match="wrong_decision"):
        main(["--task-set", SPEC.id, "--split", "test", "--out", str(tmp_path)])
    report = json.loads((tmp_path / "test/report/planting.json").read_text())
    assert report["max_slot_attempts"] == MAX_ATTEMPTS
    assert report["families"]["wrong_decision"] | {"first_diffs": []} == {
        "attempts": MAX_ATTEMPTS, "redraws": MAX_ATTEMPTS, "redraw_rate": "1.0000",
        "causes": {"decision differs": MAX_ATTEMPTS}, "first_diffs": []}


# -- (2) one compared field wrong redraws the case with that cause --------------------------------------------------


def _first_case():
    return build_split(GEN, QUOTAS, TEST, primaries={PRIMARY}, limit=1, check=False).cases[0]


def _other(value):
    return "PERTURBED" if not isinstance(value, bool) else not value


def perturb_decision(p, g):
    p.decision = "APPROVE" if p.decision != "APPROVE" else "HAND_OVER"


def perturb_drop_finding(p, g):
    p.findings = p.findings[1:]


def perturb_add_finding(p, g):
    p.findings = sorted(p.findings + ["DUPLICATE_INVOICE"])


def perturb_treatment(p, g):
    n, treatment, basis = p.lines[0]
    p.lines = [(n, _other(treatment), basis)] + p.lines[1:]


def perturb_basis(p, g):
    n, treatment, basis = p.lines[0]
    p.lines = [(n, treatment, _other(basis))] + p.lines[1:]


def perturb_buyer_action(p, g):
    p.buyer_actions = p.buyer_actions + [("WITHHOLD_TAX", "10", "WH-2")]


def perturb_gold_fact(p, g):
    key = next((e["line_no"], k) for e in g.answer.facts for k, v in e.items()
               if k != "line_no" and v.get("value") is not None)
    p.facts = p.facts | {key: _other(p.facts[key])}


CASES = [
    ("decision", perturb_decision, "decision differs"),
    ("finding code (one the engine finds, not planted)", perturb_drop_finding, "extra finding"),
    ("finding code (planted, not found)", perturb_add_finding, "missing finding"),
    ("line treatment", perturb_treatment, "treatment differs"),
    ("line basis", perturb_basis, "basis differs"),
    ("buyer action", perturb_buyer_action, "action differs"),
    ("gold fact", perturb_gold_fact, "fact differs"),
]


def test_the_case_has_every_compared_field():
    g = _first_case()
    assert g.built.attempt == 0 and g.built.planted.findings and g.built.planted.lines[0][2]
    assert any(v.get("value") is not None for e in g.answer.facts or [] for k, v in e.items() if k != "line_no")
    assert "DUPLICATE_INVOICE" not in g.built.planted.findings


@pytest.mark.parametrize(("field", "perturb", "cause"), CASES, ids=[c[0] for c in CASES])
def test_one_wrong_field_redraws_the_case_with_its_cause(monkeypatch, tmp_path, field, perturb, cause):
    original = _first_case()
    target = original.built.case_id
    seen = []

    def perturbed(built, families, d):
        p = planted_truth(built, families, d)
        if built.case_id == target and built.attempt == 0:
            perturb(p, original)
            seen.append(field)
        return p

    monkeypatch.setattr(build_mod, "planted_truth", perturbed)
    b = build_split(GEN, QUOTAS, TEST, primaries={PRIMARY}, limit=1, check=False)
    assert seen == [field]                                       # only that field, only on the first draw

    g = b.cases[0]
    assert g.built.case_id == target and g.built.attempt == 1    # redrawn; the second draw agrees
    assert not compare(g.built.planted, g.answer)

    path = tmp_path / "planting.json"
    path.write_text(json.dumps(b.planting_report()))             # as db-generate writes it
    report = json.loads(path.read_text())
    assert (report["attempts"], report["redraws"], report["causes"]) == (2, 1, {cause: 1})
    family = report["families"][original.families[0]]
    assert family["causes"] == {cause: 1} and len(family["first_diffs"]) == 1
    rules = [r for r in report["rules"].values() if r["redraws"]]
    assert rules and all(r["causes"] == {cause: 1} for r in rules)


# -- buyer action rate and basis are compared, not only the action ---------------------------------------------------


@pytest.mark.parametrize(("want", "same"), [
    (("WITHHOLD_TAX", "10", "WH-2"), True),
    (("WITHHOLD_TAX", "15", "WH-2"), False),
    (("WITHHOLD_TAX", "10", "WH-3"), False),
])
def test_buyer_action_rate_and_basis_are_compared(want, same):
    g = _first_case()
    action = BuyerAction(action="WITHHOLD_TAX", rate=Decimal("10"), basis="WH-2", base_amount=Decimal("100.00"))
    answer = g.answer.model_copy(update={"buyer_actions": [action]})
    g.built.planted.buyer_actions = [want]
    assert (compare(g.built.planted, answer) == []) is same
