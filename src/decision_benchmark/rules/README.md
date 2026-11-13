# rules

Rules engine for task set ap-invoices-my-sg. It computes every answer key from the company's policy pack and the tax-rule sheet (`docs/task-sets/ap-invoices-my-sg/tax-rules-v0.9.md`). Design: `docs/plans/step-11-plan.md` §5.

- `view.py`: `build_case_view`, the one case view both tracks share
- `fraud.py`, `duplicates.py`, `validity_sg.py`, `validity_my.py`, `tax_sg.py`, `tax_my.py`, `matching.py`, `routing.py`, `gl.py`: the checks
- `decide.py`: `compute_answer`, findings to decision by fixed priority
- `findings.py`: finding codes, tiers and order; `UnsupportedCase`
- `constants.py`: rates and thresholds with their sources
- `table_rows.py`: which tests cover each row of the rule-sheet table

The engine never guesses. A situation outside the v0.9 rules raises `UnsupportedCase`, and the generator redraws the case.
