"""Malaysian e-invoices and SST invoice particulars: ME-1, ME-3, ME-4 (A12 build PR 2 commit 12). ME-2 is the v0.9
MyInvois mandatory-field check (tests/rules/test_table_rows.py, row 12)."""

import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries.my.einvoice_timeline import timeline
from decision_benchmark.task_sets.ap_invoices.countries.my.models import MyEinvoiceStatus
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer, ein
from .my_cases import company_facts, one_line, result, supplier_facts
from .test_my_exemptions import imported

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
VALIDATED = {"uuid": "F9D425P6DS7D8IU", "validation_datetime": "2026-11-02T10:15:00Z"}
SELF_BILL = "ISSUE_SELF_BILLED_EINVOICE"
SHEET = (Path(__file__).resolve().parents[2] / "docs/tax-rules-v0.10.md").read_text(encoding="utf-8")


def actions(a) -> list[str]:
    return [x.action for x in a.buyer_actions]


# -- ME-1: supplier in a mandatory phase, outside its interim relaxation period, issues a validated e-invoice -----
# Phases, exemptions and relaxation periods: rule sheet v0.10 ME-1 (20 Nov 2026), data/einvoice_timeline.yaml.

ESTABLISHED = {   # band: (implementation date, last day of the interim relaxation period)
    "above_100m": ("2024-08-01", "2025-01-31"), "25m_to_100m": ("2025-01-01", "2025-06-30"),
    "5m_to_25m": ("2025-07-01", "2025-12-31"), "3m_to_5m": ("2026-01-01", "2027-12-31"),
}


def plus(day: str, n: int) -> str:
    return str(dt.date.fromisoformat(day) + dt.timedelta(days=n))


def me1(day: str, band: str | None = "5m_to_25m", basis: str = "fy2022_audited", validated: bool = False,
        plain: bool = False, **status):
    """One-line case dated day from a supplier with that turnover band; the factory's e-invoice has no UUID."""
    r, c = one_line(day=day)
    if band is not None:
        supplier_facts(r, einvoice={"turnover_band": band, "turnover_basis": basis, **status})
    if validated:
        ein(c).update(VALIDATED)
    if plain:
        ein(c)["is_einvoice"] = False
    return r, c


def finding_of(r, c):
    a = answer(r, c)
    return (a.decision, [f.evidence for f in a.findings if f.evidence.get("rule") == "ME-1"])


def test_me1_supplier_in_its_phase_without_a_validated_einvoice():
    a = answer(*me1("2026-01-01"))
    assert a.decision is RCI and a.reason_codes == ["MISSING_MANDATORY_FIELD"]
    assert a.findings[0].evidence == {"missing": ["uuid", "validation_datetime"], "rule": "ME-1"}
    assert answer(*me1("2026-01-01", plain=True)).findings[0].evidence["missing"][0] == "validated_einvoice"


def test_me1_near_miss_validated_or_before_the_phase():
    assert answer(*me1("2026-01-01", validated=True)).decision is OK
    assert answer(*me1("2025-06-30")).decision is OK


@pytest.mark.parametrize("band, dates", ESTABLISHED.items())
def test_me1_each_phase_starts_with_its_relaxation_period(band, dates):
    start, end = dates
    assert finding_of(*me1(plus(start, -1), band, plain=True)) == (OK, [])        # before the implementation date
    assert finding_of(*me1(start, band, plain=True)) == (OK, [])                  # relaxation: consolidated allowed
    assert finding_of(*me1(end, band, plain=True)) == (OK, [])                    # last day of the relaxation period
    decision, found = finding_of(*me1(plus(end, 1), band, plain=True))           # the day after: individual e-invoice
    assert decision is RCI and found == [{"missing": ["validated_einvoice", "uuid", "validation_datetime"], "rule": "ME-1"}]


@pytest.mark.parametrize("band", ["below_1m", "1m_to_3m"])
def test_me1_turnover_below_rm3m_is_exempt(band):
    assert finding_of(*me1("2028-03-01", band, plain=True)) == (OK, [])


def test_me1_near_miss_rm3m_to_5m_is_not_exempt():
    assert finding_of(*me1("2028-03-01", "3m_to_5m", plain=True))[0] is RCI


@pytest.mark.parametrize("kind", ["foreign_diplomatic_office", "individual_not_in_business"])
def test_me1_exempt_persons(kind):
    r, c = me1("2026-03-02", "above_100m", plain=True)
    supplier_facts(r, supplier_kind=kind)
    assert finding_of(r, c) == (OK, [])


@pytest.mark.parametrize("kind", ["statutory_body", "local_authority", "international_organisation"])
def test_me1_public_bodies_exempt_for_supplies_before_1_july_2025(kind):
    r, c = me1("2025-06-30", "above_100m", plain=True)
    supplier_facts(r, supplier_kind=kind)
    assert finding_of(r, c) == (OK, [])
    r, c = me1("2025-07-01", "above_100m", plain=True)                        # near miss: from 1 Jul 2025
    supplier_facts(r, supplier_kind=kind)
    assert finding_of(r, c)[0] is RCI


