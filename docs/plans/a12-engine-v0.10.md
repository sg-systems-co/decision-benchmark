# Step A12 — rules engine for rule sheet v0.10 (plan)

Status: draft for review, 17 Nov 2026. Inputs: [spec v0.10](../task-sets/ap-invoices/spec-v0.10.md), [rule sheet v0.10](../tax-rules-v0.10.md) (incl. §0.1a), schemas `schemas/ap-invoices/v0.10/`. No code in this step.

## 1. What A12 delivers

- The engine applies every rule in the sheet; where a case's documents don't settle a rule, HAND_OVER. Nothing guesses.
- Per case: `tax_lines` with `basis`, the case-level worst line by `x-severity-order`, `buyer_actions`, gold `facts` with evidence, `engine_version`, `rules_version`.
- `check_rules`: the same code path as the keys, for agent variant (b).
- Typed models for every fact the rules read; treaty rates as data with a per-row `confirmed` flag.
- Tests: positive + near-miss per rule ID, coverage test, date boundaries, golden keys, version guard, reference-row check.

## 2. Findings from the current engine (what changes and why)

| Today (v0.9) | Problem for v0.10 | Change |
| --- | --- | --- |
| `TaxResult` holds one `treatment` per case (`findings.py`); MY `PRECEDENCE`, SG early returns | Spec needs one treatment per line + worst line | Per-line `LineResult`; case summary computed generically from the pack's severity order |
| `InvoiceLine.facts: dict[str, bool \| None]`, names like `same_service_unclear` | Spec's `facts.lines` has typed fields with evidence | Typed `MyLineFacts` / `SgLineFacts` exactly as `$defs/line_facts`, each field a `LineFact[T]` (value + evidence) |
| Tax rules read the line's catalog `category` | `check_rules` gets facts, not categories | Rules read classification from line facts (`service_item`, `tariff_code`, `exempt_supply`, ...); the catalog supplies defaults and GL only |
| `UnsupportedCase` for sales tax by a registered non-manufacturer, non-standard GST rates, mixed SG lines, unknown group relation | These are now rules (MG-1, SG-3, §5, MS-6) | Remove each raise in the commit that adds its rule |
| `test_shared_code.py` forbids MY/SG/GST/SST in shared code | Rule IDs like `SG-3` would trip it | Rule IDs and registries live only in the country packs; shared code handles opaque rule IDs |
| Keys carry no versions; no golden file | Spec: a key change needs a version bump | Golden keys + version guard (§9) |
| C1 (`G(n)` in group relief) and C2 (no 30 kg courier limit) | Already applied in A11 (`GROUP_RELIEF_ITEMS`, `maintenance_repair`, catalog README) | Regression tests only |
| Generator not built (B1) | Reference-row check needs generated cases | Check runs over the fixture suite now; B1 wires it to every generated case |

Existing keys: the current suite produces **132 answer keys in 126 tests** (counted by instrumenting `answer_case`): 33 table rows, 37 misc, 27 B2B/insurance, 17 priority, 5 worked-example, 4 MY-scope, 3 task-set. The plan snapshots all of them (§4.4).

## 3. Architecture

Shared (no country names, existing test stays):

- `models/evidence.py`: `EvidenceRef` (doc_id; path or span; quote) and `LineFact[T]` (value, evidence), mirroring `$defs/evidence` and `$defs/fact`.
- `rules/facts.py`: `FactReader` — every rule reads facts through it. It records each field read (for gold facts and `missing`), returns the value, and turns null into an `Unsettled` for that line.
- `rules/lines.py`: runs the pack's line rules, builds `LineResult(line_no, treatment, basis, buyer_actions, read, missing, findings)`, the case-level worst line by `pack.severity_order`, and the decision (most severe line; §5 of the sheet).
- `rules/registry.py`: `RuleSpec(rule_id, valid_from, valid_to, outcomes, reads)`; generic, filled by each pack.
- `rules/check.py`: `check_rules` (§8).
- `versions.py`: `ENGINE_VERSION` (= package version), `RULES_VERSION` from the TaskSetSpec.

Country packs (`countries/my/rules/`, `countries/sg/rules/`): one module per area, each registering its `RuleSpec`s; `severity_order` equals the schema part's `x-severity-order` (test). Withholding is a pack module in each country; the treaty tables stay in `countries/<c>/data/`.

## 4. Coverage table (one row per rule ID, plus §5)

Sources: **L** line fact (schema name in `$defs/line_facts`), **I** invoice / e-invoice block, **S** supplier master, **C** company master, **K** contract record, **D** documents (certificates, emails, customs forms), **T** data table. "New" = new model field (§5 lists types). Module paths are under `countries/my/rules/` or `countries/sg/rules/` unless shared.

### 4.1 Malaysia — service tax (MS)

