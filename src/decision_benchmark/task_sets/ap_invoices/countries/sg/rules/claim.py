"""Can the buyer claim the GST on a line it was rightly charged? SG-1 and SG-10 (rule sheet v0.10 section 4).

SG-10 here is the v0.9 Regulations 26/27 logic; A12 build PR 3 commit 14 adds the v0.10 list (motor-car
exceptions, director-only benefits, CSR) and SG-9 (partially exempt buyers). SG-1 condition 8 (missing-trader
fraud) is not modelled (A12 decision 6).
"""

from __future__ import annotations

from ....findings import NotSettled
from ..models import SgTaxTreatment as T
from .context import LineCtx, Outcome


def assess(ctx: LineCtx) -> Outcome:
    cls = ctx.profile.disallowed
    if cls == "motor_car":
        return _depends(ctx, "vehicle_is_motor_car", "vehicle_regulation_25_1_unclear", disallowed_if=True)
    if cls == "staff_medical":
        return _depends(ctx, "staff_medical_obligatory", "staff_medical_obligation_unclear", disallowed_if=False)
    if cls == "medical_accident_insurance":
        # Claimable when obligatory under the Work Injury Compensation Act or a collective agreement.
        return _depends(ctx, "insurance_obligatory", "insurance_obligation_unclear", disallowed_if=False)
    if cls is not None:
        return Outcome(T.NOT_CLAIMABLE_DISALLOWED, "SG-10")
    if not ctx.fact("business_purpose", True, "SG-1"):
        # SG-1: not for the purpose of the business.
        return Outcome(T.NOT_CLAIMABLE_DISALLOWED, "SG-1")
    return Outcome(T.CLAIMABLE, "SG-1")


def _depends(ctx: LineCtx, name: str, reason: str, disallowed_if: bool) -> Outcome:
    value = ctx.reader.value(name)
    if value is None:
        raise NotSettled("SG-10", reason)
    return Outcome(T.NOT_CLAIMABLE_DISALLOWED if value == disallowed_if else T.CLAIMABLE, "SG-10")
