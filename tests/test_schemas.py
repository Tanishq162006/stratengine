from datetime import datetime

from schema import (
    AssetClass,
    Indicator,
    MarketRegime,
    RoundContext,
    StrategyCard,
    StrategyFamily,
    Timeframe,
    TradingContext,
)
from schema.strategy_card import ManualPlaybook, PositionSizing, RuleSet


def _make_card() -> StrategyCard:
    return StrategyCard(
        card_id="test-1",
        title="RSI(2) Mean Reversion on SPY",
        source="QuantStart",
        url="https://www.quantstart.com/articles/test-article/",
        asset_class=AssetClass.EQUITY,
        strategy_family=StrategyFamily.MEAN_REVERSION,
        market_regime=MarketRegime.MEAN_REVERTING,
        timeframe=Timeframe.DAILY,
        indicators_used=[Indicator(name="RSI", params={"period": 2}, purpose="oversold signal")],
        entry_rules=RuleSet(
            description="Enter long when RSI(2) < 10 and price > 200-day SMA.",
            conditions=["RSI(2) < 10", "Close > SMA(200)"],
        ),
        exit_rules=RuleSet(description="Exit when RSI(2) > 70.", conditions=["RSI(2) > 70"]),
        risk_rules=RuleSet(
            description="Stop loss 3 ATR below entry.",
            conditions=["stop = entry - 3 * ATR(14)"],
        ),
        position_sizing=PositionSizing(method="volatility_target", max_leverage=1.0),
        claims_made=["Sharpe > 1.5 on 2010-2020 SPY"],
        failure_modes=["Underperforms in strong downtrends"],
        code_hints=["if rsi < 10 and close > sma200: buy"],
        confidence=0.7,
        manual_playbook=ManualPlaybook(
            checklist=["RSI(2) below 10", "Above 200-day SMA", "VIX below 35"],
            decision_tree="if RSI(2)<10 and Close>SMA(200) and VIX<35 then long; exit when RSI(2)>70",
            signal_summary="Short-term oversold bounces in uptrends, gated by VIX regime.",
            regime_notes="Works in mean-reverting bull markets; fails in strong downtrends.",
            sizing_framework="Volatility-targeted 0.5% daily dollar vol per trade, max 10% position.",
            risk_protocol="3 ATR stop below entry, max 2% portfolio risk per trade, no stacking correlated mean-reversion trades.",
        ),
        tags=["spy", "rsi2"],
    )


def test_strategy_card_roundtrip():
    c = _make_card()
    dumped = c.model_dump_json()
    loaded = StrategyCard.model_validate_json(dumped)
    assert loaded.card_id == "test-1"
    assert loaded.asset_class is AssetClass.EQUITY
    assert loaded.indicators_used[0].name == "RSI"


def test_round_context_minimal():
    rc = RoundContext(
        round_name="test",
        asset_classes=[AssetClass.EQUITY],
        timeframe=Timeframe.DAILY,
        backtest_start="2018-01-01",
        backtest_end="2022-12-31",
    )
    assert rc.transaction_cost_bps == 5.0
    assert rc.objective == "sharpe"


def test_trading_context_minimal():
    tc = TradingContext(
        asset_classes=[AssetClass.EQUITY],
        timeframe=Timeframe.DAILY,
        question="Is SPY setup for a mean-reversion long?",
    )
    assert tc.trader_style == "swing"
    assert tc.risk_tolerance == "medium"


def test_empty_title_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StrategyCard(
            card_id="x",
            title="   ",
            source="q",
            url="https://example.com",
            asset_class=AssetClass.EQUITY,
            strategy_family=StrategyFamily.MOMENTUM,
            timeframe=Timeframe.DAILY,
            entry_rules=RuleSet(description="a"),
            exit_rules=RuleSet(description="a"),
            risk_rules=RuleSet(description="a"),
        )
