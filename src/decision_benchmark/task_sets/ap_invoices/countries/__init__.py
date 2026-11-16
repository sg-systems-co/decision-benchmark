"""Country packs and their registry. Adding a country: add a pack folder and one entry in PACKS."""

from __future__ import annotations

from enum import StrEnum

from .base import CountryPack, LineFact
from .my import PACK as MY_PACK
from .sg import PACK as SG_PACK

PACKS: dict[str, CountryPack] = {p.country: p for p in (MY_PACK, SG_PACK)}


def pack(country: str) -> CountryPack:
    try:
        return PACKS[country]
    except KeyError:
        raise ValueError(f"no country pack for {country!r} (have {sorted(PACKS)})") from None


def scheme_types(scheme: str) -> tuple[str, ...]:
    for p in PACKS.values():
        if scheme in p.registration_types:
            return p.registration_types[scheme]
    raise ValueError(f"unknown tax registration scheme {scheme!r}")


def all_tax_codes() -> frozenset[str]:
    return frozenset(str(code) for p in PACKS.values() for code in p.tax_codes)


TaxTreatment = StrEnum("TaxTreatment", {str(c): str(c) for p in PACKS.values() for c in p.tax_codes})
"""Every pack's tax-treatment codes, in registry order (the output schema's enum)."""

__all__ = ["PACKS", "CountryPack", "LineFact", "TaxTreatment", "all_tax_codes", "pack", "scheme_types"]
