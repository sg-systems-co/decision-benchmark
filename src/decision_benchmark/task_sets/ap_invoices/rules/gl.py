"""GL accounts: per invoice line, and the case-level account (plan Q6; spec v0.10 clarification).

Each line books to its PO line's account, else to the chart-of-accounts account for its category's
GL role. The case-level account is the account of the line with the largest amount excluding tax
(ties: the lowest line number).
"""

from __future__ import annotations

from ..findings import UnsupportedCase
from ..models import Catalog, PurchaseOrder
from .view import CaseView


def line_accounts(view: CaseView, po: PurchaseOrder | None, line_map: dict[int, int] | None,
                  catalog: Catalog) -> dict[int, str]:
    coa = view.policy
    out: dict[int, str] = {}
    for line in view.invoice.lines:
        if po is not None and line_map is not None:
            po_line = po.line(line_map[line.line_no])
            assert po_line is not None
            code = po_line.gl_account
            acct = coa.account(code)
            if acct is None or not acct.active:
                raise UnsupportedCase(f"PO GL account {code} is not an active account in the chart of accounts")
        else:
            role = catalog.get(line.category).gl_role
            matches = [a.code for a in coa.chart_of_accounts if a.active and a.role == role]
            if len(matches) != 1:
                raise UnsupportedCase(f"chart of accounts has {len(matches)} active accounts for GL role {role}")
            code = matches[0]
        out[line.line_no] = code
    return out


def case_account(view: CaseView, accounts: dict[int, str]) -> str:
    """The account of the line with the largest absolute amount excluding tax (spec v0.10 clarification, so credit
    notes and mixed-sign invoices follow one rule); ties: the lowest line number."""
    line = min(view.invoice.lines, key=lambda x: (-abs(x.net_amount), x.line_no))
    return accounts[line.line_no]
