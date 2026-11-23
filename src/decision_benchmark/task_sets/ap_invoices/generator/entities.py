"""Entities (B1-2): the buying companies of a split with their people, policy pack, suppliers, contracts, certificates,
ledger history and background mail. Country neutral: registrations, party facts and the clean line come from the
country pack's generation part; names come from content/names/<country>.yaml.

Each company is built from its own derived seed. Splits are disjoint by construction: the name combinations and the
identifiers are partitioned three ways (``partition``), train, test and every other split, so no company, supplier or
person name, tax id, registration number or bank account can appear in two splits. A name belongs to the partition of
its text (``name_partition``: sha256 of the name, mod 3), so the rule holds across countries and name banks; every
generated identifier ends in a digit whose value mod 3 is the partition.

Company names are distinct across a split; supplier and person names within a company. A supplier name drawn again at
another company of the split is the same supplier: it keeps the identity first drawn for it (registrations, registration
number, bank account, address, contact, categories), so a shared name never carries two tax ids.

Each company has a kind (the pack's ``company_kinds`` in turn) and, besides its ordinary suppliers, one supplier of each
special kind the rules need (the pack's ``special_suppliers``: a government agency, a group company, a landlord under a
transitional contract, a foreign supplier with a permanent establishment ...). The clean base uses the ordinary
suppliers and the 'general' one; the rule recipes pick the special ones.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import cache

import yaml

from decision_benchmark.core.generator.seeds import rng
from decision_benchmark.core.model import CENT
from decision_benchmark.core.generator.spec import Generation, SplitSpec

from ..countries import pack
from ..models import Catalog, Category, load_catalog
from ..spec import CONTENT
from .country import SpecialSupplier

SUPPLIERS = (15, 30)
PEOPLE = (4, 8)
FOREIGN_SUPPLIER_SHARE = Decimal("0.15")
"""Foreign suppliers in each company's master (B1-4 and B1-5 plant their lines)."""
HISTORY_GAP_DAYS = (45, 120)
HISTORY_LEAD_DAYS = 365
"""Background history starts 12 months before the window (B1 plan section 6)."""
BACKGROUND_MAIL = (4, 10)
APPROVAL = (("ops_manager", Decimal("20000.00")), ("director", Decimal("200000.00")))
GENERAL = "general"
"""The special supplier kind the clean base may also use: registered for goods and services, a manufacturer."""
PARTITIONS = {"train": 0, "test": 1}
"""The release splits' partitions; every other split (a private one) uses partition 2."""
N_PARTITIONS = 3
GOODS_PRICE = (Decimal("5"), Decimal("400"))
SERVICE_PRICE = (Decimal("150"), Decimal("4000"))


@cache
def catalog() -> Catalog:
    return load_catalog(CONTENT / "catalog" / "categories.yaml")


@cache
def names(country: str) -> dict:
    return yaml.safe_load((CONTENT / "names" / f"{country}.yaml").read_text(encoding="utf-8"))


def money(value: Decimal) -> str:
    return f"{value.quantize(CENT, ROUND_HALF_UP):.2f}"


def price(r: random.Random, kind: str) -> Decimal:
    lo, hi = GOODS_PRICE if kind == "goods" else SERVICE_PRICE
    return (lo + (hi - lo) * Decimal(r.randrange(10_000)) / 10_000).quantize(CENT, ROUND_HALF_UP)


def tax_of(net: Decimal, rate: Decimal) -> Decimal:
    return (net * rate / 100).quantize(CENT, ROUND_HALF_UP)


def day_between(r: random.Random, lo: date, hi: date) -> date:
    return lo + timedelta(days=r.randrange((hi - lo).days + 1))


