"""StrategyCard — the canonical structured representation of a trading strategy
extracted from a source article or doc."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    FUTURES = "futures"
    FX = "fx"
    CRYPTO = "crypto"
    OPTIONS = "options"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    MULTI_ASSET = "multi_asset"
    UNKNOWN = "unknown"


class StrategyFamily(str, Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"
    BREAKOUT = "breakout"
    PAIRS_STAT_ARB = "pairs_stat_arb"
    CARRY = "carry"
    VOLATILITY = "volatility"
    EVENT_DRIVEN = "event_driven"
    MARKET_MAKING = "market_making"
    ARBITRAGE = "arbitrage"
    MACRO = "macro"
    FACTOR = "factor"
    ML_PREDICTIVE = "ml_predictive"
    DISCRETIONARY = "discretionary"
    OTHER = "other"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"
    ANY = "any"


class Timeframe(str, Enum):
    TICK = "tick"
    SECOND = "second"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1M"
    MULTI = "multi"


class Indicator(BaseModel):
    name: str = Field(..., description="E.g. 'RSI', 'EMA', 'ATR', 'Bollinger Bands'.")
    params: dict[str, float | int | str] = Field(default_factory=dict)
    purpose: str | None = Field(
        default=None, description="What role this indicator plays in the strategy."
    )


class RuleSet(BaseModel):
    """A set of natural-language + semi-structured rules."""

    description: str
    conditions: list[str] = Field(default_factory=list)


class PositionSizing(BaseModel):
    method: Literal[
        "fixed_fractional",
        "kelly",
        "volatility_target",
        "equal_weight",
        "risk_parity",
        "fixed_notional",
        "discretionary",
        "other",
    ] = "fixed_fractional"
    notes: str | None = None
    max_leverage: float | None = None


class ManualPlaybook(BaseModel):
    """Discretionary trader-facing summary."""

    thesis: str
    signal_checklist: list[str] = Field(default_factory=list)
    confirmation: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class StrategyCard(BaseModel):
    # Identity
    card_id: str = Field(..., description="Stable ID, e.g. sha1 of source URL + title.")
    title: str
    source: str = Field(..., description="Human-readable source name, e.g. 'QuantStart'.")
    url: HttpUrl
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    # Classification
    asset_class: AssetClass
    strategy_family: StrategyFamily
    market_regime: MarketRegime = MarketRegime.ANY
    timeframe: Timeframe
    indicators_used: list[Indicator] = Field(default_factory=list)

    # Rules
    entry_rules: RuleSet
    exit_rules: RuleSet
    risk_rules: RuleSet
    position_sizing: PositionSizing = Field(default_factory=PositionSizing)

    # Evidence
    claims_made: list[str] = Field(
        default_factory=list,
        description="Performance/behavior claims in the article (Sharpe X, beats Y, etc.).",
    )
    failure_modes: list[str] = Field(
        default_factory=list,
        description="Known failure modes, regime sensitivities, or caveats.",
    )
    code_hints: list[str] = Field(
        default_factory=list,
        description="Pseudocode, formulas, or implementation notes from the article.",
    )

    # Meta
    confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Extractor's confidence the card faithfully represents the article.",
    )
    manual_playbook: ManualPlaybook | None = None
    tags: list[str] = Field(default_factory=list)
    raw_excerpt: str | None = Field(
        default=None, description="Short quoted snippet for provenance."
    )

    @field_validator("title", "source")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()
