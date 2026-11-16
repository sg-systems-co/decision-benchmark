"""Malaysian SST cases outside the v0.9 rule sheet: the engine refuses them instead of guessing."""

from typing import get_args

import pytest

from decision_benchmark.task_sets.ap_invoices_my_sg.models import Decision as D
from decision_benchmark.task_sets.ap_invoices_my_sg.models import Supplier
from decision_benchmark.task_sets.ap_invoices_my_sg.models import TaxTreatment as T
from decision_benchmark.task_sets.ap_invoices_my_sg.rules import UnsupportedCase
from decision_benchmark.task_sets.ap_invoices_my_sg.rules.tax_my import GROUP_RELATIONS_HANDLED

from .factory import answer, my_base, my_line, set_lines, set_po_line


def _sales_tax_invoice(**supplier):
    """Raw resin with 10% sales tax; no Schedule C certificate, so only the supplier decides the code."""
    r, c = my_base()
    set_po_line(r, category="test_raw_resin", gl_account="5100-100", qty=100, unit_price="12.40")
    r["goods_receipts"][0]["lines"][0]["qty_received"] = 100
    set_lines(c, [my_line(1, "test_raw_resin", 100, "12.40", rate="10", tax_type="01", po_line_no=1)])
    r["suppliers"][0].update(supplier)
    return r, c


def test_sales_tax_by_registered_non_manufacturer_is_unsupported():
    r, c = _sales_tax_invoice(sst_type="sales", is_manufacturer=False)
    with pytest.raises(UnsupportedCase, match="registered non-manufacturer, outside the v0.9 rule sheet"):
        answer(r, c)


def test_sales_tax_by_supplier_without_sales_tax_registration_is_not_registered():
    # Registered for service tax only: no sales-tax registration.
    r, c = _sales_tax_invoice(sst_type="service", is_manufacturer=True)
    a = answer(r, c)
    assert a.decision is D.REQUEST_CORRECTED_INVOICE
    assert a.tax_treatment is T.SST_SUPPLIER_NOT_REGISTERED
    assert "SUPPLIER_NOT_TAX_REGISTERED" in a.reason_codes


def test_sales_tax_by_supplier_with_no_sst_registration_at_all_is_not_registered():
    r, c = _sales_tax_invoice(sst_registration_no=None, sst_type="none", is_manufacturer=False)
    c["invoice"]["supplier_sst_no"] = None
    a = answer(r, c)
    assert a.tax_treatment is T.SST_SUPPLIER_NOT_REGISTERED


def test_sales_tax_by_registered_manufacturer_is_correct():
    r, c = _sales_tax_invoice(sst_type="sales", is_manufacturer=True)
    a = answer(r, c)
    assert a.decision is D.APPROVE and a.tax_treatment is T.SST_CORRECT


def test_group_relation_values_are_all_handled():
    # A new value (for example a clear "same group") needs its rule (Service Tax Policy 8/2020)
    # in tax_my.py and tests in the same PR, then an entry in GROUP_RELATIONS_HANDLED.
    values = set(get_args(Supplier.model_fields["group_relation"].annotation))
    assert values == set(GROUP_RELATIONS_HANDLED)