@dataclass
class CompanyWorld:
    """One buying company and what its systems hold, as JSON-ready dicts (validated when a case is built)."""

    country: str
    company: dict
    suppliers: list[dict]
    categories: dict[str, list[str]]
    """supplier_id -> the categories it sells."""
    ledger: list[dict] = field(default_factory=list)
    emails: list[dict] = field(default_factory=list)
    contracts: list[dict] = field(default_factory=list)
    residence_certificates: list[dict] = field(default_factory=list)
    account_for_role: dict[str, str] = field(default_factory=dict)
    kind: str = ""
    """The company's kind (rules.yaml ``companies``)."""
    special: dict[str, str] = field(default_factory=dict)
    """Special supplier kind -> supplier_id."""

    @property
    def company_id(self) -> str:
        return self.company["company_id"]

    def records(self) -> dict:
        """The company records shared by all its cases (each case adds its own PO and receipt)."""
        return {"company": self.company, "suppliers": self.suppliers, "purchase_orders": [], "goods_receipts": [],
                "ledger": self.ledger, "emails": self.emails, "contracts": self.contracts,
                "residence_certificates": self.residence_certificates}

    def domestic_suppliers(self) -> list[dict]:
        return [s for s in self.suppliers if s["country"] == self.country]

    def ordinary_suppliers(self) -> list[dict]:
        """The domestic suppliers the clean base draws from: the ordinary ones and the general special one."""
        special = {sid for k, sid in self.special.items() if k != GENERAL}
        return [s for s in self.domestic_suppliers() if s["supplier_id"] not in special]

    def supplier(self, supplier_id: str) -> dict:
        return next(s for s in self.suppliers if s["supplier_id"] == supplier_id)

    def kind_of(self, supplier_id: str) -> str:
        return next((k for k, sid in self.special.items() if sid == supplier_id), "")

    def certificate_categories(self, day: date) -> set[str]:
        out: set[str] = set()
        for cert in self.company["policy_pack"]["exemption_certificates"]:
            if date.fromisoformat(cert["valid_from"]) <= day and (
                    cert.get("valid_to") is None or day <= date.fromisoformat(cert["valid_to"])):
                out |= set(cert["categories"])
        return out


def partition(split: SplitSpec) -> int:
    return PARTITIONS.get(split.name, N_PARTITIONS - 1)


def name_partition(text: str) -> int:
    """The partition a name belongs to, from its text alone."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big") % N_PARTITIONS


class Ids:
    """Identifiers of one split: digit strings unique in the split whose last digit is the split's partition mod 3."""

    def __init__(self, part: int, r: random.Random) -> None:
        self.part, self.r = part, r
        self.used: set[str] = set()

    def digits(self, n: int) -> str:
        for _ in range(10_000):
            text = f"{self.r.randrange(10 ** n):0{n}d}"
            if int(text[-1]) % N_PARTITIONS == self.part and text not in self.used:
                self.used.add(text)
                return text
        raise ValueError("identifier space exhausted")

    def account(self) -> str:
        d = self.digits(12)
        return f"{d[:4]} {d[4:8]} {d[8:]}"


class _Names:
    """Distinct name combinations for one split and country."""

    def __init__(self, country: str, partition: int, r: random.Random) -> None:
        self.bank = names(country)
        self.partition, self.r = partition, r
        self.used: set[str] = set()
        """Company names: distinct across the split."""
        self.local: set[str] = set()
        """Supplier and person names: distinct within one company (reset per company)."""

    def new_company(self) -> None:
        self.local = set()

    def _pick(self, *pools: list[str], local: bool = False) -> str:
        used = self.local if local else self.used
        for _ in range(10_000):
            text = " ".join(self.r.choice(p) for p in pools)
            if name_partition(text) != self.partition:
                continue
            if text not in used:
                used.add(text)
                return text
        raise ValueError("name banks exhausted")

    def company(self) -> str:
        b = self.bank
        return f"{self._pick(b['company_first'], b['company_second'], b['company_third'])} {b['suffix']}"

    def supplier(self) -> str:
        b = self.bank
        return f"{self._pick(b['supplier_first'], b['supplier_second'], local=True)} {b['suffix']}"

    def person(self) -> str:
        b = self.bank
        return self._pick(b["given"], b["family"], local=True)


def _address(r: random.Random, bank: dict, country: str) -> dict:
    out = {"lines": [f"{r.randrange(1, 99)}, {r.choice(bank['streets'])}"], "city": r.choice(bank["cities"]),
           "postcode": pack(country).generation.postcode(r), "country": country}
    if bank["states"]:
        out["state"] = r.choice(bank["states"])
    return out


def _slug(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())[:16]


def country_categories(country: str) -> list[Category]:
    return [c for c in catalog().categories if country in c.countries]


