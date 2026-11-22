# Changelog

All releases of the SG Systems Decision Benchmark. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning rules:

- Any change to a rule, the decision list, the tax-treatment codes, the scoring, or any answer key is a new spec version (for example v0.9 to v0.10). Scores are compared only within one spec version.
- Patch releases (for example v0.9.1) are for card or doc changes only. Data must be byte-identical.
- Clarifications without a version bump are allowed only while no scores exist for that version.
- An engine change that alters any answer key is a new spec version. Every answer key records the engine version and the rule-sheet version that wrote it.

## [Unreleased]

Spec: v0.10 (synthetic, rules-based), in review. Scores comparable with: v0.10.* (none exist yet).

Engine: 0.10.3. Rules as of: 2026-11-22.

### Engine (A12, build PRs #12, #14, #15, #17 and this one)

- Every rule of rule sheet v0.10 is built, line by line: Malaysian service tax, rental, construction, Ministerial exemptions, sales tax, e-invoices, designated and special areas; Singapore GST; withholding tax in both countries; mixed invoices. A rule the documents don't settle gives HAND_OVER with that rule as basis.
- Answer keys carry `tax_lines` (treatment, basis, GL account per line), `buyer_actions`, the gold `facts` with evidence, `engine_version` 0.10.0 and `rules_version` v0.10.
- `check_rules` (agent variant b) runs the same code path on facts a caller supplies; the reference-row check shows it reproduces every answer key from its gold facts.
- The release catalog maps categories to the facts and lists the rules need (fact defaults, P.U. (A) 212/2018 items, area goods kinds) and adds 44 categories; goods for G-1, G-3 and L-8 are pinned to one tariff code each, read at subheading level from the archived orders.
- Release entries from v0.10 pin the engine: `release/publish.py` checks the "Engine: … Rules as of: …" line against the package version.

### Engine 0.10.1: goods rates before 1 Jul 2025 (MG-3)

- Before 1 Jul 2025 a goods line takes its category's class under the orders then in force: the Sales Tax (Rates of Tax) and (Goods Exempted from Tax) Orders 2018 from 1 Sep 2018 and 2022 from 1 Jun 2022, with every amendment. Engine 0.10.0 applied the 2025 classes to every date. The orders are archived and in the manifest.
- Exempt before 1 Jul 2025, so no sales tax on goods invoiced before then (P.U. (A) 199/2025 para 3(2)): HDPE, polypropylene and PVC resin, copper wire, electric forklifts, power tools, centrifugal pumps, fishmeal, feed premix and other-section rebar (5% from 1 Jul 2025), and motorcycles 8711.20.96 00 (exempt without a break; G-1 continues it).
- Gauges (90.26), thermostats and controllers (90.32) and tool bits (82.07): the earlier orders exempt their headings only in part, so a line dated before 1 Jul 2025 is HAND_OVER (MG-3). So is any goods line dated before sales tax began on 1 Sep 2018.
- Rule sheet section 2: P.U. (A) 165/2026 and 303/2026 amend the Persons Exempted Order, not the Goods Exempted Order; the sources line now says so and names the 2018 and 2022 orders.
- G-3 ends on 31 Aug 2026. From 1 Sep 2026 P.U. (A) 303/2026 adds Schedule B items 5 to 7 (animal feed, fertiliser and pesticide manufacturers) to the Persons Exempted Order: a buyer holding the certificate is exempt (MG-4; tax shown → `SST_SHOULD_BE_EXEMPT`), and without one the ordinary rate applies (MG-2). Rule sheet G-3 and MG-4 updated.

### Engine 0.10.2: e-invoice phases, exemptions and relaxation periods (ME-1)

