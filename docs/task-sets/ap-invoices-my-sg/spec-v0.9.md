# SG Systems Decision Benchmark — Task set 1 (supplier invoices, MY/SG) — spec v0.9

Status: approved and frozen, 13 Nov 2026. Changes need a version bump.

## Scope and version

This spec defines task set 1 of the SG Systems Decision Benchmark: supplier-invoice decisions for buying companies in Malaysia and Singapore. Version v0.9 is "synthetic, rules-based". Accountant review and the real-data check with the first customer come after launch, and lead to a new version. Any change to a rule, the decision list or the scoring raises the version, and scores are compared only within one version.

- **The job being tested:** an accounts-payable clerk receives a supplier invoice, checks it against the company's records and rules, and decides what happens to it. That includes the tax treatment and the GL account, or handing it to a person.
- **In scope:** goods and services invoices and credit notes from local and foreign suppliers. Malaysian SST (sales tax and service tax), Singapore GST, PO matching, duplicates, invoice validity, changed bank details, approval limits.
- **Out of scope for v0.9:** payment runs, month-end close, multi-currency revaluation, withholding tax, customs and import permits, and expense claims (planned as a later task set).
- **Two tracks on the same cases:**
  - Decision track: a model gets the full case file and returns a decision.
  - Agent track: an agent gets only the invoice and has to look the rest up through MCP tools before deciding.

## Case format

Each case belongs to one fictional buying company. A company's records are shared by all its cases, as in a real ERP. Every company comes with a policy pack: AP tolerance policy, approval matrix, chart of accounts with GL codes, its tax registration, and its exemption certificates where relevant.

| Part | Contents | Decision track | Agent track |
| --- | --- | --- | --- |
| Invoice | Structured record (MyInvois-style fields for Malaysia, Peppol PINT-SG-style fields for Singapore) plus a rendered PDF; some cases are scans or photos | Given | Given |
| Purchase order | PO lines, prices, quantities, approver | Given | Looked up |
| Goods receipt | What was received and when | Given | Looked up |
| Supplier record | Name, tax registration, bank account on file, payment terms | Given | Looked up |
| History | Paid and open invoices from the same supplier | Given (last 10) | Looked up |
| Email thread | Supplier or colleague messages linked to the invoice, if any | Given | Looked up in the AP inbox |
| Policy pack | Tolerances, approval limits, chart of accounts, tax registration | Given | Looked up in the policy folder |
| People | Simulated procurement colleague and supplier who answer questions | Not used | Can be asked, once per case |
| Answer key | Decision, tax treatment, GL account, reason codes, source of the answer (rules or experts) | Never shown | Never inside the environment |

- **Languages:** documents are mostly English. Some line descriptions and emails are in Bahasa Malaysia or Chinese, and a few Malaysian invoices from Thai suppliers carry Thai text.
- **Modality:** v0.9 ships both the structured record and the rendered PDF. Entrants say which they used, and results are reported separately for each.

## Decisions, tax treatment and exception mix

Every output has one decision, one tax treatment and one GL account. The decision names follow evalsafe's style. The mapping is a first guess, to be checked against evalsafe's own documentation in the planning run.

| Decision | When it is right | Closest evalsafe action |
| --- | --- | --- |
| APPROVE | Matches PO and receipt within tolerance, valid invoice, tax correct, within approval limit | (approval, name to confirm) |
| DISPUTE\_PRICE | Unit price above the PO price beyond tolerance | DISPUTE\_LINES |
| DISPUTE\_QUANTITY | Billed quantity above the received quantity | DISPUTE\_LINES |
| HOLD\_NOT\_RECEIVED | Goods or service not yet received | HOLD\_REQUEST\_DOCUMENTS |
| REJECT\_DUPLICATE | Same invoice already paid or open | REJECT\_AS\_DUPLICATE |
| REQUEST\_CORRECTED\_INVOICE | Invoice invalid or tax wrongly charged: missing mandatory fields, supplier not tax-registered, wrong rate, tax charged when an exemption applies | REQUEST\_CORRECTED\_INVOICE |
| FRAUD\_REVIEW | Bank details differ from the supplier record, or the change came only by email | FRAUD\_REVIEW |
| ROUTE\_FOR\_APPROVAL | No PO, or amount above the approver's limit | HUMAN\_APPROVAL / PROCUREMENT\_REVIEW |
| HAND\_OVER | The model is not sure enough to decide, or the case cannot be settled from the information available | (none) |

