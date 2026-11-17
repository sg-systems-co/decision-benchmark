# SG Systems Decision Benchmark — Task set 1 (supplier invoices, MY/SG) — spec v0.10

Status: draft for review, 17 Nov 2026. Replaces [spec v0.9](spec-v0.9.md) once approved; then frozen, and changes need a version bump. Rules: [rule sheet v0.10](../../tax-rules-v0.10.md), approved 17 Nov 2026. Output: [`schemas/ap-invoices/v0.10/`](../../../schemas/ap-invoices/v0.10/).

## What changed from v0.9

v0.10 follows the full-coverage scope decided on 16 Nov 2026: every rule that can decide what happens to a supplier invoice received by a company in Malaysia or Singapore, with nothing left out because it is rare or awkward (rule sheet §0, §7).

- **Rules:** rule sheet v0.10 replaces v0.9. Answers cite its rule IDs (MS-x, K-x, L-x, P-x, MG-x, G-x, ME-x, SG-x, WH-x).
- **Output:** new optional fields `tax_lines`, `buyer_actions` and `facts`; eight new tax-treatment codes; `tax_treatment` is now defined as the worst line. A v0.9 output is still a valid v0.10 output and scores the same on the main score.
- **Scoring:** main score and case-level tax accuracy unchanged. New extra columns: per-line tax accuracy, buyer-action accuracy, facts score.
- **Leaderboards:** two lanes on the same cases, model lane and system lane. Two agent-track variants. A reference row "engine on perfect facts".
- **Answer keys:** record the engine version and rule-sheet version that wrote them.
- **Cases:** at least half of the public test split are hard cases (scans or PDFs only, conflicting documents, missing information).
- **Scope:** withholding tax on payments to non-residents moves into scope as a buyer action (rule sheet §4A).

## Scope and version

This spec defines task set 1 of the SG Systems Decision Benchmark: supplier-invoice decisions for buying companies in Malaysia and Singapore. Version v0.10 is "synthetic, rules-based". Any change to a rule, the decision list, the tax-treatment codes, the scoring or any answer key raises the version, and scores are compared only within one version.

- **The job being tested:** an accounts-payable clerk receives a supplier invoice, checks it against the company's records and rules, and decides what happens to it. That includes the tax treatment of each line, the GL account, the actions the buyer must take itself (account for tax, issue a self-billed e-invoice, withhold tax), or handing it to a person.
- **In scope:** goods and services invoices and credit notes from local and foreign suppliers. Malaysian service tax (Groups A–M) and sales tax, imported and digital services, designated and special areas, Ministerial exemptions, rate transitions, MyInvois e-invoices including self-billed ones; Singapore GST including zero-rated and exempt supplies, customer accounting, reverse charge, partial exemption and the Regulation 26/27 rules; withholding tax on payments to non-residents in both countries; PO matching, duplicates, invoice validity, changed bank details, approval limits.
- **Out of scope for v0.10:** payment runs, month-end close, multi-currency revaluation, customs and import permits, and expense claims (planned as a later task set).
- **Answers follow official rules only**, as written in the rule sheet. Where a case's documents don't settle a rule, the answer is HAND_OVER. Accountant review comes after launch.
- **Two tracks on the same cases:**
  - Decision track: a model or system gets the full case file and returns a decision.
  - Agent track: an agent gets only the invoice and has to look the rest up through MCP tools before deciding. It runs in two variants (see "Leaderboards").

## Case format

Each case belongs to one fictional buying company. A company's records are shared by all its cases, as in a real ERP. Every company comes with a policy pack: AP tolerance policy, approval matrix, chart of accounts with GL codes, its tax registrations, and its exemption certificates where relevant.

