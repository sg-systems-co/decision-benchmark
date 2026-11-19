"""Malaysian types: SST codes, category tax profile, MyInvois block, party tax facts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ...models.common import CountryBlock, Model, Money, Num, TaxProfile, internal
from ...models.evidence import LineFact, LineFacts, Share, fact_field


class MyTaxTreatment(StrEnum):
    """The codes of $defs/tax_code in schemas/ap-invoices/v0.10/countries/my.schema.json."""

    SST_CORRECT = "SST_CORRECT"
    SST_WRONG_RATE = "SST_WRONG_RATE"
    SST_SHOULD_BE_EXEMPT = "SST_SHOULD_BE_EXEMPT"
    SST_SUPPLIER_NOT_REGISTERED = "SST_SUPPLIER_NOT_REGISTERED"
    NO_SST = "NO_SST"
    SST_NOT_CHARGEABLE_BY_TRADER = "SST_NOT_CHARGEABLE_BY_TRADER"
    SST_UNDERCHARGED = "SST_UNDERCHARGED"
    SST_BUYER_ACCOUNTS = "SST_BUYER_ACCOUNTS"


MyTaxClass = Literal["sales_5", "sales_10", "sales_exempt", "service_8", "service_6", "none"]
MyTaxType = Literal["01", "02", "03", "04", "05", "06", "E"]
ServiceItem = Annotated[str, Field(pattern=r"^[A-Z]([0-9]+)?(\([a-z]\))?$")]
"""An item in the First Schedule, Service Tax Regulations 2018: group letter, item number, item letter.
Examples: "G(a)", "G(h)", "J1(a)", "I8", "L"."""


class MyTaxProfile(TaxProfile):
    tax_class: MyTaxClass
    schedule_c_eligible: bool = False
    service_item: ServiceItem | None = None
    """First Schedule item of a taxable service. Required for service_6 and service_8, null otherwise."""
    b2b_exempt: bool = False
    """The item is in a B2B exemption scheme (Group G except items (j) and (k), Group J same item,
    Group I item 8, Group L): exempt when both parties are registered, the buyer provides the same
    item, and the service is not for personal use."""
    group_relief: bool = False
    """Group G items (a) to (i), (l) and (n) only (constants.GROUP_RELIEF_ITEMS)."""
    area_items: list[Literal[1, 2, 3, 4, 5, 6, 7]] = []
    """Items of the Schedule to P.U. (A) 212/2018 the service falls under: services taxed inside and between areas (MS-7)."""
    area_goods: list[AreaGoods] = []
    """Kinds of goods the area orders name (MG-5); the lists, zones and dates are in data/area_goods_lists.yaml."""


class MyInvoisLine(Model):
    line_no: int
    classification_code: str | None = None
    tax_type: MyTaxType | None = None
    tax_exemption_reason: str | None = None


class MyInvois(CountryBlock):
    """MyInvois-style fields. is_einvoice False: an ordinary invoice from a supplier below the threshold."""

    country: Literal["MY"] = "MY"
    is_einvoice: bool
    einvoice_version: str | None = None
    einvoice_type_code: str | None = None
    uuid: str | None = None
    validation_datetime: str | None = None
    supplier_tin: str | None = None
    supplier_brn: str | None = None
    supplier_sst_no: str | None = None
    supplier_msic_code: str | None = None
    buyer_tin: str | None = None
    buyer_brn: str | None = None
    buyer_sst_no: str | None = None
    tax_total_by_type: dict[str, Money] | None = None
    lines: list[MyInvoisLine] = []


MyZone = Literal["labuan", "langkawi", "tioman", "pangkor", "pulau_1", "free_zone", "licensed_warehouse",
                 "licensed_manufacturing_warehouse", "jda", "petroleum_supply_base"]
"""Designated areas (Labuan, Langkawi, Tioman, Pangkor from 1 Jan 2020, Pulau 1 from 1 Dec 2024) and special areas
(free zones, licensed warehouses, LMWs, the JDA; a petroleum supply base for sales tax from 1 Jan 2020) (MS-7, MG-5).
None: principal customs area."""
LineZone = Literal["pca", "labuan", "langkawi", "tioman", "pangkor", "pulau_1", "free_zone", "licensed_warehouse",
                   "licensed_manufacturing_warehouse", "jda", "petroleum_supply_base"]
"""A zone as a line fact names it: pca is the principal customs area."""
AreaGoods = Literal["alcohol", "tobacco", "smoking_pipes", "e_cigarette", "e_liquid_no_nicotine", "e_liquid_nicotine",
                    "petroleum", "marble", "anchovies", "motor_vehicle", "forklift", "crane", "office_equipment_furniture",
                    "firefighting_pollution_control", "tyres", "chemicals", "air_conditioning", "manufacturing_aid",
                    "chocolate", "cosmetics_perfume"]
"""Kinds of goods the designated-area and special-area sales tax orders name (data/area_goods_lists.yaml)."""

SalesBand = Literal["below_1m", "1m_to_1_5m", "above_1_5m"]
"""Annual sales declared to LHDN for the latest year of assessment, in RM (K-1)."""


class MsmeStatus(Model):
    """The company as a tenant under the SME rental exemptions (K-1, K-2). None: the records don't show it."""

    mypmk_registered_on: date | None = None
    """When the company registered and declared MSME status in RMCD's MyPMK system; None: not registered or not shown."""
    mypmk_status_known: bool = True
    declared_sales_band: SalesBand | None = None
    year_of_assessment: int | None = Field(default=None, ge=2000, le=2100)
    paid_up_capital: Money | None = None
    group_holding_pct: Num | None = Field(default=None, ge=0, le=100)
    """If set up by a company in a group: that company's holding, in percent."""
    ssm_registered_on: date | None = None


