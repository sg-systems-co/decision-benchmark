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

OUTSIDE_EXEMPT_FROM = date(2017, 9, 6)
"""Services under s4A (i) and (ii) performed outside Malaysia are exempt (Exemption (No. 9) Order 2017)."""
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
    row = treaties.row(ctx.supplier.country)
    if row is None:
        return domestic
    return min(domestic, getattr(row, column).for_payer(ctx.cf.industrial_undertaking))


def _special_services(ctx: LineCtx, domestic: Decimal, gross: Decimal) -> tuple[BuyerAction, ...]:
    """WH-2 (i), (ii): 10% of the Malaysian part (services performed outside Malaysia exempt from 6 Sep 2017; mixed
    contracts apportioned; hotel accommodation left out of the reimbursed gross)."""
    try:
        place = ctx.need("place_of_performance", "WH-2")
        share = WHOLE_SHARE
        if place == "outside":
            return () if ctx.day >= OUTSIDE_EXEMPT_FROM else (
                _withhold(_rate(ctx, "WH-2", domestic, "technical_fees"), "WH-2", gross),)
        if place == "mixed":
            share = ctx.need("in_country_share", "WH-2")
    except NotSettled as ns:
        raise _not_settled(ns.basis, ns.reason) from None
    hotel = ctx.fact("hotel_reimbursement", ZERO, "WH-2")
    return (_withhold(_rate(ctx, "WH-2", domestic, "technical_fees"), "WH-2", (gross - hotel) * share),)


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
        if _certified(ctx, "WH-2") and treaties.row(ctx.supplier.country) is not None:
            raise _not_settled("WH-2", "treaty royalty definition for rent of movable property not read")
        return (_withhold(SPECIAL_CLASSES_RATE, "WH-2", gross),)
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
