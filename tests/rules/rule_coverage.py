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

RULE_TESTS: dict[str, dict[str, list[str]]] = {}

NOT_ENGINE: dict[str, str] = {
    "P-21": 'the sheet: "not a company purchase; recorded for completeness"',
    "G-2": "import-stage exemption of soya beans; customs and import permits are out of scope (spec v0.10, Scope)",
    "G-6": "re-import at customs; out of scope as G-2",
    "G-7": 'the sheet: "refund-only windows (no invoice effect)"',
}

NOT_ENGINE_GUARDS: dict[str, list[str]] = {}

PENDING: set[str] = {
    *(f"MS-{i}" for i in range(1, 11)), *(f"K-{i}" for i in range(1, 9)), *(f"L-{i}" for i in range(1, 9)),
    *(f"P-{i}" for i in range(1, 22)), *(f"MG-{i}" for i in range(1, 7)), *(f"G-{i}" for i in range(1, 8)),
    *(f"ME-{i}" for i in range(1, 5)), *(f"SG-{i}" for i in range(1, 13)), *(f"WH-{i}" for i in range(1, 6)),
    *SECTION_5,
}
