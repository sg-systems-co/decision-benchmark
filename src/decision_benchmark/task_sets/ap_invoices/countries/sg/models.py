"""Singapore types: GST codes, category tax profile, PINT-SG block, party tax facts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import StringConstraints

from ...models.common import CountryBlock, Model, Money, TaxProfile
from ...models.evidence import LineFact, LineFacts, Share, fact_field


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


class SgLineFacts(LineFacts):
    """Singapore line facts: exactly the fields of $defs/line_facts in schemas/ap-invoices/v0.10/countries/sg.schema.json
    (names, value types, families, rules; tests/models/test_line_facts.py checks it)."""

    exempt_supply: LineFact[Literal["financial", "digital_payment_token", "residential_property", "investment_precious_metal", "none"]] | None = fact_field("classification", "SG-5")
    zero_rating_provision: LineFact[Annotated[str, StringConstraints(pattern=r"^s21\((3\)\([a-y]|6A?)\)$")]] | None = fact_field("classification", "SG-6")
    prescribed_goods: LineFact[Literal["mobile_phone", "memory_card", "off_the_shelf_software", "none"]] | None = fact_field("classification", "SG-7")
    disallowed_category: LineFact[Literal["club_subscription", "staff_medical", "motor_car", "family_benefit", "medical_accident_insurance", "betting", "director_only_benefit", "third_party_csr", "none"]] | None = fact_field("classification", "SG-10")
    vehicle_is_motor_car: LineFact[bool] | None = fact_field("classification", "SG-10")
    delivery_date: LineFact[date] | None = fact_field("time_and_rate", "SG-3")
    amount_paid_before_change: LineFact[Money] | None = fact_field("time_and_rate", "SG-3")
    value_delivered_before_change: LineFact[Money] | None = fact_field("time_and_rate", "SG-3")
    contract_excludes_tax_change: LineFact[bool] | None = fact_field("time_and_rate", "SG-3")
    goods_outside_singapore: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-6")
    export_evidence: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-6")
    international_transport: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-6")
    staff_medical_obligatory: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-10")
    insurance_obligatory: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-10")
    chauffeured_pay_per_trip: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-10")
    car_used_by_third_party: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-10")
    purchase_attribution: LineFact[Literal["taxable", "exempt", "residual"]] | None = fact_field("buyer_and_purpose", "SG-9")
    business_purpose: LineFact[bool] | None = fact_field("buyer_and_purpose", "SG-1", "SG-10")
    payment_nature: LineFact[Literal["interest", "royalty", "knowledge_or_information", "movable_property_rent", "technical_or_management_fee", "electronic_service", "ship_charter", "professional_fee", "director_fee", "copyrighted_article", "none"]] | None = fact_field("withholding", "WH-5")
    place_of_performance: LineFact[Literal["in_country", "outside", "mixed"]] | None = fact_field("withholding", "WH-5")
    certificate_of_residence: LineFact[bool] | None = fact_field("withholding", "WH-5")
    beneficiary_outside_singapore: LineFact[bool] | None = fact_field("scope_and_exemption", "SG-6")
    low_value_goods: LineFact[bool] | None = fact_field("classification", "SG-8")
