"""What one Malaysian line rule reads (LineCtx) and what it returns (Outcome, Exempt, Partial).

Facts come from three places, and each has one rule for "not shown":
- line facts, read through the FactReader: not recorded means the case doesn't raise the question, so
  the ordinary value holds (``fact``); recorded with a null value means the documents don't show it,
  and the line is HAND_OVER with the reading rule as its basis;
- the supplier and company masters (party facts): a None or a "known: false" flag the rule needs is
  HAND_OVER the same way (``NotSettled``);
- the catalog profile of the line's category: the service item and tax class when the line facts don't
  record them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import cached_property

from ....codes import Code
from ....fact_reader import FactReader
from ....findings import NotSettled, finding
from ....models import BuyerAction, Catalog, Company, Finding, Invoice, InvoiceLine, Supplier
from ....models.common import ZERO
from ....models.contract import ContractRecord
from ..constants import TAX_TYPE_SALES, TAX_TYPE_SERVICE
from ..models import MyCompanyFacts, MyInvoisLine, MySupplierFacts, MyTaxProfile
from ..models import MyTaxTreatment as T

HOME = "MY"
LOCAL_AUTHORITY_TO = date(2025, 9, 30)


@dataclass(frozen=True)
class Exempt:
    """No tax is due on the whole line, by the rule in basis."""

    basis: str


@dataclass(frozen=True)
class Partial:
    """Tax is due on part of the line only: ``taxable`` of the net amount, by the rule in basis."""

    basis: str
    taxable: Decimal


@dataclass(frozen=True)
class Taxable:
    """The line stays taxable by the rule in basis (e.g. a consultation fee not itemised, P-12): a correct line
    names this rule as its basis."""

    basis: str


@dataclass(frozen=True)
class Outcome:
    code: str
    basis: str
    findings: tuple[Finding, ...] = ()
    actions: tuple[BuyerAction, ...] = ()


@dataclass
class LineCtx:
    line: InvoiceLine
    ext: MyInvoisLine | None
    reader: FactReader
    profile: MyTaxProfile
    supplier: Supplier
    sf: MySupplierFacts
    company: Company
    cf: MyCompanyFacts
    day: date
    """The invoice date: the date the rules are judged at unless a rule names another."""
    processing_date: date
    """The case's processing date (as_of_date): K-1 registrations are judged at it (A12 decision 5)."""
    catalog: Catalog
    contracts: list[ContractRecord] = field(default_factory=list)
    """The case's contracts with this supplier."""
    invoice: Invoice | None = None
    """The invoice the line is on (rules that read its printed parties, e.g. L-5)."""

    # -- facts ----------------------------------------------------------------

    def fact(self, name: str, default, basis: str):
        return self.reader.value_or(name, default, basis)

    def need(self, name: str, basis: str):
        return self.reader.need(name, basis)

    @cached_property
    def item(self) -> str | None:
        """The First Schedule item: the line fact, else the category's item."""
        return self.fact("service_item", self.profile.service_item, "MS-4")

    @property
    def group(self) -> str | None:
        return self.item[0] if self.item else None

    @property
    def net(self) -> Decimal:
        return self.line.net_amount

    @property
    def charged(self) -> bool:
        return self.line.tax_amount > ZERO

    @property
    def is_goods(self) -> bool:
        return self.profile.tax_class.startswith("sales_")

    @property
    def tax_type(self) -> str | None:
        """The tax type charged: the e-invoice line's, else the one the line's nature implies."""
        if self.ext is not None and self.ext.tax_type in (TAX_TYPE_SALES, TAX_TYPE_SERVICE):
            return self.ext.tax_type
        return TAX_TYPE_SALES if self.is_goods else TAX_TYPE_SERVICE

    @property
    def foreign_supplier(self) -> bool:
        return self.supplier.country != HOME

    # -- parties --------------------------------------------------------------

    def supplier_registered(self, kind: str, basis: str) -> bool:
        if self.supplier.registration("MY_SST", on=self.day, types=(kind,)) is not None:
            return True
        if not self.sf.registration_known:
            raise NotSettled(basis, "supplier SST registration not shown")
        return False

    def contract(self, basis: str) -> ContractRecord | None:
        """The contract behind the line: the only one with the supplier, or the only one in force on the invoice
        date. None: no written contract in the case. Several and none singled out: HAND_OVER."""
        if len(self.contracts) <= 1:
            return self.contracts[0] if self.contracts else None
        live = [k for k in self.contracts
                if (k.start is None or k.start <= self.day) and (k.end is None or self.day <= k.end)]
        if len(live) == 1:
            return live[0]
        raise NotSettled(basis, "which contract the line falls under is not shown")

    def government_supplier(self, basis: str, new_scope_from: date) -> bool:
        """Federal and State Governments neither charge nor pay on new-scope services from 1 Jul 2025; local
        authorities are exempt only 1 Jul-30 Sep 2025 (STP 1/2025 items 2-3, 2/2025, 3/2025: K-5, L-7, P-8)."""
        kind = self.sf.supplier_kind
        if kind == "federal_state_government":
            return self.day >= new_scope_from
        if kind == "local_authority":
            return new_scope_from <= self.day <= LOCAL_AUTHORITY_TO
        return False

    def buyer_registered(self) -> bool:
        """The company is a registered person under the Service Tax Act 2018 on the invoice date (the B2B order,
        s26 and the Service Tax Policies are made under that Act): a sales-tax registration doesn't count."""
        return self.company.registration("MY_SST", on=self.day, types=("service",)) is not None

    def buyer_provides(self, prefix: str) -> bool:
        """The company provides a service whose First Schedule item starts with prefix (e.g. "K", "J", "G(h)")."""
        return any(s.startswith(prefix) for s in self.cf.services_provided)

    # -- outcomes -------------------------------------------------------------

    def exempt(self, rule: Exempt, label: str | None = None) -> Outcome:
        """Tax charged on an exempt line: SST_SHOULD_BE_EXEMPT; none charged: NO_SST."""
        if self.charged:
            return Outcome(T.SST_SHOULD_BE_EXEMPT, rule.basis, (
                finding(Code.TAX_SHOULD_BE_EXEMPT, line=self.line.line_no, basis=label or rule.basis),))
        return Outcome(T.NO_SST, rule.basis)

    def exempt_part(self, basis: str) -> Outcome:
        """Tax charged on the whole line where part of it is exempt."""
        return Outcome(T.SST_SHOULD_BE_EXEMPT, basis, (
            finding(Code.TAX_SHOULD_BE_EXEMPT, line=self.line.line_no, basis=basis, part=True),))

    def not_registered(self, tax: str, basis: str) -> Outcome:
        return Outcome(T.SST_SUPPLIER_NOT_REGISTERED, basis, (
            finding(Code.SUPPLIER_NOT_TAX_REGISTERED, line=self.line.line_no, tax=tax),))

    def wrong_rate(self, basis: str, expected: Decimal) -> Outcome:
        return Outcome(T.SST_WRONG_RATE, basis, (
            finding(Code.WRONG_TAX_RATE, line=self.line.line_no, charged=str(self.line.tax_rate), expected=str(expected)),))

    def undercharged(self, basis: str, tax: str) -> Outcome:
        return Outcome(T.SST_UNDERCHARGED, basis, (finding(Code.TAX_UNDERCHARGED, line=self.line.line_no, tax=tax),))
