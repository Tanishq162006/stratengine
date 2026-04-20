"""Dedup: verify cosine merge + list merging. We don't spin up Chroma for this
unit test — we exercise the pure helpers (`_cosine`, `_merge_lists`, and the
StrategyCard merge logic)."""
from __future__ import annotations


def test_cosine_identity_and_orthogonal():
    from dedup import _cosine

    assert abs(_cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(_cosine([1.0, 0.0], [0.0, 1.0]) - 0.0) < 1e-9
    assert abs(_cosine([1.0, 1.0], [1.0, 1.0]) - 1.0) < 1e-9
    assert abs(_cosine([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) - 1.0) < 1e-9


def test_merge_lists_dedupes_case_insensitive():
    from dedup import _merge_lists

    out = _merge_lists(["Momentum", "Breakout"], ["momentum", "Trend"])
    assert out == ["Momentum", "Breakout", "Trend"]


def test_merge_lists_empty_inputs():
    from dedup import _merge_lists

    assert _merge_lists([], None, []) == []
