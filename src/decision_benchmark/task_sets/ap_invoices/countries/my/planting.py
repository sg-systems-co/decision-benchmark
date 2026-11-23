"""Planting the Malaysian rules (B1-4): company kinds, the special suppliers the rules need, and one recipe per rule.

A recipe sets one invoice line so that the rule decides it, in its problem form (tax charged where the rule says none
is due, or the wrong tax) or its correct form, states the facts the rule reads in the case's documents, and says what
the engine must find: the line's treatment and basis, the finding codes and the buyer actions (Draft.expect). The
expected answer comes from the rule sheet for the situation built, never from running the engine (B1 plan section 4:
plant, then let the engine find it independently).

Facts no structured field holds are stated as phrasebank phrases in the invoice line description
(content/phrasebanks/facts/MY.yaml). Party facts sit in the supplier and company records; contract facts in the
contract records the special suppliers carry. Dates: the allocator gives each case a date inside the rule's window
(content/generator/rules.yaml, from the rule sheet), so a recipe only checks what the window can't (e.g. a category's
earlier class).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from ...codes import Code
from ...generator.country import CannotPlant, SpecialSupplier
from ...models.answer import WITHHOLD_TAX
from ...generator.entities import catalog, day_between
from . import einvoice_timeline as tl
from . import treaties
from .constants import (
    CLASSIFICATION_OTHERS as CLASSIFICATION, SALES_TAX_ORDERS_2025_FROM, TAX_CLASS_RATE,
    TAX_TYPE_NOT_APPLICABLE as NOT_APPLICABLE, TAX_TYPE_SALES, TAX_TYPE_SERVICE,
)
from .rules.einvoice import ISSUE_SELF_BILLED
from .rules.imported import ACCOUNT_IMPORTED
from .models import MyTaxProfile, MyTaxTreatment as T
from .rules import rates, scope

PROBLEM, CORRECT = "problem", "correct"

IMPORTED_ACTION = (ACCOUNT_IMPORTED, None, None)
SELF_BILLED_ACTION = (ISSUE_SELF_BILLED, None, None)


# -- companies -----------------------------------------------------------------------------------------------------

COMPANY_KINDS = ("it", "msme", "fin", "new_sme", "builder", "plain")
"""Given to the Malaysian companies of a split in turn, so a split of 6 Malaysian companies has one of each."""
PROVIDED = {"it": ["G(h)", "I8"], "builder": ["L", "G(f)"], "fin": ["H3", "H2"]}
"""First Schedule items each kind provides itself (the B2B order, MS-5; P-1; L-3)."""
SME_KINDS = ("msme", "new_sme")
COMPANY_EINVOICE = {
    "it": {"turnover_band": "above_100m", "turnover_basis": "fy2022_audited"},
    "fin": {"turnover_band": "25m_to_100m", "turnover_basis": "fy2022_audited"},
    "builder": {"turnover_band": "5m_to_25m", "turnover_basis": "fy2022_audited"},
    "plain": {"turnover_band": "3m_to_5m", "turnover_basis": "fy2022_audited"},
    "msme": {"turnover_band": "below_1m", "turnover_basis": "fy2022_audited"},
    "new_sme": {"turnover_band": "1m_to_3m", "turnover_basis": "new_business", "business_started_on": "2025-11-03"},
}
"""Each kind's turnover, which fixes its own e-invoicing phase (ME-3, by the ME-1 timeline): the SME kinds are below
RM3m (exempt: they never self-bill), the others spread over the four phases (1 Aug 2024, 1 Jan 2025, 1 Jul 2025,
1 Jan 2026)."""
SHIP_OWNER_KINDS = ("plain",)
"""The kinds registered as ship owners (P-9, MRO of ships). No other kind holds a status P-9 names."""


def company_facts(kind: str) -> dict:
    facts = {"country": "MY", "is_registered_manufacturer": True, "services_provided": list(PROVIDED.get(kind, [])),
             "einvoice": dict(COMPANY_EINVOICE[kind]),
             "buyer_kinds": ["registered_ship_owner"] if kind in SHIP_OWNER_KINDS else []}
    if kind == "msme":
        # K-1: declared sales below RM1m, registered in MyPMK; paid-up capital and group holding within the limits.
        facts["msme"] = {"mypmk_registered_on": "2025-03-14", "declared_sales_band": "below_1m",
                         "year_of_assessment": 2024, "paid_up_capital": "500000.00", "group_holding_pct": "0"}
    if kind == "new_sme":
        # K-2: registered with SSM on 3 Nov 2025, so new for a year from then; sales above the K-1 bands.
        facts["msme"] = {"mypmk_registered_on": "2025-12-01", "declared_sales_band": "above_1_5m",
                         "year_of_assessment": 2025, "paid_up_capital": "300000.00", "group_holding_pct": "0",
                         "ssm_registered_on": "2025-11-03"}
    return facts


def link_company(company: dict, special: dict[str, list[dict]]) -> None:
    """The company's group: a holding company owns 60% of it and 75% of each group supplier (MS-6, K-6). An SME kind
    belongs to no group (its K-1 / K-2 conditions say so)."""
    facts = company.setdefault("tax_facts", {"country": "MY"})
    groups = special.get("group", [])
    if facts.get("msme") is not None or not groups:
        facts["group"] = {"shareholdings": []}
        return
    gids = [g["tax_facts"]["group_company_id"] for g in groups]
    parent = f"{company['company_id']}-holding"
    facts["group"] = {"shareholdings": [{"holder_id": parent, "held_id": company["company_id"], "pct": "60"}] + [
        {"holder_id": parent, "held_id": gid, "pct": "75"} for gid in gids]}
    facts["group_companies"] = gids


# -- special suppliers ---------------------------------------------------------------------------------------------

BIG = {"is_manufacturer": True, "einvoice": {"turnover_band": "above_100m", "turnover_basis": "fy2022_audited"}}
"""A domestic special supplier makes goods and provides services (registered for both taxes) and is in the first
e-invoicing phase, so any rule's line can come from it (except the co-owner's, generation.yaml supplier_lacks)."""

SPECIAL_SUPPLIERS = (
    SpecialSupplier("general", ("industrial_valves", "bearings", "hand_tools", "advertising", "business_consultancy",
                                "security_guards"), facts=dict(BIG)),
    SpecialSupplier("government", ("parking",), facts={"supplier_kind": "federal_state_government", **BIG}),
    SpecialSupplier("jmb", ("parking",), facts={"supplier_kind": "developer_jmb_mc", **BIG}),
    SpecialSupplier("mro", ("vehicle_servicing",), facts={"approvals": ["caam_amo", "mida_shipyard"], **BIG}),
    SpecialSupplier("training", ("training_courses",), facts={"recognised_training_centre": True, **BIG}),
    SpecialSupplier("group", ("catering", "parking"), facts={"external_share_within_5pct": True, **BIG}),
    SpecialSupplier("k4_landlord", ("parking",), facts=dict(BIG),
                    contract={"signed_on": "2025-05-12", "stamped_on": "2025-05-20", "has_price_review_clause": False,
                              "states_service": True, "states_fixed_value": True, "states_period": True,
                              "start": "2025-06-01", "end": "2027-05-31"}),
    SpecialSupplier("l1_contractor", ("parking",), facts=dict(BIG),
                    contract={"signed_on": "2025-03-10", "stamped_on": "2025-04-02", "has_price_review_clause": False,
                              "states_service": True, "states_fixed_value": True, "states_period": True,
                              "start": "2025-03-15", "end": "2027-03-31"}),
    SpecialSupplier("co_owner_partner", ("parking",), facts=dict(BIG)),
    SpecialSupplier("co_owner", ("water_supply",), registered_for=(),
                    facts={"einvoice": {"turnover_band": "1m_to_3m", "turnover_basis": "fy2022_audited"}},
                    contract={"signed_on": "2023-02-01", "stamped_on": "2023-02-10", "has_price_review_clause": True,
                              "states_service": True, "states_fixed_value": True, "states_period": True,
                              "start": "2023-03-01", "end": "2029-02-28", "parties": ["co_owner_partner"]}),
    SpecialSupplier("new_registrant", ("parking",), registered_from="2024-03-01",
                    facts={"registered_before_2024_02_26": False, **BIG}),
    SpecialSupplier("local_authority", ("parking",), facts={"supplier_kind": "local_authority", **BIG}),
    SpecialSupplier("dgta_mro", ("vehicle_servicing",), facts={"approvals": ["dgta_amo"], **BIG}),
    SpecialSupplier("foreign_pe", ("imported_consultancy",), foreign=True, homes=("SG", "JP", "GB"),
                    facts={"pe_in_country": True}),
    SpecialSupplier("foreign_cert", ("imported_consultancy", "foreign_digital_services"), foreign=True,
                    homes=("JP", "SG", "GB"), residence=True),
    SpecialSupplier("foreign", ("imported_consultancy", "foreign_digital_services"), foreign=True,
                    homes=("US", "CN", "IN")),
)
"""One of each per split, shared by its Malaysian companies. categories: what the supplier's clean lines carry; the
planted lines come from the recipes. The landlord (K-4) and the contractor (L-1) hold contracts signed and stamped before the transitional
dates, without a price-review clause; the co-owner (K-8) isn't registered and its contract names its partner."""
SPECIAL_KINDS = tuple(s.kind for s in SPECIAL_SUPPLIERS)


