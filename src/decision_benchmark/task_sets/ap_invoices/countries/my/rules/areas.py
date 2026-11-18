"""Designated and special areas (MS-7 for services, MG-5 for goods).

Designated areas: Labuan, Langkawi, Tioman, Pangkor; special areas: free zones, licensed warehouses,
licensed manufacturing warehouses, the JDA. The rule sheet: services (and goods) between and within these
areas are not taxed, except as the Minister prescribes; principal customs area <-> DA/SA rules are as in
the DA/SA orders, which the sheet does not restate. The JDA works by refund since 15 Aug 2022 (P-20): the
tax on the invoice is correct (A12 decision 1).
"""

from __future__ import annotations

from datetime import date

from ....findings import NotSettled, UnsupportedCase
from .context import Exempt, LineCtx

JDA_REFUND_FROM = date(2022, 8, 15)


def check(ctx: LineCtx, basis: str) -> Exempt | None:
    """basis: MS-7 (services) or MG-5 (goods)."""
    if not (ctx.cf.zone_known and ctx.sf.zone_known):
        raise NotSettled(basis, "zone status not shown")
    mine, theirs = ctx.cf.zone, ctx.sf.zone
    if mine is None and theirs is None:
        return None
    if "jda" in (mine, theirs):
        if ctx.day >= JDA_REFUND_FROM:
            return None
        raise UnsupportedCase("JDA before the refund route: not in the rule sheet")
    if mine is not None and theirs is not None:
        return Exempt(basis)
    raise UnsupportedCase("principal customs area <-> designated or special area: the rule sheet defers to the DA/SA orders")
