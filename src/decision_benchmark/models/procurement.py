"""Purchase orders and goods receipts (step-11 plan §4.4)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import model_validator

from .common import Model, Money, Num


class POLine(Model):
    line_no: int
    item_code: str | None = None
    description: str
    category: str
    qty: Num
    uom: str
    unit_price: Money
    gl_account: str


class POAmendment(Model):
    amended_on: date
    line_no: int
    field: Literal["unit_price", "qty"]
    old: Num
    new: Num
    approved_by: str | None = None


class PurchaseOrder(Model):
    po_number: str
    company_id: str
    supplier_id: str
    po_date: date
    currency: str
    requester_id: str
    approver_id: str
    status: Literal["open", "partially_received", "received", "closed"]
    lines: list[POLine]
    amendments: list[POAmendment] = []
    total_net: Money

    @model_validator(mode="after")
    def _lines(self) -> PurchaseOrder:
        nos = [line.line_no for line in self.lines]
        if not nos or len(nos) != len(set(nos)):
            raise ValueError("a PO needs lines with unique line numbers")
        return self

    def line(self, line_no: int) -> POLine | None:
        return next((line for line in self.lines if line.line_no == line_no), None)


class GRLine(Model):
    po_line_no: int
    qty_received: Num
    uom: str
    note: str | None = None


class GoodsReceipt(Model):
    gr_number: str
    po_number: str
    gr_date: date
    kind: Literal["goods", "service_confirmation"]
    received_by: str
    lines: list[GRLine]
