"""The slot allocator (B1 plan §3.6): one deterministic pass that turns a split's quotas into a table of case slots.

Order: exception type x country and the two-problem pairs; hard kinds; foreign suppliers and line counts; mixed
cases; the rule floor; the date-boundary floor. The axes meet only through explicit compatibility rules, every
quota is met exactly, and a demand that can't be placed raises InfeasibleDemand naming it. The result goes to
``report/slots.json`` (``Allocation.report()``), which tests compare with the plan's tables.

Generic: countries, exception types, rule ids and precedence rows are strings the task set supplies.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction
from math import floor

from .quotas import InfeasibleDemand, apportion, as_fraction, halves, share_of
from .seeds import rng
from .spec import Generation, RuleSpec, SplitSpec

H1, H2, H3 = "H1", "H2", "H3"
"""Hard kinds: scan-only, conflicting documents, missing information (B1 plan §3.2)."""
PROBLEM, CORRECT = "problem", "correct"
MAX_PROBLEM_LINES = 2
"""A tax slot carries at most two planted problem lines."""


@dataclass
class RuleUse:
    rule: str
    form: str
    carrier: str


@dataclass
class Slot:
    key: int
    """Position before the final shuffle (stable within one allocation)."""
    country: str
    primary: str
    secondary: str | None = None
    hard: str | None = None
    row: str | None = None
    foreign: bool = False
    lines: int = 1
    mixed: str | None = None
    """None, 'lines' (lines with different outcomes) or 'split' (one line turns on a split)."""
    rules: list[RuleUse] = field(default_factory=list)
    window: tuple[date, date] | None = None
    """Dates the case can take: the country window narrowed by its rules' windows and its boundary side."""
    boundary: tuple[date, str] | None = None
    branch: str = ""
    """The boundary's branch the slot carries (two boundaries may share a day)."""
    supplier: str = ""
    """The supplier kind its rules need ('' any)."""
    companies: tuple[str, ...] | None = None
    """The company kinds that can carry all its rules (None: any)."""
    case_index: int = 0

    def types(self) -> tuple[str, ...]:
        return (self.primary,) if self.secondary is None else (self.primary, self.secondary)

    def export(self) -> dict:
        return {
            "case_index": self.case_index, "country": self.country, "primary": self.primary,
            "secondary": self.secondary, "hard": self.hard, "row": self.row, "foreign": self.foreign,
            "lines": self.lines, "mixed": self.mixed,
            "rules": [{"rule": u.rule, "form": u.form, "carrier": u.carrier} for u in self.rules],
            "window": [self.window[0].isoformat(), self.window[1].isoformat()] if self.window else None,
            "boundary": {"day": self.boundary[0].isoformat(), "side": self.boundary[1], "branch": self.branch}
            if self.boundary else None,
            "supplier": self.supplier or None,
            "companies": list(self.companies) if self.companies is not None else None,
        }


@dataclass
class Allocation:
    split: SplitSpec
    slots: list[Slot]
    gen: Generation
    quotas: dict[str, object]

    def report(self) -> dict:
        """The tables of B1 plan §3 for this split, counted from the slots."""
        gen, slots, n = self.gen, self.slots, self.split.n_cases
        names = [t.name for t in gen.types]
        mix = {t: {c: 0 for c in gen.countries} for t in names}
        for s in slots:
            mix[s.primary][s.country] += 1
        hard = Counter(s.hard for s in slots if s.hard)
        hard_by_type = {t: sum(1 for s in slots if s.primary == t and s.hard) for t in names}
        n_by_type = {t: sum(mix[t].values()) for t in names}
        uses = Counter((u.rule, u.form) for s in slots for u in s.rules)
        floor_tier = gen.floor_for(n)
        rules = {r.id: {"country": r.country, "family": r.family, "total": uses[(r.id, PROBLEM)] + uses[(r.id, CORRECT)],
                        "problem": uses[(r.id, PROBLEM)]} for r in gen.rules}
        groups: dict[str, int] = Counter()
        for r in gen.rules:
            groups[r.country] += rules[r.id]["total"]
        problem_by_family: dict[str, int] = Counter()
        for r in gen.rules:
            problem_by_family[f"{r.country}:{r.family}"] += rules[r.id]["problem"]
        boundaries = Counter(f"{s.country}:{s.boundary[0].isoformat()}:{s.boundary[1]}" for s in slots if s.boundary)
        return {
            "split": self.split.name, "n_cases": n, "seed": self.split.seed,
            "exception_mix": {t: {**mix[t], "total": n_by_type[t]} for t in names},
            "countries": {c: sum(1 for s in slots if s.country == c) for c in gen.countries},
            "two_problems": {
                "total": sum(1 for s in slots if s.secondary),
                "pairs": dict(sorted(Counter(f"{s.primary}+{s.secondary}" for s in slots if s.secondary).items())),
            },
            "hard": {
                "total": sum(hard.values()), H1: hard[H1], H2: hard[H2], H3: hard[H3],
                "scan_only_cap": floor(sum(hard.values()) * as_fraction(gen.hard_cases.scan_only_cap_of_hard)),
                "rows": dict(sorted(Counter(s.row for s in slots if s.row).items())),
                "row_cap": floor(hard[H2] * as_fraction(gen.hard_cases.conflict_row_cap)),
                "share_by_type": {t: f"{Fraction(hard_by_type[t], n_by_type[t]) * 100:.2f}" if n_by_type[t] else None
                                  for t in names},
            },
            "foreign": {c: sum(1 for s in slots if s.country == c and s.foreign) for c in gen.countries},
            "lines": {"cases": dict(sorted(Counter(str(s.lines) for s in slots).items(), key=lambda kv: int(kv[0]))),
                      "total": sum(s.lines for s in slots)},
            "mixed": {"total": sum(1 for s in slots if s.mixed), "split": sum(1 for s in slots if s.mixed == "split"),
                      "by_country": {c: sum(1 for s in slots if s.mixed and s.country == c) for c in gen.countries}},
            "rule_floor": {"per_rule": floor_tier.per_rule, "problem_per_rule": floor_tier.problem_per_rule,
                           "problem_per_family": floor_tier.problem_per_family, "by_country": dict(groups),
                           "total": sum(groups.values()), "problem_by_family": dict(sorted(problem_by_family.items())),
                           "rules": rules},
            "date_boundaries": dict(sorted(boundaries.items())),
            "slots": [s.export() for s in sorted(slots, key=lambda s: s.case_index)],
        }


