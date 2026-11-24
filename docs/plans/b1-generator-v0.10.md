# B1 plan for spec v0.10: the structured generator

Status: draft for review, 20 Nov 2026. Replaces sections 4, 5, 7 and 8 and the B1 row of section 12 of the [step 11 plan](step-11-plan.md) for B1. Its sections 1–3, 6, 9–11 and 13–16 still apply except where this plan says otherwise. No code in this PR. Plan, review, Sebastian's approval, then the build.

Inputs: [spec v0.10](../task-sets/ap-invoices/spec-v0.10.md), [rule sheet v0.10](../tax-rules-v0.10.md), the [A12 plan](a12-engine-v0.10.md), the catalog README (`src/decision_benchmark/task_sets/ap_invoices/content/catalog/README.md`), engine 0.10.2 (ME-1 rewritten; it lands before B1-1).

Standing rules: answers follow the official rules only, and where a case's documents don't settle a rule the answer is HAND_OVER. The hidden split is never public and never used for training or tuning. Case text comes from committed phrasebanks, never from an LLM at generation time. Builds are byte-reproducible from the tagged commit. Code stays generic across countries.

## 1. What changes from the step 11 plan

| Step 11 | v0.10 |
| --- | --- |
| §4 data model: one tax code per case, untyped line facts, no contract records | Typed line facts with evidence, party facts with `*_known` flags, contract records and certificates of residence, all built in A12. The generator fills them (section 2). |
| §4.10 parquet columns | Added: `company_json`, `contracts_json`, `answer_tax_lines_json`, `answer_buyer_actions_json`, `answer_facts_json`, `engine_version`, `rules_version`, `hard_kinds`, `planted_rules`, `open_questions`. `invoice_json` is null on scan-only cases. |
| §5.1 quotas: the exception mix only | The exception mix is unchanged. On top of it: the hard-case share, mixed-tax invoices, a per-rule floor and a date-boundary floor (section 3). |
| §5.4: 13 table rows | 77 engine rules plus the two mixed-invoice rules of sheet §5. The 4 rules that aren't engine rules (P-21, G-2, G-6, G-7) are never planted. |
| §7.2 families: the v0.9 tax rows | One starter family per engine rule in B1; full families in B2. |
| §7.3 phrasebanks express email signals | They also express every line fact, each with a value parser that reads the stated phrase back to the same value (section 2.3). |
| §8.2 dates: 5 Jan – 30 Oct 2026 | One window per country, spanning every dated boundary inside it (section 6). |
| §8.4 planted = found on findings | Also on per-line treatment and basis, buyer actions, the HAND_OVER basis and the gold facts (section 4). Reference row on every case (section 5). |
| §8.2 companies: 40 train, 10 test, 6 hidden | 60 train, 20 test, 12 hidden, half Malaysian and half Singaporean (decision 3). |
| Catalog README limits for v0.9: no rental lines; construction contracts only from 1 Jul 2025 | Replaced by the v0.10 limits (section 3.5). Each limit is a test. |

## 2. What a case holds in v0.10

### 2.1 Records and documents

Every case document has a doc id, which evidence references cite:

- the invoice id;
- a PO number, a receipt id, an email message id;
- `supplier:<supplier_id>` and `company:<company_id>` for the master records;
- a contract id;
- the policy-pack file name, for certificates (exemption certificates and certificates of residence).

The decision track also gets `company_json` and `contracts_json`: the spec lists the company record and the contract record as "Given".

### 2.2 The answer key, and what the generator writes instead

The engine alone writes the key:

- decision, `tax_treatment` (the worst line), `gl_account` (the line with the largest absolute amount excluding tax), `reason_codes`, `answer_source`, `findings`;
- `tax_lines`: per line `treatment`, `basis` and `gl_account`;
- `buyer_actions`;
- gold `facts`: per line, every field the engine read, with its value (or null) and evidence;
- `engine_version` and `rules_version`.

The generator writes the **generator truth**, which is never an input to the engine:

- `planted`: per line, the expected treatment and basis; per case, the expected decision, findings and buyer actions;
- `hard_kinds`;
- `open_questions`: only `Q-A1` may appear (section 3.5);
- `families`, `exception_types`, `two_problems`, as in v0.9.

### 2.3 Stating every fact the key depends on

The generator sets every fact through one **statement registry** (`task_sets/ap_invoices/generator/statements.py`). For each fact it writes the value into exactly one governing document, and records the evidence that the engine copies into the gold facts.

| Fact kind | Where the generator states it | Evidence |
| --- | --- | --- |
| Line classification: `service_item`, `tariff_code`, the Singapore supply category | the invoice line description (phrasebank), the e-invoice `classification_code` where the record has one, the PO line description | invoice id with a `lines[i]` path, or a span |
| Other line facts: classification, time and rate, scope and exemption, buyer and purpose, split | an invoice field where one exists (service period, delivery date); otherwise a phrase in the line description, the invoice notes, the PO line or a linked email | path or span |
| Contract facts (K-4, L-1, L-2, L-3 and others) | contract record fields: `signed_on`, `stamped_on`, `has_price_review_clause`, `variation_orders` and so on | contract id with a path |
| Withholding facts | `payment_nature` in the line description; `place_of_performance` and `in_country_share` in an invoice note or an email; the certificate of residence in the policy pack | path or span |
| Area facts: `recipient_zone`, `service_site_zone`, `delivery_zone` | the supplier or company master's zone, or a line fact stated in the PO or contract. Never inferred from an address (catalog README) | path |
| Party facts: registrations, MSME status, group structure, partial-exemption status, zone, e-invoice status, PE, FRP status, supplier kind, approvals | the company and supplier records, exported whole | `company:` or `supplier:` with a path |

