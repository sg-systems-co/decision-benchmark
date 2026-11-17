"""Every official URL the benchmark cites has an entry in docs/sources/manifest.yaml, and every
entry is cited by something. See docs/sources/README.md.

A `cited_by` item is a file path ("the file cites this URL") or "path#RULE" ("rule RULE in that file
uses this source"). Files listed under `pending_citers` are not in the repository yet."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "docs/sources/manifest.yaml").read_text(encoding="utf-8"))
P = "src/decision_benchmark/task_sets/ap_invoices"
CITING_FILES = (
    f"{P}/content/catalog/categories.yaml",
    "docs/task-sets/ap-invoices/tax-rules-v0.9.md",
    "docs/task-sets/ap-invoices/spec-v0.9.md",
    f"{P}/countries/my/constants.py",
    f"{P}/countries/sg/constants.py",
    "CHANGELOG.md",
    "docs/tax-rules-v0.10.md",
)
# URLs in those files that are not sources.
NOT_SOURCES = {"https://keepachangelog.com/en/1.1.0/"}
FIELDS = ("id", "title", "authority", "country", "official_url", "retrieved", "sha256", "bytes",
          "content_type", "archive_path", "wayback_url", "cited_by")
URL = re.compile(r"https?://[^\s<>\"'`\]]+")


def _clean(url: str) -> str:
    # Drop trailing punctuation and a closing bracket that belongs to the surrounding text.
    while True:
        if url[-1] in ".,;:":
            url = url[:-1]
        elif url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1]
        else:
            return url


def _citations() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for f in CITING_FILES:
        if not (ROOT / f).exists():  # a pending citer, committed later
            continue
        for m in URL.findall((ROOT / f).read_text(encoding="utf-8")):
            url = _clean(m)
            if url not in NOT_SOURCES:
                found.setdefault(url, set()).add(f)
    return found


SOURCES = MANIFEST["sources"]
BY_URL = {s["official_url"]: s for s in SOURCES}
PENDING = set(MANIFEST["pending_citers"])


def test_every_cited_url_has_an_entry():
    missing = sorted(set(_citations()) - set(BY_URL))
    assert not missing, f"cited but not in docs/sources/manifest.yaml: {missing}"


def test_every_entry_is_cited_and_cited_by_is_exact():
    cites = _citations()
    for s in SOURCES:
        assert s["cited_by"], f"{s['id']} is cited by nothing"
        citing = cites.get(s["official_url"], set())
        named = set()
        for c in s["cited_by"]:
            path, _, rule = c.partition("#")
            assert path in PENDING or (ROOT / path).exists(), f"{s['id']}: {path} does not exist and is not a pending citer"
            if path in PENDING:
                assert rule, f"{s['id']}: a pending citer is named with the rule that uses the source"
                continue
            named.add(path)
            if rule:  # the rule ID must appear in that file
                assert re.search(rf"\b{re.escape(rule)}\b", (ROOT / path).read_text(encoding="utf-8")), f"{s['id']}: {rule} not in {path}"
            else:  # a plain path means the file cites the URL itself
                assert path in citing, f"{s['id']}: {path} does not cite {s['official_url']}"
        assert citing <= named, f"{s['id']}: cited by {sorted(citing - named)} but cited_by does not say so"


def test_rule_ids_look_like_rule_ids():
    for s in SOURCES:
        for c in s["cited_by"]:
            if "#" in c:
                assert re.fullmatch(r"[A-Z]{1,2}-\d+", c.split("#", 1)[1]), (s["id"], c)


def test_entries_are_well_formed():
    ids = [s["id"] for s in SOURCES]
    assert len(ids) == len(set(ids)), "duplicate id"
    assert len(BY_URL) == len(SOURCES), "duplicate official_url"
    for s in SOURCES:
        assert tuple(k for k in FIELDS if k in s) == FIELDS, s["id"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s["id"]), s["id"]
        assert s["country"] in ("my", "sg") and s["authority"] in ("RMCD", "LHDN", "MOF", "IRAS", "AGC"), s["id"]
        assert s.get("available", True) in (True, False), s["id"]
        if "published" in s:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s["published"])), s["id"]
        if s["sha256"] is None:  # a failed download keeps its entry and says why
            assert s["fetch_error"] and s["archive_path"] is None, s["id"]
        else:
            assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]) and s["bytes"] > 0, s["id"]
            assert s["archive_path"].startswith(f"sources/{s['country']}/{s['authority'].lower()}/{s['id']}/{s['retrieved']}/"), s["id"]
        assert s["wayback_url"] is None or s["wayback_url"].startswith("https://web.archive.org/web/"), s["id"]


@pytest.mark.parametrize("url", ["https://example.com/a.pdf).", "https://x.gov/(gst)/page,"])
def test_url_cleaning(url):
    assert _clean(url) in ("https://example.com/a.pdf", "https://x.gov/(gst)/page")
