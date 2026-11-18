"""Service tax on one line (MS-1 to MS-4, MS-9; the exemption rules in their own modules).

Order: a supplier that charges service tax must be registered (MS-1 (b)); the service must be in the
First Schedule on the invoice date (MS-1 (a)); then each exclusion or exemption rule in turn; a taxable
line with no tax is undercharged (MS-9); else the rate (MS-2, MS-3).
"""

from __future__ import annotations

from ....findings import UnsupportedCase
from ....models.common import ZERO
from ..constants import TAX_TYPE_SALES
from ..models import MyTaxTreatment as T
from . import areas, b2b, group_relief, rates, scope
from .context import Exempt, LineCtx, Outcome, Partial

LABELS = {"MS-5": "b2b"}
"""The finding label v0.9 keys use for an exemption (others use the rule ID)."""
EXEMPTIONS = (scope.exclusion, lambda ctx: areas.check(ctx, "MS-7"), group_relief.check, b2b.check)
"""The exclusion and exemption rules, in the order they are tried."""


def assess(ctx: LineCtx) -> Outcome:
    if ctx.charged and ctx.tax_type == TAX_TYPE_SALES:
        raise UnsupportedCase(f"sales tax on {ctx.line.category}, outside the planted v0.9 situations")
    if ctx.charged and not ctx.supplier_registered("service", "MS-1"):
        return ctx.not_registered("service", "MS-1")
    if not scope.in_schedule(ctx.item, ctx.day):
        return ctx.exempt(Exempt("MS-1"), "not_taxable")
    partials: list[Partial] = []
    for rule in EXEMPTIONS:
        result = rule(ctx)
        if isinstance(result, Exempt):
            return ctx.exempt(result, LABELS.get(result.basis))
        if isinstance(result, Partial):
            partials.append(result)
    if not ctx.charged:
        if any(p.taxable <= ZERO for p in partials):
            return Outcome(T.NO_SST, partials[0].basis)
        if not ctx.supplier_registered("service", "MS-1"):
            return Outcome(T.NO_SST, "MS-1")
        return ctx.undercharged("MS-9", "service")
    return rates.check_rate(ctx, partials)
