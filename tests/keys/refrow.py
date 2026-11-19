"""Pytest plugin for the reference-row check (A12 plan §11): for every answer key the engine writes during a test run,
run check_rules on the key's gold facts and compare its per-line results and buyer actions with the key's.

Loaded only by tests/rules/test_reference_row.py (``-p refrow``). Writes one JSON line per checked key to the file
named by DB_REFROW_OUT: {"test", "call", "ok", "diff"}.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_ROWS: list[dict] = []


@pytest.fixture(autouse=True)
def _reference_row(request, monkeypatch):
    import decision_benchmark.task_sets.ap_invoices.rules as rules

    original = rules.answer_case
    calls = 0

    def checking(records, case, catalog, *args, **kwargs):
        nonlocal calls
        key = original(records, case, catalog, *args, **kwargs)
        out = rules.check_rules(records, case, [dict(x) for x in (key.facts or [])], catalog)
        got = [(x.line_no, x.treatment, x.basis) for x in out.lines]
        want = [(t.line_no, t.treatment, t.basis) for t in key.tax_lines]
        acts_got = [a.model_dump(mode="json") for x in out.lines for a in x.buyer_actions]
        acts_got = [a for i, a in enumerate(acts_got) if a not in acts_got[:i]]
        acts_want = [a.model_dump(mode="json") for a in key.buyer_actions]
        ok = got == want and acts_got == acts_want
        _ROWS.append({"test": request.node.nodeid, "call": calls, "ok": ok,
                      "diff": None if ok else {"lines": [got, want], "actions": [acts_got, acts_want]}})
        calls += 1
        return key

    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "answer_case", None) is original:
            monkeypatch.setattr(module, "answer_case", checking)
    yield


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("DB_REFROW_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            for row in sorted(_ROWS, key=lambda r: (r["test"], r["call"])):
                f.write(json.dumps(row, default=str) + "\n")
