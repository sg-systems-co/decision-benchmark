"""db-generate (B1-1 skeleton): the slot report and provenance for a release split or a split spec."""

import json

from decision_benchmark.core.generator.cli import build_hash, main
from decision_benchmark.task_sets.ap_invoices.spec import SPEC


def test_release_split(tmp_path):
    assert main(["--task-set", SPEC.id, "--split", "test", "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "test/report/slots.json").read_text())
    assert report["n_cases"] == 500 and len(report["slots"]) == 500
    prov = json.loads((tmp_path / "test/report/provenance.json").read_text())
    assert prov["pipeline_hash"] == build_hash(SPEC) and len(prov["pipeline_hash"]) == 64
    first = (tmp_path / "test/report/slots.json").read_bytes()
    main(["--task-set", SPEC.id, "--split", "test", "--out", str(tmp_path)])
    assert (tmp_path / "test/report/slots.json").read_bytes() == first          # byte-identical rebuild


def test_split_spec(tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text("name: extra\nn_cases: 300\nseed: 99\nid_start: 9001\n")
    assert main(["--task-set", SPEC.id, "--split-spec", str(spec), "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "extra/report/slots.json").read_text())
    assert report["hard"]["total"] == 150 and min(s["case_index"] for s in report["slots"]) == 9001
