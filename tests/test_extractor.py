"""Extractor tests. The LLM call is monkeypatched — no real API calls."""
from __future__ import annotations

from unittest.mock import patch


_FAKE_JSON = """{
  "card_id": "abc123",
  "title": "RSI2 Mean Reversion",
  "source": "TestSource",
  "url": "https://example.com/a",
  "asset_class": "equity",
  "strategy_family": "mean_reversion",
  "market_regime": "mean_reverting",
  "timeframe": "1d",
  "indicators_used": [{"name": "RSI", "params": {"period": 2}, "purpose": "oversold"}],
  "entry_rules": {"description": "RSI(2) < 10 and above 200 SMA", "conditions": ["RSI(2) < 10", "Close > SMA(200)"]},
  "exit_rules": {"description": "RSI(2) > 70", "conditions": ["RSI(2) > 70"]},
  "risk_rules": {"description": "3 ATR stop", "conditions": ["stop = entry - 3*ATR(14)"]},
  "position_sizing": {"method": "volatility_target", "max_leverage": 1.0},
  "claims_made": ["Sharpe > 1.5"],
  "failure_modes": ["weak in strong downtrends"],
  "code_hints": ["if rsi < 10 and close > sma200: buy"],
  "confidence": 0.7,
  "manual_playbook": null,
  "tags": ["rsi2", "spy"],
  "raw_excerpt": "Buy when RSI(2) is below 10 and close is above the 200-day SMA."
}"""


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResp:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def create(self, **kwargs):
        return _FakeResp(_FAKE_JSON)


class _FakeClient:
    def __init__(self, *a, **kw):
        self.messages = _FakeMessages()


def test_extract_card_parses_json_into_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch("extractor.Anthropic", _FakeClient):
        from extractor import extract_card

        card = extract_card("some article body", "TestSource", "https://example.com/a")
    assert card is not None
    assert card.title == "RSI2 Mean Reversion"
    assert card.confidence == 0.7
    assert card.indicators_used[0].name == "RSI"


def test_extract_card_handles_skip(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    class _SkipMessages:
        def create(self, **kwargs):
            return _FakeResp('{"skip": true, "reason": "not a strategy"}')

    class _SkipClient:
        def __init__(self, *a, **kw):
            self.messages = _SkipMessages()

    with patch("extractor.Anthropic", _SkipClient):
        from extractor import extract_card
        card = extract_card("an overview article", "TestSource", "https://example.com/b")
    assert card is None
