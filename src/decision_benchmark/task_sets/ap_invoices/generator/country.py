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


class CountryGeneration(Protocol):
    country: str
    currency: str
    foreign_countries: tuple[str, ...]

    def postcode(self, r: random.Random) -> str: ...

    def registration_no(self, r: random.Random, start: date) -> str: ...

    def company_registrations(self, r: random.Random, start: date) -> list[dict]: ...

    def company_facts(self, r: random.Random) -> dict | None: ...

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date) -> list[dict]:
        """kinds: the category kinds the supplier sells ('goods', 'service')."""

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None: ...

    def clean_line(self, category: Category, day: date) -> CleanLine | None:
        """The clean form of a line of this category on this day, or None if the clean base can't use it then."""

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        """The country's e-invoice block for an invoice with these lines (each with its 'ext' fields)."""
