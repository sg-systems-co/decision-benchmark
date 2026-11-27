"""The family templates (content/hardcases/*.yaml, step 11 plan §7.2) and the two-problem pairs.

A template is data: params with their ranges, a list of named ops (generator/ops.py) whose arguments may name a param
as "{name}", and ``expect``, an assertion on the engine's answer (decision and finding codes), never the answer itself.
The loader checks every op and argument, and the pairs: a (primary, secondary) pair of types is usable only if some
family of each can apply together (neither removes what the other needs).
"""

from __future__ import annotations

import random
import re
from functools import cache
from typing import Any

import yaml
from pydantic import model_validator

from ..models import Model
from ..spec import CONTENT
from .ops import OPS, Draft

PARAM_REF = re.compile(r"^\{(\w+)\}$")


class ParamSpec(Model):
    int_range: tuple[int, int] | None = None
    choice: list[Any] | None = None

    @model_validator(mode="after")
    def _one(self) -> ParamSpec:
        if (self.int_range is None) == (self.choice is None):
            raise ValueError("a param has exactly one of int_range or choice")
        return self

    def draw(self, r: random.Random) -> Any:
        if self.int_range is not None:
            return r.randint(*self.int_range)
        assert self.choice is not None
        return r.choice(self.choice)


class OpCall(Model):
    op: str
    args: dict[str, Any] = {}


class Expect(Model):
    decision: str
    findings: list[str] = []


class Template(Model):
    family: str
    version: int
    countries: list[str]
    primary_type: str | None
    """The exception type the family is drawn for; None: it is planted only where a slot names its rule."""
    rule: str | None = None
    """The rule a tax family plants (rules.yaml id)."""
    supplier: str = ""
    """The special supplier kind the family needs ('' any)."""
    foreign: bool | None = None
    """The family needs a foreign (True) or domestic (False) supplier; None: either."""
    companies: list[str] = []
    """The company kinds the family needs (empty: any but a hand-over kind, generation.yaml handover_companies)."""
    weight: int = 1
    summary: str
    params: dict[str, ParamSpec] = {}
    ops: list[OpCall]
    expect: Expect

    @model_validator(mode="after")
    def _ops(self) -> Template:
        for call in self.ops:
            spec = OPS.get(call.op)
            if spec is None:
                raise ValueError(f"{self.family}: unknown op {call.op}")
            if set(call.args) != set(spec.params):
                raise ValueError(f"{self.family}: {call.op} takes {sorted(spec.params)}, got {sorted(call.args)}")
            for value in call.args.values():
                m = PARAM_REF.match(str(value))
                if m and m.group(1) not in self.params:
                    raise ValueError(f"{self.family}: {call.op} names unknown param {m.group(1)}")
        return self

    @property
    def requires(self) -> frozenset[str]:
        return frozenset().union(*(OPS[c.op].requires for c in self.ops))

    @property
    def removes(self) -> frozenset[str]:
        return frozenset().union(*(OPS[c.op].removes for c in self.ops))

    def compatible(self, other: Template) -> bool:
        """Both families can apply to one case (in either order)."""
        return not (self.requires & other.removes) and not (other.requires & self.removes)

    def calls(self, r: random.Random) -> list[tuple[str, dict]]:
        """The ops with their arguments, params drawn."""
        drawn = {name: spec.draw(r) for name, spec in sorted(self.params.items())}
        out = []
        for call in self.ops:
            args = {}
            for k, v in call.args.items():
                m = PARAM_REF.match(str(v))
                args[k] = drawn[m.group(1)] if m else v
            out.append((call.op, args))
        return out


@cache
def templates() -> dict[str, list[Template]]:
    """Families by primary type."""
    out: dict[str, list[Template]] = {}
    for path in sorted((CONTENT / "hardcases").glob("*.yaml")):
        if path.name == "pairs.yaml":
            continue
        t = Template.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if t.family != path.stem:
            raise ValueError(f"{path.name}: family {t.family} must match the file name")
        if t.primary_type is not None:
            out.setdefault(t.primary_type, []).append(t)
    return out


@cache
def rule_families() -> dict[str, Template]:
    """The family of each rule (rule id -> template), drawn or not."""
    out: dict[str, Template] = {}
    for path in sorted((CONTENT / "hardcases").glob("*.yaml")):
        if path.name == "pairs.yaml":
            continue
        t = Template.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if t.rule is not None:
            if t.rule in out:
                raise ValueError(f"rule {t.rule} has two families")
            out[t.rule] = t
    return out


def check_pairs(pairs: tuple[tuple[str, str], ...]) -> list[str]:
    """Pairs no family combination can build (empty: every pair is usable)."""
    fams = templates()
    bad = []
    for p, s in pairs:
        if not any(a.compatible(b) for a in fams.get(p, []) for b in fams.get(s, [])):
            bad.append(f"{p}+{s}")
    return bad


def apply(d: Draft, families: list[tuple[Template, list[tuple[str, dict]]]]) -> None:
    """Apply the families' ops: early ones (a rule's line) first, then primary, then secondary; ops marked late (copies
    of the finished invoice) last."""
    calls = [call for _, cs in families for call in cs]
    early = [c for c in calls if OPS[c[0]].early]
    late = [c for c in calls if OPS[c[0]].late]
    rest = [c for c in calls if c not in early and c not in late]
    d.refresh()                                   # amounts as the lines stand (a rule recipe changed rates)
    for name, args in early + rest + late:
        OPS[name].fn(d, **args)
        d.refresh()
    d.finish()


def requires_taxed_line(families: list[Template]) -> bool:
    return any("taxed_line" in t.requires for t in families)


__all__ = ["ParamSpec", "Template", "apply", "check_pairs", "requires_taxed_line", "rule_families", "templates"]
