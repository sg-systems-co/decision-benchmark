"""One positive and at least one near-miss test per row of the rule-sheet table.

The table is "From rules to benchmark checks" in tax-rules-v0.9.md. Which test
covers which row is recorded in decision_benchmark/rules/table_rows.py, and
test_table_coverage.py checks that every row is covered.
"""

from decision_benchmark.task_sets.ap_invoices_my_sg.models import Decision as D
from decision_benchmark.task_sets.ap_invoices_my_sg.models import TaxTreatment as T

from .factory import answer, my_base, my_line, set_lines, set_po_line, sg_base, sg_line


def _check(a, decision, tax, *codes):
    assert a.decision is decision, a.findings
    assert a.tax_treatment is tax
    for code in codes:
        assert code in a.reason_codes, a.reason_codes


def _sg_with(category, gl, qty=1, price="4800.00", **facts):
    r, c = sg_base()
    set_po_line(r, category=category, gl_account=gl, qty=qty, unit_price=price)
    r["goods_receipts"][0]["lines"][0]["qty_received"] = qty
    set_lines(c, [sg_line(1, category, qty, price, po_line_no=1, **facts)])
    return r, c


def _my_with(category, gl, rate, tax_type="02", qty=1, price="3200.00"):
    r, c = my_base()
    set_po_line(r, category=category, gl_account=gl, qty=qty, unit_price=price)
    r["goods_receipts"][0]["lines"][0]["qty_received"] = qty
    set_lines(c, [my_line(1, category, qty, price, rate=rate, tax_type=tax_type, po_line_no=1)])
    return r, c


# Row 1: SG valid tax invoice, registered supplier, business expense -> CLAIMABLE, APPROVE


def test_row01_positive():
    _check(answer(*sg_base()), D.APPROVE, T.CLAIMABLE, "MATCHED_WITHIN_TOLERANCE")


def test_row01_negative_supplier_deregistered_before_invoice():
    r, c = sg_base()
    r["suppliers"][0].update(gst_status="deregistered", gst_status_date="2026-06-30")
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.GST_WRONGLY_CHARGED)


# Row 2: SG above S$1,000 without customer name or "Tax Invoice" -> NOT_CLAIMABLE_INVALID_INVOICE


def test_row02_positive_no_customer_name():
    r, c = sg_base()
    c["invoice"]["buyer_block"]["name"] = None
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.NOT_CLAIMABLE_INVALID_INVOICE, "INVALID_TAX_INVOICE")


def test_row02_positive_no_tax_invoice_wording():
    r, c = sg_base()
    c["invoice"]["document_title"] = "Invoice"
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.NOT_CLAIMABLE_INVALID_INVOICE, "INVALID_TAX_INVOICE")


def test_row02_negative_at_or_below_threshold_simplified_invoice_ok():
    r, c = _sg_with("machine_parts", "6400-000", qty=1, price="917.43")  # gross 1,000.00
    c["invoice"]["buyer_block"]["name"] = None
    c["invoice"]["document_title"] = None
    assert c["invoice"]["totals"]["gross"] == "1000.00"
    _check(answer(r, c), D.APPROVE, T.CLAIMABLE)


# Row 3: SG foreign-currency invoice without SGD amounts -> NOT_CLAIMABLE_INVALID_INVOICE


def test_row03_positive():
    r, c = sg_base()
    c["invoice"].update(currency="USD", exchange_rate="1.30")
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.NOT_CLAIMABLE_INVALID_INVOICE, "FOREIGN_CURRENCY_NO_SGD_AMOUNTS")


def test_row03_negative_sgd_amounts_shown():
    r, c = sg_base()
    c["invoice"].update(currency="USD", exchange_rate="1.30", gross_sgd="2125.50", tax_total_sgd="175.50")
    _check(answer(r, c), D.APPROVE, T.CLAIMABLE)


# Row 4: SG supplier's GST number invalid or missing, GST charged -> GST_WRONGLY_CHARGED
# (CHANGELOG clarification: "missing" = not registered or number doesn't match the record.)


def test_row04_positive_supplier_not_registered():
    r, c = sg_base()
    r["suppliers"][0].update(gst_status="none", gst_reg_no=None, gst_status_date=None)
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.GST_WRONGLY_CHARGED, "SUPPLIER_NOT_TAX_REGISTERED")


