#!/usr/bin/env python3
"""Copy the allowlisted files into build/hf/ and check the result.

Only files named in release/allowlist.txt are copied. The staged folder is
then checked with check_public.py (staged mode). Prints one line per file:
sha256, size, path.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_public  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWLIST = REPO_ROOT / "release" / "allowlist.txt"
DEFAULT_OUT = REPO_ROOT / "build" / "hf"


class StageError(Exception):
    pass


def parse_allowlist(path: Path) -> list[tuple[str, str]]:
    entries = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "->" not in line:
            raise StageError(f"{path.name}:{n}: expected '<source> -> <destination>'")
        src, dest = (part.strip() for part in line.split("->", 1))
        if not src or not dest or dest.startswith("/") or ".." in Path(dest).parts:
            raise StageError(f"{path.name}:{n}: bad entry")
        entries.append((src, dest))
    return entries


def plan(root: Path, allowlist: Path) -> dict[str, Path]:
    """Map destination path -> source file."""
    mapping: dict[str, Path] = {}
    for src, dest in parse_allowlist(allowlist):
        matches = sorted(p for p in root.glob(src) if p.is_file())
        if not matches:
            raise StageError(f"allowlist entry matched nothing: {src}")
        if not dest.endswith("/") and len(matches) != 1:
            raise StageError(f"allowlist entry {src} matched {len(matches)} files but names one destination")
        for m in matches:
            target = dest + m.name if dest.endswith("/") else dest
            if target in mapping:
                raise StageError(f"two sources for {target}")
            mapping[target] = m
    return mapping


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage(root: Path = REPO_ROOT, out: Path = DEFAULT_OUT, allowlist: Path = DEFAULT_ALLOWLIST) -> list[str]:
    """Stage files into out. Returns the sorted destination paths. Raises StageError."""
    root, out = root.resolve(), out.resolve()
    if out == root or root.is_relative_to(out):
        raise StageError("output folder must not contain the repo")
    mapping = plan(root, allowlist)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for dest, src in mapping.items():
        target = out / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)

    staged = sorted(check_public.list_files(out, "staged"))
    if staged != sorted(mapping):
        raise StageError("staged folder does not match the allowlist")
    findings = check_public.check(out, "staged")
    if findings:
        raise StageError("check_public failed on the staged folder:\n" + "\n".join(map(str, findings)))
    return staged


def manifest_lines(out: Path, files: list[str]) -> list[str]:
    return [f"{sha256(out / f)}  {f}" for f in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--manifest", type=Path, help="also write 'sha256  path' lines to this file")
    args = parser.parse_args(argv)
    try:
        files = stage(REPO_ROOT, args.out, args.allowlist)
    except StageError as exc:
        print(f"stage: ERROR: {exc}", file=sys.stderr)
        return 1
    out = args.out.resolve()
    for f in files:
        print(f"{sha256(out / f)}  {(out / f).stat().st_size:>9}  {f}")
    if args.manifest:
        args.manifest.write_text("\n".join(manifest_lines(out, files)) + "\n", encoding="utf-8")
    print(f"stage: {len(files)} files staged in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
