"""The dataset card parses and matches the card-only (alpha) release."""

import re
from pathlib import Path

import yaml
from huggingface_hub import DatasetCard

import check_public as cp

ROOT = Path(__file__).resolve().parents[2]
CARD_PATH = ROOT / "hf/ap-invoices/README.md"


def test_card_front_matter_parses_with_huggingface_hub():
    card = DatasetCard.load(CARD_PATH)
    data = card.data.to_dict()
    assert data["license"] == "cc-by-4.0"
    assert data["language"] == ["en", "ms", "zh", "th"]
    assert data["size_categories"] == ["1K<n<10K"]
    assert "text-classification" in data["task_categories"]


def test_alpha_card_has_no_configs_and_viewer_off():
    front = yaml.safe_load(CARD_PATH.read_text().split("---\n")[1])
    assert "configs" not in front
    assert front["viewer"] is False


def test_card_text():
    text = CARD_PATH.read_text()
    assert "**Version v0.10 — synthetic, rules-based.**" in text
    assert "spec-v0.10.md" in text and "schemas/ap-invoices/v0.10/output.schema.json" in text
    for field in ("`tax_lines`", "`buyer_actions`", "`facts`"):
        assert field in text
    assert "Data not yet published." in text
    assert cp.PUBLIC_TEST_CANARY in text
    assert cp.HIDDEN_CANARY_GUID not in text
    for heading in ["## Splits", "## What a case contains", "## Output format", "## Scoring", "## Answer keys",
                    "## Limitations", "## How to submit results", "## Licence", "## Citation"]:
        assert heading in text
    assert re.search(r"author\s+=\s+\{\{SG Systems\}\}", text)


def test_card_states_review_status_plainly():
    text = CARD_PATH.read_text()
    assert "No human has reviewed the rules or the answer keys yet." in text
    assert "131 Singapore treaty-rate fields" in text and "HAND_OVER" in text
    assert "a score measures agreement with the published rules, not accuracy on real invoices" in text
    assert "Each release pins an engine version and an as-of date." in text
    assert "accountant review comes after launch" in text
