"""Business-to-business exemptions (MS-5): Service Tax (Persons Exempted from Payment of Tax) Order 2018
with its 2019, 2020, 2024 and 2025 amendments; rental guide paras 24-26; construction guide para 36.

The buyer is exempt when all of its order item's conditions hold. Items 3 and 4 (imported digital and IT
services) are in imported.py; items 7 and 10 (patients, disabled students) in scope.py. The buyer must be
registered for service tax (the order is made under the Service Tax Act 2018); a sales-tax registration doesn't
count.
"""

from __future__ import annotations

from decimal import Decimal

from ..constants import NO_B2B_ITEMS
from .context import Exempt, LineCtx, Partial

WHOLE = Decimal(1)


def check(ctx: LineCtx) -> Exempt | Partial | None:
    if ctx.foreign_supplier or not ctx.buyer_registered():
        return None
    item, group = ctx.item, ctx.group
    if group == "H":
        # Item 6 (2025): a buyer regulated by Labuan FSA, for its Labuan-regulated services.
        return Exempt("MS-5") if ctx.cf.labuan_fsa_regulated else None
    if group == "K":
        # Item 8 (2025): a registered Group K provider renting the asset to sublet it; the sublet part only.
        if not ctx.fact("same_service_as_buyer", ctx.buyer_provides("K"), "MS-5"):
            return None
        if not ctx.fact("sublet", False, "MS-5"):
            return None
        share = ctx.fact("sublet_share", WHOLE, "MS-5")
        return Exempt("MS-5") if share >= WHOLE else Partial("MS-5", ctx.net * (WHOLE - share))
    if not ((group == "G" and item not in NO_B2B_ITEMS) or item == "I8" or group in ("J", "L")):
        return None
    # Items 1 (Group G except (j), (k)), 2 (I8), 5 (Group J), 9 (Group L): the same item, not personal or own use.
    if ctx.fact("personal_use", False, "MS-5"):
        return None
    if group == "L" and ctx.fact("own_use", False, "MS-5"):
        return None
    if ctx.fact("same_service_as_buyer", item in ctx.cf.services_provided, "MS-5"):
        return Exempt("MS-5")
    return None
