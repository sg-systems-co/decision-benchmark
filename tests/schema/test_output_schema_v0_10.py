"""Output schema v0.10: the generic part, the country parts and the results schema.

The valid examples pass and the invalid ones fail; a v0.9 output is still a v0.10 output; the codes,
order and rule IDs in the country parts match the spec and the rule sheet; the derived blocks are
current."""

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
V9 = ROOT / "schemas/ap-invoices/v0.9"
V10 = ROOT / "schemas/ap-invoices/v0.10"
SPEC = (ROOT / "docs/task-sets/ap-invoices/spec-v0.10.md").read_text(encoding="utf-8")
SHEET = (ROOT / "docs/tax-rules-v0.10.md").read_text(encoding="utf-8")

sys.path.insert(0, str(ROOT / "schemas"))
import derive  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


OUTPUT = _load(V10 / "output.schema.json")
RESULTS = _load(V10 / "results.schema.json")
PART_PATHS = sorted((V10 / "countries").glob("*.schema.json"))
PARTS = {p.stem.split(".")[0].upper(): _load(p) for p in PART_PATHS}
ALL_SCHEMAS = [OUTPUT, RESULTS, *PARTS.values()]
REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in ALL_SCHEMAS)
VALIDATOR = Draft202012Validator(OUTPUT, registry=REGISTRY)
RESULTS_VALIDATOR = Draft202012Validator(RESULTS, registry=REGISTRY)

EX = V10 / "examples"
VALID = sorted((EX / "valid").glob("*.json"))
INVALID = sorted((EX / "invalid").glob("*.json"))
RESULTS_VALID = sorted((EX / "results/valid").glob("*.json"))
RESULTS_INVALID = sorted((EX / "results/invalid").glob("*.json"))

NEW_CODES = {
    "MY": {"SST_BUYER_ACCOUNTS", "SST_UNDERCHARGED", "SST_NOT_CHARGEABLE_BY_TRADER"},
    "SG": {"CUSTOMER_ACCOUNTING", "REVERSE_CHARGE", "NOT_CLAIMABLE_EXEMPT_USE", "RESIDUAL_APPORTIONED", "GST_UNDERCHARGED"},
}
ACTIONS = {"ACCOUNT_IMPORTED_SERVICE_TAX", "ACCOUNT_CUSTOMER_ACCOUNTING_GST", "ACCOUNT_REVERSE_CHARGE_GST",
           "ISSUE_SELF_BILLED_EINVOICE", "WITHHOLD_TAX"}
RULE_ID = re.compile(r"\b(?:MS|MG|ME|SG|WH|K|L|P|G)-\d+\b")


def codes(country: str) -> list[str]:
    return [c["const"] for c in PARTS[country]["$defs"]["tax_code"]["oneOf"]]


def errors(validator, obj) -> list:
    return list(validator.iter_errors(obj))


# -- schemas -------------------------------------------------------------------


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s["$id"].rsplit("/v0.10/", 1)[1])
def test_schemas_are_valid_draft_2020_12(schema):
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].startswith("https://github.com/sg-systems-co/decision-benchmark/blob/main/schemas/ap-invoices/v0.10/")


def test_derived_blocks_are_current():
    assert derive.main([str(V10), "--check"]) == 0


def test_example_counts():
    assert len(VALID) >= 12 and len(INVALID) >= 14
    assert len(RESULTS_VALID) >= 3 and len(RESULTS_INVALID) >= 1


# -- examples ------------------------------------------------------------------


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_examples_pass(path):
    VALIDATOR.validate(_load(path))


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_examples_fail(path):
    assert errors(VALIDATOR, _load(path))


@pytest.mark.parametrize("path", RESULTS_VALID, ids=lambda p: p.stem)
def test_valid_results_pass(path):
    RESULTS_VALIDATOR.validate(_load(path))


@pytest.mark.parametrize("path", RESULTS_INVALID, ids=lambda p: p.stem)
def test_invalid_results_fail(path):
    assert errors(RESULTS_VALIDATOR, _load(path))


