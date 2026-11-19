"""The goods the Malaysian sales tax area orders name (MG-5): a typed loader for data/area_goods_lists.yaml."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from ...models.common import Model, Money
from .models import AreaGoods

AREA_GOODS_FILE = Path(__file__).resolve().parent / "data" / "area_goods_lists.yaml"


class AreaGoodsRow(Model):
    order: Literal["da", "sa", "pulau_1_not_taxed"]
    goods: list[AreaGoods]
    zones: list[str]
    from_: date = Field(alias="from")
    to: date | None = None
    not_used_directly: bool = False
    tasik_kenyir: bool = False
    headings: list[str] = []
    value_above: Money | None = None
    value_basis: Literal["cif", "sales_price"] | None = None
    note: str | None = None
    source: str

    def in_force(self, day: date) -> bool:
        return self.from_ <= day and (self.to is None or day <= self.to)


class AreaGoodsTable(Model):
    source: list[str]
    rows: list[AreaGoodsRow]


@cache
def table() -> AreaGoodsTable:
    return AreaGoodsTable.model_validate(yaml.safe_load(AREA_GOODS_FILE.read_text(encoding="utf-8")))


def rows(order: str, zone: str, day: date) -> list[AreaGoodsRow]:
    """The rows of one order in force for a zone on a day."""
    return [r for r in table().rows if r.order == order and zone in r.zones and r.in_force(day)]


def names(kinds: list[str], row: AreaGoodsRow) -> bool:
    return bool(set(kinds) & set(row.goods))


def heading_of(tariff: str | None) -> str | None:
    """The tariff heading as the orders write it: "8703.23.10 00" -> "87.03"."""
    if not tariff:
        return None
    digits = re.sub(r"\D", "", tariff)
    return f"{digits[:2]}.{digits[2:4]}"


def value_over(row: AreaGoodsRow, value: Decimal | None, basis: str | None) -> bool | None:
    """Whether a vehicle's value is above the row's threshold, on the row's basis; None: not shown."""
    if row.value_above is None:
        return True
    if value is None or basis is None:
        return None
    return basis == row.value_basis and value > row.value_above
