# Sources

The answer keys follow the official rules of the Royal Malaysian Customs Department (RMCD), the Inland Revenue Board of Malaysia (LHDN), the Ministry of Finance Malaysia (MOF) and the Inland Revenue Authority of Singapore (IRAS). Government sites move and replace files. So we keep a copy of every source we cite, and this folder records exactly which version we used.

## The manifest

[`manifest.yaml`](manifest.yaml) has one entry per source:

| Field | Meaning |
|---|---|
| `id` | Stable name for the source. |
| `title`, `authority`, `country` | What the document is and who publishes it. |
| `official_url` | Where we downloaded it. This is the URL the benchmark cites. |
| `retrieved` | The date we downloaded it. |
| `sha256`, `bytes`, `content_type` | The fingerprint, size and type of the file exactly as downloaded. |
| `archive_path` | Where our copy is kept (see below). |
| `wayback_url` | A snapshot in the Internet Archive, or `null` if the capture failed. |
| `cited_by` | Who uses it. A file path means the file cites the URL. `path#RULE` means rule RULE in that file (for example `docs/tax-rules-v0.10.md#K-1`) relies on it. |

Some entries also have:

| Field | Meaning |
|---|---|
| `published` | The publication date the authority gives, for example in the MySST policy tables. |
| `available: false` | The authority no longer serves the document. We keep the entry and our copy. |
| `fetch_error`, `attempts` | Why a download failed and what we tried: a retry, an official alternative host, and a real browser. |
| `note` | Anything a reader should know, such as a moved page or a site's labelling error. |

A source we could not download keeps its entry, with `sha256: null`.

`pending_citers` lists files that cite sources but are not in this repository yet. At present there are none: the v0.10 rule sheet, `docs/tax-rules-v0.10.md`, is committed, and the test checks that every rule ID named in `cited_by` appears in it.

## Data tables

Some sources are tables that the engine reads as data: tax-treaty withholding rates and tariff-code lists. They live in the country packs as `countries/<country>/data/*.yaml`. Each file names its manifest IDs in its header, and every row has a `source`. `tests/test_country_data_sources.py` checks both. The private archive's `scripts/extract_tables.py` generates these files from the archived documents.

The copies themselves are not in this repository. Government documents are kept in a separate private archive under `archive_path`. This repository holds only the metadata. For an HTML page, the archive also has a PDF print of the page as we saw it.

## Checking a document

1. Download it from `official_url`. If that no longer works, use `wayback_url`.
2. Compute its SHA-256, for example with `shasum -a 256 file.pdf` or `sha256sum file.pdf`.
3. Compare the result with `sha256`. If they match, you have the exact file the answer keys were built from.

PDFs normally match byte for byte. HTML pages can differ even when nothing visible changed, because some sites add timestamps or tokens to each response. For an HTML page, compare the text instead.

## Keeping it current

A weekly job in the private archive downloads every `official_url` again.
- **The source changed:** it saves the new version next to the old one and opens an issue there. A changed source may mean the law changed, so it needs review before any data release.
- **The source is unreachable:** it opens an issue instead.

The job never edits this manifest. Any change here is made by hand.

A test (`tests/test_sources_manifest.py`) fails if a cited URL has no entry here, or if an entry is cited by nothing.
