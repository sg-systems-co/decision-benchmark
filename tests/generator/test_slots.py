"""B1-1 acceptance: the slot allocator gives the exact tables of B1 plan §3 for 2,000 / 500 / 300 cases, and an
infeasible demand fails loudly. §3.1 and §3.2 are read from the plan itself, so the plan and the allocator can't drift
apart silently; the other numbers are quoted from the plan next to each assertion."""

import re
from collections import Counter
from datetime import date, timedelta
from functools import cache
from pathlib import Path

import pytest

from decision_benchmark.core.generator.cli import release_splits
from decision_benchmark.core.generator.quotas import InfeasibleDemand
from decision_benchmark.core.generator.slots import H1, H2, H3, PROBLEM, allocate
from decision_benchmark.core.generator.spec import Generation, SplitSpec
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

ROOT = Path(__file__).resolve().parents[2]
PLAN = (ROOT / "docs/plans/b1-generator-v0.10.md").read_text(encoding="utf-8")
GEN = SPEC.generation
SIZES = (2000, 500, 300)
COLUMN = {2000: 0, 500: 1, 300: 2}
"""The plan's tables have the columns Train (2,000), Test (500) and a third split of 300."""
TYPE_ROWS = {
    "Clean": "clean", "Tax problem": "tax_problem", "Price mismatch": "price_mismatch",
    "Quantity mismatch": "quantity_mismatch", "Invalid invoice / missing fields": "invalid_invoice",
    "Duplicate": "duplicate", "Not received": "not_received", "No PO / above limit": "no_po_or_above_limit",
    "Changed bank details": "bank_change", "Ambiguous (HAND_OVER)": "ambiguous",
}


@cache
def report(n: int) -> dict:
    split = SplitSpec(name=f"n{n}", n_cases=n, seed=2026112200 + n)
    return allocate(GEN, dict(SPEC.quotas), split).report()


def _number(cell: str) -> int:
    return int(re.sub(r"[^\d]", "", cell.split("(")[0]))


def plan_table(heading: str) -> dict[str, list[int]]:
    """Rows of the first markdown table after a heading: first cell -> the last three numeric cells."""
    part = PLAN[PLAN.index(heading):]
    rows = {}
    for line in part.splitlines()[1:]:
        if line.startswith("#"):
            break
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.search(r"\d", cells[-1]) and not set(cells[-1]) <= set("-: "):
            rows[cells[0]] = [_number(c) for c in cells[-3:]]
    return rows


# -- §3.1 exception mix ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", SIZES)
def test_exception_mix_is_the_plan_table(n):
    table = plan_table("### 3.1 Exception mix")
    r = report(n)
    for label, name in TYPE_ROWS.items():
        assert r["exception_mix"][name]["total"] == table[label][COLUMN[n]], label
    assert sum(v["total"] for v in r["exception_mix"].values()) == table["Total"][COLUMN[n]] == n
    assert r["two_problems"]["total"] == next(v for k, v in table.items() if k.startswith("Two problems"))[COLUMN[n]]


