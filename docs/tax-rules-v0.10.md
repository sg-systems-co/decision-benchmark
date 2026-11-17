# SG Systems Decision Benchmark — Task set 1 — rule sheet v0.10

Status: approved by Sebastian, 17 Nov 2026 (second pass the same evening: section 6 closed, all four decisions taken, Service Tax and Sales Tax Policies added). Every rule below was read in the official text named next to it on 16–17 Nov 2026 (gazetted orders and regulations as linked from mysst.customs.gov.my, Ministerial exemptions published as Service Tax Policies and Sales Tax Policies, RMCD industry guides, LHDN and IRAS pages, the GST Act on Singapore Statutes Online). Accountant review after launch. Not tax advice.

**Scope (Sebastian, 16 Nov 2026):** every rule that can decide what happens to a supplier invoice received by a company in Malaysia or Singapore. Nothing is left out because it is rare or awkward. Where a case's documents don't settle a rule, the answer is HAND_OVER.

**How each rule is written:** what the rule says → the facts that decide it and where a clerk sees them → the answer → what happens when the documents don't show the fact.

---

## 0. What changes against v0.9

### 0.1 Corrections to work already done (found in the law itself)

| # | What we had | What the law says | Fix |
| --- | --- | --- | --- |
| C1 | Group relief covers Group G items (a)–(i) and (l) (Service Tax Policy 8/2020) | First Schedule paragraph 3, Service Tax Regulations 2018, as amended by the Service Tax (Amendment) (No. 2) Regulations 2024 [P.U. (A) 354/2024]: items (a)–(i), (l) **and (n)** since 1 May 2024. The 2020 policy predates the amendment. | Add `G(n)` to `GROUP_RELIEF_ITEMS`; `maintenance_repair` gets `group_relief: true`; drop the README rule that keeps group questions off maintenance. |
| C2 | Courier: parcels up to 30 kg | The 30 kg limit was in the old Group I item 6, deleted 26 Feb 2024 [Service Tax (Amendment) Regulations 2024]. Courier is now Group J item 1(d), no weight limit. | Remove the 30 kg note from the catalog and README. |
| C3 | "Same service" for logistics B2B compared by item | Persons Exempted Order item 5 (Group J) says "the same taxable service"; the logistics guide reads it as the same item 1(a)/1(c)/1(d)/2. | Keep A11's item matching; cite both. |
| C4 | Rental left out (Q10) | Rental is Group K since 1 Jul 2025, 6% since 1 Jan 2026; its B2B exemption (Order item 8) applies **only when the rented asset is sublet or subleased**, and only to the sublet portion. | Add rental with its own B2B condition (MS-B4). |
| C5 | Group relief: any external supply ends it | First Schedule para 8(2) (from 1 Jan 2020): relief continues if supplies of that service to outsiders in the month and the next 11 months are ≤ 5% of its total. For item (i), "same service" means its sub-items (i)–(x) only (STP 8/2020 para 5). | Model the 5% test as a supplier fact (MS-B6). |
| C6 | Exemptions only from gazetted orders | The Minister also exempts under Service Tax Act s34(3)(a) (buyer need not pay) and s34(4) (supplier need not charge), and Sales Tax Act s35(3). These are published as Service Tax Policies (STP, 79 documents) and Sales Tax Policies (9). Many still apply in 2026 and decide invoices: SME tenants, rental group relief, construction contracts to 30 Jun 2027, financial-services B2B, imported services, MRO, JMB charges, healthcare consultation fees, education fee items, motorcycles. None were in v0.9 or the archive. | Read all current ones (done 17 Nov, listed under MS-10 and MG-6); archive them; the engine applies them like order items. |

### 0.2 New areas

Malaysian service tax groups A–M in full, sales tax beyond the 5/10/exempt split, imported services and digital services, designated and special areas, rate transitions; Singapore zero-rated and exempt supplies, customer accounting, reverse charge, partial exemption, director-only benefits, the remaining motor-car rules; invoices that mix tax treatments.

### 0.3 Answer format (spec v0.10)

v0.9 gives one tax treatment per case. Mixed invoices need more:

