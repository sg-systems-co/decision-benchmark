"""Sales tax (MG): who may charge it, rates, exemptions.

v0.9 logic, moved here unchanged; A12 build PR 2 commit 11 adds MG-1 to MG-6 and G-1 to G-7.
"""

from __future__ import annotations

from ....findings import UnsupportedCase
from ..constants import TAX_CLASS_RATE
from ..models import MyTaxTreatment as T
from .context import Exempt, LineCtx, Outcome


def _schedule_c_holds(ctx: LineCtx) -> bool:
    if not ctx.cf.is_registered_manufacturer:
        return False
    return any(cert.kind == "schedule_c" and cert.valid_on(ctx.day) and ctx.line.category in cert.categories
               for cert in ctx.company.policy_pack.exemption_certificates)


def assess(ctx: LineCtx) -> Outcome:
    if not ctx.charged:
        return Outcome(T.NO_SST, "MG-1")
    cls = ctx.profile.tax_class
    if cls == "sales_exempt":
        raise UnsupportedCase(f"sales tax on {ctx.line.category}, outside the planted v0.9 situations")
    if not ctx.supplier_registered("sales", "MG-1"):
        return ctx.not_registered("sales", "MG-1")
    if not ctx.sf.is_manufacturer:
        raise UnsupportedCase("sales tax charged by a registered non-manufacturer, outside the v0.9 rule sheet")
    if ctx.profile.schedule_c_eligible and _schedule_c_holds(ctx):
        return ctx.exempt(Exempt("MG-4"), "schedule_c")
    expected = TAX_CLASS_RATE[cls]
    if ctx.line.tax_rate != expected:
        return ctx.wrong_rate("MG-2", expected)
    return Outcome(T.SST_CORRECT, "MG-2")
