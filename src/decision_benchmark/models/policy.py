"""Policy pack of a buying company (step-11 plan §4.2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .common import Model, Money, Num, internal


class TolerancePolicy(Model):
    price_tolerance_pct: Num
    price_tolerance_abs: Money | None = None
    """Optional. If both are set, the larger allowance applies."""
    quantity_tolerance_units: Num = Decimal("0")
    rounding_tolerance: Money
    duplicate_window_days: int = Field(ge=1)


class ApprovalLimit(Model):
    approval_role: str
    limit: Money
    currency: Literal["MYR", "SGD"]


class NonPoPolicy(Model):
    allowed_categories: list[str] = []
    max_amount: Money = Decimal("0.00")


class Account(Model):
    code: str
    name: str
    type: Literal["expense", "asset", "liability", "income", "tax"]
    description: str = ""
    active: bool = True
    role: str | None = internal(None)
    """Catalog GL role this account serves (generator truth, not exported)."""


class TaxRegistration(Model):
    country: Literal["MY", "SG"]
    numbers: dict[str, str]
    status: Literal["registered", "not_registered"]
    effective_from: date | None = None


class ExemptionCertificate(Model):
    kind: Literal["schedule_c", "group_g_b2b_declaration"]
    number: str
    valid_from: date
    valid_to: date | None = None
    categories: list[str]

    def valid_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class RuleText(Model):
    counts_only_verified: bool = True
    """True: only an approved ERP amendment (price) or a verified supplier-master change (bank) counts."""
    text: str


class PolicyDocument(Model):
    doc_id: str
    title: str
    text: str


class PolicyPack(Model):
    tolerance_policy: TolerancePolicy
    approval_matrix: list[ApprovalLimit]
    non_po_policy: NonPoPolicy = NonPoPolicy()
    chart_of_accounts: list[Account]
    tax_registration: TaxRegistration
    exemption_certificates: list[ExemptionCertificate] = []
    price_change_rule: RuleText
    bank_change_rule: RuleText
    documents: list[PolicyDocument] = []

    @model_validator(mode="after")
    def _unique(self) -> PolicyPack:
        codes = [a.code for a in self.chart_of_accounts]
        if len(codes) != len(set(codes)):
            raise ValueError("chart of accounts has duplicate codes")
        roles = [a.approval_role for a in self.approval_matrix]
        if len(roles) != len(set(roles)):
            raise ValueError("approval matrix has duplicate roles")
        return self

    def account(self, code: str) -> Account | None:
        return next((a for a in self.chart_of_accounts if a.code == code), None)

    def limit_for(self, approval_role: str) -> ApprovalLimit | None:
        return next((a for a in self.approval_matrix if a.approval_role == approval_role), None)
