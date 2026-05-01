"""Propose new sources to fill gaps in the strategy knowledge base.

- Scans existing cards by (asset_class, strategy_family).
- Identifies cells with zero or very low coverage.
- Emits candidate URLs into sources/proposed.json for human review.

The web-search step is intentionally stubbed: we don't have a web search API
wired in, so this module emits a search *prompt* the user can run manually,
and accepts a `candidates` argument for programmatic injection (e.g. from tests
or from a future integration).
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from config import SOURCES_DIR, load_settings
from schema import StrategyCard

PROPOSED_PATH = SOURCES_DIR / "proposed.json"


@dataclass
class Gap:
    asset_class: str
    strategy_family: str
    count: int


@dataclass
class Proposal:
    gap: Gap
    search_prompt: str
    candidates: list[dict] = field(default_factory=list)  # [{url, justification}]
    status: str = "pending"  # pending | accepted | rejected


def _all_cards() -> list[StrategyCard]:
    s = load_settings()
    if not s.db_path.exists():
        return []
    con = sqlite3.connect(s.db_path)
    try:
        rows = con.execute("SELECT card_json FROM cards").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    return [StrategyCard.model_validate_json(r[0]) for r in rows]


def find_gaps(min_count: int = 3) -> list[Gap]:
    cards = _all_cards()
    counts = Counter()
    for c in cards:
        counts[(c.asset_class.value, c.strategy_family.value)] += 1

    asset_classes = {"equity", "etf", "futures", "fx", "crypto", "options", "fixed_income", "commodity"}
    families = {
        "momentum", "mean_reversion", "trend_following", "breakout", "pairs_stat_arb",
        "carry", "volatility", "event_driven", "market_making", "arbitrage", "macro", "factor",
    }
    gaps: list[Gap] = []
    for a in asset_classes:
        for f in families:
            c = counts.get((a, f), 0)
            if c < min_count:
                gaps.append(Gap(asset_class=a, strategy_family=f, count=c))
    gaps.sort(key=lambda g: g.count)
    return gaps


def _load_proposed() -> dict:
    if not PROPOSED_PATH.exists():
        return {"proposals": []}
    return json.loads(PROPOSED_PATH.read_text())


def _save_proposed(data: dict) -> None:
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSED_PATH.write_text(json.dumps(data, indent=2) + "\n")


def propose(
    *,
    min_count: int = 3,
    max_gaps: int = 10,
    injected_candidates: dict[tuple[str, str], list[dict]] | None = None,
) -> list[Proposal]:
    """Identify gaps and emit proposals. Existing pending/accepted/rejected
    proposals are preserved — new gaps append."""
    existing = _load_proposed()
    seen = {
        (p["gap"]["asset_class"], p["gap"]["strategy_family"]): p
        for p in existing.get("proposals", [])
    }

    new_proposals: list[Proposal] = []
    for gap in find_gaps(min_count=min_count)[:max_gaps]:
        key = (gap.asset_class, gap.strategy_family)
        if key in seen and seen[key].get("status") != "pending":
            continue
        search_prompt = (
            f"Find 3-5 high-quality public articles or docs that describe concrete "
            f"trading strategies in the {gap.strategy_family.replace('_', ' ')} family "
            f"for {gap.asset_class.replace('_', ' ')} assets. Prefer sources with "
            f"specific entry/exit rules and backtest results. Avoid marketing posts."
        )
        candidates = (injected_candidates or {}).get(key, [])
        new_proposals.append(Proposal(gap=gap, search_prompt=search_prompt, candidates=candidates))

    # Merge: keep all old records, append new pending ones.
    all_records = list(existing.get("proposals", []))
    for p in new_proposals:
        key = (p.gap.asset_class, p.gap.strategy_family)
        if key in seen:
            # Refresh the pending record with latest candidates.
            rec = seen[key]
            rec["candidates"] = p.candidates
            rec["search_prompt"] = p.search_prompt
        else:
            all_records.append(
                {
                    "gap": {"asset_class": p.gap.asset_class, "strategy_family": p.gap.strategy_family, "count": p.gap.count},
                    "search_prompt": p.search_prompt,
                    "candidates": p.candidates,
                    "status": p.status,
                }
            )
    _save_proposed({"proposals": all_records})
    return new_proposals