def special_facts(kind: str, identity: dict) -> dict:
    if kind == "group":
        return {"group_company_id": f"GRP-{identity['registration_no']}"}
    return {}


# -- lines ---------------------------------------------------------------------------------------------------------


def profile(category: str) -> MyTaxProfile:
    p = catalog().get(category).tax["MY"]
    assert isinstance(p, MyTaxProfile)
    return p


def item_of(category: str) -> str | None:
    return profile(category).service_item


def goods_class(category: str, day: date) -> str | None:
    """The goods' class on the day (MG-2, MG-3), None when no order settles it (no earlier class for the date)."""
    p = profile(category)
    if day >= SALES_TAX_ORDERS_2025_FROM:
        return p.tax_class
    earlier = [e for e in p.earlier_classes if e.valid_from <= day <= e.valid_to]
    return earlier[0].tax_class if earlier else None


def service_ext(rate: Decimal) -> dict:
    return {"classification_code": CLASSIFICATION, "tax_type": TAX_TYPE_SERVICE if rate > 0 else NOT_APPLICABLE}


def goods_ext(rate: Decimal) -> dict:
    return {"classification_code": CLASSIFICATION, "tax_type": TAX_TYPE_SALES if rate > 0 else NOT_APPLICABLE}


def ext_for(category: str, rate: Decimal) -> dict:
    return goods_ext(rate) if catalog().get(category).kind == "goods" else service_ext(rate)


def standard_rate(category: str, day: date) -> Decimal:
    """The rate a correct invoice charges on the category's line on the day (service item or goods class)."""
    if catalog().get(category).kind == "goods":
        cls = goods_class(category, day)
        if cls is None or cls == "sales_exempt":
            raise CannotPlant(f"{category} carries no sales tax on {day}")
        return TAX_CLASS_RATE[cls]
    item = item_of(category)
    assert item is not None
    return rates.standard_rate(item, day)


def provided(d) -> list[str]:
    return list((d.cw.company.get("tax_facts") or {}).get("services_provided", []))


def pick(d, categories: list[str], what: str) -> str:
    """One of the categories the company doesn't provide itself (else the B2B order would decide the line), and no
    group-relief item from the group supplier (else group relief would)."""
    ok = [c for c in categories if item_of(c) not in provided(d)
          and not (d.supplier_kind == "group" and profile(c).group_relief)]
    if not ok:
        raise CannotPlant(f"no {what} category the company doesn't provide itself")
    return d.r.choice(ok)


def exempt(d, n: int, form: str, category: str, basis: str, facts: dict | None = None,
           open_question: str | None = None) -> None:
    """The rule exempts the line: correct, no tax (NO_SST); problem, the standard rate charged (SST_SHOULD_BE_EXEMPT)."""
    rate = standard_rate(category, d.day) if form == PROBLEM else Decimal(0)
    d.set_line(n, category, rate, ext_for(category, rate))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    if form == PROBLEM:
        d.expect(n, T.SST_SHOULD_BE_EXEMPT.value, basis, (Code.TAX_SHOULD_BE_EXEMPT.value,))
    else:
        d.expect(n, T.NO_SST.value, basis)
    if open_question:
        d.built.planted.open_questions.append(open_question)


def taxed(d, n: int, category: str, basis: str, facts: dict | None = None, rate: Decimal | None = None,
          ext: dict | None = None) -> None:
    """The rule leaves the line taxable and the invoice charges it right (SST_CORRECT)."""
    rate = standard_rate(category, d.day) if rate is None else rate
    d.set_line(n, category, rate, ext or ext_for(category, rate))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    d.expect(n, T.SST_CORRECT.value, basis)


def wrong_rate(d, n: int, category: str, basis: str, right: Decimal, facts: dict | None = None) -> None:
    other = {Decimal(8): Decimal(6), Decimal(6): Decimal(8), Decimal(10): Decimal(5), Decimal(5): Decimal(10)}
    rate = other[right]
    d.set_line(n, category, rate, ext_for(category, rate))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    d.expect(n, T.SST_WRONG_RATE.value, basis, (Code.WRONG_TAX_RATE.value,))


def foreign(d) -> bool:
    return d.supplier["country"] != "MY"


def need_domestic(d, rule: str) -> None:
    if foreign(d):
        raise CannotPlant(f"{rule} needs a domestic supplier")


def need_foreign(d, rule: str) -> None:
    if not foreign(d):
        raise CannotPlant(f"{rule} needs a foreign supplier")


def need_kind(d, rule: str, kind: str) -> None:
    if d.supplier_kind != kind:
        raise CannotPlant(f"{rule} needs the {kind} supplier, not {d.supplier_kind or 'an ordinary one'}")


