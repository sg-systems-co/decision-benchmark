"""Malaysian rates, codes and mandatory fields, each with its source from tax-rules-v0.9.md."""

from __future__ import annotations

from decimal import Decimal

TAX_CLASS_RATE = {
    "sales_5": Decimal("5"),
    "sales_10": Decimal("10"),
    "service_8": Decimal("8"),
    "service_6": Decimal("6"),
}
SALES_TAX_SOURCE = "https://mysst.customs.gov.my/faq-sales-tax/"
SERVICE_TAX_SOURCE = "https://mysst.customs.gov.my/faq-services-tax/"
GROUP_G_SOURCE = (
    "https://mysst.customs.gov.my/assets/document/Industry%20Guides/GI/Guide%20on%20Management%20Services%20%20V5%206.5.2026.pdf"
)

TAX_TYPE_SALES = "01"
TAX_TYPE_SERVICE = "02"

EINVOICE_MANDATORY_HEADER = (
    "supplier_tin",
    "buyer_tin",
    "supplier_brn",
    "buyer_brn",
    "einvoice_type_code",
    "currency",
)
"""MyInvois mandatory fields (rule sheet): supplier and buyer TIN, registration numbers, type code, currency.
The issue date is always present in the model and is not planted as missing."""
EINVOICE_MANDATORY_LINE = ("classification_code", "description", "unit_price", "tax_type")
EINVOICE_MANDATORY_TOTALS = ("tax_total_by_type",)
EINVOICE_SOURCE = "https://sdk.myinvois.hasil.gov.my/documents/invoice-v1-0/"

GROUP_RELATIONS_HANDLED = ("unrelated", "unclear")
"""Every value of MySupplierFacts.group_relation that tax.assess handles explicitly."""
