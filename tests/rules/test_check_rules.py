"""check_rules (A12 plan §8, build PR 5 commit 18): the same code path as the answer keys, on facts a caller supplies."""

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.models import CompanyRecords
from decision_benchmark.task_sets.ap_invoices.rules import CheckRulesResult, check_rules
from decision_benchmark.task_sets.ap_invoices.versions import ENGINE_VERSION, RULES_VERSION

from .factory import CATALOG, answer, wrap
from .my_cases import company_facts, one_line, sg_one_line
from .test_my_exemptions import imported


def run(r, c, lines):
    return check_rules(CompanyRecords.model_validate(r), wrap(c), lines, CATALOG)


def gold_lines(key) -> list[dict]:
    return [dict(x) for x in (key.facts or [])]


def same_as_key(r, c):
    key = answer(r, c)
    out = run(r, c, gold_lines(key))
    assert [(x.line_no, x.treatment, x.basis) for x in out.lines] == [(t.line_no, t.treatment, t.basis) for t in key.tax_lines]
    assert [a for x in out.lines for a in x.buyer_actions] == list(key.buyer_actions)
    return out


@pytest.mark.parametrize("case", [
    lambda: one_line(),
    lambda: one_line("legal_services", rate="8", subject_outside_malaysia=True),
    lambda: one_line(rate="6", service_item="K", asset_type="machinery", sublet=True),
    lambda: imported(),
    lambda: sg_one_line(),
    lambda: sg_one_line(exempt_supply="financial"),
    lambda: sg_one_line("test_residential_lease_sg", rate="0"),
])
def test_check_rules_with_the_gold_facts_equals_the_answer_key(case):
    r, c = case()
    out = same_as_key(r, c)
    assert out.engine_version == ENGINE_VERSION and out.rules_version == RULES_VERSION


def test_supplied_facts_decide_and_recorded_facts_are_ignored():
    # The invoice records subject_outside_malaysia: true; check_rules reads only what is supplied.
    r, c = one_line("legal_services", rate="8", subject_outside_malaysia=True)
    assert (run(r, c, []).lines[0].treatment, run(r, c, []).lines[0].basis) == ("SST_CORRECT", "MS-2")
    out = run(r, c, [{"line_no": 1, "subject_outside_malaysia": {"value": True}}])     # evidence optional
    assert (out.lines[0].treatment, out.lines[0].basis) == ("SST_SHOULD_BE_EXEMPT", "MS-4")


def test_a_null_fact_leaves_the_line_unsettled_with_its_rule():
    r, c = one_line("legal_services", rate="8")
    out = run(r, c, [{"line_no": 1, "subject_outside_malaysia": {"value": None}}])
    assert (out.lines[0].treatment, out.lines[0].basis) == (None, "MS-4")


def test_missing_lists_the_facts_read_but_not_supplied():
    r, c = one_line("legal_services", rate="8")
    out = run(r, c, [{"line_no": 1, "statutory_fee_amount": {"value": "0.00"}}])
    assert "subject_outside_malaysia" in out.lines[0].missing
    assert "statutory_fee_amount" not in out.lines[0].missing


def test_buyer_actions_come_back_per_line():
    r, c = imported()
    company_facts(r, einvoice_phase_start="2025-01-01")
    out = run(r, c, [])
    assert [a.action for a in out.lines[0].buyer_actions] == ["ACCOUNT_IMPORTED_SERVICE_TAX", "ISSUE_SELF_BILLED_EINVOICE"]


@pytest.mark.parametrize("lines, error", [
    ([{"line_no": 2, "residential": {"value": True}}], ValueError),
    ([{"line_no": 1}, {"line_no": 1}], ValueError),
    ([{"line_no": 1, "no_such_fact": {"value": True}}], ValidationError),
    ([{"line_no": 1, "residential": {"value": "maybe"}}], ValidationError),
])
def test_bad_input_is_rejected(lines, error):
    r, c = one_line()
    with pytest.raises(error):
        run(r, c, lines)


def test_check_rules_returns_no_decision_or_gl():
    assert set(CheckRulesResult.model_fields) == {"engine_version", "rules_version", "lines"}
    r, c = one_line()
    assert set(run(r, c, []).lines[0].model_dump()) == {"line_no", "treatment", "basis", "buyer_actions", "missing"}
