"""RoundContext — constraints for an algorithmic competition or systematic trading round."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .strategy_card import AssetClass, Timeframe


class RoundContext(BaseModel):
    competition: Literal[
        "imc_prosperity", "worldquant_iqc", "quantconnect", "custom"
    ] = "custom"
    round_name: str = "Round 1"

    # Universe
    asset_classes: list[AssetClass]
    symbols: list[str] = Field(default_factory=list)
    timeframe: Timeframe

    # Simulation window
    backtest_start: str = Field(..., description="ISO date, inclusive.")
    backtest_end: str = Field(..., description="ISO date, inclusive.")
    out_of_sample_start: str | None = None
    out_of_sample_end: str | None = None

    # Hard constraints
    max_drawdown: float | None = Field(
        default=None, description="Fractional, e.g. 0.20 for 20%."
    )
    min_sharpe: float | None = None
    max_turnover: float | None = None
    transaction_cost_bps: float = Field(
        default=5.0, description="Round-trip cost in basis points, default 5bps."
    )
    slippage_bps: float = Field(default=2.0)
    starting_capital: float = 100_000.0
    max_leverage: float = 1.0

    # Soft goals
    objective: Literal["sharpe", "sortino", "calmar", "total_return", "custom"] = "sharpe"
    objective_notes: str | None = None

    # Retrieval hints
    preferred_strategy_families: list[str] = Field(default_factory=list)
    excluded_strategy_families: list[str] = Field(default_factory=list)
    regime_hint: str | None = None

    # Misc
    notes: str | None = None
