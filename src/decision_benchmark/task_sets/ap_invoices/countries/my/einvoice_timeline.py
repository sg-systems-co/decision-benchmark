"""The Malaysian e-invoicing timeline (ME-1): a typed loader for data/einvoice_timeline.yaml and the supplier's
implementation date and interim relaxation end that follow from its record."""

from __future__ import annotations

from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal

import yaml

from ...models.common import Model
from .models import EinvoiceBand, MyEinvoiceStatus, SupplierKind

TIMELINE_FILE = Path(__file__).resolve().parent / "data" / "einvoice_timeline.yaml"


class TimelineRow(Model):
    kind: Literal["phase", "exempt_band", "new_business", "exempt_person", "relaxation"]
    bands: list[EinvoiceBand] = []
    start: date | None = None
    starts: list[date] = []
    started_from: date | None = None
    started_to: date | None = None
    supplier_kinds: list[SupplierKind] = []
    to: date | None = None
    statutory_fees: bool = False
    source: str


class Timeline(Model):
    source: list[str]
    rows: list[TimelineRow]

    def of(self, kind: str) -> list[TimelineRow]:
        return [r for r in self.rows if r.kind == kind]


@cache
def timeline() -> Timeline:
    return Timeline.model_validate(yaml.safe_load(TIMELINE_FILE.read_text(encoding="utf-8")))


def exempt_band(band: EinvoiceBand) -> bool:
    return any(band in r.bands for r in timeline().of("exempt_band"))


def exempt_person(kind: SupplierKind) -> TimelineRow | None:
    return next((r for r in timeline().of("exempt_person") if kind in r.supplier_kinds), None)


def implementation_date(status: MyEinvoiceStatus) -> date | None:
    """When the supplier must start issuing e-invoices. None: no mandatory date (yet)."""
    if status.turnover_basis != "new_business":
        return next((r.start for r in timeline().of("phase") if status.turnover_band in r.bands), None)
    started = status.business_started_on
    assert started is not None
    for r in timeline().of("new_business"):
        assert r.started_from is not None and r.start is not None
        if started < r.started_from or (r.started_to is not None and started > r.started_to):
            continue
        if r.started_to is not None:                       # commenced 2023-2025: turnover of at least RM1m
            return r.start if status.turnover_band != "below_1m" else None
        if status.turnover_band == "below_1m" or status.turnover_reached_1m_on is not None:
            # First year below RM1m: 1 January of the second year following the year turnover reached RM1m.
            reached = status.turnover_reached_1m_on
            return date(reached.year + 2, 1, 1) if reached is not None else None
        return max(r.start, started)
    return None


def relaxation_end(start: date, band: EinvoiceBand) -> date | None:
    """The last day of the interim relaxation period for this implementation date and band (Specific Guideline
    Table 16.1). None: the table has no period for it."""
    return next((r.to for r in timeline().of("relaxation") if start in r.starts and band in r.bands), None)


def earliest_relaxation_end() -> date:
    """Before this day no supplier can be past its relaxation period."""
    return min(r.to for r in timeline().of("relaxation") if r.to is not None)
