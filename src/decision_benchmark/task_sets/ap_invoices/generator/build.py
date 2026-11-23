"""The build loop (B1 plan section 4): plant, let the engine find, compare, redraw on any difference.

Every slot gets a clean base case and its families: the primary type's family, then the secondary's on a two-problem
slot. The planted truth is the clean base's lines as the ops changed them, the primary family's decision and the union
of the families' findings, and the facts the statement registry stated. The engine's answer is compared on the decision,
the finding codes, each line's treatment and basis, the buyer actions (action, rate, basis) and every gold fact (it must
equal the stated value, or be null where nothing stated it); a difference redraws the slot (next attempt number), at most
20 attempts.

``planting_report`` (report/planting.json) gives attempts, redraws and their causes per family and per rule, with the
first five diffs. The build stops (PlantingFailed) when a family or rule with at least 20 attempts redraws more than 5%,
when the overall redraw rate passes 1%, or when a slot reaches 20 attempts.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property

from decision_benchmark.core.case import Provenance
from decision_benchmark.core.generator.seeds import rng
from decision_benchmark.core.generator.slots import Allocation, Slot, allocate
from decision_benchmark.core.generator.spec import Generation, SplitSpec

from ..envelope import ApCaseEnvelope, envelope
from ..findings import UnsupportedCase
from ..models import AnswerKey, Case, CompanyRecords, Email, GoodsReceipt, LedgerInvoice, PurchaseOrder
from ..rules import answer_case
from .entities import CompanyWorld, build_world, catalog
from .hardcases import Template, apply, requires_taxed_line, templates
from .ops import Draft
from .scenario import BuiltCase, NoCleanForm, Planted, clean_case

MAX_ATTEMPTS = 20
RULE_MIN_ATTEMPTS = 20
RULE_MAX_REDRAW = Fraction(5, 100)
OVERALL_MAX_REDRAW = Fraction(1, 100)
FIRST_DIFFS = 5


class PlantingFailed(RuntimeError):
    """A slot still differs after MAX_ATTEMPTS draws, or a redraw threshold is crossed. ``report``: the planting report
    up to the failing slot, when a slot stopped the build."""

    report: dict | None = None


@dataclass
class GeneratedCase:
    built: BuiltCase
    envelope: ApCaseEnvelope
    records: CompanyRecords
    answer: AnswerKey
    families: list[str]

    def export(self) -> dict:
        """The case as JSON-ready data: envelope, the records the case adds, the answer key, the generator truth."""
        return {
            "case_id": self.built.case_id,
            "company_id": self.built.company_id,
            "envelope": self.envelope.model_dump(mode="json"),
            "purchase_orders": self.built.records["purchase_orders"],
            "goods_receipts": self.built.records["goods_receipts"],
            "ledger_add": self.built.records.get("ledger_add", []),
            "emails_add": self.built.records.get("emails_add", []),
            "answer": self.answer.model_dump(mode="json"),
            "planted": {"decision": self.built.planted.decision, "lines": self.built.planted.lines,
                        "findings": self.built.planted.findings, "buyer_actions": self.built.planted.buyer_actions},
            "families": self.families,
            "attempt": self.built.attempt,
        }


@dataclass
class _Tally:
    attempts: int = 0
    redraws: int = 0
    causes: Counter = field(default_factory=Counter)
    diffs: list[str] = field(default_factory=list)

    def add(self, cause: str | None, diff: str = "") -> None:
        self.attempts += 1
        if cause is not None:
            self.redraws += 1
            self.causes[cause] += 1
            if len(self.diffs) < FIRST_DIFFS:
                self.diffs.append(diff)

    def export(self) -> dict:
        rate = Fraction(self.redraws, self.attempts) if self.attempts else Fraction(0)
        return {"attempts": self.attempts, "redraws": self.redraws, "redraw_rate": f"{float(rate):.4f}",
                "causes": dict(sorted(self.causes.items())), "first_diffs": self.diffs}


@dataclass
class Build:
    split: SplitSpec
    allocation: Allocation
    world: dict[str, list[CompanyWorld]]
    cases: list[GeneratedCase] = field(default_factory=list)
    families: dict[str, _Tally] = field(default_factory=dict)
    rules: dict[str, _Tally] = field(default_factory=dict)
    max_slot_attempts: int = 0
    attempts: int = 0
    """Every draw, including those of a slot that stopped the build."""

    @property
    def redraws(self) -> Counter:
        out: Counter = Counter()
        for t in self.families.values():
            out.update(t.causes)
        return out

    def planting_report(self) -> dict:
        attempts = self.attempts
        redraws = attempts - len(self.cases)
        mix = Counter(c.built.case["exception_types"][0] if c.built.case["exception_types"] else "clean"
                      for c in self.cases)
        pairs = Counter("+".join(c.built.case["exception_types"]) for c in self.cases if c.built.case["two_problems"])
        return {
            "split": self.split.name, "cases": len(self.cases), "attempts": attempts, "redraws": redraws,
            "redraw_rate": f"{redraws / attempts:.4f}" if attempts else "0.0000",
            "max_slot_attempts": self.max_slot_attempts,
            "exception_mix": dict(sorted(mix.items())), "two_problems": {"total": sum(pairs.values()),
                                                                          "pairs": dict(sorted(pairs.items()))},
            "thresholds": {"family_or_rule_max_redraw": str(RULE_MAX_REDRAW), "at_attempts": RULE_MIN_ATTEMPTS,
                           "overall_max_redraw": str(OVERALL_MAX_REDRAW), "slot_max_attempts": MAX_ATTEMPTS},
            "families": {k: v.export() for k, v in sorted(self.families.items())},
            "rules": {k: v.export() for k, v in sorted(self.rules.items())},
            "causes": dict(sorted(self.redraws.items())),
        }

    def check_thresholds(self) -> None:
        report = self.planting_report()
        problems = []
        for kind, tallies in (("family", self.families), ("rule", self.rules)):
            for name, t in tallies.items():
                if t.attempts >= RULE_MIN_ATTEMPTS and Fraction(t.redraws, t.attempts) > RULE_MAX_REDRAW:
                    problems.append(f"{kind} {name}: {t.redraws} of {t.attempts} attempts redrawn")
        if report["attempts"] and Fraction(report["redraws"], report["attempts"]) > OVERALL_MAX_REDRAW:
            problems.append(f"overall: {report['redraws']} of {report['attempts']} attempts redrawn")
        if problems:
            raise PlantingFailed("; ".join(problems))

    def dumps(self) -> str:
        """Every built case, one JSON line each, keys sorted: the bytes the reproducibility check compares."""
        return "".join(json.dumps(c.export(), sort_keys=True) + "\n" for c in self.cases)


class _Companies:
    """Each company's records validated once and shared by its cases (each case adds its own documents)."""

    def __init__(self, world: dict[str, list[CompanyWorld]]) -> None:
        self.world = world

    @cached_property
    def validated(self) -> dict[str, CompanyRecords]:
        return {cw.company_id: CompanyRecords.model_validate(cw.records())
                for companies in self.world.values() for cw in companies}

    def records_for(self, built: BuiltCase) -> CompanyRecords:
        base = self.validated[built.company_id]
        r = built.records
        return base.model_copy(update={
            "purchase_orders": [PurchaseOrder.model_validate(p) for p in r["purchase_orders"]],
            "goods_receipts": [GoodsReceipt.model_validate(g) for g in r["goods_receipts"]],
            "ledger": base.ledger + [LedgerInvoice.model_validate(x) for x in r.get("ledger_add", [])],
            "emails": base.emails + [Email.model_validate(x) for x in r.get("emails_add", [])]})


