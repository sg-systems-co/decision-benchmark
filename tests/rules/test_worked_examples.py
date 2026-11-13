"""The three worked examples of step-11 plan §6 give exactly the answer keys shown there.
Every answer key also validates against output.schema.json as a prediction."""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from decision_benchmark.task_sets.ap_invoices_my_sg.models import Case, CompanyRecords
from decision_benchmark.task_sets.ap_invoices_my_sg.rules import answer_case

from .factory import CATALOG, answer, my_base, sg_base

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "tests/fixtures/worked-examples").glob("*.yaml"))
SCHEMA = json.loads((ROOT / "schemas/ap-invoices-my-sg/v0.9/output.schema.json").read_text())


def _load(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CompanyRecords.model_validate(data["records"]), Case.model_validate(data["case"]), data["expect"]


def test_three_examples_exist():
    assert [p.stem for p in EXAMPLES] == ["ap-my-00137", "ap-my-01206", "ap-sg-00548"]


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_worked_example(path):
    records, case, expect = _load(path)
    key = answer_case(records, case, CATALOG)
    got = key.model_dump(mode="json")
    for field, value in expect.items():
        assert got[field] == value, field
    jsonschema.validate(key.as_output(), SCHEMA)


def test_findings_evidence_of_the_two_problem_case():
    records, case, _ = _load(next(p for p in EXAMPLES if p.stem == "ap-my-01206"))
    key = answer_case(records, case, CATALOG)
    by_code = {f.code: f.evidence for f in key.findings}
    assert by_code["WRONG_TAX_RATE"] == {"line": 1, "charged": "8", "expected": "6"}
    assert by_code["PRICE_ABOVE_PO"]["variance_pct"] == "5.08"


def test_hand_over_answer_keys_validate_against_the_schema():
    r, c = my_base()
    r["suppliers"][0]["group_relation"] = "unclear"
    jsonschema.validate(answer(r, c).as_output(), SCHEMA)
    r, c = sg_base()
    jsonschema.validate(answer(r, c).as_output(), SCHEMA)
