"""Tariff codes exempted from sales tax by Sales Tax Policies (G-1, G-2, G-3): a typed loader for
data/sales_tax_exempt_tariff_codes.yaml (generated from the archived policies; see its header)."""

from __future__ import annotations

import re
from datetime import date
from functools import cache
from pathlib import Path

import yaml
from pydantic import Field

from ...models.common import Model

TARIFF_FILE = Path(__file__).resolve().parent / "data" / "sales_tax_exempt_tariff_codes.yaml"


class TariffRow(Model):
    tariff_code: str = Field(pattern=r"^\d{4}(\.\d{2}){0,2}( \d{2})?$")
    description: str
    group: str
    item_no: int | None = None
    rule: str = Field(pattern=r"^G-\d$")
    effective_from: date
    source: str

    @property
    def digits(self) -> str:
        return re.sub(r"\D", "", self.tariff_code)


class TariffTable(Model):
    source: list[str]
    retrieved: date
    table: str
    notes: list[str] = []
    rows: list[TariffRow]


@cache
def table() -> TariffTable:
    return TariffTable.model_validate(yaml.safe_load(TARIFF_FILE.read_text(encoding="utf-8")))


def find(code: str) -> TariffRow | None:
    """The row covering a tariff code. A 4-digit code in the table is a heading covering its subheadings."""
    digits = re.sub(r"\D", "", code)
    for row in table().rows:
        if digits == row.digits or (len(row.digits) == 4 and digits.startswith(row.digits)):
            return row
    return None
