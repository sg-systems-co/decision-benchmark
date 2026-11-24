"""Named edit operations (step 11 plan §7.2): small typed functions that turn a clean base case into a family's case.

A template is data: a list of ops with parameters, never an expression. Each op declares what it needs and what it
removes (``requires``, ``removes``), so the loader rejects a pair of families that can't apply together. Ops that plant
a rule's line (``early``) run first; ops that copy the finished invoice (the duplicates) run last (``late``), after every
other family's ops. Country specifics (which rate is wrong, what makes an invoice invalid, how a rule is planted) come
from the pack's generation part.
"""

from __future__ import annotations

import copy
import inspect
from collections import Counter
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from ..countries import pack
from . import phrases
from .entities import CompanyWorld, catalog, in_base, money, tax_of
from .scenario import BuiltCase
from .statements import Statements


class Turns:
    """Deterministic turns over a split: when k kept cases have asked for key, the next gets options[k % len(options)]. Only a
    kept case counts (commit); a redraw moves on by its attempt number (offset), so a turn the slot can't take isn't
    asked for twenty times. The build stays reproducible."""

    def __init__(self, seen: Counter | None = None, offset: int = 0):
        self.seen = seen if seen is not None else Counter()
        self.taken: Counter = Counter()
        self.offset = offset

    def take(self, key: str, options: list):
        k = self.seen[key] + self.taken[key] + self.offset
        self.taken[key] += 1
        return options[k % len(options)]

    def commit(self) -> None:
        self.seen.update(self.taken)
        self.taken = Counter()


