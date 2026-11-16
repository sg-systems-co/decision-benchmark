# rules

Shared rules engine for task set ap-invoices. It computes every answer key from the company's policy pack and the tax-rule sheet (`docs/task-sets/ap-invoices/tax-rules-v0.9.md`). Design: `docs/plans/step-11-plan.md` §5.

- `view.py`: `build_case_view`, the one case view both tracks share; `view.pack` is the invoice country's pack
- `fraud.py`, `duplicates.py`, `matching.py`, `routing.py`, `gl.py`: the checks every country shares
- `decide.py`: `compute_answer`; asks the country pack for validity findings and the tax treatment, then sets the decision by fixed priority

Country-specific validity and tax live in `../countries/<cc>/` (`validity.py`, `tax.py`, `constants.py`). Codes and the priority table are in `../codes.py`; findings, `UnsupportedCase` and `Unsettled` in `../findings.py`. `tests/rules/test_shared_code.py` fails if a file here names a country.

The engine never guesses. A situation outside the v0.9 rules raises `UnsupportedCase`, and the generator redraws the case.