| Rule | Lives in | Facts read (source) | New model fields | Outcome / actions | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| MS-1 | my/service_tax.py | L `service_item`; S SST registration on invoice date; I tax charged | S `MySupplierFacts.registration_known` | SST_SUPPLIER_NOT_REGISTERED; SST_SHOULD_BE_EXEMPT; NO_SST | registration status unknown | from 2018-09-01 |
| MS-2 | my/service_tax.py | L `service_item`, `fb_content`, `package_single_price`, `financial_charge` (card); I rate; S operator group | catalog `MyTaxProfile.rates` (dated) | SST_CORRECT; SST_WRONG_RATE | Group A–E subitem not shown | 6% list per Rate Order; rental 6% from 2026-01-01 |
| MS-3 | my/service_tax.py | L `service_period_start/end`, `amount_paid_before_change`; I issue date | — | SST_CORRECT; SST_WRONG_RATE | service period unknown on a spanning invoice | change dates 2024-03-01, 2025-07-01, 2026-01-01 |
| MS-4 | my/service_tax.py (+ groups.py) | L `service_item`, `subject_outside_malaysia`, `statutory_fee_amount`, `residential`, `air_route`, `carriage`, `patient_citizen`, `student_citizen`, `oku_holder`, `financial_charge`, `asset_type`, `asset_in_malaysia`, `financial_lease`, `education_fee_item`; S supplier kind | spec changes 2–5, 10, 21, 22 (§5.4) | SST_SHOULD_BE_EXEMPT; SST_CORRECT; NO_SST | any exclusion fact null | per item: C karaoke from 2024-02-26; H, K, L, M from 2025-07-01; G(n) residential text 2025 |
| MS-5 | my/b2b.py | L `same_service_as_buyer`, `personal_use`, `sublet`, `sublet_share`; C SST registration, `services_provided`, Labuan FSA; D B2B declaration | C `labuan_fsa_regulated`; spec change 6 (`own_use`) | SST_SHOULD_BE_EXEMPT | purpose or "same service" null | items 1–2 2019; 3 2019/2020; 4 2019; 5 2024; 6, 8, 9 2025-07-01 |
| MS-6 | my/group_relief.py | C group structure; S group link, external share ≤ 5%; L `service_item` (+ sub-item for (i)) | C `group: GroupStructure`; S `group_company_id`, `external_share_within_5pct`; spec change 5 | NO_SST / SST_SHOULD_BE_EXEMPT if charged; imported group G not taxable (para 3A) | relation or 5% status unknown | (n) from 2024-05-01; para 8(2) from 2020-01-01 |
| MS-7 | my/areas.py | C, S zone and address | C/S `zone: MyZone`, `zone_known` | NO_SST / SST_SHOULD_BE_EXEMPT | address inside a known zone, status unknown | DA/SA orders, JDA refund route from 2022-08-15 |
| MS-8 | my/imported.py | S country, FRP status; C `services_provided`, Group H registration; L `same_service_as_buyer`, `supplier_paid` | S `is_foreign_registered_person`, `frp_supplies_outsiders_in_my` | SST_BUYER_ACCOUNTS + ACCOUNT_IMPORTED_SERVICE_TAX; NO_SST (exceptions); SST_CORRECT (STP 3/2020) | any deciding fact unknown | s26A from 2019; STP 1/2025 item 6 from 2025-07-01 |
| MS-9 | my/service_tax.py, my/sales_tax.py | as MS-1/MS-2 and MG-1/MG-2, tax not charged | — | SST_UNDERCHARGED (REQUEST_CORRECTED_INVOICE) | taxability unknown | — |
| MS-10 | my/policies.py | dispatches P-1 … P-21 | — | SST_SHOULD_BE_EXEMPT when a P rule holds and tax was charged | as each P rule | as each P rule |

### 4.2 Malaysia — rental (K) and construction (L)

| Rule | Lives in | Facts read (source) | New model fields | Outcome / actions | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| K-1 | my/rental.py | C MSME: MyPMK registration and date, sales band, year of assessment, paid-up capital, group holding | C `msme: MsmeStatus` | SST_SHOULD_BE_EXEMPT / NO_SST | any MSME fact unknown | < RM1m from 2025-07-01; RM1m–1.5m from 2026-01-01; backdating if registered by 2026-12-31 |
| K-2 | my/rental.py | C SSM registration date, capital, group holding, MyPMK | C `msme.ssm_registered_on` | as K-1 | unknown | from 2026-01-01; 1 year from SSM registration |
| K-3 | my/rental.py | L `asset_type` | — | as K-1 | asset type null | from 2025-07-01 |
| K-4 | my/rental.py | K signed, stamped, price-review clause, states service/value/period, end; L `contract_signed`, `contract_stamped`, `price_review_clause` | `ContractRecord` (§5.2) | as K-1 | contract facts unknown | 2025-07-01–2026-06-30; signed/stamped by 2025-06-09 |
| K-5 | my/rental.py | S supplier kind (federal/state, local authority) | S `supplier_kind` | NO_SST / SST_SHOULD_BE_EXEMPT | kind unknown | federal/state from 2025-07-01; local authority 2025-07-01–2025-09-30 |
| K-6 | my/rental.py | as MS-6 (group, 5% test); S not a foreign registered person | as MS-6 | as K-1 | as MS-6 | from 2025-07-01 |
| K-7 | my/rental.py | L `asset_in_malaysia` | — | NO_SST / SST_SHOULD_BE_EXEMPT | location null | STP 8/2025 date |
| K-8 | my/rental.py | I supplier block, K co-owners | `ContractRecord.parties` | supplier identity for MS-1 | co-owner split not shown | STP 4/2026 date |
| L-1 | my/construction.py | K signed (< 2025-07-01), stamped (< 2025-12-31), clause, VOs, EOTs; L `contract_*` | `ContractRecord.variation_orders`, `extensions_of_time`; spec change 7 | SST_SHOULD_BE_EXEMPT / NO_SST | any contract fact unknown | to 2027-06-30 |
| L-2 | my/construction.py | L `residential_share`; K mixed-development statement | spec change 8 | apportioned: residential part exempt | split or statement missing | STP 3/2025 |
| L-3 | my/construction.py | L `design_and_build`, `exemption_statement_on_invoice`; L `service_item` G(a),(c)–(g),(i),(n) | — | NO_SST / SST_SHOULD_BE_EXEMPT | statement or numbers missing | STP 3/2025 |
| L-4 | my/construction.py | L `place_of_worship` | — | as L-3 | null | STP 3/2025 |
| L-5 | my/construction.py | L `residential`; I recipient name and residential address | — | as L-3 | address not on invoice | from 2025-07-01 |
| L-6 | my/construction.py | L `client_established_in_malaysia`, `exemption_statement_on_invoice` | — | as L-3 | null | STP 5/2026 date |
| L-7 | my/construction.py | S/C government kind | as K-5 | as K-5 | unknown | federal/state from 2025-07-01; local authority to 2025-09-30 |
| L-8 | my/construction.py | L `materials_works_separated`, `installation_separated`; S manufacturer, sales-tax registration; spec change 9 (ship/platform election) | — | work only taxed if separated; whole value otherwise (service or sales tax) | split not shown → whole invoice taxed (not HAND_OVER, per §5); election not shown → HAND_OVER | STP 7/2025 date |

