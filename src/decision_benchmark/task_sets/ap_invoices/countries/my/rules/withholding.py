"""Malaysian withholding tax on payments to non-residents: WH-1 to WH-4 (rule sheet v0.10 §4A).

Sources: LHDN "Withholding tax" page; Public Ruling 10/2019; Income Tax (Exemption) (No. 9) Order 2017; LHDN
"Double Tax Agreements Withholding Tax Rates" (treaties.py). Withholding doesn't change the line's tax treatment:
it is a buyer action, WITHHOLD_TAX with its rate, basis and base amount. A treaty rate needs the payee's
certificate of residence; without it the domestic rate applies. An open question here leaves the tax treatment set
(NotSettled with tax_related False).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....findings import NotSettled
from ....models import BuyerAction
from ....models.answer import WITHHOLD_TAX
from ....models.common import CENT, ZERO
from .. import treaties
from .context import LineCtx

OUTSIDE_CHARGEABLE_FROM = date(2017, 1, 17)
"""Public Ruling 10/2019 para 5.2: from 17.1.2017 (Finance Act 2017 s6) s4A (i) and (ii) income is chargeable
whether the services are performed in or outside Malaysia; before, services performed outside were not."""
OUTSIDE_EXEMPT_FROM = date(2017, 9, 6)
"""Services under s4A (i) and (ii) performed outside Malaysia are exempt (Exemption (No. 9) Order 2017, deemed in
operation on 6 September 2017). Public Ruling 10/2019 §21: the period of performance decides, whatever the contract
or payment date (every row of its table)."""
NO_GROSS_UP_FROM = date(2018, 12, 5)
"""Public Ruling 10/2019 para 12.1 note: where the payer bears the s109B tax, it is computed on the gross amount paid
(no regrossing) if the payment date agreed in the contract is on or after 5.12.2018."""
CONTRACTOR_RATE, EMPLOYEES_RATE = Decimal(10), Decimal(3)
"""WH-3: s107A, 10% for the contractor and 3% for its employees."""
SPECIAL_CLASSES_RATE = Decimal(10)
OTHER_GAIN_RATE, ENTERTAINER_RATE = Decimal(10), Decimal(15)
WHOLE_SHARE = Decimal(1)


def _not_settled(basis: str, reason: str) -> NotSettled:
    return NotSettled(basis, reason, tax_related=False)


def _withhold(rate: Decimal, basis: str, base: Decimal) -> BuyerAction:
    return BuyerAction(action=WITHHOLD_TAX, rate=rate, basis=basis, base_amount=base.quantize(CENT))


def _certified(ctx: LineCtx, basis: str) -> bool:
    held = any(c.country == ctx.supplier.country and c.valid_on(ctx.day) for c in ctx.residence_certificates)
    return bool(ctx.fact("certificate_of_residence", held, basis))


def _rate(ctx: LineCtx, basis: str, domestic: Decimal, column: str) -> Decimal:
    """The domestic rate, or the lower treaty rate with a certificate of residence (LHDN notes i, iii, iv)."""
    if not _certified(ctx, basis):
        return domestic
    row = treaties.row(ctx.supplier.country, ctx.day)
    if row is None:
        return domestic
    return min(domestic, getattr(row, column).for_payer(ctx.cf.industrial_undertaking))


def _s109b(ctx: LineCtx, rate: Decimal, base: Decimal) -> BuyerAction:
    """A WH-2 (s109B) withholding. Before 5 Dec 2018, where the payer bears the tax, the base is regrossed
    (base x 100 / (100 - rate)); the agreed payment date is the invoice's due date, never before the invoice date."""
    if ctx.day >= NO_GROSS_UP_FROM:
        return _withhold(rate, "WH-2", base)          # paid on or after the invoice date
    due = ctx.invoice.due_date if ctx.invoice is not None else None
    if due is not None and due >= NO_GROSS_UP_FROM:
        return _withhold(rate, "WH-2", base)
    try:
        borne = ctx.fact("tax_borne_by_payer", None, "WH-2")
    except NotSettled as ns:
        raise _not_settled(ns.basis, ns.reason) from None
    if borne is None:
        raise _not_settled("WH-2", "before 5 Dec 2018: whether the payer bears the tax is not shown")
    if borne:
        if due is None:
            raise _not_settled("WH-2", "the payer bears the tax and the agreed payment date is not shown")
        base = base * Decimal(100) / (Decimal(100) - rate)
    return _withhold(rate, "WH-2", base)


