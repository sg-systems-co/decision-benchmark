"""Which tests cover each rule of docs/tax-rules-v0.10.md (A12 plan §12).

tests/rules/test_rule_coverage.py checks that every rule ID in the sheet, and each of the two
mixed-invoice rules of §5, is in exactly one place:

- RULE_TESTS: at least one positive and one near-miss test, as "module::function" under tests/rules;
- NOT_ENGINE: not an engine rule (the reason), with at least one guard test in NOT_ENGINE_GUARDS
  asserting it has no effect on the invoice;
- PENDING: not built yet. Emptied rule by rule in A12 build PRs 2-4; it must be empty at engine 0.10.0.
"""

from __future__ import annotations

SECTION_5 = ("§5-a", "§5-b")
"""§5-a: each line on its own, decision by the most severe line; §5-b: the split as the deciding fact."""

M = "test_my_service_tax::"
X = "test_my_exemptions::"
B = "test_b2b_and_insurance::"
K = "test_my_rental::"
C = "test_my_construction::"
RULE_TESTS: dict[str, dict[str, list[str]]] = {
    # A12 build PR 2: Malaysia.
    "MS-1": {"positive": [M + "test_ms1_unregistered_supplier_charging_service_tax",
                          M + "test_ms1_service_tax_on_a_line_outside_the_first_schedule",
                          M + "test_ms1_new_scope_item_before_it_became_taxable"],
             "near_miss": [M + "test_ms1_near_miss_new_scope_item_after_it_became_taxable",
                           M + "test_ms1_near_miss_no_tax_outside_the_first_schedule"]},
    "MS-2": {"positive": [M + "test_ms2_wrong_rate"], "near_miss": [M + "test_ms2_near_miss_right_rate"]},
    "MS-3": {"positive": [M + "test_ms3_period_before_the_change_keeps_the_old_rate",
                          M + "test_ms3_spanning_period_without_a_split_is_a_hand_over",
                          M + "test_ms3_spanning_period_with_the_split_shown_checks_each_part"],
             "near_miss": [M + "test_ms3_near_miss_period_after_the_change_takes_the_new_rate"]},
    "MS-4": {"positive": [M + "test_ms4_exclusion_charged_should_be_exempt"],
             "near_miss": [M + "test_ms4_near_miss_ordinary_fact_is_taxable"]},
    "MS-5": {"positive": [X + "test_ms5_rental_sublet_in_full_is_exempt",
                          X + "test_ms5_rental_sublet_in_part_exempts_the_sublet_part",
                          X + "test_ms5_construction_and_finance_items", B + "test_b2b_positive"],
             "near_miss": [X + "test_ms5_near_miss_condition_fails", B + "test_b2b_near_miss_personal_use",
                           B + "test_b2b_near_miss_buyer_provides_a_different_item"]},
    "MS-6": {"positive": [X + "test_ms6_group_company_supply_is_relieved",
                          X + "test_ms6_maintenance_is_relieved_from_1_may_2024"],
             "near_miss": [X + "test_ms6_near_miss_no_control_or_above_5pct",
                           X + "test_ms6_near_miss_item_outside_group_relief"]},
    "MS-7": {"positive": [X + "test_ms7_service_within_a_designated_area_is_not_taxed"],
             "near_miss": [X + "test_ms7_near_miss_principal_customs_area_and_jda"]},
    "MS-8": {"positive": [X + "test_ms8_buyer_accounts_for_imported_service_tax",
                          X + "test_ms8_foreign_registered_person"],
             "near_miss": [X + "test_ms8_exceptions_buyer_accounts_for_nothing",
                           X + "test_ms8_near_miss_excluded_service_is_not_imported_taxable"]},
    "K-1": {"positive": [K + "test_k1_sme_tenant_is_exempt", K + "test_k1_registration_by_end_2026_backdates", K + "test_k1_registration_after_2026_counts_from_its_date"],
            "near_miss": [K + "test_k1_near_miss_condition_fails"]},
    "K-2": {"positive": [K + "test_k2_new_sme_in_its_first_year_is_exempt"],
            "near_miss": [K + "test_k2_near_miss_after_its_first_year"]},
    "K-3": {"positive": [K + "test_k3_aircraft_and_vessels_are_exempt"],
            "near_miss": [K + "test_k3_near_miss_drones_and_floating_storage"]},
    "K-4": {"positive": [K + "test_k4_non_reviewable_contract_is_exempt_to_30_june_2026"],
            "near_miss": [K + "test_k4_near_miss_condition_fails"]},
    "K-5": {"positive": [K + "test_k5_government_lessor"],
            "near_miss": [K + "test_k5_near_miss_local_authority_after_september_2025"]},
    "K-6": {"positive": [K + "test_k6_rental_between_group_companies_is_exempt"],
            "near_miss": [K + "test_k6_near_miss_supplies_to_outsiders_above_5pct"]},
    "K-7": {"positive": [K + "test_k7_asset_outside_malaysia_is_not_taxable"],
            "near_miss": [K + "test_k7_near_miss_asset_in_malaysia"]},
    "K-8": {"positive": [K + "test_k8_invoice_in_one_co_owners_name_makes_it_the_supplier"],
            "near_miss": [K + "test_k8_near_miss_registered_co_owner"]},
    "L-1": {"positive": [C + "test_l1_non_reviewable_contract_is_exempt_to_june_2027", C + "test_l1_variation_order_qualifies_on_its_own_terms", C + "test_l1_work_after_the_end_needs_qualifying_extensions_of_time"],
            "near_miss": [C + "test_l1_near_miss_condition_fails"]},
    "L-2": {"positive": [C + "test_l2_residential_part_of_a_mixed_development_is_exempt", C + "test_l2_the_stated_contract_can_show_it"],
            "near_miss": [C + "test_l2_near_miss_contract_does_not_state_mixed_development"]},
    "L-3": {"positive": [C + "test_l3_consultant_to_a_main_contractor_on_design_and_build_is_exempt"],
            "near_miss": [C + "test_l3_near_miss_no_statement_or_not_a_main_contractor"]},
    "L-4": {"positive": [C + "test_l4_place_of_worship_is_exempt"],
            "near_miss": [C + "test_l4_near_miss_commercial_building"]},
    "L-6": {"positive": [C + "test_l6_facility_for_a_foreign_client_with_the_statement_is_exempt"],
            "near_miss": [C + "test_l6_near_miss_no_statement_on_the_invoice"]},
    "L-7": {"positive": [C + "test_l7_government_contractor"],
            "near_miss": [C + "test_l7_near_miss_local_authority_after_september_2025"]},
    "L-8": {"positive": [C + "test_l8_materials_not_separated_tax_the_whole_invoice", C + "test_l8_installation_not_separated_by_a_manufacturer_bears_sales_tax", C + "test_l8_ship_or_platform_follows_the_election"],
            "near_miss": [C + "test_l8_near_miss_installation_by_a_non_manufacturer_bears_service_tax"]},
    "MS-9": {"positive": [M + "test_ms9_registered_supplier_leaves_service_tax_off"],
             "near_miss": [M + "test_ms9_near_miss_unregistered_supplier_charges_nothing",
                           M + "test_ms9_near_miss_excluded_line_charges_nothing"]},
}

NOT_ENGINE: dict[str, str] = {
    "P-21": 'the sheet: "not a company purchase; recorded for completeness"',
    "G-2": "import-stage exemption of soya beans; customs and import permits are out of scope (spec v0.10, Scope)",
    "G-6": "re-import at customs; out of scope as G-2",
    "G-7": 'the sheet: "refund-only windows (no invoice effect)"',
}

NOT_ENGINE_GUARDS: dict[str, list[str]] = {}

PENDING: set[str] = {
    "MS-10", "L-5",
    *(f"P-{i}" for i in range(1, 22)), *(f"MG-{i}" for i in range(1, 7)), *(f"G-{i}" for i in range(1, 8)),
    *(f"ME-{i}" for i in range(1, 5)), *(f"SG-{i}" for i in range(1, 13)), *(f"WH-{i}" for i in range(1, 6)),
    *SECTION_5,
}
