"""playbook_generator — mocked LLM."""
from __future__ import annotations

import json
from unittest.mock import patch

from schema import AssetClass, Timeframe, TradingContext

_GOOD = {
    "playbooks": [
        {
            "name": f"Playbook {i}",
            "thesis": "test thesis",
            "strategy_family": "mean_reversion",
            "asset_class": "equity",
            "timeframe": "1d",
            "entry_checklist": ["RSI(2) < 10", "Close > SMA(200)"],
            "exit_checklist": {
                "take_profit": ["RSI(2) > 70"],
                "stop_loss": ["Close < entry - 3*ATR(14)"],
                "time_based": ["Exit after 10 days"],
            },
            "sizing_framework": {
                "method": "volatility_target",
                "per_trade_risk_pct": 0.01,
                "max_position_pct": 0.1,
                "notes": "halve if VIX > 25",
            },
            "regime_detection": {
                "current_regime_rules": ["SPY > SMA(200)"],
                "invalidation_signals": ["SPY < SMA(200) 3 days"],
            },
            "risk_protocol": {
                "max_position_pct": 0.1,
                "max_portfolio_drawdown_pct": 0.08,
                "correlation_limits": "max 2 concurrent",
                "circuit_breakers": ["halt if DD > 5% in 5d"],
            },
            "source_card_ids": [f"card-{i}"],
        }
        for i in range(3)
    ]
}


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


def _mk_client(payload):
    class _C:
        def __init__(self, *a, **kw):
            self.messages = self

        def create(self, **kwargs):
            return _Resp(json.dumps(payload))

    return _C


def _ctx() -> TradingContext:
    return TradingContext(
        asset_classes=[AssetClass.EQUITY],
        timeframe=Timeframe.DAILY,
        question="SPY setup?",
    )


def test_generate_playbooks_returns_valid(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch("playbook_generator.Anthropic", _mk_client(_GOOD)):
        from playbook_generator import generate_playbooks

        out = generate_playbooks(_ctx(), cards=[])
    assert len(out["playbooks"]) == 3
    assert out["warnings"] == []
    pb = out["playbooks"][0]
    for field in (
        "entry_checklist",
        "exit_checklist",
        "sizing_framework",
        "regime_detection",
        "risk_protocol",
        "source_card_ids",
    ):
        assert field in pb


def test_generate_playbooks_filters_invalid(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    bad = {
        "playbooks": [
            {"name": "partial", "entry_checklist": ["x"]},  # missing required fields
            _GOOD["playbooks"][0],
        ]
    }
    with patch("playbook_generator.Anthropic", _mk_client(bad)):
        from playbook_generator import generate_playbooks

        out = generate_playbooks(_ctx(), cards=[])
    assert len(out["playbooks"]) == 1
    assert any("missing" in w for w in out["warnings"])
