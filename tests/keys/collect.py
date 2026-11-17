#!/usr/bin/env python3
"""Collect every answer key the test suite writes, and write or compare the golden file.

The golden file for an engine version is tests/fixtures/keys/keys-<version>.yaml: {"engine_version": ...,
"keys": [{"test", "call", "key"}, ...]}. YAML, like the worked-example fixtures, because data files
(.json, .jsonl) never live in git (release/check_public.py rule 5). The engine version is the package
version (decision_benchmark.__version__).

    python tests/keys/collect.py           # write the golden file for the current version (new versions only)
    python tests/keys/collect.py --print   # print the collected keys

An engine change that alters any key needs a new version: this script refuses to overwrite an
existing golden file with different keys, and tests/keys/test_golden_keys.py fails until the
version is bumped, the new golden file written and the change listed in changes.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests/fixtures/keys"
SOURCES = ["tests/rules", "tests/core"]


def engine_version() -> str:
    from decision_benchmark import __version__

    return __version__


def golden_path(version: str) -> Path:
    return GOLDEN_DIR / f"keys-{version}.yaml"


def collect() -> list[dict]:
    """Run the key-writing tests with the recorder and return their keys."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "keys.jsonl"
        env = os.environ | {"DB_KEYS_OUT": str(out), "PYTHONPATH": os.pathsep.join(
            [str(ROOT / "tests/keys"), os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)}
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "recorder", "-p", "no:cacheprovider", *SOURCES],
                             cwd=ROOT, env=env, capture_output=True, text=True)
        if run.returncode != 0:
            raise RuntimeError("key collection run failed:\n" + run.stdout[-3000:] + run.stderr[-2000:])
        return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


def read_golden(version: str) -> list[dict] | None:
    path = golden_path(version)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("engine_version") != version:
        raise ValueError(f"{path.name}: engine_version {data.get('engine_version')!r} is not {version}")
    return data["keys"]


def write_golden(version: str, rows: list[dict]) -> Path:
    path = golden_path(version)
    text = yaml.safe_dump({"engine_version": version, "keys": rows}, sort_keys=True, allow_unicode=True, width=120)
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()
    rows = collect()
    if args.print:
        for r in rows:
            print(json.dumps(r, sort_keys=True))
        return 0
    version = engine_version()
    existing = read_golden(version)
    if existing is not None and existing != rows:
        print(f"keys differ from {golden_path(version).name}: bump the engine version first", file=sys.stderr)
        return 1
    print(f"{write_golden(version, rows).relative_to(ROOT)}: {len(rows)} keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