@pytest.mark.parametrize("kind", ["statutory_body", "local_authority"])
def test_me1_statutory_body_exempt_for_statutory_fees_from_1_july_2025(kind):
    r, c = one_line(day="2026-03-02", statutory_fee_amount="3200.00")
    supplier_facts(r, supplier_kind=kind, einvoice={"turnover_band": "above_100m", "turnover_basis": "fy2022_audited"})
    ein(c)["is_einvoice"] = False
    assert finding_of(r, c)[1] == []
    r, c = one_line(day="2026-03-02", statutory_fee_amount="1000.00")             # near miss: part of the line only
    supplier_facts(r, supplier_kind=kind, einvoice={"turnover_band": "above_100m", "turnover_basis": "fy2022_audited"})
    ein(c)["is_einvoice"] = False
    assert finding_of(r, c)[0] is RCI


@pytest.mark.parametrize("started, start", [("2023-05-01", "2026-07-01"), ("2025-12-31", "2026-07-01"),
                                            ("2026-03-01", "2026-07-01")])
def test_me1_new_business_from_1_july_2026_with_relaxation_to_2027(started, start):
    kw = {"basis": "new_business", "business_started_on": started}
    assert finding_of(*me1(plus(start, -1), "3m_to_5m", plain=True, **kw)) == (OK, [])
    assert finding_of(*me1("2027-12-31", "3m_to_5m", plain=True, **kw)) == (OK, [])
    assert finding_of(*me1("2028-01-01", "3m_to_5m", plain=True, **kw))[0] is RCI


def test_me1_new_business_commenced_after_1_july_2026_has_no_published_relaxation():
    kw = {"basis": "new_business", "business_started_on": "2026-09-01"}
    assert finding_of(*me1("2026-08-31", "3m_to_5m", plain=True, **kw)) == (OK, [])      # before commencement
    assert answer(*me1("2026-09-01", "3m_to_5m", plain=True, **kw)).decision is HO   # Table 16.1 has no period
    assert answer(*me1("2026-09-01", "3m_to_5m", validated=True, **kw)).decision is OK


def test_me1_new_business_above_rm5m_has_no_published_relaxation():
    kw = {"basis": "new_business", "business_started_on": "2024-02-01"}
    assert finding_of(*me1("2026-06-30", "5m_to_25m", plain=True, **kw)) == (OK, [])
    assert answer(*me1("2026-07-01", "5m_to_25m", plain=True, **kw)).decision is HO


def test_me1_new_business_first_year_below_rm1m_starts_two_years_after_reaching_it():
    kw = {"basis": "new_business", "business_started_on": "2026-02-01", "turnover_reached_1m_on": "2026-11-15"}
    assert finding_of(*me1("2027-12-31", "3m_to_5m", plain=True, **kw)) == (OK, [])      # starts 1 Jan 2028
    assert answer(*me1("2028-01-01", "3m_to_5m", plain=True, **kw)).decision is HO       # no published period
    kw = {"basis": "new_business", "business_started_on": "2026-02-01"}
    assert finding_of(*me1("2030-01-02", "below_1m", plain=True, **kw)) == (OK, [])      # RM1m not reached


def test_me1_new_business_commenced_2023_to_2025_below_rm1m_has_no_date():
    kw = {"basis": "new_business", "business_started_on": "2024-02-01"}
    assert finding_of(*me1("2028-03-01", "below_1m", plain=True, **kw)) == (OK, [])


def test_me1_unknown_phase_is_a_hand_over_with_the_tax_set():
    r, c = me1("2026-11-02", band=None)
    supplier_facts(r, einvoice_phase_known=False)
    a = answer(r, c)
    assert (a.decision, a.tax_treatment) == (HO, "SST_CORRECT")


def test_me1_near_miss_unknown_phase_settled_when_it_does_not_decide():
    r, c = me1("2025-01-31", band=None, plain=True)        # no supplier is past its relaxation period yet
    supplier_facts(r, einvoice_phase_known=False)
    assert answer(r, c).decision is OK
    r, c = me1("2025-02-01", band=None, plain=True)
    supplier_facts(r, einvoice_phase_known=False)
    assert answer(r, c).decision is HO
    r, c = me1("2026-11-02", band=None, validated=True)     # a validated e-invoice settles it whatever the phase
    supplier_facts(r, einvoice_phase_known=False)
    assert answer(r, c).decision is OK


@pytest.mark.parametrize("status, error", [
    ({"turnover_band": "3m_to_5m", "turnover_basis": "new_business"}, "new business commenced"),
    ({"turnover_band": "3m_to_5m", "turnover_basis": "fy2022_audited", "business_started_on": "2024-01-01"}, "is a new business"),
    ({"turnover_band": "3m_to_5m", "turnover_basis": "new_business", "business_started_on": "2024-01-01",
      "turnover_reached_1m_on": "2025-01-01"}, "2026 or later"),
    ({"turnover_band": "RM5m-25m", "turnover_basis": "fy2022_audited"}, "Input should be"),
])
def test_me1_einvoice_status_is_checked(status, error):
    with pytest.raises(ValidationError, match=error):
        MyEinvoiceStatus.model_validate(status)


def test_me1_timeline_dates_are_the_sheets():
    me1_text = SHEET[SHEET.index("- ME-1 "):SHEET.index("- ME-2 ")]
    for row in timeline().rows:
        for d in [row.start, row.to, *row.starts, row.started_from, row.started_to]:
            if d is not None and row.kind != "new_business":
                assert f"{d.day} {d:%b} {d.year}" in me1_text or (row.kind == "exempt_person" and d == dt.date(2025, 6, 30)), (row, d)
    assert "before 1 Jul 2025" in me1_text and "from 1 Jul 2026" in me1_text and "2023–2025" in me1_text


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