def _outside_chargeable(ctx: LineCtx) -> bool:
    """Services under s4A (i), (ii) performed outside Malaysia are chargeable only when performed from 17 Jan 2017
    to 5 Sep 2017 (Public Ruling 10/2019 para 5.2, §21). The service period shows when; a period across either date
    has no apportionment fact, so it is not settled."""
    start = ctx.fact("service_period_start", None, "WH-2")      # inside _special_services' try: a null fact
    end = ctx.fact("service_period_end", None, "WH-2")          # is re-raised as non-tax
    if start is None or end is None:
        raise _not_settled("WH-2", "services performed outside Malaysia: the period of performance is not shown")
    sides = {OUTSIDE_CHARGEABLE_FROM <= d < OUTSIDE_EXEMPT_FROM for d in (start, end)}
    if len(sides) > 1 or (start < OUTSIDE_CHARGEABLE_FROM and end >= OUTSIDE_EXEMPT_FROM):
        raise _not_settled("WH-2", "the period of performance spans 17 Jan 2017 or 6 Sep 2017")
    return sides == {True}


def _special_services(ctx: LineCtx, domestic: Decimal, gross: Decimal) -> tuple[BuyerAction, ...]:
    """WH-2 (i), (ii): 10% of the Malaysian part (services performed outside Malaysia chargeable only from 17 Jan to
    5 Sep 2017; mixed contracts apportioned; hotel accommodation left out of the reimbursed gross)."""
    try:
        place = ctx.need("place_of_performance", "WH-2")
        share = WHOLE_SHARE
        if place == "outside":
            if not _outside_chargeable(ctx):
                return ()
            return (_s109b(ctx, _rate(ctx, "WH-2", domestic, "technical_fees"), gross),)
        if place == "mixed":
            share = ctx.need("in_country_share", "WH-2")
    except NotSettled as ns:
        raise _not_settled(ns.basis, ns.reason) from None
    hotel = ctx.fact("hotel_reimbursement", ZERO, "WH-2")
    return (_s109b(ctx, _rate(ctx, "WH-2", domestic, "technical_fees"), (gross - hotel) * share),)


def actions(ctx: LineCtx) -> tuple[BuyerAction, ...]:
    if not ctx.foreign_supplier:
        return ()
    nature = ctx.fact("payment_nature", "none", "WH-1")
    if nature in ("none", "freight"):
        return ()                       # freight alone is outside s4A (iii)
    domestic = treaties.table().domestic
    gross = ctx.net
    if nature == "interest":
        return (_withhold(_rate(ctx, "WH-1", domestic.interest, "interest"), "WH-1", gross),)
    if nature == "royalty":
        return (_withhold(_rate(ctx, "WH-1", domestic.royalties, "royalties"), "WH-1", gross),)
    if nature in ("services_on_property", "technical_advice"):
        return _special_services(ctx, domestic.technical_fees, gross)
    if nature == "movable_property_rent":
        # s4A (iii) applies wherever the property is used. Many treaties put the use of industrial, commercial or
        # scientific equipment inside the royalty definition (LHDN note v): with a certificate, HAND_OVER until the
        # treaty's royalty definition is read and confirmed; without one, the domestic rate.
        if _certified(ctx, "WH-2") and treaties.row(ctx.supplier.country, ctx.day) is not None:
            raise _not_settled("WH-2", "treaty royalty definition for rent of movable property not read")
        return (_s109b(ctx, SPECIAL_CLASSES_RATE, gross),)
    if nature == "contract_payment":
        pe = ctx.sf.pe_in_country
        if pe is None:
            raise _not_settled("WH-3", "permanent establishment in Malaysia not shown")
        if not pe:
            # s107A applies "instead of s109B" only with a PE or business presence; without one, s109B (WH-2).
            return _special_services(ctx, domestic.technical_fees, gross)
        return (_withhold(CONTRACTOR_RATE, "WH-3", gross), _withhold(EMPLOYEES_RATE, "WH-3", gross))
    if nature == "other_gain":
        return (_withhold(OTHER_GAIN_RATE, "WH-4", gross),)
    if nature == "public_entertainer":
        return (_withhold(ENTERTAINER_RATE, "WH-4", gross),)
    return ()
