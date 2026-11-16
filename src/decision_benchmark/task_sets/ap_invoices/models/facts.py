"""Fact sheets of simulated colleagues and supplier contacts (step-11 plan §4.7)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import model_validator

from .common import Model

Topic = Literal[
    "delivery",
    "quantity",
    "price",
    "bank_details",
    "approval",
    "tax",
    "vehicle_use",
    "duplicate",
    "service_period",
    "other",
]


class Fact(Model):
    fact_id: str
    topic: Topic
    release: Literal["always", "on_topic"]
    reply_key: str
    params: dict[str, Any] = {}


class FactSheet(Model):
    person_id: str | None = None
    contact_id: str | None = None
    role: str
    facts: list[Fact] = []
    fallback_reply_key: str

    @model_validator(mode="after")
    def _one_id(self) -> FactSheet:
        if (self.person_id is None) == (self.contact_id is None):
            raise ValueError("a fact sheet names exactly one of person_id or contact_id")
        return self
