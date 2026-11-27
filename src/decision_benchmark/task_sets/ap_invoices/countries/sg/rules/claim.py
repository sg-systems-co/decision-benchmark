"""Can the buyer claim the GST on a line it was rightly charged? SG-1, SG-9, SG-10 (rule sheet v0.10 section 4).

SG-10: Regulations 26/27 and the related IRAS rules (club fees, staff medical and insurance with their
exceptions, motor cars with the Regulation 25(1) exclusions and the chauffeured and third-party exceptions,
family benefits, betting, benefits for directors only, CSR for third parties). SG-9: a partially exempt buyer
(de minimis not met) can't claim input tax directly attributable to exempt supplies; residual input tax is
apportioned; a buyer that meets the de minimis rule claims them in full, by SG-9 (engine 0.10.5; a line used for
taxable supplies stays SG-1). SG-1 condition 8 (missing-trader fraud) is not modelled (A12 decision 6).
"""

from __future__ import annotations

from datetime import date

from ....findings import NotSettled
from ..models import SgTaxTreatment as T
from .context import LineCtx, Outcome

CHAUFFEURED_FROM = date(2022, 4, 1)
"""Pay-per-trip chauffeured private hire car services are claimable from 1 Apr 2022."""
THIRD_PARTY_CAR_FROM = date(2023, 1, 1)
"""A motor car used by a third party is claimable from 1 Jan 2023, on the IRAS conditions."""
BSPV_REGISTERED_BEFORE = date(1998, 4, 1)
"""Regulation 25(1): a business service passenger vehicle registered before 1 Apr 1998 is not a motor car."""
ALWAYS_DISALLOWED = ("club_subscription", "family_benefit", "betting", "director_only_benefit", "third_party_csr")


def assess(ctx: LineCtx) -> Outcome:
    out = _regulations(ctx)
    if out is not None:
        return out
    if not ctx.fact("business_purpose", True, "SG-1"):
        return Outcome(T.NOT_CLAIMABLE_DISALLOWED, "SG-1")
    return _partial_exemption(ctx) or Outcome(T.CLAIMABLE, "SG-1")


def _regulations(ctx: LineCtx) -> Outcome | None:
    cls = ctx.fact("disallowed_category", ctx.profile.disallowed or "none", "SG-10")
    if cls == "none":
        return None
    if cls in ALWAYS_DISALLOWED:
        return Outcome(T.NOT_CLAIMABLE_DISALLOWED, "SG-10")
    if cls == "motor_car":
        if ctx.day >= CHAUFFEURED_FROM and ctx.fact("chauffeured_pay_per_trip", False, "SG-10"):
            return Outcome(T.CLAIMABLE, "SG-10")
        if ctx.day >= THIRD_PARTY_CAR_FROM and ctx.fact("car_used_by_third_party", False, "SG-10"):
            return Outcome(T.CLAIMABLE, "SG-10")
        if ctx.reader.value("vehicle_is_motor_car") is None:
            registered = ctx.fact("vehicle_registered_on", None, "SG-10")
            if registered is not None:
                # A business service passenger vehicle: not a motor car if registered before 1 Apr 1998.
                return Outcome(T.CLAIMABLE if registered < BSPV_REGISTERED_BEFORE else T.NOT_CLAIMABLE_DISALLOWED,
                               "SG-10")
        return _depends(ctx, "vehicle_is_motor_car", "vehicle_regulation_25_1_unclear", disallowed_if=True)
    if cls == "staff_medical":
        return _depends(ctx, "staff_medical_obligatory", "staff_medical_obligation_unclear", disallowed_if=False)
    # medical_accident_insurance: claimable when obligatory under the Work Injury Compensation Act or a collective
    # agreement.
    return _depends(ctx, "insurance_obligatory", "insurance_obligation_unclear", disallowed_if=False)


def _depends(ctx: LineCtx, name: str, reason: str, disallowed_if: bool) -> Outcome:
    value = ctx.reader.value(name)
    if value is None:
        raise NotSettled("SG-10", reason)
    return Outcome(T.NOT_CLAIMABLE_DISALLOWED if value == disallowed_if else T.CLAIMABLE, "SG-10")


def _partial_exemption(ctx: LineCtx) -> Outcome | None:
    status = ctx.cf.input_tax_status
    if status is None:
        raise NotSettled("SG-9", "buyer's input-tax status not shown")
    if status == "fully_taxable":
        return None
    attribution = ctx.need("purchase_attribution", "SG-9")
    if status == "de_minimis_met":
        # The de minimis rule (SG-9) lets the buyer claim input tax on exempt and residual purchases in full; a
        # purchase used for taxable supplies is claimable by SG-1. Not shown: the basis isn't settled -> HAND_OVER.
        return None if attribution == "taxable" else Outcome(T.CLAIMABLE, "SG-9")
    if attribution == "exempt":
        return Outcome(T.NOT_CLAIMABLE_EXEMPT_USE, "SG-9")
    if attribution == "residual":
        return Outcome(T.RESIDUAL_APPORTIONED, "SG-9")
    return Outcome(T.CLAIMABLE, "SG-9")
