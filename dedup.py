"""Near-duplicate merge + clustering for the StrategyCard library.

Dedup rules:
  - Compare cards with the same (asset_class, strategy_family, timeframe).
  - Cosine similarity on their embedding document (same string the indexer stores).
  - If sim >= threshold (default 0.92), keep the higher-confidence card; merge
    unique `claims_made`, `failure_modes`, `code_hints`, `tags` from the loser.
  - The losing card is removed from SQLite and Chroma.

Clusters:
  - (strategy_family, asset_class, timeframe) groups, with a representative card
    (highest confidence) per cluster.
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import load_settings
from indexer import _embed_text  # reuse same document text
from schema import StrategyCard

DEFAULT_SIMILARITY_THRESHOLD = 0.92


@dataclass
class DedupReport:
    groups_examined: int
    merges: int
    removed_card_ids: list[str]


@dataclass
class Cluster:
    key: tuple[str, str, str]  # (strategy_family, asset_class, timeframe)
    card_ids: list[str]
    representative_id: str


def _all_cards() -> list[StrategyCard]:
    s = load_settings()
    con = sqlite3.connect(s.db_path)
    rows = con.execute("SELECT card_json FROM cards").fetchall()
    con.close()
    return [StrategyCard.model_validate_json(r[0]) for r in rows]


def _chroma_collection():
    s = load_settings()
    s.chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(s.chroma_path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client.get_or_create_collection("strategy_cards")


def _get_embeddings(ids: list[str]) -> dict[str, list[float]]:
    coll = _chroma_collection()
    res = coll.get(ids=ids, include=["embeddings"])
    out: dict[str, list[float]] = {}
    embs = res.get("embeddings") or []
    for i, _id in enumerate(res.get("ids", [])):
        if i < len(embs) and embs[i] is not None:
            out[_id] = list(embs[i])
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _merge_lists(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for item in lst or []:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(item)
    return out


def _delete_card(card_id: str) -> None:
    s = load_settings()
    with sqlite3.connect(s.db_path) as con:
        con.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
    try:
        _chroma_collection().delete(ids=[card_id])
    except Exception:
        pass


def _upsert_card(card: StrategyCard) -> None:
    s = load_settings()
    with sqlite3.connect(s.db_path) as con:
        con.execute(
            """UPDATE cards SET title=?, source=?, url=?, confidence=?, tags=?, card_json=?
               WHERE card_id=?""",
            (
                card.title,
                card.source,
                str(card.url),
                card.confidence,
                json.dumps(card.tags),
                card.model_dump_json(),
                card.card_id,
            ),
        )
    coll = _chroma_collection()
    coll.upsert(
        ids=[card.card_id],
        documents=[_embed_text(card)],
        metadatas=[
            {
                "asset_class": card.asset_class.value,
                "strategy_family": card.strategy_family.value,
                "market_regime": card.market_regime.value,
                "timeframe": card.timeframe.value,
                "source": card.source,
                "confidence": card.confidence,
            }
        ],
    )


def merge_duplicates(threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> DedupReport:
    cards = _all_cards()
    groups: dict[tuple[str, str, str], list[StrategyCard]] = defaultdict(list)
    for c in cards:
        groups[(c.strategy_family.value, c.asset_class.value, c.timeframe.value)].append(c)

    merges = 0
    removed: list[str] = []
    groups_examined = 0

    for key, group in groups.items():
        if len(group) < 2:
            continue
        groups_examined += 1
        embs = _get_embeddings([c.card_id for c in group])
        # Sort desc by confidence so winners are processed first.
        group.sort(key=lambda c: c.confidence, reverse=True)
        alive: list[StrategyCard] = []
        for cand in group:
            dup_winner = None
            for winner in alive:
                if cand.card_id not in embs or winner.card_id not in embs:
                    continue
                if _cosine(embs[cand.card_id], embs[winner.card_id]) >= threshold:
                    dup_winner = winner
                    break
            if dup_winner is None:
                alive.append(cand)
                continue
            # Merge unique fields from loser into winner.
            merged = dup_winner.model_copy(
                update={
                    "claims_made": _merge_lists(dup_winner.claims_made, cand.claims_made),
                    "failure_modes": _merge_lists(dup_winner.failure_modes, cand.failure_modes),
                    "code_hints": _merge_lists(dup_winner.code_hints, cand.code_hints),
                    "tags": _merge_lists(dup_winner.tags, cand.tags),
                }
            )
            _upsert_card(merged)
            _delete_card(cand.card_id)
            # Reflect merged fields so further iterations in this loop see them.
            for i, w in enumerate(alive):
                if w.card_id == dup_winner.card_id:
                    alive[i] = merged
                    break
            removed.append(cand.card_id)
            merges += 1

    return DedupReport(groups_examined=groups_examined, merges=merges, removed_card_ids=removed)


def clusters() -> list[Cluster]:
    cards = _all_cards()
    buckets: dict[tuple[str, str, str], list[StrategyCard]] = defaultdict(list)
    for c in cards:
        buckets[(c.strategy_family.value, c.asset_class.value, c.timeframe.value)].append(c)
    out: list[Cluster] = []
    for key, group in buckets.items():
        group.sort(key=lambda c: c.confidence, reverse=True)
        out.append(
            Cluster(
                key=key,
                card_ids=[c.card_id for c in group],
                representative_id=group[0].card_id,
            )
        )
    out.sort(key=lambda c: len(c.card_ids), reverse=True)
    return out


def cluster_of(card: StrategyCard) -> tuple[str, str, str]:
    return (card.strategy_family.value, card.asset_class.value, card.timeframe.value)