def _action(a) -> tuple[str, str | None, str | None]:
    return (a.action, None if a.rate is None else str(a.rate), a.basis)


def stated_facts(case: dict) -> dict[tuple[int, str], object]:
    """(line_no, fact) -> stated value, from the invoice lines as the statement registry wrote them."""
    lines = (case.get("invoice") or {}).get("lines", [])
    return {(line["line_no"], name): f["value"] for line in lines for name, f in (line.get("facts") or {}).items()}


def planted_truth(built: BuiltCase, families: list[Template], d: Draft) -> Planted:
    """The generator truth after the ops: the primary family's decision, every family's findings plus the ops' own,
    the lines as the ops left them, and the stated facts."""
    return Planted(
        decision=families[0].expect.decision if families else "APPROVE", lines=built.planted.lines,
        findings=sorted([f for t in families for f in t.expect.findings] + d.findings),
        buyer_actions=built.planted.buyer_actions, facts=stated_facts(built.case))


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
    found_actions = sorted((_action(a) for a in answer.buyer_actions), key=repr)
    want_actions = sorted((tuple(a) for a in planted.buyer_actions), key=repr)
    if found_actions != want_actions:
        diffs.append(f"buyer actions {found_actions} != {want_actions}")
    for entry in answer.facts or []:
        for name, fact in sorted(entry.items()):
            if name == "line_no":
                continue
            key = (entry["line_no"], name)
            if fact.get("value") != planted.facts.get(key):
                diffs.append(f"fact line {key[0]} {name} {fact.get('value')!r} != stated {planted.facts.get(key)!r}")
    return diffs