def buyer_phase_start(company: dict) -> date | None:
    """The company's own e-invoicing implementation date by the ME-1 timeline; None: exempt (below RM3m) or none."""
    from .models import MyEinvoiceStatus

    status = (company.get("tax_facts") or {}).get("einvoice")
    if not status:
        return None
    s = MyEinvoiceStatus.model_validate(status)
    return None if tl.exempt_band(s.turnover_band) else tl.implementation_date(s)


def self_billing(company: dict, day: date) -> tuple:
    """ME-3: the buyer self-bills from its own implementation date (relaxation period included)."""
    start = buyer_phase_start(company)
    return (SELF_BILLED_ACTION,) if start is not None and day >= start else ()


def self_billed(d) -> tuple:
    return self_billing(d.cw.company, d.day)


def certificate_categories(d) -> set[str]:
    return d.cw.certificate_categories(d.day)


def goods_on(d, categories: list[str] | None = None, taxable: bool = True) -> list[str]:
    """Goods categories with a settled class on the day (no goods before 1 Sep 2018, no partly exempt heading before
    1 Jul 2025: planting limits 3 and 4), outside the company's certificates, without catalog facts."""
    names = categories if categories is not None else [c.category for c in catalog().categories
                                                        if c.kind == "goods" and "MY" in c.countries]
    out = []
    for c in names:
        p = profile(c)
        cls = goods_class(c, d.day)
        if cls is None or p.facts or c in certificate_categories(d) or p.area_goods:
            continue
        if taxable and cls == "sales_exempt":
            continue
        out.append(c)
    return out


SERVICES_8 = ["advertising", "security_guards", "recruitment_services", "legal_services", "audit_accounting",
              "business_consultancy", "engineering_consultancy", "vehicle_servicing"]
"""Plain 8% services, taxable since 1 Sep 2018 (6% before 1 Mar 2024), no catalog facts."""
SERVICES_6 = ["parking", "telecoms"]
GROUP_RELIEF = ["legal_services", "audit_accounting", "surveying_valuation", "engineering_consultancy",
                "architectural_services", "business_consultancy", "management_services", "it_services"]
RENTAL = ["equipment_rental", "commercial_premises_rental", "passenger_vehicle_rental"]
DA_ZONES = ["langkawi", "labuan", "tioman", "pangkor"]
"""Designated areas a line may name (never Pulau 1: planting limit 1)."""


# -- the recipes ---------------------------------------------------------------------------------------------------

Recipe = Callable[..., None]
RECIPES: dict[str, Recipe] = {}
"""Rule id -> recipe(d, n, form). What the case's supplier must be able to do is the rule's ``needs`` in rules.yaml."""


def recipe(rule: str):
    def wrap(fn: Recipe) -> Recipe:
        RECIPES[rule] = fn
        return fn
    return wrap


# MS: service tax


@recipe("MS-1")
def _ms1(d, n, form):
    if foreign(d):
        if form == PROBLEM:
            # A foreign supplier that isn't a registered person charges SST on its invoice.
            c = pick(d, ["imported_consultancy", "foreign_digital_services"], "imported service")
            rate = standard_rate(c, d.day)
            d.set_line(n, c, rate, service_ext(rate))
            d.expect(n, T.SST_SUPPLIER_NOT_REGISTERED.value, "MS-1", (Code.SUPPLIER_NOT_TAX_REGISTERED.value,), self_billed(d))
        else:
            # Interest is no taxable service: no tax, nothing for the buyer to account for (WH-1 withholds).
            d.set_line(n, "loan_interest_non_resident", Decimal(0), service_ext(Decimal(0)))
            d.expect(n, T.NO_SST.value, "MS-1", (), self_billed(d) + (_withholding(d, "interest"),))
        return
    if form == PROBLEM:
        # A service that becomes taxable only on 1 Jul 2025 (Group K, L) charged before then.
        if d.day >= scope.NEW_SCOPE_FROM:
            raise CannotPlant("MS-1 problem needs an invoice before 1 Jul 2025")
        c = d.r.choice(["construction_works", "commercial_premises_rental"])
        d.set_line(n, c, Decimal(6), service_ext(Decimal(6)))
        d.expect(n, T.SST_SHOULD_BE_EXEMPT.value, "MS-1", (Code.TAX_SHOULD_BE_EXEMPT.value,))
    else:
        exempt(d, n, CORRECT, "water_supply", "MS-1")


@recipe("MS-2")
def _ms2(d, n, form):
    need_domestic(d, "MS-2")
    c = pick(d, SERVICES_8 + SERVICES_6, "plain service")
    right = standard_rate(c, d.day)
    if form == PROBLEM:
        wrong_rate(d, n, c, "MS-2", right)
    else:
        taxed(d, n, c, "MS-2")


@recipe("MS-3")
def _ms3(d, n, form):
    """A service provided wholly in February 2024 at 6%, invoiced on or after 1 Mar 2024 when the item is 8%: the
    rate in force when the service was provided applies (reg 3A)."""
    need_domestic(d, "MS-3")
    if not rates.GENERAL_RATE_FROM <= d.day:
        raise CannotPlant("MS-3 needs an invoice on or after 1 Mar 2024")
    c = pick(d, ["advertising", "security_guards", "legal_services", "audit_accounting", "business_consultancy"],
             "8% service")
    start = day_between(d.r, date(2024, 2, 1), date(2024, 2, 15))
    end = day_between(d.r, start + timedelta(days=7), date(2024, 2, 29))
    rate = Decimal(6) if form == CORRECT else Decimal(8)
    d.set_line(n, c, rate, service_ext(rate))
    d.state(n, "service_period_start", start)
    d.state(n, "service_period_end", end)
    if form == CORRECT:
        d.expect(n, T.SST_CORRECT.value, "MS-3")
    else:
        d.expect(n, T.SST_WRONG_RATE.value, "MS-3", (Code.WRONG_TAX_RATE.value,))


@recipe("MS-4")
def _ms4(d, n, form):
    need_domestic(d, "MS-4")
    exempt(d, n, form, "commercial_cleaning", "MS-4", {"premises_use": d.r.choice(["residential", "educational"])})


@recipe("MS-5")
def _ms5(d, n, form):
    """B2B order items 1, 9: the company provides the same item and buys it for its business."""
    need_domestic(d, "MS-5")
    options = {"G(h)": ["it_services", "software_development"], "I8": ["advertising"],
               "G(f)": ["architectural_services"]}
    if d.day >= scope.NEW_SCOPE_FROM:
        options["L"] = ["construction_works"]
    cats = [c for item in provided(d) for c in options.get(item, [])]
    if not cats:
        raise CannotPlant("MS-5 needs a company that provides a B2B item")
    c = d.r.choice(cats)
    exempt(d, n, form, c, "MS-5")
    if form == CORRECT:
        # Reg 10(1A): the exempt line shows why (ME-4).
        _ext(d, n)["tax_exemption_reason"] = "Exempt under the Service Tax (Persons Exempted from Payment of Tax) Order"


@recipe("MS-6")
def _ms6(d, n, form):
    need_kind(d, "MS-6", "group")
    cats = [c for c in GROUP_RELIEF if item_of(c) not in provided(d)]
    exempt(d, n, form, d.r.choice(cats), "MS-6")


