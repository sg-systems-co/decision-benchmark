"""The CountryPack interface. One pack per country; the registry in __init__.py maps country -> pack.

A pack holds everything the shared models and rules must not know about one
country: its tax registration schemes, its tax-treatment codes, the category
tax profile model, the e-invoice block model, the party tax-fact models, the
line facts it reads, its invoice validity check, its tax assessment and its
constants with sources. Adding a country means adding one pack and one line in
the registry.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from types import ModuleType
from typing import TYPE_CHECKING, ClassVar

from ..findings import TaxResult
from ..models.common import CountryBlock, TaxProfile
from ..models.evidence import LineFact, LineFacts

if TYPE_CHECKING:
    from ..models import Catalog, Category, Company, Finding, Invoice, InvoiceLine
    from ..rules.view import CaseView


class CountryPack:
    country: ClassVar[str]
    currency: ClassVar[str]
    registration_types: ClassVar[dict[str, tuple[str, ...]]]
    """Tax registration scheme -> allowed types. Scheme names start with the country code."""
    certificate_kinds: ClassVar[tuple[str, ...]] = ()
    """Exemption-certificate kinds a company's policy pack may hold."""
    tax_codes: ClassVar[type[StrEnum]]
    tax_profile: ClassVar[type[TaxProfile]]
    profile_required: ClassVar[bool]
    """True: every category used in this country needs a tax profile; False: the default profile applies."""
    einvoice: ClassVar[type[CountryBlock]]
    company_facts: ClassVar[type[CountryBlock]]
    supplier_facts: ClassVar[type[CountryBlock]]
    line_facts_model: ClassVar[type[LineFacts]]
    """The line facts this country's rules read: exactly its schema part's $defs/line_facts."""
    constants: ClassVar[ModuleType]

    # -- models ---------------------------------------------------------------

    def check_company(self, company: Company) -> None:
        """Raise ValueError if the company's country fields don't fit this country."""
        if company.base_currency != self.currency:
            raise ValueError(f"a {self.country} company has base_currency {self.currency}")
        if company.tax_facts is not None and not isinstance(company.tax_facts, self.company_facts):
            raise ValueError(f"company tax_facts must be the {self.country} model")
        for reg in company.tax_registrations:
            if reg.scheme not in self.registration_types:
                raise ValueError(f"a {self.country} company can't hold a {reg.scheme} registration")
        for cert in company.policy_pack.exemption_certificates:
            if cert.kind not in self.certificate_kinds:
                raise ValueError(f"{cert.kind} certificates don't exist in {self.country}")

    def check_category(self, category: Category) -> None:
        """Raise ValueError if the category's profile for this country is missing or doesn't fit."""
        if self.profile_required and self.country not in category.tax:
            raise ValueError(f"{category.category}: categories used in {self.country} need a tax profile")

    def check_invoice(self, invoice: Invoice) -> None:
        """Raise ValueError for e-invoice lines that don't exist or line facts of another country."""
        nos = {line.line_no for line in invoice.lines}
        ext = [line.line_no for line in getattr(invoice.einvoice, "lines", [])]
        if len(ext) != len(set(ext)) or not set(ext) <= nos:
            raise ValueError("einvoice lines must name existing invoice lines, once each")
        for line in invoice.lines:
            if line.facts is not None and not isinstance(line.facts, self.line_facts_model):
                raise ValueError(f"line {line.line_no}: line facts must be the {self.country} model")

    # -- reading --------------------------------------------------------------

    def fact(self, line: InvoiceLine, name: str) -> LineFact | None:
        """The recorded fact, or None when the line's facts don't record it."""
        if name not in self.line_facts_model.model_fields:
            raise KeyError(f"{name!r} is not a {self.country} line fact")
        return getattr(line.facts, name) if line.facts is not None else None

    def profile(self, category: Category) -> TaxProfile:
        return category.tax.get(self.country) or self.tax_profile()

    def supplier_facts_of(self, supplier) -> CountryBlock:
        facts = supplier.tax_facts
        return facts if isinstance(facts, self.supplier_facts) else self.supplier_facts(country=self.country)

    def company_facts_of(self, company: Company) -> CountryBlock:
        facts = company.tax_facts
        return facts if isinstance(facts, self.company_facts) else self.company_facts(country=self.country)

    def einvoice_line(self, invoice: Invoice, line_no: int):
        """The e-invoice extension of one line, or None."""
        return next((x for x in getattr(invoice.einvoice, "lines", []) if x.line_no == line_no), None)

    def gross_in_local_currency(self, invoice: Invoice) -> Decimal | None:
        """The invoice gross in this country's currency as printed on a foreign-currency invoice, if any."""
        return None

    # -- rules ----------------------------------------------------------------

    def validity(self, invoice: Invoice) -> list[Finding]:
        """Invoice-validity findings that hold whatever the tax treatment."""
        raise NotImplementedError

    def assess_tax(self, view: CaseView, catalog: Catalog) -> TaxResult:
        raise NotImplementedError
