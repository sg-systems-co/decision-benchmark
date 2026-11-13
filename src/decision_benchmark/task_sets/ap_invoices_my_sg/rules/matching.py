"""PO, receipt, quantity and price matching; totals tie-out (step-11 plan §5.3)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ..models import Finding, PurchaseOrder
from .findings import UnsupportedCase, finding
from .view import CaseView

ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class PoResolution:
    po: PurchaseOrder | None
    ambiguous: bool


def resolve_po(view: CaseView) -> PoResolution:
    """The invoice's PO: the referenced one, else the single fitting open PO; two or more fitting POs is ambiguous."""
    pos = view.purchase_orders
    ref = view.invoice.po_reference
    if ref:
        match = [p for p in pos if p.po_number == ref]
        if match:
            return PoResolution(match[0], False)
    if len(pos) == 1:
        return PoResolution(pos[0], False)
    return PoResolution(None, len(pos) > 1)


def check_totals(view: CaseView) -> None:
    """Totals must tie within the rounding tolerance. A bigger gap has no rule in v0.9 (plan Q33)."""
    inv = view.invoice
    tol = view.policy.tolerance_policy.rounding_tolerance
    for line in inv.lines:
        if line.unit_price is not None:
            expected = (line.qty * line.unit_price).quantize(CENT, ROUND_HALF_UP)
            if abs(expected - line.net_amount) > CENT:
                raise UnsupportedCase(f"line {line.line_no}: qty x unit price does not give the net amount")
    net = sum((line.net_amount for line in inv.lines), ZERO)
    tax = sum((line.tax_amount for line in inv.lines), ZERO)
    gaps = [abs(net - inv.totals.net)]
    if inv.totals.tax is not None:
        gaps.append(abs(tax - inv.totals.tax))
        gaps.append(abs(inv.totals.net + inv.totals.tax + inv.totals.rounding - inv.totals.gross))
    else:
        gaps.append(abs(inv.totals.net + tax + inv.totals.rounding - inv.totals.gross))
    if any(g > tol for g in gaps):
        raise UnsupportedCase("totals don't tie within the rounding tolerance")


def po_unit_price(po: PurchaseOrder, line_no: int, day) -> Decimal:
    line = po.line(line_no)
    assert line is not None
    price = line.unit_price
    for a in sorted(po.amendments, key=lambda a: a.amended_on):
        if a.line_no == line_no and a.field == "unit_price" and a.approved_by and a.amended_on <= day:
            price = a.new
    return price


@dataclass(frozen=True)
class MatchResult:
    findings: list[Finding]
    max_variance_pct: Decimal | None


def line_map(view: CaseView, po: PurchaseOrder) -> dict[int, int]:
    """Invoice line number -> PO line number."""
    out = {}
    for i, line in enumerate(view.invoice.lines):
        po_line_no = line.po_line_no if line.po_line_no is not None else (
            po.lines[i].line_no if i < len(po.lines) else None
        )
        if po_line_no is None or po.line(po_line_no) is None:
            raise UnsupportedCase(f"invoice line {line.line_no} has no PO line")
        out[line.line_no] = po_line_no
    return out


def check(view: CaseView, po: PurchaseOrder, exclude_ledger_ids: frozenset[str] = frozenset()) -> MatchResult:
    """``exclude_ledger_ids``: history items this invoice duplicates; their quantities are not 'already invoiced'."""
    inv = view.invoice
    tp = view.policy.tolerance_policy
    day = view.as_of_date
    mapping = line_map(view, po)

    received: dict[int, Decimal] = {}
    for gr in view.goods_receipts:
        if gr.po_number == po.po_number:
            for gl in gr.lines:
                received[gl.po_line_no] = received.get(gl.po_line_no, ZERO) + gl.qty_received
    invoiced: dict[int, Decimal] = {}
    for h in view.history:
        old = h.invoice
        if h.ledger_id in exclude_ledger_ids:
            continue
        if old.doc_type == "invoice" and old.po_reference == po.po_number:
            for i, line in enumerate(old.lines):
                pl = line.po_line_no if line.po_line_no is not None else (
                    po.lines[i].line_no if i < len(po.lines) else None
                )
                if pl is not None:
                    invoiced[pl] = invoiced.get(pl, ZERO) + line.qty
    # Credit notes against the PO reduce what was invoiced.
    for h in view.history:
        cn = h.invoice
        if cn.doc_type == "credit_note" and cn.po_reference == po.po_number:
            for line in cn.lines:
                if line.po_line_no is not None:
                    invoiced[line.po_line_no] = invoiced.get(line.po_line_no, ZERO) - line.qty

    out: list[Finding] = []
    billed_lines = list(mapping.values())
    if all(received.get(pl, ZERO) <= ZERO for pl in billed_lines):
        out.append(finding("NOT_RECEIVED", po_number=po.po_number))
    else:
        for line in inv.lines:
            pl = mapping[line.line_no]
            billable = received.get(pl, ZERO) - invoiced.get(pl, ZERO)
            if line.qty > billable + tp.quantity_tolerance_units:
                out.append(
                    finding(
                        "QUANTITY_ABOVE_RECEIVED",
                        line=line.line_no,
                        billed=str(line.qty),
                        received_not_yet_invoiced=str(billable),
                    )
                )

    max_var: Decimal | None = None
    for line in inv.lines:
        if line.unit_price is None:
            continue
        pl = mapping[line.line_no]
        po_price = po_unit_price(po, pl, day)
        if po_price <= ZERO:
            raise UnsupportedCase("PO unit price is zero")
        diff = line.unit_price - po_price
        var = (diff / po_price * 100).quantize(CENT, ROUND_HALF_UP)
        max_var = var if max_var is None else max(max_var, var)
        allowed = po_price * tp.price_tolerance_pct / 100
        if tp.price_tolerance_abs is not None:
            allowed = max(allowed, tp.price_tolerance_abs)
        if diff > allowed:
            out.append(
                finding(
                    "PRICE_ABOVE_PO",
                    line=line.line_no,
                    po=f"{po_price:.2f}",
                    invoice=f"{line.unit_price:.2f}",
                    variance_pct=str(var),
                )
            )
    return MatchResult(out, max_var)