| Part | Contents | Decision track | Agent track |
| --- | --- | --- | --- |
| Invoice | Structured record (MyInvois-style fields for Malaysia, Peppol PINT-SG-style fields for Singapore) plus a rendered PDF; some cases are scans or photos only (see "Hard cases") | Given | Given |
| Purchase order | PO lines, prices, quantities, approver | Given | Looked up |
| Goods receipt | What was received and when | Given | Looked up |
| Supplier record | Name, tax registration, manufacturer or trader, residence and permanent establishment, bank account on file, payment terms | Given | Looked up |
| Company record | Tax registrations, group structure (parent, shareholding, board control), Singapore partial-exemption status, Malaysian MSME status, designated or special area | Given | Looked up |
| Contract record | For rental and construction: dates signed and stamped, price-review clause, project type | Given where relevant | Looked up |
| History | Paid and open invoices from the same supplier | Given (last 10) | Looked up |
| Email thread | Supplier or colleague messages linked to the invoice, if any | Given | Looked up in the AP inbox |
| Policy pack | Tolerances, approval limits, chart of accounts, tax registrations, exemption certificates, certificates of residence | Given | Looked up in the policy folder |
| Rules | The rule sheet as documents | Not given | In the policy folder (both agent variants) |
| People | Simulated procurement colleague and supplier who answer questions | Not used | Can be asked, once per case |
| Answer key | See "Answer keys and versions" | Never shown | Never inside the environment |

- **Document ids.** Every case document has an id: the invoice id, a PO number, a receipt id, an email message id, a supplier or company record id, a contract id, or a policy-pack file name. The evidence references in `facts` use them.
- **Languages:** documents are mostly English. Some line descriptions and emails are in Bahasa Malaysia or Chinese, and a few Malaysian invoices from Thai suppliers carry Thai text.
- **Modality:** every case ships both the structured record and the rendered PDF, as v0.9 decided, except the scan-only cases (see "Hard-case share"), whose invoice is a scan, photo or PDF only and is the same in both modes. Entrants say which they used, and results are reported separately for each.

## Decisions

Every output has one decision. The decisions are unchanged from v0.9.

| Decision | When it is right | Closest evalsafe action |
| --- | --- | --- |
| APPROVE | Matches PO and receipt within tolerance, valid invoice, tax correct, within approval limit | (approval, name to confirm) |
| DISPUTE\_PRICE | Unit price above the PO price beyond tolerance | DISPUTE\_LINES |
| DISPUTE\_QUANTITY | Billed quantity above the received quantity | DISPUTE\_LINES |
| HOLD\_NOT\_RECEIVED | Goods or service not yet received | HOLD\_REQUEST\_DOCUMENTS |
| REJECT\_DUPLICATE | Same invoice already paid or open | REJECT\_AS\_DUPLICATE |
| REQUEST\_CORRECTED\_INVOICE | Invoice invalid, or tax wrongly charged or undercharged on any line | REQUEST\_CORRECTED\_INVOICE |
| FRAUD\_REVIEW | Bank details differ from the supplier record, or the change came only by email | FRAUD\_REVIEW |
| ROUTE\_FOR\_APPROVAL | No PO, or amount above the approver's limit | HUMAN\_APPROVAL / PROCUREMENT\_REVIEW |
| HAND\_OVER | The model is not sure enough to decide, or the case cannot be settled from the information available | (none) |

When a case has two problems, the decision follows the fixed priority of v0.9: fraud, then duplicate, then invalid invoice (which includes every wrongly charged or undercharged tax line), then mismatch, then routing. Buyer actions never change the decision.

## Tax treatment

The two countries ask different questions, because Malaysian SST is not a credit system like GST.

- **Malaysia (SST):** was the tax charged correctly, and must the buyer account for any itself? Sales tax is single-stage and there is no input credit (MG-1).
- **Singapore (GST):** can the buyer claim the GST as input tax, and must it account for any itself?

### Codes

New codes in v0.10 are marked **new**. Each code's definition and rule IDs are also in the country parts of the schema (`countries/my.schema.json`, `countries/sg.schema.json`), which are the machine-readable source.

**Malaysia**

