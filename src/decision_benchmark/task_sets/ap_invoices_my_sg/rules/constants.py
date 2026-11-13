"""Rates and thresholds the rules engine uses, each with its official source.

Sources are the pages cited in docs/task-sets/ap-invoices-my-sg/tax-rules-v0.9.md,
plus the IRAS GST rate page (CHANGELOG clarification, step-11 plan Q2).
"""

from __future__ import annotations

from decimal import Decimal

# Singapore -----------------------------------------------------------------

SG_GST_RATE = Decimal("9")
SG_GST_RATE_SOURCE = "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates"

SG_FULL_TAX_INVOICE_THRESHOLD = Decimal("1000.00")
"""Above S$1,000 a full tax invoice is needed: "tax invoice" wording, customer name, GST amount."""
SG_INVOICE_SOURCE = (
    "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/"
    "invoicing-price-display-and-record-keeping/invoicing-customers"
)
SG_INPUT_TAX_SOURCE = (
    "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax"
)

# Malaysia ------------------------------------------------------------------

MY_TAX_CLASS_RATE = {
    "sales_5": Decimal("5"),
    "sales_10": Decimal("10"),
    "service_8": Decimal("8"),
    "service_6": Decimal("6"),
}
MY_SALES_TAX_SOURCE = "https://mysst.customs.gov.my/faq-sales-tax/"
MY_SERVICE_TAX_SOURCE = "https://mysst.customs.gov.my/faq-services-tax/"
MY_GROUP_G_SOURCE = (
    "https://mysst.customs.gov.my/assets/document/Industry%20Guides/GI/Guide%20on%20Management%20Services%20%20V5%206.5.2026.pdf"
)

MY_TAX_TYPE_SALES = "01"
MY_TAX_TYPE_SERVICE = "02"

MY_EINVOICE_MANDATORY_HEADER = (
    "supplier_tin",
    "buyer_tin",
    "supplier_brn",
    "buyer_brn",
    "einvoice_type_code",
    "currency",
)
"""MyInvois mandatory fields (rule sheet): supplier and buyer TIN, registration numbers, type code, currency.
The issue date is always present in the model and is not planted as missing."""
MY_EINVOICE_MANDATORY_LINE = ("classification_code", "description", "unit_price", "tax_type")
MY_EINVOICE_MANDATORY_TOTALS = ("tax_total_by_type",)
MY_EINVOICE_SOURCE = "https://sdk.myinvois.hasil.gov.my/documents/invoice-v1-0/"
