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
- **Commit 11 (MG-1 to MG-6, G-1, G-3 to G-5; G-2, G-6, G-7 guards).** No existing key changes. New key: `test_sales_tax_by_registered_non_manufacturer_is_not_chargeable_by_a_trader` (formerly `UnsupportedCase`; MG-1: sales tax charged by a registered non-manufacturer is `SST_NOT_CHARGEABLE_BY_TRADER`). New keys from `tests/rules/test_my_sales_tax.py`.
- **Commit 12 (ME-1, ME-3, ME-4; ME-2 is the v0.9 check).** No existing key changes. New keys from `tests/rules/test_my_einvoice.py`. An open non-tax question (an unknown e-invoicing phase, ME-1 or ME-3) makes the case HAND_OVER with its tax treatment set.

Rules still pending after this PR (no line fact the rule needs; see the PR description): L-5, P-15. Rules not built in this PR by plan: SG-1 to SG-12, WH-1 to WH-5, §5 (PR 3).

Review of PR #14 (18 Nov 2026), pushed to the same PR under 0.10.0.dev2:

- **A. Group relief (MS-6, K-6): companies controlled by one company are a group (First Schedule paras 4-5).** Control counts through subsidiaries; sisters under a common parent company are relieved; an individual owner forms no group. No existing key changes. New keys: `test_ms6_sisters_under_a_common_parent_company_are_relieved`, `test_ms6_near_miss_sisters_under_a_common_individual_are_not_a_group`, `test_ms6_indirect_control_through_a_subsidiary_is_relieved` (2 keys), `test_ms6_near_miss_parent_controls_only_one_sister`, `test_ms6_unknown_board_control_on_the_common_parent_path_is_a_hand_over`.
- **B. B2B buyer (MS-5): a service-tax registration only.** The buyer must be a registered person under the Service Tax Act 2018; the same test now applies to s26 (MS-8), P-1 and the L-3 main contractor. Fixtures that meant a registered service provider but gave the buyer only a sales-tax registration now also give it a service-tax registration (`buyer_service_registered` in `tests/rules/factory.py`: `test_b2b_and_insurance.py`, row 8 of `test_table_rows.py`, `test_group_g_same_service_unclear_is_a_hand_over`, `test_hand_over_line_is_null_with_its_basis`, and `tests/rules/my_cases.py`). No existing key changes. New key: `test_ms5_near_miss_buyer_registered_for_sales_tax_only` (2 keys: sales-tax registration only, `SST_CORRECT` by MS-2; with a service-tax registration, `SST_SHOULD_BE_EXEMPT` by MS-5).
- **C. Rate change (MS-3): no split from the payment amount.** The amount paid before the change keeps the old rate; the rest is split by the value provided on each side where the documents show it (new line fact `value_provided_before_change`), else HAND_OVER with basis MS-3. Changed keys: `test_ms3_spanning_period_with_the_split_shown_checks_each_part` (2 keys; same treatments and basis MS-3, the gold facts now show `value_provided_before_change` 1200.00 in place of `amount_paid_before_change`, which alone no longer settles the split). New keys: `test_ms3_payment_before_the_change_keeps_the_old_rate` (2 keys), `test_ms3_payment_alone_is_not_the_split_of_the_rest` (HAND_OVER, MS-3).
- **New facts and rules (L-5, P-15, P-20, Group M).** L-5: work on a completed residential building (`completed_building`) is exempt with the recipient and residential address on the invoice, else taxed. P-15: health-examination management (`excluded_management_kind`) exempt before 1 May 2026, taxable from then. P-20: bank digital services to 31 Jul 2025 and non-bank digital payments 1 Aug 2022-31 Jul 2025 (`digital_payment_provider`). MS-4 Group M: by `education_provider_kind`, never from whether a fee is recorded; not shown is HAND_OVER. Changed keys (MS-4, P-16, P-17; same treatments and bases, the gold facts now include `education_provider_kind`): `test_ms4_education` cases 0-3, `test_p16_near_miss_tuition_for_a_non_citizen`, `test_p17_near_miss_centre_not_recognised`. `test_ms4_education` cases 4-5 (a recorded fee without the provider kind) are replaced by cases 4-7 with the provider kind; the fee-only case is now `test_ms4_education_without_provider_kind_or_fee_is_a_hand_over` (HAND_OVER, MS-4). New keys: `test_l5_*` (4), `test_p15_*` (2), `test_p20_digital_payment_*`, `test_p20_near_miss_outside_the_windows_*`, `test_p20_unknown_provider_kind_is_a_hand_over` (8), `test_ms4_education_without_provider_kind_or_fee_is_a_hand_over` (3).

Still pending after the review: SG-1 to SG-12, WH-1 to WH-5, §5 (PR 3). The line "Rules still pending after this PR" above (L-5, P-15) is superseded.

## 0.10.0.dev3

A12 build PR 3 (Singapore, withholding, mixed invoices). One version for the PR, as for 0.10.0.dev2: the golden file is rewritten at each commit and this section lists every change against 0.10.0.dev2 by commit and rule ID.

- **Commit 13 (SG-1 to SG-6, SG-11, SG-12).** All 486 keys of 0.10.0.dev2 unchanged apart from `engine_version`, except one:
  - `test_row05_negative_ovr_vendor_charges_no_gst` (SG-4): an OVR vendor charging a GST-registered buyer no GST stays `NO_GST`; its basis is now SG-4 (the vendor is not entitled to charge) in place of SG-12.
  - New key: `test_gst_rate_below_the_time_of_supply_rate_is_undercharged` (formerly `UnsupportedCase` "GST rate"; SG-3: 8% in 2026 is `GST_UNDERCHARGED`).
  - New keys from `tests/rules/test_sg_gst.py`.
- **Commit 14 (SG-7 to SG-10).** Changed key: `test_row05_negative_ovr_vendor_charges_no_gst` (SG-8): stays `NO_GST`; its basis is now SG-8 (an imported service to a fully taxable buyer, which does nothing; for a partially exempt buyer the same invoice is `REVERSE_CHARGE`), in place of SG-4 from commit 13 (SG-12 in 0.10.0.dev2). No other existing key changes. New keys from `tests/rules/test_sg_claims.py`.
- **Commit 15 (WH-1 to WH-5; treaty loaders).** No existing key changes. New keys from `tests/rules/test_withholding.py`. The Singapore treaty file is loaded as it stands (step 11d has not changed it): a rate counts as confirmed only with the status "single rate in the article" (62 articles); a case that needs another row with a certificate of residence is HAND_OVER.
- **Commit 16 (§5-a, §5-b).** No existing key changes. New key: `test_sg_mixed_claimable_and_disallowed_lines_are_approved` (formerly `UnsupportedCase`, plan Q4; §5-a: `APPROVE`, case `NOT_CLAIMABLE_DISALLOWED`, lines `CLAIMABLE` SG-1 and `NOT_CLAIMABLE_DISALLOWED` SG-10). New keys from `tests/rules/test_mixed_invoices.py`. `PENDING` in `tests/rules/rule_coverage.py` is now empty.

Against 0.10.0.dev2 after PR 3: one existing key changed, `test_row05_negative_ovr_vendor_charges_no_gst` (basis SG-12 -> SG-8, treatment `NO_GST` unchanged); every other key unchanged apart from `engine_version`.
