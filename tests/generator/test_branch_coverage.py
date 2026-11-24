"""Branch coverage (review of B1-5): report/branches.json lists every branch the rules engine can decide, for every
plantable rule in both countries, with its planted count; each in-window branch is planted in at least 2 train cases
and 1 test case, or content/generator/branch_reasons.yaml gives the reason (hand-over branches: HAND_OVER only).
generator/branches.py reads the branches off the engine's code; the counts come from re-running the engine on each
built case."""

from functools import cache

import pytest

from decision_benchmark.task_sets.ap_invoices.countries import pack
from decision_benchmark.task_sets.ap_invoices.generator.branches import HAND_OVER_ONLY, index_for, reasons
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

from .test_families import built

GEN = SPEC.generation
FLOOR = {2000: 2, 500: 1}
"""The branch floor: cases per branch in train and in test."""
COUNTRIES = sorted({r.country for r in GEN.rules if pack(r.country).generation.plants_rules})


@cache
def table(n: int) -> dict:
    return built(n).branch_report(GEN)["branches"]


def below_floor() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for c in COUNTRIES:
        out[c] = {bid for bid, b in table(2000)[c].items() if b["kind"] != "hand_over"
                  and (b["cases"] < FLOOR[2000] or table(500)[c][bid]["cases"] < FLOOR[500])}
    return out


def test_every_plantable_rule_has_branches():
    for c in COUNTRIES:
        rules = {b["rule"] for b in table(2000)[c].values()}
        assert {r.id for r in GEN.rules if r.country == c} <= rules, c


def test_the_table_lists_both_countries_and_every_branch_kind():
    assert COUNTRIES == ["MY", "SG"]
    kinds = {b["kind"] for c in COUNTRIES for b in table(2000)[c].values()}
    assert kinds == {"decision", "hand_over", "path", "fact"}


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_each_branch_meets_the_floor_or_has_its_reason(country):
    missing = below_floor()[country] - set(reasons().get(country, {}))
    assert not missing, sorted(missing)


def test_the_reasons_are_current():
    """Every reason names a branch the engine still has and the splits still don't plant at the floor."""
    low = below_floor()
    for c, entries in reasons().items():
        assert set(entries) <= set(table(2000)[c]), sorted(set(entries) - set(table(2000)[c]))
        assert set(entries) <= low[c], sorted(set(entries) - low[c])


def test_the_report_gives_each_low_branch_its_reason():
    for c in COUNTRIES:
        for bid, b in table(2000)[c].items():
            if b["kind"] == "hand_over":
                assert b["reason"] == HAND_OVER_ONLY
            elif bid in below_floor()[c]:
                assert b["reason"], bid
            else:
                assert b["reason"] is None, bid


def test_the_review_branches_are_planted():
    """Review of B1-5, A-D: SG-4's three suppliers, SG-8's imports and buyers, SG-9's de minimis buyer, SG-10's
    claimable exceptions."""
    sg = table(2000)["SG"]
    planted = {bid for bid, b in sg.items() if b["cases"] >= FLOOR[2000] and table(500)["SG"][bid]["cases"] >= 1}
    expected = {
        "SG-4 rules._not_entitled return#1", "SG-4 rules._not_entitled return#2", "SG-4 rules._not_entitled return#3",
        "SG-8 reverse_charge.uncharged#1", "SG-8 fact low_value_goods_reverse", "SG-8 fact de_minimis_alone",
        "SG-8 fact group_member", "SG-8 fact group_de_minimis", "SG-9 fact de_minimis_claims_all",
        "SG-10 claim._regulations#2", "SG-10 claim._regulations#3", "SG-10 claim._regulations#4 CLAIMABLE",
        "SG-10 claim._depends#2 via claim#1 CLAIMABLE", "SG-10 claim._depends#2 via claim#2 CLAIMABLE",
        "SG-10 claim._depends#2 via claim#3 CLAIMABLE",
    }
    assert expected <= planted, sorted(expected - planted)


def test_the_index_reads_each_country_once_and_stably():
    a = [b.id for b in index_for("SG", {r.id for r in GEN.rules}).branches()]
    assert a == list(table(500)["SG"]) and len(a) == len(set(a))
