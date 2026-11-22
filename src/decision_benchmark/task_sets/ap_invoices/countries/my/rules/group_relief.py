"""Group relief (MS-6, K-6): First Schedule paras 3-9, Service Tax Regulations 2018 [P.U. (A) 214/2018], as amended
by P.U. (A) 354/2024; Service Tax Policy 8/2020 and amendment no. 1; STP 2/2025 Appendix A (rental).

Para 4: two or more companies are companies within a group if one company controls each of the other companies.
Control: more than 50% of the issued share capital, or 20-50% with power over the board; para 5 counts control
held directly, indirectly through subsidiaries, or both. So the supplier and the buyer are in one group when some
company controls both of them (one of them, or a common parent). Nominee and fiduciary holdings don't count; an
individual owner forms no group. Relief is lost when the supplier's supplies of the service to outsiders exceed
5% (para 8(2), from 1 Jan 2020, P.U. (A) 357/2019 para 1(2)). Before then para 8 alone applied: any supply of the
service to outsiders ended the relief, so the outside share must be shown as zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....findings import NotSettled
from ....models.common import ZERO
from ..constants import GROUP_RELIEF_ITEMS
from ..models import GroupStructure
from .context import Exempt, LineCtx

FIVE_PCT_FROM = date(2020, 1, 1)
"""Para 8(2), inserted by P.U. (A) 357/2019: "These Regulations come into operation on 1 January 2020"."""
MAINTENANCE_RELIEF_FROM = date(2024, 5, 1)
"""G(n) is in group relief since 1 May 2024 [P.U. (A) 354/2024]."""
CONTROL_PCT = Decimal(50)
BOARD_PCT = Decimal(20)


def controlled_by(group: GroupStructure, parent: str, assume_board: bool) -> set[str]:
    """The companies the parent controls, directly or through companies it controls (para 5), the parent included.
    assume_board: count a 20-50% holding whose board control is not shown as control (the optimistic reading)."""
    holdings = [s for s in group.shareholdings if not s.nominee and s.holder_kind == "company"]
    controlled = {parent}
    changed = True
    while changed:
        changed = False
        for held in {s.held_id for s in holdings} - controlled:
            mine = [s for s in holdings if s.held_id == held and s.holder_id in controlled]
            total = sum((s.pct for s in mine), ZERO)
            board = any(s.board_control or (assume_board and s.board_control is None) for s in mine)
            if total > CONTROL_PCT or (total >= BOARD_PCT and board):
                controlled.add(held)
                changed = True
    return controlled


def related(ctx: LineCtx, basis: str) -> bool:
    """The supplier and the company are companies within one group (paras 4-5)."""
    if ctx.sf.group_relation == "unclear":
        raise NotSettled(basis, "group_relief_unclear")
    other = ctx.sf.group_company_id
    if other is None:
        return False
    group = ctx.cf.group
    if group is None:
        raise NotSettled(basis, "group structure not shown")
    me = ctx.company.company_id
    parents = {me, other} | {s.holder_id for s in group.shareholdings if s.holder_kind == "company"}
    if any({me, other} <= controlled_by(group, p, assume_board=False) for p in parents):
        return True
    if any({me, other} <= controlled_by(group, p, assume_board=True) for p in parents):
        raise NotSettled(basis, "power over the board not shown")
    return False


def within_5pct(ctx: LineCtx, basis: str) -> bool:
    """The supplier's supplies to outsiders keep the relief: within 5% from 1 Jan 2020 (para 8(2)), none before
    (para 8)."""
    share = ctx.sf.external_share_within_5pct
    if ctx.day < FIVE_PCT_FROM:
        if share is False:
            return False                # above 5%, so not none
        none = ctx.sf.no_external_supplies
        if none is None:
            raise NotSettled(basis, "before 1 Jan 2020: no supplies to outsiders not shown")
        return none
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
