"""Malaysian sales tax: MG-1 to MG-6, G-1, G-3 to G-5, and guards for G-2, G-6, G-7 (A12 build PR 2 commit 11)."""

import importlib.util
from pathlib import Path

import pytest

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .my_cases import company_facts, one_line, result, supplier_facts

RCI, OK, HO = D.REQUEST_CORRECTED_INVOICE, D.APPROVE, D.HAND_OVER
MOTORCYCLE, FEED, SOYA = "8711.20.96 00", "2301.20.10 00", "1201.10.00 00"


def goods(category="test_raw_resin", rate="10", **kw):
    return one_line(category, rate=rate, price="12.40", qty=100, **kw)


def certificate(r, kind, **over):
    cert = {"kind": kind, "number": f"{kind}-1", "valid_from": "2026-01-01", "categories": ["test_raw_resin"]} | over
    r["company"]["policy_pack"].setdefault("exemption_certificates", []).append(cert)


# -- MG-1: who may charge sales tax ---------------------------------------------------------------


def test_mg1_manufacturer_reselling_bought_in_goods():
    r, c = goods(manufactured_by_supplier=False)
    a = result(r, c)
    assert a == (RCI, "SST_NOT_CHARGEABLE_BY_TRADER", "MG-1")


def test_mg1_unregistered_supplier_charging_sales_tax():
    r, c = goods(supplier=("service",))
    assert result(r, c) == (RCI, "SST_SUPPLIER_NOT_REGISTERED", "MG-1")


def test_mg1_near_miss_registered_manufacturer_selling_its_own_goods():
    assert result(*goods(manufactured_by_supplier=True)) == (OK, "SST_CORRECT", "MG-2")


def test_mg1_near_miss_trader_charges_nothing():
    r, c = goods(rate="0")
    supplier_facts(r, is_manufacturer=False)
    assert result(r, c) == (OK, "NO_SST", "MG-1")


def test_mg1_unknown_supplier_type_with_tax_charged_is_a_hand_over():
    assert result(*goods(manufactured_by_supplier=None)) == (HO, None, "MG-1")


def test_mg1_imported_goods_bear_sales_tax_at_import():
    r, c = goods(rate="0")
    r["suppliers"][0]["country"] = "CN"
    assert result(r, c) == (OK, "NO_SST", "MG-1")
    r, c = goods(supplier=())
    r["suppliers"][0]["country"] = "CN"
    assert result(r, c) == (RCI, "SST_SUPPLIER_NOT_REGISTERED", "MG-1")


def test_ms9_manufacturer_leaves_sales_tax_off_its_goods():
    assert result(*goods(rate="0")) == (RCI, "SST_UNDERCHARGED", "MS-9")


def test_service_tax_on_goods_is_not_a_taxable_service():
    assert result(*goods(rate="8", tax_type="02")) == (RCI, "SST_SHOULD_BE_EXEMPT", "MS-1")
    assert result(*goods(rate="6", tax_type="02", materials_works_separated=True)) == (RCI, "SST_SHOULD_BE_EXEMPT", "L-8")


# -- MG-2: rate by tariff code ---------------------------------------------------------------------


def test_mg2_wrong_rate_and_exempt_goods():
    assert result(*goods(rate="5")) == (RCI, "SST_WRONG_RATE", "MG-2")
    assert result(*goods("test_finished_goods", rate="10")) == (RCI, "SST_WRONG_RATE", "MG-2")
    assert result(*goods("test_exempt_goods", rate="10")) == (RCI, "SST_SHOULD_BE_EXEMPT", "MG-2")


def test_mg2_near_miss_right_rate():
    assert result(*goods("test_finished_goods", rate="5")) == (OK, "SST_CORRECT", "MG-2")
    assert result(*goods("test_exempt_goods", rate="0")) == (OK, "NO_SST", "MG-2")


# -- MG-3, G-1: rate transitions and motorcycles ------------------------------------------------------


def test_mg3_policy_code_invoiced_before_the_policy_date_takes_the_category_rate():
    # The fixture category is 10% before 1 Jul 2025 too. The release motorcycle category was exempt then
    # (Goods Exempted Orders 2018 and 2022): test_goods_before_2025.
    assert result(*goods(day="2025-06-25", tariff_code=MOTORCYCLE)) == (OK, "SST_CORRECT", "MG-3")


def test_g1_motorcycles_exempt_from_july_2025():
    assert result(*goods(day="2025-07-02", tariff_code=MOTORCYCLE)) == (RCI, "SST_SHOULD_BE_EXEMPT", "G-1")


def test_g1_near_miss_other_motorcycle_code():
    assert result(*goods(tariff_code="8711.20.10 00")) == (OK, "SST_CORRECT", "MG-2")


# -- MG-4, G-4: certificates and pallets ----------------------------------------------------------------


@pytest.mark.parametrize("kind", ["schedule_a", "schedule_b", "schedule_c"])
def test_mg4_buyer_holds_a_certificate_for_the_goods(kind):
    r, c = goods()
    certificate(r, kind)
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MG-4")


