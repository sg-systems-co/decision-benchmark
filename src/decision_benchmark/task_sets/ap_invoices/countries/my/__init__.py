"""Malaysia: SST (sales tax and service tax), MyInvois e-invoices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...findings import TaxResult
from ..base import CountryPack
from . import constants, tax, validity
from .models import MyContractFacts, MyLineFacts, MyCompanyFacts, MyInvois, MySupplierFacts, MyTaxProfile, MyTaxTreatment

if TYPE_CHECKING:
    from ...models import Catalog, Category, Company, Finding, Invoice
    from ...rules.view import CaseView


class MalaysiaPack(CountryPack):
    country = "MY"
    currency = "MYR"
    registration_types = {"MY_TIN": ("tin",), "MY_SST": ("sales", "service")}
    certificate_kinds = ("schedule_c", "b2b_declaration")
    tax_codes = MyTaxTreatment
    tax_profile = MyTaxProfile
    profile_required = True
    einvoice = MyInvois
    company_facts = MyCompanyFacts
    contract_facts = MyContractFacts
    supplier_facts = MySupplierFacts
    line_facts_model = MyLineFacts
    constants = constants

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

    def assess_tax(self, view: CaseView, catalog: Catalog) -> TaxResult:
        return tax.assess(
            view.invoice,
            view.supplier,
            self.supplier_facts_of(view.supplier),
            view.company,
            self.company_facts_of(view.company),
            catalog,
        )


PACK = MalaysiaPack()
