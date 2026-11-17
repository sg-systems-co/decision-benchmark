"""Malaysian SST treatment: was SST charged correctly? (step-11 plan §5.3, A12 plan §4)

Each line is assessed on its own into a LineResult with the rule ID that decides it. The case-level
code is the worst line by the pack's severity order (spec v0.10). Line facts are read through a
FactReader, so the answer key's gold facts are exactly the fields read.

Rule IDs (bases) follow the v0.10 sheet; until the v0.10 Malaysian rules land (A12 build PR 2) the
v0.9 logic below names its closest v0.10 rule.
"""

from __future__ import annotations

from datetime import date

from ...codes import Code
from ...fact_reader import FactReader
from ...findings import LineResult, TaxResult, UnsupportedCase, Unsettled, finding, worst_line
from ...models import Catalog, Company, Finding, Invoice, Supplier
from ...models.common import ZERO
from ...models.evidence import LineFacts
from .constants import TAX_CLASS_RATE, TAX_TYPE_SALES, TAX_TYPE_SERVICE
from .models import MyCompanyFacts, MyInvois, MySupplierFacts, MyTaxProfile
from .models import MyTaxTreatment as T


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
    facts: dict[int, LineFacts] | None = None,
) -> TaxResult:
    """facts: line facts to use instead of those recorded on the lines (check_rules)."""
    from . import PACK

    e = inv.einvoice
    assert isinstance(e, MyInvois)
    ext = {x.line_no: x for x in e.lines}
    day = inv.issue_date
    lines: list[LineResult] = []
    findings: list[Finding] = []
    unsettled: list[Unsettled] = []
    for line in inv.lines:
        reader = FactReader(PACK, line, (facts or {}).get(line.line_no))
        code, basis, line_findings, line_unsettled = _assess_line(
            line, reader, ext.get(line.line_no), supplier, supplier_facts, company, company_facts, catalog, day)
        findings += line_findings
        if line_unsettled:
            unsettled.append(line_unsettled)
        lines.append(LineResult(line.line_no, code, basis, read=tuple(reader.recorded_reads()),
                                missing=tuple(reader.missing())))
    if unsettled:
        return TaxResult(None, [], unsettled, lines)
    return TaxResult(worst_line(lines, PACK.severity_order), findings, [], lines)


def _assess_line(line, reader, line_ext, supplier, supplier_facts, company, company_facts, catalog, day):
    """(code, basis, findings, unsettled) for one line; code None when unsettled."""
    cat = catalog.get(line.category)
    profile = cat.tax["MY"]
    assert isinstance(profile, MyTaxProfile)
    cls = profile.tax_class
    n = line.line_no
    is_service = cls.startswith("service_")
    if line.tax_amount <= ZERO:
        return T.NO_SST, "MS-1" if not cls.startswith("sales_") else "MG-1", [], None
    tax_type = line_ext.tax_type if line_ext else None
    if tax_type is None:
        # A missing tax type is a mandatory-field problem (validity.py); the tax itself is
        # assessed as usual ("Unchanged" in the rule sheet), from the category's class.
        tax_type = TAX_TYPE_SERVICE if is_service else TAX_TYPE_SALES
    if tax_type == TAX_TYPE_SERVICE:
        if not is_service:
            raise UnsupportedCase(f"service tax on {cat.category}, which is not a taxable service")
        # Supplier not registered for service tax (MS-1).
        if not _sst_registered_for(supplier, "service", day):
            return T.SST_SUPPLIER_NOT_REGISTERED, "MS-1", [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, line=n, tax="service")], None
        if profile.group_relief:
            # Group relief (MS-6; Group G items (a) to (i), (l) and (n) only). For other items the group
            # relation is irrelevant. Every value of group_relation is handled here explicitly.
            # A clear "same group" value must not be added without its rule and tests in the same PR;
            # test_group_relation_values_are_all_handled fails if the Literal gains a value that is not
            # in GROUP_RELATIONS_HANDLED.
            relation = supplier_facts.group_relation
            if relation == "unclear":
                # The documents don't show whether the supplier is in the buyer's group.
                return None, "MS-6", [], Unsettled("group_relief_unclear", tax_related=True)
            if relation != "unrelated":
                raise UnsupportedCase(f"group relation {relation!r} has no rule in v0.9")
        if profile.b2b_exempt:
            # B2B exemption (MS-5): both registered, the buyer provides a taxable service under the
            # same First Schedule item, not for personal use.
            buyer_registered = company.registration("MY_SST", on=day) is not None
            if buyer_registered:
                personal = reader.get("personal_use")
                if personal is not None and personal.value is None:
                    return None, "MS-5", [], Unsettled("b2b_personal_use_unclear", tax_related=True)
                if not (personal is not None and personal.value):
                    same = reader.get("same_service_as_buyer")
                    if same is not None and same.value is None:
                        return None, "MS-5", [], Unsettled("b2b_same_service_unclear", tax_related=True)
                    # Not recorded on the line: the company's own service items decide (v0.9).
                    provides = same.value if same is not None else profile.service_item in company_facts.services_provided
                    if provides:
                        return T.SST_SHOULD_BE_EXEMPT, "MS-5", [finding(Code.TAX_SHOULD_BE_EXEMPT, line=n, basis="b2b")], None
        rate_basis = "MS-2"
    elif tax_type == TAX_TYPE_SALES:
        if not cls.startswith("sales_") or cls == "sales_exempt":
            raise UnsupportedCase(f"sales tax on {cat.category}, outside the planted v0.9 situations")
        if not _sst_registered_for(supplier, "sales", day):
            return T.SST_SUPPLIER_NOT_REGISTERED, "MG-1", [finding(Code.SUPPLIER_NOT_TAX_REGISTERED, line=n, tax="sales")], None
        if not supplier_facts.is_manufacturer:
            raise UnsupportedCase("sales tax charged by a registered non-manufacturer, outside the v0.9 rule sheet")
        # Schedule C raw materials bought by a registered manufacturer (MG-4).
        if profile.schedule_c_eligible and _schedule_c_holds(company, company_facts, cat.category, day):
            return T.SST_SHOULD_BE_EXEMPT, "MG-4", [finding(Code.TAX_SHOULD_BE_EXEMPT, line=n, basis="schedule_c")], None
        rate_basis = "MG-2"
    else:
        raise UnsupportedCase(f"tax charged on line {n} with tax type {tax_type!r}")
    # Rate (MS-2, MG-2).
    expected = TAX_CLASS_RATE[cls]
    if line.tax_rate != expected:
        return T.SST_WRONG_RATE, rate_basis, [
            finding(Code.WRONG_TAX_RATE, line=n, charged=str(line.tax_rate), expected=str(expected))], None
    return T.SST_CORRECT, rate_basis, [], None