### 4.3 Malaysia — Ministerial exemptions (P)

All in `my/policies.py`. Outcome when the rule holds and tax was charged: SST_SHOULD_BE_EXEMPT; when it holds and no tax: NO_SST.

| Rule | Facts read (source) | New model fields | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- |
| P-1 | C Group H registration; L `financial_charge`, spec change 12 (`financial_use`) | spec change 12 | use unknown | STP 1/2025 item 5 |
| P-2 | L `financial_charge` (extended enum) | spec change 11 | charge type null | STP 1/2025 item 7 |
| P-3 | S provider registered; L `financial_charge`, spec change 11 | spec change 11 | structure fact null | item 8 |
| P-4 | L `financial_charge` (ASNB fund management) | spec change 11 | null | item 9 |
| P-5 | L `financial_charge` (government securities, not advisory) | spec change 11 | null | item 10 |
| P-6 | C insurer; L `financial_charge` reinsurance, `financial_use` | spec changes 11–12 | use null | item 11 |
| P-7 | L `financial_charge` (Bursa brokerage, commodity platform, TIA-i) | spec change 11 | null | TIA-i from 2026-06-01 |
| P-8 | S supplier kind | S `supplier_kind` | unknown | from 2025-07-01; local authorities to 2025-09-30 |
| P-9 | L `mro_aircraft_ship`; C buyer kind (AOC airline, ship-owner, government, foreign company); S approvals (CAAM AMO, MIDA shipyard, DGTA AMO) | C `buyer_kinds`; S `approvals` | any fact unknown | MIDA from 2024-03-01; foreign company from 2025-09-01; DGTA from 2026-09-22; to 2027-12-31 |
| P-10 | L `building_charge`, `residential`; S developer/JMB/MC | S `supplier_kind` | null | from 2026-07-01 |
| P-11 | L `building_charge`, `residential` | — | null | STP 5/2024 |
| P-12 | L `itemised_consultation_fee`, `service_item` I14 | — | not itemised → whole invoice taxed (not HAND_OVER) | STP 5/2025 |
| P-13 | spec change 13 (`patient_category`) | spec change 13 | category null | STP 5/2025 |
| P-14 | spec change 13 (`medical_aid`, `referral_walk_in`), `patient_citizen` | spec change 13 | null | STP 6/2025 |
| P-15 | L `service_item` G(i) health-exam management | — | — | taxable from 2026-05-01 |
| P-16 | L `education_fee_item`; spec change 14 (`fully_sponsored`, diplomat child) | spec change 14 | null | STP 4/2025 |
| P-17 | L `oku_holder`; S registered/recognised centre | S `recognised_training_centre` | null | STP 6/2020 |
| P-18 | L `carriage` | — | null | STP 4/2024 |
| P-19 | spec change 15 (`digital_content_type`) | spec change 15 | null | STP 4/2020, 5/2020 |
| P-20 | L `service_item`, `financial_charge`; I date | — | — | dated: banking digital to 2025-07-31; non-bank digital payments 2022-08-01–2025-07-31; Labuan imported to 2021-12-31; JDA refund route from 2022-08-15 |
| P-21 | — | — | — | **not an engine rule**: the sheet says "not a company purchase; recorded for completeness"; never planted |

### 4.4 Malaysia — sales tax (MG, G) and e-invoices (ME)

