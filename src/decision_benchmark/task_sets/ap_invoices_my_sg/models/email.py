"""AP inbox email (step-11 plan §4.6).

The structured flags are generator truth. The rules engine reads them; they are
never exported. The phrasebank text must say what the flags say.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import model_validator

from .common import Model, internal


class EmailAddress(Model):
    name: str | None = None
    address: str


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
    requests_bank_change: bool = internal(False)
    new_bank_account: str | None = internal(None)
    mentions_price_change: bool = internal(False)
    price_change_status: Literal["amended_in_erp", "verbal_only", "none"] = internal("none")
    lookalike_sender: bool = internal(False)
    contains_instruction_injection: bool = internal(False)

    @model_validator(mode="after")
    def _bank_change(self) -> Email:
        if self.requests_bank_change and not self.new_bank_account:
            raise ValueError("a bank-change email needs new_bank_account")
        return self
