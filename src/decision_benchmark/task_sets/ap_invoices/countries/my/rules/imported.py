"""Imported taxable services (MS-8): Service Tax Act s26 (registered persons) and s26A (others above the
threshold); exceptions in the B2B order items 3 and 4 (MS-5), group paras 1B and 3A (MS-6), STP 2/2020,
STP 3/2020 and STP 1/2025 item 6.

The overseas supplier's invoice correctly shows no SST; the buyer accounts for it itself: SST_BUYER_ACCOUNTS
with the buyer action ACCOUNT_IMPORTED_SERVICE_TAX. A foreign registered person (FRP) charges SST on its
digital services itself.
"""

from __future__ import annotations

from ....findings import NotSettled
from ....models import BuyerAction
from ..constants import NO_B2B_ITEMS
from ..models import MyTaxTreatment as T
from . import group_relief, policies, rates, scope
from .context import Exempt, LineCtx, Outcome

ACCOUNT_IMPORTED = "ACCOUNT_IMPORTED_SERVICE_TAX"
IMPORTED_GROUP_ITEMS = ("G(a)", "G(b)", "G(c)", "G(d)", "G(e)", "G(f)", "G(g)", "G(h)", "G(i)", "G(l)")
"""Para 3A: imported Group G items (a) to (i) and (l) from a group company abroad are not imported taxable services."""
FINANCIAL_USES = ("taxable_financial_services", "offshore_financial_services", "export_related_financial_services")


def _buyer_accounts(basis: str = "MS-8") -> Outcome:
    return Outcome(T.SST_BUYER_ACCOUNTS, basis, actions=(BuyerAction(action=ACCOUNT_IMPORTED),))


def assess(ctx: LineCtx) -> Outcome:
    item, frp = ctx.item, ctx.sf.is_foreign_registered_person
    if ctx.charged:
        if frp and ctx.supplier_registered("service", "MS-8"):
            # STP 3/2020: the FRP's invoice correctly carries SST.
            out = rates.check_rate(ctx, [])
            return Outcome(out.code, "MS-8", out.findings) if out.code == T.SST_CORRECT else out
        return ctx.not_registered("service", "MS-1")
    if not scope.in_schedule(item, ctx.day):
        return Outcome(T.NO_SST, "MS-1")
    # Group H policies are for financial services bought in Malaysia; imported ones follow STP 1/2025 item 6 below.
    found = policies.check(ctx) if ctx.group != "H" else None
    if isinstance(found, Exempt):
        return Outcome(T.NO_SST, found.basis)
    if isinstance(scope.exclusion(ctx), Exempt):
        return Outcome(T.NO_SST, "MS-4")
    if policies.labuan_imported(ctx):
        return Outcome(T.NO_SST, "P-20")
    registered = ctx.buyer_registered()
    if frp:
        # Digital services from an FRP: to a group company not taxed unless the FRP also supplies outsiders
        # in Malaysia (paras 1B, 2A); B2B item 3: a registered buyer accounts for the tax itself.
        if group_relief.related(ctx, "MS-6"):
            outsiders = ctx.sf.frp_supplies_outsiders_in_my
            if outsiders is None:
                raise NotSettled("MS-6", "FRP supplies to outsiders in Malaysia not shown")
            if not outsiders:
                return Outcome(T.NO_SST, "MS-6")
        if registered:
            return _buyer_accounts("MS-5")
        return ctx.undercharged("MS-9", "service")
    if item in IMPORTED_GROUP_ITEMS and group_relief.related(ctx, "MS-6"):
        return Outcome(T.NO_SST, "MS-6")
    if registered:
        personal = ctx.fact("personal_use", False, "MS-5")
        same = ctx.fact("same_service_as_buyer", item in ctx.cf.services_provided, "MS-5")
        if item == "G(h)" and same and not personal:
            # B2B item 4: a registered IT provider reselling the identical imported IT service.
            return Outcome(T.NO_SST, "MS-5")
        eligible = (ctx.group == "G" and item not in NO_B2B_ITEMS) or item == "I8"
        if eligible and same and not personal and ctx.fact("supplier_paid", False, "MS-8"):
            # STP 2/2020: the same service to its customers, for business, the supplier paid.
            return Outcome(T.NO_SST, "MS-8")
        if ctx.group == "H" and ctx.buyer_provides("H") and ctx.fact("financial_use", None, "MS-8") in FINANCIAL_USES:
            # STP 1/2025 item 6: a registered Group H provider buying for its financial services.
            return Outcome(T.NO_SST, "MS-8")
        return _buyer_accounts()
    raise NotSettled("MS-8", "unregistered buyer: s26A threshold not shown")
