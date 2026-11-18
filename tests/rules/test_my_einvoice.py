"""Malaysian e-invoices and SST invoice particulars: ME-1, ME-3, ME-4 (A12 build PR 2 commit 12). ME-2 is the v0.9
MyInvois mandatory-field check (tests/rules/test_table_rows.py, row 12)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer, ein
from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_exemptions import imported

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
VALIDATED = {"uuid": "F9D425P6DS7D8IU", "validation_datetime": "2026-11-02T10:15:00Z"}
SELF_BILL = "ISSUE_SELF_BILLED_EINVOICE"


def actions(a) -> list[str]:
    return [x.action for x in a.buyer_actions]


# -- ME-1: supplier in a mandatory phase issues a validated e-invoice ------------------------------------


def test_me1_supplier_in_its_phase_without_a_validated_einvoice():
    r, c = one_line()
    supplier_facts(r, einvoice_phase_start="2025-07-01")
    a = answer(r, c)
    assert a.decision is RCI and a.reason_codes == ["MISSING_MANDATORY_FIELD"]
    assert a.findings[0].evidence == {"missing": ["uuid", "validation_datetime"], "rule": "ME-1"}
    r, c = one_line()
    ein(c)["is_einvoice"] = False
    supplier_facts(r, einvoice_phase_start="2025-07-01")
    assert answer(r, c).findings[0].evidence["missing"][0] == "validated_einvoice"


def test_me1_near_miss_validated_or_before_the_phase():
    r, c = one_line()
    ein(c).update(VALIDATED)
    supplier_facts(r, einvoice_phase_start="2025-07-01")
    assert answer(r, c).decision is OK
    r, c = one_line()
    supplier_facts(r, einvoice_phase_start="2027-01-01")
    assert answer(r, c).decision is OK


def test_me1_unknown_phase_is_a_hand_over_with_the_tax_set():
    r, c = one_line()
    supplier_facts(r, einvoice_phase_known=False)
    a = answer(r, c)
    assert (a.decision, a.tax_treatment) == (HO, "SST_CORRECT")


# -- ME-3: self-billed e-invoices ------------------------------------------------------------------------


def test_me3_foreign_supplier_the_buyer_self_bills():
    r, c = imported()
    company_facts(r, einvoice_phase_start="2025-01-01")
    a = answer(r, c)
    assert (a.decision, a.tax_treatment) == (OK, "SST_BUYER_ACCOUNTS")
    assert actions(a) == ["ACCOUNT_IMPORTED_SERVICE_TAX", SELF_BILL]


@pytest.mark.parametrize("facts", [
    {"self_billing_type": "agents_dealers_distributors"},
    {"self_billing_type": "individual_not_in_business"},
    {"self_billing_type": "interest_payment", "interest_exception": "none"},
])
def test_me3_section_8_3_types_on_a_domestic_invoice(facts):
    r, c = one_line(**facts)
    company_facts(r, einvoice_phase_start="2025-01-01")
    assert actions(answer(r, c)) == [SELF_BILL]


@pytest.mark.parametrize("facts, phase", [
    ({"self_billing_type": "interest_payment", "interest_exception": "public_lender"}, "2025-01-01"),
    ({"self_billing_type": "interest_payment", "interest_exception": "late_payment_charge"}, "2025-01-01"),
    ({"self_billing_type": "none"}, "2025-01-01"),
    ({"self_billing_type": "agents_dealers_distributors"}, "2027-01-01"),   # buyer not yet in its phase
    ({"self_billing_type": "agents_dealers_distributors"}, None),
])
def test_me3_near_miss_exception_or_buyer_not_in_its_phase(facts, phase):
    r, c = one_line(**facts)
    company_facts(r, einvoice_phase_start=phase)
    assert actions(answer(r, c)) == []


def test_me3_unknown_phase_or_exception_is_a_hand_over_with_the_tax_set():
    r, c = imported()
    company_facts(r, einvoice_phase_known=False)
    a = answer(r, c)
    assert (a.decision, a.tax_treatment) == (HO, "SST_BUYER_ACCOUNTS")
    r, c = one_line(self_billing_type="interest_payment", interest_exception=None)
    company_facts(r, einvoice_phase_start="2025-01-01")
    assert (answer(r, c).decision, answer(r, c).tax_treatment) == (HO, "SST_CORRECT")


# -- ME-4: SST invoice particulars ---------------------------------------------------------------------


@pytest.mark.parametrize("change, missing", [
    (lambda c: c["invoice"]["supplier_block"].update(address=None), "supplier_address"),
    (lambda c: ein(c).update(supplier_sst_no=None), "supplier_sst_no"),
    (lambda c: c["invoice"].update(currency="USD"), "ringgit_amounts"),
])
def test_me4_sst_invoice_missing_a_particular(change, missing):
    r, c = one_line()
    change(c)
    if missing == "ringgit_amounts":
        r["purchase_orders"][0]["currency"] = "USD"
    a = answer(r, c)
    assert a.decision is RCI
    assert {"missing": [missing], "rule": "ME-4"} in [f.evidence for f in a.findings]


def test_me4_b2b_exempt_invoice_must_show_the_buyer_and_the_exemption():
    r, c = one_line("management_services", rate="0")
    company_facts(r, services_provided=["G(i)"])
    a = answer(r, c)
    assert (a.decision, a.tax_lines[0].basis) == (RCI, "MS-5")
    assert a.findings[0].evidence == {"missing": ["buyer_sst_no", "line1.tax_exemption_reason"], "rule": "ME-4"}


def test_me4_near_miss_b2b_invoice_with_the_particulars():
    r, c = one_line("management_services", rate="0")
    company_facts(r, services_provided=["G(i)"])
    ein(c)["buyer_sst_no"] = "W10-0000-00000001"
    ein(c)["lines"][0]["tax_exemption_reason"] = "Exempted under the Persons Exempted from Payment of Tax Order"
    assert result(r, c) == (OK, "NO_SST", "MS-5")


def test_me4_near_miss_unregistered_supplier_issues_no_sst_invoice():
    r, c = one_line(rate="0", supplier=())
    ein(c)["supplier_sst_no"] = None
    assert result(r, c) == (OK, "NO_SST", "MS-1")
