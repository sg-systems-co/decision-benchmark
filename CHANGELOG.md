# Changelog

All releases of the SG Systems Decision Benchmark. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning rules:

- Any change to a rule, the decision list, the tax-treatment codes, the scoring, or any answer key is a new spec version (for example v0.9 to v0.10). Scores are compared only within one spec version.
- Patch releases (for example v0.9.1) are for card or doc changes only. Data must be byte-identical.
- Clarifications without a version bump are allowed only while no scores exist for that version.

## [Unreleased]

Spec: v0.9 (synthetic, rules-based). Scores comparable with: v0.9.*

### Clarifications (no version bump; no scores exist yet)

Decided by Sebastian on 13 Nov 2026 (step-11 plan, §16). The spec and the tax-rule sheet files stay unchanged.

- **Singapore GST rate (rules).** The standard rate used by the answer keys is 9%, per the IRAS page on current GST rates (https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates). The tax-rule sheet does not state the rate.
- **"Invalid or missing" GST number (rules, tax-rule sheet table row 4).**
  - The supplier is not GST-registered on the invoice date, or the GST number printed on the invoice does not match the supplier record: `GST_WRONGLY_CHARGED`.
  - The supplier is GST-registered but leaves its GST number off the invoice: an invalid tax invoice, `NOT_CLAIMABLE_INVALID_INVOICE`, per the IRAS list of common reasons an invoice is invalid.
  - Both end as REQUEST_CORRECTED_INVOICE.
- **Invalid, missing or duplicate predictions (scoring).** A prediction that breaks the schema, a case with no prediction, a case predicted more than once, and an agent run that ends without a decision all get the worst cost: 10 under the main weights, 5 under 1 / 2 / 5, 20 under 1 / 3 / 20. They are not counted as critical errors. They count as decided (not handed over) for coverage, and as wrong for accuracy, tax accuracy and GL accuracy.
- **Tax treatment and GL account on HAND_OVER cases (answer keys, scoring).** Where the open question is the tax itself (for example whether a vehicle falls under the Regulation 25(1) exclusions), the answer key's tax treatment is null. The GL account is always set. Tax accuracy and GL accuracy leave out cases whose answer-key value is null.
- **Risk–coverage curve (scoring).** Drawn only when every prediction other than HAND_OVER gives a `confidence`. Cases the entry decided are ranked by confidence, highest first; tied confidences form one step. At each step, risk is the share of wrong decisions among the cases kept so far, and coverage is the share of all cases kept. HAND_OVER predictions are never kept. The area under the curve (AURC) is the mean risk over all steps.

## [v0.9.0-alpha.1] - 2026-11-13

Spec: v0.9 (synthetic, rules-based). Scores comparable with: v0.9.*

### Rules

- Tax-rule sheet v0.9, verified against the official sources on 13 Nov 2026.

### Decisions

- Nine decisions as in spec v0.9.

### Scoring

- Clarification (no version bump; no scores exist yet). The spec's cost table leaves three cases implicit. They cost:
  - a wrong non-approve decision where a different non-approve decision is right (for example DISPUTE_QUANTITY instead of DISPUTE_PRICE): 3
  - a non-approve decision other than HAND_OVER on a case where handing over is right: 3
  - APPROVE on a case where handing over is right: 10
- Tax and GL accuracy are scored over the cases an entry decided, and are always shown next to coverage.

### Data

- None yet. Train and test data are added when the generator lands, in v0.9.0.

### Card and docs

- Dataset card (card-only form), spec v0.9, tax-rule sheet v0.9, output schema v0.9.

### Tooling

- Hidden-split guard, secret scan, staging and publishing to Hugging Face.
