"""Every golden answer key of the current engine version is a valid v0.10 output (A12 plan §7).

Its case-level treatment is the worst line by the pack's severity order, and every basis is a rule of
that country's registry.
"""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from decision_benchmark import __version__
from decision_benchmark.task_sets.ap_invoices.countries import PACKS
from decision_benchmark.task_sets.ap_invoices.findings import LineResult, worst_line
from decision_benchmark.task_sets.ap_invoices.models import AnswerKey

ROOT = Path(__file__).resolve().parents[2]
V10 = ROOT / "schemas/ap-invoices/v0.10"
_ALL = [json.loads(p.read_text()) for p in (V10 / "output.schema.json", *sorted((V10 / "countries").glob("*.json")))]
VALIDATOR = Draft202012Validator(_ALL[0], registry=Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _ALL))
GOLDEN_PATH = ROOT / f"tests/fixtures/keys/keys-{__version__}.yaml"
GOLDEN = yaml.safe_load(GOLDEN_PATH.read_text())["keys"] if GOLDEN_PATH.exists() else []


def test_golden_keys_exist():
    assert GOLDEN, f"{GOLDEN_PATH.name} is missing or empty"


@pytest.mark.parametrize("row", GOLDEN, ids=lambda r: f"{r['test'].split('::')[-1]}#{r['call']}")
def test_every_golden_key_is_a_valid_v010_output(row):
    key = AnswerKey.model_validate(row["key"])
    VALIDATOR.validate(key.as_output())
    pack = PACKS[key.case_id.split("-")[1].upper()]
    assert key.tax_lines and {t.basis for t in key.tax_lines} <= set(pack.rules)
    if all(t.treatment for t in key.tax_lines):
        lines = [LineResult(t.line_no, t.treatment, t.basis) for t in key.tax_lines]
        assert worst_line(lines, pack.severity_order) == key.tax_treatment
