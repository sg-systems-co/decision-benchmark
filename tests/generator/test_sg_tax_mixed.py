"""B1-5 acceptance (B1 plan section 7): one family per Singapore rule; the Singapore floors met (16 / 4 / 2 per rule;
2 problem forms per rule in train, 2 per family in test); every Singapore rule reachable on 50 draws; the mixed quota
(at least 12% of each split, a third of it Malaysian §5-b split cases) realised in the built cases. Planting limit 5 is
in test_planting_limits.py."""

from collections import Counter
from functools import cache

import pytest

from decision_benchmark.core.generator.slots import CORRECT, PROBLEM
from decision_benchmark.task_sets.ap_invoices.countries.sg import planting
from decision_benchmark.task_sets.ap_invoices.generator.entities import catalog
from decision_benchmark.task_sets.ap_invoices.generator.hardcases import rule_families, templates
from decision_benchmark.task_sets.ap_invoices.generator.reachability import DRAWS
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

from .test_families import built
from .test_my_tax_families import FLOOR, reach

GEN = SPEC.generation
SG_RULES = [r for r in GEN.rules if r.country == "SG"]
PROBLEM_TREATMENTS = {"GST_WRONGLY_CHARGED", "GST_UNDERCHARGED"}
ACTIONS = {"ACCOUNT_REVERSE_CHARGE_GST": "SG-8", "ACCOUNT_CUSTOMER_ACCOUNTING_GST": "SG-7"}
DUPLICATES = {"DUPLICATE_INVOICE", "NEAR_DUPLICATE"}


def sg_appearances(g) -> tuple[set[str], set[str]]:
    rules, problems = set(), set()
    for t in g.answer.tax_lines:
        rules.add(t.basis)
        if t.treatment in PROBLEM_TREATMENTS:
            problems.add(t.basis)
    for a in g.answer.buyer_actions:
        rules.add(a.basis or ACTIONS[a.action])
    if {f.code.value for f in g.answer.findings} & DUPLICATES:
        rules.add("SG-11")                       # a duplicate claim, caught by the duplicate check
    return rules, problems


@cache
def counts(n: int):
    total, problem = Counter(), Counter()
    for g in built(n).cases:
        if g.envelope.country == "SG":
            rules, problems = sg_appearances(g)
            total.update(rules)
            problem.update(problems)
    return total, problem


def test_one_family_per_singapore_rule():
    fams = rule_families()
    for r in SG_RULES:
        t = fams[r.id]
        assert t.countries == ["SG"] and t.ops[0].args == {"line": 1, "rule": r.id,
                                                           "form": PROBLEM if r.problem_form else CORRECT}
        assert t.primary_type == ("tax_problem" if r.problem_form else None)
    assert set(planting.SG_RECIPES) == {r.id for r in SG_RULES}
    assert {t.family for t in templates()["tax_problem"]} >= {f"tax_sg_{r.id.lower().replace('-', '_')}"
                                                              for r in SG_RULES if r.problem_form}


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_singapore_floors_are_met(n):
    total, problem = counts(n)
    assert not {r.id: total[r.id] for r in SG_RULES if total[r.id] < FLOOR[n]}
    if n == 2000:
        assert not {r.id: problem[r.id] for r in SG_RULES if r.problem_form and problem[r.id] < 2}
    if n == 500:
        assert sum(problem[r.id] for r in SG_RULES if r.problem_form and r.correct_form) >= 2


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_every_singapore_slot_rule_is_planted(n):
    by_index = {s.case_index: s for s in built(n).allocation.slots}
    for g in built(n).cases:
        if g.envelope.country == "SG":
            slot = by_index[int(g.built.case_id.rsplit("-", 1)[1])]
            rules, _ = sg_appearances(g)
            assert {u.rule for u in slot.rules} <= rules, g.built.case_id


def test_every_singapore_rule_is_reachable_on_50_draws():
    report = reach()
    for r in SG_RULES:
        forms = report[r.id]
        assert set(forms) == {f for f, ok in ((PROBLEM, r.problem_form), (CORRECT, r.correct_form)) if ok}
        for form, v in forms.items():
            assert v["agreed"] == v["draws"] == DRAWS, (r.id, form, v)


def test_rules_without_a_correct_form_include_sg12():
    assert {r.id for r in GEN.rules if not r.correct_form} == {"MS-9", "K-8", "SG-12"}


# -- mixed invoices ------------------------------------------------------------------------------------------------

SPLIT_FACTS = {"package_single_price", "materials_works_separated", "installation_separated",
               "itemised_consultation_fee", "education_fee_item"}
SPLIT_RULES = {"L-8", "P-12", "P-16", "MS-2"}


def mixed_kind(g) -> str | None:
    """'split' when a line turns on a §5-b split (its answer reads a split fact or comes from a split category), 'lines'
    when two lines have different outcomes, else None."""
    for entry in g.answer.facts or []:
        if set(entry) & SPLIT_FACTS:
            return "split"
    for t, line in zip(g.answer.tax_lines, g.envelope.payload.invoice.lines):
        profile = catalog().get(line.category).tax.get(g.envelope.country)
        defaults = set(getattr(profile, "facts", {}) or {})
        if t.basis in SPLIT_RULES and defaults & SPLIT_FACTS:
            return "split"
    return "lines" if len({(t.treatment, t.basis) for t in g.answer.tax_lines}) >= 2 else None


@pytest.mark.parametrize("n, total, split", [(2000, 240, 80), (500, 60, 20), (300, 36, 12)])
def test_mixed_quota_is_realised(n, total, split):
    kinds = {g.built.case_id: mixed_kind(g) for g in built(n).cases}
    by_index = {s.case_index: s for s in built(n).allocation.slots}
    for g in built(n).cases:
        slot = by_index[int(g.built.case_id.rsplit("-", 1)[1])]
        if slot.mixed == "split":
            assert kinds[g.built.case_id] == "split" and g.envelope.country == "MY", g.built.case_id
        elif slot.mixed == "lines":
            assert kinds[g.built.case_id] is not None, g.built.case_id
    assert sum(k is not None for k in kinds.values()) >= total
    assert sum(k == "split" for k in kinds.values()) >= split