def build_world(gen: Generation, split: SplitSpec) -> dict[str, list[CompanyWorld]]:
    """The buying companies of a split, half per country (B1 plan decision 3: 60 / 20 / 12)."""
    total = gen.companies_for(split.n_cases)
    per_country = {c: total // len(gen.countries) + (i < total % len(gen.countries))
                   for i, c in enumerate(gen.countries)}
    part = partition(split)
    ids = Ids(part, rng(split.seed, "ids"))
    world: dict[str, list[CompanyWorld]] = {}
    for country, n in per_country.items():
        namer = _Names(country, part, rng(split.seed, "names", country))
        known: dict[str, dict] = {}
        world[country] = [_company(gen, split, country, k, namer, ids, known) for k in range(n)]
    return world


def _company(gen: Generation, split: SplitSpec, country: str, k: int, namer: _Names, ids: Ids,
             known: dict[str, dict]) -> CompanyWorld:
    r = rng(split.seed, "company", country, k)
    g = pack(country).generation
    bank = names(country)
    lo, hi = gen.windows[country]
    cid = f"{country.lower()}-co-{k + 1:03d}"
    legal = namer.company()
    namer.new_company()
    domain = f"{_slug(legal)}.example"
    people = []
    roles = ["requester", "manager", "director", "finance_manager", "ap_clerk", "procurement", "stores", "requester"]
    for i in range(r.randint(*PEOPLE)):
        name = namer.person()
        person = {"person_id": f"{cid}-p{i + 1}", "name": name, "role": roles[i],
                  "email": f"{_slug(name)}{i + 1}@{domain}"}
        if roles[i] == "manager":
            person["approval_role"] = "ops_manager"
        if roles[i] == "director":
            person["approval_role"] = "director"
        people.append(person)
    gl_roles = sorted({c.gl_role for c in catalog().categories})
    accounts = {role: f"{5000 + 10 * i:04d}-{r.randrange(100, 999)}" for i, role in enumerate(gl_roles)}
    currency = g.currency
    policy = {
        "tolerance_policy": {"price_tolerance_pct": "2.0", "rounding_tolerance": "0.05", "duplicate_window_days": 90},
        "approval_matrix": [{"approval_role": role, "limit": money(limit), "currency": currency}
                            for role, limit in APPROVAL],
        "non_po_policy": {"allowed_categories": [], "max_amount": "0.00"},
        "chart_of_accounts": [{"code": code, "name": role.replace("_", " ").title(), "type": "expense", "role": role}
                              for role, code in accounts.items()],
        "price_change_rule": {"counts_only_verified": True, "text": "Only approved ERP amendments change a PO price."},
        "bank_change_rule": {"counts_only_verified": True, "text": "Only verified changes to the supplier master count."},
        "exemption_certificates": [],
    }
    start = lo - timedelta(days=HISTORY_LEAD_DAYS + 365 * r.randint(1, 6))
    company = {
        "company_id": cid, "split": split.name, "country": country, "legal_name": legal,
        "registration_no": g.registration_no(r, start, ids),
        "address": _address(r, bank, country), "base_currency": currency, "industry": r.choice(bank["industries"]),
        "tax_registrations": g.company_registrations(r, start, ids), "people": people, "policy_pack": policy,
    }
    kind = g.company_kinds[k % len(g.company_kinds)] if g.company_kinds else ""
    facts = g.company_facts(r, kind)
    if facts is not None:
        company["tax_facts"] = facts
    cw = CompanyWorld(country, company, [], {}, account_for_role=accounts, kind=kind)
    cats = country_categories(country)
    n = r.randint(*SUPPLIERS)
    for j in range(n):
        cw_supplier(cw, r, namer, ids, known, cats, j, foreign=r.random() < float(FOREIGN_SUPPLIER_SHARE), start=start)
    for j, spec in enumerate(g.special_suppliers(), n):
        _special_supplier(cw, r, namer, ids, known, spec, j, start)
    g.link_company(cw.company, {k: cw.supplier(sid) for k, sid in cw.special.items()})
    _contracts(cw, r, lo)
    _special_contracts(cw, g.special_suppliers())
    _certificates(cw, r, lo, ids)
    _history(cw, r, lo - timedelta(days=HISTORY_LEAD_DAYS), hi)
    _background_mail(cw, r, lo, hi, domain)
    return cw


