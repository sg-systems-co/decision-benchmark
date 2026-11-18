"""Is the line a taxable service at all (MS-1 (a)), and does an item exclusion apply (MS-4)?

Sources: Service Tax Regulations 2018 First Schedule with its amendments to 2025; Service Tax
(Persons Exempted from Payment of Tax) Order 2018 items 7 and 10 (patients, disabled students);
rule sheet v0.10 MS-1, MS-4. Each exclusion is a line fact; not recorded means the ordinary case
(the exclusion doesn't apply), recorded null means HAND_OVER with basis MS-4.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....findings import NotSettled
from ....models.common import ZERO
from .context import Exempt, LineCtx, Partial

NEW_SCOPE_FROM = date(2025, 7, 1)
"""Groups H (finance), K (rental), L (construction), M (education) and private healthcare (I14-16) are
taxable services from 1 Jul 2025 (2025 amendments; P-8 names the same new scope)."""
NEW_SCOPE_GROUPS = ("H", "K", "L", "M")
NEW_SCOPE_ITEMS = ("I14", "I15", "I16")
HEALTHCARE_ITEMS = NEW_SCOPE_ITEMS
EXCLUDED_CARRIAGE = ("outside_to_outside", "last_exit_to_outside", "outside_to_first_entry", "transshipment",
                     "to_licensed_warehouse")
"""Group J item 1 exclusions: carriage outside Malaysia, to/from the last exit or first entry point, transshipment,
goods landed for a licensed warehouse until re-export."""
EXCLUDED_AIR_ROUTES = ("international", "rural_air_service", "within_sabah", "within_sarawak")
"""Group I item 10 exclusions: international legs, Rural Air Services routes, routes within Sabah or within Sarawak."""
EXCLUDED_CLEANING = ("religious", "educational", "residential", "agricultural")
EXCLUDED_FINANCIAL = ("interest_or_profit", "penalty", "basic_banking")
"""Group H items 3-4 exclusions: interest and profit-based returns, penalty charges, basic banking."""
EXCLUDED_INSURANCE = ("international_transport", "export_credit", "risk_outside_malaysia",
                      "educational_or_religious_insured")
SCHOOL_FEE_LIMIT = Decimal("60000")
"""Group M: private school fees are taxable above RM60,000 per student per year."""
EXCLUDED_MANAGEMENT = ("strata_management_to_owners", "cmsa_fund_management", "religious_welfare_body")
"""Group G (i) exclusions: strata management to owners, CMSA fund management, religious/welfare/health/public-transport
bodies. Health-examination management is P-15 (policies.py)."""
EXCLUDED_SUPPLIER_KINDS = ("approved_rnd_company", "research_institute")
"""Group G (g): approved R&D companies, contract R&D companies and research institutes are excluded as persons."""


def in_schedule(item: str | None, day: date) -> bool:
    """MS-1 (a): the item is a taxable service in the First Schedule on the day."""
    if item is None:
        return False
    if item[0] in NEW_SCOPE_GROUPS or item in NEW_SCOPE_ITEMS:
        return day >= NEW_SCOPE_FROM
    return True


def _outside(ctx: LineCtx) -> bool:
    return bool(ctx.fact("subject_outside_malaysia", False, "MS-4"))


def exclusion(ctx: LineCtx) -> Exempt | Partial | None:
    """The MS-4 exclusion for the line's item, if one applies."""
    item, group = ctx.item, ctx.group
    assert item is not None
    out = Exempt("MS-4")
    if group == "G":
        letter = item[2] if item.startswith("G(") else ""
        if letter in ("a", "b", "c", "d", "e", "f"):
            if _outside(ctx):
                return out
            fee = ctx.fact("statutory_fee_amount", ZERO, "MS-4")
            if fee > ZERO:
                # The part paid as a statutory fee to the Government or a statutory body is excluded.
                return Partial("MS-4", ctx.net - fee)
        elif letter == "g":
            if ctx.sf.supplier_kind in EXCLUDED_SUPPLIER_KINDS or _outside(ctx):
                return out
            if ctx.fact("oku_holder", False, "MS-4"):
                return out
        elif letter == "i":
            if _outside(ctx) or ctx.fact("excluded_management_kind", "none", "MS-4") in EXCLUDED_MANAGEMENT:
                return out
        elif letter == "j":
            if ctx.fact("staff_secondment", False, "MS-4") or _outside(ctx):
                return out
        elif letter == "k":
            if _outside(ctx):
                return out
        elif letter == "n":
            if ctx.fact("residential", False, "MS-4"):
                return out
    elif group == "H":
        if ctx.fact("financial_charge", None, "MS-4") in EXCLUDED_FINANCIAL:
            return out
        if ctx.fact("insurance_cover", "other", "MS-4") in EXCLUDED_INSURANCE:
            return out
        if _outside(ctx) or ctx.fact("export_related", False, "MS-4"):
            return out
    elif item == "I8":
        if _outside(ctx):
            return out
    elif item == "I10":
        if ctx.fact("air_route", "within_peninsula", "MS-4") in EXCLUDED_AIR_ROUTES:
            return out
    elif item == "I13":
        if ctx.fact("premises_use", "commercial", "MS-4") in EXCLUDED_CLEANING:
            return out
    elif item in HEALTHCARE_ITEMS:
        if patient_is_citizen(ctx):
            return out
    elif group == "J":
        if ctx.fact("carriage", "domestic", "MS-4") in EXCLUDED_CARRIAGE:
            return out
    elif group == "K":
        if ctx.fact("asset_type", "other", "MS-4") in ("housing", "reading_material"):
            return out
        if ctx.fact("financial_lease", False, "MS-4"):
            return out
    elif group == "L":
        # The Regulations exclude residential buildings (not an approved mixed development, L-2); work on a completed
        # residential building is L-5 (construction.py).
        if (ctx.fact("residential", False, "MS-4") and ctx.fact("residential_share", None, "L-2") is None
                and not ctx.fact("completed_building", False, "L-5")):
            return out
    elif group == "M":
        return _education(ctx)
    return None


def patient_is_citizen(ctx: LineCtx) -> bool:
    """Private healthcare: the patient's citizenship decides (Order item 7). No ordinary value: HAND_OVER if not shown."""
    category = ctx.fact("patient_category", None, "MS-4")
    if category is not None:
        return category == "citizen"
    return bool(ctx.need("patient_citizen", "MS-4"))


def _student_category(ctx: LineCtx) -> str:
    category = ctx.fact("student_category", None, "MS-4")
    if category is None:
        citizen = ctx.fact("student_citizen", None, "MS-4")
        if citizen is None:
            raise NotSettled("MS-4", "student category not shown")
        category = "citizen" if citizen else "non_citizen"
    return category


def _education(ctx: LineCtx) -> Exempt | None:
    """Group M by provider kind (no ordinary value: not shown -> HAND_OVER). Private schools: fees above RM60,000 per
    student per year; higher education and language centres: non-citizen students. Disabled citizens are exempt
    (Order item 10)."""
    kind = ctx.need("education_provider_kind", "MS-4")
    if kind == "private_school":
        if ctx.fact("student_category", None, "MS-4") == "disabled_citizen":
            return Exempt("MS-4")
        return Exempt("MS-4") if ctx.need("annual_fee_per_student", "MS-4") <= SCHOOL_FEE_LIMIT else None
    return Exempt("MS-4") if _student_category(ctx) in ("citizen", "disabled_citizen") else None
