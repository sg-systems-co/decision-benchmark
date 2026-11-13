"""Shared types: base model, exact decimals, enums, internal fields and export.

Money and other decimals are exact. They are read from strings or ints, never
from floats, and written as strings, so JSON output is byte-stable.

A field marked with ``internal()`` is generator truth (for example the catalog
category of an invoice line, or the structured flags of an email). The rules
engine may read it. ``export_dict`` drops it, so it never reaches a dataset row
that a model or agent sees.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import IntEnum, StrEnum
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


class Country(StrEnum):
    MY = "MY"
    SG = "SG"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    DISPUTE_PRICE = "DISPUTE_PRICE"
    DISPUTE_QUANTITY = "DISPUTE_QUANTITY"
    HOLD_NOT_RECEIVED = "HOLD_NOT_RECEIVED"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    REQUEST_CORRECTED_INVOICE = "REQUEST_CORRECTED_INVOICE"
    FRAUD_REVIEW = "FRAUD_REVIEW"
    ROUTE_FOR_APPROVAL = "ROUTE_FOR_APPROVAL"
    HAND_OVER = "HAND_OVER"


class TaxTreatment(StrEnum):
    # Singapore GST
    CLAIMABLE = "CLAIMABLE"
    NOT_CLAIMABLE_DISALLOWED = "NOT_CLAIMABLE_DISALLOWED"
    NOT_CLAIMABLE_INVALID_INVOICE = "NOT_CLAIMABLE_INVALID_INVOICE"
    GST_WRONGLY_CHARGED = "GST_WRONGLY_CHARGED"
    NO_GST = "NO_GST"
    # Malaysia SST
    SST_CORRECT = "SST_CORRECT"
    SST_WRONG_RATE = "SST_WRONG_RATE"
    SST_SHOULD_BE_EXEMPT = "SST_SHOULD_BE_EXEMPT"
    SST_SUPPLIER_NOT_REGISTERED = "SST_SUPPLIER_NOT_REGISTERED"
    NO_SST = "NO_SST"


SG_TAX_CODES = frozenset(
    {
        TaxTreatment.CLAIMABLE,
        TaxTreatment.NOT_CLAIMABLE_DISALLOWED,
        TaxTreatment.NOT_CLAIMABLE_INVALID_INVOICE,
        TaxTreatment.GST_WRONGLY_CHARGED,
        TaxTreatment.NO_GST,
    }
)
MY_TAX_CODES = frozenset(set(TaxTreatment) - SG_TAX_CODES)


class Tier(IntEnum):
    """Decision priority from the spec: fraud, duplicate, invalid invoice, mismatch, routing."""

    FRAUD = 1
    DUPLICATE = 2
    INVALID_INVOICE = 3
    MISMATCH = 4
    ROUTING = 5


class AnswerSource(StrEnum):
    RULES = "rules"
    HANDOVER_BY_CONSTRUCTION = "handover_by_construction"
