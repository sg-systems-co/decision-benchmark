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
    foreign: bool = False
    """It needs a foreign supplier."""
    note: str = ""

    @field_validator("carrier")
    @classmethod
    def _carrier(cls, v: str) -> str:
        if v not in ("line", "finding", "action"):
            raise ValueError(f"carrier {v!r}")
        return v


class FloorTier(Model):
    """The rule floor for splits of at least ``min_cases`` cases (the largest tier that fits applies)."""

    min_cases: int
    per_rule: int
    problem_per_rule: int = 0
    """Problem forms per rule that has one."""
    problem_per_family: int = 0
    """Problem forms per family (when a per-rule problem floor can't hold)."""


class BoundaryTier(Model):
    min_cases: int
    per_side: int
    """Cases on each side of every boundary, within ``days`` of it."""
    days: int = 31


class CompanyTier(Model):
    """Companies built for splits of at least ``min_cases`` cases (the largest tier that fits applies)."""

    min_cases: int
    companies: int


class Boundary(Model):
    country: str
    day: date
    """The first day of the new state (the after side starts here)."""
    note: str = ""


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
