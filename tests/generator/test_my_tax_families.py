"""B1-4 acceptance (B1 plan section 7): one family per Malaysian rule; the Malaysian rule floors met in the built splits
(16 train, 4 test, 2 in 300 cases; problem forms 2 per rule in train, 2 per family in test); every rule reachable (50
draws per form, the engine agrees on each); each rule planted inside its rule-sheet window; the fact phrases read back."""

import json
import random
from collections import Counter
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from decision_benchmark.core.generator.slots import CORRECT, PROBLEM
from decision_benchmark.core.generator.spec import SplitSpec
from decision_benchmark.task_sets.ap_invoices.countries import pack
from decision_benchmark.task_sets.ap_invoices.countries.my import planting
from decision_benchmark.task_sets.ap_invoices.generator import phrases
from decision_benchmark.task_sets.ap_invoices.generator.hardcases import rule_families, templates
from decision_benchmark.task_sets.ap_invoices.generator.reachability import DRAWS, check
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

from .test_families import built

GEN = SPEC.generation
MY_RULES = [r for r in GEN.rules if r.country == "MY"]
FLOOR = {2000: 16, 500: 4, 300: 2}
PROBLEM_TREATMENTS = {"SST_SHOULD_BE_EXEMPT", "SST_WRONG_RATE", "SST_UNDERCHARGED", "SST_SUPPLIER_NOT_REGISTERED",
                      "SST_NOT_CHARGEABLE_BY_TRADER"}
ACTION_RULES = {"ISSUE_SELF_BILLED_EINVOICE": "ME-3", "ACCOUNT_IMPORTED_SERVICE_TAX": "MS-8"}


def appearances(g) -> tuple[set[str], set[str]]:
    """The rules that decide a non-null outcome in the key (B1 plan section 3.4), and those in a problem form."""
    rules, problems = set(), set()
    for t in g.answer.tax_lines:
        rules.add(t.basis)
        if t.treatment in PROBLEM_TREATMENTS:
            problems.add(t.basis)
    for a in g.answer.buyer_actions:
        rules.add(a.basis or ACTION_RULES[a.action])
    for f in g.answer.findings:
        if f.code.value == "MISSING_MANDATORY_FIELD":
            rules.add(f.evidence.get("rule", "ME-2"))
    return rules, problems


# -- families ------------------------------------------------------------------------------------------------------


def test_one_family_per_malaysian_rule():
    fams = rule_families()
    assert {r.id for r in MY_RULES} <= set(fams)
    for r in MY_RULES:
        t = fams[r.id]
        assert t.countries == ["MY"] and t.ops[0].op == "plant_rule" and t.ops[0].args["rule"] == r.id
        assert t.primary_type == ("tax_problem" if r.problem_form else None)          # drawn only for a problem
        assert t.ops[0].args["form"] == (PROBLEM if r.problem_form else CORRECT)
    assert set(planting.RECIPES) == {r.id for r in MY_RULES}
    assert not [t for t in templates()["tax_problem"] if t.family == "wrong_rate"]      # the placeholder is gone


# -- floors --------------------------------------------------------------------------------------------------------


@cache
def counts(n: int) -> tuple[Counter, Counter]:
    total, problem = Counter(), Counter()
    for g in built(n).cases:
        if g.envelope.country == "MY":
            rules, problems = appearances(g)
            total.update(rules)
            problem.update(problems)
    return total, problem


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_malaysian_floors_are_met(n):
    total, problem = counts(n)
    short = {r.id: total[r.id] for r in MY_RULES if total[r.id] < FLOOR[n]}
    assert not short, short
    if n == 2000:
        assert not {r.id: problem[r.id] for r in MY_RULES if r.problem_form and problem[r.id] < 2}
    if n == 500:
        by_family = Counter()
        for r in MY_RULES:
            if r.problem_form and r.correct_form:
                by_family[r.family] += problem[r.id]
        assert all(by_family[f] >= 2 for f in ("MS", "K", "L", "P", "MG"))


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_every_slot_rule_is_planted(n):
    """Each Malaysian rule appearance the allocator gave a slot is in the case's key."""
    by_index = {s.case_index: s for s in built(n).allocation.slots}
    for g in built(n).cases:
        if g.envelope.country != "MY":
            continue
        rules, _ = appearances(g)
        slot = by_index[int(g.built.case_id.rsplit("-", 1)[1])]
        assert {u.rule for u in slot.rules} <= rules, g.built.case_id


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_rules_are_planted_inside_their_windows(n):
    rules = {r.id: r for r in MY_RULES}
    for g in built(n).cases:
        day = g.envelope.payload.invoice.issue_date
        for rule in g.rules:
            if rule in rules:
                lo, hi = rules[rule].window(PROBLEM if rules[rule].problem_form and g.families[0] ==
                                            rule_families()[rule].family else CORRECT, GEN.windows["MY"])
                assert lo <= day <= hi, (g.built.case_id, rule, day)


# -- reachability --------------------------------------------------------------------------------------------------


@cache
def reach() -> dict:
    return check(GEN, SplitSpec(name="reach", n_cases=500, seed=2026112299))


