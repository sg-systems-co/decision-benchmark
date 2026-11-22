# Catalog of categories, ap-invoices

`categories.yaml` lists every goods and service category the generator may put on an invoice line. For each one it says how the tax rules treat it and which GL role it books to. The rules engine reads it; it never guesses a category's treatment.

The file is drafted by Claude in the planning chat and approved by Sebastian (step-11 plan §7.1, §14). The rules-engine tests keep using the small test-only catalog in `tests/fixtures/catalog.yaml`; `tests/models/test_catalog.py` loads the release catalog.

## Release catalog v1 (16 Nov 2026)

70 categories: 40 goods, 30 services. 62 are used in Malaysia, 67 in Singapore.

| Malaysia | Count |
| --- | --- |
| `sales_10` | 25 |
| `sales_5` | 9 |
| `sales_exempt` | 4 |
| Schedule C eligible (of the sales-tax goods) | 17: raw materials, packaging, components |
| `service_6` | 7 (F&B, logistics ×3, telecoms, parking, construction) |
| `service_8` | 16 (13 Group G, advertising, hotel, vehicle servicing) |
| B2B exemption (`b2b_exempt`) | 16: Group G except (j) and (k), logistics J1(a) and J1(d), advertising I8, construction L |
| Group relief (`group_relief`) | 11: the Group G items (a) to (i) and (n) |
| `none` | 1 |

Singapore: 8 categories carry a Regulation 26/27 class (motor_car ×3, and one each of the other five).

**Where the rates come from.** Every source is an official page or a PDF linked from one, and every one was opened and read on 16 Nov 2026.

- Goods: the gazetted Sales Tax (Rate of Sales Tax) Order 2025 [P.U. (A) 170/2025] and Sales Tax (Goods Exempted from Sales Tax) Order 2025 [P.U. (A) 171/2025], with all later amendments, as linked from https://mysst.customs.gov.my/sst-orders/ (see the header of `categories.yaml`). Each goods entry names its HS heading or exact subheading in `note`.
- Services: the RMCD industry guides linked from https://mysst.customs.gov.my/industry-guides/, the service-tax FAQ and the MOF releases. Every taxable service names its First Schedule item in `service_item`.
- Singapore: the IRAS page on conditions for claiming input tax.

**Left out of v1 (v0.9).** Rental and leasing, financial services, private healthcare, education, beauty, cleaning services, domestic flights and Malaysian electricity were left out because rule sheet v0.9 didn't settle them. Rule sheet v0.10 settles all of them except domestic electricity (P-21, not a company purchase), and A12 added categories for them; the v0.9 limits no longer apply (B1 plan, decision 13).

### Planting limits for v0.10 (B1 plan §3.5)

Each limit is a test run over every generated case, in `tests/generator/test_planting_limits.py`. The PR that builds the cases a limit governs adds its test; until then the engine test named here holds the rule.

| # | Limit | Test |
| --- | --- | --- |
| 1 | No Q-A2 to Q-A5 case: no engine result names those questions, and no master or line fact gives the zone `pulau_1`. | `test_limit_1_no_open_area_questions` (B1-4); engine: `tests/rules/test_my_areas.py` |
| 2 | Q-A1 only when flagged: `open_questions: [Q-A1]` in the generator truth if and only if the engine's line result carries Q-A1. | `test_limit_2_q_a1_only_when_flagged` (B1-4); engine: `tests/rules/test_my_areas.py` |
| 3 | No goods line dated before 1 Sep 2018 (invoice or delivery date). | `test_limit_3_no_goods_before_sales_tax` (B1-4); engine: `test_goods_before_2025.py` |
| 4 | No `process_gauges`, `control_instruments` or `tool_bits` line dated before 1 Jul 2025. | `test_limit_4_no_partly_exempt_headings_early` (B1-4); engine: `test_goods_before_2025.py` |
| 5 | A case that reads an unconfirmed Singapore treaty row is HAND_OVER with basis WH-5, in an Ambiguous slot. | `test_limit_5_unconfirmed_treaty_rows` (B1-5); engine: `test_withholding.py` |
| 6a | A zone always comes from a master or a line fact, never from an address. | `test_limit_6a_zone_from_records` (B1-4) |
| 6b | Self-billing types (a), (b), (f) and (g) only. | `test_limit_6b_self_billing_types` (B1-4) |
| 6c | `sales_exempt` and `none` categories are never charged tax. | `test_limit_6c_exempt_categories_uncharged` (B1-4) |
| 6d | `group_relation: unclear` only on group-relief categories. | `test_limit_6d_unclear_group_relation` (B1-4) |
| 6e | Credit notes are clean only (step 11 Q12). | `test_limit_6e_clean_credit_notes` (B1-3) |
| 7 | Every planted WH-2 line states its service period. | `test_limit_7_wh2_service_period` (B1-4) |