| Code | Meaning | Rules | Decision effect |
| --- | --- | --- | --- |
| `SST_SUPPLIER_NOT_REGISTERED` | Service tax or sales tax charged by a supplier that is not registered for it (and not liable to be) on the invoice date | MS-1, MG-1 | REQUEST\_CORRECTED\_INVOICE |
| `SST_NOT_CHARGEABLE_BY_TRADER` **new** | Sales tax charged on goods the supplier did not manufacture: by a trader, distributor or retailer, or by a registered manufacturer reselling goods it bought in. Only a registered manufacturer charges sales tax, on taxable goods it manufactured and sold | MG-1 | REQUEST\_CORRECTED\_INVOICE |
| `SST_SHOULD_BE_EXEMPT` | Tax charged where an exclusion, exemption, relief or area rule means none is due: item exclusions, B2B exemptions, group relief, designated and special areas, Ministerial exemptions (K-x, L-x, P-x, G-x), exempt goods, Schedules A, B, C | MS-1, MS-4, MS-5, MS-6, MS-7, MS-10, MG-2, MG-4, MG-5, MG-6 | REQUEST\_CORRECTED\_INVOICE |
| `SST_WRONG_RATE` | Tax charged at a rate other than the one for the service or tariff code and the dates on the documents, higher or lower | MS-2, MS-3, MG-2, MG-3 | REQUEST\_CORRECTED\_INVOICE |
| `SST_UNDERCHARGED` **new** | Service tax or sales tax left off a taxable line: service tax on a taxable service to a buyer with no exemption, or sales tax on taxable goods by the registered manufacturer that made them. The buyer owes only what is invoiced, but the invoice is wrong | MS-9, MG-1 | REQUEST\_CORRECTED\_INVOICE |
| `SST_CORRECT` | Tax due and charged at the right rate by a supplier entitled to charge it | MS-1, MS-2, MG-1, MG-2 | none |
| `SST_BUYER_ACCOUNTS` **new** | Imported taxable service: the overseas supplier correctly shows no SST, and the buyer accounts for service tax itself (Service Tax Act s26, s26A). Comes with the buyer action `ACCOUNT_IMPORTED_SERVICE_TAX` | MS-8 | none |
| `NO_SST` | No SST due and none charged | MS-1, MS-8, MG-2 | none |

**Singapore**

| Code | Meaning | Rules | Decision effect |
| --- | --- | --- | --- |
| `GST_WRONGLY_CHARGED` | GST charged when it should not be (supplier not registered, OVR vendor to a registered buyer, exempt or zero-rated supply, customer-accounting goods), or at a rate higher than the time-of-supply rules allow | SG-3, SG-4, SG-5, SG-6, SG-7 | REQUEST\_CORRECTED\_INVOICE |
| `GST_UNDERCHARGED` **new** | GST lower than it should be: a rate lower than the time-of-supply rules allow for the dates on the documents (SG-3), or GST left off a standard-rated supply by a GST-registered supplier where none of SG-5 to SG-8 applies (SG-12). The supplier must issue a corrected invoice | SG-3, SG-12 | REQUEST\_CORRECTED\_INVOICE |
| `NOT_CLAIMABLE_INVALID_INVOICE` | Not a valid tax invoice (a required item is missing), so no input tax can be claimed on it | SG-2 | REQUEST\_CORRECTED\_INVOICE |
| `NOT_CLAIMABLE_DISALLOWED` | Input tax disallowed under Regulations 26/27 and related IRAS rules (club fees, staff medical, motor cars, family and director-only benefits, CSR for third parties), or not for the purpose of the business | SG-1, SG-10 | none (booked without input tax) |
| `NOT_CLAIMABLE_EXEMPT_USE` **new** | Partially exempt buyer that does not meet the de minimis rule; the line is directly attributable to its exempt supplies, so the input tax is not claimable | SG-9 | none (booked without input tax) |
| `RESIDUAL_APPORTIONED` **new** | Partially exempt buyer; the line is residual (used for both taxable and exempt supplies), so the input tax is claimable only by the buyer's apportionment | SG-9 | none |
| `CLAIMABLE` | All eight claim conditions hold; the input tax is claimable in full | SG-1 | none |
| `CUSTOMER_ACCOUNTING` **new** | Prescribed goods (mobile phones, memory cards, off-the-shelf software) above S$10,000 excl. GST to a GST-registered buyer for business: the supplier correctly charges no GST on a customer accounting tax invoice, and the buyer accounts for it. Comes with the buyer action `ACCOUNT_CUSTOMER_ACCOUNTING_GST` | SG-7 | none |
| `REVERSE_CHARGE` **new** | Imported service or low-value goods bought by a GST-registered buyer not entitled to full input tax: the buyer accounts for GST itself. Comes with the buyer action `ACCOUNT_REVERSE_CHARGE_GST` | SG-8 | none |
| `NO_GST` | No GST charged and none due: supplier not registered, exempt, zero-rated (0% shown) or out-of-scope supply, or an imported service to a fully taxable buyer | SG-4, SG-5, SG-6, SG-8 | none |

