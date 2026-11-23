"""Contract records, certificates of residence and the new party facts (A12 plan §5.2-5.3)."""

import copy
from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from decision_benchmark.task_sets.ap_invoices.countries import PACKS
from decision_benchmark.task_sets.ap_invoices.countries.my.models import (
    GroupStructure,
    MsmeStatus,
    MyCompanyFacts,
    MyContractFacts,
    MySupplierFacts,
    Shareholding,
)
from decision_benchmark.task_sets.ap_invoices.countries.sg.models import PintSg, SgCompanyFacts, SgSupplierFacts
from decision_benchmark.task_sets.ap_invoices.models import (
    CompanyRecords,
    ContractChange,
    ContractRecord,
    CountryBlock,
    ResidenceCertificate,
)

ROOT = Path(__file__).resolve().parents[2]
MY_RECORDS = yaml.safe_load((ROOT / "tests/fixtures/worked-examples/ap-my-00137.yaml").read_text())["records"]
COMPANY_ID = MY_RECORDS["company"]["company_id"]
SUPPLIER_ID = MY_RECORDS["suppliers"][0]["supplier_id"]


def contract(**over) -> dict:
    base = {"contract_id": "K-1", "company_id": COMPANY_ID, "supplier_id": SUPPLIER_ID,
            "signed_on": "2025-05-20", "stamped_on": "2025-06-05", "has_price_review_clause": False}
    return base | over


def records(**over) -> dict:
    return copy.deepcopy(MY_RECORDS) | over


# -- contract record ------------------------------------------------------------


def test_contract_record_with_changes_and_country_facts():
    c = ContractRecord.model_validate(contract(
        variation_orders=[{"signed_on": "2025-06-10", "stamped_on": "2025-07-01", "changes_value": False}],
        extensions_of_time=[{"signed_on": "2025-06-12", "changes_value": None}],
        tax_facts={"country": "MY", "mixed_development_stated": True, "design_and_build": False},
        value="125000.00", start="2025-07-01", end="2027-06-30"))
    assert isinstance(c.tax_facts, MyContractFacts) and c.tax_facts.mixed_development_stated
    assert c.variation_orders[0].changes_value is False and c.extensions_of_time[0].stamped_on is None


@pytest.mark.parametrize("over, msg", [
    ({"stamped_on": "2025-05-01"}, "stamped after it is signed"),
    ({"start": "2026-01-01", "end": "2025-12-31"}, "ends after it starts"),
    ({"parties": [SUPPLIER_ID]}, "not the supplier itself"),
    ({"parties": ["S-2", "S-2"]}, "duplicate party"),
    ({"tax_facts": {"country": "MY", "unknown": 1}}, "Extra inputs"),
    ({"value": 10.5}, "not a float"),
])
def test_contract_record_errors(over, msg):
    with pytest.raises(ValidationError, match=msg):
        ContractRecord.model_validate(contract(**over))


def test_contract_change_dates():
    with pytest.raises(ValidationError, match="stamped after it is signed"):
        ContractChange(signed_on="2025-06-10", stamped_on="2025-06-01")


def test_records_hold_contracts_and_certificates():
    r = CompanyRecords.model_validate(records(
        contracts=[contract()],
        residence_certificates=[{"certificate_id": "COR-1", "supplier_id": SUPPLIER_ID, "country": "SG",
                                 "valid_from": "2026-01-01", "valid_to": "2026-12-31"}]))
    assert r.contract("K-1").signed_on == date(2025, 5, 20)
    assert r.residence_certificate(SUPPLIER_ID, date(2026, 6, 1)).country == "SG"
    assert r.residence_certificate(SUPPLIER_ID, date(2027, 1, 1)) is None


@pytest.mark.parametrize("over, msg", [
    ({"contracts": [contract(), contract()]}, "duplicate contract_id"),
    ({"contracts": [contract(company_id="other")]}, "belongs to another company"),
    ({"contracts": [contract(supplier_id="nobody")]}, "not in the records"),
    ({"contracts": [contract(parties=["nobody"])]}, "not in the records"),
    ({"contracts": [contract(tax_facts={"country": "SG"})]}, "tax_facts are for SG"),
    ({"residence_certificates": [{"certificate_id": "C", "supplier_id": "nobody", "country": "SG",
                                  "valid_from": "2026-01-01"}]}, "not in the records"),
])
def test_records_reference_errors(over, msg):
    with pytest.raises(ValidationError, match=msg):
        CompanyRecords.model_validate(records(**over))