@pytest.mark.parametrize("name", [
    "unknown-buyer-action", "withhold-tax-without-rate", "tax-lines-duplicate-line-no",
    "case-treatment-contradicts-worst-line", "fact-without-evidence",
])
def test_required_invalid_examples_exist(name):
    assert (EX / "invalid" / f"{name}.json").exists()


@pytest.mark.parametrize("name, code, basis", [
    ("my-sales-tax-left-off-by-manufacturer", "SST_UNDERCHARGED", "MS-9"),
    ("sg-gst-left-off-standard-rated", "GST_UNDERCHARGED", "SG-12"),
])
def test_tax_left_off_examples(name, code, basis):
    out = _load(EX / "valid" / f"{name}.json")
    assert {"treatment": code, "basis": basis} in [{k: x[k] for k in ("treatment", "basis")} for x in out["tax_lines"]]
    assert out["tax_treatment"] == code and out["decision"] == "REQUEST_CORRECTED_INVOICE"


def test_results_file_without_lane_is_invalid():
    entry = _load(EX / "results/invalid/no-lane.json")
    assert "lane" not in entry and errors(RESULTS_VALIDATOR, entry)
    assert not errors(RESULTS_VALIDATOR, {**entry, "lane": "model"})


def test_every_new_field_code_and_action_has_a_valid_example():
    seen_codes, seen_actions, fields = set(), set(), set()
    for path in VALID:
        out = _load(path)
        fields |= set(out)
        seen_codes |= {out["tax_treatment"], *(line["treatment"] for line in out.get("tax_lines", []))}
        seen_actions |= {a["action"] for a in out.get("buyer_actions", [])}
    assert {"tax_lines", "buyer_actions", "facts"} <= fields
    assert NEW_CODES["MY"] | NEW_CODES["SG"] <= seen_codes
    assert seen_actions == ACTIONS
    assert any(_load(p).get("buyer_actions") == [] for p in VALID), "an empty buyer_actions list"


def test_duplicate_line_no_fails_only_for_the_duplicate():
    out = _load(EX / "invalid/tax-lines-duplicate-line-no.json")
    assert errors(VALIDATOR, out)
    out["tax_lines"][1]["line_no"] = 2
    VALIDATOR.validate(out)


def test_null_line_needs_null_case_level_treatment():
    out = _load(EX / "valid/my-rental-sublet-hand-over.json")
    assert out["decision"] == "HAND_OVER" and out["tax_treatment"] is None
    VALIDATOR.validate(out)
    assert errors(VALIDATOR, {**out, "tax_treatment": "SST_CORRECT"})


def test_line_no_bounds_match_the_derived_block():
    line_no = OUTPUT["$defs"]["line_no"]
    assert (line_no["minimum"], line_no["maximum"]) == (1, 200)
    assert len(OUTPUT["$defs"]["unique_line_no"]["allOf"]) == 200


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_worst_line_rule_follows_the_order(country):
    order = PARTS[country]["x-severity-order"]
    prefix = "ap-my-" if country == "MY" else "ap-sg-"
    basis = "MS-1" if country == "MY" else "SG-1"
    for i, worse in enumerate(order):
        for better in order[i:]:
            lines = [{"line_no": 1, "treatment": better, "basis": basis}, {"line_no": 2, "treatment": worse, "basis": basis}]
            out = {"case_id": prefix + "00001", "decision": "APPROVE", "gl_account": "6100-000", "reason_codes": [], "tax_lines": lines}
            assert not errors(VALIDATOR, {**out, "tax_treatment": worse}), (worse, better)
            if better != worse:
                assert errors(VALIDATOR, {**out, "tax_treatment": better}), (worse, better)


# -- v0.9 compatibility -------------------------------------------------------


@pytest.mark.parametrize("path", sorted((V9 / "examples/valid").glob("*.json")), ids=lambda p: p.stem)
def test_v09_outputs_are_valid_v010_outputs(path):
    VALIDATOR.validate(_load(path))


