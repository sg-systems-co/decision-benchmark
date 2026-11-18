"""Findings -> decision by fixed priority -> answer key (step-11 plan §5.2, §5.3).

``compute_answer`` is the only function that writes answer keys. It raises
``UnsupportedCase`` for any situation outside the v0.9 rules, so the generator
redraws the case instead of the engine guessing.
"""

from __future__ import annotations

from ..codes import Code
from ..findings import DECISION, UnsupportedCase, Unsettled, sort_findings
from ..models import AnswerKey, AnswerSource, Catalog, Decision, Finding, GraderTruth, TaxLine, Tier
from ..versions import ENGINE_VERSION, RULES_VERSION
from . import duplicates, fraud, gl, matching, routing
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

    findings += view.pack.validity(inv)
    tax_result = view.pack.assess_tax(view, catalog)
    tax = tax_result.treatment
    findings += tax_result.findings
    unsettled += tax_result.unsettled

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
                str(f.evidence["ledger_id"]) for f in findings if f.code in (Code.DUPLICATE_INVOICE, Code.NEAR_DUPLICATE)
            )
            match = matching.check(view, po_res.po, exclude_ledger_ids=dup_ids)
            findings += match.findings
            variance = match.max_variance_pct
        if not po_res.ambiguous:
            blocking = any(f.tier <= Tier.INVALID_INVOICE for f in findings)
            findings += routing.check(view, po_res, blocking_found=blocking)
    if po_res.po is not None and mapping is None:
        mapping = matching.line_map(view, po_res.po)

    accounts = gl.line_accounts(view, po_res.po, mapping, catalog)
    gl_account = gl.case_account(view, accounts)
    findings = sort_findings(findings)
    lines_out = _lines_out(view, tax_result, accounts)

    if unsettled:
        if findings:
            raise UnsupportedCase("a case the rules don't settle also has another problem (plan Q14)")
        return AnswerKey(
            case_id=view.case_id,
            decision=Decision.HAND_OVER,
            tax_treatment=None if any(u.tax_related for u in unsettled) else tax,
            gl_account=gl_account,
            reason_codes=[Code.CANNOT_SETTLE_FROM_RULES],
            answer_source=AnswerSource.HANDOVER_BY_CONSTRUCTION,
            findings=[],
            grader_truth=_truth(view, po_res, variance, contact=False),
            **lines_out,
        )

    assert tax is not None
    decision = DECISION[findings[0].code] if findings else Decision.APPROVE
    reasons = [Code(f.code) for f in findings] or [Code.MATCHED_WITHIN_TOLERANCE]
    reasons += tax_result.extra_reasons
    return AnswerKey(
        case_id=view.case_id,
        decision=decision,
        tax_treatment=tax,
        gl_account=gl_account,
        reason_codes=reasons,
        answer_source=AnswerSource.RULES,
        findings=findings,
        grader_truth=_truth(view, po_res, variance, contact=decision in SUPPLIER_CONTACT),
        **lines_out,
    )


def _lines_out(view: CaseView, tax_result, accounts: dict[int, str]) -> dict:
    """tax_lines (with each line's GL), buyer actions, gold facts and versions for the answer key."""
    by_no = {line.line_no: line for line in view.invoice.lines}
    facts = []
    for res in tax_result.lines:
        recorded = by_no[res.line_no].facts
        if res.read and recorded is not None:
            facts.append({"line_no": res.line_no, **recorded.to_output(list(res.read))})
    return {
        "tax_lines": [TaxLine(line_no=r.line_no, treatment=r.treatment, basis=r.basis, gl_account=accounts[r.line_no])
                      for r in tax_result.lines],
        "buyer_actions": _unique([a for r in tax_result.lines for a in r.buyer_actions]),
        "facts": facts or None,
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
    }


def _unique(actions: list) -> list:
    """Each buyer action once (the schema's uniqueItems), in line order."""
    out: list = []
    for a in actions:
        if a not in out:
            out.append(a)
    return out


def _truth(view: CaseView, po_res: matching.PoResolution, variance, contact: bool) -> GraderTruth:
    return GraderTruth(
        supplier_id=view.supplier.supplier_id,
        po_number=po_res.po.po_number if po_res.po else None,
        price_variance_pct=variance,
        requires_supplier_contact=contact,
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