def test_row04_positive_number_does_not_match_record():
    r, c = sg_base()
    c["invoice"]["supplier_gst_no"] = "20-9999999-X"
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.GST_WRONGLY_CHARGED, "SUPPLIER_NOT_TAX_REGISTERED")


def test_row04_negative_registered_supplier_omits_number_is_invalid_invoice():
    r, c = sg_base()
    c["invoice"]["supplier_gst_no"] = None
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.NOT_CLAIMABLE_INVALID_INVOICE, "INVALID_TAX_INVOICE")


def test_row04_negative_unregistered_supplier_charges_no_gst():
    r, c = _sg_with("machine_parts", "6400-000", qty=10, price="150.00")
    r["suppliers"][0].update(gst_status="none", gst_reg_no=None, gst_status_date=None)
    set_lines(c, [sg_line(1, "machine_parts", 10, "150.00", rate="0", po_line_no=1)])
    c["invoice"]["supplier_gst_no"] = None
    _check(answer(r, c), D.APPROVE, T.NO_GST)


# Row 5: SG OVR-registered overseas vendor charges GST to the registered buyer -> GST_WRONGLY_CHARGED


def test_row05_positive():
    r, c = sg_base()
    r["suppliers"][0].update(gst_regime="ovr", country="OTHER")
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.GST_WRONGLY_CHARGED, "OVR_GST_CHARGED_TO_REGISTERED_BUYER")


def test_row05_negative_ovr_vendor_charges_no_gst():
    r, c = sg_base()
    r["suppliers"][0].update(gst_regime="ovr", country="OTHER")
    set_lines(c, [sg_line(1, "machine_parts", 10, "150.00", rate="0", po_line_no=1)])
    _check(answer(r, c), D.APPROVE, T.NO_GST)


# Row 6: SG club subscription, staff medical, motor car running costs, family benefit
#        -> NOT_CLAIMABLE_DISALLOWED, APPROVE booked without input tax


def test_row06_positive_each_class():
    cases = [
        ("club_subscription", "6420-000", {}),
        ("staff_medical", "6510-000", {"staff_medical_obligatory": False}),
        ("motor_car_running", "6610-000", {"vehicle_is_motor_car": True}),
        ("family_benefit", "6520-000", {}),
    ]
    for category, gl, facts in cases:
        a = answer(*_sg_with(category, gl, **facts))
        _check(a, D.APPROVE, T.NOT_CLAIMABLE_DISALLOWED, "GST_NOT_CLAIMABLE_DISALLOWED")
        assert a.gl_account == gl


def test_row06_negative_obligatory_staff_medical_is_claimable():
    a = answer(*_sg_with("staff_medical", "6510-000", staff_medical_obligatory=True))
    _check(a, D.APPROVE, T.CLAIMABLE)


# Row 7: MY service tax at 8% on logistics, F&B, telecoms or parking -> SST_WRONG_RATE


def test_row07_positive():
    a = answer(*_my_with("logistics_haulage", "5300-400", rate="8"))
    _check(a, D.REQUEST_CORRECTED_INVOICE, T.SST_WRONG_RATE, "WRONG_TAX_RATE")


def test_row07_negative_six_percent_is_correct():
    a = answer(*_my_with("logistics_haulage", "5300-400", rate="6"))
    _check(a, D.APPROVE, T.SST_CORRECT)


# Row 8: MY service tax on a Group G service between two registered persons providing the same service
#        -> SST_SHOULD_BE_EXEMPT


def test_row08_positive():
    r, c = _my_with("management_services", "6160-000", rate="8")
    r["company"]["services_provided"] = ["management_services"]
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.SST_SHOULD_BE_EXEMPT, "TAX_SHOULD_BE_EXEMPT")


def test_row08_negative_buyer_does_not_provide_the_service():
    a = answer(*_my_with("management_services", "6160-000", rate="8"))
    _check(a, D.APPROVE, T.SST_CORRECT)


def test_row08_negative_guard_services_are_excluded():
    r, c = _my_with("guard_services", "6170-000", rate="8")
    r["company"]["services_provided"] = ["guard_services"]
    _check(answer(r, c), D.APPROVE, T.SST_CORRECT)


