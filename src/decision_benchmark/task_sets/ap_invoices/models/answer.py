"""Answer key (step-11 plan §4.9). Written only by the rules engine."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from decision_benchmark.core.case import AnswerEnvelope

from ..codes import Code
from .common import TASK_SET_ID, AnswerSource, Decision, Model, Money, Num, Tier

WITHHOLD_TAX = "WITHHOLD_TAX"


class Finding(Model):
    code: Code
    tier: Tier
    evidence: dict[str, Any] = {}
    """JSON-ready values only (strings, ints, lists)."""


class GraderTruth(Model):
    """What the agent-track graders check against. Never part of the scored output."""

    supplier_id: str
    po_number: str | None = None
    price_variance_pct: Num | None = None
    requires_supplier_contact: bool = False


class TaxLine(Model):
    """One invoice line's tax treatment (spec v0.10 tax_lines)."""

    line_no: int = Field(ge=1, le=200)
    treatment: str | None
    basis: str
    gl_account: str | None = None


class BuyerAction(Model):
    """An action the buyer itself must take (spec v0.10 buyer_actions). WITHHOLD_TAX carries rate, basis, base."""

    action: str
    rate: Num | None = None
    basis: str | None = None
    base_amount: Money | None = None

    @model_validator(mode="after")
    def _withholding(self) -> BuyerAction:
        parts = (self.rate, self.basis, self.base_amount)
        if self.action == WITHHOLD_TAX and any(p is None for p in parts):
            raise ValueError("WITHHOLD_TAX needs rate, basis and base_amount")
        if self.action != WITHHOLD_TAX and any(p is not None for p in parts):
            raise ValueError("only WITHHOLD_TAX carries rate, basis and base_amount")
        return self

    def as_output(self) -> dict[str, Any]:
        out: dict[str, Any] = {"action": self.action}
        if self.action == WITHHOLD_TAX:
            assert self.rate is not None and self.base_amount is not None
            rate = int(self.rate) if self.rate == self.rate.to_integral_value() else float(self.rate)
            out |= {"rate": rate, "basis": self.basis, "base_amount": f"{self.base_amount:.2f}"}
        return out


class AnswerKey(Model):
    case_id: str
    decision: Decision
    tax_treatment: str | None
    """A tax-treatment code of the invoice country's pack."""
    gl_account: str | None
    reason_codes: list[Code]
    answer_source: AnswerSource
    findings: list[Finding] = []
    grader_truth: GraderTruth
    tax_lines: list[TaxLine] = []
    buyer_actions: list[BuyerAction] = []
    facts: list[dict[str, Any]] | None = None
    """Gold facts: per line, the facts the engine read, in the spec's facts.lines format (with evidence)."""
    engine_version: str
    """The decision-benchmark package version whose engine wrote this key."""
    rules_version: str
    """The rule sheet version the engine applied."""

    @field_validator("tax_treatment")
    @classmethod
    def _known_code(cls, value: str | None) -> str | None:
        from ..countries import all_tax_codes

        if value is not None and value not in all_tax_codes():
            raise ValueError(f"unknown tax treatment {value!r}")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> AnswerKey:
        if not self.reason_codes:
            raise ValueError("an answer key needs at least one reason code")
        handover = self.decision is Decision.HAND_OVER
        if handover != (self.answer_source is AnswerSource.HANDOVER_BY_CONSTRUCTION):
            raise ValueError("HAND_OVER if and only if answer_source is handover_by_construction")
        if not handover and (self.tax_treatment is None or self.gl_account is None):
            raise ValueError("tax treatment and GL account may be null only on HAND_OVER")
        nos = [line.line_no for line in self.tax_lines]
        if len(nos) != len(set(nos)):
            raise ValueError("tax_lines name each line once")
        if not handover and any(line.treatment is None for line in self.tax_lines):
            raise ValueError("a line treatment may be null only on HAND_OVER")
        return self

    def as_output(self) -> dict[str, Any]:
        """The answer in the leaderboard output format (schemas/ap-invoices/v0.10/output.schema.json)."""
        out: dict[str, Any] = {
            "case_id": self.case_id,
            "decision": self.decision.value,
            "tax_treatment": str(self.tax_treatment) if self.tax_treatment else None,
            "gl_account": self.gl_account,
            "reason_codes": [str(c) for c in self.reason_codes],
        }
        if self.tax_lines:
            out["tax_lines"] = [line.model_dump(mode="json", exclude_none=True) | {"treatment": line.treatment}
                                for line in self.tax_lines]
            out["buyer_actions"] = [a.as_output() for a in self.buyer_actions]
        if self.facts:
            out["facts"] = {"lines": self.facts}
        return out

    def envelope(self) -> AnswerEnvelope:
        """The answer key in the shared core format, for the scorer."""
        out = self.as_output()
        return AnswerEnvelope(
            case_id=self.case_id,
            task_set=TASK_SET_ID,
            decision=out["decision"],
            answer={k: out[k] for k in ("tax_treatment", "gl_account", "reason_codes")},
            answer_source=self.answer_source,
        )
