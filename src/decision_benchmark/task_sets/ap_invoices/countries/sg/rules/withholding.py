"""Singapore withholding tax on payments to non-residents: WH-5 (rule sheet v0.10 §4A).

Sources: IRAS "Types of payment and withholding tax rates" and "Payments that are subject to withholding tax";
the treaty texts (treaties.py). Applies to payments to non-residents without a Singapore branch receiving them. A
treaty rate needs the payee's certificate of residence and a confirmed treaty row; a row not yet confirmed is
HAND_OVER. Service fees under a treaty without a technical-fees article are business profits: not taxed for a
non-resident without a PE in Singapore that holds a certificate of residence. Open questions here leave the tax
treatment set (NotSettled with tax_related False).
"""

from __future__ import annotations

from decimal import Decimal

from ....findings import NotSettled
from ....models import BuyerAction
from ....models.answer import WITHHOLD_TAX
from ....models.common import CENT
from .. import treaties
from .context import LineCtx

DOMESTIC = {
    "interest": Decimal(15), "royalty": Decimal(10), "knowledge_or_information": Decimal(10),
    "movable_property_rent": Decimal(15), "technical_or_management_fee": Decimal(17),
    "professional_fee": Decimal(15), "director_fee": Decimal(24),
}
"""IRAS rates: interest and loan fees 15%; royalties and knowledge or information 10%; movable property rent 15%;
technical, service and management fees for work in Singapore at the corporate rate 17%; non-resident professionals
15%; directors 24%."""
NOT_SUBJECT = ("none", "electronic_service", "ship_charter", "copyrighted_article")
"""Services delivered electronically from overseas without staff in Singapore, ship charters (nil), payments for a
copyrighted article (use only)."""
TREATY_COLUMN = {"interest": "interest", "royalty": "royalties", "knowledge_or_information": "royalties"}


def _not_settled(reason: str) -> NotSettled:
    return NotSettled("WH-5", reason, tax_related=False)


def _certified(ctx: LineCtx) -> bool:
    held = any(c.country == ctx.supplier.country and c.valid_on(ctx.day) for c in ctx.residence_certificates)
    try:
        return bool(ctx.fact("certificate_of_residence", held, "WH-5"))
    except NotSettled as ns:
        raise _not_settled(ns.reason) from None


def _treaty_rate(ctx: LineCtx, column: str, domestic: Decimal) -> Decimal:
    row = treaties.treaty(ctx.supplier.country)
    if row is None:
        return domestic
    article = getattr(row, column)
    if not article.confirmed:
        raise _not_settled(f"treaty {column} rate for {ctx.supplier.country} not confirmed")
    return min(domestic, article.rate)


def actions(ctx: LineCtx) -> tuple[BuyerAction, ...]:
    if not ctx.foreign_supplier:
        return ()
    try:
        nature = ctx.fact("payment_nature", "none", "WH-5")
    except NotSettled as ns:
        raise _not_settled(ns.reason) from None
    if nature in NOT_SUBJECT:
        return ()
    branch = ctx.sf.has_branch_receiving
    if branch is None:
        raise _not_settled("Singapore branch receiving the payment not shown")
    if branch:
        return ()
    rate = DOMESTIC[nature]
    certified = _certified(ctx)
    if nature in TREATY_COLUMN:
        if certified:
            rate = _treaty_rate(ctx, TREATY_COLUMN[nature], rate)
    elif nature == "technical_or_management_fee":
        try:
            place = ctx.need("place_of_performance", "WH-5")
        except NotSettled as ns:
            raise _not_settled(ns.reason) from None
        if place == "outside":
            return ()
        if place == "mixed":
            raise _not_settled("work done in Singapore not split from work outside")
        if certified:
            row = treaties.treaty(ctx.supplier.country)
            article = row.technical_fees if row is not None else None
            if article is not None and article.confirmed:
                rate = min(rate, article.rate)
            elif row is not None:
                raise _not_settled(f"treaty technical-fees article for {ctx.supplier.country} not confirmed")
    return (BuyerAction(action=WITHHOLD_TAX, rate=rate, basis="WH-5", base_amount=ctx.net.quantize(CENT)),)
