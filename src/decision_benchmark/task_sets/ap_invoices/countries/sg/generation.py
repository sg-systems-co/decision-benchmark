"""The Singaporean part of the generator: GST registrations, the clean line and the tax-invoice block.

The clean line: a category with no Regulation 26/27 class and no catalog fact defaults, charged at the GST rate on the
day; the buyer claims it (SG-1). From a supplier not registered for GST: no GST (SG-4). From a foreign supplier: an
imported service without GST, reverse-charged by a buyer not entitled to full credit (SG-8). The rule recipes are in
planting.py."""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path
from decimal import Decimal

from ...generator.country import CannotPlant, CleanLine, ProblemLine
from ...generator.entities import stated_rate
from ...models import Category
from . import planting
from .models import SgTaxProfile, SgTaxTreatment as T
from .rules.gst import rate_on

SG_IMPORTED_CLEAN = ("business_consultancy", "it_services", "advertising", "legal_services", "engineering_consultancy")
"""Services a foreign supplier's clean line may carry (no payment nature, so no withholding)."""


def _gst_no(r: random.Random, ids) -> str:
    d = ids.digits(8)
    return f"M{d[0]}-{d[1:]}-{chr(65 + r.randrange(26))}"


class SingaporeGeneration:
    country = "SG"
    currency = "SGD"

    foreign_countries = ("MY", "CN", "JP", "US", "GB", "IN")
    """Where foreign suppliers of Singaporean companies are based (treaty partners)."""
    foreign_currencies = {"MY": "MYR", "CN": "CNY", "JP": "JPY", "US": "USD", "GB": "GBP", "IN": "INR"}
    RATES = {"MYR": (Decimal("0.30"), 4), "CNY": (Decimal("0.185"), 4), "JPY": (Decimal("0.0088"), 6),
             "USD": (Decimal("1.32"), 4), "GBP": (Decimal("1.70"), 4), "INR": (Decimal("0.0157"), 6)}
    company_kinds = planting.SG_COMPANY_KINDS
    certificate_covers: tuple[str, ...] = ()
    certificate_excludes: tuple[str, ...] = ()
    plants_rules = True
    """The rule recipes are in planting.py."""
    reusable_bases = ("SG-8",)
    """A withholding rule may take a line planted for an imported service (it keeps that line's basis)."""

    # Branch coverage (generator/branches.py): the engine's files, its outcome helpers, the functions whose returns are
    # a rule's deciding paths, and the deciding facts it reads on a shared line of code.
    engine_files = (*sorted((Path(__file__).parent / "rules").glob("*.py")), Path(__file__).parent / "validity.py")
    branch_calls = ("wrongly_charged", "undercharged")
    branch_hand_overs = ("_not_settled",)
    branch_functions = {"rules._not_entitled": "SG-4", "reverse_charge.full_credit": "SG-8"}
    branch_facts = planting.SG_BRANCH_FACTS
    branch_case_facts = planting.SG_CASE_FACTS

    def postcode(self, r: random.Random) -> str:
        return f"{r.randrange(100_000, 829_999)}"

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        return f"{start.year}{ids.digits(5)}{chr(65 + r.randrange(26))}"

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]:
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def company_facts(self, r: random.Random, kind: str = "") -> dict | None:
        return planting.company_facts(kind or "plain")

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        if not kinds:
            return []                    # not registered for GST (SG-4)
        return [{"scheme": "SG_GST", "number": _gst_no(r, ids), "type": "local", "valid_from": str(start)}]

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None:
        return None

    def special_suppliers(self) -> tuple:
        return planting.SG_SPECIAL_SUPPLIERS

    def special_facts(self, kind: str, identity: dict) -> dict:
        return {}

    def link_company(self, company: dict, special: dict[str, dict]) -> None:
        return None

    def clean_line(self, category: Category, day: date, company: dict | None = None, supplier: dict | None = None,
                   kind: str = "") -> CleanLine | None:
        p = category.tax.get("SG")
        if p is not None and (not isinstance(p, SgTaxProfile) or p.disallowed or p.facts):
            return None
        if supplier is not None and supplier["country"] != self.country:
            if category.category not in SG_IMPORTED_CLEAN:
                return None
            if company is None or planting.full_credit(company):
                return CleanLine(Decimal(0), {"tax_category": "NA"}, T.NO_GST.value, "SG-8")
            return CleanLine(Decimal(0), {"tax_category": "NA"}, T.REVERSE_CHARGE.value, "SG-8",
                             (planting.REVERSE_ACTION,))
        if supplier is not None and not planting.registered(supplier, day):
            return CleanLine(Decimal(0), {"tax_category": "NA"}, T.NO_GST.value, "SG-4")
        return CleanLine(rate_on(day), {"tax_category": "SR"}, T.CLAIMABLE.value, "SG-1")

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        gst = next((x["number"] for x in supplier.get("tax_registrations", []) if x["scheme"] == "SG_GST"), None)
        return {"country": "SG", "document_title": "Tax Invoice", "supplier_gst_no": gst,
                "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines]}

    def wrong_rate(self, category: Category, day: date, clean: CleanLine) -> ProblemLine | None:
        return ProblemLine(clean.rate + 1, T.GST_WRONGLY_CHARGED.value, "SG-3")    # above every allowed rate

    def make_invalid(self, invoice: dict, rules: list[str] = (), d=None) -> tuple[list[str], tuple[str, str] | None]:
        planting.drop_particular(invoice, d)           # an IRAS tax-invoice particular (SG-2), in turn
        return ["INVALID_TAX_INVOICE"], (T.NOT_CLAIMABLE_INVALID_INVOICE.value, "SG-2")

    def exchange_rate(self, currency: str, day: date) -> Decimal:
        base, places = self.RATES[currency]
        return stated_rate(base, currency, day, places)       # an invoice's own stated rate; read as printed

    def refresh_einvoice(self, invoice: dict) -> None:
        return None

    def plant(self, d, line: int, rule: str, form: str) -> None:
        planting.plant(d, line, rule, form)

    def plant_branch(self, d, line: int, branch: str, side: str) -> None:
        fn = planting.SG_BRANCHES.get(branch)
        if fn is None:
            raise CannotPlant(f"no branch recipe {branch}")
        fn(d, line, side)

    def plant_handover(self, d, line: int, kind: str) -> None:
        if kind != "unconfirmed_treaty":
            raise CannotPlant(f"no hand-over recipe {kind}")
        planting.unconfirmed_treaty(d, line)

    def plant_split(self, d, line: int) -> None:
        raise CannotPlant("no Singapore split cases (the §5-b splits are Malaysian)")

    def finish_case(self, d) -> None:
        planting.finish(d)

    def mix_line(self, d, line: int) -> None:
        planting.mix_line(d, line)

    def suppliers_for(self, cw, kind: str, needs: set[str], foreign: bool, day: date,
                      turns=None) -> list[dict] | None:
        if kind:
            return [cw.supplier(sid) for sid in cw.special[kind]]
        if foreign:
            sids = cw.special.get("sg_foreign", []) + cw.special.get("sg_foreign_my", [])
            return [cw.supplier(sid) for sid in sids]
        if "not_entitled" in needs and "shared" not in needs:
            # SG-4's problem form: the kinds of supplier not entitled to charge GST, in turn.
            which = turns.take("SG-4 supplier", list(planting.SG4_SUPPLIERS)) if turns is not None else "not_registered"
            if which == "ovr":
                return [cw.supplier(sid) for sid in cw.special.get("sg_ovr", [])]
            if which == "number_mismatch":
                return [s for s in cw.ordinary_suppliers() if planting.registered(s, day)]
        if "no_gst" in needs or "not_entitled" in needs:
            return [cw.supplier(sid) for sid in cw.special.get("sg_unregistered", [])]
        ordinary = [s for s in cw.ordinary_suppliers() if planting.registered(s, day)]
        return [s for s in ordinary if planting.supplier_fits(s, needs, day)]


generation_part = SingaporeGeneration()
