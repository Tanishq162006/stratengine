"""patcher — mocked Anthropic client + injected evaluate_fn."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch as pmock

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


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


def _mk_client(patched_code):
    class _C:
        def __init__(self, *a, **kw):
            self.messages = self

        def create(self, **kwargs):
            return _Resp(patched_code)

    return _C


def test_patch_succeeds_on_first_attempt(tmp_db, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from patcher import patch

    attempts = {"n": 0}

    def fake_eval(code):
        attempts["n"] += 1
        # First patch is good.
        return True, ""

    with pmock("patcher.Anthropic", _mk_client("print('fixed')")):
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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from patcher import patch

    def fake_eval(code):
        return False, "still broken"

    with pmock("patcher.Anthropic", _mk_client("still broken code")):
        result = patch(
            code="broken",
            error="initial error",
            candidate={"name": "cand-B"},
            round_ctx=_ctx(),
            evaluate_fn=fake_eval,
        )
    assert result.success is False
    assert result.attempts == 3
