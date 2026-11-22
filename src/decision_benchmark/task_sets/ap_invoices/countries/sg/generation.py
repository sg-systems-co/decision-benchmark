"""The Singaporean part of the generator: GST registrations, the clean line and the tax-invoice block.

The clean line: a category with no Regulation 26/27 class and no catalog fact defaults, charged at the GST rate on the
day (SG-3); the buyer claims it (SG-1)."""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from ...generator.country import CleanLine
from ...models import Category
from .models import SgTaxProfile, SgTaxTreatment as T
from .rules.gst import rate_on


def _gst_no(r: random.Random, ids) -> str:
    d = ids.digits(8)
    return f"M{d[0]}-{d[1:]}-{chr(65 + r.randrange(26))}"


class SingaporeGeneration:
    country = "SG"
    currency = "SGD"

    foreign_countries = ("MY", "CN", "JP", "US", "GB", "IN")
    """Where foreign suppliers of Singaporean companies are based (treaty partners)."""

    def postcode(self, r: random.Random) -> str:
        return f"{r.randrange(100_000, 829_999)}"

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        return f"{start.year}{ids.digits(5)}{chr(65 + r.randrange(26))}"

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]:
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def company_facts(self, r: random.Random) -> dict | None:
        return {"country": "SG", "input_tax_status": "fully_taxable", "non_business_receipts": False}

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None:
        return None

    def clean_line(self, category: Category, day: date) -> CleanLine | None:
        p = category.tax.get("SG")
        if p is not None and (not isinstance(p, SgTaxProfile) or p.disallowed or p.facts):
            return None
        return CleanLine(rate_on(day), {"tax_category": "SR"}, T.CLAIMABLE.value, "SG-1")

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        gst = next(x["number"] for x in supplier["tax_registrations"] if x["scheme"] == "SG_GST")
        return {"country": "SG", "document_title": "Tax Invoice", "supplier_gst_no": gst,
                "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines]}


generation_part = SingaporeGeneration()
