"""Malaysian service tax core: MS-1 to MS-4 and MS-9 (rule sheet v0.10 section 1; A12 build PR 2 commit 6)."""

import pytest

from decision_benchmark.task_sets.ap_invoices.countries.my.rules.rates import standard_rate
from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import CATALOG, answer
from .my_cases import one_line, result, supplier_facts

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER


# -- MS-1: is service tax due at all? -------------------------------------------------------------


def test_ms1_unregistered_supplier_charging_service_tax():
    r, c = one_line(supplier=())
    assert result(r, c) == (RCI, "SST_SUPPLIER_NOT_REGISTERED", "MS-1")


def test_ms1_service_tax_on_a_line_outside_the_first_schedule():
    r, c = one_line("office_supplies", rate="8", tax_type="02")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")


def test_ms1_new_scope_item_before_it_became_taxable():
    # Group K (rental) is a taxable service from 1 Jul 2025 only.
    r, c = one_line(rate="8", day="2025-06-20", service_item="K", asset_type="machinery")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")


def test_ms1_near_miss_new_scope_item_after_it_became_taxable():
    r, c = one_line(rate="8", day="2025-07-02", service_item="K", asset_type="machinery")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms1_near_miss_no_tax_outside_the_first_schedule():
    r, c = one_line("office_supplies", rate="0")
    assert result(r, c) == (OK, "NO_SST", "MS-1")


def test_ms1_unknown_registration_is_a_hand_over():
    r, c = one_line(supplier=())
    supplier_facts(r, registration_known=False)
    assert result(r, c) == (HO, None, "MS-1")


# -- MS-2: rate ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("category, item, rate, facts", [
    ("it_services", None, "6", {}),
    ("logistics_haulage", None, "8", {}),
    ("it_services", "I4", "8", {}),                                     # parking: 6%
    ("it_services", "B", "6", {"fb_content": "alcohol_alone"}),         # alcohol sold alone: 8%
    ("it_services", "C", "6", {"package_single_price": True}),          # Group C package: the group's 8%
    ("it_services", "A", "8", {"fb_content": "food"}),                  # food at a hotel: 6%
])
def test_ms2_wrong_rate(category, item, rate, facts):
    if item:
        facts["service_item"] = item
    r, c = one_line(category, rate=rate, **facts)
    a = answer(r, c)
    assert (a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis) == (RCI, "SST_WRONG_RATE", "MS-2")
    assert "WRONG_TAX_RATE" in a.reason_codes


