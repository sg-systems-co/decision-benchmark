"""The build loop (B1 plan section 4): plant, let the engine find, compare, redraw on any difference.

B1-2 builds the clean slots of a split. Every case is compared on its decision, its finding codes, each line's
treatment and basis, and its buyer actions; a difference redraws the case with the next attempt number, at most 20
attempts, then the build fails. ``planting_report`` counts attempts and redraws (B1-3 adds the stop thresholds).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property

from decision_benchmark.core.case import Provenance
from decision_benchmark.core.generator.quotas import InfeasibleDemand
from decision_benchmark.core.generator.slots import Allocation, Slot, allocate
from decision_benchmark.core.generator.spec import Generation, SplitSpec

from ..envelope import ApCaseEnvelope, envelope
from ..models import AnswerKey, Case, CompanyRecords, GoodsReceipt, PurchaseOrder
from ..rules import answer_case
from .entities import CompanyWorld, build_world, catalog
from .scenario import BuiltCase, NoCleanForm, Planted, clean_case

MAX_ATTEMPTS = 20


class PlantingFailed(RuntimeError):
    """A slot still differs from what the engine finds after MAX_ATTEMPTS draws."""


@dataclass
class GeneratedCase:
    built: BuiltCase
    envelope: ApCaseEnvelope
    records: CompanyRecords
    answer: AnswerKey

    def export(self) -> dict:
        """The case as JSON-ready data: envelope, the records the case adds, the answer key, the generator truth."""
        return {
            "case_id": self.built.case_id,
            "company_id": self.built.company_id,
            "envelope": self.envelope.model_dump(mode="json"),
            "purchase_orders": self.built.records["purchase_orders"],
            "goods_receipts": self.built.records["goods_receipts"],
            "answer": self.answer.model_dump(mode="json"),
            "planted": {"decision": self.built.planted.decision, "lines": self.built.planted.lines,
                        "findings": self.built.planted.findings, "buyer_actions": self.built.planted.buyer_actions},
            "attempt": self.built.attempt,
        }


@dataclass
class Build:
    split: SplitSpec
    allocation: Allocation
    world: dict[str, list[CompanyWorld]]
    cases: list[GeneratedCase] = field(default_factory=list)
    redraws: Counter = field(default_factory=Counter)

    def planting_report(self) -> dict:
        attempts = sum(c.built.attempt + 1 for c in self.cases)
        return {"cases": len(self.cases), "attempts": attempts, "redraws": attempts - len(self.cases),
                "causes": dict(sorted(self.redraws.items()))}

    def dumps(self) -> str:
        """Every built case, one JSON line each, keys sorted: the bytes the reproducibility check compares."""
        return "".join(json.dumps(c.export(), sort_keys=True) + "\n" for c in self.cases)


class _Companies:
    """Each company's records validated once and shared by its cases (each case adds its PO and receipt)."""

    def __init__(self, world: dict[str, list[CompanyWorld]]) -> None:
        self.world = world

    @cached_property
    def validated(self) -> dict[str, CompanyRecords]:
        return {cw.company_id: CompanyRecords.model_validate(cw.records())
                for companies in self.world.values() for cw in companies}

    def records_for(self, built: BuiltCase) -> CompanyRecords:
        base = self.validated[built.company_id]
        return base.model_copy(update={
            "purchase_orders": [PurchaseOrder.model_validate(p) for p in built.records["purchase_orders"]],
            "goods_receipts": [GoodsReceipt.model_validate(g) for g in built.records["goods_receipts"]]})


def compare(planted: Planted, answer: AnswerKey) -> list[str]:
    """Differences between what was planted and what the engine found (empty: planted = found)."""
    diffs = []
    if answer.decision.value != planted.decision:
        diffs.append(f"decision {answer.decision.value} != {planted.decision}")
    found_codes = sorted(f.code.value for f in answer.findings)
    if found_codes != sorted(planted.findings):
        diffs.append(f"findings {found_codes} != {sorted(planted.findings)}")
    found_lines = [(t.line_no, t.treatment, t.basis) for t in answer.tax_lines]
    if found_lines != [tuple(x) for x in planted.lines]:
        diffs.append(f"lines {found_lines} != {planted.lines}")
    found_actions = sorted(a.action for a in answer.buyer_actions)
    if found_actions != sorted(planted.buyer_actions):
        diffs.append(f"buyer actions {found_actions} != {sorted(planted.buyer_actions)}")
    return diffs


def assign_companies(gen: Generation, slots: list[Slot], world: dict[str, list[CompanyWorld]]) -> dict[int, CompanyWorld]:
    """Slots to companies, round robin per country in case order (each company gets an even share)."""
    out: dict[int, CompanyWorld] = {}
    seen: Counter = Counter()
    for s in sorted(slots, key=lambda s: s.case_index):
        companies = world[s.country]
        out[s.case_index] = companies[seen[s.country] % len(companies)]
        seen[s.country] += 1
    return out


def build_clean(gen: Generation, quotas: dict, split: SplitSpec, provenance: Provenance | None = None,
                limit: int | None = None) -> Build:
    """Build the clean slots of a split (B1-2), in case order. ``limit``: only the first n clean slots."""
    allocation = allocate(gen, quotas, split)
    world = build_world(gen, split)
    companies = _Companies(world)
    clean = sorted((s for s in allocation.slots if s.primary == "clean"), key=lambda s: s.case_index)
    owner = assign_companies(gen, allocation.slots, world)
    build = Build(split, allocation, world)
    for slot in clean[:limit]:
        build.cases.append(_plant(gen, split, owner[slot.case_index], slot, companies, provenance, build.redraws))
    return build


def _plant(gen: Generation, split: SplitSpec, cw: CompanyWorld, slot: Slot, companies: _Companies,
           provenance: Provenance | None, redraws: Counter) -> GeneratedCase:
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            built = clean_case(gen, split, cw, slot, attempt)
        except NoCleanForm as e:
            redraws["no clean form"] += 1
            last = str(e)
            continue
        env = envelope(built.case_id, split.name, Case.model_validate(built.case), provenance=provenance,
                       canary=split.canary)
        records = companies.records_for(built)
        answer = answer_case(records, env, catalog())
        diffs = compare(built.planted, answer)
        if not diffs:
            return GeneratedCase(built, env, records, answer)
        redraws[diffs[0].split(" ")[0]] += 1
        last = "; ".join(diffs)
    raise PlantingFailed(f"slot {slot.case_index} ({slot.country}, clean): {MAX_ATTEMPTS} attempts; last: {last}")


__all__ = ["Build", "GeneratedCase", "InfeasibleDemand", "PlantingFailed", "build_clean", "compare"]
