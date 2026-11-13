"""Finding codes, their priority tier, their order and the decision each one sets.

The order is the spec's priority (fraud, duplicate, invalid invoice, mismatch,
routing), with a fixed order inside each tier (step-11 plan §5.2, Q7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import Decision, Finding, Tier

ORDER: tuple[tuple[str, Tier, Decision], ...] = (
    ("BANK_DETAILS_DIFFER_FROM_RECORD", Tier.FRAUD, Decision.FRAUD_REVIEW),
    ("BANK_CHANGE_BY_EMAIL_ONLY", Tier.FRAUD, Decision.FRAUD_REVIEW),
    ("DUPLICATE_INVOICE", Tier.DUPLICATE, Decision.REJECT_DUPLICATE),
    ("NEAR_DUPLICATE", Tier.DUPLICATE, Decision.REJECT_DUPLICATE),
    ("MISSING_MANDATORY_FIELD", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("INVALID_TAX_INVOICE", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("FOREIGN_CURRENCY_NO_SGD_AMOUNTS", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("SUPPLIER_NOT_TAX_REGISTERED", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("OVR_GST_CHARGED_TO_REGISTERED_BUYER", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("TAX_SHOULD_BE_EXEMPT", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("WRONG_TAX_RATE", Tier.INVALID_INVOICE, Decision.REQUEST_CORRECTED_INVOICE),
    ("NOT_RECEIVED", Tier.MISMATCH, Decision.HOLD_NOT_RECEIVED),
    ("QUANTITY_ABOVE_RECEIVED", Tier.MISMATCH, Decision.DISPUTE_QUANTITY),
    ("PRICE_ABOVE_PO", Tier.MISMATCH, Decision.DISPUTE_PRICE),
    ("NO_PO", Tier.ROUTING, Decision.ROUTE_FOR_APPROVAL),
    ("ABOVE_APPROVAL_LIMIT", Tier.ROUTING, Decision.ROUTE_FOR_APPROVAL),
)

RANK = {code: i for i, (code, _, _) in enumerate(ORDER)}
TIER = {code: tier for code, tier, _ in ORDER}
DECISION = {code: decision for code, _, decision in ORDER}

CLEAN_REASON = "MATCHED_WITHIN_TOLERANCE"
DISALLOWED_REASON = "GST_NOT_CLAIMABLE_DISALLOWED"
HANDOVER_REASON = "CANNOT_SETTLE_FROM_RULES"


class UnsupportedCase(Exception):
    """The case contains a situation the v0.9 rules don't cover. The generator must redraw it.

    The engine raises this instead of guessing.
    """


@dataclass(frozen=True)
class Unsettled:
    """The official rules don't settle the case from the facts available: HAND_OVER by construction."""

    reason: str
    tax_related: bool


def finding(code: str, **evidence: Any) -> Finding:
    return Finding(code=code, tier=TIER[code], evidence=evidence)


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Stable sort by priority; one finding per code (the first one found)."""
    seen: set[str] = set()
    out = []
    for f in sorted(findings, key=lambda f: RANK[f.code]):
        if f.code not in seen:
            seen.add(f.code)
            out.append(f)
    return out
