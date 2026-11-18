"""Customer accounting for prescribed goods (SG-7): IRAS "Customer accounting for prescribed goods".

Mobile phones, memory cards and off-the-shelf software sold to a GST-registered buyer (every Singapore buyer is
registered) for business, above S$10,000 excluding GST per invoice: the supplier charges no GST and issues a
customer accounting tax invoice stating the buyer must account for it; the buyer accounts for the GST.
"""

from __future__ import annotations

from decimal import Decimal

from ....codes import Code
from ....findings import NotSettled, finding
from ....models import BuyerAction
from ....models.common import ZERO
from ..models import SgTaxTreatment as T
from .context import LineCtx, Outcome

PRESCRIBED_THRESHOLD = Decimal("10000.00")
ACCOUNT_CUSTOMER_ACCOUNTING = "ACCOUNT_CUSTOMER_ACCOUNTING_GST"


def _prescribed_value(ctx: LineCtx) -> Decimal:
    """The invoice's prescribed goods, excluding GST, in SGD."""
    total = sum((x.net_amount for x in ctx.invoice.lines
                 if x.facts is not None and getattr(x.facts, "prescribed_goods", None) is not None
                 and x.facts.prescribed_goods.value not in (None, "none")), ZERO)
    if ctx.invoice.currency == "SGD":
        return total
    if ctx.invoice.exchange_rate is None:
        raise NotSettled("SG-7", "SGD value of the prescribed goods not shown")
    return total * ctx.invoice.exchange_rate


def applies(ctx: LineCtx) -> bool:
    if ctx.fact("prescribed_goods", "none", "SG-7") == "none":
        return False
    if not ctx.fact("business_purpose", True, "SG-7"):
        return False
    return _prescribed_value(ctx) > PRESCRIBED_THRESHOLD


def charged(ctx: LineCtx) -> Outcome | None:
    return ctx.wrongly_charged("SG-7") if applies(ctx) else None


def uncharged(ctx: LineCtx) -> Outcome | None:
    if not applies(ctx):
        return None
    if ctx.invoice.einvoice.customer_accounting_statement:
        return Outcome(T.CUSTOMER_ACCOUNTING, "SG-7", actions=(BuyerAction(action=ACCOUNT_CUSTOMER_ACCOUNTING),))
    # Not a customer accounting tax invoice: it lacks the statement the buyer accounts by.
    return Outcome(T.NOT_CLAIMABLE_INVALID_INVOICE, "SG-7", (
        finding(Code.INVALID_TAX_INVOICE, missing=["customer_accounting_statement"]),))
