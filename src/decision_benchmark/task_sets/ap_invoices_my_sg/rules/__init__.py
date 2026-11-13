"""Rules engine: computes every answer key from the policy pack and tax-rules-v0.9.md.

Pure functions, no I/O. Entry points:

- ``build_case_view(records, case)``: what the case knows (shared by both tracks)
- ``compute_answer(view, catalog)``: the answer key, or ``UnsupportedCase``
- ``answer_case(records, case, catalog)``: both in one call
"""

from ..models import AnswerKey, Case, Catalog, CompanyRecords
from .decide import compute_answer
from .findings import UnsupportedCase, Unsettled
from .view import CaseView, build_case_view


def answer_case(records: CompanyRecords, case: Case, catalog: Catalog) -> AnswerKey:
    return compute_answer(build_case_view(records, case), catalog)


__all__ = ["CaseView", "UnsupportedCase", "Unsettled", "answer_case", "build_case_view", "compute_answer"]
