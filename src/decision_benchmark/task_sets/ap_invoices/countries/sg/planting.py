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

SG_COMPANY_KINDS = ("plain", "partial", "receipts")
"""Fully taxable; partially exempt (de minimis not met: SG-9, and reverse charge, SG-8); fully taxable with
non-business receipts (reverse charge, SG-8)."""


def company_facts(kind: str) -> dict:
    return {"country": "SG", "input_tax_status": "partially_exempt" if kind == "partial" else "fully_taxable",
            "non_business_receipts": kind == "receipts"}


def full_credit(company: dict) -> bool:
    """The buyer is entitled to full input tax credit (SG-8): fully taxable, no non-business receipts."""
    f = company.get("tax_facts") or {}
    return f.get("input_tax_status") != "partially_exempt" and not f.get("non_business_receipts")


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
)
"""The split's suppliers of each kind, shared by its Singapore companies: a supplier not registered for GST (SG-4);
foreign suppliers without a Singapore branch: without a certificate of residence (domestic withholding rates), resident
in Malaysia with one (the treaty's confirmed royalty and technical-fee rates), and resident where the treaty rows are
not confirmed (WH-5 HAND_OVER, planting limit 5)."""


def registered(supplier: dict, day: date) -> bool:
    return any(x["scheme"] == "SG_GST" and date.fromisoformat(x["valid_from"]) <= day
               for x in supplier.get("tax_registrations", []))


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
    need_registered(d, "SG-1")
    if partially_exempt(d.cw.company):
        raise CannotPlant("SG-1: a partially exempt buyer's claim is SG-9")
    standard(d, n, d.r.choice(PLAIN_SERVICES))


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
    over = d.r.random() < 0.5
    rate = rate_on(d.day) + (1 if over else -1)
    d.set_line(n, c, rate, ext(True))
    if over:
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-3", (Code.WRONG_TAX_RATE.value,))
    else:
        d.expect(n, T.GST_UNDERCHARGED.value, "SG-3", (Code.WRONG_TAX_RATE.value,))


@recipe("SG-4")
def _sg4(d, n, form):
    """A supplier not registered for GST: it can't charge GST; every line of its invoice is decided by SG-4."""
    if registered(d.supplier, d.day):
        raise CannotPlant("SG-4 needs a supplier not registered for GST")
    if foreign(d):
        # A foreign supplier isn't registered for GST here: GST on its invoice is wrongly charged (SG-4).
        if form != PROBLEM:
            raise CannotPlant("SG-4 correct needs a domestic supplier (a foreign line without GST is SG-8)")
        c = d.r.choice(["business_consultancy", "it_services"])
        d.set_line(n, c, rate_on(d.day), ext(True))
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-4", (Code.SUPPLIER_NOT_TAX_REGISTERED.value,))
        for k, x in enumerate(d.invoice["lines"], 1):       # SG-4 decides every line of the invoice
            if k != n:
                charged = Decimal(x["tax_rate"]) > 0
                d.expect(k, (T.GST_WRONGLY_CHARGED if charged else T.NO_GST).value, "SG-4")
        return
    c = d.r.choice(["hand_tools", "business_consultancy"])
    if form == PROBLEM:
        d.set_line(n, c, rate_on(d.day), ext(True))
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-4", (Code.SUPPLIER_NOT_TAX_REGISTERED.value,))
    else:
        no_gst(d, n, c, "SG-4")


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
    rate = rate_on(d.day) if form == PROBLEM else Decimal(0)
    d.set_line(n, c, rate, ext(form == PROBLEM))
    _above_threshold(d, n)
    if form == PROBLEM:
        d.expect(n, T.GST_WRONGLY_CHARGED.value, "SG-7", (Code.TAX_SHOULD_BE_EXEMPT.value,))
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


@recipe("SG-8")
def _sg8(d, n, form):
    """An imported service: no GST on the invoice; the buyer reverse-charges it unless entitled to full credit."""
    need_foreign(d, "SG-8")
    no_gst(d, n, d.r.choice(["business_consultancy", "it_services"]), "SG-8", actions=_reverse(d))
    if not full_credit(d.cw.company):
        d.planted_line(n, T.REVERSE_CHARGE.value, "SG-8")


def _reverse(d) -> tuple:
    return () if full_credit(d.cw.company) else (REVERSE_ACTION,)


@recipe("SG-9")
def _sg9(d, n, form):
    need_registered(d, "SG-9")
    if not partially_exempt(d.cw.company):
        raise CannotPlant("SG-9 needs a partially exempt buyer")
    attribution = d.r.choice(["exempt", "residual", "taxable"])
    standard(d, n, d.r.choice(PLAIN_SERVICES), "SG-9", facts={"purchase_attribution": attribution})
    code = {"exempt": T.NOT_CLAIMABLE_EXEMPT_USE, "residual": T.RESIDUAL_APPORTIONED, "taxable": T.CLAIMABLE}
    d.planted_line(n, code[attribution].value, "SG-9")


@recipe("SG-10")
def _sg10(d, n, form):
    need_registered(d, "SG-10")
    c = d.r.choice(["club_subscription", "staff_family_gifts", "lucky_draw_tickets", "director_benefits", "csr_items",
                    "golf_club_fees", "private_club_services"])
    d.set_line(n, c, rate_on(d.day), ext(True))
    d.expect(n, T.NOT_CLAIMABLE_DISALLOWED.value, "SG-10")


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
    its attribution (taxable here), and SG-9 decides it."""
    if not partially_exempt(d.cw.company) or foreign(d):
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
