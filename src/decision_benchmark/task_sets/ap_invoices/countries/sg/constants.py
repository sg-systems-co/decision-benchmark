"""Singapore rates and thresholds, each with its source from tax-rules-v0.9.md."""

from __future__ import annotations

from decimal import Decimal

GST_RATE = Decimal("9")
GST_RATE_SOURCE = "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates"

FULL_TAX_INVOICE_THRESHOLD = Decimal("1000.00")
"""Above S$1,000 a full tax invoice is needed: "tax invoice" wording, customer name, GST amount."""
INVOICE_SOURCE = (
    "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/"
    "invoicing-price-display-and-record-keeping/invoicing-customers"
)
INPUT_TAX_SOURCE = (
    "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax"
)
