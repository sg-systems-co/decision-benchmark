"""Planting the Singapore rules (B1-5): company kinds, the special suppliers the rules need, one recipe per rule (SG-1
to SG-12, WH-5), the hand-over the unconfirmed treaty rows give (planting limit 5), the dated branch of 1 Jan 2024 and
the line that makes an invoice mixed.

As in the Malaysian pack (countries/my/planting.py): a recipe sets one line so the rule decides it, states the facts it
reads, and says what the engine must find, from the rule sheet for the situation built.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from ...codes import Code
from ...generator.country import CannotPlant, SpecialSupplier
from ...models.answer import WITHHOLD_TAX
from ...generator.entities import catalog, day_between, money
from . import treaties
from .models import SgTaxTreatment as T
from .rules.customer_accounting import ACCOUNT_CUSTOMER_ACCOUNTING, PRESCRIBED_THRESHOLD
from .rules.gst import rate_on
from .rules.reverse_charge import ACCOUNT_REVERSE_CHARGE
from .rules.withholding import DOMESTIC

PROBLEM, CORRECT = "problem", "correct"
REVERSE_ACTION = (ACCOUNT_REVERSE_CHARGE, None, None)
CUSTOMER_ACTION = (ACCOUNT_CUSTOMER_ACCOUNTING, None, None)

# -- companies -----------------------------------------------------------------------------------------------------

SG_COMPANY_KINDS = ("plain", "partial", "receipts", "de_minimis", "group", "group_dm")
"""Fully taxable; partially exempt (de minimis not met: SG-9, and reverse charge, SG-8); fully taxable with
non-business receipts (reverse charge, SG-8); partially exempt but meeting the de minimis rule (claims all its input
tax: SG-9; no reverse charge on its own, SG-8); fully taxable, in a GST group that is not entitled to full input tax
credit (reverse charge, SG-8); meeting the de minimis rule, in such a group (reverse charge all the same, SG-8)."""
SG_STATUS = {"partial": "partially_exempt", "de_minimis": "de_minimis_met", "group_dm": "de_minimis_met"}
SG_GROUP_KINDS = ("group", "group_dm")


def company_facts(kind: str) -> dict:
    facts = {"country": "SG", "input_tax_status": SG_STATUS.get(kind, "fully_taxable"),
             "non_business_receipts": kind == "receipts"}
    if kind in SG_GROUP_KINDS:
        facts |= {"in_gst_group": True, "gst_group_full_credit": False}
    return facts


def full_credit(company: dict) -> bool:
    """The buyer is entitled to full input tax credit (SG-8): not partially exempt (meeting the de minimis rule counts
    as entitled), no non-business receipts, and not in a GST group without full credit."""
    f = company.get("tax_facts") or {}
    if f.get("input_tax_status") == "partially_exempt" or f.get("non_business_receipts"):
        return False
    return not f.get("in_gst_group") or bool(f.get("gst_group_full_credit"))


def de_minimis(company: dict) -> bool:
    return (company.get("tax_facts") or {}).get("input_tax_status") == "de_minimis_met"


def partially_exempt(company: dict) -> bool:
    return (company.get("tax_facts") or {}).get("input_tax_status") == "partially_exempt"


# -- special suppliers ---------------------------------------------------------------------------------------------

NO_BRANCH = {"has_branch_receiving": False}
SG_SPECIAL_SUPPLIERS = (
    SpecialSupplier("general", ("industrial_valves", "bearings", "hand_tools", "advertising", "business_consultancy",
                                "security_guards")),
    SpecialSupplier("sg_unregistered", ("hand_tools", "business_consultancy"), registered_for=()),
    SpecialSupplier("sg_foreign", ("business_consultancy", "it_services"), foreign=True, homes=("US", "CN", "IN"),
                    facts=dict(NO_BRANCH)),
    SpecialSupplier("sg_foreign_my", ("business_consultancy", "it_services"), foreign=True, homes=("MY",),
                    residence=True, facts=dict(NO_BRANCH)),
    SpecialSupplier("sg_foreign_unconfirmed", ("business_consultancy", "it_services"), foreign=True,
                    homes=("JP", "CN", "GB"), residence=True, facts=dict(NO_BRANCH)),
    SpecialSupplier("sg_ovr", ("it_services",), foreign=True, homes=("US", "GB", "IN"), registered_for=("service",),
                    registration_type="ovr", facts=dict(NO_BRANCH)),
)
"""The split's suppliers of each kind, shared by its Singapore companies: a supplier not registered for GST (SG-4);
foreign suppliers without a Singapore branch: without a certificate of residence (domestic withholding rates), resident
in Malaysia with one (the treaty's confirmed royalty and technical-fee rates), and resident where the treaty rows are
not confirmed (WH-5 HAND_OVER, planting limit 5); overseas vendors registered under the OVR regime, which may not
charge GST to a GST-registered buyer (SG-4)."""


def registered(supplier: dict, day: date) -> bool:
    """Registered for GST locally on the day (an OVR registration doesn't count: SG-4)."""
    return any(x["scheme"] == "SG_GST" and x.get("type", "local") == "local"
               and date.fromisoformat(x["valid_from"]) <= day for x in supplier.get("tax_registrations", []))


def ovr(supplier: dict) -> bool:
    return any(x["scheme"] == "SG_GST" and x.get("type") == "ovr" for x in supplier.get("tax_registrations", []))


def supplier_fits(supplier: dict, needs: set[str], day: date) -> bool:
    return "gst" not in needs or registered(supplier, day)


# -- lines ---------------------------------------------------------------------------------------------------------


def ext(charged: bool, category: str = "SR") -> dict:
    return {"tax_category": category if charged else ("ZR" if category == "ZR" else "NA")}


def foreign(d) -> bool:
    return d.supplier["country"] != "SG"


def need_domestic(d, rule):
    if foreign(d):
        raise CannotPlant(f"{rule} needs a domestic supplier")


def need_foreign(d, rule):
    if not foreign(d):
        raise CannotPlant(f"{rule} needs a foreign supplier")


def need_registered(d, rule):
    need_domestic(d, rule)
    if not registered(d.supplier, d.day):
        raise CannotPlant(f"{rule} needs a GST-registered supplier")


PLAIN_SERVICES = ["advertising", "security_guards", "business_consultancy", "legal_services", "audit_accounting",
                  "engineering_consultancy", "it_services", "management_services"]
"""Standard-rated services with no Regulation 26/27 class and no catalog facts."""


def standard(d, n: int, category: str, basis: str = "SG-1", rate: Decimal | None = None, facts=None) -> None:
    rate = rate_on(d.day) if rate is None else rate
    d.set_line(n, category, rate, ext(True))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    d.expect(n, T.CLAIMABLE.value, basis)


def wrongly(d, n, category, basis, finding=Code.TAX_SHOULD_BE_EXEMPT.value, cat="SR", facts=None):
    d.set_line(n, category, rate_on(d.day), ext(True, cat))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    d.expect(n, T.GST_WRONGLY_CHARGED.value, basis, (finding,))


def no_gst(d, n, category, basis, cat="NA", facts=None, actions=()):
    d.set_line(n, category, Decimal(0), ext(False, cat))
    for fact, value in (facts or {}).items():
        d.state(n, fact, value)
    d.expect(n, T.NO_GST.value, basis, (), actions)


# -- the recipes ---------------------------------------------------------------------------------------------------

Recipe = Callable[..., None]
SG_RECIPES: dict[str, Recipe] = {}


def recipe(rule: str):
    def wrap(fn: Recipe) -> Recipe:
        SG_RECIPES[rule] = fn
        return fn
    return wrap


@recipe("SG-1")
def _sg1(d, n, form):
    """A claimable line, or one bought for no business purpose (not claimable, SG-1 condition 1), in turn."""
    need_registered(d, "SG-1")
    if partially_exempt(d.cw.company):
        raise CannotPlant("SG-1: a partially exempt buyer's claim is SG-9")
    if d.turn("SG-1", ["claim", "not_business"]) == "claim":
        standard(d, n, d.r.choice(PLAIN_SERVICES))
        return
    d.set_line(n, d.r.choice(["hand_tools", "it_services", "business_consultancy"]), rate_on(d.day), ext(True))
    d.state(n, "business_purpose", False)
    d.expect(n, T.NOT_CLAIMABLE_DISALLOWED.value, "SG-1")


@recipe("SG-2")
def _sg2(d, n, form):
    """An invalid tax invoice: line n carries GST; the invalid-invoice family removes a particular, and every line
    with GST then can't be claimed (SG-2)."""
    need_registered(d, "SG-2")
    standard(d, n, d.r.choice(PLAIN_SERVICES))


@recipe("SG-3")
def _sg3(d, n, form):
    need_registered(d, "SG-3")
    c = d.r.choice(PLAIN_SERVICES)
    if form == CORRECT:
        # Performed in December 2023, invoiced in early 2024: the supply spans the change, the old rate is allowed.
        if not date(2024, 1, 1) <= d.day <= date(2024, 3, 31):
            raise CannotPlant("SG-3 correct needs an invoice in Jan-Mar 2024")
        performed = day_between(d.r, date(2023, 12, 1), date(2023, 12, 31))
        standard(d, n, c, "SG-3", Decimal(8), {"delivery_date": performed})
        return
    over = d.turn("SG-3", ["over", "under"]) == "over"
    rate = rate_on(d.day) + (1 if over else -1)
    d.set_line(n, c, rate, ext(True))
    if over:
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-3", (Code.WRONG_TAX_RATE.value,))
    else:
        d.expect(n, T.GST_UNDERCHARGED.value, "SG-3", (Code.WRONG_TAX_RATE.value,))


SG4_SUPPLIERS = ("not_registered", "number_mismatch", "ovr")
"""The suppliers not entitled to charge GST (SG-4), the problem form's pools in turn: not registered; registered, but
the GST number the invoice prints doesn't match the registration; an OVR-registered overseas vendor charging a
GST-registered buyer (every Singapore buyer is). A registration that ended before the invoice date is the engine's
not-registered path (no registration on the day)."""


@recipe("SG-4")
def _sg4(d, n, form):
    """A supplier not entitled to charge GST: GST on its invoice is wrongly charged, and SG-4 decides every line of
    it. The correct form: a supplier not registered for GST charges none."""
    if foreign(d) and ovr(d.supplier):
        if form != PROBLEM:
            raise CannotPlant("SG-4 correct needs a supplier not registered (an OVR vendor's line without GST is SG-8)")
        d.set_line(n, "it_services", rate_on(d.day), ext(True))
        _whole_invoice(d, n, Code.OVR_GST_CHARGED_TO_REGISTERED_BUYER.value)
        return
    if registered(d.supplier, d.day):
        if form != PROBLEM or foreign(d):
            raise CannotPlant("SG-4 needs a supplier not entitled to charge GST")
        d.set_line(n, d.r.choice(PLAIN_SERVICES), rate_on(d.day), ext(True))
        d.invoice["einvoice"]["supplier_gst_no"] = _other_gst_no(d.invoice["einvoice"]["supplier_gst_no"])
        _whole_invoice(d, n, Code.SUPPLIER_NOT_TAX_REGISTERED.value)
        return
    if foreign(d):
        # A foreign supplier isn't registered for GST here: GST on its invoice is wrongly charged (SG-4).
        if form != PROBLEM:
            raise CannotPlant("SG-4 correct needs a domestic supplier (a foreign line without GST is SG-8)")
        d.set_line(n, d.r.choice(["business_consultancy", "it_services"]), rate_on(d.day), ext(True))
        _whole_invoice(d, n, Code.SUPPLIER_NOT_TAX_REGISTERED.value)
        return
    c = d.r.choice(["hand_tools", "business_consultancy"])
    if form == PROBLEM:
        d.set_line(n, c, rate_on(d.day), ext(True))
        _whole_invoice(d, n, Code.SUPPLIER_NOT_TAX_REGISTERED.value)
    else:
        no_gst(d, n, c, "SG-4")


def _whole_invoice(d, n: int, code: str) -> None:
    """GST on line n wrongly charged (finding code); SG-4 decides every other line of the invoice too, a line without
    GST included (the last other line carries none: an exempt lease from a registered supplier)."""
    d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-4", (code,))
    others = [k for k in range(1, len(d.invoice["lines"]) + 1) if k != n]
    if others and all(Decimal(d.line(k)["tax_rate"]) > 0 for k in others):
        d.set_line(others[-1], "residential_lease_sg", Decimal(0), ext(False, "ES"))
    for k, x in enumerate(d.invoice["lines"], 1):
        if k != n:
            charged = Decimal(x["tax_rate"]) > 0
            d.expect(k, (T.GST_WRONGLY_CHARGED if charged else T.NO_GST).value, "SG-4")


def _other_gst_no(number: str) -> str:
    """A GST number of the same form that isn't the supplier's: its digits shifted by one."""
    return "".join(str((int(ch) + 1) % 10) if ch.isdigit() else ch for ch in number)


@recipe("SG-5")
def _sg5(d, n, form):
    need_registered(d, "SG-5")
    if form == PROBLEM:
        wrongly(d, n, "residential_lease_sg", "SG-5", cat="SR")
    else:
        no_gst(d, n, "residential_lease_sg", "SG-5", cat="ES")


@recipe("SG-6")
def _sg6(d, n, form):
    need_registered(d, "SG-6")
    if form == PROBLEM:
        wrongly(d, n, "international_freight_sg", "SG-6", cat="SR")
    else:
        no_gst(d, n, "international_freight_sg", "SG-6", cat="ZR")


@recipe("SG-7")
def _sg7(d, n, form):
    """Prescribed goods above S$10,000 to a GST-registered buyer: customer accounting."""
    need_registered(d, "SG-7")
    c = d.r.choice(["mobile_phones", "memory_cards", "packaged_software"])
    # The problem form in turn: GST charged anyway, or no GST but no customer accounting statement on the invoice.
    charged = form == PROBLEM and d.turn("SG-7", ["charged", "no_statement"]) == "charged"
    rate = rate_on(d.day) if charged else Decimal(0)
    d.set_line(n, c, rate, ext(charged))
    _above_threshold(d, n)
    if charged:
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-7", (Code.TAX_SHOULD_BE_EXEMPT.value,))
    elif form == PROBLEM:
        d.expect(n, T.NOT_CLAIMABLE_INVALID_INVOICE.value, "SG-7", (Code.INVALID_TAX_INVOICE.value,))
    else:
        d.invoice["einvoice"]["customer_accounting_statement"] = True
        d.expect(n, T.CUSTOMER_ACCOUNTING.value, "SG-7", (), (CUSTOMER_ACTION,))


def _above_threshold(d, n: int) -> None:
    """The line's value well above S$10,000 (whole units at a plausible unit price)."""
    x = d.line(n)
    unit = Decimal(d.r.randrange(400, 1200))
    qty = int(PRESCRIBED_THRESHOLD / unit) + d.r.randint(2, 20)
    x["unit_price"], x["qty"] = money(unit), qty
    if d.po is not None:
        d.po["lines"][n - 1].update(unit_price=money(unit), qty=qty)
    if d.gr is not None:
        d.gr["lines"][n - 1]["qty_received"] = qty


SG8_GOODS = ["hand_tools", "bearings", "industrial_valves"]
"""Goods an overseas supplier sells (no Regulation 26/27 class, no catalog facts)."""


@recipe("SG-8")
def _sg8(d, n, form):
    """From an overseas supplier, in turn: an imported service, low-value goods (both reverse-charged by a buyer not
    entitled to full credit, from 1 Jan 2020 and 1 Jan 2023), or other imported goods (GST paid at import: NO_GST)."""
    need_foreign(d, "SG-8")
    # In turn for each kind of buyer (entitled to full credit or not), so both meet each kind of import.
    kind = d.turn(f"SG-8 {full_credit(d.cw.company)}", ["service", "low_value_goods", "goods"])
    if kind == "service":
        no_gst(d, n, d.r.choice(["business_consultancy", "it_services"]), "SG-8", actions=_reverse(d))
    elif kind == "low_value_goods":
        no_gst(d, n, d.r.choice(SG8_GOODS), "SG-8", facts={"low_value_goods": True}, actions=_reverse(d))
        _low_value(d, n)
    else:
        no_gst(d, n, d.r.choice(SG8_GOODS), "SG-8")
        return
    if not full_credit(d.cw.company):
        d.planted_line(n, T.REVERSE_CHARGE.value, "SG-8")


def _low_value(d, n: int) -> None:
    """A low-value goods line: a few units at a low price."""
    x = d.line(n)
    x["unit_price"], x["qty"] = money(Decimal(d.r.randrange(20, 120))), d.r.randint(1, 3)
    if d.po is not None:
        d.po["lines"][n - 1].update(unit_price=x["unit_price"], qty=x["qty"])
    if d.gr is not None:
        d.gr["lines"][n - 1]["qty_received"] = x["qty"]


def _reverse(d) -> tuple:
    return () if full_credit(d.cw.company) else (REVERSE_ACTION,)


@recipe("SG-9")
def _sg9(d, n, form):
    need_registered(d, "SG-9")
    if not partially_exempt(d.cw.company):
        raise CannotPlant("SG-9 needs a partially exempt buyer")
    attribution = d.turn("SG-9", ["exempt", "residual", "taxable"])
    standard(d, n, d.r.choice(PLAIN_SERVICES), "SG-9", facts={"purchase_attribution": attribution})
    code = {"exempt": T.NOT_CLAIMABLE_EXEMPT_USE, "residual": T.RESIDUAL_APPORTIONED, "taxable": T.CLAIMABLE}
    d.planted_line(n, code[attribution].value, "SG-9")


SG10_ALWAYS = ["club_subscription", "staff_family_gifts", "lucky_draw_tickets", "director_benefits", "csr_items",
               "golf_club_fees", "private_club_services"]
"""Regulation 26/27 classes with no exception: club fees, family benefits, betting, directors' benefits, CSR."""
MOTOR_CARS = ["company_car_leasing", "vehicle_servicing", "company_car_tyres_parts"]
SG10_BRANCHES: dict[str, tuple[list[str], dict, bool]] = {
    # branch: (categories, facts stated, claimable)
    "always": (SG10_ALWAYS, {}, False),
    "chauffeured": (["chauffeured_private_hire"], {}, True),
    "third_party_car": (["company_car_leasing"], {"car_used_by_third_party": True}, True),
    "old_service_vehicle": (MOTOR_CARS, {"vehicle_registered_on": date(1996, 5, 14)}, True),
    "newer_service_vehicle": (MOTOR_CARS, {"vehicle_registered_on": date(2019, 8, 2)}, False),
    "motor_car": (MOTOR_CARS, {"vehicle_is_motor_car": True}, False),
    "not_a_motor_car": (MOTOR_CARS, {"vehicle_is_motor_car": False}, True),
    "staff_medical_obligatory": (["staff_medical"], {"staff_medical_obligatory": True}, True),
    "staff_medical_voluntary": (["staff_medical"], {"staff_medical_obligatory": False}, False),
    "insurance_obligatory": (["group_medical_insurance"], {"insurance_obligatory": True}, True),
    "insurance_voluntary": (["group_medical_insurance"], {"insurance_obligatory": False}, False),
}
"""SG-10's branches, in turn: the classes with no exception; the motor-car exceptions (pay-per-trip chauffeured hire from
1 Apr 2022, a car used by a third party from 1 Jan 2023, the Regulation 25(1) exclusions: a business service passenger
vehicle registered before 1 Apr 1998, or a vehicle that isn't a motor car, such as a taxi, a school-transport car or a
goods vehicle); staff medical costs and insurance, claimable when obligatory (Work Injury Compensation Act, a collective
agreement, a work-related health risk under written law). The case window starts after both exception dates."""


@recipe("SG-10")
def _sg10(d, n, form):
    need_registered(d, "SG-10")
    categories, facts, claimable = SG10_BRANCHES[d.turn("SG-10", list(SG10_BRANCHES))]
    d.set_line(n, d.r.choice(categories), rate_on(d.day), ext(True))
    for fact, value in facts.items():
        d.state(n, fact, value)
    d.expect(n, (T.CLAIMABLE if claimable else T.NOT_CLAIMABLE_DISALLOWED).value, "SG-10")


@recipe("SG-11")
def _sg11(d, n, form):
    """A duplicate claim: the slot's duplicate family plants the copy in the ledger; nothing more on the line."""
    need_domestic(d, "SG-11")


@recipe("SG-12")
def _sg12(d, n, form):
    need_registered(d, "SG-12")
    d.set_line(n, d.r.choice(PLAIN_SERVICES), Decimal(0), {"tax_category": None})
    d.expect(n, T.GST_UNDERCHARGED.value, "SG-12", (Code.TAX_UNDERCHARGED.value,))


def _certified(d) -> bool:
    sid = d.built.case["supplier_id"]
    return any(c["supplier_id"] == sid and date.fromisoformat(c["valid_from"]) <= d.day
               for c in d.cw.residence_certificates)


@recipe("WH-5")
def _wh5(d, n, form):
    """A payment to a non-resident without a Singapore branch: withhold at the domestic rate, or the confirmed treaty
    rate with a certificate of residence (royalties, technical fees for work in Singapore)."""
    need_foreign(d, "WH-5")
    certified = _certified(d)
    natures = ["royalty", "technical_or_management_fee"] + ([] if certified else ["interest"])
    nature = d.r.choice(natures)
    category = {"royalty": "software_royalty", "technical_or_management_fee": "technical_services_from_abroad",
                "interest": "loan_interest_non_resident"}[nature]
    rate = DOMESTIC[nature]
    if certified:
        row = treaties.treaty(d.supplier["country"], d.day)
        article = None if row is None else getattr(row, "royalties" if nature == "royalty" else "technical_fees")
        if row is not None:
            if article is None or not article.confirmed:
                raise CannotPlant("WH-5 settled needs a confirmed treaty row")
            rate = min(rate, article.rate)
    facts = {"place_of_performance": "in_country"} if nature == "technical_or_management_fee" else {}
    no_gst(d, n, category, "SG-8", facts=facts, actions=_reverse(d) + ((WITHHOLD_TAX, str(rate), "WH-5"),))
    if not full_credit(d.cw.company):
        d.planted_line(n, T.REVERSE_CHARGE.value, "SG-8")


def unconfirmed_treaty(d, n: int) -> None:
    """Planting limit 5: a royalty to a payee holding a certificate of residence where the treaty row isn't
    confirmed: HAND_OVER (WH-5), the line's GST treatment unchanged."""
    need_foreign(d, "unconfirmed treaty")
    if not _certified(d):
        raise CannotPlant("the unconfirmed-treaty hand-over needs a certificate of residence")
    row = treaties.treaty(d.supplier["country"], d.day)
    if row is None or row.royalties.confirmed:
        raise CannotPlant("the unconfirmed-treaty hand-over needs an unconfirmed royalty row")
    no_gst(d, n, "software_royalty", "SG-8", actions=_reverse(d))
    if not full_credit(d.cw.company):
        d.planted_line(n, T.REVERSE_CHARGE.value, "SG-8")


# -- the 1 Jan 2024 branch, partial exemption, mixed lines --------------------------------------------------------

SG_BRANCHES: dict[str, Recipe] = {}


def _branch_rate(d, n, side):
    """1 Jan 2024: GST goes from 8% to 9% (SG-3); a line wholly on one side takes that side's rate."""
    need_registered(d, "gst_rate_2024")
    if partially_exempt(d.cw.company):
        raise CannotPlant("gst_rate_2024: the claim of a partially exempt buyer is SG-9")
    standard(d, n, d.r.choice(PLAIN_SERVICES))


SG_BRANCHES["gst_rate_2024"] = _branch_rate


def finish(d) -> None:
    """A partially exempt buyer attributes each claimable purchase (SG-9): every line it would claim under SG-1 states
    its attribution (taxable here), and SG-9 decides it. A buyer meeting the de minimis rule states what each purchase
    is for too (in turn: exempt, residual or taxable supplies), but claims all its input tax: the line stays claimable
    under SG-1 whatever the attribution (sheet SG-9: not claimable "unless the de minimis rule is met")."""
    if foreign(d):
        return
    if de_minimis(d.cw.company):
        for n, (_, treatment, basis) in enumerate(d.built.planted.lines, 1):
            if treatment == T.CLAIMABLE.value and basis == "SG-1":
                d.state(n, "purchase_attribution", d.turn("SG-9 de minimis", ["exempt", "residual", "taxable"]))
        return
    if not partially_exempt(d.cw.company):
        return
    for n, (_, treatment, basis) in enumerate(d.built.planted.lines, 1):
        if treatment == T.CLAIMABLE.value and basis in ("SG-1", "SG-3"):
            d.state(n, "purchase_attribution", "taxable")
            if basis == "SG-1":                        # SG-3 keeps its basis: the rate check decides the line
                d.planted_line(n, treatment, "SG-9")


def mix_line(d, n: int) -> None:
    """A line whose outcome differs from the clean ones: an exempt residential lease (SG-5)."""
    need_registered(d, "mixed")
    no_gst(d, n, "residential_lease_sg", "SG-5", cat="ES")


def plant(d, n: int, rule: str, form: str) -> None:
    fn = SG_RECIPES.get(rule)
    if fn is None:
        raise CannotPlant(f"no recipe for {rule}")
    fn(d, n, form)


__all__ = ["SG_COMPANY_KINDS", "SG_RECIPES", "SG_SPECIAL_SUPPLIERS", "company_facts", "finish", "mix_line", "plant",
           "unconfirmed_treaty"]


# -- SG-2: the tax-invoice particular an invalid invoice misses -----------------------------------------------------

SG2_PARTICULARS = ("supplier_name", "supplier_address", "supplier_gst_no", "by_size", "simplified")
"""In turn (validity.check): the supplier's name, address or GST number; one that turns on the invoice's size (above
S$1,000 including GST: the words "Tax Invoice", the customer's name or the GST amount; up to S$1,000: the GST amount or
a statement that the price includes GST), chosen once the final amounts are known; or a simplified invoice (the lines
brought under S$1,000) that shows neither the GST amount nor such a statement."""
SG2_FULL = ("tax_invoice_wording", "customer_name", "gst_amount")
SG2_PLAIN = ("SG-1", "SG-2", "SG-9")
"""Line bases whose answer doesn't turn on the amounts (a simplified invoice may scale such lines down)."""


def drop_particular(invoice: dict, d=None) -> None:
    which = d.turn("SG-2 particular", list(SG2_PARTICULARS)) if d is not None else "supplier_address"
    if which == "simplified":
        if all(basis in SG2_PLAIN for _, _, basis in d.built.planted.lines):
            _simplified(d)
            d.final.append(lambda: d.invoice["totals"].update(tax=None))
            return
        which = "supplier_address"
    if which == "supplier_name":
        invoice["supplier_block"]["name"] = None
    elif which == "supplier_address":
        invoice["supplier_block"]["address"] = None
    elif which == "supplier_gst_no":
        invoice["einvoice"]["supplier_gst_no"] = None
    else:
        d.final.append(lambda: _drop_by_size(d, d.invoice))


def _simplified(d) -> None:
    """Every line a few units at a low price, the invoice under S$1,000 including GST (PO and receipt follow)."""
    for n, x in enumerate(d.invoice["lines"], 1):
        x["unit_price"], x["qty"] = money(Decimal(d.r.randrange(20, 90))), d.r.randint(1, 3)
        if d.po is not None:
            d.po["lines"][n - 1].update(unit_price=x["unit_price"], qty=x["qty"])
        if d.gr is not None:
            d.gr["lines"][n - 1]["qty_received"] = x["qty"]


def _drop_by_size(d, invoice: dict) -> None:
    from .constants import FULL_TAX_INVOICE_THRESHOLD

    if Decimal(invoice["totals"]["gross"]) <= FULL_TAX_INVOICE_THRESHOLD:
        invoice["totals"]["tax"] = None              # neither the GST amount nor "price includes GST"
        return
    which = d.turn("SG-2 full particular", list(SG2_FULL))
    if which == "tax_invoice_wording":
        invoice["einvoice"]["document_title"] = None
    elif which == "customer_name":
        invoice["buyer_block"]["name"] = None
    else:
        invoice["totals"]["tax"] = None


# -- branch coverage: deciding facts the engine reads on a shared line of code (generator/branches.py) ---------------

def _company(case):
    return case.records.company.tax_facts


def _fact(case, n: int, name: str):
    facts = case.envelope.payload.invoice.lines[n - 1].facts
    f = getattr(facts, name, None) if facts is not None else None
    return f.value if f is not None else None


def _sg8(lr, treatment: str) -> bool:
    return lr is not None and lr.basis == "SG-8" and lr.treatment == treatment


SG_BRANCH_FACTS = (
    ("SG-8", "de_minimis_alone", "a buyer meeting the de minimis rule, in no GST group: entitled to full credit, no "
     "reverse charge (sheet SG-8)",
     lambda c, n, lr: _sg8(lr, "NO_GST") and _company(c).input_tax_status == "de_minimis_met"
     and not _company(c).in_gst_group and (catalog().get(c.envelope.payload.invoice.lines[n - 1].category).kind
                                           == "service" or _fact(c, n, "low_value_goods"))),
    ("SG-8", "group_member", "a fully taxable member of a GST group not entitled to full credit: reverse charge",
     lambda c, n, lr: _sg8(lr, "REVERSE_CHARGE") and _company(c).in_gst_group
     and _company(c).input_tax_status == "fully_taxable"),
    ("SG-8", "group_de_minimis", "a member meeting the de minimis rule, in a GST group not entitled to full credit: "
     "reverse charge all the same", lambda c, n, lr: _sg8(lr, "REVERSE_CHARGE") and _company(c).in_gst_group
     and _company(c).input_tax_status == "de_minimis_met"),
    ("SG-8", "low_value_goods_reverse", "low-value goods to a buyer not entitled to full credit: reverse charge",
     lambda c, n, lr: _sg8(lr, "REVERSE_CHARGE") and _fact(c, n, "low_value_goods") is True),
    ("SG-8", "low_value_goods_full_credit", "low-value goods to a buyer entitled to full credit: no reverse charge",
     lambda c, n, lr: _sg8(lr, "NO_GST") and _fact(c, n, "low_value_goods") is True),
    ("SG-9", "de_minimis_claims_all", "a buyer meeting the de minimis rule claims a purchase for its exempt or mixed "
     "supplies in full (the line stays SG-1)", lambda c, n, lr: lr is not None and lr.basis == "SG-1"
     and lr.treatment == "CLAIMABLE" and _company(c).input_tax_status == "de_minimis_met"
     and _fact(c, n, "purchase_attribution") in ("exempt", "residual")),
)
"""(rule, name, what it is, holds(case, line_no, line_result))."""


def _missing(tax, item: str) -> bool:
    return any(f.code.value == "INVALID_TAX_INVOICE" and item in (f.evidence or {}).get("missing", [])
               for f in tax.findings)


SG_CASE_FACTS = tuple(
    ("SG-2", f"missing {item}", f"a tax invoice without its {item.replace('_', ' ')} (validity.check)",
     lambda c, n, tax, item=item: _missing(tax, item))
    for item in ("supplier_name", "supplier_address", "supplier_gst_no", "tax_invoice_wording", "customer_name",
                 "gst_amount", "gst_amount_or_price_includes_gst_statement")
) + (
    ("SG-2", "foreign currency without SGD amounts", "an invoice in another currency without its SGD totals",
     lambda c, n, tax: any(f.code.value == "FOREIGN_CURRENCY_NO_SGD_AMOUNTS" for f in tax.findings)),
    ("SG-11", "duplicate invoice", "an invoice number already in the ledger (the duplicate check)",
     lambda c, n, tax: any(f.code.value == "DUPLICATE_INVOICE" for f in c.answer.findings)),
    ("SG-11", "near duplicate", "a near-duplicate of a ledger invoice (the duplicate check)",
     lambda c, n, tax: any(f.code.value == "NEAR_DUPLICATE" for f in c.answer.findings)),
)
"""Case-level: (rule, name, what it is, holds(case, None, tax result))."""
