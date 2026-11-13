"""Malaysian SST treatment: was SST charged correctly? (step-11 plan §5.3)

Each line is assessed on its own. The invoice code is the first code in
PRECEDENCE that any line has (plan Q4).
"""

from __future__ import annotations

from decimal import Decimal

from ..models import Catalog, Company, Finding, InvoiceMY, Supplier, TaxTreatment
from .constants import MY_TAX_CLASS_RATE, MY_TAX_TYPE_SALES, MY_TAX_TYPE_SERVICE
from .findings import UnsupportedCase, Unsettled, finding

ZERO = Decimal("0")

PRECEDENCE = (
    TaxTreatment.SST_SUPPLIER_NOT_REGISTERED,
    TaxTreatment.SST_SHOULD_BE_EXEMPT,
    TaxTreatment.SST_WRONG_RATE,
    TaxTreatment.SST_CORRECT,
    TaxTreatment.NO_SST,
)


def _schedule_c_holds(company: Company, category: str, day) -> bool:
    if not company.is_registered_manufacturer:
        return False
    return any(
        cert.kind == "schedule_c" and cert.valid_on(day) and category in cert.categories
        for cert in company.policy_pack.exemption_certificates
    )


def assess(
    inv: InvoiceMY, supplier: Supplier, company: Company, catalog: Catalog
) -> tuple[TaxTreatment | None, list[Finding], list[Unsettled]]:
    codes: list[TaxTreatment] = []
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        cat = catalog.get(line.category)
        n = line.line_no
        if line.tax_amount <= ZERO:
            codes.append(TaxTreatment.NO_SST)
            continue
        tax_type = line.tax_type
        if tax_type is None:
            # A missing tax type is a mandatory-field problem (validity_my); the tax itself is
            # assessed as usual ("Unchanged" in the rule sheet), from the category's class.
            cls = cat.my_tax_class or ""
            tax_type = MY_TAX_TYPE_SERVICE if cls.startswith("service_") else MY_TAX_TYPE_SALES
        if tax_type == MY_TAX_TYPE_SERVICE:
            if not (cat.my_tax_class or "").startswith("service_"):
                raise UnsupportedCase(f"service tax on {cat.category}, which is not a taxable service")
            # 1. Supplier not registered for service tax.
            if not supplier.sst_registered_for("service"):
                codes.append(TaxTreatment.SST_SUPPLIER_NOT_REGISTERED)
                findings.append(finding("SUPPLIER_NOT_TAX_REGISTERED", line=n, tax="service"))
                continue
            if cat.group_g and not cat.group_g_excluded:
                # Group relief: documents don't show whether the supplier is in the buyer's group.
                if supplier.group_relation == "unclear":
                    unsettled.append(Unsettled("group_relief_unclear", tax_related=True))
                    continue
                # 3. B2B exemption for Group G services between registered persons.
                if company.sst_registration_no and not line.facts.personal_use:
                    if line.facts.same_service_unclear:
                        unsettled.append(Unsettled("group_g_same_service_unclear", tax_related=True))
                        continue
                    if cat.category in company.services_provided:
                        codes.append(TaxTreatment.SST_SHOULD_BE_EXEMPT)
                        findings.append(finding("TAX_SHOULD_BE_EXEMPT", line=n, basis="group_g_b2b"))
                        continue
        elif tax_type == MY_TAX_TYPE_SALES:
            if not (cat.my_tax_class or "").startswith("sales_") or cat.my_tax_class == "sales_exempt":
                raise UnsupportedCase(f"sales tax on {cat.category}, outside the planted v0.9 situations")
            if not (supplier.sst_registered_for("sales") and supplier.is_manufacturer):
                codes.append(TaxTreatment.SST_SUPPLIER_NOT_REGISTERED)
                findings.append(finding("SUPPLIER_NOT_TAX_REGISTERED", line=n, tax="sales"))
                continue
            # 2. Schedule C raw materials bought by a registered manufacturer.
            if cat.schedule_c_eligible and _schedule_c_holds(company, cat.category, inv.issue_date):
                codes.append(TaxTreatment.SST_SHOULD_BE_EXEMPT)
                findings.append(finding("TAX_SHOULD_BE_EXEMPT", line=n, basis="schedule_c"))
                continue
        else:
            raise UnsupportedCase(f"tax charged on line {n} with tax type {line.tax_type!r}")
        # 4. Rate.
        expected = MY_TAX_CLASS_RATE[cat.my_tax_class]  # type: ignore[index]
        if line.tax_rate != expected:
            codes.append(TaxTreatment.SST_WRONG_RATE)
            findings.append(finding("WRONG_TAX_RATE", line=n, charged=str(line.tax_rate), expected=str(expected)))
        else:
            codes.append(TaxTreatment.SST_CORRECT)
    if unsettled:
        return None, [], unsettled
    code = next(c for c in PRECEDENCE if c in codes)
    return code, findings, []
