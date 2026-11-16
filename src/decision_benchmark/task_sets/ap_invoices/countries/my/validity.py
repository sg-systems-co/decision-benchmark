"""MyInvois mandatory fields (rule sheet row 12). Ordinary invoices below the threshold are not checked (plan Q11)."""

from __future__ import annotations

from ...codes import Code
from ...findings import finding
from ...models import Finding, Invoice
from .constants import EINVOICE_MANDATORY_HEADER, EINVOICE_MANDATORY_LINE
from .models import MyInvois

BASE_LINE_FIELDS = ("description", "unit_price")


def check(inv: Invoice) -> list[Finding]:
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    if not e.is_einvoice:
        return []
    missing = [name for name in EINVOICE_MANDATORY_HEADER if not getattr(e if hasattr(e, name) else inv, name)]
    ext = {x.line_no: x for x in e.lines}
    for line in inv.lines:
        for name in EINVOICE_MANDATORY_LINE:
            source = line if name in BASE_LINE_FIELDS else ext.get(line.line_no)
            if getattr(source, name, None) in (None, ""):
                missing.append(f"line{line.line_no}.{name}")
    if not e.tax_total_by_type:
        missing.append("tax_total_by_type")
    return [finding(Code.MISSING_MANDATORY_FIELD, missing=missing)] if missing else []
