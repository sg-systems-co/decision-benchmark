"""Planting limits (B1 plan section 3.5), run over every generated case. Each PR that builds the cases a limit governs
adds its test here (the catalog README lists them)."""

from .test_families import built


def test_limit_6e_clean_credit_notes():
    """Credit notes are clean only (step 11 Q12): no generated credit note carries a problem."""
    for n in (2000, 500, 300):
        for g in built(n).cases:
            inv = g.envelope.payload.invoice
            if inv.doc_type == "credit_note":
                assert g.envelope.payload.exception_types == [] and g.answer.decision.value == "APPROVE"
            for entry in g.records.ledger:
                if entry.invoice.doc_type == "credit_note":
                    assert entry.invoice.original_invoice_ref