def cause_of(diffs: list[str], planted: Planted, answer: AnswerKey) -> str:
    """The redraw cause the plan names (section 4)."""
    first = diffs[0]
    if first.startswith("findings"):
        found = {f.code.value for f in answer.findings}
        return "extra finding" if found - set(planted.findings) else "missing finding"
    if first.startswith("lines"):
        found = [(t.treatment, t.basis) for t in answer.tax_lines]
        want = [(x[1], x[2]) for x in planted.lines]
        if [f[0] for f in found] != [w[0] for w in want]:
            return "treatment differs"
        return "basis differs"
    if first.startswith("buyer"):
        return "action differs"
    if first.startswith("fact"):
        return "fact differs"
    return "decision differs"


def assign_companies(gen: Generation, slots: list[Slot], world: dict[str, list[CompanyWorld]]) -> dict[int, CompanyWorld]:
    """Slots to companies, round robin per country in case order (each company gets an even share)."""
    out: dict[int, CompanyWorld] = {}
    seen: Counter = Counter()
    for s in sorted(slots, key=lambda s: s.case_index):
        companies = world[s.country]
        out[s.case_index] = companies[seen[s.country] % len(companies)]
        seen[s.country] += 1
    return out


def choose_families(slot: Slot, attempt: int, seed: int) -> list[Template]:
    """The primary type's family and, on a two-problem slot, a compatible secondary family (weighted draws)."""
    r = rng(seed, "case", slot.case_index, "families", attempt)
    fams = templates()
    if slot.primary == "clean":
        return []
    primaries = [t for t in fams[slot.primary] if slot.country in t.countries]
    if slot.secondary is None:
        return [_weighted(r, primaries)]
    pairs = [(a, b) for a in primaries for b in fams[slot.secondary] if slot.country in b.countries and a.compatible(b)]
    return list(_weighted(r, pairs, weight=lambda p: p[0].weight * p[1].weight))


def _weighted(r, items, weight=lambda t: t.weight):
    total = sum(weight(x) for x in items)
    pick = r.randrange(total)
    for x in items:
        pick -= weight(x)
        if pick < 0:
            return x
    raise AssertionError("unreachable")


