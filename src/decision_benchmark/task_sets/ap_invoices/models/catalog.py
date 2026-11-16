"""Catalog of item and service categories (step-11 plan §7.1).

A category is used in one or more countries. Its tax profile in each country
comes from that country's pack (``tax_profile``). The file format is described
in content/catalog/README.md in this task set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, SerializeAsAny, field_validator, model_validator

from .common import CountryCode, Model, TaxProfile, country_pack


class Category(Model):
    category: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["goods", "service"]
    label: str
    countries: list[CountryCode] = Field(min_length=1)
    tax: dict[str, SerializeAsAny[TaxProfile]] = {}
    """Country code -> tax profile. A country whose pack needs a profile must have one."""
    gl_role: str
    sources: list[str] = Field(min_length=1)
    note: str = ""

    @field_validator("tax", mode="before")
    @classmethod
    def _profiles(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {
            country: country_pack(country).tax_profile.model_validate(p) if isinstance(p, dict) else p
            for country, p in value.items()
        }

    @model_validator(mode="after")
    def _consistent(self) -> Category:
        extra = set(self.tax) - set(self.countries)
        if extra:
            raise ValueError(f"{self.category}: tax profile for {sorted(extra)}, where the category is not used")
        for country in self.countries:
            country_pack(country).check_category(self)
        if any(not s.startswith("https://") for s in self.sources):
            raise ValueError(f"{self.category}: sources must be https URLs")
        return self


class Catalog(Model):
    version: int
    categories: list[Category]

    @model_validator(mode="after")
    def _unique(self) -> Catalog:
        names = [c.category for c in self.categories]
        if len(names) != len(set(names)):
            raise ValueError("duplicate category names")
        return self

    def get(self, name: str) -> Category:
        for c in self.categories:
            if c.category == name:
                return c
        raise KeyError(f"unknown catalog category: {name}")


def load_catalog(path: Path) -> Catalog:
    return Catalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
