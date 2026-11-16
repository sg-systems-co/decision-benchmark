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
- **Malaysian sales-tax rate of a goods category (rules, catalog).** Proposed in the catalog PR, pending Sebastian's approval. The tax-rule sheet says goods are taxed at 5% or 10% or exempt, but not which goods. The catalog takes each goods category's rate from the gazetted orders as linked on https://mysst.customs.gov.my/sst-orders/: the Sales Tax (Rate of Sales Tax) Order 2025 [P.U. (A) 170/2025] and the Sales Tax (Goods Exempted from Sales Tax) Order 2025 [P.U. (A) 171/2025], with every later amendment (P.U. (A) 199/2025, 399/2025, 281/2026; 200/2025, 400/2025). A category is `sales_10` only when its HS heading is in neither order, `sales_5` only when its exact subheading is in the First Schedule of the rate order and the heading is not in the exemption order, and `sales_exempt` only when its heading is in the exemption order and not in the rate order. Wrong rates are still planted only on services (decision Q9).
- **Singapore medical exceptions (rules, tax-rule sheet "disallowed" list).** Proposed, pending approval. The IRAS page the sheet cites (read 16 Nov 2026) gives exceptions the sheet leaves out: staff medical expenses are also claimable when the treatment is for a work-related health risk under written law, or COVID-19 treatment under a government advisory; and medical and accident insurance premiums are claimable when the cover is obligatory under the Work Injury Compensation Act or a collective agreement. `staff_medical_obligatory` means "any IRAS exception applies". The insurance exception needs an engine change before insurance cases can be planted with an obligation; until then the generator uses insurance only where the documents state the cover is voluntary.
- **Source links (docs).** Two links in the tax-rule sheet and the spec died when mysst.customs.gov.my moved its files on to a new host: the RMCD guide on management services and Service Tax Policy 8/2020. They now point to the same documents as linked from https://mysst.customs.gov.my/industry-guides/ and /service-tax-policy/. No rule changed.
- **Risk–coverage curve (scoring).** Drawn only when every prediction other than HAND_OVER gives a `confidence`. Cases the entry decided are ranked by confidence, highest first; tied confidences form one step. At each step, risk is the share of wrong decisions among the cases kept so far, and coverage is the share of all cases kept. HAND_OVER predictions are never kept. The area under the curve (AURC) is the mean risk over all steps.

## [v0.9.0-alpha.1.1] - 2026-11-16

Spec: v0.9 (synthetic, rules-based). Scores comparable with: v0.9.*

Card republished under the new name ap-invoices; no data change.

### Renamed

- **Task set `ap-invoices-my-sg` is now `ap-invoices`** (16 Nov 2026, PR #4 review). Countries are no longer part of the task-set name: each country is a country pack in the code, a config of the Hugging Face dataset (`MY`, `SG`), and a slice of the results (reported per country and overall). Paths moved with it: `docs/task-sets/ap-invoices/`, `schemas/ap-invoices/v0.9/`, `hf/ap-invoices/`, `results/ap-invoices/v0.9/`. The schema, decisions, tax-treatment codes, reason codes and answer keys are unchanged. The Hugging Face dataset `sgsystems/decision-benchmark-ap-my-sg` (which held only the card) is moved to `sgsystems/decision-benchmark-ap-invoices`; the old URL redirects.

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
