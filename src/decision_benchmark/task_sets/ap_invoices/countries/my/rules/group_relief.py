"""Group relief (MS-6): First Schedule paras 3-9, Service Tax Regulations 2018.

v0.9 logic, moved here unchanged; A12 build PR 2 commit 7 replaces it with the control and 5% tests.
"""

from __future__ import annotations

from ....findings import NotSettled
from .context import Exempt, LineCtx


def check(ctx: LineCtx) -> Exempt | None:
    if not ctx.profile.group_relief:
        return None
    if ctx.sf.group_relation == "unclear":
        raise NotSettled("MS-6", "group_relief_unclear")
    return None
