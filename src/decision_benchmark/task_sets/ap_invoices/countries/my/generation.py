"""The Malaysian part of the generator: registrations, party facts, the clean line and the MyInvois block.

The clean line follows the catalog and the rate tables only (B1 plan section 4: the generator plants, the engine finds
independently): goods take their class on the day, services their First Schedule rate while the item is taxable.
Categories the clean base leaves to the tax families (B1-4): any with catalog fact defaults; education (Group M) and
private healthcare (Group I items 14-16), which have no ordinary value; courier before 26 Feb 2024 (the old 30 kg item
needs the parcel weight); the 26 Feb 2024 additions during the STP 1/2024 window; an item the company provides itself
(the B2B order would decide it); a group-relief item from the group supplier; and what the Government supplier sells in
the 2025 scope (K-5, L-7, P-8). A foreign supplier's clean line is an imported service the buyer accounts for (MS-8),
with its self-billed e-invoice (ME-3). The rule recipes are in planting.py.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timezone
from decimal import Decimal

from ...generator.country import CleanLine, ProblemLine
from ...models import Category
from . import planting
from .constants import (
    CLASSIFICATION_OTHERS, SALES_TAX_ORDERS_2025_FROM, TAX_CLASS_RATE, TAX_TYPE_NOT_APPLICABLE, TAX_TYPE_SALES,
    TAX_TYPE_SERVICE,
)
from .models import MyTaxProfile, MyTaxTreatment as T
from .rules import rates, scope
from .rules.policies import NEW_REGISTRANT_TO

CLASSIFICATION = {"goods": CLASSIFICATION_OTHERS, "service": CLASSIFICATION_OTHERS}
"""MyInvois classification code for every clean line."""
NOT_APPLICABLE = TAX_TYPE_NOT_APPLICABLE
IMPORTED_CLEAN = ("imported_consultancy", "imported_it_services", "foreign_digital_services")
"""The imported services a foreign supplier's clean line carries (no payment nature, so no withholding)."""
GOVERNMENT_SCOPE = ("H", "K", "L", "M")


