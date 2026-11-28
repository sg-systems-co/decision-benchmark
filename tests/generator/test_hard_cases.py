"""B1-6, hard cases (B1 plan section 3.2): the hard quotas are exact and the scan-only cap holds; every scan-only case
ships as a scan, photo or PDF only; every conflicting-documents case passes the counterfactual check (the invoice's
value A in the governing document changes the key); every missing-information case passes the null-fact check (the
fact is stated nowhere, and stating it ends the hand-over); facts stated in an email are cited by spans that read back.
"""

from collections import Counter
from fractions import Fraction

import pytest

from decision_benchmark.core.generator.quotas import as_fraction
from decision_benchmark.task_sets.ap_invoices.generator import phrases
from decision_benchmark.task_sets.ap_invoices.generator.build import fact_parser
from decision_benchmark.task_sets.ap_invoices.generator.hard import check_conflict, check_missing
from decision_benchmark.task_sets.ap_invoices.generator.statements import check_evidence

from .test_clean_base import case_docs
from .test_families import GEN, built

HARD = {2000: {"H1": 320, "H2": 640, "H3": 40}, 500: {"H1": 80, "H2": 160, "H3": 10}, 300: {"H1": 48, "H2": 96, "H3": 6}}
"""B1 plan section 3.2: scan-only, conflicting documents, missing information per split."""


@pytest.mark.parametrize("n", sorted(HARD))
def test_hard_kinds_are_exact_and_scan_only_stays_under_its_cap(n):
    kinds = Counter(g.hard for g in built(n).cases if g.hard)
    assert dict(kinds) == HARD[n]
    assert kinds["H1"] <= sum(kinds.values()) * as_fraction(GEN.hard_cases.scan_only_cap_of_hard)


@pytest.mark.parametrize("n", sorted(HARD))
def test_scan_only_cases_ship_as_a_scan_photo_or_pdf_only(n):
    cases = [g for g in built(n).cases if g.hard == "H1"]
    modality = Counter(g.envelope.modality for g in cases)
    assert set(modality) <= {"scan", "photo", "pdf"}
    assert abs(Fraction(modality["scan"], len(cases)) - Fraction(4, 10)) <= Fraction(1, 10)
    assert all(g.export()["scan_only"] for g in cases)
    assert all(g.envelope.modality == "pdf" and not g.export()["scan_only"] for g in built(n).cases if g.hard != "H1")


@pytest.mark.parametrize("n", sorted(HARD))
def test_every_conflicting_documents_case_changes_its_key_with_the_invoices_value(n):
    cap = int(HARD[n]["H2"] * as_fraction(GEN.hard_cases.conflict_row_cap))
    rows = Counter()
    for g in built(n).cases:
        if g.hard != "H2":
            continue
        assert g.row and g.conflict and g.conflict["row"] == g.row, g.built.case_id
        assert not check_conflict(g), (g.built.case_id, check_conflict(g))
        rows[g.row] += 1
    assert max(rows.values()) <= cap
    assert set(rows) == {r.id for r in GEN.hard_cases.rows}            # every precedence row is planted


@pytest.mark.parametrize("n", sorted(HARD))
def test_every_missing_information_case_hands_over_on_a_fact_stated_nowhere(n):
    cases = [g for g in built(n).cases if g.hard == "H3"]
    assert cases and all(g.envelope.payload.exception_types == ["ambiguous"] for g in cases)
    for g in cases:
        assert g.answer.answer_source.value == "handover_by_construction"
        assert not check_missing(g), (g.built.case_id, check_missing(g))


def test_the_missing_facts_vary():
    facts = Counter((g.envelope.country, m["fact"]) for g in built(2000).cases if g.hard == "H3" for m in g.missing)
    assert len({f for c, f in facts if c == "MY"}) >= 3 and len({f for c, f in facts if c == "SG"}) >= 3


@pytest.mark.parametrize("n", [2000, 500])
def test_facts_stated_in_an_email_are_cited_by_spans_that_read_back(n):
    spans = 0
    for g in built(n).cases:
        facts = g.answer.model_dump(mode="json")["facts"] or []
        cited = [r for e in facts for k, v in e.items() if k != "line_no" for r in v.get("evidence", [])
                 if r.get("span")]
        spans += len(cited)
        if cited:
            assert not check_evidence(facts, case_docs(g), fact_parser(g.envelope.country)), g.built.case_id
    assert spans > 0


def test_every_conflict_phrase_fills_from_the_case():
    values = {"number": "W10-1808-31000123", "signed": "15 April 2025", "country": "Singapore", "price": "MYR 120.00"}
    for country in ("MY", "SG"):
        for row, templates in phrases.conflicts(country).items():
            for t in templates:
                assert "{" not in t.format(**values), (country, row, t)
