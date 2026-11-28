"""The build loop (B1 plan section 4): plant, let the engine find, compare, redraw on any difference.

Every slot gets a clean base case and its families: the primary type's family, then the secondary's on a two-problem
slot; a tax type's family is the family of the rule the slot's first problem form names, or one drawn among the rule
families that fit the slot (its company, supplier kind, dates). Then every other rule appearance the slot names (the
rule floor) is planted on the next free line by its rule's recipe; findings and buyer actions last. The supplier and the
date follow the rules: a special supplier where a rule needs one, a date inside every rule's window. The planted truth
is the clean base's lines as the ops changed them, the primary family's decision and the union of the families' and
recipes' findings, the buyer actions, and the facts the statement registry stated. The engine's answer is compared on the decision,
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
from decision_benchmark.core.generator.quotas import as_fraction
from decision_benchmark.core.generator.slots import Allocation, Slot, allocate
from decision_benchmark.core.generator.spec import Generation, SplitSpec

from decision_benchmark.core.generator.slots import H1, H2, H3, PROBLEM
from decision_benchmark.core.generator.spec import RuleSpec

from ..countries import pack
from ..envelope import ApCaseEnvelope, envelope
from ..findings import DECISION, UnsupportedCase
from ..models import AnswerKey, Case, CompanyRecords, Email, GoodsReceipt, LedgerInvoice, PurchaseOrder
from ..rules import answer_case
from .country import CannotPlant
from .entities import CompanyWorld, build_world, catalog
from .hardcases import Template, apply, requires_taxed_line, rule_families, templates
from .ops import OPS, Draft, Turns, plant_rule
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
    rules: list[str] = field(default_factory=list)
    """The rules planted: the families' and the slot's rule appearances."""
    branch: str | None = None
    """The dated branch the case plants, "<branch>:<side>" (generation.yaml boundaries)."""
    realized: dict[str, str] = field(default_factory=dict)
    """A slot rule planted as one of its branches that another rule decides: slot rule -> the rule in the key."""
    hard: str | None = None
    """The hard kind the slot was given (H1 scan-only, H2 conflicting documents, H3 missing information)."""
    row: str | None = None
    """H2: the precedence row (generation.yaml hard_cases.rows)."""
    missing: list[dict] = field(default_factory=list)
    """H3: the facts planted missing (Draft.missing)."""
    conflict: dict | None = None
    """H2: what the invoice says and the patches that put it in the governing document (Draft.conflict)."""

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
            "planted_rules": self.rules,
            "branch": self.branch,
            "open_questions": self.built.planted.open_questions,
            "hard_kinds": [self.hard] if self.hard else [],
            "precedence_row": self.row,
            "scan_only": self.hard == H1,
            "missing_facts": self.missing,
            "conflict": self.conflict,
            "attempt": self.built.attempt,
        }


SCAN_ONLY_MODALITIES = ("scan", "photo", "pdf", "scan", "photo", "pdf", "scan", "photo", "pdf", "scan")
"""The scan-only invoice files in turn: 4 scans, 3 photos, 3 PDFs in every 10 (B1 plan decision 11)."""


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
    turns: Counter = field(default_factory=Counter)
    """How often each recipe's turn key was taken by a kept case (ops.Turns)."""
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

    def branch_report(self, gen: Generation) -> dict:
        """report/branches.json: every branch the engine can decide, per country, with the cases planting it."""
        from .branches import coverage

        return {"split": self.split.name, "cases": len(self.cases), "branches": coverage(gen, self.cases)}

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
    """The generator truth after the ops: the primary family's decision (APPROVE when no family and no finding), every
    family's findings plus the ops' and recipes' own, the lines as the ops left them, the buyer actions (each once, in
    line order), and the stated facts."""
    findings = sorted(set([f for t in families for f in t.expect.findings] + d.findings))   # one per code (the key's)
    decision = families[0].expect.decision if families else (DECISION[findings[0]].value if findings else "APPROVE")
    actions: list = []
    seen: set = set()
    for n in sorted(built.planted.line_actions):
        line = built.case["invoice"]["lines"][n - 1]
        for a in built.planted.line_actions[n]:
            # Each action once, as the key lists them: a withholding counts with its base (the line's net amount).
            key = (*a, line["net_amount"] if a[0] == "WITHHOLD_TAX" else None)
            if key not in seen:
                seen.add(key)
                actions.append(tuple(a))
    return Planted(
        decision=decision, lines=built.planted.lines, findings=findings, buyer_actions=actions,
        facts=stated_facts(built.case), line_actions=built.planted.line_actions,
        open_questions=sorted(set(built.planted.open_questions)))


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


