"""Golden answer keys and the version guard (A12 plan §9).

Every answer key the rules and core tests write must equal the golden file of the current engine
version. A key that changes without a version bump fails here. After a bump, write the new golden
file with tests/keys/collect.py and list the change, by rule ID, in tests/fixtures/keys/changes.md.
"""

import importlib.util
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("keys_collect", HERE / "collect.py")
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)

CHANGES = collect.GOLDEN_DIR / "changes.md"


@pytest.fixture(scope="module")
def collected():
    return collect.collect()


def test_golden_file_exists_for_the_engine_version():
    version = collect.engine_version()
    assert collect.golden_path(version).exists(), (
        f"no golden keys for engine version {version}: run tests/keys/collect.py and list the change in changes.md")


def test_keys_equal_the_golden_file(collected):
    version = collect.engine_version()
    golden = collect.read_golden(version)
    assert golden is not None
    diff = [(g["test"], g["call"]) for g, c in zip(golden, collected, strict=False) if g != c]
    assert len(golden) == len(collected) and not diff, (
        f"answer keys changed without an engine version bump ({version}): "
        f"{len(golden)} golden vs {len(collected)} now; first differences: {diff[:5]}")


def test_every_golden_file_is_listed_in_changes():
    listed = set(re.findall(r"^## (\S+)", CHANGES.read_text(encoding="utf-8"), re.MULTILINE))
    files = {p.name.removeprefix("keys-").removesuffix(".yaml") for p in collect.GOLDEN_DIR.glob("keys-*.yaml")}
    assert files == listed
