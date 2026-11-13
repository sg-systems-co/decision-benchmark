"""PINT-SG-style invoice record (Singapore)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import Money
from .invoice_base import InvoiceBase, InvoiceLineBase
from .invoice_my import InvoiceMY


class InvoiceLineSG(InvoiceLineBase):
    tax_category: Literal["SR", "ZR", "ES", "OS", "NA"] | None = None


class InvoiceSG(InvoiceBase):
    country: Literal["SG"] = "SG"
    lines: list[InvoiceLineSG]
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


Invoice = Annotated[InvoiceMY | InvoiceSG, Field(discriminator="country")]
