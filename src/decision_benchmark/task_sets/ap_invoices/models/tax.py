"""Tax registrations, shared by companies and suppliers. Each scheme belongs to one country pack."""

from __future__ import annotations

from datetime import date

from pydantic import model_validator

from .common import Model


class TaxRegistration(Model):
    scheme: str
    """A scheme declared by a country pack; scheme names start with the country code."""
    number: str
    type: str
    """One of the types the pack allows for the scheme (e.g. sales / service, local / ovr)."""
    valid_from: date | None = None
    valid_to: date | None = None
    """Last day the registration is valid (inclusive). None: still valid."""

    @model_validator(mode="after")
    def _known(self) -> TaxRegistration:
        from ..countries import scheme_types

        allowed = scheme_types(self.scheme)
        if self.type not in allowed:
            raise ValueError(f"{self.scheme} registrations have type {' / '.join(allowed)}, not {self.type!r}")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to is before valid_from")
        return self

    def valid_on(self, day: date) -> bool:
        return (self.valid_from is None or self.valid_from <= day) and (self.valid_to is None or day <= self.valid_to)


class HasTaxRegistrations(Model):
    tax_registrations: list[TaxRegistration] = []

    def registration(
        self, scheme: str, on: date | None = None, types: tuple[str, ...] | None = None
    ) -> TaxRegistration | None:
        """The first registration in ``scheme`` (valid on ``on``, of one of ``types``), or None."""
        for reg in self.tax_registrations:
            if reg.scheme == scheme and (on is None or reg.valid_on(on)) and (types is None or reg.type in types):
                return reg
        return None
