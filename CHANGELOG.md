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
- **Singapore medical exceptions (rules, tax-rule sheet "disallowed" list).** Proposed, pending approval. The IRAS page the sheet cites (read 16 Nov 2026) gives exceptions the sheet leaves out: staff medical expenses are also claimable when the treatment is for a work-related health risk under written law, or COVID-19 treatment under a government advisory; and medical and accident insurance premiums are claimable when the cover is obligatory under the Work Injury Compensation Act or a collective agreement. `staff_medical_obligatory` means "any IRAS exception applies". The insurance exception is the line fact `insurance_obligatory` (next entry).
- **Malaysian B2B exemption and Singapore insurance exception (rules, tax-rule sheet table row 8 and "disallowed" list).** Proposed in A11, pending approval.
  - The row "service tax on a Group G service between two registered persons providing the same service" covers every B2B exemption scheme with the same conditions (both SST-registered, the buyer itself provides a taxable service under the same First Schedule item, not for personal use), matched by service item, not by category:
    - Group G except items (j) employment and (k) private agencies (guards): RMCD Guide on Management Services, para 24 (https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/Industry%20Guides/EN/Guide%20on%20Management%20Services%20%20V5%206.5.2026.pdf), and the maintenance guide, para 32 (https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/Industry%20Guides/MS/PANDUAN%20PERKHIDMATAN%20PENYENGGARAAN%20290324.pdf).
    - Group J logistics, same item only (1(a), 1(c), 1(d), 2): RMCD logistics guide, B2B exemption, paras I–II (https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/Industry%20Guides/MS/Panduan%20Perkhidmatan%20Logistik%2006062025.pdf).
    - Group I item 8 advertising: RMCD Guide on Advertising Services V4, paras 12–14 (https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/Industry%20Guides/EN/Guide%20on%20Advertising%20V4_20220119.pdf).
    - Group L construction works: RMCD Guide on Construction Work Services (17 Mar 2026), para 36 (https://pub-359af8e1f79c472292a7e44ec60f3027.r2.dev/Industry%20Guides/EN/GUIDE%20ON%20CONSTRUCTION%20WORK%20SERVICES%20DATED%2017.03.2026%20%5BAMENDMENT%5D%20%5BBI%5D_2.11.26%20(1).pdf).
  - Group relief, and so the HAND_OVER when the documents don't show whether the supplier is in the buyer's group, applies only to Group G items (a) to (i), (l) and (n): items (a) to (i) and (l) under Service Tax Policy 8/2020 and amendment no. 1, and item (n) maintenance and repair since 1 May 2024 under the Service Tax (Amendment) Regulations 2024 and Service Tax (Amendment) (No. 2) Regulations 2024 [P.U. (A) 354/2024], First Schedule paras 3 and 3A. For every other item the group relation is irrelevant.
  - Singapore medical and accident insurance premiums are claimable when the insurance is obligatory under the Work Injury Compensation Act or a collective agreement (https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax). Line fact `insurance_obligatory`: true claimable, false disallowed, unknown HAND_OVER.
  - The finding basis of this exemption is renamed from `group_g_b2b` to `b2b` (and the certificate kind `group_g_b2b_declaration` to `b2b_declaration`), because it now covers Groups G, J, I8 and L. That is the only answer-key change: the `TAX_SHOULD_BE_EXEMPT` finding's evidence in B2B cases.
- **Source links (docs).** Two links in the tax-rule sheet and the spec died when mysst.customs.gov.my moved its files on to a new host: the RMCD guide on management services and Service Tax Policy 8/2020. They now point to the same documents as linked from https://mysst.customs.gov.my/industry-guides/ and /service-tax-policy/. No rule changed.
- **Risk–coverage curve (scoring).** Drawn only when every prediction other than HAND_OVER gives a `confidence`. Cases the entry decided are ranked by confidence, highest first; tied confidences form one step. At each step, risk is the share of wrong decisions among the cases kept so far, and coverage is the share of all cases kept. HAND_OVER predictions are never kept. The area under the curve (AURC) is the mean risk over all steps.

### Docs

- **Sources are now archived.** Every official source the benchmark cites is kept in a private archive; `docs/sources/manifest.yaml` lists each one with its URL, retrieval date, SHA-256 and Wayback snapshot.
- **Sources for rule sheet v0.10 archived.** All 79 Service Tax Policies and 9 Sales Tax Policies, the LHDN and IRAS withholding tax sources, and GST Act s21. Manifest entries name the v0.10 rules that use them (`docs/tax-rules-v0.10.md#RULE`). New data tables in the country packs: DTA withholding rates (LHDN; IRAS treaty texts, machine-read and flagged for review) and the tariff codes in Sales Tax Policies 1/2025, 2/2025 and 1/2026. No change to rules or answer keys.

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
