#!/usr/bin/env python3
"""Write or check the derived blocks of a versioned output schema.

Some output rules hold across fields, and JSON Schema has no keyword for them. This script writes
them as plain JSON Schema, so any validator in any language enforces them without our code:

- In every country part (countries/*.schema.json), `$defs/case_summary`: when the case-level value
  is set, it is the worst line by the part's `x-severity-order` (worst first). Every line then
  carries a code no worse than it, and at least one line carries it exactly.
- In output.schema.json, `$defs/unique_line_no`: no line number appears twice in a list of lines,
  for every line number `$defs/line_no` allows.

Field names come from `x-derive` in output.schema.json, so nothing here knows a task set or a
country. Usage:

    python schemas/derive.py schemas/ap-invoices/v0.10          # rewrite the derived blocks
    python schemas/derive.py schemas/ap-invoices/v0.10 --check  # exit 1 if they are stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def dumps(obj, indent: int = 0, width: int = 110) -> str:
    """JSON with short objects and arrays kept on one line."""
    flat = json.dumps(obj, ensure_ascii=False)
    if len(flat) + indent <= width or not isinstance(obj, (dict, list)) or not obj:
        return flat
    pad = " " * (indent + 2)
    if isinstance(obj, dict):
        items = [f"{pad}{json.dumps(k, ensure_ascii=False)}: {dumps(v, indent + 2, width)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + " " * indent + "}"
    items = [f"{pad}{dumps(v, indent + 2, width)}" for v in obj]
    return "[\n" + ",\n".join(items) + "\n" + " " * indent + "]"


def case_summary(order: list[str], cfg: dict) -> dict:
    summary, lines, value = cfg["summary_field"], cfg["lines_field"], cfg["line_value_field"]
    clauses = []
    for i, code in enumerate(order):
        clauses.append({
            "if": {"required": [summary, lines], "properties": {summary: {"const": code}}},
            "then": {"properties": {lines: {
                "items": {"required": [value], "properties": {value: {"enum": order[i:]}}},
                "contains": {"required": [value], "properties": {value: {"const": code}}},
            }}},
        })
    return {
        "$comment": "Derived by schemas/derive.py from x-severity-order. Do not edit by hand.",
        "description": f"A set {summary} is the worst {value} in {lines}, by x-severity-order.",
        "allOf": clauses,
    }


def unique_line_no(line_no: dict, cfg: dict) -> dict:
    key = cfg["line_key_field"]
    return {
        "$comment": "Derived by schemas/derive.py from $defs/line_no. Do not edit by hand.",
        "description": f"No {key} appears twice.",
        "allOf": [
            {"contains": {"required": [key], "properties": {key: {"const": n}}}, "minContains": 0, "maxContains": 1}
            for n in range(line_no["minimum"], line_no["maximum"] + 1)
        ],
    }


def derive(folder: Path) -> dict[Path, dict]:
    """Every schema file of the folder with its derived blocks filled in."""
    out_path = folder / "output.schema.json"
    output = json.loads(out_path.read_text(encoding="utf-8"))
    cfg = output["x-derive"]
    output["$defs"]["unique_line_no"] = unique_line_no(output["$defs"]["line_no"], cfg)
    files = {out_path: output}
    for part_path in sorted((folder / "countries").glob("*.schema.json")):
        part = json.loads(part_path.read_text(encoding="utf-8"))
        codes = [c["const"] for c in part["$defs"]["tax_code"]["oneOf"]]
        order = part["x-severity-order"]
        if sorted(order) != sorted(codes) or len(set(order)) != len(order):
            raise SystemExit(f"{part_path}: x-severity-order must list every tax code once")
        part["$defs"]["case_summary"] = case_summary(order, cfg)
        files[part_path] = part
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    stale = []
    for path, obj in derive(args.folder).items():
        if json.loads(path.read_text(encoding="utf-8")) != obj:
            stale.append(path)
            if not args.check:
                path.write_text(dumps(obj) + "\n", encoding="utf-8")
    if args.check and stale:
        print("derived blocks are stale, run schemas/derive.py:", *map(str, stale), sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
