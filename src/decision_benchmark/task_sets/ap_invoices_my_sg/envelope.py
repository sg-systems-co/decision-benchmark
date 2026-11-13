"""The invoice Case inside the shared core.CaseEnvelope.

For now the payload Case still carries case_id, split, country, languages,
modality and provenance itself (the rules engine and the fixtures read them
there). ApCaseEnvelope checks that the envelope and the payload agree. B1
removes the copies from the payload when the generator starts writing envelopes
(step-11 plan §3).
"""

from __future__ import annotations

from pydantic import model_validator

from decision_benchmark.core.case import CaseEnvelope, Document

from .models.case import Case
from .models.common import TASK_SET_ID


class ApCaseEnvelope(CaseEnvelope[Case]):
    @model_validator(mode="after")
    def _matches_payload(self) -> ApCaseEnvelope:
        p = self.payload
        if self.task_set != TASK_SET_ID:
            raise ValueError(f"task_set must be {TASK_SET_ID}")
        pairs = {
            "case_id": (self.case_id, p.case_id),
            "split": (self.split, p.split),
            "country": (self.country, p.country.value),
            "languages": (self.languages, p.languages),
            "modality": (self.modality, p.modality),
            "provenance": (self.provenance, p.provenance),
        }
        for name, (outer, inner) in pairs.items():
            if outer != inner:
                raise ValueError(f"envelope {name} differs from the payload: {outer!r} vs {inner!r}")
        return self


def envelope(case: Case, canary: str | None = None) -> ApCaseEnvelope:
    documents = [Document(role="invoice", record="invoice")]
    if case.invoice_file:
        documents.append(Document(role="invoice", file=case.invoice_file))
    return ApCaseEnvelope(
        case_id=case.case_id,
        task_set=TASK_SET_ID,
        split=case.split,
        country=case.country.value,
        languages=list(case.languages),
        modality=case.modality,
        provenance=case.provenance,
        canary=canary,
        documents=documents,
        payload=case,
    )
