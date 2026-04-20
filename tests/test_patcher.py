"""patcher — llm_client mocked + injected evaluate_fn."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from schema import AssetClass, RoundContext, Timeframe


@pytest.fixture()
def tmp_db(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="patch_test_"))
    monkeypatch.setenv("STRATENGINE_DB_PATH", str(d / "test.db"))
    yield d


def _ctx() -> RoundContext:
    return RoundContext(
        round_name="t",
        asset_classes=[AssetClass.EQUITY],
        timeframe=Timeframe.DAILY,
        backtest_start="2020-01-01",
        backtest_end="2020-12-31",
    )


def test_patch_succeeds_on_first_attempt(tmp_db, monkeypatch):
    from patcher import patch

    monkeypatch.setattr("llm_client.complete", lambda **kw: "print('fixed')")

    attempts = {"n": 0}

    def fake_eval(code):
        attempts["n"] += 1
        return True, ""

    result = patch(
        code="print('broken)",
        error="SyntaxError: EOL while scanning string literal",
        candidate={"name": "cand-A"},
        round_ctx=_ctx(),
        evaluate_fn=fake_eval,
    )
    assert result.success is True
    assert result.attempts == 1


def test_patch_gives_up_after_three_attempts(tmp_db, monkeypatch):
    from patcher import patch

    monkeypatch.setattr("llm_client.complete", lambda **kw: "still broken code")

    def fake_eval(code):
        return False, "still broken"

    result = patch(
        code="broken",
        error="initial error",
        candidate={"name": "cand-B"},
        round_ctx=_ctx(),
        evaluate_fn=fake_eval,
    )
    assert result.success is False
    assert result.attempts == 3
