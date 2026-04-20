"""Retrieval layer. Constraint-aware card retrieval."""
from __future__ import annotations

from typing import Union

from rich.console import Console

from indexer import load_card, query
from schema import RoundContext, StrategyCard, TradingContext
from source_quality import NEUTRAL_DEFAULT, score_for

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


def retrieve(
    ctx: ContextT, top_k: int = 10, max_per_cluster: int = 2
) -> list[StrategyCard]:
    where = _build_where(ctx)
    qtext = _query_text(ctx)
    # Over-fetch 3x so source-quality reweighting + cluster diversification have headroom.
    raw_hits = query(qtext, where=where, top_k=top_k * 3)

    scored: list[tuple[float, StrategyCard]] = []
    for h in raw_hits:
        c = load_card(h["card_id"])
        if not c:
            continue
        distance = h.get("distance") or 0.0
        sq = score_for(c.source) - NEUTRAL_DEFAULT
        composite = -distance + 0.15 * sq
        scored.append((composite, c))
    scored.sort(key=lambda t: t[0], reverse=True)

    # Diversify across clusters so top-N isn't 5 near-identical mean-reversion cards.
    per_cluster: dict[tuple[str, str, str], int] = {}
    cards: list[StrategyCard] = []
    for _, c in scored:
        key = (c.strategy_family.value, c.asset_class.value, c.timeframe.value)
        if per_cluster.get(key, 0) >= max_per_cluster:
            continue
        per_cluster[key] = per_cluster.get(key, 0) + 1
        cards.append(c)
        if len(cards) >= top_k:
            break

    prefs = set(ctx.preferred_strategy_families)
    if prefs:
        cards.sort(key=lambda c: 0 if c.strategy_family.value in prefs else 1)
    console.log(f"Retrieved {len(cards)} cards (source-weighted, cluster-diversified)")
    return cards