The allocator's own limits (exact quotas, hard kinds only where the plan allows them, a rule at most once per case, the precedence-row cap) are tested now, in `tests/generator/test_slots.py`.

### Rules for the generator (B1)

- **B2B exemption.** A company's `services_provided` lists First Schedule items (`service_item` values such as `G(h)`, `J1(a)`, `I8`, `L`), not categories. A line is exempt when its category has `b2b_exempt: true`, both parties are SST-registered, the buyer provides the same item and the line is not for personal use. Different categories can share an item: `it_services` and `software_development` are both `G(h)`, `logistics_haulage` and `warehousing` both `J1(a)`. Courier is `J1(d)`, a different item from `J1(a)`.
- **Group relief** applies only to categories with `group_relief: true` (Group G items (a) to (i), (l) and (n); see `GROUP_RELIEF_ITEMS`). Set `group_relation: unclear` only on invoices for those; for any other category the relation doesn't matter and the case is not a HAND_OVER.
- **Construction:** any contract the K-x and L-x rules settle, including non-reviewable contracts signed before 1 July 2025 (L-1) and residential work (L-2, L-5); the v0.9 limit (contracts signed on or after 1 July 2025, commercial premises only) is gone.
- **Courier:** a courier licensed under the Postal Services Act 2012 (item `J1(d)`). Before 26 February 2024 courier delivery was the old Group I item 6, parcels up to 30 kg only: a courier line dated before then (or in the STP 1/2024 window to 31 March 2024) states `parcel_weight_kg`. **Vehicle servicing in Malaysia:** labour only (spare parts are not service-taxed).
- **26 February 2024 additions (engine 0.10.3).** `karaoke_event_venue` (Group C item 1(e)), `maintenance_repair` and the other G(n) categories, the I12 brokering categories and the Group J logistics categories are taxable services only from 26 February 2024 (Service Tax (Amendment) Regulations 2024). A line dated 26 February to 31 March 2024 falls under the STP 1/2024 transitional exemption and needs the supplier fact `registered_before_2024_02_26` where it decides (1-31 March). A line with a service period across 26 February 2024 or 1 July 2025 (the start of Groups H items 2-4, K, L, M and Group I items 14-16) is taxed only on the part from the start date (reg 3A, MS-3): B1 states `value_provided_before_change` on such a line or plants it as HAND_OVER.
- **`wellness_centre_services`** (Group C item 2): before 1 July 2025 the line fact `wellness_facility_kind` names an excluded facility (private, Government or university healthcare facility; T&CM practitioner premises from 27 November 2024); not recorded means none.
- **Critical raw materials from 1 January 2026 (MG-3).** These are the animal feed, fertiliser and pesticide raw materials of Sales Tax Policy No. 1/2026 (refund route from 1 January 2026, rule G-3) and, from 1 September 2026, Schedule B items 5 to 7 of the Persons Exempted Order [P.U. (A) 303/2026] (MG-4). The pinned G-3 categories carry them; no other category relies on the Policy's appendix codes.
- **Singapore motor cars and staff medical:** `vehicle_servicing`, `company_car_tyres_parts` and `company_car_leasing` need the line fact `vehicle_is_motor_car`; `staff_medical` needs `staff_medical_obligatory`, true when any IRAS exception applies. Where the documents don't say, the case is HAND_OVER.
- **`group_medical_insurance`** needs the line fact `insurance_obligatory`: true when the cover is obligatory under the Work Injury Compensation Act or a collective agreement (claimable), false when it is not (disallowed). Where the documents don't say, the case is HAND_OVER.
- **`parking` in Singapore** is delivery-vehicle parking only.
- `sales_exempt` and `none` categories appear in clean cases only; the generator never charges tax on them.
- **Goods invoices dated before 1 July 2025.** A goods line dated before 1 July 2025 takes its category's `earlier_classes` (the Sales Tax (Rates of Tax) and (Goods Exempted from Tax) Orders 2018 and 2022; engine 0.10.1). B1 plants such a line only for a category that has `earlier_classes`. `process_gauges`, `control_instruments` and `tool_bits` have none, because the earlier orders exempt their headings only in part: the engine answers HAND_OVER and B1 does not plant them before 1 July 2025. B1 plants no goods line dated before 1 September 2018, when sales tax began. Until engine 0.10.1 was merged, B1 planted no goods line dated before 1 July 2025 at all. Decided in the review of build PR 5 (PR #18), 19 Nov 2026.
- **Designated and special areas (MS-7, MG-5).** `area_items` maps a service category to the items of the Schedule to P.U. (A) 212/2018 (services taxed inside and between areas); `area_goods` maps a goods category to the goods kinds the sales tax area orders name (the lists, zones and dates are in `countries/my/data/area_goods_lists.yaml`). Where a category might fall under a Schedule A item (office equipment, chemicals), it is mapped as listed, so a line into a special area is HAND_OVER rather than a guess. B1 plants no case that turns on Q-A2, Q-A3, Q-A4 or Q-A5, and no Pulau 1 case. Q-A1 cases (DA-listed goods from a principal customs area manufacturer) are planted only with `open_question: Q-A1` in the generator truth (the engine's line result carries it), so they can be dropped if the accountant review overturns the reading. A zone always comes from a master or a line fact, never from an address.
- **Self-billed e-invoices (ME-3).** Of the nine `self_billing_type` values (section 8.3 (a) to (i) of the LHDN e-Invoice Specific Guideline v4.9), only four arise on supplier invoices, so B1 plants only these: `agents_dealers_distributors` (a), `foreign_supplier` (b), `individual_not_in_business` (f) and `interest_payment` (g). On (g), `interest_exception` may be planted; where an exception applies, the supplier issues the e-invoice and there is no buyer action. Decided in the review of build PR 1 (PR #12), 18 Nov 2026.

### GL roles

The chart-of-accounts templates (B1) must have exactly one active account for each role used here: `audit_accounting_fees`, `bank_charges`, `building_works`, `cleaning_supplies`, `club_subscriptions`, `components`, `freight_inward`, `insurance`, `interest_expense`, `it_equipment`, `it_services`, `legal_fees`, `management_fees`, `marketing_advertising`, `motor_vehicle_running`, `motor_vehicles`, `office_equipment`, `office_furniture`, `office_supplies`, `packaging_materials`, `parking`, `plant_machinery`, `postage_courier`, `professional_fees`, `raw_materials`, `recruitment`, `rent`, `repairs_maintenance`, `royalties`, `safety_ppe`, `security`, `staff_welfare`, `staff_welfare_medical`, `telecoms`, `tools_small_equipment`, `training`, `travel`, `utilities`, `warehousing`.

## Format

YAML. Validated by `decision_benchmark.task_sets.ap_invoices.models.Catalog` (`src/decision_benchmark/task_sets/ap_invoices/models/catalog.py`). Unknown keys are errors. Don't write numbers as floats; this file has none.

A category lists the countries it is used in. Its tax treatment in each country is a **tax profile** under `tax:`, keyed by country code. The profile's fields come from that country's pack (`countries/<cc>/models.py`), so adding a country adds a profile type there, not a column here.

```yaml
version: 1
categories:
  - category: logistics_haulage        # unique, lower_snake_case
    kind: service                      # goods | service
    label: "Lorry haulage and freight transport"
    countries: [MY, SG]                # where the generator may use it
    tax:                               # one profile per country; see "Tax profiles"
      MY: {tax_class: service_6, service_item: "J1(a)", b2b_exempt: true, group_relief: false}
      # SG omitted: no Regulation 26/27 class, so the default SG profile applies
    gl_role: freight_inward            # key into the chart-of-accounts templates
    sources:                           # at least one https URL, taken from tax-rules-v0.9.md
      - "https://mysst.customs.gov.my/faq-services-tax/"
    note: "Group J item 1(a): one of the four 6% service categories, B2B exemption for the same item only."
```

### Tax profiles

| Country | Required | Keys |
| --- | --- | --- |
| `MY` (`MyTaxProfile`) | yes, for every category used in MY | `tax_class`: `sales_5`, `sales_10`, `sales_exempt`, `service_8`, `service_6`, `none` (not taxable under SST in v0.9); for goods, the class under the 2025 orders, from 1 Jul 2025. `earlier_classes` (goods only): the class before 1 Jul 2025 by period, `{valid_from, valid_to, tax_class}`, ending by 30 Jun 2025; none means a line dated before 1 Jul 2025 is HAND_OVER. `schedule_c_eligible` (goods under sales tax only). `service_item`: the First Schedule item, e.g. `G(a)`, `J1(a)`, `I8`, `L`; required for `service_6` and `service_8`, null otherwise. `b2b_exempt`: the item is in a B2B scheme (Group G except (j) and (k), Group J same item, Group I item 8, Group L). `group_relief`: Group G items (a) to (i), (l) and (n) only. The flags default to `false`. |
| `SG` (`SgTaxProfile`) | no; omit when nothing applies | `disallowed`: Regulation 26/27 class: `club_subscription`, `staff_medical`, `motor_car`, `family_benefit`, `medical_accident_insurance`, `betting`, or null (the default). |

### Checks the loader enforces

- Every country in `countries` has a country pack; `tax` has no key outside `countries`.
- A country whose pack requires a profile (MY) has one.
- MY: goods never carry a `service_*` class, services never a `sales_*` class; `service_item` is set exactly for `service_6` and `service_8`; `b2b_exempt` and `group_relief` need a `service_item`; `group_relief` only on Group G items; `G(j)` and `G(k)` are never `b2b_exempt`; `schedule_c_eligible: true` needs `kind: goods` and a `sales_*` class.
- Every source is an `https://` URL.

### What to include (step-11 plan §7.1, decisions Q9 and Q10)

- About 60 categories: 30 goods, 30 services.
- Every situation in the rule-sheet table needs at least one category: the four 6% services (F&B, logistics, telecoms, parking), the B2B schemes (Group G, logistics, advertising, construction) and the items without it (employment and guard services), Schedule C raw materials, components, packaging and manufacturing aids, and all six Singapore Regulation 26/27 classes.
- Leave out categories the rule sheet doesn't settle: rental and leasing (Q10), and goods whose 5% or 10% sales-tax rate has no source in the rule sheet (Q9). Construction may be included at `service_6`.
- `sales_exempt` and `none` categories are allowed in clean cases, but the generator never plants tax on them.
- The SG `motor_car`, `staff_medical` and `medical_accident_insurance` classes need the invoice line's facts (`vehicle_is_motor_car`, `staff_medical_obligatory`, `insurance_obligatory`, declared by the SG pack) (whether the vehicle is a motor car under Regulation 25(1); whether the medical cost or the insurance is obligatory). Where the documents don't say, the case is HAND_OVER by construction.
- `gl_role` names are free text but must match the chart-of-accounts templates (added in PR B1). Use plain roles such as `it_services`, `freight_inward`, `raw_materials`, `club_subscriptions`, `staff_welfare_medical`, `motor_vehicle_running`.