def test_every_malaysian_rule_is_reachable_on_50_draws():
    report = reach()
    assert {r.id for r in MY_RULES} <= set(report)
    for r in MY_RULES:
        forms = report[r.id]
        assert set(forms) == {f for f, ok in ((PROBLEM, r.problem_form), (CORRECT, r.correct_form)) if ok}
        for form, v in forms.items():
            assert v["agreed"] == v["draws"] == DRAWS, (r.id, form, v)


def test_rules_without_a_correct_form():
    """MS-9 (undercharged) and K-8 (the unregistered co-owner) appear only as problems: their whole floor is
    problems, on tax slots."""
    assert {r.id for r in MY_RULES if not r.correct_form} == {"MS-9", "K-8"}
    assert all(set(reach()[r]) == {PROBLEM} for r in ("MS-9", "K-8"))


# -- windows and slots ---------------------------------------------------------------------------------------------


def test_rule_windows_lie_in_the_case_window():
    lo, hi = GEN.windows["MY"]
    for r in MY_RULES:
        for form, (a, b) in r.windows.items():
            assert lo <= a <= b <= hi, (r.id, form)
    w = {r.id: r.windows for r in MY_RULES}
    assert w["K-4"]["correct"] == (date(2025, 7, 1), date(2026, 6, 30))               # STP 2/2025 item 3
    assert w["P-20"]["problem"][1] == date(2025, 7, 31)                                # digital banking to 31 Jul 2025
    assert w["MG-3"]["problem"][1] == date(2025, 6, 30)                                # the 2025 orders from 1 Jul
    assert w["P-10"]["problem"][0] == date(2026, 7, 1)
    assert w["G-3"]["correct"] == (date(2026, 1, 1), date(2026, 8, 31))
    assert w["K-2"]["problem"][0] == date(2026, 1, 1)


@pytest.mark.parametrize("n", sorted(FLOOR))
def test_slots_keep_one_supplier_kind_and_a_common_date(n):
    rules = {r.id: r for r in GEN.rules}
    report = built(n).allocation.report()
    for s in report["slots"]:
        kinds = {rules[u["rule"]].supplier for u in s["rules"]} - {""}
        assert len(kinds) <= 1 and (not kinds or s["supplier"] in kinds)
        lacks = set(GEN.supplier_lacks.get(s["supplier"] or "", ()))
        assert not lacks & set().union(*(rules[u["rule"]].needs for u in s["rules"]))
        lo, hi = (date.fromisoformat(x) for x in s["window"])
        assert lo <= hi
        for u in s["rules"]:
            a, b = rules[u["rule"]].window(u["form"], GEN.windows[s["country"]])
            assert a <= lo and hi <= b
            assert not (rules[u["rule"]].domestic and s["foreign"])
        allowed = [set(rules[u["rule"]].companies) for u in s["rules"] if rules[u["rule"]].companies]
        if s["boundary"]:
            b = next(x for x in GEN.boundaries if x.country == s["country"] and x.day.isoformat() == s["boundary"]["day"])
            allowed += [set(b.companies)] if b.branch and b.companies else []
        assert not allowed or set(s["companies"]) == set.intersection(*allowed)


def test_each_company_has_the_special_suppliers():
    for cw in built(300).world["MY"]:
        assert set(cw.special) == {s.kind for s in pack("MY").generation.special_suppliers()}
    kinds = Counter(cw.kind for cw in built(300).world["MY"])
    assert set(kinds) == set(planting.COMPANY_KINDS)                                  # 6 companies, one of each


# -- phrases -------------------------------------------------------------------------------------------------------


def test_every_fact_phrase_reads_back():
    r = random.Random(1)
    samples = {"date": date(2025, 5, 3), "money": "1234.50", "share": "0.6"}
    for name, spec in phrases.bank("MY").items():
        values = list(spec["values"]) if spec["kind"] in ("enum", "bool") else [samples[spec["kind"]]]
        for value in values:
            for _ in range(3):
                text = f"Something else; {phrases.express('MY', name, value, r)}; more"
                assert phrases.parse("MY", name, text) == phrases.json_value("MY", name, value), (name, value)


def test_a_text_stating_two_values_reads_as_neither():
    with pytest.raises(phrases.PhraseError):
        phrases.parse("MY", "residential", "for a residential building; for a commercial building")
    with pytest.raises(phrases.PhraseError):
        phrases.parse("MY", "residential", "nothing about it")


def test_planting_report_gives_every_malaysian_rule():
    report = json.loads(json.dumps(built(2000).planting_report()))
    for r in MY_RULES:
        t = report["rules"][r.id]
        assert t["attempts"] > 0 and {"redraws", "causes", "first_diffs"} <= set(t)


# -- review of B1-4 ---------------------------------------------------------------------------------------------------


def my_built(n):
    return [g for g in built(n).cases if g.envelope.country == "MY"]


