"""Task set ap-invoices: supplier-invoice decisions for buying companies, one country pack per country.

models/     country-neutral pydantic records (company, policy pack, supplier, PO, receipt, invoice, email, facts)
countries/  one pack per country (MY, SG): tax registrations, tax codes, e-invoice fields, validity, tax
rules/      the shared rules engine that writes every answer key; tax and validity come from the pack
codes.py    every finding and reason code, and the priority table
findings.py findings, priority sort, UnsupportedCase, Unsettled, TaxResult
content/    catalog (later: phrasebanks, hard-case templates, policy text, names, Typst layouts)
spec.py     this task set's TaskSetSpec, registered with core on import
"""

from decision_benchmark.core.task_set import register

from . import countries  # noqa: F401  (loads the country packs the models look up)
from .spec import SPEC

register(SPEC)

__all__ = ["SPEC"]
