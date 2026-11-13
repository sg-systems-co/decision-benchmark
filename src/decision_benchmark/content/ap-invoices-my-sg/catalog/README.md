# Catalog of categories, ap-invoices-my-sg

`categories.yaml` lists every goods and service category the generator may put on an invoice line. For each one it says how the tax rules treat it and which GL role it books to. The rules engine reads it; it never guesses a category's treatment.

The file is drafted by Claude in the planning chat and approved by Sebastian (step-11 plan §7.1, §14). Until it lands, the rules engine is tested with a small test-only catalog in `tests/fixtures/catalog.yaml`.

## Format

YAML. Validated by `decision_benchmark.models.Catalog` (`src/decision_benchmark/models/catalog.py`). Unknown keys are errors. Don't write numbers as floats; this file has none.

```yaml
version: 1
categories:
  - category: logistics_haulage        # unique, lower_snake_case
    kind: service                      # goods | service
    label: "Lorry haulage and freight transport"
    countries: [MY, SG]                # where the generator may use it
    my_tax_class: service_6            # required if MY is listed; see below
    schedule_c_eligible: false         # goods under sales tax only
    group_g: false                     # Group G professional service (B2B exemption test)
    group_g_excluded: false            # Group G but excluded from the B2B exemption (employment, guard services)
    sg_disallowed: null                # Regulation 26/27 class, or null
    gl_role: freight_inward            # key into the chart-of-accounts templates
    sources:                           # at least one https URL, taken from tax-rules-v0.9.md
      - "https://mysst.customs.gov.my/faq-services-tax/"
    note: "Logistics is one of the four 6% service categories."
```

### Allowed values

| Key | Values |
| --- | --- |
| `my_tax_class` | `sales_5`, `sales_10`, `sales_exempt`, `service_8`, `service_6`, `none` (not taxable under SST in v0.9) |
| `sg_disallowed` | `club_subscription`, `staff_medical`, `motor_car`, `family_benefit`, `medical_accident_insurance`, `betting`, or null |

### Checks the loader enforces

- `my_tax_class` is set exactly when `MY` is in `countries`.
- Goods never carry a `service_*` class; services never carry a `sales_*` class.
- `group_g: true` needs `kind: service` and `my_tax_class: service_8`.
- `group_g_excluded: true` needs `group_g: true`.
- `schedule_c_eligible: true` needs `kind: goods` and a `sales_*` class.
- `sg_disallowed` only on categories used in `SG`.
- Every source is an `https://` URL.

### What to include (step-11 plan §7.1, decisions Q9 and Q10)

- About 60 categories: 30 goods, 30 services.
- Every situation in the rule-sheet table needs at least one category: the four 6% services (F&B, logistics, telecoms, parking), Group G services (and the excluded employment and guard services), Schedule C raw materials, components, packaging and manufacturing aids, and all six Singapore Regulation 26/27 classes.
- Leave out categories the rule sheet doesn't settle: rental and leasing (Q10), and goods whose 5% or 10% sales-tax rate has no source in the rule sheet (Q9). Construction may be included at `service_6`.
- `sales_exempt` and `none` categories are allowed in clean cases, but the generator never plants tax on them.
- The `motor_car` and `staff_medical` classes need the invoice line's facts (whether the vehicle is a motor car under Regulation 25(1); whether the medical cost is obligatory). Where the documents don't say, the case is HAND_OVER by construction.
- `gl_role` names are free text but must match the chart-of-accounts templates (added in PR B1). Use plain roles such as `it_services`, `freight_inward`, `raw_materials`, `club_subscriptions`, `staff_welfare_medical`, `motor_vehicle_running`.