class MalaysiaGeneration:
    country = "MY"
    currency = "MYR"

    foreign_countries = ("SG", "CN", "JP", "US", "DE", "IN")
    """Where foreign suppliers of Malaysian companies are based (treaty partners)."""
    company_kinds = planting.COMPANY_KINDS
    certificate_covers = ("wooden_pallets", "corrugated_cartons")
    """G-4 plants pallets under the company's Schedule C certificate; MG-4 cartons (taxed at 10% under every order, so
    a problem form exists on every date)."""
    plants_rules = True
    """The rule recipes are in planting.py."""

    def postcode(self, r: random.Random) -> str:
        return f"{r.randrange(10_000, 99_999)}"

    def registration_no(self, r: random.Random, start: date, ids) -> str:
        return f"{start.year}{ids.digits(8)}"

    def company_registrations(self, r: random.Random, start: date, ids) -> list[dict]:
        sst = ids.digits(12)
        number = f"W10-{sst[:4]}-{sst[4:]}"
        return [
            {"scheme": "MY_TIN", "number": f"C{ids.digits(10)}", "type": "tin"},
            {"scheme": "MY_SST", "number": number, "type": "sales", "valid_from": str(date(2018, 9, 1))},
            {"scheme": "MY_SST", "number": number, "type": "service", "valid_from": str(date(2018, 9, 1))},
        ]

    def company_facts(self, r: random.Random, kind: str = "") -> dict | None:
        return planting.company_facts(kind)

    def special_suppliers(self):
        return planting.SPECIAL_SUPPLIERS

    def special_facts(self, kind: str, identity: dict) -> dict:
        return planting.special_facts(kind, identity)

    def link_company(self, company: dict, special: dict[str, dict]) -> None:
        planting.link_company(company, special)

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date, ids) -> list[dict]:
        regs = [{"scheme": "MY_TIN", "number": f"C{ids.digits(10)}", "type": "tin"}]
        sst = ids.digits(12)
        number = f"W10-{sst[:4]}-{sst[4:]}"
        for kind, sst in (("goods", "sales"), ("service", "service")):
            if kind in kinds:
                regs.append({"scheme": "MY_SST", "number": number, "type": sst, "valid_from": str(start)})
        return regs

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None:
        band = r.choice(["above_100m", "25m_to_100m", "5m_to_25m"])
        return {"country": "MY", "is_manufacturer": "goods" in kinds, "registered_before_2024_02_26": True,
                "einvoice": {"turnover_band": band, "turnover_basis": "fy2022_audited"}}

    def clean_line(self, category: Category, day: date, company: dict | None = None, supplier: dict | None = None,
                   kind: str = "") -> CleanLine | None:
        p = category.tax.get("MY")
        if not isinstance(p, MyTaxProfile) or p.facts:
            return None
        provided = set(((company or {}).get("tax_facts") or {}).get("services_provided", []))
        if p.service_item is not None and p.service_item in provided:
            return None
        if supplier is not None and supplier["country"] != self.country:
            return self._imported(category, day)
        if kind == "group" and p.group_relief:
            return None
        if kind == "government" and p.service_item and (
                p.service_item[0] in GOVERNMENT_SCOPE or p.service_item in scope.HEALTHCARE_ITEMS):
            return None
        line = self._domestic(category, p, day)
        if line is not None and line.rate > 0 and supplier is not None and not planting.registered(
                supplier, "sales" if category.kind == "goods" else "service", day):
            return None
        return line

    def _imported(self, category: Category, day: date) -> CleanLine | None:
        """An imported service: the overseas invoice shows no SST, the registered buyer accounts for it (MS-8), and
        self-bills the e-invoice once in its phase (ME-3)."""
        if category.category not in IMPORTED_CLEAN:
            return None
        actions = (planting.IMPORTED_ACTION,) + ((planting.SELF_BILLED_ACTION,) if day >= planting.COMPANY_PHASE_START else ())
        return CleanLine(Decimal(0), {"classification_code": CLASSIFICATION["service"], "tax_type": NOT_APPLICABLE},
                         T.SST_BUYER_ACCOUNTS.value, "MS-8", actions)

    def _domestic(self, category: Category, p: MyTaxProfile, day: date) -> CleanLine | None:
        if category.kind == "goods":
            cls = p.tax_class
            if day < SALES_TAX_ORDERS_2025_FROM:
                earlier = [e for e in p.earlier_classes if e.valid_from <= day <= e.valid_to]
                if not earlier:
                    return None
                cls = earlier[0].tax_class
            if cls == "sales_exempt":
                # Exempt under the 2025 orders: MG-2; exempt only under the earlier orders: MG-3.
                basis = "MG-2" if p.tax_class == "sales_exempt" else "MG-3"
                return CleanLine(Decimal(0), {"classification_code": CLASSIFICATION["goods"], "tax_type": NOT_APPLICABLE},
                                 T.NO_SST.value, basis)
            return CleanLine(TAX_CLASS_RATE[cls], {"classification_code": CLASSIFICATION["goods"], "tax_type": TAX_TYPE_SALES},
                             T.SST_CORRECT.value, "MG-2")
        item = p.service_item
        if item is None:
            return CleanLine(Decimal(0), {"classification_code": CLASSIFICATION["service"], "tax_type": NOT_APPLICABLE},
                             T.NO_SST.value, "MS-1")
        if item[0] == "M" or item in scope.HEALTHCARE_ITEMS:
            return None     # education and private healthcare: no ordinary value, MS-4 needs the provider or patient facts
        start = scope.taxable_from(item)
        if item == scope.COURIER_ITEM and day < scope.SCOPE_2024_FROM:
            return None
        if start == scope.SCOPE_2024_FROM and start <= day <= NEW_REGISTRANT_TO:
            return None
        if not scope.in_schedule(item, day):
            return CleanLine(Decimal(0), {"classification_code": CLASSIFICATION["service"], "tax_type": NOT_APPLICABLE},
                             T.NO_SST.value, "MS-1")
        return CleanLine(rates.standard_rate(item, day),
                         {"classification_code": CLASSIFICATION["service"], "tax_type": TAX_TYPE_SERVICE},
                         T.SST_CORRECT.value, "MS-2")

    def einvoice(self, company: dict, supplier: dict, lines: list[dict], day: date, number: str) -> dict:
        if supplier["country"] != self.country:
            # An overseas supplier issues no MyInvois e-invoice; the buyer self-bills (ME-3).
            return {"country": "MY", "is_einvoice": False,
                    "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines]}

        def reg(party, scheme, kinds=None):
            return next((x["number"] for x in party["tax_registrations"]
                         if x["scheme"] == scheme and (kinds is None or x["type"] in kinds)), None)

        by_type: dict[str, Decimal] = {}
        for line in lines:
            tax = Decimal(line["tax_amount"])
            if tax > 0:
                by_type[line["ext"]["tax_type"]] = by_type.get(line["ext"]["tax_type"], Decimal(0)) + tax
        stamp = datetime.combine(day, time(9, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "country": "MY", "is_einvoice": True, "einvoice_version": "1.1", "einvoice_type_code": "01",
            "uuid": f"{number}-MYINVOIS", "validation_datetime": stamp,
            "supplier_tin": reg(supplier, "MY_TIN"), "supplier_brn": supplier["registration_no"],
            "supplier_sst_no": reg(supplier, "MY_SST"),
            "buyer_tin": reg(company, "MY_TIN"), "buyer_brn": company["registration_no"],
            "buyer_sst_no": reg(company, "MY_SST", ("service",)),
            "tax_total_by_type": {k: f"{v:.2f}" for k, v in by_type.items()} or {NOT_APPLICABLE: "0.00"},
            "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines],
        }

    def wrong_rate(self, category: Category, day: date, clean: CleanLine) -> ProblemLine | None:
        if clean.rate == 0:
            return None
        other = {Decimal(8): Decimal(6), Decimal(6): Decimal(8), Decimal(10): Decimal(5), Decimal(5): Decimal(10)}
        return ProblemLine(other[clean.rate], T.SST_WRONG_RATE.value, clean.basis)

    def make_invalid(self, invoice: dict, rules: list[str] = ()) -> tuple[list[str], tuple[str, str] | None]:
        if set(rules) & {"ME-1", "ME-2", "ME-4"}:
            return [], None                             # the rule's recipe plants the invalidity itself
        invoice["einvoice"]["buyer_tin"] = None        # a MyInvois mandatory field (ME-2)
        return ["MISSING_MANDATORY_FIELD"], None

    def plant(self, d, line: int, rule: str, form: str) -> None:
        planting.plant(d, line, rule, form)

    def suppliers_for(self, cw, kind: str, needs: set[str], foreign: bool, day: date) -> list[dict] | None:
        if kind:
            return [cw.supplier(cw.special[kind])]
        if foreign:
            pe = cw.special.get("foreign_pe")
            return [s for s in cw.suppliers if s["country"] != self.country and s["supplier_id"] != pe]
        if not needs:
            return None
        return [s for s in cw.ordinary_suppliers() if planting.supplier_fits(s, needs, day)]

    def exchange_rate(self, currency: str, day: date) -> Decimal:
        return Decimal("4.40")           # an invoice's own stated rate; the rules read it as printed

    def refresh_einvoice(self, invoice: dict) -> None:
        by_type: dict[str, Decimal] = {}
        ext = {x["line_no"]: x for x in invoice["einvoice"]["lines"]}
        for line in invoice["lines"]:
            tax = Decimal(line["tax_amount"])
            if tax > 0:
                kind = ext[line["line_no"]]["tax_type"]
                by_type[kind] = by_type.get(kind, Decimal(0)) + tax
        invoice["einvoice"]["tax_total_by_type"] = {k: f"{v:.2f}" for k, v in by_type.items()} or {NOT_APPLICABLE: "0.00"}


generation_part = MalaysiaGeneration()
