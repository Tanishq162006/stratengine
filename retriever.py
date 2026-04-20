"""Retrieval layer. Constraint-aware card retrieval."""
from __future__ import annotations

from typing import Union

from rich.console import Console

from indexer import load_card, query
from schema import RoundContext, StrategyCard, TradingContext

console = Console()

ContextT = Union[RoundContext, TradingContext]


def _query_text(ctx: ContextT) -> str:
    if isinstance(ctx, RoundContext):
        parts = [
            ctx.round_name,
            ctx.objective,
            ctx.objective_notes or "",
            ctx.regime_hint or "",
            " ".join(ctx.preferred_strategy_families),
            ctx.notes or "",
        ]
    else:
        parts = [
            ctx.trader_style,
            ctx.objective,
            ctx.current_regime.value,
            ctx.regime_notes or "",
            " ".join(ctx.preferred_strategy_families),
            ctx.question or "",
            ctx.notes or "",
        ]
    return " | ".join(p for p in parts if p)


def _build_where(ctx: ContextT) -> dict:
    conditions: list[dict] = []
    asset_vals = [a.value for a in ctx.asset_classes]
    if asset_vals:
        conditions.append({"asset_class": {"$in": asset_vals}})
    # timeframe exact match OR 'multi'
    conditions.append(
        {"$or": [{"timeframe": {"$eq": ctx.timeframe.value}}, {"timeframe": {"$eq": "multi"}}]}
    )
    if ctx.excluded_strategy_families:
        conditions.append(
            {"strategy_family": {"$nin": list(ctx.excluded_strategy_families)}}
        )
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def retrieve(ctx: ContextT, top_k: int = 10) -> list[StrategyCard]:
    where = _build_where(ctx)
    qtext = _query_text(ctx)
    hits = query(qtext, where=where, top_k=top_k)
    cards: list[StrategyCard] = []
    for h in hits:
        c = load_card(h["card_id"])
        if c:
            cards.append(c)
    # preferred families rank boost: stable sort preferred to top
    prefs = set(ctx.preferred_strategy_families)
    if prefs:
        cards.sort(key=lambda c: 0 if c.strategy_family.value in prefs else 1)
    console.log(f"Retrieved {len(cards)} cards for context")
    return cards