| Rule | Lives in | Facts read (source) | New model fields | Outcome / actions | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| MG-1 | my/sales_tax.py | S sales-tax registration, manufacturer; spec change 1 (`manufactured_by_supplier`) | S `registration_known` | SST_SUPPLIER_NOT_REGISTERED; SST_NOT_CHARGEABLE_BY_TRADER; SST_UNDERCHARGED via MS-9 | supplier type unknown with tax charged | — |
| MG-2 | my/sales_tax.py | L `tariff_code`; T rate and exemption orders | T `sales_tax_rates.yaml` (rate orders), existing exempt-codes table | SST_CORRECT; SST_WRONG_RATE; SST_SHOULD_BE_EXEMPT | tariff code null | rate orders from 2025-07-01, amendments 2026 |
| MG-3 | my/sales_tax.py | I issue date; L `delivery_date` | — | SST_CORRECT / SST_WRONG_RATE / NO_SST | dates unknown on a crossing invoice | 2025-07-01; 2026-01-01 exemptions |
| MG-4 | my/sales_tax.py | D certificates (Schedule A item, B, C; scope; validity); C manufacturer | policy cert kinds `schedule_a`, `schedule_b` with item numbers and tariff/category scope | SST_SHOULD_BE_EXEMPT | goods inside scope unknown | per certificate validity |
| MG-5 | my/areas.py | C, S zone | as MS-7 | NO_SST / SST_SHOULD_BE_EXEMPT | zone status unknown | DA/SA orders |
| MG-6 | my/sales_tax.py | dispatches G-1 … G-7 | — | as G rules | as G rules | as G rules |
| G-1 | my/sales_tax.py | L `tariff_code` 8711.20.96 00 / 8711.20.99 00 | — | SST_SHOULD_BE_EXEMPT / NO_SST | code null | from 2025-07-01 |
| G-2 | — | — | — | **not an engine rule**: import-stage exemption of soya beans; customs and import permits are out of scope (spec v0.10, Scope) | — | from 2025-07-01 |
| G-3 | my/sales_tax.py | L `tariff_code` (appendix lists); C licensed manufacturer | T tariff table (exists) | see Open question 1 (refund route) | code null | from 2026-01-01 |
| G-4 | my/sales_tax.py | L `tariff_code` pallets; spec change 16 (`pallet_returnable`); D Schedule C | spec change 16 | SST_SHOULD_BE_EXEMPT / SST_CORRECT | returnable null | STP 1/2022 |
| G-5 | my/sales_tax.py | I bill-to/ship-to; spec change 17 (`drop_shipment_export`) | spec change 17 | NO_SST (correct) / SST_SHOULD_BE_EXEMPT | ship-to abroad not shown | STP 2/2022 |
| G-6 | — | — | — | **not an engine rule**: re-import at customs; out of scope as G-2 | — | to 2026-12-31 |
| G-7 | — | — | — | **not an engine rule**: the sheet says "refund-only windows (no invoice effect)"; guard test asserts the invoice is treated as without it | — | 2025 windows |
| ME-1 | my/einvoice.py | S turnover band, phase start; I e-invoice fields | S `einvoice_phase_start` | MISSING_MANDATORY_FIELD → REQUEST_CORRECTED_INVOICE | supplier phase unknown | LHDN timeline |
| ME-2 | my/validity.py (exists) | I TIN, registration numbers, classification, tax type, totals | — | MISSING_MANDATORY_FIELD | — | as ME-1 |
| ME-3 | my/einvoice.py | C buyer phase start; S foreign; spec change 18 (`self_billing_type`) | C `einvoice_phase_start` | ISSUE_SELF_BILLED_EINVOICE | buyer phase or type unknown | buyer's phase |
| ME-4 | my/validity.py | I reg 10(1) particulars; reg 10(1A) buyer details for B2B | — | MISSING_MANDATORY_FIELD | — | 10(1A) from 2019 |

### 4.5 Singapore — GST (SG)

| Rule | Lives in | Facts read (source) | New model fields | Outcome / actions | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| SG-1 | sg/gst.py | C registration; L `business_purpose`; I addressed to buyer | — | CLAIMABLE; NOT_CLAIMABLE_DISALLOWED | business purpose null | — |
| SG-2 | sg/validity.py (exists) | I tax-invoice items, SGD amounts | — | NOT_CLAIMABLE_INVALID_INVOICE (every GST line; spec choice 9) | — | — |
| SG-3 | sg/gst.py | I issue date; L `delivery_date`, `amount_paid_before_change`, `value_delivered_before_change`, `contract_excludes_tax_change` | catalog `GST_RATES` dated (7/8/9) | GST_WRONGLY_CHARGED; GST_UNDERCHARGED; accept rate shown when the election is possible | dates unknown on a spanning supply | 8% 2023-01-01; 9% 2024-01-01 |
| SG-4 | sg/gst.py | S registration, number, OVR type | — | GST_WRONGLY_CHARGED | registration unknown | — |
| SG-5 | sg/gst.py | L `exempt_supply` | — | GST_WRONGLY_CHARGED; NO_GST | null | — |
| SG-6 | sg/gst.py | L `zero_rating_provision`, `goods_outside_singapore`, `export_evidence`, `international_transport`; spec change 19 | spec change 19 | GST_WRONGLY_CHARGED; NO_GST (0% shown, spec choice 10) | counterparty/beneficiary not shown | (c) passenger insuring from 2023-01-01; (u) before 2022-01-01; (e) accommodation booking from 2023 |
| SG-7 | sg/customer_accounting.py | L `prescribed_goods`, `business_purpose`; I value excl. GST > S$10,000, CA statement | I `PintSg.customer_accounting_statement` | CUSTOMER_ACCOUNTING + ACCOUNT_CUSTOMER_ACCOUNTING_GST; GST_WRONGLY_CHARGED | goods type null | — |
| SG-8 | sg/reverse_charge.py | C input-tax status; S outside Singapore; spec change 20 (`low_value_goods`) | C `SgCompanyFacts.input_tax_status` | REVERSE_CHARGE + ACCOUNT_REVERSE_CHARGE_GST; NO_GST | status unknown | RC services from 2020-01-01; LVG from 2023-01-01 |
| SG-9 | sg/partial_exemption.py | C input-tax status; L `purchase_attribution` | as SG-8 | NOT_CLAIMABLE_EXEMPT_USE; RESIDUAL_APPORTIONED | attribution null | — |
| SG-10 | sg/disallowed.py | L `disallowed_category`, `vehicle_is_motor_car`, `staff_medical_obligatory`, `insurance_obligatory`, `chauffeured_pay_per_trip`, `car_used_by_third_party` | — | NOT_CLAIMABLE_DISALLOWED; CLAIMABLE | any of these null | private hire from 2022-04-01; third-party car from 2023-01-01 |
| SG-11 | rules/duplicates.py (exists) | ledger | — | REJECT_DUPLICATE (decision); claim timing is not an answer field | — | — |
| SG-12 | sg/gst.py | S registration; L `exempt_supply`, `zero_rating_provision`, `prescribed_goods`; C input-tax status | — | GST_UNDERCHARGED | supply category unknown | — |