@dataclass
class Draft:
    """A case being edited: the built clean case plus what families add."""

    built: BuiltCase
    cw: CompanyWorld
    r: random.Random
    findings: list[str] = field(default_factory=list)
    """Finding codes the ops added on top of the templates' expect (country-specific ones)."""
    approver_pinned: bool = False
    """A family chose the PO approver on purpose (above_approval_limit); otherwise it follows the final amount."""
    uses: list = field(default_factory=list)
    """The slot's rule appearances (core.generator.slots.RuleUse) the case plants."""
    planted_rules: list[str] = field(default_factory=list)
    """Rules the ops planted (for the per-rule report)."""
    turns: Turns | None = None
    """The split's turns (Turns.take): a recipe's branches in rotation rather than drawn."""
    realized: dict = field(default_factory=dict)
    """Rule -> the rule the key names for it, where a recipe plants one of its branches that another rule decides (an
    imported service from a group company abroad is MS-8's branch, decided by group relief)."""
    late: list = field(default_factory=list)
    """Statements made once every op has run (amounts as final: a fact that is a share of a line's amount)."""
    final: list = field(default_factory=list)
    """Edits made after the last refresh (a document that prints no tax total, an e-invoice without its totals)."""
    tax_due: dict = field(default_factory=dict)
    """Line number -> tax(line) for a line whose tax isn't its rate on its net amount (part of it exempt, part paid
    before a rate change, a fixed amount per unit); refresh recomputes it from the line's current amounts."""

    def turn(self, key: str, options: list):
        """The next of options for key, in turn over the split's cases (drawn when the draft has no turns)."""
        if not options:
            raise ValueError(f"no options for {key}")
        return self.turns.take(key, options) if self.turns is not None else self.r.choice(options)

    @property
    def invoice(self) -> dict:
        return self.built.case["invoice"]

    @property
    def po(self) -> dict | None:
        pos = self.built.records["purchase_orders"]
        return pos[0] if pos else None

    @property
    def gr(self) -> dict | None:
        grs = self.built.records["goods_receipts"]
        return grs[0] if grs else None

    @property
    def day(self) -> date:
        return date.fromisoformat(self.invoice["issue_date"])

    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.built.case["as_of_date"])

    def line(self, n: int) -> dict:
        return self.invoice["lines"][n - 1]

    def planted_line(self, n: int, treatment: str, basis: str) -> None:
        lines = self.built.planted.lines
        lines[n - 1] = (n, treatment, basis)

    # -- planting a rule's line (the pack's recipes call these) ---------------------------------------------------

    @property
    def supplier(self) -> dict:
        return self.cw.supplier(self.built.case["supplier_id"])

    @property
    def supplier_kind(self) -> str:
        return self.cw.kind_of(self.built.case["supplier_id"])

    def set_line(self, n: int, category: str, rate: Decimal, ext: dict) -> None:
        """Line n becomes a line of ``category`` charged at ``rate`` (0: no tax), with the country's e-invoice line
        fields ``ext``; its facts are stated afresh (the delivery date or the invoice's service period)."""
        cat = catalog().get(category)
        x = self.line(n)
        x["category"] = category
        x["description"] = cat.label if cat.kind == "goods" else f"{cat.label}, {self.day:%B %Y}"
        if catalog().get(x["category"]).kind == "goods":
            x["uom"] = "unit"
        elif x["uom"] == "unit":
            x["uom"] = "job"
            x["qty"] = min(int(x["qty"]), 2)
        x["tax_rate"] = str(rate)
        if self.po is not None:
            p = self.po["lines"][n - 1]
            p.update(category=category, description=x["description"], uom=x["uom"], qty=x["qty"],
                     gl_account=self.cw.account_for_role[cat.gl_role])
        if self.gr is not None:
            self.gr["lines"][n - 1].update(uom=x["uom"], qty_received=x["qty"])
            goods = any(catalog().get(y["category"]).kind == "goods" for y in self.invoice["lines"])
            self.gr["kind"] = "goods" if goods else "service_confirmation"
        block = self.invoice.get("einvoice") or {}
        for e in block.get("lines", []):
            if e["line_no"] == n:
                for k in [k for k in e if k != "line_no"]:
                    del e[k]
                e.update(ext)
        x.pop("facts", None)
        self.tax_due.pop(n, None)
        fields = pack(self.cw.country).line_facts_model.model_fields
        st = self.statements()
        if cat.kind == "goods" and self.gr is not None and "delivery_date" in fields:
            st.state(x, "delivery_date", self.gr["gr_number"], "gr_date")
        if cat.kind == "service" and self.invoice.get("service_period_start"):
            st.state(x, "service_period_start", self.invoice["invoice_id"], "service_period_start")
            st.state(x, "service_period_end", self.invoice["invoice_id"], "service_period_end")
        self.built.planted.line_actions[n] = []

    def statements(self) -> Statements:
        st = Statements()
        st.docs = self.built.docs
        return st

    def state(self, n: int, fact: str, value) -> None:
        """State a line fact as a phrasebank phrase in the invoice line's description."""
        country = self.cw.country
        phrase = phrases.express(country, fact, value, self.r)
        self.statements().state_phrase(self.line(n), fact, phrases.json_value(country, fact, value), phrase,
                                       self.invoice["invoice_id"], f"lines[{n - 1}].description")

    def expect(self, n: int, treatment: str, basis: str, findings: tuple[str, ...] = (),
               actions: tuple[tuple[str, str | None, str | None], ...] = ()) -> None:
        """What the engine must find for line n: its treatment and basis, the findings and buyer actions it brings."""
        self.planted_line(n, treatment, basis)
        self.findings += list(findings)
        self.built.planted.line_actions[n] = list(actions)

    def add_actions(self, n: int, actions: tuple[tuple[str, str | None, str | None], ...]) -> None:
        self.built.planted.line_actions.setdefault(n, []).extend(actions)

    def line_kind(self, n: int) -> str:
        return catalog().get(self.line(n)["category"]).kind

    def drop_facts_citing(self, doc_id: str) -> None:
        """Withdraw statements whose evidence is a document the case no longer has."""
        for line in self.invoice["lines"]:
            facts = line.get("facts") or {}
            for name in [k for k, v in facts.items() if any(e["doc_id"] == doc_id for e in v.get("evidence", []))]:
                del facts[name]
            if not facts:
                line.pop("facts", None)
        self.built.docs.pop(doc_id, None)

    def refresh(self) -> None:
        """Recompute line amounts, totals, the PO total and the e-invoice totals after the ops."""
        for line in self.invoice["lines"]:
            net = (Decimal(str(line["qty"])) * Decimal(line["unit_price"])).quantize(Decimal("0.01"))
            line["net_amount"] = money(net)
            due = self.tax_due.get(line["line_no"])
            line["tax_amount"] = money(due(line) if due is not None else tax_of(net, Decimal(line["tax_rate"])))
        net = sum(Decimal(x["net_amount"]) for x in self.invoice["lines"])
        tax = sum(Decimal(x["tax_amount"]) for x in self.invoice["lines"])
        self.invoice["totals"] = {"net": money(net), "tax": money(tax), "gross": money(net + tax)}
        pack(self.cw.country).generation.refresh_einvoice(self.invoice)
        if self.po is not None:
            self.po["total_net"] = money(sum(Decimal(str(x["qty"])) * Decimal(x["unit_price"]) for x in self.po["lines"]))

    def finish(self) -> None:
        """After every op: the PO approver is the lowest role whose limit covers the final amount (a family that
        changed quantities or prices must not add an approval problem by accident), unless a family pinned it."""
        self.refresh()
        if self.po is None or self.approver_pinned:
            return
        matrix = sorted(self.cw.company["policy_pack"]["approval_matrix"], key=lambda a: Decimal(a["limit"]))
        gross = in_base(self.invoice, self.gross())
        role = next((a["approval_role"] for a in matrix if gross <= Decimal(a["limit"])), matrix[-1]["approval_role"])
        self.po["approver_id"] = next(p["person_id"] for p in self.cw.company["people"] if p.get("approval_role") == role)

    def gross(self) -> Decimal:
        return sum(Decimal(x["net_amount"]) + Decimal(x["tax_amount"]) for x in self.invoice["lines"])