@pytest.mark.parametrize("over, msg", [
    ({"valid_to": "2025-12-31"}, "not before its valid_from"),
    ({"country": "Singapore"}, "String should match pattern"),
])
def test_residence_certificate_errors(over, msg):
    base = {"certificate_id": "C", "supplier_id": "S", "country": "SG", "valid_from": "2026-01-01"}
    with pytest.raises(ValidationError, match=msg):
        ResidenceCertificate.model_validate(base | over)


def test_residence_certificate_validity_is_inclusive():
    cert = ResidenceCertificate(certificate_id="C", supplier_id="S", country="SG", valid_from="2026-01-01",
                                valid_to="2026-12-31")
    assert cert.valid_on(date(2026, 1, 1)) and cert.valid_on(date(2026, 12, 31))
    assert not cert.valid_on(date(2025, 12, 31))


# -- Malaysian party facts --------------------------------------------------------


def test_msme_and_group_structure():
    facts = MyCompanyFacts.model_validate({
        "msme": {"mypmk_registered_on": "2026-03-01", "declared_sales_band": "1m_to_1_5m", "year_of_assessment": 2025,
                 "paid_up_capital": "2000000.00", "group_holding_pct": "15", "ssm_registered_on": "2019-02-01"},
        "group": {"shareholdings": [{"holder_id": "C-1", "held_id": "S-9", "pct": "35", "board_control": True}]},
        "zone": "labuan", "einvoice": {"turnover_band": "5m_to_25m", "turnover_basis": "fy2022_audited"}, "buyer_kinds": ["aoc_airline"]})
    assert facts.msme.declared_sales_band == "1m_to_1_5m"
    assert facts.group.shareholdings[0].board_control is True and facts.zone == "labuan"


@pytest.mark.parametrize("data, msg", [
    ({"declared_sales_band": "below_2m"}, "Input should be"),
    ({"group_holding_pct": "120"}, "less than or equal to 100"),
    ({"year_of_assessment": 1990}, "greater than or equal to 2000"),
])
def test_msme_errors(data, msg):
    with pytest.raises(ValidationError, match=msg):
        MsmeStatus.model_validate(data)


def test_shareholding_errors():
    with pytest.raises(ValidationError, match="does not hold itself"):
        Shareholding(holder_id="C-1", held_id="C-1", pct="60")
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        Shareholding(holder_id="C-1", held_id="S-1", pct="101")
    with pytest.raises(ValidationError, match="one shareholding per holder"):
        GroupStructure.model_validate({"shareholdings": [
            {"holder_id": "C-1", "held_id": "S-1", "pct": "60"}, {"holder_id": "C-1", "held_id": "S-1", "pct": "10"}]})


def test_supplier_facts_defaults_keep_v09_behaviour():
    f = MySupplierFacts()
    assert f.registration_known and f.supplier_kind == "company" and not f.is_foreign_registered_person
    assert f.external_share_within_5pct is None and f.pe_in_country is None and f.group_relation == "unrelated"
    with pytest.raises(ValidationError):
        MySupplierFacts(supplier_kind="ministry")
    with pytest.raises(ValidationError):
        MySupplierFacts(approvals=["faa_part_145"])


def test_company_facts_reject_unknown_zone_and_buyer_kind():
    with pytest.raises(ValidationError):
        MyCompanyFacts(zone="penang")
    with pytest.raises(ValidationError):
        MyCompanyFacts(buyer_kinds=["bank"])


# -- Singapore party facts --------------------------------------------------------


def test_sg_party_facts_and_invoice_statement():
    assert SgCompanyFacts().input_tax_status == "fully_taxable"
    assert SgCompanyFacts(input_tax_status=None).input_tax_status is None
    with pytest.raises(ValidationError):
        SgCompanyFacts(input_tax_status="exempt")
    assert SgSupplierFacts(has_branch_receiving=False).pe_in_country is None
    assert PintSg(customer_accounting_statement=True).customer_accounting_statement


@pytest.mark.parametrize("country", sorted(PACKS))
def test_every_pack_declares_contract_and_line_fact_models(country):
    pack = PACKS[country]
    assert issubclass(pack.contract_facts, CountryBlock)
    assert pack.contract_facts.model_fields["country"].default == country
    assert pack.line_facts_model.__name__.startswith(country.title())
