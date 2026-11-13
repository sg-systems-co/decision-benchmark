"""Code shared by every task set: base types, the case and answer envelopes, task-set registration.

Later builds add the generator framework (seeds, quotas, phrasebank assembler),
rendering, the scorer, results CI, the Inspect task factory, the environment
base and the grader framework here. Nothing in core may import a task set.
"""

from .case import AnswerEnvelope, CaseEnvelope, Document, Provenance
from .model import AnswerSource, Model, Money, Num, export_dict, internal
from .task_set import HAND_OVER, CostWeights, TaskSetSpec, get, register, registered

__all__ = [
    "HAND_OVER",
    "AnswerEnvelope",
    "AnswerSource",
    "CaseEnvelope",
    "CostWeights",
    "Document",
    "Model",
    "Money",
    "Num",
    "Provenance",
    "TaskSetSpec",
    "export_dict",
    "get",
    "internal",
    "register",
    "registered",
]
