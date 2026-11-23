"""B1-3 acceptance (B1 plan section 7): the families build every slot; the built exception mix and two-problem counts
are the plan's (section 3.1) for 2,000 / 500 / 300 cases; planted = found on the v0.10 fields; the redraw thresholds hold
(no family or rule above 5% at 20 or more attempts, overall at most 1%, no slot at 20 attempts); report/planting.json
gives attempts, redraws and causes per family."""

import json
from collections import Counter
from functools import cache

import pytest

from decision_benchmark.core.generator.cli import main
from decision_benchmark.core.generator.spec import SplitSpec
from decision_benchmark.task_sets.ap_invoices.generator.build import (
    MAX_ATTEMPTS, Build, PlantingFailed, _Tally, build_split, compare,
)
from decision_benchmark.task_sets.ap_invoices.generator.entities import catalog
from decision_benchmark.task_sets.ap_invoices.generator.hardcases import Template, check_pairs, templates
from decision_benchmark.task_sets.ap_invoices.generator.statements import check_evidence
from decision_benchmark.task_sets.ap_invoices.rules import check_rules
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

from .test_clean_base import case_docs
from .test_slots import COLUMN, TYPE_ROWS, plan_table

GEN, QUOTAS = SPEC.generation, dict(SPEC.quotas)
SIZES = {2000: SplitSpec(name="train", n_cases=2000, seed=2026112201),
         500: SplitSpec(name="test", n_cases=500, seed=2026112202),
         300: SplitSpec(name="x300", n_cases=300, seed=99)}


@cache
def built(n: int) -> Build:
    return build_split(GEN, QUOTAS, SIZES[n])


# -- the exception mix and the pairs -------------------------------------------------------------------------------


@pytest.mark.parametrize("n", sorted(SIZES))
def test_built_exception_mix_and_pairs_are_the_plan_table(n):
    table = plan_table("### 3.1 Exception mix")
    report = built(n).planting_report()
    assert report["cases"] == n
    for label, name in TYPE_ROWS.items():
        assert report["exception_mix"][name] == table[label][COLUMN[n]], label
    two = next(v for k, v in table.items() if k.startswith("Two problems"))[COLUMN[n]]
    assert report["two_problems"]["total"] == two
    slots = built(n).allocation.report()["two_problems"]["pairs"]
    assert report["two_problems"]["pairs"] == slots                      # the exact pairs the allocator chose


@pytest.mark.parametrize("n", sorted(SIZES))
def test_planted_equals_found_and_each_family_gives_its_expect(n):
    fams = {t.family: t for ts in templates().values() for t in ts}
    for g in built(n).cases:
        assert not compare(g.built.planted, g.answer), g.built.case_id
        names = g.families
        if names != ["clean_base"]:
            primary = fams[names[0]]
            assert g.answer.decision.value == primary.expect.decision
            found = Counter(f.code.value for f in g.answer.findings)
            for name in names:
                for code in fams[name].expect.findings:
                    assert found[code] >= 1, (g.built.case_id, name, code)
        assert g.envelope.payload.two_problems == (len(names) == 2)


# -- redraw thresholds and the report ------------------------------------------------------------------------------


@pytest.mark.parametrize("n", sorted(SIZES))
def test_redraw_thresholds_hold(n):
    report = built(n).planting_report()
    assert report["max_slot_attempts"] < MAX_ATTEMPTS
    assert report["redraws"] * 100 <= report["attempts"]
    for kind in ("families", "rules"):
        for name, t in report[kind].items():
            if t["attempts"] >= 20:
                assert t["redraws"] * 20 <= t["attempts"], (kind, name)


def test_planting_report_lists_every_family_with_attempts_redraws_and_causes():
    report = built(2000).planting_report()
    expected = {t.family for ts in templates().values() for t in ts} | {"clean_base"}
    assert set(report["families"]) == expected
    for t in report["families"].values():
        assert {"attempts", "redraws", "redraw_rate", "causes", "first_diffs"} <= set(t) and t["attempts"] > 0
    assert report["rules"] and set(report["thresholds"]) == {
        "family_or_rule_max_redraw", "at_attempts", "overall_max_redraw", "slot_max_attempts"}


def test_thresholds_stop_the_build():
    b = Build(SIZES[300], built(300).allocation, {})
    b.families["f"] = _Tally()
    for i in range(20):
        b.families["f"].add("extra finding" if i < 2 else None, "diff")
    with pytest.raises(PlantingFailed, match="family f: 2 of 20"):
        b.check_thresholds()


def test_db_generate_writes_planting_json(tmp_path):
    assert main(["--task-set", SPEC.id, "--split", "test", "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "test/report/planting.json").read_text())
    assert report["cases"] == 500 and report["families"]["price_above_po"]["attempts"] > 0


# -- templates and pairs -------------------------------------------------------------------------------------------


def test_every_type_has_a_family_and_every_pair_can_be_built():
    fams = templates()
    assert set(fams) == {t.name for t in GEN.types} - {"clean"}
    assert check_pairs(GEN.two_problems.pairs) == []


def test_templates_reject_unknown_ops_and_arguments():
    base = {"family": "x", "version": 1, "countries": ["MY"], "primary_type": "price_mismatch", "summary": "s",
            "expect": {"decision": "DISPUTE_PRICE"}}
    with pytest.raises(ValueError, match="unknown op"):
        Template.model_validate(base | {"ops": [{"op": "no_such_op"}]})
    with pytest.raises(ValueError, match="takes"):
        Template.model_validate(base | {"ops": [{"op": "raise_unit_price_pct", "args": {"line": 1}}]})
    with pytest.raises(ValueError, match="unknown param"):
        Template.model_validate(base | {"ops": [{"op": "raise_unit_price_pct", "args": {"line": 1, "pct": "{p}"}}]})


def test_conflicting_families_are_never_paired():
    fams = {t.family: t for ts in templates().values() for t in ts}
    assert not fams["price_above_po"].compatible(fams["no_po"])            # no PO leaves no price to dispute
    assert not fams["not_received"].compatible(fams["no_po"])
    assert fams["exact_duplicate"].compatible(fams["no_po"])
    for g in built(2000).cases:
        if len(g.families) == 2:
            assert fams[g.families[0]].compatible(fams[g.families[1]])


# -- evidence, reference row, reproducibility over every family ----------------------------------------------------


def test_evidence_and_reference_row_on_every_case():
    for g in built(500).cases:
        assert not check_evidence(g.answer.facts or [], case_docs(g)), g.built.case_id
        lines = [{k: (v if k == "line_no" else {"value": v["value"]}) for k, v in e.items()} for e in g.answer.facts or []]
        result = check_rules(g.records, g.envelope, lines, catalog())
        assert [(x.line_no, x.treatment, x.basis) for x in result.lines] == [
            (t.line_no, t.treatment, t.basis) for t in g.answer.tax_lines], g.built.case_id


def test_100_cases_of_every_type_built_twice_are_byte_identical():
    first = build_split(GEN, QUOTAS, SIZES[500], limit=100).dumps()
    assert first == build_split(GEN, QUOTAS, SIZES[500], limit=100).dumps()
    assert len({json.loads(x)["families"][0] for x in first.splitlines()}) >= 8
