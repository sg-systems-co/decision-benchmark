"""Effective dates of tax treaties and protocols that change withholding rates (rule sheet §4A, engine 0.10.3).

A country pack keeps them in data/treaty_effective_dates.yaml: one row per payee country (ISO code) whose treaty row
takes effect on a date that matters to the cases. Before that date the treaty row doesn't apply and the domestic rate
does (each row's `before` says why: no earlier treaty, or an earlier one with no lower rate). Generic: nothing here
names a country."""

from __future__ import annotations

from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal

import yaml

from .common import Model


class TreatyDate(Model):
    country: str
    instrument: str
    entry_into_force: date
    effective_from: date
    before: Literal["domestic_rate"]
    note: str
    source: str


class TreatyDates(Model):
    source: list[str]
    rows: list[TreatyDate]


@cache
def load(path: Path) -> dict[str, TreatyDate]:
    table = TreatyDates.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    return {r.country: r for r in table.rows}


def in_effect(path: Path, country: str, day: date) -> bool:
    """Whether the payee country's treaty row applies on the day (True when the file names no date for it)."""
    row = load(path).get(country)
    return row is None or day >= row.effective_from
