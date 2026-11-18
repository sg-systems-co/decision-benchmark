"""Packs, rule registry, worst line and the new answer-key fields (A12 plan §3, §7, §9)."""

import json
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource

from decision_benchmark import __version__
from decision_benchmark.task_sets.ap_invoices.countries import PACKS
from decision_benchmark.task_sets.ap_invoices.fact_reader import FactReader
from decision_benchmark.task_sets.ap_invoices.findings import LineResult, worst_line
from decision_benchmark.task_sets.ap_invoices.models import AnswerKey, BuyerAction, TaxLine
from decision_benchmark.task_sets.ap_invoices.registry import RuleSpec, registry
from decision_benchmark.task_sets.ap_invoices.spec import SPEC
from decision_benchmark.task_sets.ap_invoices.versions import ENGINE_VERSION, RULES_VERSION

from .factory import answer, line_facts, my_base, sg_base, sg_line, set_lines

ROOT = Path(__file__).resolve().parents[2]
V10 = ROOT / "schemas/ap-invoices/v0.10"
PARTS = {p.stem.split(".")[0].upper(): json.loads(p.read_text()) for p in sorted((V10 / "countries").glob("*.json"))}
_ALL = [json.loads((V10 / "output.schema.json").read_text()), *PARTS.values()]
VALIDATOR = Draft202012Validator(_ALL[0], registry=Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in _ALL))


@pytest.mark.parametrize("country", sorted(PACKS))
def test_severity_order_is_the_schema_part(country):
    assert list(PACKS[country].severity_order) == PARTS[country]["x-severity-order"]


@pytest.mark.parametrize("country", sorted(PACKS))
def test_registry_lists_every_rule_of_the_schema_part(country):
    assert list(PACKS[country].rules) == PARTS[country]["$defs"]["rule_id"]["enum"]
    assert all(isinstance(spec, RuleSpec) and spec.rule_id == rid for rid, spec in PACKS[country].rules.items())


def test_rule_spec_dates():
    spec = RuleSpec("X-1", valid_from=date(2025, 7, 1), valid_to=date(2026, 6, 30))
    assert not spec.applies_on(date(2025, 6, 30)) and spec.applies_on(date(2025, 7, 1))
    assert spec.applies_on(date(2026, 6, 30)) and not spec.applies_on(date(2026, 7, 1))
    assert RuleSpec("X-2").applies_on(date(1990, 1, 1))
    with pytest.raises(ValueError, match="before valid_from"):
        RuleSpec("X-3", valid_from=date(2026, 1, 2), valid_to=date(2026, 1, 1))
    with pytest.raises(ValueError, match="twice"):
        registry(RuleSpec("X-1"), RuleSpec("X-1"))


def test_worst_line():
    order = ("BAD", "MID", "OK")
    lines = [LineResult(1, "OK", "R-1"), LineResult(2, "MID", "R-2"), LineResult(3, "OK", "R-1")]
    assert worst_line(lines, order) == "MID"
    assert worst_line([*lines, LineResult(4, None, "R-3")], order) is None
    assert worst_line([], order) is None
    with pytest.raises(ValueError, match="not in the severity order"):
        worst_line([LineResult(1, "ODD", "R-1")], order)


def test_fact_reader_records_reads_and_missing():
    from decision_benchmark.task_sets.ap_invoices.models import InvoiceLine

    facts = PACKS["SG"].line_facts_model.model_validate(line_facts(1, vehicle_is_motor_car=True))
    line = InvoiceLine(line_no=1, qty=1, uom="u", net_amount="10.00", category="motor_car_running", facts=facts)
    reader = FactReader(PACKS["SG"], line)
    assert reader.value("vehicle_is_motor_car") is True
    assert reader.get("business_purpose") is None
    reader.get("vehicle_is_motor_car")
    assert reader.read == ["vehicle_is_motor_car", "business_purpose"]
    assert reader.recorded_reads() == ["vehicle_is_motor_car"] and reader.missing() == ["business_purpose"]
    with pytest.raises(KeyError):
        reader.get("personal_use")


def test_buyer_action_shape():
    a = BuyerAction(action="WITHHOLD_TAX", rate="10", basis="WH-2", base_amount="18000")
    assert a.as_output() == {"action": "WITHHOLD_TAX", "rate": 10, "basis": "WH-2", "base_amount": "18000.00"}
    assert BuyerAction(action="WITHHOLD_TAX", rate="2.5", basis="WH-5", base_amount="1").as_output()["rate"] == 2.5
    with pytest.raises(ValidationError, match="needs rate, basis and base_amount"):
        BuyerAction(action="WITHHOLD_TAX", basis="WH-2", base_amount="1")
    with pytest.raises(ValidationError, match="only WITHHOLD_TAX"):
        BuyerAction(action="ACCOUNT_REVERSE_CHARGE_GST", rate="9")


def test_answer_key_line_rules():
    base = dict(case_id="ap-sg-00001", gl_account="6100", reason_codes=["MATCHED_WITHIN_TOLERANCE"], answer_source="rules",
                grader_truth={"supplier_id": "S"}, engine_version="x", rules_version="v0.9", decision="APPROVE",
                tax_treatment="CLAIMABLE")
    with pytest.raises(ValidationError, match="each line once"):
        AnswerKey(tax_lines=[TaxLine(line_no=1, treatment="CLAIMABLE", basis="SG-1")] * 2, **base)
    with pytest.raises(ValidationError, match="null only on HAND_OVER"):
        AnswerKey(tax_lines=[TaxLine(line_no=1, treatment=None, basis="SG-10")], **base)


def test_versions_in_keys():
    assert ENGINE_VERSION == __version__ and RULES_VERSION == SPEC.spec_version
    key = answer(*sg_base())
    assert (key.engine_version, key.rules_version) == (ENGINE_VERSION, RULES_VERSION)


def test_gold_facts_are_the_facts_read():
    r, c = sg_base()
    set_lines(c, [sg_line(1, "motor_car_running", 1, "300.00", vehicle_is_motor_car=True, business_purpose=True)])
    key = answer(r, c)
    assert key.facts == [{"line_no": 1, "vehicle_is_motor_car": {
        "value": True, "evidence": [{"doc_id": "INV-CASE-1", "path": "lines[0].description"}]}}]
    assert [(t.treatment, t.basis) for t in key.tax_lines] == [("NOT_CLAIMABLE_DISALLOWED", "SG-10")]


def test_hand_over_line_is_null_with_its_basis():
    r, c = my_base()
    c["invoice"]["lines"][0]["facts"] = line_facts(1, same_service_as_buyer=None)
    key = answer(r, c)
    assert key.decision == "HAND_OVER" and key.tax_treatment is None
    assert [(t.treatment, t.basis) for t in key.tax_lines] == [(None, "MS-5")]
    assert key.facts == [{"line_no": 1, "same_service_as_buyer": {"value": None}}]
    VALIDATOR.validate(key.as_output())
