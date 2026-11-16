"""Malaysian types: SST codes, category tax profile, MyInvois block, party tax facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from ...models.common import CountryBlock, Model, Money, TaxProfile, internal


class MyTaxTreatment(StrEnum):
    SST_CORRECT = "SST_CORRECT"
    SST_WRONG_RATE = "SST_WRONG_RATE"
    SST_SHOULD_BE_EXEMPT = "SST_SHOULD_BE_EXEMPT"
    SST_SUPPLIER_NOT_REGISTERED = "SST_SUPPLIER_NOT_REGISTERED"
    NO_SST = "NO_SST"


MyTaxClass = Literal["sales_5", "sales_10", "sales_exempt", "service_8", "service_6", "none"]
MyTaxType = Literal["01", "02", "03", "04", "05", "06", "E"]


class MyTaxProfile(TaxProfile):
    tax_class: MyTaxClass
    schedule_c_eligible: bool = False
    group_g: bool = False
    group_g_excluded: bool = False


class MyInvoisLine(Model):
    line_no: int
    classification_code: str | None = None
    tax_type: MyTaxType | None = None
    tax_exemption_reason: str | None = None


class MyInvois(CountryBlock):
    """MyInvois-style fields. is_einvoice False: an ordinary invoice from a supplier below the threshold."""

    country: Literal["MY"] = "MY"
    is_einvoice: bool
    einvoice_version: str | None = None
    einvoice_type_code: str | None = None
    uuid: str | None = None
    validation_datetime: str | None = None
    supplier_tin: str | None = None
    supplier_brn: str | None = None
    supplier_sst_no: str | None = None
    supplier_msic_code: str | None = None
    buyer_tin: str | None = None
    buyer_brn: str | None = None
    buyer_sst_no: str | None = None
    tax_total_by_type: dict[str, Money] | None = None
    lines: list[MyInvoisLine] = []


class MyCompanyFacts(CountryBlock):
    country: Literal["MY"] = "MY"
    is_registered_manufacturer: bool = False
    services_provided: list[str] = []
    """Catalog service categories the company itself provides (Group G B2B test)."""
    group_companies: list[str] = []


class MySupplierFacts(CountryBlock):
    country: Literal["MY"] = "MY"
    is_manufacturer: bool = False
    turnover_band: str | None = None
    service_categories: list[str] = []
    msic_code: str | None = None
    # Generator truth.
    # Do not add a clear "same group" value without its rule (Service Tax Policy 8/2020, group
    # relief) in tax.py and tests in the same PR. tax.py handles every value explicitly;
    # tests/rules/test_tax_my_scope.py fails if this Literal gains a value it doesn't handle.
    group_relation: Literal["unrelated", "unclear"] = internal("unrelated")
    """unclear: the documents don't show whether the supplier is in the buyer's group (group relief)."""
