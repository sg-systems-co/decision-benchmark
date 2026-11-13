"""The TaskSetSpec of ap-invoices-my-sg, from docs/task-sets/ap-invoices-my-sg/spec-v0.9.md.

Costs: "Cost per case" table and the two alternative weightings (1 / 2 / 5, 1 / 3 / 20).
Invalid predictions get the missed-problem cost (CHANGELOG clarification, plan Q19).
Quotas: "Exception mix" table, keyed by primary exception type (plan §5.1).
"""

from __future__ import annotations

from decimal import Decimal

from decision_benchmark.core.task_set import CostWeights, TaskSetSpec

from .models.common import TASK_SET_ID, Decision

D = Decimal

SPEC = TaskSetSpec(
    id=TASK_SET_ID,
    title="Supplier invoices, Malaysia and Singapore",
    spec_version="v0.9",
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
    output_schema="schemas/ap-invoices-my-sg/v0.9/output.schema.json",
    hf_repo_id="sgsystems/decision-benchmark-ap-my-sg",
)
