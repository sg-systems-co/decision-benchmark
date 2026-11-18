"""Business-to-business exemptions (MS-5): Service Tax (Persons Exempted from Payment of Tax) Order 2018.

v0.9 logic, moved here unchanged; A12 build PR 2 commit 7 extends it to every order item.
"""

from __future__ import annotations

from .context import Exempt, LineCtx


def check(ctx: LineCtx) -> Exempt | None:
    if not ctx.profile.b2b_exempt or not ctx.buyer_registered():
        return None
    if ctx.fact("personal_use", False, "MS-5"):
        return None
    if ctx.fact("same_service_as_buyer", ctx.item in ctx.cf.services_provided, "MS-5"):
        return Exempt("MS-5")
    return None
