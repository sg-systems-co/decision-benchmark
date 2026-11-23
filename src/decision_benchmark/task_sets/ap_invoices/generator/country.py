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

    def postcode(self, r: random.Random) -> str: ...

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        """ids: the split's identifier source (entities.Ids); every number comes from ids.digits()."""

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]: ...

    def company_facts(self, r: random.Random) -> dict | None: ...

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        """kinds: the category kinds the supplier sells ('goods', 'service')."""

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None: ...

    def clean_line(self, category: Category, day: date) -> CleanLine | None:
        """The clean form of a line of this category on this day, or None if the clean base can't use it then."""

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        """The country's e-invoice block for an invoice with these lines (each with its 'ext' fields)."""

    def wrong_rate(self, category: Category, day: date, clean: CleanLine) -> ProblemLine | None:
        """A rate the rules reject for this clean line (finding WRONG_TAX_RATE), or None if it carries no tax."""

    def make_invalid(self, invoice: dict) -> tuple[list[str], tuple[str, str] | None]:
        """Make the invoice fail the country's invoice requirements: the finding codes, and the (treatment, basis) its
        taxed lines take instead of their own (None: unchanged)."""

    def refresh_einvoice(self, invoice: dict) -> None:
        """Recompute the e-invoice block's totals after a family changed amounts."""

