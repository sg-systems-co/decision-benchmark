"""Versions recorded in every answer key (spec v0.10 "Answer keys and versions", A12 plan §9).

ENGINE_VERSION is the decision-benchmark package version: an engine change that alters any answer
key needs a new one (tests/keys/test_golden_keys.py). RULES_VERSION is the rule sheet the engine
applies, the task set's spec version.
"""

from __future__ import annotations

from decision_benchmark import __version__

from .spec import SPEC

ENGINE_VERSION = __version__
RULES_VERSION = SPEC.spec_version
