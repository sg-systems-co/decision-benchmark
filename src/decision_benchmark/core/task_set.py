"""Task-set registration.

Each task set describes itself with one TaskSetSpec and registers it. Shared
code (scorer, results CI, Inspect tasks, release) looks a task set up by id and
reads everything task-specific from its spec. Core never imports a task set;
`import decision_benchmark.task_sets` registers all of them.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, model_validator

from .case import AnswerEnvelope
from .model import Model, Num

HAND_OVER = "HAND_OVER"


class CostWeights(Model):
    """Cost per case for one weighting. A right decision, and HAND_OVER where handing over is right, cost 0."""

    name: str
    handover: Num
    """HAND_OVER on a case where handing over is not the right answer."""
    false_alarm: Num
    """A wrong non-approve decision (wrong hold, dispute or route)."""
    missed: Num
    """A wrong approve decision (a missed problem)."""


class TaskSetSpec(Model):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str
    spec_version: str
    decisions: tuple[str, ...]
    approve_decision: str
    """The decision that lets the item through; wrong ones count as missed problems."""
    trap_decisions: tuple[str, ...]
    """Right decisions on trap cases. Approving such a case is also a critical error."""
    extra_fields: tuple[str, ...]
    """Scored answer fields besides the decision, in output order."""
    costs: tuple[CostWeights, ...]
    """The leaderboard weighting first, then the alternatives."""
    invalid_output_is: str = "missed"
    """Which cost a schema-breaking, missing or duplicate prediction gets (CostWeights field name)."""
    quotas: dict[str, Num]
    """Share of cases (percent) per primary exception type. Sums to 100."""
    output_schema: str
    """Path of the output JSON schema, relative to the repository root."""
    hf_repo_id: str

    @model_validator(mode="after")
    def _consistent(self) -> TaskSetSpec:
        if len(set(self.decisions)) != len(self.decisions):
            raise ValueError("duplicate decision")
        if HAND_OVER not in self.decisions:
            raise ValueError("every task set offers HAND_OVER")
        if self.approve_decision not in self.decisions:
            raise ValueError("approve_decision is not a decision")
        if not set(self.trap_decisions) <= set(self.decisions) - {self.approve_decision, HAND_OVER}:
            raise ValueError("trap_decisions must be decisions other than approve and HAND_OVER")
        if not self.costs:
            raise ValueError("at least one cost weighting")
        if self.invalid_output_is not in ("handover", "false_alarm", "missed"):
            raise ValueError("invalid_output_is names a CostWeights field")
        if sum(self.quotas.values(), Decimal(0)) != 100:
            raise ValueError("quotas must sum to 100")
        return self

    def check_answer(self, answer: AnswerEnvelope) -> None:
        """Raise ValueError if an answer-key envelope does not fit this task set."""
        if answer.task_set != self.id:
            raise ValueError(f"answer is for task set {answer.task_set}, not {self.id}")
        if answer.decision not in self.decisions:
            raise ValueError(f"unknown decision {answer.decision}")
        if tuple(answer.answer) != self.extra_fields:
            raise ValueError(f"answer fields {list(answer.answer)} differ from {list(self.extra_fields)}")


_REGISTRY: dict[str, TaskSetSpec] = {}


def register(spec: TaskSetSpec) -> TaskSetSpec:
    existing = _REGISTRY.get(spec.id)
    if existing is not None and existing != spec:
        raise ValueError(f"task set {spec.id} is already registered with a different spec")
    _REGISTRY[spec.id] = spec
    return spec


def get(task_set_id: str) -> TaskSetSpec:
    try:
        return _REGISTRY[task_set_id]
    except KeyError:
        raise KeyError(f"unknown task set {task_set_id!r}; import decision_benchmark.task_sets first") from None


def registered() -> list[str]:
    return sorted(_REGISTRY)
