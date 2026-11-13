"""MyInvois mandatory fields (tax-rule sheet, "E-invoices (MyInvois)")."""

from __future__ import annotations

from ..models import Finding, InvoiceMY
from .constants import MY_EINVOICE_MANDATORY_HEADER, MY_EINVOICE_MANDATORY_LINE
from .findings import finding


def check(inv: InvoiceMY) -> list[Finding]:
    if not inv.is_einvoice:
        return []  # suppliers below the e-invoice threshold send ordinary invoices (plan Q11)
    missing = [name for name in MY_EINVOICE_MANDATORY_HEADER if not getattr(inv, name)]
    for line in inv.lines:
        for name in MY_EINVOICE_MANDATORY_LINE:
            if getattr(line, name) in (None, ""):
                missing.append(f"line{line.line_no}.{name}")
    if not inv.tax_total_by_type:
        missing.append("tax_total_by_type")
    return [finding("MISSING_MANDATORY_FIELD", missing=missing)] if missing else []
