"""B1-2 acceptance (B1 plan section 7): 500 clean cases per country with planted = found; every gold fact's evidence
resolves in a document of the case; the reference row reproduces every key from its gold facts; 100 cases built twice
are byte-identical. Plus the entities: companies 60 / 20 / 12, half per country, with suppliers, people, policy packs,
contracts, certificates and history, names disjoint between train and test."""

from collections import Counter
from datetime import date
from functools import cache

import pytest

from decision_benchmark.core.generator.cli import release_splits
from decision_benchmark.core.generator.spec import SplitSpec
from decision_benchmark.core.model import export_dict
from decision_benchmark.task_sets.ap_invoices.countries import pack
from decision_benchmark.task_sets.ap_invoices.generator.build import build_clean, compare, fact_parser
from decision_benchmark.task_sets.ap_invoices.generator.entities import build_world, catalog
from decision_benchmark.task_sets.ap_invoices.generator.statements import EvidenceError, Statements, check_evidence, resolve
from decision_benchmark.task_sets.ap_invoices.models import CompanyRecords
from decision_benchmark.task_sets.ap_invoices.rules import check_rules
from decision_benchmark.task_sets.ap_invoices.spec import SPEC

GEN, QUOTAS = SPEC.generation, dict(SPEC.quotas)
RELEASE = release_splits(SPEC)
BIG = SplitSpec(name="clean-500", n_cases=2500, seed=20261123)
"""A 2,500-case split has 1,000 clean slots: 500 per country."""


@cache
def big():
    return build_clean(GEN, QUOTAS, BIG)


@cache
def world(name: str):
    split = RELEASE.get(name) or SplitSpec(name=name, n_cases=300, seed=99)
    return build_world(GEN, split)


def case_docs(g) -> dict[str, dict]:
    """The case's documents as exported (internal fields removed), by doc id."""
    inv = g.envelope.payload.invoice
    docs = {inv.invoice_id: export_dict(inv)}
    for po in g.records.purchase_orders:
        docs[po.po_number] = export_dict(po)
    for gr in g.records.goods_receipts:
        docs[gr.gr_number] = export_dict(gr)
    supplier = g.records.supplier(g.envelope.payload.supplier_id)
    docs[f"supplier:{supplier.supplier_id}"] = export_dict(supplier)
    docs[f"company:{g.records.company.company_id}"] = export_dict(g.records.company)
    for email in g.records.emails:
        if email.case_id == g.built.case_id:
            docs[email.message_id] = export_dict(email)
    return docs


# -- 500 clean cases per country, planted = found ------------------------------------------------------------------


def test_500_clean_cases_per_country_with_planted_equal_to_found():
    b = big()
    assert Counter(g.envelope.country for g in b.cases) == {"MY": 500, "SG": 500}
    for g in b.cases:
        assert not compare(g.built.planted, g.answer), g.built.case_id
        assert g.answer.decision.value == "APPROVE" and g.answer.answer_source.value == "rules"
    report = b.planting_report()
    assert report["redraws"] <= report["cases"] // 100          # overall redraw rate at most 1% (plan section 4)


def test_clean_cases_cover_both_kinds_and_the_whole_window():
    b = big()
    bases = Counter((g.envelope.country, t.basis) for g in b.cases for t in g.answer.tax_lines)
    assert {("MY", "MS-2"), ("MY", "MG-2"), ("SG", "SG-1")} <= set(bases)
    for country, (lo, hi) in GEN.windows.items():
        days = [g.envelope.payload.invoice.issue_date for g in b.cases if g.envelope.country == country]
        assert min(days) - lo < (hi - lo) / 10 and hi - max(days) < (hi - lo) / 10
    # Every company but the reserved kinds (generation.yaml reserved_companies), which take only the cases whose rule
    # appearances name them.
    kinds = {cw.company_id: cw.kind for cws in b.world.values() for cw in cws}
    assert len(kinds) == 60
    ordinary = {cid for cid, kind in kinds.items() if kind not in GEN.reserved_companies}
    assert ordinary <= {g.built.company_id for g in b.cases}
    for g in b.cases:
        if kinds[g.built.company_id] in GEN.reserved_companies:
            assert any(kinds[g.built.company_id] in t.companies for r in GEN.rules if r.id in g.rules
                       for turns in r.appearance_turns.values() for t in turns), g.built.case_id


