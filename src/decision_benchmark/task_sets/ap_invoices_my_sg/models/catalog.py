"""Catalog of goods and service categories (step-11 plan §7.1).

The catalog says, per category, how the tax rules treat it and which GL role it
books to. Every entry cites at least one source from the tax-rule sheet. The
file format is described in content/catalog/README.md in this task set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .common import Model

MyTaxClass = Literal["sales_5", "sales_10", "sales_exempt", "service_8", "service_6", "none"]
SgDisallowed = Literal[
    "club_subscription",
    "staff_medical",
    "motor_car",
    "family_benefit",
    "medical_accident_insurance",
    "betting",
]


class Category(Model):
    category: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["goods", "service"]
    label: str
    countries: list[Literal["MY", "SG"]] = Field(min_length=1)
    my_tax_class: MyTaxClass | None = None
    schedule_c_eligible: bool = False
    group_g: bool = False
    group_g_excluded: bool = False
    sg_disallowed: SgDisallowed | None = None
    gl_role: str
    sources: list[str] = Field(min_length=1)
    note: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> Category:
        if "MY" in self.countries and self.my_tax_class is None:
            raise ValueError(f"{self.category}: Malaysian categories need my_tax_class")
        if "MY" not in self.countries and (self.my_tax_class or self.schedule_c_eligible or self.group_g):
            raise ValueError(f"{self.category}: Malaysian tax fields on a category not used in Malaysia")
        if "SG" not in self.countries and self.sg_disallowed:
            raise ValueError(f"{self.category}: sg_disallowed on a category not used in Singapore")
        if self.group_g and (self.kind != "service" or self.my_tax_class != "service_8"):
            raise ValueError(f"{self.category}: Group G categories are services taxed at 8%")
        if self.group_g_excluded and not self.group_g:
            raise ValueError(f"{self.category}: group_g_excluded needs group_g")
        if self.schedule_c_eligible and (self.kind != "goods" or not (self.my_tax_class or "").startswith("sales_")):
            raise ValueError(f"{self.category}: Schedule C applies to goods under sales tax")
        if self.kind == "goods" and (self.my_tax_class or "").startswith("service_"):
            raise ValueError(f"{self.category}: goods can't carry a service-tax class")
        if self.kind == "service" and (self.my_tax_class or "").startswith("sales_"):
            raise ValueError(f"{self.category}: services can't carry a sales-tax class")
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