def fact_parser(country: str):
    """check_evidence's reader for facts stated as phrases (generator/phrases.py)."""
    from . import phrases

    return lambda fact, text: phrases.parse(country, fact, text)


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
    """Slots to companies, round robin per country in case order among the companies of a kind the slot's rules
    allow (each company gets an even share of what it can take), foreign-supplier slots in a round of their own (so
    every kind of buyer gets its share of the rules that turn on the buyer there). A reserved kind takes only the slots
    that name it, a hand-over kind its share of the hand-over slots."""
    out: dict[int, CompanyWorld] = {}
    seen: Counter = Counter()
    handovers: Counter = Counter()
    for s in sorted(slots, key=lambda s: s.case_index):
        if gen.type(s.primary).handover and s.hard == H3 and s.companies is None:
            # A hand-over kind takes its share of the country's missing-information slots (one in every 1/share, where
            # it has a company).
            i, handovers[s.country] = handovers[s.country], handovers[s.country] + 1
            took = None
            for kind, share in sorted(gen.handover_companies.items()):
                mine = [cw for cw in world[s.country] if cw.kind == kind]
                step = int(1 / as_fraction(share))
                if mine and i % step == 0:
                    took = mine[seen[(s.country, kind)] % len(mine)]
                    seen[(s.country, kind)] += 1
                    break
            if took is not None:
                out[s.case_index] = took
                continue
        allowed = (lambda kind: kind in s.companies) if s.companies is not None else (
            lambda kind: kind not in gen.reserved_companies)
        companies = [cw for cw in world[s.country] if allowed(cw.kind)]
        if not companies:
            raise PlantingFailed(f"slot {s.case_index}: no {s.country} company of kind {s.companies}")
        key = (s.country, s.companies, s.foreign)
        out[s.case_index] = companies[seen[key] % len(companies)]
        seen[key] += 1
    return out


def _rules(gen: Generation) -> dict[str, RuleSpec]:
    return {r.id: r for r in gen.rules}


def planted_hard_kinds() -> set[str]:
    """The hard kinds some family plants (Template.hard)."""
    return {t.hard for ts in templates().values() for t in ts if t.hard}


