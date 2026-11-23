"""The reachability check (B1 plan section 3.4): each rule planted on 50 draws, in each of its forms, and the engine
must agree on every draw (no redraws).

A draw is a slot made for the rule alone: a tax slot for its problem form (the rule's family plants line 1), a clean
slot for its correct form (the rule is planted as a floor appearance), an invalid-invoice slot for a finding rule, a
foreign-supplier slot where the rule needs one; its dates are the rule's window, its supplier the kind the rule needs,
its company one of the kinds it allows (in turn). Country neutral: the countries whose pack plants rules.
"""

from __future__ import annotations

from collections import Counter

from decision_benchmark.core.generator.slots import CORRECT, PROBLEM, RuleUse, Slot
from decision_benchmark.core.generator.spec import Generation, RuleSpec, SplitSpec

from ..countries import pack
from .build import Build, _Companies, attempt_slot
from .entities import build_world

DRAWS = 50


def slot_for(gen: Generation, rule: RuleSpec, form: str, draw: int) -> Slot:
    tax = next(t.name for t in gen.types if t.tax)
    clean = next(t.name for t in gen.types if t.tier is None and not t.handover)
    primary = tax if form == PROBLEM else (rule.types[0] if rule.types else clean)
    lines = 2 if rule.carrier == "line" and form == CORRECT and primary == tax else 1
    return Slot(key=draw, country=rule.country, primary=primary, foreign=rule.foreign, lines=lines,
                rules=[RuleUse(rule.id, form, rule.carrier)] if form == CORRECT or primary != tax else [],
                window=rule.window(form, gen.windows[rule.country]), supplier=rule.supplier,
                companies=rule.companies or None, case_index=900_000 + draw)


def check(gen: Generation, split: SplitSpec, draws: int = DRAWS) -> dict:
    """{rule: {form: {"draws", "agreed", "causes", "first_diffs"}}} for every rule of a country with recipes."""
    world = build_world(gen, split)
    companies = _Companies(world)
    out: dict[str, dict] = {}
    for rule in gen.rules:
        if not pack(rule.country).generation.plants_rules:
            continue
        forms = [f for f, ok in ((PROBLEM, rule.problem_form), (CORRECT, rule.correct_form)) if ok]
        for form in forms:
            build = Build(split, None, world)  # type: ignore[arg-type]
            agreed, causes, diffs = 0, Counter(), []
            pool = [cw for cw in world[rule.country] if not rule.companies or cw.kind in rule.companies]
            for draw in range(draws):
                slot = slot_for(gen, rule, form, draw)
                if form == PROBLEM:
                    slot.rules = [RuleUse(rule.id, PROBLEM, rule.carrier)]
                case, last, _ = attempt_slot(gen, split, pool[draw % len(pool)], slot, companies, None, build, draw)
                if case is not None and (rule.id in case.rules):
                    agreed += 1
                else:
                    causes[last.split(":")[0] if last else "rule not planted"] += 1
                    if len(diffs) < 3:
                        diffs.append(last)
            out.setdefault(rule.id, {})[form] = {"draws": draws, "agreed": agreed, "causes": dict(causes),
                                                  "first_diffs": diffs}
    return out


__all__ = ["DRAWS", "check", "slot_for"]