- **Spans** come from the phrasebank assembler. It knows where it put each value phrase, so it records the character offsets in the email body or line description.
- **Value parsers.** Each fact expresser in the phrasebanks registers a parser that maps its surface phrase back to the value. A linter round-trips every variant in every language.
- **Missing on purpose.** A fact the engine needs, with no ordinary default (`ctx.need`), is stated nowhere. A party fact that is missing is exported as null, with its `*_known` flag false. The key is then HAND_OVER with that rule as basis and `answer_source: handover_by_construction`, and the gold fact is null.

**Acceptance check** (it extends the step 11 B1 check, "every internal fact the answer key depends on is stated in the exported documents"). For every case and every gold fact:

- a non-null value has at least one evidence reference that names a document of the case;
- a path resolves in the exported record and equals the value;
- a span's text parses back to the value.

For every null gold fact, no document of the case has a field or phrase that states it. For party facts, every field the engine read is present in the exported record, unless its `*_known` flag is false and the key is HAND_OVER on it.

**Scan-only cases.** The structured invoice record isn't exported, so in B1 their evidence paths point into the internal record. B3 replaces them with spans into the rendered text (decision 7). Evidence location isn't scored in v0.10, only that a cited document exists in the case.

## 3. Quotas

### 3.1 Exception mix (unchanged from v0.9)

Counts are exact per split. Within each type the countries split 50/50, largest remainder for odd counts.

| Primary type | Share | Train | Test | Hidden |
| --- | --- | --- | --- | --- |
| Clean | 40% | 800 | 200 | 120 |
| Tax problem | 10% | 200 | 50 | 30 |
| Price mismatch | 10% | 200 | 50 | 30 |
| Quantity mismatch | 8% | 160 | 40 | 24 |
| Invalid invoice / missing fields | 8% | 160 | 40 | 24 |
| Duplicate | 7% | 140 | 35 | 21 |
| Not received | 5% | 100 | 25 | 15 |
| No PO / above limit | 5% | 100 | 25 | 15 |
| Changed bank details | 4% | 80 | 20 | 12 |
| Ambiguous (HAND_OVER) | 3% | 60 | 15 | 9 |
| **Total** | 100% | 2,000 | 500 | 300 |
| **Two problems** (problem cases only; the secondary in a lower tier) | 15% | 300 | 75 | 45 |

### 3.2 Hard cases

At least half of each split, with scan-only cases at most a third of the hard cases. Counts are exact. A test checks each definition.

- **H1 scan-only:** the structured invoice record is withheld; the invoice ships only as a scan, a photo or a PDF.
- **H2 conflicting documents:** the invoice states value A for a fact a rule reads, and the governing document in the precedence table (section 3.2a) states B. The key follows B. **Counterfactual test:** re-running the engine with A substituted must change the key. So a program that only maps the invoice's fields to the engine's inputs gets the case wrong.
- **H3 missing information:** a fact the engine needs, with no ordinary default, is in no document, so the answer is HAND_OVER. H3 can only sit in Ambiguous slots: they are the only HAND_OVER slots, and a HAND_OVER case never takes a second problem (step 11 Q14).

| | Train 2,000 | Test 500 | Hidden 300 |
| --- | --- | --- | --- |
| Hard total (50%) | 1,000 | 250 | 150 |
| H1 scan-only (cap ⌊hard / 3⌋ = 333 / 83 / 50) | 320 | 80 | 48 |
| H3 missing information (inside Ambiguous 60 / 15 / 9) | 40 | 10 | 6 |
| H2 conflicting documents | 640 | 160 | 96 |

Arithmetic: 320 + 40 + 640 = 1,000; 80 + 10 + 160 = 250; 48 + 6 + 96 = 150. Every scan-only count is under its cap.

- **The rest of the Ambiguous slots** (20 / 5 / 3) hold rule HAND_OVERs that aren't a missing fact, for example a withholding case that needs one of the 131 unconfirmed Singapore treaty rows. Q-A2 to Q-A5 reasons are never planted, so in practice none come from there.
- **Q-A1 cases are not Ambiguous.** MG-5 step 2 settles them (no sales tax on the invoice). They go in ordinary slots, flagged `open_question: Q-A1`.
- **One label per case.** A case may have more than one hard kind but counts once, under the label it was assigned. The scan-only cap counts every scan-only case, whatever its label.
- **H1 spread:** in proportion to the exception types' shares, so scan-only says nothing about the decision.
- **The Ambiguous exception (decision of 23 Nov 2026, review of B1-1):** Ambiguous is about 83% hard (H3 40 + H1 10 of 60 in train), outside the 30–70% band below. H3 can only sit in Ambiguous, and H1 stays proportional across every type, so the band applies to the types that take H2. `tests/generator/test_slots.py` checks the band on those types.
- **H2 spread:**
  - H2 goes wherever a precedence pattern exists, with each exception type's hard share between 30% and 70%.
  - No precedence row takes more than 25% of a split's H2 cases (train at most 160, test at most 40, hidden at most 24). The nine rows give room for 225%.
  - `report/slots.json` gives the count per row.
- **Shortcut check:** the step 11 shortcut check (§8.5) also gets hard-kind features.

#### 3.2a Precedence table

H2 is planted only from these rows. Each row's rule names the governing source.

