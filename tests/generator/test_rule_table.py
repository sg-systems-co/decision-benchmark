"""The rule table the floor counts (content/generator/rules.yaml) agrees with the rule sheet and with the engine's
golden keys (B1 plan §3.4): 75 counted rules plus 6 not counted are the sheet's 81 rule ids; a rule has a problem form
exactly when the golden keys show it deciding a wrongly charged or undercharged line; line rules appear as a line
basis and the withholding rules as WITHHOLD_TAX bases."""

import re
from pathlib import Path

import yaml

from decision_benchmark.task_sets.ap_invoices.spec import SPEC

ROOT = Path(__file__).resolve().parents[2]
GEN = SPEC.generation
SHEET = (ROOT / "docs/tax-rules-v0.10.md").read_text(encoding="utf-8")
PROBLEM_TREATMENTS = ("SHOULD_BE_EXEMPT", "WRONG_RATE", "UNDERCHARGED", "NOT_REGISTERED", "WRONGLY_CHARGED",
                      "NOT_CHARGEABLE")


def _golden() -> list[dict]:
    newest = max((ROOT / "tests/fixtures/keys").glob("keys-*.yaml"), key=lambda p: [
        int(x) if x.isdigit() else x for x in re.split(r"[.\-]", p.stem.removeprefix("keys-"))])
    return [r["key"] for r in yaml.safe_load(newest.read_text(encoding="utf-8"))["keys"]]


def test_the_table_and_not_counted_are_the_sheets_81_rule_ids():
    sheet = {f"{a}-{b}" for a, b in re.findall(r"\b(MS|K|L|P|MG|G|ME|SG|WH)-(\d+)\b", SHEET)}
    counted = {r.id for r in GEN.rules}
    assert len(counted) == 75 and set(GEN.not_counted) == {"MS-10", "MG-6", "P-21", "G-2", "G-6", "G-7"}
    assert counted | set(GEN.not_counted) == sheet
    assert sum(r.country == "MY" for r in GEN.rules) == 62 and sum(r.country == "SG" for r in GEN.rules) == 13


def test_problem_forms_match_the_golden_keys():
    seen = set()
    for key in _golden():
        for line in key.get("tax_lines") or []:
            if line.get("basis") and any(p in (line.get("treatment") or "") for p in PROBLEM_TREATMENTS):
                seen.add(line["basis"])
    table = {r.id for r in GEN.rules if r.problem_form}
    assert table == seen & {r.id for r in GEN.rules}


def test_carriers_match_the_golden_keys():
    line_bases, withholding = set(), set()
    for key in _golden():
        line_bases |= {t["basis"] for t in key.get("tax_lines") or [] if t.get("basis")}
        withholding |= {a["basis"] for a in key.get("buyer_actions") or [] if a.get("basis")}
    for r in GEN.rules:
        if r.carrier == "line":
            assert r.id in line_bases, r.id
        if r.id.startswith("WH-"):
            assert r.carrier == "action" and r.id in withholding and r.foreign, r.id
    assert not {r.id for r in GEN.rules if r.carrier != "line"} & line_bases