def allocate(gen: Generation, quotas: dict[str, object], split: SplitSpec) -> Allocation:
    """Fill the slot table of one split. Deterministic given the split's seed; raises InfeasibleDemand if a quota or
    demand can't be met exactly."""
    a = _Allocator(gen, quotas, split)
    a.exception_mix()
    a.two_problems()
    a.hard_cases()
    a.foreign()
    a.lines()
    a.mixed()
    a.rule_floor()
    a.boundaries()
    a.precedence_rows()
    a.order()
    return Allocation(split, a.slots, gen, quotas)


class _Lazy:
    """A read-only mapping computed on access."""

    def __init__(self, fn) -> None:
        self.fn = fn

    def __getitem__(self, key):
        return self.fn(key)


class _Allocator:
    def __init__(self, gen: Generation, quotas: dict[str, object], split: SplitSpec) -> None:
        if [t.name for t in gen.types] != list(quotas):
            raise InfeasibleDemand("the generation types and the quota keys differ")
        self.gen, self.quotas, self.split = gen, quotas, split
        self.n = split.n_cases
        self.slots: list[Slot] = []
        self.cells: dict[tuple[str, str], list[Slot]] = {}

    def _rng(self, *purpose: str):
        return rng(self.split.seed, "slots", *purpose)

    def _shuffled(self, slots: list[Slot], *purpose: str) -> list[Slot]:
        out = list(slots)
        self._rng(*purpose).shuffle(out)
        return out

    def _pick(self, pool: list[Slot], k: int, what: str, *purpose: str) -> list[Slot]:
        if k > len(pool):
            raise InfeasibleDemand(f"{what}: needs {k} slots, only {len(pool)} fit")
        return self._shuffled(pool, *purpose)[:k]

    # 1. exception type x country
    def exception_mix(self) -> None:
        counts = {t: share_of(self.n, self.quotas[t]) for t in self.quotas}
        if sum(counts.values()) != self.n:
            raise InfeasibleDemand(f"the exception mix gives {sum(counts.values())} cases, not {self.n}")
        for t, by_country in halves(counts, self.gen.countries).items():
            for c, k in by_country.items():
                cell = [Slot(key=len(self.slots) + i, country=c, primary=t, window=self.gen.windows[c])
                        for i in range(k)]
                self.slots += cell
                self.cells[(t, c)] = cell

    # 1b. two-problem pairs
    def two_problems(self) -> None:
        tp = self.gen.two_problems
        total = share_of(self.n, tp.share)
        secondaries: dict[str, list[str]] = {}
        for p, s in tp.pairs:
            secondaries.setdefault(p, []).append(s)
        eligible = {f"{t}|{c}": len(cell) for (t, c), cell in self.cells.items() if t in secondaries}
        for key, k in apportion(total, eligible).items():
            t, c = key.split("|")
            chosen = self._pick(self.cells[(t, c)], k, f"two problems on {t} in {c}", "pairs", t, c)
            options = secondaries[t]
            start = self._rng("pairs-rotation", t, c).randrange(len(options))
            for i, slot in enumerate(sorted(chosen, key=lambda s: s.key)):
                slot.secondary = options[(start + i) % len(options)]

    # 2. hard kinds
    def hard_cases(self) -> None:
        hc = self.gen.hard_cases
        total = share_of(self.n, hc.share)
        scan = share_of(total, hc.scan_only_share_of_hard)
        cap = floor(total * as_fraction(hc.scan_only_cap_of_hard))
        if scan > cap:
            raise InfeasibleDemand(f"scan-only {scan} exceeds its cap {cap}")
        handover_cells = {k: v for k, v in self.cells.items() if self.gen.type(k[0]).handover}
        handover_n = sum(len(v) for v in handover_cells.values())
        missing_exact = handover_n * as_fraction(hc.missing_share_of_handover)
        if missing_exact.denominator != 1:
            raise InfeasibleDemand(f"missing information: {missing_exact} of {handover_n} hand-over cases isn't whole")
        missing = int(missing_exact)
        conflict = total - scan - missing
        if conflict < 0:
            raise InfeasibleDemand("hard kinds exceed the hard total")
        # H3 only in hand-over cells.
        for (t, c), k in self._apportion_cells(missing, handover_cells).items():
            for s in self._pick(self.cells[(t, c)], k, f"missing information in {t}/{c}", "H3", t, c):
                s.hard = H3
        # H1 over every cell in proportion to its size.
        for (t, c), k in self._apportion_cells(scan, self.cells).items():
            pool = [s for s in self.cells[(t, c)] if s.hard is None]
            for s in self._pick(pool, k, f"scan-only in {t}/{c}", "H1", t, c):
                s.hard = H1
        # H2 over the cells with at least one compatible precedence row.
        # H2 over every non-hand-over cell of a country with precedence rows; precedence_rows moves a label from a
        # slot no row fits (its type, supplier or lines) to one a row fits.
        conflict_cells = {k: v for k, v in self.cells.items() if not self.gen.type(k[0]).handover
                          and any(k[1] in r.countries for r in hc.rows)}
        for (t, c), k in self._apportion_cells(conflict, conflict_cells).items():
            pool = [s for s in self.cells[(t, c)] if s.hard is None]
            for s in self._pick(pool, k, f"conflicting documents in {t}/{c}", "H2", t, c):
                s.hard = H2
        self._check_band()

    def _band_allows(self, give: str, take: str) -> bool:
        """Moving a hard label from a slot of type ``give`` to one of type ``take`` keeps both inside the band."""
        if give == take:
            return True
        lo, hi = (as_fraction(x) for x in self.gen.hard_cases.type_hard_share_band)

        def share(t: str, delta: int) -> Fraction:
            n_t = sum(len(v) for k, v in self.cells.items() if k[0] == t)
            return Fraction((sum(1 for s in self.slots if s.primary == t and s.hard) + delta) * 100, n_t)

        return share(give, -1) >= lo and share(take, 1) <= hi

    def _check_band(self) -> None:
        """Each type that takes conflicting documents keeps its hard share inside the band."""
        hc = self.gen.hard_cases
        lo, hi = (as_fraction(x) for x in hc.type_hard_share_band)
        for t in {k[0] for k in self.cells if not self.gen.type(k[0]).handover
                  and any(k[1] in r.countries for r in hc.rows)}:
            n_t = sum(len(v) for k, v in self.cells.items() if k[0] == t)
            h_t = sum(1 for s in self.slots if s.primary == t and s.hard)
            if n_t and not lo <= Fraction(h_t * 100, n_t) <= hi:
                raise InfeasibleDemand(f"hard share of {t} is {h_t}/{n_t}, outside {lo}-{hi}%")

    def _apportion_cells(self, total: int, cells: dict) -> dict:
        weights = {f"{t}|{c}": len(v) for (t, c), v in cells.items()}
        return {tuple(k.split("|")): n for k, n in apportion(total, weights).items() if n}

    # 3a. foreign suppliers, per country
    def foreign(self) -> None:
        for c in self.gen.countries:
            pool = [s for s in self.slots if s.country == c]
            share = as_fraction(self.gen.foreign_share)
            k = apportion(len(pool), {"foreign": share, "domestic": 100 - share})["foreign"]
            def can(slot: Slot) -> bool:
                return all(self.gen.type(t).foreign and (self.gen.type(t).foreign_countries is None
                                                         or slot.country in self.gen.type(t).foreign_countries)
                           for t in slot.types())

            cells = {key: [s for s in v if can(s)] for key, v in self.cells.items() if key[1] == c}
            cells = {key: v for key, v in cells.items() if v}
            for (t, cc), m in self._apportion_cells(k, cells).items():
                for s in self._pick(cells[(t, cc)], m, f"foreign suppliers in {t}/{cc}", "foreign", t, cc):
                    s.foreign = True

    # 3b. lines per case
    def lines(self) -> None:
        buckets = apportion(self.n, self.gen.lines)
        counts: list[int] = []
        for bucket, k in buckets.items():
            lo, _, hi = bucket.partition("-")
            sizes = [str(x) for x in range(int(lo), int(hi or lo) + 1)]
            for size, m in apportion(k, {s: 1 for s in sizes}).items():
                counts += [int(size)] * m
        order = self._shuffled(self.slots, "lines")
        for s, k in zip(order, counts, strict=True):
            s.lines = k
        # Three in four one-line tax slots swap counts with an untaxed slot of more lines (same country), so the problem
        # forms (at most two lines a slot) have room; the split's line counts stay the plan's.
        single = [s for i, s in enumerate(x for x in order if self._tax(x) and x.lines == 1) if i % 4]
        longer = [s for s in self._shuffled(self.slots, "lines swap") if not self._tax(s) and s.lines >= 2]
        for s in single:
            other = next((o for o in longer if o.country == s.country), None)
            if other is None:
                continue
            longer.remove(other)
            s.lines, other.lines = other.lines, s.lines

    # 4a. mixed cases
    def mixed(self) -> None:
        mx = self.gen.mixed
        total = share_of(self.n, mx.share)
        split_exact = total * as_fraction(mx.split_share)
        if split_exact.denominator != 1:
            raise InfeasibleDemand(f"split cases: {split_exact} of {total} mixed cases isn't whole")
        split = int(split_exact)
        ok = [s for s in self.slots if not self.gen.type(s.primary).handover]
        for c, k in apportion(split, {c: 1 for c in mx.split_countries}).items():
            # A split case keeps a line of its own for the split (besides a tax slot's line for its problem).
            pool = [s for s in ok if s.country == c and s.lines >= 1 + self._tax(s) and not s.foreign]
            untaxed = [s for s in pool if not self._tax(s)]
            pool = untaxed if len(untaxed) >= k else pool       # a tax slot's lines are the problem forms' room
            for s in self._pick(pool, k, f"split cases in {c}", "mixed-split", c):
                s.mixed = "split"
                if mx.split_window is not None:
                    assert s.window is not None
                    s.window = (max(s.window[0], mx.split_window[0]), min(s.window[1], mx.split_window[1]))
        for c, k in apportion(total - split, {c: 1 for c in self.gen.countries}).items():
            pool = [s for s in ok if s.country == c and s.lines >= 2 and s.mixed is None and not s.foreign]
            for s in self._pick(pool, k, f"mixed lines in {c}", "mixed-lines", c):
                s.mixed = "lines"

    # 4b. rule floor
    def rule_floor(self) -> None:
        tier = self.gen.floor_for(self.n)
        if tier.per_rule == 0:
            return
        problem = {r.id: 0 for r in self.gen.rules}
        correct = {r.id: 0 for r in self.gen.rules}
        if tier.problem_per_rule:
            for r in self.gen.rules:
                if r.problem_form:
                    problem[r.id] = min(tier.problem_per_rule, tier.per_rule)
        if tier.problem_per_family:
            families: dict[tuple[str, str], list[str]] = {}
            for r in self.gen.rules:
                if r.problem_form and r.correct_form:  # a rule with only a problem form takes all its floor below
                    families.setdefault((r.country, r.family), []).append(r.id)
            branched = {r.id: r.branches.get(PROBLEM, 0) * tier.per_branch for r in self.gen.rules}
            for (c, fam), ids in families.items():
                # The family's problem lines: those its rules' branches already need count towards it.
                need = max(0, tier.problem_per_family - sum(branched[x] for x in ids))
                start = self._rng("family", c, fam).randrange(len(ids))
                for i in range(need):
                    problem[ids[(start + i) % len(ids)]] += 1
        for r in self.gen.rules:
            if r.correct_form:
                correct[r.id] = tier.per_rule - problem[r.id]
            else:
                problem[r.id] = tier.per_rule          # every appearance is a problem form
            # A rule whose recipe takes several branches in turn: each at least per_branch times.
            problem[r.id] = max(problem[r.id], r.branches.get(PROBLEM, 0) * tier.per_branch)
            correct[r.id] = max(correct[r.id], r.branches.get(CORRECT, 0) * tier.per_branch)
        rank = {s.key: i for i, s in enumerate(self._shuffled(self.slots, "rules"))}
        # A tax slot keeps one line for its tax problem: the first problem form placed there, or else the problem its
        # tax family plants. Correct forms get the other lines.
        reserved = {s.key: self._tax(s) for s in self.slots}
        free_lines = {s.key: s.lines - reserved[s.key] - (s.mixed == "split") for s in self.slots}
        problems = {s.key: 0 for s in self.slots}

        def free_problem_of(key: int) -> int:
            """Problem lines the slot can still take: the reserved line first, then free lines (at most two)."""
            if not reserved[key] or problems[key] >= MAX_PROBLEM_LINES:
                return 0
            later = min(free_lines[key], MAX_PROBLEM_LINES - max(problems[key], 1))
            return later + (problems[key] == 0)

        free_problem = _Lazy(free_problem_of)
        free_finding = {s.key: 1 for s in self.slots}
        free_action = {s.key: s.lines for s in self.slots}
        demands = [(r, PROBLEM, problem[r.id]) for r in self.gen.rules if problem[r.id]]
        demands += [(r, CORRECT, correct[r.id]) for r in self.gen.rules if correct[r.id]]
        # Most constrained first: fewest candidate slots, problem forms before correct ones, the rules with the most
        # appearances (each needs a slot of its own), then those that can share a slot with the fewest other demands
        # (a rule that pairs with none should take a slot no pair needs).
        share = {(r.id, f): sum(self._can_share(r, f, r2, f2) for r2, f2, _ in demands if r2.id != r.id)
                 for r, f, _ in demands}
        def room(rule: RuleSpec, form: str) -> int:
            """Candidate slots, the narrowest appearance turn's side counted alone (it must find its slot first)."""
            cands = self._candidates(rule, form)
            sides = [t.foreign for t in rule.appearance_turns.get(form, ()) if t.foreign is not None]
            return min([len(cands)] + [sum(s.foreign == side for s in cands) for side in sides])

        demands.sort(key=lambda d: (room(d[0], d[1]), d[1] != PROBLEM, -d[2], share[(d[0].id, d[1])], d[0].id))
        for base, form, k in demands:
            candidates = self._candidates(base, form)
            for i in range(k):
                rule = base
                if base.window_turns.get(form):          # this appearance's date window, in turn
                    turns = base.window_turns[form]
                    rule = base.model_copy(update={"windows": {**base.windows, form: turns[i % len(turns)]}})
                pool = [s for s in candidates
                        if all(u.rule != rule.id for u in s.rules) and self._fits(s, rule, form)
                        and self._free(s, rule, form, free_lines, free_problem, free_finding, free_action) > 0]
                if rule.alternate_foreign:          # in turn foreign and domestic, where both can still take it
                    pool = [s for s in pool if s.foreign == bool(i % 2)] or pool
                # Appearance turns plant branches, so they apply where the split has a branch floor.
                turns_on = tier.per_branch > 0 and base.appearance_turns.get(form)
                turn = base.appearance_turns[form][i % len(base.appearance_turns[form])] if turns_on else None
                if turn is not None or base.appearance_turns.get(form):
                    pool = [s for s in pool if self._turn_fits(s, rule, form, turn)]
                if not pool:
                    raise InfeasibleDemand(f"rule floor: {rule.id} ({form}) placed {i} of {k}; no compatible slot "
                                           f"has room in a split of {self.n}")
                if turn is not None and turn.companies and set(turn.companies) <= set(self.gen.reserved_companies):
                    # A reserved company's case takes no other rule: the slot with the fewest lines, so the least
                    # room is closed to the others.
                    s = min(pool, key=lambda s: (s.lines, free_problem[s.key] if form == PROBLEM else 0, rank[s.key]))
                elif form == PROBLEM:
                    # Best fit: the slot with the least problem room that still fits (a second problem where one
                    # can pair, a one-line slot for a rule that pairs with nothing), so no room is wasted.
                    s = min(pool, key=lambda s: (free_problem[s.key], s.lines, rank[s.key]))
                else:
                    s = max(pool, key=lambda s: (self._free(s, rule, form, free_lines, free_problem, free_finding,
                                                            free_action), -rank[s.key]))
                s.rules.append(RuleUse(rule.id, form, rule.carrier))
                s.window = self._narrowed(s, rule, form)
                s.supplier = s.supplier or rule.supplier
                kinds = (turn.companies if turn is not None and turn.companies else ()) or rule.companies
                if kinds:
                    s.companies = tuple(sorted(set(kinds) & set(s.companies or kinds)))
                if rule.carrier == "line":
                    if form == PROBLEM and problems[s.key] == 0:
                        problems[s.key] += 1             # takes the reserved line
                    else:
                        problems[s.key] += form == PROBLEM
                        free_lines[s.key] -= 1
                elif rule.carrier == "finding":
                    free_finding[s.key] -= 1
                else:
                    free_action[s.key] -= 1
                if rule.carrier != "line" and (rule.takes_line or rule.foreign):   # a foreign action sets its line
                    free_lines[s.key] -= 1

    def _narrowed(self, s: Slot, rule: RuleSpec, form: str) -> tuple[date, date]:
        lo, hi = rule.window(form, self.gen.windows[s.country])
        assert s.window is not None
        return max(lo, s.window[0]), min(hi, s.window[1])

    def _can_share(self, a: RuleSpec, fa: str, b: RuleSpec, fb: str) -> bool:
        """Two rule appearances could sit in one slot (same country, one supplier kind, needs met, common dates)."""
        if a.country != b.country or (a.supplier and b.supplier and a.supplier != b.supplier):
            return False
        if (a.foreign and b.domestic) or (a.domestic and b.foreign):
            return False
        kind = a.supplier or b.supplier
        if kind and (set(a.needs) | set(b.needs)) & set(self.gen.supplier_lacks.get(kind, ())):
            return False
        if self.gen.needs_clash(set(a.needs) | set(b.needs)):
            return False
        if a.companies and b.companies and not set(a.companies) & set(b.companies):
            return False
        wa, wb = a.window(fa, self.gen.windows[a.country]), b.window(fb, self.gen.windows[b.country])
        return max(wa[0], wb[0]) <= min(wa[1], wb[1])

    def _fits(self, s: Slot, rule: RuleSpec, form: str) -> bool:
        """The rule can join the slot's rules: one supplier kind, a company kind both allow, a common date."""
        if rule.supplier and s.supplier and rule.supplier != s.supplier:
            return False
        if rule.whole_case and s.mixed:
            return False
        if s.lines < rule.min_lines.get(form, 1):
            return False
        if s.rules and (form in rule.alone or any(u.form in self._rule(u.rule).alone for u in s.rules)):
            if not all(u.rule in rule.alone_with and rule.id in self._rule(u.rule).alone_with for u in s.rules):
                return False              # a rule that plants alone shares its case only with its alone_with rules
        if form in rule.alone and form != PROBLEM and (self._tax(s) or s.mixed):
            return False                  # nor with a tax problem its slot's family would plant, nor a mixing line
        kind = s.supplier or rule.supplier
        needs = set(rule.needs).union(*(self._rule(u.rule).needs for u in s.rules))
        if kind and needs & set(self.gen.supplier_lacks.get(kind, ())):
            return False
        if self.gen.needs_clash(needs):
            return False
        if rule.companies and s.companies is not None and not set(rule.companies) & set(s.companies):
            return False
        if s.companies is not None and set(s.companies) <= set(self.gen.reserved_companies) and not (
                set(rule.companies) | {k for t in rule.appearance_turns.get(form, ()) for k in t.companies}) & set(
                s.companies):
            return False                  # a reserved company's case takes only the rules that name its kind
        lo, hi = self._narrowed(s, rule, form)
        return lo <= hi

    def _turn_fits(self, s: Slot, rule: RuleSpec, form: str, turn) -> bool:
        """An appearance turn's own needs: the supplier side it names (else the rule's), and its company kinds."""
        foreign = turn.foreign if turn is not None and turn.foreign is not None else (
            True if rule.foreign else False if (rule.domestic or form in rule.domestic_forms) else None)
        if foreign is not None and s.foreign != foreign:
            return False
        kinds = set(turn.companies if turn is not None else ()) or set(rule.companies)
        if kinds and s.companies is not None and not kinds & set(s.companies):
            return False
        if s.companies is not None and set(s.companies) <= set(self.gen.reserved_companies) and not kinds & set(
                s.companies):
            return False
        return True

    def _tax(self, s: Slot) -> bool:
        return any(self.gen.type(t).tax for t in s.types())

    def _rule(self, rule_id: str) -> RuleSpec:
        return next(r for r in self.gen.rules if r.id == rule_id)

    def _candidates(self, rule: RuleSpec, form: str) -> list[Slot]:
        out = []
        for s in self.slots:
            if s.country != rule.country or self.gen.type(s.primary).handover:
                continue
            turned = any(t.foreign is not None for t in rule.appearance_turns.get(form, ()))
            if not turned and ((rule.foreign and not s.foreign)
                               or ((rule.domestic or form in rule.domestic_forms) and s.foreign)):
                continue
            if set(rule.exclude_types) & set(s.types()):
                continue
            if form == PROBLEM:
                if not any(self.gen.type(t).tax for t in s.types()):
                    continue
            elif rule.whole_case and self._tax(s):
                continue                 # it decides every line, so no tax problem could join it
            elif rule.types and not set(rule.types) & set(s.types()):
                continue
            out.append(s)
        return out

    @staticmethod
    def _free(s, rule, form, free_lines, free_problem, free_finding, free_action) -> int:
        if rule.carrier == "line":
            return free_problem[s.key] if form == PROBLEM else free_lines[s.key]
        free = free_finding[s.key] if rule.carrier == "finding" else free_action[s.key]
        return min(free, free_lines[s.key]) if rule.takes_line or rule.foreign else free

    # 4c. date boundaries
    def boundaries(self) -> None:
        tier = self.gen.boundary_floor_for(self.n)
        if tier.per_side == 0:
            return
        taken: set[int] = set()
        # The boundaries whose branch needs a type of slot first, so the others don't take the few that fit.
        for b in sorted(self.gen.boundaries, key=lambda b: not b.types):
            lo, hi = self.gen.windows[b.country]
            sides = {
                "before": (max(lo, b.day - timedelta(days=tier.days)), b.day - timedelta(days=1)),
                "after": (b.day, min(hi, b.day + timedelta(days=tier.days - 1))),
            }
            for side, window in sides.items():
                if window[0] > window[1]:
                    raise InfeasibleDemand(f"boundary {b.country} {b.day}: no {side} days inside the window")
                pool = [s for s in self.slots if s.country == b.country and s.key not in taken
                        and not any(u.form in self._rule(u.rule).alone for u in s.rules)
                        and not (s.mixed == "lines" and s.lines - sum(
                            u.carrier == "line" or self._rule(u.rule).takes_line for u in s.rules) < 1 + b.line)
                        and max(window[0], s.window[0]) <= min(window[1], s.window[1])
                        and (side == "before" or s.window[0] <= b.day)      # the after side starts on the day
                        and (not b.branch or self._takes_branch(s, b, side))]
                for s in self._pick(pool, tier.per_side, f"boundary {b.country} {b.day} {side}", "boundary",
                                    b.country, b.day.isoformat(), side):
                    s.window = (max(window[0], s.window[0]), min(window[1], s.window[1]))
                    s.boundary = (b.day, side)
                    s.branch = b.branch
                    if b.branch:
                        s.supplier = s.supplier or b.supplier
                        if b.companies:
                            s.companies = tuple(sorted(set(b.companies) & set(s.companies or b.companies)))
                    taken.add(s.key)

    def _takes_branch(self, s: Slot, b, side: str) -> bool:
        """The slot can carry the boundary's branch line: a free line, its type, one supplier kind, the needs met,
        a company kind both allow."""
        if self.gen.type(s.primary).handover:
            return False
        if side in b.types and not set(b.types[side]) & set(s.types()):
            return False
        if set(b.exclude_types.get(side, ())) & set(s.types()):
            return False
        if side in b.findings and any(u.carrier == "finding" and u.rule != b.finding_rule for u in s.rules):
            return False                  # one finding per code: the branch's would hide the slot's
        used = self._tax(s) + (s.mixed == "split") + sum(
            1 for u in s.rules if u.carrier == "line" or self._rule(u.rule).takes_line)
        if b.line and s.lines - used < 1:
            return False
        if b.supplier and s.supplier and b.supplier != s.supplier:
            return False
        kind = s.supplier or b.supplier
        needs = set(b.needs).union(*(self._rule(u.rule).needs for u in s.rules))
        if kind and needs & set(self.gen.supplier_lacks.get(kind, ())):
            return False
        if self.gen.needs_clash(needs):
            return False
        if b.companies and s.companies is not None and not set(b.companies) & set(s.companies):
            return False
        if s.companies is not None and set(s.companies) <= set(self.gen.reserved_companies) and not set(
                b.companies) & set(s.companies):
            return False                  # a reserved company's case takes only what names its kind
        if b.supplier and any(self._rule(u.rule).domestic for u in s.rules) and s.foreign:
            return False
        return not s.foreign

    # 4d. precedence rows for the conflicting-documents cases
    def precedence_rows(self) -> None:
        """Each H2 slot takes a precedence row it can carry (country, type, supplier side and kind, company kinds,
        dates, a free line): fewest options first, then the least used row, within the cap per row."""
        hc = self.gen.hard_cases
        h2 = [s for s in self.slots if s.hard == H2]
        row_cap = floor(len(h2) * as_fraction(hc.conflict_row_cap))
        used: Counter = Counter()
        # Rows that ride on a rule's line: a slot carrying the rule takes the row, its H2 label moved from a domestic
        # H2 slot of the same type and country (which keeps its counts exact).
        for row in hc.rows:
            if not row.rides_on or row.line:
                continue
            for s in self._shuffled([s for s in self.slots if s.hard is None
                                     and any(u.rule in row.rides_on for u in s.rules)], "rides", row.id):
                if used[row.id] >= row_cap or not self._row_fits(s, row):
                    continue
                donor = next((x for x in sorted(h2, key=lambda x: x.key) if x.row is None and x.country == s.country
                              and x.primary == s.primary and not x.foreign), None)
                if donor is None:
                    continue
                donor.hard, s.hard = None, H2
                h2 = [x for x in h2 if x is not donor] + [s]
                self._take_row(s, row)
                used[row.id] += 1
        # The others: fewest fitting rows first, then the least used row. A slot no row fits under the cap (its lines
        # all taken) passes its H2 label to an unlabelled slot that one fits: of the same type where one is free (in
        # the same country first), else of another type (the hard total is exact and the plan sets no per-country
        # count; each type's hard share stays in the band, checked below).
        def rows_for(s: Slot) -> list:
            return [r for r in hc.rows if (r.line or not r.rides_on) and used[r.id] < row_cap and self._row_fits(s, r)]

        rest = sorted((s for s in h2 if s.row is None), key=lambda s: (len(rows_for(s)), s.key))
        for s in rest:
            fits = rows_for(s)
            if not fits:
                pool = self._shuffled([x for x in self.slots if x.hard is None and x.row is None
                                       and not self.gen.type(x.primary).handover], "h2-swap", s.key)
                # The same type first (the same country before another), then other types (keeping the band).
                pool.sort(key=lambda x: (x.primary != s.primary, x.country != s.country))
                swap = next((x for x in pool if rows_for(x) and self._band_allows(s.primary, x.primary)), None)
                if swap is None:
                    raise InfeasibleDemand(f"conflicting documents: no precedence row under the cap {row_cap} fits "
                                           f"{s.primary}/{s.country}")
                s.hard, swap.hard, s = None, H2, swap
                fits = rows_for(s)
            row = min(fits, key=lambda r: (used[r.id], [x.id for x in hc.rows].index(r.id)))
            self._take_row(s, row)
            used[row.id] += 1
        self._check_band()

    def _take_row(self, s: Slot, row) -> None:
        """The slot carries the row: its supplier kind, company kinds and dates narrowed to the row's."""
        s.row = row.id
        kind = row.supplier.get(s.country, "")
        s.supplier = s.supplier or kind
        kinds = row.companies.get(s.country)
        if kinds:
            s.companies = tuple(sorted(set(kinds) & set(s.companies or kinds)))
        lo, hi = row.windows.get(s.country, self.gen.windows[s.country])
        assert s.window is not None
        s.window = (max(lo, s.window[0]), min(hi, s.window[1]))

    def _row_fits(self, s: Slot, row) -> bool:
        if s.country not in row.countries or not set(s.types()) <= set(row.types):
            return False
        if row.line and any(self._rule(u.rule).whole_case for u in s.rules):
            return False                  # a rule deciding every line would decide the row's line too
        if row.foreign is not None and s.foreign != row.foreign:
            return False
        if row.unmixed and s.mixed is not None:
            return False
        if any(u.form in self._rule(u.rule).alone for u in s.rules):
            return False                  # a rule that plants alone (its branch's own supplier) shares with no row
        kind = row.supplier.get(s.country, "")
        if kind and s.supplier and s.supplier != kind:
            return False
        needs = set(row.needs).union(*(self._rule(u.rule).needs for u in s.rules))
        boundary = next((b for b in self.gen.boundaries if s.boundary and b.country == s.country
                         and b.day == s.boundary[0] and b.branch == s.branch), None)
        if boundary is not None:
            needs |= set(boundary.needs)
        if (kind or s.supplier) and needs & set(self.gen.supplier_lacks.get(kind or s.supplier, ())):
            return False
        if self.gen.needs_clash(needs):
            return False
        kinds = set(row.companies.get(s.country, ()))
        if s.companies is not None and set(s.companies) <= set(self.gen.reserved_companies):
            return False                  # a reserved company's case takes only what names its kind
        if kinds and s.companies is not None and not kinds & set(s.companies):
            return False
        lo, hi = row.windows.get(s.country, self.gen.windows[s.country])
        assert s.window is not None
        if max(lo, s.window[0]) > min(hi, s.window[1]):
            return False
        ride = any(u.rule in row.rides_on and (u.form == CORRECT or not row.line) for u in s.rules)
        if row.line:
            used = self._tax(s) + (s.mixed is not None) + (s.boundary is not None) + sum(
                1 for u in s.rules if u.carrier == "line" or self._rule(u.rule).takes_line or self._rule(u.rule).foreign)
            return s.lines - used >= 1 or ride
        return ride or not row.rides_on

    # 5. final order
    def order(self) -> None:
        for i, s in enumerate(self._shuffled(self.slots, "order")):
            s.case_index = self.split.id_start + i
