# Step 11 plan: generator, rules engine, scorer, agent environment

Status: approved by Sebastian on 13 Nov 2026, with the decisions in §16. Task set: `ap-invoices-my-sg`. Spec: v0.9 ("synthetic, rules-based"), frozen.

This PR adds only this plan. No code. The builds happen in later runs, one PR per row in §12, after review. PR A ended with commit A8, which split generic code (`core/`) from the task set (`task_sets/ap_invoices_my_sg/`); §3, §3.1 and §12 describe the split.

Inputs read: `spec-v0.9.md`, `tax-rules-v0.9.md`, `schemas/ap-invoices-my-sg/v0.9/`, `release/`, `CHANGELOG.md`, `docs/plans/step-08-plan.md`, and the stack decisions extract of 13 Nov 2026 (DECIDED and PROPOSED items).

The plan follows the spec and the tax-rule sheet as written. Where they leave something open, I say how I would build it and list it as an open question in §16. None of my recommendations change a rule, a decision, a tax code or a cost.

## 1. What step 11 delivers

1. **Rules engine.** Computes every answer key from the policy pack and `tax-rules-v0.9.md`. Every row of the "From rules to benchmark checks" table is implemented and tested.
2. **Case generator.** Fictional companies, suppliers, POs, receipts, history, AP inbox, invoices (MyInvois-style and PINT-SG-style), Typst PDFs, Augraphy scans and photos. Planted exceptions in the spec's mix. Text from committed phrasebanks. Output in the parquet layout that `release/` and the dataset card expect.
3. **Hard-case template format.** Reviewable YAML templates. Claude drafts the content later; this plan fixes the format.
4. **Scorer.** Plain-Python metrics, a CLI that scores predictions JSONL, an Inspect AI task, CI that re-scores results PRs, and three trivial baselines.
5. **Agent environment and graders.** An MCP environment (OpenEnv `MCPEnvironment` image) wrapped in an Inspect task, final-state graders for the 10-step rubric, and tests against deliberately bad agents.
6. **Hidden split, planned only.** How `decision-benchmark-hidden` uses this generator with private seeds, and the one Claude Code hook. Built in the hidden repo, never here.

## 2. Principles

- **One source of truth for each answer.** Only the rules engine writes answer keys. Templates, phrasebanks and the environment never decide an answer.
- **One case view.** A single function builds what a case "knows" (`CaseView`). The rules engine, the decision-track export and the environment all use it. So both tracks always see the same facts and share one answer key.
- **Planted equals found.** The generator plants problems; the rules engine independently finds problems. If the two sets differ, the case is rejected and redrawn. This catches accidental extra problems and engine bugs early.
- **Structured facts drive answers, text only expresses them.** The rules engine reads structured fields (for example `requests_bank_change: true` on an email), never free text. Phrasebank tests check that the text says what the flag says.
- **Plain Python.** Pydantic for schemas, `random.Random` with derived seeds, PyYAML, pyarrow. Heavier tools (Typst, Augraphy, Inspect, OpenEnv) sit in separate dependency groups, so the rules engine, generator core and scoring CLI install without them.
- **Nothing hidden here.** No hidden seeds, canary-bearing files, hidden case counts by id or anything named after the hidden split. `check_public.py` rule 1 also forbids path segments containing `hidden` or `private`, so no new file or folder may use those words.

## 3. Module layout

Legend: **[A]**, **[B1]** … = the build PR in §12 that creates it. **[A8]** = the last commit of PR A, which split core from the task set (§3.1).

The spec gives every task set one case format, one scorer and one leaderboard. So the package has two halves: `core/` holds generic code, and `task_sets/<id>/` holds everything that knows about one task set. `ap_invoices_my_sg` is the first task set; expense claims are planned as a later one.

```
pyproject.toml                    [A] becomes an installable package (uv_build backend), so the
                                      hidden repo can depend on a tagged version; new dependency groups
src/decision_benchmark/
  core/                           generic code only; never imports task_sets/ and never names a
                                  task set (tests/core/test_core_isolation.py enforces both)
    model.py                      [A8] Model, Money, Num, internal fields, export_dict, AnswerSource
    case.py                       [A8] CaseEnvelope, Document, Provenance, AnswerEnvelope (§3.1)
    task_set.py                   [A8] TaskSetSpec and the registry (§3.1)
    generator/                    [B1]
      seeds.py                        derived seeds (§8.1)
      quotas.py                       exact counts per split, from TaskSetSpec.quotas
      text.py                         phrasebank loader and assembler
      export.py                       parquet writers for envelopes (decision / agent / companies)
      cli.py                          `db-generate --task-set <id>`
    render/                       [B3]
      typst.py                        calls the pinned Typst compiler
      degrade.py                      Augraphy scan and photo pipelines
      pdfcheck.py                     text check of a rendered PDF against expected strings
    scorer/                       [C]
      metrics.py                      all leaderboard metrics, plain Python, costs from TaskSetSpec.costs
      validate.py                     predictions JSONL (against TaskSetSpec.output_schema) and metadata.yaml
      baselines.py                    always-approve and always-hand-over for any task set
      cli.py                          `db-score`, `db-leaderboard`
      inspect_tasks.py                Inspect task factory: a decision task and an agent task per TaskSetSpec
      inspect_scorers.py              Inspect scorer + metrics wrapping metrics.py
    env/                          [D1]
      base.py                         per-case state container, audit log, read-only guard, state hash
      server.py                       OpenEnv MCPEnvironment adapter over a task set's tool list
    graders/                      [D2]
      framework.py                    runs a rubric over final state: gates, step results, pass rule
      judge.py                        AI-judge wrapper (reported separately)
  task_sets/
    __init__.py                   [A8] imports every task set, which registers its TaskSetSpec
    ap_invoices_my_sg/
      __init__.py  spec.py        [A8] the TaskSetSpec (decisions, extra fields, costs, quotas,
                                      schema path, HF repo id), registered on import
      envelope.py                 [A8] the invoice Case as payload of the core CaseEnvelope
      models/                     [A] pydantic records (§4)
        common.py                     task-set enums (countries, decisions, tax codes, tiers);
                                      re-exports the core base types
        company.py  supplier.py  procurement.py (PO, receipt)  invoice_base.py  invoice_my.py
        invoice_sg.py  email.py  policy.py  case.py  answer.py  facts.py  catalog.py
      rules/                      [A] rules engine, pure functions, no I/O
        view.py                       CaseView builder (the one case view)
        matching.py                   PO, receipt, price, quantity, partial delivery
        duplicates.py                 exact and near duplicates, credit-note reissues
        fraud.py                      bank details vs record, bank change by email
        validity_sg.py                IRAS tax-invoice checks
        validity_my.py                MyInvois mandatory fields
        tax_sg.py  tax_my.py          tax treatment
        routing.py                    no PO, approval limit
        gl.py                         GL account
        decide.py                     findings -> decision by fixed priority -> answer key
        constants.py                  rates and thresholds, each with its source URL from the rule sheet
        table_rows.py                 maps each row of the rule-sheet table to its tests (§5.4)
      generator/                  [B1]
        entities.py                   companies, suppliers, people, banks, CoA, policy packs
        scenario.py                   clean base case: PO, receipt, invoice, history, cover email
        ops.py                        named edit operations used by hard-case templates (§7.2)
        hardcases.py                  loads and instantiates templates
        consistency.py                cross-file checks (§8.4)
      render/                     [B3]
        viewmodel.py                  record -> formatted strings per layout; expected strings for pdfcheck
      baseline.py                 [C] rules-only baseline
      env/                        [D1]
        state.py                      this task set's company systems on top of core env/base.py
        tools.py                      the MCP tools (§10.2), plain functions over state
        colleagues.py                 scripted fact-sheet replies (§10.3)
      rubric/                     [D2]
        rubric.py                     the 10-step rubric (§10.4) for core graders/framework.py
        traps.py                      trap counters
        judge_prompt.md               the step-10 judge prompt
      content/                    shipped as package data, so the hidden repo gets the same content
        catalog/                  [A] item and service categories, tax class, GL role, sources
        policy/                   [B1] policy-pack templates and policy-document text templates
        phrasebanks/              [B1 starter, B2 full] text banks (§7.3)
        hardcases/                [B1 format, B2 content] hard-case templates (§7.2)
        names/                    [B1] company, person, street, bank name banks
        typst/                    [B3] invoice layouts
        fonts.lock.yaml           [B3] font files: URL, sha256, licence (fonts are not committed)
        release-seeds.yaml        [B1] public seeds for train and test
baselines/ap-invoices-my-sg/      [C] baseline entries (predictions + metadata)
results/ap-invoices-my-sg/v0.9/   [C] results entries; leaderboard.md
docker/                           [B3] build.Dockerfile (release builds); [D1] env.Dockerfile
tests/
  core/                           [A8] isolation, registry, envelopes; later generator, render, scorer, env, graders
  models/  rules/                 [A] task-set tests; later generator/, env/, rubric/ for the task set
  fixtures/                       YAML only: check_public rule 5 rejects .json/.jsonl/.csv in git
```

All content files are YAML or Typst. That matters because `check_public.py` (repo mode) fails on any `.json`, `.jsonl`, `.csv` or `.parquet` file outside its exempt paths.

Later sections use short paths. `content/.../` means `task_sets/ap_invoices_my_sg/content/`; `generator/ops.py`, `rules/…`, `env/tools.py` and `rubric/…` are in the task set; `core/…` paths are in core.

Where a file goes, in one rule: if a second task set (expense claims) would use it unchanged, it goes in `core/`; if it names invoices, POs, SST, GST or this task set's decisions, it goes in the task set. Core code reads task-specific things only through the `TaskSetSpec` or through functions the task set hands it (for example the tool list for the environment, or the rubric steps for the grader framework).

### 3.1 Shared case format and task-set registration (built in A8)

**Case envelope** (`core/case.py`). Only the fields the spec already gives every task set:

- `case_id`, `task_set`, `split`, `country`, `languages`, `modality`, `provenance`, `canary`
- `documents`: a list of `{role, record | file}`. `record` names a field of the payload that holds a structured record; `file` is a path in the release (PDF, scan or photo). Exactly one of the two.
- `payload`: the task set's own case model. For this task set it is the invoice `Case` (§4.8).