class Shareholding(Model):
    holder_id: str = Field(min_length=1)
    held_id: str = Field(min_length=1)
    holder_kind: Literal["company", "individual"] = "company"
    """Only companies form a group (First Schedule para 4): sisters owned by one individual are not a group."""
    pct: Num = Field(ge=0, le=100)
    board_control: bool | None = None
    """Power over the board (counts with a 20-50% holding, First Schedule paras 4-7). None: not shown."""
    nominee: bool = False
    """Held as nominee or fiduciary: does not count."""

    @model_validator(mode="after")
    def _distinct(self) -> Shareholding:
        if self.holder_id == self.held_id:
            raise ValueError("a company does not hold itself")
        return self


class GroupStructure(Model):
    """Shareholdings among the buying company and its group (MS-6, K-6). Company and supplier ids."""

    shareholdings: list[Shareholding] = []

    @model_validator(mode="after")
    def _unique(self) -> GroupStructure:
        pairs = [(s.holder_id, s.held_id) for s in self.shareholdings]
        if len(pairs) != len(set(pairs)):
            raise ValueError("one shareholding per holder and held company")
        return self


BuyerKind = Literal["aoc_airline", "registered_ship_owner", "government_department", "foreign_company", "jda_operator"]
"""Buyer kinds the rules name: P-9 (MRO of aircraft and ships); jda_operator, the MTJA or a company operating in the
JDA (MS-7, Service Tax Policy 1/2021)."""


class MyCompanyFacts(CountryBlock):
    country: Literal["MY"] = "MY"
    is_registered_manufacturer: bool = False
    services_provided: list[ServiceItem] = []
    """First Schedule service items the company itself provides (B2B exemption test), e.g. "G(h)"."""
    group_companies: list[str] = []
    msme: MsmeStatus | None = None
    group: GroupStructure | None = None
    zone: MyZone | None = None
    zone_known: bool = True
    einvoice_phase_start: date | None = None
    """When the company's mandatory e-invoicing phase starts (ME-3 self-billing). None: not in a mandatory phase."""
    einvoice_phase_known: bool = True
    """False: the case can't show the company's e-invoicing phase (ME-3)."""
    industrial_undertaking: bool = False
    """An enterprise in an industrial undertaking (LHDN DTA note iv on 15/10 interest rows)."""
    labuan_fsa_regulated: bool = False
    buyer_kinds: list[BuyerKind] = []
    tasik_kenyir: bool = False
    """The company's free zone is the Tasik Kenyir Duty Free Area (MG-5, P.U. (A) 207/2018)."""


SupplierKind = Literal["company", "federal_state_government", "local_authority", "developer_jmb_mc",
                       "approved_rnd_company", "research_institute", "statutory_body", "private_hei",
                       "religious_welfare_body"]
"""private_hei: a private higher educational institution registered under Act 555 (MS-7 item 3)."""


