# Answer-key changes by engine version

Every golden key file `keys-<version>.yaml` holds the answer keys the rules and core tests write under that engine version (`tests/keys/collect.py`). `tests/keys/test_golden_keys.py` fails when a key changes without a version bump. Each version below lists what changed against the one before, by rule ID.

## 0.9.0a1

Baseline before A12: the v0.9 engine. 124 keys written in 118 tests (8 further engine calls end in `UnsupportedCase` by design and write no key).

## 0.10.0.dev1

A12 build PR 1, commit 4: per-line results, line GL, versions in keys. 129 keys.

- **All 124 keys of 0.9.0a1:** every v0.9 field (decision, tax treatment, GL account, reason codes, answer source, findings, grader truth) is unchanged. Added fields only:
  - `tax_lines`: one entry per invoice line with `treatment`, `basis` and `gl_account`. The case-level treatment equals the worst line by the pack's severity order in every key. Bases name the closest v0.10 rule for the v0.9 logic (MS-1, MS-2, MS-5, MS-6, MG-1, MG-2, MG-4; SG-1, SG-2, SG-4, SG-10, SG-12); A12 build PRs 2 and 3 replace them rule by rule.
  - `buyer_actions`: empty in every key (no v0.9 rule gives one).
  - `facts`: the line facts the engine read that the line records (11 keys).
  - `engine_version` `0.10.0.dev1`, `rules_version` `v0.9` (the rules applied are still those of sheet v0.9; it becomes `v0.10` with engine 0.10.0).
- **New keys (spec v0.10 clarification, GL per line):** `test_lines_booking_to_two_gl_accounts_each_keep_their_account` (formerly `UnsupportedCase`: lines booking to two GL accounts now each keep their account; the case-level account is the line with the largest amount excluding tax) and `test_case_gl_account_ties_go_to_the_lowest_line`.
- **New keys from new tests (no rule change):** `test_gold_facts_are_the_facts_read`, `test_hand_over_line_is_null_with_its_basis`, `test_versions_in_keys` (tests/rules/test_registry.py).

## 0.10.0.dev2

A12 build PR 2 (Malaysia). One version for the whole PR: its golden file is rewritten at each commit of the PR, and this section lists every change against 0.10.0.dev1 by commit and rule ID. No 0.10.0.dev2 key reaches main before the PR is merged.

- **Commit 6 (MS-1 to MS-4, MS-9).** All 129 keys of 0.10.0.dev1: unchanged apart from `engine_version`. 87 new keys from the new tests in `tests/rules/test_my_service_tax.py`.
- **Commit 7 (MS-5 to MS-8).** No existing key changes. 43 new keys from `tests/rules/test_my_exemptions.py`. Buyer actions are now listed once per case (the schema's `uniqueItems`).
- **Commit 8 (K-1 to K-8).** No existing key changes. New keys from `tests/rules/test_my_rental.py`.
- **Commit 9 (L-1 to L-4, L-6 to L-8).** No existing key changes. New keys from `tests/rules/test_my_construction.py`.
- **Commit 10 (MS-10, P-1 to P-14, P-16 to P-20; P-21 guard).** No existing key changes. New keys from `tests/rules/test_my_policies.py`.
