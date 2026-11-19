"""Reverse charge on imported services and low-value goods (SG-8): IRAS "GST and the digital economy" (local
businesses); IRAS e-Tax guide on overseas vendor registration, footnote 4: reverse charge applies to GST-registered
persons "not entitled to full input tax credit or belong[ing] to a GST group that is not entitled to full input tax
credit". Not entitled: a partially exempt buyer (de minimis not met), a buyer with non-business receipts, a member of
such a GST group. A buyer meeting the de minimis rule may claim all input tax (IRAS "Claiming input tax incurred to
make exempt supplies"), so on its own it does nothing. Imported services from 1 Jan 2020; low-value goods from
1 Jan 2023 (IRAS "GST and the digital economy", local businesses; IRAS e-Tax guide on reverse charge). Other imported
goods bear GST at import, not on the invoice. The facts are read in the sheet's order: supplier outside Singapore;
service or low-value goods; input-tax status; non-business receipts; GST group and its credit.
"""

from __future__ import annotations

from datetime import date

from ....findings import NotSettled
from ....models import BuyerAction
from ..models import SgTaxTreatment as T
from .context import LineCtx, Outcome

REVERSE_CHARGE_FROM = date(2020, 1, 1)
LOW_VALUE_GOODS_FROM = date(2023, 1, 1)
ACCOUNT_REVERSE_CHARGE = "ACCOUNT_REVERSE_CHARGE_GST"


def uncharged(ctx: LineCtx) -> Outcome | None:
    """A line without GST from a supplier outside Singapore."""
    if not ctx.foreign_supplier:
        return None
    service = ctx.catalog.get(ctx.line.category).kind == "service"
    low_value = not service and ctx.fact("low_value_goods", False, "SG-8")
    start = REVERSE_CHARGE_FROM if service else LOW_VALUE_GOODS_FROM
    if not (service or low_value) or ctx.day < start:
        return Outcome(T.NO_GST, "SG-8")
    if full_credit(ctx):
        return Outcome(T.NO_GST, "SG-8")
    return Outcome(T.REVERSE_CHARGE, "SG-8", actions=(BuyerAction(action=ACCOUNT_REVERSE_CHARGE),))


def full_credit(ctx: LineCtx) -> bool:
    """The buyer is entitled to full input tax credit (SG-8)."""
    cf = ctx.cf
    if cf.input_tax_status is None:
        raise NotSettled("SG-8", "buyer's input-tax status not shown")
    if cf.input_tax_status == "partially_exempt":
        return False
    if cf.non_business_receipts is None:
        raise NotSettled("SG-8", "buyer's non-business receipts not shown")
    if cf.non_business_receipts:
        return False
    if cf.in_gst_group:
        if cf.gst_group_full_credit is None:
            raise NotSettled("SG-8", "whether the buyer's GST group is entitled to full input tax credit not shown")
        return cf.gst_group_full_credit
    return True
