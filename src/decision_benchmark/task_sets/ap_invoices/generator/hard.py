"""Checks on the hard cases (B1 plan section 3.2): what makes each kind hard holds in the built case.

H3 (missing information), the null-fact check: every fact the case was planted without is stated in no document of the
case (no field holds it, no text reads back to it, a party record exports it as not shown), and stating it ends the
hand-over, so the case hands over because of that fact. H2 (conflicting documents), the counterfactual check: the
invoice states value A where the governing document states B and the key follows B, so putting A in the governing
document changes the key.
"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING, Any

from ..models import Case, CompanyRecords
from ..rules import answer_case
from . import phrases

if TYPE_CHECKING:
    from .build import GeneratedCase

KNOWN_FLAG = {"einvoice": "einvoice_phase_known"}
"""A party fact and the flag its record sets false when it doesn't show the fact (B1 plan section 2.3)."""


def case_texts(g: GeneratedCase, line: int | None = None) -> list[str]:
    """The free texts of the case's documents that could state a fact of the line (None: of any line): its invoice
    line and PO line, the invoice's notes and payment terms, the case's emails."""
    inv = g.envelope.payload.invoice
    picked = [x for x in inv.lines if line is None or x.line_no == line]
    texts = [x.description or "" for x in picked] + list(inv.notes) + [inv.payment_terms_text or ""]
    for e in g.built.records.get("emails_add", []):
        # A fact email says "Line k: ..." per fact: only the line's own sentences (and any others) count.
        sentences = (e.get("body", "") or "").split("\n")
        texts += [x for x in sentences if line is None or not re.match(r"Line \d+:", x) or x.startswith(f"Line {line}:")]
    texts += [x.get("description", "") or "" for po in g.built.records["purchase_orders"]
              for k, x in enumerate(po.get("lines", []), 1) if line is None or k == line]
    return [t for t in texts if t]


def stated_anywhere(g: GeneratedCase, item: dict) -> list[str]:
    """Where a planted-missing fact is stated after all (empty: nowhere)."""
    found = []
    country = g.envelope.country
    if item["party"] == "line":
        n, fact = item["line"], item["fact"]
        line = g.built.case["invoice"]["lines"][n - 1]
        if fact in (line.get("facts") or {}):
            found.append(f"line {n} records {fact}")
        if g.built.case["invoice"].get(fact) is not None:
            found.append(f"the invoice field {fact}")
        if fact in phrases.bank(country):
            for text in case_texts(g, n):
                try:
                    phrases.parse(country, fact, text)
                except phrases.PhraseError:
                    continue
                found.append(f"{fact} in {text!r}")
    else:
        record = g.records.company if item["party"] == "company" else g.records.supplier(g.envelope.payload.supplier_id)
        facts, flag = record.tax_facts, KNOWN_FLAG[item["fact"]]
        if facts is None or getattr(facts, item["fact"]) is not None or getattr(facts, flag):
            found.append(f"the {item['party']} record shows {item['fact']} (or doesn't flag it as not shown)")
    return found


def with_fact(g: GeneratedCase, item: dict) -> tuple[CompanyRecords, Any]:
    """The case's records and envelope with the planted-missing fact stated (in the invoice line, or the party's
    record)."""
    records, env = g.records, g.envelope
    if item["party"] == "line":
        payload = env.payload.model_dump(mode="json")
        line = payload["invoice"]["lines"][item["line"] - 1]
        line["facts"] = line.get("facts") or {}
        line["facts"][item["fact"]] = {
            "value": item["supply"],
            "evidence": [{"doc_id": payload["invoice"]["invoice_id"], "path": f"lines[{item['line'] - 1}].description"}]}
        env = env.model_copy(update={"payload": Case.model_validate(payload)})
    else:
        data = records.model_dump(mode="json")
        target = data["company"] if item["party"] == "company" else next(
            s for s in data["suppliers"] if s["supplier_id"] == env.payload.supplier_id)
        target["tax_facts"] = (target.get("tax_facts") or {}) | {item["fact"]: copy.deepcopy(item["supply"]),
                                                                 KNOWN_FLAG[item["fact"]]: True}
        records = CompanyRecords.model_validate(data)
    return records, env


