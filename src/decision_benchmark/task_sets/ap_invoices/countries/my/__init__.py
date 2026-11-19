"""Malaysia: SST (sales tax and service tax), MyInvois e-invoices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...findings import TaxResult
from ...registry import RuleSpec, registry
from ..base import CountryPack
from . import constants, rules as line_rules, validity
from .models import MyContractFacts, MyLineFacts, MyCompanyFacts, MyInvois, MySupplierFacts, MyTaxProfile, MyTaxTreatment

if TYPE_CHECKING:
    from ...models.evidence import LineFacts
    from ...models import Catalog, Category, Company, Finding, Invoice
    from ...rules.view import CaseView


class MalaysiaPack(CountryPack):
    country = "MY"
    currency = "MYR"
    registration_types = {"MY_TIN": ("tin",), "MY_SST": ("sales", "service")}
    certificate_kinds = ("schedule_a", "schedule_b", "schedule_c", "b2b_declaration")
    tax_codes = MyTaxTreatment
    tax_profile = MyTaxProfile
    profile_required = True
    einvoice = MyInvois
    company_facts = MyCompanyFacts
    contract_facts = MyContractFacts
    supplier_facts = MySupplierFacts
    line_facts_model = MyLineFacts
    constants = constants
    # x-severity-order of schemas/ap-invoices/v0.10/countries/my.schema.json (tests/rules/test_registry.py).
    severity_order = (
        "SST_SUPPLIER_NOT_REGISTERED",
        "SST_NOT_CHARGEABLE_BY_TRADER",
        "SST_SHOULD_BE_EXEMPT",
        "SST_WRONG_RATE",
        "SST_UNDERCHARGED",
        "SST_CORRECT",
        "SST_BUYER_ACCOUNTS",
        "NO_SST",
    )
    # Every rule ID of the schema part's $defs/rule_id (docs/tax-rules-v0.10.md). Validity dates are added
    # with each rule's implementation (A12 build PRs 2 and 3).
    rules = registry(*(RuleSpec(r) for r in (
        *(f"MS-{i}" for i in range(1, 11)), *(f"MG-{i}" for i in range(1, 7)), *(f"ME-{i}" for i in range(1, 5)),
        *(f"K-{i}" for i in range(1, 9)), *(f"L-{i}" for i in range(1, 9)), *(f"P-{i}" for i in range(1, 22)),
        *(f"G-{i}" for i in range(1, 8)), *(f"WH-{i}" for i in range(1, 5)),
    )))

    def check_company(self, company: Company) -> None:
        super().check_company(company)
        if company.registration("MY_TIN") is None:
            raise ValueError("a Malaysian company needs base_currency MYR and a TIN")

    def check_category(self, category: Category) -> None:
        super().check_category(category)
        p = category.tax["MY"]
        assert isinstance(p, MyTaxProfile)
        name, kind, cls = category.category, category.kind, p.tax_class
        if p.schedule_c_eligible and (kind != "goods" or not cls.startswith("sales_")):
            raise ValueError(f"{name}: Schedule C applies to goods under sales tax")
        if kind == "goods" and cls.startswith("service_"):
            raise ValueError(f"{name}: goods can't carry a service-tax class")
        if kind == "service" and cls.startswith("sales_"):
            raise ValueError(f"{name}: services can't carry a sales-tax class")
        if (p.b2b_exempt or p.group_relief) and p.service_item is None:
            raise ValueError(f"{name}: b2b_exempt and group_relief need a service_item")
        if cls.startswith("service_") and p.service_item is None:
            raise ValueError(f"{name}: a taxable service needs its service_item")
        if not cls.startswith("service_") and p.service_item is not None:
            raise ValueError(f"{name}: service_item is only for service_6 and service_8")
        if p.group_relief and p.service_item not in constants.GROUP_RELIEF_ITEMS:
            raise ValueError(f"{name}: group_relief is only for Group G items (a) to (i), (l) and (n)")
        if p.b2b_exempt and p.service_item in constants.NO_B2B_ITEMS:
            raise ValueError(f"{name}: {p.service_item} has no B2B exemption")

    def validity(self, invoice: Invoice) -> list[Finding]:
        return validity.check(invoice)

    def assess_tax(self, view: CaseView, catalog: Catalog, facts: dict[int, LineFacts] | None = None) -> TaxResult:
        return line_rules.assess(view, catalog, facts)


PACK = MalaysiaPack()