def family_fits(gen: Generation, t: Template, slot: Slot, cw: CompanyWorld) -> bool:
    """A drawn family's rule can join the slot: its problem form on the slot's dates, supplier and company."""
    if t.foreign is not None and t.foreign != slot.foreign:
        return False
    if t.hard != (slot.hard if slot.hard in planted_hard_kinds() else None):
        return False                   # a hard kind some family plants comes only from such a family
    if t.companies and cw.kind not in t.companies:
        return False
    if cw.kind in gen.handover_companies and cw.kind not in t.companies:
        return False                   # a hand-over kind takes only the families that name it
    if t.supplier and slot.supplier and t.supplier != slot.supplier:
        return False
    if t.rule is None:
        return True
    r = _rules(gen).get(t.rule)
    if r is None or r.country != slot.country or any(u.rule == t.rule and u.form == PROBLEM for u in slot.rules):
        return False
    if any(u.rule == t.rule for u in slot.rules):
        # A correct form of the rule on the slot gives way to the family (line 1), if the other rules keep a line each.
        rules = _rules(gen)
        own = sum(1 for u in slot.rules if u.rule != t.rule and u.rule in rules
                  and (u.carrier == "line" or rules[u.rule].takes_line or rules[u.rule].foreign))
        if slot.lines < 1 + own:
            return False
    turns = r.appearance_turns.get(PROBLEM, ())
    sides = {t.foreign for t in turns if t.foreign is not None and (not t.companies or cw.kind in t.companies)}
    if slot.foreign not in sides and ((r.foreign and not slot.foreign)
                                      or ((r.domestic or PROBLEM in r.domestic_forms) and slot.foreign)):
        return False
    if set(r.exclude_types) & set(slot.types()):
        return False
    if r.whole_case and slot.mixed:
        return False                   # it decides every line, so the case can't be a mixed one
    if r.whole_case and slot.row and next(x for x in gen.hard_cases.rows if x.id == slot.row).line:
        return False                   # nor carry a precedence row's own line
    if slot.lines < r.min_lines.get(PROBLEM, 1):
        return False
    if r.supplier and slot.supplier and r.supplier != slot.supplier:
        return False
    kind = slot.supplier or r.supplier
    needs = set(r.needs).union(*(_rules(gen)[u.rule].needs for u in slot.rules if u.rule in _rules(gen)))
    boundary = _branch(gen, slot)
    if boundary is not None:
        needs |= set(boundary.needs)           # the dated branch line the slot carries
    if kind and needs & set(gen.supplier_lacks.get(kind, ())):
        return False
    if gen.needs_clash(needs):
        return False
    if r.companies and cw.kind not in set(r.companies).union(*(t.companies for t in turns)):
        return False
    if cw.kind in gen.reserved_companies and cw.kind not in set(r.companies).union(*(t.companies for t in turns)):
        return False                   # a reserved company takes only the rules that name its kind
    lo, hi = r.window(PROBLEM, gen.windows[slot.country])
    assert slot.window is not None
    return max(lo, slot.window[0]) <= min(hi, slot.window[1])


def choose_families(slot: Slot, attempt: int, seed: int, gen: Generation | None = None,
                    cw: CompanyWorld | None = None) -> list[Template]:
    """The primary type's family and, on a two-problem slot, a compatible secondary family (weighted draws). A tax
    type takes the family of the slot's first problem form if it names one."""
    r = rng(seed, "case", slot.case_index, "families", attempt)
    fams = templates()
    if slot.primary == "clean":
        return []
    named = next((rule_families()[u.rule] for u in slot.rules if u.form == PROBLEM and u.rule in rule_families()), None)

    def options(type_name: str) -> list[Template]:
        if gen is not None and gen.type(type_name).tax and named is not None:
            return [named]
        out = [t for t in fams[type_name] if slot.country in t.countries]
        if gen is not None and cw is not None:
            out = [t for t in out if family_fits(gen, t, slot, cw)]
        return out

    primaries = options(slot.primary)
    if slot.secondary is None:
        return [_weighted(r, primaries)]
    pairs = [(a, b) for a in primaries for b in options(slot.secondary) if a.compatible(b)]
    return list(_weighted(r, pairs, weight=lambda p: p[0].weight * p[1].weight))


def _weighted(r, items, weight=lambda t: t.weight):
    if not items:
        raise CannotPlant("no family fits the slot")
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


def _tally(build: Build, families: list[Template], planted: Planted, cause: str | None, diff: str,
           rules: list[str] = (), extra: list[str] = ()) -> None:
    """Count an attempt for each family it uses (the drawn ones, and the family of each rule the slot plants) and each
    rule it plants: the slot's rules, the families' rules, and the rules the planted lines and buyer actions name."""
    names = [t.family for t in families] or ["clean_base"]
    names += [rule_families()[r].family for r in rules if r in rule_families()
              and rule_families()[r].family not in names]
    names += [x for x in extra if x.startswith("branch:") and x not in names]
    for name in names:
        build.families.setdefault(name, _Tally()).add(cause, diff)
    named = {x[2] for x in planted.lines if x[2]} | {a[2] for a in planted.buyer_actions if a[2]} | set(rules)
    for rule in sorted(named):
        build.rules.setdefault(rule, _Tally()).add(cause, diff)


