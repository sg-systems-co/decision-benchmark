"""Named edit operations (step 11 plan §7.2): small typed functions that turn a clean base case into a family's case.

A template is data: a list of ops with parameters, never an expression. Each op declares what it needs and what it
removes (``requires``, ``removes``), so the loader rejects a pair of families that can't apply together. Ops that copy
the finished invoice (the duplicates) run last (``late``), after every other family's ops. Country specifics (which
rate is wrong, what makes an invoice invalid) come from the pack's generation part.
"""

from __future__ import annotations

import copy
import inspect
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from ..countries import pack
from .entities import CompanyWorld, catalog, money, tax_of
from .scenario import BuiltCase


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
            line["tax_amount"] = money(tax_of(net, Decimal(line["tax_rate"])))
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
        role = next((a["approval_role"] for a in matrix if self.gross() <= Decimal(a["limit"])), matrix[-1]["approval_role"])
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


OPS: dict[str, OpSpec] = {}


def op(requires: tuple[str, ...] = (), removes: tuple[str, ...] = (), late: bool = False):
    """Register an op. requires / removes name case parts: 'po' (the PO and its receipt), 'receipt', 'taxed_line'."""
    def wrap(fn: Callable) -> Callable:
        params = tuple(p for p in inspect.signature(fn).parameters if p != "d")
        OPS[fn.__name__] = OpSpec(fn.__name__, fn, frozenset(requires), frozenset(removes), late, params)
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
    factor = int(limit / d.gross()) + 1 + d.r.randint(0, 2)
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
    codes, override = pack(d.cw.country).generation.make_invalid(d.invoice)
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


# -- rule hand-over --------------------------------------------------------------------------------------------------


@op(requires=("po",), removes=("po_reference",))
def add_second_fitting_po(d: Draft) -> None:
    """The invoice names no PO and two open POs of the supplier fit it (step 11 Q14: HAND_OVER)."""
    second = copy.deepcopy(d.po)
    second["po_number"] = f"{d.po['po_number']}-B"
    second["po_date"] = str(date.fromisoformat(d.po["po_date"]) - timedelta(days=d.r.randint(3, 20)))
    d.built.records["purchase_orders"].append(second)
    d.invoice["po_reference"] = None
