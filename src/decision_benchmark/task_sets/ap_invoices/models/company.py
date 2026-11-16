"""Buying company and its people (step-11 plan §4.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import CompanyTaxFacts, CountryCode, Model, country_pack
from .policy import PolicyPack
from .tax import HasTaxRegistrations


class Address(Model):
    lines: list[str]
    city: str | None = None
    postcode: str | None = None
    state: str | None = None
    country: str


class Person(Model):
    person_id: str
    name: str
    role: Literal["procurement", "stores", "finance_manager", "requester", "director", "ap_clerk", "manager"]
    email: str
    approval_role: str | None = None
    languages: list[str] = ["en"]


class Company(HasTaxRegistrations):
    company_id: str
    split: str
    country: CountryCode
    legal_name: str
    trading_name: str | None = None
    registration_no: str
    address: Address
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    industry: str
    tax_facts: CompanyTaxFacts | None = None
    """Facts only the company's country rules use (e.g. manufacturer status); the country pack's model."""
    people: list[Person]
    policy_pack: PolicyPack

    @model_validator(mode="after")
    def _country_rules(self) -> Company:
        ids = [p.person_id for p in self.people]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate person_id")
        country_pack(self.country).check_company(self)
        return self

    def person(self, person_id: str) -> Person | None:
        return next((p for p in self.people if p.person_id == person_id), None)
