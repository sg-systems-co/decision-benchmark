"""Task-set registration and the shared case and answer envelopes."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import decision_benchmark.task_sets  # noqa: F401  (registers every task set)
from decision_benchmark.core import Document, TaskSetSpec, get, register, registered
from decision_benchmark.core.case import AnswerEnvelope
from decision_benchmark.task_sets.ap_invoices import SPEC
from decision_benchmark.task_sets.ap_invoices.envelope import ApCaseEnvelope, envelope
from decision_benchmark.task_sets.ap_invoices.models import Case, CompanyRecords, load_catalog
from decision_benchmark.task_sets.ap_invoices.rules import answer_case

ROOT = Path(__file__).resolve().parents[2]
CATALOG = load_catalog(ROOT / "tests/fixtures/catalog.yaml")
EXAMPLES = sorted((ROOT / "tests/fixtures/worked-examples").glob("*.yaml"))


def _load(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CompanyRecords.model_validate(data["records"]), ApCaseEnvelope.model_validate(data["case"])


def test_registry():
    assert "ap-invoices" in registered()
    assert get("ap-invoices") is SPEC
    assert register(SPEC) is SPEC  # registering the same spec again is harmless
    with pytest.raises(ValueError):
        register(SPEC.model_copy(update={"title": "something else"}))
    with pytest.raises(KeyError):
        get("no-such-task-set")


def test_spec_matches_the_output_schema():
    schema = json.loads((ROOT / SPEC.output_schema).read_text())
    assert list(schema["properties"]["decision"]["enum"]) == list(SPEC.decisions)
    assert schema["required"] == ["case_id", "decision", *SPEC.extra_fields]


def test_spec_costs_and_quotas_follow_the_spec():
    primary = SPEC.costs[0]
    assert (primary.handover, primary.false_alarm, primary.missed) == (1, 3, 10)
    assert [(c.handover, c.false_alarm, c.missed) for c in SPEC.costs[1:]] == [(1, 2, 5), (1, 3, 20)]
    assert SPEC.quotas["clean"] == 40 and SPEC.quotas["ambiguous"] == 3
    assert SPEC.hf_repo_id == "sgsystems/decision-benchmark-ap-invoices"
    assert SPEC.report_by == ("country",)


def _spec_kwargs(**over):
    kw = SPEC.model_dump()
    kw.update(over)
    return kw


@pytest.mark.parametrize(
    "over",
    [
        {"decisions": ("APPROVE", "REJECT")},
        {"approve_decision": "PAY"},
        {"trap_decisions": ("APPROVE",)},
        {"quotas": {"clean": Decimal(50)}},
        {"invalid_output_is": "zero"},
        {"id": "Not_A_Slug"},
        {"report_by": ("region",)},
    ],
    ids=["no_hand_over", "approve_unknown", "trap_is_approve", "quotas_not_100", "bad_invalid_cost", "bad_id",
         "report_by_unknown_field"],
)
def test_spec_validation(over):
    with pytest.raises(ValidationError):
        TaskSetSpec(**_spec_kwargs(**over))


def test_document_has_exactly_one_source():
    with pytest.raises(ValidationError):
        Document(role="invoice")
    with pytest.raises(ValidationError):
        Document(role="invoice", record="invoice", file="pdf/a.pdf")


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_worked_examples_fit_both_envelopes(path):
    records, env = _load(path)
    assert env.documents[0].record == "invoice" and env.invoice_file is None
    rebuilt = envelope(env.case_id, env.split, env.payload)
    assert rebuilt == env
    assert ApCaseEnvelope.model_validate(env.model_dump(mode="json")) == env
    key = answer_case(records, env, CATALOG)
    SPEC.check_answer(key.envelope())
    assert key.case_id == env.case_id


def test_payload_holds_invoice_data_only():
    assert set(Case.model_fields) == {
        "company_id", "as_of_date", "supplier_id", "invoice",
        "fact_sheets", "exception_types", "families", "two_problems",
    }


def test_invoice_file_is_a_document():
    _, env = _load(EXAMPLES[0])
    with_file = envelope(env.case_id, env.split, env.payload, invoice_file="pdf/train/ap-my-00137.pdf")
    assert with_file.invoice_file == "pdf/train/ap-my-00137.pdf"
    assert [d.file for d in with_file.documents] == [None, "pdf/train/ap-my-00137.pdf"]


@pytest.mark.parametrize(
    "change",
    [
        {"country": "SG"},
        {"task_set": "other"},
        {"modality": "fax"},
        {"documents": [{"role": "invoice", "file": "a.pdf"}]},
        {"documents": [{"role": "invoice", "record": "invoice"}, {"role": "po", "record": "purchase_order"}]},
        {"documents": [{"role": "invoice", "record": "invoice"}, {"role": "invoice", "file": "a.pdf"},
                       {"role": "invoice", "file": "b.jpg"}]},
    ],
    ids=["country_differs_from_invoice", "task_set", "modality", "no_invoice_record", "unknown_record", "two_files"],
)
def test_envelope_rejects(change):
    _, env = _load(EXAMPLES[0])
    data = env.model_dump(mode="json") | change
    with pytest.raises(ValidationError):
        ApCaseEnvelope.model_validate(data)


def test_check_answer_rejects_wrong_fields():
    good = dict(case_id="x", task_set=SPEC.id, decision="APPROVE", answer_source="rules",
                answer={"tax_treatment": "NO_GST", "gl_account": "6100", "reason_codes": ["MATCHED_WITHIN_TOLERANCE"]})
    SPEC.check_answer(AnswerEnvelope(**good))
    for over in ({"decision": "PAY"}, {"task_set": "other"}, {"answer": {"tax_treatment": "NO_GST"}}):
        with pytest.raises(ValueError):
            SPEC.check_answer(AnswerEnvelope(**{**good, **over}))