# -- evidence, reference row, reproducibility --------------------------------------------------------------------


def test_every_gold_fact_has_evidence_that_resolves():
    b = big()
    stated = 0
    for g in b.cases:
        facts = g.answer.facts or []
        stated += sum(len(entry) - 1 for entry in facts)
        assert not check_evidence(facts, case_docs(g), fact_parser(g.envelope.country)), g.built.case_id
    assert stated > 500                                          # the registry states facts the rules read


def test_reference_row_reproduces_every_key():
    for g in big().cases:
        lines = [dict(entry) for entry in g.answer.facts or []]
        for entry in lines:
            for name, fact in list(entry.items()):
                if name != "line_no":
                    entry[name] = {"value": fact["value"]}
        result = check_rules(g.records, g.envelope, lines, catalog())
        got = [(x.line_no, x.treatment, x.basis) for x in result.lines]
        assert got == [(t.line_no, t.treatment, t.basis) for t in g.answer.tax_lines], g.built.case_id
        actions = []
        for x in result.lines:
            actions += [a for a in x.buyer_actions if a not in actions]
        assert actions == g.answer.buyer_actions, g.built.case_id


def test_100_cases_built_twice_are_byte_identical():
    split = RELEASE["test"]
    first = build_clean(GEN, QUOTAS, split, limit=100).dumps()
    assert first == build_clean(GEN, QUOTAS, split, limit=100).dumps()
    assert first.count("\n") == 100


def test_release_splits_have_the_plan_clean_counts():
    assert len(build_clean(GEN, QUOTAS, RELEASE["test"]).cases) == 200
    assert len(big().cases) == 1000


# -- the statement registry ----------------------------------------------------------------------------------------


def test_statements_read_values_from_the_document():
    st = Statements()
    st.document("INV-1", {"service_period_start": "2026-01-01", "lines": [{"description": "x"}]})
    line: dict = {}
    assert st.state(line, "service_period_start", "INV-1", "service_period_start") == "2026-01-01"
    assert line["facts"]["service_period_start"]["evidence"] == [{"doc_id": "INV-1", "path": "service_period_start"}]
    assert resolve(st.docs["INV-1"], "lines[0].description") == "x"
    with pytest.raises(EvidenceError):
        st.state(line, "x", "INV-1", "missing")
    bad = [{"line_no": 1, "service_period_start": {"value": "2026-02-01", "evidence": [
        {"doc_id": "INV-1", "path": "service_period_start"}]}, "delivery_date": {"value": "2026-01-02", "evidence": [
        {"doc_id": "GR-9", "path": "gr_date"}]}}]
    problems = check_evidence(bad, st.docs)
    assert len(problems) == 2 and "not '2026-02-01'" in problems[0] and "not a document" in problems[1]


