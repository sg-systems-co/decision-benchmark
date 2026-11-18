"""Pytest plugin: records every answer key the rules engine writes during a test run.

Loaded only by tests/keys/collect.py (``-p recorder``), never by the normal suite. It wraps
``answer_case`` wherever a test module imported it and writes one JSON line per call to the
file named by DB_KEYS_OUT, sorted by test id and call number.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_KEYS: list[dict] = []


@pytest.fixture(autouse=True)
def _record_keys(request, monkeypatch):
    import decision_benchmark.task_sets.ap_invoices.rules as rules

    original = rules.answer_case
    calls = 0

    def recording(*args, **kwargs):
        nonlocal calls
        key = original(*args, **kwargs)
        _KEYS.append({"test": request.node.nodeid, "call": calls, "key": key.model_dump(mode="json")})
        calls += 1
        return key

    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "answer_case", None) is original:
            monkeypatch.setattr(module, "answer_case", recording)
    yield


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("DB_KEYS_OUT")
    if out:
        rows = sorted(_KEYS, key=lambda r: (r["test"], r["call"]))
        with open(out, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
