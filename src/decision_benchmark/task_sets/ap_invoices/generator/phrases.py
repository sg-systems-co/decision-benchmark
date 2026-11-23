"""Fact expressers and their parsers (B1 plan section 2.3), from the committed phrasebanks in content/phrasebanks/facts.

``express`` gives the phrase that states a fact's value; ``parse`` reads a document text back to the value. A value
is compared in its JSON form (the form gold facts take), so a date is "2025-05-03", money "1234.50", a share 0.6.
Country neutral: each country's file names its facts; the pack's line-facts model types them.
"""

from __future__ import annotations

import random
import re
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from typing import Any

import yaml

from ..countries import pack
from ..models.evidence import EVIDENCE_OPTIONAL
from ..spec import CONTENT

DATE_RE = r"\d{1,2} [A-Z][a-z]+ \d{4}"
MONEY_RE = r"\d+\.\d{2}"
SHARE_RE = r"\d{1,3}(?:\.\d+)?%"
TYPED = {"date": DATE_RE, "money": MONEY_RE, "share": SHARE_RE}


class PhraseError(ValueError):
    """A text that doesn't state the fact, or states two values."""


@cache
def bank(country: str) -> dict[str, dict]:
    path = CONTENT / "phrasebanks" / "facts" / f"{country}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))["facts"]
    fields = pack(country).line_facts_model.model_fields
    for name, spec in data.items():
        if name not in fields:
            raise ValueError(f"{path.name}: {name} is not a {country} line fact")
        if spec["kind"] in ("enum", "bool"):
            phrases = [(v, p) for v, ps in spec["values"].items() for p in ps]
            for v, p in phrases:
                for w, q in phrases:
                    if v != w and p in q:
                        raise ValueError(f"{path.name}: {name}: phrase {p!r} occurs inside {q!r}")
        elif spec["kind"] in TYPED:
            if not spec.get("templates") or any(t.count("{value}") != 1 for t in spec["templates"]):
                raise ValueError(f"{path.name}: {name}: a typed fact needs templates with one {{value}}")
        else:
            raise ValueError(f"{path.name}: {name}: unknown kind {spec['kind']}")
    return data


def json_value(country: str, fact: str, value: Any) -> Any:
    """The value as the pack's line-facts model writes it (the form of gold facts)."""
    model = pack(country).line_facts_model
    facts = model.model_validate({fact: {"value": value}}, context={EVIDENCE_OPTIONAL: True})
    return getattr(facts, fact).model_dump(mode="json")["value"]


def can_express(country: str, fact: str, value: Any) -> bool:
    spec = bank(country).get(fact)
    if spec is None:
        return False
    if spec["kind"] in TYPED:
        return True
    return json_value(country, fact, value) in [json_value(country, fact, v) for v in spec["values"]]


def express(country: str, fact: str, value: Any, r: random.Random) -> str:
    spec = bank(country).get(fact)
    if spec is None:
        raise PhraseError(f"no phrasebank entry for {country} {fact}")
    v = json_value(country, fact, value)
    if spec["kind"] in TYPED:
        return r.choice(spec["templates"]).replace("{value}", _format(spec["kind"], v))
    for key, phrases in spec["values"].items():
        if json_value(country, fact, key) == v:
            return r.choice(phrases)
    raise PhraseError(f"{country} {fact}: no phrase for {v!r}")


def parse(country: str, fact: str, text: str) -> Any:
    """The value the text states for the fact (JSON form). PhraseError if it states none or two."""
    spec = bank(country).get(fact)
    if spec is None:
        raise PhraseError(f"no phrasebank entry for {country} {fact}")
    if spec["kind"] in TYPED:
        found = set()
        for t in spec["templates"]:
            pattern = re.escape(t).replace(re.escape("{value}"), f"({TYPED[spec['kind']]})")
            found |= {_read(spec["kind"], m) for m in re.findall(pattern, text)}
    else:
        found = {json_value(country, fact, key) for key, phrases in spec["values"].items()
                 for p in phrases if _contains(text, p)}
    if len(found) != 1:
        raise PhraseError(f"{country} {fact}: {text!r} states {len(found)} values")
    value = found.pop()
    return json_value(country, fact, value) if spec["kind"] in TYPED else value


def _contains(text: str, phrase: str) -> bool:
    """The phrase stands on its own in the text (not inside a longer word)."""
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text) is not None


def _format(kind: str, v: Any) -> str:
    if kind == "date":
        d = date.fromisoformat(v)
        return f"{d.day} {d:%B %Y}"
    if kind == "share":
        return f"{(Decimal(str(v)) * 100).normalize():f}%"
    return str(v)


def _read(kind: str, text: str) -> Any:
    if kind == "date":
        return datetime.strptime(text, "%d %B %Y").date().isoformat()
    if kind == "share":
        return str(Decimal(text.rstrip("%")) / 100)
    return text


__all__ = ["PhraseError", "bank", "can_express", "express", "json_value", "parse"]
