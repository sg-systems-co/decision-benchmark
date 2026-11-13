# core

Code shared by every task set. The spec gives all task sets one case format, one scorer and one leaderboard; this package holds those.

- `model.py`: base model, exact decimals (`Money`, `Num`), internal fields, `export_dict`, `AnswerSource`
- `case.py`: the case envelope (`CaseEnvelope`, `Document`, `Provenance`) and the answer-key envelope (`AnswerEnvelope`)
- `task_set.py`: `TaskSetSpec` and the registry (`register`, `get`, `registered`)
- `generator/`, `scorer/`, `graders/`: later builds (see their READMEs)

Rule: nothing here imports `decision_benchmark.task_sets` or names a task set. `tests/core/test_core_isolation.py` enforces it.