### 4.6 Withholding (WH)

| Rule | Lives in | Facts read (source) | New model fields | Outcome / actions | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| WH-1 | my/withholding.py | S residence; L `payment_nature`, `certificate_of_residence`; T LHDN DTA (notes i, iii, iv, v); C industrial undertaking | C `industrial_undertaking` | WITHHOLD_TAX (15% interest / 10% royalty, or treaty) | nature or residence unknown | — |
| WH-2 | my/withholding.py | L `payment_nature`, `place_of_performance`, `in_country_share`, `hotel_reimbursement`, `certificate_of_residence`; T DTA | — | WITHHOLD_TAX 10% (or treaty) on the Malaysian part | place unknown; mixed without share | outside-Malaysia exemption from 2017-09-06; no grossing-up from 2018-12-05 |
| WH-3 | my/withholding.py | S PE in Malaysia; L `payment_nature` contract | S `pe_in_country` | **two** WITHHOLD_TAX: 10% and 3%, basis WH-3 | PE status unknown | — |
| WH-4 | my/withholding.py | L `payment_nature` other gain / public entertainer | — | WITHHOLD_TAX 10% / 15% | nature null | — |
| WH-5 | sg/withholding.py | S residence, SG branch; L `payment_nature`, `place_of_performance`, `certificate_of_residence`; T treaty rows | S `has_branch_receiving` | WITHHOLD_TAX (15/10/15/17/24, nil, or treaty) | nature/place unknown; treaty row not confirmed | — |

### 4.7 Mixed invoices (sheet §5)

| Rule | Lives in | Facts read | New model fields | Outcome | HAND_OVER when | Dates |
| --- | --- | --- | --- | --- | --- | --- |
| §5-a line by line | rules/lines.py (shared) | each line's result | — | case treatment = worst line; decision follows the most severe line | any line unsettled → case null | — |
| §5-b split as deciding fact | pack rules L-8, P-12, P-16, MS-2 | split facts | — | not itemised → whole invoice takes the taxed treatment | — (sheet decides) | as those rules |

**Row count:** 81 rule IDs in the sheet (MS 10, K 8, L 8, P 21, MG 6, G 7, ME 4, SG 12, WH 5) + 2 §5 rows = 83 rows. Not engine rules: P-21, G-2, G-6, G-7 (reasons above); each keeps one guard test.

## 5. Data model changes

All pydantic, `extra="forbid"`, validated by the pack's `check_*` methods like today.

### 5.1 Line facts

- `MyLineFacts`, `SgLineFacts`: exactly the field names, types and families of `$defs/line_facts` in `countries/my.schema.json` / `sg.schema.json`; every field `LineFact[T] | None`. A test generates the expected field set and JSON types from the schema and fails on any difference.
- `InvoiceLine.facts` becomes the pack's line-facts model (like `Company.tax_facts`). Renames: `same_service_unclear` → `same_service_as_buyer` (null = unclear); the SG names are unchanged.

### 5.2 Records

- `ContractRecord` (shared `models/contract.py`): `contract_id`, `supplier_id`, `parties`, `signed_on`, `stamped_on`, `has_price_review_clause`, `states_service`, `states_fixed_value`, `states_period`, `start`, `end`, `value`, `variation_orders: list[ContractChange]`, `extensions_of_time: list[ContractChange]` (`signed_on`, `stamped_on`, `changes_value`), `tax_facts` (pack model: `mixed_development_stated`, `design_and_build`, …). `CompanyRecords.contracts`; document role `contract`.
- `ResidenceCertificate` (shared): `supplier_id`, `country`, `valid_from`, `valid_to`; in `CompanyRecords`.

### 5.3 Party facts

- `MyCompanyFacts` + `msme: MsmeStatus` (`mypmk_registered_on`, `declared_sales_band: Literal["below_1m","1m_to_1_5m","above_1_5m"]`, `year_of_assessment`, `paid_up_capital`, `group_holding_pct`, `ssm_registered_on`), `group: GroupStructure` (shareholdings with pct, board control, nominee), `zone`, `zone_known`, `einvoice_phase_start`, `industrial_undertaking`, `labuan_fsa_regulated`, `buyer_kinds`.
- `MySupplierFacts` + `registration_known`, `supplier_kind`, `group_company_id`, `external_share_within_5pct: bool | None`, `is_foreign_registered_person`, `frp_supplies_outsiders_in_my`, `pe_in_country: bool | None`, `einvoice_phase_start`, `approvals`, `recognised_training_centre`, `zone`; `group_relation` is retired.
- `SgCompanyFacts` + `input_tax_status: Literal["fully_taxable","de_minimis_met","partially_exempt"] | None`.
- `SgSupplierFacts` + `has_branch_receiving: bool | None`, `pe_in_country: bool | None`.
- `PintSg` + `customer_accounting_statement`.

