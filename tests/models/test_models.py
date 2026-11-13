"""Model basics: exact decimals, frozen records, internal fields, discriminated invoices."""

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from decision_benchmark.models import (
    AnswerKey,
    Email,
    Invoice,
    InvoiceMY,
    InvoiceSG,
    TolerancePolicy,
    export_dict,
)

MY_INVOICE = {
    "country": "MY",
    "invoice_id": "i1",
    "invoice_number": "A-1",
    "issue_date": "2026-10-01",
    "supplier_block": {"name": "S"},
    "buyer_block": {"name": "B"},
    "currency": "MYR",
    "totals": {"net": "100.00", "tax": "8.00", "gross": "108.00"},
    "is_einvoice": True,
    "lines": [
        {
            "line_no": 1,
            "qty": 1,
            "uom": "unit",
            "unit_price": "100.00",
            "net_amount": "100.00",
            "tax_rate": "8",
            "tax_amount": "8.00",
            "tax_type": "02",
            "category": "it_services",
        }
    ],
}


def test_money_rejects_floats_and_extra_decimals():
    with pytest.raises(ValidationError, match="not a float"):
        TolerancePolicy(price_tolerance_pct="2", rounding_tolerance=0.05, duplicate_window_days=90)
    with pytest.raises(ValidationError, match="at most 2 decimals"):
        TolerancePolicy(price_tolerance_pct="2", rounding_tolerance="0.051", duplicate_window_days=90)


def test_money_and_numbers_serialise_as_strings():
    tp = TolerancePolicy(price_tolerance_pct="2.50", rounding_tolerance="0.5", duplicate_window_days=90)
    dumped = tp.model_dump(mode="json")
    assert dumped["price_tolerance_pct"] == "2.5"
    assert dumped["rounding_tolerance"] == "0.50"
    assert dumped["quantity_tolerance_units"] == "0"


def test_records_are_frozen_and_strict():
    tp = TolerancePolicy(price_tolerance_pct="2", rounding_tolerance="0.05", duplicate_window_days=90)
    with pytest.raises(ValidationError):
        tp.price_tolerance_pct = Decimal("3")  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        TolerancePolicy(price_tolerance_pct="2", rounding_tolerance="0.05", duplicate_window_days=90, x=1)


def test_invoice_union_picks_the_country_model():
    adapter = TypeAdapter(Invoice)
    assert isinstance(adapter.validate_python(MY_INVOICE), InvoiceMY)
    sg = {k: v for k, v in MY_INVOICE.items() if k != "is_einvoice"} | {"country": "SG", "currency": "SGD"}
    sg["lines"] = [{k: v for k, v in sg["lines"][0].items() if k != "tax_type"} | {"tax_category": "SR"}]
    assert isinstance(adapter.validate_python(sg), InvoiceSG)


def test_export_drops_internal_fields_recursively():
    inv = InvoiceMY.model_validate(MY_INVOICE)
    out = export_dict(inv)
    assert "category" not in out["lines"][0]
    assert "facts" not in out["lines"][0]
    assert out["lines"][0]["unit_price"] == "100.00"
    email = Email(
        thread_id="t",
        message_id="m",
        company_id="c",
        sent_at="2026-10-01T09:00:00",
        sender={"address": "a@x.example"},
        to=[{"address": "b@y.example"}],
        subject="s",
        body="b",
        requests_bank_change=True,
        new_bank_account="123",
    )
    exported = export_dict(email)
    assert "requests_bank_change" not in exported and "new_bank_account" not in exported


def test_bank_change_email_needs_the_new_account():
    with pytest.raises(ValidationError, match="new_bank_account"):
        Email(
            thread_id="t",
            message_id="m",
            company_id="c",
            sent_at="2026-10-01T09:00:00",
            sender={"address": "a@x.example"},
            to=[],
            subject="s",
            body="b",
            requests_bank_change=True,
        )


def test_answer_key_null_tax_only_on_hand_over():
    base = dict(case_id="ap-my-00001", gl_account="6100", reason_codes=["X"], truth_supplier_id="S")
    with pytest.raises(ValidationError, match="only on HAND_OVER"):
        AnswerKey(decision="APPROVE", tax_treatment=None, answer_source="rules", **base)
    with pytest.raises(ValidationError, match="if and only if"):
        AnswerKey(decision="HAND_OVER", tax_treatment=None, answer_source="rules", **base)
    AnswerKey(decision="HAND_OVER", tax_treatment=None, answer_source="handover_by_construction", **base)
