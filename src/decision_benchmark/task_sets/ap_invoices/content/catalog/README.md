# Catalog of categories, ap-invoices

`categories.yaml` lists every goods and service category the generator may put on an invoice line. For each one it says how the tax rules treat it and which GL role it books to. The rules engine reads it; it never guesses a category's treatment.

The file is drafted by Claude in the planning chat and approved by Sebastian (step-11 plan §7.1, §14). The rules-engine tests keep using the small test-only catalog in `tests/fixtures/catalog.yaml`; `tests/models/test_catalog.py` loads the release catalog.

## Release catalog v1 (16 Nov 2026)

61 categories: 31 goods, 30 services. 53 are used in Malaysia, 58 in Singapore.

| Malaysia | Count |
| --- | --- |
| `sales_10` | 25 (13 of them Schedule C eligible: raw materials, packaging, components) |
| `sales_exempt` | 4 |
| `service_6` | 7 (F&B, logistics ×3, telecoms, parking, construction) |
| `service_8` | 16 (10 Group G, 2 Group G excluded: employment and guards) |
| `none` | 1 |

Singapore: 8 categories carry a Regulation 26/27 class (motor_car ×3, and one each of the other five).

**Where the rates come from.** Every goods rate comes from the Sales Tax (Rate of Sales Tax) Order 2025 and the Sales Tax (Goods Exempted from Sales Tax) Order 2025, read at HS-heading level (see the header of `categories.yaml` and the CHANGELOG clarification). Service-tax rates and groups come from the rule sheet's sources. Each goods entry names its HS heading in `note`.

**Left out on purpose.** Goods at 5% (headings could not be checked at subheading level), rental and leasing (Q10; its rate also changed to 6% on 1 January 2026), financial services, private healthcare, education, beauty, cleaning services, domestic flights and Malaysian electricity (none of these is settled by the rule sheet).

### Rules for the generator (B1)

- **B2B exemptions v0.9 does not model.** Logistics (`logistics_haulage`, `courier_services`, `warehousing`), advertising and construction works have B2B exemptions of their own, and `maintenance_repair` is kept out of the Group G B2B test. A company's `services_provided` may only contain categories with `group_g: true` and `group_g_excluded: false`, so no buyer ever provides one of these services.
- **Construction:** contracts signed on or after 1 July 2025, commercial premises only.
- **Singapore motor cars and staff medical:** `vehicle_servicing`, `company_car_tyres_parts` and `company_car_leasing` need the line fact `vehicle_is_motor_car`; `staff_medical` needs `staff_medical_obligatory`. Where the documents don't say, the case is HAND_OVER.
- **`parking` in Singapore** is used for delivery-vehicle parking only.
- `sales_exempt` and `none` categories appear in clean cases only; the generator never charges tax on them.

### GL roles

The chart-of-accounts templates (B1) must have exactly one active account for each role used here: `audit_accounting_fees`, `building_works`, `cleaning_supplies`, `club_subscriptions`, `components`, `freight_inward`, `it_services`, `legal_fees`, `management_fees`, `marketing_advertising`, `motor_vehicle_running`, `office_furniture`, `office_supplies`, `packaging_materials`, `parking`, `plant_machinery`, `postage_courier`, `professional_fees`, `raw_materials`, `recruitment`, `repairs_maintenance`, `safety_ppe`, `security`, `staff_welfare`, `staff_welfare_medical`, `telecoms`, `tools_small_equipment`, `training`, `travel`, `utilities`, `warehousing`.

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
      MY: {tax_class: service_6}
      # SG omitted: no Regulation 26/27 class, so the default SG profile applies
    gl_role: freight_inward            # key into the chart-of-accounts templates
    sources:                           # at least one https URL, taken from tax-rules-v0.9.md
      - "https://mysst.customs.gov.my/faq-services-tax/"
    note: "Logistics is one of the four 6% service categories."
```

### Tax profiles

| Country | Required | Keys |
| --- | --- | --- |
| `MY` (`MyTaxProfile`) | yes, for every category used in MY | `tax_class`: `sales_5`, `sales_10`, `sales_exempt`, `service_8`, `service_6`, `none` (not taxable under SST in v0.9). `schedule_c_eligible` (goods under sales tax only), `group_g` (Group G professional service, B2B exemption test), `group_g_excluded` (Group G but excluded: employment, guard services). The three flags default to `false`. |
| `SG` (`SgTaxProfile`) | no; omit when nothing applies | `disallowed`: Regulation 26/27 class: `club_subscription`, `staff_medical`, `motor_car`, `family_benefit`, `medical_accident_insurance`, `betting`, or null (the default). |

### Checks the loader enforces

- Every country in `countries` has a country pack; `tax` has no key outside `countries`.
- A country whose pack requires a profile (MY) has one.
- MY: goods never carry a `service_*` class, services never a `sales_*` class; `group_g: true` needs `kind: service` and `tax_class: service_8`; `group_g_excluded: true` needs `group_g: true`; `schedule_c_eligible: true` needs `kind: goods` and a `sales_*` class.
- Every source is an `https://` URL.

### What to include (step-11 plan §7.1, decisions Q9 and Q10)

- About 60 categories: 30 goods, 30 services.
- Every situation in the rule-sheet table needs at least one category: the four 6% services (F&B, logistics, telecoms, parking), Group G services (and the excluded employment and guard services), Schedule C raw materials, components, packaging and manufacturing aids, and all six Singapore Regulation 26/27 classes.
- Leave out categories the rule sheet doesn't settle: rental and leasing (Q10), and goods whose 5% or 10% sales-tax rate has no source in the rule sheet (Q9). Construction may be included at `service_6`.
- `sales_exempt` and `none` categories are allowed in clean cases, but the generator never plants tax on them.
- The SG `motor_car` and `staff_medical` classes need the invoice line's facts (`vehicle_is_motor_car`, `staff_medical_obligatory`, declared by the SG pack) (whether the vehicle is a motor car under Regulation 25(1); whether the medical cost is obligatory). Where the documents don't say, the case is HAND_OVER by construction.
- `gl_role` names are free text but must match the chart-of-accounts templates (added in PR B1). Use plain roles such as `it_services`, `freight_inward`, `raw_materials`, `club_subscriptions`, `staff_welfare_medical`, `motor_vehicle_running`.