### 5.4 Spec changes needed (facts the schema lacks; not invented in code)

1 `manufactured_by_supplier` (MG-1) · 2 `export_related` (MS-4 H, P-1) · 3 `insurance_cover` (MS-4 H item 2) · 4 `premises_use` (MS-4 I13) · 5 `service_sub_item` (MS-6, item (i) sub-items) · 6 `own_use` (MS-5 item 9) · 7 variation-order and EOT facts (L-1) · 8 `mixed_development_stated` (L-2) · 9 `ship_platform_election` (L-8 item 1) · 10 `annual_fee_per_student` (Group M) · 11 extend `financial_charge` (P-2–P-5, P-7) · 12 `financial_use` (P-1, P-6) · 13 `patient_category`, `medical_aid`, `referral_walk_in` (P-13, P-14) · 14 `fully_sponsored`, student category (P-16) · 15 `digital_content_type` (P-19) · 16 `pallet_returnable` (G-4) · 17 `drop_shipment_export` (G-5) · 18 `self_billing_type` (ME-3) · 19 `beneficiary_outside_singapore` (SG-6 (j), (k)) · 20 `low_value_goods` (SG-8) · 21 `staff_secondment` (MS-4 G(j)) · 22 `excluded_management_kind` (MS-4 G(i)). How they enter the spec: Open question 2.

## 6. Catalog changes

- **C1, C2:** already applied in A11 (verified: `GROUP_RELIEF_ITEMS` includes `G(n)`, `maintenance_repair.group_relief: true`, no 30 kg text). Add regression tests.
- **Profile model:** `MyTaxProfile` gains `b2b_condition: Literal["same_item","same_item_sublet"]`, dated `rates`; `SgTaxProfile` gains defaults for `exempt_supply`, `zero_rating_provision`, `prescribed_goods`. The tax rules read line facts; the profile gives generator defaults and GL roles.
- **Rental (Group K, MS-5 item 8 sublet condition):** `equipment_rental`, `commercial_premises_rental`, `passenger_vehicle_rental`, `aircraft_vessel_charter`, `residential_housing_rental` (excluded). Sources: `guide-rental-or-leasing-services`, `stp-2-2025-amendment-5`, `dcp-2-2025-pindaan-5`, `service-tax-regulations-2018-amendment-1-2025`, `service-tax-rate-of-tax-order-2018-amendment-1-2026`, `guide-passenger-vehicle-rental-service-ms`.
- **New categories** (source ids from `docs/sources/manifest.yaml`):

| Category | Rules reached | Source |
| --- | --- | --- |
| golf_club_fees, karaoke_event_venue, private_club_services | MS-4 C–E, SG-10 | guide-group-c-d-and-e-services-ms |
| domestic_flight | MS-4 I10 | guide-domestic-flight-ms |
| aircraft_ship_mro | G(n), P-9 | guide-maintenance-or-repair-services-ms, stp-6-2024-amendment-3 |
| building_maintenance_charges | P-10, P-11 | stp-3-2026-amendment-1, stp-5-2024 |
| healthcare_consultation, staff_medical_treatment | I14–16, P-12–P-14 | guide-private-healthcare-services-ms, stp-5-2025-amendment-4, stp-6-2025 |
| staff_education_fees | Group M, P-16, P-17 | guide-private-education-services, stp-4-2025-amendment-2, stp-6-2020 |
| imported_consultancy, imported_it_services | MS-8, MS-5 items 1, 4 | guide-imported-taxable-services-ms, stp-2-2020 |
| foreign_digital_services | MS-5 item 3, MS-8 | guide-digital-service-by-foreign-service-provider-fsp, stp-3-2020 |
| software_royalty | WH-1, WH-5 | lhdn-public-ruling-10-2019, iras-types-of-payment-and-withholding-tax-rates |
| equipment_rental_from_abroad, technical_services_from_abroad | WH-2, WH-5 | lhdn-public-ruling-10-2019, income-tax-exemption-no-9-order-2017 |
| loan_interest_non_resident | WH-1, WH-5, SG-5 | lhdn-withholding-tax, iras-types-of-payment-and-withholding-tax-rates |
| business_insurance, bank_fees_commissions, card_activation | Group H, P-1–P-7 | guide-insurance-or-takaful-services-ms, guide-financial-services, stp-1-2025-amendment-5 |
| freight_forwarding, customs_agent | J1(a), J2, P-18 | guide-logistic-services-ms, guide-customs-agent-services-ms, stp-4-2024-amendment-1 |
| commercial_cleaning | I13 | guide-cleaning-services-ms |
| motorcycles, animal_feed_raw_materials | G-1, G-3 | sales-tax-policy-1-2025-amendment-1, sales-tax-policy-1-2026 |
| construction_materials, installed_equipment | L-8 | stp-7-2025, guide-construction-work-services-amendment |
| mobile_phones, memory_cards, packaged_software | SG-7 | customer-accounting-for-prescribed-goods |
| financial_advisory, residential_lease_sg | SG-5 | supplies-exempt-from-gst |
| international_freight_sg | SG-6 | providing-international-services |
| director_benefits, csr_items | SG-10 | employee-benefits-claiming-gst |
| chauffeured_private_hire | SG-10 | motor-vehicle-expenses-claiming-gst |

## 7. Engine outputs per case