def test_row08_negative_buyer_not_registered():
    r, c = _my_with("management_services", "6160-000", rate="8")
    r["company"].update(services_provided=["management_services"], sst_registration_no=None)
    c["invoice"]["buyer_sst_no"] = None
    _check(answer(r, c), D.APPROVE, T.SST_CORRECT)


# Row 9: MY sales tax on raw materials bought by a registered manufacturer under Schedule C
#        -> SST_SHOULD_BE_EXEMPT


def _schedule_c(valid_to="2027-12-31"):
    r, c = _my_with("test_raw_resin", "5100-100", rate="10", tax_type="01", qty=100, price="12.40")
    r["suppliers"][0].update(sst_type="sales", is_manufacturer=True)
    r["company"]["policy_pack"]["exemption_certificates"] = [
        {"kind": "schedule_c", "number": "SC-0001", "valid_from": "2026-01-01", "valid_to": valid_to,
         "categories": ["test_raw_resin"]}
    ]
    return r, c


def test_row09_positive():
    _check(answer(*_schedule_c()), D.REQUEST_CORRECTED_INVOICE, T.SST_SHOULD_BE_EXEMPT, "TAX_SHOULD_BE_EXEMPT")


def test_row09_negative_certificate_expired():
    _check(answer(*_schedule_c(valid_to="2026-06-30")), D.APPROVE, T.SST_CORRECT)


def test_row09_negative_buyer_not_a_registered_manufacturer():
    r, c = _schedule_c()
    r["company"]["is_registered_manufacturer"] = False
    _check(answer(r, c), D.APPROVE, T.SST_CORRECT)


# Row 10: MY service tax charged by a supplier with no SST registration -> SST_SUPPLIER_NOT_REGISTERED


def test_row10_positive():
    r, c = my_base()
    r["suppliers"][0].update(sst_registration_no=None, sst_type="none")
    c["invoice"]["supplier_sst_no"] = None
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.SST_SUPPLIER_NOT_REGISTERED, "SUPPLIER_NOT_TAX_REGISTERED")


def test_row10_negative_unregistered_supplier_charges_nothing():
    r, c = _my_with("it_services", "6150-100", rate="0")
    r["suppliers"][0].update(sst_registration_no=None, sst_type="none")
    _check(answer(r, c), D.APPROVE, T.NO_SST)


# Row 11: MY correct rate, registered supplier -> SST_CORRECT, APPROVE (if nothing else is wrong)


def test_row11_positive():
    _check(answer(*my_base()), D.APPROVE, T.SST_CORRECT, "MATCHED_WITHIN_TOLERANCE")


def test_row11_negative_something_else_wrong():
    r, c = my_base()
    set_lines(c, [my_line(1, "it_services", 1, "3400.00", po_line_no=1)])
    _check(answer(r, c), D.DISPUTE_PRICE, T.SST_CORRECT, "PRICE_ABOVE_PO")


# Row 12: MY e-invoice missing a mandatory field -> tax unchanged, REQUEST_CORRECTED_INVOICE


def test_row12_positive_buyer_tin():
    r, c = my_base()
    c["invoice"]["buyer_tin"] = None
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.SST_CORRECT, "MISSING_MANDATORY_FIELD")


def test_row12_positive_line_tax_type():
    r, c = my_base()
    c["invoice"]["lines"][0]["tax_type"] = None
    _check(answer(r, c), D.REQUEST_CORRECTED_INVOICE, T.SST_CORRECT, "MISSING_MANDATORY_FIELD")


def test_row12_negative_ordinary_invoice_below_threshold():
    r, c = my_base()
    c["invoice"].update(is_einvoice=False, buyer_tin=None)
    _check(answer(r, c), D.APPROVE, T.SST_CORRECT)


# Row 13: facts not enough to tell (e.g. Regulation 25(1) vehicle) -> HAND_OVER by construction


def test_row13_positive_vehicle_unclear():
    a = answer(*_sg_with("motor_car_running", "6610-000"))
    assert a.decision is D.HAND_OVER
    assert a.answer_source.value == "handover_by_construction"
    assert a.tax_treatment is None and a.gl_account == "6610-000"
    assert a.reason_codes == ["CANNOT_SETTLE_FROM_RULES"]


def test_row13_negative_vehicle_stated():
    a = answer(*_sg_with("motor_car_running", "6610-000", vehicle_is_motor_car=True))
    _check(a, D.APPROVE, T.NOT_CLAIMABLE_DISALLOWED)
