# SG Systems Decision Benchmark — Task set 1 — tax-rule sheet v0.9

Status: verified against the official sources on 13 Nov 2026. Accountant review after launch.

Rules the benchmark's tax checks use, taken only from official pages, verified against those pages on 13 November 2026, with accountant review after launch. Not tax advice.

## Singapore: GST

**Question the benchmark asks:** can the buying company claim the GST on this supplier invoice as input tax?

**Conditions for a claim** ([IRAS, conditions for claiming input tax](<https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax>)): all must hold.

1. The buyer is GST-registered.
2. The goods or services are supplied to the buyer.
3. They are used for the purpose of the business.
4. Local purchases are supported by a valid tax invoice addressed to the buyer, or a simplified tax invoice.
5. Imports are supported by import permits (out of scope for v0.9).
6. The input tax is attributable to taxable supplies.
7. The claim is not disallowed under Regulations 26 and 27 of the GST (General) Regulations.
8. Reasonable steps have been taken to rule out missing trader fraud ([IRAS e-Tax guide](<https://www.iras.gov.sg/docs/default-source/archive/etaxguide_gst_gst-general-guide-for-businesses(1).pdf?sfvrsn=4307f059_4>)). Not modelled in v0.9.

**Valid tax invoice** ([IRAS, invoicing customers](<https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/invoicing-price-display-and-record-keeping/invoicing-customers>)). A full tax invoice shows all of these:

- the words "Tax Invoice"
- supplier's name, address and GST registration number
- invoice date and number
- customer's name and address
- description of the goods or services
- GST rate
- total excluding GST, GST amount, and total including GST

IRAS lists common reasons an invoice is invalid:

- no supplier name, address or GST number
- above S$1,000: no "tax invoice" wording, customer name or GST amount
- S$1,000 or below: no GST amount and no "price includes GST" statement
- foreign-currency invoices without the Singapore dollar amounts

**GST wrongly charged:**

- The supplier has no GST registration number, or it is invalid or expired.
- An overseas vendor registered under the OVR regime charges GST to a GST-registered buyer. IRAS says not to claim it, and to ask the vendor for a refund instead.

**Disallowed even with a valid invoice (Regulations 26 and 27):**

- benefits for staff's family members or relatives
- costs and running expenses of motor cars, unless the car is excluded from the definition in Regulation 25(1)
- club subscription fees (including transfer fees) charged by sports and recreation clubs
- staff medical expenses, unless obligatory under the Work Injury Compensation Act or a collective agreement
- medical and accident insurance
- betting, sweepstakes, lotteries and games of chance ([IRAS guide on reimbursements](https://www.iras.gov.sg/docs/default-source/e-tax/etax-guide_guide-on-reimbursement-and-disbursement-of-expenses_2019-12-30.pdf?sfvrsn=3254880e_32))

**Timing:**

- Input tax is claimed in the period of the tax invoice date.
- If the supplier is not paid within 12 months of the due date, the claim must be repaid ([IRAS](<https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/claim-input-tax-in-the-correct-accounting-period>)).
- The same purchase must not be claimed twice, which ties into the duplicate check.

## Malaysia: SST and e-invoices

**Question the benchmark asks:** was SST charged correctly on this invoice? Malaysia has no input tax credit like GST, so wrongly charged SST is a cost the buyer must push back on.

**Sales tax:**

- [Sales tax is single-stage](https://mysst.customs.gov.my/faq-sales-tax/). It is charged on taxable goods manufactured in Malaysia by a registered manufacturer and sold by them, and on imported taxable goods.
- Rates are 5% or 10% on discretionary and non-essential goods, with essential goods exempt ([MOF, 9 June 2025](https://www.mof.gov.my/portal/en/news/press-release/targeted-revision-of-sales-tax-rate-and-expansion-of-service-tax-scope-effective-1-july-2025)).
- **Schedule C:** a registered manufacturer can buy raw materials, components, packaging and manufacturing aids exempt from sales tax ([RMCD FAQ](https://mysst.customs.gov.my/faq-sales-tax/)). Sales tax on such a purchase, when the buyer holds the exemption, should not have been charged.

**Service tax:**

- The rate is [8% for taxable services, except F&B, logistics, telecommunications and parking at 6%](https://mysst.customs.gov.my/faq-services-tax/). Credit and charge cards pay RM25 per card. The 8% rate applies from 1 March 2024.
- From 1 July 2025 the scope added leasing or rental, construction, financial services, private healthcare, education and beauty services ([MOF](https://www.mof.gov.my/portal/en/news/press-release/targeted-revision-of-sales-tax-rate-and-expansion-of-service-tax-scope-effective-1-july-2025)).
  - Rental is charged at 8%, with exemptions including [B2B transactions and group relief](https://www.mof.gov.my/portal/pdf/siaran-media/expansion-sst-scope.pdf).
  - Construction works are at 6% ([Budget 2026 revenue section](https://belanjawan.mof.gov.my/pdf/belanjawan2026/revenue/section2.pdf)).
- **B2B exemption for Group G professional services** ([RMCD guide on management services](https://mysst.customs.gov.my/assets/document/Industry%20Guides/GI/Guide%20on%20Management%20Services%20%20V5%206.5.2026.pdf)). It applies when:
  - both provider and recipient are registered persons
  - the recipient provides the same service
  - it is not for personal use
  - employment services and guard services are excluded
- **Group relief:** some Group G services between companies in the same group are not taxable ([Service Tax Policy 8/2020](https://mysst.customs.gov.my/assets/document/Service%20Policy/STP%208_2020.pdf)).
- **Registration:** for Group G services the threshold is RM500,000 over 12 months ([RMCD](https://mysst.customs.gov.my/registering-business/)). A supplier below it, and not registered, should not charge service tax.

**E-invoices (MyInvois):**

- An e-invoice has [55 data fields](https://www.hasil.gov.my/media/fzagbaj2/irbm-e-invoice-guideline.pdf).
- The [MyInvois data structure](https://sdk.myinvois.hasil.gov.my/documents/invoice-v1-0/) marks as mandatory:
  - supplier and buyer TIN
  - registration numbers
  - e-invoice type code and date
  - currency
  - a line classification, description, unit price and tax type per line
  - total tax per tax type
- Tax type codes are [01 sales tax, 02 service tax, 03 tourism tax, 04 high-value goods tax, 05 sales tax on low-value goods, 06 not applicable, E exemption](https://sdk.myinvois.hasil.gov.my/codes/tax-types/).
- Who must issue e-invoices, per the [LHDN implementation timeline](https://www.hasil.gov.my/en/e-invois/pelaksanaan-e-invois-di-malaysia/garis-masa-pelaksanaan-e-invois/) (updated 30 August 2026):
  - turnover above RM100 million from 1 August 2024
  - above RM25 million from 1 January 2025
  - above RM5 million from 1 July 2025
  - up to RM5 million from 1 January 2026
  - below RM3,000,000: exempt
- The generator gives every Malaysian supplier a turnover band, so each case knows whether an e-invoice is expected.

## From rules to benchmark checks

| Situation planted in a case | Tax treatment in the answer key | Decision |
| --- | --- | --- |
| SG: valid tax invoice, registered supplier, business expense | CLAIMABLE | APPROVE (if nothing else is wrong) |
| SG: invoice above S$1,000 without the customer's name or the words "Tax Invoice" | NOT\_CLAIMABLE\_INVALID\_INVOICE | REQUEST\_CORRECTED\_INVOICE |
| SG: foreign-currency invoice without Singapore dollar amounts | NOT\_CLAIMABLE\_INVALID\_INVOICE | REQUEST\_CORRECTED\_INVOICE |
| SG: supplier's GST number invalid or missing, GST charged | GST\_WRONGLY\_CHARGED | REQUEST\_CORRECTED\_INVOICE |
| SG: OVR-registered overseas vendor charges GST to the registered buyer | GST\_WRONGLY\_CHARGED | REQUEST\_CORRECTED\_INVOICE |
| SG: club subscription, staff medical, motor car running costs, family benefit | NOT\_CLAIMABLE\_DISALLOWED | APPROVE, booked without input tax |
| MY: service tax at 8% on logistics, F&B, telecoms or parking | SST\_WRONG\_RATE | REQUEST\_CORRECTED\_INVOICE |
| MY: service tax on a Group G service between two registered persons providing the same service | SST\_SHOULD\_BE\_EXEMPT | REQUEST\_CORRECTED\_INVOICE |
| MY: sales tax on raw materials bought by a registered manufacturer under Schedule C | SST\_SHOULD\_BE\_EXEMPT | REQUEST\_CORRECTED\_INVOICE |
| MY: service tax charged by a supplier with no SST registration | SST\_SUPPLIER\_NOT\_REGISTERED | REQUEST\_CORRECTED\_INVOICE |
| MY: correct rate, registered supplier | SST\_CORRECT | APPROVE (if nothing else is wrong) |
| MY: e-invoice missing a mandatory field, e.g. buyer TIN or a line's tax type | Unchanged | REQUEST\_CORRECTED\_INVOICE |
| Facts not enough to tell, e.g. whether a car falls under the Regulation 25(1) exclusions | Answer key marks the case as one where handing over is correct | HAND\_OVER |

**How the answer key is set, and verification:**

1. **Official rules only.** Every answer follows the official rules and guidance cited above, never a firm's habits or preferences. Where the rules leave a choice, the answer key takes the action the official text points to:
   - A Singapore expense blocked under Regulations 26/27 is a valid business expense whose GST cannot be claimed, so it is APPROVE with NOT\_CLAIMABLE\_DISALLOWED. It is not rejected.
   - Malaysian SST charged when it should not have been can only be corrected by the supplier, so the decision is REQUEST\_CORRECTED\_INVOICE.
2. **Where the rules do not settle a case, handing over is the right answer.** One example is whether a vehicle falls under the Regulation 25(1) exclusions when the documents do not say.
3. **Verification pass, 13 November 2026, by Claude.** Every rule above was re-checked against the official page it cites. No rule needed correcting. The e-invoice threshold, previously marked "to verify", is now confirmed from LHDN.
4. **Realism** is covered by variety: many companies, suppliers, layouts and combinations of problems. It is checked against real cases with the first customer after launch, and a new version is released from that.
5. **Human review** by accountants happens after launch, as a separate step, and leads to a new released version. v0.9 is labelled "synthetic, rules-based" until then.
