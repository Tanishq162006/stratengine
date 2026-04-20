"""TradingContext — constraints for a discretionary/manual trading query."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .strategy_card import AssetClass, MarketRegime, Timeframe


class TradingContext(BaseModel):
    # Who is asking
    trader_style: Literal[
        "intraday", "swing", "position", "long_term_investor", "macro", "discretionary"
    ] = "swing"
    risk_tolerance: Literal["low", "medium", "high"] = "medium"

    # What they're trading
    asset_classes: list[AssetClass]
    symbols: list[str] = Field(default_factory=list)
    timeframe: Timeframe

    # Current market view
    current_regime: MarketRegime = MarketRegime.ANY
    regime_notes: str | None = None

    # Goals
    objective: Literal[
        "entry_signal", "exit_signal", "thesis_check", "risk_framework", "playbook"
    ] = "playbook"
    horizon_days: int | None = None

    # Portfolio constraints
    max_position_pct: float = Field(default=0.10, ge=0.0, le=1.0)
    max_portfolio_risk_pct: float = Field(default=0.02, ge=0.0, le=1.0)

    # Retrieval hints
    preferred_strategy_families: list[str] = Field(default_factory=list)
    excluded_strategy_families: list[str] = Field(default_factory=list)

    # Free-form
    question: str | None = Field(
        default=None, description="Plain-English question from the trader."
    )
    notes: str | None = None