def test_company_turnover_fits_its_kind_and_fixes_its_phase():
    """SME kinds are below RM3m (exempt, never self-bill); the others spread over the four phases. The phase is the
    ME-1 timeline applied to the company's own record (no stated phase start)."""
    bands = {}
    for cw in built(2000).world["MY"]:
        facts = cw.company["tax_facts"]
        assert "einvoice_phase_start" not in facts
        bands[cw.kind] = facts["einvoice"]["turnover_band"]
        assert (planting.buyer_phase_start(cw.company) is None) == (cw.kind in planting.SME_KINDS)
    assert bands["msme"] == "below_1m" and bands["new_sme"] == "1m_to_3m"
    assert sorted(bands[k] for k in ("it", "fin", "builder", "plain")) == sorted(
        ["above_100m", "25m_to_100m", "5m_to_25m", "3m_to_5m"])


def test_self_billing_follows_the_buyers_own_phase():
    seen = Counter()
    for n in sorted(FLOOR):
        for g in my_built(n):
            if g.records.supplier(g.envelope.payload.supplier_id).country == "MY":
                continue
            start = planting.buyer_phase_start(export_company(g))
            billed = any(a.action == "ISSUE_SELF_BILLED_EINVOICE" for a in g.answer.buyer_actions)
            day = g.envelope.payload.invoice.issue_date
            assert billed == (start is not None and day >= start), g.built.case_id
            seen[(start is None, billed)] += 1
    assert seen[(True, False)] and seen[(False, True)] and seen[(False, False)]     # SMEs, in phase, not yet


def export_company(g) -> dict:
    return {"tax_facts": g.records.company.tax_facts.model_dump(mode="json")}


def test_only_the_p9_companies_are_ship_owners():
    for n in sorted(FLOOR):
        for cw in built(n).world["MY"]:
            kinds = cw.company["tax_facts"]["buyer_kinds"]
            assert kinds == (["registered_ship_owner"] if cw.kind in planting.SHIP_OWNER_KINDS else [])
    for g in my_built(2000):
        if "P-9" in g.rules:
            assert "registered_ship_owner" in g.records.company.tax_facts.buyer_kinds


@pytest.mark.parametrize("n, per_kind", [(2000, 3), (500, 2), (300, 1)])
def test_several_suppliers_of_each_special_kind(n, per_kind):
    world = built(n).world["MY"]
    for cw in world:
        assert all(len(sids) == per_kind for sids in cw.special.values())
    used: dict[str, set] = {}
    for g in my_built(n):
        sid = g.envelope.payload.supplier_id
        kind = next(cw for cw in world if cw.company_id == g.built.company_id).kind_of(sid)
        if kind and kind != "general":
            used.setdefault(kind, set()).add(g.records.supplier(sid).name)
    if per_kind > 1:
        cases = Counter()
        for g in my_built(n):
            k = next(cw for cw in world if cw.company_id == g.built.company_id).kind_of(g.envelope.payload.supplier_id)
            cases[k] += 1
        for kind, names in used.items():
            if cases[kind] >= 3 * per_kind:
                assert len(names) == per_kind, kind                 # every supplier of the kind is used


def test_foreign_invoices_state_their_own_currency_and_a_varying_rate():
    g_my = pack("MY").generation
    rates = {}
    for n in sorted(FLOOR):
        for g in my_built(n):
            supplier = g.records.supplier(g.envelope.payload.supplier_id)
            inv = g.envelope.payload.invoice
            if supplier.country == "MY":
                assert inv.currency == "MYR" and inv.exchange_rate is None
                continue
            assert inv.currency == g_my.foreign_currencies[supplier.country]
            base, _ = g_my.RATES[inv.currency]
            assert base * Decimal("0.95") <= inv.exchange_rate <= base * Decimal("1.05")
            rates.setdefault(inv.currency, set()).add(inv.exchange_rate)
    assert set(rates) == set(g_my.foreign_currencies.values())
    assert all(len(v) > 1 for v in rates.values())                    # never one constant rate


# -- in-window date branches --------------------------------------------------------------------------------------

MY_BRANCHES = [b for b in GEN.boundaries if b.country == "MY" and b.branch]


def test_every_in_window_boundary_has_a_branch_recipe_or_a_reason():
    days = {b.day for b in GEN.boundaries if b.country == "MY"}
    without = {b.day for b in GEN.boundaries if b.country == "MY" and not b.branch}
    assert without == {date(2025, 9, 1)}                     # P-9 for foreign-company buyers: no foreign buyers
    assert {b.branch for b in MY_BRANCHES} == set(planting.BRANCHES)
    assert {date(2024, 2, 26), date(2024, 3, 1), date(2024, 4, 1), date(2025, 7, 1)} <= days - without


@pytest.mark.parametrize("n, per_side", [(2000, 2), (500, 1)])
def test_each_branch_is_planted_on_both_sides(n, per_side):
    cases = Counter()
    for g in my_built(n):
        if g.branch:
            name, side = g.branch.split(":")
            b = next(x for x in MY_BRANCHES if x.branch == name)
            day = g.envelope.payload.invoice.issue_date
            assert (day < b.day) == (side == "before") and abs((day - b.day).days) <= 31, g.built.case_id
            cases[(name, side)] += 1
    for b in MY_BRANCHES:
        for side in ("before", "after"):
            assert cases[(b.branch, side)] >= per_side, (b.branch, side)