def test_v09_spec_example_is_valid_and_has_every_main_score_field():
    spec9 = (ROOT / "docs/task-sets/ap-invoices/spec-v0.9.md").read_text(encoding="utf-8")
    line = next(x for x in spec9.splitlines() if x.startswith('{"case_id"'))
    out = json.loads(line)
    VALIDATOR.validate(out)
    # The main score and the v0.9 columns read only fields a v0.9 output has.
    assert OUTPUT["required"] == _load(V9 / "output.schema.json")["required"]
    assert set(OUTPUT["required"]) <= set(out)


def test_v09_vocabulary_is_kept():
    v9 = _load(V9 / "output.schema.json")["properties"]
    assert OUTPUT["properties"]["decision"]["enum"] == v9["decision"]["enum"]
    assert {c for c in v9["tax_treatment"]["enum"] if c} <= set(codes("MY")) | set(codes("SG"))
    for name in ("case_id", "gl_account", "reason_codes", "confidence", "explanation"):
        assert {k: v for k, v in OUTPUT["properties"][name].items() if k != "description"} == \
               {k: v for k, v in v9[name].items() if k != "description"}, name


def test_engine_codes_are_valid_v010_codes():
    from decision_benchmark.task_sets.ap_invoices.countries import PACKS

    for country, pack in PACKS.items():
        assert {str(c) for c in pack.tax_codes} <= set(codes(country))


# -- country parts, spec and sheet ---------------------------------------------


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_country_part_codes(country):
    part = PARTS[country]
    assert part["x-country"] == country
    assert NEW_CODES[country] <= set(codes(country))
    assert sorted(part["x-severity-order"]) == sorted(codes(country))
    rules = set(part["$defs"]["rule_id"]["enum"])
    for c in part["$defs"]["tax_code"]["oneOf"]:
        assert c["description"] and c["x-rules"] and set(c["x-rules"]) <= rules, c["const"]


def test_tax_codes_are_unique_across_countries():
    assert not set(codes("MY")) & set(codes("SG"))


def test_country_rule_ids_are_exactly_the_sheets():
    in_sheet = set(RULE_ID.findall(SHEET))
    my, sg = (set(PARTS[c]["$defs"]["rule_id"]["enum"]) for c in ("MY", "SG"))
    assert not my & sg
    assert my | sg == in_sheet
    assert {r for r in in_sheet if r.startswith("SG-")} | {"WH-5"} == sg


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_spec_states_codes_rules_and_order(country):
    order = PARTS[country]["x-severity-order"]
    assert " > ".join(f"`{c}`" for c in order) in SPEC
    for c in PARTS[country]["$defs"]["tax_code"]["oneOf"]:
        row = next((x for x in SPEC.splitlines() if x.startswith(f"| `{c['const']}`")), None)
        assert row, c["const"]
        assert ", ".join(c["x-rules"]) in row, c["const"]
        assert ("**new**" in row) == (c["const"] in NEW_CODES[country]), c["const"]


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_line_facts_have_family_and_rules(country):
    part = PARTS[country]
    rules = set(part["$defs"]["rule_id"]["enum"])
    facts = {k: v for k, v in part["$defs"]["line_facts"]["properties"].items() if k != "line_no"}
    assert facts
    for name, spec in facts.items():
        assert spec["$ref"].endswith("output.schema.json#/$defs/fact"), name
        assert spec["x-family"] and spec["x-rules"] and set(spec["x-rules"]) <= rules, name
        assert f"`{name}`" in SPEC, f"{name} missing from the spec's facts table"
    first = "service_item" if country == "MY" else "exempt_supply"
    assert facts[first]["x-family"] == "classification"
    if country == "MY":
        assert {"tariff_code", "sublet", "itemised_consultation_fee", "materials_works_separated", "place_of_performance"} <= set(facts)