# -- entities ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name, n", [("train", 60), ("test", 20), ("x300", 12)])
def test_companies_per_split(name, n):
    w = world(name)
    assert {c: len(v) for c, v in w.items()} == {"MY": n // 2, "SG": n // 2}


def test_company_records_are_complete_and_valid():
    roles = {c.gl_role for c in catalog().categories}
    for country, companies in world("test").items():
        for cw in companies:
            records = CompanyRecords.model_validate(cw.records())
            special = len(pack(country).generation.special_suppliers()) * GEN.special_per_kind(500)
            assert 15 + special <= len(records.suppliers) <= 30 + special and 4 <= len(records.company.people) <= 8
            assert {p.approval_role for p in records.company.people} >= {"ops_manager", "director"}
            assert {a.role for a in records.company.policy_pack.chart_of_accounts} == roles
            assert records.ledger and not [e for e in records.emails if e.case_id or e.signals]
            lo = GEN.windows[country][0]
            assert min(e.invoice.issue_date for e in records.ledger) < lo     # history starts before the window
            transitional = {sid for k in ("k4_landlord", "l1_contractor") for sid in cw.special.get(k, [])}
            for k in records.contracts:
                # Ordinary contracts have a price-review clause (no K-4 or L-1); the landlord and the contractor
                # the K-4 and L-1 recipes use hold contracts signed and stamped before the transitional dates without.
                assert k.has_price_review_clause != (k.supplier_id in transitional) and k.signed_on < date(2025, 6, 9)
            foreign = {s.supplier_id for s in records.suppliers if s.country != country}
            assert {c.supplier_id for c in records.residence_certificates} <= foreign


def test_history_rates_are_right_for_their_dates():
    from decision_benchmark.task_sets.ap_invoices.countries import pack

    for country, companies in world("test").items():
        g = pack(country).generation
        for cw in companies[:3]:
            for entry in cw.ledger:
                day = date.fromisoformat(entry["invoice"]["issue_date"])
                supplier = cw.supplier(entry["supplier_id"])
                for line in entry["invoice"]["lines"]:
                    clean = g.clean_line(catalog().get(line["category"]), day, cw.company, supplier,
                                         cw.kind_of(supplier["supplier_id"]))
                    assert clean is not None and str(clean.rate) == line["tax_rate"]


SPLITS = ("train", "test", "x300")
"""One split per partition: train (0), test (1), any other split (2)."""


def identities(w) -> dict[str, set[str]]:
    """Everything that identifies a party in one split's world, by kind."""
    out: dict[str, set[str]] = {k: set() for k in ("company", "supplier", "person", "tax_id", "registration_no",
                                                   "bank_account", "certificate")}
    for companies in w.values():
        for cw in companies:
            out["company"].add(cw.company["legal_name"])
            out["person"] |= {p["name"] for p in cw.company["people"]}
            out["registration_no"].add(cw.company["registration_no"])
            out["certificate"] |= {c["number"] for c in cw.company["policy_pack"]["exemption_certificates"]}
            for party in (cw.company, *cw.suppliers):
                out["tax_id"] |= {r["number"] for r in party.get("tax_registrations", [])}
            for s in cw.suppliers:
                out["supplier"].add(s["name"])
                out["person"] |= {c["name"] for c in s["contacts"]}
                out["registration_no"].add(s["registration_no"])
                out["bank_account"].add(s["bank_account"]["account_no"])
    return out


def test_no_name_or_identifier_appears_in_two_splits():
    ids = {name: identities(world(name)) for name in SPLITS}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            for kind in ids[a]:
                assert not ids[a][kind] & ids[b][kind], (a, b, kind, sorted(ids[a][kind] & ids[b][kind])[:3])
    for kind, values in ids["train"].items():
        assert values, kind


def test_every_name_and_identifier_is_in_its_splits_partition():
    from decision_benchmark.task_sets.ap_invoices.generator.entities import N_PARTITIONS, name_partition, partition

    for name in SPLITS:
        part = partition(RELEASE.get(name) or SplitSpec(name=name, n_cases=300, seed=99))
        assert part == SPLITS.index(name)
        found = identities(world(name))
        for kind in ("company", "supplier", "person"):
            for value in found[kind]:
                stem = value.removesuffix(" Sdn Bhd").removesuffix(" Pte Ltd")
                assert name_partition(stem) == part, (kind, value)
        for kind in ("tax_id", "registration_no", "bank_account", "certificate"):
            for value in found[kind]:
                assert int([ch for ch in value if ch.isdigit()][-1]) % N_PARTITIONS == part, (kind, value)


def test_a_shared_supplier_name_is_one_supplier():
    shared = 0
    for name in SPLITS:
        for companies in world(name).values():
            seen: dict[str, dict] = {}
            for cw in companies:
                for s in cw.suppliers:
                    key = {"regs": s.get("tax_registrations"), "registration_no": s["registration_no"],
                           "bank": s["bank_account"], "country": s["country"], "categories": cw.categories[s["supplier_id"]],
                           "facts": s.get("tax_facts")}
                    if s["name"] in seen:
                        shared += 1
                        assert seen[s["name"]] == key, s["name"]
                    seen[s["name"]] = key
    assert shared > 100                                            # common suppliers do recur across companies


def test_company_names_are_distinct_in_a_split():
    for name in SPLITS:
        legal = [cw.company["legal_name"] for cs in world(name).values() for cw in cs]
        assert len(legal) == len(set(legal))
