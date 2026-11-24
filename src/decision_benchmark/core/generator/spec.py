"""What a task set tells the generator: the generic generation config carried by its TaskSetSpec (B1 plan §3).

Core never names a task set or a country. Countries, exception types, rule ids and precedence rows are opaque
strings here; the task set supplies them (usually from YAML in its content folder).
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction

from pydantic import field_validator, model_validator

from ..model import Model
from .quotas import as_fraction


class ExceptionType(Model):
    """One primary exception type of the mix (its share of cases lives in TaskSetSpec.quotas)."""

    name: str
    tier: int | None = None
    """Priority tier of the problem (1 highest). None: not a problem (clean) or a hand-over type."""
    handover: bool = False
    """The type's cases are HAND_OVER (they never take a second problem, step 11 Q14)."""
    tax: bool = False
    """The type's problem is a tax problem (rule-floor problem forms go to these primaries and secondaries)."""
    foreign: bool = True
    """The type's cases can come from a foreign supplier (False: never chosen for the foreign-supplier share)."""
    foreign_countries: tuple[str, ...] | None = None
    """Where foreign is True: only in these countries (None: every country)."""


class TwoProblems(Model):
    share: str
    """Percent of all cases that carry a secondary problem."""
    pairs: tuple[tuple[str, str], ...]
    """Allowed (primary, secondary) pairs. The secondary's tier is always lower than the primary's."""


class PrecedenceRow(Model):
    """A row of the precedence table: a fact where a governing document overrides what the main document says."""

    id: str
    countries: tuple[str, ...]
    types: tuple[str, ...]
    """Exception types whose cases can carry this row."""


class HardCases(Model):
    """Hard-case quotas (B1 plan §3.2). Kinds: scan-only (no structured record), conflicting documents (precedence
    table), missing information (only on hand-over types)."""

    share: str
    """Percent of every split that is hard."""
    scan_only_share_of_hard: str
    scan_only_cap_of_hard: str
    """The scan-only count may not exceed this fraction of the hard count (rounded down)."""
    missing_share_of_handover: str
    """Fraction of the hand-over type's cases that are missing-information cases."""
    conflict_row_cap: str
    """No precedence row takes more than this fraction of a split's conflicting-documents cases."""
    type_hard_share_band: tuple[str, str]
    """Percent band each exception type's hard share stays in, for the types that take conflicting documents."""
    rows: tuple[PrecedenceRow, ...]


class Mixed(Model):
    """Mixed cases: lines with different outcomes, or one line that turns on a split (B1 plan §3.3)."""

    share: str
    """Percent of every split."""
    split_share: str
    """Fraction of the mixed cases that are split cases."""
    split_countries: tuple[str, ...]
    split_window: tuple[date, date] | None = None
    """The dates a split case can take (where the task set's splits decide)."""
    split_needs: tuple[str, ...] = ()
    """What a split case's supplier must be able to do (as a rule's needs)."""


