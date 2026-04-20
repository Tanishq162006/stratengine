from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from decision_scorer import (
    DEFAULT_SCENARIOS,
    MissingHistoricalDataError,
    ScorerWeights,
    score_playbook,
)


GOOD_PLAYBOOK = {
    "name": "mean-rev SPY",
    "entry_checklist": [
        "RSI(2) < 10 at daily close",
        "Close > SMA(200)",
        "VIX < 35",
    ],
    "exit_checklist": {
        "take_profit": ["RSI(2) > 70 at daily close"],
        "stop_loss": ["Close < entry - 3 * ATR(14)"],
        "time_based": ["Exit after 10 trading days"],
    },
    "sizing_framework": {
        "method": "volatility_target",
        "per_trade_risk_pct": 0.01,
        "max_position_pct": 0.10,
    },
    "regime_detection": {
        "current_regime_rules": ["SPY > SMA(200)", "VIX < 35"],
        "invalidation_signals": ["SPY < SMA(200) for 3 days"],
    },
    "risk_protocol": {
        "max_position_pct": 0.10,
        "max_portfolio_drawdown_pct": 0.08,
        "correlation_limits": "max 2 concurrent",
    },
}


def test_score_without_scenarios_in_range():
    score = score_playbook(GOOD_PLAYBOOK, skip_scenarios=True)
    for v in (
        score.signal_clarity,
        score.risk_completeness,
        score.cognitive_load,
        score.regime_specificity,
        score.composite,
    ):
        assert 0.0 <= v <= 1.0
    assert score.historical_scenarios == 0.0


def test_weights_normalize_and_composite_math():
    w = ScorerWeights(
        signal_clarity=1.0,
        risk_completeness=1.0,
        cognitive_load=1.0,
        regime_specificity=1.0,
        historical_scenarios=0.0,
    )
    score = score_playbook(GOOD_PLAYBOOK, weights=w, skip_scenarios=True)
    # With no scenarios, composite should equal the mean of the other four
    # (since each weight is equal after normalization and skip_scenarios is on).
    manual = (
        score.signal_clarity
        + score.risk_completeness
        + score.cognitive_load
        + score.regime_specificity
    ) / 4.0
    assert abs(score.composite - manual) < 1e-9


def test_missing_historical_data_raises(tmp_path):
    with pytest.raises(MissingHistoricalDataError):
        score_playbook(GOOD_PLAYBOOK, data_dir=tmp_path)


def test_scenarios_use_local_csv(tmp_path: Path):
    # Build a minimal SPY CSV covering one scenario window.
    name, start, end = DEFAULT_SCENARIOS[1]  # 2022-rate-hikes
    dates = pd.date_range(start=start, end=end, freq="B")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": 100,
            "high": 101,
            "low": 99,
            "close": [100 + i * 0.1 for i in range(len(dates))],
            "volume": 0,
        }
    )
    df.to_csv(tmp_path / "SPY.csv", index=False)

    # Only run one scenario so we don't need every CSV.
    score = score_playbook(
        GOOD_PLAYBOOK,
        scenarios=[(name, start, end)],
        data_dir=tmp_path,
    )
    assert 0.0 <= score.historical_scenarios <= 1.0
    assert len(score.scenarios) == 1
    assert 0.0 <= score.composite <= 1.0
