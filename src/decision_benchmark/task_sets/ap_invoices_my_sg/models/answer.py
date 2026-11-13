"""Answer key (step-11 plan §4.9). Written only by the rules engine."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from decision_benchmark.core.case import AnswerEnvelope

from .common import TASK_SET_ID, AnswerSource, Decision, Model, Num, TaxTreatment, Tier


class Finding(Model):
    code: str
    tier: Tier
    evidence: dict[str, Any] = {}
    """JSON-ready values only (strings, ints, lists)."""


class AnswerKey(Model):
    case_id: str
    decision: Decision
    tax_treatment: TaxTreatment | None
    gl_account: str | None
    reason_codes: list[str]
    answer_source: AnswerSource
    findings: list[Finding] = []
    # For agent-track graders
    truth_supplier_id: str
    truth_po_number: str | None = None
    truth_price_variance_pct: Num | None = None
    requires_supplier_contact: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> AnswerKey:
        if not self.reason_codes:
            raise ValueError("an answer key needs at least one reason code")
        handover = self.decision is Decision.HAND_OVER
        if handover != (self.answer_source is AnswerSource.HANDOVER_BY_CONSTRUCTION):
            raise ValueError("HAND_OVER if and only if answer_source is handover_by_construction")
        if not handover and (self.tax_treatment is None or self.gl_account is None):
            raise ValueError("tax treatment and GL account may be null only on HAND_OVER")
        return self

    def as_output(self) -> dict[str, Any]:
        """The answer in the leaderboard output format (output.schema.json)."""
        return {
            "case_id": self.case_id,
            "decision": self.decision.value,
            "tax_treatment": self.tax_treatment.value if self.tax_treatment else None,
            "gl_account": self.gl_account,
            "reason_codes": list(self.reason_codes),
        }

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
