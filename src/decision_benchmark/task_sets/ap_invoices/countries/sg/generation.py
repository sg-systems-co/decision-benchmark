"""The Singaporean part of the generator: GST registrations, the clean line and the tax-invoice block.

The clean line: a category with no Regulation 26/27 class and no catalog fact defaults, charged at the GST rate on the
day (SG-3); the buyer claims it (SG-1)."""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from ...generator.country import CannotPlant, CleanLine, ProblemLine
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
    company_kinds: tuple[str, ...] = ()
    certificate_covers: tuple[str, ...] = ()
    plants_rules = False
    """B1-5 adds the Singaporean rule recipes; until then the floor appearances of Singaporean rules are not planted."""

    def postcode(self, r: random.Random) -> str:
        return f"{r.randrange(100_000, 829_999)}"

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        return f"{start.year}{ids.digits(5)}{chr(65 + r.randrange(26))}"

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]:
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def company_facts(self, r: random.Random, kind: str = "") -> dict | None:
        return {"country": "SG", "input_tax_status": "fully_taxable", "non_business_receipts": False}

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None:
        return None

    def special_suppliers(self) -> tuple:
        return ()            # B1-5

    def special_facts(self, kind: str, identity: dict) -> dict:
        return {}

    def link_company(self, company: dict, special: dict[str, dict]) -> None:
        return None

    def clean_line(self, category: Category, day: date, company: dict | None = None, supplier: dict | None = None,
                   kind: str = "") -> CleanLine | None:
        p = category.tax.get("SG")
        if p is not None and (not isinstance(p, SgTaxProfile) or p.disallowed or p.facts):
            return None
        return CleanLine(rate_on(day), {"tax_category": "SR"}, T.CLAIMABLE.value, "SG-1")

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        gst = next(x["number"] for x in supplier["tax_registrations"] if x["scheme"] == "SG_GST")
        return {"country": "SG", "document_title": "Tax Invoice", "supplier_gst_no": gst,
                "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines]}

    def wrong_rate(self, category: Category, day: date, clean: CleanLine) -> ProblemLine | None:
        return ProblemLine(clean.rate + 1, T.GST_WRONGLY_CHARGED.value, "SG-3")    # above every allowed rate

    def make_invalid(self, invoice: dict, rules: list[str] = ()) -> tuple[list[str], tuple[str, str] | None]:
        invoice["supplier_block"]["address"] = None    # an IRAS tax-invoice particular (SG-2)
        return ["INVALID_TAX_INVOICE"], (T.NOT_CLAIMABLE_INVALID_INVOICE.value, "SG-2")

    def exchange_rate(self, currency: str, day: date) -> Decimal:
        return Decimal("1.35")           # an invoice's own stated rate; the rules read it as printed

    def refresh_einvoice(self, invoice: dict) -> None:
        return None

    def plant(self, d, line: int, rule: str, form: str) -> None:
        raise CannotPlant(f"no Singaporean rule recipes yet (B1-5): {rule}")

    def suppliers_for(self, cw, kind: str, needs: set[str], foreign: bool, day: date) -> list[dict] | None:
        return None


generation_part = SingaporeGeneration()