class RuleSpec(Model):
    """One rule the floor counts (B1 plan §3.4)."""

    id: str
    country: str
    family: str
    carrier: str
    """How the rule appears in an answer key: 'line' (a line basis), 'finding' or 'action'."""
    problem_form: bool = False
    """The rule can decide a problem line (wrongly charged or undercharged)."""
    types: tuple[str, ...] = ()
    """Exception types whose cases can carry it. Empty: any type that isn't a hand-over type."""
    exclude_types: tuple[str, ...] = ()
    """Exception types whose cases can't carry it (their own problem would decide its line)."""
    foreign: bool = False
    """It needs a foreign supplier."""
    domestic: bool = False
    """It needs a domestic supplier (never on a foreign-supplier slot)."""
    domestic_forms: tuple[str, ...] = ()
    """Forms that need a domestic supplier when the rule itself doesn't."""
    correct_form: bool = True
    """The rule can decide a correct line. False: every appearance is a problem form (e.g. undercharged)."""
    supplier: str = ""
    """The kind of supplier it needs, as the task set names it ('' any). A case has one supplier, so two rules that
    need different kinds never share a slot."""
    companies: tuple[str, ...] = ()
    """Company kinds that can carry it, as the task set names them (empty: any)."""
    whole_case: bool = False
    """The rule decides every line of the case (a mixed slot can't carry it)."""
    takes_line: bool = False
    """A finding or action rule that needs a line of its own (it can't ride on another rule's line)."""
    needs: tuple[str, ...] = ()
    """What the case's supplier must be able to do, as the task set names it (e.g. charge a tax)."""
    form_needs: dict[str, tuple[str, ...]] = {}
    """Per form: what the supplier must do on top of needs (the pool the case's supplier comes from)."""
    min_lines: dict[str, int] = {}
    """Per form: the fewest lines a case carrying it needs (a whole-case rule's branch on another line)."""
    alternate_foreign: bool = False
    """Its appearances alternate between foreign- and domestic-supplier cases (its branches differ between them)."""
    alone: tuple[str, ...] = ()
    """Forms whose case plants no other rule (a branch that needs a supplier no other rule's line could take)."""
    alone_with: tuple[str, ...] = ()
    """Rules it may share such a case with (their branches take the same supplier)."""
    window_turns: dict[str, tuple[tuple[date, date], ...]] = {}
    """Per form: date windows its floor appearances take in turn (a rule whose branches sit near different dates),
    each inside the form's window."""
    windows: dict[str, tuple[date, date]] = {}
    """Per form ('problem', 'correct'): the case dates the rule can be planted on (absent: the country window)."""
    branches: dict[str, int] = {}
    """Per form: the deciding branches the rule's recipe takes in turn (review of B1-5: each branch planted at least
    ``per_branch`` times), so the floor gives the form at least branches x per_branch appearances."""
    note: str = ""

    @field_validator("carrier")
    @classmethod
    def _carrier(cls, v: str) -> str:
        if v not in ("line", "finding", "action"):
            raise ValueError(f"carrier {v!r}")
        return v

    @model_validator(mode="after")
    def _forms(self) -> RuleSpec:
        if not (self.problem_form or self.correct_form):
            raise ValueError(f"rule {self.id} has neither a problem nor a correct form")
        if self.foreign and self.domestic:
            raise ValueError(f"rule {self.id} needs both a foreign and a domestic supplier")
        for form, (lo, hi) in self.windows.items():
            if form not in ("problem", "correct") or lo > hi:
                raise ValueError(f"rule {self.id}: bad window {form} {lo}..{hi}")
        for form, turns in self.window_turns.items():
            lo, hi = self.windows.get(form, (date.min, date.max))
            if form not in ("problem", "correct") or any(a > b or a < lo or b > hi for a, b in turns):
                raise ValueError(f"rule {self.id}: bad window_turns {form}")
        for form, k in self.branches.items():
            if form not in ("problem", "correct") or k < 1 or not (self.problem_form if form == "problem"
                                                                     else self.correct_form):
                raise ValueError(f"rule {self.id}: bad branches {form}: {k}")
        return self

    def window(self, form: str, country_window: tuple[date, date]) -> tuple[date, date]:
        lo, hi = self.windows.get(form, country_window)
        return max(lo, country_window[0]), min(hi, country_window[1])


class FloorTier(Model):
    """The rule floor for splits of at least ``min_cases`` cases (the largest tier that fits applies)."""

    min_cases: int
    per_rule: int
    problem_per_rule: int = 0
    """Problem forms per rule that has one."""
    problem_per_family: int = 0
    """Problem forms per family (when a per-rule problem floor can't hold)."""
    per_branch: int = 0
    """Appearances per deciding branch a rule declares (RuleSpec.branches)."""


class BoundaryTier(Model):
    min_cases: int
    per_side: int
    """Cases on each side of every boundary, within ``days`` of it."""
    days: int = 31


class CompanyTier(Model):
    """Companies built for splits of at least ``min_cases`` cases (the largest tier that fits applies)."""

    min_cases: int
    companies: int


class SpecialTier(Model):
    """Suppliers of each special kind (a kind some rule needs) for splits of at least ``min_cases`` cases."""

    min_cases: int
    per_kind: int


class Boundary(Model):
    country: str
    day: date
    """The first day of the new state (the after side starts here)."""
    note: str = ""
    branch: str = ""
    """The task set's recipe for a line whose answer turns on this date, planted on the boundary's slots ('' none)."""
    supplier: str = ""
    companies: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    """As a rule's (RuleSpec): the supplier kind, company kinds and supplier needs the branch line takes."""
    types: dict[str, tuple[str, ...]] = {}
    """Per side ('before', 'after'): a slot carrying the branch has one of these exception types (absent: any)."""
    exclude_types: dict[str, tuple[str, ...]] = {}
    """Per side: a slot carrying the branch has none of these exception types."""
    findings: tuple[str, ...] = ()
    """Sides whose branch line brings a finding-carrier rule (the slot then carries no other finding rule)."""


