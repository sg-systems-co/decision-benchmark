"""Bank details against the supplier record; bank changes that came only by email."""

from __future__ import annotations

import re

from ..models import BankChangeRequest, Finding
from ..codes import Code
from ..findings import finding
from .view import CaseView


def norm_account(account_no: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", account_no).upper()


def check(view: CaseView) -> list[Finding]:
    if view.invoice.doc_type == "credit_note":
        return []  # a credit note pays nothing out
    record = norm_account(view.supplier.bank_account.account_no)
    out: list[Finding] = []
    block = view.invoice.bank_block
    if block and block.account_no and norm_account(block.account_no) != record:
        out.append(
            finding(
                Code.BANK_DETAILS_DIFFER_FROM_RECORD,
                invoice_account=block.account_no,
                record_account=view.supplier.bank_account.account_no,
            )
        )
    verified_new = {norm_account(c.new_account_no) for c in view.supplier.bank_change_log if c.verified}
    for email in view.emails:
        signal = email.signal("bank_change_request")
        if not isinstance(signal, BankChangeRequest):
            continue
        new = norm_account(signal.new_bank_account)
        if new not in verified_new or new != record:
            out.append(finding(Code.BANK_CHANGE_BY_EMAIL_ONLY, message_id=email.message_id))
    return out