@recipe("MS-7")
def _ms7(d, n, form):
    """Accommodation or food provided on a designated island, by the operator there (site rule)."""
    need_domestic(d, "MS-7")
    exempt(d, n, form, d.r.choice(["hotel_accommodation", "catering"]), "MS-7",
           {"service_site_zone": d.r.choice(DA_ZONES)})


@recipe("MS-8")
def _ms8(d, n, form):
    need_foreign(d, "MS-8")
    c = pick(d, ["imported_consultancy", "foreign_digital_services", "imported_it_services"], "imported service")
    d.set_line(n, c, Decimal(0), service_ext(Decimal(0)))
    d.expect(n, T.SST_BUYER_ACCOUNTS.value, "MS-8", (), (IMPORTED_ACTION,) + self_billed(d))


@recipe("MS-9")
def _ms9(d, n, form):
    need_domestic(d, "MS-9")
    c = pick(d, SERVICES_8 + SERVICES_6, "plain service")
    d.set_line(n, c, Decimal(0), service_ext(Decimal(0)))
    d.expect(n, T.SST_UNDERCHARGED.value, "MS-9", (Code.TAX_UNDERCHARGED.value,))


# P-1 to P-20: Service Tax Policies


def _financial(d, n, form, basis, charge, use=None, category="bank_fees_commissions"):
    need_domestic(d, basis)
    facts = {"financial_charge": charge}
    if use:
        facts["financial_use"] = use
    exempt(d, n, form, category, basis, facts)


@recipe("P-1")
def _p1(d, n, form):
    _financial(d, n, form, "P-1", "fee_or_commission", "taxable_financial_services")


@recipe("P-2")
def _p2(d, n, form):
    _financial(d, n, form, "P-2", d.r.choice(["bursa_clearing_trading_fee", "listing_perusal_fee"]))


@recipe("P-3")
def _p3(d, n, form):
    _financial(d, n, form, "P-3", "shariah_structure_fee")


@recipe("P-4")
def _p4(d, n, form):
    _financial(d, n, form, "P-4", "asnb_fund_management")


@recipe("P-5")
def _p5(d, n, form):
    _financial(d, n, form, "P-5", "government_securities_fee")


@recipe("P-6")
def _p6(d, n, form):
    _financial(d, n, form, "P-6", "reinsurance", "medical_life_family_cover", category="business_insurance")


@recipe("P-7")
def _p7(d, n, form):
    _financial(d, n, form, "P-7", d.r.choice(["bursa_share_brokerage", "commodity_platform_fee"]))


@recipe("P-8")
def _p8(d, n, form):
    need_kind(d, "P-8", "government")
    exempt(d, n, form, "staff_medical_treatment", "P-8")


@recipe("P-9")
def _p9(d, n, form):
    need_kind(d, "P-9", "mro")
    exempt(d, n, form, "aircraft_ship_mro", "P-9")


@recipe("P-10")
def _p10(d, n, form):
    need_kind(d, "P-10", "jmb")
    exempt(d, n, form, "building_maintenance_charges", "P-10")


@recipe("P-11")
def _p11(d, n, form):
    need_domestic(d, "P-11")
    exempt(d, n, form, "building_maintenance_charges", "P-11",
           {"residential": True, "building_charge": d.r.choice(["sinking_fund", "warranty_repair"])})


@recipe("P-12")
def _p12(d, n, form):
    need_domestic(d, "P-12")
    exempt(d, n, form, "healthcare_consultation", "P-12")


@recipe("P-13")
def _p13(d, n, form):
    need_domestic(d, "P-13")
    exempt(d, n, form, "staff_medical_treatment", "P-13",
           {"patient_category": d.r.choice(["foreign_worker_screening", "newborn_with_citizen_parent"])})


@recipe("P-14")
def _p14(d, n, form):
    need_domestic(d, "P-14")
    exempt(d, n, form, "staff_medical_treatment", "P-14", {"referral_walk_in": False})


@recipe("P-15")
def _p15(d, n, form):
    """Health-examination management: exempt to 30 Apr 2026, taxable as a management service from 1 May 2026."""
    need_domestic(d, "P-15")
    facts = {"excluded_management_kind": "health_examination_management"}
    if d.day >= date(2026, 5, 1):
        if form == PROBLEM:
            raise CannotPlant("P-15 problem needs an invoice before 1 May 2026")
        taxed(d, n, "management_services", "P-15", facts)
    else:
        exempt(d, n, form, "management_services", "P-15", facts)


@recipe("P-16")
def _p16(d, n, form):
    need_domestic(d, "P-16")
    exempt(d, n, form, "staff_education_fees", "P-16",
           {"education_fee_item": d.r.choice(["books", "uniform", "food", "transport", "accommodation"])})


@recipe("P-17")
def _p17(d, n, form):
    need_kind(d, "P-17", "training")
    exempt(d, n, form, "training_courses", "P-17", {"oku_holder": True})


@recipe("P-18")
def _p18(d, n, form):
    need_domestic(d, "P-18")
    exempt(d, n, form, "logistics_haulage", "P-18",
           {"carriage": d.r.choice(["door_to_door_international", "ocean_peninsula_east_malaysia"])})


@recipe("P-19")
def _p19(d, n, form):
    need_domestic(d, "P-19")
    exempt(d, n, form, "telecoms", "P-19",
           {"digital_content_type": d.r.choice(["online_distance_learning", "e_newspaper_journal_periodical"])})


@recipe("P-20")
def _p20(d, n, form):
    """Digital services of a bank, exempt to 31 Jul 2025 (and of a non-bank provider from 1 Aug 2022)."""
    need_domestic(d, "P-20")
    if d.day > date(2025, 7, 31):
        raise CannotPlant("P-20 needs an invoice by 31 Jul 2025")
    exempt(d, n, form, "telecoms", "P-20", {"digital_payment_provider": d.r.choice(["bank", "non_bank"])})


# K-1 to K-8: rental


def _rental(d, n, form, basis, category=None, facts=None):
    need_domestic(d, basis)
    exempt(d, n, form, category or d.r.choice(RENTAL), basis, facts)


@recipe("K-1")
def _k1(d, n, form):
    if d.cw.kind != "msme":
        raise CannotPlant("K-1 needs an SME tenant")
    _rental(d, n, form, "K-1")


@recipe("K-2")
def _k2(d, n, form):
    if d.cw.kind != "new_sme":
        raise CannotPlant("K-2 needs a new SME")
    _rental(d, n, form, "K-2")


@recipe("K-3")
def _k3(d, n, form):
    _rental(d, n, form, "K-3", "aircraft_vessel_charter")


@recipe("K-4")
def _k4(d, n, form):
    need_kind(d, "K-4", "k4_landlord")
    if d.cw.kind in SME_KINDS:
        raise CannotPlant("K-4: an SME tenant takes K-1 or K-2 first")
    _rental(d, n, form, "K-4", "commercial_premises_rental")


@recipe("K-5")
def _k5(d, n, form):
    need_kind(d, "K-5", "government")
    _rental(d, n, form, "K-5", "commercial_premises_rental")


