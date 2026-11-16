"""Supplier master record (step-11 plan §4.3)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from .common import Model, SupplierTaxFacts
from .company import Address
from .tax import HasTaxRegistrations


class Contact(Model):
    contact_id: str
    name: str
    email: str
    phone: str | None = None


class BankAccount(Model):
    bank_name: str
    account_name: str
    account_no: str
    swift: str | None = None


class BankChange(Model):
    changed_on: date
    old_account_no: str
    new_account_no: str
    method: Literal["verified_change_form", "email_only", "phone_unverified"]
    verified_by: str | None = None

    @property
    def verified(self) -> bool:
        return self.method == "verified_change_form" and bool(self.verified_by)


class Supplier(HasTaxRegistrations):
    supplier_id: str
    company_id: str
    name: str
    country: str = Field(pattern=r"^([A-Z]{2}|OTHER)$")
    """The supplier's own country (it may be a country without a pack, or OTHER)."""
    address: Address
    registration_no: str | None = None
    currency: str
    payment_terms_days: int
    contacts: list[Contact] = []
    bank_account: BankAccount
    """The account on file as of the latest change in bank_change_log."""
    bank_change_log: list[BankChange] = []
    tax_facts: SupplierTaxFacts | None = None
    """Facts only the buyer country's rules use (e.g. manufacturer status); that country pack's model."""