@dataclass(frozen=True)
class OpSpec:
    name: str
    fn: Callable
    requires: frozenset[str]
    removes: frozenset[str]
    late: bool
    params: tuple[str, ...]
    early: bool = False


OPS: dict[str, OpSpec] = {}


def op(requires: tuple[str, ...] = (), removes: tuple[str, ...] = (), late: bool = False, early: bool = False):
    """Register an op. requires / removes name case parts: 'po' (the PO and its receipt), 'receipt', 'taxed_line'."""
    def wrap(fn: Callable) -> Callable:
        params = tuple(p for p in inspect.signature(fn).parameters if p != "d")
        OPS[fn.__name__] = OpSpec(fn.__name__, fn, frozenset(requires), frozenset(removes), late, params, early)
        return fn
    return wrap


# -- price and quantity ------------------------------------------------------------------------------------------


@op(requires=("po",))
def raise_unit_price_pct(d: Draft, line: int, pct: int) -> None:
    """The invoice bills a line above the PO price (no approved amendment)."""
    x = d.line(line)
    x["unit_price"] = money(Decimal(x["unit_price"]) * (100 + Decimal(pct)) / 100)


@op(requires=("po",))
def set_line_qty(d: Draft, line: int, qty: int) -> None:
    """The line's quantity on the PO, the receipt and the invoice."""
    d.line(line)["qty"] = qty
    d.po["lines"][line - 1]["qty"] = qty
    if d.gr is not None:
        d.gr["lines"][line - 1]["qty_received"] = qty


@op(requires=("po", "receipt"))
def short_receipt(d: Draft, line: int, units: int) -> None:
    """The receipt records fewer units than the invoice bills."""
    gl = d.gr["lines"][line - 1]
    gl["qty_received"] = max(0, int(gl["qty_received"]) - units)


@op(requires=("po",), removes=("receipt",))
def remove_receipt(d: Draft) -> None:
    """Nothing was received against the PO yet."""
    if d.gr is not None:
        d.drop_facts_citing(d.gr["gr_number"])
    d.built.records["goods_receipts"] = []


# -- routing -------------------------------------------------------------------------------------------------------


@op(removes=("po", "receipt"))
def remove_po_reference(d: Draft) -> None:
    """No PO: the invoice names none and the company has none for it."""
    if d.gr is not None:
        d.drop_facts_citing(d.gr["gr_number"])
    if d.po is not None:
        d.built.docs.pop(d.po["po_number"], None)
    d.invoice["po_reference"] = None
    for x in d.invoice["lines"]:
        x["po_line_no"] = None
    d.built.records["purchase_orders"] = []
    d.built.records["goods_receipts"] = []


@op(requires=("po",))
def scale_above_approval_limit(d: Draft, role: str) -> None:
    """The PO was approved by ``role``, whose limit the invoice exceeds: every quantity is scaled up whole."""
    d.refresh()
    limit = next(Decimal(a["limit"]) for a in d.cw.company["policy_pack"]["approval_matrix"] if a["approval_role"] == role)
    factor = int(limit / in_base(d.invoice, d.gross())) + 1 + d.r.randint(0, 2)
    for n, x in enumerate(d.invoice["lines"], 1):
        x["qty"] = int(x["qty"]) * factor
        d.po["lines"][n - 1]["qty"] = int(d.po["lines"][n - 1]["qty"]) * factor
    if d.gr is not None:                       # receipts scale in proportion, so a short receipt stays short
        for gl in d.gr["lines"]:
            gl["qty_received"] = int(gl["qty_received"]) * factor
    approver = next(p for p in d.cw.company["people"] if p.get("approval_role") == role)
    d.po["approver_id"] = approver["person_id"]
    d.approver_pinned = True


# -- bank details ----------------------------------------------------------------------------------------------------


def _other_account(d: Draft) -> str:
    record = d.invoice["bank_block"]["account_no"]
    while True:
        digits = f"{d.r.randrange(10**12):012d}"
        account = f"{digits[:4]} {digits[4:8]} {digits[8:]}"
        if account != record:
            return account


@op()
def change_invoice_bank(d: Draft) -> None:
    """The invoice prints a bank account that is not the one on the supplier record."""
    d.invoice["bank_block"]["account_no"] = _other_account(d)


