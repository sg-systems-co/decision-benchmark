"""The shared case format: one case envelope and one answer-key envelope for every task set.

The envelope holds only what every task set has. Everything specific to a task
set (records, documents' structured fields, generator truth) sits in its
payload, a pydantic model the task set declares.

The answer-key envelope holds the decision, the extra scored fields the task
set declares in its TaskSetSpec (by name, never a confidence), and the source
of the answer. A task set's own answer key may carry more (findings, agent
grader truth); it converts to this envelope for scoring.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

from .model import AnswerSource, Model

P = TypeVar("P", bound=BaseModel)


class Provenance(Model):
    generator_version: str
    seed: int
    pipeline_hash: str


class Document(Model):
    """One document in a case: a structured record in the payload, or a file in the release."""

    role: str
    record: str | None = None
    """Name of the payload field that holds the structured record."""
    file: str | None = None
    """Path of the file relative to the release root (a PDF, scan or photo)."""

    @model_validator(mode="after")
    def _one_source(self) -> Document:
        if (self.record is None) == (self.file is None):
            raise ValueError("a document has exactly one of record or file")
        return self


class CaseEnvelope(Model, Generic[P]):
    case_id: str
    task_set: str
    split: str
    country: str = Field(pattern=r"^[A-Z]{2}$")
    languages: list[str]
    modality: str
    provenance: Provenance | None = None
    canary: str | None = None
    documents: list[Document]
    payload: P

    @model_validator(mode="after")
    def _records_exist(self) -> CaseEnvelope[P]:
        if not self.languages:
            raise ValueError("a case has at least one language")
        for doc in self.documents:
            if doc.record is not None and doc.record not in type(self.payload).model_fields:
                raise ValueError(f"document {doc.role!r} names a record the payload does not have: {doc.record}")
        return self


class AnswerEnvelope(Model):
    case_id: str
    task_set: str
    decision: str
    answer: dict[str, Any]
    """The task set's extra scored fields, JSON-ready, exactly the names in TaskSetSpec.extra_fields."""
    answer_source: AnswerSource
