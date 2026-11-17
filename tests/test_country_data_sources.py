"""Every data table in a country pack names its sources, and every row points to one of them.

A data table is a YAML file under task_sets/*/countries/*/data/ with a top-level `source` list
(manifest IDs from docs/sources/manifest.yaml) and a `rows` list; each row has a `source` that is
one of the file's sources."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_IDS = {s["id"] for s in yaml.safe_load((ROOT / "docs/sources/manifest.yaml").read_text(encoding="utf-8"))["sources"]}
TABLES = sorted((ROOT / "src/decision_benchmark/task_sets").glob("*/countries/*/data/*.yaml"))


def test_there_are_data_tables():
    assert TABLES


@pytest.mark.parametrize("path", TABLES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_row_has_a_source(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    head = path.read_text(encoding="utf-8").splitlines()[:5]
    sources = data["source"]
    assert sources and set(sources) <= MANIFEST_IDS, f"unknown source IDs: {set(sources) - MANIFEST_IDS}"
    assert any("manifest" in line and line.startswith("#") for line in head), "header comment names the manifest"
    assert data["rows"], "a table has rows"
    for i, row in enumerate(data["rows"]):
        assert row.get("source") in sources, f"row {i} has no source from the header: {row}"
