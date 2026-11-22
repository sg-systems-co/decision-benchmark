"""Singapore treaty withholding rates: a typed loader for data/dta_withholding_rates.yaml (read by script from the
IRAS treaty texts; see the file's header). A rate counts as confirmed only where the article states a single rate
and no protocol amends it (status "single rate in the article"); every other row needs a person's reading, so a
case that needs it is HAND_OVER (rule sheet §4A). The file is loaded as it stands; no rate is edited here."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import yaml
from pydantic import field_validator

from ...models import treaty_dates
from ...models.common import Model

SG_TREATY_FILE = Path(__file__).resolve().parent / "data" / "dta_withholding_rates.yaml"
SG_TREATY_DATES_FILE = Path(__file__).resolve().parent / "data" / "treaty_effective_dates.yaml"
"""Treaty rows that take effect on or after 1 Jan 2023: before the date, the domestic rate (engine 0.10.3)."""
CONFIRMED_STATUS = "single rate in the article"
IRAS_COUNTRIES = {
    "Albania": "AL", "Armenia": "AM", "Australia": "AU", "Austria": "AT", "Bahrain": "BH", "Bangladesh": "BD",
    "Barbados": "BB", "Belarus": "BY", "Belgium": "BE", "Bhutan": "BT", "Brazil": "BR", "Brunei": "BN",
    "Bulgaria": "BG", "Cabo Verde": "CV", "Cambodia": "KH", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Cyprus": "CY", "Czech Republic": "CZ", "Denmark": "DK", "Ecuador": "EC", "Egypt": "EG", "Estonia": "EE",
    "Ethiopia": "ET", "Fiji": "FJ", "Finland": "FI", "France": "FR", "Gabon": "GA", "Georgia": "GE", "Germany": "DE",
    "Ghana": "GH", "Greece": "GR", "Guernsey": "GG", "Hong Kong": "HK", "Hungary": "HU", "India": "IN",
    "Indonesia": "ID", "Ireland": "IE", "Isle of Man": "IM", "Israel": "IL", "Italy": "IT", "Japan": "JP",
    "Jersey": "JE", "Jordan": "JO", "Kazakhstan": "KZ", "Kenya": "KE", "Korea, Republic of": "KR", "Kuwait": "KW",
    "Kyrgyzstan": "KG", "Laos": "LA", "Latvia": "LV", "Libya": "LY", "Liechtenstein": "LI", "Lithuania": "LT",
    "Luxembourg": "LU", "Malaysia": "MY", "Malta": "MT", "Mauritius": "MU", "Mexico": "MX", "Mongolia": "MN",
    "Morocco": "MA", "Myanmar": "MM", "Netherlands": "NL", "New Zealand": "NZ", "Nigeria": "NG", "Norway": "NO",
    "Oman": "OM", "Pakistan": "PK", "Panama": "PA", "Papua New Guinea": "PG", "Philippines": "PH", "Poland": "PL",
    "Portugal": "PT", "Qatar": "QA", "Romania": "RO", "Russian Federation": "RU", "Rwanda": "RW",
    "San Marino": "SM", "Saudi Arabia": "SA", "Serbia": "RS", "Seychelles": "SC", "Slovak Republic": "SK",
    "Slovenia": "SI", "South Africa": "ZA", "Spain": "ES", "Sri Lanka": "LK", "Sweden": "SE", "Switzerland": "CH",
    "Taiwan": "TW", "Tanzania": "TZ", "Thailand": "TH", "Tunisia": "TN", "Turkmenistan": "TM", "Türkiye": "TR",
    "Ukraine": "UA", "United Arab Emirates": "AE", "United Kingdom": "GB", "United States of America": "US",
    "Uruguay": "UY", "Uzbekistan": "UZ", "Vietnam": "VN",
}
"""IRAS country names (whitespace normalised) -> ISO 3166-1 alpha-2 (a test checks every row maps)."""


class TreatyArticle(Model):
    rate: Decimal | None = None
    article: str | None = None
    rates_found: list[str] = []
    quote: str | None = None
    status: str

    @property
    def confirmed(self) -> bool:
        return self.status == CONFIRMED_STATUS and self.rate is not None


class TreatyRow(Model):
    country: str
    agreement: str
    interest: TreatyArticle
    royalties: TreatyArticle
    technical_fees: TreatyArticle
    source: str

    @field_validator("country", mode="before")
    @classmethod
    def _one_line(cls, value: str) -> str:
        return " ".join(str(value).split())


class TreatyTable(Model):
    source: list[str]
    retrieved: str
    table: str
    method: str
    units: str
    rows: list[TreatyRow]


@cache
def sg_table() -> TreatyTable:
    return TreatyTable.model_validate(yaml.safe_load(SG_TREATY_FILE.read_text(encoding="utf-8")))


def treaty(country: str, day: date | None = None) -> TreatyRow | None:
    """The treaty row for a payee country (ISO code): the comprehensive DTA where there is also a limited one. None:
    no treaty, or (with a day) the treaty not yet in effect on that day (treaty_effective_dates.yaml)."""
    if day is not None and not treaty_dates.in_effect(SG_TREATY_DATES_FILE, country, day):
        return None
    rows = [r for r in sg_table().rows if IRAS_COUNTRIES[r.country] == country]
    rows.sort(key=lambda r: r.agreement != "DTA")
    return rows[0] if rows else None