Until B1, the invoice `Case` still carries its own `case_id`, `split`, `country`, `languages`, `modality` and `provenance`, because the rules engine and the A fixtures read them there. `ApCaseEnvelope` checks that envelope and payload agree. B1 removes the copies from the payload when the generator starts writing envelopes, and the export writes envelope columns plus a payload column. No answer key changes from this.

**Answer-key envelope** (`core/case.py`): `case_id`, `task_set`, `decision`, `answer` (the extra scored fields the task set declares, by name; never a confidence), `answer_source`. The task set's `AnswerKey` keeps its findings and agent-grader truth and converts with `AnswerKey.envelope()`. For this task set the extra fields are `tax_treatment`, `gl_account` and `reason_codes`.

**TaskSetSpec** (`core/task_set.py`): `id`, `title`, `spec_version`, `decisions` (must include `HAND_OVER`), `approve_decision`, `trap_decisions` (approving a case whose right decision is one of these is a critical error), `extra_fields`, `costs` (the leaderboard weighting first, then the alternatives), `invalid_output_is` (which cost an invalid prediction gets; Q19), `quotas` (percent per primary exception type, summing to 100), `output_schema` (path) and `hf_repo_id`. `task_sets/ap_invoices_my_sg/spec.py` builds it from the spec's tables and registers it on import; `import decision_benchmark.task_sets` registers every task set. A test checks that the spec's decisions and fields match `output.schema.json`.

**release/ (note only; no code change in A8).** `release/` still hard-codes this task set: `publish.py` has the HF repo id, and `allowlist.txt` names the card, schema and docs paths of `ap-invoices-my-sg`. When B3 touches release wiring (§9.4), it makes `stage.py` and `publish.py` take `--task-set <id>`, read `hf_repo_id` from the TaskSetSpec, and use one allowlist per task set (`release/allowlists/<id>.txt`). `check_public.py` stays generic as it is. The HF collection stays one collection for all task sets. Until then, the hard-coded values must equal the spec's; a B3 test checks that.

## 4. Data model

Pydantic v2 models, `extra="forbid"`, frozen. Money is `Decimal`, serialised as a string with two decimals (`"3456.00"`). Dates are ISO strings. JSON is written with sorted keys, compact separators and `ensure_ascii=False`, so it is byte-stable. Field lists below; names are final unless review changes them.

### 4.1 Company (buying company)

- `company_id` (`my-c-007`), `split`, `country` (`MY`/`SG`), `legal_name`, `trading_name`, `registration_no` (MY SSM number / SG UEN), `address`, `base_currency` (`MYR`/`SGD`), `industry`
- MY: `tin`, `sst_registration_no` (or null), `is_registered_manufacturer`, `services_provided` (list of service categories; used for the Group G B2B test), `group_companies` (names; used for group relief)
- SG: `gst_reg_no`, `gst_registered_since` (every SG buyer is GST-registered in v0.9; see Q5)
- `people`: list of Person
- `policy_pack`: PolicyPack

**Person:** `person_id`, `name`, `role` (`procurement`, `stores`, `finance_manager`, `requester`, `director`, `ap_clerk`), `email`, `approval_role` (key into the approval matrix, or null), `languages`.

### 4.2 Policy pack

- `tolerance_policy`: `price_tolerance_pct`, `price_tolerance_abs` (optional; the larger allowance applies if both are set), `quantity_tolerance_units` (default 0), `rounding_tolerance` (amount allowed between sum of lines and printed total), `duplicate_window_days`
- `approval_matrix`: list of `{approval_role, limit, currency}`
- `non_po_policy`: `allowed_categories` (for example utilities, telecoms), `max_amount`
- `chart_of_accounts`: list of `{code, name, type (expense/asset/liability/tax), description, active}`
- `tax_registration`: country, numbers, status, effective dates (mirrors the company fields; this is what the policy folder shows)
- `exemption_certificates`: list of `{kind (schedule_c / group_g_b2b_declaration), number, valid_from, valid_to, categories}`
- `price_change_rule`: "price changes count only through an approved PO amendment in the ERP" (flag + text)
- `bank_change_rule`: "supplier bank changes count only through the verified change process in the supplier master" (flag + text)
- `documents`: rendered policy texts (from `content/.../policy/` templates) that the environment's policy folder serves

### 4.3 Supplier

- `supplier_id`, `company_id`, `name`, `country`, `address`, `registration_no`, `currency`, `payment_terms_days`, `contacts` (`{contact_id, name, email, phone}`)
- `bank_account`: `{bank_name, account_name, account_no, swift}`; `bank_change_log`: list of `{changed_on, old_account_no, new_account_no, method, verified_by}`
- MY: `tin`, `brn`, `sst_registration_no` (or null), `sst_type` (`sales`/`service`/`both`/`none`), `is_manufacturer`, `turnover_band` (drives whether an e-invoice is expected), `service_categories`, `msic_code`
- SG: `gst_reg_no` (or null), `gst_status` (`registered`/`deregistered`/`none`), `gst_status_date`, `gst_regime` (`local`/`ovr`)
- Thai suppliers (MY cases only): same MY fields with `country: TH`, no SST registration.

Generator-only metadata (for example "this supplier is a lookalike of S-0042") lives outside the model and is never exported.

### 4.4 Purchase order and goods receipt

**PurchaseOrder:** `po_number`, `company_id`, `supplier_id`, `po_date`, `currency`, `requester_id`, `approver_id`, `status` (`open`/`partially_received`/`received`/`closed`), `lines` (`{line_no, item_code, description, category, qty, uom, unit_price, gl_account}`), `amendments` (`{date, line_no, field, old, new, approved_by}`), `total_net`.

**GoodsReceipt:** `gr_number`, `po_number`, `gr_date`, `kind` (`goods`/`service_confirmation`), `received_by`, `lines` (`{po_line_no, qty_received, uom, note}`).

### 4.5 Invoice

**Common core (both countries):** `invoice_id`, `doc_type` (`invoice`/`credit_note`), `invoice_number`, `issue_date`, `due_date`, `supplier_block` (name, address, tax ids as printed), `buyer_block` (name, address, tax ids as printed; any part may be absent), `po_reference` (or null), `currency`, `exchange_rate` (or null), `lines` (`{line_no, description, qty, uom, unit_price, net_amount, tax_rate, tax_amount}`), `totals` (`net`, `tax`, `gross`, `rounding`), `bank_block` (as printed), `payment_terms_text`, `notes`, `original_invoice_ref` (credit notes), `languages`.

**MY extras (MyInvois-style; names follow the MyInvois data structure in snake_case):** `is_einvoice`, `einvoice_version`, `einvoice_type_code` (`01` invoice, `02` credit note), `uuid`, `validation_datetime`, `supplier_tin`, `supplier_brn`, `supplier_sst_no`, `supplier_msic_code`, `buyer_tin`, `buyer_brn`, `buyer_sst_no`, per line `classification_code` and `tax_type` (`01`, `02`, `06`, `E`), per line `tax_exemption_reason`, `tax_total_by_type`.

The mandatory set used by the "missing mandatory field" check is exactly the list in the rule sheet: supplier and buyer TIN, registration numbers, type code and date, currency, per line classification, description, unit price and tax type, and total tax per tax type. Fields not on that list may be absent without consequence. Suppliers below the e-invoice threshold send ordinary invoices (`is_einvoice: false`; e-invoice-only fields null).

**SG extras (PINT-SG-style):** `is_peppol`, `customization_id`, `profile_id`, `invoice_type_code` (`380`/`381`), `document_title` (`"Tax Invoice"`, `"Invoice"` or null), `supplier_gst_no`, per line `tax_category` (`SR`, `ZR`, `ES`, `OS`, `NA`) and `tax_rate`, `tax_total`, `tax_total_sgd` and `gross_sgd` (for foreign-currency invoices), `price_includes_gst_statement` (simplified invoices).

### 4.6 Email

- `thread_id`, `message_id`, `company_id`, `case_id` (or null for background mail), `sent_at`, `from` (`{name, address}`), `to`, `cc`, `subject`, `body`, `languages`, `attachments` (references to records, for example the case invoice)
- Structured flags, never exported: `intent`, `requests_bank_change`, `new_bank_account`, `mentions_price_change`, `price_change_status` (`amended_in_erp`/`verbal_only`/`none`), `lookalike_sender`, `contains_instruction_injection`. The rules engine reads only these flags, during generation.

### 4.7 Fact sheet (agent track)

Per case, per simulated person:
- `person_id` (colleague) or `contact_id` (supplier contact), `role`
- `facts`: list of `{fact_id, topic, release (always / on_topic), reply_key, params}`
- `fallback_reply_key`

Topics are a fixed list for all cases: `delivery`, `quantity`, `price`, `bank_details`, `approval`, `tax`, `vehicle_use`, `duplicate`, `service_period`, `other`.

### 4.8 Case

The task set's payload inside the core case envelope (§3.1). Fields as built in A (the "Links" line was dropped in A: the engine finds the PO, receipts and threads itself):

