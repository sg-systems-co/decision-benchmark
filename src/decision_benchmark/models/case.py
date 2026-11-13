"""Company records, ledger history and the case (step-11 plan §4.8, §4.11)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import model_validator

from .common import Country, Model
from .company import Company
from .email import Email
from .facts import FactSheet
from .invoice_sg import Invoice
from .procurement import GoodsReceipt, PurchaseOrder
from .supplier import Supplier


class LedgerInvoice(Model):
    """An invoice or credit note already in the AP ledger (history)."""

    ledger_id: str
    supplier_id: str
    status: Literal["paid", "open"]
    posted_on: date
    invoice: Invoice


class CompanyRecords(Model):
    """Everything the company's systems hold. Shared by all cases of the company."""

    company: Company
    suppliers: list[Supplier]
    purchase_orders: list[PurchaseOrder] = []
    goods_receipts: list[GoodsReceipt] = []
    ledger: list[LedgerInvoice] = []
    emails: list[Email] = []

    @model_validator(mode="after")
    def _ids(self) -> CompanyRecords:
        for name, ids in (
            ("supplier_id", [s.supplier_id for s in self.suppliers]),
            ("po_number", [p.po_number for p in self.purchase_orders]),
            ("gr_number", [g.gr_number for g in self.goods_receipts]),
            ("ledger_id", [entry.ledger_id for entry in self.ledger]),
            ("message_id", [e.message_id for e in self.emails]),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {name}")
        return self

    def supplier(self, supplier_id: str) -> Supplier | None:
        return next((s for s in self.suppliers if s.supplier_id == supplier_id), None)


class Provenance(Model):
    generator_version: str
    seed: int
    pipeline_hash: str


class Case(Model):
    case_id: str
    split: str
    country: Country
    company_id: str
    as_of_date: date
    supplier_id: str
    invoice: Invoice
    invoice_file: str | None = None
    modality: Literal["pdf", "scan", "photo"] = "pdf"
    fact_sheets: list[FactSheet] = []
    exception_types: list[str] = []
    families: list[str] = []
    two_problems: bool = False
    provenance: Provenance | None = None
    languages: list[str] = ["en"]

    @model_validator(mode="after")
    def _consistent(self) -> Case:
        if self.invoice.country != self.country.value:
            raise ValueError("invoice country differs from case country")
        if self.invoice.issue_date > self.as_of_date:
            raise ValueError("invoice is dated after the case's as_of_date")
        return self