| Fact | The invoice says | What governs |
| --- | --- | --- |
| Supplier registration (MS-1, MG-1, SG-4) | a registration number | the supplier record on the invoice date |
| Group relation and the 5% test (MS-6, K-6) | a "group relief" note | the company record's group structure |
| Exemption certificate scope and validity (MG-4, the MS-5 declaration) | an exemption statement | the certificate in the policy pack |
| Zone (MS-7, MG-5) | a ship-to or bill-to address | the master's zone, or the line fact stated in the PO or contract |
| Contract dates and clause (K-4, L-1, L-2) | a "contract signed before …" note | the contract record |
| Time of supply (MS-3, SG-3, MG-3) | the issue date only | the goods receipt's delivery date; the contract or the service period on the invoice |
| Price (matching) | a price | the PO with its approved ERP amendments; emails don't count (policy pack) |
| Certificate of residence (WH-1, WH-5) | a "treaty resident" note | the certificate in the policy pack |
| Partial-exemption status (SG-8, SG-9) | nothing | the company record |

Anything outside the table isn't planted as H2. An example is a supplier email "correcting" a service period with no corrected invoice.

### 3.3 Mixed-tax invoices

A case counts as mixed when at least two of its lines have different treatments or bases, or one line turns on a §5-b split.

- At least 240 / 60 / 36 mixed cases (12% of each split).
- Of those, at least 80 / 20 / 12 are Malaysian §5-b split cases (a third of the 12% floor, not of every mixed case built): L-8 materials and works, L-8 installation by a sales-tax manufacturer, P-12 consultation fees, P-16 education fee items, MS-2 packages. These are floors; a split may build more of either (review of B1-5).
- Lines may book to different GL accounts (spec clarification, 18 Nov 2026), so step 11 Q6 (one GL account per invoice) no longer applies.

Lines per invoice: 1 line 45%, 2 lines 30%, 3 lines 15%, 4–6 lines 10%. The mean is about 2.0.

### 3.4 Per-rule floor

**What counts as an appearance.** A rule appears in a case when it decides a non-null outcome in the key, as one of:

- the `basis` of a tax line;
- the basis of a `WITHHOLD_TAX` action;
- the rule of a buyer action: MS-8, SG-7, SG-8, ME-3;
- the rule behind a finding: ME-1, ME-2, ME-4, SG-2, SG-11. The generator maps finding code and country to the rule, so the engine doesn't change.

A rule counts at most once per case. HAND_OVER appearances are counted and reported, but don't count toward the floor. MS-10 and MG-6 dispatch to the P-x and G-x rules and never appear as a basis themselves: they are met through those rules.

**The floor: 4 in test, 16 in train** (and 2 in hidden). Train is four times test, the same ratio as the split sizes.

| Group | Rules counted | Test demand (× 4) | Train demand (× 16) | Takes a line basis? |
| --- | --- | --- | --- | --- |
| MS-1 to MS-9 | 9 | 36 | 144 | yes |
| P-1 to P-20 (through MS-10) | 20 | 80 | 320 | yes |
| K-1 to K-8 | 8 | 32 | 128 | yes |
| L-1 to L-8 | 8 | 32 | 128 | yes |
| MG-1 to MG-5 | 5 | 20 | 80 | yes |
| G-1, G-3, G-4, G-5 (through MG-6) | 4 | 16 | 64 | yes |
| ME-1 to ME-4 | 4 | 16 | 64 | no (findings, buyer action) |
| WH-1 to WH-4 | 4 | 16 | 64 | no (buyer action) |
| **Malaysia** | **62** | **248** | **992** | |
| SG-1 to SG-12 | 12 | 48 | 192 | 11 of 12 (SG-11 is a finding) |
| WH-5 | 1 | 4 | 16 | no (buyer action) |
| **Singapore** | **13** | **52** | **208** | |
| **Total** | **75**, plus the 2 dispatchers | **300** | **1,200** | |

The 81 rule IDs of the sheet are the 75 counted rules, the 2 dispatchers (MS-10, MG-6) and the 4 rules that aren't engine rules (P-21, G-2, G-6, G-7).

**Arithmetic, Malaysia, test (250 cases):**

- about 2.0 lines per case gives about 500 line bases;
- the rules that take a line basis need 54 × 4 = 216 of them, 43% of the lines. The other lines are ordinary (MS-2, MG-2) and also count toward those two rules;
- ME-1, ME-2 and ME-4 need 3 × 4 = 12 findings; the Malaysian invalid-invoice quota is 20 cases;
- WH-1 to WH-4, ME-3 and MS-8 ride on foreign-supplier lines. 15% of Malaysian cases have a foreign supplier, about 37 in test, against 24 appearances needed. One line can carry MS-8, ME-3 and WH-2 at once.

Malaysia, train: 54 × 16 = 864 of about 2,000 line bases. Singapore, test: 11 × 4 = 44 of about 500 line bases.

**Problem-form floor.** A problem form is an appearance where the rule decides a wrongly charged or undercharged line.

- **Train: at least 2 per rule that has a problem form.**
  - Malaysia: 52 such rules, so 104 lines. Capacity: 100 Malaysian tax-primary cases, plus about 50 tax secondaries under fraud and duplicate primaries (40 + 70 Malaysian primaries in those tiers), with up to two problem lines per case. That gives about 300 lines.
  - Singapore: 6 such rules, so 12 lines, against 100 Singaporean tax-primary cases.
- **Test: at least 2 problem lines per family** (MS, K, L, P, MG/G, SG), 12 in all. A per-rule floor can't hold in test: 52 Malaysian problem-form rules against about 25 Malaysian tax-primary cases and a few secondaries.

**Rules that can't meet the floor:**