def _plant(gen: Generation, split: SplitSpec, cw: CompanyWorld, slot: Slot, companies: _Companies,
           provenance: Provenance | None, build: Build) -> GeneratedCase:
    last, names = "", ["clean_base"]
    for attempt in range(MAX_ATTEMPTS):
        build.max_slot_attempts = max(build.max_slot_attempts, attempt + 1)
        build.attempts += 1
        case, last, names = attempt_slot(gen, split, cw, slot, companies, provenance, build, attempt)
        if case is not None:
            return case
    raise PlantingFailed(f"slot {slot.case_index} ({slot.country}, {slot.primary}"
                         f"{'+' + slot.secondary if slot.secondary else ''}): {MAX_ATTEMPTS} attempts, planted != found "
                         f"on every one; last families {'+'.join(names)}: {last}")


def attempt_slot(gen: Generation, split: SplitSpec, cw: CompanyWorld, slot: Slot, companies: _Companies,
                 provenance: Provenance | None, build: Build, attempt: int
                 ) -> tuple[GeneratedCase | None, str, list[str]]:
    """One draw of a slot: the case if planted = found, else None with the difference (tallied in build)."""
    try:
        families = choose_families(slot, attempt, split.seed, gen, cw)
    except CannotPlant as e:
        build.families.setdefault("no family", _Tally()).add("no family fits", str(e))
        return None, str(e), ["clean_base"]
    names = [t.family for t in families] or ["clean_base"]
    family_rules = [t.rule for t in families if t.rule]
    g = pack(cw.country).generation
    floor = [u for u in slot.rules if u.rule not in family_rules] if g.plants_rules else []
    rules = _rules(gen)
    kind = slot.supplier or next((rules[x].supplier for x in family_rules if rules[x].supplier), "") or next(
        (t.supplier for t in families if t.supplier), "")
    uses = [(x, PROBLEM) for x in family_rules] + [(u.rule, u.form) for u in floor]
    planted_rules = [x for x, _ in uses]
    # "shared": the case plants more than one rule, so a supplier pool one rule's branch needs (e.g. a supplier not
    # yet registered) mustn't be offered (generator/country.py suppliers_for).
    together = set(planted_rules)
    shared = len(together) > 1 and not all(y in rules[x].alone_with for x in together for y in together
                                            if x != y and x in rules)
    shared = shared or slot.boundary is not None or slot.mixed is not None    # a branch or split line is planted too
    needs = {"shared"} if shared else set()
    needs |= set().union(*(rules[x].needs for x in planted_rules if x in rules),
                        *(rules[x].form_needs.get(f, ()) for x, f in uses if x in rules))
    branch = None
    boundary = _branch(gen, slot) if g.plants_rules else None
    if boundary is not None:
        needs |= set(boundary.needs)
    if slot.mixed == "split":
        needs |= set(gen.mixed.split_needs)
    needs |= {x for t in families for x in t.needs}
    if slot.row:
        # A precedence row's case: what its supplier must do (a supplier offered in turn must do it too).
        needs |= set(next(r for r in gen.hard_cases.rows if r.id == slot.row).needs)
    turns = Turns(build.turns, attempt)
    try:
        window = _window(gen, slot, [(rules[x], PROBLEM) for x in family_rules])
        built = clean_case(gen, split, cw, slot, attempt, need_taxed=requires_taxed_line(families), window=window,
                           suppliers=lambda day: g.suppliers_for(cw, kind, needs, slot.foreign, day, turns))
    except (NoCleanForm, CannotPlant) as e:
        build.families.setdefault(names[0], _Tally()).add("no clean form", str(e))
        return None, str(e), names
    d = Draft(built, cw, rng(split.seed, "case", slot.case_index, "ops", attempt), uses=list(slot.rules), turns=turns,
              types=tuple(slot.types()))
    taken: set[int] = set()
    calls = [(t, t.calls(rng(split.seed, "case", slot.case_index, "params", t.family, attempt))) for t in families]
    try:
        for _, cs in calls:                                   # the families' rule lines (line 1)
            for name, args in cs:
                if OPS[name].early:
                    OPS[name].fn(d, **args)
        taken = _plant_floor(d, floor, first_line=2 if family_rules else 1,
                             own_line={r.id for r in gen.rules if r.takes_line or r.foreign})
        if boundary is not None:
            free = [k for k in range(1, len(d.invoice["lines"]) + 1)
                    if k not in taken and not (family_rules and k == 1)]
            if not free and boundary.line:
                raise CannotPlant(f"no free line for the {boundary.branch} branch")
            g.plant_branch(d, free[0] if boundary.line else 0, boundary.branch, slot.boundary[1])
            branch = f"{boundary.branch}:{slot.boundary[1]}"
            if boundary.line:
                taken.add(free[0])
        if slot.mixed == "split" and g.plants_rules:
            free = [k for k in range(1, len(d.invoice["lines"]) + 1)
                    if k not in taken and not (family_rules and k == 1)]
            if not free:
                raise CannotPlant("no free line for the split")
            g.plant_split(d, free[0])
            taken.add(free[0])
        if slot.hard == H2 and slot.row and g.plants_rules:
            row = next(r for r in gen.hard_cases.rows if r.id == slot.row)
            line = None
            if row.line:
                free = [k for k in range(1, len(d.invoice["lines"]) + 1)
                        if k not in taken and not (family_rules and k == 1)]
                if slot.mixed == "lines":
                    free = free[:-1]                       # the last free line is the mixing line's (_mix)
                if not free and not row.rides_on:
                    raise CannotPlant(f"no free line for the {row.id} conflict")
                line = free[0] if free else None          # None: it rides on a planted line (rides_on)
                if line is not None:
                    taken.add(line)
            g.plant_conflict(d, line, row.id)
        if g.plants_rules:
            g.finish_case(d)
        if slot.mixed == "lines" and g.plants_rules:          # before the families' ops, which scale amounts
            _mix(d, g, taken | ({1} if family_rules else set()))
    except CannotPlant as e:
        _tally(build, families, built.planted, "cannot plant", str(e), planted_rules, _branch_names(boundary))
        return None, f"cannot plant: {e}", names
    apply(d, [(t, [c for c in cs if not OPS[c[0]].early]) for t, cs in calls])
    if d.late:                                                # facts stated from the final amounts
        for fn in d.late:
            fn()
        d.refresh()
    try:
        for fn in d.final:                                    # edits the last refresh would undo
            fn()
    except CannotPlant as e:
        _tally(build, families, built.planted, "cannot plant", str(e), planted_rules, _branch_names(boundary))
        return None, f"cannot plant: {e}", names
    if slot.hard == H2 and g.plants_rules and d.conflict is None:
        raise PlantingFailed(f"slot {slot.case_index}: the {slot.row} conflict recorded no patch")
    types = [slot.primary] + ([slot.secondary] if slot.secondary else [])
    built.planted = planted_truth(built, families, d)
    built.case |= {"exception_types": [] if slot.primary == "clean" else types,
                   "families": [t.family for t in families] or ["clean_base"],
                   "two_problems": slot.secondary is not None}
    modality = "pdf"
    if slot.hard == H1:
        # Scan-only: the invoice ships as a scan, a photo or a PDF only (B1 plan decision 11: 40 / 30 / 30), in turn.
        modality = turns.take("H1 modality", list(SCAN_ONLY_MODALITIES))
    env = envelope(built.case_id, split.name, Case.model_validate(built.case), provenance=provenance,
                   canary=split.canary, modality=modality)
    records = companies.records_for(built)
    try:
        answer = answer_case(records, env, catalog())
    except UnsupportedCase as e:
        _tally(build, families, built.planted, "engine unsupported", str(e), planted_rules, _branch_names(boundary))
        return None, f"unsupported: {e}", names
    diffs = compare(built.planted, answer)
    if not diffs:
        _tally(build, families, built.planted, None, "", planted_rules, _branch_names(boundary))
        turns.commit()
        planted = list(dict.fromkeys(d.realized.get(x, x) for x in planted_rules))
        return GeneratedCase(built, env, records, answer, names, planted, branch, dict(d.realized), slot.hard,
                             slot.row, list(d.missing), d.conflict), "", names
    _tally(build, families, built.planted, cause_of(diffs, built.planted, answer), "; ".join(diffs), planted_rules,
           _branch_names(boundary))
    return None, "; ".join(diffs), names


