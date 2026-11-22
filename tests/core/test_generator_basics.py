"""Generic generator pieces: derived seeds, exact counts, the pipeline hash (step 11 plan §8.1, §5.1)."""

from fractions import Fraction

import pytest

from decision_benchmark.core.generator.provenance import pipeline_hash
from decision_benchmark.core.generator.quotas import InfeasibleDemand, apportion, halves, share_of
from decision_benchmark.core.generator.seeds import derive, rng


def test_derive_is_stable_and_purpose_specific():
    assert derive(42, 7, "lines") == derive(42, 7, "lines")
    assert derive(42, 7, "lines") != derive(42, 7, "dates") != derive(43, 7, "lines")
    assert derive(42, "a", "bc") != derive(42, "ab", "c")          # parts are separated, not concatenated
    assert 0 <= derive(1) < 2**64
    a, b = rng(5, "x"), rng(5, "x")
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]


def test_derive_known_value():
    # Pinned so a change to the derivation can't pass unnoticed (it would change every build).
    assert derive(2026112201, "slots", "order") == 0xb452b3eaa416a49


def test_apportion_is_exact_with_ties_to_the_earlier_key():
    assert apportion(10, {"a": 1, "b": 1, "c": 1}) == {"a": 4, "b": 3, "c": 3}
    assert apportion(7, {"a": "2/3", "b": "1/3"}) == {"a": 5, "b": 2}
    counts = apportion(1000, {str(i): i for i in range(1, 30)})
    assert sum(counts.values()) == 1000
    assert apportion(0, {"a": 1}) == {"a": 0}
    with pytest.raises(InfeasibleDemand):
        apportion(3, {"a": 0})


def test_share_of_must_be_whole():
    assert share_of(2000, "40") == 800 and share_of(300, Fraction(3)) == 9
    with pytest.raises(InfeasibleDemand, match="not a whole number"):
        share_of(250, "15")


def test_halves_keep_totals_even():
    out = halves({"a": 35, "b": 25, "c": 25, "d": 15}, ("X", "Y"))
    assert out["a"] == {"X": 18, "Y": 17} and out["b"] == {"X": 12, "Y": 13}
    assert sum(v["X"] for v in out.values()) == sum(v["Y"] for v in out.values()) == 50


def test_pipeline_hash_names_every_file(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.py").write_text("1")
    (tmp_path / "a" / "__pycache__").mkdir()
    (tmp_path / "a" / "__pycache__" / "x.pyc").write_bytes(b"cache")
    (tmp_path / "lock").write_text("pinned")
    h = pipeline_hash(tmp_path, ["a"])
    assert h == pipeline_hash(tmp_path, ["a"])
    (tmp_path / "a" / "__pycache__" / "x.pyc").write_bytes(b"other")
    assert pipeline_hash(tmp_path, ["a"]) == h                    # caches don't count
    assert pipeline_hash(tmp_path, ["a"], {"uv.lock": tmp_path / "lock"}) != h
    (tmp_path / "a" / "x.py").write_text("2")
    assert pipeline_hash(tmp_path, ["a"]) != h
    with pytest.raises(FileNotFoundError):
        pipeline_hash(tmp_path, ["missing"])
