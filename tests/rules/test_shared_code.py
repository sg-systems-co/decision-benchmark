"""Shared models and rules know no country; every country pack fills the same interface; constants are defined once."""

import ast
import json
import re
from pathlib import Path

from decision_benchmark.task_sets.ap_invoices.countries import PACKS, CountryPack, TaxTreatment
from decision_benchmark.task_sets.ap_invoices.models import CountryBlock, TaxProfile

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src/decision_benchmark"
TASK = PKG / "task_sets/ap_invoices"
SHARED = sorted(
    [*(TASK / "rules").glob("*.py"), *(TASK / "models").glob("*.py"), TASK / "findings.py", TASK / "envelope.py",
     TASK / "registry.py", TASK / "fact_reader.py"]
)
COUNTRY_WORDS = re.compile(
    r"\b(MY|SG|TH|MYR|SGD|THB)\b|GST|SST|Malaysia|Singapore|Thai|MyInvois|PINT|Peppol|IRAS|Schedule C|Group G",
    re.IGNORECASE,
)
COUNTRY_CODES = re.compile(r"\b(MY|SG|TH|MYR|SGD|THB)\b")


def test_shared_models_and_rules_name_no_country():
    assert SHARED
    for path in SHARED:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hit = COUNTRY_CODES.search(line) or COUNTRY_WORDS.search(line)
            assert not hit, f"{path.relative_to(TASK)}:{n}: {line.strip()}"


def test_shared_code_does_not_import_a_country_pack_directly():
    for path in SHARED:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"countries\.(my|sg)\b|countries import (my|sg)\b", text), path.name


def test_constants_are_defined_once():
    """A module-level UPPER_CASE name is assigned in one module only (others import it). PACK is the pack protocol."""
    where: dict[str, list[str]] = {}
    for path in sorted([*(PKG / "core").rglob("*.py"), *(PKG / "task_sets").rglob("*.py")]):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for t in targets:
                if isinstance(t, ast.Name) and t.id.isupper() and t.id != "PACK":
                    where.setdefault(t.id, []).append(str(path.relative_to(PKG)))
    dupes = {name: files for name, files in where.items() if len(files) > 1}
    assert not dupes, dupes


def test_every_pack_fills_the_interface():
    codes_seen: set[str] = set()
    for country, pack in PACKS.items():
        assert isinstance(pack, CountryPack) and pack.country == country
        assert re.fullmatch(r"[A-Z]{3}", pack.currency)
        assert all(scheme.startswith(f"{country}_") and types for scheme, types in pack.registration_types.items())
        for block in (pack.einvoice, pack.company_facts, pack.supplier_facts):
            assert issubclass(block, CountryBlock) and block.model_fields["country"].default == country
        assert issubclass(pack.tax_profile, TaxProfile)
        codes = {str(c) for c in pack.tax_codes}
        assert codes and not codes & codes_seen, "tax-treatment codes must be unique across packs"
        codes_seen |= codes
        assert type(pack).validity is not CountryPack.validity
        assert type(pack).assess_tax is not CountryPack.assess_tax
        assert pack.constants.__name__.endswith(f".{country.lower()}.constants")


def test_tax_codes_match_the_output_schema():
    """Each pack's codes are its v0.10 schema part's $defs/tax_code. Singapore gains its new v0.10 codes in A12
    build PR 3; until then its codes are a subset."""
    for country, pack in PACKS.items():
        part = json.loads((ROOT / f"schemas/ap-invoices/v0.10/countries/{country.lower()}.schema.json").read_text())
        codes = {c["const"] for c in part["$defs"]["tax_code"]["oneOf"]}
        mine = {str(c) for c in pack.tax_codes}
        assert mine == codes if country == "MY" else mine <= codes, country