@recipe("K-6")
def _k6(d, n, form):
    need_kind(d, "K-6", "group")
    _rental(d, n, form, "K-6", "equipment_rental")


@recipe("K-7")
def _k7(d, n, form):
    _rental(d, n, form, "K-7", "equipment_rental", {"asset_in_malaysia": False})


@recipe("K-8")
def _k8(d, n, form):
    """Co-owners under one agreement are separate suppliers: the one that invoices isn't registered (STP 4/2026)."""
    need_kind(d, "K-8", "co_owner")
    if form != PROBLEM:
        raise CannotPlant("K-8 has only a problem form")
    rate = standard_rate("commercial_premises_rental", d.day)
    d.set_line(n, "commercial_premises_rental", rate, service_ext(rate))
    d.expect(n, T.SST_SUPPLIER_NOT_REGISTERED.value, "K-8", (Code.SUPPLIER_NOT_TAX_REGISTERED.value,))


# L-1 to L-8: construction


@recipe("L-1")
def _l1(d, n, form):
    need_kind(d, "L-1", "l1_contractor")
    exempt(d, n, form, "construction_works", "L-1")


@recipe("L-2")
def _l2(d, n, form):
    need_domestic(d, "L-2")
    exempt(d, n, form, "construction_works", "L-2", {"residential_share": Decimal(1), "mixed_development_stated": True})


@recipe("L-3")
def _l3(d, n, form):
    need_domestic(d, "L-3")
    if "L" not in provided(d):
        raise CannotPlant("L-3 needs a main contractor")
    exempt(d, n, form, "engineering_consultancy", "L-3",
           {"design_and_build": True, "exemption_statement_on_invoice": True})


@recipe("L-4")
def _l4(d, n, form):
    need_domestic(d, "L-4")
    exempt(d, n, form, "construction_works", "L-4", {"place_of_worship": True})


@recipe("L-5")
def _l5(d, n, form):
    need_domestic(d, "L-5")
    exempt(d, n, form, "construction_works", "L-5", {"residential": True, "completed_building": True})


@recipe("L-6")
def _l6(d, n, form):
    need_domestic(d, "L-6")
    exempt(d, n, form, "construction_works", "L-6",
           {"client_established_in_malaysia": False, "exemption_statement_on_invoice": True})


@recipe("L-7")
def _l7(d, n, form):
    need_kind(d, "L-7", "government")
    exempt(d, n, form, "construction_works", "L-7")


@recipe("L-8")
def _l8(d, n, form):
    """Installation by a registered manufacturer not shown separately: sales tax on the whole value (STP 7/2025)."""
    need_domestic(d, "L-8")
    c = "installed_equipment"
    if form == CORRECT:
        rate = d.r.choice([Decimal(10), Decimal(5)])
        d.set_line(n, c, rate, goods_ext(rate))
        d.expect(n, T.SST_CORRECT.value, "L-8")
    else:
        rate = rates.standard_rate("L", d.day)
        d.set_line(n, c, rate, service_ext(rate))
        d.expect(n, T.SST_WRONG_RATE.value, "L-8", (Code.WRONG_TAX_RATE.value,))


# MG-1 to MG-5, G-1 to G-5: sales tax


@recipe("MG-1")
def _mg1(d, n, form):
    cats = goods_on(d)
    if not cats:
        raise CannotPlant("MG-1: no taxable goods on the day")
    c = d.r.choice(cats)
    if foreign(d):
        if form == PROBLEM:
            rate = standard_rate(c, d.day)
            d.set_line(n, c, rate, goods_ext(rate))
            d.expect(n, T.SST_SUPPLIER_NOT_REGISTERED.value, "MG-1", (Code.SUPPLIER_NOT_TAX_REGISTERED.value,), self_billed(d))
        else:
            d.set_line(n, c, Decimal(0), goods_ext(Decimal(0)))
            d.expect(n, T.NO_SST.value, "MG-1", (), self_billed(d))
        return
    if form == PROBLEM:
        rate = standard_rate(c, d.day)
        d.set_line(n, c, rate, goods_ext(rate))
        d.state(n, "manufactured_by_supplier", False)
        d.expect(n, T.SST_NOT_CHARGEABLE_BY_TRADER.value, "MG-1", (Code.SALES_TAX_CHARGED_BY_TRADER.value,))
    else:
        exempt(d, n, CORRECT, c, "MG-1", {"manufactured_by_supplier": False})


@recipe("MG-2")
def _mg2(d, n, form):
    need_domestic(d, "MG-2")
    cats = [c for c in goods_on(d) if goods_class(c, d.day) == profile(c).tax_class]
    if not cats:
        raise CannotPlant("MG-2: no goods taxed at today's class on the day")
    c = d.r.choice(cats)
    if form == PROBLEM:
        wrong_rate(d, n, c, "MG-2", standard_rate(c, d.day))
    else:
        taxed(d, n, c, "MG-2")


@recipe("MG-3")
def _mg3(d, n, form):
    """Goods exempt under the 2018/2022 orders, taxed under the 2025 orders, invoiced before 1 Jul 2025."""
    need_domestic(d, "MG-3")
    cats = [c for c in goods_on(d, taxable=False) if goods_class(c, d.day) == "sales_exempt"
            and profile(c).tax_class != "sales_exempt"]
    if d.day >= SALES_TAX_ORDERS_2025_FROM or not cats:
        raise CannotPlant("MG-3 needs goods exempt only under the earlier orders, before 1 Jul 2025")
    c = d.r.choice(cats)
    rate = TAX_CLASS_RATE[profile(c).tax_class] if form == PROBLEM else Decimal(0)
    d.set_line(n, c, rate, goods_ext(rate))
    if form == PROBLEM:
        d.expect(n, T.SST_SHOULD_BE_EXEMPT.value, "MG-3", (Code.TAX_SHOULD_BE_EXEMPT.value,))
    else:
        d.expect(n, T.NO_SST.value, "MG-3")


@recipe("MG-4")
def _mg4(d, n, form):
    """The company's Schedule C certificate covers the goods (not the pallets, which are G-4)."""
    need_domestic(d, "MG-4")
    covered = sorted(certificate_categories(d) - {"wooden_pallets"})
    if form == PROBLEM:            # the goods would carry tax without the certificate
        covered = [c for c in covered if goods_class(c, d.day) not in (None, "sales_exempt")]
    if not covered:
        raise CannotPlant("MG-4 needs a certificate covering goods taxed on the day")
    c = d.r.choice(covered)
    rate = TAX_CLASS_RATE[goods_class(c, d.day)] if form == PROBLEM else Decimal(0)
    d.set_line(n, c, rate, goods_ext(rate))
    if form == PROBLEM:
        d.expect(n, T.SST_SHOULD_BE_EXEMPT.value, "MG-4", (Code.TAX_SHOULD_BE_EXEMPT.value,))
    else:
        d.expect(n, T.NO_SST.value, "MG-4")