- `case_id` (`ap-my-00421`, `ap-sg-00017`), `split`, `country`, `company_id`, `as_of_date`
- `invoice` (MY or SG model), `invoice_file` (`pdf/{split}/{case_id}.pdf` or `.jpg`), `modality` (`pdf`/`scan`/`photo`)
- Links: `supplier_id`, `po_number`, `gr_numbers`, `thread_ids`
- `fact_sheets`
- Planting record: `exception_types` (list), `families` (template ids), `two_problems`
- Provenance: `generator_version`, `seed` (the case's derived seed), `pipeline_hash`
- `languages`

### 4.9 Answer key

- `decision`, `tax_treatment` (or null), `gl_account` (or null), `reason_codes` (ordered by priority), `answer_source` (`rules` / `handover_by_construction`)
- `findings`: list of `{code, tier, evidence}` (for example `{code: PRICE_ABOVE_PO, tier: mismatch, evidence: {line: 1, po: "1180.00", invoice: "1240.00", variance_pct: "5.08"}}`)
- For agent graders: `truth_supplier_id`, `truth_po_number`, `truth_price_variance_pct`, `requires_supplier_contact`

### 4.10 Parquet configs

Exactly the three configs the card and allowlist expect: `data/{decision,agent,companies}/{train,test}-00000-of-00001.parquet`, plus `pdf/{train,test}/{case_id}.{pdf,jpg}`.

| Config | Columns |
| --- | --- |
| `decision` | `case_id`, `split`, `country`, `company_id`, `as_of_date`, `languages`, `modality`, `invoice_json`, `invoice_file`, `purchase_order_json`, `goods_receipt_json`, `supplier_json`, `history_json` (last 10), `emails_json`, `policy_pack_json`, `answer_decision`, `answer_tax_treatment`, `answer_gl_account`, `answer_reason_codes`, `answer_source`, `answer_findings_json`, `exception_types`, `families`, `two_problems`, `generator_version`, `seed`, `pipeline_hash`, `canary` |
| `agent` | `case_id`, `split`, `country`, `company_id`, `as_of_date`, `languages`, `modality`, `invoice_json`, `invoice_file`, `fact_sheets_json`, the same `answer_*` columns plus `answer_supplier_id`, `answer_po_number`, `answer_price_variance_pct`, `answer_requires_supplier_contact`, provenance, `canary` |
| `companies` | `company_id`, `split`, `country`, `company_json` (incl. people and policy pack), `suppliers_json`, `purchase_orders_json`, `goods_receipts_json`, `invoices_json` (history), `inbox_json`, `canary` |

- `canary` is the public test canary string on every test row of every config (check_public rule 6 requires it on test files) and null on train rows.
- No `answer_*` column in `companies` (check_public rule 5).
- Rows are sorted by `case_id` / `company_id`. One file per config and split; one row group; zstd at a fixed level; no extra metadata.

### 4.11 What a case can see (CaseView)

Company tables hold background records plus the records made for each case. For case X, `CaseView` contains:
- every PO and receipt of the company dated on or before X's `as_of_date` (other cases' POs stay visible: they are realistic noise and make PO matching a real step)
- every history invoice and credit note dated on or before `as_of_date` (case invoices are never in the history table)
- background email threads and X's own threads; other cases' threads are not visible
- the supplier master as of `as_of_date` (bank change log entries after it are hidden)

The decision track gets the PO, receipts, supplier, the last 10 history items of that supplier, X's threads and the policy pack. The generator checks that every record the answer depends on (for example the original of a duplicate) is inside that decision-track subset.

## 5. Exception planting

### 5.1 Exact quotas

Counts are exact per split, not sampled. Within each type, countries split 50/50 (largest remainder for odd counts).

| Primary type | Share | Train | Test | Hidden (300) |
| --- | --- | --- | --- | --- |
| Clean | 40% | 800 | 200 | 120 |
| Tax problem | 10% | 200 | 50 | 30 |
| Price mismatch | 10% | 200 | 50 | 30 |
| Quantity mismatch | 8% | 160 | 40 | 24 |
| Invalid invoice / missing fields | 8% | 160 | 40 | 24 |
| Duplicate (incl. near) | 7% | 140 | 35 | 21 |
| Not received | 5% | 100 | 25 | 15 |
| No PO / above limit | 5% | 100 | 25 | 15 |
| Changed bank details | 4% | 80 | 20 | 12 |
| Ambiguous (HAND_OVER) | 3% | 60 | 15 | 9 |

- A case's **primary** type is the problem that sets the decision. The shares refer to primary types.
- **Two problems:** 15% of all cases (300 / 75 / 45), drawn only from problem cases. The secondary problem always has a lower priority tier than the primary, so the primary still sets the decision. Allowed pairs live in `hardcases/pairs.yaml`.
- Ambiguous cases never get a second problem (Q14).
- "Tax problem" includes SG `NOT_CLAIMABLE_DISALLOWED`, whose decision is APPROVE. It is not "clean".

### 5.2 Priority tiers

From the spec: fraud, then duplicate, then invalid invoice, then mismatch, then routing.

| Tier | Findings | Decision |
| --- | --- | --- |
| 1 fraud | `BANK_DETAILS_DIFFER_FROM_RECORD`, `BANK_CHANGE_BY_EMAIL_ONLY` | FRAUD_REVIEW |
| 2 duplicate | `DUPLICATE_INVOICE`, `NEAR_DUPLICATE` | REJECT_DUPLICATE |
| 3 invalid invoice | `MISSING_MANDATORY_FIELD`, `INVALID_TAX_INVOICE`, `FOREIGN_CURRENCY_NO_SGD_AMOUNTS`, `SUPPLIER_NOT_TAX_REGISTERED`, `WRONG_TAX_RATE`, `TAX_SHOULD_BE_EXEMPT`, `OVR_GST_CHARGED_TO_REGISTERED_BUYER` | REQUEST_CORRECTED_INVOICE |
| 4 mismatch | `NOT_RECEIVED` > `QUANTITY_ABOVE_RECEIVED` > `PRICE_ABOVE_PO` | HOLD_NOT_RECEIVED / DISPUTE_QUANTITY / DISPUTE_PRICE |
| 5 routing | `NO_PO`, `ABOVE_APPROVAL_LIMIT` | ROUTE_FOR_APPROVAL |
| — | rules do not settle the case | HAND_OVER (`handover_by_construction`) |
| — | nothing found | APPROVE |

Placing "tax wrongly charged" in tier 3 follows the spec: REQUEST_CORRECTED_INVOICE covers both invalid invoices and wrongly charged tax, and the spec's own two-problem example (price mismatch plus wrong tax rate) then resolves to REQUEST_CORRECTED_INVOICE. The order inside tier 4 is my proposal (Q7). The generator never plants two problems of the same tier, so the inner order matters only as a tie-break.

### 5.3 How the rules engine derives each part

All checks run on `CaseView`. Each check returns findings with evidence.

**Fraud (`fraud.py`).**
- Invoice `bank_block.account_no` differs from the supplier's account on file at `as_of_date` → `BANK_DETAILS_DIFFER_FROM_RECORD`.
- A thread linked to this invoice has `requests_bank_change` and the supplier master has no verified change matching it → `BANK_CHANGE_BY_EMAIL_ONLY`, even if the invoice shows the old account.
- A change made through the verified process before the invoice date, with the invoice showing the new account, is not a finding (decoy).

**Duplicates (`duplicates.py`).**
- Exact: same supplier and same normalised invoice number (case, spaces, dashes, leading zeros ignored) among paid or open history → `DUPLICATE_INVOICE`.
- Near: same supplier, same gross amount, different number, same PO reference or same lines and service period, within `duplicate_window_days` → `NEAR_DUPLICATE`.
- Not duplicates: recurring invoices for different service periods; an invoice reissued after a credit note that fully cancels the original.

**Validity, SG (`validity_sg.py`).** Uses the IRAS full tax-invoice list and common-invalidity list from the rule sheet.
- Gross above S$1,000 and (no "Tax Invoice" title, or no customer name, or no GST amount) → `INVALID_TAX_INVOICE`.
- S$1,000 or below: no GST amount and no "price includes GST" statement → `INVALID_TAX_INVOICE`.
- Supplier name, address or GST number missing on the invoice of a registered supplier → `INVALID_TAX_INVOICE` (Q3).
- Foreign currency without SGD amounts → `FOREIGN_CURRENCY_NO_SGD_AMOUNTS`.

**Validity, MY (`validity_my.py`).** E-invoice (`is_einvoice`) missing any field in the mandatory set → `MISSING_MANDATORY_FIELD`. The tax treatment is computed as usual ("Unchanged" in the rule sheet).

**Tax, SG (`tax_sg.py`), first match wins:**
1. GST charged and supplier `gst_status` is not `registered` on the invoice date, or the printed GST number does not match the supplier record → `GST_WRONGLY_CHARGED`.
2. Supplier `gst_regime: ovr` and GST charged to the (registered) buyer → `GST_WRONGLY_CHARGED`.
3. An SG validity finding → `NOT_CLAIMABLE_INVALID_INVOICE`.
4. No GST charged → `NO_GST`.
5. Category is on the Regulation 26/27 list (club subscription, staff medical not obligatory, motor car costs, family benefits, medical and accident insurance, betting) → `NOT_CLAIMABLE_DISALLOWED`.
6. Otherwise → `CLAIMABLE`.

Vehicle cost where the documents don't say whether the vehicle is a motor car under Regulation 25(1), or staff medical where it's unclear whether WICA or a collective agreement makes it obligatory → no tax code; case is HAND_OVER by construction.

**Tax, MY (`tax_my.py`), per line, then combined:**
1. Service tax charged by a supplier without SST registration → `SST_SUPPLIER_NOT_REGISTERED`.
2. Sales tax on a Schedule C category, buyer holds a valid Schedule C certificate → `SST_SHOULD_BE_EXEMPT`.
3. Service tax on a Group G service, both parties registered, buyer provides the same service, not personal use, not employment or guard services → `SST_SHOULD_BE_EXEMPT`.
4. Service tax at 8% on logistics, F&B, telecoms or parking → `SST_WRONG_RATE`.
5. SST charged at the right rate by a registered supplier → `SST_CORRECT`.
6. No SST on any line and none due → `NO_SST`.

When lines differ, the invoice code is the first one in that order that any line has (Q4). Group relief appears only in HAND_OVER cases where the documents don't show whether the supplier is in the same group.

**Matching (`matching.py`).**
- No receipt at all for the PO lines billed → `NOT_RECEIVED`.
- Billed quantity above cumulative received quantity minus quantity already invoiced, beyond `quantity_tolerance_units` → `QUANTITY_ABOVE_RECEIVED`. Partial receipt with billed = received is fine (Q8).
- Unit price above the PO price (after approved amendments) by more than the tolerance → `PRICE_ABOVE_PO`. Verbal or email-only price approvals don't count, per the policy pack's `price_change_rule`.
- Sum of lines vs printed total within `rounding_tolerance` is fine. A gap beyond it has no rule in the sheet, so it is not planted in v0.9 (Q33).