@pytest.mark.parametrize("over", [{"valid_to": "2026-06-30"}, {"categories": ["test_finished_goods"]}])
def test_mg4_near_miss_certificate_expired_or_other_goods(over):
    r, c = goods()
    certificate(r, "schedule_a", **over)
    assert result(r, c) == (OK, "SST_CORRECT", "MG-2")


def test_g4_one_way_pallets_are_schedule_c_packaging():
    r, c = goods(pallet_returnable=False)
    certificate(r, "schedule_c")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "G-4")


def test_g4_near_miss_returnable_pallets_are_taxable():
    r, c = goods(pallet_returnable=True)
    certificate(r, "schedule_c")
    assert result(r, c) == (OK, "SST_CORRECT", "G-4")


def test_g4_unknown_returnable_is_a_hand_over():
    r, c = goods(pallet_returnable=None)
    certificate(r, "schedule_c")
    assert result(r, c) == (HO, None, "G-4")


# -- MG-5: designated areas -------------------------------------------------------------------------


def test_mg5_goods_within_a_designated_area():
    r, c = goods()
    company_facts(r, zone="langkawi")
    supplier_facts(r, zone="langkawi")
    assert result(r, c) == (RCI, "SST_SHOULD_BE_EXEMPT", "MG-5")


def test_mg5_near_miss_principal_customs_area():
    assert result(*goods()) == (OK, "SST_CORRECT", "MG-2")


def test_mg5_unknown_zone_status_is_a_hand_over():
    r, c = goods()
    company_facts(r, zone="labuan", zone_known=False)
    assert result(r, c) == (HO, None, "MG-5")


# -- MG-6: G-3, G-5 ----------------------------------------------------------------------------------------


def test_g3_feed_raw_materials_are_taxed_on_the_invoice_refund_route():
    # Decision 1: the refund is an optional later claim, so the line is SST_CORRECT with no buyer action.
    r, c = goods(day="2026-02-01", tariff_code=FEED)
    a = result(r, c)
    assert a == (OK, "SST_CORRECT", "G-3")


def test_g3_near_miss_before_january_2026():
    assert result(*goods(day="2025-12-10", tariff_code=FEED)) == (OK, "SST_CORRECT", "MG-3")


# G-3 ends on 31 Aug 2026: from 1 Sep 2026 P.U. (A) 303/2026 Schedule B items 5-7 cover these buyers (MG-4).
ITEMS_5_7 = {"valid_from": "2026-09-01"}   # a Schedule B certificate under the new items starts on 1 Sep 2026


@pytest.mark.parametrize("day, with_certificate, expected", [
    ("2026-08-31", False, (OK, "SST_CORRECT", "G-3")),
    ("2026-08-31", True, (OK, "SST_CORRECT", "G-3")),          # the certificate is not valid yet
    ("2026-09-01", False, (OK, "SST_CORRECT", "MG-2")),
    ("2026-09-01", True, (RCI, "SST_SHOULD_BE_EXEMPT", "MG-4")),
])
def test_g3_ends_on_31_august_2026_then_mg4_schedule_b(day, with_certificate, expected):
    r, c = goods(day=day, tariff_code=FEED)
    if with_certificate:
        certificate(r, "schedule_b", **ITEMS_5_7)
    assert result(r, c) == expected


def test_mg4_schedule_b_items_5_7_buyer_invoiced_without_tax():
    r, c = goods(rate="0", day="2026-09-01", tariff_code=FEED)
    certificate(r, "schedule_b", **ITEMS_5_7)
    assert result(r, c) == (OK, "NO_SST", "MG-4")


def test_g5_drop_shipment_export_is_invoiced_without_sales_tax():
    assert result(*goods(drop_shipment_export=True)) == (RCI, "SST_SHOULD_BE_EXEMPT", "G-5")
    assert result(*goods(rate="0", drop_shipment_export=True)) == (OK, "NO_SST", "G-5")


def test_g5_near_miss_not_a_drop_shipment():
    assert result(*goods(drop_shipment_export=False)) == (OK, "SST_CORRECT", "MG-2")


def test_mg6_a_policy_exemption_by_tariff_code():
    assert result(*goods(tariff_code="8711.20.99 00")) == (RCI, "SST_SHOULD_BE_EXEMPT", "G-1")


def test_mg6_near_miss_a_code_in_no_policy():
    assert result(*goods(tariff_code="3901.10.10 00")) == (OK, "SST_CORRECT", "MG-2")


# -- Guards: G-2, G-6, G-7 are not engine rules ----------------------------------------------------------


def test_g2_guard_soya_beans_on_a_supplier_invoice_are_ordinary_goods():
    assert result(*goods(tariff_code=SOYA)) == (OK, "SST_CORRECT", "MG-2")


def test_g7_guard_machinery_in_a_refund_only_window_is_taxed_as_usual():
    assert result(*goods(day="2025-08-15")) == (OK, "SST_CORRECT", "MG-2")


def test_g6_guard_no_answer_key_names_a_not_engine_rule():
    spec = importlib.util.spec_from_file_location("keys_collect", Path(__file__).resolve().parents[1] / "keys/collect.py")
    collect = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collect)
    golden = collect.read_golden(collect.engine_version()) or []
    bases = {t["basis"] for row in golden for t in row["key"]["tax_lines"]}
    assert not bases & {"G-2", "G-6", "G-7", "P-21"}
