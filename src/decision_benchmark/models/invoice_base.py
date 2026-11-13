"""Fields shared by Malaysian and Singaporean invoices (step-11 plan §4.5)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from .common import Model, Money, Num, internal


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


class LineFacts(Model):
    """Facts about a line that the documents may or may not settle. None means the documents don't say.

    The rules engine reads only the facts that matter for the line's category.
    """

    vehicle_is_motor_car: bool | None = None
    staff_medical_obligatory: bool | None = None
    recipient_provides_same_service: bool | None = None
    personal_use: bool = False


class InvoiceLineBase(Model):
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
    facts: LineFacts = internal(LineFacts())


class InvoiceBase(Model):
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
