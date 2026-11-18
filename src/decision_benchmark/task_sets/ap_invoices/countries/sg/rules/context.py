"""What one Singapore line rule reads (LineCtx) and what it returns (Outcome).

Facts follow the Malaysian pack's convention: a line fact not recorded takes the ordinary value (the case
doesn't raise the question); recorded with a null value, the documents don't show it and the line is
HAND_OVER with the reading rule as basis (NotSettled). Party facts that a rule needs and that are None are
HAND_OVER the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ....codes import Code
from ....fact_reader import FactReader
from ....findings import finding
from ....models import BuyerAction, Catalog, Company, Finding, Invoice, InvoiceLine, Supplier
from ....models.common import ZERO
from ....models.contract import ResidenceCertificate
from ....models.tax import TaxRegistration
from ..models import PintSgLine, SgCompanyFacts, SgSupplierFacts, SgTaxProfile
from ..models import SgTaxTreatment as T

HOME_COUNTRY = "SG"


@dataclass(frozen=True)
class Outcome:
    code: str
    basis: str
    findings: tuple[Finding, ...] = ()
    actions: tuple[BuyerAction, ...] = ()


@dataclass
class LineCtx:
    line: InvoiceLine
    ext: PintSgLine | None
    reader: FactReader
    profile: SgTaxProfile
    invoice: Invoice
    supplier: Supplier
    sf: SgSupplierFacts
    company: Company
    cf: SgCompanyFacts
    registration: TaxRegistration | None
    """The supplier's GST registration on the invoice date."""
    charged: bool
    """The line carries GST (a rate or amount on the line, or GST on the invoice not split by line)."""
    day: date
    processing_date: date
    catalog: Catalog
    residence_certificates: list[ResidenceCertificate] = field(default_factory=list)
    """The supplier's certificates of residence in the case records (treaty withholding rates)."""


    def fact(self, name: str, default, basis: str):
        return self.reader.value_or(name, default, basis)

    def need(self, name: str, basis: str):
        return self.reader.need(name, basis)

    @property
    def net(self) -> Decimal:
        return self.line.net_amount

    @property
    def foreign_supplier(self) -> bool:
        return self.supplier.country != HOME_COUNTRY

    @property
    def rate_shown(self) -> bool:
        return self.line.tax_rate > ZERO

    def wrongly_charged(self, basis: str, code: Code = Code.TAX_SHOULD_BE_EXEMPT) -> Outcome:
        return Outcome(T.GST_WRONGLY_CHARGED, basis, (finding(code, line=self.line.line_no, basis=basis),))

    def undercharged(self, basis: str, code: Code = Code.TAX_UNDERCHARGED) -> Outcome:
        return Outcome(T.GST_UNDERCHARGED, basis, (finding(code, line=self.line.line_no, basis=basis),))
