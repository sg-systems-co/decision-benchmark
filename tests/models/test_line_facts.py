"""Each country pack's line-facts model is exactly its schema part's $defs/line_facts (A12 plan §5.1).

Names, families, rules and value types must match, so the engine's gold facts and the facts an
entry submits use one vocabulary.
"""

import json
import typing
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries import PACKS
from decision_benchmark.task_sets.ap_invoices.models.evidence import EvidenceRef, LineFact, LineFacts

ROOT = Path(__file__).resolve().parents[2]
EV = [{"doc_id": "INV-1", "path": "lines[0].description"}]


def schema_facts(country: str) -> dict:
    part = json.loads((ROOT / f"schemas/ap-invoices/v0.10/countries/{country.lower()}.schema.json").read_text())
    return {k: v for k, v in part["$defs"]["line_facts"]["properties"].items() if k != "line_no"}


def kind(value_schema: dict) -> tuple:
    """A comparable description of a schema value: ('enum', values), ('bool',), ('date',), ('money',), ('share',), ('pattern', p)."""
    if "enum" in value_schema:
        return ("enum", tuple(v for v in value_schema["enum"] if v is not None))
    t = value_schema["type"][0]
    if t == "boolean":
        return ("bool",)
    if t == "number":
        return ("share",)
    if value_schema.get("format") == "date":
        return ("date",)
    if value_schema.get("pattern") == r"^-?\d+(\.\d{1,2})?$":
        return ("money",)
    return ("pattern", value_schema["pattern"])


def sample(k: tuple):
    return {"enum": lambda: k[1][0], "bool": lambda: True, "date": lambda: "2026-01-01", "money": lambda: "12.50",
            "share": lambda: "0.4"}.get(k[0], lambda: None)()


@pytest.mark.parametrize("country", sorted(PACKS))
def test_model_fields_equal_the_schema(country):
    model = PACKS[country].line_facts_model
    assert issubclass(model, LineFacts)
    facts = schema_facts(country)
    assert list(model.model_fields) == list(facts)
    for name, spec in facts.items():
        extra = model.model_fields[name].json_schema_extra
        assert extra == {"family": spec["x-family"], "rules": spec["x-rules"]}, name


@pytest.mark.parametrize("country", sorted(PACKS))
def test_model_value_types_equal_the_schema(country):
    model = PACKS[country].line_facts_model
    for name, spec in schema_facts(country).items():
        k = kind(spec["properties"]["value"])
        if k[0] == "enum":
            for v in k[1]:
                model.model_validate({name: {"value": v, "evidence": EV}})
            with pytest.raises(ValidationError):
                model.model_validate({name: {"value": "not-a-listed-value", "evidence": EV}})
        elif k[0] == "pattern":
            fact_cls = typing.get_args(typing.get_type_hints(model, include_extras=True)[name])[0]
            str_hint = typing.get_args(fact_cls.model_fields["value"].annotation)[0]
            patterns = [m.pattern for m in typing.get_args(str_hint)[1:] if hasattr(m, "pattern")]
            assert patterns == [k[1]], name
        else:
            got = model.model_validate({name: {"value": sample(k), "evidence": EV}})
            value = getattr(got, name).value
            expected = {"bool": bool, "date": date, "money": Decimal, "share": Decimal}[k[0]]
            assert isinstance(value, expected), name


def test_dumped_facts_use_the_schema_json_types():
    model = PACKS["MY"].line_facts_model
    facts = model.model_validate({
        "sublet_share": {"value": "0.4", "evidence": EV},
        "statutory_fee_amount": {"value": "120", "evidence": EV},
        "contract_signed": {"value": "2025-06-01", "evidence": EV},
        "sublet": {"value": None},
    })
    out = facts.to_output()
    assert out["sublet_share"]["value"] == 0.4
    assert out["statutory_fee_amount"]["value"] == "120.00"
    assert out["contract_signed"] == {"value": "2025-06-01", "evidence": EV}
    assert out["sublet"] == {"value": None}
    assert list(facts.to_output(["sublet", "personal_use"])) == ["sublet"]
    assert set(facts.recorded()) == {"sublet_share", "statutory_fee_amount", "contract_signed", "sublet"}


@pytest.mark.parametrize("bad, msg", [
    ({"value": True}, "needs at least one evidence reference"),
    ({"value": None, "evidence": EV}, "has no evidence"),
    ({"value": True, "evidence": [{"doc_id": "X"}]}, "exactly one of path or span"),
    ({"value": True, "evidence": [{"doc_id": "X", "path": "a", "span": {"start": 0, "end": 2}}]}, "exactly one of path or span"),
    ({"value": True, "evidence": [{"doc_id": "X", "span": {"start": 5, "end": 5}}]}, "ends after it starts"),
])
def test_fact_and_evidence_rules(bad, msg):
    with pytest.raises(ValidationError, match=msg):
        LineFact[bool].model_validate(bad)


def test_share_bounds():
    model = PACKS["MY"].line_facts_model
    with pytest.raises(ValidationError, match="between 0 and 1"):
        model.model_validate({"sublet_share": {"value": "1.2", "evidence": EV}})
    EvidenceRef(doc_id="C-1", span={"start": 0, "end": 3})


def test_pack_fact_lookup_rejects_unknown_names():
    with pytest.raises(KeyError):
        PACKS["MY"].fact(None, "vehicle_is_motor_car")