def build_split(gen: Generation, quotas: dict, split: SplitSpec, provenance: Provenance | None = None,
                limit: int | None = None, primaries: set[str] | None = None, check: bool = True) -> Build:
    """Build a split's slots in case order (``primaries``: only those primary types; ``limit``: the first n)."""
    allocation = allocate(gen, quotas, split)
    world = build_world(gen, split)
    companies = _Companies(world)
    owner = assign_companies(gen, allocation.slots, world)
    slots = sorted((s for s in allocation.slots if primaries is None or s.primary in primaries),
                   key=lambda s: s.case_index)
    build = Build(split, allocation, world)
    for slot in slots[:limit]:
        try:
            build.cases.append(_plant(gen, split, owner[slot.case_index], slot, companies, provenance, build))
        except PlantingFailed as e:
            e.report = build.planting_report()      # db-generate writes it: a stopped build still shows why
            raise
    if check:
        build.check_thresholds()
    return build


def build_clean(gen: Generation, quotas: dict, split: SplitSpec, provenance: Provenance | None = None,
                limit: int | None = None) -> Build:
    """The clean slots only (B1-2)."""
    return build_split(gen, quotas, split, provenance, limit, primaries={"clean"})


def _tally(build: Build, families: list[Template], planted: Planted, cause: str | None, diff: str) -> None:
    for name in [t.family for t in families] or ["clean_base"]:
        build.families.setdefault(name, _Tally()).add(cause, diff)
    for basis in sorted({x[2] for x in planted.lines if x[2]}):
        build.rules.setdefault(basis, _Tally()).add(cause, diff)


def _plant(gen: Generation, split: SplitSpec, cw: CompanyWorld, slot: Slot, companies: _Companies,
           provenance: Provenance | None, build: Build) -> GeneratedCase:
    last, names = "", ["clean_base"]
    for attempt in range(MAX_ATTEMPTS):
        build.max_slot_attempts = max(build.max_slot_attempts, attempt + 1)
        build.attempts += 1
        families = choose_families(slot, attempt, split.seed)
        names = [t.family for t in families] or ["clean_base"]
        try:
            built = clean_case(gen, split, cw, slot, attempt, need_taxed=requires_taxed_line(families))
        except NoCleanForm as e:
            build.families.setdefault(families[0].family if families else "clean_base", _Tally()).add("no clean form", str(e))
            last = str(e)
            continue
        d = Draft(built, cw, rng(split.seed, "case", slot.case_index, "ops", attempt))
        apply(d, [(t, t.calls(rng(split.seed, "case", slot.case_index, "params", t.family, attempt))) for t in families])
        types = [slot.primary] + ([slot.secondary] if slot.secondary else [])
        built.planted = planted_truth(built, families, d)
        built.case |= {"exception_types": [] if slot.primary == "clean" else types,
                       "families": [t.family for t in families] or ["clean_base"],
                       "two_problems": slot.secondary is not None}
        env = envelope(built.case_id, split.name, Case.model_validate(built.case), provenance=provenance,
                       canary=split.canary)
        records = companies.records_for(built)
        try:
            answer = answer_case(records, env, catalog())
        except UnsupportedCase as e:
            _tally(build, families, built.planted, "engine unsupported", str(e))
            last = f"unsupported: {e}"
            continue
        diffs = compare(built.planted, answer)
        if not diffs:
            _tally(build, families, built.planted, None, "")
            return GeneratedCase(built, env, records, answer, [t.family for t in families] or ["clean_base"])
        _tally(build, families, built.planted, cause_of(diffs, built.planted, answer), "; ".join(diffs))
        last = "; ".join(diffs)
    raise PlantingFailed(f"slot {slot.case_index} ({slot.country}, {slot.primary}"
                         f"{'+' + slot.secondary if slot.secondary else ''}): {MAX_ATTEMPTS} attempts, planted != found "
                         f"on every one; last families {'+'.join(names)}: {last}")


__all__ = ["Build", "GeneratedCase", "PlantingFailed", "build_clean", "build_split", "compare", "planted_truth",
           "stated_facts"]