- P-21, G-2, G-6 and G-7 are not engine rules and never appear in a key. That's by design, and guard tests cover it.
- MS-10 and MG-6 never appear as a basis; their P-x and G-x rules meet it.
- No engine rule fails on capacity. These rules are narrowed by a date window or a planting limit but keep settled branches inside the window:
  - K-5 and L-7: the local-authority branch runs only 1 Jul – 30 Sep 2025; the Federal and State branch is open-ended.
  - P-20: digital banking and non-bank digital payments run to 31 Jul 2025; the JDA refund route is current.
  - MS-7 and MG-5 without Pulau 1 or Q-A2 to Q-A5: Labuan, Langkawi, Tioman, Pangkor, free zones and LMWs remain.
  - MG-3 without the three partly exempt headings.
  - WH-5 with only the 62 confirmed treaty rows, plus the domestic rates.
- B1-4 and B1-5 add a reachability test: each rule is planted on 50 draws and the engine must agree. It turns this analysis into a checked list. Any rule that fails is reported in that PR, and its floor is lowered only with Sebastian's approval.

**Date-boundary floor.** For each dated boundary in section 6: at least 2 train cases within 31 days on each side, and at least 1 test case on each side.

### 3.5 Planting limits

Each limit is a test in `tests/generator/test_planting_limits.py`, run over every generated case.

1. **No Q-A2 to Q-A5 case.** No engine result names those questions, and no master or line fact gives the zone `pulau_1`.
2. **Q-A1 only when flagged.** A case is a Q-A1 case if and only if its generator truth has `open_questions: [Q-A1]` and the engine's line result carries Q-A1.
3. **No goods line dated before 1 Sep 2018.** Neither the invoice date nor the delivery date.
4. **No partly exempt headings before 1 Jul 2025.** No `process_gauges`, `control_instruments` or `tool_bits` line dated before 1 Jul 2025.
5. **Unconfirmed treaty rows only as HAND_OVER.** A case that reads one of the 131 unconfirmed Singapore treaty rows (119 amended by a protocol, 10 with several rates, 2 with no rate) is HAND_OVER with basis WH-5, in an Ambiguous slot. No settled key reads one.
6. **The other catalog README limits:**
   - a zone never comes from an address;
   - self-billing types (a), (b), (f) and (g) only;
   - `sales_exempt` and `none` categories are never charged tax;
   - `group_relation: unclear` only on group-relief categories;
   - credit notes are clean only (step 11 Q12).
7. **Every planted WH-2 line states its service period** (`service_period_start` and `service_period_end`), since the period of performance decides services outside Malaysia (engine 0.10.3, rule sheet WH-2); a WH-2 HAND_OVER happens only where B1 leaves the period out on purpose.

B1-1 rewrites the catalog README's rules for the generator for v0.10 and links each rule to its test.

### 3.6 How the quotas combine without conflict

One deterministic allocator, `core/generator/slots.py`, fills the slot table. It is generic: it reads the demands from the TaskSetSpec and the country packs. The order:

1. **Exception type × country**, plus the exact two-problem pairs.
2. **Hard kind:** H3 only into Ambiguous slots; H1 in proportion to the exception types; H2 into slots that have a precedence pattern, within the 25% row cap.
3. **Rule-floor demands:**
   - problem forms into tax-primary and tax-secondary slots;
   - correct forms into any line of a compatible slot. Compatibility covers country, foreign supplier, company traits and date window.
4. **Mixed-tax and date-boundary demands.**

The axes interact only through these compatibility rules, so each demand is bounded by the capacity shown above. The allocator asserts every quota exactly and fails loudly if it can't place a demand. It writes `report/slots.json`, which must match the tables in this plan.

## 4. Planted = found

The step 11 rule stays: the generator plants, the engine finds independently, and any difference redraws the case. A slot gets at most 20 attempts, then the build fails.

**Compared:**

- decision and finding codes;
- for each planted line, treatment and basis;
- buyer actions, with rate and basis;
- the HAND_OVER basis;
- every gold fact against the value the registry stated.

