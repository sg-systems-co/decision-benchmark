"""FactReader (A12 plan §3, §7): every line rule reads line facts through it.

It records each field a rule looks up, so the answer key's gold facts are exactly the fields the
engine read, and (for check_rules) which of them the caller did not supply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models.evidence import LineFact, LineFacts

if TYPE_CHECKING:
    from .countries.base import CountryPack
    from .models import InvoiceLine


class FactReader:
    def __init__(self, pack: CountryPack, line: InvoiceLine, facts: LineFacts | None = None) -> None:
        """facts: the line facts to read; None reads the facts recorded on the invoice line."""
        self.pack = pack
        self.line = line
        self.facts = facts if facts is not None else line.facts
        self.read: list[str] = []

    def get(self, name: str) -> LineFact | None:
        """The fact, or None when it isn't recorded. Unknown names raise KeyError."""
        if name not in self.pack.line_facts_model.model_fields:
            raise KeyError(f"{name!r} is not a {self.pack.country} line fact")
        if name not in self.read:
            self.read.append(name)
        return getattr(self.facts, name) if self.facts is not None else None

    def value(self, name: str):
        """The fact's value; None when it isn't recorded or the documents don't show it."""
        fact = self.get(name)
        return fact.value if fact is not None else None

    def recorded_reads(self) -> list[str]:
        """The fields read that the facts record, in reading order (the line's gold facts)."""
        return [n for n in self.read if self.facts is not None and getattr(self.facts, n) is not None]

    def missing(self) -> list[str]:
        """The fields read that the facts don't record."""
        recorded = set(self.recorded_reads())
        return [n for n in self.read if n not in recorded]