- Rule sheet ME-1 rewritten (20 Nov 2026) from the archived LHDN timeline page, e-Invoice Guideline v4.6 sections 1.5-1.6 and Specific Guideline v4.9 section 16: the implementation date by FY2022 / YA2022 turnover, new businesses, the exempt persons, the RM3m exemption, and the interim relaxation periods. The dates are pack data (`countries/my/data/einvoice_timeline.yaml`).
- Correction: inside a supplier's interim relaxation period (to 31 Jan 2025, 30 Jun 2025 or 31 Dec 2025 by phase; to 31 Dec 2027 for the up-to-RM5m phase starting 1 Jan or 1 Jul 2026) an ordinary invoice raises no ME-1 finding, since the supplier may issue a consolidated e-invoice (Specific Guideline 16.2(a), (d)). Engine 0.10.1 raised the finding from the implementation date. Where Table 16.1 publishes no relaxation period for a supplier's implementation date (a new business commenced after 1 Jul 2026, or above RM5m), an invoice without a validated e-invoice is HAND_OVER.
- The supplier record states the facts that fix the phase (`einvoice`: turnover band, turnover basis, commencement date, the date turnover reached RM1m) instead of a phase start date; the unused free-text `turnover_band` is gone. Three supplier kinds are added for the exempt persons (foreign diplomatic office, individual not conducting business, international organisation). A statutory body or local authority is exempt for supplies before 1 Jul 2025 and, after that, for statutory fees and charges only (the line fact `statutory_fee_amount`).
- A validated e-invoice now settles ME-1 before the supplier's phase is looked at, so an unknown phase no longer hands over an invoice that has one; an unknown phase hands over only from 1 Feb 2025, when it can decide.

### Generator B1-1: core framework and slot allocator

- `core/generator/`: derived seeds, exact counts, the generic generation config (`TaskSetSpec.generation`), the slot allocator and the pipeline hash. `db-generate --task-set <id> --split train|test` (or `--split-spec`) writes the slot table and its report (`report/slots.json`) and provenance. No cases yet; B1-2 builds them.
- ap-invoices: the generator config (`content/generator/generation.yaml`), the rule table the per-rule floor counts (`content/generator/rules.yaml`, 75 rules; problem forms checked against the golden keys), the two-problem pairs (`content/hardcases/pairs.yaml`) and the public release seeds (`content/release-seeds.yaml`).
- The allocator reproduces every table of B1 plan section 3 for 2,000, 500 and 300 cases, and an infeasible demand stops the build with the demand named. Catalog README: the v0.10 planting limits, each with the test that enforces it.

### Engine 0.10.3: dated rule branches (date sweep)