@op()
def add_bank_change_email(d: Draft) -> None:
    """An email in the case thread asks to pay a new account; nothing verified reached the supplier master."""
    supplier = next(s for s in d.cw.suppliers if s["supplier_id"] == d.built.case["supplier_id"])
    contact = supplier["contacts"][0]
    sent = d.day - timedelta(days=d.r.randint(1, 10))
    domain = d.cw.company["people"][0]["email"].split("@")[1]
    d.built.records.setdefault("emails_add", []).append({
        "thread_id": f"T-{d.built.case_id}", "message_id": f"M-{d.built.case_id}-bank", "company_id": d.cw.company_id,
        "case_id": d.built.case_id, "sent_at": f"{sent}T{d.r.randrange(8, 18):02d}:15:00",
        "sender": {"name": contact["name"], "address": contact["email"]}, "to": [{"address": f"ap@{domain}"}],
        "subject": "Change of bank account", "body": "Please pay this and future invoices into our new account.",
        "intent": "bank_change_request",
        "signals": [{"kind": "bank_change_request", "new_bank_account": _other_account(d)}],
    })


# -- duplicates (late: they copy the finished invoice) ------------------------------------------------------------


def _ledger_copy(d: Draft, number: str, tag: str, days_before: int) -> None:
    old = copy.deepcopy(d.invoice)
    issued = max(d.day - timedelta(days=days_before), date.fromisoformat(d.po["po_date"]) if d.po else d.day)
    old.update(invoice_id=f"HIST-{d.built.case_id}-{tag}", invoice_number=number, issue_date=str(issued),
               due_date=str(issued + timedelta(days=30)))
    if old["einvoice"].get("uuid"):
        old["einvoice"]["uuid"] = f"{old['einvoice']['uuid']}-{tag}"     # the earlier document had its own id
    d.built.records.setdefault("ledger_add", []).append({
        "ledger_id": f"L-{d.built.case_id}-{tag}", "supplier_id": d.built.case["supplier_id"], "status": "paid",
        "posted_on": str(issued), "invoice": old})


@op(late=True)
def add_history_duplicate(d: Draft, days_before: int) -> None:
    """The same invoice number is already in the ledger (the supplier sent the invoice again)."""
    _ledger_copy(d, d.invoice["invoice_number"], "dup", days_before)


@op(requires=("po",), late=True)
def add_near_duplicate(d: Draft, days_before: int) -> None:
    """An invoice with another number but the same amount, PO and period is already in the ledger."""
    number = d.invoice["invoice_number"]
    _ledger_copy(d, f"{number[:-2]}{(int(number[-2:]) + 37) % 100:02d}R", "near", days_before)


# -- invoice requirements and tax --------------------------------------------------------------------------------


@op()
def make_invoice_invalid(d: Draft) -> None:
    """The invoice misses a particular the country requires (the pack chooses which: an e-invoice field, a tax-invoice particular)."""
    codes, override = pack(d.cw.country).generation.make_invalid(d.invoice, [u.rule for u in d.uses], d)
    d.findings += codes
    if override is not None:
        for n, x in enumerate(d.invoice["lines"], 1):
            if Decimal(x["tax_rate"]) > 0:
                d.planted_line(n, *override)


@op(requires=("taxed_line",))
def set_wrong_rate(d: Draft, line: int) -> None:
    """The line charges a rate the rules reject (starter tax family; B1-4 adds a family per rule)."""
    x = d.line(line)
    clean = pack(d.cw.country).generation.clean_line(catalog().get(x["category"]), d.day)
    wrong = pack(d.cw.country).generation.wrong_rate(catalog().get(x["category"]), d.day, clean)
    if wrong is None:
        raise ValueError("set_wrong_rate needs a taxed line")
    x["tax_rate"] = str(wrong.rate)
    d.planted_line(line, wrong.treatment, wrong.basis)


@op(early=True)
def plant_rule(d: Draft, line: int, rule: str, form: str) -> None:
    """Line ``line`` shows the rule deciding it, in its problem or correct form (the pack's recipe for the rule)."""
    pack(d.cw.country).generation.plant(d, line, rule, form)
    d.planted_rules.append(rule)


@op(early=True)
def plant_handover(d: Draft, line: int, kind: str) -> None:
    """Line ``line`` raises a question the rules leave open (the pack's recipe for ``kind``): the case is HAND_OVER."""
    pack(d.cw.country).generation.plant_handover(d, line, kind)


# -- rule hand-over --------------------------------------------------------------------------------------------------


@op(requires=("po",), removes=("po_reference",))
def add_second_fitting_po(d: Draft) -> None:
    """The invoice names no PO and two open POs of the supplier fit it (step 11 Q14: HAND_OVER)."""
    second = copy.deepcopy(d.po)
    second["po_number"] = f"{d.po['po_number']}-B"
    second["po_date"] = str(date.fromisoformat(d.po["po_date"]) - timedelta(days=d.r.randint(3, 20)))
    d.built.records["purchase_orders"].append(second)
    d.invoice["po_reference"] = None
