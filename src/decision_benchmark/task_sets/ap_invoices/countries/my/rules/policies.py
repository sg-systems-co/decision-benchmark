"""Ministerial exemptions still in force (MS-10): P-1 to P-20 (rule sheet v0.10 MS-10).

Service Tax Policies under Service Tax Act s34(3)(a) and s34(4), latest version of each read 17 Nov 2026.
Each is a line rule: when its facts hold, no service tax is due (Exempt). A few say a line stays taxable
(Taxable): the correct line then names that rule as its basis. P-21 is not an engine rule (not a company
purchase).
"""

from __future__ import annotations

from datetime import date

from ....findings import NotSettled
from .context import Exempt, LineCtx, Taxable
from .scope import COURIER_ITEM, HEALTHCARE_ITEMS, NEW_SCOPE_FROM, OLD_COURIER_LIMIT_KG, SCOPE_2024_FROM, taxable_from

EXISTING_REGISTRANT_TO = date(2024, 2, 29)
NEW_REGISTRANT_TO = date(2024, 3, 31)
"""STP 1/2024 paras 5.1(iii) and 5.2: on the services added on 26 Feb 2024, a supplier already registered before
26 Feb 2024 neither charges nor collects tax for 26-29 Feb 2024; a supplier newly liable to register, for
26 Feb-31 Mar 2024 (rule sheet P-20, expired dated exemptions; "26 Feb 2024 additions")."""


def transitional_2024(ctx: LineCtx) -> Exempt | None:
    """STP 1/2024: the transitional exemption on the services added on 26 Feb 2024 (by invoice date)."""
    if ctx.foreign_supplier or not SCOPE_2024_FROM <= ctx.day <= NEW_REGISTRANT_TO:
        return None
    if taxable_from(ctx.item) != SCOPE_2024_FROM:
        return None
    if ctx.item == COURIER_ITEM and ctx.need("parcel_weight_kg", "MS-1") <= OLD_COURIER_LIMIT_KG:
        return None                     # courier up to 30 kg was already taxable (old Group I item 6)
    if ctx.day <= EXISTING_REGISTRANT_TO:
        return Exempt("P-20")
    before = ctx.sf.registered_before_2024_02_26
    if before is None:
        raise NotSettled("P-20", "STP 1/2024: whether the supplier was registered before 26 Feb 2024 is not shown")
    return None if before else Exempt("P-20")


FINANCIAL_USES_P1 = ("taxable_financial_services", "offshore_financial_services", "export_related_financial_services")
TIA_I_FROM = date(2026, 6, 1)
"""P-7: TIA-i account fees exempt from 1 Jun 2026."""
MRO_TO = date(2027, 12, 31)
MRO_FOREIGN_BUYER_FROM = date(2025, 9, 1)
MRO_MIDA_FROM = date(2024, 3, 1)
MRO_DGTA_FROM = date(2026, 9, 22)
MRO_BUYERS = ("aoc_airline", "registered_ship_owner", "government_department")
NON_RESIDENTIAL_CHARGES_FROM = date(2026, 7, 1)
"""P-10: maintenance charges and sinking fund for non-residential buildings by a developer, JMB or MC, from 1 Jul 2026."""
SCREENING_CATEGORIES = ("foreign_worker_screening", "diplomat_with_mofa_letter", "newborn_with_citizen_parent")
"""P-13 (STP 5/2025 items 3-5)."""
EDUCATION_ITEMS_EXEMPT = ("books", "uniform", "food", "transport", "accommodation", "refundable_deposit", "pta_fee",
                          "trip", "student_pass")
"""P-16 (STP 4/2025 (Amdt 2)): education fee items other than tuition."""
NOT_DIGITAL = ("online_distance_learning", "e_newspaper_journal_periodical")
"""P-19 (STP 4/2020, 5/2020): not taxable digital services."""
DIGITAL_ITEMS = ("G(l)", "I2")
EXEMPT_CARRIAGE = ("door_to_door_international", "ocean_peninsula_east_malaysia")
"""P-18 (STP 4/2024 and Amdt 1)."""
LABUAN_IMPORTED_TO = date(2021, 12, 31)
HEALTH_EXAM_TAXABLE_FROM = date(2026, 5, 1)
"""P-15 (STP 1/2026): health-examination management services are taxable as management services from 1 May 2026."""
BANK_DIGITAL_TO = date(2025, 7, 31)
"""P-20: banking digital services exempt to 31 Jul 2025 (STP 10/2020 Amdt 2)."""
NON_BANK_DIGITAL = (date(2022, 8, 1), date(2025, 7, 31))
"""P-20: non-bank digital payment services exempt 1 Aug 2022-31 Jul 2025 (STP 1/2022)."""
"""P-20: imported services to Labuan, exempt to 31 Dec 2021 (STP 2/2019)."""


def _financial(ctx: LineCtx) -> Exempt | None:
    charge = ctx.fact("financial_charge", None, "MS-10")
    if charge in ("bursa_clearing_trading_fee", "listing_perusal_fee"):
        return Exempt("P-2")
    if charge == "shariah_structure_fee" and ctx.supplier_registered("service", "P-3"):
        return Exempt("P-3")
    if charge == "asnb_fund_management":
        return Exempt("P-4")
    if charge == "government_securities_fee":
        return Exempt("P-5")
    if charge in ("bursa_share_brokerage", "commodity_platform_fee") or (
            charge == "tia_i_account_fee" and ctx.day >= TIA_I_FROM):
        return Exempt("P-7")
    if charge == "reinsurance" and ctx.fact("financial_use", None, "P-6") == "medical_life_family_cover":
        return Exempt("P-6")
    if ctx.buyer_registered() and ctx.buyer_provides("H") and charge != "bursa_share_brokerage":
        if ctx.fact("financial_use", None, "P-1") in FINANCIAL_USES_P1:
            return Exempt("P-1")
    return None


