"""Singapore types: GST codes, category tax profile, PINT-SG block, party tax facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from ...models.common import CountryBlock, Model, Money, TaxProfile


class SgTaxTreatment(StrEnum):
    CLAIMABLE = "CLAIMABLE"
    NOT_CLAIMABLE_DISALLOWED = "NOT_CLAIMABLE_DISALLOWED"
    NOT_CLAIMABLE_INVALID_INVOICE = "NOT_CLAIMABLE_INVALID_INVOICE"
    GST_WRONGLY_CHARGED = "GST_WRONGLY_CHARGED"
    NO_GST = "NO_GST"


SgDisallowed = Literal[
    "club_subscription",
    "staff_medical",
    "motor_car",
    "family_benefit",
    "medical_accident_insurance",
    "betting",
]


class SgTaxProfile(TaxProfile):
    disallowed: SgDisallowed | None = None
    """Regulation 26/27 class of the expense, if any."""


class PintSgLine(Model):
    line_no: int
    tax_category: Literal["SR", "ZR", "ES", "OS", "NA"] | None = None


class PintSg(CountryBlock):
    """PINT-SG-style fields and what a Singapore tax invoice prints."""

    country: Literal["SG"] = "SG"
    is_peppol: bool = False
    customization_id: str | None = None
    profile_id: str | None = None
    invoice_type_code: Literal["380", "381"] = "380"
    document_title: str | None = None
    """As printed, e.g. "Tax Invoice". None: no title."""
    supplier_gst_no: str | None = None
    tax_total_sgd: Money | None = None
    gross_sgd: Money | None = None
    price_includes_gst_statement: bool = False
    lines: list[PintSgLine] = []


class SgCompanyFacts(CountryBlock):
    country: Literal["SG"] = "SG"


class SgSupplierFacts(CountryBlock):
    country: Literal["SG"] = "SG"
