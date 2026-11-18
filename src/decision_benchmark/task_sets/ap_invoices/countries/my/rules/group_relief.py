"""Group relief (MS-6, K-6): First Schedule paras 3-9, Service Tax Regulations 2018, as amended by
P.U. (A) 354/2024; Service Tax Policy 8/2020 and amendment no. 1; STP 2/2025 Appendix A (rental).

A group: one company controls the other, by more than 50% of the shares or 20-50% with power over the
board; nominee and fiduciary holdings don't count (paras 4-7). Relief is lost when the supplier's supplies
of the service to outsiders exceed 5% (para 8(2), from 1 Jan 2020).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....findings import NotSettled
from ..constants import GROUP_RELIEF_ITEMS
from .context import Exempt, LineCtx

MAINTENANCE_RELIEF_FROM = date(2024, 5, 1)
"""G(n) is in group relief since 1 May 2024 [P.U. (A) 354/2024]."""
CONTROL_PCT = Decimal(50)
BOARD_PCT = Decimal(20)


def _controls(ctx: LineCtx, holder: str, held: str, basis: str) -> bool:
    group = ctx.cf.group
    assert group is not None
    for s in group.shareholdings:
        if s.holder_id != holder or s.held_id != held or s.nominee:
            continue
        if s.pct > CONTROL_PCT:
            return True
        if s.pct >= BOARD_PCT:
            if s.board_control is None:
                raise NotSettled(basis, "power over the board not shown")
            return s.board_control
    return False


def related(ctx: LineCtx, basis: str) -> bool:
    """The supplier and the company are in one group (paras 4-7)."""
    if ctx.sf.group_relation == "unclear":
        raise NotSettled(basis, "group_relief_unclear")
    other = ctx.sf.group_company_id
    if other is None:
        return False
    if ctx.cf.group is None:
        raise NotSettled(basis, "group structure not shown")
    me = ctx.company.company_id
    return _controls(ctx, me, other, basis) or _controls(ctx, other, me, basis)


def within_5pct(ctx: LineCtx, basis: str) -> bool:
    share = ctx.sf.external_share_within_5pct
    if share is None:
        raise NotSettled(basis, "supplies to outsiders within 5% not shown")
    return share


def check(ctx: LineCtx) -> Exempt | None:
    """MS-6 for a domestic Group G line. Imported group services are in imported.py, rental (K-6) in rental.py."""
    if ctx.foreign_supplier or ctx.item not in GROUP_RELIEF_ITEMS:
        return None
    if ctx.item == "G(n)" and ctx.day < MAINTENANCE_RELIEF_FROM:
        return None
    if related(ctx, "MS-6") and within_5pct(ctx, "MS-6"):
        return Exempt("MS-6")
    return None