@pytest.mark.parametrize("n", SIZES)
def test_countries_split_each_type_evenly(n):
    r = report(n)
    for name, cell in r["exception_mix"].items():
        assert abs(cell["MY"] - cell["SG"]) <= 1, name
    assert r["countries"] == {"MY": n // 2, "SG": n // 2}


@pytest.mark.parametrize("n", SIZES)
def test_two_problems_respect_tiers_and_pairs(n):
    slots = report(n)["slots"]
    pairs = {tuple(p) for p in GEN.two_problems.pairs}
    for s in slots:
        if s["secondary"]:
            assert (s["primary"], s["secondary"]) in pairs
            assert GEN.type(s["secondary"]).tier > GEN.type(s["primary"]).tier
        assert not (GEN.type(s["primary"]).handover and s["secondary"])


# -- §3.2 hard cases ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", SIZES)
def test_hard_cases_are_the_plan_table(n):
    table = plan_table("### 3.2 Hard cases")
    h = report(n)["hard"]
    col = COLUMN[n]
    assert h["total"] == table["Hard total (50%)"][col]
    assert h[H1] == next(v for k, v in table.items() if k.startswith("H1"))[col]
    assert h[H3] == next(v for k, v in table.items() if k.startswith("H3"))[col]
    assert h[H2] == next(v for k, v in table.items() if k.startswith("H2"))[col]
    assert h[H1] <= h["scan_only_cap"] == h["total"] // 3          # cap ⌊hard / 3⌋ = 333 / 83 / 50
    assert h["row_cap"] == {2000: 160, 500: 40, 300: 24}[n]           # §3.2: at most 160 / 40 / 24 per row
    assert max(h["rows"].values()) <= h["row_cap"]
    assert sum(h["rows"].values()) == h[H2]


@pytest.mark.parametrize("n", SIZES)
def test_hard_kinds_go_where_the_plan_says(n):
    r = report(n)
    rows = {row.id: row for row in GEN.hard_cases.rows}
    for s in r["slots"]:
        if s["hard"] == H3:
            assert GEN.type(s["primary"]).handover                     # H3 only in Ambiguous slots
        if s["hard"] == H2:
            assert s["country"] in rows[s["row"]].countries and s["primary"] in rows[s["row"]].types
        else:
            assert s["row"] is None
    for name, share in r["hard"]["share_by_type"].items():
        if not GEN.type(name).handover:
            assert 30 <= float(share) <= 70, name                     # each type's hard share in 30-70%


@pytest.mark.parametrize("n", SIZES)
def test_scan_only_is_spread_in_proportion_to_the_types(n):
    r = report(n)
    h1 = Counter(s["primary"] for s in r["slots"] if s["hard"] == H1)
    for name, cell in r["exception_mix"].items():
        expected = r["hard"][H1] * cell["total"] / n
        assert abs(h1[name] - expected) <= 2, name


# -- §3.3 mixed and lines --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", SIZES)
def test_mixed_cases_and_lines(n):
    r = report(n)
    m = r["mixed"]
    assert m["total"] == {2000: 240, 500: 60, 300: 36}[n]             # §3.3: 240 / 60 / 36
    assert m["split"] == m["total"] // 3                               # a third are Malaysian §5-b cases
    for s in r["slots"]:
        if s["mixed"] == "split":
            assert s["country"] == "MY"
        if s["mixed"] == "lines":
            assert s["lines"] >= 2
        if s["mixed"]:
            assert not GEN.type(s["primary"]).handover
    cases = r["lines"]["cases"]
    assert cases["1"] == n * 45 // 100 and cases["2"] == n * 30 // 100 and cases["3"] == n * 15 // 100
    assert cases["4"] + cases["5"] + cases["6"] == n // 10 and max(cases["4"], cases["5"], cases["6"]) - min(
        cases["4"], cases["5"], cases["6"]) <= 1
    assert abs(r["lines"]["total"] / n - 2.0) < 0.01                  # mean about 2.0


# -- §3.4 rule floor -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n, per_rule, my, sg", [(2000, 16, 992, 208), (500, 4, 248, 52), (300, 2, 124, 26)])
def test_rule_floor_is_the_plan_table(n, per_rule, my, sg):
    f = report(n)["rule_floor"]
    assert f["per_rule"] == per_rule
    assert all(v["total"] == per_rule for v in f["rules"].values())
    assert f["by_country"] == {"MY": my, "SG": sg}                     # §3.4: 248 / 52 test, 992 / 208 train
    assert f["total"] == 75 * per_rule                                 # 300 test, 1,200 train
    assert len(f["rules"]) == 75


def test_problem_form_floors():
    train = report(2000)["rule_floor"]["rules"]
    problem_rules = [r for r in GEN.rules if r.problem_form]
    assert sum(r.country == "MY" for r in problem_rules) == 52 and sum(r.country == "SG" for r in problem_rules) == 6
    assert all(train[r.id]["problem"] >= 2 for r in problem_rules)    # train: at least 2 per rule
    only_problem = [r for r in GEN.rules if not r.correct_form]
    assert sorted(r.id for r in only_problem) == ["K-8", "MS-9", "SG-12"]   # undercharged (both); the unregistered co-owner
    assert all(train[r.id]["problem"] == 16 for r in only_problem)    # every appearance a problem form
    assert sum(v["problem"] for v in train.values()) == 2 * 58 + 3 * 14  # 104 MY + 12 SG, plus 14 more for each of the 3
    test = report(500)["rule_floor"]["problem_by_family"]
    for fam in ("MY:L", "MY:P", "MY:MG"):
        assert test[fam] == 2, fam                                     # test: 2 per family
    assert test["MY:MS"] == test["MY:K"] == test["SG:SG"] == 2 + 4    # MS-9, K-8, SG-12: all 4 of theirs are problems
    report_500 = report(500)["rule_floor"]["rules"]
    assert report_500["MS-9"]["problem"] == report_500["K-8"]["problem"] == 4