- Rule sheet v0.10 updated twice on 22 Nov 2026 after engine tests of the branches dated outside the B1 case windows found errors in all four areas tested; a sweep of every dated rule element (about 120 boundaries, each tested on both sides) found more. Every error below is fixed; no existing answer key changes its answer (three change only their gold facts, because their tests now state a fact the corrected rule reads).
- Inside the case windows:
  - Group H item 1 (credit and charge cards, RM25 per card) is a taxable service since 1 Sep 2018 (the 2018 Regulations' Group H); engine 0.10.2 taxed it only from 1 Jul 2025.
  - The 26 Feb 2024 additions (karaoke centres, G(n) maintenance or repair, I12 brokering, Group J logistics; Service Tax (Amendment) Regulations 2024) are not taxable services before that date, and STP 1/2024's transitional exemptions apply 26-29 Feb 2024 (existing registrants) and 26 Feb-31 Mar 2024 (new registrants; supplier fact `registered_before_2024_02_26`), basis P-20. Before 26 Feb 2024 courier delivery is the old Group I item 6, parcels up to 30 kg (line fact `parcel_weight_kg`).
  - MS-3 applies reg 3A to scope changes: a supply wholly before a service's start date is not taxed even when invoiced after it; across the date only the part from it; a payment received before it is not taxed.
  - SG-6: from 1 Jan 2023, s21(3)(c) zero-rates only insuring passenger transport (and goods transport), and (e) excludes accommodation bookings (line facts `transport_service_kind`, `accommodation_booking`).
  - MS-5 item 5 (logistics) applies from 1 Mar 2024; every B2B item is now dated from its amending order.
  - L-1 follows STP 3/2025 Amendment No. 3 Appendix A (e) and (g): a contract ending on 1 Jul 2025 doesn't qualify; an extension of time qualifies only on an original contract that expired before 1 Jul 2025.
  - Treaty rows take effect on their effective dates (`treaty_effective_dates.yaml`; MY Poland 1 Jan 2024, Russia 1 Jan 2026; SG Greece 1 Jan 2023, Kenya and Taiwan 1 Jan 2027): the domestic rate before. Three LHDN sources added to the manifest.
  - 8% charged on rental provided from 1 Jan 2026 is `SST_WRONG_RATE` (REQUEST_CORRECTED_INVOICE; the correction comes as a credit note), whether invoiced before or after the 13 Mar 2026 gazette date (STP 2/2025 Amendment No. 5, Appendix B).
- Before the windows: MS-5 before 1 Jan 2019 and items 1-4 before 1 Jan 2020; MS-6 before the 5% test (1 Jan 2020; supplier fact `no_external_supplies`); MS-8 before 1 Jan 2019 and STP 2/2020 before 1 Jan 2020; WH-2 by the period of performance (17 Jan and 6 Sep 2017) and grossing-up before 5 Dec 2018 (`tax_borne_by_payer`); the Group C wellness exclusions before 1 Jul 2025 (`wellness_facility_kind`); SG-10 vehicles registered before 1 Apr 1998 (`vehicle_registered_on`). After the windows: K-2's one year is a calendar year (across 29 Feb 2028).
- New catalog category `wellness_centre_services` (Group C item 2); `karaoke_event_venue` is Group C item 1(e).

### Spec v0.10

**Why.** On 16 Nov 2026 Sebastian set the scope to full coverage: every rule that can decide what happens to a supplier invoice received by a company in Malaysia or Singapore, with nothing left out because it is rare or awkward, and HAND_OVER wherever a case's documents don't settle a rule. Rule sheet v0.10 (approved 17 Nov 2026) writes those rules down. Mixed invoices, imported services, withholding and self-billing don't fit one tax treatment per case, so the answer format and the scoring grow with it.

**Added**

- Rule sheet v0.10, `docs/tax-rules-v0.10.md`, committed unchanged. It supersedes the v0.9 sheet, which stays in place for v0.9 scores. Answers cite its rule IDs (MS-x, K-x, L-x, P-x, MG-x, G-x, ME-x, SG-x, WH-x).
- Spec v0.10, `docs/task-sets/ap-invoices/spec-v0.10.md`, and output schema v0.10, `schemas/ap-invoices/v0.10/`: a generic `output.schema.json`, the country parts `countries/my.schema.json` and `countries/sg.schema.json` (codes with definitions and rule IDs, worst-line order, rule IDs, buyer actions, line facts), and `results.schema.json`. `schemas/derive.py` generates the cross-field rules as plain JSON Schema.
- Optional output fields:
  - `tax_lines`: one entry per invoice line with `line_no`, `treatment` and `basis` (the rule ID).
  - `buyer_actions`: `ACCOUNT_IMPORTED_SERVICE_TAX` (MS-8), `ACCOUNT_CUSTOMER_ACCOUNTING_GST` (SG-7), `ACCOUNT_REVERSE_CHARGE_GST` (SG-8), `ISSUE_SELF_BILLED_EINVOICE` (ME-3), and `WITHHOLD_TAX` with `rate`, `basis` (WH-1 to WH-5) and `base_amount`. Empty list when none apply.
  - `facts`: per line, the facts the rules turn on, each with an evidence reference into the case documents.
- Tax-treatment codes. Malaysia: `SST_BUYER_ACCOUNTS` (MS-8), `SST_UNDERCHARGED` (MS-9, MG-1), `SST_NOT_CHARGEABLE_BY_TRADER` (MG-1). Singapore: `CUSTOMER_ACCOUNTING` (SG-7), `REVERSE_CHARGE` (SG-8), `NOT_CLAIMABLE_EXEMPT_USE` (SG-9), `RESIDUAL_APPORTIONED` (SG-9), `GST_UNDERCHARGED` (SG-3, SG-12). No code is removed.
- Extra columns, never in the main score: per-line tax accuracy, buyer-action accuracy (exact set; `WITHHOLD_TAX` also by rate and basis), facts score (per-field exact match, per field family). A column the entry didn't submit shows "not submitted", not 0.
- Two leaderboards on the same cases with the same scorer: model lane (one model, one call per case, no tools, no engine) and system lane (tools, rules engine, pipeline or agent). Every submission and results file states its lane.
- Agent-track variants, scored separately: (a) rules as documents in the policy folder; (b) the same plus a `check_rules` tool that takes the facts and returns the engine's per-line result.
- Reference row "engine on perfect facts" on the system-lane board, labelled as a reference, not an entry. "Always approve" and "always hand over" stay as floors.
- Hard-case share: at least half of the public test split are scans or PDFs only, cases with conflicting documents, or cases with missing information. The engine writes the keys, so on clean structured cases a program scores near-perfect; the hard cases make the score measure reading and judgement.

**Changed**

- `tax_treatment` stays the case-level value, defined as the worst line by a fixed order per country (spec, "Case level: the worst line").
- Withholding tax on payments to non-residents moves into scope, as a buyer action; it never changes the decision.
- Answer keys record `engine_version` and `rules_version`; each release pins an engine version and an as-of date.
- Unchanged: the nine decisions, the main score (cost table and weightings), case-level tax accuracy, GL accuracy, the exception mix, the splits. A v0.9-style prediction still validates and scores on the main score.

**Corrections found in the law (rule sheet §0.1)**

- C1: group relief covers Group G items (a)–(i), (l) and (n) since 1 May 2024 (Service Tax (Amendment) (No. 2) Regulations 2024 [P.U. (A) 354/2024]), not only (a)–(i) and (l) as in Service Tax Policy 8/2020. Already applied in the catalog and engine (A11).
- C2: courier services have no 30 kg limit; that limit sat in the old Group I item 6, deleted on 26 Feb 2024, and courier is now Group J item 1(d). Already applied (A11).
- C3: "same service" for the logistics B2B exemption is the same item 1(a), 1(c), 1(d) or 2, per the Persons Exempted Order item 5 and the logistics guide. A11's item matching stays; both sources are cited.
- C4: rental (Group K) is taxable since 1 Jul 2025 (6% since 1 Jan 2026); its B2B exemption (Order item 8) applies only to the sublet or subleased portion (MS-5). Engine: A12.
- C5: group relief survives external supplies of up to 5% of the service in the month and the next 11 months (First Schedule para 8(2)); for item (i) the "same service" is its sub-items. Modelled as a supplier fact (MS-6). Engine: A12.
- C6: the Minister's exemptions under Service Tax Act s34(3)(a), s34(4) and Sales Tax Act s35(3), published as Service Tax Policies and Sales Tax Policies, decide invoices too (MS-10, MG-6, K-x, L-x). Read in full on 17 Nov 2026 and archived. Engine: A12.

**Additions to the sheet after the spec review (§0.1a, 17 Nov 2026).** MS-9 also covers sales tax left off by the registered manufacturer that made the goods (`SST_UNDERCHARGED`). MG-1 names `SST_NOT_CHARGEABLE_BY_TRADER` for sales tax on goods the supplier did not manufacture, including a registered manufacturer reselling goods it bought in. New rule SG-12: GST left off a standard-rated supply by a GST-registered supplier → `GST_UNDERCHARGED`. §0.3 gives the full worst-line order by group.

**Sources manifest.** The sheet is no longer a pending citer. New entry for SG-12: the IRAS page on the responsibilities of a GST-registered business. The Service Tax Policy index page now also names MS-10. The two IRAS section roots the sheet names (GST, withholding tax) are treated as navigation, not sources; each IRAS page the rules use has its own entry.

### v0.10 clarifications (no version bump; no v0.10 scores exist yet)

Decided by Sebastian in the review of the A12 engine plan (PR #11), 18 Nov 2026.

- **Line facts (schema, spec "Facts").** 26 optional line-fact fields the rules read but the country parts lacked are added, each with its type, family and the rules that read it: Malaysia `manufactured_by_supplier`, `export_related`, `insurance_cover`, `premises_use`, `service_sub_item`, `own_use`, `variation_signed`, `variation_stamped`, `variation_changes_value`, `mixed_development_stated`, `ship_platform_election`, `annual_fee_per_student`, `financial_use`, `patient_category`, `medical_aid`, `referral_walk_in`, `fully_sponsored`, `student_category`, `digital_content_type`, `pallet_returnable`, `drop_shipment_export`, `self_billing_type`, `staff_secondment`, `excluded_management_kind`; Singapore `beneficiary_outside_singapore`, `low_value_goods`. `financial_charge` gains the charge types of P-2, P-3, P-4, P-5 and P-7.
- **GL account per line (schema, spec `tax_lines`).** Each `tax_lines` entry may carry its own `gl_account`. The case-level `gl_account` is the GL account of the line with the largest amount excluding tax (ties: the lowest `line_no`). Line GL accuracy is reported in the per-line column, next to per-line tax accuracy; the main score and case-level GL accuracy are unchanged. The results schema gains `line_gl_accuracy`.
- **ME-3 self-billing types (sheet, schema, spec "Facts").** Decided by Sebastian in the review of build PR 1 (PR #12), 18 Nov 2026. ME-3 now lists the nine transaction types of section 8.3 of the LHDN e-Invoice Specific Guideline v4.9. In the Malaysian part, `self_billing_type` names them, in place of the catch-all `other_section_8_3`: `agents_dealers_distributors`, `foreign_supplier`, `profit_distribution`, `ecommerce`, `betting_gaming_payout`, `individual_not_in_business`, `interest_payment`, `insurance_claim_payment`, `capital_return_or_liquidation` (and `none`). A new line fact, `interest_exception`, records the exceptions to item (g): `public_lender`, `employee_to_employer`, `foreign_payor`, `related_company_treasury`, `late_payment_charge` (and `none`). Where an exception applies, the supplier issues the e-invoice and there is no buyer action.
- **Case-level GL with credit notes (spec `tax_lines`).** Decided in the same review. "Largest amount" is the largest absolute amount excluding tax, so credit notes and invoices with lines of both signs follow the same rule. Ties still go to the lowest `line_no`.
- **Malaysian line facts from the review of build PR 2 (schema, spec "Facts").** Decided by Sebastian in the review of PR #14, 18 Nov 2026. New: `value_provided_before_change` (split; MS-3: the value provided before a rate change, where the documents show it), `completed_building` (L-5), `digital_payment_provider` (`bank`, `non_bank`, `none`; P-20 dated digital-payment exemptions), `education_provider_kind` (`private_school`, `higher_education`, `language_centre`; Group M). `excluded_management_kind` gains `health_examination_management` (P-15).
- **Singapore line fact from the review of build PR 3 (schema, spec "Facts").** Decided by Sebastian in the review of PR #15, 18 Nov 2026. New: `value_performed_in_singapore` (split; WH-5: the value of technical, service or management work performed in Singapore, where the documents show it).
- **Malaysian area facts for MS-7 and MG-5 (schema, spec "Facts").** Decided by Sebastian with the rewritten MS-7 and MG-5 (sheet of 18 Nov 2026). New line facts: `recipient_zone`, `service_site_zone`, `delivery_zone` (zones, `pca` for the principal customs area), `international_leg` (the five item-7 legs of P.U. (A) 212/2018, or `none`), `used_directly_in_approved_activity`, `motor_vehicle_value` with `motor_vehicle_value_basis` (`cif`, `sales_price`). Zones gain `pulau_1` and `petroleum_supply_base`. From the PR 4 review (19 Nov): line facts `employer_staff_accommodation`, `educational_training_welfare_purpose`, `non_commercial_religious_welfare` (item 3 exclusions) and `canteen_kind` (item 4 exclusions).
- **`check_rules` on facts the caller doesn't supply (spec, variant (b)).** Decided by Sebastian in the review of build PR 5 (PR #18), 19 Nov 2026. A fact the rules read but the call doesn't supply takes the engine's ordinary default and is listed in `missing`; the line's `treatment` is null only where a rule can't settle it. This is the only way the tool reproduces the answer keys from their gold facts (the reference-row check). The spec said a missing fact makes the treatment null; it now says this.
- **Buyer actions are obligations only (spec `buyer_actions`).** An optional later claim is not a buyer action: where an exemption works by refund (G-3, the JDA refund route in P-20), the line is `SST_CORRECT` with no buyer action.

### v0.9 clarifications (no version bump; no scores exist yet; carried into v0.10)

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
