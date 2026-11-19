"""Reference-row check (A12 plan §11): for every case the fixture suite plants, check_rules run on the answer key's gold
facts gives the key's per-line treatments, bases and buyer actions. In B1 the same check runs over every generated case
of every split."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(bool(os.environ.get("DB_REFROW_OUT")), reason="inside the reference-row run itself")
def test_check_rules_reproduces_every_answer_key_from_its_gold_facts():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "refrow.jsonl"
        env = os.environ | {"DB_REFROW_OUT": str(out), "PYTHONPATH": os.pathsep.join(
            [str(ROOT / "tests/keys"), os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)}
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "refrow", "-p", "no:cacheprovider",
                              "tests/rules", "tests/core"], cwd=ROOT, env=env, capture_output=True, text=True)
        assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-2000:]
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    bad = [(r["test"], r["call"], r["diff"]) for r in rows if not r["ok"]]
    assert len(rows) > 600, f"only {len(rows)} keys checked"
    assert not bad, f"{len(bad)} of {len(rows)} keys differ; first: {bad[:3]}"