class MySupplierFacts(CountryBlock):
    country: Literal["MY"] = "MY"
    is_manufacturer: bool = False
    turnover_band: str | None = None
    service_categories: list[str] = []
    msic_code: str | None = None
    registration_known: bool = True
    """False: the case can't show whether the supplier is registered for SST (MS-1, MG-1)."""
    supplier_kind: SupplierKind = "company"
    group_company_id: str | None = None
    """The supplier's id in the buyer's group structure, if it is a group company."""
    external_share_within_5pct: bool | None = None
    """The supplier's supplies of the service to outsiders stay within 5% (First Schedule para 8(2)). None: not shown."""
    is_foreign_registered_person: bool = False
    frp_supplies_outsiders_in_my: bool | None = None
    pe_in_country: bool | None = None
    """A permanent establishment or business presence in Malaysia (WH-3). None: not shown."""
    einvoice_phase_start: date | None = None
    """When the supplier's mandatory e-invoicing phase starts (ME-1). None: not in a mandatory phase (for example
    annual turnover below RM3m)."""
    einvoice_phase_known: bool = True
    """False: the case can't show the supplier's e-invoicing phase (ME-1)."""
    approvals: list[Literal["caam_amo", "mida_shipyard", "dgta_amo"]] = []
    recognised_training_centre: bool = False
    zone: MyZone | None = None
    """The zone of the supplier's principal place of business (MS-7, MG-5). None: principal customs area."""
    zone_known: bool = True
    area_licences: list[Literal["mavcom_air_service", "cma_telecoms", "customs_agent_s90", "entertainment_premises"]] = []
    """Licences and approvals items 1, 2, 5 and 6 of P.U. (A) 212/2018 name (MS-7)."""
    area_licences_known: bool = True
    """False: the case can't show the supplier's licences (HAND_OVER where one decides the line)."""
    # Generator truth.
    # Do not add a clear "same group" value without its rule (Service Tax Policy 8/2020, group
    # relief) in tax.py and tests in the same PR. tax.py handles every value explicitly;
    # tests/rules/test_tax_my_scope.py fails if this Literal gains a value it doesn't handle.
    group_relation: Literal["unrelated", "unclear"] = internal("unrelated")
    """unclear: the documents don't show whether the supplier is in the buyer's group (group relief)."""


class MyContractFacts(CountryBlock):
    """Contract facts only Malaysian rules read (L-2, L-3)."""

    country: Literal["MY"] = "MY"
    mixed_development_stated: bool | None = None
    design_and_build: bool | None = None
    planning_permission_no: str | None = None


