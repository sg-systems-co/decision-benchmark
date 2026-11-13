"""Shared types for every task set: base model, exact decimals, internal fields and export.

Money and other decimals are exact. They are read from strings or ints, never
from floats, and written as strings, so JSON output is byte-stable.

A field marked with ``internal()`` is generator truth (for example a
category or a structured flag that the text only expresses). The rules
engine may read it. ``export_dict`` drops it, so it never reaches a dataset row
that a model or agent sees.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

CENT = Decimal("0.01")


class Model(BaseModel):
    """Base for every record: unknown fields are errors, instances are frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("use a string or an int for exact decimals, not a float (quote it in YAML)")
    if isinstance(value, (int, str, Decimal)):
        try:
            d = Decimal(str(value).strip())
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal number: {value!r}") from exc
        if not d.is_finite():
            raise ValueError(f"not a finite number: {value!r}")
        return d
    raise ValueError(f"not a decimal number: {value!r}")


def _to_money(value: Any) -> Decimal:
    d = _to_decimal(value)
    exponent = d.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError(f"money has at most 2 decimals: {value!r}")
    return d.quantize(CENT)


def plain_decimal(d: Decimal) -> str:
    """Decimal as a plain string without exponent or trailing zeros ("8", "2.5")."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


Money = Annotated[Decimal, BeforeValidator(_to_money), PlainSerializer(lambda d: f"{d:.2f}", return_type=str)]
"""An amount with exactly two decimals, written as "3456.00"."""

Num = Annotated[Decimal, BeforeValidator(_to_decimal), PlainSerializer(plain_decimal, return_type=str)]
"""A quantity, rate or percentage, written as a plain string ("8", "2.5")."""


def internal(default: Any = ..., **kwargs: Any) -> Any:
    """A field that holds generator truth and is dropped by export_dict."""
    return Field(default, json_schema_extra={"internal": True}, **kwargs)


def is_internal(model_cls: type[BaseModel], name: str) -> bool:
    extra = model_cls.model_fields[name].json_schema_extra
    return isinstance(extra, dict) and bool(extra.get("internal"))


def export_dict(model: BaseModel) -> dict[str, Any]:
    """JSON-ready dict of a model without its internal fields (recursively)."""
    return _strip(model, model.model_dump(mode="json"))


def _strip(value: Any, dumped: Any) -> Any:
    if isinstance(value, BaseModel):
        out = {}
        for name in type(value).model_fields:
            if is_internal(type(value), name):
                continue
            out[name] = _strip(getattr(value, name), dumped[name])
        return out
    if isinstance(value, (list, tuple)):
        return [_strip(v, d) for v, d in zip(value, dumped, strict=True)]
    if isinstance(value, dict):
        return {k: _strip(value[k], dumped[k]) for k in value}
    return dumped


class AnswerSource(StrEnum):
    """Where an answer key comes from. v0.9 has only rules-derived keys and hand-overs by construction."""

    RULES = "rules"
    HANDOVER_BY_CONSTRUCTION = "handover_by_construction"
