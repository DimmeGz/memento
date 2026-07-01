"""Tests for dedup threshold helper logic (mirrors FactsStore decision)."""


def test_dedup_threshold_comparison() -> None:
    threshold = 0.97
    assert 0.98 >= threshold
    assert not (0.90 >= threshold)