- `AnswerKey` gains `tax_lines: list[TaxLine]` (`line_no`, `treatment`, `basis`), `buyer_actions` (WH-3 gives two `WITHHOLD_TAX` entries; `base_amount` in the invoice currency: gross line amount plus reimbursements, minus hotel accommodation, times the in-country share where WH-2 apportions), `facts` (gold, `facts.lines` format with evidence), `engine_version`, `rules_version`.
- Case-level `tax_treatment` = worst line by `pack.severity_order`; a test asserts `severity_order == x-severity-order` and that every key validates against `schemas/ap-invoices/v0.10/output.schema.json` (with the country parts).
- Gold facts = exactly the fields `FactReader` recorded for that line, with the evidence from the line's facts model. The evaluation order of rules is fixed per pack; a change that alters which facts are read changes keys and needs a version bump (§9).

## 8. `check_rules` interface

```python
def check_rules(records: CompanyRecords, case: ApCaseEnvelope, lines: FactsLines, catalog: Catalog) -> CheckRulesResult
# CheckRulesResult: engine_version, rules_version, lines: list[LineCheck]
# LineCheck: line_no, treatment | None, basis, buyer_actions, missing: list[str]
```

- `lines` is the spec's `facts.lines` (evidence optional), validated with the pack's line-facts model. Party facts come from `records` (the environment).
- Implementation: `rules/lines.py::assess_lines(view, catalog, source)` is the only tax path. `compute_answer` calls it with the gold facts; `check_rules` calls it with the supplied facts. A field the rules read but the caller did not supply goes to `missing` and the line's treatment is null. No copy of rule logic.
- It returns per-line results only; never the decision, GL or other checks.

## 9. Dated rules and versions

- Every `RuleSpec` carries `valid_from` / `valid_to` (rate changes, policies with end dates, expired exemptions kept per P-20). The rule applies by the date the rule names (invoice date, service period, delivery, payment, contract dates).
- `ENGINE_VERSION` = `decision_benchmark.__version__`, set to `0.10.0` in the last build commit; `RULES_VERSION = "v0.10"` in the TaskSetSpec; both in every key.
- Release pinning: each CHANGELOG release entry states `Engine: <version>. Rules as of: <date>.`; `release/publish.py` checks that line against `__version__` and the staged keys.
- Version guard: `tests/fixtures/keys/golden.jsonl` (first line holds `engine_version`). The test regenerates every fixture key; any difference while `ENGINE_VERSION` equals the golden's version fails ("key changed without a version bump"). After a bump, the golden must be regenerated and `tests/fixtures/keys/changes.md` must list each changed key with its rule ID.

## 10. Treaty rates as data

- Malaysia: `countries/my/data/dta_withholding_rates.yaml` (LHDN table) with notes as typed fields: lower of treaty and domestic (i), certificate of residence required (iii), 15/10 industrial-undertaking rows (iv), royalty rate for technical fees where no article exists (v).
- Singapore: `countries/sg/data/dta_withholding_rates.yaml` from treaty texts; each field gets `confirmed: bool`. Today only rows with status "single rate in the article" may become confirmed; the 131 flagged fields stay `confirmed: false` until step 11d.
- A typed loader validates every row; a case that needs an unconfirmed row → HAND_OVER. No rates are hand-checked in A12.

## 11. Reference-row check

`tests/rules/test_reference_row.py`: for every case, build `FactsLines` from the gold facts and run `check_rules`; its per-line results and buyer actions must equal the key's. It runs over every fixture case now; in B1 the same test runs over every generated case of every split and fails on any difference.

## 12. Tests

- Per rule ID: one positive and one near-miss, registered in `countries/<c>/rule_tests.py` (`RULE_TESTS: dict[rule_id, {"positive": [...], "near_miss": [...]}]`), like `table_rows.py`.
- Coverage: `test_rule_coverage.py` parses every rule ID from `docs/tax-rules-v0.10.md` and fails if one has no registered, existing tests (not-engine rules need their guard test). During the build a `PENDING` set lists unbuilt rules; the last commit empties and deletes it.
- Date boundaries: generated from each `RuleSpec`: day before start, start, end, day after end.
- Existing keys: commit 1 snapshots all 132 current keys. Expected changes: every key gains the additive fields; tests that expect `UnsupportedCase` for sales tax by a registered non-manufacturer (now MG-1) and non-standard GST rates (now SG-3) become positive tests of those rules. Any other change must be listed with its rule ID in `changes.md`, or the test fails.

## 13. Commit order and test estimates

Each commit is one area and keeps the suite green; counts are cumulative from 389.

