"""Tests for release/check_public.py.

Every hidden-looking file and every fake token is built at runtime in a
temporary folder. Nothing of the kind is ever committed to this repo.
"""

from __future__ import annotations

import os
import random
import shutil
import string
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import check_public as cp

REPO_ROOT = Path(__file__).resolve().parents[2]


def rules(findings) -> set[str]:
    return {f.rule.split(" ")[0] for f in findings}


def write(root: Path, rel: str, text: str = "x\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def fake_hf_token() -> str:
    # Built at runtime so no token-like literal exists in this file.
    rng = random.Random(7)
    return "hf" + "_" + "".join(rng.choice(string.ascii_letters) for _ in range(34))


def write_cases(root: Path, config: str, file_split: str, n: int, **columns) -> None:
    """Write data/<config>/<file_split>-00000.parquet; keyword args override columns."""
    rows = {
        "case_id": [f"ap-{file_split}-{i:05d}" for i in range(n)],
        "split": [file_split] * n,
        "answer_decision": ["APPROVE"] * n,
    }
    if file_split == "test":
        rows["canary"] = [cp.PUBLIC_TEST_CANARY] * n
    rows.update(columns)
    p = root / f"data/{config}/{file_split}-00000.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(rows), p)


def staged_with_data(root: Path) -> Path:
    write(root, "README.md", "card\n")
    write_cases(root, "decision", "train", 2000)
    write_cases(root, "decision", "test", 500)
    return root


# --- the current repo -------------------------------------------------------


def test_current_repo_passes():
    assert cp.check(REPO_ROOT, "repo") == []


def test_clean_staged_alpha_tree_passes(tmp_path):
    write(tmp_path, "README.md", "card\n")
    write(tmp_path, "schema/output.schema.json", "{}\n")
    write(tmp_path, "docs/spec-v0.9.md", "spec\n")
    assert cp.check(tmp_path, "staged") == []


def test_clean_staged_tree_with_data_passes(tmp_path):
    assert cp.check(staged_with_data(tmp_path), "staged") == []


# --- step 8 acceptance: hidden file and fake token make the check fail -------


def test_hidden_jsonl_file_fails(tmp_path):
    write(tmp_path, "hidden/x.jsonl", '{"case_id": "ap-my-00001"}\n')
    found = rules(cp.check(tmp_path, "repo"))
    assert "1" in found and "5" in found


def test_fake_token_fails(tmp_path):
    write(tmp_path, "notes.txt", f"token = {fake_hf_token()}\n")
    found = cp.check(tmp_path, "repo")
    assert rules(found) == {"7"}
    # The finding names the file and the kind of secret, never the value.
    assert all(fake_hf_token() not in str(f) for f in found)


@pytest.mark.skipif(
    shutil.which("gitleaks") is None and not os.environ.get("REQUIRE_GITLEAKS"),
    reason="gitleaks not installed (CI installs it and sets REQUIRE_GITLEAKS=1)",
)
def test_gitleaks_flags_fake_token(tmp_path):
    assert shutil.which("gitleaks"), "REQUIRE_GITLEAKS is set but gitleaks is not installed"
    write(tmp_path, "config.env", f'HF_TOKEN="{fake_hf_token()}"\n')
    res = subprocess.run(
        ["gitleaks", "dir", str(tmp_path), "--redact", "--no-banner", "--log-level", "error"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    assert fake_hf_token() not in res.stdout + res.stderr


# --- rule 1: path names -----------------------------------------------------


@pytest.mark.parametrize("rel", ["hidden/a.md", "x/HoldOut/a.md", "held-out.md", "private_notes.md", "a/hiddenset.txt"])
def test_rule1_path_names_fail(tmp_path, rel):
    write(tmp_path, rel)
    assert "1" in rules(cp.check(tmp_path, "repo"))


def test_rule1_word_in_content_is_fine(tmp_path):
    write(tmp_path, "docs/a.md", "The hidden split is private.\n")
    assert cp.check(tmp_path, "repo") == []


# --- rule 2: hidden canary --------------------------------------------------


def test_rule2_hidden_canary_fails(tmp_path):
    write(tmp_path, "docs/a.md", f"canary {cp.HIDDEN_CANARY_GUID}\n")
    assert rules(cp.check(tmp_path, "repo")) == {"2"}


def test_rule2_hidden_canary_in_parquet_row_fails(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "train", 2000, note=[cp.HIDDEN_CANARY_GUID] * 2000)
    assert "2" in rules(cp.check(tmp_path, "staged"))


def test_rule2_public_canary_is_fine(tmp_path):
    write(tmp_path, "docs/a.md", f"{cp.PUBLIC_TEST_CANARY}\n")
    assert cp.check(tmp_path, "repo") == []


# --- rule 3: split values ---------------------------------------------------


def test_rule3_hidden_split_value_fails(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "train", 2000, split=["hidden"] * 2000)
    assert "3" in rules(cp.check(tmp_path, "staged"))


def test_rule3_split_must_match_file_name(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "test", 500, split=["train"] * 500)
    assert "3" in rules(cp.check(tmp_path, "staged"))


# --- rule 4: row counts -----------------------------------------------------


def test_rule4_extra_rows_fail(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "test", 800)
    assert "4" in rules(cp.check(tmp_path, "staged"))


def test_rule4_missing_split_fails(tmp_path):
    write_cases(tmp_path, "decision", "train", 2000)
    assert "4" in rules(cp.check(tmp_path, "staged"))


def test_rule4_duplicate_case_ids_fail(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "train", 2000, case_id=["ap-my-00001"] * 2000)
    assert "4" in rules(cp.check(tmp_path, "staged"))


# --- rule 5: data location --------------------------------------------------


@pytest.mark.parametrize("rel", ["data.jsonl", "data/decision/train-0.parquet", "cases.csv", "x/answers.json"])
def test_rule5_data_in_repo_fails(tmp_path, rel):
    write(tmp_path, rel, "{}\n")
    assert "5" in rules(cp.check(tmp_path, "repo"))


def test_rule5_exempt_paths_pass(tmp_path):
    write(tmp_path, "release/manifests/v0.9.0-alpha.1.sha256", "abc  README.md\n")
    write(tmp_path, "schemas/ap-invoices-my-sg/v0.9/output.schema.json", '{"type": "object"}\n')
    write(tmp_path, "schemas/ap-invoices-my-sg/v0.9/examples/valid/a.json", '{"decision": "APPROVE"}\n')
    assert cp.check(tmp_path, "repo") == []


def test_rule5_answer_keys_in_exempt_path_fail(tmp_path):
    write(tmp_path, "schemas/ap-invoices-my-sg/v0.9/examples/valid/a.json", '{"answer_decision": "APPROVE"}\n')
    assert rules(cp.check(tmp_path, "repo")) == {"5"}


def test_rule5_staged_data_outside_data_paths_fails(tmp_path):
    write(tmp_path, "README.md")
    write_cases(tmp_path, "decision", "train", 10)
    (tmp_path / "data/decision/train-00000.parquet").rename(tmp_path / "extra.parquet")
    assert "5" in rules(cp.check(tmp_path, "staged"))


def test_rule5_staged_unknown_config_fails(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "secretconfig", "train", 10)
    assert "5" in rules(cp.check(tmp_path, "staged"))


# --- rule 6: public test canary ---------------------------------------------


def test_rule6_test_rows_without_canary_fail(tmp_path):
    staged_with_data(tmp_path)
    write_cases(tmp_path, "decision", "test", 500, canary=["nope"] * 500)
    assert rules(cp.check(tmp_path, "staged")) == {"6"}


# --- command line -----------------------------------------------------------


def test_cli_exit_codes(tmp_path, capsys):
    write(tmp_path, "ok.md")
    assert cp.main([str(tmp_path)]) == 0
    write(tmp_path, "hidden/x.jsonl", "{}\n")
    assert cp.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "FAIL [1 path-name] hidden/x.jsonl" in out
