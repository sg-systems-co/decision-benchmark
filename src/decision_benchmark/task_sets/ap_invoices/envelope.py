"""The invoice Case inside the shared core.CaseEnvelope.

The envelope holds case_id, split, country, languages, modality, provenance,
canary and the documents (the structured invoice record and, once rendered,
the invoice file). The payload Case holds invoice data only. The rules engine
reads the envelope.
"""

from __future__ import annotations

from pydantic import model_validator

from decision_benchmark.core.case import CaseEnvelope, Document, Provenance

from .models.case import Case
from .models.common import TASK_SET_ID

MODALITIES = ("pdf", "scan", "photo")


class ApCaseEnvelope(CaseEnvelope[Case]):
    @model_validator(mode="after")
    def _fits_task_set(self) -> ApCaseEnvelope:
        if self.task_set != TASK_SET_ID:
            raise ValueError(f"task_set must be {TASK_SET_ID}")
        if self.country != self.payload.invoice.country:
            raise ValueError(f"case country {self.country} differs from invoice country {self.payload.invoice.country}")
        if self.modality not in MODALITIES:
            raise ValueError(f"modality must be one of {MODALITIES}")
        if not any(d.role == "invoice" and d.record == "invoice" for d in self.documents):
            raise ValueError("documents must include the structured invoice record")
        if len([d for d in self.documents if d.file is not None]) > 1:
            raise ValueError("a case has at most one invoice file")
        return self

    @property
    def invoice_file(self) -> str | None:
        return next((d.file for d in self.documents if d.file is not None), None)


def envelope(
    case_id: str,
    split: str,
    payload: Case,
    *,
    languages: list[str] | None = None,
    modality: str = "pdf",
    invoice_file: str | None = None,
    provenance: Provenance | None = None,
    canary: str | None = None,
) -> ApCaseEnvelope:
    documents = [Document(role="invoice", record="invoice")]
    if invoice_file:
        documents.append(Document(role="invoice", file=invoice_file))
    return ApCaseEnvelope(
        case_id=case_id,
        task_set=TASK_SET_ID,
        split=split,
        country=payload.invoice.country,
        languages=languages or ["en"],
        modality=modality,
        provenance=provenance,
        canary=canary,
        documents=documents,
        payload=payload,
    )
