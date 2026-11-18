"""A11: the Malaysian B2B exemption by First Schedule service item, group relief for Group G
items (a) to (i), (l) and (n) only, and the Singapore medical and accident insurance exception.

Malaysian B2B conditions in every scheme: supplier and buyer are both SST-registered, the buyer
itself provides a taxable service under the same item, and the service is not for personal use.
"""

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D
from decision_benchmark.task_sets.ap_invoices.countries import TaxTreatment as T

from .factory import (
    answer, buyer_service_registered, ein, my_base, my_line, set_lines, set_po_line, sg_base, sg_line, tax_facts,
)

# One category per B2B scheme: (category, GL account, rate, item, a different item of another scheme).
SCHEMES = {
    "G": ("management_services", "6160-000", "8", "G(i)", "G(h)"),
    "J": ("logistics_haulage", "5300-400", "6", "J1(a)", "J1(d)"),
    "I8": ("advertising", "6160-000", "8", "I8", "I2"),
    "L": ("construction_works", "6160-000", "6", "L", "G(a)"),
}


def _my(category, gl, rate, provides=(), **facts):
    r, c = my_base()
    set_po_line(r, category=category, gl_account=gl)
    set_lines(c, [my_line(1, category, 1, "3200.00", rate=rate, tax_type="02", po_line_no=1, **facts)])
    tax_facts(r["company"], services_provided=list(provides))
    buyer_service_registered(r)
    return r, c


def _exempt(a):
    assert (a.decision, a.tax_treatment) == (D.REQUEST_CORRECTED_INVOICE, T.SST_SHOULD_BE_EXEMPT), a.findings
    assert "TAX_SHOULD_BE_EXEMPT" in a.reason_codes


def _correct(a):
    assert (a.decision, a.tax_treatment) == (D.APPROVE, T.SST_CORRECT), a.findings


@pytest.mark.parametrize("scheme", SCHEMES)
def test_b2b_positive(scheme):
    category, gl, rate, item, _ = SCHEMES[scheme]
    _exempt(answer(*_my(category, gl, rate, provides=[item])))


@pytest.mark.parametrize("scheme", SCHEMES)
def test_b2b_near_miss_buyer_provides_a_different_item(scheme):
    category, gl, rate, _, other = SCHEMES[scheme]
    _correct(answer(*_my(category, gl, rate, provides=[other])))


@pytest.mark.parametrize("scheme", SCHEMES)
def test_b2b_near_miss_buyer_not_registered(scheme):
    category, gl, rate, item, _ = SCHEMES[scheme]
    r, c = _my(category, gl, rate, provides=[item])
    r["company"]["tax_registrations"] = [x for x in r["company"]["tax_registrations"] if x["scheme"] != "MY_SST"]
    ein(c)["buyer_sst_no"] = None
    _correct(answer(r, c))


@pytest.mark.parametrize("scheme", SCHEMES)
def test_b2b_near_miss_personal_use(scheme):
    category, gl, rate, item, _ = SCHEMES[scheme]
    _correct(answer(*_my(category, gl, rate, provides=[item], personal_use=True)))


def test_courier_is_its_own_logistics_item():
    # Logistics guide, example 52: a 1(d) courier and a 1(a) logistics provider are different items.
    _correct(answer(*_my("courier_services", "5300-400", "6", provides=["J1(a)"])))
    _exempt(answer(*_my("courier_services", "5300-400", "6", provides=["J1(d)"])))


def test_same_item_different_categories():
    # The buyer provides G(h) through software development and buys IT services, also G(h).
    _exempt(answer(*_my("it_services", "6150-100", "8", provides=["G(h)"])))


@pytest.mark.parametrize("category, item", [("recruitment_services", "G(j)"), ("guard_services", "G(k)")])
def test_employment_and_guards_are_never_exempt(category, item):
    _correct(answer(*_my(category, "6160-000" if item == "G(j)" else "6170-000", "8", provides=[item])))


def test_unclear_group_relation_on_maintenance_is_a_hand_over():
    # G(n) is in group relief since 1 May 2024 (P.U. (A) 354/2024, First Schedule paras 3 and 3A).
    for provides in ([], ["G(n)"]):
        r, c = _my("maintenance_repair", "6160-000", "8", provides=provides)
        tax_facts(r["suppliers"][0], group_relation="unclear")
        a = answer(r, c)
        assert a.decision is D.HAND_OVER and a.tax_treatment is None


def test_maintenance_b2b_exemption():
    _exempt(answer(*_my("maintenance_repair", "6160-000", "8", provides=["G(n)"])))


def test_unclear_group_relation_on_g_a_is_still_a_hand_over():
    # G(a) is in group relief (Service Tax Policy 8/2020): the documents must settle the relation.
    r, c = _my("legal_services", "6160-000", "8")
    tax_facts(r["suppliers"][0], group_relation="unclear")
    a = answer(r, c)
    assert a.decision is D.HAND_OVER and a.tax_treatment is None


def test_unclear_group_relation_on_a_non_g_scheme_is_not_a_hand_over():
    r, c = _my("advertising", "6160-000", "8")
    tax_facts(r["suppliers"][0], group_relation="unclear")
    _correct(answer(r, c))


def _insurance(**facts):
    r, c = sg_base()
    set_po_line(r, category="group_medical_insurance", gl_account="6510-000", qty=1, unit_price="4800.00")
    r["goods_receipts"][0]["lines"][0]["qty_received"] = 1
    set_lines(c, [sg_line(1, "group_medical_insurance", 1, "4800.00", po_line_no=1, **facts)])
    return answer(r, c)


def test_obligatory_insurance_is_claimable():
    a = _insurance(insurance_obligatory=True)
    assert (a.decision, a.tax_treatment) == (D.APPROVE, T.CLAIMABLE)


def test_voluntary_insurance_is_disallowed():
    a = _insurance(insurance_obligatory=False)
    assert (a.decision, a.tax_treatment) == (D.APPROVE, T.NOT_CLAIMABLE_DISALLOWED)
    assert "GST_NOT_CLAIMABLE_DISALLOWED" in a.reason_codes


def test_unknown_insurance_obligation_is_a_hand_over():
    a = _insurance()
    assert a.decision is D.HAND_OVER and a.tax_treatment is None
