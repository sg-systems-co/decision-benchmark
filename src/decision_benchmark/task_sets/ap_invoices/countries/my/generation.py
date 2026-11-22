"""The Malaysian part of the generator: registrations, party facts, the clean line and the MyInvois block.

The clean line follows the catalog and the rate tables only (B1 plan section 4: the generator plants, the engine finds
independently): goods take their class on the day, services their First Schedule rate while the item is taxable.
Categories the clean base leaves to the tax families (B1-4): any with catalog fact defaults; education (Group M) and
private healthcare (Group I items 14-16), which have no ordinary value; courier before 26 Feb 2024 (the old 30 kg item
needs the parcel weight); and the 26 Feb 2024 additions during the STP 1/2024 window.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timezone
from decimal import Decimal

from ...generator.country import CleanLine
from ...models import Category
from .constants import SALES_TAX_ORDERS_2025_FROM, TAX_CLASS_RATE, TAX_TYPE_SALES, TAX_TYPE_SERVICE
from .models import MyTaxProfile, MyTaxTreatment as T
from .rules import rates, scope
from .rules.policies import NEW_REGISTRANT_TO

NOT_APPLICABLE = "06"
"""MyInvois tax type for a line with no tax."""
CLASSIFICATION = {"goods": "022", "service": "022"}
"""MyInvois classification code ("others") for every clean line."""


def _digits(r: random.Random, n: int) -> str:
    return "".join(str(r.randrange(10)) for _ in range(n))


class MalaysiaGeneration:
    country = "MY"
    currency = "MYR"

    foreign_countries = ("SG", "CN", "JP", "US", "DE", "IN")
    """Where foreign suppliers of Malaysian companies are based (treaty partners)."""

    def postcode(self, r: random.Random) -> str:
        return f"{r.randrange(10_000, 99_999)}"

    def registration_no(self, r: random.Random, start: date) -> str:
        return f"{start.year}{r.randrange(10**8):08d}"

    def company_registrations(self, r: random.Random, start: date) -> list[dict]:
        return [
            {"scheme": "MY_TIN", "number": f"C{_digits(r, 10)}", "type": "tin"},
            {"scheme": "MY_SST", "number": f"W10-{_digits(r, 4)}-{_digits(r, 8)}", "type": "sales",
             "valid_from": str(date(2018, 9, 1))},
        ]

    def company_facts(self, r: random.Random) -> dict | None:
        return {"country": "MY", "is_registered_manufacturer": True, "services_provided": []}

    def supplier_registrations(self, r: random.Random, kinds: set[str], start: date) -> list[dict]:
        regs = [{"scheme": "MY_TIN", "number": f"C{_digits(r, 10)}", "type": "tin"}]
        number = f"W10-{_digits(r, 4)}-{_digits(r, 8)}"
        for kind, sst in (("goods", "sales"), ("service", "service")):
            if kind in kinds:
                regs.append({"scheme": "MY_SST", "number": number, "type": sst, "valid_from": str(start)})
        return regs

    def supplier_facts(self, r: random.Random, kinds: set[str]) -> dict | None:
        band = r.choice(["above_100m", "25m_to_100m", "5m_to_25m"])
        return {"country": "MY", "is_manufacturer": "goods" in kinds, "registered_before_2024_02_26": True,
                "einvoice": {"turnover_band": band, "turnover_basis": "fy2022_audited"}}

    def clean_line(self, category: Category, day: date) -> CleanLine | None:
        p = category.tax.get("MY")
        if not isinstance(p, MyTaxProfile) or p.facts:
            return None
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
            "tax_total_by_type": {k: f"{v:.2f}" for k, v in by_type.items()} or {NOT_APPLICABLE: "0.00"},
            "lines": [{"line_no": line["line_no"], **line["ext"]} for line in lines],
        }


generation_part = MalaysiaGeneration()
