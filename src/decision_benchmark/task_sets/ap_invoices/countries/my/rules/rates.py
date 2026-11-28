"""Service tax rates (MS-2) and rate changes over time (MS-3).

Sources: Service Tax (Rate of Tax) Order 2018 with its 2024, 2025 and 2026 amendments; Second
Schedule (cards); Service Tax Policy 3/2024 and amendment no. 1 (Groups A-E operators). Rule sheet
v0.10 MS-2, MS-3.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ....findings import NotSettled
from ....models.common import CENT, ZERO
from . import scope
from .context import Exempt, LineCtx, Outcome, Partial
from ..models import MyTaxTreatment as T

GENERAL_RATE_FROM = date(2024, 3, 1)
"""8% for every service not on the 6% list (Rate of Tax (Amendment) Order 2024). Before: 6% for all."""
RENTAL_SIX_FROM = date(2026, 1, 1)
"""Group K rental: 8% from 1 Jul 2025, 6% from 1 Jan 2026 [P.U. (A) 125/2026]."""
"""8% charged on rental provided from 1 Jan 2026 is a wrong rate whenever the invoice was issued, before or after the
order's gazette date of 13 Mar 2026: STP 2/2025 (Amendment No. 5) Appendix B treats it as overpaid; the correction
comes as a credit note (rule sheet section 1, "Rental at 8% from 1 Jan 2026", settled 22 Nov 2026)."""
RATE_CHANGES = (GENERAL_RATE_FROM, date(2025, 7, 1), RENTAL_SIX_FROM)
"""The dates on which a service's rate can change (MS-3); scope changes add scope.scope_dates (reg 3A)."""
SIX_PERCENT_GROUPS = ("B", "J", "L", "M")
"""Rate of Tax Order First Schedule: F&B (B), logistics (J), construction (L), education (M)."""
SIX_PERCENT_ITEMS = ("I2", "I4", "I14", "I15", "I16")
"""Telecommunications, parking, private healthcare, T&CM, allied health."""
OPERATOR_GROUPS = ("A", "B", "C", "D", "E")
"""Groups A-E operators: each service at its own rate (STP 3/2024)."""
CARD_TAX = Decimal("25")
"""RM25 per card per year (Second Schedule; Group H item 1)."""
SIX = Decimal("6")
EIGHT = Decimal("8")


def standard_rate(item: str, day: date) -> Decimal:
    """The rate for a First Schedule item on a day (MS-2)."""
    if day < GENERAL_RATE_FROM:
        return SIX
    group = item[0]
    if group == "K":
        return SIX if day >= RENTAL_SIX_FROM else EIGHT
    return SIX if group in SIX_PERCENT_GROUPS or item in SIX_PERCENT_ITEMS else EIGHT


def line_rate(ctx: LineCtx, day: date) -> Decimal:
    """The rate for this line on a day: STP 3/2024 for what a Groups A-E operator sells, else the item's rate; 0 on
    a day the line is not a taxable service (reg 3A scope changes, MS-3)."""
    item = ctx.item
    assert item is not None
    if not scope.taxable_on(ctx, day):
        return ZERO
    if day >= GENERAL_RATE_FROM and ctx.group in OPERATOR_GROUPS:
        if ctx.fact("package_single_price", False, "MS-2"):
            # A package sold at one price takes the group's rate.
            return SIX if ctx.group == "B" else EIGHT
        content = ctx.fact("fb_content", None, "MS-2")
        if content in ("food", "non_alcoholic_drink", "food_with_alcohol"):
            return SIX
        if content in ("alcohol_alone", "corkage", "tobacco"):
            return EIGHT
    return standard_rate(item, day)


def _tax(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate / 100).quantize(CENT, ROUND_HALF_UP)


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= CENT


def period(ctx: LineCtx) -> tuple[date, date] | None:
    """The service period on the invoice (MS-3), or None when the line records none."""
    start = ctx.fact("service_period_start", None, "MS-3")
    end = ctx.fact("service_period_end", None, "MS-3")
    if start is None and end is None:
        return None
    if start is None:
        start = ctx.need("service_period_start", "MS-3")
    if end is None:
        end = ctx.need("service_period_end", "MS-3")
    return start, end


def _spanning_tax(ctx: LineCtx, taxable: Decimal, old: Decimal, new: Decimal) -> Decimal:
    """MS-3 for a service period spanning a rate change (A12 decision 4; review of PR #14, C): payments received
    before the change keep the old rate; the rest is taxed by the part provided on each side of the date, where the
    documents show it (value_provided_before_change, the value provided before the change, of which a payment
    received before the change already covers its amount). No pro-rata split by days: not shown -> HAND_OVER."""
    paid = min(ctx.fact("amount_paid_before_change", ZERO, "MS-3"), taxable)
    if paid >= taxable:
        return _tax(taxable, old)
    provided = ctx.fact("value_provided_before_change", None, "MS-3")
    if provided is None:
        raise NotSettled("MS-3", "service period spans a rate change and the value provided on each side is not shown")
    at_old = min(max(paid, provided), taxable)
    return _tax(at_old, old) + _tax(taxable - at_old, new)