@recipe("MG-5")
def _mg5(d, n, form):
    """Goods delivered from a principal customs area manufacturer to a designated island. A quarter are goods the DA
    order lists (motor vehicles into Tioman or Pangkor): MG-5 step 2 exempts them, resting on Q-A1 (flagged)."""
    need_domestic(d, "MG-5")
    listed = "motorcycles_50_150cc"
    if d.r.random() < 0.25 and (form == CORRECT or goods_class(listed, d.day) not in (None, "sales_exempt")):
        c, zone, question = listed, d.r.choice(["tioman", "pangkor"]), "Q-A1"
    else:
        cats = goods_on(d)
        if not cats:
            raise CannotPlant("MG-5: no taxable goods on the day")
        c, zone, question = d.r.choice(cats), d.r.choice(DA_ZONES), None
    exempt(d, n, form, c, "MG-5", {"delivery_zone": zone}, open_question=question)


@recipe("G-1")
def _g1(d, n, form):
    need_domestic(d, "G-1")
    exempt(d, n, form, "motorcycles_50_150cc", "G-1")


@recipe("G-3")
def _g3(d, n, form):
    """Critical raw materials of Sales Tax Policy 1/2026: charged as normal, refunded (1 Jan to 31 Aug 2026)."""
    need_domestic(d, "G-3")
    cats = [c for c in ("animal_feed_fishmeal", "animal_feed_premix") if c not in certificate_categories(d)]
    if not cats:
        raise CannotPlant("G-3: the company's certificate covers the raw materials (MG-4)")
    taxed(d, n, d.r.choice(cats), "G-3")


@recipe("G-4")
def _g4(d, n, form):
    """Pallets under a Schedule C certificate: one-way pallets exempt, returnable ones taxable (STP 1/2022)."""
    need_domestic(d, "G-4")
    if "wooden_pallets" not in certificate_categories(d):
        raise CannotPlant("G-4 needs a certificate covering pallets")
    if form == CORRECT and d.r.random() < 0.5:
        taxed(d, n, "wooden_pallets", "G-4", {"pallet_returnable": True})
        return
    rate = standard_rate("wooden_pallets", d.day) if form == PROBLEM else Decimal(0)
    d.set_line(n, "wooden_pallets", rate, goods_ext(rate))
    d.state(n, "pallet_returnable", False)
    if form == PROBLEM:
        d.expect(n, T.SST_SHOULD_BE_EXEMPT.value, "G-4", (Code.TAX_SHOULD_BE_EXEMPT.value,))
    else:
        d.expect(n, T.NO_SST.value, "G-4")


@recipe("G-5")
def _g5(d, n, form):
    need_domestic(d, "G-5")
    cats = goods_on(d)
    if not cats:
        raise CannotPlant("G-5: no taxable goods on the day")
    exempt(d, n, form, d.r.choice(cats), "G-5", {"drop_shipment_export": True})


# ME-1 to ME-4: e-invoices and invoice particulars (findings and the self-billing action)


@recipe("ME-1")
def _me1(d, n, form):
    """A supplier past its relaxation period sends an invoice that isn't a validated e-invoice."""
    need_domestic(d, "ME-1")
    if not past_relaxation(d.supplier, d.day):
        raise CannotPlant("ME-1 needs a supplier past its relaxation period")
    e = d.invoice["einvoice"]
    e.update(is_einvoice=False, uuid=None, validation_datetime=None)
    d.findings.append(Code.MISSING_MANDATORY_FIELD.value)


@recipe("ME-2")
def _me2(d, n, form):
    need_domestic(d, "ME-2")
    d.invoice["einvoice"]["buyer_tin"] = None            # a MyInvois mandatory field
    d.findings.append(Code.MISSING_MANDATORY_FIELD.value)


@recipe("ME-3")
def _me3(d, n, form):
    """Self-billing: on a foreign supplier's lines the buyer issues the e-invoice (every line already brings it); on a
    domestic line, an agent's commission (type (a))."""
    if not self_billing(d.cw.company, d.day):
        raise CannotPlant("ME-3 needs a buyer in its e-invoicing phase on the day")
    if foreign(d):
        return
    d.state(n, "self_billing_type", "agents_dealers_distributors")
    d.add_actions(n, (SELF_BILLED_ACTION,))


@recipe("ME-4")
def _me4(d, n, form):
    """An SST invoice without the supplier's address (reg 10(1)). Line n (its own) charges tax as normal."""
    need_domestic(d, "ME-4")
    if not Decimal(d.line(n)["tax_rate"]) > 0:
        taxed(d, n, pick(d, SERVICES_8 + SERVICES_6, "plain service"), "MS-2")
    d.invoice["supplier_block"]["address"] = None
    d.findings.append(Code.MISSING_MANDATORY_FIELD.value)


# WH-1 to WH-4: withholding on payments to non-residents (buyer actions)


def _withholding(d, nature: str) -> tuple:
    """WITHHOLD_TAX at the domestic rate, or the lower treaty rate with a certificate of residence (WH-1, WH-2)."""
    domestic = treaties.table().domestic
    column, rate, basis = {"interest": ("interest", domestic.interest, "WH-1"),
                           "royalty": ("royalties", domestic.royalties, "WH-1"),
                           "technical_advice": ("technical_fees", domestic.technical_fees, "WH-2")}[nature]
    sid = d.built.case["supplier_id"]
    certified = any(c["supplier_id"] == sid and date.fromisoformat(c["valid_from"]) <= d.day
                    and (c.get("valid_to") is None or d.day <= date.fromisoformat(c["valid_to"]))
                    for c in d.cw.residence_certificates)
    if certified:
        row = treaties.row(d.supplier["country"], d.day)
        if row is not None:
            rate = min(rate, getattr(row, column).for_payer(False))
    return (WITHHOLD_TAX, str(rate), basis)


@recipe("WH-1")
def _wh1(d, n, form):
    need_foreign(d, "WH-1")
    if d.r.random() < 0.5:
        d.set_line(n, "software_royalty", Decimal(0), service_ext(Decimal(0)))
        d.expect(n, T.SST_BUYER_ACCOUNTS.value, "MS-8", (),
                 (IMPORTED_ACTION,) + self_billed(d) + (_withholding(d, "royalty"),))
    else:
        d.set_line(n, "loan_interest_non_resident", Decimal(0), service_ext(Decimal(0)))
        d.expect(n, T.NO_SST.value, "MS-1", (), self_billed(d) + (_withholding(d, "interest"),))


@recipe("WH-2")
def _wh2(d, n, form):
    """Technical advice performed in Malaysia (s4A (ii)); the line states its service period (planting limit 7)."""
    need_foreign(d, "WH-2")
    if not d.invoice.get("service_period_start"):
        raise CannotPlant("WH-2 needs the invoice's service period")
    d.set_line(n, "technical_services_from_abroad", Decimal(0), service_ext(Decimal(0)))
    d.state(n, "place_of_performance", "in_country")
    d.expect(n, T.SST_BUYER_ACCOUNTS.value, "MS-8", (),
             (IMPORTED_ACTION,) + self_billed(d) + (_withholding(d, "technical_advice"),))