| # | Commit | New tests | Suite |
| --- | --- | --- | --- |
| 1 | Golden snapshot of the 132 keys + version-guard scaffold (no behaviour change) | 3 | 392 |
| 2 | `EvidenceRef`, `LineFact`, `MyLineFacts`/`SgLineFacts` = schema; `InvoiceLine.facts` migration | 25 | 417 |
| 3 | Contract record, residence certificates, party facts (§5.2–5.3) | 30 | 447 |
| 4 | Registry, `FactReader`, per-line results, worst line, new key fields, versions (v0.9 logic per line; golden diff additive only) | 20 | 467 |
| 5 | Rule coverage test with `PENDING` | 4 | 471 |
| 6 | MS-1–MS-4, MS-9 (service tax core, Groups A–J, M) | 40 | 511 |
| 7 | MS-5 B2B, MS-6 group relief, MS-7 areas, MS-8 imported | 30 | 541 |
| 8 | Group K, K-1–K-8 | 30 | 571 |
| 9 | Group L, L-1–L-8 | 30 | 601 |
| 10 | MS-10, P-1–P-21 | 55 | 656 |
| 11 | MG-1–MG-6, G-1–G-7, sales-tax rate table | 35 | 691 |
| 12 | ME-1–ME-4 | 14 | 705 |
| 13 | SG-1–SG-6, SG-11, SG-12 | 35 | 740 |
| 14 | SG-7–SG-10 | 30 | 770 |
| 15 | Treaty loaders with `confirmed`; WH-1–WH-5 | 35 | 805 |
| 16 | §5 mixed invoices | 10 | 815 |
| 17 | Catalog: rental, new categories, C1/C2 regressions. Built without the §6 profile fields `b2b_condition` and dated `rates` (accepted in the PR 5 review, 19 Nov 2026): the engine derives both from the service item and the date. Goods for G-1, G-3 and L-8 are pinned to one tariff code each, split where a heading's codes differ in rate | 20 | 835 |
| 18 | `check_rules` + equivalence tests | 15 | 850 |
| 19 | Reference-row test, `PENDING` emptied, version 0.10.0, `changes.md` | 6 | 856 |

## 14. Open questions

1. **Refund-route exemptions.** G-3: "exempt from 1 Jan 2026 until the Persons Exempted Order is amended (refund route)"; P-20: "JDA (refund route since 15 Aug 2022)". On the invoice the tax is then correctly charged. Treat as `SST_CORRECT` with no buyer action, or add a buyer action for the refund claim (a spec change)?
2. **How the 22 missing line facts (§5.4) enter the spec.** CHANGELOG: "Clarifications without a version bump are allowed only while no scores exist for that version." No v0.10 scores exist. Amend the v0.10 schema as a clarification, or open v0.11?
3. **Mixed invoices with two GL accounts.** Sheet §5: "a Singapore supplier bill with a claimable item and a club fee"; spec: "GL account: one code from the company's chart of accounts". The engine raises `UnsupportedCase` when lines book to two accounts. Keep one GL per case (only plant mixed invoices within one GL role), or change the output?
4. **Splitting a service across a rate change.** MS-3: "taxed by the part provided on each side of the date", deciding facts "service period on the invoice, payment date". When the invoice shows only the period, split pro rata by days, or HAND_OVER unless the invoice shows the split?
5. **K-1 backdating.** K-1: "Registration by 31 Dec 2026 still backdates to 1 Jul 2025 / 1 Jan 2026." Judge the tenant's MyPMK status at the invoice date, or at the release as-of date (so a later registration before the as-of date counts)?
6. **Missing-trader fraud.** SG-1: "Conditions for a claim (all eight; v0.9) — unchanged"; dataset card: "Missing-trader-fraud checks for Singapore GST are not modelled." Keep condition 8 unplanted, or model it (needs a fact for "reasonable steps")?

## 15. Verification for the build (after approval)

Full suite green at every commit; `derive.py --check`; every key validates against the v0.10 output schema; coverage test with an empty `PENDING`; golden diff reviewed against `changes.md`; reference-row test green; `check_public --mode repo` OK.

## 16. Decisions from review (PR #11, 17 Nov 2026)

Answers to §14:

1. **Refund-route exemptions (G-3, P-20):** `SST_CORRECT`, no buyer action. The tax is correctly charged on the invoice; the refund is an optional later claim to RMCD. Buyer actions (D1) cover obligations only; the spec's buyer-actions section says so.
2. **The 22 missing line facts (§5.4):** v0.10 is amended as a clarification (no v0.10 scores exist; the fields are optional). They go into the country parts with types, families and rules, `derive.py` is rerun, and the CHANGELOG gets a clarification line. This is the first commit of build PR 1, before the typed line-fact models.
3. **Two GL accounts on one invoice:** same clarification. Each `tax_lines` entry gets an optional `gl_account`. The case-level `gl_account` stays: the GL of the line with the largest amount excluding tax (ties: lowest `line_no`). Main score and GL accuracy unchanged; line GL is reported in the per-line column like per-line tax. The `UnsupportedCase` for two GL accounts is removed.
4. **MS-3 spanning a rate change:** no pro-rata split by days. Whole period on one side → that side's rate. Spans the date and the invoice or a case document shows the split → each part checked. Spans the date, no split shown → HAND_OVER, basis MS-3.
5. **K-1 backdating:** judged at the case's processing date, never the release as-of date. A MyPMK registration on or before the processing date whose backdating covers the invoice date makes the line exempt; a later registration doesn't count.
6. **SG-1 condition 8 (missing-trader fraud):** stays unplanted in v0.10; a guard test checks that no generated case relies on it.

Changes to the plan:

- **A. Four build PRs**, each reviewed and merged before the next, each keeping the suite green and listing changed keys in `changes.md` with the rule ID:
  - PR 1, foundation: the spec clarification (answers 2 and 3), then commits 1–5.
  - PR 2, Malaysia: commits 6–12.
  - PR 3, Singapore, withholding, mixed invoices: commits 13–16.
  - PR 4, catalog, `check_rules`, reference-row check, version 0.10.0: commits 17–19.
- **B. Treaty rates (§10):** the per-row `confirmed` flag stays. Step 11d (the hand check of the 131 flagged Singapore fields) arrives as a separate data change before PR 3; PR 3 loads the file as it stands then and edits no rates.