def check_missing(g: GeneratedCase) -> list[str]:
    """The null-fact check on an H3 case: problems (empty when it holds)."""
    from .entities import catalog

    if not g.missing:
        return ["no fact was planted missing"]
    problems = []
    if g.answer.decision.value != "HAND_OVER":
        problems.append(f"decision {g.answer.decision.value}, not HAND_OVER")
    for item in g.missing:
        problems += stated_anywhere(g, item)
        records, env = with_fact(g, item)
        if answer_case(records, env, catalog()).decision.value == "HAND_OVER":
            problems.append(f"stating {item['fact']} doesn't end the hand-over")
    return problems


def _apply(data: Any, patch: dict) -> None:
    from .statements import PATH_PART, resolve

    parts = PATH_PART.findall(patch["path"])
    *head, (name, index) = parts
    parent = data
    for n, i in head:
        parent = parent[n] if n else parent[int(i)]
    op = patch.get("op", "set")
    if op == "append":
        resolve(data, patch["path"]).append(copy.deepcopy(patch["value"]))
    elif op == "delete":
        if name:
            parent.pop(name, None)
        else:
            parent.pop(int(index))
    elif name:
        parent[name] = copy.deepcopy(patch["value"])
    else:
        parent[int(index)] = copy.deepcopy(patch["value"])


def with_conflict(g: GeneratedCase) -> tuple[CompanyRecords, Any]:
    """The case's records and envelope with what the invoice says put in the governing document (the patches)."""
    records = g.records.model_dump(mode="json")
    payload = g.envelope.payload.model_dump(mode="json")
    sid = g.envelope.payload.supplier_id
    for patch in (g.conflict or {}).get("patches", []):
        target = patch["target"]
        if target == "invoice":
            data = payload["invoice"]
            for line in data["lines"]:
                line["facts"] = line.get("facts") or {}
        elif target == "company":
            data = records["company"]
        elif target == "supplier":
            data = next(s for s in records["suppliers"] if s["supplier_id"] == sid)
        elif target.startswith("contract:"):
            data = next(k for k in records["contracts"] if k["contract_id"] == target.split(":", 1)[1])
        elif target == "records":
            data = records
        else:
            raise ValueError(f"unknown patch target {target}")
        _apply(data, patch)
    env = g.envelope.model_copy(update={"payload": Case.model_validate(payload)})
    return CompanyRecords.model_validate(records), env


def key_view(answer) -> tuple:
    """What a conflict must change: the decision, each line's treatment and basis, the findings, the buyer actions."""
    return (answer.decision.value, tuple((t.line_no, t.treatment, t.basis) for t in answer.tax_lines),
            tuple(sorted(f.code.value for f in answer.findings)),
            tuple(sorted(str(a.model_dump(mode="json")) for a in answer.buyer_actions)))


def check_conflict(g: GeneratedCase) -> list[str]:
    """The counterfactual check on an H2 case: problems (empty when putting value A in the governing document changes
    the key)."""
    from .entities import catalog

    if not g.conflict or not g.conflict.get("patches"):
        return ["no conflict was recorded"]
    from ..findings import UnsupportedCase

    records, env = with_conflict(g)
    try:
        changed = answer_case(records, env, catalog())
    except UnsupportedCase:
        return []          # with A the rules leave the case open beside another problem: not the key either way
    if key_view(changed) == key_view(g.answer):
        return [f"{g.conflict['row']}: the key doesn't change with the invoice's value in the governing document"]
    return []


__all__ = ["case_texts", "check_conflict", "check_missing", "key_view", "stated_anywhere", "with_conflict",
           "with_fact"]