@pytest.mark.parametrize("country, column", [("MY", 1), ("SG", 2)])
def test_spec_family_table_matches_the_country_part(country, column):
    facts = {k: v for k, v in PARTS[country]["$defs"]["line_facts"]["properties"].items() if k != "line_no"}
    for family in {v["x-family"] for v in facts.values()}:
        row = next(x for x in SPEC.splitlines() if x.startswith("| " + family.replace("_", "\\_") + " |"))
        assert set(re.findall(r"`([a-z_0-9]+)`", row.split(" | ")[column])) == {
            k for k, v in facts.items() if v["x-family"] == family}, family


def test_clarification_facts_and_line_gl():
    my = PARTS["MY"]["$defs"]["line_facts"]["properties"]
    sg = PARTS["SG"]["$defs"]["line_facts"]["properties"]
    assert {"manufactured_by_supplier", "own_use", "ship_platform_election", "self_billing_type", "variation_changes_value"} <= set(my)
    assert {"beneficiary_outside_singapore", "low_value_goods"} <= set(sg)
    for part in PARTS.values():
        assert part["$defs"]["tax_line"]["properties"]["gl_account"]["type"] == "string"
        assert "gl_account" not in part["$defs"]["tax_line"]["required"]
    out = _load(EX / "valid/sg-mixed-lines-two-gl-accounts.json")
    assert len({x["gl_account"] for x in out["tax_lines"]}) == 2


@pytest.mark.parametrize("country", ["MY", "SG"])
def test_buyer_actions_per_country(country):
    simple, withhold = PARTS[country]["$defs"]["buyer_action"]["oneOf"]
    wh = withhold["properties"]["basis"]["enum"]
    assert all(b.startswith("WH-") for b in wh)
    assert set(simple["properties"]["action"]["enum"]) | {"WITHHOLD_TAX"} <= ACTIONS
    assert wh == (["WH-1", "WH-2", "WH-3", "WH-4"] if country == "MY" else ["WH-5"])


def test_spec_example_is_verbatim_and_valid():
    line = next(x for x in SPEC.splitlines() if x.startswith('{"case_id"'))
    out = json.loads(line)
    VALIDATOR.validate(out)
    assert out["tax_lines"] and out["buyer_actions"]


def test_spec_facts_snippet_is_valid():
    line = next(x for x in SPEC.splitlines() if x.startswith('{"facts"'))
    out = {"case_id": "ap-my-01577", "decision": "APPROVE", "tax_treatment": "SST_CORRECT", "gl_account": "1600-100",
           "reason_codes": [], **json.loads(line)}
    VALIDATOR.validate(out)


def test_wrong_country_case_level_code_is_not_a_schema_error():
    # As in v0.9: a Malaysian code on a Singapore case is a wrong tax treatment, not a schema break.
    VALIDATOR.validate({"case_id": "ap-sg-00001", "decision": "APPROVE", "tax_treatment": "SST_CORRECT",
                        "gl_account": "6100-000", "reason_codes": []})


def test_me3_self_billing_types_are_the_nine_items_of_section_8_3():
    """Review of PR #12 (18 Nov 2026): ME-3 lists the nine items (a)-(i) of section 8.3 of the LHDN e-Invoice
    Specific Guideline v4.9; item (g) has its own exceptions, where the supplier issues the e-invoice."""
    my = PARTS["MY"]["$defs"]["line_facts"]["properties"]
    assert my["self_billing_type"]["properties"]["value"]["enum"] == [
        "agents_dealers_distributors", "foreign_supplier", "profit_distribution", "ecommerce", "betting_gaming_payout",
        "individual_not_in_business", "interest_payment", "insurance_claim_payment", "capital_return_or_liquidation",
        "none", None]
    exc = my["interest_exception"]
    assert exc["properties"]["value"]["enum"] == [
        "public_lender", "employee_to_employer", "foreign_payor", "related_company_treasury", "late_payment_charge",
        "none", None]
    assert exc["x-rules"] == ["ME-3"] and list(my).index("interest_exception") == list(my).index("self_billing_type") + 1
