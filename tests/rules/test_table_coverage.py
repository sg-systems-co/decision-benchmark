"""Every row of the rule-sheet table has a registered positive and near-miss test."""

from pathlib import Path

from decision_benchmark.rules.table_rows import ROWS

from . import test_table_rows

SHEET = Path(__file__).resolve().parents[2] / "docs/task-sets/ap-invoices-my-sg/tax-rules-v0.9.md"
HEADER = "| Situation planted in a case |"


def table_situations() -> list[str]:
    lines = SHEET.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(HEADER))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(line.split("|")[1].strip().replace("\\_", "_"))
    return rows


def test_table_has_thirteen_rows():
    assert len(table_situations()) == 13


def test_registry_matches_the_table_exactly():
    assert list(ROWS) == table_situations()


def test_every_row_has_positive_and_negative_tests_that_exist():
    for situation, tests in ROWS.items():
        assert tests["positive"] and tests["negative"], situation
        for name in tests["positive"] + tests["negative"]:
            assert callable(getattr(test_table_rows, name, None)), f"{situation}: {name} missing"


def test_no_unregistered_row_tests():
    registered = {n for t in ROWS.values() for n in t["positive"] + t["negative"]}
    defined = {n for n in dir(test_table_rows) if n.startswith("test_row")}
    assert defined == registered