### Case level: the worst line

`tax_treatment` stays the case-level value, kept for the leaderboard. It is the worst line of the invoice in this order, worst first:

1. tax wrongly charged or undercharged
2. invalid invoice
3. not claimable (disallowed, exempt use)
4. residual apportioned
5. claimable, correct, buyer accounts, no tax

Inside each group the order is fixed too, so every set of lines has exactly one worst line. The full order per country (also `x-severity-order` in the country parts):

- **Malaysia:** `SST_SUPPLIER_NOT_REGISTERED` > `SST_NOT_CHARGEABLE_BY_TRADER` > `SST_SHOULD_BE_EXEMPT` > `SST_WRONG_RATE` > `SST_UNDERCHARGED` > `SST_CORRECT` > `SST_BUYER_ACCOUNTS` > `NO_SST`
- **Singapore:** `GST_WRONGLY_CHARGED` > `GST_UNDERCHARGED` > `NOT_CLAIMABLE_INVALID_INVOICE` > `NOT_CLAIMABLE_DISALLOWED` > `NOT_CLAIMABLE_EXEMPT_USE` > `RESIDUAL_APPORTIONED` > `CLAIMABLE` > `CUSTOMER_ACCOUNTING` > `REVERSE_CHARGE` > `NO_GST`

Malaysia has no invalid-invoice, not-claimable or residual codes: an invalid Malaysian invoice (ME-2, ME-4) is a decision (REQUEST\_CORRECTED\_INVOICE), not a tax treatment. Inside the first group the Malaysian codes follow the v0.9 engine's finding order (not registered, should be exempt, wrong rate), with the trader code next to not registered (both mean "not entitled to charge", MG-1) and undercharged last (the buyer is not overcharged).

When an output has both `tax_lines` and a non-null `tax_treatment`, `tax_treatment` must equal the worst line treatment; the schema rejects anything else. A null line treatment (allowed on HAND\_OVER only) means the worst line is unknown, so `tax_treatment` must then be null too.

### `tax_lines`

One entry per invoice line:

| Field | Meaning |
| --- | --- |
| `line_no` | The line number printed on the invoice (1–200). Each line once. |
| `treatment` | The country's tax code for this line. null only when the decision is HAND\_OVER. |
| `basis` | The rule ID from the rule sheet that decides this line, for example `MS-8`, `K-1`, `SG-9`. On a null treatment, the rule the documents don't settle. |

All lines of one output use one country's codes and rule IDs. `basis` is required and is published in the answer keys, but it is not scored in v0.10: several rules can lead to the same treatment, and the sheet does not rank them.

Mixed invoices (rule sheet §5): each line gets its own treatment. Where the law ties the treatment to how the invoice is split (L-8 materials and works, L-8 installation by a sales-tax manufacturer, P-12 consultation fees, P-16 education fee items, MS-2 packages from Group A–E operators), the split is a deciding fact; not itemised, the whole invoice takes the taxed treatment.

### `buyer_actions`

Actions the buyer itself must take besides the decision (decisions D1–D3 of the rule sheet). A list; empty when none apply.

| Action | When | Rules |
| --- | --- | --- |
| `ACCOUNT_IMPORTED_SERVICE_TAX` | Malaysia: the buyer accounts for service tax on an imported taxable service (with `SST_BUYER_ACCOUNTS`) | MS-8 |
| `ACCOUNT_CUSTOMER_ACCOUNTING_GST` | Singapore: the buyer accounts for GST on prescribed goods (with `CUSTOMER_ACCOUNTING`) | SG-7 |
| `ACCOUNT_REVERSE_CHARGE_GST` | Singapore: the buyer accounts for GST under reverse charge (with `REVERSE_CHARGE`) | SG-8 |
| `ISSUE_SELF_BILLED_EINVOICE` | Malaysia: the buyer issues the e-invoice itself for a transaction type in the LHDN Specific Guideline section 8.3, when it is in a mandatory phase on the transaction date | ME-3 |
| `WITHHOLD_TAX` | A payment to a non-resident is subject to withholding | WH-1 to WH-4 (Malaysia), WH-5 (Singapore) |

