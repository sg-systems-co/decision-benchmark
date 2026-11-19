"""Designated and special areas: MS-7 (service tax) and MG-5 (sales tax), rule sheet v0.10 as rewritten 18 Nov 2026.

Sources: Service Tax Act 2018 and Sales Tax Act 2018 s2 and Parts VIII-IX, as amended by Acts A1596/A1597 (Pangkor,
from 1 Jan 2020) and A1718/A1719 (Pulau 1, from 1 Dec 2024); P.U. (A) 212/2018 and its amendments (the services taxed
inside and between areas); P.U. (A) 370/2024 (Pulau 1); P.U. (A) 206/2018 and 207/2018 and their amendments (goods
taxed on entry, data/area_goods_lists.yaml); Service Tax Policies 1/2021 and 2/2022 (JDA); RMCD Panduan Perkhidmatan
Penginapan (V4) and Panduan Makanan dan Minuman (V7) (site-bound services).

A zone is never read off an address: the party's master gives it (None: principal customs area), a line fact names
another establishment or site, or the case doesn't settle it (HAND_OVER). Open questions Q-A2 to Q-A5 are HAND_OVER
with the question in the reason; Q-A1 lines follow the sheet and carry the question as open_question.
"""

from __future__ import annotations

from datetime import date

from ....findings import NotSettled
from .. import area_goods
from . import rates
from .context import Exempt, LineCtx

PANGKOR_FROM = date(2020, 1, 1)
PULAU_1_FROM = date(2024, 12, 1)
SUPPLY_BASE_SALES_FROM = date(2020, 1, 1)
"""A petroleum supply base is a special area for sales tax from 1 Jan 2020 (Act A1596); for service tax open (Q-A5)."""
DESIGNATED = {"labuan": None, "langkawi": None, "tioman": None, "pangkor": PANGKOR_FROM, "pulau_1": PULAU_1_FROM}
SPECIAL = ("free_zone", "licensed_warehouse", "licensed_manufacturing_warehouse", "jda")
SUPPLY_BASE = "petroleum_supply_base"
SA_LISTED_ZONES = ("free_zone", "licensed_warehouse", "licensed_manufacturing_warehouse")
JDA_EXEMPT = (date(2021, 5, 1), date(2022, 8, 14))
"""Service Tax Policy 1/2021: a jda_operator buyer is exempt on services provided within the JDA; replaced by the refund
route of Policy 2/2022 from 15 Aug 2022 (the invoice is correct as charged)."""
IN_SPECIAL_AREAS_FROM = date(2018, 9, 6)
"""Items 3 and 4: the words "in special areas" from 6 Sep 2018 (P.U. (A) 232/2018); before, all areas."""
STATE_GOVERNMENT_EXCLUDED_FROM = date(2020, 1, 1)
ITEM_6_FROM = date(2019, 9, 1)
ITEM_5_DESIGNATED_FROM = date(2025, 5, 30)
ITEM_7 = (date(2024, 3, 1), date(2025, 5, 29))
GOODS_BETWEEN_AREAS_FROM = date(2026, 1, 1)
"""MG-5 step 5: from 1 Jan 2026 the DA order's words "imported or transported into the designated area" may reach
DA-listed goods moved between two designated areas (HAND_OVER)."""
SITE_ITEMS = (3, 4, 5, 6)
"""Accommodation, food and beverages, customs clearance: provided where performed (site rule)."""


def _party_zone(known: bool, zone: str | None, basis: str, who: str) -> str:
    if not known:
        raise NotSettled(basis, f"{who} zone not shown")
    return zone or "pca"


def supplier_zone(ctx: LineCtx, basis: str) -> str:
    return _party_zone(ctx.sf.zone_known, ctx.sf.zone, basis, "supplier")


def company_zone(ctx: LineCtx, basis: str) -> str:
    return _party_zone(ctx.cf.zone_known, ctx.cf.zone, basis, "company")


def kind(zone: str, day: date, supply_base: str = "pca") -> str:
    """pca, da or sa on a day. supply_base: what a petroleum supply base counts as."""
    if zone in DESIGNATED:
        start = DESIGNATED[zone]
        return "da" if start is None or day >= start else "pca"
    if zone in SPECIAL:
        return "sa"
    if zone == SUPPLY_BASE:
        return supply_base
    return "pca"


# -- MS-7: service tax ---------------------------------------------------------------------------------------


def _licence(ctx: LineCtx, name: str) -> bool:
    if not ctx.sf.area_licences_known:
        raise NotSettled("MS-7", "supplier licences not shown")
    return name in ctx.sf.area_licences