class MyLineFacts(LineFacts):
    """Malaysia line facts: exactly the fields of $defs/line_facts in schemas/ap-invoices/v0.10/countries/my.schema.json
    (names, value types, families, rules; tests/models/test_line_facts.py checks it)."""

    service_item: LineFact[Annotated[str, StringConstraints(pattern=r"^[A-M]([0-9]+)?(\([a-z]\))?$")]] | None = fact_field("classification", "MS-4", "MS-5", "MS-6")
    tariff_code: LineFact[Annotated[str, StringConstraints(pattern=r"^\d{4}(\.\d{2}){0,2}( \d{2})?$")]] | None = fact_field("classification", "MG-2", "MG-6")
    fb_content: LineFact[Literal["food", "non_alcoholic_drink", "food_with_alcohol", "alcohol_alone", "corkage", "tobacco", "other"]] | None = fact_field("classification", "MS-2", "MS-4")
    financial_charge: LineFact[Literal["fee_or_commission", "interest_or_profit", "penalty", "basic_banking", "insurance_premium", "reinsurance", "card_activation", "bursa_share_brokerage", "bursa_clearing_trading_fee", "listing_perusal_fee", "shariah_structure_fee", "asnb_fund_management", "government_securities_fee", "commodity_platform_fee", "tia_i_account_fee"]] | None = fact_field("classification", "MS-4", "P-1", "P-3", "P-5", "P-6", "P-2", "P-4", "P-7")
    asset_type: LineFact[Literal["housing", "reading_material", "aircraft", "drone", "vessel", "floating_storage", "vehicle", "machinery", "commercial_premises", "other"]] | None = fact_field("classification", "MS-4", "K-3")
    education_fee_item: LineFact[Literal["tuition", "books", "uniform", "food", "transport", "accommodation", "refundable_deposit", "pta_fee", "trip", "student_pass"]] | None = fact_field("classification", "MS-4", "P-16")
    service_period_start: LineFact[date] | None = fact_field("time_and_rate", "MS-3")
    service_period_end: LineFact[date] | None = fact_field("time_and_rate", "MS-3")
    amount_paid_before_change: LineFact[Money] | None = fact_field("time_and_rate", "MS-3")
    delivery_date: LineFact[date] | None = fact_field("time_and_rate", "MG-3")
    subject_outside_malaysia: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4")
    statutory_fee_amount: LineFact[Money] | None = fact_field("scope_and_exemption", "MS-4")
    residential: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4", "L-5", "P-11")
    asset_in_malaysia: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4", "K-7")
    financial_lease: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4")
    air_route: LineFact[Literal["within_peninsula", "peninsula_east_malaysia", "between_sabah_sarawak", "within_sabah", "within_sarawak", "rural_air_service", "international"]] | None = fact_field("scope_and_exemption", "MS-4")
    carriage: LineFact[Literal["domestic", "outside_to_outside", "last_exit_to_outside", "outside_to_first_entry", "transshipment", "to_licensed_warehouse", "door_to_door_international", "ocean_peninsula_east_malaysia"]] | None = fact_field("scope_and_exemption", "MS-4", "P-18")
    patient_citizen: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4", "P-13")
    student_citizen: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4")
    oku_holder: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4", "P-17")
    mro_aircraft_ship: LineFact[bool] | None = fact_field("scope_and_exemption", "P-9")
    building_charge: LineFact[Literal["maintenance", "sinking_fund", "warranty_repair", "none"]] | None = fact_field("scope_and_exemption", "P-10", "P-11")
    personal_use: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-5")
    same_service_as_buyer: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-5", "MS-8")
    sublet: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-5")
    sublet_share: LineFact[Share] | None = fact_field("buyer_and_purpose", "MS-5")
    supplier_paid: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-8")
    materials_works_separated: LineFact[bool] | None = fact_field("split", "L-8")
    installation_separated: LineFact[bool] | None = fact_field("split", "L-8")
    itemised_consultation_fee: LineFact[bool] | None = fact_field("split", "P-12")
    package_single_price: LineFact[bool] | None = fact_field("split", "MS-2")
    contract_signed: LineFact[date] | None = fact_field("contract", "K-4", "L-1")
    contract_stamped: LineFact[date] | None = fact_field("contract", "K-4", "L-1")
    price_review_clause: LineFact[bool] | None = fact_field("contract", "K-4", "L-1")
    residential_share: LineFact[Share] | None = fact_field("contract", "L-2")
    design_and_build: LineFact[bool] | None = fact_field("contract", "L-3")
    place_of_worship: LineFact[bool] | None = fact_field("contract", "L-4")
    client_established_in_malaysia: LineFact[bool] | None = fact_field("contract", "L-6")
    exemption_statement_on_invoice: LineFact[bool] | None = fact_field("contract", "L-3", "L-6")
    payment_nature: LineFact[Literal["interest", "royalty", "services_on_property", "technical_advice", "movable_property_rent", "contract_payment", "other_gain", "public_entertainer", "freight", "none"]] | None = fact_field("withholding", "WH-1", "WH-2", "WH-3", "WH-4")
    place_of_performance: LineFact[Literal["in_country", "outside", "mixed"]] | None = fact_field("withholding", "WH-2")
    in_country_share: LineFact[Share] | None = fact_field("withholding", "WH-2")
    hotel_reimbursement: LineFact[Money] | None = fact_field("withholding", "WH-2")
    certificate_of_residence: LineFact[bool] | None = fact_field("withholding", "WH-1", "WH-2", "WH-4")
    manufactured_by_supplier: LineFact[bool] | None = fact_field("classification", "MG-1")
    export_related: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4", "P-1")
    insurance_cover: LineFact[Literal["international_transport", "export_credit", "risk_outside_malaysia", "educational_or_religious_insured", "other"]] | None = fact_field("classification", "MS-4")
    premises_use: LineFact[Literal["commercial", "industrial", "residential", "religious", "educational", "agricultural"]] | None = fact_field("scope_and_exemption", "MS-4")
    service_sub_item: LineFact[Annotated[str, StringConstraints(pattern=r"^\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\)$")]] | None = fact_field("classification", "MS-6")
    own_use: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-5")
    variation_signed: LineFact[date] | None = fact_field("contract", "L-1")
    variation_stamped: LineFact[date] | None = fact_field("contract", "L-1")
    variation_changes_value: LineFact[bool] | None = fact_field("contract", "L-1")
    mixed_development_stated: LineFact[bool] | None = fact_field("contract", "L-2")
    ship_platform_election: LineFact[Literal["manufacturing", "construction"]] | None = fact_field("contract", "L-8")
    annual_fee_per_student: LineFact[Money] | None = fact_field("scope_and_exemption", "MS-4")
    financial_use: LineFact[Literal["taxable_financial_services", "offshore_financial_services", "export_related_financial_services", "medical_life_family_cover", "other"]] | None = fact_field("buyer_and_purpose", "P-1", "P-6")
    patient_category: LineFact[Literal["citizen", "non_citizen", "foreign_worker_screening", "diplomat_with_mofa_letter", "newborn_with_citizen_parent"]] | None = fact_field("scope_and_exemption", "P-13")
    medical_aid: LineFact[bool] | None = fact_field("scope_and_exemption", "P-14")
    referral_walk_in: LineFact[bool] | None = fact_field("scope_and_exemption", "P-14")
    fully_sponsored: LineFact[bool] | None = fact_field("scope_and_exemption", "P-16")
    student_category: LineFact[Literal["citizen", "non_citizen", "disabled_citizen", "diplomat_child"]] | None = fact_field("scope_and_exemption", "MS-4", "P-16")
    digital_content_type: LineFact[Literal["online_distance_learning", "e_newspaper_journal_periodical", "other"]] | None = fact_field("classification", "P-19")
    pallet_returnable: LineFact[bool] | None = fact_field("classification", "G-4")
    drop_shipment_export: LineFact[bool] | None = fact_field("scope_and_exemption", "G-5")
    self_billing_type: LineFact[Literal[
        "agents_dealers_distributors", "foreign_supplier", "profit_distribution", "ecommerce", "betting_gaming_payout",
        "individual_not_in_business", "interest_payment", "insurance_claim_payment", "capital_return_or_liquidation", "none",
    ]] | None = fact_field("classification", "ME-3")
    interest_exception: LineFact[Literal[
        "public_lender", "employee_to_employer", "foreign_payor", "related_company_treasury", "late_payment_charge", "none",
    ]] | None = fact_field("classification", "ME-3")
    staff_secondment: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-4")
    excluded_management_kind: LineFact[Literal["strata_management_to_owners", "cmsa_fund_management", "religious_welfare_body", "health_examination_management", "none"]] | None = fact_field("scope_and_exemption", "MS-4", "P-15")
    value_provided_before_change: LineFact[Money] | None = fact_field("split", "MS-3")
    completed_building: LineFact[bool] | None = fact_field("scope_and_exemption", "L-5")
    digital_payment_provider: LineFact[Literal["bank", "non_bank", "none"]] | None = fact_field("classification", "P-20")
    education_provider_kind: LineFact[Literal["private_school", "higher_education", "language_centre"]] | None = fact_field("classification", "MS-4")
    recipient_zone: LineFact[LineZone] | None = fact_field("scope_and_exemption", "MS-7")
    service_site_zone: LineFact[LineZone] | None = fact_field("scope_and_exemption", "MS-7")
    delivery_zone: LineFact[LineZone] | None = fact_field("scope_and_exemption", "MG-5")
    international_leg: LineFact[Literal["outside_to_outside", "last_exit_to_outside", "outside_to_first_entry", "transshipment", "to_customs_warehouse", "none"]] | None = fact_field("scope_and_exemption", "MS-7")
    used_directly_in_approved_activity: LineFact[bool] | None = fact_field("buyer_and_purpose", "MG-5")
    motor_vehicle_value: LineFact[Money] | None = fact_field("classification", "MG-5")
    motor_vehicle_value_basis: LineFact[Literal["cif", "sales_price"]] | None = fact_field("classification", "MG-5")
    employer_staff_accommodation: LineFact[bool] | None = fact_field("scope_and_exemption", "MS-7")
    educational_training_welfare_purpose: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-7")
    non_commercial_religious_welfare: LineFact[bool] | None = fact_field("buyer_and_purpose", "MS-7")
    canteen_kind: LineFact[Literal["educational_institution", "religious_body", "none"]] | None = fact_field("scope_and_exemption", "MS-7")