Each action is an object `{"action": ...}`. `WITHHOLD_TAX` also carries `rate` (percent), `basis` (the WH rule ID) and `base_amount` (the amount the rate applies to, in the invoice currency, as a decimal string). A payment with two withholdings (WH-3: 10% for the contractor and 3% for its employees) lists two `WITHHOLD_TAX` objects.

## Facts (optional, scored separately)

`facts` lets an entry show what it read. Per invoice line, it gives the facts the rules turn on, each with its value and where the case documents show it.

```json
{"facts": {"lines": [{"line_no": 2, "materials_works_separated": {"value": true, "evidence": [{"doc_id": "INV-MY-01577", "path": "lines[1].description"}]}, "contract_signed": {"value": null}}]}}
```

- **Value.** Typed per field (code, enum, boolean, date, decimal string, share 0–1). null means "the documents don't show this fact", the situation that leads a rule to HAND\_OVER.
- **Evidence.** Every non-null value needs at least one reference: `doc_id` (a case document id) and either `path` (a field path in the document's structured record) or `span` (character offsets into the document's text, end exclusive), with an optional `quote`. A null value has no evidence.
- **Fields.** At minimum the line's classification (`service_item` or `tariff_code` for Malaysia; the supply category for Singapore) and every line fact a rule in the sheet reads. The full list, with types, families and the rules that read each field, is in the country parts (`$defs/line_facts`). Families:

| Family | Malaysia | Singapore |
| --- | --- | --- |
| classification | `service_item`, `tariff_code`, `fb_content`, `financial_charge`, `asset_type`, `education_fee_item` | `exempt_supply`, `zero_rating_provision`, `prescribed_goods`, `disallowed_category`, `vehicle_is_motor_car` |
| time\_and\_rate | `service_period_start`, `service_period_end`, `amount_paid_before_change`, `delivery_date` | `delivery_date`, `amount_paid_before_change`, `value_delivered_before_change`, `contract_excludes_tax_change` |
| scope\_and\_exemption | `subject_outside_malaysia`, `statutory_fee_amount`, `residential`, `asset_in_malaysia`, `financial_lease`, `air_route`, `carriage`, `patient_citizen`, `student_citizen`, `oku_holder`, `mro_aircraft_ship`, `building_charge` | `goods_outside_singapore`, `export_evidence`, `international_transport`, `staff_medical_obligatory`, `insurance_obligatory`, `chauffeured_pay_per_trip`, `car_used_by_third_party` |
| buyer\_and\_purpose | `personal_use`, `same_service_as_buyer`, `sublet`, `sublet_share`, `supplier_paid` | `purchase_attribution`, `business_purpose` |
| split | `materials_works_separated`, `installation_separated`, `itemised_consultation_fee`, `package_single_price` | (none) |
| contract | `contract_signed`, `contract_stamped`, `price_review_clause`, `residential_share`, `design_and_build`, `place_of_worship`, `client_established_in_malaysia`, `exemption_statement_on_invoice` | (none) |
| withholding | `payment_nature`, `place_of_performance`, `in_country_share`, `hotel_reimbursement`, `certificate_of_residence` | `payment_nature`, `place_of_performance`, `certificate_of_residence` |

Party facts (registrations, group structure, partial-exemption status, supplier residence) are case facts, not line facts, and are not part of `facts` in v0.10.

