"""The country-code type, country-block bases and the hook to the country packs.

Decision and Tier are defined in ../codes.py and re-exported here.

The generic base types (Model, Money, Num, internal fields, export_dict,
AnswerSource) live in decision_benchmark.core.model and are re-exported here.
Nothing in models/ names a country: country-specific types and checks come
from the country packs (../countries/), looked up by country code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AfterValidator, BeforeValidator, SerializeAsAny

from decision_benchmark.core.model import (  # noqa: F401  (re-exported)
    CENT,
    ZERO,
    AnswerSource,
    Model,
    Money,
    Num,
    export_dict,
    internal,
    is_internal,
    plain_decimal,
)

from ..codes import Decision, Tier  # noqa: F401  (re-exported)

if TYPE_CHECKING:
    from ..countries.base import CountryPack

TASK_SET_ID = "ap-invoices"


def country_pack(country: str) -> CountryPack:
    """The pack for a country code. Imported late: the packs themselves import these models."""
    from ..countries import pack

    return pack(country)


def _registered(country: str) -> str:
    country_pack(country)
    return country


CountryCode = Annotated[str, AfterValidator(_registered)]
"""A country with a country pack (a buying company's country, an invoice's country)."""


class CountryBlock(Model):
    """Base of every country-specific block (e-invoice fields, party tax facts).

    The block names its country; the country's pack says which model it is.
    """

    country: str


def _parse_block(kind: str):
    def parse(value: Any) -> Any:
        if isinstance(value, dict):
            return getattr(country_pack(value.get("country", "")), kind).model_validate(value)
        return value

    return BeforeValidator(parse)


EInvoiceBlock = Annotated[SerializeAsAny[CountryBlock], _parse_block("einvoice")]
"""Country fields of an invoice (its e-invoice standard and printed tax details): the pack's ``einvoice`` model."""

CompanyTaxFacts = Annotated[SerializeAsAny[CountryBlock], _parse_block("company_facts")]
"""Tax facts about a buying company that only its country's rules use: the pack's ``company_facts`` model."""

SupplierTaxFacts = Annotated[SerializeAsAny[CountryBlock], _parse_block("supplier_facts")]
"""Tax facts about a supplier that only the buyer country's rules use: the pack's ``supplier_facts`` model."""

ContractTaxFacts = Annotated[SerializeAsAny[CountryBlock], _parse_block("contract_facts")]
"""Facts about a contract that only one country's rules use: the pack's ``contract_facts`` model."""


class TaxProfile(Model):
    """Base of a category's tax profile in one country (the pack's ``tax_profile`` model)."""
