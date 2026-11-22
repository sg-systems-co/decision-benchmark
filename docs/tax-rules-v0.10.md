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

### 0.1a Additions after the spec review (17 Nov)

Found while writing spec v0.10 (PR #10), which listed where the sheet was unclear:
- **MS-9** now also covers sales tax left off by the registered manufacturer that made the goods.
- **MG-1** names the code for sales tax charged on goods the supplier did not manufacture, including a registered manufacturer reselling goods it bought in (Sales Tax Act: sales tax is charged on taxable goods manufactured by a registered manufacturer).
- **SG-12** (new): GST left off a standard-rated supply by a registered supplier → `GST_UNDERCHARGED`.
- **§0.3** gives the full worst-line order; the order inside each group is set in the spec.
- **ME-3** (18 Nov, after the engine review) lists all section 8.3 self-billing types from the guideline, with the interest exceptions, and says which arise on supplier invoices.
- **MS-7 and MG-5** (18 Nov) rewritten from the Service Tax Act and Sales Tax Act Parts VIII–IX, their amendment Acts and every area order with its amendments (all archived in decision-benchmark-sources PR #4). The earlier text deferred PCA ↔ area cases to the orders and the FAQ; the rules now state them. Pulau 1 is added as an area. The petroleum supply base is added for sales tax and left open for service tax (Q-A5). The JDA follows Service Tax Policies 1/2021 and 2/2022, and five open questions (Q-A1 to Q-A5) are listed in §6.
- **SG-8** (18 Nov) adds the GST-group condition and the de minimis case, as the engine review decided.
- **Group H item 1, MS-3, MS-4, L-1, MS-8** (22 Nov, date sweep): card services taxable since 2018; reg 3A scope-change rule; the 26 Feb 2024 additions with STP 1/2024; L-1's exact Appendix A conditions; MS-8 from 1 Jan 2019. 8% rental from 1 Jan 2026 settled as wrong rate (STP 2/2025 Amendment No. 5, Appendix B).
- **MS-5, MS-6, WH-2, SG-6** (22 Nov, out-of-window engine tests): dates added. The tests found two errors inside the case windows. SG-6 (c) and (e) were zero-rated on every date, though narrowed from 1 Jan 2023. MS-5 item 5 (logistics) was applied before its 1 Mar 2024 start.
- **ME-1** (20 Nov, B1 plan review) states the e-invoice phases, exemptions and the interim relaxation periods. Correction: the engine raised a missing e-invoice finding inside a relaxation period, where LHDN allows a consolidated e-invoice instead; for suppliers with turnover up to RM5m that period runs to 31 Dec 2027.

### 0.2 New areas

Malaysian service tax groups A–M in full, sales tax beyond the 5/10/exempt split, imported services and digital services, designated and special areas, rate transitions; Singapore zero-rated and exempt supplies, customer accounting, reverse charge, partial exemption, director-only benefits, the remaining motor-car rules; invoices that mix tax treatments.

### 0.3 Answer format (spec v0.10)

v0.9 gives one tax treatment per case. Mixed invoices need more:

- `tax_lines`: one entry per invoice line — `line_no`, `treatment` (the country's code), `basis` (rule ID below).
- `tax_treatment`: the case-level summary, kept for the leaderboard: the worst line by a fixed order (wrongly charged or undercharged > invalid > not claimable (disallowed, exempt use) > residual apportioned > claimable, correct, buyer accounts, no tax). The full order per country, including the order inside each group, is set in spec v0.10.
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
- **Scope changes (Service Tax Regulations 2018 reg 3A; added 22 Nov 2026).** When a service becomes taxable, a supply spanning the start date is taxed only on the part provided on or after it, and a payment received before the start date for a service provided on or after it is not taxed. When a service stops being taxable, only the part before the date is taxed. This applies to every scope change: the 26 Feb 2024 additions (MS-4) and the 1 Jul 2025 additions (Groups H items 2–4, K, L, M and Group I items 14–16). The RMCD rental guide (9 Jun 2025, paras 40–41, examples 24–25) applies it to rental. Deciding facts are as for rate changes; unknown split on a spanning supply → HAND_OVER.

### MS-4 Item scope and exclusions, by group

Each line maps to one First Schedule item (`service_item`). Where an item has an exclusion, the exclusion is a line fact; if the documents don't show it, HAND_OVER.

**Group A Accommodation** (hotels etc.): 8%. Business travel rooms. Tourism tax is a separate tax, not an SST check.

**Group B Food and beverage** (restaurants, caterers, incl. take-away/delivery by the outlet): 6%, including food served together with alcoholic drinks (Rate Order First Schedule item 4); alcoholic drinks sold without food fall outside the 6% list and are at 8%. Delivery by the F&B operator itself is excluded from Group J.

**Groups C–F** (8%, threshold RM500,000; text of the 2018 Regulations with amendments 2018 no. 3, 2019, 2023, 2024 nos. 1–2 and 2025, read 17 Nov):
- **C** operators of night-clubs, dance halls, cabarets, karaoke centres (from 26 Feb 2024), First/Second/Third Class public houses and beer houses (Excise Act s35(1)(a)/(b)), and wellness centres or massage parlours whether or not registered. Taxed: all types of services in the premises; any other First Schedule service they supply; cigarettes, tobacco, pipes, e-cigarettes and liquids, alcoholic and non-alcoholic drinks. Excluded: private healthcare, T&CM and allied health supplied there by Group I items 14–16 providers (2025). Before 1 Jul 2025 the wellness item excluded facilities under the Private Healthcare Facilities Act, government and university healthcare facilities and (from 27 Nov 2024, P.U. (A) 354/2024 para 2(c)) premises or healthcare facilities run by a practitioner registered under the Traditional and Complementary Medicine Act 2016 in a recognised practice area.
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

**Group H Finance** (items 2–4 from 1 Jul 2025):
- item 1: card activation, RM25 per card. Taxable since 1 Sep 2018: the 2018 Regulations' Group H "Credit card and charge card" (corrected 22 Nov 2026; the earlier heading dated it from 1 Jul 2025).
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
- **L-1 non-reviewable contracts**: exempt to **30 Jun 2027** if the supplier is registered, no price-review clause, signed before 1 Jul 2025 and LHDN-stamped before 31 Dec 2025, states service, fixed value and duration, still in force after 1 Jul 2025; variation orders and extensions of time qualify only if they don't change the value and were signed before 1 Jul 2025 and stamped before 31 Dec 2025. Exact conditions (STP 3/2025 Amendment No. 3, Appendix A): (e) the contract remains in force after 1 Jul 2025, so a contract ending on or before 1 Jul 2025 doesn't qualify; (g) an extension of time qualifies where it rests on an original contract meeting (a)–(d), the value is unchanged, the original contract expired before 1 Jul 2025, and the EOT document was signed before 1 Jul 2025 and stamped before 31 Dec 2025.
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

- In-force dates (added 20 Nov 2026 after the engine's out-of-window tests): the Order applies from 1 Jan 2019 (P.U. (A) 380/2018); before that no B2B exemption exists. Items 1 and 2 had no own-use or personal-consumption condition before 1 Jan 2020. Item 4 applies from 1 Jan 2020. Item 5 applies from 1 Mar 2024. Items 6, 8 and 9 apply from the in-force date of their 2025 amendment. Each date is confirmed against the archived amending order in the engine PR that dates it.
- Deciding facts: buyer's SST registration (company master, invoice buyer block), the buyer's own service items, purpose (own use / personal / sublet), the B2B declaration the buyer gave the supplier.
- Unknown purpose or unclear "same service" → HAND_OVER.

### MS-6 Group relief (First Schedule paras 3–9)

Group G items (a)–(i), (l), (n) supplied between companies in the same group are not taxable services. Group = one company controls the other: >50% of shares, or 20–50% plus power over the board (paras 4–7; nominee/fiduciary holdings don't count). Relief is lost if the supplier provides that service to outsiders above 5% of its total for the service in the month and the next 11 months (para 8(2), from 1 Jan 2020, P.U. (A) 357/2019; before then any supply of the service to outsiders ended the relief, so a pre-2020 line needs the outside share to be shown as zero, else HAND_OVER); for item (i) the "same service" is sub-items (i)–(x) (STP 8/2020).

- Deciding facts: the group structure (company master: parent, shareholding, board control), the supplier's external share for that service (supplier fact).
- Unknown relation or unknown 5% status → HAND_OVER.
- Imported Group G services (items (a)–(i), (l)) from a group company abroad: not an imported taxable service (para 3A; STP 8/2020 amendment no. 1 para 1A). Digital services from a foreign registered person to a group company in Malaysia: not taxed, unless that FRP also supplies the service to outsiders in Malaysia (para 1B, 2A).
- Rental between group companies: K-6 above (STP 2/2025 Appendix A, until the Regulations are amended).

### MS-7 Designated and special areas (rewritten 18 Nov 2026 from the Act and every area order)

**Areas** (Service Tax Act 2018 s2 as amended; Parts VIII and IX, ss47–56):
- Designated areas (DA): Labuan, Langkawi, Tioman; Pangkor from 1 Jan 2020 (Act A1597); Pulau 1 from 1 Dec 2024 (Act A1719, Pulau 1 as defined in Customs Act 1967 s2(1)).
- Special areas (SA): free zones, licensed warehouses, licensed manufacturing warehouses (LMW), the Joint Development Area (JDA). Act A1597 para 3(b) adds petroleum supply bases licensed under Customs Act s77B, but its commencement notice (P.U. (B) 660/2019) brings into force only paras 3(a) and 3(d), the Pangkor provisions. No archived text brings para 3(b) into force, so for service tax a petroleum supply base is open question Q-A5: a line where it decides the answer → HAND_OVER, not planted. For sales tax it is a special area from 1 Jan 2020 (Act A1596, in force in full under P.U. (B) 659/2019).
- Principal customs area (PCA): the rest of Malaysia. In Parts VIII and IX "Malaysia" means the PCA (ss47, 52).

**Where a service is provided.** Each line has a "from" zone and a "to" zone.
- From: the zone of the supplier's principal place of business (ss49, 54 turn on it). Supplier master.
- To: the zone of the buyer establishment that receives the service, which is the establishment the invoice is addressed to. Company master; a line fact `recipient_zone` overrides it when the invoice names another establishment of the buyer.
- Site-bound services (accommodation, food and beverages, customs clearance, and any service the invoice shows performed at a named site) are provided where they are performed. Both "from" and "to" are the site's zone (line fact `service_site_zone`). RMCD's Panduan Perkhidmatan Penginapan (V4, 26 Feb 2024) says accommodation provided within a designated area is not subject to service tax ("perkhidmatan penginapan yang disediakan di dalam kawasan yang ditetapkan … tidak tertakluk kepada cukai perkhidmatan"). Its Panduan Makanan dan Minuman (V7, 19 Apr 2024) says the same for food and drink. Both are archived.

**Decision.** MS-7 runs after MS-1 to MS-4 have found a taxable service from a supplier who may charge. It removes the tax or confirms it. It is judged at the time of supply (MS-3); where a period spans an order's start or end date and no split is shown, HAND_OVER, as in MS-3.

1. From PCA to PCA: MS-7 does not apply.
2. From PCA to a DA or SA: taxed as normal. A registered person whose principal place of business is in the PCA charges tax on services it provides to a DA (s50) or an SA (s55).
   - JDA, 1 May 2021 to 14 Aug 2022: the Malaysia-Thailand Joint Authority (MTJA) and companies operating in the JDA are exempt from paying tax on services provided within the JDA by PCA companies (Service Tax Policy 1/2021, under s34(3)(a)). Tax charged on such a line → `SST_SHOULD_BE_EXEMPT`. Buyer fact: buyer kind `jda_operator` (company master).
   - JDA, from 15 Aug 2022: JDA operator companies reclaim the tax by quarterly refund (Service Tax Policy 2/2022, under s34(3)(b)). The invoice is correct as charged (`SST_CORRECT`); the refund claim is outside AP. RMCD's service tax FAQ still says "From PCA (other than SA) to JDA – not subject to service tax"; that is the position under Policy 1/2021, and Policy 2/2022 replaced it.
   - Before 1 May 2021 the JDA has no special rule: taxed as normal (Policy 1/2021 para 2(b) confirms the tax was due).
3. From a DA or SA to the PCA: taxed as normal. A person whose principal place of business is in a DA or SA charges tax on services it provides within Malaysia (ss49, 54).
4. Both zones in areas (within one area, between areas, or between a DA and an SA): no service tax (ss48, 53), unless one of these applies:
   - Pulau 1 (from 1 Dec 2024): every taxable service in the First Schedule provided within Pulau 1, between Pulau 1 and another DA, or between Pulau 1 and an SA is taxed (P.U. (A) 370/2024 para 2).
   - A service in the Schedule of P.U. (A) 212/2018, in force on the time of supply (table below).
   - Otherwise: tax charged → `SST_SHOULD_BE_EXEMPT`; no tax → correct.

**Services the Minister taxes inside and between areas** (P.U. (A) 212/2018 as amended by P.U. (A) 232/2018, 231/2019, 393/2019, 65/2024, 371/2024, 165/2025, 337/2026; para 3 makes each listed service chargeable when the listed person provides it):

| Item | Service | Provided by | In force |
|---|---|---|---|
| 1 | Passenger air transport between DAs, between SAs, DA to SA, SA to DA. From 1 Dec 2024 "designated areas" here excludes Pulau 1 (371/2024), which falls under the Pulau 1 order instead. | Holder of an air service licence (s35) or air service permit (s36) under the Malaysian Aviation Commission Act 2015 | From 1 Sep 2018 |
| 2 | Telecommunication services on the same four routes; same Pulau 1 exclusion | A telecommunication services or content applications service provider registered under the Communications and Multimedia Act 1998 or licensed under its Licensing Regulations 2000 | From 1 Sep 2018 |
| 3 | Accommodation premises in special areas (the words "in special areas" from 6 Sep 2018, 232/2018), excluding premises provided by an employer as a facility to its employees (from 1 Jan 2020, 393/2019; wording restated from 25 Sep 2026, 337/2026). Also excluded: premises provided by the Federal Government (State Government added from 1 Jan 2020), a statutory body or local authority, or a private higher educational institution registered under Act 555 (before 1 Jan 2020 only when provided for educational, training or welfare purposes); premises of a registered religious or welfare body for religious or welfare activities and not for commercial purposes. | Any person operating accommodation premises (hotel, inn, lodging house, service apartment, homestay or similar) | From 1 Sep 2018 |
| 4 | Food and beverages in special areas ("in special areas" from 6 Sep 2018) | (1) Restaurant, bar, snack bar, canteen, coffee house or any place providing food and drinks, eat-in or take-away, excluding a canteen in an educational institution and a canteen operated by a religious institution or body; (2) catering; (3) food courts | From 1 Sep 2018 |
| 5 | Clearing goods from customs control in special areas; also in designated areas excluding Pulau 1 from 30 May 2025 (165/2025) | A customs agent approved under Customs Act s90 (s90(2) from 1 Jan 2020) | From 1 Sep 2018 |
| 6 | Food and beverages in special areas | A person operating a night-club, dance hall or cabaret, or a place licensed under Excise Act s35(1)(a) or (b) as a First, Second or Third Class Public House or First or Second Class Beer House | 1 Sep 2019 (231/2019) |
| 7 | (a) All logistics services, except five international legs: delivery from a place outside Malaysia to a place outside Malaysia; from the last point of exit in Malaysia to a place outside Malaysia; from a place outside Malaysia to the first point of entry; goods arriving at a Malaysian customs port or airport for transfer between aircraft or vessels until carried out of Malaysia; goods arriving for transfer to a customs warehouse, licensed warehouse or approved place until carried out of Malaysia. (b) Delivery, distribution or transport of goods including courier, except food and beverage delivery by item-4 persons. (c) The same through an e-commerce platform. (d) Release of goods from customs control. | Logistics providers (supply chain management, warehousing, freight forwarding, port or airport, shipping, aviation, cold chain), delivery and transport providers, e-commerce delivery, couriers licensed under Postal Services Act 2012 s10, customs agents approved under Customs Act s90(2) | 1 Mar 2024 to 29 May 2025 (65/2024; deleted by 165/2025) |

- How the table reads (settled in the PR 4 review, 19 Nov):
  - Items 1 and 2 "between designated areas" and "between special areas" mean two different areas. A flight or telecom service within one area is not listed, so it is untaxed (step 4).
  - Item 7 names no route. It applies to any line where both zones are areas, which is the whole scope of the order.
  - Item 3 exclusions are facts. Supplier kinds (supplier master): `federal_state_government`, `local_authority`, `statutory_body`, `private_hei` (registered under Act 555), `religious_welfare_body`. A religious or welfare body is excluded only for premises used for religious or welfare activities and not commercially (line fact `non_commercial_religious_welfare`). Before 1 Jan 2020, government, statutory body and private HEI premises are excluded only when provided for educational, training or welfare purposes (line fact `educational_training_welfare_purpose`). From 1 Jan 2020, premises an employer provides to its own employees are excluded (line fact `employer_staff_accommodation`). A fact the documents don't show, where it decides the line → HAND_OVER.
  - Item 4 excludes a canteen in an educational institution and a canteen operated by a religious institution or body. Line fact `canteen_kind`: `educational_institution`, `religious_body` or none. Unknown where it decides the line → HAND_OVER.
- Deciding facts: supplier zone (supplier master), recipient zone (company master or line), site zone for site-bound lines (line), the line's category (catalog maps each category to a schedule item or none), the supplier's licence or approval where an item names one (supplier master: `area_licences`, values `mavcom_air_service`, `cma_telecoms`, `customs_agent_s90`, `entertainment_premises`), and for item 7 whether the line is one of the five international legs (line).
- Unknown zone of a party → HAND_OVER. Unknown site zone for a site-bound line → HAND_OVER. Unknown licence or international leg where it decides the line → HAND_OVER. A zone is never read off an address: the master shows it or the case doesn't settle it.
- Pulau 1 appears only where a master gives it as a zone. Its legal boundary (Customs Act s2(1)) is not archived yet, so the generator plants Pulau 1 only with the zone stated in the master.

### MS-8 Imported taxable services

A business in Malaysia that acquires a taxable service from a supplier outside Malaysia accounts for service tax itself (Service Tax Act s26 for registered persons, s26A for others above the threshold). The overseas supplier's invoice correctly shows no SST. In force from 1 Jan 2019 (Service Tax (Amendment) Act 2018); before that no tax on imported services, so the answer is the ordinary no-SST result with no buyer action. STP 2/2020 applies from the effective date the policy states, confirmed against the archive in the engine PR.

- Answer: `SST_BUYER_ACCOUNTS` (new code); decision unaffected; `buyer_actions` += `ACCOUNT_IMPORTED_SERVICE_TAX`.
- Exceptions (buyer accounts for nothing):
  - B2B order items 3 and 4; group para 3A (MS-6).
  - **STP 2/2020**: a registered person that provides the same service to its customers is exempt from accounting for imported Group G services (except (j) employment and (k) security) and imported advertising (I8), if the service is for business and the supplier has been paid. Not for digital services from a foreign registered person.
  - **STP 3/2020**: a registered person that pays SST to a foreign registered person on a digital service it resells claims it back by offset in its SST-02; the FRP's invoice correctly carries SST.
  - **STP 1/2025 item 6**: imported financial services bought by a registered Group H provider to provide taxable financial services, offshore or export-related financial services.
- Deciding facts: supplier country and FRP status, buyer's own service items, payment status. Unknown → HAND_OVER.

### MS-9 Tax not charged when it should have been

The supplier omitted service tax on a taxable line to a buyer with no exemption, or a registered manufacturer omitted sales tax on taxable goods it manufactured and sold (MG-1, MG-2). The buyer owes only what is invoiced; the error is the supplier's, but the invoice is wrong.
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
| P-20 | Expired, kept as dated rules: banking digital services (to 31 Jul 2025); non-bank digital payments (1 Aug 2022–31 Jul 2025); Labuan imported services (to 31 Dec 2021); JDA (refund route since 15 Aug 2022); the STP 1/2024 transitional exemptions for the 26 Feb 2024 additions (26 Feb–31 Mar 2024, MS-4) | dates | STP 10/2020 Amdt 2; 1/2022; 2/2019; 2/2022 |
| P-21 | Electricity to domestic users ≤ 800 kWh (1 Sep–31 Dec 2026) | not a company purchase; recorded for completeness | STP 6/2026 (Amdt 1) |

Transitional "new-scope" exemptions that ended (registration grace periods in July–August 2025, 26 Feb–31 Mar 2024) are kept as dated rules so invoices dated in those windows get the right answer.
- **26 Feb 2024 additions** (Service Tax (Amendment) Regulations 2024, in force 26 Feb 2024; STP 1/2024): karaoke centres (Group C), maintenance or repair (G(n)), brokering and underwriting other than financial (I12), and logistics (Group J) became taxable on 26 Feb 2024. Before that date they are not taxable services. Courier delivery was the old Group I item 6 (parcels up to 30 kg) until it moved to Group J on 26 Feb 2024. STP 1/2024 exemptions: a supplier already registered for other services before 26 Feb 2024 neither charges nor collects tax on the new services for 26–29 Feb 2024 and charges from 1 Mar 2024; a supplier newly liable to register neither charges nor collects for 26 Feb–31 Mar 2024 and charges from 1 Apr 2024. Tax shown inside those windows → `SST_SHOULD_BE_EXEMPT`, basis P-20 (expired dated exemptions). Supplier fact: `registered_before_2024_02_26`. Unknown, where it decides → HAND_OVER.
- **Rental at 8% from 1 Jan 2026** (settled 22 Nov 2026; was open question Q-R1). STP 2/2025 (Amendment No. 5), Appendix B, fixes the rental rate at 6% from 1 Jan 2026 and treats 8% charged on rental provided on or after that date as overpaid by the recipient. The supplier claims the 2% back under Service Tax Act s38(1)(b) only with proof that it returned the tax to the tenant, for example by credit note. For AP, a rental line provided on or after 1 Jan 2026 and charged at 8% is `SST_WRONG_RATE`, REQUEST_CORRECTED_INVOICE (the correction comes as a credit note), whether the invoice was issued before or after the order's gazette date of 13 Mar 2026.

---

## 2. Malaysia — sales tax

Sources: Sales Tax (Rate of Sales Tax) Order 2025 [P.U. (A) 170/2025] + amendments 199/2025, 399/2025, 281/2026; Sales Tax (Goods Exempted from Sales Tax) Order 2025 [171/2025] + 200/2025, 400/2025, 276/2026; Sales Tax (Persons Exempted from Payment of Tax) Order 2018 Schedules A, B, C and amendments (among them 165/2026 and 303/2026, listed here among the exemption order's amendments until 19 Nov 2026); before 1 Jul 2025 (MG-3), the Sales Tax (Rates of Tax) Orders 2018 [221/2018] and 2022 [176/2022] and (Goods Exempted from Tax) Orders 2018 [219/2018] and 2022 [175/2022], with their amendments; RMCD sales tax FAQ and Guide on Manufacturing; MOF release 5 Jan 2026.

### MG-1 Who may charge sales tax

Sales tax is single-stage: charged by a **registered manufacturer** on taxable goods it manufactured and sold, or at import (RMCD FAQ). A trader, distributor or retailer reselling goods does not charge sales tax on its invoice.

- Deciding facts: supplier type and SST registration (supplier master: manufacturer or trader).
- Sales tax charged by a supplier not registered for sales tax → `SST_SUPPLIER_NOT_REGISTERED`, REQUEST_CORRECTED_INVOICE.
- Sales tax charged on goods the supplier did not manufacture (a trader, distributor or retailer, or a registered manufacturer reselling goods it bought in) → `SST_NOT_CHARGEABLE_BY_TRADER` (new code), REQUEST_CORRECTED_INVOICE.
- Sales tax left off taxable goods by the registered manufacturer that made them → `SST_UNDERCHARGED` (MS-9), REQUEST_CORRECTED_INVOICE.
- Unknown supplier type with sales tax charged → HAND_OVER.

### MG-2 Rate by tariff code

10% unless the goods are exempt (Goods Exempted Order) or listed at 5% (First Schedule) or a specific rate (Second Schedule: petroleum). Read at subheading level.

- Deciding facts: the goods and their tariff code (line description, catalog).
- Wrong rate → `SST_WRONG_RATE` (now planted on goods too).
- Exempt goods taxed → `SST_SHOULD_BE_EXEMPT`.

### MG-3 Rate transitions (1 Jul 2025 and later amendments)

Goods that stopped being exempt on 1 Jul 2025 aren't taxed if invoiced before that date (Rate Order amendment 2025 para 3). Before 1 Jul 2025 the rate comes from the orders then in force: the 2018 orders from 1 Sep 2018, the 2022 orders from 1 Jun 2022. A goods category whose heading those orders exempt only in part has no earlier rate, and its lines dated before 1 Jul 2025 are HAND_OVER (added 19 Nov 2026, engine 0.10.1). The 1 Jan 2026 exemptions for critical raw materials used by registered manufacturers, animal feed, fertiliser and pesticides apply from that date.

- Deciding facts: invoice date, delivery date.

### MG-4 Exemptions by person (Persons Exempted Order)

- Schedule C: registered manufacturers buy raw materials, components, packaging and manufacturing aids for taxable goods exempt (items 1–5 as in the manufacturing guide).
- Schedule B: manufacturers of non-taxable goods buy inputs exempt. From 1 Sep 2026, items 5–7 (P.U. (A) 303/2026) add licensed manufacturers of animal feed, fertiliser and pesticide products, ending G-3's refund route.
- Schedule A: specific persons and purposes (e.g. items 34–38, 49, 54–56, 62 in the manufacturing guide; oil and gas items 33A/33B; others).
- All require the buyer to hold the exemption (certificate in the case documents) for those goods and that period.

- Deciding facts: certificate kind, number, validity, goods covered (company master and the PO/invoice reference).
- Unknown whether the goods are inside the certificate's scope → HAND_OVER.

### MG-5 Designated and special areas (rewritten 18 Nov 2026 from the Act and every area order)

**Areas**: as in MS-7 (Sales Tax Act 2018 s2 as amended by Acts A1596, from 1 Jan 2020, and A1718, from 1 Dec 2024). Parts VIII and IX (ss48–61) set the rules; in them "Malaysia" means the PCA.

**Zones of a goods line.** "From": where the goods were made or dispatched, which is the supplier's zone (supplier master). "To": the zone the goods are transported into, which is the delivery address's zone (line fact `delivery_zone`; default the company master's zone).

**Decision.** MG-5 runs after MG-1 and MG-2 and is judged at the invoice date (MG-3). Where no sales tax is due and the invoice shows some, the answer is `SST_SHOULD_BE_EXEMPT`.

1. From PCA to PCA: MG-5 does not apply.
2. From a PCA manufacturer into a DA (other than Pulau 1) or an SA: no sales tax on the invoice. The transport is treated as an export (ss51(1)(b), 58(1)(b)); no tax is levied on goods transported to a DA or SA from Malaysia (ss50(1)(a)(i), 57(1)(a)(i)). RMCD's Guide on Manufacturing and Import/Export (as at 1 Jan 2021) says these goods are declared on Customs Form No. 2 (K2), or JDA No. 3 for the JDA.
   - Goods the DA order taxes on entry (list below): the same guide says the tax is declared on Customs Form No. 1 (K1) on entering the DA. That is the buyer's import declaration, so the supplier's invoice still carries no sales tax. The buyer's K1 payment is outside AP (no `buyer_actions` value). This reading rests on the guide's sentence; it is open question Q-A1 for the accountant review.
   - Goods the SA order taxes on entry into a free zone, licensed warehouse or LMW (list below): no official text says whether the PCA manufacturer charges the tax on its invoice or it is paid on a customs declaration. Such a line → HAND_OVER either way (open question Q-A2). Not planted until settled.
3. From a DA (other than Pulau 1): the Act does not apply to goods manufactured in a DA other than petroleum (s49(1)). Sales tax on such a line → `SST_SHOULD_BE_EXEMPT`, whatever the "to" zone: goods sent from a DA to the PCA bear tax as an importation (s50(1)(b)), declared by the importer on K1 (guide, Table 1 row 10), not on the supplier's invoice. Petroleum manufactured in a DA: ordinary MG rules.
4. From an SA: the Act does not apply to goods manufactured in an SA (s56).
   - SA to SA, SA to DA: no tax (s57(1)(a)(ii), (iii)); tax shown → `SST_SHOULD_BE_EXEMPT`.
   - SA to PCA: tax is due as on an importation (ss57(1)(b), 58(1)(a)), declared on K1 or K9 (guide paras 56–58). No tax on the invoice → correct. Tax shown on the invoice → HAND_OVER: no official text says whether an LMW or warehouse licensee who paid the K9 tax may show it on its invoice (open question Q-A3).
   - JDA to PCA: no tax (s57(1)(a)(i); guide para 59(iii), Form JDA3); tax shown → `SST_SHOULD_BE_EXEMPT`.
5. From one area to another (within one DA, between DAs, DA to SA): no tax (ss50(1)(a)(ii), (iii)); tax shown → `SST_SHOULD_BE_EXEMPT`. For goods the DA order lists, moved between two DAs, the order's words "imported or transported into the designated area" (from 1 Jan 2026) may reach them → HAND_OVER for those lines only.
6. Pulau 1 (from 1 Dec 2024): the Act applies to goods manufactured in Pulau 1, except goods the Minister declares by order (s49(2)). Goods imported into Pulau 1 or transported into it from the PCA, a DA or an SA bear sales tax, except declared goods (s50(2)(a)). The DA order (P.U. (A) 369/2024) taxes all goods into Pulau 1 except wine, spirits, beer or malt liquor, chocolate, cosmetics and perfume.
   - A registered manufacturer in Pulau 1 selling goods made there, delivered in Pulau 1, not in that list: ordinary MG rules.
   - Goods in that list made in Pulau 1: HAND_OVER (no s49(2) order found yet).
   - Goods transported into Pulau 1 from elsewhere: HAND_OVER. The Act does not say whether the supplier charges this tax on its invoice or it is collected on entry (open question Q-A4).
   - Goods made in Pulau 1 and sent out of it: HAND_OVER. Section 50(2) covers goods into Pulau 1; no archived text covers goods leaving it (part of Q-A4).
   - Not planted until Q-A4 and the Pulau 1 boundary are settled.

**Goods the DA order taxes on entry** (P.U. (A) 206/2018 as amended by 92/2019, 391/2019, 420/2020, 94/2023, 369/2024, 481/2025):
- 1 Sep 2018 to 26 Mar 2019: wine, spirit, beer, malt liquor, tobacco and tobacco products into all DAs. Item deleted by 92/2019.
- From 1 Sep 2018: marble and anchovies into Langkawi; motor vehicles into Tioman. Pangkor added for motor vehicles from 1 Jan 2020 (391/2019).
- 1 Jan 2020 to 31 Dec 2020: petroleum into the DAs (391/2019).
- From 1 Jan 2021 (420/2020, paragraph replaced): petroleum, cigarettes, tobacco products, smoking pipes including bowls, electronic cigarettes and similar vaporising devices, and their liquid or gel preparations into the DAs. Until 31 Mar 2023 only preparations "not containing nicotine"; from 1 Apr 2023 "whether or not containing nicotine" (94/2023). From 1 Dec 2024 these apply to the DAs other than Pulau 1 (369/2024).
- From 1 Jan 2026 (481/2025): completely built-up motor vehicles imported into Labuan or Langkawi under headings 87.03 and 87.11, CIF value above RM300,000; motor vehicles made in the PCA and transported into Labuan or Langkawi under the same headings, sales price above RM300,000 excluding excise duty, sales tax, licence fee and insurance.

**Goods the SA order taxes on entry** (P.U. (A) 207/2018 as amended by 401/2018, 349/2021, 100/2023):
- Schedule A goods imported or transported into a free zone (from 1 Jan 2019 also a licensed warehouse or LMW) to be used or consumed there: forklifts; cranes; office equipment or furniture; firefighting and pollution control equipment; motor vehicles and spare parts; petroleum and petroleum products; tyres; explosives and chemicals; air conditioning equipment; manufacturing aids (until 31 Dec 2018); goods not used directly in the activities approved under the Free Zones Act 1990 First and Second Schedules, in warehousing under Customs Act s65, or in LMW manufacturing under s65A (wording from 1 Jan 2019).
- Wine, spirit, beer, malt liquor, tobacco and tobacco products into the Tasik Kenyir Duty Free Area.
- From 3 Sep 2021 (349/2021): cigarettes, tobacco products, smoking pipes, electronic cigarettes and their preparations into any free zone. Preparations "not containing nicotine" until 31 Mar 2023; "whether or not containing nicotine" from 1 Apr 2023 (100/2023).

- How the lists read (PR 4 review, 19 Nov): "moved between two DAs" in step 5 means two different DAs. The SA order's "to be used or consumed there" has no separate fact: a listed good delivered into the zone is taken as used there, and the line is HAND_OVER under Q-A2 anyway. The catalog maps categories to goods kinds, and a data file gives each list its kinds, zones and dates. The mappings of laptops, printers and office furniture to "office equipment or furniture", and of paints, adhesives, solvents and cleaning chemicals to "explosives and chemicals", are provisional and are reviewed when Q-A2 is settled.
- Deciding facts: supplier zone and whether it manufactured the goods (supplier master), delivery zone (line), the goods' category (catalog maps categories to the DA and SA lists), CIF value or sales price for the motor vehicle items (line), whether goods are used directly in the approved activity (line), whether the free zone is Tasik Kenyir (company master).
- Unknown zone, delivery zone, list membership or direct use, where it decides the line → HAND_OVER.

### MG-6 Ministerial sales tax exemptions (Sales Tax Policies, read 17 Nov 2026)

| Rule | Exemption | Source |
| --- | --- | --- |
| G-1 | Motorcycles 8711.20.96 00 and 8711.20.99 00 (50–250 cc, other) exempt from 1 Jul 2025 | Sales Tax Policy 1/2025 (Amdt 1) |
| G-2 | Soya beans 1201.10.00 00 and 1201.90.00 00 imported, exempt from 1 Jul 2025 | 2/2025 |
| G-3 | Raw materials for animal feed, fertilisers and pesticides (tariff codes in its Appendices I–III) bought by licensed manufacturers: 1 Jan 2026 to 31 Aug 2026, refund route (invoice correct as charged). From 1 Sep 2026 the Persons Exempted Order covers them (P.U. (A) 303/2026, Schedule B items 5–7), so MG-4 applies: a buyer holding the certificate is exempt, and tax shown → `SST_SHOULD_BE_EXEMPT`; without one, the ordinary rate applies (MG-2) | 1/2026; P.U. (A) 303/2026 |
| G-4 | Pallets: exempt under Schedule C items 1/3 only as one-way packaging that goes to the buyer; returnable transport pallets are taxable | 1/2022 |
| G-5 | Drop-shipment: a registered manufacturer exporting directly for a Malaysian trader invoices the trader without sales tax (one trader level only, bill-to/ship-to on the invoice) | 2/2022 |
| G-6 | Re-imports of exported goods returned because of the Middle East conflict, by the same manufacturer, to 31 Dec 2026 | 2/2026 |
| G-7 | Refund-only windows (no invoice effect): inputs for goods newly taxable on 1 Jul 2025 (3/2025); machinery under Schedule A item 55 bought 1 Jul–26 Sep 2025 (4/2025) | 3/2025, 4/2025 |

---

## 3. Malaysia — e-invoices and invoice validity

Sources: LHDN e-Invoice Guideline and Specific Guideline; MyInvois SDK; LHDN timeline (updated 30 Aug 2026); Service Tax Regulations 2018 (invoice particulars).

- ME-1 Supplier must issue a validated e-invoice when it is in a mandatory phase on the invoice date and outside that phase's interim relaxation period (rewritten 20 Nov 2026 from the archived LHDN timeline page, e-Invoice Guideline v4.6 §1.5–1.6 and Specific Guideline v4.9 §16).
  - Phases (LHDN timeline, updated 30 Aug 2026): annual turnover or revenue above RM100m from 1 Aug 2024; above RM25m up to RM100m from 1 Jan 2025; above RM5m up to RM25m from 1 Jul 2025; up to RM5m from 1 Jan 2026. Turnover is the FY2022 audited figure, or YA2022 revenue without audited accounts, pro-rated to 12 months if the year end changed; later changes don't move the phase (Guideline §1.5). New businesses: started 2023–2025 with turnover of at least RM1m, from 1 Jul 2026; started 2026 or later, from 1 Jul 2026 or the commencement date, or, if the first year is below RM1m, from 1 January of the second year after turnover reaches RM1m.
  - Exempt: turnover below RM3m (timeline page, 30 Aug 2026; Guideline v4.6 of 7 Dec 2025 still says RM1m, and the later page governs); foreign diplomatic offices; individuals not in business; statutory bodies and local authorities for statutory fees and charges, and for any supply before 1 Jul 2025; international organisations for supplies before 1 Jul 2025 (Guideline §1.6.1).
  - Interim relaxation (Specific Guideline §16, Table 16.1): six months from each phase's start: 1 Aug 2024–31 Jan 2025; 1 Jan–30 Jun 2025; 1 Jul–31 Dec 2025; and for the up-to-RM5m phase (1 Jan 2026 and 1 Jul 2026 start dates) until 31 Dec 2027. During it the supplier may issue a consolidated e-invoice and need not issue an individual one even if the buyer asks (§16.2(a), (d)). So a supplier invoice without a validated e-invoice, dated inside the supplier's relaxation period, raises no ME-1 finding.
  - Answer: missing validated e-invoice outside the relaxation period → finding, REQUEST_CORRECTED_INVOICE. Unknown supplier phase, where the invoice date falls on a date where the phase decides the line → HAND_OVER.
  - ME-3 during the buyer's relaxation period: the buyer may issue a consolidated self-billed e-invoice (§16.2(b)); `ISSUE_SELF_BILLED_EINVOICE` still applies.
- ME-2 Mandatory fields (TIN, registration numbers, classification, tax type, totals per tax type) — missing → REQUEST_CORRECTED_INVOICE (v0.9).
- ME-3 Self-billed e-invoice: the **buyer** issues the e-invoice itself for the transaction types in section 8.3 of the LHDN e-Invoice Specific Guideline (version 4.9, 7 Sep 2026; https://www.hasil.gov.my/wp-content/uploads/IRBM-e-Invoice-Specific-Guideline.pdf), read in full in the archived copy 18 Nov 2026: (a) payments to agents, dealers, distributors; (b) goods sold or services rendered by foreign suppliers; (c) profit distribution; (d) e-commerce transactions; (e) pay-outs to betting and gaming winners (casino and gaming-machine pay-outs exempted until further notice); (f) transactions with individuals not conducting a business, only where no other item applies; (g) interest payments, except (i) interest charged by businesses such as financial institutions to the public at large, (ii) interest paid by an employee to the employer, (iii) interest paid by a foreign payor to a Malaysian taxpayer, (iv) interest to a related company in Malaysia providing centralised treasury services, (v) late-payment interest or charges imposed by Malaysian taxpayers (for these exceptions the supplier issues the e-invoice); (h) claim, compensation or benefit payments from an insurer's insurance business; (i) payments on capital reduction, redemption, share buyback, return of capital or liquidation. Of these, (a), (b), (f) and (g) arise on supplier invoices in AP; (c), (d), (e), (h) and (i) are not supplier-invoice transactions in task set 1. Answer: `buyer_actions` += `ISSUE_SELF_BILLED_EINVOICE` (decided 17 Nov, D2) when the buyer is in a mandatory phase on the transaction date.
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
- From 1 Jan 2023 (Act 35 of 2022): (c) covers only insuring passenger transport, while arranging passenger transport is no longer zero-rated (insuring or arranging goods transport still is); (e) no longer covers arranging or facilitating the booking of accommodation (s21(4E)). Line facts: `transport_service_kind` (`insuring_passenger`, `arranging_passenger`, `goods`) for (c), and `accommodation_booking` (yes/no) for (e). From 1 Jan 2023, a (c) or (e) line that doesn't show which → HAND_OVER.
- Answer: a local supplier charging 9% on a line that qualifies → `GST_WRONGLY_CHARGED`. Where qualification turns on facts the buyer's documents show (route, goods location, export evidence), the engine decides; where it turns on the supplier's contract counterparty or the beneficiary's location not shown → HAND_OVER. Note for (j): a Singapore buyer is normally the contracting party, so (j) rarely applies to its purchases.

### SG-7 Customer accounting for prescribed goods

Mobile phones (screen ≤ 17.5 cm, not sold with a plan), memory cards (not USB flash drives) and off-the-shelf software (physical media or key in physical packaging), sold to a GST-registered buyer for business use, above S$10,000 excl. GST per invoice: the supplier must **not** charge GST; it issues a customer accounting tax invoice stating the buyer must account for GST of $X; the buyer accounts for output tax and claims input tax.
- GST charged anyway → `GST_WRONGLY_CHARGED`, REQUEST_CORRECTED_INVOICE.
- Correct CA invoice → `CUSTOMER_ACCOUNTING` (new code); `buyer_actions` += account for GST.

### SG-8 Reverse charge (imported services and low-value goods)

Applies only to GST-registered buyers **not entitled to full input tax credit**. Three kinds of buyer are not entitled: a partially exempt buyer that does not meet the de minimis rule, a buyer with non-business receipts, and a member of a GST group that is not entitled to full input tax credit (IRAS e-Tax guide on overseas vendor registration, footnote 4: reverse charge applies to GST-registered persons "not entitled to full input tax credit or belong[ing] to a GST group that is not entitled to full input tax credit"). Such a buyer accounts for GST on imported services from 1 Jan 2020 and on low-value goods from 1 Jan 2023 (IRAS "GST and the digital economy", local businesses; IRAS e-Tax guide on reverse charge).
- A buyer meeting the de minimis rule may claim all its input tax (IRAS "Claiming input tax incurred to make exempt supplies"), so on its own it does nothing. Inside a GST group without full credit, it reverse-charges.
- A fully taxable buyer does nothing.
- Imported goods other than low-value goods bear GST at import, not on the invoice: `NO_GST`.
- Deciding facts, read in this order: supplier outside Singapore (supplier master); service or low-value goods (catalog, line fact `low_value_goods`); the buyer's input-tax status (`fully_taxable`, `de_minimis_met`, `partially_exempt`); non-business receipts; GST group membership and whether the group is entitled to full input tax credit (all company master). The first one the case can't show → HAND_OVER.
- Answer: `REVERSE_CHARGE` with `buyer_actions` += `ACCOUNT_REVERSE_CHARGE_GST` where it applies; otherwise `NO_GST`.

### SG-9 Partially exempt buyers

Input tax directly attributable to exempt supplies is not claimable unless the de minimis rule is met (exempt supplies ≤ S$40,000 a month on average and ≤ 5% of total supplies); residual input tax is apportioned.
- Deciding facts: buyer status (company master: fully taxable / de minimis met / partially exempt) and the purpose of the purchase.
- Answer: `NOT_CLAIMABLE_EXEMPT_USE` (new code) for directly attributable lines; `RESIDUAL_APPORTIONED` (new) for residual lines. Unknown attribution → HAND_OVER.

### SG-10 Regulations 26/27 and related IRAS rules

- v0.9 list, with the IRAS exceptions added in A11 (staff medical: WICA, collective agreement, work-related health risk under written law, COVID-19 advisory; insurance: obligatory under WICA or a collective agreement).
- Motor cars: the Regulation 25(1) exclusions are business service passenger vehicles registered before 1 Apr 1998 (line or asset fact `vehicle_registered_on`), taxis, private cars registered for school transport, unused cars supplied for sale or hire, cars supplied to financial institutions for hire purchase, dealer stock, used cars supplied for hire, and driving-school cars. Claimable exceptions: pay-per-trip chauffeured private hire car services (from 1 Apr 2022); a motor car used by a third party (from 1 Jan 2023, on the IRAS conditions).
- Benefits given only to sole proprietors, partners or directors → not claimable (employee benefits page).
- Corporate social initiatives for third-party beneficiaries → not for the purpose of business, not claimable.

### SG-11 Timing and payment

Claim in the period of the invoice date (or posting date if applied consistently); repay if the supplier isn't paid within 12 months of the due date. Duplicate claims are caught by the duplicate check.

### SG-12 GST not charged when it should have been (added 17 Nov after the spec review)

A GST-registered supplier must charge and account for GST on its standard-rated supplies and issue tax invoices for them (IRAS, responsibilities of a GST-registered business). A line from a registered supplier that shows no GST on a standard-rated supply, where none of SG-5 to SG-8 applies, is wrong in the same way as MS-9: the buyer has no GST to claim, and the invoice is wrong.
- Answer: `GST_UNDERCHARGED`, REQUEST_CORRECTED_INVOICE. (SG-3 covers a rate lower than the time-of-supply rules allow; SG-12 covers GST left off entirely.)
- Deciding facts: supplier GST registration on the invoice date; supply category (exempt, zero-rated, out of scope, customer accounting, reverse charge). Unknown → HAND_OVER.

---

## 4A. Withholding tax on payments to non-residents (decided 17 Nov, D3)

Withholding doesn't change the tax treatment of the invoice; it changes what the buyer pays the supplier and what it pays the tax authority. Answer: `buyer_actions` += `WITHHOLD_TAX` with `rate`, `basis` and the base amount. Where a DTA rate is claimed, the case must hold the payee's certificate of residence; without it the domestic rate applies.

**Malaysia** (LHDN "Withholding tax" page; Public Ruling 10/2019 "Withholding Tax on Special Classes of Income"; both read 17 Nov 2026). The payer is a resident person, the government, or anyone claiming the payment as a business expense in Malaysia.
- **WH-1 Interest** to a non-resident: 15% (ITA s109). **Royalty**: 10% (s109).
- **WH-2 Special classes of income** (s4A, s109B): 10% of the gross amount (no grossing-up from 5 Dec 2018), for (i) services in connection with the non-resident's property or rights, or installing/operating plant bought from it; (ii) technical advice, assistance or services for managing or administering a scientific, industrial or commercial undertaking; (iii) rent or payments for use of movable property. Services performed **outside** Malaysia under (i) and (ii) are exempt [Income Tax (Exemption) (No. 9) Order 2017, from 6 Sep 2017]; mixed contracts are apportioned to the Malaysian part. Before 17 Jan 2017, services under (i) and (ii) performed outside Malaysia were not chargeable at all; they became chargeable from 17 Jan 2017 until the exemption from 6 Sep 2017 (Public Ruling 10/2019 para 5.2). Whether a supply falls before or after 6 Sep 2017 is decided by when the services were performed and when payment was made (Public Ruling 10/2019 §21), not by the invoice date; where the documents don't show both → HAND_OVER. Before 5 Dec 2018, where the payer bears the tax under the contract, the base is grossed up; the fact `tax_borne_by_payer` decides it, and unknown → HAND_OVER. (iii) applies wherever the property is used. Reimbursements are part of the gross amount, except hotel accommodation. Freight alone is outside (iii); handling or agency fees with it fall under (ii).
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

**Designated and special areas (read 18 Nov 2026).** MS-7 and MG-5 are read in full from the archived Acts and orders. Five questions are open. In Q-A1 to Q-A4 the official texts say tax is due, but not who collects it or how it shows on an invoice:
- Q-A1: goods the DA order taxes, sent from a PCA manufacturer into a DA. The RMCD manufacturing guide (as at 1 Jan 2021) says they are declared on K1 on entering the DA, so the sheet treats the invoice as carrying no sales tax.
- Q-A2: Schedule A goods (and tobacco or alcohol) sent from a PCA manufacturer into a free zone, licensed warehouse or LMW. → HAND_OVER, not planted.
- Q-A3: tax shown on an invoice from an LMW or licensed warehouse for goods sent into the PCA (tax declared on K9). → HAND_OVER, not planted.
- Q-A4: goods transported into Pulau 1, and listed goods made there. → HAND_OVER, not planted. The Pulau 1 boundary (Customs Act s2(1)) is not archived yet.
- Q-A5: whether a petroleum supply base is a special area for service tax. Act A1597 para 3(b) adds it, but no archived notice brings that paragraph into force. → HAND_OVER where it decides the answer, not planted.

Next research step: look for RMCD guides published after 1 Jan 2021 that settle Q-A1 to Q-A4. Candidates are a newer Guide on Manufacturing and Import/Export, the free zone and LMW guides, and any Pulau 1 guide. For Q-A5, look for a P.U. (B) notice bringing Act A1597 para 3(b) into force. Also archive the Customs Act definition of Pulau 1. Each answer found moves its question out of HAND_OVER with a citation. Until then, Q-A1 stays as written and is flagged for the accountant review.

Left for the archive and engine PRs, as data rather than rules: the per-country DTA rate tables (LHDN and IRAS pages), the tariff-code lists in Sales Tax Policy 1/2026, and the full Service Tax and Sales Tax Policy texts (all to be archived in decision-benchmark-sources with manifest entries).

## 7. Decisions (taken by Sebastian, 17 Nov 2026)

Rule behind all four: the benchmark covers everything an AP team must do in practice, so the model can be used in every case.

- **D1 `buyer_actions`: yes.** A list field in the answer, scored as an extra column like per-line treatments.
- **D2 Self-billed e-invoices: yes**, as `ISSUE_SELF_BILLED_EINVOICE`.
- **D3 Withholding tax: yes**, as `WITHHOLD_TAX` with rate and basis (§4A).
- **D4 SME rental exemption: yes.** The legal instrument is the Minister's exemption under Service Tax Act s34(3)(a) and s34(4), published as Service Tax Policy 2/2025 (Amendment No. 5) of 22 Jul 2026; cited as K-1 and K-2.

## 8. Sources

Malaysia — https://mysst.customs.gov.my/sst-regulations/ , /sst-orders/ , /industry-guides/ , /service-tax-policy/ (Service Tax Policies 1/2019–6/2026), /sales-tax-policy/ (Sales Tax Policies 1/2022–2/2026), /faq-services-tax/ , /faq-sales-tax/ ; MOF releases of 9 Jun 2025 and 5 Jan 2026; LHDN e-invoice timeline and MyInvois SDK; LHDN withholding tax page (https://www.hasil.gov.my/en/perundangan/cukai-pegangan/), Public Ruling 10/2019 (https://www.hasil.gov.my/wp-content/uploads/PR_10_2019.pdf), DTA withholding rates (https://www.hasil.gov.my/en/antarabangsa/perjanjian-pengelakan-pencukaian-dua-kali-pppdk/kadar-cukai-pegangan/).
Malaysia, areas (MS-7, MG-5) — Service Tax Act 2018 Parts VIII–IX and Acts A1597, A1719; Sales Tax Act 2018 Parts VIII–IX and Acts A1596, A1718 with their commencement notices; P.U. (A) 212/2018 and amendments 232/2018, 231/2019, 393/2019, 65/2024, 371/2024, 165/2025, 337/2026; P.U. (A) 370/2024 (Pulau 1); P.U. (A) 206/2018 and amendments 92/2019, 391/2019, 420/2020, 94/2023, 369/2024, 481/2025; P.U. (A) 207/2018 and amendments 401/2018, 349/2021, 100/2023; Service Tax Policies 1/2021 and 2/2022; RMCD Guide on Manufacturing and Import/Export (as at 1 Jan 2021); RMCD Panduan Perkhidmatan Penginapan (V4, 26 Feb 2024) and Panduan Makanan dan Minuman (V7, 19 Apr 2024); RMCD service tax and sales tax FAQs; commencement notices P.U. (B) 659/2019, 660/2019, 470/2024, 471/2024. All archived in decision-benchmark-sources (PR #4 and the v0.10 archive).
Singapore — https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/ (pages listed in §4), incl. GST rate change transitional rules and adjustments pages; GST Act 1993 s21 (https://sso.agc.gov.sg/Act/GSTA1993); IRAS, responsibilities of a GST-registered business (https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/responsibilities-of-a-gst-registered-business) for SG-12; IRAS withholding tax pages (https://www.iras.gov.sg/taxes/withholding-tax/).