__all__ = ["Build", "GeneratedCase", "PlantingFailed", "attempt_slot", "build_clean", "build_split", "compare",
           "fact_parser", "planted_truth", "stated_facts"]

def _window(gen: Generation, slot: Slot, extra: list[tuple[RuleSpec, str]]) -> tuple:
    """The slot's dates narrowed by the drawn families' rule windows."""
    assert slot.window is not None
    lo, hi = slot.window
    for r, form in extra:
        a, b = r.window(form, gen.windows[slot.country])
        lo, hi = max(lo, a), min(hi, b)
    if lo > hi:
        raise CannotPlant("the families' rule windows miss the slot's dates")
    return lo, hi


def _mix(d: Draft, g, used: set[int]) -> None:
    """A mixed 'lines' case: at least two lines with different outcomes; if the planted lines all agree, a line no
    rule took becomes one that differs."""
    if len({(t, b) for _, t, b in d.built.planted.lines}) >= 2:
        return
    free = [k for k in range(1, len(d.invoice["lines"]) + 1) if k not in used]
    if not free:
        raise CannotPlant("no free line to mix")
    g.mix_line(d, free[-1])
    if len({(t, b) for _, t, b in d.built.planted.lines}) < 2:
        raise CannotPlant("the mixing line didn't change the outcome")


