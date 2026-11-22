"""``db-generate``: build a split (B1-1 skeleton: the slot table and its report).

    db-generate --task-set <id> --split train --out build/
    db-generate --task-set <id> --split-spec spec.yaml --out build/

The public splits use the task set's release seeds. Anyone else passes a split spec (name, n_cases, seed, id_start,
canary); nothing here knows any particular private split. Writes ``<out>/<split>/report/slots.json``,
``provenance.json`` and, when the task set names a builder, ``planting.json`` (attempts, redraws and causes per family
and rule); it exits non-zero if a redraw threshold is crossed. Writing the cases themselves comes with B1-7.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import yaml

from .. import task_set
from ..case import Provenance
from ..task_set import TaskSetSpec
from .provenance import pipeline_hash
from .slots import allocate
from .spec import SplitSpec


def release_splits(spec: TaskSetSpec) -> dict[str, SplitSpec]:
    gen = spec.generation
    assert gen is not None
    data = yaml.safe_load((Path(gen.root) / gen.release_seeds).read_text(encoding="utf-8"))
    return {name: SplitSpec(name=name, **v) for name, v in data["splits"].items()}


def build_hash(spec: TaskSetSpec) -> str:
    gen = spec.generation
    assert gen is not None
    lock = Path(gen.lock_file) if gen.lock_file else None
    extra = {lock.name: lock} if lock is not None and lock.exists() else None
    return pipeline_hash(Path(gen.root), gen.pipeline_paths, extra)


def generate(spec: TaskSetSpec, split: SplitSpec, out: Path, version: str) -> Path:
    gen = spec.generation
    if gen is None:
        raise SystemExit(f"task set {spec.id} has no generator config")
    allocation = allocate(gen, dict(spec.quotas), split)
    report_dir = out / split.name / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    _write(report_dir / "slots.json", allocation.report())
    provenance = Provenance(generator_version=version, seed=split.seed, pipeline_hash=build_hash(spec))
    _write(report_dir / "provenance.json", {"task_set": spec.id, "split": split.name, "n_cases": split.n_cases,
                                            **provenance.model_dump()})
    if gen.builder:
        module, _, name = gen.builder.partition(":")
        build = getattr(importlib.import_module(module), name)(gen, dict(spec.quotas), split, provenance=provenance,
                                                               check=False)
        _write(report_dir / "planting.json", build.planting_report())
        build.check_thresholds()     # raises after the report is written, so a failed build still shows why
    return report_dir


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="db-generate", description=__doc__.splitlines()[0])
    ap.add_argument("--task-set", required=True)
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--split", help="a public split from the task set's release seeds")
    which.add_argument("--split-spec", type=Path, help="YAML with name, n_cases, seed, id_start, canary")
    ap.add_argument("--out", type=Path, default=Path("build"))
    args = ap.parse_args(argv)

    importlib.import_module("decision_benchmark.task_sets")   # registers every task set (core imports none statically)
    version = importlib.import_module("decision_benchmark").__version__

    spec = task_set.get(args.task_set)
    if args.split_spec:
        split = SplitSpec(**yaml.safe_load(args.split_spec.read_text(encoding="utf-8")))
    else:
        splits = release_splits(spec)
        if args.split not in splits:
            ap.error(f"unknown split {args.split!r}; release splits: {sorted(splits)}")
        split = splits[args.split]
    report = generate(spec, split, args.out, version)
    print(f"{report}: slots.json, provenance.json{', planting.json' if spec.generation.builder else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