- `tax_lines`: one entry per invoice line — `line_no`, `treatment` (the country's code), `basis` (rule ID below).
- `tax_treatment`: the case-level summary, kept for the leaderboard: the worst line by a fixed order (wrongly charged > invalid > disallowed/not claimable > claimable / correct).
- `buyer_actions` (decided 17 Nov, D1): actions the buyer itself must take besides the decision. Values: `ACCOUNT_IMPORTED_SERVICE_TAX` (MS-8), `ACCOUNT_CUSTOMER_ACCOUNTING_GST` (SG-7), `ACCOUNT_REVERSE_CHARGE_GST` (SG-8), `ISSUE_SELF_BILLED_EINVOICE` (ME-3), `WITHHOLD_TAX` with `rate` and `basis` (WH-1 to WH-4).

Scoring: the decision and case-level treatment keep their cost table; per-line treatments are reported as an extra accuracy column (not in the main score), so v0.9-style entries still score.

---

## 1. Malaysia — service tax

Sources for this section, all linked from https://mysst.customs.gov.my/sst-regulations/ and /sst-orders/:
Service Tax Regulations 2018 [P.U. (A) 214/2018] First Schedule, with amendments 2018 (×3), 2019 (×2), 2020 (×2), 2023 (×2), 2024 (×2), 2025 (×2); Service Tax (Rate of Tax) Order 2018 with amendments 2024, 2025 (from 1 Jul 2025) and 2026 (deemed 1 Jan 2026); Service Tax (Persons Exempted from Payment of Tax) Order 2018 with amendments 2019, 2020, 2024, 2025; designated/special area orders; RMCD industry guides (https://mysst.customs.gov.my/industry-guides/); all Service Tax Policies 1/2019 to 6/2026 with their amendments (https://mysst.customs.gov.my/service-tax-policy/, latest version of each read 17 Nov 2026; see MS-10).

### MS-1 Is service tax due on this line at all?

Service tax is due only when **(a)** the service is in the First Schedule, **(b)** the supplier is a registered person (or liable to be), and **(c)** no exclusion in that item, exemption order or area rule applies.

- Deciding facts: the service (catalog item), the supplier's SST number on the invoice and in the supplier master, the exclusions below.
- Answers: tax charged but (a) or (b) fails → `SST_SUPPLIER_NOT_REGISTERED` / `SST_SHOULD_BE_EXEMPT`, REQUEST_CORRECTED_INVOICE. Tax not charged when due → see MS-9.
- Unknown registration status → HAND_OVER (unchanged from v0.9).

### MS-2 Rate

| Rate | Services | Source |
| --- | --- | --- |
| 6% | prepared/served food; non-alcoholic beverages; food with any beverage; telecommunications (incl. with subscription broadcasting); parking; logistics; healthcare; traditional and complementary medicine; allied health; construction works; education; rental or leasing (from 1 Jan 2026) | Rate of Tax Order, First Schedule items 1–14 (2025, 2026 amendments) |
| RM25 per card per year | credit/charge cards | Second Schedule |
| 8% | every other taxable service | para 3(1) |
| Mixed premises rule | Groups A, C, D, E operators: other services they supply alongside their main service are at 8%; Group B (F&B outlets): at 6% | para 3(3) |
| Several services from one Group A–E operator | Each service at its own rate, not the main service's; a package sold as one price takes the group's rate. Alcohol in a food package (buffet, banquet) 6%; corkage 8%; ready-to-drink non-alcoholic drinks 6%; tobacco and alcohol sold alone 8% | STP 3/2024 and amendment no. 1 |
| Telecom operators (I2) | telecom and telecom-plus-internet/TV packages 6%; subscription broadcasting alone and digital services 8% | STP 3/2024 table 1 |

- Deciding facts: the service; for Groups A–E, which subitem the line falls under.
- Wrong rate → `SST_WRONG_RATE`, REQUEST_CORRECTED_INVOICE.

### MS-3 Rate changes over time

Services spanning a rate change are taxed by the part provided on each side of the date; payments received before the change keep the old rate (Rate of Tax (Amendment) Order 2025 para 5; same pattern 2024). Rental: 8% from 1 Jul 2025 to 31 Dec 2025, 6% from 1 Jan 2026.

- Deciding facts: service period on the invoice, payment date (remittance or prior receipt).
- Unknown service period on a spanning invoice → HAND_OVER.

### MS-4 Item scope and exclusions, by group

Each line maps to one First Schedule item (`service_item`). Where an item has an exclusion, the exclusion is a line fact; if the documents don't show it, HAND_OVER.

**Group A Accommodation** (hotels etc.): 8%. Business travel rooms. Tourism tax is a separate tax, not an SST check.

**Group B Food and beverage** (restaurants, caterers, incl. take-away/delivery by the outlet): 6%, including food served together with alcoholic drinks (Rate Order First Schedule item 4); alcoholic drinks sold without food fall outside the 6% list and are at 8%. Delivery by the F&B operator itself is excluded from Group J.

**Groups C–F** (8%, threshold RM500,000; text of the 2018 Regulations with amendments 2018 no. 3, 2019, 2023, 2024 nos. 1–2 and 2025, read 17 Nov):
- **C** operators of night-clubs, dance halls, cabarets, karaoke centres (from 26 Feb 2024), First/Second/Third Class public houses and beer houses (Excise Act s35(1)(a)/(b)), and wellness centres or massage parlours whether or not registered. Taxed: all types of services in the premises; any other First Schedule service they supply; cigarettes, tobacco, pipes, e-cigarettes and liquids, alcoholic and non-alcoholic drinks. Excluded: private healthcare, T&CM and allied health supplied there by Group I items 14–16 providers (2025). Before 1 Jul 2025 the wellness item excluded facilities under the Private Healthcare Facilities Act, government and university healthcare facilities and (from 2024) registered T&CM practitioners' premises.
- **D** private clubs and club houses with membership-restricted entry: all services in the club, other First Schedule services, tobacco and drinks; private healthcare by I14 providers excluded.
- **E** golf courses and driving ranges: the golf services, other First Schedule services, any other service in the club, tobacco and drinks (food deleted from item (d) in 2024, so food follows Group B); private healthcare by I14 providers excluded.
- **F** licensed betting, sweepstakes, lotteries, gaming machines, games of chance and casino card games.
- Business relevance: a company invoice from these suppliers (club membership, golf, karaoke for an event) is taxable at 8% unless a line is food (6%, Group B rate) or an excluded healthcare service. In Singapore the same purchases hit Regulation 26/27 (club fees), SG-10.

**Group G Professionals or skills** (8%, threshold RM500,000):
- (a) legal, (b) syarie legal, (c) accounting/audit/bookkeeping, (d) surveying/valuation/estate agency, (e) engineering, (f) architecture — **excluded**: services in connection with goods or land outside Malaysia or subject matter outside Malaysia; services requiring statutory fees paid to the Federal/State Government or a statutory body (the statutory fee part).
- (g) consultancy — excluded: healthcare/veterinary consultancy; consultancy about goods/land/matters outside Malaysia; training or coaching for holders of a valid Kad OKU. Suppliers excluded as persons: approved R&D companies and contract R&D companies, approved research institutes.
- (h) IT services incl. distributing/reselling IT services — excluded: sale of goods with the IT service.
- (i) management services incl. project management — excluded: matters outside Malaysia; strata management to owners; fund management under the CMSA; religious/welfare/bereavement/health/public-transport bodies.
- (j) employment services — excluded: secondment/supply of staff; placement abroad. **No B2B, no group relief.**
- (k) security guard services — excluded: guarding outside Malaysia. **No B2B, no group relief.**
- (l) digital services incl. electronic platforms.
- (n) maintenance or repair (incl. management, corrective/preventive maintenance, calibration, overhaul) — excluded: residential maintenance management by developers/JMB/MC; maintenance/repair of goods fixed to a residential house provided directly to the owner/occupant; facility maintenance in the construction works period is **included** (2025).

**Group H Finance** (from 1 Jul 2025):
- item 1: card activation, RM25 per card.
- item 2: insurance/takaful to businesses — excluded: cover for international transport of goods/passengers (and the domestic leg by the same provider), educational and religious institutions, export credit, risks outside Malaysia; reinsurance is now taxable.
- items 3–4: fee-based financial services (fees, commissions) — excluded: interest, profit-based financing returns, penalty charges, price-difference returns; basic banking (account operation, transfers, debit cards, counter/ATM transactions, statements); services relating to goods/land/matters outside Malaysia (except outward remittance charged to Malaysian customers); export-related services; inward remittance charged to the overseas agent.
- Specific exemptions in the RMCD Guide on Financial Services (24 Oct 2025) paras 53–56: Bursa share brokerage; Bursa clearing/trading fees for brokers; certain Bursa listing perusal fees; Shariah-based fees meeting the guide's conditions; Labuan entities (Order item 6).

**Group I Other service providers** (8% unless listed at 6%):
- item 2 telecommunications and content/digital services (6%) — excluded: telecom services to another telecom provider.
- item 4 parking (6%).
- item 5 motor vehicle service/repair (labour; parts sold are goods).
- item 8 advertising incl. digital — excluded: promotion outside Malaysia.
- item 9 electricity to domestic consumers above 600 kWh — **not** a business purchase; out of scope for company invoices except where a case uses a residential premises (not generated).
- item 10 air passenger transport by a holder of an air service licence or permit (Malaysian Aviation Commission Act 2015 ss35–36), plus ancillary services — excluded: outside→outside, Malaysia→abroad, abroad→Malaysia, Rural Air Services Agreement routes, and routes within Sabah or within Sarawak by a s35 licensee. Text unchanged since 2018 (the 2018 no. 3 amendment only inserted items after it). So a domestic flight between Peninsular Malaysia and Sabah/Sarawak, or within the Peninsula, is taxable at 8%.
- item 12 brokering/underwriting (non-financial) and financial brokering under Group H item 3.
- item 13 cleaning of goods, land or commercial/industrial buildings — excluded: religious, educational, residential, agricultural.
- items 14–16 private healthcare, T&CM, allied health (6%) — exempt for Malaysian citizens (Order item 7). Company-paid staff treatment: the recipient is the patient; citizenship of the patient decides.

**Group J Logistics** (6%):
- item 1(a) logistics incl. supply-chain management, warehousing, freight forwarding, port/airport, shipping, aviation, cold chain; 1(b) delivery/transport of goods; 1(c) delivery via e-commerce platforms; 1(d) licensed couriers; item 2 customs agents (release of goods).
- Excluded from item 1: carriage from outside Malaysia to outside Malaysia; from the last exit point to outside Malaysia; from outside Malaysia to the first entry point; transshipment between craft; goods landed for transfer to a customs/licensed warehouse until re-export; F&B delivery by a Group B operator.

**Group K Rental or leasing** (8% from 1 Jul 2025, 6% from 1 Jan 2026 [P.U. (A) 125/2026]; registration threshold RM1m [P.U. (A) 201/2025]): all tangible assets — excluded: housing accommodation (incl. SOHO, serviced apartments/condominiums/suites, residential suites); reading materials; assets located outside Malaysia; financial leases. Ministerial exemptions in **STP 2/2025 (Amendment No. 5), 22 Jul 2026**, under s34(3)(a) and s34(4) — this is the legal instrument for the SME exemption (§7 D4):
- **K-1 SME tenants** (item 4): exempt if the tenant registered and declared MSME status in RMCD's MyPMK system; annual sales declared to LHDN for the latest year of assessment < RM1m (from 1 Jul 2025) or RM1m–RM1.5m (from 1 Jan 2026); paid-up ordinary share capital ≤ RM2.5m; if set up by a company in a group, that company holds ≤ 20%. Registration by 31 Dec 2026 still backdates to 1 Jul 2025 / 1 Jan 2026.
- **K-2 new SMEs** (item 9, from 1 Jan 2026): exempt for 1 year from SSM registration (or the Sabah/Sarawak agency), same share-capital and group conditions, MyPMK registration.
- **K-3 aircraft and vessels** (item 6): rental of aircraft (not drones) and ships exempt (not floating storage units).
- **K-4 non-reviewable contracts** (item 3): exempt 1 Jul 2025–30 Jun 2026 if the supplier is registered, the written contract has no price-review clause, was signed and LHDN-stamped by 9 Jun 2025, states service, fixed value and period, and runs past 1 Jul 2025. Rental from 1 Jul 2026 under such contracts is taxable.
- **K-5 government** (item 1): Federal and State Governments neither charge nor pay; local authorities exempt only 1 Jul–30 Sep 2025.
- **K-6 group relief** (item 5, Appendix A): rental between companies of the same group, inside or outside Malaysia (not from a foreign registered person), is exempt; same control test and 5% outsider test as MS-6.
- **K-7 location** (STP 8/2025): an asset within 12 nautical miles of the baselines (UNCLOS) is in Malaysia and taxable; beyond, not taxable.
- **K-8 joint lessors** (STP 4/2026): co-owners renting under one agreement are separate suppliers, each invoicing its own share; a single invoice in one party's name makes that party the supplier.
- Deciding facts: tenant MSME/MyPMK status, sales band, share capital and group holding (company master), contract stamping date and price-review clause (contract record), asset type and location (line). Unknown → HAND_OVER.

**Group L Construction works** (6%, threshold RM1.5m): excluded by the Regulations: residential buildings and their public facilities (not if approved as mixed development). Ministerial exemptions in **STP 3/2025 (Amendment No. 3), 30 Jan 2026**, plus STP 7/2025, 2/2026, 5/2026:
- **L-1 non-reviewable contracts**: exempt to **30 Jun 2027** if the supplier is registered, no price-review clause, signed before 1 Jul 2025 and LHDN-stamped before 31 Dec 2025, states service, fixed value and duration, still in force after 1 Jul 2025; variation orders and extensions of time qualify only if they don't change the value and were signed before 1 Jul 2025 and stamped before 31 Dec 2025.
- **L-2 mixed development**: the residential part and its facilities are exempt, with shared facilities apportioned by non-residential built-up area ÷ total built-up area; needs a surveyor/architect split and a stamped contract stating mixed development.
- **L-3 design-and-build**: consultants under items G(a), (c)–(g), (i), (n) to a registered main contractor on a design-and-build project are exempt (planning permission and contract numbers on the invoice); the main contractor charges 6% on the whole contract value to the developer.
- **L-4 places of worship**: construction for religious worship and its facilities, and renovation converting non-residential buildings to places of worship, exempt; not for commercial buildings on the same site.
- **L-5 completed residential buildings** (STP 2/2026, from 1 Jul 2025): construction work on completed homes exempt; the invoice must name the recipient and the residential address.
- **L-6 offshore and onshore facilities for foreign clients** (STP 5/2026): exempt where the client is not established in Malaysia; the invoice must carry the STP 5/2026 statement.
- **L-7 government**: Federal/State exempt; local authorities only 1 Jul–30 Sep 2025.
- **L-8 materials and works on one invoice** (STP 7/2025 item 3): if the invoice shows materials and construction work separately, only the work is taxed; if not separated, the whole invoice is taxed. **Installation by a registered sales-tax manufacturer** (item 2): separated → service tax on installation only; not separated → sales tax on the whole value if the supplier is a registered manufacturer, service tax on the whole value if not. Ships and platforms (item 1): the company chooses manufacturing (sales tax) or construction (service tax).
- Deciding facts: contract dates, stamping, clauses, project type, recipient residence, line split (contract record and invoice lines). Unknown → HAND_OVER.

**Group M Education**: private school fees above RM60,000 per student per year; higher education/language centres for non-citizens. Company-sponsored staff education: the student's citizenship decides; disabled citizens exempt (Order item 10).

### MS-5 Business-to-business exemptions (Persons Exempted from Payment of Tax Order)

The buyer is exempt when **all** conditions hold; the supplier must then not charge tax (it shows the exemption on the invoice per the guides).

| Order item | Service | Buyer must | Source |
| --- | --- | --- | --- |
| 1 | Group G except (j), (k) | be registered, provide a service under the **same item**, not for personal consumption | Order 2018 + 2019 amendment |
| 2 | Advertising (I8) | be a registered advertising provider; not personal | Order 2018 + 2019 |
| 3 | Digital services from a foreign registered person | account for service tax itself (s26/26A) and hold the FRP's invoice | 2019, 2020 amendments |
| 4 | IT services imported from outside Malaysia | be a registered IT provider reselling the identical service; not personal | 2019 amendment |
| 5 | Logistics (Group J) | be a registered Group J provider of the same service; not personal | 2024 amendment |
| 6 | Financial services (Group H) | be regulated by Labuan FSA and use the service for Labuan-regulated services | 2025 amendment |
| 8 | Rental or leasing (Group K) | be a registered Group K provider of the same service, renting the asset **to sublet or sublease** it; exemption covers the sublet portion only | 2025 amendment; rental guide paras 24–26 |
| 9 | Construction works (Group L) | be a registered Group L provider of the same service; not own use | 2025 amendment; construction guide para 36 |

(Items 7 and 10 are patient/student exemptions, MS-4.)

- Deciding facts: buyer's SST registration (company master, invoice buyer block), the buyer's own service items, purpose (own use / personal / sublet), the B2B declaration the buyer gave the supplier.
- Unknown purpose or unclear "same service" → HAND_OVER.

### MS-6 Group relief (First Schedule paras 3–9)

Group G items (a)–(i), (l), (n) supplied between companies in the same group are not taxable services. Group = one company controls the other: >50% of shares, or 20–50% plus power over the board (paras 4–7; nominee/fiduciary holdings don't count). Relief is lost if the supplier provides that service to outsiders above 5% of its total for the service in the month and the next 11 months (para 8(2)); for item (i) the "same service" is sub-items (i)–(x) (STP 8/2020).

- Deciding facts: the group structure (company master: parent, shareholding, board control), the supplier's external share for that service (supplier fact).
- Unknown relation or unknown 5% status → HAND_OVER.
- Imported Group G services (items (a)–(i), (l)) from a group company abroad: not an imported taxable service (para 3A; STP 8/2020 amendment no. 1 para 1A). Digital services from a foreign registered person to a group company in Malaysia: not taxed, unless that FRP also supplies the service to outsiders in Malaysia (para 1B, 2A).
- Rental between group companies: K-6 above (STP 2/2025 Appendix A, until the Regulations are amended).

### MS-7 Designated and special areas

Services between and within designated areas (Labuan, Langkawi, Tioman, Pangkor) and special areas (free zones, licensed warehouses, licensed manufacturing warehouses, the JDA) are not taxed except as the Minister prescribes; principal customs area ↔ DA/SA rules as in the DA/SA orders and the service-tax FAQ.

- Deciding facts: supplier and buyer locations (addresses, zone status in the company master).
- Unknown zone status for an address inside a known zone → HAND_OVER.

### MS-8 Imported taxable services

A business in Malaysia that acquires a taxable service from a supplier outside Malaysia accounts for service tax itself (Service Tax Act s26 for registered persons, s26A for others above the threshold). The overseas supplier's invoice correctly shows no SST.

- Answer: `SST_BUYER_ACCOUNTS` (new code); decision unaffected; `buyer_actions` += `ACCOUNT_IMPORTED_SERVICE_TAX`.
- Exceptions (buyer accounts for nothing):
  - B2B order items 3 and 4; group para 3A (MS-6).
  - **STP 2/2020**: a registered person that provides the same service to its customers is exempt from accounting for imported Group G services (except (j) employment and (k) security) and imported advertising (I8), if the service is for business and the supplier has been paid. Not for digital services from a foreign registered person.
  - **STP 3/2020**: a registered person that pays SST to a foreign registered person on a digital service it resells claims it back by offset in its SST-02; the FRP's invoice correctly carries SST.
  - **STP 1/2025 item 6**: imported financial services bought by a registered Group H provider to provide taxable financial services, offshore or export-related financial services.
- Deciding facts: supplier country and FRP status, buyer's own service items, payment status. Unknown → HAND_OVER.

### MS-9 Tax not charged when it should have been

The supplier omitted service tax on a taxable line to a buyer with no exemption. The buyer owes only what is invoiced; the error is the supplier's, but the invoice is wrong.
- Answer: `SST_UNDERCHARGED` (new code), REQUEST_CORRECTED_INVOICE.

### MS-10 Other Ministerial exemptions still in force (Service Tax Policies)

Read 17 Nov 2026 in the latest version of each policy. Each is a line rule: when its facts hold, no service tax is due; tax charged anyway → `SST_SHOULD_BE_EXEMPT`, REQUEST_CORRECTED_INVOICE.

| Rule | Exemption | Conditions the case must show | Source |
| --- | --- | --- | --- |
| P-1 | Financial services (Group H) bought by a registered Group H provider | used to provide taxable financial services, offshore financial services (not outward remittance) or export-related financial services; not for exempt Bursa brokerage | STP 1/2025 (Amdt 5) item 5 |
| P-2 | Bursa clearing/trading fees to brokers; listing perusal/processing fees named in the STP | none | item 7 |
| P-3 | Islamic finance fees integral to the Shariah structure | provider registered; fee not comparable to a conventional one and not charged separately | item 8 |
| P-4 | ASNB fixed-price fund management (ASB, ASM) | none | item 9 |
| P-5 | Fees on government-issued or guaranteed securities (purchase, sale, custody, clearing, settlement, administration) | not advisory | item 10 |
| P-6 | Reinsurance/retakaful bought by insurers | used for medical, life or family takaful cover | item 11 |
| P-7 | Share brokerage on Bursa-listed shares; domestic commodity platform fees for Islamic finance; TIA-i account fees (from 1 Jun 2026) | as in the STP | items 12–14 |
| P-8 | Federal and State Governments | new-scope services from 1 Jul 2025 (H, K, L, M, healthcare); local authorities only to 30 Sep 2025 | STP 1/2025 item 2–3; 2/2025; 3/2025 |
| P-9 | MRO (maintenance, repair, overhaul) of aircraft and ships, G(n) | buyer is an AOC airline, a ship-owner registered with the Marine Department, a government department, or a foreign company for a foreign-going ship/aircraft (from 1 Sep 2025); supplier is a CAAM-approved AMO or MIDA-approved shipyard (from 1 Mar 2024), or a DGTA-approved AMO (from 22 Sep 2026); until 31 Dec 2027 | STP 6/2024 (Amdt 3), 2 Nov 2026 |
| P-10 | Maintenance charges and sinking fund for non-residential buildings charged by a developer, JMB or MC | from 1 Jul 2026; services the JMB buys from third parties stay taxable | STP 3/2026 (Amdt 1), 2 Nov 2026 |
| P-11 | Residential maintenance: sinking fund not taxable; free warranty not taxable; repair of residential buildings and of fixtures supplied directly to the owner/occupant excluded | — | STP 5/2024; Regulations G(n) |
| P-12 | Private healthcare (I14–16): consultation fees | itemised separately; if not, the whole invoice is taxed | STP 5/2025 (Amdt 4) item 1 |
| P-13 | Health screening of non-citizen workers through screening-management providers; foreign diplomats (MOFA letter); newborns not yet citizens with one citizen parent | as in the STP | items 3–5 |
| P-14 | Healthcare treatment with medical aids: taxable; facility-to-facility referrals taxed only if the patient walked in to the second facility; ancillary services and medical equipment rental to non-citizen patients at 6% | — | STP 6/2025 |
| P-15 | Health examination management services: taxable as management services from 1 May 2026 (exempt before) | — | STP 1/2026 |
| P-16 | Education fee items exempt: books, uniforms, food, transport, accommodation, refundable deposits, PTA fees, trips outside tuition, student pass/visa; fully sponsored fees; diplomats' children | — | STP 4/2025 (Amdt 2) |
| P-17 | Training or coaching for Kad OKU holders by registered/recognised centres | — | STP 6/2020 |
| P-18 | Logistics: door-to-door international delivery on one airway bill/B/L and one invoice; transit goods not broken bulk; ocean freight Peninsular ↔ Sabah/Sarawak/Labuan and between them | — | STP 4/2024 and Amdt 1 |
| P-19 | Online distance learning (recognised education) and e-newspapers, e-journals and periodicals are not taxable digital services | — | STP 4/2020, 5/2020 |
| P-20 | Expired, kept as dated rules: banking digital services (to 31 Jul 2025); non-bank digital payments (1 Aug 2022–31 Jul 2025); Labuan imported services (to 31 Dec 2021); JDA (refund route since 15 Aug 2022) | dates | STP 10/2020 Amdt 2; 1/2022; 2/2019; 2/2022 |
| P-21 | Electricity to domestic users ≤ 800 kWh (1 Sep–31 Dec 2026) | not a company purchase; recorded for completeness | STP 6/2026 (Amdt 1) |

Transitional "new-scope" exemptions that ended (registration grace periods in July–August 2025, 26 Feb–31 Mar 2024) are kept as dated rules so invoices dated in those windows get the right answer.

---

## 2. Malaysia — sales tax

Sources: Sales Tax (Rate of Sales Tax) Order 2025 [P.U. (A) 170/2025] + amendments 199/2025, 399/2025, 281/2026; Sales Tax (Goods Exempted from Sales Tax) Order 2025 [171/2025] + 200/2025, 400/2025, 165/2026, 276/2026, 303/2026; Sales Tax (Persons Exempted from Payment of Tax) Order 2018 Schedules A, B, C and amendments; RMCD sales tax FAQ and Guide on Manufacturing; MOF release 5 Jan 2026.

### MG-1 Who may charge sales tax

Sales tax is single-stage: charged by a **registered manufacturer** on taxable goods it manufactured and sold, or at import (RMCD FAQ). A trader, distributor or retailer reselling goods does not charge sales tax on its invoice.

- Deciding facts: supplier type and SST registration (supplier master: manufacturer or trader).
- Sales tax on a trader's invoice → `SST_SUPPLIER_NOT_REGISTERED` (or a new `SST_NOT_CHARGEABLE_BY_TRADER`), REQUEST_CORRECTED_INVOICE.
- Unknown supplier type with sales tax charged → HAND_OVER.

### MG-2 Rate by tariff code

10% unless the goods are exempt (Goods Exempted Order) or listed at 5% (First Schedule) or a specific rate (Second Schedule: petroleum). Read at subheading level.

- Deciding facts: the goods and their tariff code (line description, catalog).
- Wrong rate → `SST_WRONG_RATE` (now planted on goods too).
- Exempt goods taxed → `SST_SHOULD_BE_EXEMPT`.

### MG-3 Rate transitions (1 Jul 2025 and later amendments)

Goods that stopped being exempt on 1 Jul 2025 aren't taxed if invoiced before that date (Rate Order amendment 2025 para 3). The 1 Jan 2026 exemptions for critical raw materials used by registered manufacturers, animal feed, fertiliser and pesticides apply from that date.

- Deciding facts: invoice date, delivery date.

### MG-4 Exemptions by person (Persons Exempted Order)

- Schedule C: registered manufacturers buy raw materials, components, packaging and manufacturing aids for taxable goods exempt (items 1–5 as in the manufacturing guide).
- Schedule B: manufacturers of non-taxable goods buy inputs exempt.
- Schedule A: specific persons and purposes (e.g. items 34–38, 49, 54–56, 62 in the manufacturing guide; oil and gas items 33A/33B; others).
- All require the buyer to hold the exemption (certificate in the case documents) for those goods and that period.

- Deciding facts: certificate kind, number, validity, goods covered (company master and the PO/invoice reference).
- Unknown whether the goods are inside the certificate's scope → HAND_OVER.

### MG-5 Designated and special areas

Sales tax doesn't apply within designated areas except on prescribed goods; special-area rules as in the DA/SA orders.

### MG-6 Ministerial sales tax exemptions (Sales Tax Policies, read 17 Nov 2026)

| Rule | Exemption | Source |
| --- | --- | --- |
| G-1 | Motorcycles 8711.20.96 00 and 8711.20.99 00 (50–250 cc, other) exempt from 1 Jul 2025 | Sales Tax Policy 1/2025 (Amdt 1) |
| G-2 | Soya beans 1201.10.00 00 and 1201.90.00 00 imported, exempt from 1 Jul 2025 | 2/2025 |
| G-3 | Raw materials for animal feed, fertilisers and pesticides (tariff codes in its Appendices I–III) bought by licensed manufacturers, exempt from 1 Jan 2026 until the Persons Exempted Order is amended (refund route) | 1/2026 |
| G-4 | Pallets: exempt under Schedule C items 1/3 only as one-way packaging that goes to the buyer; returnable transport pallets are taxable | 1/2022 |
| G-5 | Drop-shipment: a registered manufacturer exporting directly for a Malaysian trader invoices the trader without sales tax (one trader level only, bill-to/ship-to on the invoice) | 2/2022 |
| G-6 | Re-imports of exported goods returned because of the Middle East conflict, by the same manufacturer, to 31 Dec 2026 | 2/2026 |
| G-7 | Refund-only windows (no invoice effect): inputs for goods newly taxable on 1 Jul 2025 (3/2025); machinery under Schedule A item 55 bought 1 Jul–26 Sep 2025 (4/2025) | 3/2025, 4/2025 |

---

## 3. Malaysia — e-invoices and invoice validity

Sources: LHDN e-Invoice Guideline and Specific Guideline; MyInvois SDK; LHDN timeline (updated 30 Aug 2026); Service Tax Regulations 2018 (invoice particulars).

- ME-1 Supplier must issue a validated e-invoice when in a mandatory phase for the invoice date (timeline). Turnover below RM3m: exempt. Unknown supplier phase → HAND_OVER.
- ME-2 Mandatory fields (TIN, registration numbers, classification, tax type, totals per tax type) — missing → REQUEST_CORRECTED_INVOICE (v0.9).
- ME-3 Self-billed e-invoice: the **buyer** issues the e-invoice itself for the transaction types in section 8.3 of the LHDN e-Invoice Specific Guideline (version 4.9, 7 Sep 2026), including goods sold or services rendered by foreign suppliers and payments to agents, dealers and distributors (https://www.hasil.gov.my/wp-content/uploads/IRBM-e-Invoice-Specific-Guideline.pdf). Answer: `buyer_actions` += `ISSUE_SELF_BILLED_EINVOICE` (decided 17 Nov, D2) when the buyer is in a mandatory phase on the transaction date.
- ME-4 SST invoice particulars (Service Tax Regulations 2018 reg 10(1)): serial number, date, the supplier's name, address and registration number, a description identifying the service, any discount, total excluding tax, the rate and the tax as a separate amount, total including tax, and ringgit amounts for foreign-currency invoices. Under reg 10(1A) (2019), an invoice to a buyer exempt under the B2B order must also show the customer's name, address, SST number and the tax exempted. Missing → REQUEST_CORRECTED_INVOICE.

---

## 4. Singapore — GST

Sources: IRAS pages read 17 Nov 2026 — conditions for claiming input tax; invoicing customers; current GST rates; supplies exempt from GST; when to charge 0% (international services, exports); customer accounting for prescribed goods; GST and the digital economy (local businesses: reverse charge, OVR); claiming input tax incurred to make exempt supplies (de minimis); employee benefits; motor vehicle expenses; foreign currency transactions; claim input tax in the correct period; paying suppliers after claiming GST; wrongful collection of GST.

### SG-1 Conditions for a claim (all eight; v0.9) — unchanged.

Citation for condition 8 (missing trader fraud: the buyer took reasonable steps and concluded, as a reasonable person would, that the supply was not part of such an arrangement) moves from the general guide, which is no longer online, to the IRAS page "Conditions for claiming input tax" (https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/claiming-gst-(input-tax)/conditions-for-claiming-input-tax), read 17 Nov 2026; it lists all eight conditions.

### SG-2 Valid tax invoice

- Full tax invoice above S$1,000 incl. GST: "Tax Invoice"; supplier name, address, GST number; date; number; customer name and address; description; GST rate; totals excl. GST, GST, incl. GST. Zero-rated lines must show 0%; exempt/zero-rated/other supplies stated separately.
- Simplified tax invoice up to S$1,000 incl. GST: supplier name, address, GST number, date, number, description, total incl. GST, and a statement like "price payable includes GST".
- Foreign-currency invoices: totals excl. GST, GST and incl. GST converted to SGD at an approved rate.
- Missing item → `NOT_CLAIMABLE_INVALID_INVOICE`, REQUEST_CORRECTED_INVOICE.

### SG-3 Rate by time of supply

9% from 1 Jan 2024 (8% in 2023, 7% before). Source: IRAS "Transitional rules for GST rate change" and "Adjustments and concessions for GST rate change", read 17 Nov 2026 (same rules for the 2023 change).
- A supply spans the change when one or two of invoice, payment, and delivery/performance fall on or after the change date.
- Invoice issued after the change: full payment received before → old rate; otherwise the supplier **may elect** the old rate on the higher of the payment received or the value delivered before the change; the rest at the new rate.
- Invoice issued before the change: full payment or full delivery before → old rate on all; otherwise the new rate on the lower of the payment received or the value delivered after the change (the supplier issues a credit note and a new tax invoice).
- **Buyer side:** a tax invoice received after the change showing the old rate is claimed as shown, subject to the claim conditions. So the buyer's answer follows the GST shown, unless the rate shown is one the rules don't allow for the dates on the documents.
- Contracts made before the change are charged at the new rate unless the contract excludes tax changes, in which case GST is 9/109 of the fixed price.
- Deciding facts: invoice date, payment dates, delivery/performance dates or split.
- A rate the rules don't allow: higher than allowed → `GST_WRONGLY_CHARGED`; lower → `GST_UNDERCHARGED` (new), REQUEST_CORRECTED_INVOICE. An election the supplier may make but the documents don't show, with dates that allow either rate → accept the rate shown.

### SG-4 Supplier not entitled to charge GST

Supplier not GST-registered, number invalid or expired; OVR-registered vendor charging a GST-registered buyer → `GST_WRONGLY_CHARGED` (v0.9).

### SG-5 Exempt supplies

Financial services (Fourth Schedule: account operation, loans, currency exchange, shares, life insurance...), digital payment tokens, sale/lease of residential property, investment precious metals: no GST. GST charged on them → `GST_WRONGLY_CHARGED`. Fees for advising/arranging/broking are **not** exempt.

### SG-6 Zero-rated supplies

Exports of goods (s21(6), (6A) ship stores and installation) and international services under GST Act s21(3), read in full on Singapore Statutes Online 17 Nov 2026:
- (a) transport of passengers or goods by air or land into, out of or outside Singapore; by sea outside→outside, or to/from Singapore substantially outside it (loading, unloading and handling excluded here); (b) the domestic leg by the same supplier; (c) insuring or arranging such transport (from 1 Jan 2023 passenger transport only for insuring);
- (d) hire of transport used outside Singapore throughout; (e) services directly connected with land outside Singapore (incl. construction, estate agents, architects, surveyors; not accommodation booking from 2023);
- (f) services on goods outside Singapore; (g) services on goods for export supplied to an overseas person; (h) prescribed financial services on exports or outside→outside goods;
- (i) cultural, artistic, sporting, educational, entertainment, exhibition and convention services performed wholly outside Singapore;
- (j) services under a contract with an overseas person that directly benefit an overseas person outside Singapore or a GST-registered person in Singapore (not land or goods in Singapore, s21(4C)); (k) prescribed services to overseas businesses on the same basis;
- (l) prescribed ship/aircraft handling and cargo handling or storage; (m) pilotage, salvage, towage; (n) ship/aircraft survey and classification; (o) supply or hire of ships and aircraft (charter, except passenger, accommodation, entertainment, catering, education performed substantially in Singapore); (p) prescribed repair, maintenance, broking or management of ships and aircraft;
- (q) prescribed international telecommunications; (r) prescribed trust services; (s) co-location of overseas persons' servers; (t) prescribed electronic import/export systems; (u) advertising substantially outside Singapore (only before 1 Jan 2022);
- (v) supply or hire of air and sea containers for international transport; (w) their repair, maintenance, management; (x) airworthy aircraft parts; (y) prescribed services on goods in approved warehouses for overseas persons.
- Answer: a local supplier charging 9% on a line that qualifies → `GST_WRONGLY_CHARGED`. Where qualification turns on facts the buyer's documents show (route, goods location, export evidence), the engine decides; where it turns on the supplier's contract counterparty or the beneficiary's location not shown → HAND_OVER. Note for (j): a Singapore buyer is normally the contracting party, so (j) rarely applies to its purchases.

### SG-7 Customer accounting for prescribed goods

Mobile phones (screen ≤ 17.5 cm, not sold with a plan), memory cards (not USB flash drives) and off-the-shelf software (physical media or key in physical packaging), sold to a GST-registered buyer for business use, above S$10,000 excl. GST per invoice: the supplier must **not** charge GST; it issues a customer accounting tax invoice stating the buyer must account for GST of $X; the buyer accounts for output tax and claims input tax.
- GST charged anyway → `GST_WRONGLY_CHARGED`, REQUEST_CORRECTED_INVOICE.
- Correct CA invoice → `CUSTOMER_ACCOUNTING` (new code); `buyer_actions` += account for GST.

### SG-8 Reverse charge (imported services and low-value goods)

Applies only to GST-registered buyers **not entitled to full input tax** (partially exempt or with non-business receipts): they account for GST on imported services and on low-value goods. A fully taxable buyer does nothing.
- Deciding facts: buyer's partial-exemption status (company master), supplier outside Singapore.
- Answer: `REVERSE_CHARGE` (new code) where it applies; otherwise `NO_GST`.

### SG-9 Partially exempt buyers

Input tax directly attributable to exempt supplies is not claimable unless the de minimis rule is met (exempt supplies ≤ S$40,000 a month on average and ≤ 5% of total supplies); residual input tax is apportioned.
- Deciding facts: buyer status (company master: fully taxable / de minimis met / partially exempt) and the purpose of the purchase.
- Answer: `NOT_CLAIMABLE_EXEMPT_USE` (new code) for directly attributable lines; `RESIDUAL_APPORTIONED` (new) for residual lines. Unknown attribution → HAND_OVER.

### SG-10 Regulations 26/27 and related IRAS rules

- v0.9 list, with the IRAS exceptions added in A11 (staff medical: WICA, collective agreement, work-related health risk under written law, COVID-19 advisory; insurance: obligatory under WICA or a collective agreement).
- Motor cars: the Regulation 25(1) exclusions are business service passenger vehicles registered before 1 Apr 1998, taxis, private cars registered for school transport, unused cars supplied for sale or hire, cars supplied to financial institutions for hire purchase, dealer stock, used cars supplied for hire, and driving-school cars. Claimable exceptions: pay-per-trip chauffeured private hire car services (from 1 Apr 2022); a motor car used by a third party (from 1 Jan 2023, on the IRAS conditions).
- Benefits given only to sole proprietors, partners or directors → not claimable (employee benefits page).
- Corporate social initiatives for third-party beneficiaries → not for the purpose of business, not claimable.

### SG-11 Timing and payment

Claim in the period of the invoice date (or posting date if applied consistently); repay if the supplier isn't paid within 12 months of the due date. Duplicate claims are caught by the duplicate check.

---

## 4A. Withholding tax on payments to non-residents (decided 17 Nov, D3)

Withholding doesn't change the tax treatment of the invoice; it changes what the buyer pays the supplier and what it pays the tax authority. Answer: `buyer_actions` += `WITHHOLD_TAX` with `rate`, `basis` and the base amount. Where a DTA rate is claimed, the case must hold the payee's certificate of residence; without it the domestic rate applies.

**Malaysia** (LHDN "Withholding tax" page; Public Ruling 10/2019 "Withholding Tax on Special Classes of Income"; both read 17 Nov 2026). The payer is a resident person, the government, or anyone claiming the payment as a business expense in Malaysia.
- **WH-1 Interest** to a non-resident: 15% (ITA s109). **Royalty**: 10% (s109).
- **WH-2 Special classes of income** (s4A, s109B): 10% of the gross amount (no grossing-up from 5 Dec 2018), for (i) services in connection with the non-resident's property or rights, or installing/operating plant bought from it; (ii) technical advice, assistance or services for managing or administering a scientific, industrial or commercial undertaking; (iii) rent or payments for use of movable property. Services performed **outside** Malaysia under (i) and (ii) are exempt [Income Tax (Exemption) (No. 9) Order 2017, from 6 Sep 2017]; mixed contracts are apportioned to the Malaysian part. (iii) applies wherever the property is used. Reimbursements are part of the gross amount, except hotel accommodation. Freight alone is outside (iii); handling or agency fees with it fall under (ii).
- **WH-3 Contract payments** where the non-resident has a permanent establishment or business presence in Malaysia: s107A, 10% (contractor) + 3% (its employees), instead of s109B.
- **WH-4 Other gains under s4(f)**: 10% (s109F). Public entertainers 15% (s109A).
- Due within one month of paying or crediting; late → 10% increase; the expense isn't deductible until paid (s39(1)(j)).
- DTA rates: from the LHDN "Double Tax Agreements Withholding Tax Rates" table (per country: interest, royalties, technical fees); e.g. Singapore: interest 10%, royalties 8%, technical fees 5%. The engine takes the table as data with LHDN's notes: the lower of the treaty and domestic rate applies (note i); the payer keeps the certificate of residence (note iii); where a row shows 15/10 (iv), 10% applies only to interest paid by an enterprise in an industrial undertaking; where a treaty has no technical-fees article, the royalty rate applies to services inside the treaty's royalty definition (note v).

**Singapore** (IRAS "Types of payment and withholding tax rates" and "Payments that are subject to withholding tax", read 17 Nov 2026). Applies to payments to non-residents without a Singapore branch receiving them.
- **WH-5** Interest and loan fees 15%; royalties and payments for knowledge or information 10%; rent of movable property 15%; technical assistance, service and management fees **for work done in Singapore** at the corporate rate (17%, not final); services delivered electronically from overseas without staff in Singapore → not subject; ship charters nil; non-resident professionals 15% of gross; directors 24%.
- Software and digitised goods: payments for a copyrighted article (use only) → no withholding; for a copyright right (to exploit) → royalty 10%.
- Due on the 15th of the second month after the date of payment (the earliest of due date under the contract or invoice date, crediting, actual payment).
- DTA rates: IRAS publishes no per-country rate table, only the treaty texts. Rates for interest and royalties are read from each treaty's interest and royalty articles, including any protocol that amends them, and kept as data with the article and a quote. Service fees: most treaties have no technical-fees article, so service fees fall under business profits; a non-resident without a PE in Singapore that provides a certificate of residence is not taxed on them (IRAS "Payments that are subject to withholding tax"). Where a treaty row hasn't been read and confirmed, a case that needs it → HAND_OVER.

Deciding facts: supplier residence and PE status (supplier master), nature of payment (line), where the service was performed (line or contract), certificate of residence (documents). Unknown place of performance or nature → HAND_OVER.

## 5. Mixed invoices

An invoice may carry lines with different treatments (e.g. a hotel bill with room and minibar alcohol in Malaysia; a Singapore supplier bill with a claimable item and a club fee). Each line gets its own treatment under the rules above; the decision follows the most severe line (a wrongly charged line → REQUEST_CORRECTED_INVOICE for the whole invoice; a disallowed line alone → APPROVE with that line booked without input tax).

Where the law ties the treatment to how the invoice is split, the split is the deciding fact: construction materials and works (L-8), installation by a sales-tax manufacturer (L-8), healthcare consultation fees (P-12), education fee items (P-16), packages from Group A–E operators (MS-2). Not itemised → the whole invoice takes the taxed treatment.

---

## 6. Reading status

All four items open in the first draft were read on 17 Nov 2026: Groups C–F and Group I item 10 (MS-4), Singapore rate-change rules (SG-3), the full s21(3) list (SG-6), Malaysian and Singapore withholding tax (§4A). Reading them turned up a fifth gap, the Ministerial exemptions published as policies (C6), now read in full (MS-10, MG-6, Groups K and L).

Left for the archive and engine PRs, as data rather than rules: the per-country DTA rate tables (LHDN and IRAS pages), the tariff-code lists in Sales Tax Policy 1/2026, and the full Service Tax and Sales Tax Policy texts (all to be archived in decision-benchmark-sources with manifest entries).

## 7. Decisions (taken by Sebastian, 17 Nov 2026)

Rule behind all four: the benchmark covers everything an AP team must do in practice, so the model can be used in every case.

- **D1 `buyer_actions`: yes.** A list field in the answer, scored as an extra column like per-line treatments.
- **D2 Self-billed e-invoices: yes**, as `ISSUE_SELF_BILLED_EINVOICE`.
- **D3 Withholding tax: yes**, as `WITHHOLD_TAX` with rate and basis (§4A).
- **D4 SME rental exemption: yes.** The legal instrument is the Minister's exemption under Service Tax Act s34(3)(a) and s34(4), published as Service Tax Policy 2/2025 (Amendment No. 5) of 22 Jul 2026; cited as K-1 and K-2.

## 8. Sources

Malaysia — https://mysst.customs.gov.my/sst-regulations/ , /sst-orders/ , /industry-guides/ , /service-tax-policy/ (Service Tax Policies 1/2019–6/2026), /sales-tax-policy/ (Sales Tax Policies 1/2022–2/2026), /faq-services-tax/ , /faq-sales-tax/ ; MOF releases of 9 Jun 2025 and 5 Jan 2026; LHDN e-invoice timeline and MyInvois SDK; LHDN withholding tax page (https://www.hasil.gov.my/en/perundangan/cukai-pegangan/), Public Ruling 10/2019 (https://www.hasil.gov.my/wp-content/uploads/PR_10_2019.pdf), DTA withholding rates (https://www.hasil.gov.my/en/antarabangsa/perjanjian-pengelakan-pencukaian-dua-kali-pppdk/kadar-cukai-pegangan/).
Singapore — https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/ (pages listed in §4), incl. GST rate change transitional rules and adjustments pages; GST Act 1993 s21 (https://sso.agc.gov.sg/Act/GSTA1993); IRAS withholding tax pages (https://www.iras.gov.sg/taxes/withholding-tax/).
