"""Group K rental or leasing: K-1 to K-8 (rule sheet v0.10 MS-4 Group K).

Ministerial exemptions in Service Tax Policy 2/2025 (Amendment No. 5), 22 Jul 2026, under Service Tax Act
s34(3)(a) and s34(4); STP 8/2025 (location); STP 4/2026 (joint lessors). The MS-4 exclusions (housing,
reading materials, financial leases) are in scope.py; the B2B sublet exemption (order item 8) in b2b.py.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ....findings import NotSettled
from . import group_relief
from .context import Exempt, LineCtx
from .scope import NEW_SCOPE_FROM

SME_BAND_FROM = {"below_1m": date(2025, 7, 1), "1m_to_1_5m": date(2026, 1, 1)}
"""K-1: tenants with declared annual sales below RM1m exempt from 1 Jul 2025; RM1m-1.5m from 1 Jan 2026."""
BACKDATE_BY = date(2026, 12, 31)
"""K-1: a MyPMK registration by 31 Dec 2026 still backdates to the band's start."""
NEW_SME_FROM = date(2026, 1, 1)
"""K-2: new SMEs, exempt for 1 year from SSM registration, from 1 Jan 2026."""
SME_CAPITAL_LIMIT = Decimal("2500000")
SME_GROUP_LIMIT = Decimal(20)
CONTRACT_WINDOW = (date(2025, 7, 1), date(2026, 6, 30))
"""K-4: rental under a non-reviewable contract is exempt from 1 Jul 2025 to 30 Jun 2026."""
CONTRACT_DONE_BY = date(2025, 6, 9)
"""K-4: the contract was signed and LHDN-stamped by 9 Jun 2025."""
EXEMPT_ASSETS = ("aircraft", "vessel")
"""K-3: aircraft (not drones) and ships (not floating storage units)."""


def _sme_conditions(ctx: LineCtx, basis: str) -> bool:
    msme = ctx.cf.msme
    assert msme is not None
    if msme.paid_up_capital is None:
        raise NotSettled(basis, "paid-up capital not shown")
    holding = msme.group_holding_pct
    return msme.paid_up_capital <= SME_CAPITAL_LIMIT and (holding is None or holding <= SME_GROUP_LIMIT)


def _mypmk(ctx: LineCtx, basis: str) -> date | None:
    """The MyPMK registration date if on or before the processing date (A12 decision 5), else None."""
    msme = ctx.cf.msme
    assert msme is not None
    if not msme.mypmk_status_known:
        raise NotSettled(basis, "MyPMK registration not shown")
    reg = msme.mypmk_registered_on
    return reg if reg is not None and reg <= ctx.processing_date else None


def sme_tenant(ctx: LineCtx) -> bool:
    """K-1 (STP 2/2025 item 4)."""
    reg = _mypmk(ctx, "K-1")
    if reg is None:
        return False
    band = ctx.cf.msme.declared_sales_band
    if band is None:
        raise NotSettled("K-1", "declared sales band not shown")
    start = SME_BAND_FROM.get(band)
    if start is None or not _sme_conditions(ctx, "K-1"):
        return False
    effective = start if reg <= BACKDATE_BY else max(start, reg)
    return ctx.day >= effective


def new_sme(ctx: LineCtx) -> bool:
    """K-2 (STP 2/2025 item 9)."""
    ssm = ctx.cf.msme.ssm_registered_on
    if ssm is None or ctx.day < NEW_SME_FROM or not (ssm <= ctx.day < ssm + timedelta(days=365)):
        return False
    return _mypmk(ctx, "K-2") is not None and _sme_conditions(ctx, "K-2")


def non_reviewable_contract(ctx: LineCtx) -> bool:
    """K-4 (STP 2/2025 item 3)."""
    if not CONTRACT_WINDOW[0] <= ctx.day <= CONTRACT_WINDOW[1]:
        return False
    k = ctx.contract("K-4")
    signed = ctx.fact("contract_signed", k.signed_on if k else None, "K-4")
    if k is None and signed is None:
        return False
    stamped = ctx.fact("contract_stamped", k.stamped_on if k else None, "K-4")
    clause = ctx.fact("price_review_clause", k.has_price_review_clause if k else None, "K-4")
    if signed is None or stamped is None or clause is None or k is None:
        raise NotSettled("K-4", "contract dates or price-review clause not shown")
    states = (k.states_service, k.states_fixed_value, k.states_period)
    if None in states or k.end is None:
        raise NotSettled("K-4", "what the contract states not shown")
    return (not clause and signed <= CONTRACT_DONE_BY and stamped <= CONTRACT_DONE_BY and all(states)
            and k.end > CONTRACT_WINDOW[0] and ctx.supplier_registered("service", "K-4"))


def check(ctx: LineCtx) -> Exempt | None:
    if ctx.group != "K" or ctx.foreign_supplier:
        return None
    if ctx.fact("asset_type", "other", "K-3") in EXEMPT_ASSETS:
        return Exempt("K-3")
    if not ctx.fact("asset_in_malaysia", True, "K-7"):
        # STP 8/2025: beyond 12 nautical miles of the baselines the asset is outside Malaysia.
        return Exempt("K-7")
    if ctx.government_supplier("K-5", NEW_SCOPE_FROM):
        return Exempt("K-5")
    if (not ctx.sf.is_foreign_registered_person and group_relief.related(ctx, "K-6")
            and group_relief.within_5pct(ctx, "K-6")):
        return Exempt("K-6")
    if ctx.cf.msme is not None:
        if new_sme(ctx):
            return Exempt("K-2")
        if sme_tenant(ctx):
            return Exempt("K-1")
    if non_reviewable_contract(ctx):
        return Exempt("K-4")
    return None


def registration_basis(ctx: LineCtx) -> str:
    """K-8 (STP 4/2026): co-owners renting under one agreement are separate suppliers; an invoice in one party's
    name makes that party the supplier, so its registration decides."""
    if ctx.group == "K":
        k = ctx.contract("K-8")
        if k is not None and k.parties:
            return "K-8"
    return "MS-1"
