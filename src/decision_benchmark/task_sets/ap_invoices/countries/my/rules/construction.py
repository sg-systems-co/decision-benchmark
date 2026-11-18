"""Group L construction works: L-1 to L-4, L-6 to L-8 (rule sheet v0.10 MS-4 Group L).

Ministerial exemptions in STP 3/2025 (Amendment No. 3), 30 Jan 2026, STP 7/2025, 2/2026 and 5/2026. The
Regulations' exclusion of residential buildings is in scope.py (MS-4); the B2B exemption (order item 9) in
b2b.py.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....findings import NotSettled
from ..constants import TAX_TYPE_SALES, TAX_TYPE_SERVICE
from ..models import MyContractFacts
from .b2b import WHOLE
from .context import Exempt, LineCtx, Partial, Taxable
from .scope import NEW_SCOPE_FROM

CONTRACT_EXEMPT_TO = date(2027, 6, 30)
"""L-1: work under non-reviewable contracts is exempt to 30 Jun 2027."""
COMPLETED_HOMES_FROM = date(2025, 7, 1)
SIGNED_BEFORE = date(2025, 7, 1)
STAMPED_BEFORE = date(2025, 12, 31)
DESIGN_AND_BUILD_ITEMS = ("G(a)", "G(c)", "G(d)", "G(e)", "G(f)", "G(g)", "G(i)", "G(n)")
"""L-3: consultants under these items to a registered main contractor on a design-and-build project."""
SALES_TAX_RATES = (Decimal(5), Decimal(10))


def _contract_facts(ctx: LineCtx, basis: str) -> MyContractFacts | None:
    k = ctx.contract(basis)
    facts = k.tax_facts if k is not None else None
    return facts if isinstance(facts, MyContractFacts) else None


def _change_qualifies(signed: date | None, stamped: date | None, changes_value: bool | None) -> bool:
    if signed is None or stamped is None or changes_value is None:
        raise NotSettled("L-1", "variation order or extension of time not shown in full")
    return not changes_value and signed < SIGNED_BEFORE and stamped < STAMPED_BEFORE


def non_reviewable_contract(ctx: LineCtx) -> bool:
    """L-1 (STP 3/2025 (Amdt 3))."""
    if ctx.day > CONTRACT_EXEMPT_TO:
        return False
    k = ctx.contract("L-1")
    signed = ctx.fact("contract_signed", k.signed_on if k else None, "L-1")
    if k is None and signed is None:
        return False
    stamped = ctx.fact("contract_stamped", k.stamped_on if k else None, "L-1")
    clause = ctx.fact("price_review_clause", k.has_price_review_clause if k else None, "L-1")
    if signed is None or stamped is None or clause is None or k is None:
        raise NotSettled("L-1", "contract dates or price-review clause not shown")
    states = (k.states_service, k.states_fixed_value, k.states_period)
    if None in states or k.end is None:
        raise NotSettled("L-1", "what the contract states not shown")
    if clause or not all(states) or signed >= SIGNED_BEFORE or stamped >= STAMPED_BEFORE or k.end < SIGNED_BEFORE:
        return False
    if ctx.day > k.end:
        # Work after the contract's end falls under extensions of time; each must qualify.
        if not k.extensions_of_time or not all(
                _change_qualifies(x.signed_on, x.stamped_on, x.changes_value) for x in k.extensions_of_time):
            return False
    vo_signed = ctx.fact("variation_signed", None, "L-1")
    if vo_signed is not None:
        # The line bills a variation order: it qualifies only on the VO's own terms.
        if not _change_qualifies(vo_signed, ctx.need("variation_stamped", "L-1"),
                                 ctx.need("variation_changes_value", "L-1")):
            return False
    return ctx.supplier_registered("service", "L-1")


def mixed_development(ctx: LineCtx) -> Exempt | Partial | None:
    """L-2: the residential part of a mixed development is exempt, with a split and a stamped contract stating it."""
    share = ctx.fact("residential_share", None, "L-2")
    if share is None:
        return None
    facts = _contract_facts(ctx, "L-2")
    stated = ctx.fact("mixed_development_stated", facts.mixed_development_stated if facts else None, "L-2")
    if stated is None:
        raise NotSettled("L-2", "contract stating mixed development not shown")
    if not stated:
        return None
    return Exempt("L-2") if share >= WHOLE else Partial("L-2", ctx.net * (WHOLE - share))


def design_and_build(ctx: LineCtx) -> Exempt | None:
    """L-3: a consultant (G(a), (c)-(g), (i), (n)) to a registered main contractor on a design-and-build project,
    with the planning permission and contract numbers on the invoice."""
    if ctx.item not in DESIGN_AND_BUILD_ITEMS or ctx.foreign_supplier:
        return None
    facts = _contract_facts(ctx, "L-3")
    dnb = ctx.fact("design_and_build", facts.design_and_build if facts and facts.design_and_build is not None else False,
                   "L-3")
    if not dnb or not (ctx.buyer_registered() and ctx.buyer_provides("L")):
        return None
    return Exempt("L-3") if ctx.fact("exemption_statement_on_invoice", False, "L-3") else None


def completed_home(ctx: LineCtx) -> Exempt | Taxable | None:
    """L-5 (STP 2/2026, from 1 Jul 2025): construction work on a completed residential building is exempt when the
    invoice names the recipient and shows the residential address; without them it stays taxable."""
    if not (ctx.fact("residential", False, "L-5") and ctx.fact("completed_building", False, "L-5")):
        return None
    if ctx.day < COMPLETED_HOMES_FROM:
        return None
    named = bool(ctx.invoice.buyer_block.name and ctx.invoice.buyer_block.address)
    return Exempt("L-5") if named else Taxable("L-5")


def check(ctx: LineCtx) -> Exempt | Partial | Taxable | None:
    if ctx.group != "L" or ctx.foreign_supplier:
        return design_and_build(ctx)
    if ctx.government_supplier("L-7", NEW_SCOPE_FROM):
        return Exempt("L-7")
    if ctx.fact("place_of_worship", False, "L-4"):
        return Exempt("L-4")
    completed = completed_home(ctx)
    if completed is not None:
        return completed
    if not ctx.fact("client_established_in_malaysia", True, "L-6"):
        # STP 5/2026: offshore and onshore facilities for a client not established in Malaysia, with the statement.
        if ctx.fact("exemption_statement_on_invoice", False, "L-6"):
            return Exempt("L-6")
    mixed = mixed_development(ctx)
    if mixed is not None:
        return mixed
    if non_reviewable_contract(ctx):
        return Exempt("L-1")
    return None


def expected_tax_type(ctx: LineCtx) -> str | None:
    """L-8 (STP 7/2025): which tax a construction line bears when the documents name it. Ships and platforms:
    the company's election (item 1). Installation by a registered sales-tax manufacturer not shown separately:
    sales tax on the whole value (item 2). None: the line takes service tax as usual."""
    if ctx.group != "L":
        return None
    election = ctx.fact("ship_platform_election", None, "L-8")
    if election is not None:
        return TAX_TYPE_SALES if election == "manufacturing" else TAX_TYPE_SERVICE
    separated = ctx.fact("installation_separated", None, "L-8")
    if separated is False:
        manufacturer = ctx.sf.is_manufacturer and ctx.supplier_registered("sales", "L-8")
        return TAX_TYPE_SALES if manufacturer else TAX_TYPE_SERVICE
    return None


def sales_rate_ok(ctx: LineCtx) -> bool:
    return ctx.line.tax_rate in SALES_TAX_RATES