**Tax treatment.** The two countries need different questions, because Malaysian SST is not a credit system like GST.

- **Singapore (GST):** can the buyer claim the GST as input tax? Per [IRAS](<https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax>), a claim needs a valid tax invoice addressed to the buyer, a GST-registered supplier, business use, and the expense must not be disallowed under Regulations 26 and 27. Codes:
  - CLAIMABLE
  - NOT\_CLAIMABLE\_DISALLOWED (club fees, staff medical, motor car costs, family benefits)
  - NOT\_CLAIMABLE\_INVALID\_INVOICE
  - GST\_WRONGLY\_CHARGED (e.g. supplier not registered, or an overseas vendor under OVR charging a GST-registered buyer)
  - NO\_GST
- **Malaysia (SST):** was the tax charged correctly? [Sales tax is single-stage](https://mysst.customs.gov.my/faq-sales-tax/), and there is no input credit to claim. The clerk's question is whether the supplier should have charged it, and at which rate. Codes:
  - SST\_CORRECT
  - SST\_WRONG\_RATE (service tax is [8%, or 6% for F&B, telecoms, parking and logistics](https://mysst.customs.gov.my/faq-services-tax/); sales tax is 5% or 10%)
  - SST\_SHOULD\_BE\_EXEMPT (e.g. the [B2B exemption for Group G services](https://mysst.customs.gov.my/assets/document/Industry%20Guides/GI/Guide%20on%20Management%20Services%20%20V5%206.5.2026.pdf) between registered persons, or raw materials bought under a Schedule C certificate)
  - SST\_SUPPLIER\_NOT\_REGISTERED
  - NO\_SST
- Full rules, with sources, are in the [tax-rule sheet](tax-rules-v0.9.md), verified against the official pages on 13 Nov 2026. Answers follow official rules and guidance only.

**GL account:** one code from the company's chart of accounts. Scored as exact match.

**Exception mix:**

| Share of cases | Type |
| --- | --- |
| 40% | Clean, should be approved |
| 10% | Tax problems (wrong rate, should be exempt, not claimable, invalid tax invoice) |
| 10% | Price mismatch |
| 8% | Quantity mismatch |
| 8% | Invalid invoice or missing mandatory fields |
| 7% | Duplicates, including near-duplicates (same amount, different invoice number) |
| 5% | Not received |
| 5% | No PO or above the approval limit |
| 4% | Changed bank details (trap) |
| 3% | Ambiguous, where handing over is the right answer |

About 15% of cases carry two problems at once, for example a price mismatch on an invoice that also has the wrong tax rate. The answer key sets the decision by a fixed priority: fraud, then duplicate, then invalid invoice, then mismatch, then routing.

## Output and scoring

**Output, one JSON object per case:**

```json
{"case_id": "ap-my-00421", "decision": "DISPUTE_PRICE", "tax_treatment": "SST_CORRECT", "gl_account": "5100-200", "reason_codes": ["PRICE_ABOVE_PO"], "confidence": 0.82, "explanation": "Unit price RM 12.40 vs PO RM 11.80, +5.1%, tolerance 2%."}
```

- `confidence` (0–1) is optional. Without it, no risk–coverage curve can be drawn for that entry.
- `explanation` is free text. It is never scored on the leaderboard, only used in the AI-judged extras.
- Anything that breaks the schema, or names two decisions, is scored as a wrong decision.

**Cost per case (the leaderboard score; lower is better):**

| Outcome | Cost |
| --- | --- |
| Right decision | 0 |
| HAND\_OVER when handing over is the right answer | 0 |
| HAND\_OVER on any other case | 1 |
| Wrong hold, dispute or route (a false alarm) | 3 |
| Wrong APPROVE (a missed problem) | 10 |
| APPROVE on a trap (duplicate, changed bank details) | 10, plus counted as a critical error |

There is no industry-standard set of weights for AP decisions. Existing benchmarks report accuracy or criteria passed, and selective-prediction research reports risk–coverage curves instead of fixed costs. Our weights follow the business logic: a handover costs one review, a false alarm costs a review plus a round trip with the supplier, and a missed problem means money paid out wrongly. The weights are published and adjustable. Results are also shown under two other weightings (1 / 2 / 5 and 1 / 3 / 20), plus plain accuracy and the risk–coverage curve, so nobody has to accept ours. The cost score is the average cost per case. A second, realistic-mix score reweights results to 80% clean cases, closer to what an AP team actually receives.

**Also reported for every entry:**

- accuracy on the cases it decided
- coverage: the share it decided instead of handing over
- risk–coverage curve and its area, if confidence was given
- tax-treatment accuracy and GL accuracy, each scored separately
- number of critical errors
- US$ per 1,000 decisions and median latency
- pass^3: the share of cases right in all three repeated runs

**Agent track, per case:** the same decision is scored with the same costs, plus a rubric checked by code against the final state of the simulated systems:

1. supplier matched (gate)
2. PO matched (gate)
3. receipt looked up
4. price variance computed and within tolerance, or flagged (±0.5%)
5. bank details compared with the record
6. duplicate check done
7. tax treatment
8. GL account
9. decision recorded with a reason code
10. supplier query clear (AI judge, reported separately)

A failed gate sets every later step to 0. A case "passes" only if steps 1–9 all pass. The agent track adds steps used, tool calls, US$ per case and time per case.

**Baselines published with v0.9:**

- Two trivial entrants that every real entry must beat: "always approve" and "always hand over". The latter scores a cost of about 1.0 by construction.
- A rules-only script with no AI.
- 6–8 models, each run both with a prompt only and as an agent.

**Anti-gaming:**

- Answer keys never sit in the environment, and the environment is read-only except clerk actions.
- Handing everything over costs about 1.0 per case, so it cannot win.
- Contradictory or malformed outputs count as wrong.
- Graders are tested against deliberately bad agents before release.
- The hidden split is scored only by us.

## Splits, ground truth and open questions

**Splits:**

| Split | Cases | Where | Use |
| --- | --- | --- | --- |
| Train | 2,000 | Public (Hugging Face) | Anyone may train on it |
| Test | 500 | Public | Self-reported results |
| Hidden | 300 | decision-benchmark-hidden, private | Verified leaderboard runs only; never used for training or tuning, including by us |

Each split uses its own fictional companies and suppliers, so nothing leaks between them. Hard cases appear in all three, in the same proportion.

**Where the right answer comes from:**

- Every answer is computed by the generator's rules engine from the policy pack and the tax-rule sheet, following official rules and guidance only.
- Hard cases, such as two problems at once, partial deliveries, credit notes, rounding and mixed tax lines, are drafted from known real-world failure patterns. Their answers still come from the rules.
- Where the official rules do not settle a case, HAND\_OVER is the right answer by construction.
- Accountant review of the hard cases and the realism check against real cases happen after launch, with the first customer. The result is released as a new version.

**Versioning:** v0.9 ("synthetic, rules-based") at first release. v1.0 only after accountant review and the real-data check on 100–300 anonymised past cases from the first customer. Every release ships the generator seed and a changelog.

**Decided with Sebastian (13 Nov 2026). Spec approved and frozen as v0.9:**

1. Cost weights: keep 0 / 1 / 3 / 10 as the main score. There is no industry standard, so two other weightings, plain accuracy and the risk–coverage curve are shown next to it.
2. Case mix: 40% clean, 60% with a problem, so the test has enough hard cases to tell models apart. If 90% of cases were clean, as in a real inbox, "always approve" would look good. A realistic-mix score (80% clean) is reported alongside.
3. Countries: 50/50 Malaysia and Singapore. The benchmark, and Casesure, must handle both.
4. Formats: v0.9 ships both the structured invoice record and the rendered PDF or scan, and results are reported separately for each.
