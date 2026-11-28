"""Branch coverage (B1-5 review): every branch the engine can decide, for every planted rule, and how often a split
plants each one (``report/branches.json``).

A branch is read off the rule's own engine code, in the files the country pack names (``engine_files``):

- a *decision*: a call that builds an outcome and names its rule in a literal (``Outcome(T.CLAIMABLE, "<rule>")``,
  ``Exempt("<rule>")``, ``ctx.wrongly_charged("<rule>")``, ``finding(..., rule="<rule>")``). A conditional outcome
  (``T.A if ... else T.B``) gives one branch per outcome; a helper called from several places gives one branch per
  call site (the fact path that led there);
- a *hand-over*: a ``NotSettled`` the code raises with its rule in a literal, plus one branch per rule for a line or
  party fact the documents don't show (read through ``fact``/``need``);
- a *path*: each return of a function the pack names as a rule's deciding function (``branch_functions``), where
  the rule's outcome turns on which return is taken (a rule's several reasons, a credit test);
- a *fact path*: a deciding fact the code reads without taking a different line of code (``branch_facts``: e.g. a
  buyer meeting the de minimis rule takes the fully taxable path), as a predicate over the planted line.

A split plants a branch in a case when re-running the engine on the case takes it: a decision or hand-over is counted
on a line it decides (the last site of the line's basis, or of an action's basis, the engine reached on that line); a
path whenever its return is taken; a fact path when its predicate holds. Generic over countries: the packs supply the
files, the call names and the predicates.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

DECISIONS = ("Outcome", "Exempt", "Taxable", "Partial", "LineResult", "BuyerAction", "finding")
"""Calls that build an outcome (the packs add their own helpers: ``branch_calls``)."""
HAND_OVERS = ("NotSettled",)
READS = ("fact", "need")
"""Line-fact reads whose rule literal is the basis of a hand-over when the fact isn't shown."""
NOT_SHOWN = "fact not shown"
COMPUTED = "*"
"""The rule of a site whose basis is computed from what a called function returns."""


@dataclass(frozen=True)
class Branch:
    id: str
    rule: str
    kind: str
    """decision | hand_over | path | fact."""
    where: str
    """module.function:line of the site (for the reader; not part of the id)."""
    outcome: str | None = None
    text: str = ""

    def export(self) -> dict:
        return {"rule": self.rule, "kind": self.kind, "where": self.where, "outcome": self.outcome, "text": self.text}


@dataclass(frozen=True)
class FactPath:
    """A deciding fact path the code takes without a separate line of code (pack ``branch_facts``)."""

    rule: str
    name: str
    text: str
    holds: Callable
    """holds(case, line_no, line_result) -> bool, on a line the rule decides."""


@dataclass
class _Site:
    key: tuple
    rule: str
    kind: str
    file: str
    function: str
    lines: tuple[int, int]
    outcomes: tuple[str | None, ...]
    via: list[tuple[str, int, tuple[int, int]]] = field(default_factory=list)
    """Call sites of the enclosing helper (file, ordinal, line range) when it has more than one."""
    text: str = ""
    computed: bool = False
    callee: str = ""
    """The call that builds the outcome (Exempt, Taxable, Outcome, ...; 'return' for a returned rule ID)."""
    """The site's rule is computed (one of the rules its function names, or any rule: COMPUTED)."""


def _name(call: ast.Call) -> str | None:
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _outcomes(call: ast.Call) -> tuple[str | None, ...]:
    """The treatments a call names: T.X, or both arms of T.X if ... else T.Y."""
    def attr(n):
        return n.attr if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "T" else None
    for a in call.args:
        if isinstance(a, ast.IfExp) and attr(a.body) and attr(a.orelse):
            return (attr(a.body), attr(a.orelse))
        if attr(a):
            return (attr(a),)
    return (None,)


def _functions(tree: ast.AST):
    """(function node, its own nodes) for every function, nested ones excluded from their parent's nodes."""
    out = []

    def own(fn):
        stack, nodes = list(ast.iter_child_nodes(fn)), []
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            nodes.append(n)
            stack.extend(ast.iter_child_nodes(n))
        return nodes

    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((n, own(n)))
    return out