**Measured:** `report/planting.json`, per split. For each rule (from the slot's planted rules), it records:

- attempts and redraws;
- the cause of each redraw: extra finding, treatment differs, basis differs, action differs or fact differs;
- the first five diffs.

**The build stops when:**

- any rule with at least 20 attempts has a redraw rate above 5%, or
- the overall redraw rate is above 1%, or
- any slot reaches 20 attempts.

A redraw should come only from a random draw adding a second problem by accident. Anything more points to a template or engine bug. CI shows the report on every generator PR.

## 5. Gold facts and the reference row

For every case, the generator runs `check_rules` on the key's gold facts and compares the per-line treatment, basis and buyer actions with the key. Any difference fails the build: it is one of the cross-file consistency checks (step 11 §8.4). It is the same comparison as `tests/rules/test_reference_row.py`.

It runs in:

- **B1 CI**, on the 100-case double build of every generator PR;
- **the full 2,000 / 500 build**, from B1-7;
- **B3's `build-data` release job**, as a release gate.

The published reference row ("engine on perfect facts") is scored in C.

## 6. Dates

- **Invoice dates** are drawn uniformly over the window, except rule-floor and boundary slots, which draw inside their rule's sub-window.
- **`as_of_date`** is the invoice date plus 3–21 days, capped at 18 Nov 2026 (rules as of 19 Nov 2026, engine 0.10.1; 20 Nov 2026 from engine 0.10.2).
- **Background history** starts 12 months before the window. Its rates must be right for their own dates (a §8.4 check).

**Malaysia: 2 Jan 2024 – 31 Oct 2026.** Both sides of:

- 1 Mar 2024: service tax 6% → 8%;
- the e-invoice implementation dates (1 Aug 2024, 1 Jan 2025, 1 Jul 2025, 1 Jan 2026, 1 Jul 2026) and the relaxation ends inside the window (31 Jan 2025, 30 Jun 2025, 31 Dec 2025);
- 1 Jul 2025: the 2025 SST expansion and orders, the end of MG-3's earlier orders, K-1 for sales below RM1m, the start of K-4, local authorities under K-5 and L-7 until 30 Sep 2025;
- 1 Jan 2026: rental at 6%, K-1 for RM1m to RM1.5m, G-3;
- 1 May 2026 (P-15), 1 Jun 2026 (P-7, TIA-i), 30 Jun / 1 Jul 2026 (the end of K-4, P-10);
- 31 Aug / 1 Sep 2026: G-3 ends, MG-4 Schedule B items 5 to 7 begin;
- 22 Sep 2026: P-9 for DGTA-approved organisations.

Pulau 1 (from 1 Dec 2024) isn't planted.

**Singapore: 1 Jul 2023 – 31 Oct 2026.** Both sides of 1 Jan 2024: GST 8% → 9% (SG-3).

### 6.1 Rule branches dated outside the case window

These branches are tested in the engine suite but never planted, because their whole validity lies before the window start (Malaysia 2 Jan 2024, Singapore 1 Jul 2023) or after 31 Oct 2026. The windows are not widened.

| Rule | Branch | Dates | Covered by |
| --- | --- | --- | --- |
| MS-5 | The Order before it came into force; items 1 and 2 before the own-use condition; items 3 and 4 before they began | before 1 Jan 2019; before 1 Jan 2020 | `test_out_of_window_branches.py` (engine 0.10.3) |
| MS-6 | Group relief before the 5% test of First Schedule para 8(2) | before 1 Jan 2020 | `test_out_of_window_branches.py` (engine 0.10.3) |
| MS-7 | JDA exemption for the MTJA and JDA companies (Service Tax Policy 1/2021) | 1 May 2021 – 14 Aug 2022 | `test_my_areas.py` (JDA dates 30 Apr / 3 May 2021) |
| MS-7 | Item 3 exclusions before 1 Jan 2020 (public premises only for educational, training or welfare purposes; no employer-accommodation exclusion) | before 1 Jan 2020 | `test_my_areas.py::test_ms7_item3_statutory_body_and_private_hei_premises` |
| MS-7 | Item 3 before the words "in special areas" (232/2018) | 1–5 Sep 2018 | `test_my_areas.py` |
| MS-7 | Item 5: customs agent approved under s90 before s90(2) | before 1 Jan 2020 | `test_my_areas.py` |
| MS-7, MG-5 | Pangkor before it became a designated area | before 1 Jan 2020 | `test_my_areas.py` |
| P-20 | Labuan imported services | to 31 Dec 2021 | `test_my_policies.py::test_p20_labuan_imported_services_to_2021` |
| MG-3 | The 2018 orders (rates and goods exempted) | 1 Sep 2018 – 31 May 2022 | `test_goods_before_2025.py` |
| MG-3 | Goods invoiced before sales tax began: HAND_OVER | before 1 Sep 2018 | `test_goods_before_2025.py::test_goods_invoiced_before_sales_tax_began_are_not_settled` |
| MG-5 | DA order: wine, spirits, beer, malt liquor and tobacco into all DAs | 1 Sep 2018 – 26 Mar 2019 | `test_my_areas.py` |
| MG-5 | DA order: petroleum into the DAs | 1 Jan 2020 – 31 Dec 2020 | `test_my_areas.py` |
| MG-5 | Preparations "not containing nicotine" (DA order 420/2020, free-zone order 349/2021) | to 31 Mar 2023 | `test_my_areas.py` |
| MG-5 | SA order Schedule A goods into a free zone only, before licensed warehouses and LMWs were added | before 1 Jan 2019 | `test_my_areas.py` |
| ME-1 | Up-to-RM5m relaxation end, and implementation dates of new businesses after the window | 31 Dec 2027 and later | `test_my_einvoice.py` (engine 0.10.2, PR #21) |
| L-1 | Non-reviewable contracts after the exemption ends | from 1 Jul 2027 | `test_my_construction.py` |
| P-9 | MRO exemption after it ends | from 1 Jan 2028 | `test_my_policies.py` (P-9, 10 Jan 2028) |
| WH-2 | Services outside Malaysia before 17 Jan 2017 and 17 Jan – 5 Sep 2017; grossing-up before 5 Dec 2018 | before 6 Sep 2017; before 5 Dec 2018 | `test_out_of_window_branches.py`, `test_dates_sg_wh.py` (engine 0.10.3) |
| SG-3 | GST at 7%, and the 7% → 8% change | before 1 Jan 2023 | `test_sg_gst.py` (7% on 20 Dec 2022) |
| SG-6 | (u) advertising substantially outside Singapore | before 1 Jan 2022 | `test_sg_gst.py` (s21(3)(u) on 10 Nov 2021 and 10 Feb 2022) |
| SG-6 | (c) insuring passenger transport, and (e) accommodation booking, before the 2023 changes | before 1 Jan 2023 | `test_out_of_window_branches.py` (engine 0.10.3) |
| MS-8 | No tax on imported services before 1 Jan 2019 | before 1 Jan 2019 | `test_scope_changes.py` (engine 0.10.3) |
| ME-4 | Reg 10(1A) before its substitution on 1 Sep 2019 (the earlier text is not archived; nothing for the case data) | before 1 Sep 2019 | none: before both windows, not planted |
| K-2 | The one-year new-SME exemption across 29 Feb 2028 | 2028 | `test_dates_mg_me.py` (engine 0.10.3) |
| SG-8 | Reverse charge before low-value goods were included | before 1 Jan 2023 | `test_sg_claims.py` (low-value goods on 10 Nov 2022) |
| SG-10 | Before the private-hire and third-party-car exceptions | before 1 Apr 2022; before 1 Jan 2023 | `test_sg_claims.py` (10 Mar 2022, 10 Dec 2022) |

The "Covered by" column names the engine test (checked against main on 20 Nov 2026; the four branches without a test then got one in engine 0.10.3, 22 Nov 2026, with the full date sweep). Every row except ME-4 now has a test; the card says so. In B1-7 a test re-parses the sheet's dated items and fails if one lies wholly outside a window without a row here. B1-7 also copies the table into the card draft as "rule branches dated outside the case window, tested in the engine suite but not planted".

## 7. Build order

B1 is split into PRs of reviewable size, as A12 was. Each PR is reviewed and merged before the next.

| PR | Contents | Acceptance |
| --- | --- | --- |
| **B1-1** Core framework | derived seeds, `release-seeds.yaml`, pipeline hash; the slot allocator (section 3.6); the TaskSetSpec gains generic `hard_cases` and `rule_floor` config; `db-generate` skeleton; the catalog README's v0.10 limits | the allocator gives the exact tables of section 3 for 2,000 / 500 / 300; an infeasible demand fails loudly; core names no country (`test_shared_code.py`) |
| **B1-2** Entities and the clean base | companies (60 / 20 / 12, half per country) with party facts, including the supplier's e-invoice status from engine 0.10.2; suppliers, people, the policy pack (certificates, certificates of residence), POs, receipts, contracts, history, background mail; the statement registry with paths; one clean case per country | 500 clean cases per country with planted = found; every gold fact's evidence resolves; reference row green; 100 cases built twice byte-identical |
| **B1-3** Ops and the non-tax families | the op library; the template loader with `expect`; starter families for price, quantity, not received, duplicate, changed bank details, routing and invalid invoices; two-problem pairs; planted = found on the v0.10 fields; the redraw report | exception mix and two-problem counts exact; redraw thresholds hold |
| **B1-4** Malaysian tax families | one starter family per MS, K, L, P, MG, G, ME and WH-1 to WH-4 rule; floor allocation; the reachability test; planting-limit tests 1–4 and 6 | Malaysian floors met; reachability report; limit tests green |
| **B1-5** Singaporean tax and mixed invoices | SG-1 to SG-12; WH-5, with unconfirmed treaty rows as HAND_OVER (limit 5); mixed-tax and §5-b cases | Singaporean floors, mixed quota and limit 5 met |
| **B1-6** Hard cases | the H1 export flag; H2 from the precedence table with the counterfactual test; H3; starter phrasebanks with fact expressers, spans and value parsers | hard quotas exact; scan-only cap; counterfactual test on every H2; null-fact check on every H3; span round-trip |
| **B1-7** Export and the full build | the v0.10 parquet columns; `check_public` staged mode; the full 2,000 / 500 build, twice; the reference row on every case; the CI job (100-case double build plus reference row); the out-of-window table in the card draft (section 6.1) | every B1 check of the step 11 plan, plus sections 2.3, 3, 4 and 5 of this plan |

**Later PRs, where v0.10 changes them:**

- **B2 (text content):** fact expressers with value parsers for every line-fact field of both country parts in every language; a family per rule; the round-trip linter. The shortcut check adds hard-kind and rule features.
  - From the B1-2 review: Singapore GST registration numbers use a random check letter (`countries/sg/generation.py`); B2 gives them the real check-character format.
- **B3 (rendering and data alpha):** scan-only cases render without a structured record, as 40% scans, 30% photos and 30% PDFs only (decision 11); spans for scan-only evidence; the reference row as a release gate; the card states the hard share and the engine version; the release tag is `v0.10.0-alpha.N`.
- **C (scorer):** the extra columns (per line, buyer actions, facts), the two lanes, the labelled reference row, `results.schema.json` v0.10.
- **D1 (environment):** the `check_rules` MCP tool (variant b), tools for the company and contract records, the rule sheet in the policy folder.
- **D2 (graders):** the rubric is unchanged.

## 8. Decisions (review of the draft, 20 Nov 2026)

The reviewer checked the arithmetic and accepted every recommendation of section 8a, with these specifics:

- **1.** H2 definition and precedence table approved as drafted.
- **2.** H3 capped by the Ambiguous share: yes.
- **3.** Companies: 60 / 20 / 12.
- **4.** Closed by engine 0.10.2. The rule sheet now states the e-invoice phases, exemptions and interim relaxation periods (ME-1, rewritten 20 Nov 2026 from the archived LHDN timeline page, e-Invoice Guideline v4.6 and Specific Guideline v4.9). Engine 0.10.2 corrects ME-1 inside the relaxation periods. ME-1 is planted normally, inside and outside relaxation periods.
- **5.** Floor 16 / 4 / 2; problem-form floors as drafted.
- **6.** Date windows as drafted. Singapore stays at 1 Jul 2023.
- **7.** Scan-only evidence: paths in B1, spans from B3.
- **8.** `planted_rules`, `hard_kinds` and `open_questions` exported in train and test. Never in hidden: the hidden repo's export is separate.
- **9–13.** As recommended.

The review also made three changes, applied above: Q-A1 cases go in ordinary slots, not Ambiguous (section 3.2); rule branches dated outside the windows are listed, not planted (section 6.1); no precedence row takes more than 25% of the H2 cases (section 3.2).

## 8b. Built in B1-4 (Malaysian tax families), for review

Choices made while building B1-4 that the plan didn't fix. None changes a rule or an answer; each is tested.

- **Facts stated as phrases.** A line fact no structured field holds (e.g. `financial_charge`, `residential`, `delivery_zone`) is stated as a phrase from a committed phrasebank (`content/phrasebanks/facts/MY.yaml`, English starter set) appended to the invoice line description. Its evidence is the invoice and that field's path; the acceptance check reads the text back to the value with the fact's parser (section 2.3: a path either equals the value or holds a text that parses back to it). B1-6 adds spans, variants and languages.
- **MS-9 and K-8 have no correct form.** Undercharged service tax (MS-9) and the unregistered co-owner who invoices (K-8, STP 4/2026) appear only as problems, so their whole floor (16 / 4 / 2) is problem forms on tax slots (`correct_form: false` in rules.yaml). The other 50 problem-form rules keep 2 problems per rule in train and 2 per family in test.
- **Rule windows.** Each rule's planting window per form is in rules.yaml, inside the rule sheet's dates (e.g. K-4 1 Jul 2025 to 30 Jun 2026, P-20 to 31 Jul 2025, G-3 1 Jan to 31 Aug 2026). Some are narrower than the rule, to stay clear of a neighbouring branch: G(n) and Group J lines from 1 Apr 2024 (after the STP 1/2024 transitional exemption), MS-3 a service provided in February 2024 and invoiced 1 Mar to 31 May 2024. The allocator gives each slot a date inside every rule window it carries.
- **Special suppliers and company kinds.** Rules that need a particular supplier (the Federal or State Government, a local authority, a developer/JMB, approved MRO organisations, a recognised training centre, a group company, a landlord and a contractor with transitional contracts, an unregistered co-owner, a supplier newly registered in March 2024, foreign suppliers with and without a certificate of residence or a permanent establishment) use the split's suppliers of that kind: three per kind in train, two in test, one in a 300-case split (generation.yaml `special_suppliers`), shared by its Malaysian companies. Rules that need a particular company use the company kinds (`it`, `builder` and `fin` provide B2B or financial services; `msme` and `new_sme` are SME tenants; `plain`), given to the companies in turn so a 300-case split has one of each. A slot never mixes two supplier kinds, or a rule with a supplier kind whose own rule would decide first (generation.yaml `supplier_lacks`: the Government's 2025-scope exemptions, group relief and the transitional contracts before the B2B order).
- **Companies' own e-invoicing phase (engine 0.10.4).** Each company's turnover fits its kind: the SME kinds are below RM3m (exempt, they never self-bill), the others spread over the four phases (above RM100m from 1 Aug 2024, RM25m-100m from 1 Jan 2025, RM5m-25m from 1 Jul 2025, RM3m-5m from 1 Jan 2026). ME-3 applies from the company's own implementation date, taken from the ME-1 timeline. Only the `plain` companies are registered ship owners (P-9).
- **Foreign suppliers.** Foreign-supplier slots carry foreign invoices: imported services the buyer accounts for (MS-8), self-billed where the buyer is in its phase (ME-3), with withholding where the payment's nature calls for it. Each invoice is in its supplier's currency (SGD, CNY, JPY, USD, GBP, INR) and states an exchange rate that moves by up to 5% around a centre from day to day; the approval check reads it as printed. Invalid-invoice slots are never foreign: the invoice requirements (e-invoice, SST particulars) bind domestic suppliers.
- **Dated branches.** Each dated boundary inside the Malaysian window (generation.yaml `boundaries`) carries a branch recipe: a line whose answer turns on the date, planted on the boundary's slots on each side (2 per side in train, 1 in test). 1 Sep 2025 (P-9 for foreign-company buyers) has none: the buyers are Malaysian companies.
- **Tax slots keep a line for their problem.** The allocator reserves one line of a tax slot for its tax problem (a floor problem form or the family drawn), places the rules that can share a slot with the fewest others first, and gives each problem form the tightest slot that fits. Every Malaysian floor is met in 2,000, 500 and 300-case splits and in 38 allocation seeds tried.

## 8c. Built in B1-5 (Singapore tax families, mixed invoices), for review

- **SG-12 has no correct form** (GST left off a standard-rated supply appears only as a problem): its whole floor is problem forms, as for MS-9 and K-8.
- **Singapore tax slots are domestic.** A Singapore tax problem needs a GST-registered supplier, except SG-4, which decides every line of the invoice and so can't carry the slot's other rules; generation.yaml `foreign_countries: [MY]` on the tax type.
- **Invalid-invoice slots exclude the charged-line rules** SG-1, SG-3, SG-9, SG-10 and SG-4: a missing tax-invoice particular makes every Singapore line with GST SG-2, so those rules wouldn't decide their line there (rules.yaml `exclude_types`).
- **Partially exempt buyers** state the attribution of each claimable purchase (SG-9); their claims are SG-9, not SG-1.
- **Mixed quota.** Read as counts: at least 240 / 60 / 36 mixed cases and at least 80 / 20 / 12 Malaysian §5-b split cases (generation.yaml `mixed`). The built splits have 693 / 162 / 102 mixed cases (most from lines with different rules) and 124 / 32 / 19 split cases. If "a third of those" means a third of every mixed case, the split share would need raising to about 230 in train.
- **Limit 5** has its own Ambiguous-slot family on foreign-supplier slots: 3 / 1 / 1 cases in 2,000 / 500 / 300.

### Review of B1-5: every branch the engine decides, planted or explained

- **Branch table.** `generator/branches.py` reads every branch off each country's engine code (the files and helpers the pack names): a decision (a call that builds an outcome naming its rule, one row per conditional outcome and per call site of a helper), a hand-over (`NotSettled`, and one "fact not shown" row per rule), a path (each return of a function the pack names as a rule's deciding function: SG-4's reasons, SG-8's credit test, ME-1's phase, ME-3's buyer phase) and a fact path (a deciding fact read on a shared line of code, or an invoice particular a finding names). Re-running the engine on each built case under a tracer counts the cases planting each one. `db-generate` writes it to `report/branches.json`.
- **Floor.** Each in-window branch: at least 2 cases in train and 1 in test. A rule whose recipe takes several branches in turn declares them (rules.yaml `branches`), and the floor gives it 2 / 1 appearances per branch. Deterministic turns (`ops.Turns`) spread the branches evenly; a redraw moves on by its attempt number.
- **Below the floor** (`content/generator/branch_reasons.yaml`, kept current by `tests/generator/test_branch_coverage.py`): 16 Malaysian and 1 Singaporean branch, none planted. Ten are outside the case window (imported services before 2019, Labuan to 2021, WH-2 before 5 Dec 2018, an FRP before B2B item 3); four need company facts no generated company has (a Labuan FSA buyer, a buyer not registered for service tax, a company record without its phase, a company exempt from e-invoicing); three are invoices the generator doesn't build or the key can't show (a domestic invoice in another currency in each country, and a line without a description, whose finding the key names ME-2). Hand-over branches are HAND_OVER only.
- **Allocator additions** (generic): per-branch floors, date windows taken in turn (`window_turns`), appearances alternating foreign and domestic (`alternate_foreign`), cases a rule plants alone (`alone`, `alone_with`), the fewest lines (`min_lines`), per-form supplier needs (`form_needs`); a boundary branch that brings a finding avoids slots with a finding rule; a foreign action rule counts a line of its own; three in four one-line tax slots swap line counts with an untaxed slot (the plan's line counts are unchanged), so the problem branches have room.
- **Singapore (A-D).** SG-4: not registered, a GST number that isn't the registration, an OVR vendor (new supplier kind), in turn; a registration ended before the invoice date is the engine's not-registered path. SG-8: imported services, low-value goods and other imported goods; three new company kinds (meeting de minimis; in a GST group without full credit, fully taxable or meeting de minimis). SG-9: a de minimis buyer states its attribution and claims in full (the engine names SG-1). SG-10: eleven branches, the always-disallowed classes and each claimable exception and its disallowed side.
- **Malaysia.** Branches added to MS-1 to MS-5, MS-8, MS-9, P-14, P-16, P-20 (the 26-29 Feb 2024 transitional exemption), L-2, L-5, L-8, MG-1, MG-3, MG-5, G-4, WH-2, WH-4, ME-2 and ME-4, with new special suppliers (a late registrant, foreign registered persons in and out of the group, a group company abroad, three e-invoicing statuses, manufacturers on Langkawi, in a free zone and in the JDA) and four ME-1 boundaries (an ordinary invoice that needs no e-invoice yet).
- **Engine stop, not planted.** MS-3: a line charging no tax for a service paid in full before the 1 Jul 2025 scope start. Sheet MS-3 (reg 3A) says that payment is not taxed; the engine answers MS-9 (undercharged), because `service_tax.assess` checks prepayments only on a line that charges tax. The charged form (no tax was due) is planted.
- **The generator calls the engine's `buyer_in_phase`** for self-billing instead of its own copy.

## 8a. Questions as raised

1. **H2 definition.** H2 means the counterfactual key differs, and H2 is planted only from the precedence table in section 3.2a. *Recommended: yes; Sebastian approves the table.*
2. **H3 and the Ambiguous share.** H3 is capped by the 3% Ambiguous share (40 / 10 / 6), so H2 carries most of the hard share. Raising the Ambiguous share would change the spec. *Recommended: accept the cap.*
3. **Company counts.** The party-fact rules need varied companies: K-1 and K-2 MSME bands, MS-6 groups, MS-7 zones, SG-9 statuses, P-9 buyer kinds, ME-3 phases. *Recommended: train 60 (30 per country), test 20 (10 per country), hidden 12, instead of 40 / 10 / 6.*
4. **E-invoice timeline.** ME-1 said "mandatory phase … (timeline)" without listing the phases or turnover bands. *Recommended: add the LHDN timeline to the sheet as a clarification, with pack data from an archived source, before B1-4.*
5. **Floor.** 4 in test, 16 in train, 2 in hidden; a problem-form floor per rule in train (at least 2) and per family in test (at least 2). *Recommended: yes.*
6. **Date windows.** Malaysia 2 Jan 2024 – 31 Oct 2026, Singapore 1 Jul 2023 – 31 Oct 2026, `as_of_date` no later than 18 Nov 2026. *Recommended: yes.*
7. **Scan-only evidence.** Paths into the internal record in B1; spans into the rendered text from B3. *Recommended: yes.*
8. **Planting columns.** Export `planted_rules`, `hard_kinds` and `open_questions` like `exception_types`, so Q-A1 cases can be dropped if the accountant review overturns the reading. *Recommended: yes.*
9. **Redraw stop rule.** A rule above 5% (at 20 or more attempts), overall above 1%, or 20 attempts on one slot. *Recommended: yes.*
10. **Mixed-tax quota.** At least 12% per split, a third of it Malaysian §5-b cases. *Recommended: yes.*
11. **Scan-only file mix.** 40% scans, 30% photos, 30% PDFs only. Cases that aren't scan-only ship the structured record and a digital PDF, as the spec's Modality section says; this replaces step 11 Q21. *Recommended: yes.*
12. **The agent track on H3 cases.** The spec says the missing fact "must be looked up or asked for", but both tracks share one key. *Recommended: colleagues don't know the missing fact, or point to the records (step 11 Q13 stays), so the key stays HAND_OVER in both tracks.*
13. **The catalog README's v0.9 limits** (no rental; construction contracts only from 1 Jul 2025) contradict the v0.10 K and L rules. *Recommended: B1-1 replaces them with the v0.10 limits, each backed by a test.*
