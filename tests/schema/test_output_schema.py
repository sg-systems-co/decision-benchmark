"""The output schema accepts the valid examples and rejects the invalid ones."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas/ap-invoices-my-sg/v0.9"
SCHEMA = json.loads((SCHEMA_DIR / "output.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)

VALID = sorted((SCHEMA_DIR / "examples/valid").glob("*.json"))
INVALID = sorted((SCHEMA_DIR / "examples/invalid").glob("*.json"))

SPEC_EXAMPLE = (
    '{"case_id": "ap-my-00421", "decision": "DISPUTE_PRICE", "tax_treatment": "SST_CORRECT", '
    '"gl_account": "5100-200", "reason_codes": ["PRICE_ABOVE_PO"], "confidence": 0.82, '
    '"explanation": "Unit price RM 12.40 vs PO RM 11.80, +5.1%, tolerance 2%."}'
)


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_example_counts():
    assert len(VALID) >= 3 and len(INVALID) >= 6


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_examples_pass(path):
    VALIDATOR.validate(json.loads(path.read_text()))


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_examples_fail(path):
    assert list(VALIDATOR.iter_errors(json.loads(path.read_text())))


def test_spec_example_is_verbatim_and_valid():
    spec = (Path(__file__).resolve().parents[2] / "docs/task-sets/ap-invoices-my-sg/spec-v0.9.md").read_text()
    assert SPEC_EXAMPLE in spec
    VALIDATOR.validate(json.loads(SPEC_EXAMPLE))


def test_enums_match_the_spec():
    props = SCHEMA["properties"]
    assert len(props["decision"]["enum"]) == 9
    assert len([c for c in props["tax_treatment"]["enum"] if c is not None]) == 10


def test_wrong_country_tax_code_is_not_a_schema_error():
    # A Malaysian code on a Singapore case is scored as a wrong tax treatment, not a schema break.
    VALIDATOR.validate(
        {"case_id": "ap-sg-00001", "decision": "APPROVE", "tax_treatment": "SST_CORRECT", "gl_account": "6100-000", "reason_codes": []}
    )
