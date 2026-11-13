"""GL account: the PO line's account, else the CoA account for the category's GL role (plan Q6)."""

from __future__ import annotations

from ..models import Catalog, PurchaseOrder
from .findings import UnsupportedCase
from .view import CaseView


def account(view: CaseView, po: PurchaseOrder | None, line_map: dict[int, int] | None, catalog: Catalog) -> str:
    coa = view.policy
    if po is not None and line_map is not None:
        codes = set()
        for po_line_no in line_map.values():
            line = po.line(po_line_no)
            assert line is not None
            codes.add(line.gl_account)
        if len(codes) != 1:
            raise UnsupportedCase("invoice lines book to more than one GL account")
        code = codes.pop()
        acct = coa.account(code)
        if acct is None or not acct.active:
            raise UnsupportedCase(f"PO GL account {code} is not an active account in the chart of accounts")
        return code
    roles = {catalog.get(line.category).gl_role for line in view.invoice.lines}
    if len(roles) != 1:
        raise UnsupportedCase("invoice lines have more than one GL role")
    role = roles.pop()
    matches = [a.code for a in coa.chart_of_accounts if a.active and a.role == role]
    if len(matches) != 1:
        raise UnsupportedCase(f"chart of accounts has {len(matches)} active accounts for GL role {role}")
    return matches[0]