def item_applies(ctx: LineCtx, item: int, frm: str, to: str, kf: str, kt: str, day: date) -> bool:
    """Whether item n of the Schedule to P.U. (A) 212/2018 taxes this service on this route on this day. For the
    site-bound items 3-6, frm and to are the site's zone."""
    if item in (1, 2):
        # Passenger air transport, telecommunications: between DAs, between SAs, DA to SA, SA to DA.
        return frm != to and _licence(ctx, "mavcom_air_service" if item == 1 else "cma_telecoms")
    if item == 3:
        if not (kt == "sa" or day < IN_SPECIAL_AREAS_FROM):
            return False
        return not _accommodation_excluded(ctx, day)
    if item == 4:
        if not (kt == "sa" or day < IN_SPECIAL_AREAS_FROM):
            return False
        # Excluded: a canteen in an educational institution, a canteen operated by a religious institution or body.
        return ctx.fact("canteen_kind", "none", "MS-7") == "none"
    if item == 5:
        where = kt == "sa" or (kt == "da" and to != "pulau_1" and day >= ITEM_5_DESIGNATED_FROM)
        return where and _licence(ctx, "customs_agent_s90")
    if item == 6:
        return day >= ITEM_6_FROM and kt == "sa" and _licence(ctx, "entertainment_premises")
    if item == 7:
        return ITEM_7[0] <= day <= ITEM_7[1] and ctx.fact("international_leg", "none", "MS-7") == "none"
    return False


def _accommodation_excluded(ctx: LineCtx, day: date) -> bool:
    """Item 3 exclusions (P.U. (A) 212/2018 as amended by 393/2019 and 337/2026; sheet, "How the table reads").
    Local authority: every date. From 1 Jan 2020: Federal or State Government, statutory body, private HEI premises,
    and premises an employer provides to its own employees. Before 1 Jan 2020: Federal Government, statutory body and
    private HEI premises only when provided for educational, training or welfare purposes (State Government not
    excluded then, so a Federal-or-State supplier with that purpose is HAND_OVER). A registered religious or welfare
    body: premises used for religious or welfare activities and not commercially. For these supplier kinds the purpose
    or use has no ordinary value: not shown is HAND_OVER."""
    supplier = ctx.sf.supplier_kind
    if supplier == "local_authority":
        return True
    if supplier == "religious_welfare_body" and ctx.need("non_commercial_religious_welfare", "MS-7"):
        return True
    public = supplier in ("federal_state_government", "statutory_body", "private_hei")
    if day >= STATE_GOVERNMENT_EXCLUDED_FROM:
        return public or bool(ctx.fact("employer_staff_accommodation", False, "MS-7"))
    if public and ctx.need("educational_training_welfare_purpose", "MS-7"):
        if supplier == "federal_state_government":
            raise NotSettled("MS-7", "Federal or State Government premises before 1 Jan 2020 not shown")
        return True
    return False


def _service_exempt(ctx: LineCtx, frm: str, to: str, day: date, supply_base: str) -> bool:
    kf, kt = kind(frm, day, supply_base), kind(to, day, supply_base)
    if kf == "pca" and kt == "pca":
        return False                                         # step 1
    if kf == "pca":                                          # step 2: taxed (ss50, 55), except the JDA window
        return (to == "jda" and "jda_operator" in ctx.cf.buyer_kinds and JDA_EXEMPT[0] <= day <= JDA_EXEMPT[1])
    if kt == "pca":
        return False                                         # step 3: taxed (ss49, 54)
    # Step 4: both zones in areas. Pulau 1: every taxable service within it, or between it and another area.
    if "pulau_1" in (frm, to) and day >= PULAU_1_FROM:
        return False
    return not any(item_applies(ctx, n, frm, to, kf, kt, day) for n in ctx.profile.area_items)


def _service_on(ctx: LineCtx, frm: str, to: str, day: date) -> bool:
    if SUPPLY_BASE in (frm, to):
        as_sa, as_pca = (_service_exempt(ctx, frm, to, day, s) for s in ("sa", "pca"))
        if as_sa != as_pca:
            raise NotSettled("MS-7", "Q-A5: whether a petroleum supply base is a special area for service tax")
        return as_sa
    return _service_exempt(ctx, frm, to, day, "pca")