**Routing (`routing.py`).**
- No PO reference and no PO for this supplier that fits, and the category is not in `non_po_policy.allowed_categories` (or above its `max_amount`) → `NO_PO`.
- Gross (in base currency, at the invoice's own stated rate) above the limit of the PO approver's role → `ABOVE_APPROVAL_LIMIT`.

**GL (`gl.py`).** PO-backed: the `gl_account` on the PO line. Non-PO: the CoA account mapped to the line category in the company's CoA template. Every generated invoice maps to one GL account (Q6). SG disallowed expenses book gross (incl. GST) to that expense account.

**Decide (`decide.py`).** Sort findings by tier and in-tier order. Decision from the top finding; `reason_codes` = all finding codes in that order (`MATCHED_WITHIN_TOLERANCE` for clean, plus `GST_NOT_CLAIMABLE_DISALLOWED` where it applies). HAND_OVER cases get `CANNOT_SETTLE_FROM_RULES`. Tax and GL as computed; tax is null only where the unsettled question is the tax itself.

Every answer key is also validated against `output.schema.json` as if it were a prediction.

### 5.4 The rule-sheet table, row by row

| # | Table row | Implemented in | Planted by family |
| --- | --- | --- | --- |
| 1 | SG valid invoice, registered, business → CLAIMABLE / APPROVE | `tax_sg` step 6 | clean SG |
| 2 | SG > S$1,000 without customer name or "Tax Invoice" | `validity_sg` | `sg_invalid_full_invoice` |
| 3 | SG foreign currency without SGD amounts | `validity_sg` | `sg_foreign_currency_no_sgd` |
| 4 | SG supplier GST number invalid or missing, GST charged | `tax_sg` step 1 | `sg_supplier_not_registered`, `sg_deregistered_supplier` |
| 5 | SG OVR vendor charges registered buyer | `tax_sg` step 2 | `sg_ovr_charged` |
| 6 | SG club, staff medical, motor car, family benefit → APPROVE, NOT_CLAIMABLE_DISALLOWED | `tax_sg` step 5 | `sg_disallowed_expense` |
| 7 | MY service tax 8% on logistics, F&B, telecoms, parking | `tax_my` step 4 | `my_service_wrong_rate` |
| 8 | MY Group G B2B exemption | `tax_my` step 3 | `my_group_g_b2b` |
| 9 | MY Schedule C raw materials | `tax_my` step 2 | `my_schedule_c` |
| 10 | MY service tax by unregistered supplier | `tax_my` step 1 | `my_supplier_not_registered` |
| 11 | MY correct rate, registered → SST_CORRECT / APPROVE | `tax_my` step 5 | clean MY |
| 12 | MY e-invoice missing mandatory field | `validity_my` | `my_einvoice_missing_field` |
| 13 | Facts not enough to tell → HAND_OVER | `decide` | `ambiguous_*` families |

## 6. Three worked examples

Amounts in the record's currency. Records are shortened to the fields that matter.

### 6.1 Clean MY case

```yaml
case_id: ap-my-00137
company: {company_id: my-c-007, legal_name: Teratai Plastik Industri Sdn Bhd,
          is_registered_manufacturer: true, services_provided: []}
policy_pack:
  tolerance_policy: {price_tolerance_pct: "2.0", quantity_tolerance_units: 0, rounding_tolerance: "0.05"}
  approval_matrix: [{approval_role: ops_manager, limit: "20000.00", currency: MYR}]
supplier: {supplier_id: S-0031, name: Awan Biru Systems Sdn Bhd, sst_type: service,
           sst_registration_no: W10-2403-32000418, turnover_band: "RM5m-25m",
           bank_account: {account_no: "5140 2201 8876"}}
purchase_order: {po_number: PO-26-0912, approver_id: p-007-03 (ops_manager),
  lines: [{line_no: 1, description: "IT support retainer, Oct 2026", category: it_services,
           qty: 1, unit_price: "3200.00", gl_account: "6150-100"}]}
goods_receipt: {gr_number: GR-26-1450, kind: service_confirmation, lines: [{po_line_no: 1, qty_received: 1}]}
invoice:  # MyInvois-style, is_einvoice: true, all mandatory fields present
  invoice_number: ABS-INV-2611-044, po_reference: PO-26-0912
  lines: [{qty: 1, unit_price: "3200.00", net_amount: "3200.00", tax_type: "02",
           tax_rate: "8", tax_amount: "256.00", classification_code: "022"}]
  totals: {net: "3200.00", tax: "256.00", gross: "3456.00"}
  bank_block: {account_no: "5140 2201 8876"}
history: 6 paid invoices from S-0031, none with this number or amount + period
emails: cover email from the supplier, intent invoice_cover
```

Rules engine:
- fraud: bank matches, no bank-change email → none
- duplicates: no match → none
- validity: e-invoice, mandatory set complete → none
- tax: IT service is taxable at 8%; buyer does not provide IT services, so the Group G B2B exemption does not apply; supplier registered → `SST_CORRECT`
- matching: receipt present; qty 1 = 1; price 3,200.00 = PO → none
- routing: PO present; 3,456.00 ≤ 20,000.00 → none

```yaml
answer: {decision: APPROVE, tax_treatment: SST_CORRECT, gl_account: "6150-100",
         reason_codes: [MATCHED_WITHIN_TOLERANCE], answer_source: rules}
exception_types: [], two_problems: false
```

### 6.2 SG tax case (disallowed expense)

```yaml
case_id: ap-sg-00548
company: {company_id: sg-c-012, legal_name: Larkspur Precision Engineering Pte Ltd, gst_reg_no: "M2-0098761-K"}
policy_pack: {approval_matrix: [{approval_role: finance_director, limit: "50000.00", currency: SGD}]}
supplier: {supplier_id: S-0207, name: Tanjong Lumba Golf & Country Club Pte Ltd,
           gst_status: registered, gst_regime: local, gst_reg_no: "20-0412377-W"}
purchase_order: {po_number: 4500018832, approver_id: p-012-01 (finance_director),
  lines: [{description: "Corporate membership, annual subscription Nov 2026 - Oct 2027",
           category: club_subscription, qty: 1, unit_price: "4800.00", gl_account: "6420-000"}]}
goods_receipt: {kind: service_confirmation, lines: [{po_line_no: 1, qty_received: 1}]}
invoice:  # PINT-SG-style
  document_title: "Tax Invoice", supplier_gst_no: "20-0412377-W",
  buyer_block: {name: Larkspur Precision Engineering Pte Ltd, address: present}
  lines: [{qty: 1, unit_price: "4800.00", net_amount: "4800.00", tax_category: SR, tax_rate: "9", tax_amount: "432.00"}]
  totals: {net: "4800.00", tax: "432.00", gross: "5232.00"}, currency: SGD
```

Rules engine:
- fraud, duplicates: none
- validity: above S$1,000; has "Tax Invoice", customer name and address, GST number, GST amount → valid
- tax: supplier registered, local; GST charged; invoice valid; category `club_subscription` is on the Regulation 26/27 list → `NOT_CLAIMABLE_DISALLOWED`
- matching, routing: none (5,232.00 ≤ 50,000.00)
- decision: no blocking finding → APPROVE (rule-sheet note 1: a disallowed expense is approved and booked without input tax)

```yaml
answer: {decision: APPROVE, tax_treatment: NOT_CLAIMABLE_DISALLOWED, gl_account: "6420-000",
         reason_codes: [MATCHED_WITHIN_TOLERANCE, GST_NOT_CLAIMABLE_DISALLOWED], answer_source: rules}
exception_types: [tax_disallowed], two_problems: false
```

The 9% SG rate is not written in the rule sheet. See Q2.

### 6.3 Two-problem case (price mismatch + wrong service-tax rate)

```yaml
case_id: ap-my-01206
company: {company_id: my-c-019, legal_name: Seri Kenari Foods Sdn Bhd}
policy_pack: {tolerance_policy: {price_tolerance_pct: "2.0"},
              approval_matrix: [{approval_role: logistics_manager, limit: "20000.00"}]}
supplier: {supplier_id: S-0388, name: Laju Muat Logistics Sdn Bhd, sst_type: service, sst_registration_no: present}
purchase_order: {po_number: PO-SKF-26-0331, approver: logistics_manager,
  lines: [{description: "Lorry haulage Shah Alam - Butterworth, 10-tonne", category: logistics,
           qty: 10, uom: trip, unit_price: "1180.00", gl_account: "5300-400"}]}
goods_receipt: {kind: service_confirmation, lines: [{po_line_no: 1, qty_received: 10}]}
invoice:
  lines: [{qty: 10, unit_price: "1240.00", net_amount: "12400.00", tax_type: "02", tax_rate: "8", tax_amount: "992.00"}]
  totals: {net: "12400.00", tax: "992.00", gross: "13392.00"}
emails: supplier note "fuel surcharge from October" (mentions_price_change: true, price_change_status: none)
```

Rules engine:
- fraud, duplicates, mandatory fields: none
- tax: logistics service is 6%; charged 8% → `WRONG_TAX_RATE`, tax treatment `SST_WRONG_RATE` (tier 3)
- matching: qty 10 = 10; price (1,240.00 − 1,180.00) / 1,180.00 = 5.08% > 2.0%; no PO amendment, the email does not count under `price_change_rule` → `PRICE_ABOVE_PO` (tier 4)
- routing: 13,392.00 ≤ 20,000.00 → none
- decision: top finding is tier 3 → REQUEST_CORRECTED_INVOICE

```yaml
answer: {decision: REQUEST_CORRECTED_INVOICE, tax_treatment: SST_WRONG_RATE, gl_account: "5300-400",
         reason_codes: [WRONG_TAX_RATE, PRICE_ABOVE_PO], answer_source: rules,
         truth_price_variance_pct: "5.08", requires_supplier_contact: true}
exception_types: [tax_wrong_rate, price_mismatch], two_problems: true
```

Agent-track step 4 expects the variance 5.08% (±0.5) and the price flagged, here through the `PRICE_ABOVE_PO` reason code even though the decision is REQUEST_CORRECTED_INVOICE.

## 7. Content: catalog, hard-case templates, phrasebanks

### 7.1 Catalog (`content/.../catalog/`)

About 60 categories (30 goods, 30 services). Each entry: `category`, `kind` (goods/service), `countries`, MY tax class (`sales_5`, `sales_10`, `sales_exempt`, `service_8`, `service_6`, `group_g`, `none`), Schedule C eligible (bool), SG Regulation 26/27 class (or none), GL role (the CoA template key), `source` (URL from the rule sheet). Categories whose rate the rule sheet does not settle are left out (Q9, Q10).

### 7.2 Hard-case template format (`content/.../hardcases/*.yaml`)

One file per family. Claude drafts the families in the planning chat; Sebastian reviews them as a content PR. The generator instantiates a template by applying **named operations** to a clean base case. There is no expression language and no `eval`: each op is a small Python function in `generator/ops.py` with typed parameters, so a template is data that can be reviewed line by line.

```yaml
family: partial_delivery_overbilled
version: 1
countries: [MY, SG]
primary_type: quantity_mismatch      # which quota it fills
weight: 3                            # relative weight within that type
summary: Part of the PO arrived; the invoice bills the full PO quantity.
params:
  ordered_qty: {int_range: [20, 400]}
  received_share: {choice: ["0.5", "0.6", "0.75", "0.8", "0.9"]}
  category: {catalog: {kind: goods}}
ops:
  - op: set_line_category   {line: 1, category: "{category}"}
  - op: set_po_qty          {line: 1, qty: "{ordered_qty}"}
  - op: set_received_share  {line: 1, share: "{received_share}"}
  - op: set_invoice_qty     {line: 1, qty: "{ordered_qty}"}
text:
  - {intent: delivery_partial_notice, from: supplier, probability: 0.4}
facts:
  - {role: stores, topic: delivery, release: on_topic, reply_key: receipt_partial}
expect:                              # an assertion, never the answer
  decision: DISPUTE_QUANTITY
  findings_include: [QUANTITY_ABOVE_RECEIVED]
```

- `expect` is checked against the rules engine's output. A mismatch fails generation. This is how template mistakes and engine bugs surface.
- Two-problem cases are a pair of families from `pairs.yaml`, applied primary first. Ops declare what they touch, so conflicting pairs are rejected at load time.
- Starting op library (~30): `set_po_qty`, `set_received_share`, `remove_receipt`, `set_invoice_qty`, `raise_unit_price_pct`, `add_po_amendment`, `change_invoice_bank`, `add_bank_change_email`, `add_verified_bank_change`, `add_history_duplicate`, `add_near_duplicate`, `add_credit_then_reissue`, `drop_invoice_field`, `set_document_title`, `drop_buyer_name`, `set_currency_without_sgd`, `set_tax_rate`, `set_supplier_unregistered`, `set_supplier_deregistered`, `set_supplier_ovr`, `give_buyer_schedule_c`, `make_buyer_provide_service`, `remove_po_reference`, `set_approver_limit_below`, `split_lines_mixed_tax`, `set_rounding_difference`, `make_lookalike_supplier`, `add_injection_email`, `set_vehicle_unspecified`, `add_decoy_email`.
- Families to draft (first list): partial delivery (billed = received, billed > received), credit note (clean, reissue after full credit), rounding (gaps within tolerance), mixed tax lines, near-duplicates (same amount new number; recurring monthly decoy), changed bank details (invoice only, email only, both; verified change decoy; lookalike sender), price increase (amended in ERP vs verbal only), all tax rows of §5.4, ambiguous (vehicle under Reg 25(1), Group G "same service" unclear, group relief unclear, staff medical obligation unclear, two equally fitting POs).
- **Decoys.** Every surface signal of a problem also appears on cases without that problem, at a set rate (for example 15% of clean cases have a benign bank-related email, 10% a price-increase notice that was amended in the ERP). This keeps text from giving the answer away (§8.5).

### 7.3 Phrasebank format (`content/.../phrasebanks/`)

YAML. A body is assembled from parts: greeting, opener, core, closing, signature. Shared parts live in `shared.yaml`; each intent has its own file.

```yaml
intent: bank_change_request
required_slots: [supplier_name, invoice_number, new_bank, new_account]   # every core must use all of them
expresses: {requests_bank_change: true}
variants:
  en:
    subject:
      - "Change of bank account - {supplier_name}"
      - "Updated remittance details for invoice {invoice_number}"
    opener:
      - "Please be informed that our banking details have changed."
    core:
      - "Kindly remit payment for {invoice_number} to {new_bank}, account no. {new_account}, with immediate effect."
  ms:
    core:
      - "Sila buat bayaran bagi invois {invoice_number} ke akaun baharu kami di {new_bank}, no. akaun {new_account}."
  zh:
    core:
      - "请将发票 {invoice_number} 的款项汇入我司新账户：{new_bank}，账号 {new_account}。"
  en_ms:     # code-mixed
    core:
      - "Boss, our bank account already change ya. Please bank in for {invoice_number} to {new_bank} {new_account}, thanks."
```

Line descriptions use the same idea per catalog category (`descriptions/{category}.yaml`) with slot fillers (materials, sizes, models, periods). Colleague replies use `replies/{reply_key}.yaml`.

**Linters (tests):** YAML schema; every core uses its `required_slots`; no unknown slot; script check per language (Latin for EN/MS, Han for ZH, Thai for TH); a blocklist of real company and bank names; no email addresses or phone numbers outside slots.

**Language mix (proposed, Q24):** line descriptions 80% EN, 8% MS, 8% ZH, 4% Thai+EN (only on MY invoices from Thai suppliers); emails 75% EN, 8% MS, 7% ZH, 10% code-mixed (EN-MS on MY, EN-ZH on both).

**How much text is needed.** Target: no email body repeats within a split, and no line description appears more than 5 times per split. About 2,800 cases give roughly 4,500 emails and 7,000 line descriptions.

| Bank | Unit | EN | MS | ZH | TH | Code-mixed |
| --- | --- | --- | --- | --- | --- | --- |
| Shared email parts (greeting / closing / signature) | entries | 12 / 12 / 8 | 8 / 8 / 6 | 8 / 8 / 6 | – | 6 / 6 / 4 per mix |
| Email intents (~16) | subjects per intent | 6 | 3 | 3 | – | 2 |
| | openers per intent | 6 | 3 | 3 | – | 3 |
| | core sentences per intent | 10 | 5 | 5 | – | 4 |
| Line descriptions (~60 categories) | templates per category | 6 | 3 | 3 | 2 (25 goods categories) | – |
| Slot fillers (materials, sizes, models, periods) | entries | ~400 | translations where needed | | | |
| Colleague and supplier replies (~20 keys + 6 fallbacks) | per key | 4 | 2 | 2 | – | 2 |
| Invoice notes and footers | entries | 20 | 8 | 8 | 6 | – |
| Policy document texts (5 documents) | templates each | 3 | – | – | – | – |

Totals: about 2,000 EN entries, 700 MS, 700 ZH, 150 TH, 250 code-mixed. For EN emails, 8 × 6 × 10 × 12 = 5,760 part combinations per intent before slots, which covers the ~800 uses of the most common intent (invoice cover) without repeats.

**Name banks (`content/.../names/`):** company name stems MY 200, SG 200, TH 60, plus 60 industry words each; person names (MY Malay 150, MY Chinese 100 given + 60 surnames, MY Indian 80, SG similar, TH 60 + 60); streets MY 250, SG 150; towns or districts with postcodes MY 120, SG 80; 12 fictional banks with plausible SWIFT-style codes (Q31). I recommend these banks instead of Faker (Q22).

## 8. Generation pipeline

### 8.1 Seeds and provenance

- `release-seeds.yaml` holds one public seed for train and one for test. They ship with each release.
- Every random draw uses `random.Random(derive(split_seed, case_index, purpose))`, where `derive` = first 8 bytes of sha256 over the joined strings. Adding a new purpose never shifts other draws.
- Never used: `hash()`, set iteration order, wall-clock time, `os.urandom`, unseeded numpy.
- `generator_version` = package version. `pipeline_hash` = sha256 over the sorted list of `(path, sha256)` for `models/`, `rules/`, `generator/`, `render/`, all of `content/`, and `uv.lock`. Each case row stores `(generator_version, seed, pipeline_hash)`.

### 8.2 Steps per split

1. Build companies (train 40, test 10; half MY, half SG; 15–30 suppliers each, 4–8 people) and background records (POs, receipts, 12 months of history, background mail).
2. Fill the quota table into case slots: country, company, primary type, optional secondary, family, `as_of_date` (spread over 5 Jan – 30 Oct 2026, after the last e-invoice phase and before the rule check of 13 Nov 2026).
3. For each slot: build a clean base scenario, apply family ops, add decoys.
4. Build `CaseView`, run the rules engine, compare planted with found. On mismatch, redraw with the next attempt number (max 20, then fail loudly).
5. Assemble text from phrasebanks (after the answer is fixed, so text follows the structured flags).
6. Run consistency checks (§8.4).
7. Export parquet (§4.10).
8. Render PDFs and images (§9) — separate command, so steps 1–7 run without Typst or Augraphy.

### 8.3 CLI

`db-generate --split train|test --out build/` uses the public seeds. For other users (the hidden repo) the same code takes `--split-spec spec.yaml` with `name`, `n_cases`, `seed`, `id_start`, `canary` and `--exclude-entities-from <public companies parquet>`. Nothing in this repo knows any particular private split.

### 8.4 Cross-file consistency checks

Run on every case; any failure stops the build.
- Line net = qty × unit price, rounded half-up to 2 dp. Tax per line (MY) or per category (SG). Totals tie exactly, except where a rounding family planted a gap within `rounding_tolerance`.
- PO reference exists and belongs to the supplier, unless a family removed it.
- Receipt lines point at PO lines. Receipt qty ≤ PO qty. Dates: PO ≤ receipt ≤ invoice ≤ `as_of_date`.
- Tax ids, names and bank details printed on the invoice equal the supplier record, unless a family changed them.
- SG foreign-currency invoices show SGD amounts, unless planted.
- PO line GL accounts exist and are active in the CoA. Approver exists and has a role in the matrix.
- Emails name existing invoice and PO numbers. Sender domains match supplier contacts, unless a lookalike is planted.
- The original of any duplicate is in the decision track's last-10 history.
- Fact-sheet facts are true of the records and never add a fact the answer depends on (Q13).
- Planted set = found set. HAND_OVER ⇔ `answer_source: handover_by_construction`.
- Quotas exact; 50/50 countries per type; two-problem count exact.
- Splits disjoint: company names, supplier names, tax ids, bank accounts, person emails.
- After rendering: the PDF text (via `pypdf`) contains invoice number, gross total and supplier tax id as formatted, and does not contain a field the record omits.

### 8.5 Text checks

- **Variety:** share of distinct email bodies per split ≥ 98%; no line description more than 5 times per split.
- **Shortcut check:** a small naive Bayes model (plain Python, ~50 lines) trained on train text only (subjects, bodies, descriptions, numbers stripped) predicts the decision on test. It must not beat the majority-class rate by more than 5 points. If it does, decoys or phrasebanks get fixed before release.

## 9. Rendering and scans

### 9.1 PDFs (Typst)

- Typst compiler pinned through the `typst` PyPI package (it bundles the compiler); the CLI at the same version is the fallback.
- At least 6 MY and 6 SG layouts in `content/.../typst/`. Variation: header position, table style, column order, date format (`13/11/2026`, `13 Nov 2026`, `2026-11-13`), number format, font family, accent colour, a vector monogram logo drawn from the company initials (no image files).
- Data goes in as a JSON file written to a temp folder outside the repo; layouts read it with `json()`.
- Fonts: Noto Sans, Noto Serif, Noto Sans Mono, Noto Sans SC, Noto Sans Thai, plus one or two more Latin families (all OFL). Listed in `fonts.lock.yaml` with URL and sha256, fetched by a script like `install-gitleaks.sh`, and baked into the build image. System fonts are ignored.
- A4, 1–2 pages. Thai shaping is handled by Typst.

### 9.2 Scans and photos (Augraphy)

- Proposed share (Q21): 70% digital PDF, 20% scan, 10% phone photo. Scans and photos are used only for 1-page invoices.
- Typst renders PNG at 200 ppi directly, so no extra rasteriser is needed.
- Two Augraphy pipelines with fixed parameter ranges in `core/render/degrade.py`: `scan` (paper texture, light ink bleed, low-ink lines, small rotation, photocopy noise) and `photo` (perspective, lighting gradient, shadow, slight blur). Severity is capped so text stays readable.
- Seeding: Augraphy `random_seed` from the case seed, plus `random` and `numpy` seeded inside the call. `cv2.setNumThreads(1)`.
- JPEG at fixed quality and subsampling, no EXIF or other metadata.

### 9.3 Byte reproducibility (step-08 plan §7.5a)

| Output | Goal | How it is checked |
| --- | --- | --- |
| Parquet (structured records and answers) | Byte-identical on rebuild from the tag, any machine with the locked environment | CI builds 100 cases twice on every generator PR; release builds all data twice and compares sha256. Any difference fails. |
| PDFs | Byte-identical inside the pinned build image | `SOURCE_DATE_EPOCH` = tag commit time, passed as Typst's creation timestamp; fixed fonts; no system fonts. Release double build compares. |
| JPEG scans and photos | Byte-identical inside the pinned build image on amd64; may differ elsewhere | Release double build compares. If they differ, the manifest covers records and PDFs only, and the card says images "may differ in bytes but not in content". |

The build image (`docker/build.Dockerfile`) is pinned by digest, built and pushed to GHCR by a workflow using `GITHUB_TOKEN` (no manual setup), and holds uv, the fonts and the Typst version. Local builds on a Mac are fine for development; release data is built only in the image.

### 9.4 Release wiring

- `hf-publish.yml` gains a `build-data` job: run `db-generate` and `db-render` in the build image twice, compare sha256, then `stage.py` as today.
- Uncomment the data and PDF lines in `release/allowlist.txt`.
- Card: add `configs`, remove `viewer: false` and the "Data not yet published" notice, fill in the Reproducibility sentence.
- `release/manifests/v0.9.0*.sha256` committed (exempt path).
- About 2,500 rendered files (~150 MB PDFs, ~250 MB JPEGs). `publish.py` uses `upload_folder` in one commit; the dry run checks the file count. If HF rejects the size, switch to `upload_large_folder` (Q32).

## 10. Agent environment

### 10.1 Design

- Core: the task set's `env/state.py` + `env/tools.py` on top of `core/env/base.py`, plain Python over one case's `CaseView`. Testable without Docker.
- Adapter: `core/env/server.py` exposes the tools through OpenEnv's `MCPEnvironment`. The first commit of D1 is a short spike that confirms the OpenEnv API at a pinned version. If it doesn't fit, the fallback is a plain MCP server (official `mcp` SDK) in the same image. The core doesn't change either way.
- Image: `docker/env.Dockerfile`, pinned base, loads the `companies` and `agent` rows for the run. It strips every `answer_*` column at load time. A test scans the container's files and the loaded state for `answer_` keys and fails if any appear.
- Inspect: `ap_agent` task uses the image as a Docker sandbox and connects to its MCP server. A Prime Intellect verifiers adapter can come later.
- Episode: the agent gets the invoice (record or file, per the run's input mode) and the instruction. It ends at the first terminal action or at a step limit (60 tool calls), which counts as no decision (scored as invalid output, Q19).

### 10.2 MCP tools

Read tools (all read-only; every call is written to the audit log):

| Tool | Inputs | Output |
| --- | --- | --- |
| `get_case_invoice` | – | invoice record and file reference |
| `search_suppliers` | `query?`, `tax_id?`, `bank_account?` | up to 10 `{supplier_id, name, tax ids, status}` |
| `get_supplier` | `supplier_id` | supplier record as of the case date, incl. bank on file and change log |
| `search_purchase_orders` | `supplier_id?`, `po_number?`, `status?` | up to 20 PO summaries |
| `get_purchase_order` | `po_number` | header, lines, approver, amendments |
| `get_goods_receipts` | `po_number` | receipts with lines |
| `search_invoices` | `supplier_id`, `invoice_number?`, `amount?`, `date_from?`, `date_to?`, `status?` | up to 20 history items |
| `get_invoice` | `invoice_id` | full history invoice or credit note |
| `list_inbox` | `query?`, `supplier_id?` | thread summaries |
| `read_thread` | `thread_id` | messages and attachment references |
| `list_policy_documents` | – | document ids and titles |
| `read_policy_document` | `doc_id` | text plus the structured table (tolerances, approval matrix, CoA, tax registration, exemption certificates) |
| `list_people` | – | colleagues and supplier contacts: id, name, role, email |

No tool gives information the decision track lacks, except colleague replies, and those never change the answer.

Clerk actions (the only writes):

| Tool | Inputs | Effect |
| --- | --- | --- |
| `send_email` | `to` (person or contact id), `topic` (fixed list, §4.7), `subject`, `body` | stores the email in the outbox; returns the scripted reply (§10.3) |
| `post_invoice` | common fields, `decision` must be APPROVE | terminal |
| `hold_invoice` | common fields, `decision` ∈ DISPUTE_PRICE, DISPUTE_QUANTITY, HOLD_NOT_RECEIVED, FRAUD_REVIEW, ROUTE_FOR_APPROVAL | terminal |
| `reject_invoice` | common fields, `decision` ∈ REJECT_DUPLICATE, REQUEST_CORRECTED_INVOICE | terminal |
| `hand_over` | common fields, `decision` = HAND_OVER; tax and GL may be null | terminal |

Common fields: `decision`, `tax_treatment`, `gl_account`, `reason_codes` (≥1), `supplier_id`, `po_number` (or null), `price_variance_pct` (max line variance in %, or null), `note`. A decision that doesn't fit the action, or a second terminal call, returns an error and writes nothing. Outputs follow `output.schema.json` rules.

### 10.3 Colleagues and suppliers (version 1, scripted)

- Fact sheets come from the hard-case template (`facts:`) plus defaults per role.
- On `send_email` to a person with a fact sheet: release every `always` fact, plus `on_topic` facts whose topic equals the email's `topic`. If nothing is released, use the fallback reply. Reply text is assembled from `replies/` phrasebanks with a seed derived from the case seed and the person, in the person's language. Fully reproducible, no model.
- Each person answers once per case (spec: "can be asked, once per case"). A second email to the same person gets an auto-reply "already answered" and releases nothing (Q16).
- The email body is kept for the step-10 judge; the scripted reply ignores it.
- Emails to an address that is only a lookalike sender in the inbox reach no one and count as a trap (§10.5).
- Version 2 (later, not in step 11): a pinned open model paraphrases the released facts.

### 10.4 Graders (final state)

Final state = the decision record, the outbox and the audit log, read from the sandbox after the episode by the Inspect scorer. The answer key comes from the dataset row, outside the sandbox.

| Step | Pass when |
| --- | --- |
| 1 supplier matched (gate) | `supplier_id` = `answer_supplier_id` |
| 2 PO matched (gate) | `po_number` = `answer_po_number` (null = null for no-PO cases) |
| 3 receipt looked up | audit log has `get_goods_receipts` for the true PO before the terminal action (passes if no PO exists) |
| 4 price variance | \|`price_variance_pct` − truth\| ≤ 0.5 points, and if the truth is beyond tolerance, `PRICE_ABOVE_PO` is in the reason codes or the decision is DISPUTE_PRICE; null passes only for no-PO cases (Q17) |
| 5 bank details compared | audit log has `get_supplier` for the true supplier before the terminal action |
| 6 duplicate check | audit log has `search_invoices` for the true supplier before the terminal action |
| 7 tax treatment | equals the answer key (passes if the key is null) |
| 8 GL account | equals the answer key (passes if the key is null) |
| 9 decision recorded | terminal action taken, ≥1 reason code, decision equals the answer key (Q18) |
| 10 supplier query clear | AI judge, only where `requires_supplier_contact`; reported separately |

A failed gate sets every later step to 0. A case passes only if steps 1–9 pass. Also recorded per case: steps used, tool calls, US$, time.

The judge (`core/graders/judge.py`) uses a committed prompt (the task set's `rubric/judge_prompt.md`) and a model id fixed for all of v0.9 (Q30). It runs only in our own runs, never in results CI.

### 10.5 Traps and bad-agent tests

Trap counters, reported next to the rubric: replied to a lookalike sender; followed an instruction injected in an email (decision equals what the injection asked for and differs from the key); posted with a bank-change email unread; tried an unknown write tool.

Tests in `tests/graders/` run scripted agents over 200 train cases:

| Agent | Expected |
| --- | --- |
| Oracle (test-only; calls the rules engine on the env's own reads) | 100% pass, cost 0 |
| Post everything without lookups | fails steps 3, 5, 6 on every case |
| Picks the lookalike supplier | gate 1 fails, steps 2–9 all 0 |
| Picks the first PO of the supplier | gate 2 fails where a decoy PO exists |
| Hands over everything | cost = 1 − share of HAND_OVER cases; steps 7–9 fail on decided cases |
| Random valid actions | pass rate < 5% |
| Emails everyone twice | second emails release nothing |
| Calls a terminal action twice / wrong decision for the action | rejected, state unchanged |
| Reads the filesystem for answers | finds no `answer_*` key |

The oracle proves the graders accept correct work. The others prove they reject bad work.

## 11. Scorer

### 11.1 Metrics (`core/scorer/metrics.py`, plain Python)

Per case, with `t` = answer decision and `p` = predicted decision:

| Condition | Cost (main) | 1/2/5 | 1/3/20 |
| --- | --- | --- | --- |
| prediction missing, duplicated or schema-invalid | 10 (Q19) | 5 | 20 |
| `p = t` | 0 | 0 | 0 |
| `p` = HAND_OVER, `t` ≠ HAND_OVER | 1 | 1 | 1 |
| `p` = APPROVE, `t` ≠ APPROVE | 10 | 5 | 20 |
| any other wrong `p` (incl. a non-approve on a HAND_OVER case) | 3 | 2 | 3 |

Critical error: `p` = APPROVE and `t` ∈ {REJECT_DUPLICATE, FRAUD_REVIEW}. This matches the spec plus the CHANGELOG clarification.

Aggregates:
- **cost per case** (main), and under 1/2/5 and 1/3/20
- **realistic-mix cost:** clean cases (empty `exception_types`) weighted to 80%, the rest to 20%, keeping their relative shares
- **plain accuracy:** share with `p = t` (a correct HAND_OVER counts)
- **coverage:** share with `p` ≠ HAND_OVER (invalid counts as decided)
- **accuracy on decided cases**
- **tax accuracy and GL accuracy** over decided cases whose key is not null; always printed next to coverage
- **critical errors:** count
- **risk–coverage:** only if every non-HAND_OVER prediction has `confidence`. Rank decided cases by confidence (ties grouped into one step). Risk at each step = error rate among cases kept. AURC = mean risk over all steps. HAND_OVER predictions are never "kept" (Q29).
- **US$ per 1,000 decisions** and **median latency:** from `metadata.yaml` for submissions; from Inspect logs and a committed price table for our runs
- **pass^3:** share of cases with `p = t` in all three runs

All metrics are also broken down by country, input mode, exception type and two-problem flag.

### 11.2 CLI

`db-score run1.jsonl run2.jsonl run3.jsonl --split test [--data v0.9.0 | --data-dir build/] [--aggregates-only] [--out scores.yaml]`

- Loads answer columns from the HF dataset at the pinned tag (sha256 checked against `release/manifests/`), or a local build.
- Validates each line against `output.schema.json`; reports invalid lines by line number.
- Needs only core dependencies (no Inspect). `--aggregates-only` never prints per-case lines (used by the hidden repo).

`db-leaderboard` rebuilds `results/ap-invoices-my-sg/v0.9/leaderboard.md` from all entry folders.

### 11.3 Inspect tasks

- `ap_decision(split="test", input="structured"|"pdf", epochs=3)`: dataset from the `decision` config; one sample per case; input = a committed prompt template + case file (structured JSON, or the PDF / JPG as document / image content where the provider supports it); target = answer key; solver = `system_message` + `generate` (optionally with the output schema as response format).
- Scorer `ap_case_scorer`: parses the output, scores it with `metrics.py`, returns a dict value (`decision_correct`, `cost`, `cost_125`, `cost_1320`, `tax_correct`, `gl_correct`, `critical`, `handed_over`, `valid`) plus confidence in metadata. Inspect `@metric` functions wrap the aggregates.
- `epochs=Epochs(3, reducer=at_least(3))` gives Inspect's pass^3. `inspect_scorers.py` also recomputes pass^3 from the per-epoch sample scores in the log. If the two differ, our number is reported and a warning is logged (Inspect bug #5612). A unit test builds a fake log where they must agree.
- `ap_agent(...)`: see §10.1; scorer combines the decision metrics with the rubric.

### 11.4 Results PR flow (CI)

New workflow `results.yml`, on pull requests touching `results/ap-invoices-my-sg/v0.9/**`, no secrets:
1. Check folder shape: three `predictions-run*.jsonl` + `metadata.yaml`; nothing else.
2. Validate `metadata.yaml` (required keys from `docs/submitting-results.md`).
3. Validate every prediction line; exactly 500 unique test `case_id`s per run.
4. Run `db-score` against the pinned HF tag; print the score table to the job summary.
5. Fail on any structural error. A bad score never fails CI.

After merge, Claude runs `db-leaderboard` in a follow-up commit. No CI job writes to the repo.

**Needed tooling fix:** `check_public.py` (repo mode, rule 5) currently rejects any `.jsonl` file in git, so a results PR would fail `guards.yml`. PR C adds `results/ap-invoices-my-sg/*/*/predictions-run[123].jsonl` to the repo-mode exemptions. Those files are still checked for `answer_*` fields and the hidden canary (Q27).

### 11.5 Baselines (`baselines/`)

- `always_approve.py`: APPROVE, tax = the country's "correct" code (`SST_CORRECT` / `CLAIMABLE`), GL = `"UNKNOWN"`.
- `always_hand_over.py`: HAND_OVER, null tax and GL. Cost = 1 − share of HAND_OVER cases = 0.97 by construction.
- `rules_only.py`: a short, independent heuristic script over the `decision` config (bank mismatch, exact invoice number match, price and quantity vs PO and receipt, missing listed fields, a rate table). A test forbids it from importing `decision_benchmark.rules`. It should score well but not perfectly; it doubles as a check on the answer keys (every disagreement in a sample of 50 is reviewed before release).

Each baseline is committed as a results entry (three identical runs, cost US$0).

## 12. Build order

Each row is one build PR, one commit per step, reviewed and merged before the next. I split the suggested B and D into smaller PRs and moved the final data release after the environment.

| PR | Contents | Acceptance checks |
| --- | --- | --- |
| **A** Data model + rules engine | package mode in `pyproject.toml`; pydantic models; catalog with sources; `rules/*`; tests; A8: split `core/` from `task_sets/ap_invoices_my_sg/` (case and answer envelopes, TaskSetSpec, registry; §3.1) | Every rule-sheet table row has ≥1 positive and ≥1 near-miss negative test; a test parses the table in `tax-rules-v0.9.md` and fails if a row has no registered test; priority tests for every tier pair; the three worked examples in §6 give exactly the answer keys shown; every answer key validates against `output.schema.json`; no network; `check_public` passes; A8: core never imports a task set or names one (test), every answer key fits the answer envelope and the TaskSetSpec, no answer key changed |
| **B1** Structured generator | core: seeds, quotas from TaskSetSpec, phrasebank assembler, envelope parquet export, `db-generate --task-set`; task set: entities, scenario, ops, hard-case loader with a starter set, starter phrasebanks, consistency checks; envelope copies removed from the payload `Case` (§3.1) | 2,000 / 500 cases with exact quotas and 15% two-problem; planted = found for every case; all §8.4 checks pass; two builds byte-identical; CI double-builds 100 cases; companies disjoint across splits; `check_public` staged mode passes on a local stage of the parquet files |
| **B2** Text content | full phrasebanks and hard-case families (content from Claude, reviewed by Sebastian), name banks, linters, variety and shortcut checks | linters pass; variety thresholds met; shortcut check ≤ majority + 5 points; every family's `expect` holds on 50 draws |
| **B3** Rendering + data alpha | core: `render/typst.py`, Augraphy `render/degrade.py`, PDF text check; task set: Typst layouts, fonts lock, `render/viewmodel.py`; build image, `build-data` job; `release/` takes `--task-set` and reads the HF repo id from the TaskSetSpec, one allowlist per task set (§3.1); card changes, manifest | every case renders; PDF text check passes; release values (HF repo id, schema path) come from the TaskSetSpec; release double build compares records and PDFs; card states what the manifest covers; dry run lists the expected ~2,500 files; then (on "release") `v0.9.0-alpha.2` with data (Q1) |
| **C** Scorer + baselines + results CI | core: `scorer/*` driven by the TaskSetSpec (costs, decisions, schema), `db-score`, `db-leaderboard`, Inspect task factory (decision task registered as `ap_decision`), trivial baselines, `results.yml`, `check_public` exemption; task set: rules-only baseline; pass^3 cross-check | hand-computed costs on a 20-case fixture, incl. every CHANGELOG clarification row; always-hand-over cost = 1 − HAND_OVER share exactly; pass^3 cross-check test; a fake results PR fixture passes, a broken one fails; baselines committed |
| **D1** Environment | core: `env/base.py`, OpenEnv adapter `env/server.py` (after spike), agent task in the Inspect factory; task set: `env/state.py`, MCP tools, colleagues; env image, Inspect `ap_agent` | every tool covered by tests; no `answer_*` reachable in the container; read-only except clerk actions (state hash unchanged after reads); colleague replies reproducible |
| **D2** Graders + bad agents | core: grader framework, judge wrapper; task set: `rubric/*` (10 steps, traps, judge prompt); bad-agent and oracle tests | oracle 100% pass; every bad agent behaves as in §10.5; gates zero later steps; then (on "release") `v0.9.0` |
| **H** Hidden repo (in `decision-benchmark-hidden`) | §13 | done there; nothing lands here |

Why this order: once `v0.9.0` data carries scores, any answer-key fix forces a new spec version. The alpha data release lets people look at the data while C and D still exercise it (rules-only disagreements, oracle agent). Only after both pass do we tag `v0.9.0`. If you prefer `v0.9.0` right after B3 as originally suggested, that also works; the risk is a v0.10 if C or D finds a key bug.

## 13. Hidden split (plan only; built in decision-benchmark-hidden)

- **Dependency.** The hidden repo pins this package to a tag (`git+https://github.com/sg-systems-co/decision-benchmark@v0.9.0`). Same rules engine, phrasebanks and hard-case families as train and test.
- **Generation.** Locally, in the hidden repo: `db-generate --split-spec <private spec> --exclude-entities-from <public companies parquet>`. The private spec holds the private seed, `n_cases: 300`, its own id range and the hidden canary string. Quotas give 120 / 30 / 30 / 24 / 24 / 21 / 15 / 15 / 12 / 9 and 45 two-problem cases. Own companies (6) and suppliers; the exclusion list guarantees no overlap with public names, tax ids or bank accounts.
- **Canary.** Every hidden row carries the hidden canary in its `canary` column; every hidden file carries it. This repo's `check_public.py` already fails on it.
- **Scoring verified runs.** On our own runner or a Modal job, with the public Inspect tasks pointed at local hidden data. Only aggregates leave the hidden repo (`db-score --aggregates-only`). The public results entry for a verified run holds `verified.yaml` with aggregates, never per-case lines.
- **The one hook.** A Claude Code `PreToolUse` hook in the hidden repo's `.claude/settings.json` (the same idea applies in decision-lab). Matcher `Read|Grep|Glob|Edit|Write|NotebookEdit|Bash`. A small script blocks (exit 2, with a message) any tool call whose path or command touches the hidden data folders, the private spec or the canary string. Bash is allowed only for an explicit list of commands (the build and aggregate-scoring commands, which print aggregates only). This keeps hidden cases out of Claude's context and so out of any API traffic.
- **Hook in this repo:** none needed. The only support this repo gives is generic: `--split-spec`, `--exclude-entities-from` and `--aggregates-only`.

## 14. What Sebastian and Claude must supply

| What | Who | When |
| --- | --- | --- |
| Answers to the open questions (§16) | Sebastian | before PR A |
| Catalog of categories with tax class and source URL | Claude drafts, Sebastian approves | in PR A |
| Starter phrasebanks (enough for B1 tests) | Claude drafts | in PR B1 |
| Full phrasebanks (§7.3 counts) and name banks | Claude drafts in the planning chat; Sebastian reviews | before PR B2 |
| Hard-case families (§7.2) | Claude drafts in the planning chat; Sebastian reviews | before PR B2 |
| Native-speaker check of MS, ZH, TH text (optional; recommended for TH) | a paid reviewer, ~1 hour per language | before B3 release |
| Typst layout look (approve 2–3 sample PDFs) | Sebastian | during B3 |
| Judge model id for step 10 | Sebastian | before D2 |
| Modal account | Sebastian | before hidden scoring (H) |
| Accounts for GHCR, HF | none new: GHCR uses `GITHUB_TOKEN`; `HF_TOKEN` exists | – |
| "Release" go-aheads for alpha.2 and v0.9.0 | Sebastian | after B3, after D2 |

## 15. Risks

1. **A rules-engine bug becomes a frozen wrong key.** Mitigation: planted = found, template `expect`, independent rules-only baseline review, oracle agent, alpha release before `v0.9.0`.
2. **Text gives the answer away.** Mitigation: decoys, structured flags drive answers, shortcut check gate.
3. **Images not byte-identical across machines.** Mitigation: release builds only in the pinned image; scope stated on the card.
4. **OpenEnv API shifts.** Mitigation: env core independent of it; pinned version; plain MCP fallback.
5. **Inspect bug #5612 or API changes.** Mitigation: pinned version, our own pass^3, results CI does not use Inspect.
6. **Augraphy is heavy (OpenCV, numpy and more) and slow-moving.** Mitigation: separate dependency group; if it breaks, replace with ~150 lines of numpy degradation.
7. **Tax rules beyond the sheet creep in** (goods rates, rental). Mitigation: plant only table rows; catalog entries need a source from the sheet.
8. **Tracks diverge.** Mitigation: one CaseView; fact sheets never change the answer; a test compares decision-track input with what the env can show.
9. **Real-world collisions** (a generated name or account number matching a real one). Mitigation: blocklist, fictional banks, card notice.
10. **Solo-maintainer load.** Mitigation: seven small PRs, few dependencies, content as reviewable YAML.
11. **Hidden data reaching Claude's context.** Mitigation: the hook; hidden work only in the hidden repo.

## 16. Open questions and decisions

Each has my recommendation. None changes the spec; several record a reading of it.

### Decisions (Sebastian, 13 Nov 2026)

All 33 recommendations are accepted as written, with these specifics:

- **Q1.** `v0.9.0-alpha.2` after B3; `v0.9.0` only after C and D2.
- **Q2.** 9% confirmed on the IRAS GST rates page. Cite it in `rules/constants.py` and record it as a CHANGELOG clarification.
- **Q3.** Accepted, plus a CHANGELOG clarification of rule-sheet row 4 ("invalid or missing" GST number): "missing" means the supplier is not registered, or the printed number doesn't match the supplier record → `GST_WRONGLY_CHARGED`. A registered supplier who just leaves the number off the invoice → `NOT_CLAIMABLE_INVALID_INVOICE`, per the IRAS invalidity list. Both end as REQUEST_CORRECTED_INVOICE.
- **Q19.** Worst cost (10; 5 and 20 under the alternatives), not counted as critical. CHANGELOG clarification.
- **Q22.** Faker dropped; committed name banks.
- **Q25.** A paid Thai check; spot checks for MS and ZH.
- **Q30.** Judge model decided at D2. Earlier PRs don't wait on it.
- **CHANGELOG.** The clarifications for Q2, Q3, Q19, Q20 and Q29 go into one block in PR A, while no scores exist.
- **Catalog.** Claude drafts it with sources in the planning chat for PR A, in the format PR A specifies.

### Questions as raised

1. **Release order.** Publish data first as `v0.9.0-alpha.2` after B3, tag `v0.9.0` only after C and D pass? *Recommend yes* (§12).
2. **SG GST rate.** The rule sheet never states 9%. *Recommend* using 9% (IRAS, since 1 Jan 2024), citing it in `rules/constants.py`, and adding it to CHANGELOG as a clarification while no scores exist.
3. **"GST number missing."** *Recommend:* supplier not registered, deregistered, or printed number not matching the record → `GST_WRONGLY_CHARGED` (table row 4); a registered supplier that just leaves its number off the invoice → `NOT_CLAIMABLE_INVALID_INVOICE` (IRAS invalidity list).
4. **One tax code for mixed lines.** *Recommend* the precedence in §5.3 for MY; for SG, never mix claimable and disallowed lines on one invoice in v0.9.
5. **SG buyers not GST-registered.** No code fits. *Recommend* all SG buyers are registered in v0.9.
6. **One GL account per invoice.** *Recommend* every generated invoice maps to one account; GL = PO line account, or the CoA mapping for non-PO.
7. **Order inside the mismatch tier.** *Recommend* not received > quantity > price, and never plant two problems from the same tier.
8. **Partial delivery.** *Recommend:* no receipt → HOLD_NOT_RECEIVED; partial receipt with billed > received → DISPUTE_QUANTITY; billed = received → no finding.
9. **Sales-tax wrong rate on goods.** The table lists only the service-tax case. *Recommend* planting wrong rates only per the table; goods with sales tax appear in clean cases only from catalog entries with a source.
10. **Rental and construction.** Rental's B2B exemption isn't specific enough to compute. *Recommend* no rental lines in v0.9; construction at 6% allowed in clean cases, wrong-rate planting only on the four listed categories.
11. **E-invoice expected but a plain invoice sent.** Not in the table. *Recommend* not planted in v0.9.
12. **Credit notes.** *Recommend* only clean credit notes (APPROVE, tax treatment of the original) and the credit-then-reissue decoy.
13. **Fact sheets and answers.** Both tracks share one key, so *recommend* fact sheets only confirm or explain facts already in the records, or add facts the policy pack says don't count (verbal price approval).
14. **Ambiguous cases with a second problem.** *Recommend* never.
15. **Tax treatment on non-approve decisions** (incl. duplicates). *Recommend* the treatment of the document itself, as if it were the only copy.
16. **"Asked once per case."** *Recommend* once per person per case, with a required `topic` from a fixed list plus free text.
17. **Rubric step 4 "±0.5%".** *Recommend* reading it as ±0.5 percentage points on the reported max line variance, plus "flagged" = `PRICE_ABOVE_PO` reason code or DISPUTE_PRICE.
18. **Rubric step 9.** *Recommend* it requires the correct decision plus ≥1 reason code; otherwise a case could "pass" with a wrong decision.
19. **Invalid, missing or duplicate predictions, and agent step-limit timeouts.** The spec says "wrong decision" but cost depends on which wrong decision. *Recommend* the worst cost (10; 5 and 20 under the alternatives), not counted as critical. Record it in CHANGELOG as a clarification.
20. **Tax/GL keys on HAND_OVER cases.** *Recommend* null tax where the open question is the tax itself; GL always set; null keys excluded from tax/GL accuracy.
21. **Scan/photo share.** *Recommend* 70% PDF, 20% scan, 10% photo.
22. **Faker.** Its locales don't cover Malaysian and Singaporean names and addresses well, and its output changes between versions. *Recommend* dropping it for committed name banks (a deviation from the PROPOSED stack).
23. **Fonts in git.** *Recommend* not committing them: lock file with sha256, fetched by script, baked into the build image.
24. **Language mix.** *Recommend* the shares in §7.3.
25. **Native-speaker review.** *Recommend* a paid check for Thai, spot checks for MS and ZH.
26. **Company counts.** *Recommend* 40 train, 10 test (half MY, half SG), 6 hidden; 15–30 suppliers each.
27. **check_public and results files.** Rule 5 rejects predictions JSONL in git today. *Recommend* the exemption in PR C (still scanned for `answer_*` and the canary).
28. **PDF input in Inspect.** *Recommend* passing PDFs as document content where the provider supports it; our PDF-track baselines use only such models.
29. **Risk–coverage definition.** *Recommend* error-rate risk, ties grouped, AURC = mean risk over steps; no curve if any decided prediction lacks confidence.
30. **Step-10 judge model.** *Recommend* one Claude model id fixed for all of v0.9, committed prompt, reported separately.
31. **Bank names.** *Recommend* fictional banks with plausible codes, not real banks.
32. **Upload size.** *Recommend* keeping `upload_folder`; switch to `upload_large_folder` only if the dry run or first upload fails.
33. **Totals that don't tie.** A gap between the sum of lines and the printed total beyond the policy's rounding tolerance has no rule in the sheet. *Recommend* not planting it in v0.9; rounding families plant only gaps within tolerance (APPROVE).
