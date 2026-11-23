"""The statement registry (B1 plan section 2.3): every line fact the generator sets is stated in exactly one governing
document, and its evidence names that document and where in it.

``state`` reads the value from the document itself, so a path's value equals the fact's value by construction.
``state_phrase`` writes a fact no structured field holds as a phrasebank phrase into a text field of the document (an
invoice line description) and cites that field; the text reads back to the value with the fact's parser
(generator/phrases.py). ``check_evidence`` is the acceptance check over a finished case: every gold fact's evidence
names a document of the case, and a path resolves in that document's exported record to the fact's value, or to a text
that parses back to it. Spans (character offsets) arrive with the full phrasebanks (B1-6).
"""

from __future__ import annotations

import re
from typing import Any, Callable

PATH_PART = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


class EvidenceError(ValueError):
    """A gold fact whose evidence doesn't resolve to its value."""


def resolve(record: Any, path: str) -> Any:
    """The value at a field path such as ``service_period_start`` or ``lines[0].description``."""
    value = record
    for name, index in PATH_PART.findall(path):
        if name:
            if not isinstance(value, dict) or name not in value:
                raise EvidenceError(f"path {path!r}: no field {name!r}")
            value = value[name]
        else:
            i = int(index)
            if not isinstance(value, list) or i >= len(value):
                raise EvidenceError(f"path {path!r}: no item {i}")
            value = value[i]
    return value


class Statements:
    """Where each document of a case lives while the case is built: doc id -> its record as a JSON-ready dict."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def document(self, doc_id: str, record: dict) -> dict:
        self.docs[doc_id] = record
        return record

    def state(self, line: dict, fact: str, doc_id: str, path: str) -> Any:
        """Record ``fact`` on an invoice line (dict) with the value the document holds at ``path``."""
        if doc_id not in self.docs:
            raise EvidenceError(f"unknown document {doc_id!r}")
        value = resolve(self.docs[doc_id], path)
        if value is None:
            raise EvidenceError(f"{doc_id}:{path} holds no value to state {fact}")
        line.setdefault("facts", {})[fact] = {"value": value, "evidence": [{"doc_id": doc_id, "path": path}]}
        return value

    def state_phrase(self, line: dict, fact: str, value: Any, phrase: str, doc_id: str, path: str) -> None:
        """Record ``fact`` on an invoice line, stated by ``phrase`` appended to the text at ``path`` of the document.
        value: the fact's value in JSON form (the phrase reads back to it)."""
        if doc_id not in self.docs:
            raise EvidenceError(f"unknown document {doc_id!r}")
        text = resolve(self.docs[doc_id], path)
        if not isinstance(text, str):
            raise EvidenceError(f"{doc_id}:{path} is not a text")
        _assign(self.docs[doc_id], path, f"{text}; {phrase}" if text else phrase)
        line.setdefault("facts", {})[fact] = {"value": value,
                                              "evidence": [{"doc_id": doc_id, "path": path, "quote": phrase}]}


def _assign(record: Any, path: str, value: Any) -> None:
    parts = PATH_PART.findall(path)
    target = record
    for name, index in parts[:-1]:
        target = target[name] if name else target[int(index)]
    name, index = parts[-1]
    if name:
        target[name] = value
    else:
        target[int(index)] = value


def check_evidence(gold_facts: list[dict] | None, docs: dict[str, dict],
                   parse: Callable[[str, str], Any] | None = None) -> list[str]:
    """Problems with a case's gold facts (the answer key's ``facts``): empty when every non-null value has evidence that
    names a case document and every path resolves there to the value, or to a text that ``parse(fact, text)`` reads
    back to the value."""
    problems = []
    for entry in gold_facts or []:
        line_no = entry.get("line_no")
        for name, fact in entry.items():
            if name == "line_no":
                continue
            value, evidence = fact.get("value"), fact.get("evidence", [])
            if value is None:
                if evidence:
                    problems.append(f"line {line_no} {name}: null value with evidence")
                continue
            if not evidence:
                problems.append(f"line {line_no} {name}: no evidence")
            for ref in evidence:
                doc = docs.get(ref["doc_id"])
                if doc is None:
                    problems.append(f"line {line_no} {name}: {ref['doc_id']} is not a document of the case")
                    continue
                if "path" in ref:
                    try:
                        found = resolve(doc, ref["path"])
                    except EvidenceError as e:
                        problems.append(f"line {line_no} {name}: {e}")
                        continue
                    if found != value and not _reads_back(parse, name, found, value):
                        problems.append(f"line {line_no} {name}: {ref['doc_id']}:{ref['path']} is {found!r}, not {value!r}")
    return problems


def _reads_back(parse: Callable[[str, str], Any] | None, fact: str, text: Any, value: Any) -> bool:
    if parse is None or not isinstance(text, str):
        return False
    try:
        return parse(fact, text) == value
    except ValueError:
        return False
