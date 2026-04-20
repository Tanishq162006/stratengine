"""Retriever tests. These run against a temporary SQLite + Chroma store so the
real index isn't touched."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_stores(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="stratengine_test_"))
    monkeypatch.setenv("STRATENGINE_DB_PATH", str(d / "test.db"))
    monkeypatch.setenv("STRATENGINE_CHROMA_PATH", str(d / "chroma"))
    # force fresh config read everywhere that caches
    yield d


def _make_card(**overrides):
    from schema import (
        AssetClass,
        Indicator,
        MarketRegime,
        StrategyCard,
        StrategyFamily,
        Timeframe,
    )
    from schema.strategy_card import PositionSizing, RuleSet

    base = dict(
        card_id=overrides.get("card_id", "c1"),
        title=overrides.get("title", "RSI2 SPY"),
        source="test",
        url="https://example.com/a",
        asset_class=overrides.get("asset_class", AssetClass.EQUITY),
        strategy_family=overrides.get("strategy_family", StrategyFamily.MEAN_REVERSION),
        market_regime=overrides.get("market_regime", MarketRegime.MEAN_REVERTING),
        timeframe=overrides.get("timeframe", Timeframe.DAILY),
        indicators_used=[Indicator(name="RSI", params={"period": 2})],
        entry_rules=RuleSet(description="RSI2 < 10", conditions=["RSI(2) < 10"]),
        exit_rules=RuleSet(description="RSI2 > 70", conditions=["RSI(2) > 70"]),
        risk_rules=RuleSet(description="3 ATR stop"),
        position_sizing=PositionSizing(method="volatility_target"),
        confidence=0.7,
    )
    return StrategyCard(**base)


def test_retriever_filters_by_asset_class_and_timeframe(tmp_stores):
    from schema import AssetClass, RoundContext, StrategyFamily, Timeframe
    from indexer import add_card
    from retriever import retrieve

    eq_card = _make_card(card_id="eq1", title="SPY mean reversion", asset_class=AssetClass.EQUITY, timeframe=Timeframe.DAILY)
    fx_card = _make_card(card_id="fx1", title="EURUSD carry", asset_class=AssetClass.FX, timeframe=Timeframe.HOUR_1, strategy_family=StrategyFamily.CARRY)
    add_card(eq_card)
    add_card(fx_card)

    ctx = RoundContext(
        round_name="t",
        asset_classes=[AssetClass.EQUITY],
        timeframe=Timeframe.DAILY,
        backtest_start="2020-01-01",
        backtest_end="2022-12-31",
    )
    cards = retrieve(ctx, top_k=5)
    ids = [c.card_id for c in cards]
    assert "eq1" in ids
    assert "fx1" not in ids