def _branch_names(boundary) -> list[str]:
    return [f"branch:{boundary.branch}"] if boundary is not None else []


def _branch(gen: Generation, slot: Slot):
    """The dated boundary whose branch the slot carries, if any."""
    if slot.boundary is None:
        return None
    day, _ = slot.boundary
    return next((b for b in gen.boundaries if b.country == slot.country and b.day == day and b.branch
                 and b.branch == (slot.branch or b.branch)), None)


def _plant_floor(d: Draft, uses: list, first_line: int, own_line: set[str] = frozenset()) -> set[int]:
    """Plant the slot's other rule appearances: line rules on the next free lines, then findings and buyer actions
    (an action rule takes a line no line rule took, else one of an imported service, whose basis it keeps)."""
    n = first_line
    taken: dict[int, str] = {}
    for u in [u for u in uses if u.carrier == "line"]:
        if n > len(d.invoice["lines"]):
            raise CannotPlant(f"no line left for {u.rule}")
        plant_rule(d, n, u.rule, u.form)
        taken[n] = u.rule
        n += 1
    by_line_rules = set(taken)            # an action may reuse a line rule's line, never another action's
    for u in [u for u in uses if u.carrier != "line"]:
        free = [k for k in range(1, len(d.invoice["lines"]) + 1) if k not in taken and k >= first_line]
        bases = pack(d.cw.country).generation.reusable_bases
        reuse = [k for k, rule in taken.items() if k in by_line_rules and d.built.planted.lines[k - 1][2] in bases]
        line = (free or reuse or [len(d.invoice["lines"])])[0]
        plant_rule(d, line, u.rule, u.form)
        if u.rule in own_line:            # it set the line (others only add a finding or a phrase)
            taken[line] = u.rule
    return set(taken)