@recipe("WH-3")
def _wh3(d, n, form):
    """A contract payment to a non-resident contractor with a permanent establishment here (s107A: 10% + 3%)."""
    need_kind(d, "WH-3", "foreign_pe")
    d.set_line(n, "imported_consultancy", Decimal(0), service_ext(Decimal(0)))
    d.state(n, "payment_nature", "contract_payment")
    d.expect(n, T.SST_BUYER_ACCOUNTS.value, "MS-8", (),
             (IMPORTED_ACTION,) + self_billed(d) + ((WITHHOLD_TAX, "10", "WH-3"), (WITHHOLD_TAX, "3", "WH-3")))


@recipe("WH-4")
def _wh4(d, n, form):
    need_foreign(d, "WH-4")
    nature, rate = d.r.choice([("other_gain", "10"), ("public_entertainer", "15")])
    d.set_line(n, "imported_consultancy", Decimal(0), service_ext(Decimal(0)))
    d.state(n, "payment_nature", nature)
    d.expect(n, T.SST_BUYER_ACCOUNTS.value, "MS-8", (), (IMPORTED_ACTION,) + self_billed(d) + ((WITHHOLD_TAX, rate, "WH-4"),))


# -- branches: a line whose answer turns on a dated boundary (generation.yaml boundaries) ----------------------------

BEFORE, AFTER = "before", "after"
BRANCHES: dict[str, Recipe] = {}


def branch(name: str):
    def wrap(fn: Recipe) -> Recipe:
        BRANCHES[name] = fn
        return fn
    return wrap


def _uncharged(d, n, category, basis, facts=None):
    exempt(d, n, CORRECT, category, basis, facts)


@branch("scope_2024")
def _b_scope_2024(d, n, side):
    """26 Feb 2024: maintenance or repair (G(n)) becomes taxable. Before: not a taxable service (MS-1); 26-29 Feb: the
    STP 1/2024 transitional exemption for every registrant (P-20); from 1 Mar: taxed (the supplier was registered)."""
    need_domestic(d, "scope_2024")
    if side == BEFORE:
        _uncharged(d, n, "maintenance_repair", "MS-1")
    elif d.day <= date(2024, 2, 29):
        _uncharged(d, n, "maintenance_repair", "P-20")
    else:
        taxed(d, n, "maintenance_repair", "MS-2")


@branch("rate_2024")
def _b_rate_2024(d, n, side):
    """1 Mar 2024: 8% services go from 6% to 8%."""
    need_domestic(d, "rate_2024")
    taxed(d, n, pick(d, ["advertising", "security_guards", "legal_services", "audit_accounting"], "8% service"), "MS-2")


@branch("stp_new_registrant")
def _b_stp_new_registrant(d, n, side):
    """1 Apr 2024: a supplier first liable to register for the 26 Feb 2024 services charges from 1 Apr (STP 1/2024)."""
    need_kind(d, "stp_new_registrant", "new_registrant")
    if side == BEFORE:
        _uncharged(d, n, "maintenance_repair", "P-20")
    else:
        taxed(d, n, "maintenance_repair", "MS-2")


@branch("gn_group_relief")
def _b_gn_group_relief(d, n, side):
    """1 May 2024: G(n) joins group relief (P.U. (A) 354/2024)."""
    need_kind(d, "gn_group_relief", "group")
    if side == BEFORE:
        taxed(d, n, "maintenance_repair", "MS-2")
    else:
        _uncharged(d, n, "maintenance_repair", "MS-6")


def _agent_commission(d, n):
    """ME-3 type (a) on a domestic line: the buyer self-bills from its own phase start."""
    need_domestic(d, "ME-3")
    d.state(n, "self_billing_type", "agents_dealers_distributors")
    d.add_actions(n, self_billed(d))


@branch("me3_phase_1")
def _b_me3_phase_1(d, n, side):
    """1 Aug 2024: a buyer above RM100m starts its e-invoicing phase, and self-bills from then."""
    _agent_commission(d, n)


@branch("me3_phase_2")
def _b_me3_phase_2(d, n, side):
    """1 Jan 2025: a buyer of RM25m-100m starts its phase."""
    _agent_commission(d, n)


@branch("wellness_tcm")
def _b_wellness_tcm(d, n, side):
    """27 Nov 2024: wellness services at a T&CM practitioner's premises are excluded (to 30 Jun 2025)."""
    need_domestic(d, "wellness_tcm")
    facts = {"wellness_facility_kind": "tcm_practitioner_premises"}
    if side == BEFORE:
        taxed(d, n, "wellness_centre_services", "MS-2", facts)
    else:
        _uncharged(d, n, "wellness_centre_services", "MS-4", facts)


@branch("me1_relaxation_end")
def _b_me1_relaxation_end(d, n, side):
    """31 Jan 2025: the relaxation period of the first phase ends. Before: an invoice that isn't a validated e-invoice
    is fine (a consolidated e-invoice may follow); after: it misses the e-invoice (ME-1, on an invalid-invoice slot)."""
    need_domestic(d, "me1_relaxation_end")
    if side == BEFORE:
        if not phase_one(d.supplier):
            raise CannotPlant("me1_relaxation_end needs a first-phase supplier")
        d.invoice["einvoice"].update(is_einvoice=False, uuid=None, validation_datetime=None)
    else:
        from decision_benchmark.core.generator.slots import RuleUse

        _me1(d, n, CORRECT)
        d.uses.append(RuleUse("ME-1", CORRECT, "finding"))   # the invalidity is ME-1's (not the default particular)


@branch("ms7_items_5_7")
def _b_ms7_items_5_7(d, n, side):
    """30 May 2025: customs clearance on a designated island leaves item 7 (to 29 May 2025, taxed) for item 5, which
    needs the agent's s90 licence: an unlicensed agent's clearance there is then not taxed (MS-7)."""
    need_domestic(d, "ms7_items_5_7")
    if (d.supplier.get("tax_facts") or {}).get("area_licences"):
        raise CannotPlant("ms7_items_5_7 needs an agent without area licences")
    facts = {"service_site_zone": d.r.choice(DA_ZONES)}
    if side == BEFORE:
        taxed(d, n, "customs_agent", "MS-2", facts)
    else:
        _uncharged(d, n, "customs_agent", "MS-7", facts)


@branch("scope_2025")
def _b_scope_2025(d, n, side):
    """1 Jul 2025: construction becomes a taxable service."""
    need_domestic(d, "scope_2025")
    if side == BEFORE:
        _uncharged(d, n, "construction_works", "MS-1")
    else:
        taxed(d, n, "construction_works", "MS-2")


@branch("local_authority_end")
def _b_local_authority_end(d, n, side):
    """30 Sep 2025: a local authority's exemption on rental (K-5) ends."""
    need_kind(d, "local_authority_end", "local_authority")
    if side == BEFORE:
        _uncharged(d, n, "commercial_premises_rental", "K-5")
    else:
        taxed(d, n, "commercial_premises_rental", "MS-2")


@branch("rental_rate_2026")
def _b_rental_rate_2026(d, n, side):
    """1 Jan 2026: rental goes from 8% to 6%."""
    need_domestic(d, "rental_rate_2026")
    taxed(d, n, d.r.choice(["equipment_rental", "passenger_vehicle_rental"]), "MS-2")