def cw_supplier(cw: CompanyWorld, r: random.Random, namer: _Names, ids: Ids, known: dict[str, dict],
                cats: list[Category], j: int, foreign: bool, start: date) -> None:
    """Add supplier j. A name already used by another company of the split brings that supplier's identity."""
    sid = f"S{j + 1:03d}"
    while True:
        name = namer.supplier()
        identity = known.get(name)
        if identity is None or not identity.get("special"):
            break                         # a special supplier's name stays its own
    if identity is None:
        identity = known[name] = _supplier_identity(cw, r, namer, ids, cats, name, foreign, start)
    supplier = {k: v for k, v in identity.items() if k not in ("categories", "residence_from")}
    supplier |= {"supplier_id": sid, "company_id": cw.company_id,
                 "contacts": [c | {"contact_id": f"{sid}-c{i + 1}"} for i, c in enumerate(identity["contacts"])]}
    if identity.get("residence_from"):
        cw.residence_certificates.append({
            "certificate_id": f"COR-{cw.company_id}-{sid}", "supplier_id": sid, "country": identity["country"],
            "valid_from": identity["residence_from"], "valid_to": None})
    cw.suppliers.append(supplier)
    cw.categories[sid] = list(identity["categories"])


def _special_supplier(cw: CompanyWorld, r: random.Random, namer: _Names, ids: Ids, known: dict[str, dict],
                      spec: SpecialSupplier, j: int, start: date) -> None:
    """Add special supplier j: the split's one supplier of this kind (drawn at the first company, with a name new to
    the split; every company deals with the same one)."""
    g = pack(cw.country).generation
    sid = f"S{j + 1:03d}"
    identity = next((i for i in known.values() if i.get("special") == spec.kind), None)
    if identity is not None:
        name = identity["name"]
        namer.local.add(name)
    else:
        while True:
            name = namer.supplier()
            if name not in known:
                break
        cats = [catalog().get(c) for c in spec.categories]
        identity = _supplier_identity(cw, r, namer, ids, cats, name, spec.foreign, start, chosen=list(spec.categories),
                                      home=spec.home, registered_for=spec.registered_for)
        identity["special"] = spec.kind
        if spec.foreign:
            identity.pop("residence_from", None)
            if spec.residence:
                identity["residence_from"] = str(date(start.year + 1, 1, 1))
        facts = identity.get("tax_facts") or ({"country": cw.country} if spec.facts else None)
        if facts is not None:
            identity["tax_facts"] = facts | spec.facts | g.special_facts(spec.kind, identity)
        known[name] = identity
    supplier = {k: v for k, v in identity.items() if k not in ("categories", "residence_from", "special")}
    supplier |= {"supplier_id": sid, "company_id": cw.company_id,
                 "contacts": [c | {"contact_id": f"{sid}-c{i + 1}"} for i, c in enumerate(identity["contacts"])]}
    if identity.get("residence_from"):
        cw.residence_certificates.append({
            "certificate_id": f"COR-{cw.company_id}-{sid}", "supplier_id": sid, "country": identity["country"],
            "valid_from": identity["residence_from"], "valid_to": None})
    cw.suppliers.append(supplier)
    cw.categories[sid] = list(identity["categories"])
    cw.special[spec.kind] = sid


def _special_contracts(cw: CompanyWorld, specs: tuple[SpecialSupplier, ...]) -> None:
    """The contract records the special kinds carry (absolute dates from the pack)."""
    for spec in specs:
        if spec.contract is None:
            continue
        sid = cw.special[spec.kind]
        c = dict(spec.contract)
        parties = [cw.special[k] for k in c.pop("parties", [])]
        cw.contracts.append({"contract_id": f"K-{cw.company_id}-{sid}", "company_id": cw.company_id,
                             "supplier_id": sid, "parties": parties, **c})


