"""Is GST on the line what the supplier should charge? SG-3, SG-5, SG-6, SG-12 (rule sheet v0.10 section 4).

Sources: IRAS "Transitional rules for GST rate change" and "Adjustments and concessions for GST rate change"
(SG-3); "Supplies exempt from GST" (SG-5); GST Act 1993 s21(3), (6), (6A) and IRAS "When to charge 0%" (SG-6);
IRAS "Responsibilities of a GST-registered business" (SG-12). SG-4 (supplier entitled to charge) is
invoice-level, in __init__.py.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from ....codes import Code
from ....models.common import ZERO
from ..models import SgTaxTreatment as T
from .context import LineCtx, Outcome

GST_RATE_CHANGES = ((date(2024, 1, 1), Decimal(9)), (date(2023, 1, 1), Decimal(8)))
"""9% from 1 Jan 2024, 8% in 2023, 7% before (IRAS current GST rates)."""
EARLIEST_RATE = Decimal(7)
ADVERTISING_ZERO_RATED_TO = date(2021, 12, 31)
"""s21(3)(u): advertising substantially outside Singapore, zero-rated only before 1 Jan 2022."""
PROVISION = re.compile(r"^s21\(3\)\(([a-y])\)$")


def rate_on(day: date) -> Decimal:
    for start, rate in GST_RATE_CHANGES:
        if day >= start:
            return rate
    return EARLIEST_RATE


def exempt(ctx: LineCtx) -> bool:
    """SG-5: an exempt supply (financial services, digital payment tokens, residential property, investment
    precious metals). Fees for advising, arranging or broking are not exempt (the fact then says none)."""
    return ctx.fact("exempt_supply", "none", "SG-5") != "none"


def zero_rated(ctx: LineCtx) -> bool | None:
    """SG-6: whether the zero-rating provision the line falls under applies; None: the line names none."""
    provision = ctx.fact("zero_rating_provision", None, "SG-6")
    if provision is None:
        return None
    m = PROVISION.match(provision)
    letter = m.group(1) if m else None
    if letter is None or letter in ("g", "h"):
        # Exports of goods (s21(6), (6A)), services on goods for export, financial services on exports.
        return bool(ctx.need("export_evidence", "SG-6"))
    if letter in ("a", "b", "c"):
        return bool(ctx.need("international_transport", "SG-6"))
    if letter in ("d", "f"):
        return bool(ctx.need("goods_outside_singapore", "SG-6"))
    if letter in ("j", "k"):
        # Turns on the overseas beneficiary; not shown -> HAND_OVER (the sheet).
        return bool(ctx.need("beneficiary_outside_singapore", "SG-6"))
    if letter == "u":
        return ctx.day <= ADVERTISING_ZERO_RATED_TO
    return True


def allowed_rates(ctx: LineCtx) -> tuple[Decimal, Decimal, bool]:
    """SG-3: (lowest, highest) rate the time-of-supply rules allow for the dates on the documents, and whether the
    supply spans a rate change. A supply spans a change when one or two of invoice, payment and delivery fall on or
    after it. Invoice after the change: full payment before -> old rate; otherwise the supplier may elect the old
    rate (on the higher of payment or value delivered before), so the buyer accepts either rate shown. Invoice
    before the change: the old rate (later adjustments come by credit note and a new invoice)."""
    issued = ctx.day
    delivered = ctx.fact("delivery_date", issued, "SG-3")
    paid = ctx.fact("amount_paid_before_change", ZERO, "SG-3")
    for change, new in GST_RATE_CHANGES:
        after = issued >= change or delivered >= change
        before = issued < change or delivered < change or paid > ZERO
        if after and before:
            old = rate_on(change - timedelta(days=1))
            if issued < change or paid >= ctx.net:
                return old, old, True
            return old, new, True
    rate = rate_on(issued)
    return rate, rate, False


def check_rate(ctx: LineCtx) -> Outcome | None:
    """SG-3 for a line that shows a GST rate: higher than allowed -> GST_WRONGLY_CHARGED, lower -> GST_UNDERCHARGED."""
    if not ctx.rate_shown:
        return None
    low, high, spans = allowed_rates(ctx)
    if ctx.line.tax_rate > high:
        return ctx.wrongly_charged("SG-3", Code.WRONG_TAX_RATE)
    if ctx.line.tax_rate < low:
        return ctx.undercharged("SG-3", Code.WRONG_TAX_RATE)
    if spans or ctx.line.tax_rate != rate_on(ctx.day):
        return Outcome(T.CLAIMABLE, "SG-3")       # the claim rules still decide; the basis says the rate was checked
    return None


def charged_line(ctx: LineCtx) -> Outcome | None:
    """GST on a line that shouldn't carry it (SG-5, SG-6), or at a rate the rules don't allow (SG-3)."""
    if exempt(ctx):
        return ctx.wrongly_charged("SG-5")
    if zero_rated(ctx) and ctx.rate_shown:
        return ctx.wrongly_charged("SG-6")
    return None


def uncharged_line(ctx: LineCtx) -> Outcome:
    """A line without GST: correct (SG-4 not entitled, SG-5 exempt, SG-6 zero-rated with 0% shown), else a
    GST-registered supplier left GST off a standard-rated supply (SG-12)."""
    reg = ctx.registration
    if reg is None or reg.type == "ovr":
        return Outcome(T.NO_GST, "SG-4")
    if exempt(ctx):
        return Outcome(T.NO_GST, "SG-5")
    zero = zero_rated(ctx)
    if zero:
        return Outcome(T.NO_GST, "SG-6")
    return ctx.undercharged("SG-12")
