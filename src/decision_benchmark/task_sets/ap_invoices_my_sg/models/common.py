"""Task-set enums: countries, decisions, tax codes, priority tiers.

The generic base types (Model, Money, Num, internal fields, export_dict,
AnswerSource) live in decision_benchmark.core.model and are re-exported here.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from decision_benchmark.core.model import (  # noqa: F401  (re-exported)
    CENT,
    AnswerSource,
    Model,
    Money,
    Num,
    export_dict,
    internal,
    is_internal,
    plain_decimal,
)


TASK_SET_ID = "ap-invoices-my-sg"


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
