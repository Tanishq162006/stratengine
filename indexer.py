"""Indexing layer. SQLite for structured metadata, Chroma for embeddings."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from rich.console import Console

from config import CARDS_DIR, load_settings
from schema import StrategyCard

console = Console()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    strategy_family TEXT NOT NULL,
    market_regime TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    confidence REAL NOT NULL,
    tags TEXT NOT NULL,
    card_json TEXT NOT NULL,
    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cards_asset ON cards(asset_class);
CREATE INDEX IF NOT EXISTS idx_cards_family ON cards(strategy_family);
CREATE INDEX IF NOT EXISTS idx_cards_timeframe ON cards(timeframe);
"""


def _conn(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.executescript(_SCHEMA)
    return con


def _chroma(chroma_path: Path):
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(chroma_path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    return client.get_or_create_collection("strategy_cards")


def _embed_text(card: StrategyCard) -> str:
    parts = [
        card.title,
        card.strategy_family.value,
        card.asset_class.value,
        card.market_regime.value,
        card.timeframe.value,
        card.entry_rules.description,
        card.exit_rules.description,
        card.risk_rules.description,
        " ".join(card.claims_made),
        " ".join(card.failure_modes),
        " ".join(i.name for i in card.indicators_used),
        " ".join(card.tags),
    ]
    return "\n".join(p for p in parts if p)


def add_card(card: StrategyCard) -> None:
    settings = load_settings()
    with _conn(settings.db_path) as con:
        con.execute(
            """INSERT OR REPLACE INTO cards
               (card_id, title, source, url, asset_class, strategy_family,
                market_regime, timeframe, confidence, tags, card_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card.card_id,
                card.title,
                card.source,
                str(card.url),
                card.asset_class.value,
                card.strategy_family.value,
                card.market_regime.value,
                card.timeframe.value,
                card.confidence,
                json.dumps(card.tags),
                card.model_dump_json(),
            ),
        )
    coll = _chroma(settings.chroma_path)
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


def index_all() -> int:
    count = 0
    for p in sorted(CARDS_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            card = StrategyCard.model_validate_json(p.read_text())
        except Exception as e:
            console.log(f"[red]invalid card[/] {p.name}: {e}")
            continue
        add_card(card)
        count += 1
        console.log(f"[green]indexed[/] {card.card_id} {card.title}")
    console.print(f"[bold green]Indexed[/] {count} cards")
    return count


def query(text: str, where: dict | None = None, top_k: int = 10) -> list[dict]:
    settings = load_settings()
    coll = _chroma(settings.chroma_path)
    res = coll.query(query_texts=[text], n_results=top_k, where=where or None)
    out: list[dict] = []
    for i in range(len(res["ids"][0])):
        out.append(
            {
                "card_id": res["ids"][0][i],
                "distance": res["distances"][0][i] if res.get("distances") else None,
                "metadata": res["metadatas"][0][i],
                "document": res["documents"][0][i],
            }
        )
    return out


def load_card(card_id: str) -> StrategyCard | None:
    settings = load_settings()
    with _conn(settings.db_path) as con:
        row = con.execute(
            "SELECT card_json FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone()
    if not row:
        return None
    return StrategyCard.model_validate_json(row[0])


if __name__ == "__main__":
    index_all()
