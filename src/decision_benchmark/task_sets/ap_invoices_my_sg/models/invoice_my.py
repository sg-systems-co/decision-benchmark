"""MyInvois-style invoice record (Malaysia).

Field names follow the MyInvois data structure in snake_case. The fields the
tax-rule sheet marks as mandatory are optional here, so a missing field can be
planted; rules/validity_my.py checks them.
"""

from __future__ import annotations

from typing import Literal

from .common import Money
from .invoice_base import InvoiceBase, InvoiceLineBase

MyTaxType = Literal["01", "02", "03", "04", "05", "06", "E"]


class InvoiceLineMY(InvoiceLineBase):
    classification_code: str | None = None
    tax_type: MyTaxType | None = None
    tax_exemption_reason: str | None = None


class InvoiceMY(InvoiceBase):
    country: Literal["MY"] = "MY"
    lines: list[InvoiceLineMY]
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

