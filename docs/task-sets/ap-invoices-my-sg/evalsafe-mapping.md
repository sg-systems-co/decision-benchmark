# evalsafe mapping, ap-invoices-my-sg

Checked on 13 Nov 2026 for spec v0.9. The spec names an evalsafe action for each of our decisions as a first guess. This file records what evalsafe's own data shows. **The v0.9 spec is not changed.** Differences are kept here for a later spec version.

**Source.** `typesafeAI/evalsafe-invoice-processing` on Hugging Face, snapshot 2026-09-28, 150 cases, Apache-2.0. Its card and `dataset.json` don't list action names. The names were read from the `consensus` labels in all 150 cases (450 decisions across three policies, `startup`, `enterprise` and `high_volume_retailer`) through the public dataset viewer.

**What I found:**
- evalsafe uses 16 actions: PAY, SCHEDULE_PAYMENT, DISPUTE_LINES, SHORT_PAY, HOLD_REQUEST_DOCUMENTS, HOLD_VERIFY_BANK_DETAILS, VERIFY_VENDOR_OUT_OF_BAND, FRAUD_REVIEW, REJECT_AS_DUPLICATE, DUPLICATE_REVIEW, REJECT_AS_UNAUTHORIZED, REQUEST_CORRECTED_INVOICE, PROCUREMENT_REVIEW, PROJECT_OWNER_REVIEW, HUMAN_APPROVAL, APPROVAL_ESCALATION.
- Each evalsafe decision is a **set of actions plus one primary action**, scored as exact set match or primary match.
- The right answer can differ between its three company policies.

Meanings are inferred from names plus case features (for example, bank account on the invoice vs. the vendor record). evalsafe doesn't document them.

| Our decision | Spec's guess | Checked | Status |
| --- | --- | --- | --- |
| APPROVE | (to confirm) | **SCHEDULE_PAYMENT** (pay on terms; 15 primary), or **PAY** (12 primary). evalsafe has no APPROVE. | Corrected: SCHEDULE_PAYMENT closest |
| DISPUTE_PRICE | DISPUTE_LINES | DISPUTE_LINES exists. SHORT_PAY appears only as a secondary action. | Confirmed. evalsafe doesn't split price from quantity. |
| DISPUTE_QUANTITY | DISPUTE_LINES | as above | Confirmed |
| HOLD_NOT_RECEIVED | HOLD_REQUEST_DOCUMENTS | Exists (24 primary). It's broader than our use: any missing document. | Confirmed, broader |
| REJECT_DUPLICATE | REJECT_AS_DUPLICATE | Exists (18 primary). Cases with matching prior numbers or amounts cluster here. evalsafe also has DUPLICATE_REVIEW for unclear duplicates. | Confirmed. Our near-duplicates may match DUPLICATE_REVIEW. |
| REQUEST_CORRECTED_INVOICE | REQUEST_CORRECTED_INVOICE | Exists. The most common action overall (242), often secondary. | Confirmed |
| FRAUD_REVIEW | FRAUD_REVIEW | FRAUD_REVIEW exists (bank differs in 11 of 15 cases). **HOLD_VERIFY_BANK_DETAILS** also exists (bank differs in 9 of 10). VERIFY_VENDOR_OUT_OF_BAND is the most common primary action (115) and isn't tied to bank mismatch. | Partly corrected: our changed-bank-details case maps to FRAUD_REVIEW or HOLD_VERIFY_BANK_DETAILS, depending on the signals |
| ROUTE_FOR_APPROVAL | HUMAN_APPROVAL / PROCUREMENT_REVIEW | Both exist. PROCUREMENT_REVIEW clusters on missing PO (13 of 36). Also APPROVAL_ESCALATION (above limit, secondary only) and PROJECT_OWNER_REVIEW (59 primary). | Confirmed. Above-limit maps closest to HUMAN_APPROVAL / APPROVAL_ESCALATION. |
| HAND_OVER | (none) | No equivalent. evalsafe always decides. | Confirmed: none |
| — | — | REJECT_AS_UNAUTHORIZED (17 primary) has no equivalent in ours | Gap, noted |

**For a later spec version (no spec change now):**
- Consider SCHEDULE_PAYMENT as an alias name for APPROVE in any evalsafe-compatible export.
- Consider splitting FRAUD_REVIEW into "verify bank details" and "fraud review".
- Consider a "reject as unauthorised" decision.
- Consider multi-action outputs with a primary action, as an extra metric next to our single decision.
