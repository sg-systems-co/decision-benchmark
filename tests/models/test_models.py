"""Model basics: exact decimals, frozen records, internal fields, country blocks, typed registrations."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries.my.models import MyInvois
from decision_benchmark.task_sets.ap_invoices.countries.sg.models import PintSg
from decision_benchmark.task_sets.ap_invoices.models import (
    AnswerKey,
    Email,
    Invoice,
    TaxRegistration,
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
    "lines": [
        {
            "line_no": 1,
            "qty": 1,
            "uom": "unit",
            "unit_price": "100.00",
            "net_amount": "100.00",
            "tax_rate": "8",
            "tax_amount": "8.00",
            "category": "it_services",
            "facts": {"personal_use": False},
        }
    ],
    "einvoice": {"country": "MY", "is_einvoice": True, "lines": [{"line_no": 1, "tax_type": "02"}]},
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


def _sg_invoice():
    sg = MY_INVOICE | {"country": "SG", "currency": "SGD"}
    sg["lines"] = [{k: v for k, v in sg["lines"][0].items() if k != "facts"}]
    sg["einvoice"] = {"country": "SG", "document_title": "Tax Invoice", "lines": [{"line_no": 1, "tax_category": "SR"}]}
    return sg


def test_einvoice_block_comes_from_the_country_pack():
    assert isinstance(Invoice.model_validate(MY_INVOICE).einvoice, MyInvois)
    assert isinstance(Invoice.model_validate(_sg_invoice()).einvoice, PintSg)
    dumped = Invoice.model_validate(MY_INVOICE).model_dump(mode="json")
    assert dumped["einvoice"]["is_einvoice"] is True and dumped["einvoice"]["lines"][0]["tax_type"] == "02"


@pytest.mark.parametrize(
    "change, msg",
    [
        ({"country": "SG"}, "einvoice block is for MY"),
        ({"country": "TH", "einvoice": {"country": "TH"}}, "no country pack for 'TH'"),
        ({"einvoice": {"country": "MY", "is_einvoice": True, "document_title": "x"}}, "Extra inputs"),
        ({"einvoice": {"country": "MY", "is_einvoice": True, "lines": [{"line_no": 9}]}}, "existing invoice lines"),
    ],
    ids=["block_country_differs", "country_without_pack", "sg_field_on_my_block", "unknown_einvoice_line"],
)
def test_einvoice_block_errors(change, msg):
    with pytest.raises(ValidationError, match=msg):
        Invoice.model_validate(MY_INVOICE | change)


def test_line_facts_are_declared_by_the_country_pack():
    bad = MY_INVOICE | {"lines": [MY_INVOICE["lines"][0] | {"facts": {"vehicle_is_motor_car": True}}]}
    with pytest.raises(ValidationError, match="not a MY line fact"):
        Invoice.model_validate(bad)
    bad = MY_INVOICE | {"lines": [MY_INVOICE["lines"][0] | {"facts": {"personal_use": None}}]}
    with pytest.raises(ValidationError, match="can't be None"):
        Invoice.model_validate(bad)
    sg = _sg_invoice()
    sg["lines"][0]["facts"] = {"vehicle_is_motor_car": None}
    Invoice.model_validate(sg)


def test_tax_registrations_are_checked_against_the_scheme():
    TaxRegistration(scheme="MY_SST", number="W10", type="service")
    TaxRegistration(scheme="SG_GST", number="M2", type="ovr", valid_to="2026-06-29")
    with pytest.raises(ValidationError, match="sales / service"):
        TaxRegistration(scheme="MY_SST", number="W10", type="ovr")
    with pytest.raises(ValidationError, match="unknown tax registration scheme"):
        TaxRegistration(scheme="TH_VAT", number="1", type="vat")
    with pytest.raises(ValidationError, match="before valid_from"):
        TaxRegistration(scheme="SG_GST", number="M2", type="local", valid_from="2026-01-02", valid_to="2026-01-01")
    reg = TaxRegistration(scheme="SG_GST", number="M2", type="local", valid_from="2026-01-01", valid_to="2026-06-29")
    assert reg.valid_on(date(2026, 6, 29)) and not reg.valid_on(date(2026, 6, 30))


def test_export_drops_internal_fields_recursively():
    inv = Invoice.model_validate(MY_INVOICE)
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
        signals=[{"kind": "bank_change_request", "new_bank_account": "123"}, {"kind": "lookalike_sender"}],
    )
    assert email.signal("bank_change_request").new_bank_account == "123"
    exported = export_dict(email)
    assert "signals" not in exported and "123" not in str(exported)


def test_email_signals_are_typed():
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
            signals=[{"kind": "bank_change_request"}],
        )
    with pytest.raises(ValidationError, match="does not match any of the expected tags"):
        Email(thread_id="t", message_id="m", company_id="c", sent_at="2026-10-01T09:00:00",
              sender={"address": "a"}, to=[], subject="s", body="b", signals=[{"kind": "urgent"}])
    with pytest.raises(ValidationError, match="at most one signal of each kind"):
        Email(thread_id="t", message_id="m", company_id="c", sent_at="2026-10-01T09:00:00",
              sender={"address": "a"}, to=[], subject="s", body="b",
              signals=[{"kind": "lookalike_sender"}, {"kind": "lookalike_sender"}])


def test_answer_key_null_tax_only_on_hand_over():
    base = dict(case_id="ap-my-00001", gl_account="6100", reason_codes=["CANNOT_SETTLE_FROM_RULES"],
                grader_truth={"supplier_id": "S"})
    with pytest.raises(ValidationError, match="only on HAND_OVER"):
        AnswerKey(decision="APPROVE", tax_treatment=None, answer_source="rules", **base)
    with pytest.raises(ValidationError, match="if and only if"):
        AnswerKey(decision="HAND_OVER", tax_treatment=None, answer_source="rules", **base)
    AnswerKey(decision="HAND_OVER", tax_treatment=None, answer_source="handover_by_construction", **base)


def test_answer_key_codes_are_checked():
    base = dict(case_id="ap-my-00001", gl_account="6100", decision="APPROVE", answer_source="rules",
                grader_truth={"supplier_id": "S"})
    with pytest.raises(ValidationError, match="unknown tax treatment"):
        AnswerKey(tax_treatment="VAT_OK", reason_codes=["MATCHED_WITHIN_TOLERANCE"], **base)
    with pytest.raises(ValidationError):
        AnswerKey(tax_treatment="SST_CORRECT", reason_codes=["MADE_UP"], **base)
