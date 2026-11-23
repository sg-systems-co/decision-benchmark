"""What a country pack tells the generator (its ``generation`` attribute)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from ..models import Category


@dataclass(frozen=True)
class CleanLine:
    """A line the country's rules settle as correct on the day: the rate to charge, the e-invoice line fields, and the
    treatment and basis the engine must find (planted)."""

    rate: Decimal
    ext: dict = field(default_factory=dict)
    treatment: str = ""
    basis: str = ""
    actions: tuple[tuple[str, str | None, str | None], ...] = ()
    """Buyer actions the line brings, (action, rate, basis): e.g. accounting for tax on an imported service."""


@dataclass(frozen=True)
class SpecialSupplier:
    """A supplier of a kind some rule needs (rules.yaml ``supplier``), built once per company of the country.

    categories: what its clean lines may carry (the planted lines come from the rule recipes). registered_for: the
    category kinds its tax registrations cover ('goods', 'service'); empty: no registration. facts: party facts on top
    of the country's usual ones. contract: a contract record with absolute dates ({parties: [kind]} names other
    special suppliers on the supplier side). residence: it holds a certificate of residence."""

    kind: str
    categories: tuple[str, ...]
    foreign: bool = False
    registered_for: tuple[str, ...] = ("goods", "service")
    facts: dict = field(default_factory=dict)
    contract: dict | None = None
    residence: bool = False
    registered_from: str | None = None
    """The date its tax registrations start (None: the usual, years before the window)."""
    homes: tuple[str, ...] = ()
    """A foreign supplier's countries, taken in turn by the suppliers of the kind (empty: drawn)."""


class CannotPlant(ValueError):
    """A rule recipe can't plant on this draft (the attempt is redrawn)."""


@dataclass(frozen=True)
class ProblemLine:
    """A line's tax after a family plants a problem on it: the rate charged and the treatment and basis to find."""

    rate: Decimal
    treatment: str
    basis: str


class CountryGeneration(Protocol):
    country: str
    currency: str
    foreign_countries: tuple[str, ...]
    foreign_currencies: dict[str, str]
    """The currency a supplier based in each of foreign_countries invoices in."""
    company_kinds: tuple[str, ...]
    """Company kinds the rules name (rules.yaml ``companies``), given to the country's companies in turn."""
    certificate_covers: tuple[str, ...]
    """Categories every exemption certificate covers (a rule recipe plants them)."""
    certificate_excludes: tuple[str, ...]
    """Categories no exemption certificate covers (a rule recipe needs them uncovered)."""
    plants_rules: bool
    """The pack has rule recipes (plant): the slots' rule appearances are planted."""

    def postcode(self, r: random.Random) -> str: ...

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        """ids: the split's identifier source (entities.Ids); every number comes from ids.digits()."""

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]: ...

    def company_facts(self, r: random.Random, kind: str) -> dict | None: ...

    def special_suppliers(self) -> tuple[SpecialSupplier, ...]:
        """The suppliers of the kinds some rule needs, added to every company of the country."""

    def special_facts(self, kind: str, identity: dict) -> dict:
        """Party facts a special supplier takes from its own identity (e.g. its id in the buyer's group)."""

    def link_company(self, company: dict, special: dict[str, dict]) -> None:
        """Facts of the company that name its special suppliers (special: kind -> supplier record)."""

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        """kinds: the category kinds the supplier sells ('goods', 'service')."""

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None: ...

    def clean_line(self, category: Category, day: date, company: dict | None = None, supplier: dict | None = None,
                   kind: str = "") -> CleanLine | None:
        """The clean form of a line of this category on this day for this company and supplier (kind: the supplier's
        special kind, '' for an ordinary one), or None if the clean base can't use it then."""

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        """The country's e-invoice block for an invoice with these lines (each with its 'ext' fields)."""

    def wrong_rate(self, category: Category, day: date, clean: CleanLine) -> ProblemLine | None:
        """A rate the rules reject for this clean line (finding WRONG_TAX_RATE), or None if it carries no tax."""

    def make_invalid(self, invoice: dict, rules: list[str] = ()) -> tuple[list[str], tuple[str, str] | None]:
        """Make the invoice fail the country's invoice requirements: the finding codes, and the (treatment, basis) its
        taxed lines take instead of their own (None: unchanged). rules: the slot's rule appearances (a rule the pack
        plants as the invalidity itself makes this a no-op)."""

    def plant(self, d, line: int, rule: str, form: str) -> None:
        """Plant the rule on line ``line`` of the draft (generator/ops.Draft) in its 'problem' or 'correct' form: set
        the line, state the facts, and say what the engine must find (Draft.expect). CannotPlant if the draft can't
        take it."""

    def plant_branch(self, d, line: int, branch: str, side: str) -> None:
        """Plant line ``line`` so its answer turns on a dated boundary (generation.yaml ``branch``), on its 'before'
        or 'after' side."""

    def suppliers_for(self, cw, kind: str, needs: set[str], foreign: bool, day: date) -> list[dict] | None:
        """The suppliers a case may come from on the day: kind, the special supplier kind its rules need ('' any);
        needs, what its rules need the supplier to do (rules.yaml needs). None: the clean base's usual choice."""

    def exchange_rate(self, currency: str, day: date) -> Decimal:
        """The rate an invoice in a foreign currency states, to the country's currency, on the day (it varies by
        date; the rules read it as printed)."""

    def refresh_einvoice(self, invoice: dict) -> None:
        """Recompute the e-invoice block's totals after a family changed amounts."""

