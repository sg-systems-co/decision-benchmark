"""AP inbox message (step-11 plan §4.6)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Model, internal


class EmailAddress(Model):
    name: str | None = None
    address: str


class BankChangeRequest(Model):
    kind: Literal["bank_change_request"] = "bank_change_request"
    new_bank_account: str


class PriceChange(Model):
    kind: Literal["price_change"] = "price_change"
    status: Literal["amended_in_erp", "verbal_only"]
    """amended_in_erp: the PO was amended and approved; verbal_only: only the email says so."""


class LookalikeSender(Model):
    kind: Literal["lookalike_sender"] = "lookalike_sender"


class InstructionInjection(Model):
    kind: Literal["instruction_injection"] = "instruction_injection"


Signal = Annotated[
    BankChangeRequest | PriceChange | LookalikeSender | InstructionInjection, Field(discriminator="kind")
]
SignalKind = Literal["bank_change_request", "price_change", "lookalike_sender", "instruction_injection"]


class Email(Model):
    thread_id: str
    message_id: str
    company_id: str
    case_id: str | None = None
    """The case this message belongs to; None for background mail."""
    sent_at: datetime
    sender: EmailAddress
    to: list[EmailAddress]
    cc: list[EmailAddress] = []
    subject: str
    body: str
    languages: list[str] = ["en"]
    attachments: list[str] = []
    # Generator truth
    intent: str | None = internal(None)
    signals: list[Signal] = internal([])
    """What the message does, as structured facts. The rules engine reads these, never the text."""

    @model_validator(mode="after")
    def _one_per_kind(self) -> Email:
        kinds = [s.kind for s in self.signals]
        if len(kinds) != len(set(kinds)):
            raise ValueError("at most one signal of each kind per email")
        return self

    def signal(self, kind: SignalKind) -> Signal | None:
        return next((s for s in self.signals if s.kind == kind), None)