**Facts score.** The answer key holds the gold facts: for each line, every fact field the engine read to decide it, with its value (or null). Each gold field is scored by exact match: codes and enums as equal strings, booleans as equal, dates as equal dates, decimal strings and shares as equal numbers. A gold field the entry leaves out of a submitted line counts as wrong; fields beyond the gold are not scored. A non-null value counts only if at least one of its evidence references names a document of the case; where in the document it points is not scored in v0.10. The score is the share of gold fields matched, reported per family and overall, over all cases (HAND\_OVER included, since facts don't depend on the decision). **Leaving `facts` out never lowers the main score.**

## Exception mix and hard cases

**Exception mix** (unchanged from v0.9; the tax-problem share now draws on every rule in the sheet):

| Share of cases | Type |
| --- | --- |
| 40% | Clean, should be approved |
| 10% | Tax problems (wrong rate, should be exempt, not chargeable, undercharged, not claimable, invalid tax invoice) |
| 10% | Price mismatch |
| 8% | Quantity mismatch |
| 8% | Invalid invoice or missing mandatory fields |
| 7% | Duplicates, including near-duplicates (same amount, different invoice number) |
| 5% | Not received |
| 5% | No PO or above the approval limit |
| 4% | Changed bank details (trap) |
| 3% | Ambiguous, where handing over is the right answer |

About 15% of cases carry two problems at once. The decision follows the fixed priority above.

**Hard-case share.** At least half of the public test split (at least 250 of 500 cases) are hard cases. A case counts once if it has any of:

- **scan or PDF only:** the invoice comes only as a scan, photo or PDF, with no structured record;
- **conflicting documents:** two case documents disagree on a fact a rule reads (for example the invoice description and the PO, or an email that corrects the service period);
- **missing information:** a fact a rule reads is in no case document (the answer is then HAND\_OVER, or in the agent track the fact must be looked up or asked for).

**Limit on scan-only cases.** In each split, scan-only cases are at most one third of the hard cases. So at least two thirds of the hard cases also ship a structured record, and the structured-format score keeps enough hard cases. Every other case ships both formats, as v0.9 decided.

The hard-case share is independent of the exception mix: a clean case can be a scan. Train and hidden splits have the same share.

Why: the engine writes the answer keys. On a clean case with a structured record, a program that maps the record's fields to the engine's inputs reproduces the key, so it scores near-perfect. A test made of such cases would measure rule lookup only. Hard cases make the score measure reading and judgement as well.

## Output and scoring

**Output, one JSON object per case** (schema: [`output.schema.json`](../../../schemas/ap-invoices/v0.10/output.schema.json) with the country parts in `countries/`):

```json
{"case_id": "ap-my-01410", "decision": "APPROVE", "tax_treatment": "SST_BUYER_ACCOUNTS", "gl_account": "6400-200", "reason_codes": ["MATCHED_WITHIN_TOLERANCE"], "tax_lines": [{"line_no": 1, "treatment": "SST_BUYER_ACCOUNTS", "basis": "MS-8"}], "buyer_actions": [{"action": "ACCOUNT_IMPORTED_SERVICE_TAX"}, {"action": "ISSUE_SELF_BILLED_EINVOICE"}, {"action": "WITHHOLD_TAX", "rate": 10, "basis": "WH-2", "base_amount": "18000.00"}], "confidence": 0.77}
```

- Required, as in v0.9: `case_id`, `decision`, `tax_treatment`, `gl_account`, `reason_codes`. Optional: `confidence`, `explanation`, and the new `tax_lines`, `buyer_actions`, `facts`.
- A v0.9 output (no new fields) is a valid v0.10 output.
- `confidence` (0–1) is optional. Without it, no risk–coverage curve can be drawn for that entry.
- `explanation` is free text. It is never scored on the leaderboard, only used in the AI-judged extras.
- Anything that breaks the schema, or names two decisions, is scored as a wrong decision. The schema, in plain JSON Schema, also rejects: a `line_no` listed twice; a case-level treatment that is not the worst line; lines from two countries; a line treatment that is null when the decision is not HAND\_OVER; a `basis` that is not a rule ID of the sheet; an unknown buyer action; `WITHHOLD_TAX` without `rate`, `basis` or `base_amount`, or with a basis that is not a WH rule; a fact with a value but no evidence reference.
- Derived parts of the schema (the worst-line rule, the unique-line rule) are generated by `schemas/derive.py` from the country parts; a test fails if they are stale.

**Main score: cost per case** (unchanged; lower is better):

| Outcome | Cost |
| --- | --- |
| Right decision | 0 |
| HAND\_OVER when handing over is the right answer | 0 |
| HAND\_OVER on any other case | 1 |
| Wrong hold, dispute or route (a false alarm) | 3 |
| Wrong APPROVE (a missed problem) | 10 |
| APPROVE on a trap (duplicate, changed bank details) | 10, plus counted as a critical error |

The v0.9 clarifications in the CHANGELOG carry over unchanged: the three implicit cost cases (a wrong non-approve decision where a different one is right: 3; a non-approve decision other than HAND\_OVER where handing over is right: 3; APPROVE where handing over is right: 10); invalid, missing or duplicate predictions get the worst cost; tax and GL accuracy leave out cases whose key value is null; the risk–coverage curve is drawn only when every non-HAND\_OVER prediction gives a confidence. Results are also shown under the weightings 1 / 2 / 5 and 1 / 3 / 20, as plain accuracy and as a risk–coverage curve, and as a realistic-mix score reweighted to 80% clean cases. Why these weights: see spec v0.9; nothing changed.

**Also reported for every entry**, unchanged from v0.9:

- accuracy on the cases it decided
- coverage: the share it decided instead of handing over
- risk–coverage curve and its area, if confidence was given
- case-level tax-treatment accuracy and GL accuracy, each scored separately over the cases the entry decided
- number of critical errors
- US$ per 1,000 decisions and median latency
- pass^3: the share of cases right in all three repeated runs

**Extra columns, new in v0.10. None of them is part of the main score.**

| Column | Unit | Definition |
| --- | --- | --- |
| Per-line tax accuracy | invoice line | Share of answer-key lines whose treatment the entry matches for the same `line_no`, over the cases the entry decided. Key lines with a null treatment are left out. A key line the entry gives no entry for counts as wrong; entry lines with no key line are ignored. |
| Buyer-action accuracy | case | Share of cases where the entry's set of actions equals the key's exactly, over the cases the entry decided. `WITHHOLD_TAX` matches only with the same `rate` and `basis`; `base_amount` is recorded but not compared in v0.10. An empty list matches an empty key. |
| Facts score | fact field | As defined under "Facts", reported per family and overall. |

**Not submitted is not zero.** If no prediction in a run has the field, its column shows "not submitted", never 0. If some predictions have it and others don't, the ones without it count as wrong in that column. An invalid prediction counts as wrong in every column the entry submitted. So a v0.9-style prediction file scores on the main score and the v0.9 columns exactly as before, and its three extra columns show "not submitted".

## Leaderboards

**Two leaderboards, same cases, same scorer.**

| Lane | Who | Tracks |
| --- | --- | --- |
| Model lane | One model, one call per case, no tools, no rules engine | Decision track only |
| System lane | Anything with tools, a rules engine, a pipeline or an agent | Decision track and agent track |

Every submission declares its lane. Every results file records it: `metadata.yaml` and the scorer's results files follow [`results.schema.json`](../../../schemas/ap-invoices/v0.10/results.schema.json), which requires `lane` and rejects a model-lane row on the agent track. The lanes are ranked separately; a system-lane row never appears on the model-lane board.

**Agent track variants.** Scored and reported separately, both on the system lane:

- **(a) rules as documents** (`rules_as_documents`): the rule sheet sits in the policy folder as documents, next to the policy pack. The agent reads it like a clerk would.
- **(b) rules as documents plus `check_rules`** (`check_rules_tool`): the same, plus an MCP tool `check_rules`. It takes the facts of the case's lines (the `facts.lines` format; evidence optional) and returns the engine's per-line result: for each line `line_no`, `treatment`, `basis`, the buyer actions that line triggers, and `missing` (the fact fields the rule needs and did not get; treatment is then null). It reads party facts (registrations, group, partial-exemption status) from the company's records in the environment. It is the same engine and version that wrote the keys, so variant (b) measures how well the agent finds the facts, not how well it knows the rules.

**Rows that are not entries.**

- **Reference: "engine on perfect facts"** (system lane). The engine run on the generator's gold facts. It is published on the system-lane board as a ceiling and labelled as a reference, not an entry, and is never ranked. Because the same engine wrote the keys, it should reproduce them; any difference is an engine bug and blocks the release.
- **Floors: "always approve" and "always hand over"**, on both boards, as in v0.9. "Always hand over" scores a cost of about 1.0 by construction.
- **Baselines** (ranked, marked as ours): the rules-only script with no AI (system lane, decision track), and 6–8 models with a prompt only (model lane) and as agents in both variants (system lane).

**Agent-track rubric**, per case, unchanged from v0.9: the same decision with the same costs, plus code-checked steps against the final state of the simulated systems: supplier matched (gate), PO matched (gate), receipt looked up, price variance computed and within tolerance or flagged (±0.5%), bank details compared with the record, duplicate check done, tax treatment (case level), GL account, decision recorded with a reason code, and supplier query clear (AI judge, reported separately). A failed gate sets every later step to 0. A case "passes" only if steps 1–9 all pass. The agent track adds steps used, tool calls (including `check_rules` calls in variant b), US$ per case and time per case.

## Answer keys and versions

**What a key holds:** decision, case-level tax treatment, `tax_lines` (with `basis`), `buyer_actions`, the gold `facts` with evidence, GL account, reason codes, the source of the answer (rules, or HAND\_OVER by construction), and two versions:

- `engine_version`: the version of the `decision-benchmark` package whose rules engine wrote the key (for example `0.10.0`);
- `rules_version`: the rule sheet it implements (`v0.10`).

Every results file records the `engine_version` and `rules_version` of the keys it was scored against.

**An engine change that alters any answer key is a new spec version** (CHANGELOG versioning rules). An engine change that alters no key may ship as a new engine version within the same spec version. Each release pins one engine version and an as-of date: the date up to which the rule sheet was checked against the official texts.

**Where the right answer comes from:**

- Every answer is computed by the rules engine from the company's records, the policy pack and the rule sheet, following official rules and guidance only.
- Hard cases, such as two problems at once, partial deliveries, credit notes, rounding, mixed tax lines, scans, conflicting documents and missing facts, are drafted from known real-world failure patterns. Their answers still come from the rules.
- Where the official rules do not settle a case, HAND\_OVER is the right answer by construction.
- No accountant has reviewed the rules or the keys yet. Accountant review and the realism check against real cases happen after launch, with the first customer. Until then a score measures agreement with the published rules, not accuracy on real invoices. The result is released as a new version.

## Splits

| Split | Cases | Where | Use |
| --- | --- | --- | --- |
| Train | 2,000 | Public (Hugging Face) | Anyone may train on it |
| Test | 500 | Public | Self-reported results |
| Hidden | 300 | decision-benchmark-hidden, private | Verified leaderboard runs only; never used for training or tuning, including by us |

Each split uses its own fictional companies and suppliers, so nothing leaks between them. Hard cases appear in all three, in the same proportion, and at least half of each split.

## Anti-gaming

- Answer keys never sit in the environment, and the environment is read-only except clerk actions.
- `check_rules` returns per-line tax results for the facts it is given, never the case's key; it cannot see the decision, the GL account or the other checks.
- Handing everything over costs about 1.0 per case, so it cannot win.
- Contradictory or malformed outputs count as wrong.
- Graders are tested against deliberately bad agents before release.
- The hidden split is scored only by us.

**Versioning:** v0.10 ("synthetic, rules-based"). v1.0 only after accountant review and the real-data check on 100–300 anonymised past cases from the first customer. Every release ships the generator seed, the engine version, the as-of date and a changelog.

## Choices this spec makes where the rule sheet is silent (for review)

1. **Order inside each group** of the worst-line order (see "Case level").
2. **`basis` is not scored** in v0.10; it is published for checking by hand.
3. **`base_amount` of `WITHHOLD_TAX` is not compared** in buyer-action accuracy, as asked; the field is still required.
4. **Facts are line facts only.** Party facts stay out of `facts` in v0.10.
5. **Evidence location is not scored**; only that a cited document exists in the case.
6. **"Scans/PDFs" for the hard-case share** means cases whose invoice comes with no structured record. Accepted (review of PR #10) with a limit: scan-only cases are at most one third of the hard cases in each split; every other case ships both formats.
7. **Extra columns use the decided cases**, like v0.9's tax and GL accuracy; the facts score uses all cases.
8. **Line numbers run 1–200**, so the unique-line rule can be written in plain JSON Schema.
9. **An invalid Singapore tax invoice (SG-2)** is a fact about the whole document. Every line on which GST is charged takes `NOT_CLAIMABLE_INVALID_INVOICE` unless a worse code applies to it; lines with no GST keep `NO_GST`.
10. **Zero-rated lines (SG-6) with 0% shown** are `NO_GST`: there is no GST to claim.
11. **Imported services where an MS-8 exception applies** (B2B order items 3 and 4, group relief, STP 2/2020, STP 1/2025 item 6) are `NO_SST` with no buyer action; with STP 3/2020 the foreign registered person's invoice correctly carries SST, so `SST_CORRECT`.
