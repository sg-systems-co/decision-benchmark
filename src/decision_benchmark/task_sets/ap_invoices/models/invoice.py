"""Invoice and credit note: one model for every country (step-11 plan §4.5).

Country fields (the country's e-invoice standard and printed tax details) sit in
the ``einvoice`` block, whose model comes from the invoice country's pack. Line
facts are the pack's line-facts model (spec v0.10 "Facts"), parsed by the invoice's country.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from typing import Any

from pydantic import SerializeAsAny, model_validator

from .common import CountryCode, EInvoiceBlock, Model, Money, Num, country_pack, internal
from .evidence import LineFacts


class PartyBlock(Model):
    """Name and address as printed. Any part may be missing on the document."""

    name: str | None = None
    address: str | None = None


class BankBlock(Model):
    bank_name: str | None = None
    account_name: str | None = None
    account_no: str | None = None


class Totals(Model):
    net: Money
    tax: Money | None = None
    """None: no tax amount printed on the document."""
    gross: Money
    rounding: Money = Decimal("0.00")


class InvoiceLine(Model):
    line_no: int
    description: str | None = None
    qty: Num
    uom: str
    unit_price: Money | None = None
    net_amount: Money
    tax_rate: Num = Decimal("0")
    tax_amount: Money = Decimal("0.00")
    po_line_no: int | None = None
    category: str = internal()
    facts: SerializeAsAny[LineFacts] | None = internal(None)
    """Generator truth: the line facts with their evidence, the invoice country's line-facts model. None: none recorded."""


class Invoice(Model):
    country: CountryCode
    invoice_id: str
    doc_type: Literal["invoice", "credit_note"] = "invoice"
    invoice_number: str
    issue_date: date
    due_date: date | None = None
    supplier_block: PartyBlock
    buyer_block: PartyBlock
    po_reference: str | None = None
    currency: str
    exchange_rate: Num | None = None
    """Units of base currency per unit of invoice currency, as printed."""
    totals: Totals
    bank_block: BankBlock | None = None
    payment_terms_text: str | None = None
    notes: list[str] = []
    original_invoice_ref: str | None = None
    service_period_start: date | None = None
    service_period_end: date | None = None
    languages: list[str] = ["en"]
    lines: list[InvoiceLine]
    einvoice: EInvoiceBlock

    @model_validator(mode="before")
    @classmethod
    def _parse_line_facts(cls, data: Any) -> Any:
        """Line facts come as dicts in the spec's format; the invoice country's pack gives their model."""
        if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
            return data
        block = data.get("einvoice")
        if isinstance(block, dict) and block.get("country") != data.get("country"):
            raise ValueError(f"einvoice block is for {block.get('country')}, invoice is {data.get('country')}")
        lines = []
        for line in data["lines"]:
            if isinstance(line, dict) and isinstance(line.get("facts"), dict):
                line = line | {"facts": country_pack(data.get("country", "")).line_facts_model.model_validate(line["facts"])}
            lines.append(line)
        return data | {"lines": lines}

    @model_validator(mode="after")
    def _country_fields(self) -> Invoice:
        if self.einvoice.country != self.country:
            raise ValueError(f"einvoice block is for {self.einvoice.country}, invoice is {self.country}")
        country_pack(self.country).check_invoice(self)
        return self

    def line(self, line_no: int) -> InvoiceLine | None:
        return next((line for line in self.lines if line.line_no == line_no), None)
