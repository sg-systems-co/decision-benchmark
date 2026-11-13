"""Task set ap-invoices-my-sg: supplier-invoice decisions for buying companies in Malaysia and Singapore.

models/   pydantic records (company, policy pack, supplier, PO, receipt, MY and SG invoices, email, facts)
rules/    the rules engine that writes every answer key
content/  catalog (later: phrasebanks, hard-case templates, policy text, names, Typst layouts)
spec.py   this task set's TaskSetSpec, registered with core on import
"""

from decision_benchmark.core.task_set import register

from .spec import SPEC

register(SPEC)

__all__ = ["SPEC"]
