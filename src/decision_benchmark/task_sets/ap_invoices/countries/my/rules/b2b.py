"""Business-to-business exemptions (MS-5): Service Tax (Persons Exempted from Payment of Tax) Order 2018
with its 2019, 2020, 2024 and 2025 amendments; rental guide paras 24-26; construction guide para 36.

The buyer is exempt when all of its order item's conditions hold. Items 3 and 4 (imported digital and IT
services) are in imported.py; items 7 and 10 (patients, disabled students) in scope.py. The buyer must be
registered for service tax (the order is made under the Service Tax Act 2018); a sales-tax registration doesn't
count.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..constants import NO_B2B_ITEMS
from .context import Exempt, LineCtx, Partial

WHOLE = Decimal(1)
ORDER_FROM = date(2019, 1, 1)
"""P.U. (A) 380/2018 para 1(2): the Order comes into operation on 1 January 2019. Items 1 and 2."""
PERSONAL_USE_FROM = date(2020, 1, 1)
"""P.U. (A) 388/2019 para 1(2), 1 January 2020: items 1 and 2 gain "not for personal consumption" (and add items 3, 4)."""
ITEM_5_FROM = date(2024, 3, 1)
"""P.U. (A) 66/2024 para 1(2): "This Order comes into operation on 1 March 2024" (item 5, Group J)."""
ITEMS_6_TO_10_FROM = date(2025, 7, 1)
"""P.U. (A) 174/2025 para 1(2): "This Order comes into operation on 1 July 2025" (items 6 to 10)."""


def in_force(item_no: int, day: date) -> bool:
    """Whether B2B order item item_no is in force on day."""
    if item_no >= 6:
        return day >= ITEMS_6_TO_10_FROM
    if item_no == 5:
        return day >= ITEM_5_FROM
    if item_no in (3, 4):
        return day >= PERSONAL_USE_FROM
    return day >= ORDER_FROM


def check(ctx: LineCtx) -> Exempt | Partial | None:
    if ctx.foreign_supplier or not ctx.buyer_registered():
        return None
    item, group, day = ctx.item, ctx.group, ctx.day
    if group == "H":
        # Item 6 (2025): a buyer regulated by Labuan FSA, for its Labuan-regulated services.
        return Exempt("MS-5") if in_force(6, day) and ctx.cf.labuan_fsa_regulated else None
    if group == "K":
        if not in_force(8, day):
            return None
        # Item 8 (2025): a registered Group K provider renting the asset to sublet it; the sublet part only.
        if not ctx.fact("same_service_as_buyer", ctx.buyer_provides("K"), "MS-5"):
            return None
        if not ctx.fact("sublet", False, "MS-5"):
            return None
        share = ctx.fact("sublet_share", WHOLE, "MS-5")
        return Exempt("MS-5") if share >= WHOLE else Partial("MS-5", ctx.net * (WHOLE - share))
    if group == "G" and item not in NO_B2B_ITEMS or item == "I8":
        item_no = 1
    elif group == "J":
        item_no = 5
    elif group == "L":
        item_no = 9
    else:
        return None
    if not in_force(item_no, day):
        return None
    # Items 1 (Group G except (j), (k)), 2 (I8), 5 (Group J), 9 (Group L): the same item, not personal or own use
    # (items 1 and 2 only from 1 Jan 2020).
    if (item_no != 1 or day >= PERSONAL_USE_FROM) and ctx.fact("personal_use", False, "MS-5"):
        return None
    if group == "L" and ctx.fact("own_use", False, "MS-5"):
        return None
    if ctx.fact("same_service_as_buyer", item in ctx.cf.services_provided, "MS-5"):
        return Exempt("MS-5")
    return None
