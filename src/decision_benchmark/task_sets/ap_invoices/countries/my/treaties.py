"""Malaysian treaty withholding rates: a typed loader for data/dta_withholding_rates.yaml (LHDN's table, archived;
see the file's header). LHDN notes: the lower of the treaty and the domestic rate applies (i); the payer keeps the
payee's certificate of residence (iii); a 15/10 row means 10% only for interest paid by an enterprise in an
industrial undertaking (iv)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import yaml
from pydantic import field_validator

from ...models import treaty_dates
from ...models.common import Model

TREATY_FILE = Path(__file__).resolve().parent / "data" / "dta_withholding_rates.yaml"
TREATY_DATES_FILE = Path(__file__).resolve().parent / "data" / "treaty_effective_dates.yaml"
"""Treaty rows that take effect on or after 1 Jan 2023: before the date, the domestic rate (engine 0.10.3)."""
LHDN_COUNTRIES = {
    "Albania": "AL", "Argentina": "AR", "Australia": "AU", "Austria": "AT", "Bahrain": "BH", "Bangladesh": "BD",
    "Belgium": "BE", "Bosnia and Herzegovina": "BA", "Brunei": "BN", "Cambodia": "KH", "Canada": "CA", "Chile": "CL",
    "China": "CN", "Chinese Taipei": "TW", "Croatia": "HR", "Czech Republic": "CZ", "Denmark": "DK", "Egypt": "EG",
    "Fiji": "FJ", "Finland": "FI", "France": "FR", "Germany": "DE", "Hong Kong": "HK", "Hungary": "HU", "India": "IN",
    "Indonesia": "ID", "Iran": "IR", "Ireland": "IE", "Italy": "IT", "Japan": "JP", "Jordan": "JO", "Kazakhstan": "KZ",
    "Korea Republic": "KR", "Kuwait": "KW", "Kyrgyz Republic": "KG", "Laos": "LA", "Lebanon": "LB", "Luxembourg": "LU",
    "Malta": "MT", "Mauritius": "MU", "Mongolia": "MN", "Morocco": "MA", "Myanmar": "MM", "Namibia": "NA",
    "Netherlands": "NL", "New Zealand": "NZ", "Norway": "NO", "Pakistan": "PK", "Papua New Guinea": "PG",
    "Philippines": "PH", "Poland": "PL", "Qatar": "QA", "Romania": "RO", "Russia": "RU", "San Marino": "SM",
    "Saudi Arabia": "SA", "Senegal": "SN", "Seychelles": "SC", "Singapore": "SG", "Slovak Republic": "SK",
    "South Africa": "ZA", "Spain": "ES", "Sri Lanka": "LK", "Sudan": "SD", "Sweden": "SE", "Switzerland": "CH",
    "Syria": "SY", "Thailand": "TH", "Turkmenistan": "TM", "Türkiye": "TR", "Ukraine": "UA",
    "United Arab Emirates": "AE", "United Kingdom": "GB", "United States of America": "US", "Uzbekistan": "UZ",
    "Venezuela": "VE", "Vietnam": "VN", "Zimbabwe": "ZW",
}
"""LHDN's country names -> ISO 3166-1 alpha-2 (a test checks every row maps)."""


class LhdnRate(Model):
    """One printed rate: a percentage, NIL (no withholding), or 15/10 under note (iv)."""

    general: Decimal
    industrial_undertaking: Decimal | None = None

    @classmethod
    def parse(cls, text: str) -> LhdnRate:
        text = text.strip()
        if text.upper() == "NIL":
            return cls(general=Decimal(0))
        m = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?) \(iv\)", text)
        if m:
            return cls(general=Decimal(m.group(1)), industrial_undertaking=Decimal(m.group(2)))
        return cls(general=Decimal(text))

    def for_payer(self, industrial_undertaking: bool) -> Decimal:
        if industrial_undertaking and self.industrial_undertaking is not None:
            return self.industrial_undertaking
        return self.general


class LhdnRow(Model):
    country: str
    agreement: str
    interest: LhdnRate
    royalties: LhdnRate
    technical_fees: LhdnRate
    source: str

    @field_validator("interest", "royalties", "technical_fees", mode="before")
    @classmethod
    def _rate(cls, value):
        return LhdnRate.parse(str(value)) if not isinstance(value, dict) else value


class LhdnDomestic(Model):
    interest: Decimal
    royalties: Decimal
    technical_fees: Decimal
    source: str


class LhdnTable(Model):
    source: list[str]
    retrieved: str
    table: str
    units: str
    notes: list[str]
    domestic: LhdnDomestic
    rows: list[LhdnRow]


@cache
def table() -> LhdnTable:
    return LhdnTable.model_validate(yaml.safe_load(TREATY_FILE.read_text(encoding="utf-8")))


def row(country: str, day: date | None = None) -> LhdnRow | None:
    """The treaty row for a payee country (ISO code), or None: no agreement in LHDN's table, or (with a day) the
    agreement not yet in effect on that day (treaty_effective_dates.yaml)."""
    if day is not None and not treaty_dates.in_effect(TREATY_DATES_FILE, country, day):
        return None
    return next((r for r in table().rows if LHDN_COUNTRIES[r.country] == country), None)
