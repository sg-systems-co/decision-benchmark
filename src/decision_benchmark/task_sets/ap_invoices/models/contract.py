"""Contract records and certificates of residence (A12 plan §5.2).

A contract record is the written contract behind a rental or construction invoice: when it was
signed and stamped, whether prices can be reviewed, its variation orders and extensions of time.
Facts only one country's rules read sit in ``tax_facts``, that country pack's ``contract_facts``
model. A certificate of residence is the payee's proof of residence, needed for a treaty rate.
None in a fact means the documents don't show it. Nothing here names a country.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from .common import ContractTaxFacts, Model, Money


def _not_before(later: date | None, earlier: date | None, what: str) -> None:
    if later is not None and earlier is not None and later < earlier:
        raise ValueError(what)


class ContractChange(Model):
    """A variation order or an extension of time."""

    signed_on: date | None = None
    stamped_on: date | None = None
    changes_value: bool | None = None

    @model_validator(mode="after")
    def _dates(self) -> ContractChange:
        _not_before(self.stamped_on, self.signed_on, "a contract change is stamped after it is signed")
        return self


class ContractRecord(Model):
    contract_id: str = Field(min_length=1)
    company_id: str
    supplier_id: str
    parties: list[str] = []
    """Other supplier ids that are parties on the supplier side (joint lessors, co-owners)."""
    signed_on: date | None = None
    stamped_on: date | None = None
    has_price_review_clause: bool | None = None
    states_service: bool | None = None
    states_fixed_value: bool | None = None
    states_period: bool | None = None
    start: date | None = None
    end: date | None = None
    value: Money | None = None
    variation_orders: list[ContractChange] = []
    extensions_of_time: list[ContractChange] = []
    tax_facts: ContractTaxFacts | None = None

    @model_validator(mode="after")
    def _consistent(self) -> ContractRecord:
        _not_before(self.stamped_on, self.signed_on, "a contract is stamped after it is signed")
        _not_before(self.end, self.start, "a contract ends after it starts")
        if self.supplier_id in self.parties:
            raise ValueError("parties lists the other supplier-side parties, not the supplier itself")
        if len(self.parties) != len(set(self.parties)):
            raise ValueError("duplicate party")
        return self


class ResidenceCertificate(Model):
    """A payee's certificate of residence, held in the case documents."""

    certificate_id: str = Field(min_length=1)
    supplier_id: str
    country: str = Field(pattern=r"^[A-Z]{2}$")
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def _dates(self) -> ResidenceCertificate:
        _not_before(self.valid_to, self.valid_from, "a certificate's valid_to is not before its valid_from")
        return self

    def valid_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)
