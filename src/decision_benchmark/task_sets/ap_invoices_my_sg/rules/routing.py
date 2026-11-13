"""No PO and approval limits (step-11 plan §5.3)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..models import Finding
from .findings import UnsupportedCase, finding
from .matching import PoResolution
from .view import CaseView

CENT = Decimal("0.01")


def gross_in_base(view: CaseView) -> Decimal | None:
    """Invoice gross in the company's base currency, at the invoice's own stated rate. None if unknown."""
    inv = view.invoice
    base = view.company.base_currency
    if inv.currency == base:
        return inv.totals.gross
    if inv.country == "SG" and inv.gross_sgd is not None:
        return inv.gross_sgd
    if inv.exchange_rate is not None:
        return (inv.totals.gross * inv.exchange_rate).quantize(CENT, ROUND_HALF_UP)
    return None


def check(view: CaseView, po_res: PoResolution, blocking_found: bool) -> list[Finding]:
    """Routing findings. ``blocking_found``: a higher-tier finding exists, so an unknown amount is acceptable."""
    amount = gross_in_base(view)
    if amount is None:
        if blocking_found:
            return []
        raise UnsupportedCase("invoice amount in base currency is unknown")
    if po_res.po is None:
        policy = view.policy.non_po_policy
        cats = {line.category for line in view.invoice.lines}
        if cats <= set(policy.allowed_categories) and amount <= policy.max_amount:
            return []
        return [finding("NO_PO", amount=f"{amount:.2f}")]
    approver = view.company.person(po_res.po.approver_id)
    if approver is None or approver.approval_role is None:
        raise UnsupportedCase("PO approver has no approval role")
    limit = view.policy.limit_for(approver.approval_role)
    if limit is None or limit.currency != view.company.base_currency:
        raise UnsupportedCase("approval matrix has no limit for the PO approver")
    if amount > limit.limit:
        return [
            finding(
                "ABOVE_APPROVAL_LIMIT",
                amount=f"{amount:.2f}",
                limit=f"{limit.limit:.2f}",
                approver_id=approver.person_id,
            )
        ]
    return []
