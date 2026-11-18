"""Reverse charge on imported services and low-value goods (SG-8): IRAS "GST and the digital economy" (local
businesses). Applies only to GST-registered buyers not entitled to full input tax (partially exempt); a fully
taxable buyer, or one meeting the de minimis rule, does nothing. Imported services from 1 Jan 2020; low-value
goods from 1 Jan 2023. Other imported goods bear GST at import, not on the invoice.
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
    status = ctx.cf.input_tax_status
    if status is None:
        raise NotSettled("SG-8", "buyer's input-tax status not shown")
    if status == "partially_exempt":
        return Outcome(T.REVERSE_CHARGE, "SG-8", actions=(BuyerAction(action=ACCOUNT_REVERSE_CHARGE),))
    return Outcome(T.NO_GST, "SG-8")
