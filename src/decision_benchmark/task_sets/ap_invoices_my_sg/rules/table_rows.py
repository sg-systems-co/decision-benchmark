"""Which tests cover each row of the rule-sheet table (step-11 plan §5.4).

Keys are the first cell of each row of "From rules to benchmark checks" in
docs/task-sets/ap-invoices-my-sg/tax-rules-v0.9.md, exactly as written there.
tests/rules/test_table_coverage.py fails if a row is added, changed or left
without a positive and a near-miss test in tests/rules/test_table_rows.py.
"""

from __future__ import annotations

ROWS: dict[str, dict[str, list[str]]] = {
    "SG: valid tax invoice, registered supplier, business expense": {
        "positive": ["test_row01_positive"],
        "negative": ["test_row01_negative_supplier_deregistered_before_invoice"],
    },
    'SG: invoice above S$1,000 without the customer\'s name or the words "Tax Invoice"': {
        "positive": ["test_row02_positive_no_customer_name", "test_row02_positive_no_tax_invoice_wording"],
        "negative": ["test_row02_negative_at_or_below_threshold_simplified_invoice_ok"],
    },
    "SG: foreign-currency invoice without Singapore dollar amounts": {
        "positive": ["test_row03_positive"],
        "negative": ["test_row03_negative_sgd_amounts_shown"],
    },
    "SG: supplier's GST number invalid or missing, GST charged": {
        "positive": ["test_row04_positive_supplier_not_registered", "test_row04_positive_number_does_not_match_record"],
        "negative": [
            "test_row04_negative_registered_supplier_omits_number_is_invalid_invoice",
            "test_row04_negative_unregistered_supplier_charges_no_gst",
        ],
    },
    "SG: OVR-registered overseas vendor charges GST to the registered buyer": {
        "positive": ["test_row05_positive"],
        "negative": ["test_row05_negative_ovr_vendor_charges_no_gst"],
    },
    "SG: club subscription, staff medical, motor car running costs, family benefit": {
        "positive": ["test_row06_positive_each_class"],
        "negative": ["test_row06_negative_obligatory_staff_medical_is_claimable"],
    },
    "MY: service tax at 8% on logistics, F&B, telecoms or parking": {
        "positive": ["test_row07_positive"],
        "negative": ["test_row07_negative_six_percent_is_correct"],
    },
    "MY: service tax on a Group G service between two registered persons providing the same service": {
        "positive": ["test_row08_positive"],
        "negative": [
            "test_row08_negative_buyer_does_not_provide_the_service",
            "test_row08_negative_guard_services_are_excluded",
            "test_row08_negative_buyer_not_registered",
        ],
    },
    "MY: sales tax on raw materials bought by a registered manufacturer under Schedule C": {
        "positive": ["test_row09_positive"],
        "negative": ["test_row09_negative_certificate_expired", "test_row09_negative_buyer_not_a_registered_manufacturer"],
    },
    "MY: service tax charged by a supplier with no SST registration": {
        "positive": ["test_row10_positive"],
        "negative": ["test_row10_negative_unregistered_supplier_charges_nothing"],
    },
    "MY: correct rate, registered supplier": {
        "positive": ["test_row11_positive"],
        "negative": ["test_row11_negative_something_else_wrong"],
    },
    "MY: e-invoice missing a mandatory field, e.g. buyer TIN or a line's tax type": {
        "positive": ["test_row12_positive_buyer_tin", "test_row12_positive_line_tax_type"],
        "negative": ["test_row12_negative_ordinary_invoice_below_threshold"],
    },
    "Facts not enough to tell, e.g. whether a car falls under the Regulation 25(1) exclusions": {
        "positive": ["test_row13_positive_vehicle_unclear"],
        "negative": ["test_row13_negative_vehicle_stated"],
    },
}
