"""Findings -> decision by fixed priority -> answer key (step-11 plan §5.2, §5.3).

``compute_answer`` is the only function that writes answer keys. It raises
``UnsupportedCase`` for any situation outside the v0.9 rules, so the generator
redraws the case instead of the engine guessing.
"""

from __future__ import annotations

from ..models import AnswerKey, AnswerSource, Catalog, Decision, Finding, InvoiceMY, InvoiceSG, TaxTreatment
from . import duplicates, fraud, gl, matching, routing, tax_my, tax_sg, validity_my
from .findings import (
    CLEAN_REASON,
    DECISION,
    DISALLOWED_REASON,
    HANDOVER_REASON,
    UnsupportedCase,
    Unsettled,
    sort_findings,
)
from .view import CaseView

SUPPLIER_CONTACT = {Decision.DISPUTE_PRICE, Decision.DISPUTE_QUANTITY, Decision.REQUEST_CORRECTED_INVOICE}


def compute_answer(view: CaseView, catalog: Catalog) -> AnswerKey:
    inv = view.invoice
    is_credit_note = inv.doc_type == "credit_note"
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []

    matching.check_totals(view)
    findings += fraud.check(view)
    findings += duplicates.check(view)

    tax: TaxTreatment | None
    if isinstance(inv, InvoiceMY):
        findings += validity_my.check(inv)
        tax, tax_findings, tax_unsettled = tax_my.assess(inv, view.supplier, view.company, catalog)
    else:
        assert isinstance(inv, InvoiceSG)
        tax, tax_findings, tax_unsettled = tax_sg.assess(inv, view.supplier, catalog)
    findings += tax_findings
    unsettled += tax_unsettled

    po_res = matching.resolve_po(view)
    variance = None
    mapping = None
    if is_credit_note:
        _check_credit_note(view)
    else:
        if po_res.ambiguous:
            unsettled.append(Unsettled("two_purchase_orders_fit", tax_related=False))
        elif po_res.po is not None:
            mapping = matching.line_map(view, po_res.po)
            dup_ids = frozenset(
                str(f.evidence["ledger_id"]) for f in findings if f.code in ("DUPLICATE_INVOICE", "NEAR_DUPLICATE")
            )
            match = matching.check(view, po_res.po, exclude_ledger_ids=dup_ids)
            findings += match.findings
            variance = match.max_variance_pct
        if not po_res.ambiguous:
            blocking = any(f.tier <= 3 for f in findings)
            findings += routing.check(view, po_res, blocking_found=blocking)
    if po_res.po is not None and mapping is None:
        mapping = matching.line_map(view, po_res.po)

    gl_account = gl.account(view, po_res.po, mapping, catalog)
    findings = sort_findings(findings)

    if unsettled:
        if findings:
            raise UnsupportedCase("a case the rules don't settle also has another problem (plan Q14)")
        return AnswerKey(
            case_id=view.case_id,
            decision=Decision.HAND_OVER,
            tax_treatment=None if any(u.tax_related for u in unsettled) else tax,
            gl_account=gl_account,
            reason_codes=[HANDOVER_REASON],
            answer_source=AnswerSource.HANDOVER_BY_CONSTRUCTION,
            findings=[],
            truth_supplier_id=view.supplier.supplier_id,
            truth_po_number=po_res.po.po_number if po_res.po else None,
            truth_price_variance_pct=variance,
            requires_supplier_contact=False,
        )

    assert tax is not None
    decision = DECISION[findings[0].code] if findings else Decision.APPROVE
    reasons = [f.code for f in findings] or [CLEAN_REASON]
    if tax is TaxTreatment.NOT_CLAIMABLE_DISALLOWED:
        reasons.append(DISALLOWED_REASON)
    return AnswerKey(
        case_id=view.case_id,
        decision=decision,
        tax_treatment=tax,
        gl_account=gl_account,
        reason_codes=reasons,
        answer_source=AnswerSource.RULES,
        findings=findings,
        truth_supplier_id=view.supplier.supplier_id,
        truth_po_number=po_res.po.po_number if po_res.po else None,
        truth_price_variance_pct=variance,
        requires_supplier_contact=decision in SUPPLIER_CONTACT,
    )


def _check_credit_note(view: CaseView) -> None:
    """v0.9 credit notes (plan Q12): they must reference an invoice in the supplier's history."""
    ref = view.invoice.original_invoice_ref
    if not ref:
        raise UnsupportedCase("credit note without a reference to the original invoice")
    target = duplicates.norm_number(ref)
    if not any(
        h.invoice.doc_type == "invoice" and duplicates.norm_number(h.invoice.invoice_number) == target
        for h in view.history
    ):
        raise UnsupportedCase("credit note's original invoice is not in the history")