def _mro(ctx: LineCtx) -> Exempt | None:
    """P-9 (STP 6/2024 (Amdt 3)): MRO of aircraft and ships, G(n), until 31 Dec 2027."""
    if ctx.item != "G(n)" or not ctx.fact("mro_aircraft_ship", False, "P-9") or ctx.day > MRO_TO:
        return None
    kinds = set(ctx.cf.buyer_kinds)
    buyer = bool(kinds & set(MRO_BUYERS)) or ("foreign_company" in kinds and ctx.day >= MRO_FOREIGN_BUYER_FROM)
    approvals = set(ctx.sf.approvals)
    supplier = ("caam_amo" in approvals or ("mida_shipyard" in approvals and ctx.day >= MRO_MIDA_FROM)
                or ("dgta_amo" in approvals and ctx.day >= MRO_DGTA_FROM))
    return Exempt("P-9") if buyer and supplier else None


def _building(ctx: LineCtx) -> Exempt | None:
    charge = ctx.fact("building_charge", "none", "P-10")
    if charge == "none":
        return None
    residential = ctx.fact("residential", False, "P-11")
    if residential:
        # P-11 (STP 5/2024): residential sinking fund and free warranty repairs are not taxable.
        return Exempt("P-11") if charge in ("sinking_fund", "warranty_repair") else None
    if (charge in ("maintenance", "sinking_fund") and ctx.sf.supplier_kind == "developer_jmb_mc"
            and ctx.day >= NON_RESIDENTIAL_CHARGES_FROM):
        return Exempt("P-10")
    return None


def healthcare(ctx: LineCtx) -> Exempt | Taxable | None:
    """P-12 to P-14 for private healthcare (I14-16), before the citizen exemption (scope.py)."""
    category = ctx.fact("patient_category", None, "P-13")
    if category in SCREENING_CATEGORIES:
        return Exempt("P-13")
    itemised = ctx.fact("itemised_consultation_fee", None, "P-12")
    if itemised:
        return Exempt("P-12")
    walk_in = ctx.fact("referral_walk_in", None, "P-14")
    if walk_in is False:
        # STP 6/2025: a facility-to-facility referral is taxed only if the patient walked in to the second facility.
        return Exempt("P-14")
    if walk_in or ctx.fact("medical_aid", False, "P-14"):
        return Taxable("P-14")
    if itemised is False:
        # Consultation fee not itemised separately: the whole invoice is taxed.
        return Taxable("P-12")
    return None


def education(ctx: LineCtx) -> Exempt | None:
    """P-16 (STP 4/2025 (Amdt 2)): fee items other than tuition, fully sponsored fees, diplomats' children."""
    if ctx.fact("education_fee_item", "tuition", "P-16") in EDUCATION_ITEMS_EXEMPT:
        return Exempt("P-16")
    if ctx.fact("fully_sponsored", False, "P-16"):
        return Exempt("P-16")
    if ctx.fact("student_category", None, "P-16") == "diplomat_child":
        return Exempt("P-16")
    return None


def check(ctx: LineCtx) -> Exempt | Taxable | None:
    item, group = ctx.item, ctx.group
    if group == "H":
        found = _financial(ctx)
        if found:
            return found
    if (group in ("H", "M") or item in HEALTHCARE_ITEMS) and ctx.government_supplier("P-8", NEW_SCOPE_FROM):
        return Exempt("P-8")
    for rule in (_mro, _building):
        found = rule(ctx)
        if found:
            return found
    if item in HEALTHCARE_ITEMS:
        return healthcare(ctx)
    if group == "M":
        found = education(ctx)
        if found:
            return found
    if ctx.fact("oku_holder", False, "P-17") and ctx.sf.recognised_training_centre:
        return Exempt("P-17")
    if group == "J" and ctx.fact("carriage", "domestic", "P-18") in EXEMPT_CARRIAGE:
        return Exempt("P-18")
    if item in DIGITAL_ITEMS and ctx.fact("digital_content_type", "other", "P-19") in NOT_DIGITAL:
        return Exempt("P-19")
    if item in DIGITAL_ITEMS:
        provider = ctx.fact("digital_payment_provider", "none", "P-20")
        if provider == "bank" and ctx.day <= BANK_DIGITAL_TO:
            return Exempt("P-20")
        if provider == "non_bank" and NON_BANK_DIGITAL[0] <= ctx.day <= NON_BANK_DIGITAL[1]:
            return Exempt("P-20")
    if item == "G(i)" and ctx.fact("excluded_management_kind", "none", "P-15") == "health_examination_management":
        return Taxable("P-15") if ctx.day >= HEALTH_EXAM_TAXABLE_FROM else Exempt("P-15")
    return None


def labuan_imported(ctx: LineCtx) -> bool:
    """P-20: imported services to a company in Labuan, to 31 Dec 2021."""
    return ctx.cf.zone == "labuan" and ctx.day <= LABUAN_IMPORTED_TO