@branch("p15_taxable")
def _b_p15_taxable(d, n, side):
    """1 May 2026: health-examination management becomes taxable (P-15)."""
    _p15(d, n, CORRECT)


@branch("tia_i")
def _b_tia_i(d, n, side):
    """1 Jun 2026: TIA-i account fees are exempt (P-7)."""
    need_domestic(d, "tia_i")
    facts = {"financial_charge": "tia_i_account_fee"}
    if side == BEFORE:
        taxed(d, n, "bank_fees_commissions", "MS-2", facts)
    else:
        _uncharged(d, n, "bank_fees_commissions", "P-7", facts)


@branch("k4_end")
def _b_k4_end(d, n, side):
    """30 Jun 2026: the transitional exemption for rental under non-reviewable contracts (K-4) ends."""
    need_kind(d, "k4_end", "k4_landlord")
    if side == BEFORE:
        _uncharged(d, n, "commercial_premises_rental", "K-4")
    else:
        taxed(d, n, "commercial_premises_rental", "MS-2")


@branch("g3_end")
def _b_g3_end(d, n, side):
    """31 Aug 2026: the refund route for critical raw materials (G-3) ends; without a Schedule B certificate the
    ordinary rate applies (MG-2)."""
    need_domestic(d, "g3_end")
    cats = [c for c in ("animal_feed_fishmeal", "animal_feed_premix") if c not in certificate_categories(d)]
    if not cats:
        raise CannotPlant("g3_end: the company's certificate covers the raw materials")
    taxed(d, n, d.r.choice(cats), "G-3" if side == BEFORE else "MG-2")


@branch("dgta_mro")
def _b_dgta_mro(d, n, side):
    """22 Sep 2026: MRO by a DGTA-approved organisation for a ship owner is exempt (P-9)."""
    need_kind(d, "dgta_mro", "dgta_mro")
    if side == BEFORE:
        taxed(d, n, "aircraft_ship_mro", "MS-2")
    else:
        _uncharged(d, n, "aircraft_ship_mro", "P-9")


# -- §5-b splits and mixed lines -------------------------------------------------------------------------------------


def plant_split(d, n: int) -> None:
    """A line that turns on a §5-b split (B1 plan section 3.3): a package sold at one price (the group's rate, from
    1 Mar 2024); from 1 Jul 2025 also construction whose materials and works aren't shown separately (L-8: the whole
    is taxed), installation by a sales-tax manufacturer not shown separately (L-8), an itemised consultation fee or one
    that isn't (P-12), or a school fee item other than tuition (P-16). Where the supplier can't charge tax, only the
    uncharged ones."""
    need_domestic(d, "split")
    charges = registered(d.supplier, "service", d.day)
    gov = d.supplier_kind in ("government", "local_authority")
    builder = "L" in provided(d)
    options = []
    if charges and d.day >= rates.GENERAL_RATE_FROM:
        options.append("package")
    if d.day >= scope.NEW_SCOPE_FROM:
        if not gov:
            options += ["p12", "p16"]
        if charges and not gov and not builder and d.supplier_kind not in ("l1_contractor", "k4_landlord"):
            options.append("materials")
        if registered(d.supplier, "sales", d.day) and is_manufacturer(d.supplier):
            options.append("installation")
    if not options:
        raise CannotPlant("no split the supplier and the date allow")
    choice = d.r.choice(options)
    if choice == "package":
        taxed(d, n, "catering", "MS-2", {"package_single_price": True})
    elif choice == "materials":
        taxed(d, n, "construction_works", "L-8", {"materials_works_separated": False})
    elif choice == "installation":
        _l8(d, n, CORRECT)
    elif choice == "p12":
        if charges and d.r.random() < 0.5:
            # Not itemised: the whole invoice is taxed (P-12), for a non-citizen patient (a citizen's is excluded, MS-4).
            taxed(d, n, "healthcare_consultation", "P-12",
                  {"itemised_consultation_fee": False, "patient_category": "non_citizen"})
        else:
            exempt(d, n, CORRECT, "healthcare_consultation", "P-12")
    else:
        exempt(d, n, CORRECT, "staff_education_fees", "P-16", {"education_fee_item": d.r.choice(["books", "uniform"])})


def mix_line(d, n: int) -> None:
    """A line whose outcome differs from the others: water supply (not a taxable service, MS-1), else a taxed plain
    service or goods; from a foreign supplier, imported goods (no SST on the invoice, MG-1) or an imported service."""
    outcomes = {(t, b) for _, t, b in d.built.planted.lines}
    if foreign(d):
        if (T.NO_SST.value, "MG-1") not in outcomes:
            _mg1(d, n, CORRECT)
        else:
            _ms8(d, n, CORRECT)
        return
    if (T.NO_SST.value, "MS-1") not in outcomes:
        exempt(d, n, CORRECT, "water_supply", "MS-1")
    elif registered(d.supplier, "service", d.day):
        taxed(d, n, pick(d, SERVICES_8 + SERVICES_6, "plain service"), "MS-2")
    else:
        raise CannotPlant("no line that differs")


def plant_branch(d, n: int, name: str, side: str) -> None:
    fn = BRANCHES.get(name)
    if fn is None:
        raise CannotPlant(f"no branch recipe {name}")
    fn(d, n, side)


# -- helpers the generation part uses -------------------------------------------------------------------------------


def _ext(d, n: int) -> dict:
    return next(e for e in d.invoice["einvoice"]["lines"] if e["line_no"] == n)


def past_relaxation(supplier: dict, day: date) -> bool:
    """The supplier must issue a validated e-invoice on the day (ME-1): in a phase and past its relaxation period."""
    status = (supplier.get("tax_facts") or {}).get("einvoice")
    if not status:
        return False
    from .models import MyEinvoiceStatus
    s = MyEinvoiceStatus.model_validate(status)
    if tl.exempt_band(s.turnover_band):
        return False
    start = tl.implementation_date(s)
    end = tl.relaxation_end(start, s.turnover_band) if start else None
    return end is not None and day > end


def registered(supplier: dict, kind: str, day: date) -> bool:
    return any(x["scheme"] == "MY_SST" and x.get("type") == kind and date.fromisoformat(x["valid_from"]) <= day
               for x in supplier.get("tax_registrations", []))


def is_manufacturer(supplier: dict) -> bool:
    return bool((supplier.get("tax_facts") or {}).get("is_manufacturer"))


def phase_one(supplier: dict) -> bool:
    status = (supplier.get("tax_facts") or {}).get("einvoice") or {}
    return status.get("turnover_band") == "above_100m" and status.get("turnover_basis") != "new_business"


def supplier_fits(supplier: dict, needs: set[str], day: date) -> bool:
    if "service" in needs and not registered(supplier, "service", day):
        return False
    if "goods" in needs and not (registered(supplier, "sales", day) and is_manufacturer(supplier)):
        return False
    if "phase" in needs and not past_relaxation(supplier, day):
        return False
    if "phase1" in needs and not phase_one(supplier):
        return False
    return True


def plant(d, n: int, rule: str, form: str) -> None:
    fn = RECIPES.get(rule)
    if fn is None:
        raise CannotPlant(f"no recipe for {rule}")
    fn(d, n, form)


