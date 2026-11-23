"""Planting limits (B1 plan section 3.5), run over every generated case. Each PR that builds the cases a limit governs
adds its test here (the catalog README lists them)."""

from .test_families import built


def test_limit_6e_clean_credit_notes():
    """Credit notes are clean only (step 11 Q12): no generated credit note carries a problem."""
    for n in (2000, 500, 300):
        for g in built(n).cases:
            inv = g.envelope.payload.invoice
            if inv.doc_type == "credit_note":
                assert g.envelope.payload.exception_types == [] and g.answer.decision.value == "APPROVE"
            for entry in g.records.ledger:
                if entry.invoice.doc_type == "credit_note":
                    assert entry.invoice.original_invoice_ref


# -- B1-4: the Malaysian limits (catalog README, "Planting limits for v0.10") ---------------------------------------

from datetime import date  # noqa: E402
from functools import cache  # noqa: E402

from decision_benchmark.task_sets.ap_invoices.countries.my.models import MyTaxProfile  # noqa: E402
from decision_benchmark.task_sets.ap_invoices.generator.entities import catalog  # noqa: E402
from decision_benchmark.task_sets.ap_invoices.rules import build_case_view  # noqa: E402

SIZES = (2000, 500, 300)
OPEN_AREA = ("Q-A2", "Q-A3", "Q-A4", "Q-A5")
ZONE_FACTS = ("recipient_zone", "service_site_zone", "delivery_zone")
SALES_TAX_FROM = date(2018, 9, 1)
PARTLY_EXEMPT = ("process_gauges", "control_instruments", "tool_bits")
SELF_BILLING_PLANTED = ("agents_dealers_distributors", "foreign_supplier", "individual_not_in_business",
                        "interest_payment")


def my_cases():
    for n in SIZES:
        for g in built(n).cases:
            if g.envelope.country == "MY":
                yield g


@cache
def tax_result(case_id: str, n: int):
    g = next(c for c in built(n).cases if c.built.case_id == case_id)
    view = build_case_view(g.records, g.envelope)
    return view.pack.assess_tax(view, catalog())


def results():
    for n in SIZES:
        for g in built(n).cases:
            if g.envelope.country == "MY":
                yield g, tax_result(g.built.case_id, n)


def invoices(g):
    yield g.envelope.payload.invoice
    for entry in g.records.ledger:
        if entry.ledger_id.startswith(f"L-{g.built.case_id}"):
            yield entry.invoice                                   # the case's own history copies (duplicates)


def test_limit_1_no_open_area_questions():
    """No Q-A2 to Q-A5 case, and no master or line fact gives the zone pulau_1."""
    for g, result in results():
        assert not [u for u in result.unsettled if any(q in u.reason for q in OPEN_AREA)], g.built.case_id
        assert not [x for x in result.lines if x.open_question in OPEN_AREA], g.built.case_id
        parties = [g.records.company.tax_facts] + [s.tax_facts for s in g.records.suppliers]
        assert all(getattr(p, "zone", None) != "pulau_1" for p in parties if p is not None)
        for line in g.envelope.payload.invoice.lines:
            for name in ZONE_FACTS:
                fact = getattr(line.facts, name, None) if line.facts else None
                assert fact is None or fact.value != "pulau_1", g.built.case_id


def test_limit_2_q_a1_only_when_flagged():
    """open_questions: [Q-A1] in the generator truth if and only if the engine's line result carries Q-A1."""
    flagged = 0
    for g, result in results():
        found = sorted({x.open_question for x in result.lines if x.open_question})
        assert found == g.built.planted.open_questions, g.built.case_id
        assert set(found) <= {"Q-A1"}
        flagged += bool(found)
    assert flagged > 0                                               # the limit is exercised


def test_limit_3_no_goods_before_sales_tax():
    for g in my_cases():
        for inv in invoices(g):
            for line in inv.lines:
                if catalog().get(line.category).kind != "goods":
                    continue
                assert inv.issue_date >= SALES_TAX_FROM, g.built.case_id
                delivered = getattr(line.facts, "delivery_date", None) if line.facts else None
                assert delivered is None or delivered.value >= SALES_TAX_FROM, g.built.case_id


def test_limit_4_no_partly_exempt_headings_early():
    for g in my_cases():
        for inv in invoices(g):
            for line in inv.lines:
                if line.category in PARTLY_EXEMPT:
                    assert inv.issue_date >= date(2025, 7, 1), g.built.case_id


def test_limit_6a_zone_from_records():
    """A zone comes from a master or a line fact stated in a document, never from an address."""
    for g in my_cases():
        for entry in g.answer.facts or []:
            for name in ZONE_FACTS:
                if name in entry and entry[name].get("value") is not None:
                    refs = entry[name]["evidence"]
                    assert refs and all("address" not in (r.get("path") or "") for r in refs), g.built.case_id


def test_limit_6b_self_billing_types():
    for g in my_cases():
        for line in g.envelope.payload.invoice.lines:
            fact = getattr(line.facts, "self_billing_type", None) if line.facts else None
            assert fact is None or fact.value in SELF_BILLING_PLANTED, g.built.case_id


def test_limit_6c_exempt_categories_uncharged():
    for g in my_cases():
        for inv in invoices(g):
            for line in inv.lines:
                profile = catalog().get(line.category).tax["MY"]
                assert isinstance(profile, MyTaxProfile)
                if profile.tax_class in ("sales_exempt", "none"):
                    assert line.tax_amount == 0, (g.built.case_id, line.category)


def test_limit_6d_unclear_group_relation():
    for g in my_cases():
        supplier = g.records.supplier(g.envelope.payload.supplier_id)
        if supplier.tax_facts is not None and getattr(supplier.tax_facts, "group_relation", "") == "unclear":
            for line in g.envelope.payload.invoice.lines:
                assert catalog().get(line.category).tax["MY"].group_relief, g.built.case_id


def test_limit_7_wh2_service_period():
    """Every planted WH-2 line states its service period (start and end)."""
    lines = 0
    for g, result in results():
        by_no = {x.line_no: x for x in g.envelope.payload.invoice.lines}
        for x in result.lines:
            if any(a.basis == "WH-2" for a in x.buyer_actions):
                facts = by_no[x.line_no].facts
                assert facts is not None and facts.service_period_start and facts.service_period_end, g.built.case_id
                lines += 1
    assert lines > 0


def test_limit_5_unconfirmed_treaty_rows():
    """A case that reads an unconfirmed Singapore treaty row is HAND_OVER with basis WH-5, in an Ambiguous slot. No
    settled key reads one."""
    planted = 0
    for n in SIZES:
        for g in built(n).cases:
            if g.envelope.country != "SG":
                continue
            view = build_case_view(g.records, g.envelope)
            result = view.pack.assess_tax(view, catalog())
            unconfirmed = [u for u in result.unsettled if "not confirmed" in u.reason]
            if unconfirmed:
                assert g.answer.decision.value == "HAND_OVER", g.built.case_id
                assert g.envelope.payload.exception_types == ["ambiguous"], g.built.case_id
                planted += 1
            else:
                assert "unconfirmed_treaty" not in g.families
    assert planted > 0