def _supplier_identity(cw: CompanyWorld, r: random.Random, namer: _Names, ids: Ids, cats: list[Category], name: str,
                       foreign: bool, start: date, chosen: list[str] | None = None, home: str | None = None,
                       registered_for: tuple[str, ...] | None = None) -> dict:
    g = pack(cw.country).generation
    bank = names(cw.country)
    if chosen is None:
        chosen = sorted({c.category for c in r.sample(cats, r.randint(1, 3))})
    kinds = {catalog().get(c).kind for c in chosen} if registered_for is None else set(registered_for)
    identity = {
        "name": name, "country": cw.country, "address": _address(r, bank, cw.country),
        "registration_no": g.registration_no(r, start - timedelta(days=365 * r.randint(0, 10)), ids),
        "currency": g.currency, "payment_terms_days": r.choice([30, 30, 45, 60]),
        "contacts": [{"name": namer.person(), "email": f"billing@{_slug(name)}.example"}],
        "bank_account": {"bank_name": r.choice(bank["banks"]), "account_name": name, "account_no": ids.account()},
        "categories": chosen,
    }
    if foreign:
        home = home or r.choice(g.foreign_countries)
        identity |= {"country": home, "currency": "USD", "address": {"lines": ["Head office"], "country": home}}
        if r.random() < 0.5:
            identity["residence_from"] = str(date(start.year + 1, 1, 1))
    else:
        identity["tax_registrations"] = g.supplier_registrations(r, kinds, start, ids)
        facts = g.supplier_facts(r, kinds)
        if facts is not None:
            identity["tax_facts"] = facts
    return identity


def _contracts(cw: CompanyWorld, r: random.Random, lo: date) -> None:
    """A written contract with each supplier of rental or construction services: signed and stamped before the window,
    with a price-review clause, so no transitional contract exemption (K-4, L-1) applies in the clean base."""
    for supplier in cw.ordinary_suppliers():
        sid = supplier["supplier_id"]
        items = {getattr(catalog().get(c).tax.get(cw.country), "service_item", None) for c in cw.categories[sid]}
        if not any(i and i[0] in ("K", "L") for i in items):
            continue
        signed = lo - timedelta(days=r.randint(200, 900))
        cw.contracts.append({
            "contract_id": f"K-{cw.company_id}-{sid}", "company_id": cw.company_id, "supplier_id": sid,
            "signed_on": str(signed), "stamped_on": str(signed + timedelta(days=r.randint(5, 25))),
            "has_price_review_clause": True, "states_service": True, "states_fixed_value": True, "states_period": True,
            "start": str(signed + timedelta(days=30)), "end": str(date(2029, 12, 31))})


def _certificates(cw: CompanyWorld, r: random.Random, lo: date, ids: Ids) -> None:
    """An exemption certificate for each registered manufacturer, covering the categories the pack names (a rule
    recipe needs them) and two more (B1-4 plants the exempt lines; the clean base leaves the covered categories
    alone)."""
    eligible = sorted(c.category for c in country_categories(cw.country)
                      if getattr(c.tax.get(cw.country), "schedule_c_eligible", False))
    facts = cw.company.get("tax_facts") or {}
    if eligible and facts.get("is_registered_manufacturer"):
        must = list(pack(cw.country).generation.certificate_covers)
        rest = [c for c in eligible if c not in must]
        cw.company["policy_pack"]["exemption_certificates"].append({
            "kind": "schedule_c", "number": f"SC-{ids.digits(8)}",
            "valid_from": str(lo - timedelta(days=r.randint(30, 400))), "valid_to": None,
            "categories": sorted(must + r.sample(rest, min(2, len(rest))))})


