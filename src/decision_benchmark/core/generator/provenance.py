"""Provenance of a build (step 11 plan §8.1): ``pipeline_hash`` is sha256 over the sorted (path, sha256) pairs of the
files that shape the data, so a row's (generator_version, seed, pipeline_hash) names exactly what made it."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

SKIPPED_PARTS = ("__pycache__",)
SKIPPED_SUFFIXES = (".pyc",)


def files_under(root: Path, rel_paths: Iterable[str]) -> list[Path]:
    """Every file under the given paths (files or folders, relative to ``root``), skipping caches. A missing path is
    an error: the hash must not silently drop part of the pipeline."""
    out: list[Path] = []
    for rel in rel_paths:
        p = root / rel
        if not p.exists():
            raise FileNotFoundError(f"pipeline path {rel} does not exist under {root}")
        candidates = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
        out += [x for x in candidates if not set(x.parts) & set(SKIPPED_PARTS) and x.suffix not in SKIPPED_SUFFIXES]
    return out


def pipeline_hash(root: Path, rel_paths: Iterable[str], extra: dict[str, Path] | None = None) -> str:
    """sha256 over "path sha256" lines, sorted by path (paths relative to ``root``, with forward slashes). ``extra``
    adds files outside ``root`` under the given names (the dependency lock file)."""
    entries = [(f.relative_to(root).as_posix(), f) for f in files_under(root, rel_paths)]
    entries += list((extra or {}).items())
    lines = sorted(f"{name} {hashlib.sha256(f.read_bytes()).hexdigest()}" for name, f in entries)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
