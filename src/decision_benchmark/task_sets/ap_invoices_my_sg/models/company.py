"""Buying company and its people (step-11 plan §4.1)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import model_validator

from .common import Country, Model
from .policy import PolicyPack


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


class Company(Model):
    company_id: str
    split: str
    country: Country
    legal_name: str
    trading_name: str | None = None
    registration_no: str
    address: Address
    base_currency: Literal["MYR", "SGD"]
    industry: str
    # Malaysia
    tin: str | None = None
    sst_registration_no: str | None = None
    is_registered_manufacturer: bool = False
    services_provided: list[str] = []
    """Catalog service categories the company itself provides (Group G B2B test)."""
    group_companies: list[str] = []
    # Singapore
    gst_reg_no: str | None = None
    gst_registered_since: date | None = None
    people: list[Person]
    policy_pack: PolicyPack

    @model_validator(mode="after")
    def _country_fields(self) -> Company:
        if self.country is Country.MY:
            if self.base_currency != "MYR" or not self.tin:
                raise ValueError("a Malaysian company needs base_currency MYR and a TIN")
        else:
            # Step-11 plan Q5: every Singapore buying company is GST-registered in v0.9.
            if self.base_currency != "SGD" or not self.gst_reg_no or self.gst_registered_since is None:
                raise ValueError("a Singapore company needs base_currency SGD and a GST registration")
        ids = [p.person_id for p in self.people]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate person_id")
        return self

    def person(self, person_id: str) -> Person | None:
        return next((p for p in self.people if p.person_id == person_id), None)
