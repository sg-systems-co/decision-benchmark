"""The TaskSetSpec of ap-invoices, from docs/task-sets/ap-invoices/spec-v0.10.md.

Costs: "Cost per case" table and the two alternative weightings (1 / 2 / 5, 1 / 3 / 20).
Invalid predictions get the missed-problem cost (CHANGELOG clarification, plan Q19).
Quotas: "Exception mix" table, keyed by primary exception type (plan §5.1).
Results are reported per country and overall; countries are the dataset's Hugging Face configs.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from decision_benchmark.core.generator.spec import Generation
from decision_benchmark.core.task_set import CostWeights, TaskSetSpec

from .models.common import TASK_SET_ID, Decision

D = Decimal
HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parents[1]
"""src/decision_benchmark: the root the generator's paths are relative to."""
CONTENT = HERE / "content"
TASK_DIR = HERE.relative_to(PACKAGE_ROOT).as_posix()
PIPELINE_PATHS = (
    "core/generator", f"{TASK_DIR}/models", f"{TASK_DIR}/rules", f"{TASK_DIR}/countries", f"{TASK_DIR}/content",
    f"{TASK_DIR}/generator",
    *(f"{TASK_DIR}/{name}" for name in ("__init__.py", "codes.py", "envelope.py", "fact_reader.py", "findings.py",
                                        "registry.py", "spec.py", "table_rows.py", "versions.py")),
)
"""What shapes the data (step 11 plan §8.1); B3 adds render/."""
LOCK_FILE = PACKAGE_ROOT.parents[1] / "uv.lock"


def _yaml(name: str) -> dict:
    return yaml.safe_load((CONTENT / name).read_text(encoding="utf-8"))


def generation() -> Generation:
    """The generator config from content/generator/*.yaml and content/hardcases/pairs.yaml (B1 plan §3)."""
    rules = _yaml("generator/rules.yaml")
    return Generation(
        root=str(PACKAGE_ROOT), release_seeds=f"{TASK_DIR}/content/release-seeds.yaml",
        pipeline_paths=PIPELINE_PATHS, lock_file=str(LOCK_FILE),
        two_problems=_yaml("hardcases/pairs.yaml"), rules=rules["rules"], not_counted=rules["not_counted"],
        **_yaml("generator/generation.yaml"),
    )


SPEC = TaskSetSpec(
    id=TASK_SET_ID,
    title="Supplier invoices, Malaysia and Singapore",
    spec_version="v0.10",
    decisions=tuple(d.value for d in Decision),
    approve_decision=Decision.APPROVE.value,
    trap_decisions=(Decision.REJECT_DUPLICATE.value, Decision.FRAUD_REVIEW.value),
    extra_fields=("tax_treatment", "gl_account", "reason_codes"),
    costs=(
        CostWeights(name="1/3/10", handover=D(1), false_alarm=D(3), missed=D(10)),
        CostWeights(name="1/2/5", handover=D(1), false_alarm=D(2), missed=D(5)),
        CostWeights(name="1/3/20", handover=D(1), false_alarm=D(3), missed=D(20)),
    ),
    invalid_output_is="missed",
    quotas={
        "clean": D(40),
        "tax_problem": D(10),
        "price_mismatch": D(10),
        "quantity_mismatch": D(8),
        "invalid_invoice": D(8),
        "duplicate": D(7),
        "not_received": D(5),
        "no_po_or_above_limit": D(5),
        "bank_change": D(4),
        "ambiguous": D(3),
    },
    report_by=("country",),
    output_schema="schemas/ap-invoices/v0.10/output.schema.json",
    hf_repo_id="sgsystems/decision-benchmark-ap-invoices",
    generation=generation(),
)