def _paid_before_change(ctx: LineCtx, first_day: date, taxable: Decimal) -> Outcome | None:
    """MS-3: a supply wholly on or after a change, part paid before it: the paid part keeps the rate before the change
    (0 before a scope start, reg 3A). The change is the latest one on or before the supply's first day."""
    paid = min(ctx.fact("amount_paid_before_change", ZERO, "MS-3"), taxable)
    if paid <= ZERO:
        return None
    changes = sorted(set(RATE_CHANGES) | set(scope.scope_dates(ctx.item)), reverse=True)
    for change in changes:
        if change <= first_day and line_rate(ctx, change - timedelta(days=1)) != line_rate(ctx, change):
            old, new = line_rate(ctx, change - timedelta(days=1)), line_rate(ctx, change)
            expected = _tax(paid, old) + _tax(taxable - paid, new)
            if _close(ctx.line.tax_amount, expected):
                return Outcome(T.SST_CORRECT, "MS-3")
            if expected == ZERO:
                return ctx.exempt(Exempt("MS-3"), "not_taxable")
            return ctx.wrong_rate("MS-3", new)
    return None


def uncharged_due(ctx: LineCtx, taxable: Decimal) -> bool | None:
    """MS-3 (reg 3A) for a line that charges no tax: False when no tax is due because the line's value was paid, or
    provided, before the service became taxable; True when some tax is due; None when no rate or scope change bears
    on the line. A spanning supply follows _spanning_tax: the value provided before the start counts with the
    payment, and not shown, where it decides, is HAND_OVER."""
    span = period(ctx)
    first = ctx.day if span is None else span[0]
    if span is not None and line_rate(ctx, span[0]) != line_rate(ctx, span[1]):
        if line_rate(ctx, span[0]) > ZERO:
            return True
        return _spanning_tax(ctx, taxable, ZERO, line_rate(ctx, span[1])) > ZERO
    paid = min(ctx.fact("amount_paid_before_change", ZERO, "MS-3"), taxable)
    if paid <= ZERO:
        return None
    changes = sorted(set(RATE_CHANGES) | set(scope.scope_dates(ctx.item)), reverse=True)
    for change in changes:
        old = line_rate(ctx, change - timedelta(days=1))
        if change <= first and old != line_rate(ctx, change):
            return _tax(paid, old) + _tax(taxable - paid, line_rate(ctx, change)) > ZERO
    return None


def check_rate(ctx: LineCtx, partials: list[Partial]) -> Outcome:
    """Tax charged on a taxable line: right rate (and amount, where only part is taxable)?"""
    line = ctx.line
    if ctx.fact("financial_charge", None, "MS-4") == "card_activation":
        expected = (CARD_TAX * line.qty).quantize(CENT)
        if _close(line.tax_amount, expected):
            return Outcome(T.SST_CORRECT, "MS-2")
        return ctx.wrong_rate("MS-2", CARD_TAX)
    taxable = ctx.net - sum((ctx.net - p.taxable for p in partials), ZERO)
    span = period(ctx)
    if span is not None:
        start, end = span
        old, new = line_rate(ctx, start), line_rate(ctx, end)
        if old != new:
            expected = _spanning_tax(ctx, taxable, old, new)
            if _close(line.tax_amount, expected):
                return Outcome(T.SST_CORRECT, "MS-3")
            return ctx.wrong_rate("MS-3", new)
        rate, basis = old, ("MS-3" if old != line_rate(ctx, ctx.day) else "MS-2")
        prepaid = _paid_before_change(ctx, start, taxable)
        if prepaid is not None:
            return prepaid
    else:
        rate, basis = line_rate(ctx, ctx.day), "MS-2"
        prepaid = _paid_before_change(ctx, ctx.day, taxable)
        if prepaid is not None:
            return prepaid
    if partials:
        part_basis = partials[0].basis
        if _close(line.tax_amount, _tax(taxable, rate)):
            return Outcome(T.SST_CORRECT, part_basis)
        if _close(line.tax_amount, _tax(ctx.net, rate)):
            return ctx.exempt_part(part_basis)
        return ctx.wrong_rate(basis, rate)
    if line.tax_rate != rate:
        return ctx.wrong_rate(basis, rate)
    return Outcome(T.SST_CORRECT, basis)