class Generation(Model):
    """The generic generation config of a task set."""

    root: str
    """Absolute path of the task set's package; the paths below are relative to it."""
    release_seeds: str
    """The public seeds file (YAML: splits -> {n_cases, seed})."""
    pipeline_paths: tuple[str, ...]
    """What shapes the data, for the pipeline hash (step 11 plan §8.1)."""
    lock_file: str | None = None
    """Absolute path of the dependency lock file, hashed with the pipeline when present."""
    builder: str | None = None
    """"module:function" that builds a split's cases: called as builder(generation, quotas, split, provenance=...,
    check=False); the result has planting_report() and check_thresholds()."""
    countries: tuple[str, ...]
    windows: dict[str, tuple[date, date]]
    """Case dates per country (first and last day)."""
    types: tuple[ExceptionType, ...]
    two_problems: TwoProblems
    hard_cases: HardCases
    mixed: Mixed
    foreign_share: str
    """Percent of each country's cases with a foreign supplier."""
    lines: dict[str, str]
    """Lines per case: "1", "2", "3" or a range "4-6" -> percent of cases. A range is spread evenly."""
    rule_floor: tuple[FloorTier, ...]
    rules: tuple[RuleSpec, ...]
    not_counted: dict[str, str] = {}
    """Rule ids the floor doesn't count, with the reason (dispatchers, rules that aren't engine rules)."""
    boundary_floor: tuple[BoundaryTier, ...]
    boundaries: tuple[Boundary, ...]
    companies: tuple[CompanyTier, ...] = ()
    """Buying companies per split, split evenly over the countries."""
    special_suppliers: tuple[SpecialTier, ...] = ()
    """How many suppliers of each special kind a split has (the largest tier that fits; default one)."""
    supplier_lacks: dict[str, tuple[str, ...]] = {}
    needs_conflict: tuple[tuple[str, str], ...] = ()
    """Pairs of rule needs no one supplier meets together (e.g. registered and not registered)."""

    def needs_clash(self, needs: set[str]) -> bool:
        return any(a in needs and b in needs for a, b in self.needs_conflict)
    """Supplier kind -> the rule needs it can't meet (a rule that needs one never joins a slot of that kind)."""

    @model_validator(mode="after")
    def _consistent(self) -> Generation:
        names = [t.name for t in self.types]
        if len(set(names)) != len(names):
            raise ValueError("duplicate exception type")
        for p, s in self.two_problems.pairs:
            tp, ts = self.type(p), self.type(s)
            if tp.tier is None or ts.tier is None or ts.tier <= tp.tier:
                raise ValueError(f"pair ({p}, {s}): the secondary must be a problem of a lower tier")
        for row in self.hard_cases.rows:
            if not set(row.countries) <= set(self.countries) or not set(row.types) <= set(names):
                raise ValueError(f"precedence row {row.id} names an unknown country or type")
        ids = [r.id for r in self.rules]
        if len(set(ids)) != len(ids) or set(ids) & set(self.not_counted):
            raise ValueError("a rule is listed twice")
        for r in self.rules:
            if r.country not in self.countries or not set(r.types) <= set(names):
                raise ValueError(f"rule {r.id} names an unknown country or type")
        for b in self.boundaries:
            lo, hi = self.windows[b.country]
            if not lo < b.day <= hi:
                raise ValueError(f"boundary {b.day} lies outside the {b.country} window")
        if sum((as_fraction(v) for v in self.lines.values()), Fraction(0)) != 100:
            raise ValueError("line shares must sum to 100")
        return self

    def type(self, name: str) -> ExceptionType:
        return next(t for t in self.types if t.name == name)

    def floor_for(self, n_cases: int) -> FloorTier:
        fits = [t for t in self.rule_floor if t.min_cases <= n_cases]
        return max(fits, key=lambda t: t.min_cases) if fits else FloorTier(min_cases=0, per_rule=0)

    def companies_for(self, n_cases: int) -> int:
        fits = [t for t in self.companies if t.min_cases <= n_cases]
        return max(fits, key=lambda t: t.min_cases).companies if fits else len(self.countries)

    def special_per_kind(self, n_cases: int) -> int:
        fits = [t for t in self.special_suppliers if t.min_cases <= n_cases]
        return max(fits, key=lambda t: t.min_cases).per_kind if fits else 1

    def boundary_floor_for(self, n_cases: int) -> BoundaryTier:
        fits = [t for t in self.boundary_floor if t.min_cases <= n_cases]
        return max(fits, key=lambda t: t.min_cases) if fits else BoundaryTier(min_cases=0, per_side=0)


class SplitSpec(Model):
    """One split to build: the public splits come from the task set's release seeds; other users pass their own."""

    name: str
    n_cases: int
    seed: int
    id_start: int = 1
    canary: str | None = None
