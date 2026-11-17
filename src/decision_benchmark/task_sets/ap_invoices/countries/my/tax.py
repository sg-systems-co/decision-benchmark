"""Malaysian SST treatment: was SST charged correctly? (step-11 plan §5.3)

Each line is assessed on its own. The invoice code is the first code in
PRECEDENCE that any line has (plan Q4).
"""

from __future__ import annotations

from datetime import date

from ...codes import Code
from ...findings import TaxResult, UnsupportedCase, Unsettled, finding
from ...models import Catalog, Company, Finding, Invoice, Supplier
from ...models.common import ZERO
from .constants import TAX_CLASS_RATE, TAX_TYPE_SALES, TAX_TYPE_SERVICE
from .models import MyCompanyFacts, MyInvois, MySupplierFacts, MyTaxProfile
from .models import MyTaxTreatment as T

PRECEDENCE = (
    T.SST_SUPPLIER_NOT_REGISTERED,
    T.SST_SHOULD_BE_EXEMPT,
    T.SST_WRONG_RATE,
    T.SST_CORRECT,
    T.NO_SST,
)


def _sst_registered_for(supplier: Supplier, kind: str, day: date) -> bool:
    return supplier.registration("MY_SST", on=day, types=(kind,)) is not None


def _schedule_c_holds(company: Company, facts: MyCompanyFacts, category: str, day: date) -> bool:
    if not facts.is_registered_manufacturer:
        return False
    return any(
        cert.kind == "schedule_c" and cert.valid_on(day) and category in cert.categories
        for cert in company.policy_pack.exemption_certificates
    )


def assess(
    inv: Invoice,
    supplier: Supplier,
    supplier_facts: MySupplierFacts,
    company: Company,
    company_facts: MyCompanyFacts,
    catalog: Catalog,
) -> TaxResult:
    e = inv.einvoice
    assert isinstance(e, MyInvois)
    ext = {x.line_no: x for x in e.lines}
    day = inv.issue_date
    codes: list[T] = []
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        cat = catalog.get(line.category)
        profile = cat.tax["MY"]
        assert isinstance(profile, MyTaxProfile)
        cls = profile.tax_class
        n = line.line_no
        if line.tax_amount <= ZERO:
            codes.append(T.NO_SST)
            continue
        line_ext = ext.get(n)
        tax_type = line_ext.tax_type if line_ext else None
        if tax_type is None:
            # A missing tax type is a mandatory-field problem (validity.py); the tax itself is
            # assessed as usual ("Unchanged" in the rule sheet), from the category's class.
            tax_type = TAX_TYPE_SERVICE if cls.startswith("service_") else TAX_TYPE_SALES
        if tax_type == TAX_TYPE_SERVICE:
            if not cls.startswith("service_"):
                raise UnsupportedCase(f"service tax on {cat.category}, which is not a taxable service")
            # 1. Supplier not registered for service tax.
            if not _sst_registered_for(supplier, "service", day):
                codes.append(T.SST_SUPPLIER_NOT_REGISTERED)
                findings.append(finding(Code.SUPPLIER_NOT_TAX_REGISTERED, line=n, tax="service"))
                continue
            if profile.group_relief:
                # Group relief (Group G items (a) to (i), (l) and (n) only). For other items the group
                # relation is irrelevant. Every value of group_relation is handled here explicitly.
                # A clear "same group" value must not be added without its rule (Service Tax
                # Policy 8/2020) and tests in the same PR; test_group_relation_values_are_all_handled
                # fails if the Literal gains a value that is not in GROUP_RELATIONS_HANDLED.
                relation = supplier_facts.group_relation
                if relation == "unclear":
                    # The documents don't show whether the supplier is in the buyer's group.
                    unsettled.append(Unsettled("group_relief_unclear", tax_related=True))
                    continue
                if relation != "unrelated":
                    raise UnsupportedCase(f"group relation {relation!r} has no rule in v0.9")
            if profile.b2b_exempt:
                # 3. B2B exemption: both registered, the buyer provides a taxable service under the
                # same First Schedule item, not for personal use.
                buyer_registered = company.registration("MY_SST", on=day) is not None
                if buyer_registered and not line.facts.get("personal_use", False):
                    if line.facts.get("same_service_unclear", False):
                        unsettled.append(Unsettled("b2b_same_service_unclear", tax_related=True))
                        continue
                    if profile.service_item in company_facts.services_provided:
                        codes.append(T.SST_SHOULD_BE_EXEMPT)
                        findings.append(finding(Code.TAX_SHOULD_BE_EXEMPT, line=n, basis="b2b"))
                        continue
        elif tax_type == TAX_TYPE_SALES:
            if not cls.startswith("sales_") or cls == "sales_exempt":
                raise UnsupportedCase(f"sales tax on {cat.category}, outside the planted v0.9 situations")
            if not _sst_registered_for(supplier, "sales", day):
                codes.append(T.SST_SUPPLIER_NOT_REGISTERED)
                findings.append(finding(Code.SUPPLIER_NOT_TAX_REGISTERED, line=n, tax="sales"))
                continue
            if not supplier_facts.is_manufacturer:
                raise UnsupportedCase("sales tax charged by a registered non-manufacturer, outside the v0.9 rule sheet")
            # 2. Schedule C raw materials bought by a registered manufacturer.
            if profile.schedule_c_eligible and _schedule_c_holds(company, company_facts, cat.category, day):
                codes.append(T.SST_SHOULD_BE_EXEMPT)
                findings.append(finding(Code.TAX_SHOULD_BE_EXEMPT, line=n, basis="schedule_c"))
                continue
        else:
            raise UnsupportedCase(f"tax charged on line {n} with tax type {tax_type!r}")
        # 4. Rate.
        expected = TAX_CLASS_RATE[cls]
        if line.tax_rate != expected:
            codes.append(T.SST_WRONG_RATE)
            findings.append(finding(Code.WRONG_TAX_RATE, line=n, charged=str(line.tax_rate), expected=str(expected)))
        else:
            codes.append(T.SST_CORRECT)
    if unsettled:
        return TaxResult(None, [], unsettled)
    code = next(c for c in PRECEDENCE if c in codes)
    return TaxResult(code, findings, [])