@pytest.mark.parametrize("n", SIZES)
def test_rule_appearances_fit_their_slots(n):
    rules = {r.id: r for r in GEN.rules}
    for s in report(n)["slots"]:
        ids = [u["rule"] for u in s["rules"]]
        assert len(ids) == len(set(ids))                               # a rule counts at most once per case
        assert not (ids and GEN.type(s["primary"]).handover)          # HAND_OVER appearances don't count
        assert sum(u["carrier"] == "line" for u in s["rules"]) <= s["lines"]
        for u in s["rules"]:
            r = rules[u["rule"]]
            assert r.country == s["country"]
            assert s["foreign"] or not r.foreign
            if u["form"] == PROBLEM:
                assert "tax_problem" in (s["primary"], s["secondary"])
            elif r.types:
                assert set(r.types) & {s["primary"], s["secondary"]}


# -- §3.4 date-boundary floor ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n, per_side", [(2000, 2), (500, 1), (300, 0)])
def test_date_boundary_floor(n, per_side):
    r = report(n)
    for b in GEN.boundaries:
        for side in ("before", "after"):
            assert r["date_boundaries"].get(f"{b.country}:{b.day.isoformat()}:{side}", 0) == per_side
    lo_hi = {c: (str(a), str(b)) for c, (a, b) in GEN.windows.items()}
    for s in r["slots"]:
        lo, hi = s["window"]
        assert lo_hi[s["country"]][0] <= lo <= hi <= lo_hi[s["country"]][1]
        if s["boundary"]:
            day = s["boundary"]["day"]
            if s["boundary"]["side"] == "before":
                assert hi < day and (lo >= str(GEN.windows[s["country"]][0]))
            else:
                assert lo == day
            span = date.fromisoformat(hi) - date.fromisoformat(lo)
            assert span <= timedelta(days=30)


# -- determinism, release seeds --------------------------------------------------------------------------------------


def test_allocation_is_deterministic_and_seeded():
    split = SplitSpec(name="x", n_cases=500, seed=11)
    a = allocate(GEN, dict(SPEC.quotas), split).report()
    assert a == allocate(GEN, dict(SPEC.quotas), split).report()
    b = allocate(GEN, dict(SPEC.quotas), SplitSpec(name="x", n_cases=500, seed=12)).report()
    assert a["slots"] != b["slots"] and a["hard"][H2] == b["hard"][H2]
    assert sorted(s["case_index"] for s in a["slots"]) == list(range(1, 501))


def test_release_seeds_are_train_and_test():
    splits = release_splits(SPEC)
    assert {k: v.n_cases for k, v in splits.items()} == {"train": 2000, "test": 500}
    assert len({v.seed for v in splits.values()}) == 2


# -- infeasible demands fail loudly ------------------------------------------------------------------------------------


def _gen(**changes) -> Generation:
    return GEN.model_copy(update=changes)


def test_an_impossible_rule_floor_names_the_rule():
    tiers = (GEN.rule_floor[0].model_copy(update={"min_cases": 100, "per_rule": 40, "problem_per_rule": 0}),)
    with pytest.raises(InfeasibleDemand, match=r"rule floor: \S+ \((problem|correct)\) placed \d+ of"):
        allocate(_gen(rule_floor=tiers), dict(SPEC.quotas), SplitSpec(name="x", n_cases=100, seed=1))


def test_a_quota_that_isnt_whole_fails():
    with pytest.raises(InfeasibleDemand, match="not a whole number"):
        allocate(GEN, dict(SPEC.quotas), SplitSpec(name="x", n_cases=250, seed=1))


def test_a_row_cap_too_small_fails():
    hc = GEN.hard_cases.model_copy(update={"conflict_row_cap": "1/20"})
    with pytest.raises(InfeasibleDemand, match="no precedence row under the cap"):
        allocate(_gen(hard_cases=hc), dict(SPEC.quotas), SplitSpec(name="x", n_cases=500, seed=1))


def test_a_scan_only_share_over_its_cap_fails():
    hc = GEN.hard_cases.model_copy(update={"scan_only_share_of_hard": "40"})
    with pytest.raises(InfeasibleDemand, match="exceeds its cap"):
        allocate(_gen(hard_cases=hc), dict(SPEC.quotas), SplitSpec(name="x", n_cases=500, seed=1))


def test_a_hard_share_outside_the_band_fails():
    hc = GEN.hard_cases.model_copy(update={"type_hard_share_band": ("55", "70")})
    with pytest.raises(InfeasibleDemand, match="outside 55-70%"):
        allocate(_gen(hard_cases=hc), dict(SPEC.quotas), SplitSpec(name="x", n_cases=500, seed=1))


def test_too_many_boundaries_fail():
    tiers = (GEN.boundary_floor[1].model_copy(update={"per_side": 200}),)
    with pytest.raises(InfeasibleDemand, match="boundary"):
        allocate(_gen(boundary_floor=tiers), dict(SPEC.quotas), SplitSpec(name="x", n_cases=500, seed=1))