def _history(cw: CompanyWorld, r: random.Random, lo: date, hi: date) -> None:
    """Paid invoices from each domestic supplier, at the rates of their own dates (step 11 plan §8.4)."""
    g = pack(cw.country).generation
    for supplier in cw.domestic_suppliers():
        sid = supplier["supplier_id"]
        kind = cw.kind_of(sid)
        day = lo + timedelta(days=r.randrange(60))
        n = 0
        while day <= hi:
            cats = [catalog().get(c) for c in cw.categories[sid]]
            lines = []
            for i, cat in enumerate(r.sample(cats, min(len(cats), r.randint(1, 2)))):
                clean = g.clean_line(cat, day, cw.company, supplier, kind)
                if clean is None:
                    continue
                qty = r.randint(1, 40) if cat.kind == "goods" else r.randint(1, 2)
                unit = price(r, cat.kind)
                net = (Decimal(qty) * unit).quantize(CENT)
                tax = tax_of(net, clean.rate)
                lines.append({"line_no": len(lines) + 1, "description": f"{cat.label} (history)", "qty": qty,
                              "uom": "unit" if cat.kind == "goods" else "job", "unit_price": money(unit),
                              "net_amount": money(net), "tax_rate": str(clean.rate), "tax_amount": money(tax),
                              "category": cat.category, "ext": clean.ext})
            if lines:
                n += 1
                number = f"{_slug(supplier['name'])[:4].upper()}-H{day:%y%m}{n:03d}"
                cw.ledger.append({"ledger_id": f"L-{sid}-{n:03d}", "supplier_id": sid, "status": "paid",
                                  "posted_on": str(day), "invoice": invoice_dict(cw, supplier, lines, day, number,
                                                                                f"HIST-{sid}-{n:03d}", None)})
            day += timedelta(days=r.randint(*HISTORY_GAP_DAYS))


def invoice_dict(cw: CompanyWorld, supplier: dict, lines: list[dict], day: date, number: str, invoice_id: str,
                 po_number: str | None) -> dict:
    """An invoice record from lines that carry their country fields under 'ext' (moved to the e-invoice block)."""
    g = pack(cw.country).generation
    net = sum(Decimal(x["net_amount"]) for x in lines)
    tax = sum(Decimal(x["tax_amount"]) for x in lines)
    block = g.einvoice(cw.company, supplier, lines, day, number)
    clean_lines = [{k: v for k, v in x.items() if k != "ext"} for x in lines]
    company = cw.company
    rate = None if supplier["currency"] == company["base_currency"] else g.exchange_rate(supplier["currency"], day)
    out = {
        "country": cw.country, "invoice_id": invoice_id, "invoice_number": number, "issue_date": str(day),
        "due_date": str(day + timedelta(days=supplier["payment_terms_days"])),
        "supplier_block": {"name": supplier["name"], "address": ", ".join(supplier["address"]["lines"])},
        "buyer_block": {"name": company["legal_name"], "address": ", ".join(company["address"]["lines"])},
        "po_reference": po_number, "currency": supplier["currency"],
        "totals": {"net": money(net), "tax": money(tax), "gross": money(net + tax)},
        "bank_block": {"bank_name": supplier["bank_account"]["bank_name"],
                       "account_name": supplier["bank_account"]["account_name"],
                       "account_no": supplier["bank_account"]["account_no"]},
        "lines": clean_lines, "einvoice": block,
    }
    if rate is not None:
        out["exchange_rate"] = str(rate)
    return out


def in_base(invoice: dict, amount: Decimal) -> Decimal:
    """An invoice amount in the company's base currency, at the invoice's own rate."""
    rate = invoice.get("exchange_rate")
    return (amount * Decimal(rate)).quantize(CENT, ROUND_HALF_UP) if rate else amount


def _background_mail(cw: CompanyWorld, r: random.Random, lo: date, hi: date, domain: str) -> None:
    """Mail that belongs to no case: newsletters, statements, meeting notes. No signals."""
    subjects = ["Monthly statement of account", "Office closure notice", "Updated price list for next quarter",
                "Delivery schedule for the coming weeks", "Annual supplier survey", "Meeting notes: quarterly review"]
    for i in range(r.randint(*BACKGROUND_MAIL)):
        supplier = r.choice(cw.suppliers)
        sent = day_between(r, lo, hi)
        cw.emails.append({
            "thread_id": f"T-{cw.company_id}-{i + 1:03d}", "message_id": f"M-{cw.company_id}-{i + 1:03d}",
            "company_id": cw.company_id, "case_id": None, "sent_at": f"{sent}T{r.randrange(8, 18):02d}:{r.randrange(60):02d}:00",
            "sender": {"name": supplier["contacts"][0]["name"], "address": supplier["contacts"][0]["email"]},
            "to": [{"address": f"ap@{domain}"}], "subject": r.choice(subjects),
            "body": "Please find the details attached. No action is needed on any open invoice.",
            "intent": "background",
        })
