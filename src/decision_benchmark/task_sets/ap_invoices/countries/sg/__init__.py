"""Singapore: GST input-tax claims, IRAS tax invoices, PINT-SG fields."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...findings import TaxResult
from ...registry import RuleSpec, registry
from ..base import CountryPack
from . import constants, rules as line_rules
from .models import SgContractFacts, SgLineFacts, PintSg, SgCompanyFacts, SgSupplierFacts, SgTaxProfile, SgTaxTreatment

if TYPE_CHECKING:
    from ...models.evidence import LineFacts
    from ...models import Catalog, Company, Finding, Invoice
    from ...rules.view import CaseView


class SingaporePack(CountryPack):
    country = "SG"
    currency = "SGD"
    registration_types = {"SG_GST": ("local", "ovr")}
    tax_codes = SgTaxTreatment
    tax_profile = SgTaxProfile
    profile_required = False
    einvoice = PintSg
    company_facts = SgCompanyFacts
    contract_facts = SgContractFacts
    supplier_facts = SgSupplierFacts
    line_facts_model = SgLineFacts
    constants = constants
    # x-severity-order of schemas/ap-invoices/v0.10/countries/sg.schema.json (tests/rules/test_registry.py).
    severity_order = (
        "GST_WRONGLY_CHARGED",
        "GST_UNDERCHARGED",
        "NOT_CLAIMABLE_INVALID_INVOICE",
        "NOT_CLAIMABLE_DISALLOWED",
        "NOT_CLAIMABLE_EXEMPT_USE",
        "RESIDUAL_APPORTIONED",
        "CLAIMABLE",
        "CUSTOMER_ACCOUNTING",
        "REVERSE_CHARGE",
        "NO_GST",
    )
    # Every rule ID of the schema part's $defs/rule_id. Validity dates come with each rule (A12 build PR 3).
    rules = registry(*(RuleSpec(r) for r in (*(f"SG-{i}" for i in range(1, 13)), "WH-5")))

    def check_company(self, company: Company) -> None:
        super().check_company(company)
        # Step-11 plan Q5: every Singapore buying company is GST-registered in v0.9.
        reg = company.registration("SG_GST")
        if reg is None or reg.valid_from is None:
            raise ValueError("a Singapore company needs base_currency SGD and a GST registration")

    def validity(self, invoice: Invoice) -> list[Finding]:
        # Tax-invoice validity only matters for an input-tax claim, so assess_tax reports it.
        return []

    def gross_in_local_currency(self, invoice: Invoice) -> Decimal | None:
        assert isinstance(invoice.einvoice, PintSg)
        return invoice.einvoice.gross_sgd

    def assess_tax(self, view: CaseView, catalog: Catalog, facts: dict[int, LineFacts] | None = None) -> TaxResult:
        return line_rules.assess(view, catalog, facts)


PACK = SingaporePack()
