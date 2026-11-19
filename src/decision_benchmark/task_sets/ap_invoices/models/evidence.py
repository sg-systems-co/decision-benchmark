"""Evidence references and line facts, as in the output schema (spec v0.10, "Facts").

``EvidenceRef`` mirrors ``$defs/evidence`` and ``LineFact`` mirrors ``$defs/fact`` of
schemas/ap-invoices/v0.10/output.schema.json. Each country pack declares its line-facts model
(a ``LineFacts`` subclass) with exactly the fields of its schema part's ``$defs/line_facts``.
Nothing here names a country.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BeforeValidator, Field, PlainSerializer, ValidationInfo, model_validator

from decision_benchmark.core.model import Model, _to_decimal

T = TypeVar("T")
EVIDENCE_OPTIONAL = "evidence_optional"
"""Validation context key: facts supplied without evidence (check_rules input, catalog fact defaults)."""


def _to_share(value: Any) -> Decimal:
    d = _to_decimal(value)
    if not Decimal(0) <= d <= Decimal(1):
        raise ValueError(f"a share is between 0 and 1: {value!r}")
    return d


Share = Annotated[Decimal, BeforeValidator(_to_share), PlainSerializer(float, return_type=float)]
"""A share between 0 and 1, read exactly, written as a JSON number (the schema's share type)."""


class Span(Model):
    start: int = Field(ge=0)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.end <= self.start:
            raise ValueError("a span ends after it starts")
        return self


class EvidenceRef(Model):
    """Where a fact is shown: a case document, and a field path in its record or a text span."""

    doc_id: str = Field(min_length=1)
    path: str | None = Field(default=None, min_length=1)
    span: Span | None = None
    quote: str | None = None

    @model_validator(mode="after")
    def _one_location(self) -> EvidenceRef:
        if (self.path is None) == (self.span is None):
            raise ValueError("evidence has exactly one of path or span")
        return self


class LineFact(Model, Generic[T]):
    """One fact about an invoice line. value None: the documents don't show it (no evidence then)."""

    value: T | None = None
    evidence: list[EvidenceRef] = []

    @model_validator(mode="after")
    def _evidence(self, info: ValidationInfo) -> LineFact:
        if self.value is None and self.evidence:
            raise ValueError("a fact the documents don't show has no evidence")
        optional = bool(info.context and info.context.get(EVIDENCE_OPTIONAL))
        if self.value is not None and not self.evidence and not optional:
            raise ValueError("a fact with a value needs at least one evidence reference")
        return self


def fact_field(family: str, *rules: str) -> Any:
    """A line-facts field: absent (None) unless recorded; its family and rules as in the schema part."""
    return Field(default=None, json_schema_extra={"family": family, "rules": list(rules)})


class LineFacts(Model):
    """Base of a country pack's line-facts model. A field left None was not recorded for the line."""

    def recorded(self) -> dict[str, LineFact]:
        return {name: getattr(self, name) for name in type(self).model_fields if getattr(self, name) is not None}

    def to_output(self, names: list[str] | None = None) -> dict[str, dict]:
        """The recorded facts in the spec's format: {"value": ..., "evidence": [...]}, with no evidence key on a
        null value. names: only these fields (in this order), e.g. the fields the engine read."""
        out = {}
        for name in names if names is not None else list(self.recorded()):
            fact = getattr(self, name)
            if fact is None:
                continue
            dumped = fact.model_dump(mode="json")
            entry = {"value": dumped["value"]}
            if fact.evidence:
                entry["evidence"] = [e.model_dump(mode="json", exclude_none=True) for e in fact.evidence]
            out[name] = entry
        return out
