# Changelog

All releases of the SG Systems Decision Benchmark. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning rules:

- Any change to a rule, the decision list, the tax-treatment codes, the scoring, or any answer key is a new spec version (for example v0.9 to v0.10). Scores are compared only within one spec version.
- Patch releases (for example v0.9.1) are for card or doc changes only. Data must be byte-identical.
- Clarifications without a version bump are allowed only while no scores exist for that version.

## [v0.9.0-alpha.1] - 2026-11-13

Spec: v0.9 (synthetic, rules-based). Scores comparable with: v0.9.*

### Rules

- Tax-rule sheet v0.9, verified against the official sources on 13 Nov 2026.

### Decisions

- Nine decisions as in spec v0.9.

### Scoring

- Clarification (no version bump; no scores exist yet). The spec's cost table leaves three cases implicit. They cost:
  - a wrong non-approve decision where a different non-approve decision is right (for example DISPUTE_QUANTITY instead of DISPUTE_PRICE): 3
  - a non-approve decision other than HAND_OVER on a case where handing over is right: 3
  - APPROVE on a case where handing over is right: 10
- Tax and GL accuracy are scored over the cases an entry decided, and are always shown next to coverage.

### Data

- None yet. Train and test data are added when the generator lands, in v0.9.0.

### Card and docs

- Dataset card (card-only form), spec v0.9, tax-rule sheet v0.9, output schema v0.9.

### Tooling

- Hidden-split guard, secret scan, staging and publishing to Hugging Face.
