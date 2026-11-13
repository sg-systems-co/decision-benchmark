"""Tests for release/stage.py."""

from pathlib import Path

import pytest

import stage

EXPECTED_ALPHA_FILES = [
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "docs/spec-v0.9.md",
    "docs/tax-rules-v0.9.md",
    "schema/output.schema.json",
]


def test_repo_stages_exactly_the_six_alpha_files(tmp_path):
    out = tmp_path / "hf"
    assert stage.stage(stage.REPO_ROOT, out) == EXPECTED_ALPHA_FILES


def test_staged_spec_is_byte_identical(tmp_path):
    out = tmp_path / "hf"
    stage.stage(stage.REPO_ROOT, out)
    src = stage.REPO_ROOT / "docs/task-sets/ap-invoices-my-sg/spec-v0.9.md"
    assert (out / "docs/spec-v0.9.md").read_bytes() == src.read_bytes()


def test_old_staged_files_are_removed(tmp_path):
    out = tmp_path / "hf"
    (out / "leftover").mkdir(parents=True)
    (out / "leftover/old.parquet").write_text("x")
    assert stage.stage(stage.REPO_ROOT, out) == EXPECTED_ALPHA_FILES


def _mini_repo(tmp_path: Path, allowlist: str) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.md").write_text("a\n")
    (root / "hiddenset").mkdir()
    (root / "hiddenset/cases.md").write_text("x\n")
    al = root / "allowlist.txt"
    al.write_text(allowlist)
    return root, al


def test_entry_matching_nothing_fails(tmp_path):
    root, al = _mini_repo(tmp_path, "missing.md -> missing.md\n")
    with pytest.raises(stage.StageError, match="matched nothing"):
        stage.stage(root, tmp_path / "out", al)


def test_bad_destination_fails(tmp_path):
    root, al = _mini_repo(tmp_path, "a.md -> ../a.md\n")
    with pytest.raises(stage.StageError, match="bad entry"):
        stage.stage(root, tmp_path / "out", al)


def test_staged_hidden_path_fails_check_public(tmp_path):
    root, al = _mini_repo(tmp_path, "hiddenset/cases.md -> hiddenset/cases.md\n")
    with pytest.raises(stage.StageError, match="check_public failed"):
        stage.stage(root, tmp_path / "out", al)


def test_unlisted_files_are_not_staged(tmp_path):
    root, al = _mini_repo(tmp_path, "a.md -> a.md\n")
    assert stage.stage(root, tmp_path / "out", al) == ["a.md"]