class Index:
    """The branches of a country's engine, read from its files once."""

    def __init__(self, files: list[Path], rules: set[str], calls: tuple[str, ...] = (), hand_overs: tuple[str, ...] = (),
                 functions: dict[str, str] | None = None, facts: tuple[FactPath, ...] = (),
                 case_facts: tuple[FactPath, ...] = ()):
        self.case_facts = case_facts
        self.rules = rules
        decisions, handing = set(DECISIONS) | set(calls), set(HAND_OVERS) | set(hand_overs)
        self.sites: list[_Site] = []
        self.paths: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
        self.facts = facts
        self.read_rules: set[str] = set()
        functions = functions or {}
        parsed = {str(p): (p, ast.parse(p.read_text(encoding="utf-8"))) for p in files}
        sources = {f: p.read_text(encoding="utf-8").splitlines() for f, (p, _) in parsed.items()}
        modules = {f: (p.stem if p.stem != "__init__" else p.parent.name) for f, (p, _) in parsed.items()}
        callers: dict[tuple[str, str], list[tuple[str, tuple[int, int]]]] = defaultdict(list)
        for f, (_, tree) in parsed.items():
            for n in ast.walk(tree):
                if not isinstance(n, ast.Call):
                    continue
                fn = n.func
                if isinstance(fn, ast.Name):
                    target = (modules[f], fn.id)
                elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                    target = (fn.value.id, fn.attr)
                else:
                    continue
                callers[target].append((f, (n.lineno, n.end_lineno)))
        defaults: dict[str, dict[str, list[str]]] = {}
        for f, (_, tree) in parsed.items():
            for fn, _nodes in _functions(tree):
                found = [x for d in fn.args.defaults for x in _rule_literals(d, rules)]
                if found:
                    defaults.setdefault(f, {})[fn.name] = found
        for f, (p, tree) in parsed.items():
            module = p.stem if p.stem != "__init__" else p.parent.name
            for fn, nodes in _functions(tree):
                calls_here = sorted((n for n in nodes if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
                inside: list[tuple[int, int, int, int]] = []
                ordinal = Counter()
                returned = [r for r in nodes if isinstance(r, ast.Return) and _rule_literals(r.value, rules)]
                for call in sorted([*calls_here, *returned], key=lambda n: (n.lineno, n.col_offset)):
                    if isinstance(call, ast.Return):     # a rule ID returned as the basis (e.g. return "MS-4")
                        name, lits = "return", _rule_literals(call.value, rules)
                    else:
                        name = _name(call)
                        lits = [x for a in [*call.args, *(k.value for k in call.keywords)]
                                for x in _rule_literals(a, rules)]
                        if not lits and name in defaults.get(f, {}):
                            lits = defaults[f][name]           # a helper's default basis (_buyer_accounts())
                    if name in READS:
                        if lits:
                            self.read_rules.add(lits[0])
                        continue
                    if name not in decisions and name not in handing and name != "return":
                        continue
                    if not lits:
                        if name in handing or name == "finding":
                            continue                   # a hand-over or finding passing on another's rule
                        lits = _assigned_rules(call, nodes, rules)
                        if not lits:
                            continue                   # a wrapper passing on its caller's rule (ctx.exempt, ...)
                    span = (call.lineno, call.col_offset, call.end_lineno, call.end_col_offset)
                    if any(_within(span, s) for s in inside):
                        continue                       # a finding inside its Outcome: one site
                    if any(x.function == fn.name and x.file == f and x.lines[0] == call.lineno and x.callee == name
                           and x.rule in lits for x in self.sites):
                        continue                       # two actions of one rule in one statement: one site
                    inside.append(span)
                    kind = "hand_over" if name in handing else "decision"
                    computed = len(set(lits)) > 1 or lits == [COMPUTED] or (
                        name == "return" and isinstance(call.value, ast.IfExp))
                    # A helper called from several places in its own module: one branch per call site (the fact
                    # path that led there, e.g. one helper deciding three kinds of expense).
                    sites_of_fn = [c for c in callers.get((module, fn.name), []) if c[0] == f]
                    via = [(cf, k, rng) for k, (cf, rng) in enumerate(sorted(sites_of_fn), 1)] \
                        if len(sites_of_fn) > 1 else []
                    text = sources[f][call.lineno - 1].strip()
                    outcomes = _outcomes(call) if kind == "decision" and isinstance(call, ast.Call) else (None,)
                    for rule in dict.fromkeys(lits):
                        ordinal[rule] += 1
                        key = (rule, f"{module}.{fn.name}", ordinal[rule])
                        self.sites.append(_Site(key, rule, kind, f, fn.name, (call.lineno, call.end_lineno),
                                                outcomes, via, text, computed, name))
                qual = f"{module}.{fn.name}"
                if qual in functions:
                    rets = sorted((n for n in nodes if isinstance(n, ast.Return)), key=lambda n: n.lineno)
                    self.paths[(f, fn.name)] = [(r.lineno, r.end_lineno, sources[f][r.lineno - 1].strip())
                                                for r in rets]
                    self._path_rule = getattr(self, "_path_rule", {})
                    self._path_rule[(f, fn.name)] = (functions[qual], qual)
        self._by_line: dict[tuple[str, int], list[_Site]] = defaultdict(list)
        for s in self.sites:
            for ln in range(s.lines[0], s.lines[1] + 1):
                self._by_line[(s.file, ln)].append(s)
        self._path_rule = getattr(self, "_path_rule", {})
        self.files = set(parsed)

    # -- the table ----------------------------------------------------------------------------------------------------

    def branches(self) -> list[Branch]:
        out: list[Branch] = []
        for s in self.sites:
            module_fn, k = s.key[1], s.key[2]
            vias = [f"{_module(cf)}#{j}" for cf, j, _ in s.via] or [None]
            for via in vias:
                for outcome in s.outcomes:
                    bid = f"{s.rule} {module_fn}#{k}" + (f" via {via}" if via else "") + (
                        f" {outcome}" if outcome and len(s.outcomes) > 1 else "")
                    out.append(Branch(bid, s.rule, s.kind, f"{module_fn}:{s.lines[0]}", outcome, s.text))
        for (f, fn), rets in self.paths.items():
            rule, qual = self._path_rule[(f, fn)]
            for j, (start, _, text) in enumerate(rets, 1):
                out.append(Branch(f"{rule} {qual} return#{j}", rule, "path", f"{qual}:{start}", None, text))
        for rule in sorted(self.read_rules):
            out.append(Branch(f"{rule} {NOT_SHOWN}", rule, "hand_over", "", None,
                              "a line or party fact the rule reads is not shown"))
        for fp in (*self.facts, *self.case_facts):
            out.append(Branch(f"{fp.rule} fact {fp.name}", fp.rule, "fact", "", None, fp.text))
        seen, unique = set(), []
        for b in out:
            if b.id not in seen:
                seen.add(b.id)
                unique.append(b)
        return unique

    # -- tracing ------------------------------------------------------------------------------------------------------

    def trace(self, run: Callable[[], object]):
        """Run the engine; returns (its result, [(line_no or None, site, via ordinal or None)], [path branch ids])."""
        hits: list[tuple[int | None, _Site, int | None]] = []
        frames: list = []
        """The frame each hit came from (kept alive for the run, so two calls never share an identity)."""
        paths: list[tuple[int | None, str]] = []
        files = self.files
        by_line, path_rets, path_rule = self._by_line, self.paths, self._path_rule

        def line_no(frame) -> int | None:
            ctx = frame.f_locals.get("ctx")
            line = getattr(ctx, "line", None)
            return getattr(line, "line_no", None)

        def local(frame, event, arg):
            f = frame.f_code.co_filename
            if event == "line":
                for s in by_line.get((f, frame.f_lineno), ()):
                    if s.function != frame.f_code.co_name:
                        continue
                    via = None
                    if s.via:
                        back = frame.f_back
                        for cf, j, (a, b) in s.via:
                            if back is not None and back.f_code.co_filename == cf and a <= back.f_lineno <= b:
                                via = j
                                break
                    if not hits or hits[-1][1] is not s or hits[-1][0] != line_no(frame):
                        hits.append((line_no(frame), s, via))
                        frames.append(frame)
            elif event == "return":
                _settle(frame, arg)
                rets = path_rets.get((f, frame.f_code.co_name))
                if rets:
                    for j, (a, b, _) in enumerate(rets, 1):
                        if a <= frame.f_lineno <= b:
                            rule, qual = path_rule[(f, frame.f_code.co_name)]
                            paths.append((line_no(frame), f"{rule} {qual} return#{j}"))
                            break
            return local

        def _settle(frame, value) -> None:
            """Sites built in one statement (Exempt(...) if x else Taxable(...)): keep the one the frame returned."""
            k = len(hits)
            while k > 0 and frames[k - 1] is frame and hits[k - 1][1].lines == hits[-1][1].lines:
                k -= 1
            group = hits[k:]
            if len(group) < 2:
                return
            basis = value if isinstance(value, str) else getattr(value, "basis", None)
            keep = [h for h in group if h[1].rule == basis] or group
            if len(keep) > 1:
                keep = [h for h in keep if h[1].callee == type(value).__name__ or h[1].callee == "return"] or keep[-1:]
            del hits[k:], frames[k:]
            hits.extend(keep)
            frames.extend([frame] * len(keep))

        def glob(frame, event, arg):
            if event == "call" and frame.f_code.co_filename in files:
                return local
            return None

        old = sys.gettrace()
        sys.settrace(glob)
        try:
            result = run()
        finally:
            sys.settrace(old)
        return result, hits, paths

    @staticmethod
    def site_branch(s: _Site, via: int | None, outcome: str | None) -> str:
        module_fn, k = s.key[1], s.key[2]
        bid = f"{s.rule} {module_fn}#{k}"
        if s.via and via is not None:
            cf = next(c for c, j, _ in s.via if j == via)
            bid += f" via {_module(cf)}#{via}"
        if outcome and len(s.outcomes) > 1:
            bid += f" {outcome}"
        return bid


def _assigned_rules(call: ast.Call, nodes, rules: set[str]) -> list[str]:
    """The rules a computed basis can take: a variable the call reads, assigned rule literals in the function
    (``basis = "MS-2"``, ``rate, basis = old, ("MS-3" if ... else "MS-2")``)."""
    names = {a.id for a in [*call.args, *(k.value for k in call.keywords)] if isinstance(a, ast.Name)}
    out: list[str] = []
    # The assignments before the call, in order; one that assigns no rule ID (a computed value) replaces those before.
    for n in sorted((n for n in nodes if isinstance(n, ast.Assign) and n.lineno < call.lineno), key=lambda n: n.lineno):
        for target in n.targets:
            pairs = [(target, n.value)]
            if isinstance(target, ast.Tuple) and isinstance(n.value, ast.Tuple):
                pairs = list(zip(target.elts, n.value.elts))
            elif isinstance(target, ast.Tuple):
                pairs = [(t, None) for t in target.elts]
            for t, v in pairs:
                if isinstance(t, ast.Name) and t.id in names:
                    found = _rule_literals(v, rules) if v is not None else []
                    out = out + found if found else []
    return list(dict.fromkeys(out))


def _module(path: str) -> str:
    p = Path(path)
    return p.stem if p.stem != "__init__" else p.parent.name


def _rule_literals(node, rules: set[str]) -> list[str]:
    if isinstance(node, ast.Constant) and node.value in rules:
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _rule_literals(node.body, rules) + _rule_literals(node.orelse, rules)
    return []


def _within(inner, outer) -> bool:
    return (outer[0], outer[1]) <= (inner[0], inner[1]) and (inner[2], inner[3]) <= (outer[2], outer[3])


def case_branches(index: Index, tax, hits, paths, case, handover: bool) -> set[str]:
    """The branches one case plants: tax is the engine's TaxResult for the case (its lines and findings)."""
    out: set[str] = set()
    for lr in tax.lines:
        rules = {lr.basis} | {a.basis for a in lr.buyer_actions if getattr(a, "basis", None)}
        for rule in rules:
            want = "hand_over" if lr.treatment is None and rule == lr.basis else "decision"
            found = None
            for ln, s, via in hits:
                if s.rule in (rule, COMPUTED) and s.kind == want and ln in (lr.line_no, None):
                    found = (s, via)
            if found is not None:
                s, via = found
                out.add(Index.site_branch(s, via, lr.treatment if rule == lr.basis else None))
            elif want == "hand_over":
                out.add(f"{rule} {NOT_SHOWN}")
        for fp in index.facts:
            if fp.holds(case, lr.line_no, lr):
                out.add(f"{fp.rule} fact {fp.name}")
    for f in tax.findings:
        rule = (f.evidence or {}).get("rule") or (f.evidence or {}).get("basis")
        if rule in index.rules:
            found = [(s, via) for ln, s, via in hits if s.rule == rule and s.kind == "decision"]
            if found:
                out.add(Index.site_branch(found[-1][0], found[-1][1], None))
    if handover:
        for ln, s, via in hits:
            if s.kind == "hand_over":
                out.add(Index.site_branch(s, via, None))
    for fp in index.case_facts:
        if fp.holds(case, None, tax):
            out.add(f"{fp.rule} fact {fp.name}")
    out.update(bid for _, bid in paths)
    return out


_INDEX: dict[tuple[str, frozenset], Index] = {}


def index_for(country: str, rules: set[str]) -> Index:
    """The country's branch index (from its pack's engine files and branch hooks), built once."""
    from ..countries import pack

    key = (country, frozenset(rules))
    if key not in _INDEX:
        g = pack(country).generation
        _INDEX[key] = Index(list(g.engine_files), rules, g.branch_calls, g.branch_hand_overs, g.branch_functions,
                            tuple(FactPath(*f) for f in g.branch_facts),
                            tuple(FactPath(*f) for f in getattr(g, "branch_case_facts", ())))
    return _INDEX[key]


def coverage(gen, cases) -> dict:
    """{country: {branch id: {rule, kind, where, outcome, text, cases}}} for the built cases: every branch of every
    country whose pack plants rules, with the number of cases that plant it (generator/branches.py)."""
    from ..countries import pack
    from ..rules import build_case_view
    from .entities import catalog

    rules = {r.id for r in gen.rules}
    countries = sorted({r.country for r in gen.rules if pack(r.country).generation.plants_rules})
    counts: dict[str, Counter] = {c: Counter() for c in countries}
    for g in cases:
        c = g.envelope.country
        if c not in counts:
            continue
        index = index_for(c, rules)
        view = build_case_view(g.records, g.envelope)
        tax, hits, paths = index.trace(lambda: pack(c).assess_tax(view, catalog()))
        counts[c].update(case_branches(index, tax, hits, paths, g, g.answer.decision == "HAND_OVER"))
    out: dict[str, dict] = {}
    for c in countries:
        index = index_for(c, rules)
        known = {b.id for b in index.branches()}
        unknown = set(counts[c]) - known
        if unknown:
            raise ValueError(f"{c}: branches taken that the index doesn't list: {sorted(unknown)}")
        why = reasons()
        out[c] = {b.id: b.export() | {"cases": counts[c][b.id],
                                      "reason": reason_for(c, b.export(), b.id, why)} for b in index.branches()}
    return out


HAND_OVER_ONLY = ("HAND_OVER only: hand-overs are planted in Ambiguous cases only (planting limit 5's treaty rows; "
                  "B1-6 adds the missing-information cases)")


def reasons() -> dict[str, dict[str, str]]:
    """content/generator/branch_reasons.yaml: {country: {branch id: why the splits don't plant it at the floor}}."""
    import yaml

    from ..spec import CONTENT

    return yaml.safe_load((CONTENT / "generator" / "branch_reasons.yaml").read_text(encoding="utf-8"))


def reason_for(country: str, branch: dict, bid: str, why: dict[str, dict[str, str]]) -> str | None:
    if bid in why.get(country, {}):
        return why[country][bid]
    return HAND_OVER_ONLY if branch["kind"] == "hand_over" else None


__all__ = ["Branch", "FactPath", "HAND_OVER_ONLY", "Index", "case_branches", "coverage", "index_for", "reason_for",
           "reasons"]
