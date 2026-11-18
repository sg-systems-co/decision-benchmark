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
    *(f"MS-{i}" for i in (5, 6, 7, 8, 10)), *(f"K-{i}" for i in range(1, 9)), *(f"L-{i}" for i in range(1, 9)),
    *(f"P-{i}" for i in range(1, 22)), *(f"MG-{i}" for i in range(1, 7)), *(f"G-{i}" for i in range(1, 8)),
    *(f"ME-{i}" for i in range(1, 5)), *(f"SG-{i}" for i in range(1, 13)), *(f"WH-{i}" for i in range(1, 6)),
    *SECTION_5,
}