@pytest.mark.parametrize("category, item, rate, facts", [
    ("it_services", None, "8", {}),
    ("logistics_haulage", None, "6", {}),
    ("it_services", "I4", "6", {}),
    ("it_services", "B", "8", {"fb_content": "alcohol_alone"}),
    ("it_services", "B", "6", {"fb_content": "food_with_alcohol"}),     # Rate Order First Schedule item 4
    ("it_services", "C", "8", {"package_single_price": True}),
    ("it_services", "B", "6", {"package_single_price": True}),          # Group B package: 6%
    ("it_services", "K", "6", {"asset_type": "machinery"}),             # rental 6% from 1 Jan 2026
])
def test_ms2_near_miss_right_rate(category, item, rate, facts):
    if item:
        facts["service_item"] = item
    r, c = one_line(category, rate=rate, **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms2_card_activation_is_rm25_per_card():
    r, c = one_line(rate="0.78125", price="3200.00", service_item="H1", financial_charge="card_activation")
    # 3200.00 x 0.78125% = 25.00: one card.
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")
    r, c = one_line(rate="8", service_item="H1", financial_charge="card_activation")
    assert result(r, c) == (RCI, "SST_WRONG_RATE", "MS-2")


def test_ms2_the_catalog_classes_agree_with_the_rate_order():
    for cat in CATALOG.categories:
        p = cat.tax.get("MY")
        if p is not None and p.tax_class.startswith("service_"):
            import datetime as dt

            assert str(standard_rate(p.service_item, dt.date(2026, 11, 2))) == p.tax_class.removeprefix("service_"), cat


# -- MS-3: rate changes over time ----------------------------------------------------------------


RENTAL = {"service_item": "K", "asset_type": "machinery"}
SPANNING = RENTAL | {"service_period_start": "2025-12-01", "service_period_end": "2026-01-31"}


def test_ms3_period_before_the_change_keeps_the_old_rate():
    # Rental for Dec 2025 invoiced in Jan 2026: the whole period is on the 8% side.
    facts = RENTAL | {"service_period_start": "2025-12-01", "service_period_end": "2025-12-31"}
    r, c = one_line(rate="8", day="2026-01-10", **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-3")
    r, c = one_line(rate="6", day="2026-01-10", **facts)
    assert result(r, c) == (RCI, "SST_WRONG_RATE", "MS-3")


def test_ms3_spanning_period_without_a_split_is_a_hand_over():
    facts = RENTAL | {"service_period_start": "2025-12-01", "service_period_end": "2026-01-31"}
    r, c = one_line(rate="6", day="2026-02-02", **facts)
    assert result(r, c) == (HO, None, "MS-3")


def test_ms3_spanning_period_with_the_split_shown_checks_each_part():
    # 3200.00 for Dec 2025-Jan 2026: 1200.00 provided before 1 Jan 2026 at 8% (96.00), 2000.00 at 6% (120.00) = 6.75%.
    facts = SPANNING | {"value_provided_before_change": "1200.00"}
    r, c = one_line(rate="6.75", day="2026-02-02", **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-3")
    r, c = one_line(rate="6", day="2026-02-02", **facts)
    assert result(r, c) == (RCI, "SST_WRONG_RATE", "MS-3")


def test_ms3_payment_before_the_change_keeps_the_old_rate():
    # Paid in full before 1 Jan 2026: all at 8%.
    r, c = one_line(rate="8", day="2026-02-02", **(SPANNING | {"amount_paid_before_change": "3200.00"}))
    assert result(r, c) == (OK, "SST_CORRECT", "MS-3")
    # 1200.00 paid before; 2000.00 provided before (1200.00 of it already paid): 2000.00 at 8% (160.00),
    # 1200.00 at 6% (72.00) = 232.00 = 7.25%.
    facts = SPANNING | {"amount_paid_before_change": "1200.00", "value_provided_before_change": "2000.00"}
    r, c = one_line(rate="7.25", day="2026-02-02", **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-3")


def test_ms3_payment_alone_is_not_the_split_of_the_rest():
    # Review of PR #14, C: the payment amount is not a split of what was provided; the rest needs the provision split.
    r, c = one_line(rate="6.75", day="2026-02-02", **(SPANNING | {"amount_paid_before_change": "1200.00"}))
    assert result(r, c) == (HO, None, "MS-3")


def test_ms3_near_miss_period_after_the_change_takes_the_new_rate():
    facts = RENTAL | {"service_period_start": "2026-01-01", "service_period_end": "2026-01-31"}
    r, c = one_line(rate="6", day="2026-02-02", **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms3_the_2024_general_rate_change():
    # IT services for Feb 2024 (6% then) invoiced in March 2024 (8% from 1 Mar 2024).
    r, c = one_line(rate="6", day="2024-03-05", service_period_start="2024-02-01", service_period_end="2024-02-29")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-3")
    r, c = one_line(rate="6", day="2024-02-20")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


def test_ms3_unknown_period_end_is_a_hand_over():
    r, c = one_line(rate="8", service_period_start="2026-10-01", service_period_end=None)
    assert result(r, c) == (HO, None, "MS-3")


# -- MS-4: item scope and exclusions --------------------------------------------------------------


EXCLUSIONS = [
    ("legal_services", None, {"subject_outside_malaysia": True}, {"subject_outside_malaysia": False}),
    ("it_services", "G(g)", {"oku_holder": True}, {"oku_holder": False}),
    ("management_services", None, {"excluded_management_kind": "strata_management_to_owners"},
     {"excluded_management_kind": "none"}),
    ("recruitment_services", None, {"staff_secondment": True}, {"staff_secondment": False}),
    ("guard_services", None, {"subject_outside_malaysia": True}, {"subject_outside_malaysia": False}),
    ("maintenance_repair", None, {"residential": True}, {"residential": False}),
    ("it_services", "H3", {"financial_charge": "interest_or_profit"}, {"financial_charge": "fee_or_commission"}),
    ("it_services", "H2", {"insurance_cover": "export_credit"}, {"insurance_cover": "other"}),
    ("it_services", "H3", {"export_related": True}, {"export_related": False}),
    ("advertising", None, {"subject_outside_malaysia": True}, {"subject_outside_malaysia": False}),
    ("it_services", "I10", {"air_route": "international"}, {"air_route": "peninsula_east_malaysia"}),
    ("it_services", "I10", {"air_route": "within_sabah"}, {"air_route": "between_sabah_sarawak"}),
    ("it_services", "I13", {"premises_use": "residential"}, {"premises_use": "industrial"}),
    ("logistics_haulage", None, {"carriage": "transshipment"}, {"carriage": "domestic"}),
    ("it_services", "K", {"asset_type": "housing"}, {"asset_type": "machinery"}),
    ("it_services", "K", {"financial_lease": True}, {"financial_lease": False}),
    ("construction_works", None, {"residential": True}, {"residential": False}),
]
"""(category, item fact, excluded facts, ordinary facts)."""


def _rate(category, item):
    import datetime as dt

    p = CATALOG.get(category).tax["MY"]
    return str(standard_rate(item or p.service_item, dt.date(2026, 11, 2)))


@pytest.mark.parametrize("category, item, excluded, ordinary", EXCLUSIONS)
def test_ms4_exclusion_charged_should_be_exempt(category, item, excluded, ordinary):
    facts = excluded | ({"service_item": item} if item else {})
    r, c = one_line(category, rate=_rate(category, item), **facts)
    a = answer(r, c)
    assert (a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-4")
    assert "TAX_SHOULD_BE_EXEMPT" in a.reason_codes


@pytest.mark.parametrize("category, item, excluded, ordinary", EXCLUSIONS)
def test_ms4_near_miss_ordinary_fact_is_taxable(category, item, excluded, ordinary):
    facts = ordinary | ({"service_item": item} if item else {})
    r, c = one_line(category, rate=_rate(category, item), **facts)
    assert result(r, c) == (OK, "SST_CORRECT", "MS-2")


@pytest.mark.parametrize("category, item, excluded, ordinary", EXCLUSIONS[:4])
def test_ms4_excluded_line_without_tax_is_no_sst(category, item, excluded, ordinary):
    facts = excluded | ({"service_item": item} if item else {})
    r, c = one_line(category, rate="0", **facts)
    assert result(r, c) == (OK, "NO_SST", "MS-4")


def test_ms4_excluded_supplier_kind_for_consultancy():
    r, c = one_line(rate="8", service_item="G(g)")
    supplier_facts(r, supplier_kind="research_institute")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-4")


def test_ms4_statutory_fee_part_is_excluded():
    # 3200.00 of which 1200.00 is a statutory fee: tax on 2000.00 at 8% = 160.00 (5%).
    r, c = one_line("legal_services", rate="5", statutory_fee_amount="1200.00")
    assert result(r, c) == (OK, "SST_CORRECT", "MS-4")
    r, c = one_line("legal_services", rate="8", statutory_fee_amount="1200.00")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-4")


@pytest.mark.parametrize("facts, expected", [
    ({"patient_citizen": True}, ("SST_SHOULD_BE_EXEMPT", RCI)),
    ({"patient_citizen": False}, ("SST_CORRECT", OK)),
    ({"patient_category": "citizen"}, ("SST_SHOULD_BE_EXEMPT", RCI)),
    ({"patient_category": "non_citizen"}, ("SST_CORRECT", OK)),
])
def test_ms4_healthcare_patient_citizenship(facts, expected):
    r, c = one_line(rate="6", service_item="I14", **facts)
    decision, treatment, _ = result(r, c)
    assert (treatment, decision) == expected


def test_ms4_healthcare_without_the_patient_shown_is_a_hand_over():
    r, c = one_line(rate="6", service_item="I14")
    assert result(r, c) == (HO, None, "MS-4")


@pytest.mark.parametrize("facts, expected", [
    ({"student_category": "citizen"}, "SST_SHOULD_BE_EXEMPT"),
    ({"student_category": "disabled_citizen"}, "SST_SHOULD_BE_EXEMPT"),
    ({"student_category": "non_citizen"}, "SST_CORRECT"),
    ({"student_citizen": True}, "SST_SHOULD_BE_EXEMPT"),
    ({"annual_fee_per_student": "50000.00"}, "SST_SHOULD_BE_EXEMPT"),
    ({"annual_fee_per_student": "70000.00"}, "SST_CORRECT"),
])
def test_ms4_education(facts, expected):
    r, c = one_line(rate="6", service_item="M", **facts)
    assert result(r, c)[1] == expected


def test_ms4_unknown_exclusion_fact_is_a_hand_over():
    r, c = one_line("legal_services", rate="8", subject_outside_malaysia=None)
    assert result(r, c) == (HO, None, "MS-4")


# -- MS-9: tax not charged when it should have been -------------------------------------------------


def test_ms9_registered_supplier_leaves_service_tax_off():
    r, c = one_line(rate="0")
    a = answer(r, c)
    assert (a.decision, a.tax_lines[0].treatment, a.tax_lines[0].basis) == (RCI, "SST_UNDERCHARGED", "MS-9")
    assert a.reason_codes == ["TAX_UNDERCHARGED"]


def test_ms9_near_miss_unregistered_supplier_charges_nothing():
    r, c = one_line(rate="0", supplier=())
    assert result(r, c) == (OK, "NO_SST", "MS-1")


def test_ms9_near_miss_excluded_line_charges_nothing():
    r, c = one_line("legal_services", rate="0", subject_outside_malaysia=True)
    assert result(r, c) == (OK, "NO_SST", "MS-4")