def service_check(ctx: LineCtx) -> Exempt | None:
    """MS-7 for a taxable service from a domestic supplier: Exempt (no tax due) or None (taxed as normal)."""
    if ctx.foreign_supplier:
        return None
    site = ctx.fact("service_site_zone", None, "MS-7")
    if site is not None or set(ctx.profile.area_items) & set(SITE_ITEMS):
        frm = to = site if site is not None else supplier_zone(ctx, "MS-7")
    else:
        frm = supplier_zone(ctx, "MS-7")
        to = ctx.fact("recipient_zone", company_zone(ctx, "MS-7"), "MS-7")
    if frm == "pca" and to == "pca":
        return None
    span = rates.period(ctx)
    days = [span[0], span[1]] if span else [ctx.day]
    results = {_service_on(ctx, frm, to, d) for d in days}
    if len(results) > 1:
        raise NotSettled("MS-7", "service period spans an area order date and no split is shown")
    return Exempt("MS-7") if results.pop() else None


# -- MG-5: sales tax -----------------------------------------------------------------------------------------


def _vehicle_rows_match(ctx: LineCtx, row) -> bool | None:
    if row.headings:
        tariff = ctx.fact("tariff_code", None, "MG-5")
        if tariff is None:
            return None
        if area_goods.heading_of(tariff) not in row.headings:
            return False
    value = ctx.fact("motor_vehicle_value", None, "MG-5")
    basis = ctx.fact("motor_vehicle_value_basis", None, "MG-5")
    return area_goods.value_over(row, value, basis)


def listed_da(ctx: LineCtx, zone: str, day: date) -> bool | None:
    """The DA order taxes these goods into this designated area on this day; None: the documents don't settle it."""
    kinds = ctx.profile.area_goods
    unknown = False
    for row in area_goods.rows("da", zone, day):
        if not area_goods.names(kinds, row):
            continue
        match = _vehicle_rows_match(ctx, row) if row.value_above is not None else True
        if match:
            return True
        unknown = unknown or match is None
    return None if unknown else False


def listed_sa(ctx: LineCtx, zone: str, day: date) -> bool:
    """The SA order taxes these goods into this free zone, licensed warehouse or LMW on this day."""
    if zone not in SA_LISTED_ZONES:
        return False
    for row in area_goods.rows("sa", zone, day):
        if row.tasik_kenyir and not ctx.cf.tasik_kenyir:
            continue
        if row.not_used_directly:
            if not ctx.fact("used_directly_in_approved_activity", True, "MG-5"):
                return True
            continue
        if area_goods.names(ctx.profile.area_goods, row):
            return True
    return False


def goods_check(ctx: LineCtx) -> Exempt | None:
    """MG-5 for goods sold by a registered manufacturer that made them (after MG-1, MG-2)."""
    if ctx.foreign_supplier:
        return None
    day = ctx.day
    frm = supplier_zone(ctx, "MG-5")
    to = ctx.fact("delivery_zone", company_zone(ctx, "MG-5"), "MG-5")
    kf, kt = kind(frm, day, "sa" if day >= SUPPLY_BASE_SALES_FROM else "pca"), \
        kind(to, day, "sa" if day >= SUPPLY_BASE_SALES_FROM else "pca")
    if kf == "pca" and kt == "pca":
        return None                                                           # step 1
    if (frm == "pulau_1" and kf == "da") or (to == "pulau_1" and kt == "da"):  # step 6
        if frm == to == "pulau_1":
            if any(area_goods.names(ctx.profile.area_goods, r) for r in area_goods.rows("pulau_1_not_taxed", "pulau_1", day)):
                raise NotSettled("MG-5", "Q-A4: listed goods made in Pulau 1 (no s49(2) order found)")
            return None
        raise NotSettled("MG-5", "Q-A4: goods transported into or out of Pulau 1")
    if kf == "pca":                                                           # step 2
        if kt == "da":
            listed = listed_da(ctx, to, day)
            return Exempt("MG-5", open_question="Q-A1" if listed is not False else None)
        if listed_sa(ctx, to, day):
            raise NotSettled("MG-5", "Q-A2: goods the SA order taxes on entry, from a principal customs area manufacturer")
        return Exempt("MG-5")
    if kf == "da":                                                            # steps 3 and 5
        if kt == "da" and frm != to and day >= GOODS_BETWEEN_AREAS_FROM and listed_da(ctx, to, day) is not False:
            raise NotSettled("MG-5", "DA-listed goods moved between two designated areas")
        if "petroleum" in ctx.profile.area_goods:
            return None
        return Exempt("MG-5")
    if kt == "pca":                                                           # step 4, from a special area
        if frm == "jda":
            return Exempt("MG-5")
        if ctx.charged:
            raise NotSettled("MG-5", "Q-A3: tax shown on an invoice from a special area to the principal customs area")
        return Exempt("MG-5")
    return Exempt("MG-5")
