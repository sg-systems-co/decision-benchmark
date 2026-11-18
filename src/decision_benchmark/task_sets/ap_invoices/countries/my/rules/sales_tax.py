"""Sales tax on one goods line: MG-1 to MG-6 and G-1, G-3 to G-5 (rule sheet v0.10 section 2).

Sales tax is single-stage: only a registered manufacturer charges it, on taxable goods it manufactured and
sold (MG-1). The rate is the goods category's (the catalog takes it from the Rate of Sales Tax Order 2025;
v0.9 clarification), judged at the invoice date (MG-3). Exemptions: designated areas (MG-5), the Sales Tax
Policies by tariff code (G-1; G-3 works by refund, so the tax on the invoice is correct), drop-shipment
exports (G-5), the buyer's Schedule A, B or C certificate (MG-4; pallets only as one-way packaging, G-4) and
goods the category marks exempt (MG-2). G-2, G-6 and G-7 have no invoice effect (not engine rules).
"""

from __future__ import annotations

from ....findings import finding
from ....codes import Code
from ..constants import TAX_CLASS_RATE, TAX_TYPE_SERVICE
from ..models import MyTaxTreatment as T
from .. import tariffs
from . import areas
from .context import Exempt, LineCtx, Outcome, Taxable

CERTIFICATE_KINDS = ("schedule_a", "schedule_b", "schedule_c")
SALES_LABELS = {"MG-4": "schedule_c"}
"""The finding label v0.9 keys use for a Schedule C exemption."""


def _certificate(ctx: LineCtx) -> Exempt | Taxable | None:
    """MG-4: the buyer holds a Schedule A, B or C certificate covering the goods on the invoice date."""
    held = {cert.kind for cert in ctx.company.policy_pack.exemption_certificates
            if cert.kind in CERTIFICATE_KINDS and cert.valid_on(ctx.day) and ctx.line.category in cert.categories}
    if "schedule_c" in held and not (ctx.cf.is_registered_manufacturer and ctx.profile.schedule_c_eligible):
        held.discard("schedule_c")
    if not held:
        return None
    if held == {"schedule_c"}:
        returnable = ctx.fact("pallet_returnable", None, "G-4")
        if returnable is not None:
            # G-4 (Sales Tax Policy 1/2022): pallets are Schedule C packaging only one-way; returnable ones are taxable.
            return Taxable("G-4") if returnable else Exempt("G-4")
    return Exempt("MG-4")


def _policy(ctx: LineCtx) -> Exempt | Taxable | None:
    code = ctx.fact("tariff_code", None, "MG-2")
    row = tariffs.find(code) if code else None
    if row is None or row.rule == "G-2":
        return None
    if ctx.day < row.effective_from:
        return Taxable("MG-3")
    return Exempt("G-1") if row.rule == "G-1" else Taxable("G-3")


def assess(ctx: LineCtx) -> Outcome:
    n = ctx.line.line_no
    if ctx.charged and ctx.tax_type == TAX_TYPE_SERVICE:
        # Service tax on goods: not a taxable service; on a construction invoice the separated materials (L-8).
        basis = "L-8" if ctx.fact("materials_works_separated", None, "L-8") else "MS-1"
        return ctx.exempt(Exempt(basis), "not_taxable")
    if ctx.foreign_supplier:
        # Sales tax on imported goods is charged at import, not on the overseas supplier's invoice.
        if not ctx.charged:
            return Outcome(T.NO_SST, "MG-1")
        if not ctx.supplier_registered("sales", "MG-1"):
            return ctx.not_registered("sales", "MG-1")
    registered = ctx.supplier_registered("sales", "MG-1")
    if ctx.charged and not registered:
        return ctx.not_registered("sales", "MG-1")
    made = registered and ctx.fact("manufactured_by_supplier", ctx.sf.is_manufacturer, "MG-1")
    if ctx.charged and not made:
        return Outcome(T.SST_NOT_CHARGEABLE_BY_TRADER, "MG-1", (
            finding(Code.SALES_TAX_CHARGED_BY_TRADER, line=n),))
    if not made:
        return Outcome(T.NO_SST, "MG-1")
    taxable_by = None
    for rule in (lambda c: areas.check(c, "MG-5"), _policy, _drop_shipment, _certificate, _exempt_goods):
        result = rule(ctx)
        if isinstance(result, Exempt):
            return ctx.exempt(result, SALES_LABELS.get(result.basis))
        if isinstance(result, Taxable):
            taxable_by = result.basis
    if not ctx.charged:
        return ctx.undercharged("MS-9", "sales")
    expected = TAX_CLASS_RATE[ctx.profile.tax_class]
    if ctx.line.tax_rate != expected:
        return ctx.wrong_rate("MG-2", expected)
    return Outcome(T.SST_CORRECT, taxable_by or "MG-2")


def _drop_shipment(ctx: LineCtx) -> Exempt | None:
    """G-5 (Sales Tax Policy 2/2022): a registered manufacturer exporting directly for a Malaysian trader."""
    return Exempt("G-5") if ctx.fact("drop_shipment_export", False, "G-5") else None


def _exempt_goods(ctx: LineCtx) -> Exempt | None:
    """MG-2: goods the Goods Exempted Order exempts (the category's class)."""
    return Exempt("MG-2") if ctx.profile.tax_class == "sales_exempt" else None
