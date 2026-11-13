"""Supplier master record (step-11 plan §4.3)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from .common import Model, internal
from .company import Address


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


class Supplier(Model):
    supplier_id: str
    company_id: str
    name: str
    country: Literal["MY", "SG", "TH", "OTHER"]
    address: Address
    registration_no: str | None = None
    currency: str
    payment_terms_days: int
    contacts: list[Contact] = []
    bank_account: BankAccount
    """The account on file as of the latest change in bank_change_log."""
    bank_change_log: list[BankChange] = []
    # Malaysia (also used for Thai suppliers selling to Malaysian buyers)
    tin: str | None = None
    brn: str | None = None
    sst_registration_no: str | None = None
    sst_type: Literal["sales", "service", "both", "none"] = "none"
    is_manufacturer: bool = False
    turnover_band: str | None = None
    service_categories: list[str] = []
    msic_code: str | None = None
    # Singapore
    gst_reg_no: str | None = None
    gst_status: Literal["registered", "deregistered", "none"] = "none"
    gst_status_date: date | None = None
    """registered: registered since this date; deregistered: deregistered on this date."""
    gst_regime: Literal["local", "ovr"] = "local"
    # Generator truth
    group_relation: Literal["unrelated", "unclear"] = internal("unrelated")
    """unclear: the documents don't show whether the supplier is in the buyer's group (group relief)."""

    def sst_registered_for(self, kind: Literal["sales", "service"]) -> bool:
        return bool(self.sst_registration_no) and self.sst_type in (kind, "both")

    def gst_registered_on(self, day: date) -> bool:
        if self.gst_status == "registered":
            return self.gst_status_date is None or self.gst_status_date <= day
        if self.gst_status == "deregistered":
            # Registered until the deregistration date. The registration start is not modelled.
            return self.gst_status_date is not None and day < self.gst_status_date
        return False
